"""Killable bounded provider transport. Secrets exist only in controller/child memory."""

import json
import os
import sys
import time

from worker.docker_client import Capture, DockerFault
from worker.provider_observations import decode
from worker.repair_models import RepairError
from worker.workspaces import canonical


class RepairProvider:
    mode = 'offline'

    def __init__(self, settings, capture_factory=Capture):
        self.settings, self.capture_factory = settings, capture_factory

    def generate(self, request, seconds, heartbeat):
        settings = self.settings
        self.observation = {}
        if self.mode == 'gemini' and not (settings.enable_live_gemini and settings.gemini_model
                                         and settings.gemini_api_key and settings.auth_token):
            raise RepairError('live_not_enabled')
        # Start before spawning: startup/imports, response handling and IPC share this bound.
        started = time.monotonic()
        deadline = started + seconds
        payload = {'mode': self.mode, 'request': request, 'seconds': seconds,
                   'deadline_monotonic': deadline,
                   'http_timeout_seconds': settings.repair_http_timeout_seconds,
                   'output_bytes': settings.repair_output_bytes,
                   'output_tokens': settings.repair_output_tokens}
        if self.mode == 'gemini':
            payload.update(model=settings.gemini_model, api_key=settings.gemini_api_key.get_secret_value())
        # Ambient API keys, endpoint overrides, proxies and Google credentials are omitted.
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP') if key in os.environ}
        capture = None
        try:
            capture = self.capture_factory([sys.executable, '-I', '-m', 'worker.model_call'], env,
                                           settings.repair_output_bytes, canonical(payload))
            if time.monotonic() >= deadline:
                raise RepairError('provider_timeout')
            while capture.poll() is None:
                heartbeat()
                if time.monotonic() >= deadline:
                    raise RepairError('provider_timeout')
                if capture.overflow.is_set():
                    raise RepairError('provider_output_limit')
                time.sleep(0.02)
            code = capture.finish(2)
            heartbeat()
            if time.monotonic() >= deadline:
                raise RepairError('provider_timeout')
            if capture.overflow.is_set():
                raise RepairError('provider_output_limit')
            observation, valid = decode(bytes(capture.stderr))
            if observation.get('sdk_timeout') or observation.get('call_deadline_expired'):
                raise RepairError('provider_timeout')
            if code or not valid:
                raise RepairError('provider_unavailable')
            return bytes(capture.stdout).decode('utf8')
        except (OSError, DockerFault, UnicodeError):
            raise RepairError('provider_unavailable') from None
        finally:
            if capture is not None:
                capture.stop()
                try:
                    capture.finish(2)
                except DockerFault:
                    pass
                self.observation, _ = decode(bytes(capture.stderr))
                self.observation['elapsed_milliseconds'] = max(0, int((time.monotonic() - started) * 1000))
                if self.observation.get('call_deadline_expired'):
                    self.observation['timeout_origin'] = 'remaining_deadline'
                elif self.observation.get('sdk_timeout'):
                    self.observation['timeout_origin'] = 'sdk'
                elif time.monotonic() >= deadline:
                    self.observation['timeout_origin'] = 'controller'


class FakeRepairProvider(RepairProvider):
    """Deterministic demo-only fake, run through the same bounded process transport."""


class GeminiRepairProvider(RepairProvider):
    mode = 'gemini'


def configured_provider(settings):
    return GeminiRepairProvider(settings) if settings.enable_live_gemini else FakeRepairProvider(settings)


def fake_proposal(request):
    old = 'return items[start:start + page_size - 1]'
    if not any(item['path'] == 'pagination.py' and old in item['text'] for item in request['source']):
        raise RepairError('fake_not_applicable')
    return json.dumps({'diagnosis': 'The exclusive slice endpoint removes one requested item.',
                       'edits': [{'path': 'pagination.py', 'old_text': old,
                                  'new_text': 'return items[start:start + page_size]'}]})
