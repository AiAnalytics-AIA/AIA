"""Engine and session construction.

PostgreSQL is the production store. SQLite is supported for unit tests and offline
development only, and this module normalises the two so that code behaves the same
against both.

The SQLite normalisation matters more than it looks: SQLite ignores every foreign
key constraint, including ``ON DELETE CASCADE``, unless ``PRAGMA foreign_keys`` is
switched on per connection. Without the hook below, a test suite on SQLite would
happily accept writes that PostgreSQL rejects and would leave orphaned rows where
production cascades correctly -- a class of bug that only surfaces after deploy.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

__all__ = [
    "DEFAULT_SQLITE_URL",
    "create_app_engine",
    "create_session_factory",
    "is_sqlite",
    "resolve_database_url",
    "session_scope",
    "shares_one_connection",
]

DEFAULT_SQLITE_URL = "sqlite+pysqlite:///:memory:"


def resolve_database_url(url: str | None = None) -> str:
    """Return the database URL to use.

    Precedence: the explicit argument, then ``DATABASE_URL``, then in-memory
    SQLite. Production deployments always set ``DATABASE_URL``; the SQLite default
    exists so that a fresh clone can run the test suite with no services.

    ``postgres://`` is rewritten to ``postgresql+psycopg://`` because several
    hosting providers still hand out the legacy scheme, which SQLAlchemy 2 rejects.
    """
    resolved = (url or os.environ.get("DATABASE_URL") or DEFAULT_SQLITE_URL).strip()

    if resolved.startswith("postgres://"):
        resolved = "postgresql+psycopg://" + resolved[len("postgres://") :]
    elif resolved.startswith("postgresql://"):
        resolved = "postgresql+psycopg://" + resolved[len("postgresql://") :]

    return resolved


def is_sqlite(url: str) -> bool:
    """True when the URL points at SQLite."""
    return url.startswith("sqlite")


def shares_one_connection(engine: Engine) -> bool:
    """True when every session on this engine gets the same DBAPI connection.

    That is the in-memory SQLite engine ``create_app_engine`` builds: one
    connection, so separate sessions see one database. It cannot serve two
    threads. Closing a session on one thread returns *the* connection to the pool,
    which rolls back whatever a session on another thread has flushed but not yet
    committed.
    """
    from sqlalchemy.pool import StaticPool

    return isinstance(engine.pool, StaticPool)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on per-connection foreign key enforcement for SQLite.

    Without this, SQLite silently accepts rows that violate a foreign key and
    silently skips ``ON DELETE CASCADE``, so tests would diverge from PostgreSQL.
    """

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_app_engine(
    url: str | None = None,
    *,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_pre_ping: bool = True,
    **kwargs: Any,
) -> Engine:
    """Create a configured engine for the application or a test.

    ``pool_pre_ping`` is on by default: a pooled connection that a database restart
    or a proxy timeout has silently killed would otherwise surface as a failed
    request rather than a transparently reopened connection.
    """
    resolved = resolve_database_url(url)

    if is_sqlite(resolved):
        # A file-backed SQLite URL gets no pooling arguments, and an in-memory URL
        # needs a shared connection so that separate sessions see the same data.
        options: dict[str, Any] = {"echo": echo, "future": True, **kwargs}
        if ":memory:" in resolved:
            from sqlalchemy.pool import StaticPool

            options.setdefault("poolclass", StaticPool)
            options.setdefault("connect_args", {"check_same_thread": False})
        engine = create_engine(resolved, **options)
        _enable_sqlite_foreign_keys(engine)
        return engine

    return create_engine(
        resolved,
        echo=echo,
        future=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        **kwargs,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory.

    ``expire_on_commit=False`` keeps domain objects readable after a commit, which
    the API layer relies on when serialising a response.
    """
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a unit of work, committing on success and rolling back on failure."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
