"""Database engine, session factory, and initialization."""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Enable WAL mode and foreign keys for every new SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str | None = None):
    """Create a SQLAlchemy engine.

    Args:
        database_url: Override the default database URL (used in tests).

    Returns:
        A SQLAlchemy engine instance.
    """
    url = database_url or settings.database_url
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


# Default engine and session factory used by the application
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(db_engine=None) -> None:
    """Create all tables defined in models.

    Args:
        db_engine: Override the engine (used in tests).
    """
    target = db_engine or engine
    # Ensure the data directory exists before creating the DB file
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=target)
    logger.info("Database initialized at %s", settings.db_path)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for standalone session usage (e.g. scripts)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
