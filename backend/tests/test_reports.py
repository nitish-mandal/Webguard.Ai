"""Authenticated bounded dashboard projections; all execution in these tests is fake data."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from worker.publication import PublicationService
from worker.source_common import Budget
from worker.tests.test_publication import verified
from worker.tests.test_repositories import access, fixture_git
from worker.tests.test_verification import candidate

__all__ = ['access', 'candidate', 'fixture_git', 'verified']
TOKEN = 'phase11-report-operator-' + 'x' * 32
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def report_client(verified):
    access, lease, _, remote = verified
    settings = access.jobs.settings.model_copy(update={})
    from pydantic import SecretStr

    settings = settings.model_copy(update={'auth_token': SecretStr(TOKEN)})
    with TestClient(create_app(settings), base_url='http://127.0.0.1:8000') as client:
        yield client, access, lease, remote


def test_report_is_protected_read_only_and_bounds_failure_evidence(report_client):
    client, access, lease, _ = report_client
    path = '/api/jobs/' + lease.job_id + '/report'
    assert client.get(path).status_code == 401
    before = access.jobs.get(lease.job_id)
    response = client.get(path, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data['version'] == before['version']
    assert data['detection']['node_id'] == 'tests/test_pagination.py::test_first_page_contains_requested_count'
    assert data['detection']['expected'] == '[10, 20]' and data['detection']['actual'] == '[10]'
    assert len(data['detection']['observations']) == 2 and len(data['verifications']) == 1
    assert data['verifications'][0]['status'] == 'verified'
    assert len(data['verifications'][0]['checks']) == 4
    assert len(response.content) < 20000 and len(data['detection']['traceback']) <= 2048
    assert access.jobs.get(lease.job_id) == before
    for hidden in ('workspace_id', 'lease_owner', 'fence', 'idempotency_hash', TOKEN):
        assert hidden not in response.text


def test_report_labels_fake_publication_and_never_links_simulated_url(report_client):
    client, access, lease, remote = report_client
    assert PublicationService(access, remote).publish(lease).outcome == 'draft_pr_created'
    result = client.get('/api/jobs/' + lease.job_id + '/report', headers=AUTH).json()['publication']
    assert result['confirmed'] and result['simulated'] and result['pr_number'] == 1
    assert result['live_url'] is None


@pytest.mark.parametrize('url', ['https://github.com/unapproved/repo/pull/1', 'javascript:alert(1)',
                                'https://user:private@github.com/owner/repo/pull/1',
                                'https://github.com/demo-repository/pull/1'])
def test_report_refuses_unvalidated_live_urls(report_client, url):
    client, access, lease, remote = report_client
    PublicationService(access, remote).publish(lease)
    with access.jobs.db.transaction() as connection:
        connection.execute("UPDATE publication_intents SET mode='live',pr_url=? WHERE job_id=?", (url, lease.job_id))
        connection.execute('UPDATE publications SET url=? WHERE job_id=?', (url, lease.job_id))
    response = client.get('/api/jobs/' + lease.job_id + '/report', headers=AUTH)
    assert response.status_code == 200 and response.json()['publication']['live_url'] is None
    assert url not in response.text


def test_report_live_link_requires_exact_approved_repo_complete_evidence(report_client):
    client, access, lease, remote = report_client
    PublicationService(access, remote).publish(lease)
    # A storage fixture only: no live request is made. Rebind the complete proof's
    # repository identity to exercise URL projection independently of remote access.
    expected = 'https://github.com/owner/repo/pull/1'
    client.app.state.jobs.settings = client.app.state.jobs.settings.model_copy(update={'allowed_repository': 'owner/repo'})
    with access.jobs.db.transaction() as connection:
        connection.execute("UPDATE jobs SET repository='owner/repo' WHERE id=?", (lease.job_id,))
        connection.execute("UPDATE publication_intents SET repository='owner/repo',mode='live',pr_url=? WHERE job_id=?", (expected, lease.job_id))
        connection.execute('UPDATE publications SET url=? WHERE job_id=?', (expected, lease.job_id))
    data = client.get('/api/jobs/' + lease.job_id + '/report', headers=AUTH).json()['publication']
    assert not data['simulated'] and data['confirmed'] and data['live_url'] == expected
    with access.jobs.db.transaction() as connection:
        connection.execute('UPDATE publication_intents SET stale=1 WHERE job_id=?', (lease.job_id,))
    assert client.get('/api/jobs/' + lease.job_id + '/report', headers=AUTH).json()['publication']['live_url'] is None


def test_report_omits_tampered_receipts_and_raw_sensitive_fields(report_client):
    client, access, lease, _ = report_client
    snapshot = access.jobs.source_snapshot(lease.job_id)
    workspace = access.manager.reopen(lease.job_id, snapshot, Budget(5))
    folder = access.manager.path(workspace) / 'detection-receipts'
    for path in folder.glob('*.json'):
        data = json.loads(path.read_bytes())
        data['runs'][0]['stdout'] = TOKEN
        path.write_text(json.dumps(data), encoding='utf8')
    response = client.get('/api/jobs/' + lease.job_id + '/report', headers=AUTH)
    assert response.status_code == 200 and not response.json()['detection']['evidence_available']
    assert response.json()['detection']['traceback'] is None and TOKEN not in response.text


def test_empty_unknown_and_query_validation(report_client):
    client, access, _, _ = report_client
    job = access.jobs.create('queued-report', 'demo-repository')
    data = client.get('/api/jobs/' + job['id'] + '/report', headers=AUTH).json()
    assert data['detection']['verdict'] is None and data['verifications'] == [] and data['publication'] is None
    assert client.get('/api/jobs/' + 'f' * 32 + '/report', headers=AUTH).status_code == 404
    assert client.get('/api/jobs/' + job['id'] + '/report?path=private', headers=AUTH).status_code == 422


def test_recent_jobs_descending_cursor_has_no_duplicates(report_client):
    client, access, _, _ = report_client
    for index in range(4):
        access.jobs.create('recent-' + str(index), 'demo-repository')
    first = client.get('/api/jobs?limit=2&order=desc', headers=AUTH).json()
    second = client.get('/api/jobs?limit=2&order=desc&cursor=' + first['next_cursor'], headers=AUTH).json()
    values = first['items'] + second['items']
    assert len({item['id'] for item in values}) == 4
    assert [(item['created_at'], item['id']) for item in values] == sorted(
        [(item['created_at'], item['id']) for item in values], reverse=True)
    assert client.get('/api/jobs?order=unexpected', headers=AUTH).status_code == 422
