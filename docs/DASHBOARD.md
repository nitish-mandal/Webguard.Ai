# Operator dashboard (Phase 11)

**Acceptance PASSED:** the operator confirmed dashboard job
802d2957d6ef48d182a8b04919e34165 reproduced twice, verified the predefined fix
(original 1 pass, full suite 2 passes, patched regressions 9 passes), and recorded
exactly one simulated offline draft. The earlier preparation/blocker notes below
are historical. Phase 12 reran offline product/frontend/Docker checks; its live
run was explicitly deferred. See RELEASE.md and current STATUS.md.

Latest manual-test preparation: API and worker have been restarted with a new
private root .env operator token and preserved Docker/image configuration; the
running frontend was left in place. Read-only readiness/auth checks pass. Copy
only the AUTH_TOKEN value privately from root .env in your editor. Refresh the
page or click Check API, enter Operator token, click Connect, then Create repair
job once on main. Browser acceptance remains pending your confirmation of
reproduced failure, successful verification and one simulated draft. No job was
submitted by the agent during preparation.

The React dashboard uses the real authenticated API. It shows the configured
approved repository, provider mode and worker heartbeat availability; it does
not infer Docker/provider readiness from that heartbeat. HTTP handlers remain
read-only storage/projection operations except existing job creation/cancellation.

## Start from the project root

Install the existing locks using SETUP.md. Use installed Python 3.12.10 and Node
22.16.0/npm 10.9.2 (verified local versions). The examples use the workspace-local
Node installation; a compatible installed Node can run the same npm scripts.
Keep one private root `.env` shared by API/worker. Default demo configuration:

- ALLOWED_REPOSITORY=demo-repository and a private random local AUTH_TOKEN.
- ENABLE_LIVE_GEMINI=false and ENABLE_GITHUB_DRAFT_PR=false.
- The same file-backed DATABASE_URL, owned WORKSPACE_ROOT and prepared immutable
  RUNNER_IMAGE_ID for API and worker. No external credential is required.

Terminal 1, API (loopback only, access logging disabled):

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Terminal 2, worker:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
.venv\Scripts\python.exe -m worker
```

Terminal 3, frontend (the local tool path is optional when npm is already on PATH):

```powershell
$env:PATH = (Resolve-Path .tools/node-v22.16.0-win-x64).Path + ';' + $env:PATH
.tools\node-v22.16.0-win-x64\npm.cmd --prefix frontend run dev -- --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**. The frontend defaults to http://127.0.0.1:8000.
VITE_API_BASE_URL may select http://localhost:8000 instead; only those loopback
HTTP origins, without credentials/query/path overrides, are accepted by the
client. Other API hosts/ports fail before sending auth. The backend CORS origins
remain explicit localhost/127.0.0.1 ports 5173/8000; no cookies or proxy broadening.

Stop the frontend/API with Ctrl+C in their terminals. Stop the worker with Ctrl+C
to drain, or `.venv\Scripts\python.exe -m worker --stop WORKER_ID`, replacing the
ID with its startup JSON value. Confirm worker process exit; the request alone
does not confirm executor stop. For an active job use the dashboard Cancel job
button instead. Worker cleanup/reconciliation semantics are in WORKER.md.

## Authentication and submissions

Enter only the local AUTH_TOKEN at runtime in the labelled password field.
Connection checks GET jobs using the documented Authorization bearer header.
The token is kept in memory, cleared on disconnect/page close, never placed in
VITE settings, URLs, local/session storage, logs or the build. Gemini/GitHub
credentials are not dashboard inputs and stay on the server. Requests omit
cookies, reject redirects, set no-store/no-referrer and have a 10-second timeout.
Raw server/transport error strings are replaced with safe user-facing messages.

Submission always uses the server's approved repository. The operator supplies
only its Git ref (main by default); existing backend validation is authoritative.
Each logical request gets a random Idempotency-Key and an immediate in-flight
lock to prevent duplicate clicks. An uncertain result retries the same key and
frozen payload. After 202 the submit button remains disabled until the operator
explicitly selects Start another job. That creates a new logical request.

The nonsecret key is displayed for recovery. Pending requests are held only in
memory: reloading clears that client request, so keep its displayed key when
recovering an uncertain acceptance. Reconnect/check recent jobs before starting
another. Durable deduplication is performed by SQLite, not by the UI lock alone.
Submitting while the worker is unavailable still saves the job and explains that
processing must wait. Authentication errors disconnect the protected workspace.

## Data and polling

Recent jobs use GET /api/jobs?limit=10&order=desc, with bounded older-page loading
(up to 50 cached jobs). Default API order remains asc for existing clients. The
selected job shows actual state, stage, attempts/limits, pin, detection comparison
and excerpt, verification rounds/checks/image/patch/commands, cancellation and
publication metadata. Source/log/model text is rendered as escaped text, never
HTML, Markdown execution or a command. Accessible native forms/buttons, labels,
focus rings, skip link, table captions/headers and polite state announcements
support keyboard and screen readers. Manual browser/accessibility acceptance is
still pending because Computer Use was blocked (see below).

Active loaded jobs use non-overlapping polling with 1/2/4/8/10-second bounded
backoff. Requests have timeouts and AbortControllers. Terminal selected jobs stop
their own detail/evidence/events polling even if other jobs remain active. With
no active loaded jobs, automatic polling stops entirely. Refresh explicitly
checks new jobs, worker availability and later terminal cleanup/reconciliation.
Page close/disconnect/unmount cancels timers/requests. Versions prevent stale job
responses from regressing state; terminal evidence is refreshed if its snapshot
is older than the terminal job response.

Events use ordered cursor pages (50 items, at most two pages per refresh), dedup
by sequence, and retain up to 200 received events in the view. Load more events
fetches additional pages on demand. The server retains the full durable history.
Green-suite/no_reproducible_bug, failed verification, paused blockers, safe API
errors and cancellation have distinct UI explanations. Cancelled is not a claim
that all execution stopped; working-copy cleanup and later publication observation
can be refreshed explicitly.

## Read-only report and link policy

New protected GET /api/jobs/{id}/report returns a versioned, bounded safe projection:
stage/dispatch status, at most two detection observations and a 2,048-character
traceback excerpt, up to ten verification rounds/four checks each, and publication
metadata. It reads matching hashed service-owned receipts and committed SQLite
verification summaries. Missing/tampered/unavailable excerpts remain unavailable;
there is no arbitrary path input, target execution, repair or publication call.
Full stdout/stderr, source trees, credentials, controller paths/leases/fences and
idempotency hashes are excluded. Errors/auth/CORS/query limits remain unchanged.

Simulated drafts are labelled SIMULATED OFFLINE DRAFT with an explicit statement
that no GitHub PR was created, and never receive a PR hyperlink. A live_url is
returned only for a completed matching publication/current verification proof,
exact approved owner/repository, positive PR number and exact stored URL
https://github.com/owner/repository/pull/NUMBER. Stale, simulated, incomplete,
wrong-repository, credential-bearing or mismatched URLs cannot link. The client
checks the same exact URL/mode/draft/confirmed conditions before creating a link.
No arbitrary links are rendered from repository text/events. Live flags mean
configured, not live acceptance verified.

## Historical acceptance preparation and browser-tool limitation

Frontend mocked tests, TypeScript/build, backend product tests, and the real
loopback API/worker/Vite plus Docker check are recorded separately in
PHASE_PROGRESS.md and docs/baseline/phase11-*.

The automated browser attempt was blocked. Browser inventory reported "The browser access
host is unavailable". Selecting the existing Chrome window then stopped Computer
Use because it could not determine the current browser URL on Windows with enough
confidence to enforce policy. No browser job was submitted, no screenshot/visual
layout or real keyboard/screen-reader session was accepted, and no alternate UI
automation bypass was attempted. Receipt: baseline/phase11-browser.json.

The independent `runner_image/check_dashboard_api.py` starts real TCP Uvicorn,
worker and Vite processes in an isolated non-production configuration, verifies
frontend serving/CORS/operator auth, submits the demo through HTTP, checks all six
real Docker identities/settings and one simulated draft, then drains/stops only
those owned processes. Its private test token is removed on shutdown. This check
is explicitly NOT browser acceptance and does not execute the React UI in a browser.

To complete the browser gate when approved browser access is available (or
manually): start the three terminals above; connect using the local token; confirm
approved demo/offline/worker state; create one main job and observe disabled
duplicate submission; wait for two matching pagination failures, original 1 pass,
suite 2 passes and independent 9 passes (baseline control 3 fails/6 passes); confirm
one simulated draft and no live PR link; inspect/cycle controls by keyboard,
disconnect/reconnect to the durable job and confirm terminal polling stops.
Do not start another logical job to test retry/dedup. Record actual browser and
Docker results separately. Phase 12 formal readiness is conditional on completing
that browser gate; it has now been satisfied by the user-confirmed job above.
Live Gemini/GitHub remain unverified.
