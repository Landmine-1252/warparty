from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import copy_file_if_target_missing, get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
database_url = f"sqlite:///{settings.database_path}"
engine = create_engine(
    database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": settings.sqlite_busy_timeout_ms / 1000,
    },
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def configure_sqlite_connection(dbapi_connection: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        if settings.sqlite_wal:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


@event.listens_for(engine, "connect")
def _on_sqlite_connect(dbapi_connection: Any, _: Any) -> None:
    configure_sqlite_connection(dbapi_connection)


def _ensure_writable_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path = path / ".warparty-write-test"
        probe_path.touch(exist_ok=True)
        probe_path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            "Warparty cannot write to its runtime data directory "
            f"'{path}'. Check the Docker/Podman volume mount permissions, "
            "or set WARPARTY_DATA_DIR and WARPARTY_DATABASE_PATH to a writable path."
        ) from exc


def _ensure_writable_database_file(path: Path) -> None:
    try:
        with path.open("a+b"):
            pass
    except OSError as exc:
        raise RuntimeError(
            "Warparty cannot write to its SQLite database file "
            f"'{path}'. Check ownership and permissions for the mounted "
            "Docker/Podman volume, or set WARPARTY_DATABASE_PATH to a writable file."
        ) from exc


def migrate_legacy_database_if_needed(
    *,
    database_path: Path,
    legacy_database_path: Path,
    enabled: bool,
) -> bool:
    if not enabled:
        return False
    copied = copy_file_if_target_missing(legacy_database_path, database_path)
    if not copied:
        return False

    for suffix in ("-wal", "-shm"):
        copy_file_if_target_missing(
            Path(f"{legacy_database_path}{suffix}"),
            Path(f"{database_path}{suffix}"),
        )
    return True


def init_db() -> None:
    import app.models  # noqa: F401

    _ensure_writable_directory(settings.data_dir)
    _ensure_writable_directory(settings.database_path.parent)
    migrate_legacy_database_if_needed(
        database_path=settings.database_path,
        legacy_database_path=settings.legacy_data_dir / "warparty.db",
        enabled=settings.auto_migrate_legacy_data,
    )
    _ensure_writable_database_file(settings.database_path)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
