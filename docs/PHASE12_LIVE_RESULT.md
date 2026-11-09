# Phase 12: one authorized live attempt, 2026-11-06

Job **53729077308847e9879b263b7d752d15** ended **failed** at **repair**:
`provider_timeout` after the configured **30-second** Gemini call limit.
The job failure reason is `model`. No candidate was accepted, no patch was
verified, and no draft PR was created. No second submission or repair retry ran.

## Scope and startup

Approved repository: nitish-mandal/webguard-live-demo, base main, pinned commit
[b5621b9be3e6b1eabdcb1798ba877016d33a6ce6](https://github.com/nitish-mandal/webguard-live-demo/commit/b5621b9be3e6b1eabdcb1798ba877016d33a6ce6).
Preflight confirmed unchanged remote main, exact original source/test blobs,
current single-repository installation-token acceptance, and the prepared image's
Docker policy. Existing API/worker processes were not running. Started fresh
loopback API against the isolated data/phase12-live.db and owned
workspaces-phase12-live root; existing data/webguard.db and accepted Phase 11
job 802d2957d6ef48d182a8b04919e34165 were preserved.

Enabled both flags for this attempt, preserving credentials and other settings.
Child processes used a minimal environment and read the root private .env;
DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine. Exact startup commands:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log --log-level warning
.venv\Scripts\python.exe -m worker --once
```

Computer Use remained blocked by Windows browser-URL policy. Submission used the
existing authenticated HTTP endpoint directly, not the browser. Exactly one
POST /api/jobs returned 202, with repository, ref=main and sha=b5621b9...;
durable idempotency key phase12-live-nitish-mandal-main-b5621b9-20261106.
No credentials appeared in command arguments/output or this evidence. The worker
CLI returned exit 0 indicating a completed controller invocation; the persisted
job outcome is failed, not a successful repair.

## Actual Docker results

Source was acquired from GitHub and pinned to the approved SHA. Two fresh attempt
copies and distinct Docker containers ran the same full original suite, using:

```text
python -I -B -m pytest -q --capture=no -c /opt/webguard/pytest.ini -p no:cacheprovider -p webguard_report tests
```

| Observation | Exit | Test call outcomes | Runner duration |
| --- | --- | --- | --- |
| Baseline 1 | 1 | 1 failed, 1 passed | 3.296s |
| Baseline 2 | 1 | 1 failed, 1 passed | 2.469s |

Both reproduced tests/test_pagination.py::test_first_page_contains_requested_count:
expected `[10, 20]`, actual `[10]`. test_invalid_page_rejected passed both times.
Failure signatures match. Setup/teardown report phases are not extra passing tests.
Both use immutable image
sha256:6ca9f94394cf7c615ef9afa021bd7da20074c5eee955bf49dc5bc757158b04d3.
All target execution stayed in Docker; bundled source and test hashes are unchanged.

## Live provider failure and publication

The live-configured Gemini provider was selected with the configured model.
Exactly one model-call reservation was made with zero automatic retries. At
30 seconds the bounded controller recorded repair_rejected/provider_timeout and
transitioned repairing -> failed. No usable model response or proposed patch was
recorded. Actual provider receipt, generated content, billable token usage and
account quota are not established by this timeout. The stored 5461 model tokens
are the controller's budget reservation, not measured provider usage.

Candidate count 0; verification-round count 0; publication attempts 0;
publication metadata and publication intent absent. No GitHub branch or draft
publication operation was attempted, so this is not an uncertain publication
timeout and there is no draft PR link. The approved single attempt is consumed;
do not reset budgets or automatically submit another job.

## Restoration and evidence

After the worker exited, stopped the owned live API process tree, restored
ENABLE_LIVE_GEMINI=false and ENABLE_GITHUB_DRAFT_PR=false, then started fresh API
and continuous worker with the same prepared image/private settings. The current
API reports mode=offline, database_ready=true, worker_available=true and both live
capability flags false. The failed job is terminal and cannot be automatically
retried by this worker. Normal worker startup is `.venv\Scripts\python.exe -m worker`;
graceful shutdown is Ctrl+C or the documented `-m worker --stop WORKER_ID` flow.

Cleanup check found **zero managed containers and zero managed volumes**. Both
baseline receipts report cleanup complete. Current .env credentials are preserved.
Sanitized detailed receipt: baseline/phase12-live-run.json; durable job/evidence in
the isolated live database and owned receipt directories. The local one-shot
controller under .tools refuses a second submission when its run receipt exists.
Existing release ZIP remains the previous offline release snapshot.

Outcome: real GitHub acquisition and Docker reproduction demonstrated; successful
live Gemini repair, exact-patch verification and live draft publication remain
**UNVERIFIED**. No further live call was made to diagnose or work around the timeout.
