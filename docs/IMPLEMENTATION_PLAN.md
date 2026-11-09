# Implementation plan

Phase 1 baseline is in PHASE_PROGRESS.md and docs/baseline. This file replaces the
missing master-prompt handoff; specifications are not implemented functionality.

| Order | Phase / work | Dependency and exit evidence | State |
| --- | --- | --- | --- |
| 1 | Inventory, separate product/demo baseline, local tools and locks | Approved runtimes; clean installs and separately recorded checks | Baseline complete; lint findings and later Docker blocker documented |
| 2 | Validated settings, exact repository allowlist, auth configuration/check, redaction | Phase 1; reject arbitrary repository/ref input and redact secrets | Complete under user Phase 2 scope; HTTP enforcement added in Phase 3 |
| 3 | SQLite jobs/events, internal idempotent creation, lease primitives, recovery and cancellation | Phase 2; restart/crash/dedup tests | Complete under Phase 2; worker loop added in Phase 10 |
| 3a | Protected HTTP job lifecycle, readiness, safe response/error models | Tested Phase 2 transactions; auth on every job route; bounded inputs/pagination | Phase 3 complete; acceptance is storage only |
| 3b | Worker orchestration and cancellation cleanup | Phase 3 API; tested leases/reaping; execution requires actual isolation | Implemented under Phase 10; background pipeline and real API/Docker acceptance |
| 4 | Repository adapter, pinned source snapshots, owned workspace/attempt copies | Phases 2-3; approved identity/SHA; bounded read-only acquisition and cleanup | Phase 4 complete; remote mocked, no target execution |
| 5 | Isolated runner and reproducible baseline classification | Phase 4 plus working Linux Docker; resource/time/output limits, no network/credentials; real boundary tests | Accepted: 16 real checks pass on recorded immutable image, zero skips |
| 6 | Reproducible bug detection (current user scope) | Phase 4 pinning + Phase 5 runner; matching assertion signatures across two fresh runs | Accepted: real temporary-Git demo reproduced at the same commit in two fresh containers; invalid-input passes twice |
| 7 | Repair providers and validated proposed fixes | Reproduced pinned SHA, relevant redacted input, strict source edits, persistent usage | Implemented; offline real gate passes; SDK contract tested, live NOT VERIFIED |
| 8 | Independent isolated candidate verification | Exact SHA/patch/image, original tests and independent baseline-regression witness | Implemented; v4 isolation 16 pass, real verification 3 pass; exact valid candidate verified |
| 9 | GitHub publication, retries and draft-PR deduplication | Passing Phase 8 proof; exactly one draft; publication failure preserves verification | Implemented; durable simulated draft accepted after real Docker verification; live protocol mocked, live publication NOT VERIFIED |
| 9b | UI job lifecycle and accessible evidence views | Stable API and verified evidence; separate verified/draft states | Implemented under user Phase 11 scope; browser acceptance blocked by Computer Use URL-policy confidence |
| 10 | Background pipeline (user Phase 10 scope) | Phase 2 claims/state/budgets + Phase 4-9 services; automatic API-to-Docker demo, cancellation and restart tests | Implemented offline; live NOT VERIFIED; job UI remains planned |
| 11 | React operator dashboard (user Phase 11 scope) | Real API data, operator auth, bounded polling, submission/evidence/cancel/simulation; frontend checks and browser/Docker acceptance | Implemented; frontend and HTTP/Docker checks pass; browser gate BLOCKED |
| 12 | Broader acceptance and delivery (confirm next user scope) | Complete remaining Phase 11 browser gate; separate mocked/real/live evidence | Conditional; live Gemini/GitHub unverified |

Current surface includes settings, migration-backed internal job services,
state/evidence gates, persistent budgets, idempotency and fenced lease primitives.
The health/status API and status UI remain. Authenticated HTTP job storage routes
now work; a separately started worker automatically processes approved jobs.
HTTP handlers remain storage-only. Approved source acquisition and
explicit Docker execution services exist; actual isolation and demo reproduction
now pass on the recorded local Linux image. Phase 7 adds offline/Gemini providers
and proposed source candidates. Phase 8 exact verification and Phase 9 explicit
draft publication are implemented; one simulated draft follows real Docker proof.
Live SDK/GitHub calls are not verified. The user's Phase 2 scope combined the
starter roadmap's settings and storage tasks; it supersedes that earlier split.
See PHASE2_STORAGE.md and API.md for contracts before integrating worker loops.
The user's Phase 3 scope is the authenticated API only, not worker orchestration.

Phase 1 used installed Python 3.12.10 for two clean hash-locked installs and
matching installed versions. Backend/worker/contracts passed separately; the demo
confirmed exactly its intended failure. Frontend lock, clean npm ci, test,
typecheck and build evidence are complete. Existing import-order lint findings
are recorded rather than folded into this bootstrap-only change.
Do not repair the demo fixture to make baseline green. A later repair must operate
on a temporary Git copy with immutable baseline tests. No public repository setup,
paid model calls, deployment or external publication is part of this phase.

