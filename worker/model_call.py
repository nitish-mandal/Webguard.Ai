"""Trusted provider child entrypoint; never imports or runs target code."""

import json
import sys
import time

import httpx

from worker.provider_observations import emit
from worker.repair_models import INSTRUCTION, RepairProposal
from worker.repair_providers import fake_proposal


def request_timeout_ms(payload):
    # Leave response/IPC cleanup time inside the hard outer wall clock. Absolute
    # monotonic clocks are shared by controller and child on supported Python.
    remaining = min(payload['seconds'], payload.get('deadline_monotonic', float('inf')) - time.monotonic())
    if remaining <= 0.05:
        emit('call_deadline_expired')
        raise TimeoutError('Provider call deadline exhausted')
    return max(1, int(min(payload.get('http_timeout_seconds', 15), remaining * 0.8) * 1000))


def gemini_generate(payload, client_factory=None):
    from google import genai
    from google.genai import types

    factory = client_factory or genai.Client
    # No SDK retries/tools/automatic function calling. Controller accounts every retry.
    def request_prepared(_request):
        # This is local dispatch preparation, NOT proof of remote receipt.
        emit('http_request_prepared')

    def response_received(response):
        emit('http_response_received', response.status_code)

    options = types.HttpOptions(timeout=request_timeout_ms(payload),
                                retry_options=types.HttpRetryOptions(attempts=1),
                                client_args={'trust_env': False, 'event_hooks': {
                                    'request': [request_prepared], 'response': [response_received]}})
    with factory(api_key=payload['api_key'], vertexai=False, http_options=options) as client:
        # Recompute after imports/client construction, not from an old full allowance.
        call_options = types.HttpOptions(timeout=request_timeout_ms(payload),
                                        retry_options=types.HttpRetryOptions(attempts=1))
        emit('sdk_invoked')
        response = client.models.generate_content(
            model=payload['model'], contents=json.dumps(payload['request'], ensure_ascii=True),
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCTION, response_mime_type='application/json',
                response_json_schema=RepairProposal.model_json_schema(),
                max_output_tokens=payload['output_tokens'], temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                http_options=call_options,
            ),
        )
        emit('response_ready')
        return response.text or ''


def main():
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072:
            return 1
        payload = json.loads(raw)
        if payload['mode'] == 'gemini':
            emit('child_started')
        output = fake_proposal(payload['request']) if payload['mode'] == 'offline' else gemini_generate(payload)
        if len(output.encode()) > payload['output_bytes']:
            return 1
        sys.stdout.buffer.write(output.encode())
        return 0
    except (httpx.TimeoutException, TimeoutError):
        emit('sdk_timeout')
        return 1
    except Exception:  # noqa: BLE001 - raw SDK errors may contain credentials or response text.
        emit('sdk_error')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
