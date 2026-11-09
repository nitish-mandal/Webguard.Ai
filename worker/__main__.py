"""Local worker CLI. Ctrl+C/--stop drains the current bounded job, then exits."""

import argparse
import json
import signal
import sqlite3
from dataclasses import asdict

from backend.app.domain import Conflict, NotFound
from backend.app.jobs import JobService
from backend.app.settings import SettingsError, load_settings
from worker.github_publishers import PublicationError
from worker.pipeline import Runtime, Worker
from worker.source_common import SourceError


def emit(data):
    print(json.dumps(data, sort_keys=True), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env', help='Private server settings file; API and worker must agree')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--stop', metavar='WORKER_ID', help='Request graceful drain; no force kill')
    action.add_argument('--resume', metavar='JOB_ID', help='Unpause after operator fixes a blocker; budgets unchanged')
    action.add_argument('--once', action='store_true', help='Claim/process at most one available job')
    args = parser.parse_args(argv)
    runtime = None
    try:
        settings = load_settings(args.env_file)
        if args.stop or args.resume:
            jobs = JobService(settings)
            if args.stop:
                jobs.stop_worker(args.stop)
                emit({'worker_id': args.stop, 'drain_requested': True, 'stopped_confirmed': False})
            else:
                jobs.resume_dispatch(args.resume)
                emit({'job_id': args.resume, 'resumed': True, 'budgets_reset': False})
            return 0
        runtime = Runtime.configured(settings)
        worker = Worker(runtime)
        for name in ('SIGINT', 'SIGTERM'):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), lambda *_: worker.stopping.set())
        if args.once:
            result = worker.run_once()
            emit(asdict(result) if result else {'idle': True})
        else:
            worker.serve(lambda owner: emit({'worker_id': owner, 'started': True,
                'gemini': 'live_configured' if settings.enable_live_gemini else 'offline_fake',
                'github': 'live_configured' if settings.enable_github_draft_pr else 'simulated'}))
            emit({'worker_id': worker.owner, 'stopped': True})
        return 0
    except (SettingsError, SourceError, PublicationError, Conflict, NotFound, ValueError, OSError, sqlite3.Error):
        emit({'error': 'worker_configuration_or_storage', 'detail': 'Check server setup and recorded job events.'})
        return 2
    except Exception:  # noqa: BLE001 - raw errors may include untrusted data/credentials.
        emit({'error': 'worker_stopped_unexpectedly', 'detail': 'Persisted leases recover on restart.'})
        return 1
    finally:
        if runtime:
            try:
                runtime.close()
            except (SourceError, OSError, sqlite3.Error):
                emit({'error': 'worker_cleanup_blocked', 'detail': 'Owned paths retained for operator review.'})
                raise SystemExit(2) from None


if __name__ == '__main__':
    raise SystemExit(main())
