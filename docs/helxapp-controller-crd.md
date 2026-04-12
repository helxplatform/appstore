# HelxApp Controller — CRD Reference

API group: `helx.renci.org/v1`

Three CRDs work together to create Kubernetes workloads. All three must exist and be correlated (by name) for a Deployment to be created.

```
HelxApp  (what to run)     ──┐
HelxUser (who is running)  ──┼── HelxInst references both ──► Deployment + Service + PVC
HelxInst (run it now)      ──┘
```

---

## HelxApp

Defines an application template — container images, ports, environment, volumes, probes, and optional Ambassador routing.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxApp
metadata:
  name: jupyter-notebook        # referenced by HelxInst.spec.appName
  namespace: my-ns
spec:
  appClassName: JupyterLab      # logical class name; appears in labels and templates
  services:                     # one entry per container
    - name: notebook            # container name; also the key for HelxInst.spec.resources
      image: "jupyter/base-notebook:latest"  # append ",Always" to force imagePullPolicy
      command:                  # optional entrypoint override (Go template expressions allowed)
        - start-notebook.sh
        - "--NotebookApp.token=''"
      init: false               # if true, this becomes an initContainer
      environment:              # lowest precedence in the 3-way merge (app < user < inst)
        JUPYTER_ENABLE_LAB: "yes"
        GREETING: "Hello {{ .system.UserName }}"  # Go template expression — resolved at render time
      secretsFrom:              # inject all keys from these Secrets as env vars
        - my-api-keys
      configMapsFrom:           # inject all keys from these ConfigMaps as env vars
        - shared-config
      ports:
        - containerPort: 8888   # port inside the container
          port: 8888            # if non-zero, a Kubernetes Service is created
      resourceBounds:           # advisory min/max for each resource (inst overrides)
        cpu:
          min: "0.5"
          max: "4"
        memory:
          min: 512Mi
          max: 8Gi
      securityContext:          # per-container security context
        runAsUser: 1000
        runAsGroup: 100
        fsGroup: 100
        supplementalGroups: [200, 300]
      volumes:                  # volumeId → volume source string (see Volume DSL below)
        data: "pvc://data-claim:/home/jovyan/work,size=10G,retain"
        shared: "nfs:////nfs-server/exports/shared:/mnt/shared"
        creds: "secret://api-secret:/etc/creds#api-key,ro"
        conf: "configmap://app-config:/etc/app-config"
      livenessProbe:            # optional (exec, httpGet, or tcpSocket)
        httpGet:
          path: /api/status
          port: 8888
        initialDelaySeconds: 30
        periodSeconds: 60
        failureThreshold: 3
      readinessProbe:           # optional (same structure as livenessProbe)
        httpGet:
          path: /api/status
          port: 8888
        periodSeconds: 10
      ambassador:               # optional Ambassador mapping
        ambassadorId: ""        # restrict to a specific Ambassador instance
        prefix: ""              # URL prefix (Go template; default: /private/<class>/<user>/<uuid>/)
        proxyRewrite: /         # upstream rewrite target
```

### Volume DSL

The `volumes` map values use a mini-language:

```
[scheme://]source:mountPath[#subPath][,option[=value]...]
```

| Scheme | K8s volume type | Creates PVC? | Source meaning |
|--------|----------------|-------------|---------------|
| `pvc` (default) | persistentVolumeClaim | Yes | Claim name |
| `nfs` | nfs | No | `//server/path` |
| `secret` | secret | No | Secret name |
| `configmap` | configMap | No | ConfigMap name |

Options: `retain`, `rwx`/`rox`/`rwop`, `size=<value>`, `storageClass=<name>`, `ro`

### Probe structure

Each probe specifies exactly one action type:

```yaml
# HTTP GET probe
httpGet:
  path: /healthz
  port: 8080
  scheme: HTTP                # optional (HTTP or HTTPS)
  httpHeaders:                # optional
    X-Custom-Header: value

# Exec probe
exec:
  command: ["cat", "/tmp/healthy"]

# TCP socket probe
tcpSocket:
  port: 3306
```

Timing fields (all optional, all int32):
- `initialDelaySeconds` — delay before first probe
- `periodSeconds` — interval between probes
- `failureThreshold` — consecutive failures before unhealthy

---

## HelxInst

A per-user instantiation request: "run this app for this user". Creating a HelxInst triggers Deployment creation once the referenced HelxApp and HelxUser both exist.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxInst
metadata:
  name: jupyter-notebook-abc123
  namespace: my-ns
spec:
  appName: jupyter-notebook     # must match HelxApp.metadata.name (or namespace/name)
  userName: alice               # must match HelxUser.metadata.name (or namespace/name)
  referenceID: "abc123"         # optional external correlation ID; exposed as ReferenceID env var
  environment:                  # highest precedence in the 3-way merge (app < user < inst)
    CUSTOM_VAR: "instance-value"
  secretsFrom:                  # merged with app and user secretsFrom lists
    - instance-secret
  configMapsFrom:               # merged with app and user configMapsFrom lists
    - instance-config
  securityContext:              # overrides LDAP/userHandle-derived context when present
    runAsUser: 1000
    runAsGroup: 100
  resources:                    # per-container resource requests/limits (keyed by service name)
    notebook:
      request:
        cpu: "1"
        memory: 2Gi
      limit:
        cpu: "4"
        memory: 8Gi
```

### Status (set by the controller)

```yaml
status:
  observedGeneration: 1         # tracks spec changes to avoid redundant reconciles
  uuid: "550e8400-..."          # assigned on first reconcile; labels all derived objects
```

---

## HelxUser

Represents a platform user. Provides user-level environment variables, volumes, and identity source configuration.

```yaml
apiVersion: helx.renci.org/v1
kind: HelxUser
metadata:
  name: alice                   # referenced by HelxInst.spec.userName
  namespace: my-ns
  labels:
    helx.renci.org/identity-source: ldap  # triggers LDAP identity resolution (see below)
spec:
  userHandle: "http://ldap-plugin:8080/users/alice"  # legacy; superseded by identity-source label
  environment:                  # middle precedence in the 3-way merge (app < user < inst)
    HOME: /home/alice
  secretsFrom:                  # merged with app and inst secretsFrom lists
    - user-secret
  configMapsFrom:               # merged with app and inst configMapsFrom lists
    - user-config
  volumes:                      # user-level volumes; mounted on every container in the deployment
    home: "nfs:////home-server/home/alice:/home/alice"
```

### Identity source

The label `helx.renci.org/identity-source` on metadata controls how the controller resolves the user's security context (UID, GID, groups).

| Label value | Behavior |
|------------|----------|
| `ldap` | Controller calls `$LDAP_URL/users/<name>` automatically. Also sets `USER_IDENTITY=ldap` env var and injects libnss-ldap config mounts if `LDAP_CONFIGMAP` is configured. |
| (absent) | Falls back to `spec.userHandle` URL if set; otherwise no identity resolution. |

The LDAP response JSON is parsed for: `runAsUser`, `runAsGroup`, `fsGroup`, `supplementalGroups`, with fallbacks `uidNumber` → `runAsUser` and `gidNumber` → `runAsGroup`.

---

## Relationships and Naming

```
HelxInst.spec.appName  ──references──►  HelxApp.metadata.name
HelxInst.spec.userName ──references──►  HelxUser.metadata.name
```

All three resources must be in the **same namespace**. Names can be simple (`myapp`) or namespace-qualified (`my-ns/myapp`); unqualified names are resolved in the HelxInst's namespace.

---

## Environment variable merge order

When the same env var key appears in multiple sources, the highest-precedence value wins:

```
HelxApp service.environment        (lowest)
  ↓ overridden by
HelxUser spec.environment
  ↓ overridden by
HelxInst spec.environment          (highest)
```

Additionally, the controller injects **system environment variables** into every container:

| Variable | Value |
|----------|-------|
| `ReferenceID` | `HelxInst.spec.referenceID` |
| `USER` | `HelxInst.spec.userName` |
| `HOST` | (empty) |
| `APP_CLASS_NAME` | `HelxApp.spec.appClassName` |
| `APP_NAME` | `HelxInst.spec.appName` |
| `INSTANCE_NAME` | `<namespace>/<inst-name>` |
| `USER_IDENTITY` | `ldap` (only when identity-source label is `ldap`) |

---

## Labels on derived objects

All Kubernetes objects created by the controller carry these labels:

| Label | Value | Purpose |
|-------|-------|---------|
| `executor` | `helxapp-controller` | Identifies the controller |
| `helx.renci.org/id` | Instance UUID | Links all objects to the HelxInst; used for deletion |
| `helx.renci.org/app-name` | App name | Filterable |
| `helx.renci.org/username` | User name | Filterable |
| `helx.renci.org/app-class-name` | App class name | On pod template |
| `helx.renci.org/instance-name` | Instance name | On pod template |
| `helx.renci.org/retain` | `"true"` | On PVCs that should survive instance deletion |

---

## Minimal working example

```yaml
# 1. Define the application
apiVersion: helx.renci.org/v1
kind: HelxApp
metadata:
  name: nginx-demo
  namespace: demo
spec:
  appClassName: Nginx
  services:
    - name: web
      image: nginx:latest
      ports:
        - containerPort: 80
          port: 80
---
# 2. Define the user
apiVersion: helx.renci.org/v1
kind: HelxUser
metadata:
  name: alice
  namespace: demo
spec: {}
---
# 3. Create an instance (triggers Deployment + Service creation)
apiVersion: helx.renci.org/v1
kind: HelxInst
metadata:
  name: nginx-demo-alice-001
  namespace: demo
spec:
  appName: nginx-demo
  userName: alice
```

This creates:
- `Deployment/nginx-demo-<uuid>` with one `nginx:latest` container
- `Service/nginx-demo-<uuid>` mapping port 80 to the container

---

## Full-featured example

```yaml
apiVersion: helx.renci.org/v1
kind: HelxApp
metadata:
  name: jupyter-lab
  namespace: research
spec:
  appClassName: JupyterLab
  services:
    - name: notebook
      image: "jupyter/scipy-notebook:latest,Always"
      command: ["start-notebook.sh", "--NotebookApp.token=''"]
      environment:
        JUPYTER_ENABLE_LAB: "yes"
      ports:
        - containerPort: 8888
          port: 8888
      volumes:
        work: "pvc://jupyter-work:/home/jovyan/work,size=20G,retain"
      livenessProbe:
        httpGet:
          path: /api/status
          port: 8888
        initialDelaySeconds: 30
        periodSeconds: 60
      readinessProbe:
        httpGet:
          path: /api/status
          port: 8888
        periodSeconds: 10
---
apiVersion: helx.renci.org/v1
kind: HelxUser
metadata:
  name: researcher1
  namespace: research
  labels:
    helx.renci.org/identity-source: ldap
spec:
  environment:
    DEFAULT_URL: /lab
  volumes:
    shared: "nfs:////nfs.example.com/shared:/mnt/shared,ro"
---
apiVersion: helx.renci.org/v1
kind: HelxInst
metadata:
  name: jupyter-lab-researcher1-run42
  namespace: research
spec:
  appName: jupyter-lab
  userName: researcher1
  referenceID: "run42"
  environment:
    NOTEBOOK_ARGS: "--collaborative"
  resources:
    notebook:
      request:
        cpu: "2"
        memory: 4Gi
      limit:
        cpu: "8"
        memory: 16Gi
```
