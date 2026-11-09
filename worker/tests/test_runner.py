"""Mock lifecycle tests; these do not substitute for test_docker_isolation.py."""

import copy
import io
import json
import threading
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.app.settings import Redactor, Settings
from worker.docker_client import DockerCLI, DockerFault
from worker.docker_policy import (
    ENTRYPOINT,
    check_daemon,
    check_image,
    resource_name,
    tmpfs_options,
)
from worker.docker_runner import DockerRunner, output_text
from worker.runner_models import Outcome, RunInput, RunnerLimits
from worker.source_common import Budget
from worker.workspaces import DEMO_PROFILE, WorkspaceManager

IMAGE = 'sha256:' + 'a' * 64
SECRET = 'private-test-provider-value-123456'


def daemon():
    return {'OSType': 'linux', 'Architecture': 'x86_64', 'CgroupVersion': '2',
            'MemoryLimit': True, 'SwapLimit': True, 'CpuCfsQuota': True, 'PidsLimit': True,
            'SecurityOptions': ['name=seccomp,profile=builtin'], 'Warnings': []}


def image():
    return {'Id': IMAGE, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {
        'User': '10001:10001', 'Entrypoint': ENTRYPOINT, 'Cmd': None, 'WorkingDir': '/scratch',
        'Volumes': None, 'Env': ['PATH=/usr/local/bin:/usr/bin:/bin', 'LANG=C.UTF-8'],
        'Labels': {'io.webguard.runner': '1', 'io.webguard.python': '3.12',
                   'io.webguard.profile': DEMO_PROFILE.digest}}}


class Attached:
    def __init__(self, backend, container):
        self.backend, self.container = backend, container
        self.stdout, self.stderr = bytearray(backend.stdout), bytearray(backend.stderr)
        self.overflow = threading.Event()
        if backend.overflow:
            self.overflow.set()
        self.stopped = False

    def poll(self):
        return None if self.backend.hang and not self.stopped else 0

    def finish(self, timeout):
        return 0

    def stop(self):
        self.stopped = True


class FakeDocker:
    def __init__(self, limits=None):
        self.limits = limits or RunnerLimits()
        self.containers, self.volumes, self.calls = {}, {}, []
        self.stdout, self.stderr = b'1 passed\n', b''
        self.exit_code, self.oom, self.overflow, self.hang = 0, False, False, False
        self.fail, self.tamper, self.cleanup_fail = None, None, False
        self.created = datetime.now(UTC).isoformat()
        self.last_target = None

    def document(self, arguments):
        self.calls.append(arguments)
        if self.fail == 'info':
            raise DockerFault('docker_unavailable')
        return daemon()

    def inspect(self, kind, name, optional=False):
        if kind == 'image':
            return image()
        data = self.containers if kind == 'container' else self.volumes
        if name in data:
            return copy.deepcopy(data[name])
        for value in data.values():
            if value.get('Id') == name:
                return copy.deepcopy(value)
        if optional:
            return None
        raise DockerFault('cli_failed')

    def command(self, args, payload=None):
        self.calls.append(list(args))
        if self.fail == 'copy' and args[:2] == ['container', 'cp']:
            raise DockerFault('daemon_error')
        if args[:2] == ['volume', 'create']:
            metadata = dict(value.split('=', 1) for index, value in enumerate(args) if index and args[index - 1] == '--label')
            name = args[-1]
            self.volumes[name] = {'Name': name, 'Driver': 'local', 'Options': None,
                                  'Labels': metadata, 'Created': self.created}
            return name.encode()
        if args[:2] == ['container', 'create']:
            name = args[args.index('--name') + 1]
            metadata = dict(value.split('=', 1) for index, value in enumerate(args) if index and args[index - 1] == '--label')
            role, run, owner, _job = (metadata[key] for key in ('io.webguard.role', 'io.webguard.run', 'io.webguard.owner', 'io.webguard.job'))
            volume = resource_name(owner, run, 'source')
            limit = self.limits
            host = {'Privileged': False, 'ReadonlyRootfs': True, 'NetworkMode': 'none',
                    'PublishAllPorts': False, 'PortBindings': {}, 'Binds': None, 'VolumesFrom': None,
                    'Devices': [], 'DeviceRequests': None, 'DeviceCgroupRules': None,
                    'PidMode': '', 'IpcMode': 'private', 'UTSMode': '', 'UsernsMode': '',
                    'CgroupnsMode': 'private', 'CapAdd': None, 'CapDrop': ['ALL'],
                    'SecurityOpt': ['no-new-privileges=true'], 'Memory': limit.memory_mib * 1048576,
                    'MemorySwap': limit.memory_mib * 1048576, 'NanoCpus': limit.cpu_millis * 1000000,
                    'PidsLimit': limit.pids, 'ShmSize': 1048576, 'OomKillDisable': False,
                    'AutoRemove': False, 'LogConfig': {'Type': 'none'},
                    'Tmpfs': {'/scratch': tmpfs_options(limit.scratch_mib), '/tmp': tmpfs_options(limit.tmp_mib)},
                    'Mounts': [{'Type': 'volume', 'Source': volume, 'Target': '/input',
                                'ReadOnly': role == 'test', 'VolumeOptions': {'NoCopy': True}}]}
            config = {'Labels': metadata, 'User': '10001:10001', 'WorkingDir': '/scratch',
                      'Env': [f'WEBGUARD_WALL_SECONDS={limit.wall_seconds}'],
                      'Tty': False, 'OpenStdin': False,
                      'Entrypoint': ENTRYPOINT if role == 'test' else ['python'],
                      'Cmd': None if role == 'test' else ['-I', '/opt/webguard/stage.py']}
            value = {'Id': ('b' if role == 'stage' else 'c') * 64, 'Name': '/' + name, 'Image': IMAGE,
                     'Config': config, 'HostConfig': host, 'Created': self.created,
                     'Mounts': [{'Type': 'volume', 'Name': volume, 'Destination': '/input',
                                 'Driver': 'local', 'RW': role == 'stage'}],
                     'State': {'Running': False, 'ExitCode': self.exit_code, 'OOMKilled': self.oom,
                               'StartedAt': '2026-11-04T00:00:00Z', 'Error': ''}}
            value['State']['FinishedAt'] = '2026-11-04T00:00:01Z'
            if self.tamper and role == 'test':
                self.tamper(value)
            self.containers[name] = value
            return value['Id'].encode()
        if args[:2] == ['container', 'start']:
            self.containers[args[-1]]['State']['Running'] = True
        elif args[:2] == ['container', 'cp']:
            assert payload is not None
            with __import__('tarfile').open(fileobj=io.BytesIO(payload)) as archive:
                assert all(not entry.issym() and not entry.islnk() for entry in archive)
        elif args[:2] == ['container', 'rm']:
            if self.cleanup_fail:
                raise DockerFault('cleanup_test_failure')
            for name, value in list(self.containers.items()):
                if value['Id'] == args[-1] or name == args[-1]:
                    del self.containers[name]
        elif args[:2] == ['container', 'kill']:
            self.containers[args[-1]]['State']['Running'] = False
            self.hang = False
        elif args[:2] == ['volume', 'rm']:
            if self.cleanup_fail:
                raise DockerFault('cleanup_test_failure')
            self.volumes.pop(args[-1], None)
        elif args[:2] == ['container', 'ls']:
            return '\n'.join(self.containers).encode()
        elif args[:2] == ['volume', 'ls']:
            return '\n'.join(self.volumes).encode()
        return b''

    def attach(self, name, limit):
        self.last_target = name
        self.containers[name]['State']['Running'] = self.hang
        return Attached(self, name)


@pytest.fixture
def prepared(tmp_path):
    manager = WorkspaceManager(tmp_path / 'owned')
    workspace = manager.create('1' * 32)
    root = manager.path(workspace) / 'baseline'
    (root / 'tests').mkdir()
    (root / 'pagination.py').write_text('VALUE = 1\n', encoding='utf8')
    (root / 'tests/test_value.py').write_text('def test_value(): assert True\n', encoding='utf8')
    workspace = manager.seal(workspace, 'd' * 40, DEMO_PROFILE, Budget(5))
    attempt = manager.create_attempt(workspace, 1, Budget(5))
    return manager, RunInput(workspace, attempt)


def make_runner(prepared, backend=None, limits=None):
    manager, _ = prepared
    backend = backend or FakeDocker(limits)
    return DockerRunner(manager, IMAGE, limits, redactor=Redactor((SECRET,)), client=backend), backend


def test_lifecycle_stages_source_without_host_mounts_and_cleans(prepared):
    runner, backend = make_runner(prepared)
    result = runner.run(prepared[1])
    assert result.outcome == Outcome.PASSED
    assert result.exit_code == 0 and result.image_id == IMAGE and result.input_digest
    assert result.effective_settings['source_read_only'] is True
    assert result.cleanup_complete and not backend.containers and not backend.volumes
    assert result.stdout == '1 passed\n'
    calls = backend.calls
    target_create = next(i for i, args in enumerate(calls) if args[:2] == ['container', 'create'] and '--entrypoint=python' not in args)
    assert any(args[:2] == ['container', 'rm'] for args in calls[:target_create])
    assert not any('prune' in args for args in calls)
    assert result.job_id == prepared[1].workspace.job_id


@pytest.mark.parametrize('code,oom,expected', [(0, False, Outcome.PASSED), (1, False, Outcome.TEST_FAILURE),
                                               (2, False, Outcome.TEST_ENVIRONMENT_ERROR),
                                               (5, False, Outcome.TEST_ENVIRONMENT_ERROR),
                                               (137, True, Outcome.OOM), (137, False, Outcome.INFRASTRUCTURE)])
def test_exit_classification_never_treats_runner_failure_as_bug(prepared, code, oom, expected):
    runner, backend = make_runner(prepared)
    backend.exit_code, backend.oom = code, oom
    result = runner.run(prepared[1])
    assert result.outcome == expected
    assert result.exit_code == code and result.cleanup_complete


@pytest.mark.parametrize('case', ['timeout', 'cancelled', 'output', 'copy-failure', 'cleanup-failure', 'callback-failure'])
def test_all_termination_paths_attempt_owned_cleanup(prepared, case):
    limits = RunnerLimits(wall_seconds=1)
    runner, backend = make_runner(prepared, limits=limits)
    callback = None
    if case in ('timeout', 'cancelled', 'callback-failure'):
        backend.hang = True
    if case == 'cancelled':
        callback = lambda: backend.last_target is not None
    if case == 'callback-failure':
        def callback():
            if backend.last_target:
                raise RuntimeError(SECRET)
            return False
    if case == 'output':
        backend.overflow = True
    if case == 'copy-failure':
        backend.fail = 'copy'
    if case == 'cleanup-failure':
        # Allow staging removal, then fail test/volume cleanup.
        original = backend.attach
        def attach(*args):
            result = original(*args)
            backend.cleanup_fail = True
            return result
        backend.attach = attach
    result = runner.run(prepared[1], callback)
    expected = {'timeout': Outcome.TIMEOUT, 'cancelled': Outcome.CANCELLED, 'output': Outcome.OUTPUT_LIMIT}
    assert result.outcome == expected.get(case, Outcome.INFRASTRUCTURE)
    assert SECRET not in json.dumps(result.document())
    if case == 'cleanup-failure':
        assert not result.cleanup_complete
    else:
        assert result.cleanup_complete and not backend.containers and not backend.volumes


@pytest.mark.parametrize('tamper', [
    lambda value: value['HostConfig'].update(Privileged=True),
    lambda value: value['HostConfig'].update(NetworkMode='bridge'),
    lambda value: value['HostConfig'].update(ReadonlyRootfs=False),
    lambda value: value['HostConfig'].update(Devices=[{'PathOnHost': '/dev/sda'}]),
    lambda value: value['HostConfig'].update(Binds=['/private:/host']),
    lambda value: value['HostConfig'].update(CapAdd=['SYS_ADMIN']),
    lambda value: value['HostConfig'].update(SecurityOpt=['seccomp=unconfined']),
    lambda value: value['HostConfig'].update(PidsLimit=0),
    lambda value: value['HostConfig'].update(Memory=0),
    lambda value: value['HostConfig'].update(MemorySwap=-1),
    lambda value: value['HostConfig'].update(NanoCpus=0),
    lambda value: value['HostConfig'].update(Tmpfs={}),
    lambda value: value['Config'].update(User='0:0'),
    lambda value: value['Config'].update(Cmd=['sh', '-c', 'untrusted command']),
    lambda value: value['Mounts'][0].update(Type='bind'),
])
def test_effective_policy_tampering_prevents_test_start(prepared, tamper):
    runner, backend = make_runner(prepared)
    backend.tamper = tamper
    result = runner.run(prepared[1])
    assert result.outcome == Outcome.INFRASTRUCTURE
    assert backend.last_target is None
    assert result.cleanup_complete


def test_missing_docker_is_blocked_without_spawning_host_code(prepared, monkeypatch):
    client = DockerCLI()
    client.executable = None
    def forbidden(*args, **kwargs):
        raise AssertionError('host process must not start')
    monkeypatch.setattr('subprocess.Popen', forbidden)
    result = DockerRunner(prepared[0], IMAGE, client=client).run(prepared[1])
    assert result.outcome == Outcome.BLOCKED and result.reason == 'docker_missing'
    assert result.image_id is None and result.exit_code is None and result.cleanup_complete


@pytest.mark.parametrize('case', ['windows', 'no-memory', 'no-seccomp', 'cgroup1'])
def test_unsupported_daemon_is_blocked(case):
    value = daemon()
    if case == 'windows': value['OSType'] = 'windows'
    elif case == 'no-memory': value['MemoryLimit'] = False
    elif case == 'no-seccomp': value['SecurityOptions'] = []
    else: value['CgroupVersion'] = '1'
    with pytest.raises(DockerFault): check_daemon(value)


@pytest.mark.parametrize('case', ['tag', 'root', 'volumes', 'credentials', 'command', 'profile'])
def test_image_policy_requires_immutable_prepared_identity(case):
    value = image()
    image_id = IMAGE
    if case == 'tag': image_id = 'python:latest'
    elif case == 'root': value['Config']['User'] = 'root'
    elif case == 'volumes': value['Config']['Volumes'] = {'/data': {}}
    elif case == 'credentials': value['Config']['Env'].append('GITHUB_TOKEN=' + SECRET)
    elif case == 'command': value['Config']['Entrypoint'] = ['sh']
    else: value['Config']['Labels']['io.webguard.profile'] = 'bad'
    with pytest.raises(DockerFault): check_image(value, image_id, DEMO_PROFILE, daemon(), Redactor((SECRET,)))


def test_source_transfer_rejects_outside_paths_changed_tests_and_baseline_changes(prepared, tmp_path):
    runner, backend = make_runner(prepared)
    request = prepared[1]
    outside = tmp_path / 'foreign'
    outside.mkdir()
    for invalid in [replace(request, attempt=outside), replace(request, kind='shell')]:
        result = runner.run(invalid)
        assert result.outcome == Outcome.BLOCKED
        assert not any(args[:2] == ['container', 'create'] for args in backend.calls)
    (request.attempt / 'tests/test_value.py').write_text('weakened tests', encoding='utf8')
    assert runner.run(replace(request, kind='verification')).outcome == Outcome.BLOCKED
    (request.attempt / 'tests/test_value.py').write_text('def test_value(): assert True\n', encoding='utf8')
    (request.attempt / 'pagination.py').write_text('VALUE = 2\n', encoding='utf8')
    assert runner.run(request).outcome == Outcome.BLOCKED
    result = runner.run(replace(request, kind='verification'))
    assert result.outcome == Outcome.PASSED and result.patch_digest is not None


def test_redacted_output_is_bounded_and_control_characters_removed(prepared):
    runner, backend = make_runner(prepared, limits=RunnerLimits(output_bytes=1024))
    backend.stdout = (SECRET + '\x1b[31m\x00 Bearer unknown-token\n').encode()
    backend.stderr = b'error https://user:password@host/?token=private'
    result = runner.run(prepared[1])
    assert SECRET not in result.stdout and 'unknown-token' not in result.stdout
    assert 'password' not in result.stderr and 'private' not in result.stderr
    assert '\x1b' not in result.stdout and '\x00' not in result.stdout
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 1024
    assert SECRET[:15] not in output_text(SECRET[:15].encode(), runner.redactor, True)


def test_orphan_recovery_never_removes_active_recent_or_unowned_resources(prepared):
    runner, backend = make_runner(prepared)
    backend.cleanup_fail = True
    runner.run(prepared[1])
    assert backend.containers and backend.volumes
    backend.cleanup_fail = False
    assert runner.recover(min_age_seconds=300) == {}
    assert runner.recover(active_jobs=lambda _: True, min_age_seconds=0) == {}
    names = set(backend.containers)
    assert all(runner.recover(min_age_seconds=0).values())
    assert not backend.containers and not backend.volumes
    assert names


def test_environment_settings_and_resource_validation():
    with pytest.raises(ValueError): Settings(runner_image_id='python:latest')
    with pytest.raises(ValueError): RunnerLimits(memory_mib=64, scratch_mib=64)
    with pytest.raises(ValueError): RunnerLimits(pids=0)
    with pytest.raises(ValueError): Settings(runner_cpu_millis=0)


def test_cli_capture_bounds_timeout_payload_and_private_errors(monkeypatch):
    import sys
    import time

    client = DockerCLI(timeout=0.2)
    client.executable = sys.executable
    assert client.command(['-c', 'print("controller helper")']).strip() == b'controller helper'
    client.timeout = 2
    assert client.command(['-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'], payload=b'bounded bytes') == b'bounded bytes'
    with pytest.raises(DockerFault, match='cli_warning'):
        client.command(['-c', 'import sys; print("private-value",file=sys.stderr)'])
    with pytest.raises(DockerFault, match='cli_output_limit'):
        client.command(['-c', 'print("x" * 2097152)'])
    client.timeout = 0.1
    started = time.monotonic()
    with pytest.raises(DockerFault, match='cli_timeout'):
        client.command(['-c', 'import time; time.sleep(5)'])
    assert time.monotonic() - started < 3


def test_cli_environment_does_not_forward_product_credentials(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', SECRET)
    monkeypatch.setenv('GEMINI_API_KEY', SECRET)
    monkeypatch.setenv('AUTH_TOKEN', SECRET)
    client = DockerCLI()
    assert SECRET not in json.dumps(client.env)
    assert 'DOCKER_CONTEXT' not in client.env
    from pathlib import Path
    assert json.loads(Path(client.env['DOCKER_CONFIG'], 'config.json').read_text()) == {'auths': {}, 'proxies': {}}


def test_image_watchdog_exit_is_timeout_only_after_budget_elapsed(prepared):
    runner, backend = make_runner(prepared, limits=RunnerLimits(wall_seconds=1))
    backend.exit_code = 124
    result = runner.run(prepared[1])
    assert result.outcome == Outcome.TIMEOUT and result.reason == 'image_watchdog_timeout'
    assert result.cleanup_complete


def test_cleanup_never_deletes_forged_or_other_owner_resources(prepared):
    runner, backend = make_runner(prepared)
    backend.cleanup_fail = True
    runner.run(prepared[1])
    backend.cleanup_fail = False
    for document in backend.containers.values():
        document['Config']['Labels']['io.webguard.owner'] = 'f' * 32
    for document in backend.volumes.values():
        document['Labels']['io.webguard.owner'] = 'f' * 32
    before = (set(backend.containers), set(backend.volumes))
    assert runner.recover(min_age_seconds=0) == {}
    assert before == (set(backend.containers), set(backend.volumes))


def execution_context(prepared, tmp_path, limits=None):
    from backend.app.domain import JobState
    from backend.app.jobs import JobService

    manager, _ = prepared
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'execution.sqlite'}")
    jobs = JobService(settings)
    job = jobs.create('execution-job', 'demo-repository', sha='d' * 40)
    lease = jobs.claim('runner-worker')
    jobs.advance(lease, JobState.BASELINING)
    workspace = manager.create(job['id'])
    root = manager.path(workspace) / 'baseline'
    (root / 'tests').mkdir()
    (root / 'pagination.py').write_text('VALUE = 1\n', encoding='utf8')
    (root / 'tests/test_value.py').write_text('def test_value(): assert True\n', encoding='utf8')
    workspace = manager.seal(workspace, job['sha'], DEMO_PROFILE, Budget(5))
    jobs.record_source(lease, workspace.workspace_id, workspace.manifest_digest, workspace.profile_digest)
    request = RunInput(workspace, manager.create_attempt(workspace, 1, Budget(5)))
    runner, backend = make_runner((manager, request), limits=limits)
    return jobs, lease, request, runner, backend


def test_execution_service_persists_budget_receipt_and_only_valid_evidence(prepared, tmp_path):
    from backend.app.jobs import JobService
    from worker.execution import ExecutionService

    jobs, lease, request, runner, _ = execution_context(prepared, tmp_path)
    result = ExecutionService(jobs, runner).execute(lease, request)
    assert result.outcome == Outcome.PASSED
    reopened = JobService(jobs.settings)
    assert reopened.get(lease.job_id)['execution_seconds'] == 30
    proof = reopened.evidence(lease.job_id)
    assert len(proof) == 1 and proof[0]['exit_code'] == 0
    receipts = list((runner.manager.path(request.workspace) / 'runner-receipts').iterdir())
    assert len(receipts) == 1
    assert SECRET not in receipts[0].read_text()
    assert proof[0]['summary']['image_id'] == IMAGE


def test_execution_service_docker_block_does_not_spend_budget_or_create_evidence(prepared, tmp_path):
    from worker.execution import ExecutionService

    jobs, lease, request, runner, backend = execution_context(prepared, tmp_path)
    backend.fail = 'info'
    result = ExecutionService(jobs, runner).execute(lease, request)
    assert result.outcome == Outcome.BLOCKED
    assert jobs.get(lease.job_id)['execution_seconds'] == 0
    assert jobs.evidence(lease.job_id) == []


def test_execution_service_timeout_is_not_reproduction_evidence(prepared, tmp_path):
    from backend.app.domain import Conflict, JobState
    from worker.execution import ExecutionService

    jobs, lease, request, runner, backend = execution_context(prepared, tmp_path, RunnerLimits(wall_seconds=1))
    backend.hang = True
    result = ExecutionService(jobs, runner).execute(lease, request)
    assert result.outcome == Outcome.TIMEOUT
    assert jobs.evidence(lease.job_id) == []
    with pytest.raises(Conflict): jobs.advance(lease, JobState.REPRODUCED)


def test_execution_service_durable_cancellation_cleans_without_bug_evidence(prepared, tmp_path):
    from worker.execution import ExecutionService

    jobs, lease, request, runner, backend = execution_context(prepared, tmp_path)
    backend.hang = True
    original = backend.attach
    def attach(*args):
        result = original(*args)
        jobs.cancel(lease.job_id)
        return result
    backend.attach = attach
    result = ExecutionService(jobs, runner).execute(lease, request)
    assert result.outcome == Outcome.CANCELLED and result.cleanup_complete
    assert jobs.get(lease.job_id)['state'] == 'cancelled'
    assert jobs.evidence(lease.job_id) == []


def test_docker_ssh_or_credential_endpoints_are_blocked_before_process_creation(monkeypatch):
    import sys
    monkeypatch.setenv('DOCKER_HOST', 'ssh://user:private@host.invalid')
    client = DockerCLI()
    client.executable = sys.executable
    with pytest.raises(DockerFault, match='docker_endpoint'):
        client.command(['info'])


def test_ambiguous_create_timeout_quarantines_labelled_volume_until_recovery(prepared):
    runner, backend = make_runner(prepared)
    original = backend.command
    def ambiguous(args, payload=None):
        value = original(args, payload)
        if args[:2] == ['container', 'create']:
            raise DockerFault('cli_timeout')
        return value
    backend.command = ambiguous
    result = runner.run(prepared[1])
    assert result.outcome == Outcome.INFRASTRUCTURE and not result.cleanup_complete
    assert not backend.containers and backend.volumes
    backend.command = original
    assert all(runner.recover(min_age_seconds=0).values())
    assert not backend.volumes


def test_cli_recognizes_exact_missing_volume_reply_without_hiding_other_errors():
    import sys
    client = DockerCLI(timeout=2)
    client.executable = sys.executable
    name = 'wg-owned-volume'
    message = f'Error response from daemon: get {name}: no such volume'
    command = ['-c', f'import sys; print({message!r},file=sys.stderr); sys.exit(1)']
    assert client.command(command, missing=name) is None
    with pytest.raises(DockerFault):
        client.command(command, missing='another-volume')


def test_runner_decodes_and_redacts_image_report_without_accepting_plain_exit_as_proof(prepared):
    from worker.test_reports import PREFIX, classify

    runner, backend = make_runner(prepared)
    report = {'schema': 1, 'complete': True, 'exit_code': 1, 'collection_errors': [], 'tests': [
        {'node_id': 'tests/test_x.py::test_x', 'phase': phase,
         'outcome': 'failed' if phase == 'call' else 'passed', 'assertion': phase == 'call',
         'message': f'assert {SECRET} == expected' if phase == 'call' else '',
         'traceback': f'E assert {SECRET} == expected' if phase == 'call' else ''}
        for phase in ('setup', 'call', 'teardown')]}
    backend.exit_code = 1
    backend.stdout = (PREFIX + json.dumps(report) + '\n').encode()
    observed = runner.run(prepared[1])
    assert classify(observed)[0] == 'assertion_failure'
    assert SECRET not in str(observed.document())
    backend.stdout = b'FAILED tests/test_x.py::test_x - AssertionError\n'
    assert classify(runner.run(prepared[1]))[0] == 'inconclusive'


def test_source_transfer_identity_is_independent_of_filesystem_enumeration(prepared, monkeypatch):
    runner, _ = make_runner(prepared)
    original = runner.manager._inventory
    first, _ = runner._package(prepared[1])
    def reversed_files(*args, **kwargs):
        return dict(reversed(list(original(*args, **kwargs).items())))
    monkeypatch.setattr(runner.manager, '_inventory', reversed_files)
    second, _ = runner._package(prepared[1])
    assert first == second


def test_execution_receipt_always_includes_job_secret_redaction(prepared, tmp_path):
    from worker.execution import ExecutionService

    jobs, lease, request, runner, backend = execution_context(prepared, tmp_path)
    private = 'active-job-private-verification-value'
    jobs.redactor = Redactor((private,))
    backend.stdout = private.encode()
    observed = ExecutionService(jobs, runner).execute(lease, request)
    assert private not in observed.stdout and '[REDACTED]' in observed.stdout
    receipt = runner.manager.path(request.workspace) / 'runner-receipts' / (observed.run_id + '.json')
    assert private not in receipt.read_text()
