# App Spec Module Specification

Design document for `helx.app` (`helx/src/helx/app/`) — a module that parses
docker-compose-like app definition files and converts them into typed
objects suitable for building HelxApp CRDs.

> **Status: implemented.** This document describes the design as built.
> The module was originally named `appspec` and has been renamed to `app`,
> packaged as part of the `helx` library.

---

## 1. Purpose

Each app in the HeLx registry points to a **docker-compose YAML file**
(the "spec") that defines the app's containers, images, ports,
environment, volumes, and resource limits.  Today, `System.parse()` in
`tycho/model.py` (lines 338–463) converts these specs into a `System`
model that tycho then templates into raw Kubernetes manifests.

In the new architecture, the helxapp-controller creates workloads from
HelxApp CRDs.  The `helx.app` module replaces the parsing half of
`System.parse()` — it reads the compose spec, extracts the relevant
fields, and produces typed objects that map directly to `HelxAppSpec`
and its constituent `AppServiceSpec` entries from `kube.models`.

The `registry` module already references these specs by name via
`spec_dir/{app_id}/docker-compose.yaml` and loads them through
`RegistryLoader.load_spec()`.  The `helx.app` module receives the
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
`{{ helx_registry }}`.  These are rendered **before** the `helx.app`
module sees the dict — the loader handles this.  The `helx.app` module
receives a fully resolved dict with no template expressions.

### 2.8 Extended Resource Model (`x-helx-resources`)

Standard docker-compose `deploy.resources` is insufficient for
Kubernetes and the appstore UI because:

1. **GPU resources** on Kubernetes are not simple counts — they are
   typed extended resources (e.g. `nvidia.com/gpu`) managed by device
   plugins.  The compose `gpus` field and `devices[].capabilities`
   syntax have no way to name the resource type.
2. **The appstore UI** presents sliders that let users choose resource
   levels between a minimum and maximum.  Compose only has
   `limits` (max) and `reservations` (min request), but no concept of
   "the user may choose anywhere in this range."
3. **Kubernetes distinguishes requests from limits** for scheduling vs.
   OOM-kill thresholds.  The compose model conflates reservations
   (scheduling) with what should be independently tunable
   request/limit pairs.

To address these, the spec file supports an `x-helx-resources`
extension alongside (or instead of) the standard `deploy.resources`.
The parser reads `x-helx-resources` when present; if absent, it falls
back to the standard compose resources.

```yaml
version: "3"
services:
  jupyter:
    image: jupyter/scipy:latest
    ports:
      - 8888:8888
    x-helx-resources:
      bounds:
        cpu:
          min: "0.5"
          max: "8"
          default_request: "1"
          default_limit: "4"
        memory:
          min: 512Mi
          max: 32Gi
          default_request: 1Gi
          default_limit: 4Gi
        gpu:
          resource_name: nvidia.com/gpu    # explicit K8s resource name
          min: "0"
          max: "2"
          default_request: "0"
          default_limit: "0"
        ephemeral-storage:
          min: 1Gi
          max: 50Gi
          default_request: 5Gi
          default_limit: 10Gi
      lock: false          # if true, request == limit (no slider)
```

#### Design rationale

| Concept | Where it lives | Who consumes it |
|---------|---------------|-----------------|
| **bounds** (min/max per resource) | `x-helx-resources.bounds` in spec → `resourceBounds` in HelxApp CRD | Appstore UI: populates slider range |
| **default request/limit** | `default_request` / `default_limit` in each bound | Appstore UI: initial slider position; HelxInst if user accepts defaults |
| **actual request/limit** | User's slider choice → `HelxInstSpec.resources[svc].request` / `.limit` | Controller: applied to the Pod |
| **GPU resource name** | `gpu.resource_name` (defaults to `nvidia.com/gpu`) | Controller: used as the K8s resource key |
| **lock** | `x-helx-resources.lock` | If true, UI hides sliders; request == limit == default |

This maps cleanly to the existing CRD model:

- `HelxApp.spec.services[].resourceBounds` stores the bounds and
  defaults — advisory, not enforced by the controller.
- `HelxInst.spec.resources[svc].request` / `.limit` stores the user's
  actual choice, validated against bounds by appstore before creating
  the CRD.
- The controller applies the HelxInst resources to the Pod spec.

#### Fallback to compose resources

When `x-helx-resources` is absent, the parser falls back to the
standard compose model:

| Compose | Interpreted as |
|---------|---------------|
| `deploy.resources.limits` | max bound and default limit |
| `deploy.resources.reservations` | min bound and default request |

This preserves backward compatibility with existing spec files.

### 2.9 Per-User Substitution (`x-helx-vars`)

Today, `System.parse()` does a fragile double-pass: it dumps the
entire spec to YAML, renders it as a Jinja2 template with env vars
containing `username`, `identifier`, etc., then re-parses.  This
conflates two distinct template stages (registry-level settings like
`{{ helx_registry }}` vs. per-instance values like `username`), and
it happens at start-time — but the app catalog must be built at
server startup, before any user has logged in.

#### The lifecycle problem

The registry is parsed and compose specs are loaded **at catalog-build
time** (server startup) so the UI can display the list of launchable
apps.  At this point no user context exists — there is no username,
no identifier, no access token.  Yet the compose spec may contain
references to those values in environment variables, volume paths, and
commands.

If per-user references use Jinja2 syntax (`{{ username }}`), the
catalog-time Jinja2 render will either raise `UndefinedError` or
silently produce empty strings — corrupting the parsed spec.

#### Solution: distinct `${varname}` syntax

Per-user variable references use **`${varname}`** — a shell-style
syntax that Jinja2 ignores.  This cleanly separates the two
evaluation stages:

| Stage | Syntax | Resolver | When | What's available |
|-------|--------|----------|------|-----------------|
| **Catalog build** | `{{ setting }}` (Jinja2) | `RegistryLoader.load_spec()` | Server startup, before login | `settings` from registry YAML (`helx_registry`, etc.) |
| **Instance creation** | `${varname}` | Appstore + controller | User launches an app | Per-user context from `Principal` / `HelxUser` |

The Jinja2 pass resolves `{{ helx_registry }}` at catalog time.
`${username}` passes through untouched — it is an opaque string to
Jinja2, to `yaml.safe_load()`, and to the `helx.app` parser.  It is
resolved later, at instance creation time.

#### The `x-helx-vars` declaration

The spec file declares which per-user variables it expects via a
top-level `x-helx-vars` section.  This is **declarative metadata**:
it does not cause substitution by itself, but tells the system which
`${…}` references the spec contains and what they mean.

```yaml
version: "3"
x-helx-vars:
  - username          # logged-in user's name
  - identifier        # unique instance UUID
  - access_token      # OAuth access token

services:
  jupyter:
    image: jupyter/scipy:latest
    environment:
      NB_USER: "${username}"
      NB_PREFIX: "/private/jupyter/${username}/${identifier}"
    volumes:
      - "${username}-home:/home/${username},rwx,retain"
```

#### Well-known variable vocabulary

The set of per-user variables is system-defined, not app-defined.
Each app declares which subset it needs via `x-helx-vars`.

| Variable | Source | Description |
|----------|--------|-------------|
| `username` | `Principal.username` / `HelxUser.spec.userName` | Logged-in user's name |
| `identifier` | Generated UUID | Unique per-instance identifier |
| `access_token` | `Principal.access_token` / `HelxUser.spec.tokens.access` | OAuth access token |
| `refresh_token` | `Principal.refresh_token` / `HelxUser.spec.tokens.refresh` | OAuth refresh token |
| `host` | Request host | The hostname of the appstore |

These correspond directly to the values that `TychoContext.start()`
passes today (context.py:303–310).

#### Resolution protocol

1. **Catalog build** — `RegistryLoader.load_spec()` renders Jinja2
   with `settings`.  `${varname}` references are inert strings —
   they pass through Jinja2 and YAML parsing unchanged.

2. **Appspec parse** — `parse_compose()` extracts `x-helx-vars` as
   metadata on the `ComposeApp`.  String values containing `${…}`
   are preserved as-is.  The parser optionally validates that every
   `${…}` reference in the spec appears in the `x-helx-vars` list.

3. **HelxApp CRD** — `build_helxapp_spec()` stores the spec with
   `${varname}` literals in environment, command, and volume values.
   The `helx_vars` list is stored on the HelxApp so the appstore can
   inspect required variables.

4. **Instance creation** — When a user launches an app, the appstore
   resolves each declared variable from the user's `Principal`
   context and passes the bindings as part of the `HelxInst` spec:

   ```python
   HelxInstSpec(
       app_name="jupyter",
       user_name="alice",
       vars={"username": "alice", "identifier": "a1b2c3", ...},
       resources={...},
   )
   ```

5. **Controller** — The helxapp-controller substitutes `${varname}`
   in the HelxApp template using the var bindings from the HelxInst
   before creating the Pod.  This is a simple string replacement —
   no template engine required.

#### Why the appstore resolves bindings, not the controller alone

The appstore is the component that holds the user session (`Principal`,
OAuth tokens).  The controller only sees the CRD objects.  By having
the appstore populate `HelxInst.spec.vars` from the session context,
the controller remains a generic template applicator — it doesn't
need to know about OAuth, session management, or user stores.

#### Appstore user context

The appstore maintains per-user context (username, OAuth tokens, host)
in the `Principal` object (tycho/context.py:26–31) and passes it via
`extra_container_env`.  In the new model, this context populates the
`vars` map on the HelxInst.  The `x-helx-vars` declaration makes the
dependency explicit rather than relying on implicit env var injection.

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

## 4. Module Design for `helx.app`

### 4.1 File Layout

```
helx/src/helx/app/
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
    options: dict[str, str] = field(default_factory=dict)  # e.g. rwx, retain

    def to_dsl_string(self) -> str:
        """Convert to volume DSL format for HelxApp spec."""
        dsl = f"{self.source}:{self.mount_path}"
        if self.sub_path:
            dsl = f"{self.source}:{self.mount_path}#{self.sub_path}"
        if self.options:
            opts = ",".join(
                f"{k}={v}" if v else k for k, v in self.options.items()
            )
            dsl = f"{dsl},{opts}"
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
class ResourceBound:
    """Min/max/default range for a single resource type."""
    min: str | None = None
    max: str | None = None
    default_request: str | None = None
    default_limit: str | None = None
    resource_name: str | None = None   # explicit K8s name (e.g. "nvidia.com/gpu")


@dataclass
class ResourceBounds:
    """Full bounds specification from x-helx-resources.bounds."""
    cpu: ResourceBound | None = None
    memory: ResourceBound | None = None
    gpu: ResourceBound | None = None
    ephemeral_storage: ResourceBound | None = None
    lock: bool = False                  # if True, request == limit == default


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
    resource_bounds: ResourceBounds | None = None  # from x-helx-resources
    depends_on: list[str] = field(default_factory=list)
    liveness_probe: ProbeSpec | None = None
    readiness_probe: ProbeSpec | None = None


@dataclass
class ComposeApp:
    """The complete parsed result of a docker-compose spec."""
    services: list[ComposeService] = field(default_factory=list)
    helx_vars: list[str] = field(default_factory=list)  # from x-helx-vars

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

    Extracts top-level x-helx-vars into ComposeApp.helx_vars.
    For each service, prefers x-helx-resources over deploy.resources.
    """

def parse_service(
    name: str,
    svc: dict,
    probes: dict | None = None,
) -> ComposeService:
    """Parse a single service dict.

    If the service has x-helx-resources, parse_helx_resources() is
    called and the result stored on ComposeService.resource_bounds.
    The limits/requests fields are also populated from the bounds'
    default_limit/default_request values for backward compatibility.
    """

def parse_ports(raw_ports: list) -> list[int]:
    """Extract container ports from compose port entries."""

def parse_environment(env: dict | list) -> dict[str, str]:
    """Normalize environment to a str→str dict."""

def parse_volumes(raw_volumes: list[str]) -> list[VolumeMount]:
    """Parse compose volume strings into VolumeMount objects."""

def parse_resources(raw: dict) -> ComposeResources:
    """Parse a limits or reservations dict."""

def parse_helx_resources(raw: dict) -> ResourceBounds:
    """Parse an x-helx-resources dict into ResourceBounds.

    Each key in raw["bounds"] maps to a ResourceBound:
        cpu, memory, gpu, ephemeral-storage.
    The gpu bound may include a resource_name (default: nvidia.com/gpu).
    raw.get("lock", False) sets ResourceBounds.lock.
    """

def parse_resource_bound(raw: dict) -> ResourceBound:
    """Parse a single resource bound dict (min/max/default_request/default_limit)."""

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

def bounds_to_resource_bounds(bounds: ResourceBounds) -> dict:
    """Convert ResourceBounds to the dict structure for HelxApp CRD.

    Output shape matches AppServiceSpec.resource_bounds:
    {
        "cpu": {"min": "0.5", "max": "8",
                "defaultRequest": "1", "defaultLimit": "4"},
        "memory": {...},
        "nvidia.com/gpu": {"min": "0", "max": "2", ...},
        "ephemeral-storage": {...},
        "lock": false
    }

    The GPU key uses resource_name from the bound (default: nvidia.com/gpu).
    Only non-None bounds are included.
    """

def bounds_to_default_resources(bounds: ResourceBounds) -> tuple[ComposeResources, ComposeResources]:
    """Extract default request/limit from bounds as ComposeResources pair.

    Returns (requests, limits) populated from default_request/default_limit.
    Used when x-helx-resources is present but caller needs backward-
    compatible ComposeResources (e.g. for fallback or validation).
    """
```

### 4.5 `exceptions.py`

```python
class ParseError(KubeError):
    """Raised when a compose spec cannot be parsed."""
```

### 4.6 `__init__.py` — Public API

```python
from helx.app.parser import parse_compose
from helx.app.models import (
    ComposeApp, ComposeService, ComposeResources,
    ResourceBounds, ResourceBound,
    VolumeMount, ProbeSpec,
)
from helx.app.resource_map import to_k8s_resources, bounds_to_resource_bounds
from helx.app.exceptions import ParseError
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

#### Standard compose resources (fallback)

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

#### Extended resources (`x-helx-resources`)

When present on a service, `x-helx-resources` takes precedence over
`deploy.resources`.  The parser applies these rules:

1. **Presence check**: If `svc.get("x-helx-resources")` exists, call
   `parse_helx_resources()`.  Otherwise fall back to
   `deploy.resources`.
2. **Bounds parsing**: Each key in `bounds` (`cpu`, `memory`, `gpu`,
   `ephemeral-storage`) maps to a `ResourceBound` with fields `min`,
   `max`, `default_request`, `default_limit`.  All are optional
   strings.
3. **GPU resource name**: `bounds.gpu.resource_name` defaults to
   `"nvidia.com/gpu"` if the `gpu` bound exists but `resource_name`
   is absent.
4. **Lock flag**: `x-helx-resources.lock` (default `false`).  When
   true, the UI should not present sliders and should use the default
   values directly.
5. **Default backfill**: The parser also populates
   `ComposeService.limits` and `.requests` from
   `default_limit`/`default_request` of each bound.  This ensures
   that code paths that only inspect the simple `ComposeResources`
   still get reasonable values.

| `x-helx-resources` field | `ResourceBound` field | Notes |
|---|---|---|
| `bounds.cpu.min` | `cpu.min` | String, may be fractional |
| `bounds.cpu.max` | `cpu.max` | |
| `bounds.cpu.default_request` | `cpu.default_request` | → also `ComposeService.requests.cpu` |
| `bounds.cpu.default_limit` | `cpu.default_limit` | → also `ComposeService.limits.cpu` |
| `bounds.gpu.resource_name` | `gpu.resource_name` | Defaults to `nvidia.com/gpu` |
| `bounds.lock` | `ResourceBounds.lock` | Boolean |

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
    │  RegistryLoader.load_spec()     ← Jinja2 renders {{ settings }};
    │       │                            ${varname} passes through
    │       ▼
    │   dict (raw compose, with ${varname} literals in values)
    │       │
    │  helx.app.parse_compose(spec, ext=app.ext)
    │       │
    │       ▼
    │   ComposeApp                    ← .helx_vars extracted
    │       │                            ${varname} preserved in strings
    │       │
    │  build_helxapp_spec(app, compose_spec)
    │       │
    │       ▼
    │   HelxAppSpec  ──→  HelxAppManager.ensure()
    │       │               (template with ${} placeholders)
    │       │
    │  [user launches app]
    │       │
    │  build_helxinst_spec(app, principal, ...)
    │       │               (resolves vars from Principal)
    │       ▼
    │   HelxInstSpec ──→  HelxInstManager.create()
    │       │               vars={"username": "alice", ...}
    │       │
    │  [controller reconciles]
    │       └── substitutes ${varname} in HelxApp with HelxInst.vars
    │           creates Deployment + Service + PVCs
    │
    └─ ResolvedApp.ext     ← probes from registry
    └─ ResolvedApp.security_context  ← security context from registry
```

### 6.2 How `registry.spec_builder` Changes

The current `spec_builder.py` in the registry module inlines compose
parsing.  With `helx.app`, it becomes a thin adapter:

```python
from helx.app import parse_compose, to_k8s_resources, bounds_to_resource_bounds

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

        # Resource bounds: prefer x-helx-resources; fall back to compose
        if svc.resource_bounds is not None:
            rb = bounds_to_resource_bounds(svc.resource_bounds)
        elif svc.limits.cpu or svc.requests.cpu:
            rb = {
                "limits": to_k8s_resources(svc.limits).to_dict(),
                "requests": to_k8s_resources(svc.requests).to_dict(),
            }
        else:
            rb = None

        svc_specs.append(AppServiceSpec(
            name=svc.name,
            image=svc.image,
            command=svc.command,
            environment=svc.environment,
            ports=ports,
            volumes={v.source: v.to_dsl_string() for v in svc.volumes},
            security_context=app.security_context,
            resource_bounds=rb,
        ))
    return HelxAppSpec(
        app_class_name=app.app_id,
        services=svc_specs,
        # helx_vars passed through so appstore can validate context
        # before creating HelxInst
        helx_vars=compose_app.helx_vars or None,
    )
```

Note: `HelxAppSpec` gains an optional `helx_vars: list[str] | None`
field so the appstore UI / API can inspect which per-user variables
the spec requires.  The controller uses this list to know which
`${varname}` references to substitute from `HelxInst.spec.vars`.

`HelxInstSpec` gains an optional `vars: dict[str, str] | None` field
populated by the appstore from the user's `Principal` session context
at launch time (see `registry-module-spec.md` §5.2).

### 6.3 What the Module Does NOT Do

The following are **not** the `helx.app` module's responsibility:

- **I/O**: Loading files or fetching URLs.  The registry loader does
  that.
- **Jinja2 rendering**: Done by the loader before the dict reaches
  `helx.app`.
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
| GPU type hardcoded to `nvidia.com/gpu` with no override | `ResourceBound.resource_name` allows explicit K8s resource name per bound |
| No min/max range for resources — UI must infer from env vars and view logic | `ResourceBounds` provides explicit min/max/default per resource type |
| Requests and limits conflated (reservations treated as both request floor and scheduling hint) | `default_request` and `default_limit` are independent values in each bound |
| Per-user substitution via fragile double-pass Jinja2 rendering | `x-helx-vars` declares variables explicitly with `${varname}` syntax that Jinja2 ignores; resolved at instance creation via `HelxInst.spec.vars` |
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
| `test_parse_helx_resources_full` | Full `x-helx-resources` → ResourceBounds with all four resource types |
| `test_parse_helx_resources_gpu_name` | `gpu.resource_name: "amd.com/gpu"` → stored on ResourceBound |
| `test_parse_helx_resources_gpu_default_name` | Missing `resource_name` → defaults to `nvidia.com/gpu` |
| `test_parse_helx_resources_lock` | `lock: true` → `ResourceBounds.lock == True` |
| `test_parse_helx_resources_partial` | Only `cpu` bound → other bounds are None |
| `test_helx_resources_backfills_limits_requests` | `default_request`/`default_limit` → populate `svc.requests`/`svc.limits` |
| `test_helx_resources_overrides_deploy_resources` | Both present → `x-helx-resources` wins, `deploy.resources` ignored |
| `test_parse_helx_vars` | `x-helx-vars: [username, identifier]` → `ComposeApp.helx_vars` |
| `test_parse_helx_vars_absent` | No `x-helx-vars` → empty list |
| `test_helx_vars_preserves_templates` | `${username}` in environment values preserved as literal string |
| `test_helx_vars_validates_references` | `${unknown}` in spec but not in `x-helx-vars` → optional warning or error |

### 8.2 `test_models.py` — Data Model Behavior

| Test | What It Verifies |
|------|-----------------|
| `test_volume_mount_to_dsl_simple` | `VolumeMount("pvc", "/data")` → `"pvc:/data"` |
| `test_volume_mount_to_dsl_subpath` | `VolumeMount("pvc", "/data", "sub")` → `"pvc:/data#sub"` |
| `test_volume_mount_to_dsl_options` | `VolumeMount("pvc", "/data", options={"rwx": "", "retain": ""})` → `"pvc:/data,rwx,retain"` |
| `test_compose_app_get_service` | Lookup by name returns correct service |
| `test_compose_app_get_service_missing` | Lookup for missing name returns None |
| `test_resource_bound_defaults` | `ResourceBound()` → all fields None |
| `test_resource_bounds_lock_default` | `ResourceBounds()` → `lock == False` |

### 8.3 `test_resource_map.py` — Compose → K8s Translation

| Test | What It Verifies |
|------|-----------------|
| `test_to_k8s_full` | All compose fields map to ResourceSpec fields |
| `test_to_k8s_partial` | Only populated fields appear |
| `test_to_k8s_empty` | Empty ComposeResources → empty ResourceSpec |
| `test_extract_gpu_from_devices` | `[{capabilities: ["gpu"], count: 2}]` → `"2"` |
| `test_extract_gpu_no_gpu_device` | `[{capabilities: ["tpu"]}]` → None |
| `test_extract_gpu_empty` | `[]` → None |
| `test_bounds_to_resource_bounds_full` | All four resource types → dict with K8s resource names as keys |
| `test_bounds_to_resource_bounds_gpu_custom_name` | `resource_name: "amd.com/gpu"` → key is `"amd.com/gpu"` |
| `test_bounds_to_resource_bounds_gpu_default_name` | No `resource_name` → key is `"nvidia.com/gpu"` |
| `test_bounds_to_resource_bounds_lock` | `lock: true` → `{"lock": true}` in output dict |
| `test_bounds_to_resource_bounds_partial` | Only cpu bound → only `"cpu"` key present |
| `test_bounds_to_resource_bounds_empty` | No bounds → empty dict (plus `lock: false`) |
| `test_bounds_to_default_resources` | Extracts `default_request`/`default_limit` into ComposeResources pair |
| `test_bounds_to_default_resources_partial` | Missing defaults → None fields in ComposeResources |

---

## 9. Dependencies

| Dependency | Used For | Already in Project |
|---|---|---|
| None | The module is pure Python with no external dependencies | — |

The module operates on plain dicts (already parsed from YAML) and
produces dataclasses.  It imports `kube.models.ResourceSpec` only in
`resource_map.py` for the translation layer.

---

## 10. Migration Status

Migration is complete:

1. `helx.app` module is implemented with its own tests (`helx/src/helx/app/tests/`).
2. `helx.registry.spec_builder.build_helxapp_spec()` uses `helx.app.parse_compose()`
   for all compose parsing.
3. The tycho `System.parse()`, `Container`, `Limits`, `Volumes`, `Probe`,
   `HttpProbe`, `TcpProbe` classes are no longer used on the critical path.
   The `appstore/tycho/` directory is retained for reference but is not
   imported by the app-launch pipeline.
