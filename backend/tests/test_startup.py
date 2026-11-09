import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import SettingsError


def test_startup_loads_dotenv_migrates_and_requires_configured_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Isolate configuration from unrelated operator environment values.
    from backend.app.settings import Settings

    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    (tmp_path / ".env").write_text(
        "ALLOWED_REPOSITORY=owner/repo\nDATABASE_URL=sqlite:///state.sqlite\n",
        encoding="utf8",
    )
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        assert app.state.jobs.settings.allowed_repository == "owner/repo"
        assert (tmp_path / "state.sqlite").exists()
        assert client.get("/health").json() == {"status": "ok"}
        assert client.post("/api/jobs", json={"repository": "owner/repo"}).status_code == 503
        assert app.state.jobs.list_jobs() == []
        assert client.get("/api/status").json()["repair_enabled"] is False


def test_startup_rejects_invalid_settings_safely(tmp_path, monkeypatch):
    from backend.app.settings import Settings

    monkeypatch.chdir(tmp_path)
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    secret = "private-credential-in-invalid-url"
    (tmp_path / ".env").write_text(f"DATABASE_URL=https://user:{secret}@host/db", encoding="utf8")
    with pytest.raises(SettingsError) as error, TestClient(app):
        pass
    assert secret not in str(error.value)
    assert not (tmp_path / "data").exists()
