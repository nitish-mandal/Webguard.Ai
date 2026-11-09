"""Closed, bounded provider telemetry vocabulary. Never accept exception messages."""

import json
import sys

PREFIX = 'WEBGUARD_PROVIDER_EVENT '
STAGES = frozenset({'child_started', 'sdk_invoked', 'http_request_prepared',
                    'http_response_received', 'sdk_timeout', 'sdk_error',
                    'response_ready', 'call_deadline_expired'})


def emit(stage, status=None):
    if stage not in STAGES:
        raise ValueError('Unknown provider stage')
    data = {'stage': stage}
    if status is not None and type(status) is int and 100 <= status <= 599:
        data['status'] = status
    sys.stderr.write(PREFIX + json.dumps(data, separators=(',', ':')) + '\n')
    sys.stderr.flush()


def decode(raw):
    """Return only fixed booleans/status. Unknown stderr remains a transport failure."""
    result = {}
    valid = len(raw) <= 4096
    lines = raw.splitlines()
    if len(lines) > 16:
        return {}, False
    for line in lines:
        try:
            text = line.decode('utf8')
            if not text.startswith(PREFIX):
                valid = False
                continue
            data = json.loads(text[len(PREFIX):])
            if (not isinstance(data, dict) or set(data) - {'stage', 'status'}
                    or data.get('stage') not in STAGES):
                valid = False
                continue
            status = data.get('status')
            if status is not None and (type(status) is not int or not 100 <= status <= 599):
                valid = False
                continue
            result[data['stage']] = True
            if status is not None:
                result['http_status'] = status
        except (UnicodeError, ValueError, TypeError):
            valid = False
    return result, valid
