"""Validate untrusted anchored source edits, then apply to a new owned copy only."""

import ast
import difflib
import hashlib
import json
from pathlib import PurePosixPath

from pydantic import ValidationError

from worker.repair_models import RepairError, RepairProposal
from worker.source_common import Budget, SourceError, no_links, safe_path
from worker.workspaces import canonical


def parse_proposal(raw, max_bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    try:
        if not isinstance(raw, str) or len(raw.encode()) > max_bytes:
            raise ValueError('size')
        proposal = RepairProposal.model_validate(json.loads(raw, object_pairs_hook=unique))
        if not proposal.diagnosis.strip():
            raise ValueError('empty diagnosis')
        for value in [proposal.diagnosis, *(value for edit in proposal.edits
                                           for value in (edit.path, edit.old_text, edit.new_text))]:
            value.encode('utf8')  # Reject escaped unpaired surrogates before filesystem/SQLite use.
        return proposal
    except (ValueError, TypeError, ValidationError, RecursionError):
        raise RepairError('invalid_proposal') from None


def approved_path(name, profile):
    try:
        safe_path(name)
    except SourceError:
        raise RepairError('invalid_edit') from None
    path = PurePosixPath(name)
    parts = [part.casefold() for part in path.parts]
    forbidden = {'tests', 'test', 'test.py', 'secrets.py', 'credentials.py', 'config.py', 'settings.py',
                 'setup.py', 'conftest.py', 'workflows', 'dependencies', 'requirements'}
    if (name not in profile.source_edit_allowlist or path.suffix != '.py'
            or any(part in forbidden or part.startswith(('.', 'test_')) or part.endswith('_test.py')
                   for part in parts)):
        raise RepairError('invalid_edit')
    return name


def validate_edits(manager, workspace, profile, proposal, context, row, redactor):
    manifest = manager.verify(workspace, Budget(manager.limits.seconds))
    prepared = {}
    lines_changed = 0
    source_context = {item['path']: item['text'] for item in context['source']}
    for edit in proposal.edits:
        name = approved_path(edit.path, profile)
        if name in prepared or name not in source_context:
            raise RepairError('invalid_edit')
        source = manager.path(workspace) / 'baseline' / name
        no_links(source)
        if name not in manifest['files'] or source.stat().st_nlink != 1:
            raise RepairError('invalid_edit')
        data = source.read_bytes()
        try:
            old = data.decode('utf8')
        except UnicodeError:
            raise RepairError('invalid_edit') from None
        if (edit.old_text not in source_context[name] or old.count(edit.old_text) != 1
                or edit.old_text == edit.new_text or '\x00' in edit.new_text
                or any(redactor.text(value) != value or '[REDACTED]' in value
                       for value in (edit.old_text, edit.new_text))):
            raise RepairError('invalid_edit')
        new = old.replace(edit.old_text, edit.new_text, 1)
        if len(new.encode()) > manager.limits.file_bytes:
            raise RepairError('patch_limit')
        try:
            ast.parse(new, filename=name)  # Syntax only, never import/compile/execute target code.
        except (SyntaxError, ValueError, RecursionError):
            raise RepairError('invalid_edit') from None
        matcher = difflib.SequenceMatcher(a=edit.old_text.splitlines(), b=edit.new_text.splitlines(), autojunk=False)
        for operation, a, b, c, d in matcher.get_opcodes():
            if operation != 'equal':
                lines_changed += b - a + d - c
        prepared[name] = new.encode()
    if len(prepared) > row['max_patch_files'] or lines_changed > row['max_patch_lines']:
        raise RepairError('patch_limit')
    return prepared, lines_changed


def apply_edits(manager, workspace, number, prepared, heartbeat):
    attempt = manager.create_attempt(workspace, number, Budget(manager.limits.seconds))
    try:
        heartbeat()
        for name, data in prepared.items():
            target = attempt / name
            no_links(target)
            if target.stat().st_nlink != 1:
                raise RepairError('invalid_edit')
            with target.open('wb') as output:
                output.write(data)
        actual = manager._inventory(attempt, Budget(manager.limits.seconds))
        baseline = manager.verify(workspace, Budget(manager.limits.seconds))['files']
        changed = {name for name in actual if actual[name] != baseline.get(name)}
        if actual.keys() != baseline.keys() or changed != prepared.keys():
            raise RepairError('invalid_edit')
        heartbeat()
        digest = hashlib.sha256(canonical({'baseline_manifest': workspace.manifest_digest, 'files': actual})).hexdigest()
        return attempt, digest
    except BaseException:
        manager.cleanup_attempt(workspace, attempt)
        raise
