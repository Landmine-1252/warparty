from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    public_base_url: str
    database_path: Path
    data_dir: Path
    max_players_per_party: int
    image_ttl_minutes: int
    max_upload_bytes: int
    secret_key: str
    environment: str


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@lru_cache
def get_settings() -> Settings:
    data_dir = Path(os.getenv("WARPARTY_DATA_DIR", "/app/App_Data"))
    database_path = Path(os.getenv("WARPARTY_DATABASE_PATH", str(data_dir / "warparty.db")))
    environment = os.getenv("WARPARTY_ENV", "development").lower()
    secret_key = os.getenv("WARPARTY_SECRET_KEY")
    if not secret_key:
        if environment in {"production", "prod"}:
            raise RuntimeError("WARPARTY_SECRET_KEY is required in production.")
        secret_key = secrets.token_urlsafe(32)
        warnings.warn(
            "WARPARTY_SECRET_KEY is not set. Generated a temporary development key.",
            RuntimeWarning,
            stacklevel=2,
        )

    return Settings(
        public_base_url=os.getenv("WARPARTY_PUBLIC_BASE_URL", "http://localhost:8080"),
        database_path=database_path,
        data_dir=data_dir,
        max_players_per_party=_int_env("WARPARTY_MAX_PLAYERS_PER_PARTY", 4),
        image_ttl_minutes=_int_env("WARPARTY_IMAGE_TTL_MINUTES", 60),
        max_upload_bytes=_int_env("WARPARTY_MAX_UPLOAD_BYTES", 10_485_760),
        secret_key=secret_key,
        environment=environment,
    )
