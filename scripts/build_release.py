"""Allowlisted source release builder. Never include dotenv credentials or runtime data."""

import argparse
import hashlib
import json
import os
import stat
import uuid
import zipfile
from pathlib import Path

DIRECTORIES = ('backend', 'worker', 'frontend', 'runner_image', 'tests', 'scripts', 'docs', 'demo-repository')
ROOT_FILES = ('.env.example', '.gitignore', 'README.md', 'pyproject.toml', 'uv.lock', 'requirements-dev.lock')
PUBLIC_EVIDENCE = {'phase8-image.json', 'phase12-release-evidence.json', 'phase11-browser-acceptance.json'}
SKIP_DIRECTORIES = {'.git', '.venv', '.tools', '__pycache__', '.pytest_cache', '.ruff_cache', 'node_modules',
                    'dist', 'data', 'workspaces', 'artifacts', 'coverage', '.agents', '.codex', '.aws'}
EXTENSIONS = {'.py', '.md', '.ts', '.tsx', '.css', '.html', '.json', '.toml', '.lock', '.ini', '.txt'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def inventory(root):
    """Prune local directories before walking them, including permission-protected workspaces."""
    for name in ROOT_FILES:
        path = root / name
        if path.is_file():
            yield path
    for name in DIRECTORIES:
        base = root / name
        if not base.exists():
            continue
        if linked(base):
            raise ValueError('Release source symlink rejected')
        for folder, directories, files in os.walk(base, followlinks=False):
            directories[:] = sorted(item for item in directories if item not in SKIP_DIRECTORIES and not item.endswith('.egg-info'))
            for directory in directories:
                if linked(Path(folder) / directory):
                    raise ValueError('Release source symlink rejected')
            for filename in sorted(files):
                path = Path(folder) / filename
                relative = path.relative_to(root)
                if filename.startswith('.env') or filename == 'desktop.ini':
                    continue
                if relative.parts[:2] == ('docs', 'baseline') and filename not in PUBLIC_EVIDENCE:
                    continue
                if path.suffix.lower() in EXTENSIONS or filename == 'Dockerfile':
                    yield path


def verify_release(path, forbidden_secrets=()):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('Release CRC failure')
        names = archive.namelist()
        if len(names) != len(set(names)) or 'RELEASE_MANIFEST.json' not in names:
            raise ValueError('Release manifest missing or duplicate entries')
        manifest = json.loads(archive.read('RELEASE_MANIFEST.json'))
        if manifest.get('product') != 'WebGuard-AI' or manifest.get('release') != 'phase12-offline':
            raise ValueError('Unexpected release identity')
        if set(names) != {'RELEASE_MANIFEST.json', *manifest['files']}:
            raise ValueError('Release member inventory mismatch')
        for name in names:
            parts = Path(name).parts
            if (name.startswith(('/', '\\')) or '\\' in name or ':' in name or '..' in parts
                    or any(part in SKIP_DIRECTORIES for part in parts)
                    or (Path(name).name.startswith('.env') and name != '.env.example')
                    or Path(name).suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pyc', '.pyo', '.pem', '.key', '.zip', '.log'}):
                raise ValueError('Forbidden release member')
            data = archive.read(name)
            if any(secret and secret.encode('utf8') in data for secret in forbidden_secrets):
                raise ValueError('Configured credential detected in release')
            if name != 'RELEASE_MANIFEST.json' and digest(data) != manifest['files'][name]:
                raise ValueError('Release content digest mismatch')
    return {'files': len(manifest['files']), 'sha256': digest(path.read_bytes()), 'zip_verified': True,
            'credentials_excluded': True, 'runtime_data_excluded': True}


def build_release(root, output, forbidden_secrets=()):
    root, output = Path(root).resolve(), Path(output).resolve()
    destination = root / 'artifacts'
    if not output.is_relative_to(destination) or output.suffix != '.zip' or linked(destination):
        raise ValueError('Release output must be a ZIP inside project artifacts')
    output.parent.mkdir(parents=True, exist_ok=True)
    if linked(output):
        raise ValueError('Release output symlink rejected')
    if output.exists():
        verify_release(output, forbidden_secrets)
    content = {}
    for path in inventory(root):
        if linked(path) or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink != 1:
            raise ValueError('Release source must be a regular unlinked file')
        if not path.resolve().is_relative_to(root) or path.stat().st_size > 16777216:
            raise ValueError('Release source outside limits')
        data = path.read_bytes()
        if path.suffix == '.md':
            # Historical documentation can mention the developer's local paths;
            # publish portable labels rather than that machine-specific metadata.
            for absolute, replacement in ((str(root), '<PROJECT_ROOT>'), (root.as_posix(), '<PROJECT_ROOT>'),
                                           (str(Path.home()), '<USER_HOME>'), (Path.home().as_posix(), '<USER_HOME>')):
                data = data.replace(absolute.encode(), replacement.encode())
        if any(secret and secret.encode('utf8') in data for secret in forbidden_secrets):
            raise ValueError('Configured credential detected in release source')
        content[path.relative_to(root).as_posix()] = data
    required = {'README.md', 'pyproject.toml', 'uv.lock', 'requirements-dev.lock', '.env.example',
                'frontend/package.json', 'frontend/package-lock.json', 'docs/STATUS.md', 'docs/PHASE_PROGRESS.md',
                'demo-repository/pagination.py', 'demo-repository/tests/test_pagination.py'}
    if not required <= content.keys():
        raise ValueError('Required release source/locks/docs missing')
    manifest = {'product': 'WebGuard-AI', 'release': 'phase12-offline', 'live_gemini_verified': False,
                'live_github_verified': False, 'phase11_accepted_job': '802d2957d6ef48d182a8b04919e34165',
                'files': {name: digest(data) for name, data in sorted(content.items())},
                'excluded': 'Credentials, local databases/workspaces, caches, dependencies, builds and raw historical diagnostics'}
    content['RELEASE_MANIFEST.json'] = json.dumps(manifest, indent=2, sort_keys=True).encode('utf8')
    temporary = output.parent / ('.release-' + uuid.uuid4().hex + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(content.items()):
                member = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                member.compress_type = zipfile.ZIP_DEFLATED
                member.external_attr = 0o100644 << 16
                archive.writestr(member, data)
        result = verify_release(temporary, forbidden_secrets)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    checksum = output.with_suffix('.zip.sha256')
    checksum.write_text(result['sha256'] + '  ' + output.name + '\n', encoding='ascii')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='artifacts/WebGuard-AI-phase12-offline.zip')
    args = parser.parse_args()
    from dotenv import dotenv_values

    root = Path(__file__).resolve().parents[1]
    private = dotenv_values(root / '.env', interpolate=False)
    secrets = tuple(private.get(key) for key in ('AUTH_TOKEN', 'GEMINI_API_KEY', 'GITHUB_TOKEN') if private.get(key))
    try:
        result = build_release(root, root / args.output, secrets)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile):
        print(json.dumps({'zip_verified': False, 'reason': 'release_validation_failed_no_secret_output'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
