# App Spec Module Specification

Design document for `appstore/appspec/` — a module that parses
docker-compose-like app definition files and converts them into typed
objects suitable for building HelxApp CRDs.

---

## 1. Purpose

Each app in the HeLx registry points to a **docker-compose YAML file**
(the "spec") that defines the app's containers, images, ports,
environment, volumes, and resource limits.  Today, `System.parse()` in
`tycho/model.py` (lines 338–463) converts these specs into a `System`
model that tycho then templates into raw Kubernetes manifests.

In the new architecture, the helxapp-controller creates workloads from
HelxApp CRDs.  The `appspec` module replaces the parsing half of
`System.parse()` — it reads the compose spec, extracts the relevant
fields, and produces typed objects that map directly to `HelxAppSpec`
and its constituent `AppServiceSpec` entries from `kube.models`.

The `registry` module already references these specs by name via
`spec_dir/{app_id}/docker-compose.yaml` and loads them through
`RegistryLoader.load_spec()`.  The `appspec` module receives the
parsed dict and converts it to typed objects — it does not do I/O.

---

## 2. What the Spec Files Look Like

### 2.1 Canonical Example

From `fu/jupyter-notebook-example.yaml`:

```yaml
version: "3"
services:
  jupyter-helx-notebook:
    image: "{{ helx_registry }}/helxplatform/jupyter/helx-notebook:v0.1.5"
    ports:
      - 8888:8888
    volumes:
      - pvc://projects-pvc:/projects
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 8192M
        reservations:
          cpus: "1"
          memory: 8192M
```

### 2.2 A Multi-Service Example (Typical Pattern)

```yaml
version: "3"
services:
  webapp:
    image: "{{ helx_registry }}/myapp:latest"
    command: "start-server --port 8080"
    ports:
      - 8080:8080
    environment:
      - APP_MODE=production
      - DB_HOST=db
    volumes:
      - pvc://data-pvc/subdir:/data
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: 16384M
          gpus: "1"
          ephemeralStorage: 10Gi
        reservations:
          cpus: "2"
          memory: 8192M
  db:
    image: postgres:14
    ports:
      - 5432
    environment:
      POSTGRES_DB: mydb
    depends_on: []
```

### 2.3 Per-Service Fields

These are the docker-compose fields that the module must extract:

| Field | Type | Description |
|-------|------|-------------|
| `image` | str | Container image (may contain Jinja2 templates, already rendered by loader) |
| `command` | str or list | Override CMD; string is split on whitespace |
| `entrypoint` | str or list | Override ENTRYPOINT; string is split on whitespace |
| `ports` | list | Port mappings: `"8888:8888"`, `"8888"`, or `8888` |
| `expose` | list | Ports to expose without host mapping |
| `environment` | dict or list | `{KEY: val}` or `["KEY=val"]` |
| `volumes` | list[str] | Volume mounts: `source:dest` or `pvc://name/subpath:dest` |
| `deploy.resources.limits` | dict | `{cpus, memory, gpus, ephemeralStorage}` |
| `deploy.resources.reservations` | dict | Same shape; used as requests |
| `deploy.resources.reservations.devices` | list | GPU devices: `[{capabilities: ["gpu"], count: N}]` |
| `depends_on` | list | Service dependency ordering |

### 2.4 Resource Field Mapping

The compose spec uses docker-compose naming.  The controller uses
Kubernetes naming.  The mapping is:

| Compose Field | Kubernetes Equivalent | Notes |
|---|---|---|
| `cpus` | `cpu` | String; may be fractional (`"0.5"`) |
| `memory` | `memory` | String with unit (`"8192M"`, `"4Gi"`) |
| `gpus` | `nvidia.com/gpu` | String |
| `ephemeralStorage` | `ephemeral-storage` | String with unit |
| `reservations.devices[].capabilities: ["gpu"]` | `nvidia.com/gpu` | Alternate GPU syntax; `count` field gives quantity |

### 2.5 Volume Syntax

Tycho supports a `pvc://` URI scheme for volume mounts:

```
pvc://<pvc_name>[/<subpath>]:<container_path>
```

The helxapp-controller uses the volume DSL from `kube.volumes`
instead.  The mapping is:

| Compose Volume | Volume DSL |
|---|---|
| `pvc://mypvc:/data` | `mypvc:/data` |
| `pvc://mypvc/subdir:/data` | `mypvc:/data#subdir` |
| `data-vol:/data` | `data-vol:/data` |

### 2.6 Probe Injection

Probes do not come from the compose file — they come from the
registry's `ext.kube` field and are passed in alongside the compose
spec.  Probe formats:

```yaml
# Command probe
livenessProbe:
  cmd: ["pgrep", "jupyter"]
  delay: 5
  period: 5

# HTTP probe
readinessProbe:
  httpGet:
    path: /api/status
    port: 8888
  delay: 10
  period: 10

# TCP probe
livenessProbe:
  tcpSocket:
    port: 5432
  delay: 5
  period: 5

# Disable a probe
readinessProbe: "none"
```

### 2.7 Jinja2 Template Variables

The compose file may contain Jinja2 expressions like
`{{ helx_registry }}`.  These are rendered **before** the appspec
module sees the dict — the loader handles this.  The appspec module
receives a fully resolved dict with no template expressions.

---

## 3. What Tycho Does Today

`System.parse()` (model.py:338–463) performs these steps:

1. Extract `security_context` from the system dict (injected by
   registry).
2. Inject `identifier`, `username`, `system_name`, `system_port` into
   the env dict.
3. Re-render the entire spec dict as a Jinja2 template with the env
   dict — this substitutes `{{ username }}` etc. in probe paths and
   other fields.
4. For each service in `services`:
   a. Extract `entrypoint` (split string to list).
   b. Inject default volumes from tycho config (PVC mounts based on
      env vars `STDNFS_PVC`, `CREATE_HOME_DIRS`, etc.).
   c. Parse `ports` — split `"host:container"` format.
   d. Parse `expose`.
   e. Merge environment from spec + registry + system env.
   f. Extract `ext.kube.livenessProbe` / `readinessProbe`.
   g. Extract `deploy.resources.limits` → limits dict.
   h. Extract `deploy.resources.reservations` → requests dict.
   i. Extract `volumes`, `depends_on`, `image`.
   j. Build a container dict with all the above.
5. Construct a `System` object with all containers, services, security
   context, and metadata.

### 3.1 Problems with the Current Approach

| Problem | Impact |
|---------|--------|
| `System.parse()` is a 125-line static method that mixes parsing, env injection, volume injection, and model construction | Untestable without mocking env vars and config |
| Environment variable injection into the spec is done via `yaml.dump` → Jinja2 render → iterate results — fragile and hard to reason about | Template errors in spec silently produce wrong output |
| Default volume injection depends on 5+ env vars (`STDNFS_PVC`, `CREATE_HOME_DIRS`, `PARENT_DIR`, `SUBPATH_DIR`, `SHARED_DIR`) | Configuration scattered across env vars |
| Security context has 3 competing sources (env vars, registry, defaults) with unclear precedence | The `set_security_context` method (lines 256–276) contradicts itself: it checks `NFSRODS_UID` first, then `TYCHO_APP_RUN_AS_USER`, then the registry value — but the registry value unconditionally wins if present |
| `Limits` class uses compose field names (`cpus`, `memory`) not Kubernetes names | Requires translation at the K8s layer |
| GPU extraction is split between `Limits.gpus` and a separate `search_for_gpu_reservation()` that parses `devices[].capabilities` | Two code paths for the same concept |
| Volume parsing in `Volumes.process_volumes()` only supports `pvc://` format and raises on anything else | No support for standard `host:container` bind mounts |
| Probe model classes (`Probe`, `HttpProbe`, `TcpProbe`) are ad-hoc, don't produce K8s-compatible output | Need translation layer to K8s probe specs |

---

## 4. Module Design for `appstore/appspec/`

### 4.1 File Layout

```
appstore/appspec/
├── __init__.py          # Public API: parse_compose()
├── parser.py            # Core parsing: compose dict → ComposeApp
├── models.py            # ComposeService, ComposeResources, ProbeSpec, VolumeMount
├── resource_map.py      # Compose resource names → Kubernetes resource names
├── exceptions.py        # ParseError
└── tests/
    ├── __init__.py
    ├── test_parser.py
    ├── test_models.py
    └── test_resource_map.py
```

### 4.2 `models.py` — Parsed Compose Types

```python
@dataclass
class VolumeMount:
    """A parsed volume mount from a compose spec."""
    source: str            # PVC name or host path
    mount_path: str        # Container path
    sub_path: str | None = None
    is_pvc: bool = True

    def to_dsl_string(self) -> str:
        """Convert to volume DSL format for HelxApp spec."""
        dsl = f"{self.source}:{self.mount_path}"
        if self.sub_path:
            dsl = f"{self.source}:{self.mount_path}#{self.sub_path}"
        return dsl


@dataclass
class ProbeSpec:
    """A parsed probe definition from registry ext.kube."""
    probe_type: str        # "exec", "httpGet", "tcpSocket"
    delay: int = 0
    period: int = 10
    threshold: int | None = None

    # exec
    command: list[str] | None = None

    # httpGet
    path: str | None = None
    port: int | None = None
    http_headers: list[dict] | None = None

    # tcpSocket (uses port field above)


@dataclass
class ComposeResources:
    """Resource limits/requests extracted from deploy.resources."""
    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    ephemeral_storage: str | None = None


@dataclass
class ComposeService:
    """A single service parsed from a docker-compose spec."""
    name: str
    image: str
    command: list[str] | None = None
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[int] = field(default_factory=list)      # container ports
    expose: list[int] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    limits: ComposeResources = field(default_factory=ComposeResources)
    requests: ComposeResources = field(default_factory=ComposeResources)
    depends_on: list[str] = field(default_factory=list)
    liveness_probe: ProbeSpec | None = None
    readiness_probe: ProbeSpec | None = None


@dataclass
class ComposeApp:
    """The complete parsed result of a docker-compose spec."""
    services: list[ComposeService] = field(default_factory=list)

    def get_service(self, name: str) -> ComposeService | None:
        for svc in self.services:
            if svc.name == name:
                return svc
        return None
```

### 4.3 `parser.py` — The Core Parser

Pure functions that convert a parsed YAML dict into typed objects.

```python
def parse_compose(
    spec: dict,
    ext: dict | None = None,
) -> ComposeApp:
    """Parse a docker-compose dict into a ComposeApp.

    :param spec: Parsed docker-compose YAML (already Jinja2-rendered).
    :param ext: Registry ext dict (contains kube.livenessProbe etc.).
        Probe definitions are matched to services by name — if ext
        is provided at the top level, probes apply to all services.
    :raises ParseError: On missing required fields.
    """

def parse_service(
    name: str,
    svc: dict,
    probes: dict | None = None,
) -> ComposeService:
    """Parse a single service dict."""

def parse_ports(raw_ports: list) -> list[int]:
    """Extract container ports from compose port entries."""

def parse_environment(env: dict | list) -> dict[str, str]:
    """Normalize environment to a str→str dict."""

def parse_volumes(raw_volumes: list[str]) -> list[VolumeMount]:
    """Parse compose volume strings into VolumeMount objects."""

def parse_resources(raw: dict) -> ComposeResources:
    """Parse a limits or reservations dict."""

def parse_probe(raw: dict | str | None) -> ProbeSpec | None:
    """Parse a probe definition. Returns None for 'none' or absent."""
```

### 4.4 `resource_map.py` — Compose → Kubernetes Translation

```python
def to_k8s_resources(compose: ComposeResources) -> ResourceSpec:
    """Convert compose resource names to kube.models.ResourceSpec.

    Mapping:
        cpus → cpu
        memory → memory (pass through)
        gpus → gpu (mapped to nvidia.com/gpu by ResourceSpec)
        ephemeralStorage → ephemeral_storage
    """

def extract_gpu_from_devices(devices: list[dict]) -> str | None:
    """Extract GPU count from compose devices list.

    Handles: [{capabilities: ["gpu"], count: N}]
    """
```

### 4.5 `exceptions.py`

```python
class ParseError(KubeError):
    """Raised when a compose spec cannot be parsed."""
```

### 4.6 `__init__.py` — Public API

```python
from appspec.parser import parse_compose
from appspec.models import ComposeApp, ComposeService, ComposeResources, VolumeMount, ProbeSpec
from appspec.resource_map import to_k8s_resources
from appspec.exceptions import ParseError
```

---

## 5. Key Parsing Rules

### 5.1 Port Parsing

Input formats and their interpretation:

| Input | Container Port |
|-------|---------------|
| `"8888:8888"` | `8888` (after colon) |
| `"8888"` | `8888` |
| `8888` (int) | `8888` |
| `"3000:8080"` | `8080` (container port is the right side) |

### 5.2 Volume Parsing

| Input | Source | Mount Path | Sub Path |
|-------|--------|------------|----------|
| `pvc://mypvc:/data` | `mypvc` | `/data` | `None` |
| `pvc://mypvc/work:/data` | `mypvc` | `/data` | `work` |
| `data-vol:/data` | `data-vol` | `/data` | `None` |

The `pvc://` prefix is stripped.  The source is the PVC name, the
portion after the PVC name and before `:` is the sub-path, and the
right side of `:` is the container mount path.

### 5.3 Environment Parsing

Two formats are supported:

```yaml
# Dict format
environment:
  KEY: value
  OTHER: "123"

# List format
environment:
  - KEY=value
  - OTHER=123
  - FLAG_ONLY     # → {"FLAG_ONLY": ""}
```

Both produce `dict[str, str]`.

### 5.4 Resource Parsing

```yaml
deploy:
  resources:
    limits:
      cpus: "2"
      memory: 8192M
      gpus: "1"
      ephemeralStorage: 10Gi
    reservations:
      cpus: "1"
      memory: 4096M
      devices:
        - capabilities: ["gpu"]
          count: 1
```

`limits` maps to `ComposeResources` directly. `reservations` maps to
`ComposeResources` with GPU extracted from either the top-level `gpus`
key or from `devices[].capabilities`.

### 5.5 Command / Entrypoint Parsing

```yaml
# String → split on whitespace
command: "start-notebook.sh --no-browser"
# → ["start-notebook.sh", "--no-browser"]

# List → pass through
entrypoint:
  - /bin/sh
  - -c
  - "exec jupyter"
# → ["/bin/sh", "-c", "exec jupyter"]
```

If both `command` and `entrypoint` are present, `entrypoint` takes
precedence (matching docker-compose semantics where entrypoint
overrides CMD).

### 5.6 Probe Parsing

| Input | Probe Type | Fields |
|-------|-----------|--------|
| `{cmd: [...], delay: 5, period: 5}` | `exec` | `command`, `delay`, `period` |
| `{httpGet: {path: "/", port: 80}, delay: 10}` | `httpGet` | `path`, `port`, `delay` |
| `{tcpSocket: {port: 5432}}` | `tcpSocket` | `port` |
| `"none"` | — | Returns `None` (probe disabled) |
| absent | — | Returns `None` |

---

## 6. Integration with Registry and Kube

### 6.1 Data Flow

```
registry.yaml
    │
    ├─ spec_dir/{app_id}/docker-compose.yaml
    │       │
    │  RegistryLoader.load_spec()     ← Jinja2 render + YAML parse
    │       │
    │       ▼
    │   dict (raw compose)
    │       │
    │  appspec.parse_compose(spec, ext=app.ext)
    │       │
    │       ▼
    │   ComposeApp
    │       │
    │  to_helxapp_spec(app, compose_app)     ← new function in registry
    │       │
    │       ▼
    │   HelxAppSpec  ──→  HelxAppManager.ensure()
    │
    └─ ResolvedApp.ext     ← probes from registry
    └─ ResolvedApp.security_context  ← security context from registry
```

### 6.2 How `registry.spec_builder` Changes

The current `spec_builder.py` in the registry module inlines compose
parsing.  With `appspec`, it becomes a thin adapter:

```python
from appspec import parse_compose, to_k8s_resources

def build_helxapp_spec(app: ResolvedApp, compose_spec: dict) -> HelxAppSpec:
    compose_app = parse_compose(compose_spec, ext=app.ext)
    svc_specs = []
    for svc in compose_app.services:
        # Map ports: use registry service port as the exposed port
        ports = []
        for cp in svc.ports:
            registry_port = app.services.get(svc.name)
            ports.append(PortSpec(
                container_port=cp,
                port=registry_port or 0,
            ))

        svc_specs.append(AppServiceSpec(
            name=svc.name,
            image=svc.image,
            command=svc.command,
            environment=svc.environment,
            ports=ports,
            volumes={v.source: v.to_dsl_string() for v in svc.volumes},
            security_context=app.security_context,
            resource_bounds={
                "limits": to_k8s_resources(svc.limits).to_dict(),
                "requests": to_k8s_resources(svc.requests).to_dict(),
            } if svc.limits.cpu or svc.requests.cpu else None,
        ))
    return HelxAppSpec(app_class_name=app.app_id, services=svc_specs)
```

### 6.3 What the Module Does NOT Do

The following are **not** the appspec module's responsibility:

- **I/O**: Loading files or fetching URLs.  The registry loader does
  that.
- **Jinja2 rendering**: Done by the loader before the dict reaches
  appspec.
- **Default volume injection**: The legacy behavior of injecting
  `STDNFS_PVC`-based volumes from tycho config is deployment policy,
  not app specification.  This moves to the controller or is expressed
  in the registry/HelxApp spec directly.
- **Security context resolution**: Handled by the registry module and
  `kube.security`.
- **System-level env injection** (`identifier`, `username`,
  `system_name`): These are runtime values injected by the controller,
  not static spec properties.
- **Proxy rewrite / conn_string**: Controller-level concerns.

---

## 7. Improvements Over Tycho Model

| Issue in Tycho | Improvement |
|---|---|
| `System.parse()` is 125 lines mixing parsing with env injection and volume injection | `parse_compose()` is pure parsing — no env vars, no config, no side effects |
| Compose resource names (`cpus`, `ephemeralStorage`) leak into the model | `resource_map.to_k8s_resources()` translates at the boundary |
| GPU parsing split between `Limits.gpus` and `search_for_gpu_reservation()` | Single `parse_resources()` handles both `gpus` key and `devices[].capabilities` |
| `Volumes.process_volumes()` only supports `pvc://` format | `parse_volumes()` handles both `pvc://` and plain `source:dest` |
| Probe classes (`Probe`, `HttpProbe`, `TcpProbe`) are structurally inconsistent | Single `ProbeSpec` dataclass with `probe_type` discriminator |
| Environment merging (spec + registry + system) happens inside the parser | Parser only extracts spec-level env; merging is the caller's job |
| Port parsing inlined with string splitting | `parse_ports()` handles all formats (int, string, host:container) |
| No unit tests for compose parsing | `test_parser.py` covers every field and edge case |

---

## 8. Test Plan

### 8.1 `test_parser.py` — Core Parsing

| Test | What It Verifies |
|------|-----------------|
| `test_parse_minimal_service` | Service with just `image` produces valid ComposeService |
| `test_parse_ports_host_container` | `"8888:8888"` → container port 8888 |
| `test_parse_ports_container_only` | `"8888"` → container port 8888 |
| `test_parse_ports_int` | `8888` → container port 8888 |
| `test_parse_ports_different_mapping` | `"3000:8080"` → container port 8080 |
| `test_parse_environment_dict` | `{KEY: val}` → `{"KEY": "val"}` |
| `test_parse_environment_list` | `["K=V"]` → `{"K": "V"}` |
| `test_parse_environment_flag_only` | `["FLAG"]` → `{"FLAG": ""}` |
| `test_parse_volumes_pvc` | `pvc://mypvc:/data` → VolumeMount(source="mypvc", mount_path="/data") |
| `test_parse_volumes_pvc_subpath` | `pvc://mypvc/sub:/data` → VolumeMount(sub_path="sub") |
| `test_parse_volumes_plain` | `data-vol:/data` → VolumeMount(source="data-vol") |
| `test_parse_resources_limits` | `{cpus: "2", memory: "8192M"}` → ComposeResources |
| `test_parse_resources_gpu_direct` | `{gpus: "1"}` → gpu="1" |
| `test_parse_resources_gpu_devices` | `{devices: [{capabilities: ["gpu"], count: 2}]}` → gpu="2" |
| `test_parse_resources_ephemeral` | `{ephemeralStorage: "10Gi"}` → ephemeral_storage="10Gi" |
| `test_parse_command_string` | `"start.sh --port 8080"` → `["start.sh", "--port", "8080"]` |
| `test_parse_command_list` | `["start.sh", "--port"]` → pass through |
| `test_parse_entrypoint_precedence` | Both present → entrypoint wins |
| `test_parse_probe_exec` | `{cmd: [...]}` → ProbeSpec(probe_type="exec") |
| `test_parse_probe_http` | `{httpGet: {path, port}}` → ProbeSpec(probe_type="httpGet") |
| `test_parse_probe_tcp` | `{tcpSocket: {port}}` → ProbeSpec(probe_type="tcpSocket") |
| `test_parse_probe_none_string` | `"none"` → None |
| `test_parse_probe_absent` | Not present → None |
| `test_parse_multi_service` | Two services → ComposeApp with two ComposeService entries |
| `test_parse_expose` | `expose: [5432]` → expose list |
| `test_parse_depends_on` | `depends_on: [db]` → depends_on list |
| `test_missing_image_raises` | Service without `image` raises ParseError |

### 8.2 `test_models.py` — Data Model Behavior

| Test | What It Verifies |
|------|-----------------|
| `test_volume_mount_to_dsl_simple` | `VolumeMount("pvc", "/data")` → `"pvc:/data"` |
| `test_volume_mount_to_dsl_subpath` | `VolumeMount("pvc", "/data", "sub")` → `"pvc:/data#sub"` |
| `test_compose_app_get_service` | Lookup by name returns correct service |
| `test_compose_app_get_service_missing` | Lookup for missing name returns None |

### 8.3 `test_resource_map.py` — Compose → K8s Translation

| Test | What It Verifies |
|------|-----------------|
| `test_to_k8s_full` | All compose fields map to ResourceSpec fields |
| `test_to_k8s_partial` | Only populated fields appear |
| `test_to_k8s_empty` | Empty ComposeResources → empty ResourceSpec |
| `test_extract_gpu_from_devices` | `[{capabilities: ["gpu"], count: 2}]` → `"2"` |
| `test_extract_gpu_no_gpu_device` | `[{capabilities: ["tpu"]}]` → None |
| `test_extract_gpu_empty` | `[]` → None |

---

## 9. Dependencies

| Dependency | Used For | Already in Project |
|---|---|---|
| None | The module is pure Python with no external dependencies | — |

The module operates on plain dicts (already parsed from YAML) and
produces dataclasses.  It imports `kube.models.ResourceSpec` only in
`resource_map.py` for the translation layer.

---

## 10. Migration Path

1. Implement `appspec` module with its own tests.
2. Update `registry.spec_builder.build_helxapp_spec()` to use
   `appspec.parse_compose()` instead of inline parsing.
3. Verify that the `HelxAppSpec` output is identical.
4. Remove the inline parsing from `spec_builder.py`.
5. The tycho `System.parse()`, `Container`, `Limits`, `Volumes`,
   `Probe`, `HttpProbe`, `TcpProbe` classes become unused and can be
   removed when tycho is fully retired.
