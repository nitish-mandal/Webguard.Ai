"""Verified exact-patch publication with durable intent and lookup-before-create recovery."""

import json
import re
from dataclasses import dataclass
from types import SimpleNamespace

from backend.app.domain import BudgetExceeded, Conflict, JobState, LeaseLost
from worker.docker_runner import DockerRunner
from worker.github_publishers import FakeGitHubPublisher, LiveGitHubPublisher, PublicationError
from worker.patches import apply_edits
from worker.repair_models import RepairError
from worker.source_common import SourceError
from worker.verification import VerificationError, VerificationService, read_artifact


@dataclass
class PublicationResult:
    outcome: str
    reason: str | None = None
    publication: dict | None = None
    simulated: bool = True


def markdown(value, redactor, limit=1500):
    text = redactor.text(str(value))[:limit].replace('@', '[at]')
    text = ''.join(char for char in text if char in '\n\t' or ord(char) >= 32)
    return re.sub(r'([\\`*_{}\[\]()#+!<>|])', r'\\\1', text)


class PublicationService:
    def __init__(self, access, remote=None):
        self.access, self.jobs, self.manager, self.settings = access, access.jobs, access.manager, access.jobs.settings
        self.remote = remote if remote is not None else (
            LiveGitHubPublisher(self.settings) if self.settings.enable_github_draft_pr else
            FakeGitHubPublisher(self.manager.root / 'fake-github.sqlite', self.settings.allowed_repository))

    def close(self):
        close = getattr(self.remote, 'close', None)
        if close:
            close()

    def heartbeat(self, lease):
        row = self.jobs.check_lease(lease)
        if row['lease_expires_at'] - self.jobs.clock() < self.settings.lease_seconds / 2:
            self.jobs.renew(lease)
        return row

    def lost_lease(self, lease):
        current = self.jobs.get(lease.job_id)
        return PublicationResult('cancelled' if current['cancellation_requested'] else 'stale_owner', 'lease_lost',
                                 simulated=self.remote.mode == 'offline')

    def reconcile_terminal(self, job_id):
        row = self.jobs.get(job_id)
        intent = self.jobs.publication_intent(job_id)
        if row['state'] not in (JobState.CANCELLED, JobState.FAILED) or not intent or intent['mode'] != self.remote.mode:
            return 'not_applicable'
        # A PR is sent only after the validated branch commit is durably recorded.
        # Reads never reconstruct a patch or initiate a branch/PR after cancellation.
        if not intent['commit_sha']:
            return 'not_observed'
        try:
            self.remote.start(lambda: None)
            self.remote.authorize(row['repository'])
            number = self.remote.draft(intent, intent['commit_sha'])
            self.jobs.record_interrupted_draft(job_id, marker=intent['marker'],
                commit_sha=intent['commit_sha'], pr_number=number)
            return 'draft_exists' if number else 'not_observed'
        except (PublicationError, KeyError, ValueError, TypeError, AttributeError, OSError):
            self.jobs.record_interrupted_draft(job_id, marker=intent['marker'],
                commit_sha=intent['commit_sha'], pr_number=None, observation='outcome_unknown')
            return 'outcome_unknown'

    def _prepare(self, lease):
        proof = self.jobs.publication_proof(lease)
        row = self.jobs.check_lease(lease)
        candidates = [item for item in self.jobs.candidates(lease.job_id) if item['status'] == 'verified'
                      and item['id'] == proof['summary']['candidate_id'] and item['patch_digest'] == proof['patch_digest']]
        rounds = [item for item in self.jobs.verification_rounds(lease.job_id)
                  if item['id'] == proof['summary']['verification_id'] and item['status'] == 'verified'
                  and item['sha'] == row['sha'] and item['evidence_id'] == proof['id']]
        if len(candidates) != 1 or len(rounds) != 1:
            raise PublicationError('unverified_evidence')
        candidate, round_ = candidates[0], rounds[0]
        runner = DockerRunner(self.manager, round_['image_id'])
        try:
            workspace, prepared, _, _, _ = VerificationService(self.access, SimpleNamespace(jobs=self.jobs, runner=runner))._prepare(lease, candidate)
        finally:
            runner.client.close()
        verified = read_artifact(self.manager, workspace, 'verification-receipts', proof['artifact_digest'],
                                 8 * row['max_output_bytes'] + 262144)
        if (verified.get('outcome') != 'verified' or verified.get('sha') != row['sha']
                or verified.get('patch_digest') != candidate['patch_digest']
                or verified.get('candidate_id') != candidate['id'] or verified.get('round_id') != round_['id']
                or verified.get('image_id') != round_['image_id'] or verified.get('checks') != proof['summary']['checks']):
            raise PublicationError('unverified_evidence')
        attempt, digest = apply_edits(self.manager, workspace, candidate['repair_attempt'], prepared,
                                      lambda: self.heartbeat(lease))
        try:
            if digest != candidate['patch_digest']:
                raise PublicationError('unverified_evidence')
            files = {name: (attempt / name).read_bytes() for name in prepared}
            if any(self.jobs.redactor.text(value.decode('utf8')) != value.decode('utf8') for value in files.values()):
                raise PublicationError('unverified_evidence')
        finally:
            self.manager.cleanup_attempt(workspace, attempt)
        ref = row['ref'].removeprefix('refs/heads/')
        if ref.startswith(('refs/', 'webguard/jobs/')) or ref == 'webguard':
            raise PublicationError('remote_identity')
        detection_proof = self.jobs.reproduction(lease, allow_verification=True)
        detected = read_artifact(self.manager, workspace, 'detection-receipts', detection_proof['artifact_digest'],
                                 2 * row['max_output_bytes'] + 131072)
        bug = next(item for item in detected['runs'][0]['test_report']['tests']
                   if item['assertion'] and item['node_id'] == detection_proof['summary']['node_id'])
        return proof, candidate, files, ref, bug

    def body(self, intent, proof, candidate, bug):
        clean = lambda value: markdown(value, self.jobs.redactor)
        checks = []
        for name, check in proof['summary']['checks'].items():
            checks.append(f"- {clean(name)}: exit {check['exit_code']}; "
                          f"{len(check['passed_nodes'])} passed, {len(check['failed_nodes'])} failed. "
                          f"Command: {clean(json.dumps(check['command']))}")
        prefix = 'SIMULATED OFFLINE DRAFT - no GitHub PR was created.\n\n' if intent['mode'] == 'offline' else ''
        return (prefix + intent['marker'] + '\n\n'
            'Bug: reproduced assertion in ' + clean(bug['node_id']) + '.\n\n' + clean(bug['message']) + '\n\n'
            'Proposed and verified source fix: ' + clean(candidate['diagnosis']) + '\n\n'
            f"Baseline commit: {intent['base_sha']}\n\nPatch SHA256: {intent['patch_digest']}\n\n"
            f"Verification evidence SHA256: {intent['evidence_digest']}\n\n"
            'Checks actually run (unpatched regression failures are the required control):\n' + '\n'.join(checks) +
            '\n\nDraft only. The operator reviews and merges; WebGuard-AI does not merge this PR.')

    def publish(self, lease):
        row = self.jobs.get(lease.job_id)
        if row['state'] == JobState.DRAFT_PR_CREATED:
            record = self.jobs.publication(lease.job_id)
            if record and record.get('commit_sha') and record.get('marker') and record.get('mode') in ('offline', 'live'):
                return PublicationResult('draft_pr_created', publication=record, simulated=bool(record.get('simulated')))
            return PublicationResult('blocked', 'unverified_evidence')
        intent = None
        try:
            row = self.heartbeat(lease)
            if self.remote.mode == 'live' and not (self.settings.enable_github_draft_pr and self.settings.github_token
                    and self.settings.auth_token and self.settings.allowed_repository != 'demo-repository'):
                raise PublicationError('live_not_enabled')
            proof, candidate, files, base_ref, bug = self._prepare(lease)
            intent = self.jobs.prepare_publication(lease, base_ref=base_ref, mode=self.remote.mode)
            if intent['stale']:
                raise PublicationError('base_moved')
            self.remote.start(lambda: self.heartbeat(lease))
            self.remote.authorize(row['repository'])
            if self.remote.mode == 'offline':
                self.remote.seed_base(base_ref, row['sha'])  # Never resets a previously seeded/moved base.

            def check_base():
                if self.remote.base(base_ref) != row['sha']:
                    raise PublicationError('base_moved')

            check_base()
            commit = self.remote.branch(intent, files)
            if commit:
                self.jobs.note_publication(lease, phase=None if intent['phase'] == 'pr_inflight' else 'branch_ready', commit_sha=commit)
                number = self.remote.draft(intent, commit)
                if number is not None:
                    self.jobs.note_publication(lease, pr_number=number)
                    check_base()
                    record = self.jobs.finish_publication(lease, commit_sha=commit, pr_number=number)
                    return PublicationResult('draft_pr_created', publication=record, simulated=self.remote.mode == 'offline')
                if intent['phase'] == 'pr_inflight':
                    raise PublicationError('outcome_unknown')
            else:
                # A PR with the job branch but no matching ref is a collision, not permission to recreate.
                if self.remote.draft(intent, None) is not None or intent['phase'] in ('branch_inflight', 'pr_inflight'):
                    raise PublicationError('outcome_unknown')
            self.heartbeat(lease)
            try:
                current = self.jobs.get(lease.job_id)
                if current['state'] == JobState.PUBLISHING:
                    self.jobs.publication_back_to_verified(lease)
                self.jobs.advance(lease, JobState.PUBLISHING)
            except BudgetExceeded:
                raise PublicationError('publication_budget') from None
            if commit is None:
                check_base()
                self.jobs.note_publication(lease, phase='branch_inflight')
                commit = self.remote.create_branch(intent, files)
                self.heartbeat(lease)
                self.jobs.note_publication(lease, phase='branch_ready', commit_sha=commit)
            check_base()
            number = self.remote.draft(intent, commit)
            if number is None:
                self.jobs.note_publication(lease, phase='pr_inflight')
                title = ('[SIMULATED] ' if self.remote.mode == 'offline' else '') + 'WebGuard-AI verified repair ' + lease.job_id[:8]
                number = self.remote.create_draft(intent, commit, title, self.body(intent, proof, candidate, bug))
                self.heartbeat(lease)
            self.jobs.note_publication(lease, pr_number=number)
            check_base()
            record = self.jobs.finish_publication(lease, commit_sha=commit, pr_number=number)
            return PublicationResult('draft_pr_created', publication=record, simulated=self.remote.mode == 'offline')
        except LeaseLost:
            return self.lost_lease(lease)
        except PublicationError as error:
            try:
                if intent is not None:
                    self.jobs.note_publication(lease, error=error.code, stale=error.code == 'base_moved')
                    self.jobs.publication_back_to_verified(lease)
            except LeaseLost:
                return self.lost_lease(lease)
            return PublicationResult('blocked' if error.code in ('base_moved', 'outcome_unknown', 'publication_budget',
                'remote_identity', 'token_scope', 'live_not_enabled', 'unverified_evidence') else 'retryable',
                error.code, simulated=self.remote.mode == 'offline')
        except Conflict:
            return PublicationResult('blocked', 'unverified_or_cancelled', simulated=self.remote.mode == 'offline')
        except (VerificationError, RepairError, SourceError, ValueError, OSError, KeyError, TypeError, AttributeError, StopIteration):
            return PublicationResult('blocked', 'unverified_evidence', simulated=self.remote.mode == 'offline')
