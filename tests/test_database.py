from __future__ import annotations

import sqlite3

import pytest

from app.database import _ensure_writable_database_file, configure_sqlite_connection


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
