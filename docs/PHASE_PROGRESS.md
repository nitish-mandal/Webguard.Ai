# Phase progress

## Provider timeout diagnosis/fix - 2026-11-06: mocked validation PASSED

Spent job 53729077308847e9879b263b7d752d15 remains failed with one reserved call,
no patch/verification and no publication attempt. No new live job/request was
made. Configured model gemini-3.8-flash, official SDK 2.34.0. Existing events show
30.014 seconds to provider_timeout with 284.868 seconds left on the job deadline.
Both old whole-process and nested SDK HTTP timeouts were 30 seconds: insufficient
startup/finish allowance. Provider receipt/root latency cause cannot be inferred
from old logs; no HTTP acknowledgement or model response was recorded.

Prepared independent SDK cap plus remaining-deadline clipping, outer timing that
includes child creation and rejects late completion, and bounded secret-free
SDK/HTTP stage/status observations for future failures. Raw exceptions/headers/
bodies never enter evidence. No SDK retry increase, dependency/lock changes or
live configuration activation. Proposed values (NOT applied privately):
REPAIR_CALL_SECONDS=90, REPAIR_HTTP_TIMEOUT_SECONDS=60, JOB_TIMEOUT_SECONDS=420.
Existing one-call/one-repair/one-publication bounds and zero retries stay intact.

Actual checks: 12 focused mocked SDK/deadline tests pass in 2.83s; initial existing
repair/settings checks 70 pass in 27.72s; full product suite 625 passed,
24 isolation tests deselected, one existing Starlette/httpx warning, 152.32s.
Ruff passes for backend/worker/tests/scripts/runner_image. Real Docker/frontend
checks not rerun for this controller change; mock HTTP is not live acceptance.
Private flags both false, original call/job settings 30/300 preserved, failed
job/budgets unchanged. No new job or provider call without additional approval.

Details, exact commands/proposal and evidence limits:
PROVIDER_TIMEOUT_DIAGNOSIS.md; baseline/provider-timeout-diagnosis.json and
provider-timeout-*-tests.log. Phase 11 evidence preserved; previous release ZIP
not rebuilt. Successful live fix verification/publication remain UNVERIFIED.

## Phase 12 live attempt - 2026-11-06: FAILED at repair, offline restored

Exactly one authorized job: 53729077308847e9879b263b7d752d15, approved
nitish-mandal/webguard-live-demo/main at b5621b9be3e6b1eabdcb1798ba877016d33a6ce6.
Actual GitHub acquisition and two fresh Docker suite runs reproduced the same
pagination failure: 1 failed/1 passed each, exits 1/1, durations 3.296s/2.469s;
expected [10, 20], actual [10]. Bundled fixture unchanged.

The sole live Gemini attempt exceeded its configured 30-second limit:
repair_rejected reason provider_timeout, terminal failure_reason model.
No candidate, verification round, publication attempt or draft PR. No second
job/retry was submitted. Stored model tokens are reserved budget, not actual
provider billing/response proof. Successful live repair/publication remain
UNVERIFIED. This supersedes earlier readiness-only notes below.

Both flags restored false; API and worker restarted with the offline config.
Current API confirms offline mode, database_ready and worker_available, live
Gemini/GitHub flags false. Zero managed containers/volumes after cleanup. Phase 11
browser acceptance remains preserved. No new browser acceptance or release ZIP
rebuild claimed. Full commands, outcomes and limitations: PHASE12_LIVE_RESULT.md;
sanitized machine receipt: baseline/phase12-live-run.json.

## Refreshed read-only preflight - 2026-11-06: PASSED, execution OFF

After the operator opened Docker Desktop, existing DockerRunner.preflight passed
Linux daemon resource/security policy and immutable image/profile policy for
sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
No container started, target test or live pipeline execution was performed.
The earlier unavailable-engine blocker is resolved.

GitHub accepts the private installation token now; its scope lists exactly the
approved public active nitish-mandal/webguard-live-demo repository. Public main
still resolves to b5621b9be3e6b1eabdcb1798ba877016d33a6ce6, and both required
files match the unchanged local demo exactly by Git blob hash. All required
settings/bounded values are present and valid, with the recommended model set.
Both live flags remain false and no .env changes were necessary.

Read-only preparation is ready, not live acceptance: Gemini response/quota,
actual patch verification and draft creation remain UNVERIFIED. Token write
permissions were not independently established by these read-only requests.
No job, Gemini call or publication was attempted. Token acceptance is only
current validity and must be refreshed if it expires before execution.
Receipt: baseline/phase12-current-readonly-preflight.json. No credentials in
this evidence. Phase 11 browser acceptance and earlier offline release ZIP
remain unchanged. Stop here under the operator's readiness-only instruction.

## Current authenticated read-only preflight - 2026-11-06: Docker BLOCKED

All required local settings are present, offline settings validation passes,
approved repository matches, and both live flags remain false (no .env edits).
The private GitHub installation token is accepted by GitHub now and its
installation/repositories response lists exactly one repository, the approved
nitish-mandal/webguard-live-demo. Repository identity matches, it is public and
active. This is current authentication/scope proof, not a guarantee of future
validity. Contents/Pull requests write permissions were not independently proven
by these read-only requests; the repository response does not report push access.

Unauthenticated public main resolves to b5621b9be3e6b1eabdcb1798ba877016d33a6ce6.
Git blob hashes prove pagination.py and tests/test_pagination.py exactly match
the unchanged local demo. Gemini key/model present; no generation/account-quota
check or live repair was performed.

Docker CLI exists but the Linux engine is unavailable. Existing DockerRunner
preflight returned cli_failed before image inspection. Diagnostic command:
`docker --host npipe:////./pipe/dockerDesktopLinuxEngine info --format {{.ServerVersion}}`
exited 1: failed to connect to the Docker API; open
//./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
Start Docker Desktop and wait for its Linux engine, then rerun read-only daemon
and immutable-image policy checks. No container was started and current image
availability/policy could not be reverified. Readiness remains BLOCKED.

Sanitized receipt: baseline/phase12-current-readonly-preflight.json. No secret
values printed or persisted in evidence; no job, target test, Gemini request,
repository write or PR. Phase 11 browser acceptance remains preserved; existing
ZIP remains the earlier offline release snapshot.

## Private non-secret setup applied - 2026-11-06; submission blocked

Applied only the latest preflight non-secret values to root .env: approved
repository, immutable runner image, isolated live SQLite/workspace paths,
one-call/one-repair/one-publication budgets, zero repair retries, 30-second model
call, 20000-token limit and 300-second job deadline. Both live flags remain false.
Read-back assertions verified all credentials and unrelated settings preserved,
all requested values match, and offline settings validation passes. No process
restart, provider request or job submission occurred.

Local preflight now matches nitish-mandal/webguard-live-demo. The remaining
private settings are GEMINI_MODEL and GITHUB_TOKEN. Flags are intentionally off,
so submission is not ready. The selected model recommendation is gemini-3.8-flash
based on current official structured-output/model docs; no live compatibility,
account quota or patch was tested. See GITHUB_APP_SETUP.md for App registration,
exact permissions and selected-repository installation.

Added an operator-invoked local token setup helper that signs an app JWT from a
local PEM, requests exactly the approved repository and three required
permissions, verifies minted scope, and writes only GITHUB_TOKEN privately.
It never prints credential/JWT/PEM/API bodies and requires live flags off.
It has NOT been used against GitHub; tests mock issuance, reject wrong scope,
check flags and preserve existing credentials. No repository effect or model
call is part of this helper. Existing pinned dependencies already supply its
cryptography/httpx/dotenv requirements; locks unchanged.

Validation: python -m pytest tests/test_github_token_setup.py
tests/test_live_preparation.py -q: 5 passed in 5.44s; targeted ruff check passes.
These are additional setup-unit checks, not a rerun of 610 product or 24 Docker
checks and not live token issuance. Await private model/token setup, then rerun
read-only readiness before any job. Phase 11 acceptance remains preserved.
The previous release ZIP remains its prior offline snapshot.

## Demo upload verified - 2026-11-06; live execution OFF

Using explicitly authorized authenticated GitHub access, committed both unchanged
local demo files together on main in nitish-mandal/webguard-live-demo:
b5621b9be3e6b1eabdcb1798ba877016d33a6ce6 (parent
559a0f4a3915827004c1307b34fda3fceeb009ad). Ref update was non-forced and
conditioned on the expected prior SHA. Remote main and complete recursive tree
were read back. pagination.py blob 68039f864be2d65440b98090022368a666f9824f and
tests/test_pagination.py blob 042eaa17a4132e2951a0d8ae6cb95287659bfb9e match
exact local bytes. README blob 48a8a7d371b95688bf28f8fba76d028975c682f5 unchanged.
The intentional defect and original tests were preserved. Repository layout
blocker is resolved; earlier missing-file receipts below are historical.

Read-only private configuration check: AUTH_TOKEN/GEMINI_API_KEY present;
GEMINI_MODEL/GITHUB_TOKEN missing; exact repository, immutable runner image,
isolated database/workspace and one-run limits still require RELEASE.md values.
Both live flags remain false; no .env change was needed. No target execution,
Gemini request, pipeline job or draft PR was attempted. Phase 11 acceptance is
preserved. Existing release ZIP remains its prior offline snapshot.

Commit: https://github.com/nitish-mandal/webguard-live-demo/commit/b5621b9be3e6b1eabdcb1798ba877016d33a6ce6

## Rechecked live preflight - 2026-11-06: NOT READY, flags OFF

Read-only connector and separate no-cache unauthenticated GitHub API checks both
resolved main to 559a0f4a3915827004c1307b34fda3fceeb009ad. Its complete recursive
tree still contains only README.md. That file matches the bundled demo after
CRLF normalization, but not byte-for-byte. pagination.py and
tests/test_pagination.py are absent, so their unchanged contents cannot be verified.
Receipt: baseline/live-preflight-repository.json. No repository changes or target
execution occurred.

Private settings presence and comparison receipt: baseline/live-preflight-settings.json.
AUTH_TOKEN and GEMINI_API_KEY present; GEMINI_MODEL and GITHUB_TOKEN missing.
Needed updates: ALLOWED_REPOSITORY, RUNNER_IMAGE_ID, DATABASE_URL, WORKSPACE_ROOT,
MAX_MODEL_CALLS_PER_JOB, MAX_REPAIR_ATTEMPTS, MAX_PUBLICATION_ATTEMPTS,
REPAIR_MAX_RETRIES, REPAIR_CALL_SECONDS, MAX_MODEL_TOKENS_PER_JOB,
JOB_TIMEOUT_SECONDS (exact intended values in RELEASE.md). Other documented limits
already match. Both live flags verified false, with no .env edits needed.
No secret values displayed, no provider credential validation, job or PR. Existing
one-run scope approval is retained, but this request is preflight only with live
flags off. Phase 11 browser acceptance remains unchanged.

## Authorized live preflight - 2026-11-06: BLOCKED

Operator approved one live Gemini repair and one draft PR for
nitish-mandal/webguard-live-demo, base main, superseding the prior deferral for
that exact scope. Read-only GitHub checks found main exists but its root lists
only README.md. Required pagination.py and tests/test_pagination.py are absent.

Private presence checks confirmed GEMINI_API_KEY and AUTH_TOKEN are set. The
local live checker failed: GEMINI_MODEL, GITHUB_TOKEN, RUNNER_IMAGE_ID missing;
ALLOWED_REPOSITORY still demo-repository; both live flags false; one-attempt
budgets not selected. The isolated live database/workspace, 30-second model
limit, 20000-token budget and 300-second job deadline also need the documented
values in RELEASE.md. Credential values were not displayed; .env is unchanged.

Next: upload unchanged demo source/tests in the required root layout and fill
private live settings, then rerun preflight before one job. No live job, Gemini
call or PR occurred; live verification remains UNVERIFIED. Phase 11 accepted job
802d2957d6ef48d182a8b04919e34165 is preserved. The ZIP remains the prior offline
release snapshot. Older deferred-status text below is historical.

## Phase 12 - final offline verification and source release; live run DEFERRED

2026-11-06. Read SETUP.md and the full current progress/status boundaries; inspected
the worker, source/profile, provider, publication and existing acceptance gates
before changes. ANTIGRAVITY_MASTER_PROMPT.md remains absent. Phase 11 manual
browser acceptance for **802d2957d6ef48d182a8b04919e34165** is preserved below and
in baseline/phase11-browser-acceptance.json. No credential, working configuration,
accepted job/database, bundled defect or running frontend was changed by this phase.

### Live decision and exact blockers

The operator explicitly answered **"Defer the live run"** when asked to approve
the exact repository/base for one live Gemini job and draft PR. No live job,
Gemini call, GitHub acquisition/scope request, push or draft creation was attempted.
No connector account was substituted for the required server token/approval.

The private local-only configuration check found: operator auth present; approved
repository still demo-repository; GEMINI_API_KEY/GEMINI_MODEL/GITHUB_TOKEN absent;
both live flags false; RUNNER_IMAGE_ID empty in .env (the active offline worker
retains its prepared image in its preserved environment). Bounded live settings
have not been selected. The checker exits 2 with setting names/booleans, not
credential values, and explicitly says remote scope/model/publication unverified.
Receipt: baseline/phase12-live-preparation.log. This expected blocker is not a
failed offline product test. Current .env stays unchanged/offline.

Exact private settings and one-job procedure are in RELEASE.md: explicitly approve
one canonical public owner/repository/base; use a compatible public GitHub copy of
the unchanged pagination demo; fill GEMINI_API_KEY, GEMINI_MODEL, single-repository
ghs_ installation GITHUB_TOKEN, ALLOWED_REPOSITORY and RUNNER_IMAGE_ID privately;
enable the two live flags only on resumption. Use isolated live DB/owned root,
one model call/repair/publication attempt, zero provider retries, bounded token/
input/output/time/execution budgets and worker --once after one dashboard submission.
No raw key goes into chat, logs or frontend/VITE. Keep local AUTH_TOKEN private.

Current service-owned v4 policy supports this pagination layout/allowlist and its
nine immutable regressions, not arbitrary Python repositories. Source acquisition
is public unauthenticated GitHub HTTPS; private repositories/extra dependencies/
different layouts require a reviewed profile/prepared image first. A local
settings pass cannot verify actual GitHub ownership/token scope, remote base,
Gemini model/quota/response, exact live patch or draft. All remain NOT VERIFIED.
Future publication must inspect actual GitHub base/head/parent/diff/check evidence,
require draft:true and exactly one matching PR, retain uncertainty reconciliation
and leave the draft unmerged for operator review. No real PR URL exists here.

### Actual final checks

All target execution remained inside the unchanged immutable Docker v4 image.
Installed controller Python 3.12.10 and workspace Node 22.16.0/npm 10.9.2 were used;
no Python/package download, live credential installation, AppControl/security
change or fresh clean install is claimed. For npm, PATH was prepended with the
workspace Node directory and npm.cmd invoked with --prefix frontend.

| Exact command | Actual result | docs/baseline log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | Initial 604 passed, 24 deselected, 1 existing warning; 237.65s | phase12-product.log |
| Same complete product command after adding release/preparation tests | **Exit 0; 610 passed, 24 isolation cases deselected, 1 existing warning; 229.68s** | phase12-product-final.log |
| npm --prefix frontend test | **Exit 0; 26 mocked frontend tests passed**, 2 files; 5.01s | phase12-frontend.log |
| npm --prefix frontend run typecheck | Exit 0; tsc --noEmit | phase12-typecheck.log |
| npm --prefix frontend run build | Exit 0; tsc + Vite 6.4.5, 33 modules, 1.27s; 248.43 kB JS | phase12-build.log |
| .venv\Scripts\python.exe runner_image/check_release.py | **Exit 0; 24 real Docker tests passed, zero skips, 604 then-current product cases deselected, 1 existing warning; 229.35s** | phase12-docker.log, phase12-docker-gate.json |
| .venv\Scripts\python.exe -m pytest tests/test_release.py -q | Exit 0; initial 4 packaging exclusion/tamper/reproducibility tests pass; later included in 610 | phase12-release-tests.log |
| .venv\Scripts\python.exe scripts/check_live_configuration.py | Exit 2, expected missing private live values/scope and disabled flags; no network | phase12-live-preparation.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image scripts | Exit 0; full Python/source-tool tree clean | phase12-lint-first.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase12-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 46-package lock current, UV_CACHE_DIR=.tools/uv-cache | phase12-lock-check.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; zero managed containers/volumes | phase12-cleanup.json |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both prior hashes unchanged | phase12-demo-hashes.log |

Real gate environment: DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine,
WEBGUARD_ISOLATION_IMAGE from phase8-image.json, WEBGUARD_RECORD_ACCEPTANCE=1.
The strict XML gate refuses skips/missing cases and covers all 24 existing real
isolation-marked tests: sixteen boundary checks, reproduction, fake repair,
three valid/invalid verification cases, simulated publication and two automatic
pipeline/cancellation cases. Its collection preceded the six new non-isolation
release/local-preflight tests; all six passed in the final 610-product run.
The unchanged Starlette/httpx warning remains unsuppressed. PowerShell uv stderr
can display NativeCommandError despite checked native exit 0. No failures were
hidden, and mocked tests are not counted as real Docker or live execution.

### Fresh offline evidence and preservation

The actual worker-subprocess/API Docker acceptance again resolved the deterministic
demo baseline **2de13361c14264f24c29cb2f778192c9f65858d0**, observed the same
pagination assertion in two fresh containers, and used the fake provider. Original
failing node: tests/test_pagination.py::test_first_page_contains_requested_count;
expected **[10, 20]**, actual **[10]**. Exact fake patch verified: original **1 pass**,
full original suite **2 passes**, independent **9 passes**, with the unpatched
control **3 fails/6 passes**. Exactly **one simulated offline draft**, including
reopen/retry deduplication; no real GitHub branch/commit/PR. Six distinct actual
container IDs, same SHA/image and cleanup true are retained in sanitized public
baseline/phase12-release-evidence.json. Raw phase-named acceptance exports were
regenerated by their existing test fixtures; no new browser run is inferred.

Image: sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
Patch: 518e82eb4b19cce91d43f87c3618575de2f7cfc303b3879e6778f61a95460171.
Fixture hashes remain 434d71f92fb9c64ab345bbc91b3a3fc6b06013d17d48d051d3afbf502ca8a87e
and 552ab0838dde5161e8ad9b39aad67f0b1c22411a60ad221cd2fc00185989f153.
Existing offline API/worker/frontend and the user-accepted Phase 11 records were
not stopped, reconfigured or used for test submissions. The gates use temporary
databases/Git copies/owned roots, fake credentials/providers and simulated remotes.

### Release tooling and changed files

Final archive review caught and corrected an initial packaging-only omission of
demo-repository. The release now requires and includes its unchanged source and
target tests; product pytest collection remains separate. After this correction,
`.venv\Scripts\python.exe -m pytest tests/test_release.py tests/test_live_preparation.py -q`
passed all **6 tests in 0.88s**, exit 0 (baseline/phase12-release-final.log), and
the full Python ruff check passed again. These targeted post-packaging checks
supplement the recorded 610-product/24-real-Docker runs; they do not imply another
full-suite or browser execution. The final archive is rebuilt and verified twice
for identical bytes, with a separate SHA256 sidecar and per-source-file manifest.

- runner_image/check_release.py: strict aggregate 24-case real Docker release gate.
- scripts/check_live_configuration.py and tests/test_live_preparation.py: local-only
  presence/bounds/repository comparison; no network or authorization claim.
- scripts/build_release.py and tests/test_release.py: explicit source allowlist,
  private/runtime exclusion, symlink/junction/hardlink/path rejection, configured-key
  scan, deterministic names/timestamps, SHA256 manifest, CRC/member/digest validation
  and atomic ZIP/checksum creation. Tests cover exclusions, accidental credential
  leakage, output containment, tampering and byte reproducibility.
- docs/RELEASE.md, SETUP.md, STATUS.md, PHASE_PROGRESS.md and current README/dashboard/
  delivery notes: accurate accepted Phase 11 state, final checks, private future
  live values, one-job procedure, scope limits and deferred live acceptance.
- .env.example: startup comment corrected; values unchanged. No dependency/lock
  version, service behavior, private .env or bundled fixture change.
- docs/baseline/phase12-release-evidence.json and phase11-browser-acceptance.json:
  selected public acceptance records, with no credentials/controller paths/database.

Release target: artifacts/WebGuard-AI-phase12-offline.zip plus .zip.sha256. The
builder includes source, locks, tests, docs and selected sanitized evidence; it
excludes all private envs except the blank public example, local databases/owned
workspaces, .tools/.venv/node_modules/build outputs/caches/Git data, private keys,
raw historical diagnostic receipts/logs and existing artifacts. It verifies the
entire archive against its member manifest and actual configured secrets before
publication. Older exact check history remains in this document; raw local logs
stay in the working project and are not shipped. Build command:
`.venv\Scripts\python.exe scripts/build_release.py`.

**Offline verification is complete. Live acceptance is DEFERRED BY THE OPERATOR
and remains UNVERIFIED.** Exact next step: when ready, select/approve the compatible
public repository/base, privately fill RELEASE.md's .env settings and explicitly
resume one bounded live job/draft. Until then no model request, live dashboard
submission, source fetch or publication is authorized by this preparation.

## Phase 11 browser acceptance - PASSED (user-confirmed manual run)

The user confirmed submitting job **802d2957d6ef48d182a8b04919e34165** from
the WebGuard-AI dashboard and observing:

- The pagination failure reproduced **twice**.
- The predefined fix verified successfully: original test **1 passed**, full
  existing suite **2 passed**, patched regression checks **9 passed**.
- **Exactly one simulated offline draft** was recorded.

Acceptance source: the user's explicit manual browser confirmation in this
conversation. This completes the previously pending Phase 11 browser gate.
It is separate from the agent's mocked frontend tests and earlier real TCP/Docker
acceptance; no agent browser automation, screenshot or screen-reader verification
is claimed for this manual job. No additional SHA/image/container metadata is
inferred from the user's confirmation. The earlier blocker and preparation
records below are retained as historical evidence, superseded for acceptance by
this successful manual run.

**Phase 11 browser acceptance is PASSED. Phase 12 is next.** Live Gemini and live
GitHub remain **NOT VERIFIED**; a simulated offline draft is not live publication.
Only docs/STATUS.md and docs/PHASE_PROGRESS.md were updated for this confirmation.
No code, credentials, worker configuration or fixture changed, and no tests were
rerun or new job submitted for this documentation-only update.

## Historical Phase 11 manual browser preparation - formerly pending; accepted above

The running frontend at http://127.0.0.1:5173 was preserved. The API was alive and
offline but operator authentication was disabled. No root .env existed on disk
(only .env.example), so .env was created from that template with only AUTH_TOKEN
changed. A cryptographically random 48-byte URL-safe token was generated locally
and saved atomically; every other dotenv value was compared unchanged. The token
was never printed, logged, put in receipts or embedded in frontend code.

The identified API/worker process directories, launch identities and creation
times were checked. Existing runner limits, prepared image and Docker endpoint/
TLS configuration were privately captured from only relevant configuration
variables. The old worker drained cleanly. Only the API and worker were restarted,
with that configuration preserved and the new .env token. The frontend process
ID/creation time stayed unchanged. The backends now run in the background.

Read-only checks pass: /ready 200, protected GET jobs 200 with auth and 401 without,
frontend 200. Status confirms database/auth/job API ready, worker available,
approved demo repository, offline mode and both live flags false. Docker runner
preflight passed with the preserved image/configuration. The jobs list was empty;
no job submission or target execution occurred during this preparation. The token
was checked absent from service logs and safe receipts. Evidence:
baseline/phase11-manual-browser-readiness.json.

Open root .env privately in the editor and copy only the value after AUTH_TOKEN=.
Refresh the dashboard or click Check API, paste into Operator token, click Connect,
leave main and click Create repair job once. Do not click Start another job for
this acceptance. Confirm the reproduced pagination failure (expected [10, 20],
actual [10]), successful original/full-suite/independent verification (1/2/9
passes), and exactly one SIMULATED OFFLINE DRAFT with no GitHub link. No token
needs to appear in chat or screenshots.

At the time of preparation, **browser acceptance was PENDING USER CONFIRMATION**.
The successful manual job recorded above now supersedes that pending state. The earlier
Computer Use blocker below remains historical; this is preparation for a user-run
manual browser check. The user has now supplied that observed result. Live
Gemini/GitHub remain unverified. The frontend was left running for the check.

## Historical Phase 11 implementation - automated browser blocker (manual acceptance above)

2026-11-05. Inspected Phase 10 worker/state/budget/source/evidence interfaces,
existing authenticated FastAPI routes and the actual React/Vite scaffold before
editing. ANTIGRAVITY_MASTER_PROMPT.md, WEBGUARD_AI_PHASE_PROMPTS.md and product Git
metadata remain absent; this user's explicit Phase 11 scope is authoritative.
Unrelated changes, private configuration and the bundled defect were preserved.
All target tests ran inside Docker. No live Gemini or GitHub call was made.

### Implemented behavior

React now shows approved repository/provider mode/worker heartbeat availability,
runtime local operator connection, creation/retry, recent jobs, current state/stage,
attempts/limits, failure comparison/excerpt, exact verification checks/commands,
cancellation and publication. It uses real API data; mocks exist only in tests.
The local AUTH_TOKEN is entered in a labelled password field and held only in
memory, cleared on disconnect/page close. Provider credentials are not UI inputs
or VITE variables. No credential is written to local/session storage, URLs or
application logs. API client destinations are fixed loopback HTTP origins on port
8000, redirects/cookies are disabled and requests have 10-second timeout/abort.
Raw server/network errors are replaced with safe messages.

Submission is restricted to the server's configured approved repository and a
validated Git ref. A synchronous in-flight lock prevents duplicate clicks. The
random per-logical-request idempotency key and payload stay frozen on uncertain
retry; a successful submission disables creation until Start another job is
explicitly chosen. The nonsecret key is shown for recovery; pending client state
is in memory only, so reload clears it. Reconnect/check durable jobs before a new
logical submission if acceptance was uncertain. SQLite remains the durable dedup
authority. Worker unavailability permits durable queueing with a clear explanation.

Recent-job listing adds optional order=asc|desc (default asc preserved) and stable
cursor ordering; UI requests desc, ten per page, up to 50 cached jobs. Active work
uses non-overlapping polling with bounded 1/2/4/8/10-second backoff and abortable
requests. Terminal selected jobs stop individual polling even while other jobs
remain active; all polling stops with no active loaded jobs or on page close/
disconnect/unmount. Refresh explicitly checks later terminal cleanup/reconciliation.
Version checks prevent stale job/report regressions; a terminal evidence snapshot
older than the terminal job is fetched again. Ordered cursor events are deduped,
bounded to two 50-item pages per refresh and 200 received events in the view.

Native forms/buttons, associated labels, visible focus, skip link, captioned
verification tables and polite state announcements support keyboard/screen-reader
operation structurally. Loading, API/auth failures, no worker, no_reproducible_bug,
failed verification, paused blockers and cancellation have separate explanations.
Repository/log strings render as escaped text, with no HTML/eval or arbitrary
links. Simulated drafts are explicit and never link to GitHub. Only a backend
validated exact live PR URL can become an anchor after a second client check.
Manual browser/visual/keyboard/screen-reader acceptance is NOT claimed below.

### Necessary backend read model

The existing API had safe state/events but not the bounded evidence/publication
data needed for the requested dashboard. New authenticated GET /api/jobs/{id}/report
is read-only: snapshot stage/dispatch/cleanup, two detection observations and
expected/actual plus at most 2,048 traceback characters, up to ten verification
rounds/four checks, and safe publication metadata. It reads matching hashed owned
receipts and committed SQL verification summaries, never executes a target or
calls repair/publication. Missing/tampered excerpts are unavailable. Full raw
logs/source, credentials, controller paths/leases/fences and idempotency hashes
are excluded. Response models/field bounds/redaction/auth/CORS/query limits apply.

Status now exposes the nonsecret approved repository. A live_url requires the
completed matching intent/publication/current verification proof, correct SHA/
patch/digest, exact approved owner/repository, positive PR number and identical
stored https://github.com/owner/repository/pull/NUMBER. Simulated, stale,
incomplete, credential-bearing or mismatched URLs cannot link. The API does not
expose arbitrary receipt paths or introduce execution/mutation routes. Existing
default pagination, idempotency, worker, budgets and target security are preserved.
No new migration, dependency version or lockfile change was needed. The frontend
package adds only a typecheck script; existing hash/npm locks were reused.

### Changed files

| Files | Change |
| --- | --- |
| frontend/src/App.tsx, Dashboard.tsx, JobDetail.tsx, style.css | Operator connection, approved target/mode/worker display, submission/retry/history/evidence/cancel UI, responsive layout and semantic controls |
| frontend/src/api.ts, format.ts | Typed validated loopback API client, bounded timeout/abort and safe errors, exact live link guard and formatting |
| frontend/src/App.test.tsx, api.test.ts, test-data.ts | Mocked auth/privacy, duplicate/uncertain submission, polling/close/terminal/cancel/error/evidence/XSS/link tests |
| frontend/package.json | Explicit typecheck script; dependencies and package lock unchanged |
| backend/app/api_models.py, main.py, http_security.py, jobs.py | Approved repository status, report shapes/route, optional bounded descending cursor listing and query allowlist |
| backend/app/reports.py, backend/tests/test_reports.py | Read-only safe hashed-evidence projection, proof/URL checks and temporary-DB security/pagination coverage |
| runner_image/check_dashboard_api.py | Actual TCP API/worker/Vite plus six Docker observations, CORS/auth/report/dedup/cleanup; explicitly not a browser gate |
| docs/DASHBOARD.md, SETUP.md, STATUS.md, PHASE_PROGRESS.md, API.md, ARCHITECTURE.md, SECURITY.md, WORKER.md, IMPLEMENTATION_PLAN.md, DELIVERY_VALIDATION.md, README.md | Current startup/contracts/results and outstanding browser gate |
| docs/baseline/phase11-* | Preserved actual mock/product/build/HTTP/Docker results, browser blocker, hashes and shutdown proof |

### Exact checks and results (kept separate)

Commands run from root with installed Python 3.12.10 and existing workspace Node
22.16.0/npm 10.9.2. For npm, PATH was prepended with .tools/node-v22.16.0-win-x64,
and .tools/node-v22.16.0-win-x64/npm.cmd invoked with --prefix frontend. No runtime
download, clean install, security/Application Control change or bypass occurred.

| Command / tool | Actual result | docs/baseline evidence |
| --- | --- | --- |
| npm --prefix frontend test | Initial 25 mocked tests pass; final **26 passed**, 2 files, 4.74s | phase11-frontend-first.log, phase11-frontend-final.log |
| npm --prefix frontend run typecheck | Exit 0, explicit tsc --noEmit; final code | phase11-types-final.log |
| npm --prefix frontend run build | Exit 0; tsc/Vite 6.4.5, 33 modules, 1.44s; final JS 248.43 kB | phase11-build-final.log |
| .venv\Scripts\python.exe -m pytest backend/tests/test_reports.py backend/tests/test_api.py -q | Initial 110 passed, one existing warning, 24.69s | phase11-backend-first.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | Initial 603 passed, 24 deselected, one warning, 200.12s | phase11-product-first.log |
| Same full product command after final demo-URL rejection case | **Exit 0; 604 passed, 24 isolation cases deselected, one warning, 216.57s** | phase11-product-final.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 0, full Python tree clean | phase11-lint-final.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase11-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; current 46-package lock; UV_CACHE_DIR=.tools/uv-cache | phase11-lock-check.log |
| .venv\Scripts\python.exe runner_image/check_dashboard_api.py | Initial and final exit 0; real TCP API, worker and Vite start; HTTP/CORS/auth/report/dedup plus real Docker pass; browser=not_run | phase11-api-stack-first.log, phase11-api-stack-final.log, phase11-api-stack.json |
| Computer Use browser discovery, then native Chrome selection | **Browser acceptance BLOCKED**, no browser submission or screenshot/visual verification | phase11-browser.json |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both prior fixture hashes unchanged | phase11-demo-hashes.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; zero managed containers/volumes | phase11-cleanup.json |
| Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | No listeners after owned acceptance stack stopped | phase11-stack-shutdown.json |

The existing Starlette/httpx deprecation warning remains unsuppressed. PowerShell
uv stderr is formatted NativeCommandError despite native exit 0; exit/result was
checked. No failing runtime/test check was hidden. First 25 frontend tests passed;
the final 26 include the explicit finished-selected-job/other-active-job polling
case. The final production build and typecheck ran after that change. Product
test deselection is not counted as real isolation/browser acceptance. Older
standalone Phase 5/8/9/10 gates are history, not claimed fresh reruns.

### Actual TCP / Docker proof (not browser proof)

The helper started actual Uvicorn on 127.0.0.1:8000, the actual worker CLI and Vite
on 127.0.0.1:5173 with strict ports. Dedicated non-production SQLite/owned roots
were under .tools. Its random local operator token existed only in a private
ignored settings file/in-memory HTTP headers, was never printed/persisted in
receipts or frontend env, and the private settings file was removed at shutdown.
Child environments were explicitly limited; model/publication live flags were false.

Vite frontend index served HTTP 200; explicit Origin/CORS preflight passed; API
submission returned 202; protected report returned 200 with auth and 401 without.
Duplicate same-key/payload submission returned the same job. The worker acquired
the pin, reproduced, generated/validated the predefined source patch, verified
and recorded exactly one simulated draft. It drained/exited 0 on actual CLI stop;
only the helper's owned API/Vite processes were then stopped. This test did not
execute React in a browser and did not submit through browser controls.

Final job: **ac4f8c73ad394ed0bed6537c7bbc76f9**. Pinned deterministic commit:
**2de13361c14264f24c29cb2f778192c9f65858d0**. Original failing test:
tests/test_pagination.py::test_first_page_contains_requested_count, expected
**[10, 20]**, actual **[10]**, in two fresh baseline containers. The invalid-input
test remained passing. Patched original: **1 pass**; original full suite: **2
passes**; independent checks: **9 passes**. Unpatched control: **3 fails/6 passes**.
Six unique actual container IDs, same source SHA/image, cleanup true; effective
settings are exported in phase11-api-stack.json (non-root, no network/host binds,
read-only root/input and configured resource limits). No target ran on the host.

Image: sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
Patch: 518e82eb4b19cce91d43f87c3618575de2f7cfc303b3879e6778f61a95460171.
Simulated commit: e10bbe94c8c87b248b64fc1797e237f6fe372303. One fake draft, one
claim/repair/model/publication attempt, 90 reserved execution seconds, zero model
cost. No real GitHub branch/commit/PR was created. Compact proof: phase11-summary.json.
Bundled source/test hashes remain 434d71f92fb9c64ab345bbc91b3a3fc6b06013d17d48d051d3afbf502ca8a87e
and 552ab0838dde5161e8ad9b39aad67f0b1c22411a60ad221cd2fc00185989f153.

### Browser blocker and Phase 12 readiness

Applied the computer-use skill at
C:/Users/nitis/.codex/plugins/cache/openai-bundled/computer-use/26.1027.30824/skills/computer-use/SKILL.md
and read its required guidance/confirmation/API documents. Initial browser
inventory reported **"The browser access host is unavailable"**. The native Chrome
selection then returned:

> Computer Use has been stopped for this turn because it could not determine
> the current browser URL on Windows with enough confidence to enforce policy.

This is a tool-enforced browser stop. No further browser/computer inputs or UI
workaround were attempted. Independent repository, test, CLI/HTTP and documentation
work continued. No browser demo submission, actual keyboard/screen-reader test,
screenshot/layout QA or browser polling check is claimed. Mocked DOM tests and
real HTTP/Docker success do not replace that required exit gate.

Exact manual startup commands and remaining browser checklist are in DASHBOARD.md
and SETUP.md. The implementation and non-browser checks are ready, but **Phase 11
browser acceptance and formal Phase 12 readiness remain BLOCKED/conditional** on
approved browser access or a recorded manual browser run. No current Docker/API/
build blocker. Live Gemini/GitHub/download remain NOT VERIFIED; no live credential
was added or tested. All acceptance-stack processes were stopped; no preview was
left running with the disposable test auth configuration.

## Phase 10 - automatic background pipeline accepted with real Docker

2026-11-05. Inspected Phase 2 storage/state/lease/budgets and Phase 4-9 source,
Docker, detection, repair, validation, verification and publication code/results
before editing. The master/phase prompt files and product Git metadata remain
absent; the user's Phase 10 scope controls this work. No existing failures were
assumed passed. Unrelated changes, private credentials, frontend and the bundled
intentional defect were preserved. All target execution stayed inside Docker.

### Implemented and verified behavior

worker.pipeline.run_job now connects the existing guarded services. Worker.serve
polls SQLite; claim is atomic across separate connections/processes. HTTP handlers
still only persist/read jobs. Startup is `.venv\Scripts\python.exe -m worker`
from root using the same private settings/database/workspace/image as the API.
Startup prints a random worker_id and actual configured provider modes. Shutdown
is Ctrl+C or `.venv\Scripts\python.exe -m worker --stop WORKER_ID`; replace the ID
with the startup value. Shutdown drains the current bounded job, then prints
stopped:true/exits. A stop request explicitly says stopped_confirmed:false. The
actual CLI startup and stop were executed by the acceptance test, both exit 0.
Full API/worker/image commands, submission and cancellation flow: WORKER.md/SETUP.md.

Migration 7 adds job_dispatch (stage, durable defer/pause timing, bounded terminal
reconciliation reservations, cleanup tracking) and worker_sessions (heartbeats,
stale threshold, drain/stop state and repository identity). A dedicated thread
renews job leases every lease_seconds/3 during controller operations. Existing
services still fence each state/evidence/publication write. Repair/verification
no longer use stale pre-work optimistic versions for stage transitions: lease
ownership and atomic state/evidence checks remain, so legitimate heartbeat version
increments cannot spuriously reject a long-running stage. Competing workers get
one claim; expired owners cannot advance or publish. Worker availability status
uses unexpired non-draining session heartbeats, not Docker/provider readiness.

Pipeline: Docker preflight -> approved pinned source -> two fresh same-assertion
baseline observations -> configured provider/strict patch validation -> Phase 8
four-stage exact verification -> Phase 9 dedicated branch/draft publication.
Default providers remain offline_fake/simulated. A stable deterministic Git copy
of three fixed bundled files is initialized per worker without running target
code/hooks/templates/signing/instructions. Fixed Git identity/date preserve its
SHA across restarts; the bundled fixture is unchanged. No arbitrary local path or
command was added to the API. Configured approved remote sources reuse Phase 4.

Restart keeps state, pin, attempts, deadline and usage. Incomplete baseline work
is rerun cleanly; incomplete provider output is not a committed candidate; committed
candidates are revalidated. Verification never trusts a partial round, and all
new reservations/rounds use remaining persistent limits. No refund/reset occurs.
Publication retries keep verified proof and reconcile branch/tree/PR before effects,
including accepted request timeouts and expired-owner restart. Publication-only
recovery can proceed without Docker; it does not rerun repair/tests.

Transient publication errors persist a next-run time and release/fence atomically.
Known infrastructure/evidence/policy/unknown-publication blockers pause instead
of hot-looping claims. Fix setup then use `--resume JOB_ID`; that clears dispatch
pause only, never attempts/deadlines/budgets. Paused jobs still expire. Missing
Docker blocks target execution and cannot trigger a host fallback. API details
and ordered redacted events persist progress/retry/simulation information.

Cancellation stops active containers through the existing callback and prevents
further owned writes. Cancelled/deadline-failed jobs with an uncertain intent get
at most three spaced, transactionally reserved read-only remote lookups. Actual
observed draft IDs/URLs and simulated flags are retained in the intent/events
without reviving the job or creating another PR. Lookup failure records
outcome_unknown. External writes already accepted cannot be undone by cancellation.
The Phase 9 remote-base race limitation and operator-review requirement remain.

Recovery cleans only verified owned Docker resources and attempt generations,
protecting other workers' active leases. Filesystem ownership checks/cleanup are
serialized against new claims in SQLite. Current candidates remain for retry;
terminal attempts/partial acquisitions are removed. Sealed baseline and hashed
receipts/SQLite evidence remain for audit. Stopped/stale demo fixture owners are
reclaimed only without active leases; unregistered initialization has a 60-second
grace period. No broad prune, unrelated deletion or security-control bypass.

### Changed files

| Files | Change |
| --- | --- |
| worker/pipeline.py, __main__.py | Real pipeline, polling, heartbeat/lease fencing, retries/restart, maintenance, drain/resume/once CLI and static safe errors |
| worker/demo_fixture.py | Owned deterministic Git copy; fixed trusted file list, sanitized Git commands, safe close and orphan ownership metadata |
| backend/app/database.py, jobs.py | Migration 7; claim eligibility, stop checks, dispatch/defer, sessions/availability and bounded terminal publication observations |
| backend/app/settings.py, .env.example | Validated worker polling/retry settings |
| backend/app/main.py, api_models.py | Accurate worker heartbeat availability, dispatch/session readiness and safe progress/cleanup/reconciliation events |
| worker/repair.py, verification.py | Lease/state/evidence-protected transitions compatible with independent heartbeat version increments |
| worker/publication.py | Read-only cancelled/failed reconciliation; persist actual accepted drafts or unknown outcome without changing terminal states |
| worker/source_service.py, execution.py | Accurate worker-integration docstrings; execution/acquisition policy unchanged |
| worker/tests/test_pipeline.py | Replaces obsolete stub assertion with lifecycle/restart/concurrency/expiry/budget/cancellation/cleanup/tamper tests |
| worker/tests/test_pipeline_docker.py, runner_image/check_pipeline.py | Actual CLI subprocess + authenticated API + real Docker demo; real API cancellation; strict two-case non-skipped gate |
| backend/tests/test_api.py, test_jobs.py | Worker status/drain, migration-6 upgrade and new readiness tables |
| docs/WORKER.md, SETUP.md, PHASE_PROGRESS.md, STATUS.md, API.md, ARCHITECTURE.md, SECURITY.md, PUBLICATION.md, IMPLEMENTATION_PLAN.md, DELIVERY_VALIDATION.md, README.md | Startup/shutdown, current boundaries/results, recovery limits and remaining UI/live work |
| docs/baseline/phase10-* | Preserved first failures, actual successful commands, automatic proof and cleanup/hashes |

No package/dependency version or lockfile changed: Phase 10 uses only the existing
locked Python dependencies/stdlib. Offline uv lock check and pip check pass. No
new clean dependency install or frontend check is claimed.

### Exact commands and results

Controller Python remains installed 3.12.10, invoked directly without activation
or another runtime download. Docker Engine/image/profile are unchanged. Real gates
use DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine, WEBGUARD_ISOLATION_IMAGE
from phase8-image.json, WEBGUARD_RECORD_ACCEPTANCE=1. Docker transports retain their
private empty auth/proxy config. Worker subprocess environment is explicitly
limited to OS/runtime/Docker endpoint values; private settings file supplies only
its own test configuration. No credentials/environment dump or live service call.

| Command | Actual result | docs/baseline log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest worker/tests/test_pipeline.py backend/tests/test_api.py backend/tests/test_jobs.py -q | Initial 2 failed, 262 passed; both test setup/exception mistakes, corrected | phase10-unit-first.log |
| .venv\Scripts\python.exe -m pytest worker/tests/test_pipeline.py -q | Second run 10 passed, 21.74s | phase10-unit-second.log |
| Expanded worker/backend command above | 1 failed, 272 passed; deadline-after-acceptance reported stale_owner before expiry; fixed terminal handling/reconciliation | phase10-unit-expanded.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | **Exit 0; 594 passed, 24 isolation cases deselected, 1 existing warning; 139.49s** | phase10-product-first.log |
| .venv\Scripts\python.exe runner_image/check_pipeline.py | Initial real gate exit 0; 2 passed, zero skips, 1 existing warning; 36.00s | phase10-real-first.log |
| Same strict real gate after final recovery changes | **Exit 0; 2 passed, zero skips, 1 existing warning; 35.49s** | phase10-real-final.log |
| .venv\Scripts\python.exe -m worker --env-file <private test file> | Actual child process automatically processed the API-submitted job; stopped/exit 0 after drain | phase10-automatic-demo.json |
| .venv\Scripts\python.exe -m worker --env-file <same file> --stop e7f94e96c1874c58905fd6f7ac0bd772 | Actual stop command exit 0; drain requested, then worker confirmed stopped/exited | phase10-automatic-demo.json |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 0; full project clean, including touched former pipeline test I001 | phase10-lint-final.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase10-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 46 packages current; UV_CACHE_DIR=.tools/uv-cache | phase10-lock-check.log |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both prior hashes unchanged | phase10-demo-hashes.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; zero managed containers/volumes | phase10-cleanup.json |

The existing Starlette/httpx deprecation warning remains, not suppressed. The old
worker/tests/test_pipeline.py import-order finding disappeared because that stub
test was necessarily replaced in this phase. Initial new-file lint found import
ordering, a nested-if simplification and an explicit check=False requirement; all
fixed. Logs: phase10-lint-first.log, phase10-lint-fixes.log, phase10-lint-second.log.
PowerShell uv stderr is rendered as NativeCommandError despite native exit 0.

Initial two unit failures were a restart test constructing distinct manager
instances (correctly rejected by shared-service identity checks), and expecting
Conflict instead of NotFound for an unknown job. Those fixtures/assertions were
fixed, not the guards. The later deadline test exposed real pipeline reporting:
publication returned stale_owner while a just-expired job still said publishing
until the next poll. The worker now enforces expiry before reporting/cleanup and
reconciles the accepted draft while preserving failed/deadline_exceeded. All
expanded cases passed within the final complete 594-test run. No failed check is
claimed accepted and no mock lifecycle case is counted as real target execution.

### Actual automatic demo and cancellation

An authenticated ASGI TestClient POST /api/jobs returned 202/queued; an independent
actual Python CLI worker subprocess, sharing only the configured SQLite/owned
root, picked up the job. This tests the real API handlers/auth/storage, not a
separately launched TCP Uvicorn server. No handler called the worker synchronously.
The real worker ran source acquisition, two Docker baseline suites, fake provider,
patch validation, four fresh Docker verification checks and simulated publication.
API duplicate submission returned the same ID and still exactly one fake draft.

Pinned deterministic demo commit: **2de13361c14264f24c29cb2f778192c9f65858d0**.
Original failing node: tests/test_pagination.py::test_first_page_contains_requested_count;
expected **[10, 20]**, actual **[10]**, reproduced twice; invalid-input passed twice.
Correct fake patch changes only pagination.py's slice endpoint. Patched original:
**1 pass**, full original suite: **2 passes**, independent checks: **9 passes**;
unpatched regression control: **3 fails/6 passes**. All six observations have distinct
container IDs, same pinned SHA/image and successful cleanup.

Image: sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
Patch: 518e82eb4b19cce91d43f87c3618575de2f7cfc303b3879e6778f61a95460171.
Job: 3786b90624d045e9b1159cfe0bfd3575. Simulated draft **#1**, branch
webguard/jobs/3786b90624d045e9b1159cfe0bfd3575, simulated commit
8747180c8fbd78abeeffdaf8708c3446dd1b4b5b. No real GitHub PR was created.
One repair/model call, one publication mutation attempt and 90 reserved execution
seconds, zero model cost, one job claim. A 4-second lease was renewed through the
whole process; no optimistic-version conflict or budget reset. Full receipt:
phase10-automatic-demo.json. Worker CLI drain completed with exit 0.

The second real case used only a temporary Git fixture with an infinite-loop
function, observed an actually running test container, cancelled via authenticated
API, and confirmed cancelled state, container stop, empty attempts and no draft.
Receipt: phase10-cancellation.json. The bundled demo source/test hashes remain
434d71f92fb9c64ab345bbc91b3a3fc6b06013d17d48d051d3afbf502ca8a87e and
552ab0838dde5161e8ad9b39aad67f0b1c22411a60ad221cd2fc00185989f153.

### Blockers and Phase 11 readiness

No current offline/Docker blocker. Phase 10 automatic offline acceptance is
complete; Phase 11 can integrate a job UI and broaden delivery acceptance.
Frontend is unchanged/status-only with a disabled create button. Live Gemini,
live GitHub source download and live publication remain **NOT VERIFIED**; no
credential/live call was added or tested. They require the existing explicit
model/key/auth settings, exact approved repository and scoped installation token
as documented in REPAIR.md/PUBLICATION.md. Older standalone isolation/Phase 8/9
gates were not rerun this phase; unchanged image/policy evidence remains historical.
No arbitrary hostile-repository support or external draft rollback is claimed.

## Phase 9 - verified draft publisher implemented; offline Docker demo accepted

2026-11-05. Inspected Phase 8 receipts, verification/candidate gates, source/attempt
interfaces, state transitions, lease/budget services and prior results before
editing. ANTIGRAVITY_MASTER_PROMPT.md, WEBGUARD_AI_PHASE_PROMPTS.md, AGENTS.md and
product Git metadata remain absent from this archive; this user's explicit scope
is authoritative. The previous Phase 8 verification receipt SHA256 still matches
its recorded digest (phase9-prior-evidence.json). Historical exported JSON is not
imported as a trusted job: the new demonstration creates real fresh pinned
reproduction/proposal/verification records and publishes against that storage.
No bundled fixture, unrelated code, credentials or frontend were changed.

### Implemented behavior and security

PublicationService is an explicit fenced controller service. It requires a
current uncancelled verified job, complete exact-patch Phase 8 aggregate,
matching SHA/candidate/round/image/profile/patch and hashed evidence receipts.
It reconstructs only the validated source changes in a clean owned attempt,
checks its inventory/digest, collects the edited bytes and cleans the attempt.
It never runs target tests on the host or repeats verification during publishing.

Default offline mode uses a separate persistent fake GitHub SQLite remote with
unique branch and job marker. The demo records one simulated draft PR, retries
after reopening both stores and still has exactly one. `simulated: true`, offline
mode, SIMULATED title/body and simulated:// URL prevent a fake from claiming a
real GitHub publication. Protected API publication events retain the simulation
label while excluding private bodies/raw responses. No execution HTTP route or
automatic worker was enabled; status still reports storage-only processing.

The live adapter requires explicit ENABLE_GITHUB_DRAFT_PR, private server auth
and a single-repository GitHub App installation token for the exact configured
owner/repository. It checks token repository scope and immutable remote repo ID
before effects. Broad installation/classic tokens, wrong repositories, redirects,
ambient proxies, compressed/oversized/paginated responses and exceeded time/call
limits fail closed. Token headers stay server-side; raw errors never enter job
records. Updated generic redaction covers the stateless ghs_ token format too.
No real live publication or credential was used/tested.

The GitHub Git database API creates a tree with only verified source replacements,
one baseline-parent commit and a dedicated webguard/jobs/<job-id> ref; the complete
remote tree/modes/marker/parent are verified. No checkout, hooks, force push,
test/config changes, merge or target installation is performed. PR creation is
always draft:true. The bounded escaped/redacted body includes the bug, fix,
baseline, patch/evidence digests and commands/exits/counts actually observed.

Migration 6 adds durable immutable publication_intents bound to job/verification
records. Before remote effects it persists branch_inflight/pr_inflight. Retry
looks up and validates the existing branch/commit/PR by job marker and exact
identity, including accepted-request timeouts and local transaction rollback.
Invisible uncertain outcomes block blind reposting. Closed/non-draft/foreign
collisions are not replaced. Mutation retries use the existing persistent
publication attempt budget; read-only reconciliation of accepted work can finish
after that budget is exhausted. Failures retain verified proof and return to
verified without repeating model/repair/tests. Cancellation/fencing guard writes,
including a cancellation during a remote timeout.

Remote base SHA is checked before branch/PR effects and final completion. Any
observed move latches base_moved; create a new pinned job and reverify instead of
reusing that intent. GitHub has no atomic expected-base-SHA PR precondition: a
late move or cancellation can leave an already accepted external draft. Observed
PR IDs are retained on the late-base path; local completion is blocked and the
operator must review the external draft. No automatic merge/rollback is claimed.

### Changed files

| Files | Purpose |
| --- | --- |
| worker/github_publishers.py | Durable deterministic fake and bounded opt-in live REST adapter; exact tree/commit/ref/draft reconciliation |
| worker/publication.py | Verified receipt/source gates, clean patch reconstruction, fenced intent/effect/retry workflow, safe draft description |
| backend/app/database.py, jobs.py | Migration 6, durable intent/observed metadata, atomic draft completion, stronger state gates, evidence-preserving retries |
| backend/app/settings.py, .env.example | Validated publication limits, private scoped token setup and stateless-token redaction |
| backend/app/main.py, api_models.py | Intent-table readiness, safe simulated publication events and accurate storage-only status message |
| worker/tests/test_publication.py, test_github_publisher.py | Offline success/failure/timeout/cancellation/rollback/budget and mocked live REST/transport tests |
| worker/tests/test_publication_docker.py, runner_image/check_publication.py | Real two-run Docker reproduction/four-stage verification followed by exactly one durable simulated draft; strict non-skipped gate |
| backend/tests/test_jobs.py, test_settings.py, test_api.py | Migration-5 upgrade, exact draft gate, token/limit checks, readiness and simulation event projection |
| pyproject.toml, uv.lock, requirements-dev.lock | httpx promoted to explicit runtime dependency; locks regenerated without changing package versions |
| docs/PUBLICATION.md, PHASE_PROGRESS.md, STATUS.md, SETUP.md, SECURITY.md, ARCHITECTURE.md, API.md, IMPLEMENTATION_PLAN.md, DELIVERY_VALIDATION.md, README.md | Setup/contracts, acceptance evidence, remaining live/integration work |
| docs/baseline/phase9-* | Preserved actual logs, original failures, demo proof/summary, hashes and cleanup evidence |

### Commands and actual results

All commands run from root with installed controller Python 3.12.10. No activation,
runtime download, execution policy or Application Control bypass. Target code
executes only in the unchanged prepared v4 image. For Docker gates the only
task-specific variables are DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine,
WEBGUARD_ISOLATION_IMAGE from phase8-image.json and WEBGUARD_RECORD_ACCEPTANCE=1.
Docker uses an empty private auth/proxy config. No environment/credentials dump.

| Command | Actual result | docs/baseline log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest worker/tests/test_publication.py backend/tests/test_jobs.py -q | Initial 1 failed, 167 passed; assertion expected unescaped Markdown node text; corrected the test to match escaped PR body | phase9-unit-first.log |
| .venv\Scripts\python.exe -m pytest worker/tests/test_github_publisher.py -q | Initial 8 passed; mocked HTTP only | phase9-http-first.log |
| .venv\Scripts\python.exe -m pytest worker/tests/test_publication.py worker/tests/test_github_publisher.py -q | Expanded initial 24 passed, 53.02s; later cases included in final product run | phase9-unit-expanded.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | First complete run: 568 passed, 22 deselected, one existing Starlette/httpx warning; 268.65s | phase9-product-first.log |
| Same complete product command after final migration/settings/event/cancellation/budget cases | Exit 0; **576 passed**, 22 isolation cases deselected, one existing warning; **250.63s** | phase9-product-final.log |
| .venv\Scripts\python.exe runner_image/check_publication.py | First run failed before reproduction with infrastructure cleanup_failed; no acceptance/publication claimed | phase9-real-first.log |
| Same strict Docker gate | Second run exit 0; 1 passed, zero skips; 47.43s | phase9-real-second.log |
| Same strict Docker gate after final changes | Exit 0; 1 passed, zero skips; 58.57s; exactly one simulated draft | phase9-real-final.log |
| uv lock --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 46 packages resolved, existing versions retained | phase9-lock.log |
| uv export --locked --extra dev --extra bootstrap --no-emit-project --format requirements-txt --output-file requirements-dev.lock | Exit 0; hash-locked requirements regenerated | phase9-lock-export.log |
| .venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . | Exit 0; editable runtime metadata refreshed; no new dependency download/install or clean environment claimed | phase9-editable-install.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase9-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 46-package lock current; UV_CACHE_DIR=.tools/uv-cache | phase9-lock-check.log |
| .venv\Scripts\python.exe -m ruff check (all changed Python paths listed above) | Exit 0 | phase9-lint-final.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 1; only pre-existing worker/tests/test_pipeline.py I001, left untouched | phase9-lint-all.log |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both unchanged | phase9-demo-hashes.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; final zero managed containers/volumes | phase9-cleanup.json |

Final expanded product command/result is recorded in phase9-product-final.log.
PowerShell wraps native uv/pip stderr in NativeCommandError text despite their
native exit 0; exit codes/results above are checked explicitly. Initial scoped
lint found one unused import and a startswith tuple simplification; both fixed,
retained in phase9-lint-first.log. The existing full-project lint issue and warning
were not suppressed. Frontend and older standalone Phase 5/8 gates were not
rerun; Phase 9 independently runs the same real reproduction/verification pipeline.
The prior clean hash-locked installs remain Phase 7/1 evidence, not a new Phase 9
clean-install claim. httpx remains 0.28.1; no dependency version changed.

### First Docker failure and cleanup

The first run's receipt reported runner_failure/infrastructure_error,
cleanup_failed, no container ID, no target output or exit code, and cleanup false.
It failed before confirmed baseline execution; it was not classified as a bug or
used as publication evidence. An uncertain Docker operation retained one labelled
source volume. Subsequent fresh-job gate passed; finalizers now invoke the actual
access manager's recovery even on assertions, rather than only the fixture's
separate manager. The first temporary root was later pruned by pytest, so reopening
that absent path created a different owner and recovered nothing (phase9-recovery.log).

Final inspection found precisely that old owner/run/job-labelled source volume.
After checking its exact name, labels, driver and options with the existing
check_volume policy, the controller removed only that named volume. Logs:
phase9-cleanup-before.json, phase9-orphan-cleanup.log. Final phase9-cleanup.json
confirms zero managed containers/volumes. No broad Docker prune or unrelated
filesystem deletion was used. Temporary-root receipt inspection initially hit
Windows sandbox Access is denied; the approved read succeeded. No current Docker
execution blocker remains; the earlier infrastructure failure remains in history.

### Actual demo evidence and readiness

Final temporary Git baseline: d0f9db3ea3033dcc85f6c19725fc340bd06c9135.
Original test: tests/test_pagination.py::test_first_page_contains_requested_count;
expected [10, 20], actual [10], reproduced in two fresh containers before repair.
Deterministic fake repair removes only the extra `- 1` from pagination.py's slice.
Patched original: 1 pass; full original suite: 2 passes; independent checks: 9
passes. Unpatched independent control: 3 fails/6 passes. Image remains
sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
Patch digest: 593fc44b83e8f2218793d7d6b525c0f08e75760bc7c85f5662af916c3e435f69.
Verification receipt digest: 2a2c019c93f556a7d25b0c0c12b0ef937535d6e8e41b296b577de3d8e0018aa9.

Fake branch: webguard/jobs/5331bf3be3514e0abbe7e67a1ce93758.
Fake commit: 0f5d9ab761381631761f8be0605e4a23bf5708b7. Fake draft PR number 1,
mode offline, simulated true, including after reopen/retry. No GitHub PR exists
from this test. Counters remain one repair/model call, one publication mutation
attempt and 90 reserved execution seconds; publication retry does not consume
model/test budgets. Full evidence: phase9-offline-demo.json and phase9-summary.json.
Bundled source SHA256 remains 434d71f92fb9c64ab345bbc91b3a3fc6b06013d17d48d051d3afbf502ca8a87e;
original tests remain 552ab0838dde5161e8ad9b39aad67f0b1c22411a60ad221cd2fc00185989f153.

Phase 9 offline acceptance is complete; Phase 10 integration can use the explicit
publisher and durable simulation-aware events. Automatic worker/job UI remains
planned. Live acceptance is NOT VERIFIED and needs the approved GitHub repository,
single-repository installation token/permissions and explicit private server opt-in.
No live Gemini, live repository download or live GitHub publication is claimed.
See PUBLICATION.md for setup, retry and late-base/cancellation limits.

## Phase 8 - exact pagination patch VERIFIED with real Docker execution

2026-11-05. Read the current Phase 5 runner, Phase 6 baseline/receipt, Phase 7
validated proposal and storage/state/budget interfaces before editing. The master
and phase prompt files remain absent; this user's Phase 8 scope is authoritative.
Unrelated changes and the bundled demo defect were preserved. No target code ran
on the host, no live Gemini call occurred and GitHub publication remains Phase 9.

### Implemented behavior

Explicit VerificationService requires a current proposed candidate, reproduced
pinned SHA and matching hashed detection/candidate receipts. It reopens/verifies
the sealed baseline, revalidates only approved source edits/anchors/size limits,
and checks the proposed copy's full inventory/digest. Unexpected original test or
source changes, missing/tampered receipts, profile/image mismatch and incomplete
evidence block verification. The model cannot supply a command, selector, new test
or verification policy.

Every check/round starts a new owned copy of the exact commit. Only validated edits
are reapplied; the final diff/inventory must match the candidate patch digest.
Original tests remain byte-identical; no container/attempt artifacts cross copies.
Verification uses the Phase 5 runner controls and the exact baseline image/dependencies.
Four fresh-container observations are mandatory:

1. Unpatched independent regression witness: all 9 checks run; exactly the 3 new
   full-page/page-size-one assertions fail and the 6 healthy cases pass.
2. Patched original Phase 6 failing test: exactly that node passes.
3. Full original patched suite: exact baseline node set, every required phase/test
   passes (2 tests for the demo).
4. Patched independent checks: all 9 pass (full/partial pages, size one, beyond end,
   empty input, negative page, zero/negative page size).

Skipped/missing/extra nodes, missing phases, collection errors, truncated/incomplete
reports, altered commands, wrong SHA/profile/source/image/patch, reused run/container
IDs or failed cleanup cannot verify. The discriminating new tests fail baseline
and pass patched; healthy checks are not falsely claimed to fail on the baseline.
Runner results include actual structured commands, exit codes, durations, identities
and bounded redacted reports/logs. Execution receipts now always combine active job
and runner secret redactors, including when a caller constructs a default runner.

Migration 5 adds durable verification_rounds. Counts persist across restarts and
candidates, capped by the existing job max_repair_attempts; no new unbounded retry
budget. Each retry starts all checks from new baseline copies. Execution reservations
and job deadlines remain authoritative; the remaining execution allowance is divided
across remaining required checks. Missing Docker at initial preflight is explicitly
blocked without round/time debit; mid-round blockers retain partial evidence and
can resume inside remaining limits. Timeout/OOM/output/environment/runner failures
are not proof of repair. Cancellation/deadlines fail incomplete running rounds and
fence late owners; stale owners cannot record passing evidence. Rollback tests prove
aggregate writes cannot partially verify a candidate.

Only a complete same-image aggregate transaction inserts passing verification
evidence and marks the job verified. Raw/legacy exit-zero records no longer satisfy
verified/publication gates. Candidate proposal records remain immutable; candidates()
projects verified only from a matching committed round/evidence bound to its exact
SHA/patch. Other candidates remain proposed. No automatic worker/API execution or
GitHub adapter was enabled. Publication remains distinct from verification.

### Trusted v4 runtime and compatibility

Profile v4 preserves the original full-suite command. New service-owned selectors
run the exact original node or immutable image regression module using the same
trusted command prefix and a `--` path boundary. Manifest selectors are validated
both by the controller and image bootstrap. The 9 independent tests live under
/opt/webguard/regressions, never in the repo test tree or model patch. Their report
IDs use _webguard_regression; host product testpaths exclude runner_image.

This required a new profile/image identity. v3 jobs/evidence are preserved and are
not relabelled or mixed with the new image. The real demonstration created fresh
v4 Phase 6 reproduction and a Phase 7 deterministic fake proposal, then verified
using the same v4 image throughout. Python/dependency preparation is unchanged:
official Python 3.12.16 base
sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30,
the same six uv-locked pytest wheels, offline image RUN steps and no target install.

Accepted image: sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
Profile digest: 736ae723cec1f7e50af418808dc35a41776a3aa5e12e4d2fce6df79638d63557.
Receipt: baseline/phase8-image.json. Build actually ran with --pull=false and
--network=none using a new allowlisted .tools/runner-context-phase8 directory.
The existing InvalidDefaultArgInFrom build warning remains because PYTHON_BASE
has no default; the actual supplied argument was the immutable base above.
No new dependency/lock versions or host install were needed/claimed.

### Changed files and reasons

| Files | Change |
| --- | --- |
| worker/verification.py | Evidence/diff checks, fresh-copy four-stage verification, persistent retries, receipt and exact verified handoff |
| worker/check_policy.py | Trusted suite/original/regression selectors and fixed required regression IDs |
| runner_image/test_pagination_regression.py | 9 independent service-owned checks; executed only in Docker |
| runner_image/entrypoint.py, webguard_report.py, Dockerfile, prepare.py | Validated selectors, image test paths/reporter, strict build-context assets |
| worker/workspaces.py, runner_models.py, docker_runner.py | Profile v4, control/selected requests, actual command metadata, no-patch baseline regression control |
| worker/execution.py | Bounded verification-control execution, no standalone control proof, authoritative job+runner redaction |
| worker/detection.py, repair.py | Persist baseline test IDs; guarded evidence reuse during explicit verification only |
| backend/app/database.py, jobs.py | Migration 5, round/coverage/identity gates, exact verified candidate projection, cancellation/deadline interruption |
| backend/tests/test_jobs.py, worker/tests/test_detection.py, test_runner.py, test_image_preparation.py | Accurate state-proof fixtures, legacy-proof rejection, protocol and secret-redaction coverage |
| worker/tests/test_verification.py, test_verification_docker.py | Failure/skip/tamper/retry/budget/fencing/rollback cases and real positive/negative acceptance |
| runner_image/check_verification.py | Three required non-skipped real acceptance cases; unavailable Docker exits 2 |
| docs/VERIFICATION.md, PHASE_PROGRESS.md, STATUS.md and setup/security/architecture/runner/plan/README | Current contracts, profile compatibility and Phase 9 handoff |

### Actual commands/results and preserved baseline logs

Commands ran from root with existing installed controller Python 3.12.10. For real
gates: local DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine, immutable
WEBGUARD_ISOLATION_IMAGE from phase8-image.json and WEBGUARD_RECORD_ACCEPTANCE=1.
Docker CLI uses a private empty auth/proxy config; no credentials/other environment
values were printed or passed to targets. Logs below are in docs/baseline/.

| Command | Actual result | Log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest backend/tests/test_jobs.py worker/tests/test_runner.py worker/tests/test_image_preparation.py -q | Exit 0; 225 passed | phase8-prerequisites-first.log |
| .venv\Scripts\python.exe -m pytest worker/tests/test_verification.py -q | Exit 0; initial 19 cases passed (coverage later expanded) | phase8-unit-first.log |
| .venv\Scripts\python.exe runner_image/prepare.py --wheels .tools/runner-wheels --output .tools/runner-context-phase8 --base python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 | Exit 0; new trusted context/profile digest | phase8-image.json and build context |
| docker build --pull=false --network=none --build-arg PYTHON_BASE=<pinned base above> --build-arg PROFILE_DIGEST=<v4 digest above> --tag webguard-runner:phase8 .tools/runner-context-phase8 | Exit 0; built immutable v4 image | phase8-image-build.log |
| .venv\Scripts\python.exe runner_image/check_isolation.py | Exit 0; 16 passed, zero skips, 78.15s | phase8-isolation-gate.log |
| .venv\Scripts\python.exe runner_image/check_verification.py | Exit 0; 3 passed, zero skips, 67.85s | phase8-real-final.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | Exit 0; 544 passed, 21 deselected, 1 existing Starlette/httpx warning; 133.90s | phase8-product-complete.log |
| .venv\Scripts\python.exe -m ruff check worker/check_policy.py worker/verification.py worker/docker_runner.py worker/runner_models.py worker/execution.py worker/repair.py worker/detection.py worker/workspaces.py backend/app/database.py backend/app/jobs.py backend/tests/test_jobs.py worker/tests/test_detection.py worker/tests/test_verification.py worker/tests/test_verification_docker.py worker/tests/test_image_preparation.py worker/tests/test_runner.py runner_image | Exit 0; changed code clean | phase8-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 1; untouched worker/tests/test_pipeline.py I001 only | phase8-lint-all.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase8-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; current 46-package lock | phase8-lock-check.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; zero remaining managed resources | phase8-cleanup.json |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both fixture hashes unchanged | phase8-demo-hashes.log |

UV_CACHE_DIR was .tools/uv-cache for the offline lock check; PowerShell represents
uv stderr as NativeCommandError despite native exit 0. Frontend files were untouched
and not rerun. No existing warning/lint issue was suppressed. Real isolation/verification
ran separately from product tests; deselection is not counted as real acceptance.
Phase 6/7 real reproduction/proposal were exercised inside the Phase 8 scenarios;
their older standalone gate logs are history, not falsely claimed fresh reruns.

Initial full product run had 11 failures/527 passes because a cancellation-only
assertion was accidentally placed in the parameterized non-cancellation negative
test. It expected cancelled where the correct rejection reason was tests_failed,
missing_or_skipped or incomplete_evidence. The assertion was moved to the proper
cancellation case, not relaxed or hidden. Later 543 tests passed; final 544 includes
the additional job-secret receipt regression. Logs: phase8-product-first.log,
phase8-product-final.log, phase8-product-complete.log. Initial real gate already
passed all 3 cases (61.05s); final rerun passed after final safeguards.

One overlapping attempt to redirect a second product run to phase8-product-final.log
was refused by Windows: "The process cannot access the file ... because it is being
used by another process" (Out-File FileOpenFailure). That second command did not
run pytest and is not counted as a pass. After the first process completed, the
final command used phase8-product-complete.log with ErrorActionPreference=Stop.
No execution policy/Application Control changes or bypass were used.

### Actual verified repair and negative controls

Final successful commit: **3649a943b1a062c2cf05767a8437fa11b2f91013**.
Original failure: tests/test_pagination.py::test_first_page_contains_requested_count,
expected **[10, 20]**, actual **[10]**, reproduced twice before proposal.
The deterministic offline provider removes only the extra `- 1` in the slice
endpoint of an owned pagination.py copy. Original tests and bundled source remain
unchanged. Patched original test: **1 passed**; full original suite: **2 passed**;
independent regression checks: **9 passed**. Unpatched control: **3 failed, 6 passed**,
proving the new full-page/page-size-one checks discriminate the original defect.
Check exit codes are respectively **1, 0, 0, 0**, with four distinct containers,
same pinned SHA and immutable image throughout.

Candidate: 1c17113904f247acb84d047d1f3cc57b, effective status **verified**, job **verified**.
Exact patch digest: f501acd9c5b835d4741266d0d99f5240cf1f51a36796bc83959946a493138bd5.
Verification ID: ac9aea07c7b14de2bd6192cd6e7eda00.
Aggregate receipt SHA256: 0ff2caad332320af54c4c3d5e9bcb514709a41d8762ba29bb3f3f55719244b8e.
The receipt bytes were checked against that digest. Compact summary:
phase8-summary.json; full proof: phase8-real-valid.json and
phase8-verification-receipt.json (commands, per-test reports, exit codes, duration,
redacted logs and identities). Independent tests are service-owned image assets;
none were added to or edited in the bundled test tree.

Negative candidates used the same real services/constraints with a one-round test
budget: a docstring-only patch leaves the original bug and fails the original node;
an overfitted source patch fixes valid pagination but disables invalid-argument
handling, so the previously passing original test breaks in the full suite.
Both were rejected, jobs failed and candidates remained proposed. Proof:
phase8-real-bug_remains.json and phase8-real-previously_passing_breaks.json. Passing
those acceptance cases means rejection worked, not that the bad patches passed.

All owned Docker containers/volumes were removed. Fixture SHA256 values still are
434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E and
552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153.
No dependency lock changes/new host install, live Gemini call, host target execution
or GitHub publication occurred. No current real-verification blocker exists on
this accepted Docker setup. **Phase 9 publication is ready to implement against
the exact verified proof; no PR exists or is claimed.** Future publication must
preserve candidate/verified identity and the existing opt-in/auth/repository controls.
See VERIFICATION.md for complete retry, compatibility and trust limitations.

## Phase 7 - repair proposals implemented; offline accepted, live NOT VERIFIED

2026-11-05. Read the actual repository, current Phase 4/5/6 services and saved real
reproduction evidence before editing. ANTIGRAVITY_MASTER_PROMPT.md and
WEBGUARD_AI_PHASE_PROMPTS.md remain absent; the user's Phase 7 scope is authoritative.
Existing unrelated changes and the bundled intentional defect were preserved.

The previous Phase 6 receipt/hash, same pinned commit, matching assertion signatures
and two distinct Docker containers were checked first. A new real reproduction
also preceded the Phase 7 acceptance provider request. No model request is allowed
from an exported JSON file or single failing exit code alone.

### Implemented behavior and boundaries

RepairService is an explicit controller operation using approved RepositoryAccess,
fenced jobs, a sealed source snapshot and the matching hashed Phase 6 receipt. It
requires reproduced state (or a matching repairing resume), pinned SHA/profile,
two matching assertion observations and successful runner cleanup. It sends only
relevant redacted allowlisted source snippets plus failing-test diagnostic,
comparison and signature; source/log/model text is untrusted data, not instructions.

Offline is the default: deterministic fake proposes the demo slice endpoint change.
The official Google Gen AI SDK adapter is implemented and locked at 2.34.0. Live
requires explicit enable_live_gemini plus model/key/local operator auth. It uses
JSON-schema generation, no tools/automatic function calling, trust_env=false,
millisecond HTTP timeout and SDK attempts=1 (no hidden retries). Both modes use a
trusted killable child with combined byte/wall caps and lease/cancellation polling.
API key passes only through stdin memory, never argv/target environment/logs/disk.
No actual Gemini call occurred; live service/model behavior is NOT VERIFIED.

Before every original/retry call, persist call/token/live-cost reservations. No
refund or restart reset. Controller retries only timeout/unavailable errors,
bounded by retry count and job snapshot budgets. Input includes schema/instruction
bytes; output JSON and generation tokens are bounded. Invalid/malformed responses
never become commands or persisted raw error text. Offline attempts reserve
call/token accounting but no provider cost. Cost allowance is operator accounting,
not a claim about provider pricing.

Structured output requires diagnosis and edits {path, old_text, new_text}. Reject
extra/duplicate JSON fields, Markdown wrappers, blank diagnosis, coercion, oversize
or invalid Unicode. Edits require exact approved .py paths and unique anchors in
both relevant context and pinned original. Reject traversal/absolute/ambiguous
paths, tests, symlinks/junctions/hardlinks, secrets, dependencies/config/workflows,
new/deleted/renamed files, duplicate file edits, no-ops, invalid Python syntax,
credential-bearing replacements and persisted patch file/line limit violations.
Syntax/AST parsing never executes target expressions. Diff work is bounded to
edit text. Validate all edits before applying to a clean independent attempt.

Only approved files may differ after inventory recheck. The patch digest matches
the runner's canonical baseline-manifest/final-file inventory. Failure cleans only
the verified service-owned attempt/receipt; unrelated copies/files survive.
Migration 4 adds transactional fenced repair_candidates with unique job/repair
attempt, SHA/source/profile/detection identity, attempt/patch/artifact digests,
provider, redacted diagnosis, changed files and status=proposed. Resume returns
the same durable candidate without a fresh provider call. State stays repairing;
no candidate was verified and no post-patch target test ran. Phase 8 must perform
independent isolated verification. API handlers and worker.run_job remain unchanged.

### Changed files

| Files | Purpose |
| --- | --- |
| worker/repair.py | Reproduction-gated prompt, persistent usage, bounded retry orchestration, candidate receipts |
| worker/repair_models.py | Strict structured proposal/edits, fixed untrusted-data instruction, safe error codes |
| worker/repair_providers.py, model_call.py | Deterministic offline provider and official SDK adapter in killable controller child |
| worker/patches.py | Source-only path/anchor/syntax/size validation, clean-copy application and runner-compatible digest |
| worker/workspaces.py | Ownership/identity-checked individual attempt cleanup |
| backend/app/database.py, jobs.py | Migration 4, reproduced-proof lookup, durable proposed candidates and rejection events |
| backend/app/settings.py, .env.example | Validated per-call input/output/token/time/retry/cost limits; existing live flags remain off |
| pyproject.toml, uv.lock, requirements-dev.lock | Official SDK compatible constraint and complete reproducible dependency pins/hashes |
| worker/tests/test_repair.py, test_repair_docker.py | Offline validator/provider/budget/fs tests and real reproduction -> fake proposal acceptance |
| runner_image/check_repair.py | Strict gate; Docker skips are exit 2, not acceptance |
| docs/REPAIR.md, PHASE_PROGRESS.md, STATUS.md, SETUP.md, ARCHITECTURE.md, SECURITY.md, IMPLEMENTATION_PLAN.md, README.md | Contracts, actual results, live limits and Phase 8 handoff |

### Dependency installation and checks actually run

Existing Python 3.12.10 was used directly; no Python download or Application
Control bypass. uv kept existing dependency versions and added google-genai 2.34.0
plus 12 compatible dependencies. Lock resolves 46 packages; Windows installs 45
distributions including project/bootstrap packages due platform markers. Google
interfaces were checked in official docs and installed SDK source; SDK contract
test uses a fake client and real SDK config types, no external credentials.

The following commands ran from root. UV_CACHE_DIR was .tools/uv-cache for uv.
Logs/artifacts below are under docs/baseline/.

| Command | Actual result | Log |
| --- | --- | --- |
| uv lock --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 46 locked packages | phase7-lock.log |
| uv export --locked --extra dev --extra bootstrap --no-emit-project --format requirements-txt --output-file requirements-dev.lock | Exit 0; hashes exported | phase7-lock-export.log |
| .venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock | Exit 0; SDK and new dependencies installed locally | phase7-install.log |
| py -3.12 -m venv .tools/phase7-repro-venv | Exit 0; fresh venv using installed runtime | phase7-clean-install.log records subsequent install |
| .tools\phase7-repro-venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock | Exit 0; clean hash-locked install completed | phase7-clean-install.log |
| .tools\phase7-repro-venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . | Exit 0; project installed with pinned build backend | phase7-clean-project-install.log |
| .venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . | Exit 0; development metadata refreshed | phase7-project-install.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase7-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; lock current | phase7-lock-check.log |
| .venv\Scripts\python.exe -m pytest worker/tests/test_repair.py -q | Exit 0; first 35 offline cases passed | phase7-unit-first.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | Exit 0; 519 passed, 18 deselected, 1 existing warning; 87.02s | phase7-product-final.log |
| .venv\Scripts\python.exe runner_image/check_repair.py | Exit 0; 1 passed, zero skips; 16.29s; offline provider, live_verified=false, phase8_verification=not_run | phase7-real-gate.log |
| .venv\Scripts\python.exe -m ruff check worker/repair.py worker/patches.py worker/repair_models.py worker/repair_providers.py worker/model_call.py worker/tests/test_repair.py worker/tests/test_repair_docker.py backend/app/jobs.py backend/app/settings.py backend/app/database.py worker/workspaces.py runner_image/check_repair.py | Exit 0; changed code clean | phase7-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 1; unchanged worker/tests/test_pipeline.py I001 only | phase7-lint-all.log |

Both environments reported Python 3.12.10. Installed versions were compared using
importlib.metadata, normalized/sorted by distribution name: all 45 match exactly.
Proof: phase7-installed-main.json, phase7-installed-clean.json and
phase7-reproducibility.json. This is an actual clean install, not a lock-only claim.
Initial unused/import-order lint findings in new files were corrected and remain
in phase7-lint-first.log. Intermediate whole product runs passed 516 and 518 before
coverage expanded to 519. No product test failure was suppressed. One existing
Starlette/httpx warning remains. PowerShell wraps uv stderr as NativeCommandError
while the native command exits 0. Frontend was untouched/not rerun in this phase.
Prior Phase 5/6 real gates remain recorded; the 18 deselected cases were not all
rerun here. The new Phase 7 gate separately ran actual Docker reproduction, with
no skips; mocks are not counted as real reproduction or live generation.

### Actual proposed candidate, blockers and Phase 8 readiness

The saved Phase 6 proof was valid. The new real acceptance used a new temporary
Git commit **64ece02f2dd9abfbd10ba83ec832c8758c65b751**, real approved-fixture
acquisition and two fresh hardened containers on the accepted v3 image. Both
failed the same page-size assertion, expected [10, 20]/actual [10], while invalid
input passed. Signature matched prior real evidence. Only then did the offline
fake propose removing the extra `- 1` from the pagination slice in a fresh copy.

Candidate: 6cb344cc02fc49c6abc6c9cae97485b5, status **proposed**, job **repairing**.
Patch digest: 9b39166c1b954920778710658f8252100f59c1cabb296a3102be937acd52ab47.
Receipt digest: d3f3f3f3378df3418b462beb13d7914202ecf2b883dfd21a4eef482dffa5f834.
Receipt bytes were checked against that digest. Durable metadata and retained
receipt: phase7-real-proposal.json and phase7-proposal-receipt.json. verified=false;
Phase 8 verification explicitly not_run. Candidate bytes were packaged/hashed,
not executed. The strict gate may be rerun with:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/docker-resume-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_repair.py
```

The existing Linux image/profile/wheel recipe was unchanged. All target execution
was in Docker; product-owned provider echo/sleep/output helpers ran on the host
only to test trusted-controller transport. No target imports, target tests,
repository instructions or install scripts ran on the host. Owned containers and
volumes remaining: zero (phase7-cleanup.json). Bundled source/test SHA256 values
are unchanged (phase7-demo-hashes.log):
434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E and
552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153.

No current offline/Docker implementation blocker. **Live Gemini is NOT VERIFIED**
and needs explicit server opt-in/model/key/auth; no provider credentials were
required for tests. No Gemini call, verified repair or PR was made. Phase 8 is
ready to implement independent clean isolated verification of the exact candidate,
including SHA/digest/test integrity, before advancing to verified. Automatic
worker orchestration/publication remain unimplemented; job acceptance is storage
only. See REPAIR.md for full contracts and accounting/trust limitations.

## Docker resume - real Phase 5 and Phase 6 acceptance PASSED

2026-11-05. This supersedes the earlier Docker-blocked results below. The current
code/docs and Phase 4/5 interfaces were inspected before execution. Docker Desktop
is now running: CLI/Engine 29.9.2, API 1.56, Linux/amd64, cgroups v2, seccomp builtin,
CPU/memory/swap/PID support true, no engine warnings. Public approved-source reads,
model repair, publication and automatic worker orchestration are still outside
this acceptance run.

### Immutable prepared image and setup actually used

- Official Python base pulled: python:3.12-slim at
  sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30.
  Actual image Python is 3.12.16. The installed controller remains Python 3.12.10.
- The existing six wheels were rechecked by prepare.py against uv.lock. No
  dependency constraints/locks changed. No target dependency install occurred on
  the host. Trusted image RUN steps used --network=none and pip --no-index,
  --require-hashes, --no-deps and binary-only wheels; no target source entered
  the build context. This image build/install actually ran; no new host clean
  install is claimed.
- Final accepted runner image:
  sha256:b6fe81369bc8681f9f6dcc29e3f282d466c1d1599b64d65beaf4d27e93eccfdc.
  Profile v3 digest:
  6e12d025c65102a18d30cea121202b4bca1ad3fab6dd075fa903fe72c0dc4319.
  User 10001:10001, Linux/amd64, trusted image entrypoint.
- Engine/base/image receipts: baseline/docker-resume-engine.json,
  docker-resume-base.json, docker-resume-image.json. Exact wheel/asset hashes and
  base/profile/image identity: docker-resume-build-inputs.json. The first image
  receipt is retained separately as docker-resume-image-first.json.

Docker client commands used a workspace-local empty auth/proxy config at
.tools/docker-acceptance-config, not the user's credentials/config/context.
The product DockerCLI separately creates its own empty config. The local endpoint
was explicitly npipe:////./pipe/dockerDesktopLinuxEngine. Only command-process
environment values were set; private .env credentials were untouched.

These preparation commands actually ran (PowerShell, from root):

```powershell
$env:DOCKER_CONFIG = Join-Path (Get-Location) '.tools\docker-acceptance-config'
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$dockerTask = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
& $dockerTask pull --platform linux/amd64 python:3.12-slim
$runnerBase = 'python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30'
$runnerProfile = .venv\Scripts\python.exe runner_image/prepare.py --wheels .tools/runner-wheels --output .tools/runner-context-live-fixed --base $runnerBase
& $dockerTask build --pull=false --network=none --build-arg "PYTHON_BASE=$runnerBase" --build-arg "PROFILE_DIGEST=$runnerProfile" --tag webguard-runner:prepared .tools/runner-context-live-fixed
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/docker-resume-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
```

The first build used .tools/runner-context-live; the final fixed build used the
new directory shown above. The tag was only used during preparation/inspection;
all tests ran the recorded immutable sha256 image ID, with no runtime pull.

### First real failure, correction and retest

Initial real Phase 5 gate: **15 passed, 1 failed**, zero skips, exit 1 (74.45s).
The scratch-exhaustion target did hit ENOSPC within 32 MiB, but the image-owned
pytest reporter then tried to write its JSON file in that full /scratch tmpfs.
It failed with OSError [Errno 28] No space left on device; bootstrap exit 125 was
correctly classified infrastructure_error/unexpected_exit, not a code bug. Its
containers/volume were still cleaned. The focused diagnostic rerun failed once
with the same cause. Logs and that structured result are retained.

Correction: runner_image/webguard_report.py and entrypoint.py now use
/tmp/webguard-test-report.json on the existing separately bounded /tmp tmpfs.
No CPU/memory/PID/scratch/output/network/privilege limits were relaxed and the
scratch test did not remove its fill file to hide the condition. The target
profile command/digest and bundled fixture were unchanged; the image was rebuilt
and identified separately. All 16 real cases then passed on that final image.

Acceptance-only changes: worker/tests/test_docker_isolation.py can export bounded
redacted RunResult receipts when the explicit controller flag
WEBGUARD_RECORD_ACCEPTANCE=1 is set; test_detection_docker.py similarly preserves
the detector receipt and summary. Output paths are service-owned constants, not
API/repository inputs, and the flag is not passed into target containers.
Setup/status/security/architecture/source/plan/reproduction/runner docs now reflect
actual acceptance. No production API behavior or worker.run_job enablement changed.

One Windows helper attempt was blocked: `. .tools/resume-docker.ps1` returned
PSSecurityException/UnauthorizedAccess, "cannot be loaded because running scripts
is disabled on this system." The same authorized work was completed with direct
commands supported by the current tool session. No execution-policy flags,
Application Control changes or bypass were used. Both image builds exited 0 and
reported InvalidDefaultArgInFrom because the Dockerfile intentionally has no
default PYTHON_BASE; the actual supplied build argument was the pinned base above.
That warning is retained, not represented as an acceptance failure or hidden.

### Actual final commands/results

Logs/artifacts below are under docs/baseline/. The current shell had the explicit
local DOCKER_HOST and immutable WEBGUARD_ISOLATION_IMAGE above. Audit flag 1 was
used for the real gates. Product tests ran separately and never import/execute
target tests on the host.

| Command | Exact result | Log |
| --- | --- | --- |
| docker version / docker info with selected safe fields | CLI/Engine 29.9.2, Linux/cgroups v2; required support true, no warnings | docker-resume-engine.json |
| docker pull --platform linux/amd64 python:3.12-slim | Exit 0; pinned digest above | docker-resume-base-pull.log |
| docker build --pull=false --network=none ... .tools/runner-context-live-fixed | Exit 0; offline wheel install and image build completed | docker-resume-build-final.log |
| .venv\Scripts\python.exe runner_image/check_isolation.py | Exit 0; 16 passed, zero skipped, 75.94s | docker-resume-isolation-final.log |
| .venv\Scripts\python.exe runner_image/check_reproduction.py | Exit 0; 1 passed, zero skipped, 9.22s | docker-resume-reproduction.log |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | Exit 0; 478 passed, 17 deselected, 1 existing Starlette/httpx warning, 50.36s | docker-resume-product.log |
| .venv\Scripts\python.exe -m ruff check runner_image/entrypoint.py runner_image/webguard_report.py worker/tests/test_docker_isolation.py worker/tests/test_detection_docker.py | Exit 0; all changed code clean | docker-resume-lint.log |
| docker container ls --all --filter label=io.webguard.managed=webguard.runner-v1; docker volume ls --filter label=io.webguard.managed=webguard.runner-v1 | Both exit 0; zero remaining managed containers/volumes | docker-resume-cleanup.json |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Source/test before and after hashes match | docker-resume-demo-before.log, docker-resume-demo-after.log |

All 17 real cases ran separately from the 478 product tests; deselection in the
product command is not a skip or unrun acceptance claim. The real Phase 5 cases
verified passing/failing pytest, UID/capabilities/no-new-privileges/seccomp, network
denial, read-only root/input, unavailable host paths/credentials/socket, infinite
loop/time watchdog, bounded oversized output, active cancellation, kernel OOM,
effective cgroup CPU/memory/swap/PID limits, scratch exhaustion, owned orphan
recovery, trusted pytest configuration, deliberate demo failure and independent
image watchdog. Per-run results/effective settings/logs are preserved in
docker-acceptance-runs.jsonl (includes the initial failed diagnostic receipt).
Final-image receipts are summarized in docker-resume-isolation-outcomes.json.
The orphan case exercises resource recovery without running a target test.

Effective acceptance resources: 1 CPU, 128 MiB memory with 0 additional swap,
64 PIDs, 32 MiB /scratch, 8 MiB /tmp, 1 MiB shared memory, user 10001:10001,
no network/capabilities/host binds/devices/privileged mode, read-only root and input,
no-new-privileges, default seccomp, bounded output/wall time, log driver none.
The real target read the cgroup files/tmpfs sizes to verify enforcement, not only
requested flags. Service defaults remain separately documented in ISOLATED_RUNNER.md.

### Real pagination proof and Phase 7 handoff

The real Phase 4 fixture adapter acquired a temporary Git copy of the unchanged
demo. Both fresh attempts ran commit **999039a6964017db59aa94faede6aa9ddc96c13d**
using the final immutable image above and identical input/profile digests.

- Failing test: tests/test_pagination.py::test_first_page_contains_requested_count.
- Expected **[10, 20]**, actual **[10]**, both runs. This expected/actual mapping
  is grounded in the literal right-hand expectation in the test assertion.
- Same failure signature:
  90fb25a0cd2a65631746f95f3325bf179bcee758237e13e6d3ee76ab4b73867a.
- First container: d153d75a9855bc0b819d788f06ffc24a55de4473ba11fd80cec635df5c771f70;
  exit 1, total runner duration 3.625s.
- Second container: c87ac86a785044abedde14a591b1b449adfcba0f1b4ee588828c9bf622839c29;
  exit 1, duration 3.359s. Different run/container IDs, clean independent copies.
- tests/test_pagination.py::test_invalid_page_rejected passed in both containers.
  Each configured target suite had 1 deliberate failure and 1 pass.
- Durable test job state: reproduced. Summary: docker-demo-summary.json.
  Full bounded redacted receipt/command/tracebacks/snippets: docker-demo-evidence.json.
  Its SHA256 was verified against recorded evidence digest
  3c18f08f8a3ddcd72e48a6c738241790d3700f4fd48b90d217cd403540616fc0.
- Both source/test hashes still match the earlier fixture baseline:
  434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E and
  552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153.

**No remaining Docker acceptance blocker for Phases 5/6 on this recorded setup.**
Phase 7 implementation can now proceed using real reproduction evidence. No
Gemini, patch application, fixture repair or PR publication occurred. Automatic
worker orchestration and repair remain unimplemented; HTTP acceptance is storage
only. The earlier unrelated full-lint I001 and Starlette/httpx warning remain
documented. No frontend checks or new lock/install verification are claimed in
this resume. Recheck real gates after image/profile/platform changes. Containers
still support approved known repositories, not arbitrary hostile public code.

## Phase 6 - reproducible detection implemented; real execution BLOCKED

2026-11-05 (client date). The actual Phase 4 adapters/workspaces, Phase 5 Docker
runner/execution service, durable job/evidence/state services and prior results
were read before editing. ANTIGRAVITY_MASTER_PROMPT.md and
WEBGUARD_AI_PHASE_PROMPTS.md remain absent; the current user scope supplied the
Phase 6 requirements and supersedes the older proposal-adapter roadmap row.
No applicable AGENTS.md or product .git metadata was found. This project contains
the real backend/worker interfaces, not only an audit frontend.

Implemented behavior:

- Explicit DetectionService uses the approved pinned commit and only Docker-backed
  ExecutionService. An assertion candidate causes one full configured suite rerun
  on a fresh attempt/container/storage. Reproduced requires matching test IDs,
  phase outcomes and signatures, same SHA/image/profile/input identity, distinct
  runs/attempts and successful cleanup. Different observations are flaky/inconclusive.
- Missing dependencies, collection/setup/teardown/non-assertion errors, timeout,
  OOM, output limits, cancellation and runner failures remain separate. Complete
  green suites with executed tests record no_reproducible_bug, never bug-free.
  Entirely skipped/unexecuted or incomplete reports are inconclusive. Initial
  Docker/image blockers retain baselining without execution-budget debit.
- Profile v3 loads an image-owned pytest reporter: relative test IDs, phase
  outcomes, assertion type, message and traceback, bounded to 32 KiB total/256
  phase records/4 KiB trace/1 KiB message. The bootstrap emits a final JSON frame;
  runner validation/redaction precedes persistence. Missing, ambiguous, malformed,
  oversized or mismatched reports never confirm a bug. Logs/source stay inert data.
- Failure signatures hash original bounded diagnostics before redaction, so
  different secrets do not collapse into a false match. Receipts preserve SHA,
  command, failures, comparisons, tracebacks, logs, exit codes, durations and image
  identity. Expected/actual roles are populated only when a matching literal
  right-hand assertion expectation is available. AST/literal parsing never
  executes expressions. Relevant-only snippets are bounded/redacted and stop
  before the next unrelated function definition.
- Source tar members are sorted explicitly so the transferred-input digest is
  reproducible across fresh copies regardless of filesystem enumeration order.
  A reversed-inventory unit check proves identical transfer bytes.
- record_detection validates referenced same-SHA isolated proofs, fresh identities
  and matching signatures transactionally. Only a latest validated detection
  record gates reproduced/no_reproducible_bug. Legacy exit-only baseline evidence
  is preserved but insufficient. SQLite stays schema 3: the existing generic
  evidence table supports detection records; old jobs are not rewritten.
- Persistent budgets/deadlines, cancellation, lease renewal and fencing remain
  enforced. Cancellation/lost ownership cannot publish a reproduction conclusion.
  No Gemini, patches, PRs, HTTP execution or automatic worker loop was added;
  processing_enabled/repair_enabled remain false.

Changed files and reasons:

| Files | Change |
| --- | --- |
| worker/detection.py | Explicit two-run controller, limited relevant snippets, durable receipts and state updates |
| worker/test_reports.py | Strict report validation, verdicts, pre-redaction signatures, comparison observations |
| worker/docker_runner.py, runner_models.py | Bounded parsed test_report; deterministic source transfer alongside existing limits/cleanup |
| worker/execution.py | Optional record_evidence=False for detector-owned proof; default behavior preserved |
| worker/workspaces.py | v3 trusted profile explicitly loads the image reporter |
| runner_image/webguard_report.py, entrypoint.py, Dockerfile, prepare.py | Bounded reporter, bootstrap frame, trusted image and allowlisted build context |
| backend/app/jobs.py | Validated detection evidence and stronger central reproduced/no-bug gate |
| worker/tests/test_detection.py, test_detection_docker.py, test_runner.py, test_image_preparation.py | Fake classification/controller/reporting checks and separate real Docker demo acceptance |
| backend/tests/test_jobs.py | Matching-proof state fixtures; upgrade test now rejects legacy exit-only reproduction |
| runner_image/check_reproduction.py | Real-demo acceptance gate: skipped returns 2, not success |
| docs/REPRODUCTION.md and setup/status/architecture/source/plan/progress/README | Contracts, real blocker, profile migration and Phase 7 dependency |

Profile v3 changes immutable identity: prepare a new image and new job/source
snapshot. v1/v2 metadata is preserved, not relabelled. No application/development/
build dependency or lock changed, no fresh install/runtime download or Application
Control bypass occurred. Existing Python 3.12.10 was used directly. No credentials
or unrelated environment values were printed.

### Actual commands and preserved evidence

Run from root; logs are under docs/baseline/. Product testpaths exclude demo tests;
real Docker acceptance cases skip before target execution when Docker is absent.

| Command | Actual result | Log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest worker/tests/test_detection.py backend/tests/test_jobs.py worker/tests/test_image_preparation.py -q | Exit 0; 199 passed (initial targeted implementation) | phase6-unit-first.log |
| .venv\Scripts\python.exe -m pytest -q -r s | Exit 0; 478 passed, 17 skipped, 1 existing warning; 56.43s | phase6-product-final.log |
| .venv\Scripts\python.exe runner_image/check_reproduction.py | Exit 2; reproduction_acceptance=blocked; 1 skipped, 0 failures, pytest_exit=0 | phase6-reproduction-gate.log |
| .venv\Scripts\python.exe runner_image/check_isolation.py | Exit 2; isolation_acceptance=blocked; 16 skipped, 0 failures, pytest_exit=0 | phase6-isolation-gate.log |
| .venv\Scripts\python.exe -m ruff check worker/detection.py worker/test_reports.py worker/runner_models.py worker/docker_runner.py worker/execution.py worker/workspaces.py runner_image backend/app/jobs.py worker/tests/test_detection.py worker/tests/test_detection_docker.py worker/tests/test_image_preparation.py worker/tests/test_runner.py backend/tests/test_jobs.py | Exit 0; changed code clean | phase6-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | Exit 1; untouched worker/tests/test_pipeline.py I001 only | phase6-lint-all.log |
| .venv\Scripts\python.exe -m pip check | Exit 0; no broken requirements | phase6-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | Exit 0; 33 packages, lock current | phase6-lock-check.log |
| Get-Command docker -ErrorAction SilentlyContinue; Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' | docker_available=False; standard path False | phase6-tools.log |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both unchanged | phase6-demo-hashes.log |

UV_CACHE_DIR was .tools/uv-cache for the offline lock check. PowerShell formats uv
stderr as NativeCommandError despite native exit 0. The existing Starlette/httpx
warning and unrelated lint issue remain unsuppressed. Initial lint findings in
touched code (fixture aliases, min/sorted choice, __all__ ordering) were corrected;
phase6-lint-first.log preserves the final ordering finding before correction.
Earlier whole suites passed 464, 474, 475 and 477 tests as coverage expanded. Final
results apply to final code. Frontend files were untouched and checks were not
rerun in Phase 6; their last actual test/build pass is recorded in Phase 5.

### What the demo actually proved and Phase 7 readiness

The real acceptance case makes a temporary ordinary Git commit of the bundled
demo, acquires it through Phase 4 and invokes the real runner twice. It requires
the same pinned SHA/page-size assertion signature and invalid-input passing on
both runs, then checks bundled files are unchanged. Here it skipped before
execution: `ISOLATION ACCEPTANCE BLOCKED: Docker CLI unavailable; no host fallback`.
Therefore neither repeated real page-size failure nor real invalid-input pass was
proved in Phase 6. Data fakes test decisions; real temporary Git fixtures test
pinning/acquisition only. Neither counts as executed target-code reproduction.

No image was built, no runtime image identity was obtained and no target test ran
on the host. The intentional defect remains unchanged. Source/test hashes are
434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E and
552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153.

Required setup: supported Linux Docker/cgroups controls, reviewed immutable Python
3.12 base, new v3 prepared image using locked wheels, actual immutable image ID in
RUNNER_IMAGE_ID/WEBGUARD_ISOLATION_IMAGE, then exit 0 from both
runner_image/check_isolation.py and runner_image/check_reproduction.py.
See ISOLATED_RUNNER.md and REPRODUCTION.md. This supports approved known
repositories, not attestation against arbitrary hostile code.

Phase 6 independent implementation is complete; real reproduction acceptance
remains BLOCKED. Phase 7 has usable evidence/interfaces but is not execution-ready
until both real Docker gates pass. Mock execution is never counted as real proof.

## Phase 5 — Docker-only runner implemented; isolation acceptance BLOCKED

Current evidence, 2026-11-04, supersedes earlier phase status counts below. The
actual backend, worker, tests and Phase 4 interfaces were inspected before editing.
ANTIGRAVITY_MASTER_PROMPT.md, WEBGUARD_AI_PHASE_PROMPTS.md and AGENTS.md were not
present in this archive. The user's Phase 5 scope supplied the requirements.
This is the backend/source-service project, not only the website-audit frontend.
No product Git metadata is available for diff/status; unrelated files were preserved.

Implemented: structured Docker-only runner/results; validated runner settings;
immutable local image/profile checks; Linux cgroups/seccomp preflight; checked
effective non-root/networkless/read-only/capability/resource policy; tar transfer
through owned Docker storage, never host bind mounts; bounded/redacted concurrent
output; target wall watchdog plus controller timeout; OOM/environment/infra/code
failure separation; cancellation; exact ownership cleanup and age/lease-aware
orphan recovery. An ambiguous daemon operation retains its labelled source volume
and reports cleanup failure for later safe recovery. No broad prune is used.

ExecutionService explicitly joins fenced Phase 2 services and Phase 4 snapshots,
reserves persistent execution budgets, renews leases, polls durable cancellation
and writes immutable receipts outside transferred source. Only valid completed
pytest outcomes with successful cleanup may produce evidence. No API handler,
worker polling loop, automatic state transition, repair or publication was enabled.
Initial missing Docker/image does not consume execution budget. Trusted controller
helpers and test runtime remain separate; containers support approved known
repositories, not arbitrary hostile public code.

Scaffold changes and reasons:

- worker/docker_client.py, docker_policy.py, docker_runner.py, runner_models.py:
  transport, fail-closed policy, lifecycle and structured evidence-bearing results.
- worker/execution.py: explicit lease/budget/cancellation/evidence integration;
  worker/pipeline.py stays disabled.
- runner_image/: trusted Dockerfile/bootstrap/staging helper, static pytest.ini,
  controlled hash-verified build context and strict real-isolation gate.
- worker/workspaces.py: profile v2 pins trusted pytest configuration, turns off
  bytecode/cache and pytest capture, preserving controller output limits and
  preventing repository pytest options from overriding the service command.
  Immutable v1 snapshots are preserved and rejected by the v2 runner; create a
  new job/source snapshot rather than changing stored identity.
- backend/app/settings.py and .env.example: validated off-by-default image ID and
  resource limits; URI userinfo redaction covers controller endpoint schemes.
- backend/app/api_models.py: status wording accurately distinguishes the storage
  API from automatic processing/publication; capability flags remain false.
- pyproject.toml: real-isolation pytest marker only. No library dependencies or
  application/development/build lock contents changed.
- worker/tests/test_runner.py, test_image_preparation.py, test_docker_isolation.py:
  lifecycle/policy/concurrency-output/controller tests and 16 actual Docker cases.
- README and setup/security/architecture/source/status/plan/delivery/progress docs:
  current behavior, profile migration, trust limits and explicit acceptance blocker.

### Exact final checks and preserved logs

Commands run from the root unless frontend/ is specified. Existing Python 3.12.10
venv and portable Node 22.16.0/npm 10.9.2 were reused; no runtime downloaded or
Application Control bypass attempted. Installed-runtime access was permitted as
in earlier phases. Logs live under docs/baseline/; PowerShell captures combined
output and appends native exit codes (uv stderr appears as NativeCommandError
formatting despite exit 0).

| Command | Exit / result | Log |
| --- | --- | --- |
| .venv\Scripts\python.exe -m pytest -q -r s | 0; 434 passed, 16 skipped, 1 existing Starlette/httpx warning; 30.15s | phase5-product-final.log |
| .venv\Scripts\python.exe runner_image/check_isolation.py | 2; BLOCKED, tests=16, skipped=16, failures=0; pytest itself exits 0 | phase5-isolation-gate.log |
| .venv\Scripts\python.exe -m ruff check worker/docker_client.py worker/docker_policy.py worker/docker_runner.py worker/runner_models.py worker/execution.py worker/workspaces.py worker/tests/test_runner.py worker/tests/test_image_preparation.py worker/tests/test_docker_isolation.py runner_image backend/app/settings.py backend/app/api_models.py | 0; all checks passed | phase5-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests runner_image | 1; existing untouched worker/tests/test_pipeline.py I001 only | phase5-lint-all.log |
| .venv\Scripts\python.exe -m pip check | 0; no broken requirements | phase5-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | 0; 33 packages, lock current | phase5-lock-check.log |
| npm.cmd test (frontend/) | 0; 1 passed | phase5-frontend-test.log |
| npm.cmd run build (frontend/) | 0; TypeScript/Vite build pass | phase5-frontend-build.log |
| Get-Command docker -ErrorAction SilentlyContinue | No matching executable; docker_available=False | phase5-tools.log |
| Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' | False | phase5-tools.log |
| DockerCLI().document(['info', '--format', '{{json .}}']) via installed Python | DockerFault: Docker operation unavailable (docker_missing); caught and recorded | phase5-docker-probe.log |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | Both unchanged | phase5-demo-hashes.log |

The frontend command process prepended .tools/node-v22.16.0-win-x64 to PATH;
the lock check set UV_CACHE_DIR to .tools/uv-cache. No unrelated environment
variables or credentials were printed. No new clean install is claimed.

Trusted dependency preparation performed separately:

```powershell
.venv\Scripts\python.exe -m pip --isolated download --index-url https://pypi.org/simple --only-binary=:all: --no-deps --dest .tools/runner-wheels pytest==9.2.0 iniconfig==2.3.1 packaging==26.3 pluggy==1.7.0 pygments==2.21.0 colorama==0.4.6
```

Exit 0 (phase5-wheel-download.log). Product-owned `runner_image.prepare.locked_wheels`
was then called on .tools/runner-wheels, compared all six identities/hashes to
uv.lock and produced phase5-wheel-receipt.json: exit 0, verified 6
(phase5-wheel-verification.log). No wheel was installed on the target/host as part
of this preparation. Build-context unit tests use synthetic reviewed-lock fixtures;
actual downloaded wheel hash checking is separate evidence, not a real image build.

The final wheel verification was repeated with the following exact product-owned
script piped into `.venv\Scripts\python.exe -` (exit 0). It reads wheel bytes and
the trusted lock; it does not import wheel or target code:

```python
from pathlib import Path
import hashlib
import json
from runner_image.prepare import locked_wheels
files, _ = locked_wheels(Path('.tools/runner-wheels'))
receipt = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
Path('docs/baseline/phase5-wheel-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
print('Verified locked pure-Python wheels:', len(files))
```

Initial mock test run recorded one test-expectation failure: invalid source was
blocked before resources existed, rather than classified as a running-container
infrastructure failure. The expectation was corrected to reflect the fail-closed
contract. Earlier intermediate passing counts and scoped lint findings remain in
phase5-* logs; final counts above apply to final code. Native process tests run
only product-owned echo/sleep helpers to validate bounded transport, never target
code. No existing warning or unrelated lint error was suppressed.

### Real isolation exit gate and Phase 6 dependency

The actual gate reports `ISOLATION ACCEPTANCE BLOCKED: Docker CLI unavailable; no
host fallback` for every real case. There is no Docker executable or usable Linux
engine here. No Docker container was created; image identity/build, effective
settings, kernel CPU/memory/PID/scratch enforcement, network/file isolation,
real timeout/cancellation/OOM/cleanup and isolated demo failure are NOT VERIFIED.
Mock tests supplement these cases and do not replace them. Root pytest success
with skips does not satisfy the dedicated gate, whose exit 2 is intentional.

The 16 required real cases include pass/fail, non-root/capabilities/seccomp,
network denial, read-only root/input, unavailable host files/env/socket, infinite
loop timeout, oversized output, cancellation, kernel OOM, effective cgroup limits,
scratch exhaustion, orphan recovery, ignored repository pytest configuration,
the supplied deliberate demo failure and independent image watchdog timeout.

Demo source/test hashes still match
434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E and
552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153.
The fixture was not repaired and target/demo pytest was NOT run on the host.

Required setup: supported Linux Docker daemon, reviewed immutable Python 3.12 base,
offline hash-verified prepared image, actual image ID in RUNNER_IMAGE_ID and
WEBGUARD_ISOLATION_IMAGE, then a zero-exit real isolation gate. Full commands and
trusted controller/recovery contracts are in ISOLATED_RUNNER.md. No fake digest,
mutable runtime tag, automatic dependency preparation or host fallback is accepted.

Phase 5 is **not fully accepted**. Independent implementation/docs are complete;
isolation acceptance is BLOCKED. Phase 6 may build against these explicit
interfaces, but repair/verification processing must remain disabled until the
real gate passes. No end-to-end verification, model repair or live PR is claimed.

**Current status: Phase 4 approved source/workspaces implemented and verified; see Phase 4 below.**
Phase 1's baseline is retained here as historical evidence. Its continuation supersedes
earlier Python blockers. This establishes a baseline, not a claim that every check
is green or any repair feature is complete. Lint findings remain recorded;
Docker remains a later isolation blocker.

Recorded 2026-11-04 (Asia/Calcutta). Phase 1 only; no repair features enabled.

## Scope and inventory

The approved starting target is the supplied `demo-repository/`: one pure-Python,
pytest fixture. It is not an independent Git repository. The product folder also
has no `.git`; `git status --short` fails. No remote identity or pinned commit is
configured. This scope does not authorize publication or arbitrary repositories.
Future execution requires one exact owner-approved repository and pinned SHA.

| Area | Actual implementation | Explicit stub / missing functionality |
| --- | --- | --- |
| backend/app/main.py | FastAPI health and status; loopback UI CORS origins | POST jobs returns 501; no auth, validated settings, persistence or queue |
| frontend/src | React status fetch, abort cleanup, response validation, error text, disabled button; CSS | No job submission, history, progress, cancellation or evidence UI |
| worker | State enum; run_job raises PipelineNotImplemented; CLI exits 2 | No polling, leases, clone, baseline, model, patch validation, isolation or publication |
| Product tests | 2 backend, 1 worker, 1 scaffold contract, 1 frontend test | No runner boundary, durable jobs, security or integration tests |
| Demo | pagination function and 2 tests | Deliberate exclusive slice end is start + page_size - 1 |
| Configuration | pyproject, package.json, TS config, Vitest/jsdom setup, env template, ignore rules | No CI, Dockerfile, compose, runtime settings loader or original lockfiles |
| Documentation | README; SCOPE, ARCHITECTURE, SECURITY, ACCEPTANCE, STATUS, SETUP, DELIVERY_VALIDATION | Referenced ANTIGRAVITY_MASTER_PROMPT.md is absent |

The demo contract is zero-based pagination. With [10,20,30,40], page=0 and
page_size=2, source returns [10] while the test expects [10,20]. Invalid page
still raises ValueError. Expected demo result: one failed, one passed. The fixture
and its tests remain untouched. This is source evidence, not an executed pytest
result. Root pytest testpaths excludes the demo; keep target and product runs
separate. SECURITY.md requires isolation for future service jobs. The requested
manual demo baseline is attempted separately, not wired into product execution.

## Environment and execution evidence

Initially Python, Node, npm, pnpm, yarn, pip and Docker were absent from PATH.
`py -0p`: no installed Pythons. uv 0.13.0 and Git 2.55.0.windows.5 available.
No Docker executable found at its standard Docker Desktop CLI location; no
working Linux engine verified. No credentials or unrelated environment were read.

Workspace-local CPython 3.12.15 downloaded after an initial restricted-network
failure. Windows Application Control blocks its venv executable and the isolated
build interpreter (OS error 4551). uv resolved 31 packages and wrote uv.lock,
but editable build/install did NOT complete. Do not weaken OS policy or claim a
clean Python install. Obtain a policy-approved Python installation to proceed.

Separate backend, worker, product-contract and demo command attempts are preserved
in `docs/baseline/*.log`; all are blocked before Python starts, with no test result.
The expected demo assertion failure is NOT a product failure. Previous packaging
validation in DELIVERY_VALIDATION.md describes a different environment and is not
current-session test evidence.

## Change boundary

No backend, worker, UI behavior, product tests or demo files changed. Added locks,
baseline evidence and planning/setup documentation. Ignore workspace-local tool
binaries/caches and retain baseline logs. Replaced broken master-prompt handoff
references with the actual implementation plan. No feature completion assumed.

## Exit gate

Inventory, scoped defect and blockers documented. Python resolution exists but
installation/test verification is blocked by OS policy. Target failure reproduction
remains pending. Phase 1 is evidence-complete only where explicitly marked;
remaining gates must be rerun on an approved runtime before Phase 2 execution.

## Frontend final baseline

Portable Node 22.16.0 (official SHA256 verified), npm 10.9.2 installed locally.
`npm install` generated frontend/package-lock.json, followed by actual clean
`npm ci` (exit 0). One component test passed, standalone TypeScript check passed,
and production Vite build passed (all exit 0). Initial sandboxed test/build
attempts failed esbuild ancestor-directory access; permitted retry succeeded.
No source/config workaround was necessary. Logs preserve both attempts.

| Check | Result |
| --- | --- |
| Python locked dependency resolution / offline freshness check | PASS; 31 packages, install NOT complete |
| Backend / worker / contract suites | BLOCKED by Application Control before execution |
| Demo suite | BLOCKED by Application Control; intended 1 fail/1 pass established from source only |
| Frontend clean npm ci | PASS |
| Frontend existing test | PASS, 1 test |
| TypeScript --noEmit | PASS |
| Vite production build | PASS |
| Docker / service isolation / live integration | Unavailable / not implemented / NOT VERIFIED |

Remaining Phase 1 gates: approved Python clean install and separately executed
product/demo results; fully pinned isolated Python build dependencies. Do not
mark Phase 1 fully passed. See SETUP.md for exact commands and version limitations.

Detailed Phase 1 edits: README and SETUP now point to the supplied implementation
plan instead of the absent master prompt and use locked install commands. STATUS
and DELIVERY_VALIDATION link current evidence while retaining historical claims.
.gitignore excludes .tools and explicitly retains baseline logs. uv.lock and
frontend/package-lock.json were generated by the actual package managers; original
dependency constraints were preserved. No feature source, test, fixture or runtime
configuration was modified. No Git diff is available because .git is absent.

## Python 3.12.10 continuation (current result)

`py -3.12 --version` initially returned `No installed Python found!` inside the
restricted sandbox. The same command with permitted access outside that sandbox
returned `Python 3.12.10`. The installed runtime is
`C:\Users\nitis\AppData\Local\Programs\Python\Python312\python.exe`.
This is an environment discovery restriction, not a new Application Control
rejection. All subsequent Python commands used that runtime's fresh venvs with
permitted access. No new Python was downloaded, and no OS policy was changed.

The old `.venv` was moved to `.tools/venv-before-installed-python` after checking
its resolved absolute path was the workspace's `.venv`. No target code changed.

Exact successful bootstrap commands, from the project root:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
$env:UV_CACHE_DIR = "$PWD\.tools\uv-cache"
uv lock --python .venv/Scripts/python.exe --no-python-downloads
uv export --locked --extra dev --extra bootstrap --no-emit-project --format requirements-txt --output-file requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock --cache-dir .tools/pip-cache
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

Each exited 0. Logs: `baseline/python312-venv.log`, `python312-version.log`,
`python312-lock.log`, `python312-export.log`, `python312-clean-install.log` and
`python312-project-install.log`. uv resolved 33 packages including the project;
Windows omits the uvloop dependency via its platform marker. The full installed
versions, including pip and setuptools, are in `baseline/python312-freeze.log`.

Build pin: pyproject's original setuptools >=75,<81 constraint is now exactly
80.9.0. A bootstrap extra pins pip 25.0.1 and the same setuptools version. uv.lock
and hash-enforced requirements-dev.lock pin application, dev, bootstrap and
transitive dependencies. The local editable project is installed separately;
--no-deps --no-build-isolation prevents implicit build-tool resolution. No wheel
package is needed by this verified setuptools editable-build path. Application/dev
version ranges remain as original compatibility constraints; installs use the locks.

Reproducibility check in a second initially absent environment:

```powershell
py -3.12 -m venv .tools/repro-venv
.\.tools\repro-venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock --cache-dir .tools/pip-cache --disable-pip-version-check
.\.tools\repro-venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . --disable-pip-version-check
.\.tools\repro-venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip freeze --all
.\.tools\repro-venv\Scripts\python.exe -m pip freeze --all
.\.tools\repro-venv\Scripts\python.exe -m pytest -q
uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads
```

All exited 0. Both `pip freeze --all` outputs match exactly, including editable
project identity, and both `pip check` runs report `No broken requirements found.`
The second product suite also passes all four tests. See `python312-repro-*.log`
and `python312-lock-check.log`. This verifies install/version reproducibility on
Windows x64/Python 3.12.10; editable wheel archive hashes differ and byte-identical
build artifacts are not claimed. Other Python/OS combinations remain unverified.

Exact primary test/check commands and results:

| Command using .venv\Scripts\python.exe | Exit | Result | Log in docs/baseline/ |
| --- | --- | --- | --- |
| -m pytest backend/tests -q | 0 | 2 passed, 1 warning | python312-backend.log |
| -m pytest worker/tests -q | 0 | 1 passed | python312-worker.log |
| -m pytest tests -q | 0 | 1 passed | python312-product-contract.log |
| -m pytest -q | 0 | 4 passed, 1 warning; demo excluded | python312-product-all.log |
| -m pytest demo-repository/tests -q | 1 | Expected: 1 failed, 1 passed | python312-demo.log |
| -m pip check | 0 | No broken requirements found | python312-pip-check.log |
| -m ruff check backend worker tests | 1 | Existing I001 import order in backend/tests/test_api.py and worker/tests/test_pipeline.py | python312-ruff.log |

The demo failure is exactly `test_first_page_contains_requested_count`: actual
[10], expected [10,20]. Invalid-page test passes. This expected target failure is
separate from the product suite. Both fixture SHA256 hashes match the previously
preserved baseline (`demo-final-hashes.log` vs `python312-demo-hashes.log`).
Backend tests emit StarletteDeprecationWarning about the existing httpx test-client
path. It does not fail tests; no dependency migration or warning suppression was
performed. The two lint findings are recorded and unchanged because this phase
only corrects bootstrap problems. No full lint pass is claimed.

Test log captures initially mixed PowerShell text encodings when appending output.
Original captures are retained as `python312-*.raw.log`; corresponding readable
logs remove NUL bytes without changing results. Earlier blocked baseline logs
remain preserved and superseded by this continuation.

Phase 1's documented-baseline exit gate is now complete: two actual clean Python
installs with pinned tools, product tests passing, separate known demo failure,
frontend checks already passing, inventory/plan and reproducible commands recorded.
Docker remains unavailable/unverified and blocks future service isolation, not
these authorized manual demo checks. Git metadata/pinned target SHA, isolation,
durable jobs, Gemini and publication remain later work. No feature, product test
or demo fixture was changed to obtain these results.

## Phase 2: controller settings and durable services

Implemented against the user's Phase 2 scope. Inspection found neither
`ANTIGRAVITY_MASTER_PROMPT.md` nor `WEBGUARD_AI_PHASE_PROMPTS.md`, and no AGENTS.md
in the supplied workspace. Existing Phase 1 code, constraints and security docs
were read first. The starter plan split settings/storage into separate rows;
this implementation follows the user's combined Phase 2 scope instead.

Implemented:

- Validated controller settings, explicit `.env` allowlist/environment precedence,
  no interpolation, safe configuration errors, SecretStr credentials excluded from
  repr/dumps, constant-time local auth check, independent live flags default off.
  Offline startup needs no external credentials. Production/live flags require
  operator authentication; each live integration also requires its own settings.
- SQLite schema versions 1 and 2, atomic migrations/rollback/future-schema
  rejection, new connections per transaction, foreign keys and busy timeout.
  Jobs contain repository/ref/pinned SHA, UTC timestamps/deadline, state/reason,
  cancellation, persisted limits/counters, lease owner/expiry, fencing and version.
  Ordered events, append-only evidence and publication metadata have separate
  tables. No settings object, auth key or provider credential is persisted.
- Transactional internal create/get/keyset-list/events/cancel/state services.
  Durable hashed idempotency key/payload plus a unique constraint prevent duplicate
  creation, including concurrent requests on separate connections. Changed input
  conflicts. State transitions, counters and related events commit together.
- Central state graph re-exported to the worker. Evidence gates reproduction/no-bug
  and verification/publication. Verification is tied to pinned SHA, patch digest
  and current repair attempt. Old successful proof cannot authorize a new attempt.
  Terminal outcomes cannot reopen; verified remains distinct from draft PR created.
- Atomic claim/renew/release/reclaim with fencing, stale-owner rejection, immutable
  deadlines and bounded claim/repair/publication attempts. Cancellation invalidates
  leases atomically. Budget reservations are cumulative and cannot be refunded;
  restart/config changes never reset existing job limits/counters. Model calls,
  tokens, integer cost and test-time reservations are enforced transactionally.
- Redaction before metadata persistence, bounded summaries, validated identifiers,
  immutable publication identity and derived GitHub URLs. Metadata is synthetic in
  tests; no actual repository execution, Gemini call or GitHub publication exists.

API startup now loads settings and applies migrations. POST /api/jobs still returns
501, the UI stays disabled, and worker CLI still raises its explicit stub failure.
Internal services are trusted controller interfaces, not unauthenticated public
job endpoints. Protected lifecycle routes and actual worker orchestration remain
Phase 3 integration work. Docker remains a later isolation blocker.

Changed/new files:

- backend/app/settings.py, database.py, domain.py, jobs.py (new implementation).
- backend/app/main.py (startup only); worker/pipeline.py (shared state import).
- backend/tests/test_settings.py, test_jobs.py, test_startup.py (new tests).
- pyproject.toml declares python-dotenv and pydantic as direct runtime dependencies;
  uv.lock and requirements-dev.lock refreshed. Resolved versions are unchanged:
  python-dotenv 1.2.4, pydantic 2.14.2; pinned build tools remain unchanged.
- .env.example; README; docs/SETUP.md, STATUS.md, IMPLEMENTATION_PLAN.md,
  ARCHITECTURE.md, PHASE_PROGRESS.md, DELIVERY_VALIDATION.md; PHASE2_STORAGE.md
  documents service contracts; docs/baseline/phase2-*.log contains evidence.

No demo fixture, frontend source or pre-existing product test was edited. No Git
metadata exists, so no Git diff can be produced. Earlier logs remain preserved.

Exact install/lock commands (project root, installed Python 3.12.10):

```powershell
$env:UV_CACHE_DIR = "$PWD\.tools\uv-cache"
uv lock --python .venv/Scripts/python.exe --no-python-downloads
uv export --locked --extra dev --extra bootstrap --no-emit-project --format requirements-txt --output-file requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock --cache-dir .tools/pip-cache --disable-pip-version-check
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . --disable-pip-version-check
py -3.12 -m venv .tools/phase2-clean-venv
.\.tools\phase2-clean-venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock --cache-dir .tools/pip-cache --disable-pip-version-check
.\.tools\phase2-clean-venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e . --disable-pip-version-check
.\.venv\Scripts\python.exe -m pip freeze --all
.\.tools\phase2-clean-venv\Scripts\python.exe -m pip freeze --all
```

All exited 0. The fresh environment did not exist before this run; it performed an
actual clean dependency install and editable build, not just resolution. Both
freeze outputs match exactly (`phase2-install-comparison.log`). This establishes
installed-version reproducibility on Windows x64/Python 3.12.10, not byte-identical
build artifacts or verification on other platforms. Permitted outside-sandbox
runtime/package access was used as in Phase 1; no Application Control bypass or
new Python download was attempted. No blocked Phase 2 command remains.

Exact verification commands/results (logs under docs/baseline):

| Command | Exit | Result | Log |
| --- | --- | --- | --- |
| .venv\Scripts\python.exe -m pytest backend/tests -q | 0 | 178 passed; 1 warning | phase2-backend.log |
| .venv\Scripts\python.exe -m pytest worker/tests -q | 0 | 1 passed | phase2-worker.log |
| .venv\Scripts\python.exe -m pytest tests -q | 0 | 1 passed | phase2-contracts.log |
| .venv\Scripts\python.exe -m pytest -q | 0 | 180 passed; 1 warning | phase2-product-final.log |
| .tools\phase2-clean-venv\Scripts\python.exe -m pytest -q | 0 | 180 passed; 1 warning | phase2-clean-tests.log |
| .venv\Scripts\python.exe -m pytest demo-repository/tests -q | 1 | Expected: 1 failed, 1 passed | phase2-demo.log |
| .venv\Scripts\python.exe -m ruff check backend/app backend/tests/test_settings.py backend/tests/test_jobs.py backend/tests/test_startup.py worker/pipeline.py | 0 | All changed/new implementation and tests pass | phase2-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests | 1 | Same 2 pre-existing I001 findings in untouched tests | phase2-lint-all.log |
| .venv\Scripts\python.exe -m pip check | 0 | No broken requirements | phase2-pip-check.log |
| .tools\phase2-clean-venv\Scripts\python.exe -m pip check | 0 | No broken requirements | phase2-clean-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | 0 | Lock current; 33 packages resolved | phase2-lock-check.log |
| npm.cmd test (frontend/, existing Node 22.16.0/npm 10.9.2) | 0 | 1 passed | phase2-frontend-test.log |
| npm.cmd run build (frontend/) | 0 | TypeScript and Vite production build pass | phase2-frontend-build.log |

The known Starlette/httpx deprecation warning remains unsuppressed. No live SDK
migration was performed. First scoped lint run identified 3 new style/type issues;
those were corrected before final checks. The full lint baseline still has the
original backend/tests/test_api.py and worker/tests/test_pipeline.py import-order
findings, preserved as unrelated changes. No full lint pass is claimed.

Tests use temporary SQLite files and separate connections for concurrent duplicate
creation, conflicting payloads, competing worker claims, usage reservations and
cancellation races. They test all state-pair edges, transactional rollback for
migrations/jobs/events/usage/evidence/publication, startup .env validation,
redaction in database dumps/bytes, schema upgrade with existing records, reopen,
expired leases, same-name stale owners, immutable pinned revision/publication,
retry caps, deadlines and unchanged budgets after restart/config changes.

The demo's separate failure remains exactly the deliberate [10] vs [10,20]
pagination assertion; invalid-page handling passes. Both fixture hashes match
Phase 1 (`phase2-demo-hashes.log`). This is not a product-suite failure.

Phase 2 exit: implemented and tested. Phase 3 can consume the durable services;
it must enforce HTTP authentication, map safe response/error models, orchestrate
leases/reaping/cancellation and integrate a genuine isolated test boundary before
any target job execution. Docker/Linux engine is still unavailable/unverified;
there is no host fallback. No end-to-end repair/live model/live PR is claimed.
Final review also tests that changing repository approval rejects an existing
lease in the reopened service, not only new claims. Numeric model-token counts
remain visible in usage audit events while credential/token strings are redacted.
Both final full-suite reruns remain 180 passed with the same single warning;
scoped lint remains clean. `Get-Command docker` still finds no executable.

## Phase 3: authenticated job API (complete within requested scope)

Inspected Phase 2 settings, SQLite services, state/lease contracts and actual test
logs first (180 product tests passed in Phase 2; no blocked test was assumed to
have passed). Neither ANTIGRAVITY_MASTER_PROMPT.md nor
WEBGUARD_AI_PHASE_PROMPTS.md was present, and no workspace AGENTS.md was found.
The user's explicit authenticated-API scope supersedes the starter plan's earlier
suggestion to include worker orchestration in Phase 3.

Working endpoints:

- Preserved GET /health (status=ok liveness) and GET /api/status. Status now reports
  actual offline/live_configured intent, operator-auth/DB/job-API availability,
  with processing_enabled=false and repair_enabled=false regardless of live flags.
  Configured live flags do not mean any external adapter is operational.
- Added GET /ready for current SQLite read/write/migration/table readiness. Initial
  DB failure leaves the process alive but unready; runtime read-only/missing tables
  also fail readiness. Invalid settings still fail startup safely.
- POST /api/jobs validates only approved repository/ref/full optional SHA, requires
  a single bounded Idempotency-Key and operator bearer auth, and returns 202 only
  after the Phase 2 transaction commits. Same key/input returns the same current
  durable job; conflicting valid input returns 409. No in-memory fallback exists.
- Authenticated GET /api/jobs, GET /api/jobs/{id}, GET /api/jobs/{id}/events provide
  whitelisted durable details and ordered bounded pagination. Job IDs/cursors are
  validated. Internal hashes, lease owners/fences, DB paths and credentials are
  omitted. Event fields are whitelisted and re-redacted for HTTP.
- POST /api/jobs/{id}/cancel is authenticated, transactional and idempotent for
  already-cancelled jobs, and protects other terminal outcomes. The response says
  execution_stop_confirmed=false; persisted cancellation/fencing does not claim
  that a running process stopped. There is no executor to stop in this phase.

Security/interface details:

- Every job route is protected before body parsing or lookup by the local
  Authorization bearer header. A missing server AUTH_TOKEN disables all job
  routes (503), not authentication. Missing/incorrect caller tokens return 401
  with WWW-Authenticate: Bearer. Cookies/query values cannot authenticate.
- AUTH_TOKEN now accepts 32-256 visible ASCII characters, excluding whitespace and
  newlines so it is valid for the bounded header flow. This is a deliberate
  settings prerequisite change; provider-key requirements/flags are unchanged.
- No cookie sessions or ambient browser credentials, so no cookie CSRF flow.
  Future UI token entry is documented as runtime/session-memory only, never VITE_,
  localStorage, URLs or embedded source. Existing UI source remains unchanged.
- Loopback Host boundary; documented 127.0.0.1 bind with proxy headers/access logs
  off. Explicit CORS origins are localhost/127.0.0.1 on 5173 and 8000. CORS allows
  only GET/POST and the required headers, with no credentials. Preflights contain
  no job data and still obey request limits. Approved UI origins can read safe
  boundary errors; unapproved origins cannot read job responses.
- ASGI boundary caps bodies/headers at 16,384 bytes and path+query at 2,048 bytes.
  Actual body bytes are counted, including streamed and falsely declared bodies.
  Encoded bodies, malformed/duplicate JSON fields, ambiguous framing/key headers,
  invalid/unknown/duplicate query parameters and extra executable inputs fail closed.
- Stable v1 public models and safe error envelopes replace raw validation/SQL
  messages. Generic internal exceptions are deliberately contained at the HTTP
  boundary (documented scoped lint exemption) rather than logged with raw inputs.
  Default Uvicorn access arguments are filtered to omit request targets entirely;
  recommended startup disables access logs. Responses are no-store; automatic
  slash redirects are off so they cannot reflect query strings in Location.

Implementation changes:

- backend/app/main.py: app factory, startup/readiness, protected endpoints,
  transaction integration, whitelisted projection, safe error handlers and CORS.
- backend/app/api_models.py and http_security.py: new public models/cursors,
  authentication/request-size boundary and private access logging.
- backend/app/settings.py: local operator token header-safe validation.
- backend/tests/test_api.py: replaces the obsolete POST=501 scaffold expectation
  with the API integration/security tests. backend/tests/test_startup.py now expects
  auth_not_configured instead of 501. backend/tests/test_settings.py adds token
  length/whitespace prerequisites. Existing Phase 2 storage/state tests remain.
- .env.example; README; API.md, SETUP.md, STATUS.md, IMPLEMENTATION_PLAN.md,
  PHASE2_STORAGE.md, SECURITY.md, ARCHITECTURE.md, DELIVERY_VALIDATION.md and this
  progress file updated. Prior baseline logs retained; Phase 3 evidence is under
  docs/baseline/phase3-*.log.

No backend service schema/transaction semantics, demo fixture, worker implementation,
frontend source or dependency constraints were changed. No schema migration or new
package was needed; uv.lock and requirements-dev.lock are unchanged and verified
current. No clean install was rerun in Phase 3 or claimed; Phase 2's clean-install
evidence remains historical. The existing Python 3.12.10 venv was used.

Exact commands/results from the project root (frontend commands from frontend/):

| Command | Exit | Result | Log in docs/baseline/ |
| --- | --- | --- | --- |
| .venv\Scripts\python.exe -m pytest -q | 0 | 275 passed; 1 warning | phase3-product-final.log |
| .venv\Scripts\python.exe -m ruff check backend/app backend/tests/test_api.py backend/tests/test_startup.py backend/tests/test_settings.py | 0 | All changed/new code passes | phase3-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests | 1 | Existing worker/tests/test_pipeline.py I001 only | phase3-lint-all.log |
| .venv\Scripts\python.exe -m pytest demo-repository/tests -q | 1 | Expected: 1 failed, 1 passed | phase3-demo.log |
| .venv\Scripts\python.exe -m pip check | 0 | No broken requirements found | phase3-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | 0 | Lock current; 33 packages | phase3-lock-check.log |
| npm.cmd test | 0 | 1 frontend test passed | phase3-frontend-test.log |
| npm.cmd run build | 0 | tsc --noEmit and Vite build passed | phase3-frontend-build.log |

The frontend checks reused the existing Node 22.16.0/npm 10.9.2 installation,
with the workspace portable Node directory prepended to PATH for that process.
Approved outside-sandbox runtime access was used as in Phases 1-2; no Python was
redownloaded and no Application Control bypass was attempted. No Phase 3 command
remains blocked. The initial test iteration passed 266 tests; later readiness and
commit-failure coverage increased the final count to 275. Initial lint import
formatting was corrected; full lint is not claimed clean. The existing
Starlette/httpx deprecation warning remains visible and unsuppressed.

Integration tests use temporary SQLite files/app instances and no real external
credentials. They cover every protected route with missing/wrong/malformed auth,
cookie/query/duplicate-header rejection, no-auth configuration, validated inputs,
authentication before malformed JSON/lookup, durable acceptance/reopen/idempotency,
concurrent HTTP duplicate creation, changed-payload conflicts, bounded pagination,
invalid cursors, unknown IDs, terminal/cancellation protection and stale-owner
rejection after cancellation. Storage tests force a real deferred SQLite FK error
at COMMIT to prove no 202 is sent before durable success and that rollback allows
the same key to retry. Readiness tests use an actual read-only SQLite connection
and drop required tables. ASGI tests send chunked/lying-length bodies. Responses,
OpenAPI, application errors and access log arguments are checked for secret
leaks. A patched worker.run_job raises if called; HTTP acceptance never invokes it.

The demo remains the same deliberate [10] vs [10,20] assertion failure plus one
passing invalid-input test. Its two hashes match Phase 1 (phase3-demo-hashes.log).
This is not a product-suite failure. The old backend API test import-order lint
finding disappeared because that test was intentionally rewritten; the unrelated
worker test finding remains untouched.

Required setup and protocol: docs/API.md and docs/SETUP.md. Configure a private
local AUTH_TOKEN for job routes, keep live flags off, run the loopback command.
No provider credentials are needed for offline job acceptance. No real operator
credential was created or printed during this work.

Phase 3 exit: complete within the requested authenticated storage API scope.
Phase 4 can build on these tested routes/services. No worker polling, repository
cloning, container execution, repair, SDK call or PR creation is implemented.
Docker/Linux isolation is still unavailable/unverified and remains a later target
execution blocker; there is no host fallback. This archive still has no Git
metadata, so no Git diff or pinned target SHA is claimed.

## Phase 4: approved repository access and workspace management

Complete within the requested source-acquisition scope. Inspected the actual
settings, services, state machine, worker stub, migrations, security/architecture
and Phase 3 results first (275 passing tests, not assumed blocked results).
ANTIGRAVITY_MASTER_PROMPT.md and WEBGUARD_AI_PHASE_PROMPTS.md remain absent;
no workspace AGENTS.md was found. The user's explicit Phase 4 scope was followed.

Implemented behavior:

- GitHub adapter configured with one canonical approved owner/name, checked again
  against JobService settings by RepositoryAccess. Reject URL/SSH/file/local,
  credential-bearing, mixed-case/noncanonical and unsupported identities. Only
  api.github.com and codeload.github.com are used; all redirects are refused.
  Public repository metadata identity is verified, refs/commit/tree SHAs are
  validated and content is pinned. Private/authenticated reads are not implemented.
- Separate local-fixture adapter uses a controller-injected ordinary Git directory
  for the reserved demo identity. It is not a URL/path input on the HTTP API.
  Tests initialize temporary Git copies of the bundled demo without changing or
  executing the fixture. No HTTP handler or worker entrypoint invokes acquisition.
- High-level prepare requires a current fenced lease in baselining state, resolves
  a ref or explicit/already pinned SHA, persists the immutable commit and acquires
  bounded committed source. Ref movement after pin cannot silently select a new
  commit. Restart reopens the same verified recorded snapshot.
- Remote acquisition inspects bounded recursive tree metadata before requesting
  a bounded archive. Local acquisition inspects ls-tree metadata before bounded
  cat-file object reads. No clone/checkout/history copy, filters, hooks, pager,
  filesystem monitor, prompts, lazy fetch, repository instructions or installation
  scripts are executed. Git arguments are structured shell=False and its child
  environment excludes credentials; output and timeouts are enforced.
- Metadata/file count, individual/aggregate file bytes, compressed and decompressed
  archive streams and member counts are bounded. Blob object hashes are verified.
  Reject symlinks, gitlinks/submodules even without .gitmodules, .gitmodules itself,
  hardlinks/sparse/special archive members, unsafe/ambiguous/nonportable paths,
  case collisions and duplicate/unexpected archive files. Git subprocesses are
  killed on timeout/output excess. HTTP uses socket timeouts and budget checks
  around available-chunk reads; these are not OS/DNS hard-resource isolation.
- Dedicated workspace root has exclusive ownership metadata; nonempty unmarked
  roots are not adopted. Each acquisition is unique to job/workspace identity.
  A read-only baseline and canonical file/profile/SHA manifest are sealed; their
  digests are stored independently in SQLite. Tampering, missing source or profile
  change prevents reuse. Read-only attributes are not kernel immutability against
  the controller owner; hashes enforce integrity before/after copying.
- Clean attempts/resets use independent regular-file copies in fresh generation
  paths, even for the same logical attempt number. Old artifacts never enter a
  reset and stale owners cannot overwrite/delete newer copies by path reuse.
  Per-generation metadata records pinned SHA and manifest/profile digests outside
  the mutable source copy. Physical copies do not spend/replace model budgets;
  future orchestration must use existing state/usage reservation services.
- Cleanup validates owner/job/workspace markers, resolves the exact owned absolute
  path and scans all descendants before recursive deletion. Symlink/junction,
  hardlink and ownership mismatches fail closed without touching unrelated files.
  Read-only flags are changed only on verified regular owned files. Ordinary partial
  acquisition and storage/lease failure clean only that new unique workspace.
  Incomplete ownership or unsafe filesystem tampering is left for review, not
  blindly deleted. Cleanup requires quiescent work; no privileged-host race
  resistance or OS sandbox is claimed.
- Frozen code-owned target profile defines Python 3.12, trusted pytest command,
  pagination.py source-edit allowlist and an offline binary-only, no-deps recipe
  with all Python-3.12 pytest runtime versions pinned. Repo content cannot override
  it. Recipe data is not executed and no target environment/wheel set was prepared.

SQLite migration 3 adds source_snapshots (job/workspace ID, SHA, manifest/profile
digests, creation timestamp). Source record, version update and source_acquired
ordered event commit atomically and are fenced; source records cannot be replaced.
JobService gained check_lease/source_snapshot/record_source. HTTP event projection
includes only opaque source identifiers/digests, never workspace paths. Readiness
checks the new table. Source acquisition is NOT pytest evidence and never advances
reproduced/verified. Job remains baselining until the future isolated runner acts.
Persistent budgets, terminal protection and idempotency remain enforced.

Changed files:

- New worker/source_common.py, repositories.py, workspaces.py, source_service.py.
- New worker/tests/test_repositories.py: real temporary Git fixtures, mocked
  remote access, stream/process/workspace/cleanup tests. No target import/test run.
- backend/app/database.py, jobs.py, settings.py, main.py, api_models.py: migration,
  fenced source metadata, validated source limits, safe event/readiness support,
  truthful status message. backend/tests/test_jobs.py, test_settings.py and
  test_api.py updated for schema upgrade/limits/rejected local-path request fields.
- .env.example, README and architecture/setup/security/status/progress/API/plan
  docs; new SOURCE_ACCESS.md; prior logs preserved and phase4-*.log added.

No frontend source, worker.run_job implementation, bundled demo file, dependency
constraint or dependency lock content was changed. All new runtime imports are
standard library or already declared product dependencies. Current profile package
pins already exist in the product lock; target artifact hashes/preparation belong
to Phase 5. No clean install was repeated or claimed in Phase 4.

Exact checks/results (project root unless frontend/ is specified):

| Command | Exit | Result | Log under docs/baseline/ |
| --- | --- | --- | --- |
| .venv\Scripts\python.exe -m pytest -q | 0 | 366 passed; one existing warning | phase4-product-final.log |
| .venv\Scripts\python.exe -m ruff check worker/source_common.py worker/repositories.py worker/workspaces.py worker/source_service.py worker/tests/test_repositories.py backend/app backend/tests/test_jobs.py backend/tests/test_api.py backend/tests/test_settings.py | 0 | Changed/new code clean | phase4-lint.log |
| .venv\Scripts\python.exe -m ruff check backend worker tests | 1 | Untouched worker/tests/test_pipeline.py I001 only | phase4-lint-all.log |
| .venv\Scripts\python.exe -m pip check | 0 | No broken requirements | phase4-pip-check.log |
| uv lock --check --offline --python .venv/Scripts/python.exe --no-python-downloads | 0 | Lock current; 33 packages | phase4-lock-check.log |
| npm.cmd test (frontend/) | 0 | 1 passed | phase4-frontend-test.log |
| npm.cmd run build (frontend/) | 0 | TypeScript and Vite build pass | phase4-frontend-build.log |
| Get-FileHash demo-repository/pagination.py,demo-repository/tests/test_pagination.py -Algorithm SHA256 | 0 | Both hashes match earlier baseline | phase4-demo-hashes.log |
| git --version; Get-Command docker -ErrorAction SilentlyContinue | Git available; Docker absent | Git 2.55.0.windows.5; docker_available=False | phase4-tools.log |

Python 3.12.10 existing venv and Node 22.16.0/npm 10.9.2 were reused. UV_CACHE_DIR
was set only to .tools/uv-cache for the offline check. Frontend PATH was prepended
with the existing portable Node directory for that command process. Permitted
outside-sandbox runtime access was used as in prior phases; no runtime download,
Application Control bypass, GitHub credential or live source call was required.
No Phase 4 test was skipped or remains blocked.

Initial source test command was `.venv\Scripts\python.exe -m pytest
worker/tests/test_repositories.py -q` (phase4-source-first.log): 66 passed and one
failed because the test attempted to construct a giant tar member with insufficient
fixture bytes. The malformed test builder was corrected; the actual oversized
member is now rejected before extraction. Later full suites passed 342, 355, 360
and finally 366 tests as coverage expanded. Initial scoped lint issues were fixed;
full lint is not claimed clean. The existing Starlette/httpx deprecation warning
is visible and unsuppressed.

Coverage includes canonical identities/ref resolution and real commit pinning;
Git symlink and unregistered gitlink objects; .gitmodules; size/output/time limits;
mocked GitHub identity/tree/archive mismatch/truncation/redirect/host cases;
compressed/decompressed caps; secret-free HTTP transport; hooks/filters/untracked
content not executed/copied; source record rollback/reopen/immutability; cancellation
mid-acquisition; profile ownership/edit exclusions; schema 1/2 upgrade; sealed
baseline tampering; cross-job and reset-generation separation; SHA metadata; and
safe cleanup with a real filesystem symlink or Windows junction. Sentinels outside
owned trees survive rejected cleanup. The process-timeout test runs only a
product-owned Python sleep helper, never target code or a target test.

Target/demo pytest was deliberately NOT run on the host in Phase 4. Its known
Phase 3 result remains one deliberate assertion failure and one pass; source and
test hashes remain 434D71F92FB9C64AB345BBC91B3A3FC6B06013D17D48D051D3AFBF502CA8A87E
and 552AB0838DDE5161E8AD9B39AAD67F0B1C22411A60AD221CD2FC00185989F153 respectively.
Future reruns must use the actual Phase 5 isolated runner. No fixture repair,
target install, target execution, model operation or real PR occurred.

Setup/contracts: SOURCE_ACCESS.md and SETUP.md. Use a dedicated empty or previously
owned WORKSPACE_ROOT and validated source limits. Offline fixture Git paths are
controller-injected only; public GitHub requires an explicitly approved owner/name
and network access, not a provider token. The current profile expects the supplied
demo or its approved GitHub copy. Other layouts require explicit profile review.

Phase 4 exit: source acquisition and workspace services implemented and tested.
Actual GitHub network download is NOT VERIFIED (mock coverage only). No automatic
worker/source pipeline or isolated execution is claimed. Phase 5 must prepare
verified dependency artifacts and provide real network/CPU/memory/PID/output/time
limits and process cleanup in a genuine execution boundary. Docker/Linux engine
remains unavailable/unverified; source acquisition is not a replacement and there
is no target-host execution fallback. The product archive still has no .git;
temporary Git fixtures do not create product Git metadata or authorize publication.
