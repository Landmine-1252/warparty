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
    data_dir = tmp_path / "data"
    monkeypatch.delenv("WARPARTY_SECRET_KEY", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "production")
    monkeypatch.setenv("WARPARTY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db"))
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")
    monkeypatch.setenv("WARPARTY_AUTO_MIGRATE_LEGACY_DATA", "false")

    settings = get_settings()
    first_secret = settings.secret_key

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.secret_key == first_secret
    assert settings.secret_key_file == data_dir / "secret_key"
    assert settings.secret_key_file.exists()
    assert settings.cookie_secure is True
    assert settings.allowed_hosts == ("warparty.example.test", "localhost", "127.0.0.1")


def test_missing_secret_key_reuses_legacy_secret_file(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    legacy_data_dir = tmp_path / "legacy"
    legacy_data_dir.mkdir()
    legacy_secret = "legacy-secret-key-value"
    (legacy_data_dir / "secret_key").write_text(f"{legacy_secret}\n", encoding="utf-8")
    monkeypatch.delenv("WARPARTY_SECRET_KEY", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "production")
    monkeypatch.setenv("WARPARTY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db"))
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")
    monkeypatch.setenv("WARPARTY_LEGACY_DATA_DIR", str(legacy_data_dir))

    settings = get_settings()

    assert settings.secret_key == legacy_secret
    assert settings.secret_key_file.read_text(encoding="utf-8").strip() == legacy_secret


def test_legacy_secret_does_not_overwrite_existing_secret_file(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    legacy_data_dir = tmp_path / "legacy"
    data_dir.mkdir()
    legacy_data_dir.mkdir()
    current_secret = "current-secret-key-value"
    legacy_secret = "legacy-secret-key-value"
    (data_dir / "secret_key").write_text(f"{current_secret}\n", encoding="utf-8")
    (legacy_data_dir / "secret_key").write_text(f"{legacy_secret}\n", encoding="utf-8")
    monkeypatch.delenv("WARPARTY_SECRET_KEY", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "production")
    monkeypatch.setenv("WARPARTY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db"))
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")
    monkeypatch.setenv("WARPARTY_LEGACY_DATA_DIR", str(legacy_data_dir))

    settings = get_settings()

    assert settings.secret_key == current_secret
    assert settings.secret_key_file.read_text(encoding="utf-8").strip() == current_secret


def test_invalid_public_base_url_fails_clearly(monkeypatch) -> None:
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "localhost:8080")

    with pytest.raises(RuntimeError, match="WARPARTY_PUBLIC_BASE_URL"):
        get_settings()


def test_invalid_integer_env_fails_clearly(monkeypatch) -> None:
    monkeypatch.setenv("WARPARTY_MAX_PLAYERS_PER_PARTY", "many")

    with pytest.raises(RuntimeError, match="WARPARTY_MAX_PLAYERS_PER_PARTY"):
        get_settings()


def test_dotnet_style_public_base_url_is_supported_for_existing_unraid_templates(
    monkeypatch,
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.delenv("WARPARTY_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("WARPARTY_SECRET_KEY", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "production")
    monkeypatch.setenv("WARPARTY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db"))
    monkeypatch.setenv("Warparty__PublicBaseUrl", "https://warparty.example.test")
    monkeypatch.setenv("WARPARTY_AUTO_MIGRATE_LEGACY_DATA", "false")

    assert get_settings().public_base_url == "https://warparty.example.test"


def test_https_public_url_sets_secure_session_cookie(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.delenv("WARPARTY_SECRET_KEY", raising=False)
    monkeypatch.setenv("WARPARTY_ENV", "production")
    monkeypatch.setenv("WARPARTY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db"))
    monkeypatch.setenv("WARPARTY_PUBLIC_BASE_URL", "https://warparty.example.test")
    monkeypatch.setenv("WARPARTY_AUTO_MIGRATE_LEGACY_DATA", "false")
    response = Response()

    set_session_cookie(response, 1, "session-token")

    assert "secure" in response.headers["set-cookie"].lower()
