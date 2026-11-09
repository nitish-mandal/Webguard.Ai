"""Product classification/controller tests use data fakes, never host target execution."""

import hashlib
import json
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest

from backend.app.domain import Conflict, JobState, LeaseLost
from backend.app.jobs import JobService
from backend.app.settings import Redactor
from worker.detection import DetectionService
from worker.runner_models import Outcome, RunResult
from worker.test_reports import PREFIX, classify, comparison, decode_report
from worker.tests.test_repositories import access, fixture_git, job_lease
from worker.workspaces import DEMO_PROFILE, canonical

NODE = 'tests/test_pagination.py::test_first_page_contains_requested_count'
PASS = 'tests/test_pagination.py::test_invalid_page_rejected'
IMAGE = 'sha256:' + 'b' * 64

# Pytest discovers these imported fixtures by their module-level names.
__all__ = ['access', 'fixture_git']


def document(failed=True, message='assert [10] == [10, 20]', *, node=NODE):
    tests = []
    for name in (node, PASS):
        for phase in ('setup', 'call', 'teardown'):
            failure = failed and name == node and phase == 'call'
            tests.append({'node_id': name, 'phase': phase, 'outcome': 'failed' if failure else 'passed',
                          'assertion': bool(failure), 'message': message if failure else '',
                          'traceback': ('tests/test_pagination.py:14: in test_first_page_contains_requested_count\n'
                                        '    assert module.page_items([10, 20, 30, 40], 0, 2) == [10, 20]\nE   ' + message)
                                        if failure else ''})
    return {'schema': 1, 'complete': True, 'exit_code': 1 if failed else 0,
            'tests': tests, 'collection_errors': []}


def result(report=None, outcome=Outcome.TEST_FAILURE, **kwargs):
    if report is None:
        report = document()
    code = report['exit_code']
    stdout = 'pytest output\n' + PREFIX + json.dumps(report) + '\n'
    return RunResult(uuid.uuid4().hex, 'a' * 32, 'd' * 40, 'e' * 64, DEMO_PROFILE.digest,
                     input_digest='f' * 64, outcome=outcome, exit_code=code, stdout=stdout,
                     image_id=IMAGE, test_report=decode_report(stdout, code, Redactor()),
                     command=list(DEMO_PROFILE.test_command), **kwargs)


class FakeExecution:
    def __init__(self, access, rows):
        self.jobs = access.jobs
        self.runner = SimpleNamespace(manager=access.manager)
        self.rows = rows
        self.requests = []

    def execute(self, lease, request, *, record_evidence):
        assert record_evidence is False
        self.requests.append(request)
        if callable(self.rows):
            return self.rows(lease, request)
        value = self.rows[len(self.requests) - 1]
        self.jobs.reserve_usage(lease, execution_seconds=1)
        return replace(value, run_id=uuid.uuid4().hex, job_id=lease.job_id,
                       source_sha=request.workspace.sha,
                       source_manifest_digest=request.workspace.manifest_digest,
                       profile_digest=request.workspace.profile_digest)


def detect(access, rows):
    job, lease = job_lease(access)
    execution = FakeExecution(access, rows)
    detected = DetectionService(access, execution).detect(lease)
    return detected, job, lease, execution


def test_stable_assertion_requires_fresh_matching_runs_and_persists_evidence(access):
    found, job, _, execution = detect(access, [result(), result()])
    assert found.verdict == 'reproduced' and found.failing_test_id == NODE
    assert found.state_updated and access.jobs.get(job['id'])['state'] == 'reproduced'
    paths = [request.attempt for request in execution.requests]
    assert len(paths) == 2 and paths[0] != paths[1]
    assert paths[0].is_dir()  # Never import target files.
    assert execution.requests[0].workspace == execution.requests[1].workspace
    reopened = JobService(access.jobs.settings)
    assert reopened.get(job['id'])['execution_seconds'] == 2
    proofs = reopened.evidence(job['id'])
    assert [row['kind'] for row in proofs] == ['baseline', 'baseline', 'detection']
    assert proofs[-1]['artifact_digest'] == found.artifact_digest
    receipts = list((access.manager.path(execution.requests[0].workspace) / 'detection-receipts').glob('*.json'))
    raw = receipts[0].read_bytes()
    artifact = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == found.artifact_digest
    assert artifact['command'] == list(DEMO_PROFILE.test_command)
    assert artifact['snippets'] and len(canonical(artifact)) < 262144
    assert all('def test_invalid_page_rejected' not in item['text'] for item in artifact['snippets'])
    failure = next(item for item in artifact['runs'][0]['test_report']['tests'] if item['assertion'])
    assert failure['comparison']['left'] == '[10]' and failure['comparison']['right'] == '[10, 20]'
    assert failure['comparison']['actual'] == '[10]' and failure['comparison']['expected'] == '[10, 20]'
    assert artifact['untrusted_repository_data']


def test_green_suite_is_an_observation_not_bug_free_claim(access):
    found, job, _, execution = detect(access, [result(document(False), Outcome.PASSED)])
    assert found.verdict == 'no_reproducible_bug' and len(execution.requests) == 1
    assert access.jobs.get(job['id'])['state'] == 'no_reproducible_bug'


@pytest.mark.parametrize('all_skipped', [False, True])
def test_skips_do_not_fabricate_environment_errors_or_executed_tests(all_skipped):
    report = document(False)
    skipped_node = report['tests'][0]['node_id']
    report['tests'] = [item for item in report['tests'] if not (
        item['phase'] == 'call' and (item['node_id'] == skipped_node or all_skipped))]
    for item in report['tests']:
        if item['phase'] == 'setup' and (item['node_id'] == skipped_node or all_skipped):
            item['outcome'] = 'skipped'
    assert classify(result(report, Outcome.PASSED))[0] == ('inconclusive' if all_skipped else 'no_reproducible_bug')


@pytest.mark.parametrize('second', [result(document(False), Outcome.PASSED),
                                   result(document(message='assert [20] == [10, 20]')),
                                   result(document(node='tests/test_other.py::test_other'))])
def test_inconsistent_runs_are_flaky_inconclusive(access, second):
    found, job, _, _ = detect(access, [result(), second])
    assert found.verdict == 'flaky_inconclusive'
    assert access.jobs.get(job['id'])['failure_reason'] == 'reproduction'
    assert not found.failing_test_id


@pytest.mark.parametrize(('outcome', 'verdict'), [
    (Outcome.TIMEOUT, 'timeout'), (Outcome.OOM, 'oom'), (Outcome.CANCELLED, 'cancelled'),
    (Outcome.OUTPUT_LIMIT, 'output_limit'), (Outcome.INFRASTRUCTURE, 'runner_failure'),
    (Outcome.BLOCKED, 'blocked'),
])
def test_non_test_outcomes_are_never_bugs(outcome, verdict):
    assert classify(result(outcome=outcome))[0] == verdict


@pytest.mark.parametrize(('kind', 'verdict'), [('missing', 'missing_dependencies'),
                                            ('collection', 'collection_error'),
                                            ('setup', 'environment_error')])
def test_environment_errors_are_separate(kind, verdict):
    report = document()
    if kind in ('missing', 'collection'):
        report.update(exit_code=2, complete=False,
                      collection_errors=['ModuleNotFoundError: no module' if kind == 'missing' else 'SyntaxError: bad source'])
    else:
        report['tests'][0].update(outcome='failed', message='fixture error')
    assert classify(result(report, Outcome.TEST_ENVIRONMENT_ERROR))[0] == verdict


def test_second_run_environment_failure_not_flakiness_or_confirmation(access):
    found, job, _, _ = detect(access, [result(), result(outcome=Outcome.TIMEOUT)])
    assert found.verdict == 'timeout' and len(found.runs) == 2
    assert access.jobs.get(job['id'])['state'] == 'failed'
    assert access.jobs.evidence(job['id'])[-1]['exit_code'] == -1


@pytest.mark.parametrize('changed', ['image_id', 'input_digest', 'profile_digest', 'source_sha'])
def test_mismatched_source_or_environment_cannot_confirm(access, changed):
    first, second = result(), result()
    if changed in ('source_sha', 'profile_digest'):
        job, lease = job_lease(access)
        execution = FakeExecution(access, [first, second])
        original = execution.execute
        def wrong(*args, **kwargs):
            value = original(*args, **kwargs)
            if len(execution.requests) == 2:
                setattr(value, changed, '0' * len(getattr(value, changed)))
            return value
        execution.execute = wrong
        found = DetectionService(access, execution).detect(lease)
    else:
        setattr(second, changed, '0' * len(getattr(second, changed)))
        found, job, _, _ = detect(access, [first, second])
    assert found.verdict == 'runner_failure'
    assert access.jobs.get(job['id'])['state'] == 'failed'


def test_raw_failures_with_same_redaction_are_not_false_matches(access):
    secret = 'phase-six-private-value'
    access.jobs.redactor = Redactor((secret, secret + '-changed'))
    one = result(document(message=f'assert {secret} == expected'))
    two = result(document(message=f'assert {secret}-changed == expected'))
    found, job, _, execution = detect(access, [one, two])
    assert found.verdict == 'flaky_inconclusive'
    root = access.manager.path(execution.requests[0].workspace) / 'detection-receipts'
    assert secret not in next(root.glob('*.json')).read_text()
    assert secret not in str(access.jobs.evidence(job['id']))


def test_cancellation_and_lost_lease_do_not_publish_detection(access):
    job, lease = job_lease(access)
    def cancel(lease, request):
        access.jobs.cancel(lease.job_id)
        return replace(result(outcome=Outcome.CANCELLED), job_id=lease.job_id)
    found = DetectionService(access, FakeExecution(access, cancel)).detect(lease)
    assert found.verdict == 'cancelled' and not found.state_updated
    assert access.jobs.get(job['id'])['state'] == 'cancelled'
    assert access.jobs.evidence(job['id']) == []
    with pytest.raises(LeaseLost): access.jobs.check_lease(lease)


def test_single_legacy_failure_does_not_unlock_reproduced(access):
    _, lease = job_lease(access)
    access.prepare(lease)
    proof = access.jobs.add_evidence(lease, kind='baseline', artifact_digest='a' * 64,
                                     exit_code=1, summary={})
    with pytest.raises(Conflict): access.jobs.advance(lease, JobState.REPRODUCED)
    with pytest.raises(Conflict):
        access.jobs.record_detection(lease, verdict='reproduced', artifact_digest='b' * 64,
                                      runs=[proof], node_id=NODE, signature='c' * 64)
    assert len(access.jobs.evidence(lease.job_id)) == 1


@pytest.mark.parametrize('mutation', ['duplicate', 'incomplete', 'invalid_path', 'extra_frame', 'wrong_exit', 'huge', 'trailing'])
def test_report_validation_fails_closed(mutation):
    report = document()
    extra = ''
    if mutation == 'duplicate': report['tests'].append(report['tests'][0])
    if mutation == 'incomplete': report['complete'] = False
    if mutation == 'invalid_path': report['tests'][0]['node_id'] = '../outside.py::test_x'
    if mutation == 'wrong_exit': report['exit_code'] = 0
    if mutation == 'huge': report['tests'][0]['traceback'] = 'x' * 4097
    if mutation == 'extra_frame': extra = PREFIX + json.dumps(report) + '\n'
    if mutation == 'trailing': extra = 'untrusted trailing data\n'
    raw = PREFIX + json.dumps(report) + '\n' + extra
    parsed = decode_report(raw, 1, Redactor())
    value = result()
    value.test_report = parsed
    assert classify(value)[0] == 'inconclusive'


def test_report_redaction_and_signature_preserves_changed_failure_identity():
    secret = 'private-example-value'
    raw = PREFIX + json.dumps(document(message=f'assert {secret} == other'))
    parsed = decode_report(raw, 1, Redactor((secret,)))
    assert secret not in str(parsed)
    assert '[REDACTED]' in str(parsed)
    assert parsed['tests'][1]['signature'] == decode_report(raw, 1, Redactor())['tests'][1]['signature']


def test_comparison_roles_are_unknown_without_literal_expectation():
    value = comparison('assert observed == wanted', 'assert actual == expectation')
    assert value['expected'] is None and value['actual'] is None
    assert comparison('assert True', 'arbitrary instructions') is None


def test_changed_additional_failure_is_inconclusive_even_with_one_common_assertion(access):
    report = document()
    report['tests'][4].update(outcome='failed', assertion=True, message='assert False', traceback='assert False')
    found, _, _, _ = detect(access, [result(), result(report)])
    assert found.verdict == 'flaky_inconclusive'


def test_new_baseline_observation_invalidates_previous_detection_gate(access, monkeypatch):
    _, lease = job_lease(access)
    advance = access.jobs.advance
    def delayed(*args, **kwargs):
        raise Conflict('Simulated interrupted controller before transition')
    monkeypatch.setattr(access.jobs, 'advance', delayed)
    with pytest.raises(Conflict, match='interrupted'):
        DetectionService(access, FakeExecution(access, [result(), result()])).detect(lease)
    monkeypatch.setattr(access.jobs, 'advance', advance)
    access.jobs.add_evidence(lease, kind='baseline', artifact_digest='1' * 64, exit_code=2, summary={})
    with pytest.raises(Conflict): access.jobs.advance(lease, JobState.REPRODUCED)


def test_image_reporter_hooks_emit_bounded_relative_test_identity(tmp_path, monkeypatch):
    from pathlib import Path

    from runner_image import webguard_report as plugin

    monkeypatch.setattr(plugin, 'REPORT', tmp_path / 'trusted-report.json')
    plugin.pytest_sessionstart(None)
    fake_report = SimpleNamespace(failed=True, when='call', nodeid='test_pagination.py::test_page',
                                  outcome='failed', longreprtext='assert [10] == [10, 20]',
                                  longrepr=SimpleNamespace(reprcrash=SimpleNamespace(message='assert [10] == [10, 20]')))
    item = SimpleNamespace(path=Path('/scratch/work/tests/test_pagination.py'))
    call = SimpleNamespace(when='call', excinfo=SimpleNamespace(type=AssertionError))
    hook = plugin.pytest_runtest_makereport(item, call)
    next(hook)
    with pytest.raises(StopIteration): hook.send(SimpleNamespace(get_result=lambda: fake_report))
    plugin.pytest_sessionfinish(None, 1)
    report = json.loads(plugin.REPORT.read_text())
    assert report['complete'] and report['tests'][0]['assertion']
    assert report['tests'][0]['node_id'] == 'tests/test_pagination.py::test_page'
    assert plugin.REPORT.stat().st_size <= plugin.MAX_BYTES
    plugin.pytest_collectreport(SimpleNamespace(failed=True, longrepr='ModuleNotFoundError'))
    plugin.pytest_sessionfinish(None, 2)
    assert json.loads(plugin.REPORT.read_text())['complete'] is False


@pytest.mark.parametrize('field', ['run_id', 'attempt_id', 'image_id', 'input_digest', 'signature'])
def test_storage_rejects_inconsistent_reproduction_proofs_transactionally(access, monkeypatch, field):
    _, lease = job_lease(access)
    def interrupted(*args, **kwargs):
        raise Conflict('interrupted')
    monkeypatch.setattr(access.jobs, 'advance', interrupted)
    with pytest.raises(Conflict):
        DetectionService(access, FakeExecution(access, [result(), result()])).detect(lease)
    evidence = access.jobs.evidence(lease.job_id)
    first, second = evidence[:2]
    changed = dict(second['summary'])
    if field in ('run_id', 'attempt_id'):
        changed[field] = first['summary'][field]
    elif field == 'signature':
        changed['assertions'] = [{'node_id': NODE, 'signature': '0' * 64}]
    else:
        changed[field] = ('sha256:' if field == 'image_id' else '') + '0' * 64
    replacement = access.jobs.add_evidence(lease, kind='baseline', artifact_digest='4' * 64,
                                            exit_code=1, summary=changed)
    before = access.jobs.events(lease.job_id)
    with pytest.raises(Conflict):
        access.jobs.record_detection(lease, verdict='reproduced', artifact_digest='5' * 64,
                                      runs=[first['id'], replacement], node_id=NODE,
                                      signature=first['summary']['assertions'][0]['signature'])
    assert access.jobs.events(lease.job_id) == before
    assert access.jobs.evidence(lease.job_id)[-1]['id'] == replacement


def test_real_missing_docker_is_blocked_without_budget_debit(access, monkeypatch):
    from worker.docker_client import DockerCLI
    from worker.docker_runner import DockerRunner
    from worker.execution import ExecutionService

    _, lease = job_lease(access)
    client = DockerCLI()
    monkeypatch.setattr(client, 'executable', None)
    runner = DockerRunner(access.manager, IMAGE, client=client)
    found = DetectionService(access, ExecutionService(access.jobs, runner)).detect(lease)
    assert found.verdict == 'blocked' and not found.state_updated
    assert access.jobs.get(lease.job_id)['execution_seconds'] == 0
    assert access.jobs.get(lease.job_id)['state'] == 'baselining'
    assert access.jobs.evidence(lease.job_id)[-1]['summary']['verdict'] == 'blocked'
    client.close()
