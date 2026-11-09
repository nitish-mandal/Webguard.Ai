"""Live REST contract tests with MockTransport only. No real tokens/network calls."""

import hashlib
import json

import httpx
import pytest
from pydantic import SecretStr

from backend.app.settings import Settings
from worker.github_publishers import LiveGitHubPublisher, PublicationError
from worker.workspaces import canonical

TOKEN = 'ghs_unit_test_installation_' + 'b' * 32
BASE = 'a' * 40


def settings(**kwargs):
    return Settings(allowed_repository='owner/repo', enable_github_draft_pr=True,
                    github_token=TOKEN, auth_token='a' * 32, **kwargs)


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class API:
    def __init__(self):
        self.calls, self.branches, self.prs = [], {}, []
        self.base_tree = 'b' * 40
        self.trees = {self.base_tree: {'pagination.py': ('100644', blob(b'old source\n')),
                                    'tests/test_original.py': ('100644', blob(b'original tests\n'))}}
        self.commits = {BASE: {'sha': BASE, 'tree': {'sha': self.base_tree}, 'parents': [], 'message': 'base'}}
        self.broad_scope, self.corrupt_tree = False, False

    def __call__(self, request):
        assert request.url.host == 'api.github.com'
        assert request.headers['authorization'] == 'Bearer ' + TOKEN
        assert request.headers['accept-encoding'] == 'identity'
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        path = request.url.path.removeprefix('/repos/owner/repo')
        code, data = 200, None
        if request.url.path == '/installation/repositories':
            data = {'total_count': 2 if self.broad_scope else 1, 'repositories': [{'id': 1, 'full_name': 'owner/repo'}]}
        elif path == '' and request.method == 'GET':
            data = {'id': 1, 'full_name': 'owner/repo', 'archived': False, 'disabled': False}
        elif path.startswith('/git/ref/heads/'):
            branch = path.removeprefix('/git/ref/heads/')
            commit = BASE if branch == 'main' else self.branches.get(branch)
            code, data = (200, {'ref': 'refs/heads/' + branch, 'object': {'type': 'commit', 'sha': commit}}) if commit else (404, {})
        elif path.startswith('/git/commits/'):
            data = self.commits[path.rsplit('/', 1)[-1]]
        elif path.startswith('/git/trees/'):
            tree = path.rsplit('/', 1)[-1]
            data = {'sha': tree, 'truncated': False, 'tree': [
                {'path': name, 'mode': value[0], 'type': 'blob', 'sha': value[1]} for name, value in self.trees[tree].items()]}
        elif path == '/git/trees' and request.method == 'POST':
            tree = dict(self.trees[body['base_tree']])
            for item in body['tree']:
                tree[item['path']] = (item['mode'], blob(item['content'].encode()))
            if self.corrupt_tree:
                tree['tests/test_original.py'] = ('100644', '0' * 40)
            identity = hashlib.sha1(canonical(tree)).hexdigest()
            self.trees[identity] = tree
            code, data = 201, {'sha': identity}
        elif path == '/git/commits' and request.method == 'POST':
            identity = hashlib.sha1(canonical(body)).hexdigest()
            self.commits[identity] = {'sha': identity, **body, 'tree': {'sha': body['tree']},
                                      'parents': [{'sha': value} for value in body['parents']]}
            code, data = 201, {'sha': identity}
        elif path == '/git/refs' and request.method == 'POST':
            self.branches[body['ref'].removeprefix('refs/heads/')] = body['sha']
            code, data = 201, {'ref': body['ref'], 'object': {'sha': body['sha'], 'type': 'commit'}}
        elif path == '/pulls' and request.method == 'GET':
            data = self.prs
        elif path == '/pulls' and request.method == 'POST':
            assert body['draft'] is True
            pr = {'number': 1, 'draft': True, 'state': 'open', 'body': body['body'],
                  'head': {'ref': body['head'], 'sha': self.branches[body['head']], 'repo': {'full_name': 'owner/repo'}},
                  'base': {'ref': body['base'], 'repo': {'full_name': 'owner/repo'}}}
            self.prs.append(pr)
            code, data = 201, pr
        else:
            raise AssertionError('Unexpected adapter request')
        return httpx.Response(code, json=data)


def intent():
    return {'base_sha': BASE, 'base_ref': 'main', 'branch': 'webguard/jobs/' + 'c' * 32,
            'marker': '<!-- webguard-ai-job:' + 'c' * 32 + ' -->', 'created_at': 1000.0}


def test_live_adapter_creates_only_exact_tree_and_draft_then_looks_up():
    api = API()
    remote = LiveGitHubPublisher(settings(), httpx.MockTransport(api))
    remote.start(lambda: None)
    remote.authorize('owner/repo')
    job, files = intent(), {'pagination.py': b'new verified source\n'}
    assert remote.branch(job, files) is None
    commit = remote.create_branch(job, files)
    assert commit != BASE and remote.branch(job, files) == commit
    assert remote.create_draft(job, commit, 'Verified repair', job['marker']) == 1
    assert remote.draft(job, commit) == 1 and len(api.prs) == 1
    posts = [(path, body) for method, path, body in api.calls if method == 'POST']
    tree = next(body for path, body in posts if path.endswith('/git/trees'))
    assert tree['tree'] == [{'path': 'pagination.py', 'mode': '100644', 'type': 'blob', 'content': 'new verified source\n'}]
    created = next(body for path, body in posts if path.endswith('/git/commits'))
    assert created['parents'] == [BASE] and created['author']['date'] == created['committer']['date']
    assert not any('merge' in path for _, path, _ in api.calls)
    remote.close()


def test_broad_installation_token_is_rejected_before_writes():
    api = API()
    api.broad_scope = True
    remote = LiveGitHubPublisher(settings(), httpx.MockTransport(api))
    remote.start(lambda: None)
    with pytest.raises(PublicationError, match='token_scope'): remote.authorize('owner/repo')
    assert not any(method == 'POST' for method, _, _ in api.calls)
    remote.close()


def test_changed_unapproved_tree_entries_are_rejected_before_ref_creation():
    api = API()
    api.corrupt_tree = True
    remote = LiveGitHubPublisher(settings(), httpx.MockTransport(api))
    remote.start(lambda: None)
    with pytest.raises(PublicationError, match='remote_identity'):
        remote.create_branch(intent(), {'pagination.py': b'new verified source\n'})
    assert not api.branches and not api.prs
    remote.close()


def test_classic_token_and_default_live_flags_are_rejected():
    with pytest.raises(PublicationError, match='live_not_enabled'): LiveGitHubPublisher(Settings())
    classic = settings().model_copy(update={'github_token': SecretStr('ghp_' + 'x' * 40)})
    with pytest.raises(PublicationError, match='live_not_enabled'): LiveGitHubPublisher(classic)


@pytest.mark.parametrize('case', ['redirect', 'timeout', 'large', 'compressed'])
def test_http_limits_and_errors_never_expose_token_or_follow_redirects(case):
    seen = []
    def response(request):
        seen.append(str(request.url))
        if case == 'timeout': raise httpx.ReadTimeout('sensitive ' + TOKEN, request=request)
        if case == 'redirect': return httpx.Response(302, headers={'Location': 'https://untrusted.example/'})
        if case == 'large': return httpx.Response(200, content=b'x' * 2048)
        return httpx.Response(200, content=b'bad', headers={'Content-Encoding': 'gzip'})
    remote = LiveGitHubPublisher(settings(publication_response_bytes=1024), httpx.MockTransport(response))
    remote.start(lambda: None)
    with pytest.raises(PublicationError) as error:
        remote.request('GET', '/installation/repositories')
    assert TOKEN not in str(error.value) and len(seen) == 1
    assert all(url.startswith('https://api.github.com/') and TOKEN not in url for url in seen)
    remote.close()


@pytest.mark.parametrize('limit', ['deadline', 'calls', 'input'])
def test_request_budgets_block_before_network(limit):
    seen = []
    remote = LiveGitHubPublisher(settings(), httpx.MockTransport(lambda request: seen.append(request)))
    remote.start(lambda: None)
    body = None
    if limit == 'deadline': remote.deadline = 0
    if limit == 'calls': remote.calls = remote.settings.publication_max_requests
    if limit == 'input': body = {'data': 'x' * remote.settings.publication_request_bytes}
    with pytest.raises(PublicationError, match='remote_limit'):
        remote.request('POST', '/repos/owner/repo/pulls', body=body)
    assert seen == []
    remote.close()
