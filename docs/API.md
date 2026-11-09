# Job API v1 (Phase 3)

This API stores jobs; no handler runs target tests, repairs, Gemini or GitHub.
A separately started Phase 10 worker automatically claims queued jobs. See WORKER.md
for startup/shutdown. HTTP 202 is durable acceptance, not a processing result.
Model/provider keys are never client authentication tokens.

## Local operator authentication

Set a randomly generated AUTH_TOKEN in the private root `.env` or server process
environment: 32-256 visible ASCII characters, with no spaces or newlines. Use at
least 32 random bytes (for example a 43-character URL-safe encoding). Never reuse
a provider credential. No token is generated, printed or installed automatically.
An empty token leaves public probes available but every job route returns 503
auth_not_configured. Offline job acceptance needs this local token, but needs no
Gemini/GitHub credential and both live flags remain off by default.

Send `Authorization: Bearer <operator token>` on every job request. Header scheme
matching is case-insensitive; the token must match exactly. There are no cookies,
sessions, login endpoint, query-string tokens or ambient browser credentials.
Cookies cannot authenticate. CSRF cookie protection is consequently not used.
The future UI should ask the operator for a token at runtime and retain it only
in memory for that session. Never embed it in frontend code, VITE_ configuration,
localStorage, a URL, a command argument, a screenshot or logs. Swagger's Authorize
dialog supports OperatorBearer and does not persist authorization across reloads.

Start from the project root using the installed venv:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Only loopback Host headers (127.0.0.1 or localhost) are accepted. Do not bind this
development service publicly. Explicit browser origins are localhost/127.0.0.1
on ports 5173 (future UI) and 8000 (API docs). CORS permits GET/POST and the
Authorization, Content-Type and Idempotency-Key headers, without credentials;
Location is exposed. Preflight needs no token and contains no job data. Other
browser origins are rejected on actual job requests. CLI requests may omit Origin.

PowerShell flow, with the same token entered privately (never echoed):

```powershell
$operatorSecret = Read-Host 'Operator AUTH_TOKEN' -AsSecureString
$operatorCredential = [pscredential]::new('local-operator', $operatorSecret)
$headers = @{ Authorization = 'Bearer ' + $operatorCredential.GetNetworkCredential().Password }
try {
    $headers['Idempotency-Key'] = [guid]::NewGuid().ToString('N')
    $job = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/jobs' -Headers $headers -ContentType 'application/json' -Body '{"repository":"demo-repository"}'
    $headers.Remove('Idempotency-Key')
    Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/jobs/' + $job.id) -Headers $headers
} finally {
    Remove-Variable headers, operatorCredential, operatorSecret
}
```

Save/reuse a job submission's nonsecret Idempotency-Key if retrying after an
uncertain response. The example creates a fresh key for a new logical request.
The request body repository must match ALLOWED_REPOSITORY exactly.

## Endpoints

| Route | Auth | Result |
| --- | --- | --- |
| GET /health | Public | 200 `{"status":"ok"}`: process liveness only |
| GET /ready | Public | 200 ready or 503 not_ready, with database_ready boolean |
| GET /api/status | Public | Capabilities and configured mode; never settings/keys |
| POST /api/jobs | Operator | 202 JobView and relative Location after successful commit |
| GET /api/jobs | Operator | JobPage with items and next_cursor |
| GET /api/jobs/{id} | Operator | Durable JobView; valid unknown ID returns 404 |
| GET /api/jobs/{id}/events | Operator | Ordered EventPage with items and next_cursor |
| GET /api/jobs/{id}/report | Operator | Bounded versioned safe evidence/dispatch/validated publication projection (Phase 11) |
| POST /api/jobs/{id}/cancel | Operator | 200 CancelResult after durable cancellation |

POST jobs requires exactly one Idempotency-Key header (1-200 visible ASCII
characters). The JSON object accepts only repository, ref (default main) and sha
(optional full lowercase 40/64-character commit SHA). Extra fields, commands,
URLs, filesystem targets, unapproved repositories and invalid Git refs are
rejected. No ref is resolved or cloned here; null SHA means not yet pinned.

The same key and normalized valid input returns the same current job with 202,
even after restart or cancellation. A changed valid payload conflicts with 409.
Invalid/unapproved payloads are rejected before creation, regardless of key.
Concurrent submissions cannot create duplicate jobs. A failed insert, event write
or commit never returns 202. No in-memory acceptance fallback exists.

JobView exposes id, repository, ref, sha, state, UTC Unix timestamps/deadline,
typed failure reason, cancellation fields, version, usage/attempt counters and
nonsecret limit snapshots. Idempotency/payload hashes, lease owner/fence, database
paths, credentials and raw settings are omitted. A queued job is not evidence
of processing, reproduction or repair. Phase 11 adds /api/jobs/{id}/report for
bounded evidence/dispatch/publication summaries and validated live PR links.
Full evidence files, controller paths and raw logs remain private.

GET jobs accepts `limit=1..100` (default 50), optional opaque cursor and
`order=asc|desc` (default asc). Phase 11 recent-job views use desc; keep the same
order with a cursor across pages.
Return next_cursor unchanged as cursor in the next request. Ordering is
(created_at, id), so equal timestamps do not skip records. GET events accepts only
limit and `after=0..9223372036854775807` (default 0): pass next_cursor as after.
Event sequence is strictly increasing per job. Event data is whitelisted and
redacted again for HTTP; private ownership/fencing information is omitted.
A full page returns a cursor even if it was the last page; the following empty
page ends pagination with null. Duplicate/unknown query parameters are invalid.
Job IDs must be 32 lowercase hex characters; malformed IDs return 422.

Cancellation accepts an empty body, JSON null or `{}`; extra fields are invalid.
It persists cancellation_requested/cancelled_at and transitions to cancelled,
invalidating controller ownership. Repeated cancellation returns the same durable
result. Other terminal outcomes return 409 without mutation. CancelResult contains
the job and execution_stop_confirmed=false: this confirms a recorded cancellation,
not that an active process has stopped. No executor exists yet; a future runner
must implement and verify process cleanup. POST query parameters are forbidden.

## Capabilities, readiness and errors

Status reports mode=offline when both live flags are off, otherwise live_configured.
That describes configuration intent, not operational provider integrations.
processing_enabled and repair_enabled are always false in Phase 3. job_api_enabled
requires configured operator auth and database readiness. No provider name/model,
credential presence/value, target identity or database path is exposed publicly.

Phase 4 adds explicit trusted-controller source acquisition, not an HTTP source
operation or polling worker. Public GitHub reads are separate from the model/PR
live flags; the offline fixture path uses local committed objects only. API job
acceptance triggers neither. source_acquired events may expose pinned SHA,
workspace identity and manifest/profile digests, never local filesystem paths.
See SOURCE_ACCESS.md; schema migration 3 adds durable source metadata.

Readiness probes current migration versions and required tables and exercises a
SQLite write statement without changing rows. A read-only, unavailable or incomplete
database is unready while health stays live. If initial database setup fails, the
process stays alive but job routes return storage_unavailable; fix storage and
restart. Invalid server settings still fail startup safely. Probes never claim
worker/container/Gemini/GitHub readiness and do not reap expired jobs.

Job errors have a stable envelope: `{"error":{"code":"...","message":"..."}}`.
Rejected values, request bodies, validation dumps, SQL paths and exception text
are never reflected. Main codes:

| HTTP | Code | Meaning |
| --- | --- | --- |
| 401 | unauthorized | Missing, malformed or incorrect operator header |
| 403 | forbidden_origin | Unapproved browser Origin |
| 404 | unknown_job | Well-formed ID not stored |
| 409 | idempotency_conflict | Key already associated with other valid input |
| 409 | terminal_state_conflict | Completed terminal result cannot be cancelled |
| 422 | invalid_input | Invalid/missing/extra body, header, query or ID fields |
| 413 | request_too_large | Body exceeds 16,384 bytes |
| 415 | unsupported_media_type | Non-JSON mutation body or compressed body |
| 503 | auth_not_configured / service_not_ready / storage_unavailable | Cannot accept jobs |
| 500 | internal_error | Unexpected internal failure; raw exception suppressed |

Additional boundary errors: invalid_host/invalid_request (400),
request_target_too_large (414), headers_too_large (431). Unknown routes and methods
return not_found (404) and method_not_allowed (405). Readiness has its own typed
ready/not_ready body. CORS preflight errors use the framework preflight response.

Body bytes are counted before JSON validation, including chunked bodies and lying
Content-Length headers. Headers are bounded at 16,384 bytes and path+query at
2,048 bytes. Duplicate JSON keys, duplicate framing/key headers and nonfinite JSON
values are rejected. Encoded/compressed bodies are unsupported. Public and job
responses are no-store. No automatic slash redirects can reflect a request URL.

Application errors use static safe messages and do not log raw exceptions. The
standard Uvicorn access logger also has a filter that omits every request target
and untrusted request argument; the documented command disables access logs
entirely. Do not add raw request/config logging in future handlers or adapters.

OpenAPI models/security are available at /openapi.json and /docs. Implementation
references: [FastAPI query models](https://fastapi.tiangolo.com/tutorial/query-param-models/)
and [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/first-steps/).
No cookie session or OAuth provider is involved in this local bearer flow.

Phase 9 adds explicit controller publication, not an HTTP publish action. Safe
publication events expose branch/commit/PR identifiers, static failure codes and
`simulated` where relevant; bodies, tokens and raw remote responses are excluded.
An offline `draft_pr_created` event is explicitly `simulated: true` and is not a
real GitHub PR. JobService.publication() supplies full durable publication metadata
to trusted controller callers. Readiness now also checks the migration-6 intent
table, plus the Phase 10 dispatch/session tables. Phase 10 heartbeats now drive
worker_available/processing_enabled/repair_enabled; absent, draining or stale
workers report false. This is worker availability, not Docker readiness. Safe
stage/defer/cleanup and terminal publication-reconciliation events show progress,
retry timing and simulation. HTTP handlers remain storage-only. See WORKER.md.
