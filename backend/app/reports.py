"""Bounded read-only dashboard projections. No target execution, effects or raw logs."""

import hashlib
import json
import re
from contextlib import closing
from pathlib import Path

from backend.app.api_models import JobReport
from backend.app.domain import JobState
from worker.source_common import Budget, SourceError, no_links
from worker.workspaces import WorkspaceManager


def job_report(service, job_id):
    with closing(service.db.connect()) as connection:
        connection.execute('BEGIN')
        job = service._row(connection, job_id)
        dispatch = connection.execute('SELECT * FROM job_dispatch WHERE job_id=?', (job_id,)).fetchone()
        snapshot = connection.execute('SELECT * FROM source_snapshots WHERE job_id=?', (job_id,)).fetchone()
        detection = connection.execute("SELECT * FROM evidence WHERE job_id=? AND kind='detection' "
                                       'ORDER BY rowid DESC LIMIT 1', (job_id,)).fetchone()
        rounds = connection.execute('SELECT * FROM verification_rounds WHERE job_id=? ORDER BY round DESC LIMIT 10',
                                    (job_id,)).fetchall()
        intent = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (job_id,)).fetchone()
        publication = connection.execute('SELECT * FROM publications WHERE job_id=?', (job_id,)).fetchone()
        proof = service._verification(connection, job_id)
        proof = dict(proof) if proof else None
    redactor = service.redactor

    def text(value, cap=512):
        return redactor.text(value)[:cap] if isinstance(value, str) else None

    manager = workspace = None
    if snapshot:
        try:
            root = Path(service.settings.workspace_root)
            no_links(root)
            if not (root / '.webguard-owner.json').is_file():
                raise SourceError('source_missing')
            manager = WorkspaceManager(root)
            workspace = manager.reopen(job_id, dict(snapshot), Budget(2))
        except (SourceError, OSError, ValueError):
            manager = workspace = None

    def artifact(folder, digest, cap):
        if manager is None or workspace is None or not digest or not re.fullmatch(r'[0-9a-f]{64}', digest):
            return None
        try:
            directory = manager.path(workspace) / folder
            no_links(directory)
            for index, path in enumerate(directory.glob('*.json')):
                if index >= 100:
                    break
                no_links(path)
                if path.stat().st_size > cap or path.stat().st_nlink != 1:
                    continue
                with path.open('rb') as stream:
                    raw = stream.read(cap + 1)
                if len(raw) <= cap and hashlib.sha256(raw).hexdigest() == digest:
                    value = json.loads(raw)
                    return value if isinstance(value, dict) else None
        except (OSError, SourceError, ValueError, RecursionError):
            pass
        return None

    result = {'version': job['version'], 'stage': text(dispatch['stage']) if dispatch else None,
              'paused': bool(dispatch['paused']) if dispatch else False,
              'reason': text(dispatch['reason']) if dispatch else None,
              'next_run_at': dispatch['next_run_at'] or None if dispatch else None,
              'cleanup_completed': bool(dispatch['terminal_cleaned']) if dispatch else False,
              'detection': {}, 'verifications': [], 'publication': None}
    if detection:
        summary = json.loads(detection['summary'])
        observed = artifact('detection-receipts', detection['artifact_digest'], 2 * job['max_output_bytes'] + 131072)
        view = {'verdict': text(summary.get('verdict')), 'node_id': text(summary.get('node_id')),
                'evidence_available': bool(observed), 'observations': []}
        if observed and observed.get('sha') == job['sha']:
            for run in observed.get('runs', [])[:2]:
                view['observations'].append({key: run.get(key) for key in ('exit_code', 'duration_seconds', 'image_id')})
            runs = observed.get('runs') or [{}]
            for test in (runs[0].get('test_report') or {}).get('tests', []):
                if test.get('assertion') and test.get('node_id') == summary.get('node_id'):
                    comparison = test.get('comparison') or {}
                    view.update(expected=text(comparison.get('expected')), actual=text(comparison.get('actual')),
                                message=text(test.get('message'), 1024), traceback=text(test.get('traceback'), 2048))
                    break
        result['detection'] = view
    for row in rounds:
        receipt = artifact('verification-receipts', row['artifact_digest'], 8 * job['max_output_bytes'] + 262144)
        checks = receipt.get('checks', {}) if receipt else {}
        if row['status'] == 'verified' and proof and proof['id'] == row['evidence_id']:
            checks = json.loads(proof['summary']).get('checks', {})
        view = {key: row[key] for key in ('round', 'status', 'image_id', 'patch_digest')}
        view.update(reason=text(row['reason']), evidence_available=bool(receipt), checks=[])
        for name in ('baseline_regression', 'original', 'suite', 'patched_regression'):
            check = checks.get(name)
            if check:
                view['checks'].append({'name': name, 'exit_code': check.get('exit_code'),
                    'passed': min(256, len(check.get('passed_nodes', []))), 'failed': min(256, len(check.get('failed_nodes', []))),
                    'command': [text(value, 512) for value in check.get('command', [])[:32]]})
        result['verifications'].append(view)
    if intent and intent['repository'] == job['repository'] == service.settings.allowed_repository:
        confirmed = bool(publication and intent['phase'] == 'completed' and not intent['stale'] and proof
            and job['state'] == JobState.DRAFT_PR_CREATED and intent['base_sha'] == job['sha']
            and intent['patch_digest'] == proof['patch_digest'] and intent['evidence_digest'] == proof['artifact_digest']
            and publication['patch_digest'] == intent['patch_digest'] and publication['sha'] == job['sha']
            and publication['pr_number'] == intent['pr_number'] and publication['branch'] == intent['branch']
            and re.fullmatch(r'[0-9a-f]{40}', intent['commit_sha'] or ''))
        simulated = intent['mode'] != 'live'
        number = intent['pr_number']
        expected = f"https://github.com/{job['repository']}/pull/{number}" if number else None
        live_url = expected if (confirmed and not simulated and type(number) is int and number > 0
                               and re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9_.-]*', job['repository'])
                               and intent['pr_url'] == publication['url'] == expected) else None
        result['publication'] = {'simulated': simulated, 'confirmed': confirmed,
            'branch': text(intent['branch']), 'commit_sha': text(intent['commit_sha']), 'pr_number': number,
            'live_url': live_url, 'reason': text(intent['last_error'])}
    return JobReport.model_validate(redactor.clean(result))
