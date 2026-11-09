"""Mocked deadline/diagnostic tests. No real Gemini, target or GitHub execution."""

import io
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.app.domain import JobState
from backend.app.settings import Settings, SettingsError, load_settings
from worker import model_call
from worker.provider_observations import PREFIX, decode
from worker.repair import RepairService
from worker.repair_models import RepairError
from worker.repair_providers import FakeRepairProvider
from worker.tests.test_repair import access, fixture_git, reproduced

__all__ = ['access', 'fixture_git', 'reproduced']


def payload(**updates):
    return {'api_key': 'test-private-key-never-log', 'model': 'gemini-3.8-flash',
            'seconds': 90, 'http_timeout_seconds': 60, 'output_tokens': 2048,
            'request': {'untrusted_repository_data': True}, **updates}


def test_settings_load_separate_http_cap_without_enabling_live(tmp_path):
    path = tmp_path / '.env'
    path.write_text('REPAIR_CALL_SECONDS=90\nREPAIR_HTTP_TIMEOUT_SECONDS=60\n')
    s = load_settings(path, {})
    assert s.repair_call_seconds == 90 and s.repair_http_timeout_seconds == 60
    assert not s.enable_live_gemini and not s.enable_github_draft_pr
    for invalid in ('0', '111', 'not-an-integer'):
        with pytest.raises(SettingsError):
            load_settings(path, {'REPAIR_HTTP_TIMEOUT_SECONDS': invalid})


def test_sdk_timeout_recomputed_after_client_setup_and_deadline_shrinks(monkeypatch):
    clock, observed = [100.0], {}
    monkeypatch.setattr(model_call.time, 'monotonic', lambda: clock[0])

    class Client:
        def __init__(self, **kwargs):
            observed.update(kwargs)
            self.models = self
        def __enter__(self):
            clock[0] += 7  # Imports/client setup consumed most of the 10 seconds left.
            return self
        def __exit__(self, *args): pass
        def generate_content(self, **kwargs):
            observed['call'] = kwargs
            return SimpleNamespace(text='{}')

    model_call.gemini_generate(payload(deadline_monotonic=110), Client)
    assert observed['http_options'].timeout == 8000
    config = observed['call']['config']
    assert config.http_options.timeout == 2400
    assert config.http_options.retry_options.attempts == 1


def test_expired_deadline_never_constructs_sdk_client(monkeypatch, capsys):
    monkeypatch.setattr(model_call.time, 'monotonic', lambda: 100)
    with pytest.raises(TimeoutError):
        model_call.gemini_generate(payload(deadline_monotonic=99),
                                  lambda **kwargs: pytest.fail('No SDK call allowed'))
    observation, valid = decode(capsys.readouterr().err.encode())
    assert valid and observation == {'call_deadline_expired': True}


def test_real_installed_sdk_with_mock_transport_observes_response_and_no_secret(capsys):
    from google import genai

    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.extensions['timeout']['read'] == 60
        return httpx.Response(200, json={'candidates': [{'content': {'role': 'model',
            'parts': [{'text': '{"diagnosis":"mock","edits":[]}'}]}, 'finishReason': 'STOP'}]})

    def factory(**kwargs):
        kwargs['http_options'].client_args['transport'] = httpx.MockTransport(handler)
        return genai.Client(**kwargs)

    assert 'mock' in model_call.gemini_generate(payload(), factory)
    output = capsys.readouterr()
    assert 'test-private-key' not in output.err + output.out
    observation, valid = decode(output.err.encode())
    assert len(calls) == 1 and valid
    assert observation == {'sdk_invoked': True, 'http_request_prepared': True,
                           'http_response_received': True, 'http_status': 200, 'response_ready': True}


def test_child_sdk_timeout_reports_only_safe_stage(monkeypatch, capsys):
    monkeypatch.setattr(model_call.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(
        json.dumps({'mode': 'gemini'}).encode())))
    def timeout(_):
        raise httpx.ReadTimeout('api_key=private-mock-value https://user:pass@example.test')
    monkeypatch.setattr(model_call, 'gemini_generate', timeout)
    assert model_call.main() == 1
    output = capsys.readouterr()
    observation, valid = decode(output.err.encode())
    assert valid and observation == {'child_started': True, 'sdk_timeout': True}
    assert 'private-mock-value' not in output.err and 'user:pass' not in output.err


def test_real_sdk_http_error_preserves_status_without_raw_error_or_retry(monkeypatch, capsys):
    from google import genai

    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(403, json={'error': {'code': 403, 'status': 'PERMISSION_DENIED',
            'message': 'api_key=private-mock-value https://user:pass@example.test'}})
    def factory(**kwargs):
        kwargs['http_options'].client_args['transport'] = httpx.MockTransport(handler)
        return genai.Client(**kwargs)
    generate = model_call.gemini_generate
    monkeypatch.setattr(model_call, 'gemini_generate', lambda p: generate(p, factory))
    monkeypatch.setattr(model_call.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(
        json.dumps(payload(mode='gemini')).encode())))
    assert model_call.main() == 1
    observation, valid = decode(capsys.readouterr().err.encode())
    assert len(calls) == 1 and valid
    assert observation['http_response_received'] and observation['http_status'] == 403
    assert observation['sdk_error'] and not observation.get('response_ready')


class CaptureStub:
    def __init__(self, stderr=b'', code=1):
        self.stdout, self.stderr = bytearray(), bytearray(stderr)
        self.code, self.stopped = code, False
        self.overflow = SimpleNamespace(is_set=lambda: False)
    def poll(self): return self.code
    def finish(self, _): return self.code
    def stop(self): self.stopped = True


def test_startup_time_is_inside_outer_deadline(monkeypatch):
    clock, captures = [100.0], []
    monkeypatch.setattr(model_call.time, 'monotonic', lambda: clock[0])
    def spawn(*args):
        clock[0] += 2
        child = CaptureStub(code=0)
        child.stdout.extend(b'{}')
        captures.append(child)
        return child
    provider = FakeRepairProvider(Settings(), capture_factory=spawn)
    with pytest.raises(RepairError, match='provider_timeout'):
        provider.generate({}, 1, lambda: None)
    assert captures[0].stopped and provider.observation['timeout_origin'] == 'controller'
    assert provider.observation['elapsed_milliseconds'] == 2000


def test_sdk_timeout_diagnostics_persist_with_one_call_no_retry(reproduced):
    access_, lease = reproduced
    access_.jobs.settings = access_.jobs.settings.model_copy(update={'repair_max_retries': 0})
    spawned = []
    def spawn(*args):
        child = CaptureStub((PREFIX + '{"stage":"sdk_invoked"}\n' +
                             PREFIX + '{"stage":"sdk_timeout"}\n').encode())
        spawned.append(child)
        return child
    provider = FakeRepairProvider(access_.jobs.settings, capture_factory=spawn)
    with pytest.raises(RepairError, match='provider_timeout'):
        RepairService(access_, provider).propose(lease)
    assert len(spawned) == 1 and spawned[0].stopped
    assert access_.jobs.get(lease.job_id)['model_calls'] == 1
    event = next(e for e in access_.jobs.events(lease.job_id) if e['kind'] == 'repair_rejected')
    assert event['data']['provider_observation']['sdk_invoked']
    assert event['data']['provider_observation']['timeout_origin'] == 'sdk'
    assert 'http_response_received' not in event['data']['provider_observation']


@pytest.mark.parametrize('raw', [b'api_key=private-mock-value',
    (PREFIX + '{"stage":"sdk_error","message":"private-mock-value"}').encode(),
    (PREFIX + '{"stage":"http_response_received","status":"private-mock-value"}').encode()])
def test_diagnostics_never_accept_untrusted_text(raw):
    observation, valid = decode(raw)
    assert not valid and observation == {}


def test_persisted_observation_has_closed_schema(reproduced):
    access_, lease = reproduced
    access_.jobs.advance(lease, JobState.REPAIRING)
    access_.jobs.repair_observation(lease, 'provider_unavailable', observation={
        'sdk_invoked': True, 'http_status': 403, 'elapsed_milliseconds': 20,
        'raw_error': 'private-mock-value', 'api_key': 'private-mock-value',
        'timeout_origin': 'private-mock-value', 'http_response_received': 'private-mock-value'})
    event = next(e for e in access_.jobs.events(lease.job_id) if e['kind'] == 'repair_rejected')
    assert event['data']['provider_observation'] == {
        'sdk_invoked': True, 'http_status': 403, 'elapsed_milliseconds': 20}
    assert 'private-mock-value' not in json.dumps(event)
