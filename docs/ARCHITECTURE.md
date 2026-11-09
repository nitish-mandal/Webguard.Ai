# Architecture and phased implementation history

Phase 11 adds React -> operator bearer API -> durable job/report/events views.
The UI submits/cancels only through existing protected mutations; a separately
started worker owns source/model/Docker/publication work. A new protected read-only
report projects bounded redacted receipt/verification metadata and exact validated
live PR links. Provider credentials never enter the UI. Polling is bounded and
stops per terminal job/page close. Software and real HTTP/Docker checks pass;
browser acceptance is blocked by Computer Use's Windows URL-policy confidence.
Current UI contracts and startup/checklist: DASHBOARD.md.

Current boundary: a separately started worker polls and connects the source,
Docker, detection, repair, verification and publication services. HTTP handlers
remain storage-only. Phase sections retain the history; see WORKER.md for Phase 10.

React UI -> authenticated FastAPI API -> SQLite jobs/events -> polling worker.
Worker -> repository adapter -> pinned baseline -> isolated test runner ->
reproduction evidence -> Gemini proposal -> patch validator -> clean verification
runner -> evidence bundle -> GitHub branch and draft PR.

The trusted controller holds credentials. The target test container has no
credentials, network, host mounts, Docker socket or privileged access. Prepared
dependencies are built separately through a controlled trusted process. Model
context contains bounded, redacted relevant source/log data; repository content
is untrusted data, never controller instructions. The model returns structured
edits; it cannot directly execute commands or publish anything.

Persist immutable job ID, exact repository/ref/SHA, config version, timestamps,
attempts, leases, state, baseline and verification exits, artifact digests, errors,
branch and PR identifiers. Persist append-only bounded events and redact secrets.
Claim jobs atomically, heartbeat leases, recover crashes without duplicate PRs,
and record cancellation. Verification and publication are separate states.

Proposed API: POST /api/jobs (202, idempotency key), GET /api/jobs/{id},
GET /api/jobs/{id}/events, POST /api/jobs/{id}/cancel. Reject arbitrary URLs,
commands and repo names. Existing routes remain available; replace the explicit
501 only when durable acceptance exists. The implemented API is storage-only:
202 never implies processing. Actual execution still requires orchestration and
a verified isolation boundary. Isolation is now implemented and accepted; automatic
orchestration remains planned.

Use worker.pipeline.JobState as the initial vocabulary. Failures carry typed
reason codes (environment, reproduction, model, patch, verification, publishing).
Verification is valid only for the exact baseline SHA and patch digest tested.
Publication failures retain verified evidence and retry only publication.

## Phase 2 implemented boundary

Validated settings and SQLite internal services now implement the controller's
storage/state/lease/budget layer. See PHASE2_STORAGE.md for transactions, schema,
evidence gates and recovery contracts. main.py initializes them during lifespan;
no polling worker or accepting job route is enabled. All runner/model/GitHub
arrows above are still target architecture, not operational integrations.
## Phase 3 implemented boundary

The authenticated storage API now connects to the Phase 2 service layer. POST
jobs commits before 202; reads/events/cancellation require the same local bearer
flow. Public liveness and current DB readiness are distinct. See API.md for v1
models, errors, authentication and pagination. No HTTP request calls the worker;
all runner/model/GitHub arrows remain planned architecture.
## Phase 4 implemented boundary

Explicit controller call -> approved GitHub or local-fixture adapter -> immutable
commit pin -> bounded committed-source acquisition -> owned baseline + canonical
manifest/profile digests -> independent attempt generations. SQLite migration 3
persists one source_snapshots record per job and an atomic source_acquired event.
Reopen verifies the same pinned baseline; it does not resolve a moved ref again.

Remote reads use public HTTPS API/tree metadata and a bounded codeload archive,
not an unconstrained clone/checkout. Local fixtures use read-only Git object
plumbing. Source modes, paths, sizes and content IDs are validated before sealing.
No hooks, repository instructions, install/test commands or model calls run.
See SOURCE_ACCESS.md for resource limits, profile, ownership and cleanup contracts.

HTTP handlers and worker.run_job do not invoke this layer automatically. The
model/GitHub-publication arrows remain unimplemented; source access is not isolation.

## Phase 5 implemented boundary; real isolation accepted

Explicit fenced ExecutionService -> Phase 4 sealed snapshot/attempt validation ->
trusted controller tar -> Docker-managed owned volume through a bounded helper ->
helper removal -> immutable prepared image with read-only input/offline non-root
pytest in bounded tmpfs -> classified redacted receipt -> fenced evidence.
The trusted controller, SQLite, baseline and credentials remain outside the target.
No bind mounts, host execution fallback or HTTP execution route is introduced.

Docker preflight and effective container inspection fail closed on unsupported
Linux/cgroups/security/resource configurations. Cancellation/timeout/output limits
stop owned containers; cleanup validates ownership and confirms removal. Explicit
age/lease-aware recovery handles orphans and ambiguous daemon operations without
pruning unrelated resources. Persistent execution reservations survive restarts.
Only successful cleanup plus pytest pass/test-failure may yield evidence; runner
failure is not evidence of a code bug. Verification and PR creation stay distinct.

Image preparation is separate and uses reviewed immutable base identity plus
hash-verified wheels; tests never install dependencies or access a network. Profile
v2 ignores repository pytest configuration and bounds direct output. Details:
ISOLATED_RUNNER.md. Actual image build/identity, kernel enforcement and cleanup
now pass on the recorded immutable image: the strict gate exits 0 with 16 real
cases passed and zero skips. Initial scratch exhaustion exposed report allocation
sharing; report storage now uses the separate bounded /tmp tmpfs, with unchanged
container controls. Automatic worker processing remains disabled.

## Phase 6 detection boundary; real demo reproduction accepted

Explicit DetectionService -> Phase 4 pinned source -> two fresh attempts through
ExecutionService/DockerRunner -> image-owned pytest report -> strict complete-report
validation and assertion signatures -> matching same-SHA/image/input observations
-> durable detection evidence -> guarded reproduced/no_reproducible_bug state.
Other verdicts remain flaky/inconclusive or specific environment/runner failures.
Cancellation and lost fencing cannot publish a reproduction conclusion.

Profile v3 installs an explicitly loaded trusted pytest reporter; old images and
snapshots must not be relabelled. Logs/report text remain untrusted and bounded,
with secret redaction before persistence. Signatures derive from pre-redaction
diagnostics; limited relevant snippets and receipt digests form the Phase 7 handoff.
Legacy exit-only evidence no longer permits a reproduced/no-bug transition.
See REPRODUCTION.md. No HTTP execution or automatic worker loop was added. Docker
is running; the real two-run temporary-Git demo gate now exits 0. Same SHA,
signature and failed test, expected [10, 20]/actual [10], with invalid-input passing
in both fresh containers. Receipts and current setup are in PHASE_PROGRESS.md.
No Gemini, patch or publication path was invoked.

## Phase 7 proposed-source boundary

Explicit RepairService -> fenced reproduced SHA and hashed Phase 6 receipt ->
relevant redacted snippets/diagnostic JSON -> bounded offline or opt-in official
Gen AI SDK child -> strict proposal schema -> path/anchor/syntax/patch validation
-> fresh pinned attempt -> canonical patch digest -> migration-4 proposed candidate
and receipt. Provider text never becomes a controller command. SDK credentials
stay outside the target and out of persisted metadata. Each bounded retry reserves
persistent usage first; stale owners cannot write a candidate.

The real Docker reproduction -> fake proposal gate passes; live SDK calls remain
unverified. State stays repairing/status proposed until Phase 8 independently
checks/executes the exact candidate inside Docker. No post-patch target execution,
automatic worker or publication was added. Details: REPAIR.md.

## Phase 8 exact verification boundary

VerificationService -> hashed reproduced/candidate receipts -> sealed pinned
baseline -> clean reapplication/digest comparison -> unpatched regression control
and patched original/full-suite/independent checks in four fresh Docker containers
-> complete same-image/SHA/patch/test-coverage aggregate -> transactional verified
evidence and candidate projection. Original source tests/command are preserved;
new selectors and regression tests are trusted immutable image assets (profile v4).

Migration 5 persists bounded verification rounds, retries and interrupted outcomes.
Missing/skipped/changed/incomplete results cannot verify. Only matching committed
aggregate evidence permits verified/publication state gates; a bare exit-zero
record cannot. Budgets/deadlines/fencing survive restarts, and target artifacts do
not cross copies. Real acceptance passes valid, bug-remains and healthy-test-break
cases; GitHub publication stays for Phase 9. See VERIFICATION.md and current
PHASE_PROGRESS.md for exact identities/results.

## Phase 9 verified draft publication boundary

Explicit PublicationService -> current uncancelled verified job and hashed Phase 8
aggregate -> revalidate/reconstruct exact source bytes from clean pinned copy ->
durable immutable publication intent -> authorize exact repository scope -> check
remote base -> reconcile job branch/PR -> bounded Git database tree/commit/ref
writes and draft PR -> final base check -> atomic metadata and draft state.

Migration 6 stores intents and in-flight effects before network writes. Remote
marker/parent/tree/PR lookup reconciles uncertain acceptance and failed local
transactions without repeating repair or verification. Mutation budgets persist;
unknown invisible outcomes block. Verification survives failures. Cancellation
and lease fencing guard effects/writes. A late remote base race can leave an
external draft but blocks local completion and preserves its observed ID.

Offline uses a separate durable deterministic fake remote, labelled simulated.
Its demo follows real Docker verification and records exactly one fake draft.
Live REST uses only api.github.com and a single-repository installation token,
server-side, with explicit opt-in; live publication remains NOT VERIFIED. No
automatic worker, HTTP publishing route or merge operation was enabled. See
PUBLICATION.md for contracts, setup and race/visibility limits.

## Phase 10 background orchestration

API storage -> SQLite queued job -> worker atomic claim/lease heartbeat -> source,
reproduction, repair, exact verification and draft services -> persisted terminal
outcome. Migration 7 adds durable dispatch/retry timing, paused blockers and
worker session/drain records. Existing evidence gates remain authoritative; no
handler executes a job. Status availability comes from live worker heartbeats,
not a promise of Docker/provider readiness.

Restart keeps SHA, state, counters and deadlines; incomplete evidence never
verifies. Publication resumes by remote lookup before effects. Cancellation/
deadline outcomes stay terminal while bounded read-only lookups record any
already accepted draft. Owned generation cleanup retains sealed audit evidence.
The offline API/actual-worker/Docker demonstration and real cancellation gate
pass. Live Gemini/GitHub remain unverified. Contracts and commands: WORKER.md.
