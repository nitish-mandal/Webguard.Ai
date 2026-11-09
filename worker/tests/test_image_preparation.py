"""Validate trusted build contexts without building/running an image or target."""

import hashlib
import json
from pathlib import Path

import pytest

from runner_image import prepare as module
from worker.workspaces import DEMO_PROFILE

BASE = 'python:3.12-slim@sha256:' + 'a' * 64


@pytest.fixture
def wheel_set(tmp_path, monkeypatch):
    root = tmp_path / 'controller'
    root.mkdir()
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    records = []
    for name, version in module.PACKAGES.items():
        tag = 'py2.py3' if name == 'colorama' else 'py3'
        path = wheels / f'{name}-{version}-{tag}-none-any.whl'
        content = ('synthetic trusted wheel for ' + name).encode()
        path.write_bytes(content)
        records.append(f'[[package]]\nname="{name}"\nversion="{version}"\nwheels=[{{hash="sha256:{hashlib.sha256(content).hexdigest()}"}}]\n')
    (root / 'uv.lock').write_text('\n'.join(records), encoding='utf8')
    asset_dir = root / 'runner_image'
    asset_dir.mkdir()
    real_assets = Path(module.__file__).parent
    for name in ('Dockerfile', 'entrypoint.py', 'stage.py', 'webguard_report.py', 'pytest.ini', 'test_pagination_regression.py'):
        (asset_dir / name).write_bytes((real_assets / name).read_bytes())
    (root / 'worker').mkdir()
    (root / 'worker/check_policy.py').write_bytes((real_assets.parent / 'worker/check_policy.py').read_bytes())
    monkeypatch.setattr(module, 'ROOT', root)
    return wheels


def test_build_context_contains_only_controlled_assets_and_hash_locked_wheels(wheel_set, tmp_path):
    output = tmp_path / 'new-context'
    assert module.prepare(wheel_set, output, BASE) == DEMO_PROFILE.digest
    assert {path.name for path in (output / 'wheels').iterdir()} == {path.name for path in wheel_set.iterdir()}
    profile = json.loads((output / 'profile.json').read_bytes())
    assert profile['name'] == 'approved-demo-python-pytest-v4'
    assert 'webguard_report' in profile['test_command']
    assert (output / 'webguard_report.py').is_file()
    assert '/opt/webguard/pytest.ini' in profile['test_command']
    assert '--capture=no' in profile['test_command']
    lock = (output / 'requirements.lock').read_text()
    assert lock.count('--hash=sha256:') == 6
    assert '**\n' in (output / '.dockerignore').read_text()
    dockerfile = (output / 'Dockerfile').read_text()
    assert '--require-hashes' in dockerfile and '--no-index' in dockerfile and '--no-deps' in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert 'COPY . ' not in dockerfile


@pytest.mark.parametrize('base', ['python:latest', 'python:3.12-slim', 'https://user:secret@host/base', 'other/image@sha256:' + 'a'*64])
def test_mutable_or_arbitrary_bases_are_rejected(wheel_set, tmp_path, base):
    with pytest.raises(ValueError): module.prepare(wheel_set, tmp_path / 'unused', base)
    assert not (tmp_path / 'unused').exists()


@pytest.mark.parametrize('case', ['modified', 'missing', 'extra', 'script', 'existing-context'])
def test_untrusted_or_incomplete_wheel_sets_and_existing_context_fail_closed(wheel_set, tmp_path, case):
    output = tmp_path / 'output'
    file = next(wheel_set.iterdir())
    if case == 'modified': file.write_bytes(b'modified wheel')
    elif case == 'missing': file.unlink()
    elif case == 'extra': (wheel_set / 'unapproved-1.0-py3-none-any.whl').write_bytes(b'no')
    elif case == 'script': (wheel_set / 'setup.py').write_text('raise RuntimeError("never execute")', encoding='utf8')
    else:
        output.mkdir()
        (output / 'keep').write_text('keep', encoding='utf8')
    with pytest.raises(ValueError): module.prepare(wheel_set, output, BASE)
    if case == 'existing-context': assert (output / 'keep').read_text() == 'keep'
    else: assert not output.exists()


@pytest.mark.parametrize('count,skips,pytest_exit,expected', [(16, 0, 0, 'passed'),
                                                            (16, 16, 0, 'blocked'),
                                                            (0, 0, 0, 'blocked'),
                                                            (16, 0, 1, 'failed')])
def test_acceptance_gate_never_promotes_skipped_or_unrun_isolation(count, skips, pytest_exit, expected):
    import xml.etree.ElementTree as ET

    from runner_image.check_isolation import verdict
    root = ET.Element('testsuite')
    for index in range(count):
        case = ET.SubElement(root, 'testcase')
        if index < skips: ET.SubElement(case, 'skipped')
    assert verdict(root, pytest_exit)['isolation_acceptance'] == expected
