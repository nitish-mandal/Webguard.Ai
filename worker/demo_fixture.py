"""One owned deterministic Git copy of the bundled demo; never run its code."""

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from worker.source_common import SourceError, no_links
from worker.workspaces import canonical


class DemoFixture:
    def __init__(self, manager, owner):
        self.manager = manager
        self.workspace = manager.create(uuid.uuid4().hex)
        self.path = manager.path(self.workspace) / 'baseline'
        try:
            (manager.path(self.workspace) / '.fixture-owner.json').write_bytes(canonical({
                'version': 1, 'owner': owner, 'created_at': time.time(),
                'job_id': self.workspace.job_id, 'workspace_id': self.workspace.workspace_id}))
            demo = Path(__file__).resolve().parents[1] / 'demo-repository'
            for name in ('README.md', 'pagination.py', 'tests/test_pagination.py'):
                source = demo / name
                no_links(source)
                if source.stat().st_size > 65536:
                    raise SourceError('demo_fixture')
                target = self.path / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            executable = shutil.which('git')
            if not executable:
                raise SourceError('git_missing')
            env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP') if key in os.environ}
            env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
                       GIT_AUTHOR_DATE='2000-01-01T00:00:00Z', GIT_COMMITTER_DATE='2000-01-01T00:00:00Z')
            for arguments in (['init', '--template=', '-b', 'main'], ['add', '--', 'README.md', 'pagination.py', 'tests/test_pagination.py'],
                              ['commit', '-m', 'Approved unchanged demo baseline']):
                process = subprocess.run([executable, '-c', 'user.name=WebGuard-AI fixture',
                    '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgSign=false',
                    '-c', 'core.autocrlf=false', '-c', f'core.hooksPath={os.devnull}', *arguments],
                    cwd=self.path, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=10, shell=False, check=False)
                if process.returncode:
                    raise SourceError('demo_fixture')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.path.parent.exists():
            self.manager.cleanup(self.workspace)
