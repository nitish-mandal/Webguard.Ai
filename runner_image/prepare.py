"""Create a small trusted Docker build context. Does not build images or run source."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.source_common import no_links
from worker.workspaces import DEMO_PROFILE

PACKAGES = {"pytest": "9.2.0", "iniconfig": "2.3.1", "packaging": "26.3", "pluggy": "1.7.0",
            "pygments": "2.21.0", "colorama": "0.4.6"}


def locked_wheels(wheels: Path):
    no_links(wheels.absolute())
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf8"))
    selected = {package["name"]: package for package in lock["package"] if package["name"] in PACKAGES}
    allowed = {}
    requirements = []
    for name, version in PACKAGES.items():
        package = selected[name]
        if package["version"] != version:
            raise ValueError("Profile and dependency lock disagree")
        hashes = {wheel["hash"].removeprefix("sha256:") for wheel in package["wheels"]}
        allowed[name] = hashes
        requirements.append(f"{name}=={version} " + " ".join(f"--hash=sha256:{value}" for value in sorted(hashes)))
    files = []
    seen = set()
    for path in wheels.iterdir():
        no_links(path)
        match = re.fullmatch(r"([A-Za-z0-9_]+)-([0-9.]+)-(?:py3|py2\.py3)-none-any\.whl", path.name)
        if not match or not path.is_file() or path.stat().st_size > 10485760 or path.stat().st_nlink != 1:
            raise ValueError("Only locked pure-Python wheels are accepted")
        name, version = match[1].lower().replace("_", "-"), match[2]
        if name not in PACKAGES or version != PACKAGES[name]:
            raise ValueError("Unapproved wheel")
        if hashlib.sha256(path.read_bytes()).hexdigest() not in allowed[name] or name in seen:
            raise ValueError("Wheel hash or identity mismatch")
        seen.add(name)
        files.append(path)
    if seen != set(PACKAGES):
        raise ValueError("The complete locked wheel set is required")
    return files, requirements


def prepare(wheels: Path, output: Path, base: str):
    if not re.fullmatch(r"(?:docker.io/library/)?python:3\.12(?:\.[0-9]+)?-slim(?:-[a-z0-9]+)?@sha256:[0-9a-f]{64}", base):
        raise ValueError("A reviewed immutable Python 3.12 slim base digest is required")
    no_links(output.absolute())
    if output.exists():
        raise ValueError("Build context must be a new directory")
    files, requirements = locked_wheels(wheels)
    output.mkdir(parents=True)
    (output / "wheels").mkdir()
    (output / ".dockerignore").write_text(
        "**\n!Dockerfile\n!entrypoint.py\n!stage.py\n!webguard_report.py\n!check_policy.py\n!test_pagination_regression.py\n!pytest.ini\n!profile.json\n!requirements.lock\n!wheels/\n!wheels/*.whl\n",
        encoding="utf8",
    )
    for name in ("Dockerfile", "entrypoint.py", "stage.py", "webguard_report.py", "pytest.ini", 'test_pagination_regression.py'):
        shutil.copyfile(ROOT / "runner_image" / name, output / name)
    shutil.copyfile(ROOT / 'worker/check_policy.py', output / 'check_policy.py')
    for path in files:
        shutil.copyfile(path, output / "wheels" / path.name)
    (output / "profile.json").write_text(json.dumps(asdict(DEMO_PROFILE), sort_keys=True), encoding="utf8")
    (output / "requirements.lock").write_text("\n".join(requirements) + "\n", encoding="utf8")
    (output / "build-receipt.json").write_text(json.dumps({
        "base": base, "profile_digest": DEMO_PROFILE.digest,
        "wheel_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    }, sort_keys=True), encoding="utf8")
    return DEMO_PROFILE.digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    try:
        print(prepare(args.wheels, args.output, args.base))
    except (ValueError, OSError, KeyError):
        raise SystemExit("Trusted image preparation rejected; check base and locked wheel set.") from None
