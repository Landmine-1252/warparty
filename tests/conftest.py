from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import Base, configure_sqlite_connection


@pytest.fixture
def test_sessionmaker(tmp_path) -> Generator[sessionmaker[Session], None, None]:
    database_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    event.listen(engine, "connect", lambda connection, _: configure_sqlite_connection(connection))
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_sessionmaker) -> Generator[Session, None, None]:
    with test_sessionmaker() as session:
        yield session


__all__ = ["models"]
