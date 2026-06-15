"""
Tests for Plan 004: Verification Baseline

Verifies that the shared test fixtures in conftest.py work correctly.
"""

import os
import pytest
from pathlib import Path


def test_db_session_fixture(db_session):
    """db_session fixture must provide a live SQLAlchemy session."""
    assert db_session is not None
    # Should be able to execute a simple raw SQL query on SQLite
    from sqlalchemy import text
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_mock_redis_fixture(mock_redis):
    """mock_redis fixture must return None for get() calls."""
    assert mock_redis.get("any-key") is None
    assert mock_redis.setex("key", 60, "value") is True
    assert mock_redis.delete("key") is True


@pytest.mark.integration
def test_test_client_fixture(test_client):
    """test_client fixture must return a working FastAPI client (requires DB)."""
    response = test_client.get("/")
    # Root may redirect (307) or return health check (200)
    assert response.status_code in (200, 307)


def test_mock_openai_fixture(mock_openai):
    """mock_openai fixture must return a plausible OpenAI response."""
    response = mock_openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert response.choices[0].message.content == "Test response"
    assert response.choices[0].message.tool_calls is None
    assert response.usage.total_tokens == 100


def test_pytest_ini_has_required_config():
    """pytest.ini must have the minimum required configuration keys."""
    ini_path = Path(__file__).parent.parent / 'pytest.ini'
    content = ini_path.read_text(encoding='utf-8')
    for key in ('testpaths', 'markers', 'addopts', 'timeout'):
        assert key in content, f"pytest.ini is missing required key: {key}"


def test_slow_marker_registered():
    """The 'slow' marker must be registered in pytest.ini."""
    ini_path = Path(__file__).parent.parent / 'pytest.ini'
    content = ini_path.read_text(encoding='utf-8')
    assert 'slow' in content


def test_integration_marker_registered():
    """The 'integration' marker must be registered in pytest.ini."""
    ini_path = Path(__file__).parent.parent / 'pytest.ini'
    content = ini_path.read_text(encoding='utf-8')
    assert 'integration' in content


def test_conftest_sets_test_env_vars():
    """conftest.py must set JWT_SECRET_KEY for downstream tests."""
    assert os.environ.get("JWT_SECRET_KEY") is not None
    assert os.environ.get("DATABASE_URL") is not None
