"""Image-owned bootstrap. Only this code runs before the approved test command."""

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

from webguard_checks import check_command


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    if os.getuid() != 10001 or os.getgid() != 10001 or sys.version_info[:2] != (3, 12):
        raise ValueError("runtime")
    profile = json.loads(Path("/opt/webguard/profile.json").read_bytes())
    manifest_path = Path("/input/manifest.json")
    if manifest_path.stat().st_size > 2097152:
        raise ValueError("manifest")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["schema"] != 1 or manifest["profile_digest"] != hashlib.sha256(canonical(profile)).hexdigest():
        raise ValueError("profile")
    source, destination = Path("/input/source"), Path("/scratch/work")
    expected = manifest["files"]
    if not expected or len(expected) > 10000:
        raise ValueError("files")
    actual = set()
    for folder, directories, files in os.walk(source, followlinks=False):
        for name in [*directories, *files]:
            path = Path(folder) / name
            if path.is_symlink():
                raise ValueError("link")
        for name in files:
            path = Path(folder) / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("type")
            actual.add(path.relative_to(source).as_posix())
    if actual != set(expected):
        raise ValueError("file set")
    destination.mkdir(mode=0o700)
    total = 0
    for name, receipt in expected.items():
        parts = name.split("/")
        if (len(name) > 240 or any(part in (".", "..", "") or not re.fullmatch(r"[A-Za-z0-9_. -]+", part)
                                   for part in parts)):
            raise ValueError("path")
        path = source.joinpath(*parts)
        if not 0 <= receipt["size"] <= 10485760:
            raise ValueError("size")
        with path.open("rb") as stream:
            data = stream.read(receipt["size"] + 1)
        total += len(data)
        if (len(data) != receipt["size"] or total > 104857600
                or hashlib.sha256(data).hexdigest() != receipt["sha256"]):
            raise ValueError("integrity")
        target = destination.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    Path("/scratch/tmp").mkdir()
    Path("/scratch/home").mkdir()
    os.chdir(destination)
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
                   "HOME": "/scratch/home", "TMPDIR": "/scratch/tmp",
                   "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    check = manifest['check']
    command = check_command(profile['test_command'], check['name'], check['test_id'], expected)
    seconds = int(os.environ["WEBGUARD_WALL_SECONDS"])
    if not 1 <= seconds <= 300:
        raise ValueError("deadline")
    # The image-owned PID 1 keeps a second watchdog if the controller disappears.
    process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                               start_new_session=True, shell=False)
    deadline = time.monotonic() + seconds
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
                return 124
            time.sleep(0.02)
        code = process.returncode if process.returncode >= 0 else 128 - process.returncode
        report = Path('/tmp/webguard-test-report.json')
        if report.is_symlink() or not report.is_file() or report.stat().st_size > 32768:
            raise ValueError('report')
        with report.open('rb') as stream:
            data = stream.read(32769)
        document = json.loads(data)
        # One final, bounded machine report; controller still validates all fields.
        print('\nWEBGUARD_PYTEST_REPORT=' + json.dumps(document, ensure_ascii=True,
                                                      separators=(',', ':')), flush=True)
        return code
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - bootstrap errors never expose source/daemon details.
        print("Trusted runner bootstrap failed.", file=sys.stderr)
        raise SystemExit(125) from None
