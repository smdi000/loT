from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import Base
from app.config import get_settings
import app.models  # noqa: F401


@pytest.fixture(autouse=True)
def test_jwt_secret(monkeypatch: pytest.MonkeyPatch):
    """Keep tests independent from a developer's real backend/.env secrets."""

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-not-for-runtime")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session() -> Session:
    # TestClient serves routes from a worker thread. StaticPool makes the in-memory
    # SQLite database the same connection in both the test and API threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
