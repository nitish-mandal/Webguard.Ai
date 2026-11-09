"""Trusted acquisition limits and portable path rules. No target code execution."""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class SourceError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Source operation rejected ({code})")


@dataclass(frozen=True)
class SourceLimits:
    file_bytes: int = 1048576
    total_bytes: int = 10485760
    files: int = 1000
    archive_bytes: int = 10485760
    metadata_bytes: int = 1048576
    seconds: float = 20

    def __post_init__(self):
        if any(value <= 0 for value in (self.file_bytes, self.total_bytes, self.files,
                                       self.archive_bytes, self.metadata_bytes, self.seconds)):
            raise SourceError("configuration")


class Budget:
    def __init__(self, seconds: float):
        self.deadline = time.monotonic() + seconds

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError("timeout")
        return remaining


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise SourceError("workspace_identity")
    return value


def revision(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise SourceError("revision")
    return value


def safe_path(value: str) -> str:
    if not isinstance(value, str) or len(value) > 240:
        raise SourceError("unsafe_path")
    parts = value.split("/")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)),
                *(f"lpt{i}" for i in range(10))}
    if len(parts) > 16:
        raise SourceError("unsafe_path")
    for part in parts:
        if (not re.fullmatch(r"[A-Za-z0-9_. -]+", part) or part in (".", "..")
                or part.endswith((".", " ")) or part.casefold() in (".git", ".gitmodules")
                or part.split(".")[0].casefold() in reserved):
            raise SourceError("unsafe_path")
    if str(PurePosixPath(value)) != value:
        raise SourceError("unsafe_path")
    return value


def no_links(path: Path) -> None:
    """Reject symlinks AND Windows junctions/reparse points along the path."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SourceError("filesystem_link")


@dataclass(frozen=True)
class Entry:
    path: str
    oid: str
    size: int


def validate_entries(entries: list[Entry], limits: SourceLimits) -> list[Entry]:
    if not entries or len(entries) > limits.files:
        raise SourceError("size_limit")
    seen = set()
    spellings = {}
    total = 0
    for entry in entries:
        safe_path(entry.path)
        revision(entry.oid)
        if type(entry.size) is not int or not 0 <= entry.size <= limits.file_bytes:
            raise SourceError("size_limit")
        key = entry.path.casefold()
        if key in seen:
            raise SourceError("path_collision")
        seen.add(key)
        parts = entry.path.split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            if prefix.casefold() in spellings and spellings[prefix.casefold()] != prefix:
                raise SourceError("path_collision")
            spellings[prefix.casefold()] = prefix
        total += entry.size
    for key in seen:
        if any(parent.as_posix() in seen for parent in PurePosixPath(key).parents if str(parent) != "."):
            raise SourceError("path_collision")
    if total > limits.total_bytes:
        raise SourceError("size_limit")
    return entries


def write_blob(destination: Path, entry: Entry, data: bytes) -> None:
    if len(data) != entry.size:
        raise SourceError("integrity")
    header = f"blob {len(data)}\0".encode()
    digest = (hashlib.sha1(header + data, usedforsecurity=False) if len(entry.oid) == 40
              else hashlib.sha256(header + data)).hexdigest()
    if digest != entry.oid:
        raise SourceError("integrity")
    target = destination.joinpath(*safe_path(entry.path).split("/"))
    no_links(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)


class GitReader:
    """Only read-only plumbing commands; no fetch, checkout, filters or hooks."""

    def __init__(self, cwd: Path):
        self.executable = shutil.which("git")
        if self.executable is None:
            raise SourceError("git_unavailable")
        self.cwd = cwd
        no_links(cwd)
        cwd.mkdir(parents=True, exist_ok=True)

    def run(self, git_dir: Path, arguments: list[str], budget: Budget, cap: int) -> bytes:
        if not arguments or arguments[0] not in ("rev-parse", "ls-tree", "cat-file"):
            raise SourceError("command")
        no_links(git_dir)
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
               if key in os.environ}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_SYSTEM": os.devnull, "GIT_TERMINAL_PROMPT": "0",
                    "GIT_ASKPASS": "", "SSH_ASKPASS": "", "GIT_NO_REPLACE_OBJECTS": "1",
                    "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "",
                    "GIT_OPTIONAL_LOCKS": "0", "GIT_ATTR_NOSYSTEM": "1"})
        command = [self.executable, "--no-pager", "-c", f"core.hooksPath={os.devnull}",
                   "-c", "core.fsmonitor=false", "-c", "credential.helper=", "-c",
                   "protocol.allow=never", f"--git-dir={git_dir}", *arguments]
        output = bytearray()
        errors = bytearray()
        overflow = threading.Event()

        def drain(pipe, buffer, limit):
            while chunk := pipe.read(4096):
                if len(buffer) + len(chunk) > limit:
                    overflow.set()
                else:
                    buffer.extend(chunk)

        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            with subprocess.Popen(command, cwd=self.cwd, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                  creationflags=flags) as process:
                threads = [threading.Thread(target=drain, args=(process.stdout, output, cap)),
                           threading.Thread(target=drain, args=(process.stderr, errors, 65536))]
                for thread in threads:
                    thread.start()
                failure = None
                try:
                    while process.poll() is None:
                        budget.remaining()
                        if overflow.is_set():
                            raise SourceError("output_limit")
                        time.sleep(0.005)
                except SourceError as error:
                    failure = error
                    process.kill()
                finally:
                    process.wait(timeout=2)
                    for thread in threads:
                        thread.join(timeout=2)
                if failure:
                    raise failure
                budget.remaining()
                if overflow.is_set():
                    raise SourceError("output_limit")
                if process.returncode or errors:
                    raise SourceError("git_failure")
        except (OSError, subprocess.SubprocessError):
            raise SourceError("git_failure") from None
        return bytes(output)
