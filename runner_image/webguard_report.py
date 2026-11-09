"""Image-owned pytest reporter. Report text remains untrusted repository data."""

import json
from pathlib import Path

import pytest

# Reporting must survive a target filling its working scratch allocation.
# /tmp is a separate size-bounded tmpfs, never a host mount.
REPORT = Path('/tmp/webguard-test-report.json')
MAX_BYTES = 32768
_tests = []
_errors = []
_complete = True


def pytest_sessionstart(session):
    global _complete
    _tests.clear()
    _errors.clear()
    _complete = True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    global _complete
    result = yield
    report = result.get_result()
    if len(_tests) >= 256:
        _complete = False
        return
    # Explicit config lives outside source; normalize IDs to the copied source,
    # rather than pytest's config-root-relative fallback (which can omit tests/).
    if item.path.is_relative_to('/opt/webguard/regressions'):
        relative = '_webguard_regression/' + item.path.relative_to('/opt/webguard/regressions').as_posix()
    else:
        relative = item.path.relative_to('/scratch/work').as_posix()
    node_id = relative + '::' + report.nodeid.split('::', 1)[1]
    assertion = bool(report.failed and call.when == 'call' and call.excinfo
                     and issubclass(call.excinfo.type, AssertionError))
    trace = report.longreprtext if report.failed else ''
    message = str(getattr(getattr(report.longrepr, 'reprcrash', None), 'message', ''))
    if len(trace) > 4096 or len(message) > 1024 or len(node_id) > 512:
        _complete = False
    _tests.append({'node_id': node_id[:512], 'phase': report.when,
                   'outcome': report.outcome, 'assertion': assertion,
                   'message': message[:1024], 'traceback': trace[:4096]})


def pytest_collectreport(report):
    global _complete
    if report.failed:
        if len(_errors) < 16:
            _errors.append(str(report.longrepr)[:1024])
        _complete = False


def pytest_sessionfinish(session, exitstatus):
    document = {'schema': 1, 'complete': _complete, 'exit_code': int(exitstatus),
                'tests': _tests, 'collection_errors': _errors}
    data = json.dumps(document, ensure_ascii=True, separators=(',', ':')).encode()
    if len(data) > MAX_BYTES:
        data = json.dumps({'schema': 1, 'complete': False, 'exit_code': int(exitstatus),
                           'tests': [], 'collection_errors': []}).encode()
    REPORT.write_bytes(data)
