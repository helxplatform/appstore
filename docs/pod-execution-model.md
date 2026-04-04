# AppStore Pod Execution Model

A conceptual guide to the flow that produces Kubernetes workloads when a user launches an application.

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
│  CRD Spec Models    │  parse compose → typed HelxApp/HelxInst specs
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Kubernetes CRD     │  create HelxApp + HelxInst custom resources
│  Creation Layer     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  helxapp-controller │  reconcile CRDs → Deployment, Service, etc.
└─────────────────────┘
         │
         ▼
    Running Pod
```

---

## Layer 1 — REST API

**Key file:** `appstore/api/v1/views.py`

### Entry point

`POST /api/v1/instances/` is handled by `InstanceViewSet.create()`.

### What happens here

1. **Authenticate** — request user must be logged in; username is normalised to lowercase for all Kubernetes-facing identifiers (RFC 1123 requirement).
2. **Deserialize** the request body: `app_id` plus optional resource overrides (`cpus`, `gpus`, `memory`, `ephemeralStorage`).
3. **Fetch app metadata** from the App Registry (Layer 2) to learn the app's min/max resource bounds.
4. **Validate resources** — CPU, GPU, memory, and ephemeral storage are each checked against the app's configured limits. Out-of-range values return HTTP 400.
5. **Create a `UserIdentityToken`** — a 256-char random token stored in the DB; injected into the pod so the running app can authenticate callbacks to AppStore.
6. **Call `kube_client.launch()`** → Layers 2–5.
7. **Return an `InstanceSpec`** with the app URL (`proxy_path`), instance ID, and resource summary.

### proxy_path

The access URL follows the Ambassador route template:

```
/private/<app_id>/<username>/
```

Both components are lowercase to match the Go template the controller resolves:
`/private/{{ .system.AppClassName }}/{{ .system.UserName }}/`

### Readiness polling

`GET /api/v1/instances/<instance_id>/is_ready/` returns `{is_ready: true|false}`.
When called immediately after launch, the helxapp-controller may not have reconciled yet and no Deployment will exist. In that case the endpoint returns `{is_ready: false}` rather than 404, so callers can poll until ready.

---

## Layer 2 — App Registry

**Key files:** `appstore/registry/models.py`, `appstore/registry/loader.py`

### Role

Translates an `app_id` string into a `ResolvedApp` — a concrete descriptor containing the app's docker-compose path, icon, description, service port map, and optional security context.

### Registry loading

On startup, the registry scans a directory tree (configured by `APP_REGISTRY_DIR`) for `docker-compose.yaml` files. Each file corresponds to one app. A sidecar `metadata.yaml` supplies display metadata (name, description, icon, docs URL).

### ResolvedApp

```python
@dataclass
class ResolvedApp:
    app_id: str           # lowercase slug, becomes K8s resource name component
    name: str             # display name
    description: str
    spec_path: str        # filesystem path to docker-compose.yaml
    icon_path: str
    services: dict        # {service_name: port}
    count: int            # max simultaneous instances (default 1)
    security_context: SecurityContext | None
    ext: dict             # x-helx-* extensions from the compose file
```

---

## Layer 3 — CRD Spec Models

**Key files:** `appstore/appspec/`, `appstore/registry/spec_builder.py`, `appstore/kube/models.py`

### Role

Parses the docker-compose YAML into typed Python objects, then converts them into `HelxAppSpec` and `HelxInstSpec` data classes that map directly to the CRD schema expected by helxapp-controller.

### appspec — compose parsing

`appspec.parse_compose(compose_dict, ext)` parses a docker-compose structure into a `ComposeApp`:

```
ComposeApp
└── services: list[ComposeService]
    ├── name
    ├── image
    ├── command: list[str] | None
    ├── environment: dict[str, str]
    ├── ports: list[int]            # container port numbers
    ├── volumes: list[VolumeMount]
    ├── secrets: list[str]          # names of declared external secrets
    ├── limits / requests           # from deploy.resources
    └── resource_bounds             # from x-helx-resources extension
```

Environment variables may be a YAML list (`KEY=VALUE`) or dict; the parser normalises both to `dict[str, str]`.

Secrets follow docker-compose syntax:

```yaml
services:
  pgadmin:
    secrets:
      - pgadmin-env          # short form
secrets:
  pgadmin-env:
    external: true           # only external secrets are supported
```

Only secrets declared `external: true` at the top level are propagated.
Per-service secret names land in `ComposeService.secrets` and are passed through as `secretsFrom` on the CRD, which the controller maps via Kubernetes `envFrom`.

### spec_builder — compose → CRD

`build_helxapp_spec(app, compose_dict)` → `HelxAppSpec`

- Maps `ComposeService.ports` → `PortSpec(container_port, port)`.
  The `port` (Service port) comes from `ResolvedApp.services`; the first service with a non-zero Service port gets an `AmbassadorSpec` attached.
- Maps `ComposeService.volumes` → volume DSL strings (`[scheme://]src:mountPath[,options]`).
- Maps `ComposeService.secrets` → `AppServiceSpec.secrets_from` → `"secretsFrom"` in CRD.
- Carries `ResolvedApp.security_context` down to every `AppServiceSpec`.

`build_helxinst_spec(app, username, resource_request, security_context)` → `HelxInstSpec`

- Wraps the per-user resource request into `ContainerResources(request, limit)` for each declared service.
- Instance-level security context overrides app-level security context.

### kube/models — typed CRD schema

| Class | Maps to |
|-------|---------|
| `HelxAppSpec` | HelxApp CRD `.spec` |
| `HelxInstSpec` | HelxInst CRD `.spec` |
| `HelxUserSpec` | HelxUser CRD `.spec` |
| `AppServiceSpec` | `services[]` entry in HelxApp spec |
| `PortSpec` | `services[].ports[]` |
| `AmbassadorSpec` | `services[].ambassador` |
| `ResourceSpec` | CPU/memory/GPU/storage quantities |
| `ContainerResources` | request+limit pair per container |
| `SecurityContext` | pod/container security context |

Every model implements `to_dict()` which produces the camelCase JSON expected by the controller (e.g. `run_as_user` → `"runAsUser"`, `secrets_from` → `"secretsFrom"`).

---

## Layer 4 — Kubernetes CRD Creation

**Key file:** `appstore/kube/client.py`

### Role

Creates the three CRD objects that helxapp-controller watches: `HelxApp`, `HelxInst`, and optionally `HelxUser`.

### Execution sequence

```
KubeClient.launch(app, username, resource_request, identity_token, env)
│
├─ 1. build_helxapp_spec(app, compose_dict)
│      Produce HelxAppSpec (service definitions, ambassador, secrets)
│
├─ 2. apply_helxapp(namespace, app_id, helxapp_spec.to_dict())
│      kubectl apply HelxApp/<app_id>
│      (HelxApp is cluster-scoped; one per app_id, shared across users)
│
├─ 3. build_helxinst_spec(app, username, resource_request, security_context)
│      Produce HelxInstSpec (user + resource overrides)
│
├─ 4. create_helxinst(namespace, instance_name, helxinst_spec.to_dict())
│      kubectl create HelxInst/<app_id>-<instance_id>
│      (HelxInst is namespace-scoped; one per running instance)
│
└─ 5. Return instance_id for subsequent status queries
```

`HelxApp` is applied (upserted) because the app definition is shared: multiple users running the same app all reference the same `HelxApp` resource. `HelxInst` is created fresh for each launch.

---

## Layer 5 — helxapp-controller

**Operated separately; not part of this codebase.**

### Role

A Kubernetes operator that watches `HelxApp`, `HelxInst`, and `HelxUser` CRDs and reconciles the desired state into concrete Kubernetes workload objects.

### Reconciliation — what the controller creates per HelxInst

```
HelxInst created
      │
      ▼  (controller reconciles)
      │
      ├─ Deployment
      │    labels:
      │      helx.renci.org/app-name:      <app_id>
      │      helx.renci.org/user-name:     <username>      (lowercase)
      │      helx.renci.org/instance-name: <app_id>-<uuid> (controller UUID)
      │      helx.renci.org/id:            <controller-uuid>
      │      executor:                      helxapp-controller
      │
      ├─ Service(s)
      │    One per service with a non-zero port.
      │    If services[].ambassador is set, annotated with:
      │      getambassador.io/config:
      │        prefix: /private/<AppClassName>/<UserName>/
      │        service: <service-name>:<port>
      │
      ├─ envFrom secret injection
      │    For each name in services[].secretsFrom, the controller adds
      │    an envFrom[].secretRef to the container, injecting all keys
      │    from that K8s Secret as environment variables.
      │
      └─ (optional) NetworkPolicy, ServiceAccount
```

### Label-based instance identification

AppStore identifies running instances by reading Deployments labelled `executor=helxapp-controller` in the target namespace. The appstore `instance_id` is recovered from the `helx.renci.org/instance-name` label by stripping the `<app_id>-` prefix:

```
helx.renci.org/instance-name = "jupyter-a3f9c2"
app_id = "jupyter"
instance_id = "a3f9c2"   ← used in AppStore's own DB records
```

The `helx.renci.org/id` label is the controller's internal UUID and is not the same as AppStore's `instance_id`.

---

## Supporting Subsystems

### Ambassador Ingress

When `AMBASSADOR_ID` is set, each `HelxAppSpec` service that exposes a port includes an `AmbassadorSpec`:

```python
AmbassadorSpec(
    prefix="/private/{{ .system.AppClassName }}/{{ .system.UserName }}/",
    ambassador_id="edge-stack",   # or None
)
```

The controller writes this as an Ambassador v1 Mapping annotation on the generated Service. Ambassador resolves the Go template expressions at deploy time (double-pass rendering), producing per-user routes:

```
/private/jupyter/alice/  →  jupyter-svc:8888
```

AppStore's `proxy_path` is constructed to match this pattern:

```python
proxy_path = f"/private/{app_id}/{k8s_user}/"
```

### Secrets / envFrom injection

Secrets that an app needs (e.g. database credentials, API keys) are stored as K8s Secrets in the same namespace. The app's docker-compose declares them under `secrets:` with `external: true`. The controller injects them via `envFrom`:

```yaml
# docker-compose.yaml
services:
  pgadmin:
    secrets: [pgadmin-env]
secrets:
  pgadmin-env:
    external: true

# becomes in HelxApp CRD:
services:
  - name: pgadmin
    secretsFrom: [pgadmin-env]

# controller renders into pod:
containers:
  - name: pgadmin
    envFrom:
      - secretRef:
          name: pgadmin-env
```

### PersistentVolume (user home)

User home directories are provided through volumes declared in the docker-compose spec using the volume DSL:

```
[scheme://]source:mountPath[#subPath][,options]
```

Supported schemes: `pvc` (default), `nfs`, `secret`, `configmap`.

Example: `pvc://stdnfs:/home/user#alice,rw,retain`

The controller mounts the PVC at the specified path using the subPath for per-user isolation.

### Identity Token Flow

```
Launch request
    │
    ▼  AppStore creates UserIdentityToken (random, 31-day expiry)
    │  stores {token → instance_id} mapping in DB
    │
    ▼  Token injected as IDENTITY_TOKEN env var in HelxInst environment
    │
    ▼  App uses IDENTITY_TOKEN on callback requests to AppStore
    │
    ▼  AppStore looks up token → validates user identity
```

This allows the running container to authenticate back to AppStore without carrying OAuth credentials.

### Three-way Environment Merge

The controller merges environment variables from three sources in precedence order (lowest to highest):

1. `HelxApp.spec.services[].environment` — app-level defaults from docker-compose
2. `HelxUser.spec.environment` — user-level defaults (if a HelxUser CRD exists)
3. `HelxInst.spec.environment` — instance-level overrides (per-launch values)

AppStore injects `IDENTITY_TOKEN`, `REMOTE_USER`, and `NB_PREFIX` at the HelxInst level so they take precedence.

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
│   • Authenticate; normalise username to lower │
│   • Deserialize + validate resource bounds    │
│   • Create UserIdentityToken → DB             │
│   • Build instance_id                         │
└──────────────────┬────────────────────────────┘
                   │ kube_client.launch(app, username, resources, env)
                   ▼
┌───────────────────────────────────────────────┐
│ App Registry                                  │
│   • Load docker-compose.yaml for app_id       │
│   • Parse via appspec.parse_compose()         │
│   • Return ComposeApp                         │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────┐
│ spec_builder                                  │
│   • build_helxapp_spec() → HelxAppSpec        │
│     - ports, ambassador, volumes, secrets     │
│   • build_helxinst_spec() → HelxInstSpec      │
│     - username, resources, identity_token env │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────┐
│ KubeClient                                    │
│   • apply HelxApp CRD    (app definition)     │
│   • create HelxInst CRD  (per-user launch)    │
└──────────────────┬────────────────────────────┘
                   │ (async — controller reconciles)
                   ▼
┌───────────────────────────────────────────────┐
│ helxapp-controller                            │
│   • Create Deployment (pod template)          │
│   • Create Service(s)                         │
│   • Add Ambassador annotation → ingress route │
│   • Inject envFrom for secretsFrom entries    │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
          Kubernetes Deployment
                   │
                   ▼  (scheduler)
              Running Pod
                   │
                   ▼
         Service → Ambassador → /private/<app>/<user>/
```

---

## Configuration Reference

| Setting | Default | Effect |
|---------|---------|--------|
| `NAMESPACE` | `default` | Kubernetes namespace for all CRD/workload resources |
| `APP_REGISTRY_DIR` | — | Filesystem path scanned for app `docker-compose.yaml` files |
| `AMBASSADOR_ID` | — | If set, included in `AmbassadorSpec.ambassador_id` on each service |
| `KUBECONFIG` / in-cluster | — | K8s client auth; in-cluster config used automatically in pods |

---

## Key File Index

| File | Layer | Role |
|------|-------|------|
| `appstore/api/v1/views.py` | 1 | `InstanceViewSet` — API entry point |
| `appstore/api/v1/serializers.py` | 1 | Request deserialization and validation |
| `appstore/registry/models.py` | 2 | `ResolvedApp`, `AppRegistryEntry` |
| `appstore/registry/loader.py` | 2 | Registry directory scan and app loading |
| `appstore/appspec/parser.py` | 3 | `parse_compose()` — docker-compose → `ComposeApp` |
| `appstore/appspec/models.py` | 3 | `ComposeApp`, `ComposeService`, `VolumeMount` |
| `appstore/registry/spec_builder.py` | 3 | `build_helxapp_spec()`, `build_helxinst_spec()` |
| `appstore/kube/models.py` | 3 | `HelxAppSpec`, `HelxInstSpec`, `AmbassadorSpec`, etc. |
| `appstore/kube/client.py` | 4 | `KubeClient` — CRD creation via K8s API |
| `appstore/kube/status.py` | — | Instance status from Deployment labels |
| `appstore/core/models.py` | — | `UserIdentityToken`, `IrodAuthorizedUser` |
| `appstore/appstore/settings/base.py` | — | All Django/Kubernetes settings |
