"""Offline simulated remote and opt-in GitHub REST adapter. No local target execution."""

import hashlib
import json
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from worker.source_common import no_links, safe_path
from worker.workspaces import canonical


class PublicationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Publication failed (' + code + ')')


def hashes(files):
    return {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}', value):
        raise PublicationError('remote_identity')
    return value


class FakeGitHubPublisher:
    """Separate durable simulated remote; local job rollback cannot undo accepted requests."""

    mode = 'offline'

    def __init__(self, path: Path, repository):
        self.path, self.repository = path, repository
        no_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS bases (ref TEXT PRIMARY KEY,sha TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS branches (name TEXT PRIMARY KEY,sha TEXT NOT NULL,payload TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS drafts (number INTEGER PRIMARY KEY,branch TEXT NOT NULL UNIQUE,marker TEXT NOT NULL UNIQUE,payload TEXT NOT NULL)')

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def start(self, heartbeat):
        self.heartbeat = heartbeat

    def authorize(self, repository):
        self.heartbeat()
        if repository != self.repository:
            raise PublicationError('remote_identity')

    def seed_base(self, ref, revision):
        with self.connect() as connection:
            connection.execute('INSERT OR IGNORE INTO bases VALUES (?,?)', (ref, revision))

    def move_base(self, ref, revision):
        with self.connect() as connection:
            connection.execute('UPDATE bases SET sha=? WHERE ref=?', (revision, ref))

    def base(self, ref):
        self.heartbeat()
        with self.connect() as connection:
            record = connection.execute('SELECT sha FROM bases WHERE ref=?', (ref,)).fetchone()
            if not record:
                raise PublicationError('remote_identity')
            return record['sha']

    def branch(self, intent, files):
        self.heartbeat()
        with self.connect() as connection:
            record = connection.execute('SELECT * FROM branches WHERE name=?', (intent['branch'],)).fetchone()
            if not record:
                return None
            payload = json.loads(record['payload'])
            if payload != {'base_sha': intent['base_sha'], 'marker': intent['marker'], 'files': hashes(files)}:
                raise PublicationError('remote_identity')
            return sha(record['sha'])

    def create_branch(self, intent, files):
        self.heartbeat()
        payload = {'base_sha': intent['base_sha'], 'marker': intent['marker'], 'files': hashes(files)}
        commit = hashlib.sha1(canonical({**payload, 'created_at': intent['created_at']})).hexdigest()
        with self.connect() as connection:
            connection.execute('INSERT OR IGNORE INTO branches VALUES (?,?,?)',
                               (intent['branch'], commit, json.dumps(payload, sort_keys=True)))
        return self.branch(intent, files)

    def draft(self, intent, commit):
        self.heartbeat()
        with self.connect() as connection:
            record = connection.execute('SELECT * FROM drafts WHERE branch=?', (intent['branch'],)).fetchone()
            if not record:
                return None
            payload = json.loads(record['payload'])
            if (record['marker'] != intent['marker'] or payload['commit_sha'] != commit
                    or payload['base_ref'] != intent['base_ref'] or payload['draft'] is not True):
                raise PublicationError('remote_identity')
            return record['number']

    def create_draft(self, intent, commit, title, body):
        self.heartbeat()
        with self.connect() as connection:
            connection.execute('INSERT OR IGNORE INTO drafts (branch,marker,payload) VALUES (?,?,?)',
                (intent['branch'], intent['marker'], json.dumps({'commit_sha': commit, 'base_ref': intent['base_ref'],
                    'draft': True, 'title': title, 'body': body, 'simulated': True}, sort_keys=True)))
        return self.draft(intent, commit)

    def draft_count(self):
        with self.connect() as connection:
            return connection.execute('SELECT COUNT(*) FROM drafts').fetchone()[0]


class LiveGitHubPublisher:
    """Only api.github.com, no redirects/proxies, repo-scoped installation tokens only."""

    mode = 'live'

    def __init__(self, settings, transport=None):
        self.settings, self.repository = settings, settings.allowed_repository
        if (not settings.enable_github_draft_pr or not settings.github_token or not settings.auth_token
                or self.repository == 'demo-repository'
                or not re.fullmatch(r'ghs_[A-Za-z0-9_.-]{20,4096}', settings.github_token.get_secret_value())):
            raise PublicationError('live_not_enabled')
        self.client = httpx.Client(transport=transport, follow_redirects=False, trust_env=False,
            headers={'Authorization': 'Bearer ' + settings.github_token.get_secret_value(),
                     'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10',
                     'User-Agent': 'WebGuard-AI/0.1', 'Accept-Encoding': 'identity'})

    def close(self):
        self.client.close()

    def start(self, heartbeat):
        self.heartbeat, self.deadline, self.calls = heartbeat, time.monotonic() + self.settings.publication_seconds, 0

    def request(self, method, path, *, body=None, missing=False, params=None):
        self.heartbeat()
        self.calls += 1
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.calls > self.settings.publication_max_requests:
            raise PublicationError('remote_limit')
        if not path.startswith('/') or path.startswith('//'):
            raise PublicationError('remote_identity')
        raw = canonical(body) if body is not None else None
        if raw and len(raw) > self.settings.publication_request_bytes:
            raise PublicationError('remote_limit')
        try:
            with self.client.stream(method, 'https://api.github.com' + path, params=params,
                content=raw, headers={'Content-Type': 'application/json'} if raw else None,
                timeout=min(remaining, self.settings.publication_request_seconds)) as response:
                if missing and response.status_code == 404:
                    return None
                if response.status_code >= 500:
                    raise PublicationError('remote_unavailable')
                if response.status_code not in (200, 201):
                    raise PublicationError('remote_rejected')
                if response.headers.get('content-encoding', 'identity') != 'identity':
                    raise PublicationError('remote_rejected')
                if response.headers.get('link') and 'rel="next"' in response.headers['link']:
                    raise PublicationError('remote_limit')
                data = bytearray()
                for chunk in response.iter_bytes():
                    self.heartbeat()
                    if time.monotonic() >= self.deadline:
                        raise PublicationError('remote_timeout')
                    data.extend(chunk)
                    if len(data) > self.settings.publication_response_bytes:
                        raise PublicationError('remote_limit')
            self.heartbeat()
            return json.loads(data)
        except httpx.TimeoutException:
            raise PublicationError('remote_timeout') from None
        except (httpx.HTTPError, ValueError, UnicodeError, RecursionError):
            raise PublicationError('remote_unavailable') from None

    @property
    def root(self):
        return '/repos/' + self.repository

    def authorize(self, repository):
        if repository != self.repository:
            raise PublicationError('remote_identity')
        result = self.request('GET', '/installation/repositories', params={'per_page': 2})
        repositories = result.get('repositories', [])
        if result.get('total_count') != 1 or len(repositories) != 1 or repositories[0].get('full_name') != repository:
            raise PublicationError('token_scope')
        repo = self.request('GET', self.root)
        if (repo.get('full_name') != repository or repo.get('id') != repositories[0].get('id')
                or repo.get('archived') or repo.get('disabled')):
            raise PublicationError('remote_identity')

    def base(self, ref):
        data = self.request('GET', self.root + '/git/ref/heads/' + quote(ref, safe='/'))
        if data.get('ref') != 'refs/heads/' + ref or data.get('object', {}).get('type') != 'commit':
            raise PublicationError('remote_identity')
        return sha(data['object']['sha'])

    def tree(self, tree_sha):
        data = self.request('GET', self.root + '/git/trees/' + sha(tree_sha), params={'recursive': 1})
        if data.get('truncated') or data.get('sha') != tree_sha:
            raise PublicationError('remote_limit')
        leaves = {}
        for item in data.get('tree', []):
            if item.get('type') == 'tree':
                continue
            try:
                path = safe_path(item['path'])
            except (ValueError, RuntimeError):
                raise PublicationError('remote_identity') from None
            if item.get('type') != 'blob' or item.get('mode') not in ('100644', '100755') or path in leaves:
                raise PublicationError('remote_identity')
            leaves[path] = (item['mode'], sha(item['sha']))
        return leaves

    def commit(self, commit_sha):
        data = self.request('GET', self.root + '/git/commits/' + sha(commit_sha))
        if data.get('sha') != commit_sha:
            raise PublicationError('remote_identity')
        return data

    def validate_commit(self, intent, commit_sha, files):
        commit = self.commit(commit_sha)
        if (intent['marker'] not in commit.get('message', '')
                or [item.get('sha') for item in commit.get('parents', [])] != [intent['base_sha']]):
            raise PublicationError('remote_identity')
        base = self.commit(intent['base_sha'])
        expected = self.tree(base['tree']['sha'])
        for name, content in files.items():
            if name not in expected:
                raise PublicationError('remote_identity')
            expected[name] = (expected[name][0], hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest())
        if self.tree(commit['tree']['sha']) != expected:
            raise PublicationError('remote_identity')
        return commit_sha

    def branch(self, intent, files):
        data = self.request('GET', self.root + '/git/ref/heads/' + quote(intent['branch'], safe='/'), missing=True)
        if data is None:
            return None
        if data.get('ref') != 'refs/heads/' + intent['branch'] or data.get('object', {}).get('type') != 'commit':
            raise PublicationError('remote_identity')
        return self.validate_commit(intent, sha(data['object']['sha']), files)

    def create_branch(self, intent, files):
        base = self.commit(intent['base_sha'])
        leaves = self.tree(base['tree']['sha'])
        entries = []
        for name, content in sorted(files.items()):
            if name not in leaves:
                raise PublicationError('remote_identity')
            entries.append({'path': name, 'mode': leaves[name][0], 'type': 'blob', 'content': content.decode('utf8')})
        tree = self.request('POST', self.root + '/git/trees', body={'base_tree': base['tree']['sha'], 'tree': entries})
        timestamp = datetime.fromtimestamp(intent['created_at'], UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')
        identity = {'name': 'WebGuard-AI', 'email': 'webguard-ai@users.noreply.github.com', 'date': timestamp}
        commit = self.request('POST', self.root + '/git/commits', body={
            'message': 'Verified source repair\n\n' + intent['marker'], 'tree': sha(tree['sha']),
            'parents': [intent['base_sha']], 'author': identity, 'committer': identity})
        commit_sha = self.validate_commit(intent, sha(commit['sha']), files)
        if self.base(intent['base_ref']) != intent['base_sha']:
            raise PublicationError('base_moved')
        self.request('POST', self.root + '/git/refs', body={'ref': 'refs/heads/' + intent['branch'], 'sha': commit_sha})
        found = self.branch(intent, files)
        if found is None:
            raise PublicationError('outcome_unknown')
        return found

    def draft(self, intent, commit):
        owner = self.repository.split('/')[0]
        data = self.request('GET', self.root + '/pulls', params={'state': 'all', 'head': owner + ':' + intent['branch'],
                            'base': intent['base_ref'], 'per_page': 100})
        if not isinstance(data, list) or len(data) > 1:
            raise PublicationError('remote_identity')
        if not data:
            return None
        item = data[0]
        if (intent['marker'] not in (item.get('body') or '') or item.get('draft') is not True
                or item.get('state') != 'open' or item.get('head', {}).get('ref') != intent['branch']
                or item.get('head', {}).get('sha') != commit
                or item.get('head', {}).get('repo', {}).get('full_name') != self.repository
                or item.get('base', {}).get('ref') != intent['base_ref']
                or item.get('base', {}).get('repo', {}).get('full_name') != self.repository
                or type(item.get('number')) is not int or item['number'] < 1):
            raise PublicationError('remote_identity')
        return item['number']

    def create_draft(self, intent, commit, title, body):
        self.request('POST', self.root + '/pulls', body={'title': title, 'body': body, 'head': intent['branch'],
                                                      'base': intent['base_ref'], 'draft': True})
        number = self.draft(intent, commit)
        if number is None:
            raise PublicationError('outcome_unknown')
        return number
