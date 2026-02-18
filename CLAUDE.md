# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HeLx AppStore is a Django-based web application that enables users to discover, launch, and manage analytical tools and data science applications on top of Kubernetes (via Tycho). It supports multiple brand configurations with different UI and authentication setups.

## Commands

```bash
# Install dependencies
make install

# Run all tests across all brands
make test

# Run tests for a single Django app (faster)
SECRET_KEY=test DEV_PHASE=stub DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings python3 appstore/manage.py test <app_name>

# Run tests for a specific test class or method
SECRET_KEY=test DEV_PHASE=stub DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings python3 appstore/manage.py test api.tests.TestClass.test_method

# Start dev server (requires DJANGO_SETTINGS_MODULE to be set)
make start

# Start dev server for a specific brand
export DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings && make start

# Lint (flake8 is used in CI via helx-github-actions)
python3 -m flake8 appstore/

# Build Docker image (requires VER=<number>)
make VER=1 build

# Test Docker image build
make build.test

# Start PostgreSQL container (only when POSTGRES_ENABLED=true and DEV_PHASE=local)
make build.postgresql.local
```

## Local Development Setup

Copy `.env.default` to `.env` and adjust as needed. The Makefile auto-copies `.env.default` to `.env` if `.env` doesn't exist.

**Minimal env for local dev (stub mode — no Tycho required):**
```bash
export DEV_PHASE=stub
export SECRET_KEY=anyRandomString
export DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings
```

**DEV_PHASE values:** `stub` (no Tycho, SQLite), `local` (SQLite or PostgreSQL), `dev`/`val`/`prod` (requires Tycho at `TYCHO_URL`).

## Architecture

### Multi-Brand Configuration
Brand-specific settings live in `appstore/appstore/settings/` as `<brand>_settings.py` files. They all import from `base.py`. The active brand is selected by `DJANGO_SETTINGS_MODULE`. Supported brands: `braini`, `bdc`, `heal`, `restartr`, `scidas`, `eduhelx`, `argus`, `tracs`, and several `eduhelx-*` variants.

### Django Apps
- **`api/v1/`** — REST API endpoints (Django REST Framework + drf-spectacular for OpenAPI)
- **`core/`** — Core models, views, signals, admin interface, management commands
- **`frontend/`** — Serves the helx-ui React SPA (embedded in Docker via multistage build)
- **`middleware/`** — Authentication and authorization middleware (whitelist enforcement)
- **`product/`** — Brand-specific product business logic
- **`tycho/`** — Kubernetes app orchestration: launches/monitors Docker Compose-based apps via the Tycho service

### Tycho Integration
Tycho is a separate service (and Python library) that manages Docker Compose applications on Kubernetes. The `tycho/` app contains the client (`client.py`), Kubernetes operations (`kube.py`), data models (`model.py`), and app context (`context.py`). In `DEV_PHASE=stub`, Tycho is bypassed entirely with stub responses.

### Authentication
Three mechanisms coexist and are configured per-brand:
1. **Django native auth** — enabled by `ALLOW_DJANGO_LOGIN=true`
2. **OAuth2** — GitHub and/or Google via django-allauth; configured via `OAUTH_PROVIDERS`, `GITHUB_*`, `GOOGLE_*` env vars
3. **SAML SSO** — via django-saml2-auth; configured per-brand in settings

Authorization uses a whitelist: `AUTHORIZED_USERS` env var (comma-separated emails) and the `AUTHORIZED_USERS` Django group. The `middleware/` app enforces this.

### Database
SQLite3 by default in development. PostgreSQL enabled via `POSTGRES_ENABLED=true` (requires `docker-compose-postgresql.yaml` to be running locally or a real Postgres instance). Migrations live in each app's `migrations/` directory.

### Frontend
The helx-ui React app is embedded into the Docker image at build time. In development, Django serves static files from `frontend/static/`. The frontend app has a single view that serves the SPA at `/`.

## CI/CD Notes

- Do **not** delete `# noqa: F401` (or similar) inline linter suppression comments — they are intentional.
- Trivy vulnerability scanning runs on PRs; failing scans block merges to protected branches.
- Semantic versioning for releases: include `breaking|major` in commit for major bump, `feat|feature|minor` for minor bump; otherwise patch is bumped automatically on merge to master.
- Docker images are published to `containers.renci.org/helxplatform/appstore` (develop) and Docker Hub `helxplatform/appstore` (master/releases).
- Conventional commits are enforced via `.githooks/` — run `make init` to install the git hook.
