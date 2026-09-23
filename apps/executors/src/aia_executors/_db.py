"""Engine and session for the executors' operator commands (seed, smoke).

``DATABASE_URL`` only, and never a SQLite default: like the worker, an operator
command that silently ran against an in-memory database would report success
while changing nothing.
"""

from __future__ import annotations

import os

from aia_core.infrastructure.db import create_app_engine, create_session_factory
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

__all__ = ["engine_from_env"]


def engine_from_env() -> tuple[Engine, sessionmaker[Session]]:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or url.startswith("sqlite"):
        raise SystemExit("DATABASE_URL must point at PostgreSQL for an operator command")
    engine = create_app_engine(url, pool_size=2, max_overflow=2)
    return engine, create_session_factory(engine)
