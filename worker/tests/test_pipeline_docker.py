"""Real API -> automatic worker -> Docker -> fake repair -> simulated draft acceptance."""

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.domain import JobState
from backend.app.jobs import JobService
from backend.app.main import create_app
from backend.app.settings import Settings
from worker.github_publishers import FakeGitHubPublisher
from worker.pipeline import Runtime, Worker
from worker.source_common import Budget
from worker.source_service import RepositoryAccess
from worker.tests.test_docker_isolation import real
from worker.tests.test_repositories import fixture_git, git

__all__ = ['fixture_git', 'real']
pytestmark = pytest.mark.isolation
TOKEN = 'phase10-private-local-operator-' + 'a' * 32
AUTH = {'Authorization': 'Bearer ' + TOKEN}
ROOT = Path(__file__).resolve().parents[2]


def until(check, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError('Expected automatic worker progress was not observed within its deadline')


def test_real_api_job_processed_by_worker_subprocess_and_gracefully_stopped(real, tmp_path):
    image = real[0].image_id
    config = Settings(database_url=f"sqlite:///{tmp_path / 'automatic.sqlite'}",
        workspace_root=str(tmp_path / 'automatic-owned'), runner_image_id=image, auth_token=TOKEN,
        lease_seconds=4, job_timeout_seconds=180, worker_poll_seconds=0.1,
        runner_wall_seconds=15, runner_memory_mib=128, runner_scratch_mib=32, runner_tmp_mib=8)
    env_file = tmp_path / 'private-worker.env'
    values = {key.upper(): value for key, value in config.model_dump().items() if value is not None}
    values['AUTH_TOKEN'] = TOKEN
    env_file.write_text('\n'.join(key + '=' + (str(value).lower() if isinstance(value, bool) else str(value))
                                  for key, value in values.items()), encoding='utf8')
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'DOCKER_HOST') if key in os.environ}
    bundled = [(ROOT / 'demo-repository' / path).read_bytes() for path in ('pagination.py', 'tests/test_pagination.py')]
    log = tmp_path / 'worker.jsonl'
    with TestClient(create_app(config), base_url='http://127.0.0.1:8000') as api, log.open('w', encoding='utf8') as output:
        worker = subprocess.Popen([sys.executable, '-m', 'worker', '--env-file', str(env_file)], cwd=ROOT,
                                  env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), shell=False)
        worker_id = None
        try:
            def started():
                if worker.poll() is not None:
                    raise AssertionError('Worker startup failed: ' + log.read_text(encoding='utf8'))
                lines = log.read_text(encoding='utf8').splitlines()
                return json.loads(lines[0]) if lines else None
            worker_id = until(started, 30)['worker_id']
            assert api.get('/api/status').json()['worker_available']
            accepted = api.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'phase10-auto-demo'},
                                json={'repository': 'demo-repository'})
            assert accepted.status_code == 202 and accepted.json()['state'] == 'queued'
            job_id = accepted.json()['id']
            def completed():
                row = api.get('/api/jobs/' + job_id, headers=AUTH).json()
                if row['state'] in ('failed', 'cancelled'):
                    raise AssertionError('Automatic job failed: ' + json.dumps(row))
                dispatch = api.app.state.jobs.dispatch(job_id)
                if dispatch and dispatch['paused']:
                    raise AssertionError('Automatic job blocked: ' + json.dumps(dispatch))
                return row if row['state'] == 'draft_pr_created' else None
            row = until(completed)
            jobs = api.app.state.jobs
            publication = jobs.publication(job_id)
            assert publication['simulated'] and publication['draft']
            remote = FakeGitHubPublisher(Path(config.workspace_root) / 'fake-github.sqlite', 'demo-repository')
            assert remote.draft_count() == 1
            duplicate = api.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'phase10-auto-demo'},
                                 json={'repository': 'demo-repository'})
            assert duplicate.json()['id'] == job_id and remote.draft_count() == 1
            stop = subprocess.run([sys.executable, '-m', 'worker', '--env-file', str(env_file), '--stop', worker_id],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=20, shell=False, check=False)
            assert stop.returncode == 0 and json.loads(stop.stdout)['drain_requested']
            assert worker.wait(timeout=30) == 0
            assert not api.get('/api/status').json()['worker_available']
            assert TOKEN not in log.read_text(encoding='utf8') and TOKEN.encode() not in stop.stdout + stop.stderr
            snapshot = jobs.source_snapshot(job_id)
            workspace_path = Path(config.workspace_root) / (job_id + '-' + snapshot['workspace_id'])
            assert list((workspace_path / 'attempts').iterdir()) == []
            evidence = {}
            for folder in ('detection-receipts', 'verification-receipts'):
                evidence[folder] = [json.loads(path.read_bytes()) for path in (workspace_path / folder).glob('*.json')]
            detection = evidence['detection-receipts'][0]
            verification = evidence['verification-receipts'][0]
            assert detection['verdict'] == 'reproduced' and len(detection['runs']) == 2
            assert verification['outcome'] == 'verified' and len(verification['runs']) == 4
            all_runs = detection['runs'] + list(verification['runs'].values())
            assert len({run['container_id'] for run in all_runs}) == 6
            assert all(run['cleanup_complete'] and run['image_id'] == image for run in all_runs)
            assert jobs.get(job_id)['claims'] == 1 and jobs.get(job_id)['model_calls'] == 1
            assert bundled == [(ROOT / 'demo-repository' / path).read_bytes() for path in ('pagination.py', 'tests/test_pagination.py')]
            if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
                report = {'automatic': True, 'http_status': 202, 'worker_id': worker_id, 'worker_exit': 0,
                    'startup_command': ['.venv/Scripts/python.exe', '-m', 'worker', '--env-file', '<private-settings>'],
                    'stop_command': ['.venv/Scripts/python.exe', '-m', 'worker', '--env-file', '<private-settings>', '--stop', worker_id],
                    'job': row, 'publication': publication, 'simulated_drafts': remote.draft_count(),
                    'evidence': evidence, 'fixture_unchanged': True, 'live_gemini_tested': False,
                    'live_github_tested': False, 'worker_output': log.read_text(encoding='utf8'),
                    'fixture_hashes': [hashlib.sha256(value).hexdigest() for value in bundled]}
                (ROOT / 'docs/baseline/phase10-automatic-demo.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        finally:
            if worker.poll() is None:
                if worker_id:
                    api.app.state.jobs.stop_worker(worker_id)
                try:
                    worker.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=10)
                    raise AssertionError('Worker did not drain within the acceptance cleanup deadline') from None


def test_real_api_cancellation_stops_active_target_container(real, fixture_git, tmp_path):
    (fixture_git / 'pagination.py').write_text('def page_items(*args):\n    while True:\n        pass\n', encoding='utf8')
    git(fixture_git, 'add', '--', 'pagination.py')
    git(fixture_git, 'commit', '-m', 'Temporary cancellation fixture')
    config = Settings(database_url=f"sqlite:///{tmp_path / 'cancel.sqlite'}", workspace_root=str(tmp_path / 'cancel-owned'),
        auth_token=TOKEN, runner_image_id=real[0].image_id, worker_poll_seconds=0.1,
        runner_memory_mib=128, runner_scratch_mib=32, runner_tmp_mib=8, runner_wall_seconds=15)
    jobs = JobService(config)
    runtime = Runtime(RepositoryAccess.fixture(jobs, fixture_git))
    worker = Worker(runtime)
    thread = threading.Thread(target=worker.serve)
    try:
        thread.start()
        with TestClient(create_app(config), base_url='http://127.0.0.1:8000') as api:
            response = api.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'cancel-real'}, json={'repository': 'demo-repository'})
            assert response.status_code == 202
            job_id = response.json()['id']
            def running():
                return runtime.runner.client.command(['container', 'ls', '--filter', 'label=io.webguard.job=' + job_id,
                    '--filter', 'label=io.webguard.role=test', '--format', '{{.ID}}']).strip()
            assert until(running, 45)
            cancelled = api.post('/api/jobs/' + job_id + '/cancel', headers=AUTH, json={})
            assert cancelled.status_code == 200
            until(lambda: jobs.dispatch(job_id) and jobs.dispatch(job_id)['terminal_cleaned'], 30)
            assert jobs.get(job_id)['state'] == JobState.CANCELLED and jobs.publication(job_id) is None
            assert not running()
            snapshot = jobs.source_snapshot(job_id)
            workspace = runtime.manager.reopen(job_id, snapshot, Budget(5))
            assert not list((runtime.manager.path(workspace) / 'attempts').iterdir())
            if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
                (ROOT / 'docs/baseline/phase10-cancellation.json').write_text(json.dumps({
                    'http_status': cancelled.status_code, 'state': jobs.get(job_id)['state'],
                    'active_container_stopped': True, 'attempts_removed': True, 'simulated_drafts': 0}), encoding='utf8')
    finally:
        worker.stopping.set()
        thread.join(timeout=35)
        assert not thread.is_alive()
        assert all(runtime.runner.recover(min_age_seconds=0).values())
        runtime.close()
