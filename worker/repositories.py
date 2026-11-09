"""Approved GitHub HTTPS snapshots and a separate controller-selected fixture adapter."""

import gzip
import http.client
import json
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from backend.app.jobs import _ref
from backend.app.settings import Settings
from worker.source_common import (
    Budget,
    Entry,
    GitReader,
    SourceError,
    SourceLimits,
    no_links,
    revision,
    safe_path,
    validate_entries,
    write_blob,
)


def approved_identity(value: str) -> str:
    try:
        configured = Settings(allowed_repository=value)
    except ValueError:
        raise SourceError("identity") from None
    if configured.allowed_repository == "demo-repository":
        raise SourceError("identity")
    return configured.allowed_repository


def approved_ref(value: str) -> str:
    try:
        return _ref(value)
    except ValueError:
        raise SourceError("ref") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("redirect")


class HTTPS:
    """Public source only: no Authorization/cookies/proxies/redirects or ambient credentials."""

    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _transfer(self, host, path, cap, budget, destination=None):
        if host not in ("api.github.com", "codeload.github.com") or not path.startswith("/"):
            raise SourceError("host")
        url = f"https://{host}{path}"
        request = urllib.request.Request(url, headers={
            "User-Agent": "WebGuard-AI/0.1", "Accept-Encoding": "identity",
            "Accept": "application/vnd.github+json" if host == "api.github.com" else "application/octet-stream",
        })
        data = bytearray()
        output = None
        try:
            with self.opener.open(request, timeout=min(5, budget.remaining())) as response:
                if response.status != 200 or response.geturl() != url:
                    raise SourceError("redirect")
                encoding = response.headers.get("Content-Encoding", "identity")
                if encoding.lower() != "identity":
                    raise SourceError("transport")
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdigit() or len(length) > 12 or int(length) > cap):
                    raise SourceError("size_limit")
                if destination is not None:
                    output = destination.open("xb")
                count = 0
                while True:
                    budget.remaining()
                    # One buffered socket read, rather than waiting to fill 64 KiB
                    # from a slowly arriving response before checking the deadline.
                    chunk = response.read1(min(65536, cap - count + 1))
                    budget.remaining()
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > cap:
                        raise SourceError("size_limit")
                    if output:
                        output.write(chunk)
                    else:
                        data.extend(chunk)
        except TimeoutError:
            raise SourceError("timeout") from None
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
            raise SourceError("transport") from None
        finally:
            if output:
                output.close()
        return bytes(data)

    def read(self, host, path, cap, budget):
        return self._transfer(host, path, cap, budget)

    def download(self, host, path, destination, cap, budget):
        self._transfer(host, path, cap, budget, destination)


class LimitedReader:
    def __init__(self, reader, cap, budget):
        self.reader, self.remaining, self.budget = reader, cap, budget

    def read(self, size=-1):
        self.budget.remaining()
        size = min(size if size >= 0 else self.remaining + 1, self.remaining + 1)
        data = self.reader.read(size)
        self.remaining -= len(data)
        if self.remaining < 0:
            raise SourceError("size_limit")
        self.budget.remaining()
        return data


class GitHubRepository:
    def __init__(self, repository: str, transport=None):
        self.repository = approved_identity(repository)
        self.transport = transport if transport is not None else HTTPS()
        self.trees = {}

    @property
    def url(self):
        return f"https://github.com/{self.repository}.git"

    def _json(self, path, limits, budget):
        try:
            raw = self.transport.read("api.github.com", path, limits.metadata_bytes, budget)
            if len(raw) > limits.metadata_bytes:
                raise SourceError("size_limit")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise SourceError("metadata")
            return value
        except (ValueError, UnicodeError, RecursionError):
            raise SourceError("metadata") from None

    def resolve(self, ref: str, limits: SourceLimits, budget: Budget) -> str:
        approved_ref(ref)
        metadata = self._json(f"/repos/{self.repository}", limits, budget)
        if (not isinstance(metadata.get("full_name"), str)
                or metadata["full_name"].lower() != self.repository):
            raise SourceError("identity")
        commit = self._json(f"/repos/{self.repository}/commits/{urllib.parse.quote(ref, safe='')}",
                            limits, budget)
        sha = revision(commit.get("sha"))
        try:
            self.trees[sha] = revision(commit["commit"]["tree"]["sha"])
        except (KeyError, TypeError):
            raise SourceError("metadata") from None
        return sha

    def acquire(self, sha: str, destination: Path, limits: SourceLimits, budget: Budget):
        revision(sha)
        if sha not in self.trees:
            commit = self._json(f"/repos/{self.repository}/git/commits/{sha}", limits, budget)
            if commit.get("sha") != sha or not isinstance(commit.get("tree"), dict):
                raise SourceError("integrity")
            self.trees[sha] = revision(commit["tree"].get("sha"))
        tree = self._json(f"/repos/{self.repository}/git/trees/{self.trees[sha]}?recursive=1", limits, budget)
        if tree.get("sha") != self.trees[sha]:
            raise SourceError("integrity")
        rows = tree.get("tree")
        if tree.get("truncated") is not False or not isinstance(rows, list) or len(rows) > limits.files * 4:
            raise SourceError("metadata")
        entries = []
        directories = set()
        for row in rows:
            if not isinstance(row, dict):
                raise SourceError("metadata")
            path = safe_path(row.get("path"))
            mode = row.get("mode")
            if mode == "040000" and row.get("type") == "tree":
                directories.add(path)
            elif mode in ("100644", "100755") and row.get("type") == "blob":
                entries.append(Entry(path, revision(row.get("sha")), row.get("size")))
            else:
                raise SourceError("unsafe_tree")
        validate_entries(entries, limits)
        archive = destination.parent / "source.tar.gz"
        self.transport.download("codeload.github.com", f"/{self.repository}/tar.gz/{sha}",
                                archive, limits.archive_bytes, budget)
        if archive.stat().st_size > limits.archive_bytes:
            raise SourceError("size_limit")
        expected = {entry.path: entry for entry in entries}
        seen = set()
        root = None
        count = 0
        cap = limits.total_bytes + limits.files * 8192 + 65536
        try:
            with archive.open("rb") as raw:
                compressed = LimitedReader(raw, limits.archive_bytes, budget)
                with gzip.GzipFile(fileobj=compressed) as zipped:  # noqa: SIM117 - named bounded layers
                    with tarfile.open(fileobj=LimitedReader(zipped, cap, budget), mode="r|") as tar:
                        for member in tar:
                            budget.remaining()
                            count += 1
                            if count > limits.files * 4 + 1:
                                raise SourceError("size_limit")
                            name = member.name.rstrip("/")
                            prefix, separator, relative = name.partition("/")
                            safe_path(prefix)
                            if separator:
                                safe_path(relative)
                            if root is None:
                                root = prefix
                            if prefix != root:
                                raise SourceError("unsafe_path")
                            if not separator:
                                if not member.isdir():
                                    raise SourceError("unsafe_tree")
                                continue
                            if member.isdir():
                                if relative not in directories:
                                    raise SourceError("integrity")
                                continue
                            if (not member.isreg() or member.sparse is not None
                                    or relative not in expected or relative in seen):
                                raise SourceError("unsafe_tree")
                            entry = expected[relative]
                            if member.size != entry.size:
                                raise SourceError("size_limit")
                            source = tar.extractfile(member)
                            if source is None:
                                raise SourceError("integrity")
                            data = source.read(entry.size + 1)
                            write_blob(destination, entry, data)
                            seen.add(relative)
            if seen != set(expected):
                raise SourceError("integrity")
        except (tarfile.TarError, EOFError, OSError, zlib.error):
            raise SourceError("archive") from None
        finally:
            archive.unlink(missing_ok=True)


class LocalFixtureRepository:
    """A controller-injected ordinary Git directory. Never selected by an HTTP path."""

    repository = "demo-repository"

    def __init__(self, source: Path, reader: GitReader):
        source = source.absolute()
        no_links(source)
        self.git_dir = source / ".git"
        no_links(self.git_dir)
        if not self.git_dir.is_dir():
            raise SourceError("fixture_not_git")
        self.reader = reader

    def resolve(self, ref: str, limits: SourceLimits, budget: Budget) -> str:
        approved_ref(ref)
        raw = self.reader.run(self.git_dir, ["rev-parse", "--verify", "--end-of-options",
                                              f"{ref}^{{commit}}"], budget, 128)
        try:
            return revision(raw.decode("ascii").strip())
        except UnicodeError:
            raise SourceError("revision") from None

    def acquire(self, sha: str, destination: Path, limits: SourceLimits, budget: Budget):
        revision(sha)
        raw = self.reader.run(self.git_dir, ["ls-tree", "-r", "-z", "-l", "--full-tree", sha],
                              budget, limits.metadata_bytes)
        entries = []
        try:
            for line in raw.split(b"\0"):
                if not line:
                    continue
                metadata, name = line.split(b"\t", 1)
                mode, kind, oid, size = metadata.split()
                if mode not in (b"100644", b"100755") or kind != b"blob":
                    raise SourceError("unsafe_tree")
                entries.append(Entry(name.decode("ascii"), oid.decode("ascii"), int(size)))
        except (ValueError, UnicodeError):
            raise SourceError("unsafe_tree") from None
        validate_entries(entries, limits)
        for entry in entries:
            budget.remaining()
            data = self.reader.run(self.git_dir, ["cat-file", "blob", entry.oid],
                                   budget, min(limits.file_bytes, entry.size) + 1)
            write_blob(destination, entry, data)
