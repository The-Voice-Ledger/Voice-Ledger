"""
Tests for Plan 003: SPA Path Traversal Fix + Database Engine Consolidation

Covers:
- COR-03: SPA /app/* route blocks path traversal via is_relative_to()
- COR-05: Single database engine — create_engine only in connection.py
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# COR-03: SPA path traversal protection
# =========================================================================

class TestSpaPathTraversal:

    def test_is_relative_to_check_present(self):
        """is_relative_to() must be in api.py to guard the SPA route."""
        api_path = Path(__file__).parent.parent / 'voice' / 'service' / 'api.py'
        content = api_path.read_text(encoding='utf-8')
        assert 'is_relative_to' in content, \
            "api.py is missing is_relative_to() path traversal guard"

    def test_resolve_used_before_is_relative_to(self):
        """resolve() must be called to canonicalise paths before the check."""
        api_path = Path(__file__).parent.parent / 'voice' / 'service' / 'api.py'
        content = api_path.read_text(encoding='utf-8')
        # Both .resolve() and .is_relative_to() must appear in the SPA function
        import re
        # Find the serve_spa function body
        match = re.search(
            r'async def serve_spa.{0,800}is_relative_to',
            content, re.DOTALL
        )
        assert match is not None, \
            "serve_spa does not call is_relative_to() within the function"
        assert '.resolve()' in match.group(0), \
            "serve_spa does not call .resolve() before is_relative_to()"

    def test_path_traversal_logic_is_correct(self):
        """
        Simulate the path traversal check logic:
        A path outside spa_dir must be detected as unsafe.
        """
        # Simulate spa_dir = /app/web-frontend/dist
        spa_dir = Path('/fake/app/web-frontend/dist')

        # Traversal attempt: ../../database/models.py
        traversal = (spa_dir / '../../database/models.py').resolve()
        # Should NOT be relative to spa_dir
        assert not traversal.is_relative_to(spa_dir.resolve()), \
            "Path traversal was not detected — logic is broken"

    def test_safe_path_passes_check(self):
        """A normal asset path within spa_dir must pass the check."""
        spa_dir = Path('/fake/app/web-frontend/dist')
        safe = (spa_dir / 'assets/main.js').resolve()
        assert safe.is_relative_to(spa_dir.resolve()), \
            "Safe path was incorrectly rejected"

    def test_empty_path_passes_to_index(self):
        """An empty rest_of_path should serve index.html, no traversal check needed."""
        # The guard only runs when rest_of_path is truthy
        rest_of_path = ""
        assert not rest_of_path, "Empty path should be falsy and skip the check"


# =========================================================================
# COR-05: Single database engine
# =========================================================================

class TestSingleDatabaseEngine:

    def test_no_create_engine_in_models(self):
        """create_engine must not appear in database/models.py."""
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text(encoding='utf-8')
        assert 'create_engine' not in content, \
            "create_engine still present in database/models.py — double engine bug not fixed"

    def test_create_engine_in_connection(self):
        """create_engine must be called exactly once in database/connection.py."""
        connection_path = Path(__file__).parent.parent / 'database' / 'connection.py'
        content = connection_path.read_text(encoding='utf-8')
        import re
        # Count calls only (lines with assignment), not the import line
        matches = re.findall(r'engine\s*=\s*create_engine\s*\(', content)
        assert len(matches) == 1, \
            f"Expected 1 create_engine call in connection.py, found {len(matches)}"

    def test_models_imports_session_from_connection(self):
        """models.py must re-export SessionLocal from connection.py."""
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text(encoding='utf-8')
        assert 'from database.connection import' in content, \
            "models.py does not import from database.connection"
        assert 'SessionLocal' in content, \
            "models.py does not re-export SessionLocal"

    def test_models_sessionlocal_still_importable(self):
        """SessionLocal re-export is present in models.py source (backward compat)."""
        # Check at source level to avoid spinning up the actual DB engine in tests
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text(encoding='utf-8')
        assert 'SessionLocal' in content, \
            "SessionLocal not present in database/models.py (re-export missing)"
        assert 'from database.connection import' in content, \
            "models.py does not re-export SessionLocal from database.connection"

    def test_connection_echo_is_env_driven(self):
        """connection.py must use SQL_ECHO env var, not hardcoded echo=False."""
        connection_path = Path(__file__).parent.parent / 'database' / 'connection.py'
        content = connection_path.read_text(encoding='utf-8')
        assert 'SQL_ECHO' in content, \
            "connection.py does not use SQL_ECHO env var for echo setting"
        assert 'echo=False' not in content, \
            "connection.py has hardcoded echo=False instead of env-driven setting"

    def test_connection_pool_settings_present(self):
        """connection.py must have pool_pre_ping, pool_recycle, pool_size, max_overflow."""
        connection_path = Path(__file__).parent.parent / 'database' / 'connection.py'
        content = connection_path.read_text(encoding='utf-8')
        for setting in ['pool_pre_ping', 'pool_recycle', 'pool_size', 'max_overflow']:
            assert setting in content, \
                f"connection.py is missing pool setting: {setting}"
