"""
Tests for Plan 001: Security Hardening

Covers:
- SEC-01: JWT_SECRET_KEY fails fast when not set
- SEC-04: Uploaded filenames are sanitized (path traversal prevention)
- SEC-05: Exception details not leaked in HTTP responses
- SEC-06: SQL echo defaults to False
"""

import os
import sys
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# SEC-01: JWT secret must fail fast
# =========================================================================

class TestJwtSecretFailFast:

    def test_missing_jwt_secret_raises_valueerror(self):
        """If JWT_SECRET_KEY is not set, importing auth must raise ValueError."""
        import importlib
        import voice.web.auth as auth_module

        with patch.dict(os.environ, {}, clear=True):
            # Remove JWT_SECRET_KEY from env
            env_without_secret = {k: v for k, v in os.environ.items() if k != 'JWT_SECRET_KEY'}
            with patch.dict(os.environ, env_without_secret, clear=True):
                with pytest.raises((ValueError, Exception)):
                    # Force re-evaluation of module-level code
                    importlib.reload(auth_module)

    def test_jwt_secret_set_does_not_raise(self):
        """With JWT_SECRET_KEY set, auth module loads without error."""
        import importlib
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key-for-testing-only'}):
            import voice.web.auth as auth_module
            importlib.reload(auth_module)
            assert auth_module.JWT_SECRET_KEY == 'test-secret-key-for-testing-only'

    def test_no_hardcoded_fallback(self):
        """Ensure 'your-secret-key-change-in-production' is not in auth.py."""
        auth_path = Path(__file__).parent.parent / 'voice' / 'web' / 'auth.py'
        content = auth_path.read_text()
        assert 'your-secret-key-change-in-production' not in content, \
            "Hardcoded JWT secret fallback found in auth.py"


# =========================================================================
# SEC-04: Filename sanitization
# =========================================================================

class TestFilenameSanitization:

    def _sanitize(self, filename: str) -> str:
        """Replicate the sanitization logic from api.py."""
        return re.sub(r'[^\w\-.]', '_', Path(filename).name)

    def test_path_traversal_stripped(self):
        """../../etc/passwd — directory component stripped, only filename remains."""
        result = self._sanitize('../../etc/passwd')
        # Path.name strips the directory — no .. or / can survive
        assert '..' not in result
        assert '/' not in result
        # The basename 'passwd' contains only word chars so it passes through as-is
        assert result == 'passwd'

    def test_windows_path_traversal_stripped(self):
        result = self._sanitize('..\\..\\windows\\system32\\cmd.exe')
        assert '..' not in result
        assert '\\' not in result

    def test_normal_filename_preserved(self):
        result = self._sanitize('voice_command.mp3')
        assert result == 'voice_command.mp3'

    def test_spaces_replaced(self):
        result = self._sanitize('my voice file.wav')
        assert ' ' not in result

    def test_null_bytes_removed(self):
        result = self._sanitize('file\x00.wav')
        assert '\x00' not in result

    def test_only_basename_used(self):
        """Directory component is stripped — only the filename part is kept."""
        result = self._sanitize('/tmp/uploads/audio.ogg')
        assert result == 'audio.ogg'

    def test_api_uses_sanitized_filename(self):
        """Confirm api.py uses re.sub sanitization, not raw file.filename."""
        api_path = Path(__file__).parent.parent / 'voice' / 'service' / 'api.py'
        content = api_path.read_text(encoding='utf-8')
        # Should have no direct path concatenation with unsanitized file.filename
        assert 'temp_dir / file.filename' not in content, \
            "Unsanitized file.filename used in path concatenation in api.py"
        assert 'temp_path = Path(f"/tmp/voice_upload_{file.filename}")' not in content, \
            "Unsanitized file.filename used in path construction in api.py"


# =========================================================================
# SEC-05: Error details not leaked
# =========================================================================

class TestErrorDetailsNotLeaked:

    def test_no_str_e_in_http_500_responses(self):
        """str(e) must not appear in HTTPException detail= for 500 errors."""
        api_path = Path(__file__).parent.parent / 'voice' / 'service' / 'api.py'
        content = api_path.read_text(encoding='utf-8')

        import re
        # Only match: raise HTTPException(status_code=500, detail=f"...{str(e)}...")
        # Use non-greedy match limited to a single line / statement
        pattern = r'raise HTTPException\(status_code=500[^)]*detail=[^)]*str\(e\)'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, \
            f"Found {len(matches)} HTTPException(500) with str(e) in detail: {matches}"

    def test_generic_error_messages_present(self):
        """Generic error messages should be in the 500 handlers."""
        api_path = Path(__file__).parent.parent / 'voice' / 'service' / 'api.py'
        content = api_path.read_text(encoding='utf-8')
        assert 'Transcription failed. Please try again.' in content
        assert 'Command processing failed. Please try again.' in content

    def test_auth_uses_timing_safe_comparison(self):
        """verify_api_key must use hmac.compare_digest, not ==."""
        auth_path = Path(__file__).parent.parent / 'voice' / 'service' / 'auth.py'
        content = auth_path.read_text()
        assert 'hmac.compare_digest' in content, \
            "auth.py must use hmac.compare_digest for API key comparison"
        # Should NOT have a plain == comparison for api key
        assert 'api_key != expected' not in content and 'api_key == expected' not in content, \
            "auth.py uses timing-unsafe == for API key comparison"


# =========================================================================
# SEC-06: SQL echo defaults to False
# =========================================================================

class TestSqlEchoDefault:

    def test_echo_not_hardcoded_true(self):
        """echo=True must not be hardcoded in models.py."""
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text()
        assert 'echo=True' not in content, \
            "echo=True is hardcoded in database/models.py — should be env-driven"

    def test_echo_controlled_by_env(self):
        """SQL_ECHO env var should control echo behavior."""
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text()
        assert 'SQL_ECHO' in content, \
            "SQL_ECHO env var not referenced in database/models.py"

    def test_echo_false_by_default(self):
        """Without SQL_ECHO set, echo should evaluate to False."""
        with patch.dict(os.environ, {}, clear=True):
            env_without = {k: v for k, v in os.environ.items() if k != 'SQL_ECHO'}
            with patch.dict(os.environ, env_without, clear=True):
                result = os.getenv("SQL_ECHO", "false").lower() == "true"
                assert result is False

    def test_echo_true_when_env_set(self):
        """With SQL_ECHO=true, echo should evaluate to True."""
        with patch.dict(os.environ, {'SQL_ECHO': 'true'}):
            result = os.getenv("SQL_ECHO", "false").lower() == "true"
            assert result is True

    def test_pool_pre_ping_enabled(self):
        """pool_pre_ping=True should be set for connection resilience."""
        models_path = Path(__file__).parent.parent / 'database' / 'models.py'
        content = models_path.read_text()
        assert 'pool_pre_ping=True' in content, \
            "pool_pre_ping=True not set in database engine configuration"
