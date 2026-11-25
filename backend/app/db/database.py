"""SQLAlchemy 2.0 engine, session management, and schema initialization."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

DEFAULT_SQLITE_URL = "sqlite:///./fitsoul_dev.db"


class Base(DeclarativeBase):
    """Declarative base class for all FitSoul AI ORM models."""


def normalize_database_url(url: str) -> str:
    """Normalize Postgres URLs to use the psycopg v3 SQLAlchemy dialect."""
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgres://")
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgresql://")
    return cleaned


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a configured SQLAlchemy engine for Postgres or SQLite."""
    raw_url = (database_url or get_settings().database_url or "").strip() or DEFAULT_SQLITE_URL
    url = normalize_database_url(raw_url)
    if url.startswith("sqlite"):
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    """Create database tables from ORM metadata if they do not exist."""
    import app.db.tables  # noqa: F401

    Base.metadata.create_all(bind=engine)


@lru_cache
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine configured from application settings."""
    return create_db_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return a cached SQLAlchemy sessionmaker bound to the default engine."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session
