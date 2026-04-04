# helxapp-controller

A Kubernetes operator that manages application deployments via three Custom Resource Definitions (CRDs): **HelxApp** (application template), **HelxInst** (instance request), and **HelxUser** (user record). When all three exist and reference each other, the controller synthesizes Deployments, Services, and PersistentVolumeClaims.

See [docs/execution-model.md](docs/execution-model.md) for the full artifact generation pipeline and sequence diagrams.

---

## Table of Contents

- [Data Model](#data-model)
- [Operator Behavior](#operator-behavior)
- [Volume DSL](#volume-dsl)
- [Security Context Resolution](#security-context-resolution)
- [Ambassador Mapping](#ambassador-mapping)
- [Deployment](#deployment)
- [RBAC Model](#rbac-model)
- [Development](#development)
- [Testing](#testing)
- [Test Coverage](#test-coverage)
- [Extending the Operator](#extending-the-operator)
- [AI Prompt Reference](#ai-prompt-reference)
- [License](#license)

---

## Data Model

The operator manages three namespaced CRDs in the `helx.renci.org/v1` API group. The three resources arrive independently and in any order. Workloads are only created when a complete triple (app + user + instance) exists.

### HelxApp — application template

Defines *what* an application is: container images, ports, environment, volumes, and security context.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxApp
metadata:
  name: jupyterlab
spec:
  appClassName: JupyterLab
  services:
    - name: main
      image: jupyter/minimal-notebook:latest
      command: ["/bin/sh", "-c", "start-notebook.sh"]
      environment:
        NB_PREFIX: "/"
      ports:
        - containerPort: 8888
          port: 8888
      volumes:
        home: "{{ .system.UserName }}-home:/home/{{ .system.UserName }},rwx,retain"
```

| Field | Description |
|-------|-------------|
| `appClassName` | Logical class name, stamped onto pod labels |
| `services[]` | Ordered list of container definitions |
| `services[].name` | Container name; also the key for per-instance resource overrides |
| `services[].image` | Image reference, optionally followed by `,key=value` options (e.g. `,Always` sets `imagePullPolicy`) |
| `services[].command[]` | Entrypoint override; may contain Go template expressions like `{{ .system.UserName }}` |
| `services[].environment` | Map of env vars; values may contain Go template expressions |
| `services[].secretsFrom` | List of Secret names; all keys injected as env vars via `envFrom` |
| `services[].configMapsFrom` | List of ConfigMap names; all keys injected as env vars via `envFrom` |
| `services[].init` | If `true`, runs as an init container |
| `services[].ports[]` | `containerPort`/`port` pairs; a non-zero `port` triggers Service creation |
| `services[].resourceBounds` | Advisory min/max per resource type |
| `services[].securityContext` | Per-container UID/GID/FSGroup/supplementalGroups |
| `services[].volumes` | Map of `volumeId` to volume DSL string (see [Volume DSL](#volume-dsl)) |
| `services[].ambassador` | Optional [Ambassador mapping](#ambassador-mapping) configuration for the Service |

### HelxInst — instance request

A per-user instantiation: "run this app for this user". This is the *trigger* for workload creation.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxInst
metadata:
  name: jupyterlab-jeffw
spec:
  appName: jupyterlab
  userName: jeffw
  environment:
    WORKSPACE_ID: "ws-42"
    NB_PREFIX: "/custom"
  resources:
    main:
      request: { cpu: "2", memory: "1G" }
      limit:   { cpu: "2", memory: "1.1G" }
  securityContext:
    runAsUser: 1000
    fsGroup: 2000
```

| Field | Description |
|-------|-------------|
| `appName` | Name (or `namespace/name`) of the HelxApp to instantiate |
| `userName` | Name (or `namespace/name`) of the HelxUser |
| `environment` | Instance-level env vars; highest precedence in the three-way merge (app < user < inst) |
| `secretsFrom` | List of Secret names; all keys injected as env vars via `envFrom` |
| `configMapsFrom` | List of ConfigMap names; all keys injected as env vars via `envFrom` |
| `resources` | Map of service name to `{request, limit}` resource specifications |
| `securityContext` | Optional override; takes highest priority (see [Security Context Resolution](#security-context-resolution)) |

**Status fields** (set by the controller):

| Field | Description |
|-------|-------------|
| `uuid` | Assigned on first reconciliation; labels all derived Kubernetes objects |
| `observedGeneration` | Prevents redundant reconciliation |

### HelxUser — user record

Represents a platform user. Can carry user-level environment variables and volumes that apply across all instances for that user.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxUser
metadata:
  name: jeffw
spec:
  userHandle: "http://ldap-service/user/jeffw"
  environment:
    LDAP_USER: "jeffw"
  volumes:
    home: "jeffw-home:/home/jeffw,rwx,retain"
```

| Field | Description |
|-------|-------------|
| `userHandle` | Optional URL; HTTP GET returns JSON with `runAsUser`, `runAsGroup`, `fsGroup`, `supplementalGroups` |
| `environment` | User-level env vars; merged between app-level and instance-level (see precedence below) |
| `secretsFrom` | List of Secret names; all keys injected as env vars via `envFrom` |
| `configMapsFrom` | List of ConfigMap names; all keys injected as env vars via `envFrom` |
| `volumes` | User-level volumes (same DSL as HelxApp); mounted on all containers, PVCs created for `pvc://` scheme |

**Environment merge precedence** (most specific wins): HelxApp service env < HelxUser env < HelxInst env.

**envFrom merge**: `secretsFrom` and `configMapsFrom` lists from all three CRDs are combined (deduplicated by name). This injects all key-value pairs from the referenced Secrets/ConfigMaps as environment variables.

**Volume merge**: App volumes are per-service. User volumes are added to every container in the deployment alongside the app volumes.

### Relationship diagram

```
HelxApp (template)              HelxUser (identity)
    \                              /
     \--- appName      userName --/
      \        \      /        /
       \        v    v        /
        +--- HelxInst (trigger) ---+
                    |
                    v
          Deployment + Services + PVCs
```

---

## Operator Behavior

### In-memory object graph

The controller maintains bidirectional associations between the three CRD types in memory. When any resource arrives, it is registered in the graph and checked for completable triples:

- **HelxInst created** — registered; if app + user already exist, workloads are created immediately
- **HelxApp created** — registered; any instances already waiting for this app get their workloads created
- **HelxUser created** — same as HelxApp, for instances waiting for this user

### Workload generation

When a complete triple exists, the controller:

1. Transforms `HelxApp.Spec.Services` into template data structures
2. Builds a `System` context (app name, user name, UUID, environment, security context, volumes)
3. Renders Go templates (`deployment.tmpl`, `pvc.tmpl`, `service.tmpl`) with **double-pass** rendering — the first pass produces YAML, the second re-renders the YAML itself as a template to resolve expressions like `{{ .system.UserName }}` in field values
4. Creates or patches Kubernetes objects via `CreateOrUpdateResource`

### Produced objects

For a HelxInst whose HelxApp defines N services:

| Object | Count | Condition |
|--------|-------|-----------|
| Deployment | 1 | Always |
| PersistentVolumeClaim | 1 per unique `pvc://` volume | Only for PVC-scheme volumes |
| Service | 1 per service | Only when `port != 0` |

All derived objects share the label `helx.renci.org/id: <UUID>`.

### Deletion behavior

| Trigger | Effect |
|---------|--------|
| HelxInst deleted | Controller removes from graph; Kubernetes owner-reference GC removes Deployment, Services, PVCs |
| HelxApp deleted | Controller actively deletes workloads for all connected instances |
| HelxUser deleted | Same as HelxApp — active deletion of connected instance workloads |

Objects with label `helx.renci.org/retain: "true"` survive deletion, allowing persistent data to outlive instances.

### Label taxonomy

| Label | Value | Applied to |
|-------|-------|-----------|
| `executor` | `helxapp-controller` | All derived objects |
| `helx.renci.org/id` | Instance UUID | All derived objects |
| `helx.renci.org/app-name` | App name | Deployment, pod template |
| `helx.renci.org/username` | User name | Deployment, pod template |
| `helx.renci.org/app-class-name` | App class | Pod template |
| `helx.renci.org/instance-name` | Instance name | Pod template |
| `helx.renci.org/retain` | `"true"` | PVCs that survive deletion |

---

## Volume DSL

Volume entries in `HelxApp.Spec.Services[].Volumes` use a mini-language:

```
[scheme://]src:mountPath[#subPath][,option[=value]...]
```

| Segment | Description |
|---------|-------------|
| `scheme` | `pvc` (default), `nfs`, `secret`, or `configmap` |
| `src` | PVC claim name, NFS path (`//server/export`), Secret name, or ConfigMap name |
| `mountPath` | Container mount point |
| `subPath` | Optional subdirectory (or key name for secrets/configmaps) |

**Options:**

| Option | Effect |
|--------|--------|
| `retain` | Adds `helx.renci.org/retain: "true"` label; PVC survives instance deletion |
| `rwx` | `ReadWriteMany` access mode |
| `rox` | `ReadOnlyMany` access mode |
| `rwop` | `ReadWriteOncePod` access mode |
| `size=X` | Storage request (default `1G`) |
| `storageClass=X` | Storage class name |
| `ro` | Mount read-only in the container |

**Examples:**

```yaml
volumes:
  home: "{{ .system.UserName }}-home:/home/{{ .system.UserName }},rwx,retain"
  data: "shared-data:/data,size=50Gi,rwx"
  cache: "nfs:///nfs-server/cache:/mnt/cache"
  scratch: "scratch-vol:/tmp/scratch#mysubdir,rwop"
  creds: "secret://db-credentials:/mnt/creds,ro"
  cfg: "configmap://app-config:/etc/config#app.conf"
```

---

## Security Context Resolution

The pod security context is resolved in priority order:

1. **HelxInst.Spec.SecurityContext** — explicit per-instance override (highest priority)
2. **HelxUser.Spec.UserHandle** — HTTP GET to the URL; JSON response parsed for `runAsUser`, `runAsGroup`, `fsGroup`, `supplementalGroups`
3. **Omitted** — no security context on the pod spec

Per-service security contexts from `HelxApp.Spec.Services[].SecurityContext` are applied at the container level, independent of the pod-level context.

---

## Ambassador Mapping

Services can be annotated for [Ambassador](https://www.getambassador.io/) ingress routing by setting the `ambassador` field on a HelxApp service. When present, the controller adds a `getambassador.io/config` annotation to the generated Kubernetes Service with an Ambassador v1 Mapping.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxApp
metadata:
  name: filebrowser
spec:
  appClassName: Filebrowser
  services:
    - name: main
      image: wateim/filebrowser:latest
      ports:
        - containerPort: 80
          port: 8080
      ambassador:
        prefix: "/private/{{ .system.AppClassName }}/{{ .system.UserName }}/{{ .system.UUID }}/"
```

| Field | Description |
|-------|-------------|
| `ambassador.ambassadorId` | Optional; restricts the mapping to a specific Ambassador instance |
| `ambassador.prefix` | URL path prefix. Supports Go template expressions (resolved via double-pass rendering). Default: `/private/<AppClassName>/<UserName>/<UUID>/` |
| `ambassador.proxyRewrite` | Optional; rewrites the upstream path. When set, also adds an `X-Original-Path` response header |

The generated annotation includes:
- `REMOTE_USER` header set to the instance's user name
- Retry policy (gateway-error, 10 retries)
- Timeouts (300s request, 500s idle/connect)
- WebSocket support enabled
- `bypass_auth: true`

When `ambassador` is not set on a service, no annotation is added and the Service is rendered as before.

---

## Deployment

The Helm chart (`chart/`) supports two installation modes controlled by the `cluster` value (default `false`).

### Cluster install (cluster admin)

Install CRDs and deploy the controller cluster-wide:

```sh
make install                                         # install CRDs
helm install helxapp-controller chart/ --set cluster=true
```

### Namespace install (developer)

A cluster admin must first grant the developer's service account CRD permissions (Kubernetes RBAC escalation prevention requires this):

```sh
# Cluster admin — one-time per namespace:
make grant-access SA=<namespace>:<service-account>

# Developer — install the controller in their namespace:
helm install helxapp-controller chart/
```

With `cluster=false` (default), the chart creates only namespace-scoped Roles and RoleBindings. The controller automatically watches only its own namespace via the `WATCH_NAMESPACE` environment variable (set from the pod's namespace via the downward API).

### Uninstall

```sh
helm uninstall helxapp-controller    # remove controller
make uninstall                        # remove CRDs (cluster admin)
```

---

## RBAC Model

### Controller service account permissions

The controller SA requires these permissions in its watch namespace:

| Resource | API Group | Verbs |
|----------|-----------|-------|
| helxapps, helxapps/status, helxapps/finalizers | helx.renci.org | get, list, watch, create, update, patch, delete |
| helxinsts, helxinsts/status, helxinsts/finalizers | helx.renci.org | get, list, watch, create, update, patch, delete |
| helxusers, helxusers/status, helxusers/finalizers | helx.renci.org | get, list, watch, create, update, patch, delete |
| deployments | apps | get, list, watch, create, update, patch, delete |
| services | core | get, list, watch, create, update, patch, delete |
| persistentvolumeclaims | core | get, list, watch, create, update, patch, delete |

### Namespace vs cluster scope

| Mode | `--namespace` flag / `WATCH_NAMESPACE` | RBAC type | CRD access |
|------|----------------------------------------|-----------|-----------|
| Namespace-scoped | Set to deployment namespace | Roles + RoleBindings | Watch/manage CRDs in one namespace |
| Cluster-scoped | Empty (watches all namespaces) | ClusterRoles + ClusterRoleBindings | Watch/manage CRDs in all namespaces |

### User-facing roles

The chart and kustomize config provide graduated access roles:

| Role | Permissions |
|------|-------------|
| `helxapp-viewer-role` | get, list, watch on CRDs |
| `helxapp-editor-role` | create, delete, get, list, patch, update, watch on CRDs |
| `helxapp-manager-role` | Full CRD management including status and finalizers |

### Granting namespace access

For namespace-scoped installs, `make grant-access SA=<ns>:<sa>` creates the ClusterRole + RoleBinding needed for the SA to manage CRDs in its namespace. This is a one-time operation by a cluster admin.

---

## Development

### Running locally

```sh
make install       # install CRDs
make run           # run controller against current kubeconfig (watches current namespace)
```

### Building

```sh
make build                                        # compile to bin/manager
make docker-build docker-push IMG=<registry>:tag  # build and push container image
```

### Modifying the API (CRD types)

After editing `api/v1/*_types.go`:

```sh
make manifests generate    # regenerate CRD YAML and DeepCopy methods
make test                  # verify everything still works
```

---

## Testing

### Test tiers

| Tier | Command | Scope | Requirements |
|------|---------|-------|-------------|
| Unit tests | `make test` | Pure logic: template rendering, volume DSL, object graph, security context extraction | None (envtest provides local API server) |
| Controller tests | `make test` | CRD CRUD via envtest (local API server, no real cluster) | `setup-envtest` (auto-downloaded) |
| E2E tests | `make e2e` | Full controller behavior against a live cluster | Deployed controller in current kubeconfig namespace |

### Running tests

```sh
make test                    # unit + controller tests
make e2e                     # e2e tests (requires live cluster)

# Single test:
go test ./template_io/ -run TestRenderNginx -v

# E2E single test:
cd e2e && go test -v -run TestE2E_CreateTriple_DeploymentCreated ./...
```

### E2E test coverage

The 22 e2e tests cover:

| Area | Tests |
|------|-------|
| Core lifecycle | Create triple, order independence, delete inst/app/user cascades |
| Workload correctness | Labels, container spec, service ports, PVC creation, NFS volumes, resource limits |
| Security context | Instance-level override applied to pod spec |
| Volume DSL | RWX access mode, retain label, storage size |
| Retain behavior | PVC survives instance deletion |
| Update handling | App image update, instance resource update propagated to deployment |
| Status fields | UUID assignment, ObservedGeneration tracking |
| Multi-instance | Separate deployments with distinct UUIDs |

---

## Test Coverage

*Last updated: 2026-03-27*

| Package | Coverage | Notes |
|---------|----------|-------|
| `connect` | 91.7% | HTTP client for user handle; missing: response body read error |
| `template_io` | 75.2% | Template parsing, rendering, volume types, security context |
| `helxapp_operations` | 58.1% | Object graph, artifact generation, transforms; cluster CRUD functions (0%) require envtest/live cluster |
| `controllers` | 0.0% | Reconciler logic; covered by e2e tests against live cluster |
| `api/v1` | 0.0% | Generated DeepCopy code; excluded from coverage targets |
| **Total (unit)** | **36.2%** | |
| **E2E** | **22 tests** | Covers reconciler + cluster CRUD paths not reachable by unit tests |

### Coverage gaps and rationale

| Gap | Reason | Path to cover |
|-----|--------|--------------|
| `helxapp_operations.CreateOrUpdateResource` | Requires a real API server with scheme registration | E2E tests cover this path |
| `helxapp_operations.Delete{Deployments,PVCs,Services}` | Same — cluster CRUD | E2E tests |
| `helxapp_operations.{Deployment,PVC,Service}FromYAML` | YAML decode + cluster create | E2E tests |
| `controllers/*.Reconcile` | Full reconciler loop | E2E tests |
| `template_io.LoadTemplatesFromDB` | Requires PostgreSQL | Integration test with test container |

---

## Extending the Operator

### When to add or modify a CRD

| Scenario | Action | Affects |
|----------|--------|---------|
| New field on existing resource (e.g., adding probes to HelxApp services) | Add field to `api/v1/*_types.go`, run `make manifests generate` | CRD schema, templates, unit tests |
| New resource kind (e.g., HelxPolicy for network policies) | New type file in `api/v1/`, new controller in `controllers/`, register in `main.go` | CRD schema, RBAC, Helm chart roles, all test tiers |
| New workload output (e.g., generating Ingress objects) | Add template in `templates/`, add rendering in `helxapp_operations.GenerateArtifacts` | Templates, unit tests, e2e tests, RBAC (Ingress permissions) |
| New volume scheme (e.g., `hostPath://`) | Extend `processVolume()` in `helxapp_operations`, add template branch in `pod.tmpl` | Volume DSL, unit tests |

### Checklist for CRD changes

1. Edit `api/v1/*_types.go` — add/modify struct fields with JSON tags
2. `make manifests generate` — regenerate CRD YAML and DeepCopy methods
3. Update templates in `templates/` if the new field affects rendered output
4. Update `helxapp_operations` if the field requires transformation logic
5. Add unit tests for the new transform/rendering paths
6. Add e2e tests verifying the end-to-end behavior
7. Update RBAC if the controller needs permissions for new resource types
8. Update Helm chart roles (`chart/templates/roles.yaml`) for both cluster and namespace modes
9. `make test` — verify unit + controller tests pass
10. `make e2e` — verify against a live cluster

### Tying CRD changes to tests

Every CRD field should have test coverage at multiple tiers:

```
api/v1/*_types.go field
    │
    ├─ Unit test: verify transformApp/transformVolumes/etc. handles the field
    │   (helxapp_operations/helxapp_operations_test.go)
    │
    ├─ Template test: verify the rendered YAML contains expected output
    │   (template_io/template_io_test.go)
    │
    ├─ Controller test: verify CRD round-trips through the API server
    │   (controllers/helxapp_controller_test.go via envtest)
    │
    └─ E2E test: verify the field produces the correct Kubernetes object
        (e2e/e2e_test.go against live cluster)
```

---

## AI Prompt Reference

This section provides a structured context block for AI assistants working on this codebase. Include it in your prompt or system instructions.

<details>
<summary>Click to expand prompt context</summary>

```
## helxapp-controller — AI assistant context

### Project type
Kubernetes operator (controller-runtime / Kubebuilder) managing three CRDs
in API group helx.renci.org/v1.

### CRDs
- HelxApp: application template (images, ports, env, volumes, security context, ambassador mapping)
- HelxInst: per-user instance request referencing an app + user; triggers workload creation.
  Has its own environment map — merged with app-level env (instance wins on overlap).
- HelxUser: user record; optional userHandle URL for security context.
  Has environment and volumes fields — merged with app/inst (app < user < inst precedence).

### Core behavior
The three CRDs arrive independently and in any order. The controller maintains
an in-memory relational graph (helxapp_operations package). Workload objects
(Deployment, PVCs, Services) are only created when a complete triple exists.
Templates use double-pass rendering: Go templates produce YAML, then the YAML
is re-rendered as a template to resolve {{ .system.* }} expressions in field values.

### Key packages
| Package              | Role                                              |
|----------------------|---------------------------------------------------|
| api/v1/              | CRD type definitions (spec, status, DeepCopy)     |
| controllers/         | Three reconcilers, one per CRD kind               |
| helxapp_operations/  | In-memory graph, artifact generation, cluster CRUD |
| template_io/         | Template types, rendering, volume DSL parsing      |
| templates/           | Go templates (deployment, pod, container, pvc, service) |
| connect/             | HTTP client for userHandle URLs                    |
| e2e/                 | End-to-end tests (separate Go module)              |

### Volume DSL
[scheme://]src:mountPath[#subPath][,option[=value]...]
Schemes: pvc (default), nfs, secret, configmap
Options: retain, rwx/rox/rwop, size, storageClass, ro
Secret/configmap volumes reference pre-existing K8s resources (no PVC created).

### Security context priority
1. HelxInst.Spec.SecurityContext (explicit override)
2. HTTP GET to HelxUser.Spec.UserHandle URL
3. Omitted

### Build commands
make build        # compile bin/manager
make test         # unit + controller tests (envtest)
make e2e          # e2e tests against live cluster
make manifests    # regenerate CRD manifests (after changing api/v1/*_types.go)
make generate     # regenerate DeepCopy methods

### After modifying api/v1/*_types.go
Always run: make manifests generate

### Test structure
- Unit tests: template_io/, helxapp_operations/, connect/
- Controller tests (envtest): controllers/ (Ginkgo v2 + Gomega)
- E2E tests (live cluster): e2e/ (separate Go module, 22 tests)

### RBAC
- Namespace-scoped: Roles + RoleBindings, WATCH_NAMESPACE env var
- Cluster-scoped: ClusterRoles + ClusterRoleBindings, no namespace restriction
- Controller needs: CRD verbs + deployments + services + PVCs

### Labels on derived objects
helx.renci.org/id: <UUID>          — set-based lookup/deletion
helx.renci.org/retain: "true"      — survives instance deletion
helx.renci.org/app-name, username, app-class-name, instance-name

### Key patterns
- Objects with helx.renci.org/retain: "true" survive instance deletion
- PVC patches filter out "remove" operations to protect bound claims
- Templates parsed at startup via Initialize() from /templates directory
- All derived objects share label helx.renci.org/id: <UUID>
```

</details>

---

## License

Copyright 2023.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
