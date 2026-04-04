# External / Programmatic Access to HeLx Apps

This document describes how to launch and access HeLx applications programmatically — without using the HeLx UI — while still going through the same authentication and routing infrastructure that UI users rely on.

---

## Overview

HeLx's app access model is session-based: a user authenticates, AppStore creates a Kubernetes workload on their behalf, and Ambassador routes `GET /private/<app>/<username>/` to that workload. Every piece of this pipeline is available to non-UI clients as long as they can produce an authenticated session or token.

```
External client
      │
      │  1. Authenticate → obtain session cookie or token
      ▼
AppStore REST API
      │
      │  2. POST /api/v1/instances/   (launch app)
      │  3. GET  /api/v1/instances/<id>/is_ready/  (poll)
      ▼
Ambassador ingress
      │
      │  4. GET /private/<app>/<username>/   (access running app)
      ▼
Running Pod
```

---

## Step 1 — Authentication

AppStore supports multiple authentication backends (configured per deployment). An external client must authenticate through one of them to establish an identity context — a Django session or bearer token — that AppStore associates with a username.

### Option A: Social / OAuth login (standard)

The UI login flow uses OAuth 2.0 / OIDC (e.g., GitHub, Google, institutional IdP). Programmatic clients can drive the same flow using a headless browser or by exchanging credentials directly with the IdP for an access token, then presenting it to AppStore.

The exact mechanism depends on the IdP and the grant type it supports. For PKCE / authorization-code flows the client must handle the redirect dance. For deployments that allow client-credentials or device-code flows, the client can exchange directly.

After successful OAuth, AppStore creates (or updates) a Django `User` record keyed on the username returned by the IdP. The username is stored and used in lowercase throughout.

### Option B: Direct session login (dev / testing)

When `DJANGO_SECRET_KEY` is known and `ALLOW_GUEST_USERS=true` is set, a client can POST to `/accounts/login/` with `username` + `password` credentials to obtain a session cookie.

### Option C: Token-based API access

If the deployment exposes DRF Token Authentication (check `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` in settings), a client can obtain a token with:

```
POST /api/v1/auth/token/
{ "username": "alice", "password": "..." }
→ { "token": "abc123..." }
```

Then pass `Authorization: Token abc123...` on subsequent requests.

### What the identity context carries

After authentication, the user context carries:
- `request.user.username` — the canonical (lowercased) username used as a Kubernetes label value and in the Ambassador route
- Optional OAuth `access_token` / `refresh_token` — available to apps via injected env vars if the IdP flow provides them

---

## Step 2 — Launch an App

```
POST /api/v1/instances/
Authorization: Token <token>    (or session cookie)
Content-Type: application/json

{
  "app_id": "jupyter",
  "cpus":   "2",
  "memory": "4Gi",
  "gpus":   "0"
}
```

### Response

```json
{
  "app_id":      "jupyter",
  "name":        "Jupyter",
  "sid":         "a3f9c2",
  "proxy_path":  "/private/jupyter/alice/",
  "url":         "https://helx.example.org/private/jupyter/alice/",
  "cpus":        "2",
  "memory":      "4Gi",
  "gpus":        "0",
  "creation_time": "2026-04-04T12:00:00Z"
}
```

Key fields:
- `sid` — the AppStore instance ID; use this for readiness polling and deletion.
- `proxy_path` — the path under which the running app is reachable via Ambassador. Prefix with the cluster's public hostname to form the full URL.
- `url` — convenience field combining the configured `HOST` and `proxy_path`.

### Resource limits

Requested resources are validated against the app's configured bounds. Requests outside the allowed range return HTTP 400 with a description of the limit. Omitted fields default to the app's minimum values.

---

## Step 3 — Poll for Readiness

The helxapp-controller reconciles asynchronously. The Deployment and its Pod will not exist immediately after the `POST /instances/` response.

```
GET /api/v1/instances/<sid>/is_ready/
Authorization: Token <token>
```

Response while controller is reconciling:
```json
{ "is_ready": false }
```

Response once the Pod is running and the Deployment's `readyReplicas >= 1`:
```json
{ "is_ready": true }
```

Recommended polling strategy: back off starting at 2 s, cap at 30 s, timeout after 10 min. Most apps are ready within 30–60 s on a warm cluster.

---

## Step 4 — Access the Running App

Once `is_ready` is `true`, send requests to the `url` returned in Step 2.

### Authentication at the app

The running container receives:

| Env var | Value | Purpose |
|---------|-------|---------|
| `REMOTE_USER` | `alice` | Username, passed by Ambassador header or env |
| `IDENTITY_TOKEN` | 256-char token | App can use this to authenticate callbacks to AppStore |
| `NB_PREFIX` | `/private/jupyter/alice/` | Base path; apps that honour `NB_PREFIX` (e.g. JupyterLab) route correctly |

The `IDENTITY_TOKEN` is tied to this specific instance. Apps that expose an API can accept it as a bearer token and validate it by calling:

```
GET /api/v1/instances/?token=<IDENTITY_TOKEN>
```

AppStore will return the matching instance record if the token is valid and not expired.

### Cookie / session propagation

Ambassador forwards the client's cookies to the upstream service. If the app uses its own session layer (e.g. JupyterLab uses a `_xsrf` token), the client must handle those cookies in the normal way.

For headless clients, use a cookie jar that persists across redirects:

```python
import requests
session = requests.Session()
# authenticate to AppStore ...
response = session.get("https://helx.example.org/private/jupyter/alice/")
```

---

## Step 5 — Enumerate Running Instances

```
GET /api/v1/instances/
Authorization: Token <token>
```

Returns all instances belonging to the authenticated user. Filter by `app_id` in the response if needed.

---

## Step 6 — Terminate an Instance

```
DELETE /api/v1/instances/<sid>/
Authorization: Token <token>
```

AppStore deletes the `HelxInst` CRD. The helxapp-controller removes the Deployment, Service, and any associated resources. The `UserIdentityToken` for this instance is also invalidated.

---

## Full Python Example

```python
import time
import requests

BASE_URL = "https://helx.example.org"

def launch_and_wait(token: str, app_id: str, cpus: str = "1", memory: str = "2Gi") -> str:
    session = requests.Session()
    session.headers["Authorization"] = f"Token {token}"

    # Launch
    resp = session.post(f"{BASE_URL}/api/v1/instances/", json={
        "app_id": app_id, "cpus": cpus, "memory": memory
    })
    resp.raise_for_status()
    data = resp.json()
    sid = data["sid"]
    url = data["url"]
    print(f"Launched {app_id} as instance {sid}")

    # Poll for readiness
    interval = 2
    for _ in range(300):   # up to 10 minutes
        r = session.get(f"{BASE_URL}/api/v1/instances/{sid}/is_ready/")
        r.raise_for_status()
        if r.json().get("is_ready"):
            print(f"Ready at {url}")
            return url
        time.sleep(interval)
        interval = min(interval * 1.5, 30)

    raise TimeoutError(f"Instance {sid} not ready after 10 minutes")


def terminate(token: str, sid: str) -> None:
    session = requests.Session()
    session.headers["Authorization"] = f"Token {token}"
    resp = session.delete(f"{BASE_URL}/api/v1/instances/{sid}/")
    resp.raise_for_status()
    print(f"Terminated {sid}")
```

---

## Security Considerations

### Routing isolation

Ambassador routes `/private/<app>/<username>/` — the username is embedded in the path. Because the controller uses the authenticated username (lowercase, from the Django session) when building the Ambassador mapping, a user cannot accidentally receive another user's traffic by guessing a path: the prefix is fixed at deploy time via Go template rendering, and the mapping only exists for the duration of the running instance.

### Token lifetime

`UserIdentityToken` records expire after 31 days by default. Callers should treat the token as a short-lived credential and re-authenticate if an AppStore callback returns 401.

### Namespace isolation

All resources for a given deployment live in a single Kubernetes namespace (configured by `NAMESPACE`). Network policies (if enabled) restrict pod-to-pod traffic to only what each app requires.

### Secret injection

Apps that need credentials (e.g. database passwords, API keys) receive them through Kubernetes Secrets injected via `envFrom` — they are never embedded in the CRD spec or transmitted over the AppStore API. The secret names are declared in the app's docker-compose (`secrets: [name]`); the actual secrets must be pre-provisioned in the cluster namespace by an administrator.

---

## Relationship to the UI Flow

The UI and programmatic access share the identical backend code path:

| Step | UI | Programmatic |
|------|----|--------------|
| Authentication | OAuth redirect in browser | OAuth exchange or token auth |
| Launch | Click "Launch" button | `POST /api/v1/instances/` |
| Readiness | UI polls `is_ready` via JS | Client polls `is_ready` via HTTP |
| Access | Browser navigates to URL | HTTP client sends requests to URL |
| Termination | Click "Delete" button | `DELETE /api/v1/instances/<sid>/` |

The only difference is the client driving the API. No special permissions, separate endpoints, or secondary APIs are required.
