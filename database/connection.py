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
    Normalize DATABASE_URL to use the correct driver scheme.

    Neon and Railway both issue plain `postgresql://` URLs.  SQLAlchemy 2.x
    defaults to psycopg2 for that scheme, but deployed envs may only have
    psycopg v3 (package name `psycopg`) installed.

    Resolution order:
      1. If URL already has an explicit dialect+driver (e.g. +psycopg2, +psycopg,
         +asyncpg) — leave it alone.
      2. Try psycopg v3 first (preferred for new deployments).
      3. Fall back to psycopg2 if v3 is not installed.
    """
    if not url:
        return url

    # Already has an explicit driver — respect it
    if "+psycopg" in url or "+asyncpg" in url or "sqlite" in url:
        return url

    # Plain postgresql:// or postgres:// — pick the available driver
    try:
        import psycopg  # noqa: F401  (psycopg v3)
        return url.replace("postgresql://", "postgresql+psycopg://", 1) \
                  .replace("postgres://",   "postgresql+psycopg://", 1)
    except ImportError:
        pass

    try:
        import psycopg2  # noqa: F401
        return url.replace("postgres://", "postgresql://", 1)
    except ImportError:
        pass

    return url


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
