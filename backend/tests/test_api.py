import asyncio
import base64
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.domain import FailureReason, JobState, LeaseLost
from backend.app.http_security import MAX_BODY_BYTES, PrivateAccessLogFilter
from backend.app.jobs import JobService
from backend.app.main import create_app
from backend.app.settings import Settings

TOKEN = 'local-operator-test-token-1234567890'
SECRET = 'private-provider-test-key-987654321'
AUTH = {'Authorization': f'Bearer {TOKEN}'}
BASE = 'http://127.0.0.1:8000'
UNKNOWN = '0' * 32


@pytest.fixture
def configured(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'api.sqlite'}", auth_token=TOKEN,
                    gemini_api_key=SECRET, github_token='private-github-test-token-24680')


@pytest.fixture
def client(configured):
    with TestClient(create_app(configured), base_url=BASE) as session:
        yield session


def submit(client, key='request-1', **payload):
    return client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': key},
                       json={'repository': 'demo-repository', **payload})


def test_health_status_and_readiness_are_honest(client):
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/ready').json() == {'status': 'ready', 'database_ready': True}
    data = client.get('/api/status').json()
    assert data['mode'] == 'offline'
    assert data['job_api_enabled'] is True
    assert data['processing_enabled'] is False
    assert data['repair_enabled'] is False
    assert not data['live_gemini_configured']
    assert not data['live_github_configured']
    assert TOKEN not in json.dumps(data) and SECRET not in json.dumps(data)


def test_status_tracks_live_worker_heartbeat_and_graceful_drain(client):
    worker = 'd' * 32
    service = client.app.state.jobs
    service.worker_session(worker, start=True)
    data = client.get('/api/status').json()
    assert data['worker_available'] and data['processing_enabled'] and data['repair_enabled']
    service.stop_worker(worker)
    assert not client.get('/api/status').json()['worker_available']
    service.worker_session(worker, stopped=True)
    assert not service.worker_available()


@pytest.mark.parametrize('method,path', [
    ('POST', '/api/jobs'), ('GET', '/api/jobs'), ('GET', f'/api/jobs/{UNKNOWN}'),
    ('GET', f'/api/jobs/{UNKNOWN}/events'), ('POST', f'/api/jobs/{UNKNOWN}/cancel'),
])
@pytest.mark.parametrize('header', [None, 'Bearer incorrect', f'Basic {TOKEN}', f'Bearer  {TOKEN}'])
def test_every_job_route_authenticates_before_validation_or_lookup(client, method, path, header):
    headers = {} if header is None else {'Authorization': header}
    response = client.request(method, path, headers=headers, content=b'{invalid')
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized'
    assert response.headers['www-authenticate'] == 'Bearer'
    assert TOKEN not in response.text
    assert client.app.state.jobs.list_jobs() == []


def test_no_cookie_or_query_auth_and_duplicate_headers_rejected(client):
    for headers, query in [({'Cookie': f'auth_token={TOKEN}'}, ''),
                           ({}, f'?token={TOKEN}'),
                           ([('Authorization', f'Bearer {TOKEN}'), ('Authorization', f'Bearer {TOKEN}')], '')]:
        assert client.get('/api/jobs' + query, headers=headers).status_code == 401


def test_no_configured_auth_disables_all_job_access(configured):
    app = create_app(configured.model_copy(update={'auth_token': None}))
    with TestClient(app, base_url=BASE) as session:
        assert session.get('/health').status_code == 200
        assert session.get('/ready').status_code == 200
        assert not session.get('/api/status').json()['job_api_enabled']
        for method, path in [('POST', '/api/jobs'), ('GET', '/api/jobs'),
                             ('GET', f'/api/jobs/{UNKNOWN}'),
                             ('GET', f'/api/jobs/{UNKNOWN}/events'),
                             ('POST', f'/api/jobs/{UNKNOWN}/cancel')]:
            response = session.request(method, path, headers=AUTH)
            assert response.status_code == 503
            assert response.json()['error']['code'] == 'auth_not_configured'


def test_accepted_only_after_durable_storage_and_never_executes(client, configured, monkeypatch):
    import worker.pipeline

    def forbidden(*args, **kwargs):
        raise AssertionError('HTTP must never execute a repair')

    monkeypatch.setattr(worker.pipeline, 'run_job', forbidden)
    result = submit(client)
    assert result.status_code == 202
    job = result.json()
    assert result.headers['location'] == f"/api/jobs/{job['id']}"
    assert job['state'] == 'queued'
    assert job['model_calls'] == job['repair_attempts'] == 0
    assert job['sha'] is None
    assert JobService(configured).get(job['id'])['state'] == 'queued'
    assert client.get(result.headers['location'], headers=AUTH).json() == job
    events = client.get(result.headers['location'] + '/events', headers=AUTH).json()
    assert events['items'][0]['kind'] == 'created'
    assert len(events['items']) == 1
    for private in ('idempotency_hash', 'payload_hash', 'lease_owner', 'fence', 'database_url'):
        assert private not in job


@pytest.mark.parametrize('payload', [
    {'repository': 'attacker/repo'}, {'repository': 'https://github.com/owner/repo'},
    {'repository': 'file:///tmp/target'}, {'repository': '../demo-repository'},
    {'repository': 'C:\\target'}, {'repository': '/tmp/target'},
    {'command': 'pytest'}, {'path': '/tmp/target'}, {'state': 'verified'},
    {'fixture_path': '/tmp/target'}, {'workspace_root': '/tmp/target'},
    {'ref': '../outside'}, {'ref': 'main; whoami'}, {'ref': 'a//b'},
    {'ref': '/absolute'}, {'sha': 'short'}, {'sha': 'A' * 40}, {'ref': 42},
    {'repository': None}, {'ref': SECRET}, {'ref': 'a' * 201},
])
def test_invalid_unapproved_or_executable_input_is_rejected(client, payload):
    response = submit(client, **payload)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invalid_input'
    assert SECRET not in response.text
    assert client.app.state.jobs.list_jobs() == []


@pytest.mark.parametrize('body', [b'{', b'[]', b'null', b'{"repository":"demo-repository","repository":"attacker/repo"}',
                                  b'{"repository":NaN}', b'\xff'])
def test_malformed_json_never_echoes_inputs(client, body):
    response = client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'key',
                                                'Content-Type': 'application/json'}, content=body)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invalid_input'


@pytest.mark.parametrize('key', ['', 'contains space', 'x' * 201])
def test_bad_idempotency_keys(client, key):
    assert submit(client, key=key).status_code == 422


def test_missing_duplicate_keys_and_extra_query_fields(client):
    response = client.post('/api/jobs', headers=AUTH, json={'repository': 'demo-repository'})
    assert response.status_code == 422
    response = client.post('/api/jobs', headers=[('Authorization', f'Bearer {TOKEN}'),
                                                ('Idempotency-Key', 'one'), ('Idempotency-Key', 'two')],
                           json={'repository': 'demo-repository'})
    assert response.status_code == 422
    for url in ('/api/jobs?command=pytest', '/api/jobs?limit=1&limit=2', '/api/jobs?token=secret'):
        assert client.get(url, headers=AUTH).status_code == 422
    assert client.post('/api/jobs?ref=main', headers={**AUTH, 'Idempotency-Key': 'one'},
                       json={'repository': 'demo-repository'}).status_code == 422


def test_duplicate_submissions_and_conflicting_payloads(client):
    first = submit(client)
    duplicate = submit(client, ref='main', sha=None)
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    conflict = submit(client, ref='different')
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'idempotency_conflict'
    assert len(client.app.state.jobs.list_jobs()) == 1
    assert len(client.app.state.jobs.events(first.json()['id'])) == 1


def test_concurrent_http_creates_still_have_one_durable_job(client):
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: submit(client, key='same-concurrent-key'), range(6)))
    assert all(result.status_code == 202 for result in results)
    assert len({result.json()['id'] for result in results}) == 1
    assert len(client.app.state.jobs.list_jobs()) == 1


def test_restart_preserves_job_events_cancellation_and_idempotency(configured):
    with TestClient(create_app(configured), base_url=BASE) as first:
        job = submit(first).json()
        first.post(f"/api/jobs/{job['id']}/cancel", headers=AUTH)
    with TestClient(create_app(configured), base_url=BASE) as restarted:
        detail = restarted.get(f"/api/jobs/{job['id']}", headers=AUTH).json()
        assert detail['state'] == 'cancelled'
        assert detail['cancellation_requested'] is True
        duplicate = submit(restarted)
        assert duplicate.status_code == 202
        assert duplicate.json() == detail
        assert len(restarted.get('/api/jobs', headers=AUTH).json()['items']) == 1
        events = restarted.get(f"/api/jobs/{job['id']}/events", headers=AUTH).json()['items']
        assert [event['kind'] for event in events] == ['created', 'state_changed']


def test_jobs_and_events_cursor_pagination(client):
    expected = {submit(client, key=f'job-{i}').json()['id'] for i in range(4)}
    seen = []
    cursor = None
    for _ in range(6):
        page = client.get('/api/jobs', headers=AUTH,
                          params={'limit': 2, **({'cursor': cursor} if cursor else {})}).json()
        seen.extend(job['id'] for job in page['items'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 4
    assert set(seen) == expected
    lease = client.app.state.jobs.claim('worker-private')
    client.app.state.jobs.advance(lease, JobState.BASELINING)
    url = f'/api/jobs/{lease.job_id}/events'
    first = client.get(url + '?limit=1', headers=AUTH).json()
    second = client.get(url, headers=AUTH, params={'after': first['next_cursor'], 'limit': 100}).json()
    events = first['items'] + second['items']
    assert [event['sequence'] for event in events] == [1, 2, 3]
    assert 'worker-private' not in json.dumps(events)
    assert 'fence' not in json.dumps(events)


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'cursor=not-base64', 'cursor=%%%'])
def test_invalid_job_pagination(client, query):
    assert client.get('/api/jobs?' + query, headers=AUTH).status_code == 422


@pytest.mark.parametrize('value', [[-1, UNKNOWN], [float('nan'), UNKNOWN], [True, UNKNOWN], [1, '../path'], {}, [1e300, UNKNOWN]])
def test_invalid_decoded_cursors(client, value):
    cursor = base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    response = client.get('/api/jobs', headers=AUTH, params={'cursor': cursor})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invalid_input'


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'after=-1', 'after=no', 'after=9223372036854775808', 'command=pytest'])
def test_invalid_event_pagination(client, query):
    job = submit(client).json()
    response = client.get(f"/api/jobs/{job['id']}/events?{query}", headers=AUTH)
    assert response.status_code == 422


@pytest.mark.parametrize('method,suffix', [('GET', ''), ('GET', '/events'), ('POST', '/cancel')])
def test_unknown_ids_are_consistent_and_do_not_leak(client, method, suffix):
    response = client.request(method, f'/api/jobs/{UNKNOWN}{suffix}', headers=AUTH)
    assert response.status_code == 404
    assert response.json() == {'error': {'code': 'unknown_job', 'message': 'Job not found.'}}
    malformed = client.request(method, f'/api/jobs/not-an-id{suffix}', headers=AUTH)
    assert malformed.status_code == 422


def test_cancellation_persists_fences_owner_and_never_claims_executor_stopped(client):
    job = submit(client).json()
    service = client.app.state.jobs
    lease = service.claim('worker')
    service.advance(lease, JobState.BASELINING)
    url = f"/api/jobs/{job['id']}/cancel"
    response = client.post(url, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data['job']['state'] == 'cancelled'
    assert data['job']['cancellation_requested'] is True
    assert data['execution_stop_confirmed'] is False
    assert client.post(url, headers=AUTH, json={}).json() == data
    with pytest.raises(LeaseLost):
        service.renew(lease)
    assert client.post(url, headers=AUTH, json={'command': 'stop'}).status_code == 422


def test_other_terminal_outcomes_are_protected(client):
    job = submit(client).json()
    service = client.app.state.jobs
    lease = service.claim('worker')
    service.advance(lease, JobState.FAILED, failure_reason=FailureReason.ENVIRONMENT)
    before = service.get(job['id'])
    response = client.post(f"/api/jobs/{job['id']}/cancel", headers=AUTH)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'terminal_state_conflict'
    assert service.get(job['id']) == before


def test_storage_failure_never_returns_202_or_raw_error(client, monkeypatch, caplog):
    service = client.app.state.jobs

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError(f'database failure with {SECRET} {TOKEN}')

    monkeypatch.setattr(service, '_event', fail)
    result = submit(client)
    assert result.status_code == 503
    assert result.json()['error']['code'] == 'storage_unavailable'
    assert service.list_jobs() == []
    assert SECRET not in result.text + caplog.text
    assert TOKEN not in result.text + caplog.text


def test_commit_failure_rolls_back_before_acceptance_and_key_can_retry(client, monkeypatch):
    service = client.app.state.jobs
    original = service._event

    def fail_at_commit(connection, *args):
        original(connection, *args)
        connection.execute('PRAGMA defer_foreign_keys=ON')
        connection.execute("INSERT INTO events VALUES ('missing-job', 1, 0, 'invalid', '{}')")

    monkeypatch.setattr(service, '_event', fail_at_commit)
    response = submit(client)
    assert response.status_code == 503
    assert service.list_jobs() == []
    monkeypatch.setattr(service, '_event', original)
    assert submit(client).status_code == 202


def test_unexpected_errors_are_redacted(client, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError(f'private failure {SECRET} {TOKEN}')

    monkeypatch.setattr(client.app.state.jobs, 'list_jobs', fail)
    result = client.get('/api/jobs', headers=AUTH)
    assert result.status_code == 500
    assert result.json()['error']['code'] == 'internal_error'
    assert SECRET not in result.text + caplog.text
    assert TOKEN not in result.text + caplog.text


def test_liveness_differs_from_readiness_when_database_breaks(client, monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError(SECRET)

    monkeypatch.setattr(client.app.state.jobs.db, 'connect', fail)
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503
    assert not client.get('/api/status').json()['database_ready']
    assert not client.get('/api/status').json()['job_api_enabled']
    assert submit(client).status_code == 503


def test_readiness_checks_actual_sqlite_write_access(client, configured, monkeypatch):
    def readonly():
        return sqlite3.connect(f'file:{configured.database_path.as_posix()}?mode=ro', uri=True,
                               isolation_level=None)

    monkeypatch.setattr(client.app.state.jobs.db, 'connect', readonly)
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503
    assert submit(client).status_code == 503


@pytest.mark.parametrize('table', ['events', 'evidence', 'publications', 'publication_intents', 'job_dispatch', 'worker_sessions'])
def test_readiness_detects_missing_storage_tables(client, table):
    with client.app.state.jobs.db.transaction() as connection:
        connection.execute(f'DROP TABLE {table}')  # Fixed parametrized names, never HTTP input.
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503
    assert not client.get('/api/status').json()['database_ready']


def test_simulated_publication_event_is_explicit_and_redacted(client):
    job = submit(client).json()
    service = client.app.state.jobs
    with service.db.transaction() as connection:
        service._event(connection, job['id'], 'draft_pr_recorded',
                       {'pr_number': 1, 'commit_sha': 'a' * 40, 'simulated': True,
                        'draft': True, 'private_body': SECRET}, service.clock())
    result = client.get(f"/api/jobs/{job['id']}/events", headers=AUTH)
    assert result.status_code == 200
    event = next(item for item in result.json()['items'] if item['kind'] == 'draft_pr_recorded')
    assert event['data']['simulated'] and event['data']['draft']
    assert 'private_body' not in event['data'] and SECRET not in result.text


def test_detail_query_fields_and_unimplemented_mutation_routes_are_rejected(client):
    job = submit(client).json()
    assert client.get(f"/api/jobs/{job['id']}?token=hidden", headers=AUTH).status_code == 422
    assert client.post(f"/api/jobs/{job['id']}/cancel?command=stop", headers=AUTH).status_code == 422
    for action in ('run', 'retry', 'advance'):
        response = client.post(f"/api/jobs/{job['id']}/{action}", headers=AUTH)
        assert response.status_code == 404
    assert client.app.state.jobs.get(job['id'])['state'] == 'queued'


def test_database_startup_failure_is_alive_but_unready(configured, monkeypatch):
    import backend.app.main as module

    def fail(*args):
        raise sqlite3.OperationalError(SECRET)

    monkeypatch.setattr(module, 'JobService', fail)
    with TestClient(create_app(configured), base_url=BASE) as session:
        assert session.get('/health').status_code == 200
        assert session.get('/ready').status_code == 503
        assert submit(session).status_code == 503


def test_live_configuration_never_claims_live_processing(configured):
    live = Settings(**{**configured.model_dump(), 'auth_token': TOKEN, 'allowed_repository': 'owner/repo',
                       'enable_live_gemini': True, 'gemini_api_key': SECRET, 'gemini_model': 'selected-model'})
    with TestClient(create_app(live), base_url=BASE) as session:
        data = session.get('/api/status').json()
        assert data['mode'] == 'live_configured'
        assert data['live_gemini_configured'] is True
        assert data['live_github_configured'] is False
        assert data['processing_enabled'] is data['repair_enabled'] is False
        assert SECRET not in json.dumps(data)
        assert 'selected-model' not in json.dumps(data)


def test_cors_origin_allowlist_and_host_boundary(client):
    preflight = client.options('/api/jobs', headers={'Origin': 'http://127.0.0.1:5173',
                                'Access-Control-Request-Method': 'POST',
                                'Access-Control-Request-Headers': 'Authorization, Idempotency-Key, Content-Type'})
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == 'http://127.0.0.1:5173'
    assert 'access-control-allow-credentials' not in preflight.headers
    forbidden = client.get('/api/jobs', headers={**AUTH, 'Origin': 'https://unapproved.example'})
    assert forbidden.status_code == 403
    assert 'access-control-allow-origin' not in forbidden.headers
    assert client.get('/health', headers={'Host': 'unapproved.example'}).status_code == 400
    allowed = client.get('/api/jobs', headers={**AUTH, 'Origin': 'http://localhost:5173'})
    assert allowed.status_code == 200
    assert allowed.headers['cache-control'] == 'no-store'
    assert client.get('/api/jobs', headers={**AUTH, 'Origin': BASE}).status_code == 200
    unauthorized = client.get('/api/jobs', headers={'Origin': 'http://localhost:5173'})
    assert unauthorized.status_code == 401
    assert unauthorized.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_request_size_media_and_ambiguous_framing_limits(client):
    assert client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'key'},
                       content=b'x' * (MAX_BODY_BYTES + 1)).status_code == 413
    assert client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'key'},
                       content=b'repository=demo-repository').status_code == 415
    assert client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'key', 'Content-Encoding': 'gzip'},
                       content=b'xx').status_code == 415
    assert client.get('/api/jobs?' + 'x' * 2100, headers=AUTH).status_code == 414
    assert client.get('/health', headers={'X-Large': 'x' * 17000}).status_code == 431
    preflight = client.request('OPTIONS', '/api/jobs', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
    }, content=b'x' * (MAX_BODY_BYTES + 1))
    assert preflight.status_code == 413
    assert preflight.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert client.post('/api/jobs', headers={**AUTH, 'Idempotency-Key': 'key', 'Content-Length': 'no'},
                       content=b'{}').status_code == 400
    assert client.app.state.jobs.list_jobs() == []


def test_streamed_body_limit_does_not_trust_content_length(client):
    async def exercise(declared):
        headers = [(b'host', b'127.0.0.1'), (b'authorization', f'Bearer {TOKEN}'.encode()),
                   (b'idempotency-key', b'stream'), (b'content-type', b'application/json')]
        if declared is not None:
            headers.append((b'content-length', declared))
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                 'method': 'POST', 'scheme': 'http', 'path': '/api/jobs', 'raw_path': b'/api/jobs',
                 'query_string': b'', 'root_path': '', 'headers': headers,
                 'client': ('127.0.0.1', 1234), 'server': ('127.0.0.1', 8000)}
        chunks = iter([{'type': 'http.request', 'body': b'x' * 9000, 'more_body': True},
                       {'type': 'http.request', 'body': b'x' * 9000, 'more_body': False}])
        sent = []

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        await client.app(scope, receive, send)
        assert sent[0]['status'] == 413

    asyncio.run(exercise(None))
    asyncio.run(exercise(b'1'))
    assert client.app.state.jobs.list_jobs() == []


def test_success_error_and_schema_are_secret_free(client):
    job = submit(client).json()
    urls = ['/health', '/ready', '/api/status', '/api/jobs', f"/api/jobs/{job['id']}",
            f"/api/jobs/{job['id']}/events", f'/api/jobs/{UNKNOWN}', '/openapi.json']
    for url in urls:
        response = client.get(url, headers=AUTH)
        for secret in (TOKEN, SECRET, 'private-github-test-token-24680'):
            assert secret not in response.text + str(response.headers)
        assert 'set-cookie' not in response.headers
    schema = client.get('/openapi.json').json()
    for path in ('/api/jobs', '/api/jobs/{job_id}', '/api/jobs/{job_id}/events', '/api/jobs/{job_id}/cancel'):
        for operation in schema['paths'][path].values():
            assert operation['security'] == [{'OperatorBearer': []}]


def test_access_log_filter_omits_urls_and_untrusted_log_arguments():
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %d',
                               (TOKEN, SECRET, f'/api/jobs?token={TOKEN}', '1.1', 401), None)
    assert PrivateAccessLogFilter().filter(record)
    assert TOKEN not in record.getMessage()
    assert SECRET not in record.getMessage()
    assert '[request-target-omitted]' in record.getMessage()
