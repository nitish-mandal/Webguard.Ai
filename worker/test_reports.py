"""Strict bounded pytest report decoding; repository content is data, never instructions."""

import ast
import hashlib
import json
import re

from worker.docker_runner import output_text
from worker.source_common import SourceError, safe_path
from worker.workspaces import canonical

PREFIX = 'WEBGUARD_PYTEST_REPORT='


def comparison(message, trace):
    match = re.search(r'^assert (.+?) == (.+)$', message, re.MULTILINE)
    if not match:
        return None
    value = {'left': match[1][:512], 'operator': '==', 'right': match[2][:512],
             'expected': None, 'actual': None, 'basis': 'operands only; intent unverified'}
    # Infer roles only when the assertion source has a literal right-hand expectation.
    # AST/literal parsing never imports or executes repository expressions.
    for line in trace.splitlines():
        source = line.lstrip('> ').strip()
        if not source.startswith('assert '):
            continue
        try:
            assertion = ast.parse(source).body[0]
            expression = assertion.test if isinstance(assertion, ast.Assert) else None
            if (isinstance(expression, ast.Compare) and len(expression.ops) == 1
                    and isinstance(expression.ops[0], ast.Eq)
                    and ast.literal_eval(expression.comparators[0]) == ast.literal_eval(match[2])):
                value.update(expected=match[2][:512], actual=match[1][:512],
                             basis='literal right-hand expectation in assertion source')
                break
        except (SyntaxError, ValueError, TypeError, RecursionError):
            continue
    return value


def decode_report(stdout, exit_code, redactor):
    """Reject ambiguity/incomplete schemas. Hash original failure before secret redaction."""
    lines = stdout.splitlines()
    frames = [line[len(PREFIX):] for line in lines if line.startswith(PREFIX)]
    if len(frames) != 1 or not lines or lines[-1] != PREFIX + frames[0]:
        return None
    try:
        if len(frames[0].encode()) > 32768:
            return None
        report = json.loads(frames[0])
        if (set(report) != {'schema', 'complete', 'exit_code', 'tests', 'collection_errors'}
                or report['schema'] != 1 or type(report['complete']) is not bool
                or type(report['exit_code']) is not int or report['exit_code'] != exit_code
                or not isinstance(report['tests'], list) or len(report['tests']) > 256
                or not isinstance(report['collection_errors'], list)
                or len(report['collection_errors']) > 16):
            return None
        cleaned = []
        seen = set()
        for item in report['tests']:
            if set(item) != {'node_id', 'phase', 'outcome', 'assertion', 'message', 'traceback'}:
                return None
            node, phase, outcome = item['node_id'], item['phase'], item['outcome']
            if (not isinstance(node, str) or not 1 <= len(node) <= 512 or '::' not in node
                    or any(ord(char) < 32 for char in node)
                    or phase not in ('setup', 'call', 'teardown')
                    or outcome not in ('passed', 'failed', 'skipped')
                    or type(item['assertion']) is not bool or (node, phase) in seen):
                return None
            safe_path(node.split('::')[0])
            if not node.split('::')[0].endswith('.py'):
                return None
            if item['assertion'] and not (phase == 'call' and outcome == 'failed'):
                return None
            if any(not isinstance(item[key], str) or len(item[key]) > cap
                   for key, cap in (('message', 1024), ('traceback', 4096))):
                return None
            seen.add((node, phase))
            signature = hashlib.sha256(canonical(item)).hexdigest() if item['assertion'] else None
            cleaned_item = {key: output_text(value.encode(), redactor, False) if isinstance(value, str)
                            else value for key, value in item.items()}
            # Equality operands are observations, not a general expected/actual oracle.
            cleaned_item.update(signature=signature,
                                comparison=comparison(cleaned_item['message'], cleaned_item['traceback']))
            cleaned.append(cleaned_item)
        errors = report['collection_errors']
        if any(not isinstance(value, str) or len(value) > 1024 for value in errors):
            return None
        return {**report, 'tests': cleaned,
                'collection_errors': [output_text(value.encode(), redactor, False) for value in errors]}
    except (ValueError, TypeError, KeyError, SourceError):
        return None


def classify(result):
    """Assertion failures alone can become candidates. No report means inconclusive."""
    from worker.runner_models import Outcome

    special = {Outcome.BLOCKED: 'blocked', Outcome.CANCELLED: 'cancelled',
               Outcome.TIMEOUT: 'timeout', Outcome.OOM: 'oom', Outcome.OUTPUT_LIMIT: 'output_limit',
               Outcome.INFRASTRUCTURE: 'runner_failure'}
    if result.outcome in special:
        return special[result.outcome], []
    if not result.cleanup_complete:
        return 'runner_failure', []
    report = result.test_report
    if report is None:
        return ('environment_error' if result.outcome == Outcome.TEST_ENVIRONMENT_ERROR
                else 'inconclusive'), []
    errors = report['collection_errors']
    failed = [test for test in report['tests'] if test['outcome'] == 'failed']
    text = '\n'.join(errors + [test['traceback'] for test in failed])
    if re.search(r'ModuleNotFoundError|ImportError: No module named', text):
        return 'missing_dependencies', []
    if errors:
        return 'collection_error', []
    if result.exit_code == 2:
        return 'environment_error', []
    if not report['complete']:
        return 'inconclusive', []
    tests = report['tests']
    if not tests or not any(item['phase'] == 'call' and item['outcome'] in ('passed', 'failed') for item in tests):
        return 'inconclusive', []
    for node in {item['node_id'] for item in tests}:
        phases = {item['phase']: item['outcome'] for item in tests if item['node_id'] == node}
        if phases.get('setup') == 'skipped' and phases.get('teardown') == 'passed' and 'call' not in phases:
            continue
        if phases.get('teardown') != 'passed' or phases.get('setup') != 'passed':
            return 'environment_error', []
        if 'call' not in phases:
            return 'inconclusive', []
    if result.exit_code == 0 and result.outcome == Outcome.PASSED and not failed:
        return 'no_reproducible_bug', []
    if (result.exit_code == 1 and result.outcome == Outcome.TEST_FAILURE and failed
            and all(item['phase'] == 'call' and item['assertion'] for item in failed)):
        return 'assertion_failure', failed
    return 'environment_error', []
