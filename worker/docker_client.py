"""Bounded Docker CLI transport. Never execute shell strings or expose raw CLI errors."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit


class DockerFault(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"Docker operation unavailable ({code})")


class Capture:
    def __init__(self, command, env, limit, payload=None):
        self.stdout, self.stderr = bytearray(), bytearray()
        self.overflow = threading.Event()
        self.io_error = threading.Event()
        self.lock = threading.Lock()
        self.total = 0
        self.process = subprocess.Popen(
            command, env=env, stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        def read(pipe, buffer):
            try:
                while chunk := pipe.read(4096):
                    with self.lock:
                        available = max(0, limit - self.total)
                        buffer.extend(chunk[:available])
                        self.total += len(chunk[:available])
                        if len(chunk) > available:
                            self.overflow.set()
            except (OSError, ValueError):
                self.io_error.set()

        self.threads = [threading.Thread(target=read, args=(self.process.stdout, self.stdout), daemon=True),
                        threading.Thread(target=read, args=(self.process.stderr, self.stderr), daemon=True)]
        if payload is not None:
            def write():
                try:
                    self.process.stdin.write(payload)
                    self.process.stdin.close()
                except (OSError, ValueError):
                    self.io_error.set()
            self.threads.append(threading.Thread(target=write, daemon=True))
        for thread in self.threads:
            thread.start()

    def poll(self):
        return self.process.poll()

    def stop(self):
        if self.poll() is None:
            self.process.kill()

    def finish(self, timeout):
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop()
            self.process.wait(timeout=2)
            raise DockerFault("cli_timeout") from None
        finally:
            for thread in self.threads:
                thread.join(timeout=2)
            for pipe in (self.process.stdout, self.process.stderr, self.process.stdin):
                if pipe is not None:
                    pipe.close()
        if any(thread.is_alive() for thread in self.threads) or self.io_error.is_set():
            raise DockerFault("cli_io")
        return self.process.returncode


class DockerCLI:
    def __init__(self, timeout=10):
        self.executable = shutil.which("docker")
        self.timeout = timeout
        keys = ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "HOME", "USERPROFILE",
                "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
        self.env = {key: os.environ[key] for key in keys if key in os.environ}
        endpoint = urlsplit(self.env.get("DOCKER_HOST", ""))
        self.invalid_endpoint = bool(endpoint.scheme and (
            endpoint.scheme not in ("unix", "npipe", "tcp") or endpoint.username
            or endpoint.password or endpoint.query or endpoint.fragment))
        # Docker's normal client config can inject credential-bearing proxy Env
        # into every container. Execution uses an empty, service-owned config.
        self.configuration = tempfile.TemporaryDirectory(prefix="webguard-docker-cli-")
        from pathlib import Path

        Path(self.configuration.name, "config.json").write_text('{"auths":{},"proxies":{}}', encoding="utf8")
        self.env["DOCKER_CONFIG"] = self.configuration.name

    def close(self):
        self.configuration.cleanup()

    def attach(self, container, limit):
        if not self.executable:
            raise DockerFault("docker_missing")
        if self.invalid_endpoint:
            raise DockerFault("docker_endpoint")
        try:
            return Capture([self.executable, "container", "start", "--attach", container],
                           self.env, limit)
        except OSError:
            raise DockerFault("docker_unavailable") from None

    def command(self, arguments, payload=None, missing=None):
        if not self.executable:
            raise DockerFault("docker_missing")
        if self.invalid_endpoint:
            raise DockerFault("docker_endpoint")
        try:
            capture = Capture([self.executable, *arguments], self.env, 1048576, payload)
            deadline = time.monotonic() + self.timeout
            while capture.poll() is None:
                if time.monotonic() >= deadline or capture.overflow.is_set():
                    capture.stop()
                    break
                time.sleep(0.01)
            code = capture.finish(2)
            if time.monotonic() >= deadline:
                raise DockerFault("cli_timeout")
            if capture.overflow.is_set():
                raise DockerFault("cli_output_limit")
            if code:
                if missing:
                    name = re.escape(missing.encode())
                    absent = (rb"(?:No such (?:container|volume|object):\s*)" + name + rb"\s*$",
                              rb"Error response from daemon: get " + name + rb": no such volume\s*$")
                    if any(re.search(pattern, bytes(capture.stderr), re.IGNORECASE) for pattern in absent):
                        return None
                if bytes(capture.stderr).startswith(b"Error response from daemon:"):
                    raise DockerFault("daemon_error")
                raise DockerFault("cli_failed")
            if capture.stderr:
                # Docker warnings about discarded resource constraints are not success.
                raise DockerFault("cli_warning")
            return bytes(capture.stdout)
        except (OSError, subprocess.SubprocessError):
            raise DockerFault("docker_unavailable") from None

    def document(self, arguments):
        try:
            value = json.loads(self.command(arguments))
            if not isinstance(value, dict):
                raise DockerFault("cli_document")
            return value
        except (ValueError, TypeError):
            raise DockerFault("cli_document") from None

    def inspect(self, kind, name, optional=False):
        raw = self.command([kind, "inspect", "--format", "{{json .}}", name],
                           missing=name if optional else None)
        if raw is None:
            return None
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise DockerFault("cli_document")
            return value
        except (ValueError, TypeError):
            raise DockerFault("cli_document") from None
