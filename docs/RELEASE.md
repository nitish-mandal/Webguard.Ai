# Phase 12 release and deferred live acceptance

Prepared timeout follow-up: [PROVIDER_TIMEOUT_DIAGNOSIS.md](PROVIDER_TIMEOUT_DIAGNOSIS.md).
The spent job timed out at repair. For a separately approved additional attempt,
the proposed limits are REPAIR_CALL_SECONDS=90, REPAIR_HTTP_TIMEOUT_SECONDS=60 and
JOB_TIMEOUT_SECONDS=420, with unchanged one-attempt limits. These proposed values
are not applied privately; both live flags stay false. The older 30/300 setup
below is the historical configuration of the consumed attempt. No second attempt
is authorized by this document or by the prepared code fix.

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

Current setup follow-up (2026-11-06): the exact approved repository is
nitish-mandal/webguard-live-demo on main. Both demo files were uploaded unchanged
in commit b5621b9be3e6b1eabdcb1798ba877016d33a6ce6. Non-secret private live
scope/image/database/workspace/budgets were populated from the block below;
credentials were preserved and both live flags remain false. GEMINI_API_KEY
is present; GEMINI_MODEL and GITHUB_TOKEN still need private setup. Follow
[the model and GitHub App walkthrough](GITHUB_APP_SETUP.md). Older statements
about an entirely deferred/unconfigured release below describe the ZIP snapshot.
Setup does not submit or authorize additional jobs.

The current release verifies the approved demo offline. Live Gemini, GitHub source
download and live draft publication remain **UNVERIFIED**. The operator explicitly
deferred the live run during Phase 12; no approval is inferred from this release,
configuration flags, a connected account or an offline simulated draft.

Phase 11 browser acceptance remains PASSED for user-confirmed dashboard job
`802d2957d6ef48d182a8b04919e34165`: two pagination failures, predefined fix verified
(original 1 pass, full suite 2 passes, patched regressions 9 passes), one simulated
offline draft. No browser re-run is claimed in Phase 12.

## Final offline verification

Use the installed/locked development environment from SETUP.md:

```powershell
.venv\Scripts\python.exe -m pytest -m 'not isolation' -q
$env:PATH = (Resolve-Path .tools/node-v22.16.0-win-x64).Path + ';' + $env:PATH
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_release.py
```

The strict Docker gate requires all 24 existing isolation-marked cases to pass
without skips: actual boundary controls, same-commit reproduction, fake provider,
exact verification including negative patches, simulated publication/recovery,
automatic API-to-worker processing and cancellation. Missing Docker is blocked,
never host execution. This is separate from mocked tests and from live acceptance.
Record actual results in PHASE_PROGRESS.md and the public release evidence.

## Exact live prerequisites (fill privately only when resuming)

Current `.env` has local operator auth but no Gemini key/model or GitHub token;
it still approves demo-repository and both live flags are false. RUNNER_IMAGE_ID
is supplied to the running offline worker through its preserved environment and
is empty in `.env`; explicitly set it for a future fresh live process. Do not
change the working offline configuration merely to satisfy the checklist while
the live run is deferred.

The supported live target must be an **explicitly operator-approved public GitHub
copy of demo-repository**, preserving pagination.py, the original pytest node IDs
and the deliberate defect. Current service-owned v4 policy permits edits only to
pagination.py and requires its nine pagination regression checks. Acquisition
currently uses public unauthenticated GitHub reads. Arbitrary Python repositories,
private source acquisition, extra dependencies or different test layouts need a
reviewed service-owned profile/image/policy first; setting a repository name does
not implement that support. Never run its pytest/install scripts on the host.

When you decide to resume, fill these exact keys in the private root `.env`;
replace bracketed descriptions locally, never paste credentials into chat:

```dotenv
ALLOWED_REPOSITORY=owner/repository
GEMINI_API_KEY=[private Gemini API key]
GEMINI_MODEL=[operator-selected supported model with structured JSON output]
GITHUB_TOKEN=[private single-repository GitHub App installation token]
ENABLE_LIVE_GEMINI=true
ENABLE_GITHUB_DRAFT_PR=true
RUNNER_IMAGE_ID=sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3
DATABASE_URL=sqlite:///./data/phase12-live.db
WORKSPACE_ROOT=workspaces-phase12-live
MAX_MODEL_CALLS_PER_JOB=1
MAX_REPAIR_ATTEMPTS=1
MAX_PUBLICATION_ATTEMPTS=1
REPAIR_MAX_RETRIES=0
REPAIR_INPUT_BYTES=16384
REPAIR_OUTPUT_BYTES=16384
REPAIR_OUTPUT_TOKENS=2048
REPAIR_CALL_SECONDS=30
MAX_MODEL_TOKENS_PER_JOB=20000
MAX_EXECUTION_SECONDS=120
JOB_TIMEOUT_SECONDS=300
```

Keep the existing private AUTH_TOKEN; do not replace it with a provider credential.
The displayed image is the immutable image actually prepared/accepted on this
machine, not a registry tag or a promise it exists on another machine. Use
ISOLATED_RUNNER.md to prepare and validate it elsewhere. The isolated new database
and owned root preserve existing offline/browser data and prevent older queued
jobs being processed with live settings. Keep all keys outside frontend/VITE.

The GitHub token must be a short-lived `ghs_` GitHub App installation token scoped
to exactly this one repository, with Contents write, Pull requests write and
Metadata read. The adapter rejects classic/fine-grained PAT formats and broad
installation tokens. It verifies accessible-repository count/identity and remote
repository ID before writes. Token refresh/issuance is operator-owned. A configured
model name/key does not establish Gemini quota, model support or a live response.
One controller-accounted model call, zero automatic retries and bounded output/
time limits constrain the run; local cost reservation is not a provider billing
verification. No exact provider charge is claimed.

Run the local-only check, replacing owner/repository with the exact approved identity:

```powershell
.venv\Scripts\python.exe scripts/check_live_configuration.py --repository owner/repository
```

This reports only presence/validation/missing-setting names and the repository,
never credential values. It performs no network requests and grants no live
authorization. Remote repository/token scope remains unverified until the actual
live adapter check. Stale shell overrides can supersede `.env`; use fresh shells
and the reviewed Docker endpoint/image when restarting API/worker.

## One explicitly authorized live job (not run in this release)

1. Confirm the exact owner/repository, base branch and permission for **one live
   Gemini repair attempt and one draft PR** in chat, without any credentials.
2. Stop/drain the offline worker and restart API with the isolated live settings.
   Keep live worker stopped initially. Connect through the dashboard; confirm exact
   target and Live configured mode. Submit once on the approved base branch. Do
   not click Start another job. Queuing without a worker is supported.
3. From the same reviewed environment run
   `.venv\Scripts\python.exe -m worker --once` to claim at most that one queued job.
   The --once worker does not advertise a long-running session heartbeat; the UI
   can show worker unavailable while the job itself advances. Use the durable
   stage/evidence, not that heartbeat alone, to confirm this bounded run.
4. Require real GitHub source resolution/acquisition at the immutable base SHA,
   two matching Docker baseline failures and a candidate recorded with provider
   gemini. Require strict patch validation and complete same-image verification
   of that exact SHA/patch digest: original test, full original suite and independent
   regression witness/checks. Missing dependencies/timeout/collection/runner failures
   are environment outcomes, not a confirmed bug or verified repair.
5. Publication requires the still-current remote base, exact verified proof,
   scoped live token and explicit publication flag. Require one dedicated job
   branch/commit and exactly one **draft** PR. Inspect GitHub's actual PR base,
   head branch, single baseline parent and complete diff: only verified pagination.py
   edits, original tests/config/dependencies unchanged. Compare patch/evidence
   identities and reported commands/exits/counts with the worker receipts.
6. Leave the draft open for operator review. Do not merge or mark ready. Record
   the real validated PR link only after GitHub confirms it. A timeout must trigger
   marker/ref/tree/PR reconciliation before any further effect; do not submit a
   second logical job to recover uncertain acceptance. A moved base blocks until
   new pinned-baseline reproduction/verification. Cancellation cannot undo an
   already accepted draft; retain observed metadata and review it.

Resume is deferred now. The exact next step is to choose/approve that compatible
public repository/base and privately fill the settings above; then explicitly
authorize the single live run. Do not enable flags or submit live jobs on your
own while this deferral remains in effect.

## Clean source ZIP

Build and verify with:

```powershell
.venv\Scripts\python.exe scripts/build_release.py
```

Output: artifacts/WebGuard-AI-phase12-offline.zip and its .zip.sha256 sidecar.
The allowlist includes backend/worker/frontend sources, lockfiles, product and
runner tests, image preparation/controller tools, release scripts and docs. The
archive manifest records every member SHA256; entries have sorted names/fixed
timestamps, and ZIP CRC/inventory/digests and configured-secret exclusion are
verified before atomic publication of the archive. Same source/evidence produces
identical archive bytes. No raw credential or database is needed to verify it.

Excluded: `.env` and other private env files, `.tools`, virtual environments,
node_modules, frontend/dist, caches/bytecode, Git metadata, local databases and
workspaces, artifacts, private keys and raw historical diagnostic logs/receipts.
Historical results remain in PHASE_PROGRESS.md; only sanitized Phase 12 public
evidence, the preserved Phase 11 user-confirmed acceptance and immutable image
metadata are retained under docs/baseline in the ZIP. Developer-specific paths
in Markdown are replaced with portable labels. No Docker image, dependency wheel
cache or local runtime is bundled; reproduce those from locks/preparation docs.
This is an offline-verified source release candidate, not live-production acceptance.
