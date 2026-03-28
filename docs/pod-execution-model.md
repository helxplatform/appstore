# AppStore Pod Execution Model

A conceptual guide to the flow that produces Kubernetes Pods when a user launches an application.

---

## Overview

AppStore is a Django-based platform that lets authenticated users launch containerized applications as Kubernetes workloads. The user selects an app, requests resources, and receives a URL to a running instance. Under the hood, five layered subsystems convert that request into a running Pod.

```
HTTP Request
    │
    ▼
┌─────────────────────┐
│   REST API Layer    │  validate, auth, resource bounds
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  App Registry Layer │  resolve docker-compose spec from metadata
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  System Model Layer │  parse spec → System + Container objects
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  K8s Emission Layer │  render Jinja2 templates → manifests
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Kubernetes Client  │  create Deployment, Service, NetworkPolicy
└─────────────────────┘
         │
         ▼
    Running Pod
```

---

## Layer 1 — REST API

**Key files:** `appstore/api/v1/views.py`, `appstore/api/v1/models.py`, `appstore/api/v1/serializers.py`

### Entry point

`POST /api/v1/instances/` is handled by `InstanceViewSet.create()`.

### What happens here

1. **Deserialize** the request body into an `InstanceSerializer`, which requires `app_id` plus optional resource overrides (`cpus`, `gpus`, `memory`, `ephemeralStorage`).
2. **Fetch app metadata** from the `TychoContext` singleton (Layer 2) to learn the app's min/max resource bounds.
3. **Validate resources** — CPU, GPU, memory, and ephemeral storage are each checked against the app's configured limits. Out-of-range values return HTTP 400.
4. **Build a `ResourceRequest`** that carries both `limits` (hard caps) and `reservations` (scheduler hints). Memory is commonly halved for the reservation to reduce scheduling friction.
5. **Create a `UserIdentityToken`** — a 256-char random token stored in the DB that the app uses to authenticate callbacks to AppStore.
6. **Create a `Principal`** wrapping username + token + OAuth access/refresh tokens.
7. **Call `tycho.start(principal, app_id, resource_request, host, extra_env)`** → Layers 2–5.
8. **Return an `InstanceSpec`** with the app URL, system ID (`sid`), and resource summary.

### Key data structures

| Object | Source | Role |
|--------|--------|------|
| `ResourceRequest` | `api/v1/models.py` | Carries limits + reservations |
| `Principal` | `tycho/context.py` | Carries user identity for pod env vars |
| `UserIdentityToken` | `core/models.py` | Persisted auth token mapped to running sid |
| `InstanceSpec` | `api/v1/models.py` | Response: URL, sid, resources |

---

## Layer 2 — App Registry

**Key file:** `appstore/tycho/context.py`

### Role

Translates an `app_id` string into a concrete `docker-compose`-style specification that describes containers, ports, environment variables, and resource defaults.

### Context factory

```python
# views.py (module level)
contextFactory = ContextFactory()
tycho = contextFactory.get(
    context_type=settings.TYCHO_MODE,          # "live" | "null"
    product=settings.APPLICATION_BRAND,
    tycho_config_url=settings.EXTERNAL_TYCHO_APP_REGISTRY_REPO
)
```

`ContextFactory` is a singleton. In `"null"` mode it returns a stub; in `"live"` mode it returns a `TychoContext`.

### Registry loading (`_grok`)

On startup, `TychoContext._grok()` loads `tycho/conf/app-registry.yaml` (or clones an external Git repo when `EXTERNAL_TYCHO_APP_REGISTRY_ENABLED=true`). The registry maps each `app_id` to:

- A URL for the app's `docker-compose.yaml` (optionally in a remote git repo)
- Default environment variable settings (`.env` file)
- Security context defaults (UID, GID, fsGroup)
- Branding / product context (which apps are visible per product)

### Spec resolution on `start()`

When `TychoContext.start()` is called it:

1. Calls `get_spec(app_id)` → downloads and parses the app's `docker-compose.yaml`.
2. Calls `get_settings(app_id)` → loads the matching `.env` file into a dict.
3. Merges the caller's `ResourceRequest` over the spec's own `deploy.resources` stanza.
4. Injects identity env vars (`access_token`, `refresh_token`, `REMOTE_USER`, `IDENTITY_TOKEN`).
5. Applies security context (`runAsUser`, `runAsGroup`, `fsGroup`) from registry defaults.
6. Passes the fully assembled request dict to `TychoClient.start()` (Layer 3).

---

## Layer 3 — System Model

**Key file:** `appstore/tycho/model.py`

### Role

Converts the raw dict (docker-compose YAML + merged config) into typed Python objects that the template engine (Layer 4) can consume without any further string manipulation.

### Parsing (`System.parse`)

`System.parse(spec_dict)` iterates over `services` in the docker-compose structure and constructs:

```
System
├── identifier      — UUID generated at parse time (the "tycho-guid" label)
├── name            — "<app_id>-<short_uuid>"
├── namespace       — from settings.NAMESPACE
├── serviceaccount  — K8s service account for the pod
├── security_context — {run_as_user, run_as_group, fs_group}
├── env             — merged environment variables dict
├── volumes         — PVC mount specifications
└── containers[]
    ├── name
    ├── image
    ├── command
    ├── env         — container-level overrides
    ├── limits      — {cpus, memory, gpus, ephemeral_storage}
    ├── requests    — {cpus, memory}
    ├── ports
    ├── liveness_probe
    └── readiness_probe
```

The `System.identifier` UUID becomes the `tycho-guid` Kubernetes label that ties every K8s resource created for this launch together.

---

## Layer 4 — Kubernetes Emission (Templates)

**Key files:** `appstore/tycho/template/pod.yaml`, `appstore/tycho/template/service.yaml`

### Role

Jinja2 templates render the `System` object into raw Kubernetes manifest YAML. No Kubernetes client code lives in these templates — they are pure data declarations.

### Pod template highlights (`pod.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: {{ system.name }}
  labels:
    username: {{ system.username }}
    tycho-guid: {{ system.identifier }}
    executor: tycho
spec:
  serviceAccountName: {{ system.serviceaccount }}
  securityContext:
    runAsUser:  {{ system.security_context.run_as_user }}
    runAsGroup: {{ system.security_context.run_as_group }}
    fsGroup:    {{ system.security_context.fs_group }}

  # Optional init container (when CREATE_HOME_DIRS=true)
  initContainers:
    - name: volume-tasks
      image: busybox
      command: ["sh", "-c", "mkdir -p ..."]  # home dir setup
      volumeMounts: [...]

  containers:
    - name:  {{ container.name }}
      image: {{ container.image }}
      env:
        - {name: REMOTE_USER,     value: {{ system.username }}}
        - {name: IDENTITY_TOKEN,  value: {{ token }}}
        # ... app-specific env vars ...
      resources:
        limits:
          cpu:              {{ container.limits.cpus }}
          memory:           {{ container.limits.memory }}
          nvidia.com/gpu:   {{ container.limits.gpus }}
        requests:
          cpu:    {{ container.requests.cpus }}
          memory: {{ container.requests.memory }}
      ports: [...]
      volumeMounts: [...]
      livenessProbe:  {{ container.liveness_probe }}
      readinessProbe: {{ container.readiness_probe }}

  volumes:
    - name: stdnfs     # user home PVC
      persistentVolumeClaim:
        claimName: {{ pvc_name }}
```

### Service template highlights (`service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ service.name }}
  labels:
    tycho-guid: {{ system.identifier }}
  annotations:
    # Ambassador ingress mapping (when ambassador is enabled)
    getambassador.io/config: |
      prefix: /private/{{ app }}/{{ user }}/{{ sid }}/
      service: {{ system.name }}:{{ system.system_port }}
spec:
  type: ClusterIP      # LoadBalancer when Ambassador is absent
  selector:
    name: {{ system.name }}
  ports:
    - port:       {{ container.ports[0] }}
      targetPort: {{ container.ports[0] }}
```

---

## Layer 5 — Kubernetes Client

**Key file:** `appstore/tycho/kube.py`

### Role

`KubernetesCompute.start(system)` takes the rendered YAML strings, deserializes them into `kubernetes.client` objects, and issues API calls to the cluster.

### Execution sequence

```
KubernetesCompute.start(system)
│
├─ 1. Configure k8s client
│      Load in-cluster config (or kubeconfig for dev)
│
├─ 2. Pre-flight checks
│      - Confirm Ambassador service exists (affects Service type)
│      - Confirm PVCs exist
│      - Load env secrets from <system>-env ConfigMap if present
│
├─ 3. Render pod.yaml → pod_manifest (YAML string)
│      system.render("pod.yaml")
│
├─ 4. Convert Pod → Deployment
│      pod_to_deployment(system, pod_manifest)
│      ├─ V1DeploymentSpec(replicas=1, template=pod_template)
│      ├─ Selector labels: {tycho-guid, username}
│      └─ extensions_api.create_namespaced_deployment(
│             body=deployment, namespace=namespace)
│         ← Kubernetes schedules the Pod
│
├─ 5. Render service.yaml for each container
│      api.create_namespaced_service(
│          body=service_manifest, namespace=namespace)
│         ← Exposes the Pod on the cluster network
│
├─ 6. Optionally create NetworkPolicy
│      If system.requires_network_policy():
│        networking_api.create_namespaced_network_policy(...)
│
└─ 7. Return {name, sid, containers → {port mappings}}
```

### Why a Deployment rather than a bare Pod?

The rendered template produces a `Pod` spec, but `pod_to_deployment` wraps it in a `Deployment` with `replicas: 1`. This gives Kubernetes control over restarts and rolling updates, and makes querying via label selectors straightforward (`tycho-guid=<uuid>`).

---

## Supporting Subsystems

### Ambassador Ingress

When `settings.AMBASSADOR_SVC_NAME` is configured, the Service manifest includes an `getambassador.io/config` annotation. Ambassador reads this annotation and creates an edge route:

```
/private/<app_id>/<username>/<sid>/  →  <service>:<port>
```

This produces the per-user, per-instance URL returned in the API response.

### PersistentVolume (user home)

`settings.STDNFS_PVC` names a cluster-wide NFS-backed PVC. The pod template mounts it at `PARENT_DIR/SUBPATH_DIR/<username>`, giving each user persistent home storage across app restarts.

When `CREATE_HOME_DIRS=true` an `initContainer` runs `busybox mkdir` before the app container starts to ensure the subdirectory exists and has correct permissions.

### iRODS Integration

`IrodAuthorizedUser` (in `core/models.py`) maps a Django username to an iRODS UID. The pod template can inject iRODS credentials into container env vars, enabling apps to access iRODS data grids directly.

### Identity Token Flow

```
Launch request
    │
    ▼  AppStore creates UserIdentityToken (random, 31-day expiry)
    │  stores {token → sid} mapping in DB
    │
    ▼  Token injected as IDENTITY_TOKEN env var in pod
    │
    ▼  App uses IDENTITY_TOKEN on callback requests to AppStore
    │
    ▼  AppStore looks up token → validates user identity
```

This allows the running container to authenticate back to AppStore without carrying OAuth credentials.

---

## Complete Data Flow Diagram

```
User Browser / API Client
        │
        │  POST /api/v1/instances/
        │  { app_id, cpus, gpus, memory }
        ▼
┌───────────────────────────────────────────────┐
│ InstanceViewSet.create()                      │
│   • Deserialize + validate resource bounds    │
│   • Create UserIdentityToken → DB             │
│   • Build Principal (username + tokens)       │
└──────────────────┬────────────────────────────┘
                   │ tycho.start(principal, app_id, resource_request)
                   ▼
┌───────────────────────────────────────────────┐
│ TychoContext.start()                          │
│   • get_spec(app_id) → docker-compose YAML    │
│   • get_settings(app_id) → .env dict          │
│   • Merge resource request over spec defaults │
│   • Inject identity env vars                  │
│   • Build request dict                        │
└──────────────────┬────────────────────────────┘
                   │ TychoClient.start(request_dict)
                   ▼
┌───────────────────────────────────────────────┐
│ StartSystemResource.post()                    │
│   • Validate JSON schema                      │
│   • System.parse(request) → System object     │
│     (UUID, containers[], volumes, sec-context)│
│   • KubernetesCompute.start(system)           │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────┐
│ KubernetesCompute.start(system)               │
│   • system.render("pod.yaml")  → YAML string  │
│   • pod_to_deployment()        → V1Deployment │
│   • create_namespaced_deployment()  ← K8s API │
│   • system.render("service.yaml")  → YAML     │
│   • create_namespaced_service()     ← K8s API │
│   • (optional) create_namespaced_network_policy│
│   • Return {sid, port mappings}               │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
         Kubernetes Deployment
                   │
                   ▼  (scheduler)
              Running Pod
                   │
                   ▼
         Service → Ambassador → User URL
```

---

## Configuration Reference

| Setting | Default | Effect |
|---------|---------|--------|
| `TYCHO_MODE` | `live` | `live` = real K8s; `null` = stub for testing |
| `NAMESPACE` | `default` | Kubernetes namespace for all resources |
| `EXTERNAL_TYCHO_APP_REGISTRY_ENABLED` | `false` | Clone app specs from external git repo |
| `EXTERNAL_TYCHO_APP_REGISTRY_REPO` | — | Git URL for app registry |
| `CREATE_HOME_DIRS` | `false` | Add init container to create home subdirectory |
| `STDNFS_PVC` | — | PVC name for user home storage |
| `PARENT_DIR` / `SUBPATH_DIR` | — | Mount path components for user home |
| `AMBASSADOR_SVC_NAME` | — | If set, use Ambassador ingress annotations |
| `APPLICATION_BRAND` | — | Product name; filters which apps are visible |

---

## Key File Index

| File | Layer | Role |
|------|-------|------|
| `appstore/api/v1/views.py` | 1 | `InstanceViewSet` — API entry point |
| `appstore/api/v1/models.py` | 1 | `ResourceRequest`, `InstanceSpec` |
| `appstore/api/v1/serializers.py` | 1 | Request validation |
| `appstore/tycho/context.py` | 2 | `TychoContext`, `ContextFactory` |
| `appstore/tycho/conf/app-registry.yaml` | 2 | App catalog |
| `appstore/tycho/conf/tycho.yaml` | 2 | Compute defaults |
| `appstore/tycho/model.py` | 3 | `System`, `Container` |
| `appstore/tycho/template/pod.yaml` | 4 | Pod manifest template |
| `appstore/tycho/template/service.yaml` | 4 | Service manifest template |
| `appstore/tycho/kube.py` | 5 | `KubernetesCompute` — K8s API calls |
| `appstore/tycho/client.py` | 5 | `TychoClient`, `TychoService` |
| `appstore/tycho/actions.py` | 5 | `StartSystemResource` dispatcher |
| `appstore/core/models.py` | — | `UserIdentityToken`, `IrodAuthorizedUser` |
| `appstore/appstore/settings/base.py` | — | All Django/Tycho settings |
