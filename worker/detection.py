"""Bounded two-run reproduction controller. Never executes target code on the host."""

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, field

from backend.app.domain import FailureReason, JobState, LeaseLost
from worker.runner_models import RunInput
from worker.source_common import Budget, SourceError, no_links, safe_path
from worker.test_reports import classify
from worker.workspaces import canonical


@dataclass
class DetectionResult:
    verdict: str
    sha: str | None
    failing_test_id: str | None = None
    failure_signature: str | None = None
    runs: list[dict] = field(default_factory=list)
    artifact_digest: str | None = None
    state_updated: bool = False


def relevant_snippets(manager, workspace, failure, redactor):
    """Read a few relevant baseline lines as inert data. No imports/target instructions."""
    manager.verify(workspace, Budget(manager.limits.seconds))
    root = manager.path(workspace) / 'baseline'
    path = safe_path(failure['node_id'].split('::')[0])
    targets = [(path, None)]
    symbols = set(re.findall(r'\b([A-Za-z_]\w*)\(', failure['traceback']))
    targets += [(name, symbols) for name in manager._json(manager.path(workspace) / 'baseline.json')
                ['profile']['source_edit_allowlist']]
    result = []
    remaining = 3000
    for name, functions in targets[:4]:
        source = root.joinpath(*safe_path(name).split('/'))
        no_links(source)
        if not source.is_file() or source.stat().st_size > 65536:
            continue
        lines = source.read_text(encoding='utf8', errors='replace').splitlines()
        if functions is None:
            method = failure['node_id'].split('::')[-1].split('[')[0]
            indexes = [i for i, line in enumerate(lines) if re.match(r'\s*def ' + re.escape(method) + r'\(', line)]
        else:
            indexes = [i for i, line in enumerate(lines) if any(
                re.match(r'\s*def ' + re.escape(symbol) + r'\(', line) for symbol in functions)]
        for index in indexes[:1]:
            end = min(index + 14, len(lines))
            indentation = len(lines[index]) - len(lines[index].lstrip())
            for offset in range(index + 1, end):
                candidate = lines[offset]
                if (re.match(r'\s*(?:def |async def |class )', candidate)
                        and len(candidate) - len(candidate.lstrip()) <= indentation):
                    end = offset
                    break
            text = '\n'.join(lines[index:end]).rstrip()[:remaining]
            if not text:
                break
            result.append({'path': name, 'first_line': index + 1,
                           'text': redactor.text(text), 'untrusted_repository_data': True})
            remaining -= len(text)
    return result


class DetectionService:
    def __init__(self, access, execution):
        if access.jobs is not execution.jobs or access.manager is not execution.runner.manager:
            raise ValueError('Detection services must share jobs and owned workspaces')
        self.access, self.execution, self.jobs = access, execution, access.jobs

    def detect(self, lease):
        row = self.jobs.check_lease(lease)
        if row['state'] != JobState.BASELINING:
            raise ValueError('Detection requires baselining state')
        workspace = self.access.prepare(lease)
        result = DetectionResult('inconclusive', workspace.sha)
        proofs, observed, failures = [], [], []
        attempts = []
        # Two full suites, always fresh copies/containers at the same pinned source.
        for number in (1, 2):
            attempt = self.access.attempt(lease, number)
            attempts.append(attempt.name)
            run = self.execution.execute(lease, RunInput(workspace, attempt), record_evidence=False)
            result.runs.append(self.jobs.redactor.clean(run.document()))
            category, assertions = classify(run)
            if (run.job_id != lease.job_id or run.source_sha != workspace.sha
                    or run.source_manifest_digest != workspace.manifest_digest
                    or run.profile_digest != workspace.profile_digest):
                category, assertions = 'runner_failure', []
            observed.append(category)
            failures.append(assertions)
            if category == 'cancelled':
                result.verdict = 'cancelled'
                return result  # Durable cancellation has already fenced this worker.
            try:
                self.jobs.check_lease(lease)
            except LeaseLost:
                result.verdict = 'cancelled' if self.jobs.get(lease.job_id)['cancellation_requested'] else 'runner_failure'
                return result  # Never publish proof under a lost fence.
            if category in ('assertion_failure', 'no_reproducible_bug'):
                proof = self.jobs.add_evidence(
                    lease, kind='baseline', artifact_digest=hashlib.sha256(canonical(result.runs[-1])).hexdigest(),
                    exit_code=run.exit_code, summary={
                        'run_id': run.run_id, 'attempt_id': attempt.name, 'image_id': run.image_id,
                        'input_digest': run.input_digest, 'profile_digest': run.profile_digest,
                        'report_valid': True, 'cleanup_complete': run.cleanup_complete,
                        'classification': category, 'assertions': sorted([
                            {'node_id': item['node_id'], 'signature': item['signature']} for item in assertions],
                            key=lambda item: (item['node_id'], item['signature'])),
                        'test_nodes': sorted({item['node_id'] for item in run.test_report['tests']}),
                    })
                proofs.append(proof)
            if number == 1 and category == 'assertion_failure':
                continue
            break
        if observed[0] != 'assertion_failure':
            result.verdict = observed[0]
        elif observed[-1] == 'no_reproducible_bug':
            result.verdict = 'flaky_inconclusive'
        elif observed[-1] != 'assertion_failure':
            result.verdict = observed[-1]
        else:
            first, second = result.runs
            same_environment = all(first[key] == second[key] and first[key] is not None for key in
                                   ('image_id', 'input_digest', 'profile_digest', 'source_sha'))
            common = {(item['node_id'], item['signature']) for item in failures[0]} & {
                (item['node_id'], item['signature']) for item in failures[1]}
            same_tests = ({(item['node_id'], item['phase'], item['outcome'], item['signature'])
                           for item in first['test_report']['tests']} ==
                          {(item['node_id'], item['phase'], item['outcome'], item['signature'])
                           for item in second['test_report']['tests']})
            if not same_environment or attempts[0] == attempts[1] or first['run_id'] == second['run_id']:
                result.verdict = 'runner_failure'
            elif common and same_tests:
                result.verdict = 'reproduced'
                result.failing_test_id, result.failure_signature = min(common)
            else:
                result.verdict = 'flaky_inconclusive'
        snippets = []
        if result.verdict == 'reproduced':
            failure = next(item for item in failures[0] if item['node_id'] == result.failing_test_id)
            try:
                snippets = relevant_snippets(self.access.manager, workspace, failure, self.jobs.redactor)
            except (SourceError, OSError, ValueError):
                result.verdict = 'runner_failure'
                result.failing_test_id = result.failure_signature = None
        artifact = self.jobs.redactor.clean({**asdict(result), 'schema': 1,
                    'command': list(self.access.profile.test_command), 'snippets': snippets,
                    'untrusted_repository_data': True,
                    'claim': 'configured suite observation only; not a claim that the repository is bug-free'})
        directory = self.access.manager.path(workspace) / 'detection-receipts'
        no_links(directory)
        directory.mkdir(exist_ok=True)
        payload = canonical(artifact)
        digest = hashlib.sha256(payload).hexdigest()
        with (directory / (uuid.uuid4().hex + '.json')).open('xb') as stream:
            stream.write(payload)
        self.jobs.record_detection(lease, verdict=result.verdict, artifact_digest=digest, runs=proofs,
                                   node_id=result.failing_test_id, signature=result.failure_signature)
        result.artifact_digest = digest
        if result.verdict == 'blocked':
            return result  # Retry after operator fixes infrastructure; budgets remain persistent.
        if result.verdict in ('reproduced', 'no_reproducible_bug'):
            target, reason = JobState(result.verdict), None
        else:
            target = JobState.FAILED
            reason = FailureReason.REPRODUCTION if result.verdict in ('inconclusive', 'flaky_inconclusive') else FailureReason.ENVIRONMENT
        self.jobs.advance(lease, target, failure_reason=reason)
        result.state_updated = True
        return result
