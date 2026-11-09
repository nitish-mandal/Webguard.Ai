"""Release isolation/credential inventory tests, never target execution."""

import json
import zipfile

import pytest

from scripts.build_release import ROOT_FILES, build_release, verify_release


@pytest.fixture
def project(tmp_path):
    for name in (*ROOT_FILES, 'frontend/package.json', 'frontend/package-lock.json', 'docs/STATUS.md',
                 'docs/PHASE_PROGRESS.md', 'demo-repository/pagination.py',
                 'demo-repository/tests/test_pagination.py'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}' if name.endswith('.json') else 'public source\n', encoding='utf8')
    return tmp_path


def test_release_excludes_credentials_runtime_and_builds_and_is_reproducible(project):
    secret = 'private-release-fixture-token-1234567890'
    for name in ('.env', 'data/jobs.db', 'workspaces/job/source.py', '.tools/private.json',
                 'frontend/node_modules/private.js', 'frontend/dist/private.js', 'worker/__pycache__/old.pyc',
                 'docs/baseline/local-diagnostics.json', 'frontend/.env.local'):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secret, encoding='utf8')
    first, second = project / 'artifacts/first.zip', project / 'artifacts/second.zip'
    report = build_release(project, first, (secret,))
    build_release(project, second, (secret,))
    assert first.read_bytes() == second.read_bytes() and report['zip_verified']
    with zipfile.ZipFile(first) as archive:
        assert '.env.example' in archive.namelist()
        assert 'demo-repository/pagination.py' in archive.namelist()
        assert 'demo-repository/tests/test_pagination.py' in archive.namelist()
        assert 'docs/baseline/local-diagnostics.json' not in archive.namelist()
        manifest = json.loads(archive.read('RELEASE_MANIFEST.json'))
        assert manifest['phase11_accepted_job'] == '802d2957d6ef48d182a8b04919e34165'
    assert verify_release(first, (secret,))['credentials_excluded']


def test_release_blocks_a_configured_secret_accidentally_in_source(project):
    (project / 'frontend/leak.ts').write_text('private-release-secret', encoding='utf8')
    with pytest.raises(ValueError, match='credential'):
        build_release(project, project / 'artifacts/release.zip', ('private-release-secret',))


def test_release_refuses_output_outside_artifacts(project):
    with pytest.raises(ValueError, match='artifacts'):
        build_release(project, project / 'source.zip')


def test_release_detects_modified_archive_members(project):
    output = project / 'artifacts/release.zip'
    build_release(project, output)
    with zipfile.ZipFile(output, 'a') as archive:
        archive.writestr('extra.py', b'unexpected')
    with pytest.raises(ValueError, match='inventory'):
        verify_release(output)
