# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install          # Install all dependencies (appstore + helx editable install)
make test             # Run Django tests for all brands
make start brand=braini  # Run migrations, collectstatic, and start Gunicorn on :8000
make build VER=x.y.z  # Build Docker image
make build.test       # Run tests inside Docker
```

**Environment required for manual runs:**
```bash
export DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings
export SECRET_KEY=any-string
export DEV_PHASE=stub   # no Kubernetes or DB required in stub mode
```

**Run a single Django test:**
```bash
python appstore/manage.py test api.v1.tests.InstanceViewSetTests.test_create
```

**Run helx library tests (no Django needed):**
```bash
python -m pytest helx/ -q
python -m pytest helx/src/helx/kube/tests/test_helxapps.py::TestHelxAppManager::test_create
```

**Lint:**
```bash
flake8 appstore/
```

## Architecture

The appstore is a Django/DRF application that lets authenticated users launch containerized apps as Kubernetes workloads. Three layers handle this:

### Layer 1 — Django application (`appstore/`)

- **`api/v1/views.py`** — The core. `AppViewSet` serves the app catalog; `InstanceViewSet.create()` is the launch path (auth → validate resources → ensure HelxApp/HelxUser → create HelxInst).
- **`appstore/settings/`** — `base.py` is the shared config; brand-specific files (e.g. `braini_settings.py`) extend it. `DJANGO_SETTINGS_MODULE` selects the brand.
- **`core/`** — iRODS integration, user identity, whitelist.
- **`product/`** — Brand-specific feature flags and configuration loaded at runtime.
- The `tycho/` directory contains legacy code retained for reference but is no longer on the launch path.

### Layer 2 — helx library (`helx/src/helx/`)

A standalone Python SDK installed into appstore via `-e file:../helx`. Three modules:

- **`helx.app`** — Parses docker-compose YAML into typed objects (`ComposeApp`, `ComposeService`, `ProbeSpec`, etc.). Pure parsing; no I/O.
- **`helx.registry`** — Loads an `app-registry.yaml`, resolves product context inheritance (`extends` deep-merge), renders Jinja2 variables in compose files (protecting Go templates like `{{ .system.X }}`), and produces `HelxAppSpec` / `HelxInstSpec`.
- **`helx.kube`** — Manages the three CRD types via `HelxAppManager`, `HelxInstManager`, `HelxUserManager`. `KubeClient` auto-detects in-cluster vs kubeconfig. `StatusQuery` reads derived Kubernetes objects (pods, services).

Top-level facade: `helx.connect(namespace)` → `KubeClient`, `helx.load_registry(path)` → `AppRegistry`.

Standalone script: **`helx/run-app.py`** — CLI to launch/delete workloads directly from a registry file without the Django app.

### Layer 3 — helxapp-controller (external)

The controller watches HelxApp/HelxInst/HelxUser CRDs (`helx.renci.org/v1`) and creates the Deployments, Services, and PVCs. Appstore does **not** create raw Kubernetes objects — it only writes CRDs. The controller must be running in the target namespace.

**Launch sequence** (in `InstanceViewSet.create()`):
1. `HelxAppManager.ensure(app_id, spec)` — create/update HelxApp CRD
2. `HelxAppManager.wait_for_reconcile(app_id)` — poll until `status.observedGeneration == metadata.generation`
3. `HelxUserManager.ensure(username, spec)` — create/update HelxUser CRD
4. `HelxInstManager.create(inst_name, spec)` — triggers workload creation

Step 2 guards against a race condition where the controller misses a HelxInst because the HelxApp was still reconciling.

## Template rendering — two phases

App docker-compose files go through two rendering passes:

1. **Jinja2 (registry load time)** — resolves `{{ setting_name }}` variables from `app-registry.yaml`'s `settings:` block (e.g. `{{ helx_registry }}`). Go template expressions (`{{ .system.X }}`) are sentinel-protected to survive this pass.
2. **Go templates (controller deploy time)** — the controller resolves `{{ .system.UserName }}`, `{{ .system.AppClassName }}`, `{{ .system.ReferenceID }}`, etc. when creating the workload.

Variables available at phase 1 are documented in `helx/src/helx/registry/loader.py`.

## Key environment variables

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | Required. Selects brand (e.g. `appstore.settings.braini_settings`) |
| `DEV_PHASE` | `stub` = no K8s/DB required; `local` = SQLite; `dev/val/prod` = full stack |
| `NAMESPACE` | Kubernetes namespace for CRDs (default: `default`) |
| `APP_REGISTRY_PATH` | Directory containing `app-registry.yaml` and `app-specs/` |
| `LDAP_URI` | If set, HelxUser CRDs get label `helx.renci.org/identity-source: ldap` |

## Testing notes

- Django tests use `appstore.settings.testing_settings` and run in `stub` mode — no cluster needed.
- helx tests use pytest directly from `helx/`; they mock Kubernetes API calls.
- `@patch` targets must use the `helx.*` namespace (e.g. `helx.kube.security.requests.get`), not bare module names.
- The `tools/tests/` directory covers registry migration/sync utilities.
