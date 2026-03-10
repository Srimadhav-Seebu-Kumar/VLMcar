from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for backend persistence models."""


def _connect_args_for_url(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


@lru_cache(maxsize=8)
def get_engine(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine for the target database URL."""

    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=_connect_args_for_url(database_url),
    )


@lru_cache(maxsize=8)
def get_session_factory(database_url: str) -> sessionmaker[Session]:
    """Return a cached session factory for the selected database."""

    return sessionmaker(bind=get_engine(database_url), autoflush=False, expire_on_commit=False)


def init_db(database_url: str) -> None:
    """Create missing tables for all ORM models."""

    import backend.app.services.storage.models  # noqa: F401

    Base.metadata.create_all(bind=get_engine(database_url))


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    """Context-managed transactional session helper for repositories."""

    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_cached_db_handles() -> None:
    """Reset cached engine/session makers, useful for tests."""

    get_session_factory.cache_clear()
    get_engine.cache_clear()
