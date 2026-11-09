# Diagnosis and prepared fix: job 53729077308847e9879b263b7d752d15

2026-11-06. No additional live request or job was made for this diagnosis. Both
live flags remain false. The consumed job and its durable budgets are unchanged.

## What the existing evidence establishes

- Configured model: gemini-3.8-flash; installed official google-genai SDK 2.34.0.
  Model identity is non-secret. No evidence establishes model access, quota,
  provider receipt, generated content or provider billing for this request.
- Original REPAIR_CALL_SECONDS=30. The child constructed HttpOptions.timeout=30000
  milliseconds, with HttpRetryOptions.attempts=1 and trust_env=false. The installed
  SDK explicitly converts this to 30 seconds for HTTPX. It is an HTTP request
  timeout, not an additional allowance beyond the controller wall clock.
- The controller independently allowed the child process 30 seconds, including
  imports, client setup, request, response handling and IPC. The HTTP timer starts
  later inside that same process, so identical 30-second values leave no allowance
  for startup/finishing. This is a confirmed timeout-budget layering problem;
  it does not identify the source of the observed latency.
- The model-call reservation event was at 1793948233.852138; repair_rejected was
  at 1793948263.8664086: **30.014 seconds** later, reason provider_timeout.
  The absolute job deadline was 1793948518.7205596: **284.868 seconds remained**
  at reservation. Thus the 300-second job deadline was not the limiting budget.
  RepairService uses min(call timeout, remaining job deadline), not an independent
  longer repair-stage allowance. Lease/cancellation checks remain active.
- One controller model-call reservation and no retries. The 5461 stored model
  tokens are a reservation, not measured generated/billed tokens. Two Docker
  baseline failures had already reproduced the original assertion. No candidate,
  verification or publication evidence exists.

Sources: [original run](PHASE12_LIVE_RESULT.md),
[saved run receipt](baseline/phase12-live-run.json), the persisted job events,
and the original worker/model_call.py and worker/repair_providers.py behavior.
The SDK timeout convention is also documented in the
[official SDK reference](https://googleapis.github.io/python-genai/genai.html).

## Did the request reach Gemini?

**Not established.** The controller reserved a call and entered its live-provider
subprocess path. The old code emitted no startup/SDK/HTTP stage telemetry and
discarded raw SDK exceptions. Saved worker stderr is empty and no usable provider
response, HTTP status or provider acknowledgement was recorded. Neither an empty
stderr nor a reserved call proves remote receipt. The evidence cannot separate
startup/import delay, local networking/TLS, provider latency, model reasoning,
quota/auth problems or a request still in flight when the controller stopped it.
Do not attribute this failure to any one of those causes or claim the key/model
worked. No extra call was used to investigate them.

The old code had no explicit thinking configuration. There is no evidence that
thinking caused the delay, so this fix does not change model, thinking, sampling
or output budget by guesswork.

## Prepared code changes

- Added validated REPAIR_HTTP_TIMEOUT_SECONDS (default 15, range 1..110) as an
  independent cap; default whole-process limit remains 20 for existing installs.
- Start the monotonic outer deadline before child creation, pass its absolute
  value to the child, reject a late completion, and recompute the HTTP timeout
  after SDK/client initialization. Effective HTTP milliseconds are the lesser of
  the configured cap and 80% of remaining process time. An exhausted deadline
  prevents a new SDK call. The hard controller deadline still terminates a hung
  provider. HTTPX timeouts apply to HTTP operations; the outer wall clock remains
  the aggregate bound even if several operations each consume time.
- Keep SDK attempts=1, controller retry/call budgets, disabled tools, minimal
  environment, patch policy and output limits. No dependency or lock change.
- Added closed, bounded stage telemetry: child main reached, SDK invoked, local
  HTTP request prepared, HTTP response/status received, SDK timeout/error and
  response ready. Only fixed booleans, integer HTTP status/elapsed milliseconds
  and a fixed timeout-origin code can persist with a repair rejection. Exception
  messages, URLs, headers, payloads, API keys and model/source text are excluded.
  Unknown/malformed stderr still causes failure and is never stored as diagnostics.
  A local request-prepared event does not prove remote receipt; an HTTP response
  is stronger evidence. No retrospective stage data was invented for the old job.

Code: backend/app/settings.py, backend/app/jobs.py, worker/model_call.py,
worker/repair_providers.py, worker/provider_observations.py, worker/repair.py.
Tests: worker/tests/test_provider_deadlines.py and the existing SDK contract test
in worker/tests/test_repair.py. Documented default in .env.example.

## Proposed settings for a separately approved additional attempt

These are **proposed, not applied to private .env or running services**:

```dotenv
REPAIR_CALL_SECONDS=90
REPAIR_HTTP_TIMEOUT_SECONDS=60
JOB_TIMEOUT_SECONDS=420
ENABLE_LIVE_GEMINI=false
ENABLE_GITHUB_DRAFT_PR=false
```

Keep the selected model and existing one-call/one-repair/one-publication limits,
REPAIR_MAX_RETRIES=0, output cap, immutable runner image and repository scope.
MAX_EXECUTION_SECONDS=120 can stay: baseline reserves 2x30 seconds; verification
explicitly divides the remaining 60 seconds over its four required checks (15
seconds each). It is not six unconditional 30-second reservations. These limits
bound work; none guarantees provider response or successful verification.

One new live job requires explicit additional approval after reviewing these
results. It must use a fresh idempotency key and preserve the original failed
job/budgets/evidence. Recheck main's SHA, token validity/scope and Docker before
the new job; enable flags only for that authorized execution and restore them
afterward. Do not rerun the spent one-shot controller or delete its receipt.

## Mocked verification

Focused tests cover the independent cap, remaining-deadline clipping after client
setup, exhausted deadlines without SDK invocation, startup time inside the outer
deadline, HTTP response/error telemetry, secret-free errors, one HTTP attempt,
closed observation persistence and no automatic retry after the one-call limit.
The installed SDK is exercised with HTTPX MockTransport only; no real provider
is contacted. Actual results:

| Command | Result |
| --- | --- |
| .venv\Scripts\python.exe -m pytest worker/tests/test_provider_deadlines.py -q | 12 passed in 2.83s |
| .venv\Scripts\python.exe -m pytest worker/tests/test_repair.py backend/tests/test_settings.py -q | Initial existing checks: 70 passed in 27.72s |
| .venv\Scripts\python.exe -m pytest -m 'not isolation' -q | 625 passed, 24 deselected, 1 existing Starlette/httpx warning; 152.32s |
| .venv\Scripts\python.exe -m ruff check backend worker tests scripts runner_image | Passed |

Logs: baseline/provider-timeout-new-tests.log,
baseline/provider-timeout-initial-tests.log,
baseline/provider-timeout-product-tests.log. Sanitized diagnosis/check summary:
baseline/provider-timeout-diagnosis.json. No frontend or real Docker acceptance
rerun was performed for this controller-only change. Private .env retains its
30-second call and 300-second job values; the new HTTP cap defaults to 15 in
newly loaded settings until explicitly configured. Existing services were not
restarted into a proposed configuration. The failed job still has one consumed
call, no candidates/verification rounds and zero publication attempts.

The existing release ZIP remains the earlier offline snapshot. Successful live
Gemini repair, exact-patch verification and GitHub draft publication remain
UNVERIFIED. This prepared fix does not retroactively complete Phase 12 acceptance.
