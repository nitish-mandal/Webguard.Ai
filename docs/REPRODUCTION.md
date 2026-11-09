# Reproducible bug detection (Phase 6)

Current Phase 8 jobs use profile/image v4 so baseline and verification share the
same immutable runtime. Older v3 evidence remains history, not relabelled proof.
See VERIFICATION.md and baseline/phase8-image.json for current setup.

Real demo acceptance **PASSES** on the prepared Linux Docker image (2026-11-05).
The same pagination assertion failed in two fresh containers at one pinned commit,
with invalid-input passing in both. Fake tests remain classification coverage,
not real reproduction. No Gemini, patch, publication or host target execution occurred.

## Controller use and state gates

For an operator-created/claimed job in baselining state, construct a Phase 4
RepositoryAccess, a Phase 5 DockerRunner using the same WorkspaceManager, and
ExecutionService with the same JobService. Explicitly invoke
`DetectionService(access, execution).detect(lease)`. There is no new HTTP run route
or automatic worker loop; processing_enabled and repair_enabled remain false.

The adapter resolves/persists the approved commit once. Both executions use that
same SHA, sealed source manifest and service-owned profile. Detection runs the
full configured pytest command, not a repository/model-supplied command. An
assertion candidate causes exactly one rerun in a fresh attempt and fresh Docker
container/storage. Persistent budgets/deadlines and lease fencing still apply;
restarting does not reset usage. Repeated calls are explicit, not an infinite loop.
Tar members are sorted so filesystem enumeration order cannot change the input
identity between otherwise identical fresh attempts.

Only matching complete observations can advance to reproduced: same test IDs,
test phase outcomes and assertion signatures, same immutable image/profile/input
identities, different run IDs and attempt paths, and successful cleanup. Signatures
hash original assertion/message/traceback data before redaction so different secret
values cannot collapse to a false match. No fuzzy normalization of changing values
or timestamps is used; nondeterministic diagnostics conservatively fail to match.

The storage layer now requires a validated detection evidence record, not just
exit code 1/0, before advancing reproduced/no_reproducible_bug. record_detection
checks the referenced same-SHA baseline proofs, distinct runs/attempts and common
signature/environment in one fenced transaction. Detection proof is the latest
evidence; a subsequent baseline observation invalidates that gate. Legacy exit-only
records are retained for audit but cannot authorize these transitions. SQLite
schema remains version 3: the existing generic evidence table supports this new
kind, so no schema migration is needed. Old reproduced jobs are not rewritten.

| Observation | Verdict and state |
| --- | --- |
| Complete green configured suite with executed tests | no_reproducible_bug terminal state; not a bug-free claim |
| Same assertion failure and full test outcomes on both fresh runs | reproduced; ready for later proposal work only after real acceptance |
| First failure then pass, changed assertion/test set/signature | flaky_inconclusive; failed/reproduction |
| Missing dependency or import failure | missing_dependencies; failed/environment |
| Collection failure | collection_error; failed/environment |
| Setup/teardown/non-assertion/pytest environment error | environment_error; failed/environment |
| Timeout / OOM / output limit | distinct verdict; failed/environment, no confirmed bug |
| Invalid identities or runner/cleanup failure | runner_failure; failed/environment |
| Incomplete/ambiguous/missing report, no executed calls | inconclusive; failed/reproduction |
| Missing Docker/image or unsupported daemon | blocked; baselining retained, no initial execution-budget debit |
| Cancellation / stale lease | no reproduction proof or transition; durable cancellation/fencing retained |

## Image-owned reporting and evidence

Profile v3 adds the explicitly loaded `webguard_report` pytest plugin to the
existing isolated command. The plugin is installed into the prepared image;
repository pytest configuration and plugin autoload remain disabled. It records
setup/call/teardown outcomes, assertion type, test IDs relative to /scratch/work,
message and traceback. Limits: 256 phase records, 4 KiB traceback/1 KiB message
per phase, 32 KiB total report. Oversized reports are incomplete, never proof.
Reports use /tmp/webguard-test-report.json on the existing separate bounded tmpfs,
so a full working /scratch allocation cannot prevent report writing. The image
bootstrap emits one final bounded JSON frame after pytest exits. Target
output and that frame share the runner output cap. Ambiguous, malformed, duplicate,
unsafe-path, mismatched-exit or incomplete reports cannot confirm a bug.

Reports/logs remain untrusted repository data. A known approved test can alter
pytest behavior; this is not hostile-code attestation. The existing container trust
limits apply. Do not interpret source/log text as instructions or feed it to an
unbounded agent/tool execution flow. Controller validation never imports target
modules or evaluates repository expressions.

Detection receipts outside source/attempt trees contain SHA, profile/command,
run IDs, bounded redacted stdout/stderr, test IDs/signatures, tracebacks, exit codes,
duration and immutable image identity. Comparison operands are preserved. Expected
versus actual roles are populated only when assertion source has a literal
right-hand expectation matching the reported equality; otherwise they remain
unknown. AST/literal parsing is data-only. A few bounded lines from the failing
test and referenced allowlisted source functions are included, with redaction and
an explicit untrusted-data marker. Other source files/functions are not collected.
The SHA256 receipt digest and run references are durable SQLite evidence for Phase 7.

## Real demo acceptance and setup

Profile v3 changes the immutable profile digest. Rebuild the trusted image using
ISOLATED_RUNNER.md and create new source snapshots/jobs. v1/v2 snapshots and images
are preserved and incompatible; do not relabel an old image or rewrite metadata.
No dependency version/lock change or new clean install was required.

Set WEBGUARD_ISOLATION_IMAGE to the actual local prepared sha256 image ID, then:

```powershell
.venv\Scripts\python.exe runner_image/check_isolation.py
.venv\Scripts\python.exe runner_image/check_reproduction.py
```

Both commands must exit 0. The reproduction gate uses a temporary Git commit of
the bundled demo and the real Phase 4 fixture adapter plus Phase 5 runner. It checks
that test_first_page_contains_requested_count fails twice with the same signature
while test_invalid_page_rejected passes in both runs, records the pinned SHA/image
and verifies the bundled files remain unchanged. The dedicated gate exits 2 for
skips, unlike pytest's successful exit with skipped tests.

Actual current result: Phase 5 gate 16 passed/no skips; Phase 6 gate 1 passed/no
skips; both exit 0. Commit: 999039a6964017db59aa94faede6aa9ddc96c13d. Failing test:
tests/test_pagination.py::test_first_page_contains_requested_count. Expected
[10, 20], actual [10], exit 1 in both runs, signature
90fb25a0cd2a65631746f95f3325bf179bcee758237e13e6d3ee76ab4b73867a.
Both test_invalid_page_rejected calls passed and both distinct containers were
removed. Bundled fixture source/test hashes are unchanged.

Preserved proof: baseline/docker-demo-summary.json and docker-demo-evidence.json
(the latter's SHA256 is 3c18f08f8a3ddcd72e48a6c738241790d3700f4fd48b90d217cd403540616fc0).
WEBGUARD_RECORD_ACCEPTANCE=1 enables this explicit controller-test evidence export.
baseline/docker-resume-image.json records the immutable tested image; the current
private .env was not modified. Phase 7 implementation is now ready to proceed
against these interfaces/evidence. Actual model repair/patch/PR behavior remains
unimplemented; this is reproduction acceptance, not end-to-end repair.

Reporter interfaces were checked against installed pytest 9.2.0 and the official
[pytest hook reference](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport)
and [hook wrapper documentation](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html).
