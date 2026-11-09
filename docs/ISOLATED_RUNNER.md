# Isolated runner (Phase 5)

Real isolation acceptance now **PASSES**: 16 checks, zero skips, gate exit 0 on
Docker Engine 29.9.2/Linux/amd64/cgroups v2 (2026-11-05). The reviewed base, prepared
image identity and exact build/check results are in PHASE_PROGRESS.md and
baseline/docker-resume-*. The Phase 6 two-container reproduction gate also passes.
No target code was executed on the host. Historical blocked runs remain recorded.

## Controller contract

`DockerRunner.configured(manager, settings)` consumes the Phase 4 WorkspaceManager,
the validated settings and a service-owned TargetProfile. `run(RunInput(...),
cancelled=callback)` returns RunResult with job/run/SHA/manifest/profile/input
identities, derived candidate patch digest, outcome/reason, exit code, total and
test duration, bounded redacted stdout/stderr, image/container IDs, checked effective
settings and cleanup status. It never accepts shell text or a command from an API,
model or repository. There is no host execution fallback.

The demo profile is now v4: Python 3.12, full-suite command
`python -I -B -m pytest -q --capture=no -c /opt/webguard/pytest.ini -p no:cacheprovider -p webguard_report tests`.
The image owns pytest configuration; plugin autoload is disabled. Direct output
allows controller-side bounding instead of pytest accumulating captured output.
Only pagination.py is editable for verification; tests/configuration/file sets
must remain unchanged. Existing immutable v1/v2/v3 snapshots are not rewritten:
create a new v4 job/source snapshot and prepared image. The image-owned reporter
and trusted selectors provide Phase 8 targeted/full-suite/independent results;
see VERIFICATION.md. Independent tests live in the immutable image, not repo tests.

The controller rechecks baseline and attempt ownership, file inventory/hashes and
profile identity, then constructs a regular-file-only tar in memory with a trusted
manifest. A networkless, non-root staging helper receives it through Docker cp
into a labelled Docker-managed local volume. The helper is removed before target
execution. Tests receive the volume read-only; the trusted image bootstrap verifies
its manifest and copies source to bounded writable scratch. No host directory,
credential, Docker socket or device is mounted. No source enters the image build.

`ExecutionService.execute(lease, request)` is an explicit controller integration,
not a worker polling loop or HTTP execution route. It checks stored snapshot/SHA,
state and fencing, caps run limits against remaining job deadline/output/budget,
reserves worst-case execution seconds persistently and renews the lease while
polling cancellation. Reservations are not refunded on uncertainty. Initial missing
Docker/image blocks before debit. Receipts are stored outside transferred attempts.
Only completed pass/test-failure runs with successful cleanup may record fenced
baseline/verification evidence. Infrastructure, timeout, OOM and environment errors
never establish a code bug. No automatic reproduced/verified/PR state is claimed.

## Enforced policy and outcomes

Preflight requires a Linux Docker daemon, cgroups v2, CPU/memory/swap/PID support
and seccomp. Unsupported/warning configurations fail closed. Runtime uses an
already prepared local `sha256:<64 lowercase hex>` image ID, never a mutable tag
or automatic pull. Image OS/architecture, labels/profile, user, entrypoint,
environment, working directory and absence of declared volumes are checked.

Create arguments and effective inspect documents enforce user 10001:10001,
network none, all capabilities dropped, no-new-privileges, private IPC/cgroup
namespaces, read-only root, no devices/privileged mode/binds and log driver none.
Defaults: 1 CPU, 256 MiB memory with equal total memory+swap (no extra swap), 64 PIDs,
128 MiB scratch, 16 MiB /tmp, 1 MiB shared memory, 64 KiB combined output and
30 seconds target wall time. Scratch and /tmp use size-bounded noexec/nosuid/nodev
tmpfs. Memory must exceed configured writable tmpfs plus shared memory. Controller
Docker calls have separate bounded output and 10-second timeouts. The trusted
PID 1 bootstrap also enforces target wall time if controller polling stalls;
the staging helper independently expires after 60 seconds.

Exit 0 is passed, 1 pytest test_failure, 2-5 test_environment_error; kernel OOM,
controller/image watchdog timeout, output_limit, cancellation, infrastructure_error
and preflight blocked are distinct. Unexpected exits are infrastructure failures.
Stdout/stderr are drained concurrently under a combined byte cap, sanitized and
redacted; raw Docker errors are replaced by static reason codes. Runner results
do not imply successful repair or publication.

Cleanup validates exact names, IDs and persistent owner/job/run/role labels before
removal, then confirms absence. Cancellation requests stop the target and remove
owned resources; a failed removal changes the result to infrastructure failure.
An ambiguous timed-out Docker create/copy retains its labelled source volume and
reports cleanup failure, allowing a late daemon operation to be recovered safely.
`recover()` only scans this manager's labelled resources with checked names and
age, skips locally active runs and accepts a live-job guard. ExecutionService
provides the lease guard. Quiesce other workers or supply that guard before explicit
recovery; there is no broad Docker prune or automatic unsafe startup cleanup.

The Docker client uses a temporary service-owned config with empty auth/proxy
settings rather than the user's config (which can inject proxies into containers).
DOCKER_CONTEXT and user config are ignored. Use the default local endpoint or an
operator-controlled DOCKER_HOST (unix/npipe/tcp, no userinfo/query/fragment or SSH).
TLS configuration paths are controller-only and never passed into target containers.
Product provider credentials are not inherited by the Docker process or image.

## Prepare once, execute offline

Use the existing locked Python development install described in SETUP.md. No new
Python library dependency was introduced. Six exact pure-Python wheels have been
downloaded and checked against uv.lock here; see baseline/phase5-wheel-receipt.json.
Those exact wheels were used in the now built/tested prepared image. Its immutable
ID is in baseline/phase8-image.json; the official base is Python 3.12.16 at
the digest in baseline/docker-resume-base.json.

On a machine with a supported Linux Docker engine, choose and review a genuine
immutable official Python 3.12 slim base digest. Acquire that trusted base separately;
it must already be available for the offline build. The tested base is pinned below;
the actual preparation/build commands and both build attempts are logged in
PHASE_PROGRESS.md. Always use a new build-context output directory:

```powershell
# Download only wheels; do not install target dependencies on the host.
.venv\Scripts\python.exe -m pip --isolated download --index-url https://pypi.org/simple --only-binary=:all: --no-deps --dest .tools/runner-wheels pytest==9.2.0 iniconfig==2.3.1 packaging==26.3 pluggy==1.7.0 pygments==2.21.0 colorama==0.4.6
$runnerBase = 'python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30'
$runnerProfile = .venv\Scripts\python.exe runner_image/prepare.py --wheels .tools/runner-wheels --output .tools/runner-context --base $runnerBase
if ($LASTEXITCODE -ne 0) { throw 'Image preparation rejected' }
docker build --network=none --build-arg "PYTHON_BASE=$runnerBase" --build-arg "PROFILE_DIGEST=$runnerProfile" --tag webguard-runner:prepared .tools/runner-context
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
$runnerId = docker image inspect --format '{{.Id}}' webguard-runner:prepared
if ($LASTEXITCODE -ne 0) { throw 'Image inspection failed' }
$env:WEBGUARD_ISOLATION_IMAGE = $runnerId
.venv\Scripts\python.exe runner_image/check_isolation.py
```

prepare.py requires a new output directory, exact complete wheel identities and
lock hashes, rejects symlinks/extra files, and copies only allowlisted assets into
the build context. The Dockerfile installs with no index, hashes required, no
dependency resolution and binary-only wheels. No target preparation script runs.
Configure RUNNER_IMAGE_ID in the private server .env with the resulting real local
image ID after review; never use the example placeholder or tag as runtime identity.
RUNNER_CPU_MILLIS/MEMORY_MIB/PIDS/SCRATCH_MIB/TMP_MIB/WALL_SECONDS/CONTROL_SECONDS
are operator settings, not job request inputs. RUNNER_IMAGE_ID defaults empty.

## Acceptance and trust limits

Run `runner_image/check_isolation.py`, not merely generic pytest: it returns 2
for skipped/missing isolation cases, 1 for failures and 0 only for all required
cases passing without skips. It evaluates a temporary JUnit report and prints a
JSON verdict; the actual command output is recorded under docs/baseline.
Current outcome: 16 passed, no skips, gate exit 0. The initial real run passed
15 and failed scratch exhaustion: the target correctly filled /scratch, but that
also prevented the reporter writing there. Reports now use the existing separate
size-bounded /tmp tmpfs; the rebuilt image passes all 16 with unchanged limits.
Explicit WEBGUARD_RECORD_ACCEPTANCE=1 records redacted per-run JSONL under
docs/baseline/docker-acceptance-runs.jsonl for audit. It is a controller test flag,
not an API input or target environment variable.

Real cases cover passing/failing fixtures, infinite loops, oversized output,
network denial, UID/capabilities/seccomp, read-only root/input, host file/env/socket
absence, cancellation, OOM, cgroup CPU/memory/swap/PID limits, scratch exhaustion,
owned orphan recovery, repository pytest configuration exclusion, image watchdog
and the unchanged deliberately failing demo. They must run against the actual
prepared image before enabling downstream repair/verification processing.

Containers reduce risk; they are not a complete boundary for arbitrary hostile
public code. This MVP supports only approved known repositories. Trust the host,
Docker daemon, prepared image and controller-owned filesystem; privileged host
actors or hostile Docker administrators are outside this boundary. Phase 6 used
these interfaces successfully; future image/profile/platform changes require
rerunning the real gates.

Phase 6 additionally requires `runner_image/check_reproduction.py` to exit 0.
Phase 8 requires `runner_image/check_verification.py`: all 3 real cases now pass
with zero skips on the v4 image, as do all 16 isolation checks. The exact valid
candidate is verified; negative cases demonstrate rejection, not successful repair.

Official policy references: [Docker run](https://docs.docker.com/engine/containers/run/),
[tmpfs limits](https://docs.docker.com/engine/storage/tmpfs/),
[controlled tar copying](https://docs.docker.com/reference/cli/docker/container/cp/).
