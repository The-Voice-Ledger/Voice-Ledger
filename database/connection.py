"""
Database connection utilities
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def _resolve_db_url(url: str) -> str:
    """
    Normalize DATABASE_URL to use a driver that is actually installed.

    Priority:
      1. sqlite / asyncpg — leave untouched.
      2. postgresql+psycopg:// (v3 scheme) — use if psycopg is installed,
         otherwise downgrade to postgresql+psycopg2:// (v2).
      3. postgresql+psycopg2:// — verify psycopg2 is installed; warn if not.
      4. bare postgresql:// / postgres:// — pick whichever driver is present.
    """
    if not url:
        return url

    # sqlite and asyncpg never need patching
    if "sqlite" in url or "+asyncpg" in url:
        return url

    def _has_psycopg3() -> bool:
        try:
            import psycopg  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_psycopg2() -> bool:
        try:
            import psycopg2  # noqa: F401
            return True
        except ImportError:
            return False

    # Explicit psycopg v3 scheme but package not installed → downgrade to v2
    if "+psycopg" in url and "+psycopg2" not in url:
        if not _has_psycopg3():
            if _has_psycopg2():
                new_url = url.replace("+psycopg://", "+psycopg2://", 1)
                import logging as _log
                _log.getLogger(__name__).warning(
                    "psycopg (v3) not installed — downgrading DATABASE_URL "
                    "from +psycopg:// to +psycopg2://. "
                    "Install psycopg[binary]>=3.1.0 to remove this warning."
                )
                return new_url
            else:
                raise ImportError(
                    "Neither psycopg (v3) nor psycopg2 is installed. "
                    "Run: pip install psycopg[binary]"
                )
        return url  # psycopg v3 is available — use as-is

    # Explicit psycopg2 scheme — nothing to do
    if "+psycopg2" in url:
        return url

    # Bare postgresql:// / postgres:// — pick the available driver
    bare = url.replace("postgres://", "postgresql://", 1)
    if _has_psycopg3():
        return bare.replace("postgresql://", "postgresql+psycopg://", 1)
    if _has_psycopg2():
        return bare  # SQLAlchemy defaults to psycopg2 for postgresql://
    raise ImportError(
        "Neither psycopg (v3) nor psycopg2 is installed. "
        "Run: pip install psycopg[binary]"
    )


DATABASE_URL = _resolve_db_url(DATABASE_URL)

_is_sqlite = DATABASE_URL and DATABASE_URL.startswith("sqlite")
_pool_kwargs = {} if _is_sqlite else {
    "pool_size": 5,
    "max_overflow": 10,
}
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=3600,
    **_pool_kwargs,
)
SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db():
    """Get database session with automatic commit/rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
