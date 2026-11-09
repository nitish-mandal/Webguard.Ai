# Setup

Timeout follow-up: [PROVIDER_TIMEOUT_DIAGNOSIS.md](PROVIDER_TIMEOUT_DIAGNOSIS.md)
explains the spent live attempt and prepared SDK/process deadline separation.
Proposed additional-attempt settings (not applied privately): REPAIR_CALL_SECONDS=90,
REPAIR_HTTP_TIMEOUT_SECONDS=60, JOB_TIMEOUT_SECONDS=420. Both live flags remain
false; no additional provider call is authorized by setup or mocked tests.

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

## Phase 12 release / live deferral

Phase 11 browser acceptance is PASSED for user-confirmed job
802d2957d6ef48d182a8b04919e34165 (two failures, verification 1/2/9 passes, one
simulated draft). This evidence is preserved. The operator **deferred the live
run** in Phase 12; live Gemini/GitHub/source acquisition remain unverified.
Do not enable live flags or make external calls while deferred.

See [RELEASE.md](RELEASE.md) for the strict 24-case offline Docker gate, exact
private `.env` settings and one-job bounds for a future explicitly authorized live
run, the supported public demo-copy target requirement, actual PR inspection
requirements and clean ZIP contents/build verification. Current missing private
settings are GEMINI_API_KEY, GEMINI_MODEL, GITHUB_TOKEN, a canonical approved
ALLOWED_REPOSITORY and explicit RUNNER_IMAGE_ID in `.env`, plus live opt-ins and
reviewed one-job budgets. Keep the existing local AUTH_TOKEN private. Neither
credentials nor scope approval have been supplied for live acceptance.

Local-only preparation check:
`.venv\Scripts\python.exe scripts/check_live_configuration.py --repository owner/repository`.
It prints setting names/booleans, makes no network calls and does not authorize a
live run. Current `.env` stays in offline demo mode. Build the release with
`.venv\Scripts\python.exe scripts/build_release.py`; source ZIP/checksum are under
artifacts. Runtime data, credentials, dependencies/builds and raw diagnostics are
excluded; selected sanitized acceptance evidence and the member manifest are included.

## Dashboard (Phase 11)

The React dashboard now connects to the operator-authenticated API and background
worker. See [DASHBOARD.md](DASHBOARD.md) for exact API/worker/frontend commands,
token handling, job/evidence/cancellation flow and browser acceptance steps.
From root, start the API on 127.0.0.1:8000, the configured Docker worker, then
`npm --prefix frontend run dev -- --port 5173 --strictPort` and open
http://127.0.0.1:5173. With the workspace Node, prepend its directory to PATH as
shown in DASHBOARD.md. Only the local AUTH_TOKEN goes into the in-memory operator
field; Gemini/GitHub credentials remain private server settings. Both live flags
default false. No new dependencies or database migrations were required.

Validation commands: `npm --prefix frontend test`, `npm --prefix frontend run
typecheck`, `npm --prefix frontend run build`; Python product tests remain
`.venv\Scripts\python.exe -m pytest -m 'not isolation' -q`. The independent real
HTTP/Docker stack check is `.venv\Scripts\python.exe runner_image/check_dashboard_api.py`
with DOCKER_HOST and WEBGUARD_ISOLATION_IMAGE from phase8-image.json. It is not a
browser test. The automated Computer Use blocker remains historical; the user
subsequently confirmed manual browser acceptance for job 802d2957d6ef48d182a8b04919e34165.
Agent screenshot/keyboard/screen-reader acceptance is not claimed. Exact results
are in PHASE_PROGRESS.md.

## Automatic worker (Phase 10)

Follow [WORKER.md](WORKER.md) for exact startup, API submission, stop, retry and
cleanup instructions. From root run `.venv\Scripts\python.exe -m worker` with the
same private .env/DATABASE_URL/WORKSPACE_ROOT and immutable RUNNER_IMAGE_ID as the
API. Docker Desktop Linux and the prepared v4 image are required for target tests.
Default demo mode uses fake Gemini/simulated GitHub without external credentials;
the private local AUTH_TOKEN protects API routes. Live services remain unverified.

Ctrl+C drains the current bounded job, or use
`.venv\Scripts\python.exe -m worker --stop WORKER_ID` with its printed ID. Confirm
actual worker exit/stopped output; a drain request is not an executor stop.
Use API cancellation to interrupt a target. Already accepted drafts may survive.
`.venv\Scripts\python.exe -m worker --resume JOB_ID` unpauses after a setup fix
without resetting deadlines or budgets. HTTP handlers still only store/report jobs.

Migration 7 adds dispatch/retry timing and sessions; back up databases before
upgrades. WORKER_POLL_SECONDS=1 and WORKER_RETRY_SECONDS=10 are validated settings.
Real gate: `.venv\Scripts\python.exe runner_image/check_pipeline.py` with the v4
Docker acceptance environment from WORKER.md. It exercises the actual API/CLI
worker, six Docker observations and one simulated draft, plus API cancellation.
Historical setup/results below describe each phase's original boundary.

Phase 7 adds the official Google Gen AI SDK (locked 2.34.0) and SQLite migration 4.
Install the updated requirements-dev.lock; offline startup/proposals need no
external credentials. A fresh Python 3.12.10 install was run and matched all 45
installed Windows distributions. See REPAIR.md and PHASE_PROGRESS.md for evidence.

Phase 1 evidence: [PHASE_PROGRESS.md](PHASE_PROGRESS.md). Remaining work:
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). No master prompt is supplied.

## Versions and lockfiles

Verified frontend environment: Windows x64, Node 22.16.0, npm 10.9.2.
Clean `npm ci`, one component test, TypeScript and production build passed.
Locked versions include React/React DOM 19.3.1, TypeScript 5.9.3, Vite 6.4.5,
Vitest 3.2.7, jsdom 26.1.0. Full direct versions: baseline/frontend-versions.log.
Original package ranges were compatible; no dependency upgrades outside them
were necessary. Other Node/OS combinations are not verified. The project baseline
remains Node 22.12+; do not interpret that as testing every newer Node release.

Python metadata requires >=3.12; verified baseline is installed CPython 3.12.10
on Windows x64. The downloaded 3.12.15 runtime is not used. Historical Phase 1/2
clean-install runs produced matching installed versions and passing checks;
their exact evidence remains in PHASE_PROGRESS.md. Phase 4 reused the existing
development venv and did not rerun a clean install. uv 0.13.0 resolved uv.lock and the offline
lock freshness check passed. Locked direct packages: FastAPI 0.162.0,
uvicorn 0.54.0, pytest 9.2.0, httpx 0.28.1, ruff 0.17.3. Transitive versions and
artifact hashes are in uv.lock and requirements-dev.lock. The latter includes
application, development and bootstrap dependencies: pip 25.0.1 and setuptools
80.9.0. The build backend is also pinned to setuptools 80.9.0 in pyproject.toml.
Install the hash-locked dependencies first, then install the local project with
--no-deps --no-build-isolation so the build cannot resolve new tools. Other
Python versions/platforms are not verified. Reproducibility here means matching
installed versions and successful builds/tests, not byte-identical wheels.

Official references consulted for the existing tool majors:
- https://docs.astral.sh/uv/concepts/projects/sync/ (locked sync and optional extras)
- https://v6.vite.dev/guide/ (use version-specific Vite documentation)
- https://nodejs.org/dist/v22.16.0/SHASUMS256.txt (portable archive SHA256)

## Reproduce installation and checks

From the project root, on a machine with a policy-approved Python 3.12 and uv
0.13.0 for regenerating locks (uv is not needed for the pip install commands).
These commands completed successfully on this machine. Network access to package
indexes is required on first install. Do not disable Application Control.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock --cache-dir .tools/pip-cache
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python -m pytest backend/tests
.\.venv\Scripts\python -m pytest worker/tests
.\.venv\Scripts\python -m pytest tests
# Target suites must use the Docker runner, not this host environment.
# Product-only aggregate (testpaths excludes demo):
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

For POSIX use `.venv/bin/python` instead of `.venv\Scripts\python`.
Use a fresh venv for clean-install verification. The old blocked venv was preserved
in `.tools/venv-before-installed-python`. The independent second install is in
`.tools/repro-venv`; exact commands and comparisons are in PHASE_PROGRESS.md.
To intentionally regenerate locks:

```powershell
$env:UV_CACHE_DIR = "$PWD\.tools\uv-cache"
uv lock --python .venv/Scripts/python.exe --no-python-downloads
uv export --locked --extra dev --extra bootstrap --no-emit-project --format requirements-txt --output-file requirements-dev.lock
```

`python -m worker` starts the lease-aware background worker. Configure the prepared
Docker image/endpoint as in WORKER.md; missing isolation blocks target execution.

With Node 22.16.0/npm 10.9.2 on PATH:

```powershell
cd frontend
npm ci
npm test
npx --no-install tsc --noEmit
npm run build
npm run dev
```

This session used a checksum-verified portable Node in
`.tools/node-v22.16.0-win-x64`; prepend its absolute path to PATH if reusing it.
No global package installation or machine PATH edits were made. Python was also
downloaded under `.tools/python`; its uv executable shim registration warned
about an existing unmanaged shim, which was not replaced. Local tools are ignored.
Initial frontend install attempt had an incorrect local PATH; corrected before
actual npm install. Initial sandboxed Vite/esbuild commands failed ancestor-path
access; permitted unsandboxed retry passed without any product/config change.
PowerShell logs may wrap native stderr as NativeCommandError; recorded exit codes
and test/build summaries distinguish warnings from actual command failures.

## Configuration and later prerequisites

API defaults to http://127.0.0.1:8000, UI to http://127.0.0.1:5173.
The backend loads the project-root `.env` at application startup using an explicit
field allowlist, with process environment taking precedence and interpolation
disabled. Copy `.env.example` to `.env` only if you need custom settings. Defaults
select the approved demo, SQLite `data/webguard.db`, and both live flags off;
offline startup requires no external credentials. Keep `.env` out of version control.
Set AUTH_TOKEN to an operator-generated token of 32-256 visible ASCII characters
before using any job route, production or either live flag. An empty token
authenticates nobody; all job routes return 503 auth_not_configured while public
probes remain available. The constant-time authenticator now protects every job
route; HTTP creation returns 202 only after durable commit, with no worker loop.
Gemini additionally requires a
key/model; GitHub publication requires a token and exact lowercase owner/name.
Enabling a configuration flag does not implement an external adapter.

Startup applies SQLite schema migrations 1 through 5 atomically, rejecting newer or
inconsistent migration histories. Back up an existing database before future
upgrades. Jobs, evidence, events, leases, budgets and source snapshot metadata survive reopening. Settings
and credentials are never stored in the database; only nonsecret job limits are
snapshotted at creation. No migration downgrade is supported.

For a custom UI API address, set only VITE_API_BASE_URL in frontend/.env.local.
Never put secrets in VITE_ keys. Frontend environment values are not backend auth.
Detailed internal service contracts: [PHASE2_STORAGE.md](PHASE2_STORAGE.md).
HTTP/auth setup, example requests, pagination, error codes and capabilities:
[API.md](API.md). Send the local token only in the Authorization bearer header,
never in VITE_ values, URLs or logs. No cookie session is used. The existing
frontend still has no token entry or job form; use the documented local API flow.
`/health` checks liveness; `/ready` checks current SQLite readiness. Database
initialization failure leaves the app alive but unready: fix storage and restart.

Git 2.55.0.windows.5 is installed, but this product archive has no Git metadata.
The Phase 4 adapter can now pin target SHAs; tests use temporary Git copies of the
unchanged demo. No actual GitHub source acquisition is verified. Docker Engine
29.9.2/Linux with cgroups v2 now passes all real isolation and demo reproduction
checks on the recorded prepared image. Durable jobs and validated settings exist;
authenticated HTTP lifecycle routes are now implemented. Later phases require worker orchestration and
the explicit isolated runner for target execution. No host fallback
for service jobs. Use only the approved demo until exact owner/repository scope
and pinned commits are configured.

## Source acquisition (Phase 4)

See [SOURCE_ACCESS.md](SOURCE_ACCESS.md) for trusted controller interfaces and
ownership/cleanup rules. There is no HTTP source-path field or automatic worker.
Offline tests inject an operator-prepared temporary Git fixture; the bundled
demo remains a non-Git fixture. Public GitHub reads require the exact approved
canonical owner/name and network access, but no credentials. Private repository
access is unsupported; provider tokens are never forwarded during acquisition.

Configure WORKSPACE_ROOT as a dedicated empty directory or reuse an already owned
root; nonempty unmarked roots are refused. Do not delete markers to bypass this.
SOURCE_TIMEOUT_SECONDS, SOURCE_MAX_FILE_BYTES, SOURCE_MAX_TOTAL_BYTES,
SOURCE_MAX_FILES, SOURCE_MAX_ARCHIVE_BYTES and SOURCE_MAX_METADATA_BYTES are
validated controller limits in .env.example. They are never request parameters.
The current profile is a code-owned Python 3.12/pytest demo profile with an offline
pinned dependency recipe. Phase 5 implements separate offline image preparation;
it does not install target dependencies on the host.

Run product tests with `.venv\Scripts\python.exe -m pytest -q`; the root testpaths
exclude target tests. Do not run demo pytest or repository installation scripts
on the host. Historical Phase 1-3 demo failures remain evidence, with Phase 4
fixture hashes unchanged. Real Phase 5 isolation and Phase 6 demo reproduction now
pass; all target tests still run only inside Docker.

## Docker runner setup (Phase 5)

Follow [ISOLATED_RUNNER.md](ISOLATED_RUNNER.md) to prepare a reviewed digest-pinned
Python 3.12 image from hash-verified wheels, then record its local immutable image
ID in RUNNER_IMAGE_ID. A Linux Docker engine with cgroups v2 and CPU/memory/swap/
PID/seccomp support is required. The runner image has now been built and tested;
base/image receipts are in docs/baseline/docker-resume-base.json and
docker-resume-image.json. Empty RUNNER_IMAGE_ID and missing Docker still block execution.
The client uses a private empty auth/proxy config, not the user's Docker context;
use the default endpoint or explicit operator-owned DOCKER_HOST. Never pass
provider credentials to a target image or frontend.

Run `.venv\Scripts\python.exe runner_image/check_isolation.py` after configuring
WEBGUARD_ISOLATION_IMAGE to the actual prepared sha256 image ID. Exit 2 means
blocked/skipped, not accepted. Current result: 16 passed, zero skips, exit 0. Generic product
pytest returns success with skips, so it cannot replace this acceptance gate.
Profile v3 adds image-owned structured pytest reporting; rebuild the prepared image
and create a new job/source
snapshot instead of altering old immutable profile metadata. Explicit execution
services are available, but worker.run_job remains disabled and no API runs tests.
Use explicit ownership/lease-aware recovery as documented; never broad Docker prune.

Phase 6: see [REPRODUCTION.md](REPRODUCTION.md) for the explicit DetectionService.
Run `.venv\Scripts\python.exe runner_image/check_reproduction.py` for the real
two-run demo gate after the Phase 5 isolation gate passes. Current result is exit 0,
1 passed with zero skips. Fake classification tests do not prove reproduction.

To reuse the actual accepted image in a new PowerShell session:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/docker-resume-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_ISOLATION_IMAGE = $env:RUNNER_IMAGE_ID
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_isolation.py
.venv\Scripts\python.exe runner_image/check_reproduction.py
```

Alternatively configure the image ID in private server .env; no credentials were
changed during acceptance. This does not enable worker.run_job or API execution.
Report storage uses the separate bounded /tmp tmpfs, so working scratch exhaustion
does not consume the report allocation. Runner-image wheels/profile are unchanged;
Phase 7 updated the controller dependency locks for the official SDK.

## Repair proposals (Phase 7)

Use the explicit RepairService only after same-SHA reproducible detection.
ENABLE_LIVE_GEMINI defaults false and selects the deterministic offline fake.
Live requires explicit true plus GEMINI_MODEL, GEMINI_API_KEY and AUTH_TOKEN in
private server configuration. Never put these in frontend/VITE settings or URLs.
No supported live model is assumed and live calls were not tested. See REPAIR.md
for per-call limits, accounting reservations and structured response validation.
REPAIR_INPUT_BYTES/OUTPUT_BYTES, OUTPUT_TOKENS, CALL_SECONDS, MAX_RETRIES and
COST_MICROS_PER_CALL are controller settings with the REPAIR_ prefix as listed
in .env.example. The job's persistent budgets cap every attempt/retry.

Run `.venv\Scripts\python.exe runner_image/check_repair.py` with the existing
DOCKER_HOST/WEBGUARD_ISOLATION_IMAGE acceptance environment for the strict real
reproduction-to-offline-proposal gate. Current result: exit 0, 1 passed, zero skips.
It returns 2 if actual Docker reproduction is skipped. No post-patch target tests
run in Phase 7; candidates are proposed and await Phase 8 verification. The API
still stores jobs and worker.run_job remains disabled.

## Exact-patch verification (Phase 8)

See VERIFICATION.md. Migration 5 adds persistent verification rounds. Profile v4
adds trusted original-test/regression selectors and 9 immutable image-owned checks;
the full original pytest command and repository tests remain unchanged. Build/use
the new image in docs/baseline/phase8-image.json and create new v4 baseline/proposal
jobs. Do not relabel v3 images or reuse v3 evidence with the v4 runtime.

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_ISOLATION_IMAGE = $env:RUNNER_IMAGE_ID
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_isolation.py
.venv\Scripts\python.exe runner_image/check_verification.py
```

Actual results: 16 isolation checks and 3 verification acceptance cases passed,
zero skips, both gates exit 0. Candidate verification runs only in Docker and
requires the same image as its new baseline. Limits, retries, reservations and
fencing persist across restarts. Phase 9 explicit publication is described below;
automatic processing and HTTP publication remain disabled.

## Draft publication (Phase 9)

See [PUBLICATION.md](PUBLICATION.md) for the explicit lease-aware service and retry
protocol. Default offline mode uses a durable simulated GitHub remote and needs
no external credential. Run `runner_image/check_publication.py` with the same
v4 Docker environment above for real reproduction/verification followed by one
simulated draft. All target tests stay inside Docker. Migration 6 is applied by
JobService startup; back up persistent databases before deployment/upgrades.

Live publication is NOT VERIFIED. It requires an exact canonical approved
owner/repository, private server AUTH_TOKEN, a single-repository GitHub App
installation GITHUB_TOKEN (Contents/Pull requests write) and explicit
ENABLE_GITHUB_DRAFT_PR=true. Broad/classic tokens are rejected. No credential
belongs in frontend/VITE settings, URLs or logs. Transport limits are
PUBLICATION_SECONDS, PUBLICATION_REQUEST_SECONDS, PUBLICATION_MAX_REQUESTS,
PUBLICATION_RESPONSE_BYTES and PUBLICATION_REQUEST_BYTES in .env.example.
The live adapter never merges. A moved base blocks the old intent; create and
verify a new pinned-baseline job. A remotely accepted draft may survive a late
base move or cancellation and requires operator review; no automatic rollback
of external writes is claimed. The HTTP API still only stores job lifecycle data.
