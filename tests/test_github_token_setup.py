"""No external network; operator setup scope and credential-preservation checks."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values

from scripts.create_github_installation_token import (
    PERMISSIONS,
    REPOSITORY,
    save_installation_token,
)


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / '.env'
    path.write_text(f'ALLOWED_REPOSITORY={REPOSITORY}\nENABLE_LIVE_GEMINI=false\n'
                    'ENABLE_GITHUB_DRAFT_PR=false\nAUTH_TOKEN=existing-private-operator\n'
                    'GEMINI_API_KEY=existing-private-gemini\n')
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    return path, pem


def transport(wrong_scope=False):
    def handle(request):
        assert request.url.host == 'api.github.com'
        if request.url.path.endswith('/installation'):
            return httpx.Response(200, json={'id': 123})
        if request.method == 'POST':
            assert json.loads(request.content) == {
                'repositories': ['webguard-live-demo'], 'permissions': PERMISSIONS}
            return httpx.Response(201, json={'token': 'ghs_' + 'test-only-token-value' * 2,
                                           'permissions': PERMISSIONS})
        return httpx.Response(200, json={'total_count': 1, 'repositories': [
            {'full_name': 'other/repo' if wrong_scope else REPOSITORY}]})
    return httpx.MockTransport(handle)


def test_setup_scopes_token_preserves_credentials_and_flags(setup, capsys):
    path, key = setup
    before = dotenv_values(path)
    result = save_installation_token(path, 'Iv1.example', key, transport())
    after = dotenv_values(path)
    assert all(after[k] == v for k, v in before.items())
    assert after['GITHUB_TOKEN'].startswith('ghs_')
    assert result['repository_scope_verified'] and not result['job_submitted']
    assert capsys.readouterr().out == ''
    assert after['GITHUB_TOKEN'] not in json.dumps(result)


def test_setup_rejects_wrong_repository_scope_without_saving(setup):
    path, key = setup
    before = path.read_bytes()
    with pytest.raises(ValueError, match='repository_scope'):
        save_installation_token(path, 'Iv1.example', key, transport(wrong_scope=True))
    assert path.read_bytes() == before


def test_setup_requires_flags_off_before_network(setup):
    path, key = setup
    path.write_text(path.read_text().replace('ENABLE_LIVE_GEMINI=false', 'ENABLE_LIVE_GEMINI=true'))
    with pytest.raises(ValueError, match='flags_off'):
        save_installation_token(path, 'Iv1.example', key, transport())
