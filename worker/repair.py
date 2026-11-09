"""Explicit reproduced -> proposed candidate controller. No target execution/verification."""

import hashlib
import json
import uuid
from types import SimpleNamespace

from backend.app.domain import BudgetExceeded, JobState
from worker.docker_runner import output_text
from worker.patches import apply_edits, parse_proposal, validate_edits
from worker.repair_models import INSTRUCTION, RepairError, RepairProposal
from worker.repair_providers import configured_provider
from worker.source_common import Budget, no_links
from worker.test_reports import classify
from worker.workspaces import canonical


class RepairService:
    def __init__(self, access, provider=None):
        self.access, self.jobs, self.manager = access, access.jobs, access.manager
        self.settings = self.jobs.settings
        self.provider = provider if provider is not None else configured_provider(self.settings)

    def _evidence(self, lease, *, for_verification=False):
        proof = self.jobs.reproduction(lease, allow_verification=for_verification)
        record = self.jobs.source_snapshot(lease.job_id)
        if not record or record['sha'] != proof['sha'] or record['profile_digest'] != self.access.profile.digest:
            raise RepairError('reproduction_required')
        workspace = self.manager.reopen(lease.job_id, record, Budget(self.manager.limits.seconds))
        directory = self.manager.path(workspace) / 'detection-receipts'
        no_links(directory)
        cap = 2 * self.settings.max_output_bytes + 131072
        artifact = None
        for index, path in enumerate(directory.glob('*.json')):
            if index >= 100:
                raise RepairError('reproduction_required')
            no_links(path)
            if path.stat().st_size > cap or path.stat().st_nlink != 1:
                continue
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() == proof['artifact_digest']:
                artifact = json.loads(data)
                break
        if (not artifact or artifact.get('verdict') != 'reproduced' or artifact.get('sha') != workspace.sha
                or len(artifact.get('runs', [])) != 2):
            raise RepairError('reproduction_required')
        failures = []
        for run in artifact['runs']:
            category, assertions = classify(SimpleNamespace(**run))
            failure = next((item for item in assertions if item['node_id'] == proof['summary']['node_id']
                            and item['signature'] == proof['summary']['signature']), None)
            if (category != 'assertion_failure' or failure is None or run['source_sha'] != workspace.sha
                    or run['source_manifest_digest'] != workspace.manifest_digest
                    or run['profile_digest'] != workspace.profile_digest or not run['cleanup_complete']):
                raise RepairError('reproduction_required')
            failures.append(failure)
        first, second = artifact['runs']
        if (first['run_id'] == second['run_id'] or not first['image_id']
                or any(first[key] != second[key] for key in ('image_id', 'input_digest'))):
            raise RepairError('reproduction_required')
        source = [item for item in artifact['snippets'] if item['path'] in self.access.profile.source_edit_allowlist]
        context = self.jobs.redactor.clean({'sha': workspace.sha, 'failure': {
            key: failures[0][key] for key in ('node_id', 'message', 'traceback', 'comparison', 'signature')},
            'source': source, 'untrusted_repository_data': True})
        for item in context['source']:
            item['text'] = output_text(item['text'].encode(), self.jobs.redactor, True)
        for key in ('message', 'traceback'):
            context['failure'][key] = output_text(context['failure'][key].encode(), self.jobs.redactor, True)
        size = len(canonical(context)) + len(INSTRUCTION.encode()) + len(canonical(RepairProposal.model_json_schema()))
        if not source or (not for_verification and size > self.settings.repair_input_bytes):
            raise RepairError('input_limit')
        return proof, workspace, context, size

    def propose(self, lease):
        # A bundled/exported JSON alone never authorizes a provider request.
        proof, workspace, context, size = self._evidence(lease)
        if self.provider.mode == 'gemini' and not (self.settings.enable_live_gemini and self.settings.auth_token
                                                  and self.settings.gemini_api_key and self.settings.gemini_model):
            raise RepairError('live_not_enabled')
        row = self.jobs.check_lease(lease)
        if row['state'] == JobState.REPRODUCED:
            row = self.jobs.advance(lease, JobState.REPAIRING)
        existing = [item for item in self.jobs.candidates(lease.job_id) if item['repair_attempt'] == row['repair_attempts']]
        if existing:
            return existing[0]

        def heartbeat():
            current = self.jobs.check_lease(lease)
            if current['lease_expires_at'] - self.jobs.clock() < self.settings.lease_seconds / 2:
                self.jobs.renew(lease)
            return current

        proposal = None
        for retry in range(self.settings.repair_max_retries + 1):
            current = heartbeat()
            seconds = min(self.settings.repair_call_seconds, current['deadline'] - self.jobs.clock())
            if seconds <= 0:
                raise RepairError('provider_timeout')
            try:
                self.jobs.reserve_usage(lease, model_calls=1,
                    model_tokens=size + self.settings.repair_output_tokens + 1024,
                    cost_micros=self.settings.repair_cost_micros_per_call if self.provider.mode == 'gemini' else 0)
            except BudgetExceeded:
                self.jobs.repair_observation(lease, 'budget_exhausted')
                raise RepairError('budget_exhausted') from None
            try:
                raw = self.provider.generate(context, seconds, heartbeat)
                proposal = parse_proposal(raw, self.settings.repair_output_bytes)
                break
            except RepairError as error:
                self.jobs.repair_observation(lease, error.code,
                    observation=getattr(self.provider, 'observation', None))
                if error.code not in ('provider_timeout', 'provider_unavailable') or retry == self.settings.repair_max_retries:
                    raise
        heartbeat()
        try:
            prepared, changed_lines = validate_edits(self.manager, workspace, self.access.profile,
                                                    proposal, context, row, self.jobs.redactor)
        except RepairError as error:
            self.jobs.repair_observation(lease, error.code)
            raise
        attempt, digest = apply_edits(self.manager, workspace, row['repair_attempts'], prepared, heartbeat)
        artifact = None
        try:
            diagnosis = self.jobs.redactor.text(proposal.diagnosis)
            receipt = self.jobs.redactor.clean({
                'schema': 1, 'status': 'proposed', 'verification': 'awaiting_phase8', 'sha': workspace.sha,
                'source_manifest_digest': workspace.manifest_digest, 'profile_digest': workspace.profile_digest,
                'detection_id': proof['id'], 'detection_digest': proof['artifact_digest'],
                'attempt_id': attempt.name, 'patch_digest': digest, 'provider': self.provider.mode,
                'diagnosis': diagnosis, 'edits': [edit.model_dump() for edit in proposal.edits],
                'changed_lines': changed_lines, 'prompt_digest': hashlib.sha256(canonical(context)).hexdigest(),
                'untrusted_model_data': True})
            directory = self.manager.path(workspace) / 'candidate-receipts'
            no_links(directory)
            directory.mkdir(exist_ok=True)
            artifact = directory / (uuid.uuid4().hex + '.json')
            payload = canonical(receipt)
            with artifact.open('xb') as output:
                output.write(payload)
            return self.jobs.record_candidate(lease, detection_id=proof['id'], attempt_id=attempt.name,
                manifest_digest=workspace.manifest_digest, profile_digest=workspace.profile_digest,
                patch_digest=digest, artifact_digest=hashlib.sha256(payload).hexdigest(), provider=self.provider.mode,
                diagnosis=diagnosis, changed_files=sorted(prepared))
        except BaseException:
            self.manager.cleanup_attempt(workspace, attempt)
            if artifact is not None:
                no_links(artifact)
                artifact.unlink(missing_ok=True)
            raise
