# Exact-patch verification (Phase 8)

VerificationService explicitly consumes durable Phase 6 reproduction and a Phase 7
validated proposed candidate. It does not call Gemini, run targets on the host,
publish to GitHub or enable the automatic worker/API execution path. Real Docker
acceptance includes one verified fake repair and two correctly rejected bad patches.

## Required source and runtime identity

Call `VerificationService(access, execution).verify(lease, candidate_id)` with the
same approved repository/workspace/JobService used for detection and repair. The
candidate must be current for the pinned SHA and repair attempt. The verifier
reopens the sealed baseline, hashes the detection and candidate receipts, revalidates
the source edit schema/anchors/limits, and checks the proposed copy for unexpected
changes. A modified original test, candidate file, receipt, source or runtime identity
blocks verification. Exported summaries alone do not authorize verification.

Each check creates a new owned copy of the exact pinned commit. Patched checks
reapply only the validated anchored edits and compare the resulting inventory/digest
with the recorded candidate. No files/artifacts are copied from a previous test
container or attempt. Original tests remain byte-identical. Phase 5 transfer, time,
resource, network, user, read-only-root, output and cleanup controls remain enforced.
Runner receipts include the actual structured command and check selector.

Profile v4 adds service-owned check selectors and independent tests stored in the
immutable image at /opt/webguard/regressions. Full-suite command is unchanged.
Targeted checks retain its trusted Python/pytest/config/plugin prefix and replace
only the final service-owned path selector, behind `--`; arbitrary commands/options
cannot be supplied by a repository or model. The input manifest carries only a
validated selector/test ID. The image bootstrap validates the same selector policy.

Because v4 changes image/profile identity, v3 baseline/candidate jobs are not
silently relabelled. Reproduce and propose in a new v4 snapshot/job before verifying.
The real demo used the same new v4 image for both baseline runs and all verification
checks. Its Python 3.12.16 base and six locked pytest wheels are unchanged; no
dependencies are installed during target tests. The image identity is recorded in
baseline/phase8-image.json.

## Four required independent containers

| Check | Required observation for the demo |
| --- | --- |
| Unpatched regression control | All 9 new checks execute; exactly 3 full-page/page-size-one assertions fail, 6 other cases pass |
| Patched original failing test | Exact Phase 6 failing node executes and passes |
| Full original patched suite | Exact baseline test-node set executes with every setup/call/teardown passed; demo has 2 passing tests |
| Patched independent checks | All 9 execute and pass: first/second full pages, page size one, partial page, beyond end, empty input, negative page, zero/negative page size |

The three new discriminating tests fail on the unpatched baseline and pass on the
patched source. Healthy baseline cases (partial/empty/invalid handling) need not
fail before repair; they protect existing correct behavior. Independent checks are
image-owned assets and never become model edits or changes to bundled target tests.
The product testpaths exclude runner_image, so the independent target module is
never imported/executed by host product pytest. Lint/build-context checks only read
its bytes/syntax; target execution is Docker-only.

All four results must have complete bounded reports, no collection errors, no
skipped/missing/extra required nodes, all required phases, distinct run/container
IDs, successful cleanup and matching SHA/profile/source/image/patch identities.
An exit-zero result, incomplete frame or altered command alone cannot verify.
Timeout/OOM/output/runner failures, cancellation and unavailable Docker are explicit
outcomes and never evidence of repair correctness. Results and retained runner
receipts combine job and runner secret redactors before persistence.

## Durable state, retries and handoff

Migration 5 adds verification_rounds. Attempts are fenced and counted persistently
across restarts/candidates, capped by the job's existing max_repair_attempts. Each
round runs all checks from fresh baseline copies. Execution reservations and wall
deadlines remain authoritative; remaining execution time is allocated across the
remaining checks so defaults can complete all four within the persistent budget.
No reservation is refunded/reset on failure. A blocked initial Docker preflight
does not consume execution time/round count. Mid-round blockers retain an incomplete
round and can resume with a new round/copies inside the remaining limits.

Only one complete aggregate transaction can create passing verification evidence
and advance the job to verified. It binds the candidate ID, exact patch digest,
source SHA and baseline image, and checks required coverage again. Legacy raw
verification exit-zero records cannot bypass this gate or authorize publication.
Candidate proposal records remain immutable; candidates() projects status=verified
only when a matching committed verified round/evidence exists. The verification ID
is returned with that exact candidate. Other candidates remain proposed.

Failed rounds retain redacted receipts and reasons. Retry starts all checks clean;
exhausted attempts/time fail the job without verifying the candidate. Cancellation
and deadline expiration mark running rounds incomplete/failed and fence late
workers; stale owners cannot finish a round. Terminal state does not imply an
active Docker process has already stopped; the runner still stops/removes it and
records cleanup. Failed aggregate transactions cannot partially mark a candidate
verified. A completed verified candidate can be retrieved idempotently without new
test execution while the controller has the current lease.

The full receipt includes commit, patch/profile/image identity, commands, exit
codes, durations, bounded redacted stdout/stderr, per-test results and checks.
Receipt SHA256 is the durable evidence digest. Phase 9 must publish only the exact
verified SHA/patch/digest and must recheck bytes/identity; no GitHub API call or PR
creation occurred in Phase 8.

## Running acceptance

Use the newly prepared image, not the prior v3 ID:

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:RUNNER_IMAGE_ID = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_ISOLATION_IMAGE = $env:RUNNER_IMAGE_ID
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_isolation.py
.venv\Scripts\python.exe runner_image/check_verification.py
```

The Phase 8 gate requires three non-skipped real cases: valid repair, bug still
present, and previously passing invalid-input test broken. It returns 2 for skipped
Docker, 1 for failure and 0 only when all three acceptance cases pass. It exports
phase8-real-valid.json, phase8-real-bug_remains.json,
phase8-real-previously_passing_breaks.json and the hashed phase8-verification-receipt.json
under docs/baseline when the explicit controller audit flag is enabled. Negative
acceptance cases passing means their bad candidates were rejected, not repaired.

Current commands/results, exact SHA/digests and known baseline lint/warning findings
are at the top of PHASE_PROGRESS.md. The bundled demo is unchanged. No current
Docker verification blocker is present on this accepted setup; Phase 9 publication
remains to implement. Containers reduce risk for approved known repositories and
do not provide attestation against arbitrary hostile public code.
