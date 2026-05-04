from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    public_base_url: str
    database_path: Path
    data_dir: Path
    secret_key: str
    environment: str
    cookie_secure: bool
    log_level: str
    port: int
    sqlite_busy_timeout_ms: int
    sqlite_wal: bool
    stale_player_minutes: int


def _raw_env(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw


def _int_env(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    raw = _raw_env(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if min_value is not None and value < min_value:
        raise RuntimeError(f"{name} must be greater than or equal to {min_value}.")
    if max_value is not None and value > max_value:
        raise RuntimeError(f"{name} must be less than or equal to {max_value}.")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = _raw_env(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _public_base_url() -> str:
    public_base_url = _raw_env(
        "WARPARTY_PUBLIC_BASE_URL",
        _raw_env("Warparty__PublicBaseUrl", "http://localhost:8080"),
    )
    assert public_base_url is not None
    public_base_url = public_base_url.rstrip("/")
    parsed = urlparse(public_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("WARPARTY_PUBLIC_BASE_URL must be an absolute http(s) URL.")
    return public_base_url


def _log_level() -> str:
    value = _raw_env("WARPARTY_LOG_LEVEL", "info")
    assert value is not None
    normalized = value.lower()
    if normalized not in {"critical", "error", "warning", "info", "debug", "trace"}:
        raise RuntimeError(
            "WARPARTY_LOG_LEVEL must be critical, error, warning, info, debug, or trace."
        )
    return normalized


def _load_or_create_secret_key(secret_key_file: Path) -> str:
    try:
        secret_key_file.parent.mkdir(parents=True, exist_ok=True)
        if secret_key_file.exists():
            secret_key = secret_key_file.read_text(encoding="utf-8").strip()
        else:
            secret_key = secrets.token_urlsafe(32)
            secret_key_file.write_text(f"{secret_key}\n", encoding="utf-8")
            secret_key_file.chmod(0o600)
    except OSError as exc:
        raise RuntimeError(
            "Warparty could not create or read its persistent secret key at "
            f"'{secret_key_file}'. Check that the runtime data directory is writable."
        ) from exc

    if len(secret_key) < 16:
        raise RuntimeError(
            f"Secret key file '{secret_key_file}' must contain at least 16 characters."
        )
    return secret_key


@lru_cache
def get_settings() -> Settings:
    environment = _raw_env("WARPARTY_ENV", "development")
    assert environment is not None
    environment = environment.lower()
    if environment not in {"development", "production", "prod", "test"}:
        raise RuntimeError("WARPARTY_ENV must be development, production, prod, or test.")

    default_data_dir = (
        Path("./data").resolve() if environment in {"development", "test"} else Path("/data")
    )
    data_dir = default_data_dir
    database_path = data_dir / "warparty.db"
    secret_key_file = data_dir / "secret_key"
    public_base_url = _public_base_url()
    secret_key = _load_or_create_secret_key(secret_key_file)

    return Settings(
        public_base_url=public_base_url,
        database_path=database_path,
        data_dir=data_dir,
        secret_key=secret_key,
        environment=environment,
        cookie_secure=_bool_env("WARPARTY_COOKIE_SECURE", public_base_url.startswith("https://")),
        log_level=_log_level(),
        port=_int_env("WARPARTY_PORT", 8080, min_value=1, max_value=65535),
        sqlite_busy_timeout_ms=_int_env("WARPARTY_SQLITE_BUSY_TIMEOUT_MS", 5000, min_value=100),
        sqlite_wal=_bool_env("WARPARTY_SQLITE_WAL", True),
        stale_player_minutes=_int_env("WARPARTY_STALE_PLAYER_MINUTES", 60, min_value=1),
    )
