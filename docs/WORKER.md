# Background worker (Phase 10)

HTTP persists authenticated jobs. A separately started worker automatically claims
them and invokes the existing source, Docker reproduction, repair, verification
and draft-publication services. HTTP handlers never execute targets, models or
publication. Default demo mode is fully offline with fake Gemini/simulated GitHub.

## Startup and shutdown

Run from the WebGuard-AI root with installed Python 3.12.10 and the existing
hash-locked dependencies. API/worker must use the same private `.env`, file-backed
DATABASE_URL, WORKSPACE_ROOT, exact approved repository/profile and RUNNER_IMAGE_ID.
For the demo use ALLOWED_REPOSITORY=demo-repository, a private local AUTH_TOKEN,
ENABLE_LIVE_GEMINI=false and ENABLE_GITHUB_DRAFT_PR=false. No external key is needed.

Start the API in one terminal:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --no-proxy-headers --no-access-log
```

In a second root terminal, set those same two non-secret runtime variables and run:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
.venv\Scripts\python.exe -m worker
```

Startup prints a random JSON worker_id and labels providers offline_fake/simulated.
Submit POST /api/jobs with `{"repository":"demo-repository"}`, the private operator
Authorization bearer header and Idempotency-Key from API.md. Poll protected details
and events. HTTP 202 is durable acceptance, not a processing result. Starting a
worker does not submit a job. Never put keys in command arguments, URLs, frontend
or VITE settings, logs or evidence; no credentials are generated/printed for you.

Stop with **Ctrl+C** in the worker terminal, or from another root terminal run
the following, replacing WORKER_ID with its startup ID:

```powershell
.venv\Scripts\python.exe -m worker --stop WORKER_ID
```

This requests graceful drain: no new claims, finish the current bounded job and
cleanup, then print stopped:true and exit. The request returns drain_requested:true
and stopped_confirmed:false; actual exit/output is confirmation. Stop the API with
Ctrl+C in its terminal. To interrupt a target job instead, POST /api/jobs/{id}/cancel
with operator auth. Docker cancellation stops/removes the target. Pending source/Git
work ends within its configured timeout before its ownership check. Cancellation
cannot undo a draft an external service already accepted. Do not force-kill for
graceful shutdown; hard crashes recover through leases and maintenance.

Other local controller commands:

```powershell
.venv\Scripts\python.exe -m worker --once
.venv\Scripts\python.exe -m worker --resume JOB_ID
.venv\Scripts\python.exe -m worker --env-file path-to-private-settings.env
```

`--once` handles at most one claimable job (or exits idle). `--resume` unpauses an
unleased nonterminal job after an operator fixes setup; budgets/deadlines do not
reset. Use the same --env-file for stop/resume if startup used an alternate file.
CLI settings paths are operator-owned and are never API job inputs.

## Durable processing and recovery

Migration 7 adds job_dispatch and worker_sessions. SQLite write transactions
serialize claim, expiry, fence changes, retry timing and stop-request checks.
Multiple workers share the same database/owned root and compete for one fenced
claim; each worker processes one job at a time. A background thread renews leases
every lease_seconds/3 during blocking work. Existing services independently check
ownership before state, evidence and remote effects. Late owners cannot write.

Worker sessions heartbeat each second, expiring after 15 seconds. Public status
sets worker_available/processing_enabled/repair_enabled only for an unexpired,
non-draining worker of the configured repository. This reports worker availability,
not Docker/provider readiness. Liveness and database readiness stay separate.
WORKER_POLL_SECONDS defaults 1; WORKER_RETRY_SECONDS defaults 10.

Stages: queued Docker preflight -> pinned acquisition -> two fresh matching
baseline failures -> configured repair provider and strict validated candidate ->
Phase 8 original/full-suite/independent Docker checks -> exact verified proof ->
Phase 9 branch/PR reconciliation and draft publication. A green configured suite
records no_reproducible_bug; environment/flaky/runner failures are not bug proof.
Model edits never become commands and original target tests remain unchanged.

Restart keeps stage, SHA, deadlines, attempts and usage. An incomplete baseline
is rerun cleanly. An incomplete provider result is not a candidate; committed
candidates are reused and revalidated. Partial verification rounds cannot pass;
fresh rounds consume remaining persistent limits and reservations are not refunded.
Verified/publishing jobs reconcile existing markers/parents/trees/PRs before new
effects, without repeating repair/tests, even if Docker is temporarily unavailable.
Publication still requires exact evidence, unchanged base and existing live gates.

Transient publication failure persists next-run time and atomically releases/fences
the lease. Infrastructure/evidence/policy or unresolved publication blockers pause
the job instead of hot-looping claims. Events expose stage, safe reason, paused
flag and retry time. Paused jobs still expire at their original deadline. Missing
Docker blocks target execution with no host fallback; fix setup and --resume.
Stale base requires a new pinned job/reverification; invisible uncertain effects
remain blocked for operator reconciliation. No budget resets on restart/resume.

Cancelled/deadline-failed jobs never revive. With an unfinished publication intent,
maintenance reserves at most three persistently counted, spaced read-only lookups.
Observed draft IDs/URLs and simulated flags are saved in the intent and
terminal_publication_reconciled event while the state stays cancelled/failed.
Unresolved lookups report outcome_unknown. This path cannot create a branch/PR.

## Cleanup and evidence

Recovery reaps only the newly fenced job's old Docker resources. Periodic recovery
protects other active leases and ages uncertain CLI operations. Ownership labels
and resource policy are checked; no broad Docker prune is used. Execution copies
and abandoned partial acquisitions are removed only inside verified owned paths,
with SQLite protecting ownership against new claims during filesystem cleanup.
Current candidate copies remain for publication retry until terminal completion;
terminal attempts are removed. Sealed baselines, hashed receipts, SQLite evidence
and metadata remain for audit. Integrity/link failures retain paths for review.

Demo startup makes a separate owned Git copy of three fixed bundled files using
inert Git commands, fixed author/date, disabled hooks/signing/templates and a
sanitized environment. Its SHA is stable across restarts. The bundled fixture is
never altered/imported/run. Normal close removes the worker's fixture; maintenance
reclaims stale/stopped owners' fixtures only without active job leases. An
unregistered initializer gets a 60-second grace period. Active fixtures are protected.

## Real acceptance and limitations

```powershell
.venv\Scripts\python.exe -m pytest -m 'not isolation' -q
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_pipeline.py
```

The strict real gate requires two passing non-skipped cases: an actual worker CLI
subprocess receives an API-submitted job and completes six real Docker baseline/
verification observations plus one simulated draft, then stops through its CLI;
the second case cancels a real running target via API and checks cleanup. Product
tests separately cover competing connections/workers, expiry/fencing, renewal,
retries, tampering, abandoned fixtures, and accepted-PR restart recovery. Data-fake
lifecycle tests are not counted as real target execution. Results: PHASE_PROGRESS.md.

Live Gemini/GitHub/download remain unverified and retain the server model/key,
scoped-token and explicit flags in REPAIR.md/PUBLICATION.md. Only the default demo
is fully offline; an approved owner/repository uses the existing remote source
adapter. Target tests always have network disabled. Phase 11 now adds an operator
dashboard with real job/evidence/cancellation data; frontend and HTTP/Docker checks
pass, while browser acceptance is blocked. See DASHBOARD.md. Arbitrary hostile
repositories remain unsupported.
