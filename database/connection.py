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
