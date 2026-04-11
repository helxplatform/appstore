# Diagnostic Observability Epic

## Summary

This document proposes a Jira epic to add automatic, machine-readable diagnostic
evidence gathering across the HeLx app launch and proxy stack. The goal is to
make it practical for a reasoning agent, or a human operator, to diagnose
cross-layer failures without relying on ad hoc shell work, manual `kubectl`
inspection, or incomplete single-component logs.

The target outcome is a system that can answer, for any failing app instance or
request:

- What URL did the user request?
- What instance ID, `referenceID`, controller UUID, pod, and service were
  involved?
- What path/env/config did the backend app actually receive?
- What request rewrite and response redirect transformations occurred?
- What cookies, headers, and generated config influenced behavior?
- Which component first diverged from the intended behavior?

## Why This Epic Exists

Recent debugging required a long sequence of manual checks across AppStore,
helxapp-controller, Ambassador, resty, and backend containers. Several issues
were real, but difficult to localize because the observed symptom appeared in a
different component than the actual cause.

Examples of failures that were time-consuming to isolate:

- AppStore returned the wrong type of instance identity to the UI.
- Controller UUID and AppStore `referenceID` diverged.
- Ambassador request rewrite was correct, but resty failed to re-prefix
  response redirects.
- `pgadmin` behavior changed based on a trailing slash in `NB_PREFIX`.
- `rstudio-server` worked differently depending on cookies and redirect target
  path, which initially looked like a login or proxy problem.
- Jupyter readiness failed because Kubernetes CPU quantities such as `2500m`
  were parsed incorrectly.

These failures were diagnosable, but only after reconstructing the request path
and instance state by hand. The system should gather that evidence
automatically.

## Epic Goal

Create an automated diagnostic evidence pipeline that captures the relevant
request, instance, controller, proxy, and backend state in a single correlated
bundle so a reasoning agent can determine the failing layer with minimal
guesswork.

## Non-Goals

- Replace normal application logs.
- Collect full cluster state for every request.
- Store secrets or tokens in raw form.
- Build a full distributed tracing platform across every component.

## Primary Users

- Platform operators debugging instance launch and connect failures.
- Developers changing AppStore, helxapp-controller, resty, or app registry
  behavior.
- Reasoning agents that need machine-readable evidence to locate a failure
  without exploratory shell access.

## Success Criteria

For a given failing instance or connect request, the system should produce a
single diagnostic bundle that lets an agent determine, with high confidence:

1. Whether the request reached the intended backend.
2. Whether request path rewriting was correct.
3. Whether response redirect rewriting was correct.
4. Whether the backend received the intended env and generated config.
5. Whether identity mapping between AppStore, `referenceID`, controller UUID,
   service, and pod was correct.
6. Which component first produced incorrect behavior.

## Key Insight

The main diagnosis failures came from insufficient cross-layer correlation.
Single-component logs were often accurate but misleading in isolation. The
system needs evidence that is:

- correlated by request ID and instance ID
- normalized across components
- captured at both request and response time
- available as JSON for agent consumption
- safe to inspect because secrets are redacted

## Proposed Deliverable

Add a diagnostic bundle mechanism that can be triggered:

- automatically for selected failures (`4xx`, `5xx`, repeated redirect loops,
  readiness mismatches)
- manually for a known instance ID or request ID

The bundle should be available as:

- a JSON document for agents and tooling
- a concise human-readable summary

## Diagnostic Bundle Contents

### 1. Request Trace

- request ID / correlation ID
- authenticated user
- original URL
- request headers relevant to routing and auth
  - `Host`
  - `X-Forwarded-*`
  - `REMOTE_USER`
- response status
- response `Location`
- upstream `Location`
- cookie names and cookie path metadata

### 2. AppStore Instance Resolution

- requested instance ID
- resolved `referenceID`
- resolved controller UUID
- `HelxInst` name
- app ID
- username normalization results
- host used in instance URL generation
- computed `NB_PREFIX`, `FB_BASEURL`, and related env

### 3. Kubernetes / Controller State

- `HelxInst` spec and selected status fields
- `HelxApp` ambassador config fragment
- Service annotation (`getambassador.io/config`)
- selected Deployment/Pod metadata
- selected environment variables from the running container
- generated app config files when relevant
  - for example `rserver.conf`

### 4. Path Translation Trace

- intended external prefix
- Ambassador prefix
- Ambassador rewrite target
- resty original path
- resty rewritten response location
- backend request path actually observed

### 5. Backend Observation

- startup command
- selected env values relevant to routing/auth
- recent application log excerpt for this request ID or timeframe
- readiness/liveness endpoints and last observed status

### 6. Parsing / Normalization Results

- CPU and memory normalization outputs
- path normalization outputs
- identity normalization outputs
- any fallback rules invoked

## Required Workstreams

## Workstream 1: Correlation IDs End-to-End

Propagate a single request correlation ID through:

- AppStore
- resty
- Ambassador
- backend service

Requirements:

- every request should carry or receive a stable correlation ID
- logs in each component should emit the same ID
- diagnostic bundles should key off this ID

## Workstream 2: Instance Identity Graph

Build a normalized identity map for each instance:

- AppStore instance ID
- `referenceID`
- controller UUID
- `HelxInst` name
- Service name
- Pod name

Requirements:

- store the mapping in one machine-readable place
- expose it through an internal diagnostic endpoint
- make it easy for an agent to move from any one identifier to all others

## Workstream 3: Request/Response Rewrite Evidence

Capture request and redirect transformation evidence at each proxy layer.

Requirements:

- AppStore logs original request path and generated instance URL
- Ambassador logs matched mapping and effective rewrite
- resty logs original path, upstream location, final location
- bundle includes both inbound and outbound transformation steps

## Workstream 4: Runtime Env and Generated Config Snapshot

Expose the exact app runtime context that influences request behavior.

Requirements:

- selected env snapshot from launched container
- generated config snapshot for app-specific config files
- capture path-sensitive values such as:
  - `NB_PREFIX`
  - `FB_BASEURL`
  - `REFERENCE_ID`
  - `GUID`
  - `RSTUDIO_SERVER_BASE_PATH`
  - generated `www-root-path`

This data must be redacted where appropriate.

## Workstream 5: Automated Failure Triggers

Create rules that automatically collect a bundle when the system sees likely
cross-layer failures.

Examples:

- `is_ready` returns false while pod is ready
- repeated `302` or `308` loops on `/private/`
- `/private/...` request falls back to AppStore unexpectedly
- backend receives an unexpected root path instead of prefixed path
- parsing exceptions in resource normalization

## Workstream 6: Agent-Oriented Output

Produce a structured output that a reasoning agent can consume directly.

Requirements:

- JSON schema with stable field names
- explicit “observed vs expected” sections
- compact evidence excerpt plus references to raw logs
- one-paragraph summary describing likely first point of failure

Suggested top-level JSON sections:

- `request`
- `instance_resolution`
- `controller_state`
- `proxy_trace`
- `backend_state`
- `observations`
- `likely_failure_layer`

## Workstream 7: Security and Redaction

Diagnostic bundles must be safe to share with operators and agents.

Requirements:

- redact bearer tokens, cookies, passwords, OAuth tokens, and secrets
- preserve metadata needed for diagnosis
  - header presence
  - cookie names
  - path values
  - identity values
- add allow-list based field collection rather than dumping raw env or raw CRDs

## Workstream 8: Manual Trigger Interfaces

Provide operator-friendly ways to generate a bundle on demand.

Suggested interfaces:

- AppStore admin endpoint by `request_id`
- AppStore admin endpoint by `instance_id`
- command-line tool wrapping the endpoint
- optional cluster job for deeper snapshot collection

## Proposed Epic Stories

1. Add end-to-end correlation ID propagation across AppStore, resty,
   Ambassador, and backend.
2. Add an internal AppStore diagnostic endpoint for instance identity
   resolution.
3. Add machine-readable request/response rewrite logging in resty.
4. Add controller/Service/Pod snapshot collection with redaction.
5. Add backend env/config snapshot collection for selected apps.
6. Add automatic bundle generation on configured failure signatures.
7. Add JSON schema and summary renderer for agent consumption.
8. Add operator CLI or admin UI to fetch diagnostic bundles.
9. Add regression fixtures for known failure classes:
   - wrong instance ID mapping
   - wrong trailing slash in env path
   - wrong redirect prefix restoration
   - CPU quantity parse failure

## MVP Scope

The MVP should focus on connect-path and readiness failures, since that is where
the current debugging cost is highest.

MVP bundle must include:

- correlation ID
- request path and response location
- instance identity graph
- `HelxInst` and Service annotation snapshots
- resty redirect trace
- selected backend env values
- selected generated config files

## Suggested Acceptance Tests

### Acceptance Test 1: Path Rewrite Mismatch

Trigger a request where backend receives `/` but should receive a prefixed path.
The diagnostic bundle must show:

- original request path
- Ambassador rewrite target
- backend request path
- likely failure layer = request rewrite

### Acceptance Test 2: Redirect Prefix Loss

Trigger a backend redirect to `/auth-sign-in`.
The diagnostic bundle must show:

- upstream location
- final location returned to client
- original instance prefix
- likely failure layer = response redirect rewrite

### Acceptance Test 3: Instance Identity Mismatch

Trigger a case where controller UUID and `referenceID` differ.
The bundle must show the full identity graph and the mismatched lookup result.

### Acceptance Test 4: Env Path Normalization Error

Trigger a case where app env has a trailing slash but the app expects none.
The bundle must show:

- emitted env value
- generated config value
- backend-observed failure

### Acceptance Test 5: Resource Quantity Parse Failure

Trigger readiness evaluation with CPU quantity `2500m`.
The bundle must show the raw quantity, normalized value, and parsed result.

## Implementation Notes

- Prefer allow-listed collection over broad cluster scraping.
- Prefer JSON-first design with human summary derived from it.
- Make collection incremental:
  - cheap metadata on every request
  - expensive bundle collection only on trigger
- Keep raw evidence references when possible instead of duplicating large logs.

## Risks

- Over-collection of secrets or personal data
- Too much bundle volume if automatic triggers are too broad
- Tight coupling to current proxy/controller implementation details
- Diagnostic system becoming another source of truth drift

## Mitigations

- explicit redaction policy
- configurable trigger thresholds
- versioned JSON schema
- evidence collection tests tied to known regressions

## Definition of Done

This epic is complete when:

- a failing `/private/` request can be diagnosed from one generated bundle
- an agent can identify the likely failing layer without shell access
- operators no longer need to manually gather the basic evidence set from
  AppStore, controller, resty, Ambassador, and backend logs
- regression fixtures exist for the major classes of failure already seen in
  production debugging

