# Phase 2 controller contracts

`backend.app.settings.load_settings()` loads `.env` then overrides recognized
fields from the process environment. Missing external credentials are valid
with live flags off. Invalid settings raise a safe SettingsError without values.
Secret fields are excluded from repr/dumps. The redactor removes configured
secrets, credential-bearing URLs, bearer tokens, common provider-token formats
and sensitive metadata keys before persistence. Arbitrary unknown secrets cannot
be reliably inferred; adapters must also select and bound the data they submit.
Do not log raw configuration, raw ValidationError.errors(), target logs or model
responses. Keep the controller database and backups private to the operator.

`JobService(settings)` is a trusted internal service, not a public API. It uses a
new SQLite connection per operation, foreign keys, a 10-second busy timeout and
BEGIN IMMEDIATE for mutations. SQL values are bound parameters. Mutations,
version increments and ordered append-only events commit or roll back together.
No target code, model call, network request or publication runs in this service.

Methods:

- `create(key, repository, ref='main', sha=None)`, `get(id)`,
  `list_jobs(limit=50, after=(created_at, id))`, `events(id, after=sequence, limit=50)`.
  Keys and normalized payloads are hashed. A unique key constraint plus serialized
  create transaction prevents duplicate jobs; changed input conflicts. Identical
  retries return the existing current job, including terminal jobs. Payload fields
  are restricted to the approved repository and validated ref/full SHA.
- `claim(owner)`, `renew(lease)`, `release(lease)`, `expire()`.
  Claims atomically select one approved nonterminal job with no valid lease.
  Recovery retains state and all counters. Every new claim/release/terminal outcome
  changes a monotonically increasing fence. All worker mutations require the
  current owner/fence and a live lease before the immutable job deadline. Reusing
  a worker name does not revive an old lease. Deadlines and claim exhaustion
  produce typed terminal failures. A future scheduler must periodically call
  expire(); claims also do so. Read-only retrieval does not run a reaper.
- `advance(lease, state, expected_version=None, failure_reason=None)`,
  `pin_revision(lease, sha)`, `cancel(id)`. Optional expected_version provides
  optimistic concurrency in addition to mandatory fencing. Cancellation immediately
  becomes terminal and invalidates ownership; repeated cancellation is idempotent.
  Cancelling another terminal outcome conflicts. With no executor yet, there is
  no subprocess to clean up; future runners must enforce cancellation externally.
- `reserve_usage(lease, model_calls=0, model_tokens=0, cost_micros=0,
  execution_seconds=0)`. Reserve worst-case usage before doing work. Reservations
  cannot be refunded or reduced. Limits, counters, repair/publication attempts,
  output/patch limits and the absolute deadline are persisted per job. Restarting
  with increased configuration does not increase an existing job's budget.
  Model reservations require repairing state; test time requires baseline/verify
  state. BudgetExceeded rolls back the operation; the controller must stop work
  or explicitly fail the job with `budget_exhausted`. No paid calls exist yet.
- `add_evidence(...)`, `evidence(id, limit=50, after=row_cursor)`.
  Evidence is bounded, redacted metadata with SHA256 artifact/patch digests and
  a pinned commit SHA. Actual artifact files and container attestations are later
  work. Baseline pytest exit 1 is required for reproduction, exit 0 for no bug.
  Verification proof must be exit 0 for the current repair attempt and pinned SHA;
  an old attempt's successful record cannot authorize verification/publication.
- `set_publication(lease, branch, pr_number=None, draft=True)`, `publication(id)`.
  Only publishing state can record metadata; branch, SHA, patch digest and an
  assigned PR number are immutable. URLs are derived from approved repository
  and PR number, never accepted as arbitrary input. Branch intent may be stored
  before a future external call. Metadata tests use synthetic records; they do
  not verify any real GitHub branch or PR.

State graph (defined once in backend/app/domain.py; worker re-exports JobState):

```text
queued -> baselining -> reproduced -> repairing -> verifying -> verified
                  \-> no_reproducible_bug          |             |
                                                  -> repairing   -> publishing
                                                       retry        |       |
                                                       bounded      |       -> draft_pr_created
                                                                    -> verified (publication retry)
```

Any nonterminal state may fail or be cancelled. Terminal states cannot be reopened.
Verified is nonterminal and distinct from draft_pr_created. Entering repairing
and publishing consumes bounded attempt counts. Publication retry preserves the
successful verification evidence and does not start another repair. Failure
reasons are a fixed enum, not raw exception text. Timestamps/deadlines use UTC Unix
seconds; injected clocks are for deterministic tests only. Controller clocks must
be synchronized for lease correctness across processes.

Phase 3 now exposes authenticated job lifecycle routes and public probes; see
API.md. Internal hash/lease fields are not public response fields. Worker
orchestration and genuine isolation tests remain necessary before any repair
functionality can be claimed. SQLite is intended for one local
operator on a local disk, not a multi-host/shared-network database deployment.
