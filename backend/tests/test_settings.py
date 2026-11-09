import json

import pytest
from pydantic import ValidationError

from backend.app.settings import Redactor, Settings, SettingsError, load_settings


def test_dotenv_precedence_and_offline_defaults(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ALLOWED_REPOSITORY=owner/repo\nMAX_REPAIR_ATTEMPTS=2\n"
                   "GEMINI_API_KEY=\nGITHUB_TOKEN=\nUNRELATED=value\n", encoding="utf8")
    settings = load_settings(env, {"MAX_REPAIR_ATTEMPTS": "4"})
    assert settings.allowed_repository == "owner/repo"
    assert settings.max_repair_attempts == 4
    assert not settings.enable_live_gemini
    assert not settings.enable_github_draft_pr
    assert settings.gemini_api_key is None
    assert not settings.authenticate(None)
    assert Settings().allowed_repository == "demo-repository"


@pytest.mark.parametrize("fields", [
    {"max_repair_attempts": 0}, {"max_patch_files": 21}, {"lease_seconds": 301},
    {"max_cost_micros_per_job": -1}, {"job_timeout_seconds": 0},
    {"database_url": "postgres://user:secret@host/db"},
    {"database_url": "sqlite:///:memory:"}, {"database_url": "sqlite://///host/db"},
    {"allowed_repository": "https://github.com/owner/repo"},
    {"allowed_repository": "Owner/Repo"}, {"allowed_repository": "../repo"},
    {"auth_token": "short"}, {"auth_token": "x" * 257},
    {"auth_token": " " * 32}, {"auth_token": "x" * 32 + "\n"},
    {"app_env": "production"},
    {"enable_live_gemini": True}, {"enable_github_draft_pr": True},
    {"source_max_files": 0}, {"source_timeout_seconds": 0},
    {"source_max_archive_bytes": 0}, {"workspace_root": "../unrelated"}, {"workspace_root": "."},
])
def test_invalid_settings(fields):
    with pytest.raises(ValidationError):
        Settings(**fields)


def test_safe_errors_no_interpolation_and_secret_representation(tmp_path):
    env = tmp_path / ".env"
    secret = "never-print-this-private-token-123456"
    env.write_text(f"AUTH_TOKEN={secret}\nGEMINI_API_KEY=${{AUTH_TOKEN}}\n", encoding="utf8")
    settings = load_settings(env, {})
    assert settings.gemini_api_key.get_secret_value() == "${AUTH_TOKEN}"
    assert secret not in repr(settings)
    assert secret not in settings.model_dump_json()
    assert secret not in repr(settings.redactor())
    assert settings.authenticate(secret)
    assert not settings.authenticate(secret + "x")
    env.write_text(f"DATABASE_URL=https://user:{secret}@host/db", encoding="utf8")
    with pytest.raises(SettingsError) as error:
        load_settings(env, {})
    assert secret not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


def test_live_flags_are_independent_and_require_local_auth():
    common = {"auth_token": "local-auth-token-long-enough-123456", "allowed_repository": "owner/repo"}
    gemini = Settings(**common, enable_live_gemini=True, gemini_api_key="private-key",
                      gemini_model="selected-model")
    assert not gemini.enable_github_draft_pr
    github = Settings(**common, enable_github_draft_pr=True, github_token="private-token")
    assert not github.enable_live_gemini
    with pytest.raises(ValidationError):
        Settings(enable_live_gemini=True, gemini_api_key="private", gemini_model="model")


def test_recursive_redaction():
    secret = "a-configured-private-value"
    redactor = Redactor((secret,))
    cleaned = redactor.clean({
        "nested": [{"message": f"failure {secret} Bearer hidden-value"}],
        "GITHUB_TOKEN": "other-secret", "credentials": {"raw": "hidden"},
        "text": "https://user:pass@github.com/a/b?token=hidden-query",
        "known_patterns": "ghp_abcdefghijklmnop AIza123456789012345678901234567890",
        "model_tokens": 200,
    })
    result = json.dumps(cleaned)
    for value in (secret, "hidden-value", "other-secret", "user:pass", "hidden-query",
                  "abcdefghijklmnop", "123456789012345678901234567890"):
        assert value not in result
    assert "[REDACTED]" in result
    assert cleaned["model_tokens"] == 200
    assert redactor.clean({"model_tokens": secret})["model_tokens"] == "[REDACTED]"


def test_unknown_environment_does_not_become_configuration(tmp_path):
    settings = load_settings(tmp_path / "absent.env", {"SOME_OTHER_SECRET": "private"})
    assert "private" not in settings.model_dump_json()


def test_stateless_installation_token_and_publication_limits():
    token = 'ghs_12345.eyJhbGciOiJIUzI1NiJ9.payload-signature'
    assert Redactor().text(token) == '[REDACTED]'
    assert Settings().publication_seconds == 30
    for field in ('publication_seconds', 'publication_request_seconds', 'publication_max_requests',
                  'publication_response_bytes', 'publication_request_bytes'):
        with pytest.raises(ValidationError):
            Settings(**{field: 0})
