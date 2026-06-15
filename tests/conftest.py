"""
Shared test fixtures for Voice Ledger test suite.

Provides:
- In-memory SQLite database session (per-test isolation)
- FastAPI TestClient with mocked dependencies
- Mocked Redis client
- Environment variable setup
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'database', 'voice', etc. are importable
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment variables before any imports.
# Uses setdefault so explicit test overrides take precedence.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-telegram-token")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-tests-only")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for the test session."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    """
    Create a fresh database session per test.

    Uses SQLite in-memory. Because the Voice Ledger schema uses PostgreSQL-specific
    types (ARRAY, JSON), we skip create_all and yield a plain session.
    Tests that need specific tables should create them explicitly or mock at a
    higher level.

    For tests that need real table creation, use a PostgreSQL test container.
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()


@pytest.fixture
def mock_redis():
    """Provide a mocked Redis client."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def test_client(db_session):
    """
    Create a FastAPI TestClient with the database dependency overridden.

    Usage:
        def test_health(test_client):
            response = test_client.get("/")
            assert response.status_code == 200
    """
    from fastapi.testclient import TestClient
    from voice.service.api import app
    from database.connection import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_openai():
    """Mock the OpenAI client for agent tests."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage.total_tokens = 100
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client
