"""Real TCP API/worker/Vite + Docker acceptance. This is NOT browser acceptance."""

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def wait_for(check, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (httpx.HTTPError, ValueError, FileNotFoundError):
            pass
        time.sleep(0.2)
    raise RuntimeError('Acceptance condition not observed within deadline')


def main():
    image = os.environ.get('WEBGUARD_ISOLATION_IMAGE')
    if not image:
        print(json.dumps({'api_stack_acceptance': 'blocked', 'reason': 'prepared_image_required', 'browser': 'not_run'}))
        return 2
    # Dedicated loopback ports match the service's explicit CORS/client policy.
    import socket
    for port in (8000, 5173):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                print(json.dumps({'api_stack_acceptance': 'blocked', 'reason': 'port_in_use', 'port': port, 'browser': 'not_run'}))
                return 2
    runroot = ROOT / '.tools' / ('phase11-api-' + uuid.uuid4().hex)
    runroot.mkdir(parents=True)
    token = uuid.uuid4().hex + uuid.uuid4().hex
    configuration = runroot / 'private.env'
    configuration.write_text('\n'.join([
        'APP_ENV=test', f'DATABASE_URL=sqlite:///{runroot / "jobs.sqlite"}',
        f'WORKSPACE_ROOT={runroot / "owned"}', 'ALLOWED_REPOSITORY=demo-repository', f'AUTH_TOKEN={token}',
        'ENABLE_LIVE_GEMINI=false', 'ENABLE_GITHUB_DRAFT_PR=false', 'WORKER_POLL_SECONDS=0.2',
        'LEASE_SECONDS=4', 'JOB_TIMEOUT_SECONDS=180', f'RUNNER_IMAGE_ID={image}',
        'RUNNER_MEMORY_MIB=128', 'RUNNER_SCRATCH_MIB=32', 'RUNNER_TMP_MIB=8', 'RUNNER_WALL_SECONDS=15']), encoding='utf8')
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'DOCKER_HOST') if key in os.environ}
    node = ROOT / '.tools/node-v22.16.0-win-x64/node.exe'
    if not node.is_file():
        configuration.unlink()
        print(json.dumps({'api_stack_acceptance': 'blocked', 'reason': 'local_node_missing', 'browser': 'not_run'}))
        return 2
    processes, streams = {}, []
    commands = {
        'api': [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000',
                '--env-file', str(configuration), '--no-proxy-headers', '--no-access-log'],
        'worker': [sys.executable, '-m', 'worker', '--env-file', str(configuration)],
        'frontend': [str(node), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1',
                     '--port', '5173', '--strictPort'],
    }
    before = [(ROOT / 'demo-repository' / path).read_bytes() for path in ('pagination.py', 'tests/test_pagination.py')]
    receipt = {'api_stack_acceptance': 'failed', 'browser': 'not_run', 'gemini': 'offline_fake', 'github': 'simulated'}
    try:
        for name, command in commands.items():
            output = (runroot / (name + '.log')).open('wb')
            streams.append(output)
            processes[name] = subprocess.Popen(command, cwd=ROOT / 'frontend' if name == 'frontend' else ROOT,
                env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output, shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            wait_for(lambda: client.get('http://127.0.0.1:8000/ready').status_code == 200, 25)
            index = wait_for(lambda: (response if (response := client.get('http://127.0.0.1:5173')).status_code == 200 else None), 25)
            assert '/src/main.tsx' in index.text
            status = wait_for(lambda: (data if (data := client.get('http://127.0.0.1:8000/api/status').json())['worker_available'] else None), 25)
            assert status['approved_repository'] == 'demo-repository' and status['mode'] == 'offline'
            origin = {'Origin': 'http://127.0.0.1:5173'}
            preflight = client.options('http://127.0.0.1:8000/api/jobs', headers={**origin,
                'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type,idempotency-key'})
            assert preflight.status_code == 200 and preflight.headers['access-control-allow-origin'] == origin['Origin']
            headers = {**origin, 'Authorization': 'Bearer ' + token}
            key = 'phase11-real-api-' + uuid.uuid4().hex
            created = client.post('http://127.0.0.1:8000/api/jobs', headers={**headers, 'Idempotency-Key': key},
                                  json={'repository': 'demo-repository', 'ref': 'main'})
            assert created.status_code == 202
            job_id = created.json()['id']
            def completed():
                response = client.get('http://127.0.0.1:8000/api/jobs/' + job_id, headers=headers)
                assert response.status_code == 200
                job = response.json()
                if job['state'] == 'failed':
                    raise RuntimeError('Automatic demo failed: ' + str(job['failure_reason']))
                return job if job['state'] == 'draft_pr_created' else None
            job = wait_for(completed, 120)
            report_url = 'http://127.0.0.1:8000/api/jobs/' + job_id + '/report'
            assert client.get(report_url).status_code == 401
            report = client.get(report_url, headers=headers).json()
            assert report['detection']['verdict'] == 'reproduced' and report['detection']['expected'] == '[10, 20]'
            assert report['detection']['actual'] == '[10]' and len(report['detection']['observations']) == 2
            assert report['verifications'][0]['status'] == 'verified' and len(report['verifications'][0]['checks']) == 4
            assert report['publication']['simulated'] and report['publication']['confirmed'] and report['publication']['live_url'] is None
            duplicate = client.post('http://127.0.0.1:8000/api/jobs', headers={**headers, 'Idempotency-Key': key},
                json={'repository': 'demo-repository', 'ref': 'main'})
            assert duplicate.status_code == 202 and duplicate.json()['id'] == job_id
            events = client.get('http://127.0.0.1:8000/api/jobs/' + job_id + '/events?limit=100', headers=headers).json()
            from backend.app.jobs import JobService
            from backend.app.settings import load_settings
            from worker.github_publishers import FakeGitHubPublisher

            jobs = JobService(load_settings(configuration, {}))
            remote = FakeGitHubPublisher(runroot / 'owned/fake-github.sqlite', 'demo-repository')
            assert remote.draft_count() == 1
            snapshot = jobs.source_snapshot(job_id)
            owned = runroot / 'owned' / (job_id + '-' + snapshot['workspace_id'])
            detection = next(item for item in jobs.evidence(job_id) if item['kind'] == 'detection' and item['exit_code'] == 1)
            verification = next(item for item in jobs.verification_rounds(job_id) if item['status'] == 'verified')
            runs = []
            for folder, digest in (('detection-receipts', detection['artifact_digest']),
                                   ('verification-receipts', verification['artifact_digest'])):
                matches = [path.read_bytes() for path in (owned / folder).glob('*.json')
                           if path.stat().st_size <= 1048576]
                artifact = json.loads(next(raw for raw in matches if hashlib.sha256(raw).hexdigest() == digest))
                runs.extend(artifact['runs'] if isinstance(artifact['runs'], list) else artifact['runs'].values())
            assert len(runs) == len({run['container_id'] for run in runs}) == 6
            assert all(run['cleanup_complete'] and run['image_id'] == image and run['source_sha'] == job['sha'] for run in runs)
            assert before == [(ROOT / 'demo-repository' / path).read_bytes() for path in ('pagination.py', 'tests/test_pagination.py')]
            receipt.update(api_stack_acceptance='passed', frontend_http=index.status_code, api_http=created.status_code,
                cors_preflight=preflight.status_code, report_http=200, unauthenticated_report_http=401,
                job=job, report=report, events=events, simulated_drafts=1, fixture_unchanged=True,
                image_id=image, claims=jobs.get(job_id)['claims'], live_gemini_tested=False, live_github_tested=False,
                docker_runs=[{key: run[key] for key in ('run_id', 'container_id', 'source_sha', 'image_id',
                    'outcome', 'exit_code', 'duration_seconds', 'cleanup_complete', 'effective_settings')} for run in runs])
    except (RuntimeError, AssertionError, OSError, httpx.HTTPError, KeyError, ValueError):
        receipt['reason'] = 'api_stack_acceptance_failed_see_owned_service_logs'
    finally:
        worker = processes.get('worker')
        if worker and worker.poll() is None:
            try:
                first = (runroot / 'worker.log').read_text(encoding='utf8').splitlines()[0]
                worker_id = json.loads(first)['worker_id']
                stop = subprocess.run([sys.executable, '-m', 'worker', '--env-file', str(configuration), '--stop', worker_id],
                    cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=15, shell=False, check=False)
                receipt['stop_request_exit'] = stop.returncode
                receipt['worker_exit'] = worker.wait(timeout=35)
            except (OSError, ValueError, IndexError, KeyError, subprocess.TimeoutExpired):
                worker.kill()
                worker.wait(timeout=10)
                receipt.update(api_stack_acceptance='failed', reason='worker_drain_failed')
        for name in ('api', 'frontend'):
            process = processes.get(name)
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        for stream in streams:
            stream.close()
        configuration.unlink(missing_ok=True)
        (ROOT / 'docs/baseline/phase11-api-stack.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps({key: receipt.get(key) for key in ('api_stack_acceptance', 'browser', 'simulated_drafts', 'worker_exit', 'reason')}, sort_keys=True))
    return 0 if receipt['api_stack_acceptance'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
