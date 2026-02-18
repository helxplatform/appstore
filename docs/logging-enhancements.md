# Logging Enhancements — Observability, Audit Trail, and Stability

## Background

A review of the appstore codebase identified 10 logging gaps across user actions, API
observability, application failures, and system stability. Several are zero-effort fixes;
others require small middleware additions.

The logging configuration defines 3 rotating file handlers (`system_warnings.log`,
`django_debug.log`, `app_store.log`) but no loggers actually route to them — everything
goes to stdout only. Additionally, a `# TODO: Structured Logging` comment in
`api/v1/views.py` has been outstanding with no action taken.

---

## Acceptance Criteria

- [ ] All 3 file handlers receive log output in their intended log files
- [ ] All bare `logging.*` calls in `views.py` replaced with `logger.*`
- [ ] Tycho logger level changed to `INFO`
- [ ] `RequestLoggingMiddleware` added; every API request logged with user, method, path, status, and duration
- [ ] Login, logout, and login failure events appear in logs with username and IP
- [ ] `/health/` endpoint exists, checks DB, returns 200/503
- [ ] `auth_identity` exception paths emit a warning log

---

## Dead Code Findings

A secondary review identified dead and broken code in areas directly relevant to the
subtasks below. These should be resolved alongside or before the logging work to avoid
logging code that is never executed.

| Location | Issue | Affects |
|----------|-------|---------|
| `api/v1/views.py:229` — `get_social_tokens()` | Defined but never called. `get_tokens()` is used instead via `get_principal()`. Social token retrieval path is effectively dead. | Subtask 6 |
| `middleware/filter_whitelist_middleware.py:133` — `is_whitelisted()` | Static method defined but never called in `process_request` or `is_authorized`. The intended short-circuit (skip re-authorization for already-whitelisted users) is not in effect, so `is_authorized` re-runs all DB/LDAP queries on every authenticated request. | Subtask 6 |
| `middleware/filter_whitelist_middleware.py:148` — `is_whitelisted_username()` | No return statement (body is only `username = user.username`). Never called anywhere. | Subtask 6 |
| `api/v1/views.py:462` — `@functools.lru_cache` on `get_principal()` | DRF instantiates a new `InstanceViewSet` per request, so `self` is always a new object and the cache is always cold. The cache never warms. | Subtask 11 |
| `tycho/client.py:107` — `TychoClient` (HTTP service client) | Tycho is now used as an embedded library only. `TychoClient` made HTTP calls to an external Tycho API service at `TYCHO_URL` — this service usage is obsolete. The live path goes through `ComputeFactory` → `KubernetesCompute`/`DockerComposeCompute` directly. `TYCHO_URL` env var is effectively unused. | Subtasks 3, 8 |

### Impact on Subtasks

- **Subtask 4** — Logout via `UsersViewSet.logout` is one path, but `SessionIdleTimeout.process_view`
  also calls `logout(request)` silently. Both are unlogged and both need to be addressed.

- **Subtask 6** — Because `is_whitelisted()` is dead code, `is_authorized()` runs full DB and
  LDAP checks on every authenticated request (not just at login). The Django signal approach
  (`user_logged_in`) still correctly captures the auth event itself, but implementers should
  be aware authorization re-runs per request, not per session. The three active auth flows are
  Django login, OAuth (allauth), and SAML — `user_logged_in` fires for all three at the Django
  layer, but `user_login_failed` does not fire for SAML failures.

- **Subtask 10** — The bare `except:` in `auth_identity` at line 89 catches both `ValueError`
  (malformed `Bearer` token) and `AttributeError` (when the `Authorization` header is entirely
  absent and `.split()` is called on `None`). The logging fix should cover both cases distinctly.

- **Subtask 12** — The relevant method in `SessionIdleTimeout` is `process_view` (lines 19–27),
  not `__call__`. The `__call__` method is a pass-through and requires no changes.

---

## Subtasks

### P0 — Quick Wins

---

#### Subtask 1: Wire orphaned file log handlers to loggers

**Effort:** 15 min
**File:** `appstore/appstore/settings/base.py`

Three rotating file handlers (`syslog`, `djangoLog`, `app_store_log`) are defined but no
logger references them. Nothing is written to disk.

**Changes:**
- Add `"djangoLog"` to the `django.request` handlers list
- Add a new `api` logger entry pointing to `app_store_log`
- Add `"syslog"` to the root logger handlers list

**Acceptance:** Running the app produces output in all three log files under `log/`.

---

#### Subtask 2: Replace bare `logging.*` calls with `logger.*` in views.py

**Effort:** 10 min
**File:** `appstore/api/v1/views.py` lines 351, 398, 555–559

Module-level `logging.debug()` calls bypass the `api.v1.views` logger instance. They emit
as `root` and cannot be filtered or routed independently.

**Changes:** Replace each `logging.debug(...)` with `logger.debug(...)`.

**Acceptance:** No bare `logging.debug` / `logging.info` / `logging.error` calls remain in
`views.py`.

---

#### Subtask 3: Restore Tycho logger to INFO level

**Effort:** 5 min
**File:** `appstore/appstore/settings/base.py` line 347

Tycho is embedded as a library and manages all Kubernetes/Docker app lifecycle operations
directly via the Kubernetes API (`KubernetesCompute`) or Docker (`DockerComposeCompute`).
Its logger is hardcoded to `WARNING`, silencing all INFO-level library output — including
app start, stop, and status operations against the cluster.

Note: `TychoClient` (the former HTTP service client in `tycho/client.py`) is obsolete and
the `TYCHO_URL` env var is unused. The logger change applies to the library code path only.

**Changes:** Change `"level": "WARNING"` to `"level": "INFO"` in the `tycho` logger entry.

**Acceptance:** App launch/stop/status operations via `KubernetesCompute` appear in logs
at INFO level.

---

#### Subtask 4: Add log statements to all logout paths

**Effort:** 10 min
**Files:** `appstore/api/v1/views.py` line 818, `appstore/middleware/session_idle_timeout.py` line 24

`logout(request)` is called in two places with no log statement in either:
1. `UsersViewSet.logout` — explicit user-initiated logout via the API
2. `SessionIdleTimeout.process_view` — implicit logout due to idle timeout

Both leave no trace in logs.

**Changes:**
- Add `logger.info(...)` with username before `logout(request)` in `UsersViewSet.logout`
- Add `logger.info(...)` in `SessionIdleTimeout.process_view` when a session is expired,
  including username and elapsed idle time (see also Subtask 12)

**Acceptance:** Both logout paths produce a log line with username and the reason
(user-initiated vs. idle timeout).

---

### P1 — Small Features

---

#### Subtask 5: Add RequestLoggingMiddleware for API request/response visibility

**Effort:** 2–3 hrs
**New file:** `appstore/middleware/request_logging.py`

No middleware currently logs HTTP method, path, authenticated user, response status, or
request duration. Successful 200 responses leave no log evidence.

**Changes:**
- Create `RequestLoggingMiddleware` that emits one structured log line per request
  including: `method`, `path`, `user`, `status_code`, `duration_ms`, and a short `request_id`
- Register it in `MIDDLEWARE` after `AuthenticationMiddleware`
- Add an `api.requests` logger entry in settings routing to `app_store_log`

**Acceptance:** Every API request produces a log line with user, path, status, and
duration. Log file confirms output.

---

#### Subtask 6: Log user login, logout, and login failure events via Django signals

**Effort:** 1–2 hrs
**File:** `appstore/core/` (signal handler)

Login events, failed login attempts, and the auth provider used are not captured anywhere
in logs. This is a gap in both audit trail and security monitoring.

Three active auth flows must be covered: Django login, OAuth (allauth), and SAML.

**Note on dead code:** `get_social_tokens()` in `api/v1/views.py` is dead — it is never
called, and the social token path it was intended to serve has no active logging. The
signal approach below is the correct replacement path. `is_whitelisted()` in the whitelist
middleware is also dead, meaning authorization re-runs full DB and LDAP checks on every
authenticated request rather than short-circuiting at session level. This does not affect
the signal handlers but is worth resolving separately.

**Changes:**
- Connect handlers to `user_logged_in`, `user_logged_out`, and `user_login_failed` Django
  signals in `core/apps.py` or a dedicated `core/signals.py`
- Log username, IP address (`REMOTE_ADDR`), and auth backend for each event
- Login failures logged at `WARNING`; successes and logouts at `INFO`
- Note: `user_login_failed` does not fire for SAML authentication failures; SAML error
  paths in `django_saml2_auth` would need separate handling if SAML failure audit is required

**Acceptance:** Login, logout, and failed login attempts each produce a log line with user
and IP. Verified across Django login and OAuth flows. SAML coverage documented as a known
gap if not addressed.

---

#### Subtask 7: Log resource validation failures in validate_request_resources()

**Effort:** 30 min
**File:** `appstore/api/v1/views.py` lines 131–177

`validate_request_resources()` returns HTTP 400 responses with no log output. These
user-facing errors are invisible in logs, making it impossible to detect misconfigured app
specs or abuse patterns.

**Changes:** Add a `logger.warning(...)` before each `return Response(...
HTTP_400_BAD_REQUEST)` including the username, app ID, constraint that failed, and the
values requested vs. allowed.

**Acceptance:** A resource validation failure produces a warning log with the rejection
reason and user context.

---

### P2 — Medium Effort

---

#### Subtask 8: Add /health/ endpoint for Kubernetes liveness/readiness probes

**Effort:** 2–3 hrs
**Files:** `appstore/core/views.py`, `appstore/appstore/urls.py`

No health check endpoint exists. Kubernetes probes either hit the main page (wasteful,
noisy) or are unconfigured. There is no automated signal when the database becomes
unreachable.

**Database context:** The app supports two database backends configured via
`POSTGRES_ENABLED` in `settings/base.py`:
- **PostgreSQL** (default, `POSTGRES_ENABLED=true`) — a network dependency connecting to a
  separate host via `PG_DB_*` env vars. This is the backend the health check is primarily
  designed to probe; it can become unreachable independently of the app.
- **SQLite3** (`POSTGRES_ENABLED=false`) — a local file used in development only. A
  connectivity check against SQLite is essentially a no-op since the file is always present.

The health response should include which backend is being checked so the operator knows
what a 200 actually confirms (e.g. `{"database": "postgresql", "status": "ok"}`).

**Changes:**
- Add a `health(request)` view that checks DB connectivity via `connection.ensure_connection()`
- Include the database engine name in the response body
- Return `200 OK` on success or `503` with error detail on failure
- Log the result at INFO on success, ERROR on failure
- Register at `/health/` exempt from authentication middleware
- (Optional stretch) Add a Kubernetes API connectivity check via the `kubernetes` client
  (already a dependency) — since Tycho is a library, not a service, there is no `TYCHO_URL`
  to ping; the cluster reachability check is the meaningful signal instead

**Acceptance:** `GET /health/` returns 200 when the configured DB is reachable, 503 when
not. Response body identifies the database backend. Kubernetes probe can be pointed at this
URL.

---

#### Subtask 9: Add JSON log formatter for file handlers

**Effort:** 1–2 hrs
**Files:** `appstore/appstore/settings/base.py`, `requirements.txt`

All log formatters produce plain text. Log aggregation tools (Elasticsearch, CloudWatch
Logs Insights, etc.) require fragile regex parsing. Structured JSON logs enable direct
field queries.

**Changes:**
- Add `python-json-logger` to `requirements.txt`
- Add a `json` formatter to the `LOGGING["formatters"]` block
- Switch `app_store_log` and `djangoLog` handlers to use the `json` formatter
- Keep `verbose2` on the console handler for human readability

**Acceptance:** Log files contain one valid JSON object per line with fields `level`,
`name`, `funcName`, `message`, etc.

---

#### Subtask 10: Add logging to auth_identity exception paths

**Effort:** 30 min
**File:** `appstore/core/views.py` lines 84–102

The `auth_identity` view handles nginx subrequest authentication for every proxied app
request. It is an active, wired endpoint (`/auth/identity/`). Its failure paths use a bare
`except:` block and a `DoesNotExist` catch — both return HTTP errors with no log output,
making token validation failures completely invisible.

**Note on the bare `except:`:** The bare `except:` at line 89 catches two distinct
conditions that should be logged separately:
1. `AttributeError` — when the `Authorization` header is entirely absent (`None.split()`)
2. `ValueError` — when the header is malformed (not `Bearer <token>`)

Both collapse silently into the same HTTP 400 response today.

**Changes:**
- Replace bare `except:` with `except Exception as e:` and add `logger.warning(...)` that
  distinguishes whether the header was absent vs. malformed; avoid logging raw header value
- In the `DoesNotExist` handler, add `logger.warning(...)` indicating the token was not
  found (do not log the raw token value)
- In the token-expired path, add `logger.info(...)` with the username and token expiry time

**Acceptance:** All failure paths in `auth_identity` emit a log line before returning an
HTTP error response, with the absent-header and malformed-header cases distinguishable in
logs.

---

### P3 — Larger Effort

---

#### Subtask 11: Propagate correlation/request IDs across log namespaces

**Effort:** 3–4 hrs
**Depends on:** Subtask 5

Logs from `api.v1.views` and `tycho` for the same request have no shared identifier.
Debugging failures requires fragile timestamp matching across log lines.

**Changes:**
- Generate a `request_id` in `RequestLoggingMiddleware` (or accept `X-Request-ID` from
  upstream)
- Store on `request.request_id`
- Pass `extra={"request_id": request.request_id}` in key log calls in
  `InstanceViewSet.create`, `destroy`, and `partial_update`
- Consider a logging filter that injects the request ID from thread-local storage
  automatically

**Acceptance:** A single app launch failure can be traced from the incoming HTTP request
log line through to the Tycho error using a shared `request_id` value.

---

#### Subtask 12: Log session idle timeout expiry events

**Effort:** 30 min
**File:** `appstore/middleware/session_idle_timeout.py`

The `SessionIdleTimeout` middleware silently invalidates sessions. There is no log evidence
when a user is timed out, making it impossible to distinguish session expiry from
authentication failures in support investigations.

**Note:** The session expiry logic lives entirely in `process_view` (lines 19–27). The
`__call__` method is a simple pass-through and does not require changes. Logging should be
added inside `process_view` at the point where `logout(request)` is called (line 24). This
work overlaps with Subtask 4 — if Subtask 4 is done first, this subtask is reduced to
confirming the log is in place and includes the idle duration.

**Changes:**
- Add `logger.info(...)` in `process_view` when a session is expired due to idle timeout,
  including username and seconds elapsed since `last_activity`
- Add `logger.debug(...)` on each request that resets the idle timer (optional, gated
  behind DEBUG level)

**Acceptance:** Session expiry due to idle timeout produces a log line with the username
and idle duration, distinct from a user-initiated logout.

---

## Summary Table

| # | Subtask | Effort | Priority |
|---|---------|--------|----------|
| 1 | Wire orphaned file log handlers to loggers | 15 min | P0 |
| 2 | Replace bare `logging.*` calls with `logger.*` in views.py | 10 min | P0 |
| 3 | Restore Tycho logger to INFO level | 5 min | P0 |
| 4 | Add log statement to UsersViewSet logout action | 5 min | P0 |
| 5 | Add RequestLoggingMiddleware for API request/response visibility | 2–3 hrs | P1 |
| 6 | Log user login, logout, and login failure events via Django signals | 1–2 hrs | P1 |
| 7 | Log resource validation failures in validate_request_resources() | 30 min | P1 |
| 8 | Add /health/ endpoint for Kubernetes liveness/readiness probes | 2–3 hrs | P2 |
| 9 | Add JSON log formatter for file handlers | 1–2 hrs | P2 |
| 10 | Add logging to auth_identity exception paths | 30 min | P2 |
| 11 | Propagate correlation/request IDs across log namespaces | 3–4 hrs | P3 |
| 12 | Log session idle timeout expiry events | 30 min | P3 |
