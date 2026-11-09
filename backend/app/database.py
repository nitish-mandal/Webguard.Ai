"""File-backed SQLite, short transactions and numbered atomic migrations."""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS = (
    (
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY, idempotency_hash TEXT NOT NULL UNIQUE,
            payload_hash TEXT NOT NULL, repository TEXT NOT NULL, ref TEXT NOT NULL,
            sha TEXT, state TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
            deadline REAL NOT NULL, failure_reason TEXT,
            cancellation_requested INTEGER NOT NULL DEFAULT 0, cancelled_at REAL,
            repair_attempts INTEGER NOT NULL DEFAULT 0,
            publication_attempts INTEGER NOT NULL DEFAULT 0, claims INTEGER NOT NULL DEFAULT 0,
            model_calls INTEGER NOT NULL DEFAULT 0, model_tokens INTEGER NOT NULL DEFAULT 0,
            cost_micros INTEGER NOT NULL DEFAULT 0, execution_seconds INTEGER NOT NULL DEFAULT 0,
            max_repair_attempts INTEGER NOT NULL, max_publication_attempts INTEGER NOT NULL,
            max_lease_claims INTEGER NOT NULL, max_model_calls INTEGER NOT NULL,
            max_model_tokens INTEGER NOT NULL, max_cost_micros INTEGER NOT NULL,
            max_execution_seconds INTEGER NOT NULL, max_output_bytes INTEGER NOT NULL,
            max_patch_files INTEGER NOT NULL, max_patch_lines INTEGER NOT NULL,
            lease_owner TEXT, lease_expires_at REAL, fence INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE events (
            job_id TEXT NOT NULL REFERENCES jobs(id), sequence INTEGER NOT NULL,
            created_at REAL NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
            PRIMARY KEY (job_id, sequence)
        )""",
        """CREATE TABLE evidence (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
            created_at REAL NOT NULL, kind TEXT NOT NULL, sha TEXT NOT NULL,
            patch_digest TEXT, artifact_digest TEXT NOT NULL, exit_code INTEGER NOT NULL,
            summary TEXT NOT NULL
        )""",
        """CREATE TABLE publications (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), branch TEXT NOT NULL,
            pr_number INTEGER, url TEXT, draft INTEGER NOT NULL CHECK(draft=1),
            sha TEXT NOT NULL, patch_digest TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        )""",
    ),
    (
        "ALTER TABLE evidence ADD COLUMN repair_attempt INTEGER NOT NULL DEFAULT 0",
        "CREATE INDEX jobs_listing ON jobs(created_at, id)",
        "CREATE INDEX jobs_claimable ON jobs(state, lease_expires_at, deadline)",
        "CREATE INDEX evidence_job ON evidence(job_id, created_at, id)",
    ),
    (
        """CREATE TABLE source_snapshots (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), workspace_id TEXT NOT NULL UNIQUE,
            sha TEXT NOT NULL, manifest_digest TEXT NOT NULL, profile_digest TEXT NOT NULL,
            created_at REAL NOT NULL
        )""",
    ),
    (
        """CREATE TABLE repair_candidates (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
            repair_attempt INTEGER NOT NULL, created_at REAL NOT NULL,
            sha TEXT NOT NULL, source_manifest_digest TEXT NOT NULL, profile_digest TEXT NOT NULL,
            detection_id TEXT NOT NULL REFERENCES evidence(id), attempt_id TEXT NOT NULL,
            patch_digest TEXT NOT NULL, artifact_digest TEXT NOT NULL, provider TEXT NOT NULL,
            diagnosis TEXT NOT NULL, changed_files TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status='proposed'), UNIQUE(job_id, repair_attempt)
        )""",
    ),
    (
        """CREATE TABLE verification_rounds (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
            candidate_id TEXT NOT NULL REFERENCES repair_candidates(id), round INTEGER NOT NULL,
            created_at REAL NOT NULL, finished_at REAL, sha TEXT NOT NULL, patch_digest TEXT NOT NULL,
            image_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('running','failed','blocked','verified')),
            artifact_digest TEXT, evidence_id TEXT REFERENCES evidence(id), reason TEXT,
            UNIQUE(job_id, round)
        )""",
    ),
    (
        """CREATE TABLE publication_intents (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), repository TEXT NOT NULL,
            base_ref TEXT NOT NULL, base_sha TEXT NOT NULL, patch_digest TEXT NOT NULL,
            verification_id TEXT NOT NULL REFERENCES verification_rounds(id), evidence_digest TEXT NOT NULL,
            marker TEXT NOT NULL UNIQUE, branch TEXT NOT NULL UNIQUE, mode TEXT NOT NULL CHECK(mode IN ('offline','live')),
            created_at REAL NOT NULL, commit_sha TEXT, phase TEXT NOT NULL,
            stale INTEGER NOT NULL DEFAULT 0, last_error TEXT, pr_number INTEGER, pr_url TEXT
        )""",
    ),
    (
        """CREATE TABLE job_dispatch (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), next_run_at REAL NOT NULL DEFAULT 0,
            paused INTEGER NOT NULL DEFAULT 0, stage TEXT, reason TEXT,
            reconciliations INTEGER NOT NULL DEFAULT 0, reconcile_after REAL NOT NULL DEFAULT 0,
            terminal_cleaned INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE worker_sessions (
            owner TEXT PRIMARY KEY, started_at REAL NOT NULL, heartbeat_at REAL NOT NULL,
            expires_at REAL NOT NULL, stop_requested INTEGER NOT NULL DEFAULT 0,
            stopped INTEGER NOT NULL DEFAULT 0, repository TEXT NOT NULL
        )""",
    ),
)


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self, target: int = len(MIGRATIONS)) -> None:
        if not 0 <= target <= len(MIGRATIONS):
            raise ValueError("Unsupported schema version")
        with self.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                               "(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
            versions = [row[0] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version")]
            if versions != list(range(1, len(versions) + 1)) or len(versions) > target:
                raise RuntimeError("Unsupported or inconsistent database schema")
            for number in range(len(versions) + 1, target + 1):
                for statement in MIGRATIONS[number - 1]:
                    connection.execute(statement)
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)",
                                   (number, time.time()))
