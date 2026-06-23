"""Database session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

# Lazy engine creation to allow test overrides
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,      # test connection before use
            pool_size=10,            # max persistent connections per worker
            max_overflow=20,         # extra connections under burst
            pool_recycle=1800,       # recycle connections every 30 min (< RDS 8h idle timeout)
            pool_timeout=30,         # raise after 30s if no connection available
        )
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    SessionLocal = _get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
