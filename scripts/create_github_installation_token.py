"""Operator-run credential setup only: mint one-repository token into private .env.

No jobs, repository writes, Gemini requests or live-flag changes. Never prints a
JWT, private key, installation token or raw API error. Run from a private terminal.
"""

import base64
import getpass
import json
import re
import time
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from dotenv import dotenv_values, set_key

REPOSITORY = 'nitish-mandal/webguard-live-demo'
PERMISSIONS = {'contents': 'write', 'pull_requests': 'write', 'metadata': 'read'}


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def jwt_for_app(client_id, private_key):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', client_id):
        raise ValueError('invalid_client_id')
    key = serialization.load_pem_private_key(private_key, password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError('invalid_signing_key')
    now = int(time.time())
    header = encode(b'{"alg":"RS256","typ":"JWT"}')
    payload = encode(json.dumps({'iat': now - 60, 'exp': now + 540,
                                 'iss': client_id}, separators=(',', ':')).encode())
    unsigned = header + b'.' + payload
    signature = key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
    return (unsigned + b'.' + encode(signature)).decode('ascii')


def api(client, method, path, token, body=None):
    with client.stream(method, 'https://api.github.com' + path,
                       headers={'Authorization': 'Bearer ' + token,
                                'Accept': 'application/vnd.github+json',
                                'X-GitHub-Api-Version': '2026-03-10',
                                'User-Agent': 'WebGuard-AI-private-setup'},
                       json=body) as response:
        if response.status_code not in (200, 201):
            raise ValueError('github_request_rejected')
        content = bytearray()
        for part in response.iter_bytes():
            content.extend(part)
            if len(content) > 131072:
                raise ValueError('github_response_limit')
    return json.loads(content)


def save_installation_token(env_path, client_id, private_key, transport=None):
    before = dotenv_values(env_path, interpolate=False)
    if before.get('ALLOWED_REPOSITORY') != REPOSITORY or not all(
        before.get(key, '').lower() == 'false'
        for key in ('ENABLE_LIVE_GEMINI', 'ENABLE_GITHUB_DRAFT_PR')
    ):
        raise ValueError('require_approved_repository_and_flags_off')
    jwt = jwt_for_app(client_id, private_key)
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False,
                      transport=transport) as client:
        installation = api(client, 'GET', '/repos/' + REPOSITORY + '/installation', jwt)
        installation_id = installation['id']
        if type(installation_id) is not int or installation_id <= 0:
            raise ValueError('invalid_installation')
        minted = api(client, 'POST', f'/app/installations/{installation_id}/access_tokens', jwt,
                     {'repositories': ['webguard-live-demo'], 'permissions': PERMISSIONS})
        token = minted['token']
        if not isinstance(token, str) or not re.fullmatch(r'ghs_[A-Za-z0-9_.-]{20,4096}', token):
            raise ValueError('unsupported_token_format')
        if minted.get('permissions') != PERMISSIONS:
            raise ValueError('unexpected_permissions')
        scope = api(client, 'GET', '/installation/repositories?per_page=2', token)
        repos = scope.get('repositories', [])
        if (scope.get('total_count') != 1 or len(repos) != 1
                or repos[0].get('full_name') != REPOSITORY):
            raise ValueError('unexpected_repository_scope')
    # Recheck before changing the one credential; preserve flags/other keys.
    if dotenv_values(env_path, interpolate=False) != before:
        raise ValueError('configuration_changed_during_setup')
    set_key(env_path, 'GITHUB_TOKEN', token, quote_mode='always')
    return {'saved_to_private_env': True, 'repository': REPOSITORY,
            'repository_scope_verified': True, 'permissions_verified': True,
            'live_flags_unchanged': True, 'job_submitted': False}


def main():
    try:
        env_path = Path(__file__).resolve().parents[1] / '.env'
        client_id = input('GitHub App Client ID (not the client secret): ').strip()
        key_path = Path(getpass.getpass('Downloaded private .pem path (hidden): ').strip().strip('"'))
        if key_path.stat().st_size > 32768:
            raise ValueError('signing_key_size_limit')
        result = save_installation_token(env_path, client_id, key_path.read_bytes())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - never echo credentials or HTTP bodies.
        print('Setup failed; token not confirmed saved. Check App installation, permissions and PEM locally.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
