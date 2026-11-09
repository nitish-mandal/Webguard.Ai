"""Exact candidate verification: no model calls, target-host execution or publication."""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field, replace

from backend.app.domain import BudgetExceeded, FailureReason, JobState, LeaseLost
from worker.check_policy import DISCRIMINATING_IDS, REGRESSION_IDS, check_command
from worker.docker_client import DockerFault
from worker.docker_runner import DockerRunner
from worker.execution import ExecutionService
from worker.patches import apply_edits, parse_proposal, validate_edits
from worker.repair import RepairService
from worker.runner_models import Outcome, RunInput
from worker.source_common import Budget, SourceError, no_links
from worker.test_reports import classify
from worker.workspaces import canonical


class VerificationError(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__('Verification rejected (' + reason + ')')


@dataclass
class VerificationResult:
    outcome: str
    reason: str
    candidate_id: str | None = None
    round_id: str | None = None
    artifact_digest: str | None = None
    runs: dict = field(default_factory=dict)


def read_artifact(manager, workspace, folder, digest, cap):
    directory = manager.path(workspace) / folder
    no_links(directory)
    for index, path in enumerate(directory.glob('*.json')):
        if index >= 100:
            break
        no_links(path)
        if path.stat().st_size > cap or path.stat().st_nlink != 1:
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() == digest:
            return json.loads(raw)
    raise VerificationError('incomplete_evidence')


def checked_report(result, expected_nodes, *, control=False):
    category, assertions = classify(result)
    if category in ('blocked', 'timeout', 'oom', 'output_limit', 'cancelled', 'runner_failure'):
        raise VerificationError(category)
    report = result.test_report
    if (report is None or not report['complete'] or report['collection_errors'] or result.output_truncated
            or not result.cleanup_complete or report['exit_code'] != result.exit_code):
        raise VerificationError('incomplete_evidence')
    tests = report['tests']
    if {test['node_id'] for test in tests} != set(expected_nodes):
        raise VerificationError('missing_or_skipped')
    passed, failed = set(), set()
    for node in expected_nodes:
        records = [item for item in tests if item['node_id'] == node]
        phases = {item['phase']: item['outcome'] for item in records}
        if len(records) != 3 or set(phases) != {'setup', 'call', 'teardown'} or 'skipped' in phases.values():
            raise VerificationError('missing_or_skipped')
        if phases['setup'] != 'passed' or phases['teardown'] != 'passed':
            raise VerificationError('environment_error')
        (passed if phases['call'] == 'passed' else failed).add(node)
    if control:
        if (category != 'assertion_failure' or result.exit_code != 1
                or failed != set(DISCRIMINATING_IDS)
                or {item['node_id'] for item in assertions} != set(DISCRIMINATING_IDS)):
            raise VerificationError('regression_not_discriminating')
    elif result.outcome != Outcome.PASSED or result.exit_code != 0 or failed:
        raise VerificationError('tests_failed')
    return {'run_id': result.run_id, 'container_id': result.container_id, 'source_sha': result.source_sha,
            'patch_digest': result.patch_digest, 'image_id': result.image_id, 'command': result.command,
            'exit_code': result.exit_code, 'complete': True, 'skipped': 0,
            'cleanup_complete': True, 'passed_nodes': sorted(passed), 'failed_nodes': sorted(failed)}


class VerificationService:
    def __init__(self, access, execution):
        if access.jobs is not execution.jobs or access.manager is not execution.runner.manager:
            raise ValueError('Verification requires shared owned services')
        self.access, self.jobs, self.manager, self.execution = access, access.jobs, access.manager, execution

    def _prepare(self, lease, candidate):
        proof, workspace, context, _ = RepairService(self.access)._evidence(lease, for_verification=True)
        detection = read_artifact(self.manager, workspace, 'detection-receipts', proof['artifact_digest'],
                                 2 * self.jobs.settings.max_output_bytes + 131072)
        receipt = read_artifact(self.manager, workspace, 'candidate-receipts', candidate['artifact_digest'], 131072)
        required = {'sha': workspace.sha, 'patch_digest': candidate['patch_digest'],
                    'source_manifest_digest': workspace.manifest_digest, 'profile_digest': workspace.profile_digest,
                    'detection_id': proof['id'], 'detection_digest': proof['artifact_digest'],
                    'attempt_id': candidate['attempt_id']}
        if any(receipt.get(key) != value or candidate.get(key, value) != value for key, value in required.items()):
            raise VerificationError('candidate_mismatch')
        proposal = parse_proposal(json.dumps({'diagnosis': receipt['diagnosis'], 'edits': receipt['edits']}),
                                  self.jobs.settings.repair_output_bytes)
        row = self.jobs.check_lease(lease)
        prepared, _ = validate_edits(self.manager, workspace, self.access.profile, proposal, context, row, self.jobs.redactor)
        if sorted(prepared) != candidate['changed_files']:
            raise VerificationError('candidate_mismatch')
        proposed_path = self.manager.path(workspace) / 'attempts' / candidate['attempt_id']
        _, digest = self.execution.runner._package(RunInput(workspace, proposed_path, 'verification'))
        if digest != candidate['patch_digest']:
            raise VerificationError('candidate_mismatch')
        baseline = detection['runs'][0]
        if any(run.get('command') != list(self.access.profile.test_command) for run in detection['runs']):
            raise VerificationError('incomplete_evidence')
        if self.execution.runner.image_id != baseline['image_id']:
            raise VerificationError('image_mismatch')
        if not self.access.profile.name.endswith('-v4') or 'pagination.py' not in prepared:
            raise VerificationError('unsupported_regression_profile')
        nodes = sorted({test['node_id'] for test in baseline['test_report']['tests']})
        return workspace, prepared, baseline['image_id'], proof['summary']['node_id'], nodes

    def _execute(self, lease, request, remaining):
        # Allocate the remaining persistent test budget across all required checks.
        row = self.jobs.check_lease(lease)
        budget = (row['max_execution_seconds'] - row['execution_seconds']) // remaining
        if budget < 1:
            raise VerificationError('budget_exhausted')
        runner = self.execution.runner
        if isinstance(self.execution, ExecutionService):
            clone = DockerRunner(self.manager, runner.image_id,
                replace(runner.limits, wall_seconds=min(runner.limits.wall_seconds, budget)),
                runner.profile, runner.redactor, runner.client)
            clone.active, clone.lock = runner.active, runner.lock
            return ExecutionService(self.jobs, clone).execute(lease, request, record_evidence=False)
        return self.execution.execute(lease, request, record_evidence=False)

    def verify(self, lease, candidate_id=None):
        row = self.jobs.check_lease(lease)
        candidates = [item for item in self.jobs.candidates(lease.job_id)
                      if item['repair_attempt'] == row['repair_attempts'] and
                      (candidate_id is None or item['id'] == candidate_id)]
        if len(candidates) != 1 or row['state'] not in (JobState.REPAIRING, JobState.VERIFYING, JobState.VERIFIED):
            raise VerificationError('candidate_required')
        candidate = candidates[0]
        if candidate['status'] == 'verified' and row['state'] == JobState.VERIFIED:
            return VerificationResult('verified', 'already_verified', candidate['id'], candidate['verification_id'])
        try:
            workspace, prepared, image, original, nodes = self._prepare(lease, candidate)
            self.execution.runner.preflight()
        except DockerFault as error:
            return VerificationResult('blocked', error.code, candidate['id'])
        except VerificationError as error:
            return VerificationResult('blocked', error.reason, candidate['id'])
        except (SourceError, ValueError, OSError):
            return VerificationResult('blocked', 'candidate_mismatch', candidate['id'])
        if row['state'] == JobState.REPAIRING:
            self.jobs.advance(lease, JobState.VERIFYING)
        while True:
            try:
                round_id = self.jobs.begin_verification(lease, candidate['id'], image)
            except BudgetExceeded:
                self.jobs.advance(lease, JobState.FAILED, failure_reason=FailureReason.RETRIES)
                return VerificationResult('failed', 'attempts_exhausted', candidate['id'])
            result = VerificationResult('failed', 'tests_failed', candidate['id'], round_id)
            checks = {}
            seen_runs, seen_containers = set(), set()

            def heartbeat():
                current = self.jobs.check_lease(lease)
                if current['lease_expires_at'] - self.jobs.clock() < self.jobs.settings.lease_seconds / 2:
                    self.jobs.renew(lease)

            try:
                steps = (('baseline_regression', 'regression', None, REGRESSION_IDS),
                         ('original', 'original', original, [original]),
                         ('suite', 'suite', None, nodes),
                         ('patched_regression', 'regression', None, REGRESSION_IDS))
                for index, (name, check, test_id, expected) in enumerate(steps):
                    heartbeat()
                    if index == 0:
                        attempt = self.manager.create_attempt(workspace, candidate['repair_attempt'], Budget(self.manager.limits.seconds))
                        kind, digest = 'control', None
                    else:
                        attempt, digest = apply_edits(self.manager, workspace, candidate['repair_attempt'], prepared, heartbeat)
                        if digest != candidate['patch_digest']:
                            raise VerificationError('candidate_mismatch')
                        kind = 'verification'
                    run = self._execute(lease, RunInput(workspace, attempt, kind, check, test_id), len(steps) - index)
                    result.runs[name] = self.jobs.redactor.clean(run.document())
                    heartbeat()
                    if (run.source_sha != workspace.sha or run.profile_digest != workspace.profile_digest
                            or run.source_manifest_digest != workspace.manifest_digest or run.image_id != image
                            or run.patch_digest != digest
                            or not re.fullmatch(r'[0-9a-f]{32}', run.run_id or '')
                            or not re.fullmatch(r'[0-9a-f]{64}', run.container_id or '')
                            or run.run_id in seen_runs or run.container_id in seen_containers
                            or run.command != check_command(self.access.profile.test_command, check, test_id)):
                        if run.outcome == Outcome.BLOCKED:
                            raise VerificationError('blocked')
                        raise VerificationError('incomplete_evidence')
                    seen_runs.add(run.run_id)
                    seen_containers.add(run.container_id)
                    checks[name] = checked_report(run, expected, control=index == 0)
                result.outcome, result.reason = 'verified', 'all_required_checks_passed'
            except LeaseLost:
                current = self.jobs.get(lease.job_id)
                if current['deadline'] <= self.jobs.clock():
                    self.jobs.expire()
                    return VerificationResult('failed', 'deadline_exceeded', candidate['id'], round_id, runs=result.runs)
                return VerificationResult('cancelled' if current['cancellation_requested'] else 'stale_owner',
                                          'lease_lost', candidate['id'], round_id, runs=result.runs)
            except VerificationError as error:
                result.reason = error.reason
                if error.reason == 'blocked':
                    result.outcome = 'blocked'
            except (SourceError, ValueError, OSError, DockerFault):
                result.reason = 'incomplete_evidence'
            receipt = self.jobs.redactor.clean({'schema': 1, 'candidate_id': candidate['id'], 'sha': workspace.sha,
                'patch_digest': candidate['patch_digest'], 'profile_digest': workspace.profile_digest,
                'image_id': image, 'outcome': result.outcome, 'reason': result.reason,
                'round_id': round_id, 'checks': checks, 'runs': result.runs, 'untrusted_target_data': True})
            directory = self.manager.path(workspace) / 'verification-receipts'
            no_links(directory)
            directory.mkdir(exist_ok=True)
            payload = canonical(receipt)
            with (directory / (uuid.uuid4().hex + '.json')).open('xb') as stream:
                stream.write(payload)
            result.artifact_digest = hashlib.sha256(payload).hexdigest()
            self.jobs.finish_verification(lease, round_id, verdict=result.outcome,
                artifact_digest=result.artifact_digest, checks=checks,
                reason=None if result.outcome == 'verified' else result.reason)
            if result.outcome in ('verified', 'blocked'):
                return result
            current = self.jobs.check_lease(lease)
            if result.reason == 'budget_exhausted' or current['execution_seconds'] >= current['max_execution_seconds']:
                self.jobs.advance(lease, JobState.FAILED, failure_reason=FailureReason.BUDGET)
                return result
            if len(self.jobs.verification_rounds(lease.job_id)) >= current['max_repair_attempts']:
                self.jobs.advance(lease, JobState.FAILED, failure_reason=FailureReason.VERIFICATION)
                return result
