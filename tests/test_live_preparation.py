"""Local-only live preflight must never expose keys or initiate external work."""

import json

from scripts.check_live_configuration import inspect_configuration


def test_missing_configuration_is_specific_and_read_only(tmp_path):
    path = tmp_path / '.env'
    before = 'AUTH_TOKEN=' + 'a' * 40 + '\nALLOWED_REPOSITORY=demo-repository\n'
    path.write_text(before, encoding='utf8')
    report = inspect_configuration(path)
    assert not report['local_configuration_ready'] and not report['network_requests_made']
    assert {'GEMINI_API_KEY', 'GEMINI_MODEL', 'GITHUB_TOKEN', 'ALLOWED_REPOSITORY'} <= set(report['settings_to_fill_privately'])
    assert 'a' * 40 not in json.dumps(report) and path.read_text(encoding='utf8') == before


def test_prepared_local_values_do_not_claim_remote_scope_or_authorization(tmp_path):
    path = tmp_path / '.env'
    secret = 'private-local-gemini-fixture-value'
    path.write_text('AUTH_TOKEN=' + 'a' * 40 + '\nALLOWED_REPOSITORY=owner/repo\nGEMINI_API_KEY=' + secret
        + '\nGEMINI_MODEL=operator-selected-model\nGITHUB_TOKEN=ghs_' + 'b' * 40
        + '\nENABLE_LIVE_GEMINI=true\nENABLE_GITHUB_DRAFT_PR=true\nRUNNER_IMAGE_ID=sha256:' + 'c' * 64
        + '\nMAX_MODEL_CALLS_PER_JOB=1\nMAX_REPAIR_ATTEMPTS=1\nMAX_PUBLICATION_ATTEMPTS=1\nREPAIR_MAX_RETRIES=0\n', encoding='utf8')
    report = inspect_configuration(path, 'owner/repo')
    assert report['local_configuration_ready'] and secret not in json.dumps(report)
    assert not report['remote_repository_scope_verified'] and not report['live_authorization_granted_by_this_check']
    assert not inspect_configuration(path, 'other/repo')['local_configuration_ready']
