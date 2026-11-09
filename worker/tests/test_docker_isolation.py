"""REAL isolation acceptance. Never execute these target snippets on the host."""

import json
import os
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from worker.docker_client import DockerCLI, DockerFault
from worker.docker_policy import create_arguments, labels, resource_name
from worker.docker_runner import DockerRunner
from worker.runner_models import Outcome, RunInput, RunnerLimits
from worker.source_common import Budget
from worker.workspaces import DEMO_PROFILE, WorkspaceManager

pytestmark = pytest.mark.isolation


@pytest.fixture
def real(tmp_path):
    client = DockerCLI()
    if client.executable is None:
        pytest.skip('ISOLATION ACCEPTANCE BLOCKED: Docker CLI unavailable; no host fallback')
    try:
        client.document(['info', '--format', '{{json .}}'])
    except DockerFault as error:
        pytest.skip(f'ISOLATION ACCEPTANCE BLOCKED: {error.code}; no host fallback')
    image_id = os.environ.get('WEBGUARD_ISOLATION_IMAGE')
    if not image_id:
        pytest.skip('ISOLATION ACCEPTANCE BLOCKED: WEBGUARD_ISOLATION_IMAGE must be a prepared immutable image ID')
    manager = WorkspaceManager(tmp_path / 'owned')
    limits = RunnerLimits(memory_mib=128, scratch_mib=32, tmp_mib=8, wall_seconds=15)
    runner = DockerRunner(manager, image_id, limits, client=client)
    try:
        runner.preflight()
    except DockerFault as error:
        if error.code == 'unsupported_daemon':
            pytest.skip('ISOLATION ACCEPTANCE BLOCKED: Linux cgroups v2/resource controls required')
        raise  # A configured but invalid image/policy must fail, never silently skip.

    original_run = runner.run

    def audited_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
            # Explicit operator-only audit flag; no repository/API-controlled output path.
            audit = Path(__file__).resolve().parents[2] / 'docs/baseline/docker-acceptance-runs.jsonl'
            with audit.open('a', encoding='utf8') as stream:
                stream.write(json.dumps(result.document(), sort_keys=True) + '\n')
        return result

    runner.run = audited_run

    def request(test_code, extra=None):
        workspace = manager.create(uuid.uuid4().hex)
        root = manager.path(workspace) / 'baseline'
        (root / 'tests').mkdir()
        (root / 'pagination.py').write_text('VALUE = 1\n', encoding='utf8')
        (root / 'tests/test_case.py').write_text(test_code, encoding='utf8')
        for name, data in (extra or {}).items():
            target = root / name
            target.parent.mkdir(exist_ok=True, parents=True)
            target.write_bytes(data)
        workspace = manager.seal(workspace, 'd' * 40, DEMO_PROFILE, Budget(5))
        return RunInput(workspace, manager.create_attempt(workspace, 1, Budget(5)))

    yield runner, request
    assert all(runner.recover(min_age_seconds=0).values())


@pytest.mark.parametrize('success', [True, False])
def test_real_passing_and_failing_pytest(real, success):
    runner, request = real
    result = runner.run(request(f'def test_result(): assert {success}\n'))
    assert result.outcome == (Outcome.PASSED if success else Outcome.TEST_FAILURE)
    assert result.exit_code == (0 if success else 1)
    assert result.cleanup_complete and result.image_id == runner.image_id
    assert result.container_id and result.input_digest


def test_real_nonroot_no_capabilities_and_no_new_privileges(real):
    runner, request = real
    code = '''
import os
from pathlib import Path

def test_identity():
    assert os.getuid() == os.getgid() == 10001
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert int(status['CapEff'].strip(), 16) == 0
    assert status['NoNewPrivs'].strip() == '1'
    assert status['Seccomp'].strip() == '2'
'''
    assert runner.run(request(code)).outcome == Outcome.PASSED


def test_real_external_network_denied(real):
    runner, request = real
    code = '''
import socket
import pytest

def test_network():
    with pytest.raises(OSError):
        socket.create_connection(('1.1.1.1', 443), timeout=0.3)
'''
    assert runner.run(request(code)).outcome == Outcome.PASSED


def test_real_readonly_root_input_and_writable_bounded_scratch(real):
    runner, request = real
    code = '''
import errno
from pathlib import Path
import pytest

def test_filesystem():
    with pytest.raises(OSError) as error:
        Path('/opt/webguard/readonly-probe').write_text('forbidden')
    assert error.value.errno == errno.EROFS
    with pytest.raises(OSError):
        Path('/input/source/pagination.py').write_text('forbidden')
    with pytest.raises(OSError) as source_error:
        Path('/input/source/pagination.py').chmod(0o600)
    assert source_error.value.errno == errno.EROFS
    Path('/scratch/allowed').write_text('allowed')
    Path('/tmp/allowed').write_text('allowed')
    assert not Path('/var/run/docker.sock').exists()
'''
    assert runner.run(request(code)).outcome == Outcome.PASSED


def test_real_host_files_and_credentials_are_unavailable(real, tmp_path):
    runner, request = real
    host_file = tmp_path / 'host-only-secret'
    host_file.write_text('host-only-value', encoding='utf8')
    code = '''
import os
from pathlib import Path

def test_host_boundary():
    assert not Path(HOST_PATH).exists()
    assert not Path('/host').exists()
    for key in ('AUTH_TOKEN', 'GITHUB_TOKEN', 'GEMINI_API_KEY', 'DOCKER_HOST', 'AWS_SECRET_ACCESS_KEY'):
        assert key not in os.environ
'''.replace('HOST_PATH', repr(str(host_file)))
    result = runner.run(request(code))
    assert result.outcome == Outcome.PASSED and not result.effective_settings['host_bind_mounts']


def test_real_infinite_loop_timeout_and_cleanup(real):
    runner, request = real
    runner.limits = replace(runner.limits, wall_seconds=2)
    result = runner.run(request('def test_loop():\n    while True: pass\n'))
    assert result.outcome == Outcome.TIMEOUT and result.cleanup_complete
    assert result.exit_code is not None


def test_real_oversized_output_stops_and_removes_container(real):
    runner, request = real
    runner.limits = replace(runner.limits, output_bytes=4096)
    code = 'def test_output():\n    while True: print("x" * 4096, flush=True)\n'
    result = runner.run(request(code))
    assert result.outcome == Outcome.OUTPUT_LIMIT and result.cleanup_complete
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 4096
    assert result.output_truncated


def test_real_cancellation_of_running_target_and_cleanup(real):
    runner, request = real
    item = request('import time\ndef test_wait():\n    time.sleep(60)\n')
    event = threading.Event()
    results = []
    thread = threading.Thread(target=lambda: results.append(runner.run(item, event.is_set)), daemon=True)
    thread.start()
    running = False
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and thread.is_alive():
            with runner.lock:
                active = list(runner.active)
            if active:
                target = resource_name(runner.manager.owner, active[0], 'test')
                info = runner.client.inspect('container', target, optional=True)
                if info and info.get('State', {}).get('Running'):
                    running = True
                    break
            time.sleep(0.05)
        assert running, 'Target never became running; this is not a cancellation pass'
        event.set()
        thread.join(timeout=60)
        assert not thread.is_alive()
        assert results[0].outcome == Outcome.CANCELLED and results[0].cleanup_complete
    finally:
        event.set()
        thread.join(timeout=60)


def test_real_kernel_oom_is_distinct_from_assertion_failure(real):
    runner, request = real
    code = 'def test_oom():\n    blocks=[]\n    while True: blocks.append(bytearray(8 * 1024 * 1024))\n'
    result = runner.run(request(code))
    assert result.outcome == Outcome.OOM and result.cleanup_complete
    assert result.exit_code != 1


def test_real_effective_memory_cpu_pid_and_scratch_limits(real):
    runner, request = real
    code = '''
import os
from pathlib import Path

def test_cgroups():
    root = Path('/sys/fs/cgroup')
    assert int((root / 'memory.max').read_text()) == 128 * 1048576
    assert int((root / 'memory.swap.max').read_text()) == 0
    assert int((root / 'pids.max').read_text()) == 64
    quota, period = (root / 'cpu.max').read_text().split()
    assert int(quota) / int(period) == 1
    assert os.statvfs('/scratch').f_blocks * os.statvfs('/scratch').f_frsize <= 32 * 1048576
    assert os.statvfs('/tmp').f_blocks * os.statvfs('/tmp').f_frsize <= 8 * 1048576
'''
    result = runner.run(request(code))
    assert result.outcome == Outcome.PASSED
    assert result.effective_settings['pids'] == 64
    assert result.effective_settings['memory_bytes'] == 128 * 1048576
    assert result.effective_settings['nano_cpus'] == 1000000000
    assert result.cleanup_complete


def test_real_scratch_space_exhaustion_is_bounded(real):
    runner, request = real
    code = '''
import errno

def test_scratch_limit():
    written=0
    with open('/scratch/fill', 'wb', buffering=0) as stream:
        try:
            for _ in range(64):
                written += stream.write(b'x' * 1048576)
        except OSError as error:
            assert error.errno == errno.ENOSPC
        else:
            assert False, 'scratch was not bounded'
    assert written <= 32 * 1048576
'''
    result = runner.run(request(code))
    assert result.outcome == Outcome.PASSED, result.document()


def test_real_orphan_recovery_uses_ownership_and_removes_owned_resources(real):
    runner, _ = real
    owner, job, run = runner.manager.owner, uuid.uuid4().hex, uuid.uuid4().hex
    volume = resource_name(owner, run, 'source')
    args = ['volume', 'create', '--driver=local']
    for key, value in labels(owner, job, run, 'source').items():
        args += ['--label', f'{key}={value}']
    runner.client.command([*args, volume])
    runner.client.command(create_arguments(runner.image_id, owner, job, run, 'stage', volume, runner.limits))
    runner.client.command(['container', 'start', resource_name(owner, run, 'stage')])
    assert runner.recover(min_age_seconds=0) == {run: True}
    assert runner.client.inspect('volume', volume, optional=True) is None
    assert runner.client.inspect('container', resource_name(owner, run, 'stage'), optional=True) is None


def test_real_repository_pytest_configuration_cannot_replace_trusted_command(real):
    runner, request = real
    result = runner.run(request('def test_failure(): assert False\n',
                                {'pytest.ini': b'[pytest]\naddopts=--ignore=tests\n'}))
    assert result.outcome == Outcome.TEST_FAILURE


def test_real_demo_still_has_its_deliberate_failure(real):
    runner, request = real
    demo = Path(__file__).resolve().parents[2] / 'demo-repository'
    item = request((demo / 'tests/test_pagination.py').read_text(encoding='utf8'),
                   {'pagination.py': (demo / 'pagination.py').read_bytes()})
    result = runner.run(item)
    assert result.outcome == Outcome.TEST_FAILURE
    assert '1 failed' in result.stdout and '1 passed' in result.stdout


def test_real_image_watchdog_stops_target_even_without_controller_polling(real, monkeypatch):
    runner, request = real
    runner.limits = replace(runner.limits, wall_seconds=2)
    original = runner.client.attach
    def delayed(*args):
        capture = original(*args)
        time.sleep(5)  # Simulate a stalled controller before its own deadline loop.
        return capture
    monkeypatch.setattr(runner.client, 'attach', delayed)
    result = runner.run(request('def test_loop():\n    while True: pass\n'))
    assert result.exit_code == 124
    assert result.outcome == Outcome.TIMEOUT
    assert result.reason == 'image_watchdog_timeout'
    assert result.cleanup_complete
