"""Offline repair/controller tests. No target imports or target tests on the host."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.domain import Conflict, JobState, LeaseLost
from backend.app.jobs import JobService
from backend.app.settings import Redactor, Settings
from worker.detection import DetectionService
from worker.docker_client import Capture
from worker.docker_runner import DockerRunner
from worker.model_call import gemini_generate
from worker.patches import validate_edits
from worker.repair import RepairService
from worker.repair_models import RepairError, RepairProposal
from worker.repair_providers import (
    FakeRepairProvider,
    GeminiRepairProvider,
    configured_provider,
    fake_proposal,
)
from worker.runner_models import RunInput
from worker.source_common import Budget, SourceError
from worker.tests.test_detection import FakeExecution, result
from worker.tests.test_repositories import access, fixture_git, job_lease
from worker.workspaces import TargetProfile, WorkspaceManager

__all__ = ['access', 'fixture_git']


@pytest.fixture
def reproduced(access):
    _, lease = job_lease(access)
    DetectionService(access, FakeExecution(access, [result(), result()])).detect(lease)
    return access, lease


class Reply:
    mode = 'offline'

    def __init__(self, raw):
        self.raw, self.calls, self.requests = raw, 0, []

    def generate(self, request, seconds, heartbeat):
        self.calls += 1
        self.requests.append(request)
        heartbeat()
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw(request) if callable(self.raw) else self.raw


def change_proposal(request, **change):
    value = json.loads(fake_proposal(request))
    value['edits'][0].update(change)
    return json.dumps(value)


def test_valid_fake_candidate_is_durable_unverified_and_does_not_change_fixture(reproduced):
    access, lease = reproduced
    settings = access.jobs.settings
    service = RepairService(access)
    proof, workspace, _, _ = service._evidence(lease)
    baseline = (access.manager.path(workspace) / 'baseline/pagination.py').read_bytes()
    fixture_path = Path(__file__).resolve().parents[2] / 'demo-repository/pagination.py'
    bundled = fixture_path.read_bytes()
    candidate = service.propose(lease)
    assert candidate['status'] == 'proposed' and candidate['provider'] == 'offline'
    assert candidate['detection_id'] == proof['id'] and candidate['sha'] == workspace.sha
    assert access.jobs.get(lease.job_id)['state'] == JobState.REPAIRING
    attempt = access.manager.path(workspace) / 'attempts' / candidate['attempt_id']
    assert b'page_size - 1' not in (attempt / 'pagination.py').read_bytes()
    assert (access.manager.path(workspace) / 'baseline/pagination.py').read_bytes() == baseline
    assert fixture_path.read_bytes() == bundled
    for file in (attempt / 'tests').glob('*.py'):
        assert file.read_bytes() == (access.manager.path(workspace) / 'baseline/tests' / file.name).read_bytes()
    _, runner_digest = DockerRunner(access.manager)._package(RunInput(workspace, attempt, 'verification'))
    assert candidate['patch_digest'] == runner_digest
    reopened = JobService(settings)
    assert reopened.candidates(lease.job_id) == [candidate]
    before = reopened.get(lease.job_id)['model_calls']
    assert service.propose(lease) == candidate  # Durable resume returns the same proposed candidate.
    assert reopened.get(lease.job_id)['model_calls'] == before == 1
    assert access.jobs.events(lease.job_id)[-1]['kind'] == 'candidate_proposed'


def test_baseline_exit_or_exported_evidence_cannot_authorize_provider(access):
    _, lease = job_lease(access)
    access.prepare(lease)
    provider = Reply(fake_proposal)
    with pytest.raises(Conflict): RepairService(access, provider).propose(lease)
    assert provider.calls == 0 and access.jobs.get(lease.job_id)['model_calls'] == 0


def test_tampered_receipt_or_baseline_blocks_before_request(reproduced):
    access, lease = reproduced
    service = RepairService(access, Reply(fake_proposal))
    _, workspace, _, _ = service._evidence(lease)
    for receipt in (access.manager.path(workspace) / 'detection-receipts').glob('*.json'):
        receipt.write_text('{}')
    with pytest.raises(RepairError, match='reproduction_required'): service.propose(lease)
    assert service.provider.calls == 0


@pytest.mark.parametrize('raw', ['not json', '```json\n{}\n```', '{}',
                               '{"diagnosis":"x","diagnosis":"y","edits":[]}',
                               '{"diagnosis":"x","edits":[],"command":"pytest"}', 'x' * 17000,
                               '{"diagnosis":"x","edits":[{"path":"pagination.py","old_text":"x","new_text":"\\ud800"}]}'])
def test_malformed_outputs_never_create_attempts_or_candidates(reproduced, raw):
    access, lease = reproduced
    with pytest.raises(RepairError, match='invalid_proposal'): RepairService(access, Reply(raw)).propose(lease)
    assert access.jobs.candidates(lease.job_id) == []
    assert access.jobs.get(lease.job_id)['model_calls'] == 1


@pytest.mark.parametrize('path', ['../pagination.py', '/pagination.py', 'C:/target.py',
                                'tests/test_pagination.py', '.env', 'requirements.txt',
                                'pyproject.toml', '.github/workflows/check.yml', 'config.py',
                                'settings.py', 'secrets.py', 'Pagination.py', 'other.py'])
def test_forbidden_paths_are_rejected(reproduced, path):
    access, lease = reproduced
    with pytest.raises(RepairError, match='invalid_edit'):
        RepairService(access, Reply(lambda request: change_proposal(request, path=path))).propose(lease)
    assert access.jobs.candidates(lease.job_id) == []


@pytest.mark.parametrize('change', [
    {'old_text': 'absent anchor'}, {'new_text': 'return ('},
    {'new_text': 'return items[start:start + page_size - 1]'},
    {'new_text': 'token = "new-credential"'},
])
def test_bad_anchors_syntax_noops_and_secrets_are_rejected(reproduced, change):
    access, lease = reproduced
    with pytest.raises(RepairError, match='invalid_edit'):
        RepairService(access, Reply(lambda request: change_proposal(request, **change))).propose(lease)


def test_patch_line_limit_uses_persisted_job_limit(reproduced):
    access, lease = reproduced
    # The job snapshot remains authoritative even if process settings change.
    with access.jobs.db.transaction() as connection:
        connection.execute('UPDATE jobs SET max_patch_lines=1 WHERE id=?', (lease.job_id,))
    with pytest.raises(RepairError, match='patch_limit'): RepairService(access).propose(lease)
    assert not access.jobs.candidates(lease.job_id)


def test_input_limit_is_checked_before_budget_or_model(reproduced):
    access, lease = reproduced
    access.jobs.settings = access.jobs.settings.model_copy(update={'repair_input_bytes': 1024})
    provider = Reply(fake_proposal)
    with pytest.raises(RepairError, match='input_limit'): RepairService(access, provider).propose(lease)
    assert provider.calls == 0 and access.jobs.get(lease.job_id)['model_calls'] == 0


def test_prompt_contains_only_redacted_relevant_data_and_diagnosis_is_redacted(reproduced):
    access, lease = reproduced
    secret = 'private-repair-key-value'
    access.jobs.redactor = Redactor((secret,))
    provider = Reply(lambda request: json.dumps({**json.loads(fake_proposal(request)), 'diagnosis': secret}))
    candidate = RepairService(access, provider).propose(lease)
    assert candidate['diagnosis'] == '[REDACTED]'
    prompt = provider.requests[0]
    assert {item['path'] for item in prompt['source']} == {'pagination.py'}
    assert 'stdout' not in prompt and prompt['untrusted_repository_data']
    assert secret not in json.dumps(prompt)
    assert secret not in json.dumps(access.jobs.candidates(lease.job_id))


def test_provider_timeout_kills_child_and_bounds_retries_and_budgets(reproduced):
    access, lease = reproduced
    access.jobs.settings = access.jobs.settings.model_copy(update={'repair_call_seconds': 1})
    captures = []
    def sleeper(command, env, limit, payload):
        child = Capture([sys.executable, '-c', 'import time; time.sleep(30)'], env, limit)
        captures.append(child)
        return child
    provider = FakeRepairProvider(access.jobs.settings, capture_factory=sleeper)
    started = time.monotonic()
    with pytest.raises(RepairError, match='provider_timeout'): RepairService(access, provider).propose(lease)
    assert time.monotonic() - started < 10
    assert len(captures) == 2 and all(child.poll() is not None for child in captures)
    assert JobService(access.jobs.settings).get(lease.job_id)['model_calls'] == 2
    assert access.jobs.candidates(lease.job_id) == []


def test_exhausted_persistent_budget_never_requests_model(reproduced):
    access, lease = reproduced
    access.jobs.advance(lease, JobState.REPAIRING)
    row = access.jobs.get(lease.job_id)
    access.jobs.reserve_usage(lease, model_calls=row['max_model_calls'])
    provider = Reply(fake_proposal)
    with pytest.raises(RepairError, match='budget_exhausted'): RepairService(access, provider).propose(lease)
    assert provider.calls == 0
    assert JobService(access.jobs.settings).get(lease.job_id)['model_calls'] == row['max_model_calls']


def test_cancellation_during_provider_cannot_apply_or_persist_candidate(reproduced):
    access, lease = reproduced
    class Cancel(Reply):
        def generate(self, request, seconds, heartbeat):
            access.jobs.cancel(lease.job_id)
            heartbeat()
    with pytest.raises(LeaseLost): RepairService(access, Cancel('')).propose(lease)
    assert access.jobs.candidates(lease.job_id) == []


def test_record_failure_rolls_back_files_and_does_not_leave_partial_candidate(reproduced, monkeypatch):
    access, lease = reproduced
    def broken(*args, **kwargs):
        raise Conflict('injected commit failure')
    monkeypatch.setattr(access.jobs, 'record_candidate', broken)
    with pytest.raises(Conflict): RepairService(access).propose(lease)
    record = access.jobs.source_snapshot(lease.job_id)
    workspace = access.manager.reopen(lease.job_id, record, Budget(5))
    attempts = access.manager.path(workspace) / 'attempts'
    assert sorted(path.name for path in attempts.iterdir())  # Existing detection copies survive.
    assert not list((access.manager.path(workspace) / 'candidate-receipts').glob('*.json'))
    assert not access.jobs.candidates(lease.job_id)


def test_live_is_off_by_default_and_requires_explicit_settings():
    settings = Settings()
    assert isinstance(configured_provider(settings), FakeRepairProvider)
    with pytest.raises(ValueError): Settings(enable_live_gemini=True)
    with pytest.raises(RepairError, match='live_not_enabled'):
        GeminiRepairProvider(settings).generate({}, 1, lambda: None)


def test_official_sdk_adapter_contract_without_network():
    observed = {}
    class Client:
        def __init__(self, **kwargs):
            observed.update(kwargs)
            self.models = self
        def __enter__(self): return self
        def __exit__(self, *args): observed['closed'] = True
        def generate_content(self, **kwargs):
            observed['request'] = kwargs
            return SimpleNamespace(text='{"diagnosis":"x","edits":[]}')
    assert gemini_generate({'api_key': 'mock-key', 'model': 'configured-model', 'seconds': 1,
                            'output_tokens': 128, 'request': {'untrusted_repository_data': True}}, Client)
    assert observed['http_options'].timeout == 800
    assert observed['http_options'].retry_options.attempts == 1
    assert observed['http_options'].client_args['trust_env'] is False
    config = observed['request']['config']
    assert config.max_output_tokens == 128 and config.automatic_function_calling.disable
    assert config.response_mime_type == 'application/json' and config.response_json_schema
    assert observed['closed'] and observed['vertexai'] is False


def test_repair_rejects_real_symlink_or_junction_before_any_source_write(reproduced, tmp_path):
    access, lease = reproduced
    service = RepairService(access, Reply(fake_proposal))
    _, workspace, _, _ = service._evidence(lease)
    outside = tmp_path / 'unrelated'
    outside.mkdir()
    sentinel = outside / 'pagination.py'
    sentinel.write_text('untouched sentinel')
    baseline = access.manager.path(workspace) / 'baseline'
    link = baseline / 'foreign-link'
    junction = False
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != 'nt':
            raise
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(outside)],
                       check=True, capture_output=True, timeout=5)
        junction = True
    try:
        with pytest.raises(SourceError): service.propose(lease)
        assert service.provider.calls == 0 and sentinel.read_text() == 'untouched sentinel'
    finally:
        link.rmdir() if junction else link.unlink()


def test_output_limit_terminates_product_owned_child(reproduced):
    access, lease = reproduced
    captures = []
    def noisy(command, env, limit, payload):
        child = Capture([sys.executable, '-c', 'import sys; sys.stdout.write("x"*100000); sys.stdout.flush()'], env, limit)
        captures.append(child)
        return child
    provider = FakeRepairProvider(access.jobs.settings, capture_factory=noisy)
    with pytest.raises(RepairError, match='provider_output_limit'): RepairService(access, provider).propose(lease)
    assert captures[0].poll() is not None
    assert access.jobs.get(lease.job_id)['model_calls'] == 1


def test_retry_limit_reserves_each_call_and_does_not_retry_malformed_output(reproduced):
    access, lease = reproduced
    provider = Reply(RepairError('provider_unavailable'))
    with pytest.raises(RepairError): RepairService(access, provider).propose(lease)
    assert provider.calls == 2
    assert access.jobs.get(lease.job_id)['model_calls'] == 2


def test_patch_file_limit_is_enforced_even_for_approved_sources(tmp_path):
    manager = WorkspaceManager(tmp_path / 'file-limit-owned')
    workspace = manager.create('a' * 32)
    profile = TargetProfile(source_edit_allowlist=('pagination.py', 'helper.py'))
    baseline = manager.path(workspace) / 'baseline'
    for name in profile.source_edit_allowlist:
        (baseline / name).write_text('VALUE = 1\n')
    workspace = manager.seal(workspace, 'c' * 40, profile, Budget(5))
    proposal = RepairProposal(diagnosis='two source changes', edits=[
        {'path': name, 'old_text': 'VALUE = 1', 'new_text': 'VALUE = 2'} for name in profile.source_edit_allowlist])
    context = {'source': [{'path': name, 'text': 'VALUE = 1'} for name in profile.source_edit_allowlist]}
    with pytest.raises(RepairError, match='patch_limit'):
        validate_edits(manager, workspace, profile, proposal, context,
                       {'max_patch_files': 1, 'max_patch_lines': 200}, Redactor())


def test_exhausted_token_budget_is_persistent_and_does_not_call_provider(reproduced):
    access, lease = reproduced
    access.jobs.advance(lease, JobState.REPAIRING)
    row = access.jobs.get(lease.job_id)
    access.jobs.reserve_usage(lease, model_tokens=row['max_model_tokens'])
    provider = Reply(fake_proposal)
    with pytest.raises(RepairError, match='budget_exhausted'): RepairService(access, provider).propose(lease)
    assert provider.calls == 0 and JobService(access.jobs.settings).get(lease.job_id)['model_tokens'] == row['max_model_tokens']
