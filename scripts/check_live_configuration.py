"""Read-only local live-run preparation. No network, job submission or authorization."""

import argparse
import json
import re
from pathlib import Path

from dotenv import dotenv_values

from backend.app.settings import Settings, SettingsError, load_settings


def inspect_configuration(path, expected_repository=None):
    values = dotenv_values(path, interpolate=False)
    repository = values.get('ALLOWED_REPOSITORY') or 'demo-repository'
    canonical = bool(re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9_.-]*', repository))
    missing = []
    for key in ('AUTH_TOKEN', 'GEMINI_API_KEY', 'GEMINI_MODEL', 'GITHUB_TOKEN', 'RUNNER_IMAGE_ID'):
        if not values.get(key):
            missing.append(key)
    if not canonical:
        missing.append('ALLOWED_REPOSITORY')
    for key in ('ENABLE_LIVE_GEMINI', 'ENABLE_GITHUB_DRAFT_PR'):
        if str(values.get(key, 'false')).lower() != 'true':
            missing.append(key)
    bounds = {'MAX_MODEL_CALLS_PER_JOB': 1, 'MAX_REPAIR_ATTEMPTS': 1, 'MAX_PUBLICATION_ATTEMPTS': 1,
              'REPAIR_MAX_RETRIES': 0}
    for key, wanted in bounds.items():
        if str(values.get(key, '')) != str(wanted):
            missing.append(key)
    validated = False
    try:
        settings = load_settings(path, {})
        validated = isinstance(settings, Settings)
    except SettingsError:
        pass
    token = values.get('GITHUB_TOKEN') or ''
    supported_token = bool(re.fullmatch(r'ghs_[A-Za-z0-9_.-]{20,4096}', token))
    matches = canonical and expected_repository is not None and repository == expected_repository
    return {'local_configuration_ready': validated and not missing and supported_token and matches,
            'approved_repository': repository if canonical or repository == 'demo-repository' else 'invalid',
            'matches_explicit_repository': matches, 'settings_to_fill_privately': missing,
            'settings_validation_passed': validated, 'supported_installation_token_format': supported_token,
            'explicit_repository_argument_required': expected_repository is None,
            'live_authorization_granted_by_this_check': False, 'network_requests_made': False,
            'remote_repository_scope_verified': False, 'live_gemini_verified': False, 'live_publication_verified': False,
            'target_requirement': 'Public approved pagination-demo copy; existing v4 Python/pytest profile only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--repository', help='Exact operator-approved canonical owner/repository; no URL')
    args = parser.parse_args()
    result = inspect_configuration(Path(args.env_file), args.repository)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['local_configuration_ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
