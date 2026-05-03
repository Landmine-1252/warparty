from __future__ import annotations

import sqlite3

import pytest

from app.database import (
    _ensure_writable_database_file,
    configure_sqlite_connection,
    migrate_legacy_database_if_needed,
)


def test_sqlite_connection_pragmas_are_applied(tmp_path) -> None:
    database_path = tmp_path / "warparty.db"
    connection = sqlite3.connect(database_path)
    try:
        configure_sqlite_connection(connection)

        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] >= 100
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        connection.close()


def test_database_file_writability_failure_is_clear(tmp_path) -> None:
    missing_parent_path = tmp_path / "missing" / "warparty.db"

    with pytest.raises(RuntimeError, match="SQLite database file"):
        _ensure_writable_database_file(missing_parent_path)


def test_legacy_database_is_copied_without_overwriting_existing_target(tmp_path) -> None:
    legacy_database_path = tmp_path / "legacy" / "warparty.db"
    database_path = tmp_path / "data" / "warparty.db"
    legacy_database_path.parent.mkdir()
    legacy_database_path.write_bytes(b"legacy-db")
    legacy_wal_path = tmp_path / "legacy" / "warparty.db-wal"
    legacy_wal_path.write_bytes(b"legacy-wal")

    copied = migrate_legacy_database_if_needed(
        database_path=database_path,
        legacy_database_path=legacy_database_path,
        enabled=True,
    )

    assert copied is True
    assert database_path.read_bytes() == b"legacy-db"
    assert (tmp_path / "data" / "warparty.db-wal").read_bytes() == b"legacy-wal"

    database_path.write_bytes(b"current-db")
    copied = migrate_legacy_database_if_needed(
        database_path=database_path,
        legacy_database_path=legacy_database_path,
        enabled=True,
    )

    assert copied is False
    assert database_path.read_bytes() == b"current-db"
