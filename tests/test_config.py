from __future__ import annotations

import pytest
from starlette.responses import Response

from app.config import get_settings
from app.security import set_session_cookie


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_secret_key_creates_persistent_secret_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WARPARTY_ENV", "test")
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")

    settings = get_settings()
    first_secret = settings.secret_key

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.secret_key == first_secret
    assert settings.data_dir == tmp_path / "data"
    assert settings.database_path == tmp_path / "data" / "warparty.db"
    assert (tmp_path / "data" / "secret_key").exists()
    assert settings.cookie_secure is True


def test_missing_secret_key_reuses_existing_secret_file(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    current_secret = "current-secret-key-value"
    (data_dir / "secret_key").write_text(f"{current_secret}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WARPARTY_ENV", "test")
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")

    settings = get_settings()

    assert settings.secret_key == current_secret
    assert (tmp_path / "data" / "secret_key").read_text(encoding="utf-8").strip() == current_secret


def test_invalid_public_base_url_fails_clearly(monkeypatch) -> None:
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "localhost:8080")

    with pytest.raises(RuntimeError, match="WARPARTY_PUBLIC_BASE_URL"):
        get_settings()


def test_invalid_integer_env_fails_clearly(monkeypatch) -> None:
    monkeypatch.setenv("WARPARTY_PORT", "many")

    with pytest.raises(RuntimeError, match="WARPARTY_PORT"):
        get_settings()


def test_dotnet_style_public_base_url_is_supported_for_existing_unraid_templates(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WARPARTY_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "test")
    monkeypatch.setenv("Warparty__PublicBaseUrl", "https://warparty.example.test")

    assert get_settings().public_base_url == "https://warparty.example.test"


def test_https_public_url_sets_secure_session_cookie(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WARPARTY_ENV", "test")
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")
    response = Response()

    set_session_cookie(response, 1, "session-token")

    assert "secure" in response.headers["set-cookie"].lower()
