# Registry Module Specification

Design document for `helx.registry` (`helx/src/helx/registry/`) — the app-registry
processing module, producing `HelxApp` specs consumable by the
helxapp-controller.

> **Status: implemented.** This document describes the design as built.
> The module was originally located at `appstore/registry/` and has been
> moved to the `helx` library.

---

## 1. Purpose

The HeLx AppStore needs to know *what applications exist* before it can
instantiate them as Kubernetes workloads.  That catalog comes from a
**YAML app-registry file** — a declarative document that lists every
launchable application together with its metadata, container images,
ports, environment, and security contexts.

Today this processing lives inside `TychoContext` (context.py lines
45–180).  Its job is to:

1. Load the registry YAML from a local file.
2. Load a defaults YAML that is merged into every app.
3. Resolve a **product context** (e.g. `"braini"`, `"helx"`,
   `"eduhelx"`) — a named slice of the full registry.
4. Walk the context's **inheritance chain** (`extends`) to assemble the
   final set of apps via depth-first deep-merge.
5. Resolve **spec paths** so each app points to its local
   `docker-compose.yaml` specification.
6. On demand, **load** each app's docker-compose spec from that path,
   render Jinja2 template variables, and cache the result.
7. On demand, **load** the companion `.env` file for an app.
8. Merge registry-level `env` overrides into the settings.
9. When starting an app, merge the user's resource request, security
   context, ephemeral-storage, and service account into the spec — then
   hand the whole thing to the compute backend.

The new `registry` module must perform steps 1–8 identically (or with
clearly documented improvements) and replace step 9 with production of
`HelxAppSpec` / `HelxInstSpec` objects from the `kube.models` module.

> **Note — local-only registry.**  The legacy code supported fetching
> the registry and app specs from remote git URLs.  This added
> complexity (URL resolution, HTTP caching, branch-name substitution)
> that caused more problems than it solved.  The new module assumes all
> files — registry YAML, defaults YAML, docker-compose specs, and `.env`
> files — are present on the local filesystem.

---

## 2. What the Registry YAML Looks Like

See `fu/registry-example.yaml` for a full 808-line production example.
The top-level structure is:

```yaml
api: Tycho
version: 0.0.1

metadata:
  id: helx-app-registry
  name: HeLx Application Registry
  author: HeLx Dev

spec_dir: app-specs            # Base directory for docker-compose specs
                               # (relative to registry file, or absolute)

settings:                   # Jinja2 template variables for docker-compose
  helx_registry: containers.renci.org
  third_party_registry: docker.io

contexts:
  sys:                      # Operational overrides (probes, etc.)
    apps:
      jupyter-ds:
        ext:
          kube:
            livenessProbe:
              cmd: ["pgrep", "jupyter"]
              delay: 5
              period: 5

  common:                   # A base context extended by many products
    extends:
      - sys                 # Deep-merges sys's per-app overrides
    name: HeLx Common App Registry
    apps:
      jupyter-helx-tensorflow-nb:
        name: Jupyter HeLx Tensorflow Notebook
        description: …
        details: …
        docs: https://…
        services:
          jupyter-helx-tensorflow-nb: "8888"
        count: 1

  braini:                   # A product context
    extends:
      - common              # Inherits all of common's apps (including sys overlays)
    name: BRAIN-I App Registry
    jupyter-ds:             # Context-level securityContext override
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
    apps:                   # Additional apps unique to this product
      imagej:
        name: ImageJ Viewer
        …
```

### 2.1 Key Structural Rules

| Element | Location | Description |
|---------|----------|-------------|
| `contexts.<name>.extends` | list of strings | Inheritance — apps from all named contexts are deep-merged depth-first; child values override parent values at every nesting level |
| `contexts.<name>.apps` | dict | App definitions local to this context |
| `contexts.<name>.<app_id>` | dict (top-level key matching an app name) | Context-level overrides — typically `securityContext` — merged onto the app after inheritance resolution |
| `spec_dir` | string | Base directory for docker-compose specs; relative to registry file location, or absolute |
| `settings` | dict | Jinja2 variables substituted into docker-compose specs at load time |

> **Note — `mixin` keyword removed.** The legacy registry used both
> `extends` (shallow copy of app catalog) and `mixin` (deep-merge of
> per-app properties from a separate context).  Because `extends` now
> deep-merges at every level, `mixin` is redundant.  Contexts that were
> previously mixin-only (e.g. `sys`) are simply listed in `extends`
> instead.  See §3 for the unified algorithm.

### 2.2 Per-App Fields

These fields appear inside `contexts.<ctx>.apps.<app_id>`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | yes | Human-readable display name |
| `description` | str | yes | Short description |
| `details` | str | yes | Long description |
| `docs` | str | yes | Documentation URL |
| `services` | dict[str, str\|int] | yes | Map of container name → exposed port. Exactly one entry is typical. The key must match a service name in the app's docker-compose. |
| `spec` | str | no | Explicit path to docker-compose.yaml. If absent, synthesized as `{spec_dir}/{app_id}/docker-compose.yaml` |
| `icon` | str | auto | Synthesized as sibling of spec path |
| `count` | int | yes | Max concurrent instances per user. `-1` = unlimited, `1` = singleton |
| `serviceAccount` | str | no | K8s service account name for the pod |
| `securityContext` | dict | no | `{runAsUser, runAsGroup, fsGroup}` — applied at pod level |
| `ext.kube.livenessProbe` | dict | no | Probe definition: `{cmd, delay, period}` or `{httpGet: {path, port}, delay, period}` |
| `ext.kube.readinessProbe` | dict\|str | no | Same as liveness, or the string `"none"` to disable |
| `env` | dict | no | Extra env vars merged into docker-compose settings |


### 2.3 The Defaults File (`app-defaults.yaml`)

A YAML dict that is deep-merged into every resolved app *after*
inheritance and *before* context-level overrides.  Typical use: provide
default resource limits, default probe config, etc.  The merge strategy
is: lists override, dicts merge recursively, scalars override.

---

## 3. The Resolution Algorithm

The new module replaces `TychoContext._grok()` and its separate
`inherit()`, `mixin()`, and `mixin_defaults()` helpers with a **single
recursive pass** using one keyword: `extends`.

```
resolve(registry, defaults, product) → dict[app_id, ResolvedApp]
```

### Step 1: Select the product context

```python
contexts = registry["contexts"]
context  = contexts[product]       # KeyError if product not found
```

### Step 2: Resolve apps (single recursive pass)

```python
def resolve_context(contexts, context_name, apps=None):
    """Depth-first deep-merge of inherited apps."""
    if apps is None:
        apps = {}
    context = contexts[context_name]

    # Recurse into parents first — earliest ancestor's apps land first
    for base_name in context.get("extends", []):
        resolve_context(contexts, base_name, apps)

    # Deep-merge this context's apps on top (child fields win)
    for app_id, app_def in context.get("apps", {}).items():
        if app_id in apps:
            apps[app_id] = deep_merge(apps[app_id], deep_copy(app_def))
        else:
            apps[app_id] = deep_copy(app_def)

    # Apply context-level per-app overrides (bare keys matching app IDs)
    for key, value in context.items():
        if key in apps and isinstance(value, dict) and key != "apps":
            apps[key] = deep_merge(apps[key], deep_copy(value))

    return apps
```

This single function replaces the three legacy functions:

| Legacy | What it did | How `resolve_context` handles it |
|--------|-------------|----------------------------------|
| `inherit()` | Shallow-copy apps from `extends` chain | `extends` walk + **deep**-merge of app entries |
| `mixin()` | Deep-merge per-app data from `mixin` contexts | Eliminated — parent contexts listed in `extends` achieve the same deep-merge |
| `add_conf_impl()` | Merge context-level bare keys onto matching apps | Final loop in `resolve_context` |

Because every level deep-merges rather than shallow-replaces, a context
like `sys` (which only defines partial app entries — probes, security
contexts) can be listed in `extends` and its properties overlay onto
matching apps exactly as `mixin` used to do.

### Step 3: Merge defaults

```python
for app_id in apps:
    apps[app_id] = deep_merge(deep_copy(defaults), apps[app_id])
```

Uses `deepmerge.Merger` with strategy: lists override, dicts merge, sets
union.  Defaults provide the base; app values win on conflict.

### Step 4: Resolve spec paths

```python
spec_dir = registry.get("spec_dir", ".")
if not os.path.isabs(spec_dir):
    spec_dir = os.path.join(registry_dir, spec_dir)

for app_id, app in apps.items():
    if "spec" not in app:
        app["spec"] = os.path.join(spec_dir, app_id, "docker-compose.yaml")
    app["icon"] = os.path.join(os.path.dirname(app["spec"]), "icon.png")
```

### Result

`apps` is a `dict[str, dict]` where each value has all the fields from
§2.2 resolved, plus the synthesized `spec`, `icon` paths.

### Resolution order (priority low → high)

1. Earliest ancestor's `apps` entries
2. Intermediate ancestors (depth-first, left-to-right in `extends` list)
3. Current context's `apps` entries
4. Current context's bare-key overrides
5. Defaults (as a base layer — app values always win)

---

## 4. Lazy Loading (get_spec, get_settings)

After resolution, the app dict has a `spec` path but not the actual
docker-compose content.  Two methods load lazily and cache:

### 4.1 Evaluation lifecycle

The registry is loaded **at server startup, before any user has logged
in**.  This catalog-build phase must produce enough information for the
UI to display app names, descriptions, resource-slider ranges, and
icons.  Per-user values (username, OAuth tokens) do not exist yet.

App specs (docker-compose files) may contain **two kinds of variable
reference**:

| Kind | Syntax | Available at | Example |
|------|--------|-------------|---------|
| Registry settings | `{{ setting }}` (Jinja2) | Catalog build | `{{ helx_registry }}` |
| Per-user variables | `${varname}` (shell-style) | Instance creation | `${username}` |

The loader resolves Jinja2 at catalog-build time.  `${varname}`
references are **inert** — Jinja2 ignores `${}` syntax, so they pass
through rendering and YAML parsing as literal strings.  They are
resolved later by the controller when a user launches an app (see
`app-spec-module-spec.md` §2.9 for the full substitution protocol).

### 4.2 `get_spec(app_id)` → dict

1. Check `apps[app_id]["spec_obj"]` cache.
2. Read the `spec` file from disk.
3. Render as a Jinja2 template with `registry["settings"]` as context.
   `${varname}` references pass through untouched.
4. Parse the rendered text as YAML.
5. Cache in `apps[app_id]["spec_obj"]`.

(The legacy `get_definition()` was a near-duplicate of `get_spec()`;
the new module unifies them into a single method.)

### 4.3 `get_settings(app_id)` → str

1. Derive `.env` path as sibling of the `spec` path.
2. Read file (or return empty string if absent).
3. Cache in `apps[app_id]["env_obj"]`.

### 4.4 `get_env_registry(app_id, settings)` → dict

Merge registry-level `env` overrides (from the app dict's `env` field)
into the settings dict.

---

## 5. The Start-Time Assembly (Instance Creation)

When a user launches an app, `TychoContext.start()` does final assembly
today.  In the new model, this becomes two distinct operations — one
that happens once (HelxApp), one per launch (HelxInst):

### 5.1 HelxApp creation (idempotent, may already exist)

1. Load the docker-compose spec via `get_spec(app_id)` — already
   Jinja2-rendered at catalog time.  `${varname}` references are
   still present as literal strings.
2. Parse the spec via `helx.app.parse_compose()` — extracts services,
   ports, resource bounds, `x-helx-vars`.
3. Build `HelxAppSpec` via `spec_builder.build_helxapp_spec()` — the
   CRD template for this app, including `${varname}` literals and the
   `helx_vars` list.
4. Ensure the HelxApp CRD exists via `HelxAppManager.ensure()`.

### 5.2 HelxInst creation (per-user, per-launch)

1. Resolve per-user variable bindings from the user's session context:
   ```python
   vars = {}
   for var in helxapp.helx_vars:
       vars[var] = resolve_var(var, principal, instance_id)
   ```
   Where `resolve_var()` maps well-known names to `Principal` fields:
   `username` → `principal.username`, `identifier` → generated UUID,
   `access_token` → `principal.access_token`, etc.
2. Validate the user's resource request against the HelxApp's
   resource bounds.
3. Build `HelxInstSpec`:
   ```python
   HelxInstSpec(
       app_name=app_id,
       user_name=principal.username,
       vars=vars,
       resources={...},
       security_context=...,
   )
   ```
4. Create the HelxInst CRD via `HelxInstManager.create()`.

### 5.3 Controller reconciliation

The helxapp-controller sees the HelxInst, reads the referenced
HelxApp, and:
1. Walks the HelxApp spec's string values (environment, command,
   volumes).
2. Substitutes every `${varname}` occurrence using
   `HelxInst.spec.vars`.
3. Applies the HelxInst's resource request/limit to the containers.
4. Creates the Deployment, Service, PVCs, etc.

This completes the deferred evaluation: structural information
(images, ports, bounds) was available at catalog time; per-user
values are resolved only when the user launches the app.

---

## 6. Module Design for `helx.registry`

### 6.1 File Layout

```
helx/src/helx/registry/
├── __init__.py          # Public API: AppRegistry class
├── loader.py            # Load YAML from local files, Jinja2 rendering
├── resolver.py          # The core algorithm: extends resolution, defaults, path resolution
├── spec_builder.py      # Convert resolved app dict → HelxAppSpec
├── models.py            # ResolvedApp dataclass (intermediate representation)
└── tests/
    ├── __init__.py
    ├── test_loader.py
    ├── test_resolver.py
    ├── test_spec_builder.py
    └── test_registry.py
```

### 6.2 `models.py` — ResolvedApp

The intermediate representation after registry resolution, before
conversion to CRD specs.

```python
@dataclass
class ResolvedApp:
    app_id: str
    name: str
    description: str
    details: str
    docs_url: str
    spec_path: str
    icon_path: str
    services: dict[str, int]         # container_name → port
    count: int = 1
    service_account: str | None = None
    security_context: SecurityContext | None = None
    env: dict[str, str] = field(default_factory=dict)
    ext: dict | None = None          # kube extensions (probes)


    # Lazily populated by the loader
    spec_obj: dict | None = None     # Parsed docker-compose
    definition: dict | None = None
    settings_text: str | None = None

```

### 6.3 `loader.py` — Configuration & Spec Loading

Responsibilities:
- Load YAML from local filesystem paths.
- Load and render docker-compose specs (Jinja2 with `settings`).
- Load `.env` files.

```python
class RegistryLoader:
    def load_config(self, path: str) -> dict:
        """Load YAML from a local file."""

    def load_spec(self, spec_path: str, settings: dict) -> dict:
        """Read file + Jinja2 render + YAML parse."""

    def load_settings(self, spec_path: str) -> str:
        """Read the .env sibling of a spec path (empty string if absent)."""
```

### 6.4 `resolver.py` — The Core Algorithm

Pure functions, no I/O.  Operates on dicts parsed from YAML.

```python
def resolve_apps(
    registry: dict,
    defaults: dict,
    product: str,
) -> dict[str, dict]:
    """
    Execute the full resolution algorithm:
    1. Select product context
    2. Resolve apps (single recursive pass over extends chain
       with deep-merge — handles inheritance, property overlay,
       and context-level overrides in one traversal)
    3. Merge defaults
    4. Resolve spec/icon paths
    Returns the fully resolved app dict.
    """

def resolve_context(
    contexts: dict,
    context_name: str,
    apps: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """
    Depth-first deep-merge of apps across the extends chain.
    At each level: recurse into parents, deep-merge this context's
    apps, then apply bare-key overrides.
    """

def apply_defaults(apps: dict, defaults: dict) -> None:
    """Deep-merge defaults into each app (in place)."""

def resolve_paths(
    apps: dict,
    spec_dir: str,
    registry_dir: str,
) -> None:
    """Synthesize spec and icon filesystem paths."""
```

### 6.5 `spec_builder.py` — Registry → CRD Conversion

Converts a `ResolvedApp` plus a loaded docker-compose spec into
`HelxAppSpec` / `HelxInstSpec` from `kube.models`.

```python
def build_helxapp_spec(app: ResolvedApp) -> HelxAppSpec:
    """
    Convert a resolved app + its docker-compose into a HelxAppSpec.

    Reads the docker-compose services to produce AppServiceSpec entries:
    - image, command, environment, ports from docker-compose
    - volumes from docker-compose (already in DSL format or converted)
    - livenessProbe/readinessProbe from app.ext.kube
    - securityContext from app.security_context (per-container level
      comes from docker-compose; pod-level from registry)
    """

def build_helxinst_spec(
    app: ResolvedApp,
    username: str,
    resource_request: dict,
    security_context: SecurityContext | None = None,
    vars: dict[str, str] | None = None,
) -> HelxInstSpec:
    """
    Build a HelxInst spec for a user's launch request.

    - app_name: app.app_id
    - user_name: username
    - vars: per-user variable bindings (e.g. {"username": "alice",
      "identifier": "abc123"}) — the controller substitutes ${varname}
      in the HelxApp template with these values
    - resources: converted from the UI resource request format
    - security_context: from instance override, or app-level, or None
    """
```

### 6.6 `__init__.py` — `AppRegistry` Facade

The single entry point that replaces `TychoContext` for app-catalog
concerns.

```python
class AppRegistry:
    def __init__(
        self,
        registry_path: str = "app-registry.yaml",
        defaults_path: str = "app-defaults.yaml",
        product: str = "common",
    ):
        self.loader = RegistryLoader()
        raw_registry = self.loader.load_config(registry_path)
        raw_defaults = self.loader.load_config(defaults_path)
        self.settings = raw_registry.get("settings", {})
        self._raw_apps = resolve_apps(raw_registry, raw_defaults, product)
        self.apps: dict[str, ResolvedApp] = {
            k: _to_resolved_app(k, v) for k, v in self._raw_apps.items()
        }

    def get_app(self, app_id: str) -> ResolvedApp:
        """Return a resolved app by ID, or raise KeyError."""

    def list_apps(self) -> list[ResolvedApp]:
        """Return all resolved apps."""

    def get_spec(self, app_id: str) -> dict:
        """Lazy-load and cache the docker-compose spec from disk."""

    def get_settings(self, app_id: str) -> dict[str, str]:
        """Lazy-load the .env, merge registry env, return as dict."""

    def build_helxapp(self, app_id: str) -> HelxAppSpec:
        """Load spec, convert to HelxAppSpec."""

    def build_helxinst(
        self,
        app_id: str,
        principal: Principal,
        resource_request: dict,
        security_context: SecurityContext | None = None,
    ) -> HelxInstSpec:
        """Build a HelxInstSpec for launching.

        Resolves per-user variable bindings from the Principal session
        context.  Only variables declared in the app's x-helx-vars are
        included.  The controller uses these to substitute ${varname}
        in the HelxApp template.
        """
```

---

## 7. Improvements Over TychoContext

| Issue in TychoContext | Improvement |
|---|---|
| `_grok()` is a 60-line monolith mixing inheritance, URL resolution, and caching | Split into `resolver.py` (pure functions, testable with plain dicts) and `loader.py` (I/O) |
| Two separate keywords (`extends` + `mixin`) with two recursive traversals for what is logically one operation | Single `extends` keyword with deep-merge semantics — one recursive pass handles catalog assembly and property overlay |
| `inherit()` uses a mutable default argument (`apps={}`) — a classic Python bug that causes cross-call contamination | `resolve_context()` uses `None` default with explicit fresh-dict creation |
| `add_conf_impl()` is a recursive function with unclear purpose | Bare-key override handling is a clear final step inside `resolve_context()` |
| `get_spec()` and `get_definition()` are near-identical | Unified into a single `get_spec()` that loads from disk |
| App dict is an untyped `dict` — callers guess at keys | `ResolvedApp` dataclass with documented fields |
| `start()` mixes registry concerns (load spec, merge env) with compute concerns (build request, call API) | Registry module handles catalog; `kube.helxapps` / `kube.helxinsts` handle CRD creation. Clean separation. |
| Jinja2 rendering happens with `str(dict)` → template → `yaml.safe_load()` which is fragile | Use `yaml.dump()` → Jinja2 render → `yaml.safe_load()` consistently; document the double-pass pattern |
| Error handling swallows exceptions in several places | Raise typed exceptions (`RegistryError`, `SpecLoadError`) |
| No unit tests for the resolution algorithm | `test_resolver.py` tests inheritance/defaults/path resolution with synthetic YAML fixtures |

---

## 8. Test Plan

### 8.1 `test_resolver.py` — Pure Logic (No I/O)

| Test | What It Verifies |
|------|-----------------|
| `test_extends_single_base` | `extends: [common]` pulls in common's apps |
| `test_extends_chain` | `extends: [common]`, common `extends: [base]` — three levels |
| `test_extends_child_overrides_parent` | Same app_id field in child and parent — child wins |
| `test_extends_deep_merges_properties` | Parent defines partial app (e.g. probes), child defines same app (e.g. ports) — both properties present in result |
| `test_extends_overlay_context` | A context with only property overlays (like legacy `sys`) listed in `extends` merges its fields into matching apps |
| `test_extends_overlay_adds_new_app` | An overlay context that defines an app not in the child — app appears in result (known trade-off vs. legacy `mixin` which skipped non-matching apps) |
| `test_extends_order_matters` | `extends: [a, b]` — b's values override a's for the same field |
| `test_defaults_merged` | Every app gets default fields |
| `test_defaults_app_wins_on_conflict` | App's explicit value overrides default |
| `test_path_resolution_relative` | Relative `spec_dir` + registry dir produces absolute spec path |
| `test_path_resolution_absolute` | Absolute `spec_dir` is used directly |
| `test_context_override_security_context` | `braini.jupyter-ds.securityContext` applied to app |
| `test_unknown_product_raises` | Requesting a non-existent product raises an error |
| `test_cycle_detection` | `extends` cycle raises an error rather than infinite recursion |
| `test_registry_example_braini` | Load `fu/registry-example.yaml`, resolve `braini`, verify expected apps and securityContexts |

### 8.2 `test_loader.py` — File I/O

| Test | What It Verifies |
|------|-----------------|
| `test_load_config` | Loads YAML from a local file |
| `test_load_spec_renders_jinja2` | `{{ helx_registry }}` in docker-compose is substituted |
| `test_load_settings` | `.env` sibling file is read |
| `test_load_settings_missing_returns_empty` | Missing `.env` returns `""` |

### 8.3 `test_spec_builder.py` — Conversion

| Test | What It Verifies |
|------|-----------------|
| `test_build_helxapp_from_compose` | Docker-compose with image, ports, env → `HelxAppSpec` with correct `AppServiceSpec` entries |
| `test_build_helxapp_with_probes` | `ext.kube.livenessProbe` appears in the spec |
| `test_build_helxapp_with_volumes` | Compose volumes converted to DSL strings in `AppServiceSpec.volumes` |
| `test_build_helxinst_resources` | User resource request → `ContainerResources` in `HelxInstSpec.resources` |
| `test_build_helxinst_security_context` | Override security context appears in `HelxInstSpec.securityContext` |

### 8.4 `test_registry.py` — Integration (AppRegistry Facade)

| Test | What It Verifies |
|------|-----------------|
| `test_list_apps_returns_all` | All apps for the product are present |
| `test_get_app_metadata` | Name, description, docs, services are correct |
| `test_get_spec_caches` | Second call returns cached result, file read only once |
| `test_build_helxapp_end_to_end` | Full pipeline: registry YAML → `HelxAppSpec` |

---

## 9. Data Flow Summary

```
═══════════════════════════════════════════════════════════════════
  CATALOG BUILD (server startup, no users)
  Resolves: {{ jinja2 }}    Preserves: ${varname}
═══════════════════════════════════════════════════════════════════

                    registry-example.yaml
                    app-defaults.yaml
                           │
                    RegistryLoader.load_config()
                           │
                           ▼
                ┌─────────────────────┐
                │   resolver.py       │
                │  resolve_context()  │
                │  apply_defaults()   │
                │  resolve_paths()    │
                └────────┬────────────┘
                         │
              dict[app_id, dict]  (raw resolved)
                         │
                    _to_resolved_app()
                         │
              dict[app_id, ResolvedApp]
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    AppRegistry     AppRegistry    AppRegistry
    .list_apps()    .get_spec()    .build_helxapp()
          │              │              │
          │    RegistryLoader      spec_builder
          │    .load_spec()        .build_helxapp_spec()
          │    (Jinja2 resolves    (${varname} preserved
          │     {{ settings }};     in env/cmd/volumes;
          │     ${vars} pass        helx_vars stored on
          │     through)            HelxAppSpec)
          │              │              │
          ▼              ▼              ▼
    UI app catalog   dict (compose)  HelxAppSpec ──→ HelxAppManager.ensure()
    (names, bounds,  (structural     (template with
     descriptions)    info ready)     ${} placeholders)

═══════════════════════════════════════════════════════════════════
  INSTANCE CREATION (user logged in, launches app)
  Resolves: ${varname} via HelxInst.spec.vars
═══════════════════════════════════════════════════════════════════

    Principal (username, tokens, host)
          │
    AppRegistry.build_helxinst(principal, ...)
          │
          ├── resolve_var(var, principal)  for each x-helx-vars entry
          │        username  → principal.username
          │        identifier → generated UUID
          │        access_token → principal.access_token
          │
          ▼
    HelxInstSpec(vars={"username": "alice", ...}, resources={...})
          │
    HelxInstManager.create()
          │
          ▼
    helxapp-controller reconciles:
      1. Read HelxApp template
      2. Substitute ${varname} with HelxInst.spec.vars
      3. Apply HelxInst.spec.resources
      4. Create Deployment + Service + PVCs
```

---

## 10. Dependencies

| Dependency | Used For | Already in Project |
|---|---|---|
| `PyYAML` | YAML parsing | Yes |
| `Jinja2` | Template rendering in docker-compose specs | Yes |
| `deepmerge` | Dict deep-merge with configurable strategy | Yes (used by TychoContext) |

No new dependencies required.

---

## 11. Migration Status

Migration from `TychoContext` to `helx.registry` + `helx.kube` is complete:

1. `helx.registry.AppRegistry` replaces `TychoContext` for all catalog concerns.
2. `helx.kube.HelxAppManager` / `HelxInstManager` / `HelxUserManager` replace
   `TychoContext.start()` / `.delete()` / `.status()` / `.update()`.
3. `api/v1/views.py` uses `AppRegistry` and the kube managers exclusively.
4. The `tycho` module remains in the codebase for legacy compatibility but is
   no longer on the critical path for app launch.
5. The `helx` package is installed from `helx/` in this repo via
   `-e file:../helx` in `requirements.txt`.
