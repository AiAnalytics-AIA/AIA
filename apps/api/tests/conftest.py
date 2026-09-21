"""API test fixtures.

Each test gets an app with its own in-memory database, so tests are independent
and need no running services. CI reruns the same suite with ``DATABASE_URL``
pointing at PostgreSQL to catch dialect-specific behaviour.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from aia_core.infrastructure.tables import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings
from aia_api.main import create_app

ORG = "ORG-primary"
OTHER_ORG = "ORG-other"
USER = "USER-1"


@pytest.fixture
def settings() -> Settings:
    """Test settings pointing at an isolated database."""
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        log_level="WARNING",
        log_format="console",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """An application instance with a freshly created schema."""
    application = create_app(settings)
    with TestClient(application):
        Base.metadata.create_all(application.state.engine)
        try:
            yield application
        finally:
            Base.metadata.drop_all(application.state.engine)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """An unauthenticated client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client: TestClient) -> TestClient:
    """A client authenticated as the primary tenant."""
    client.headers.update({"X-AIA-User": USER, "X-AIA-Org": ORG})
    return client


@pytest.fixture
def other_auth(app: FastAPI) -> Iterator[TestClient]:
    """A client authenticated as a second tenant, for isolation tests."""
    with TestClient(app) as c:
        c.headers.update({"X-AIA-User": "USER-2", "X-AIA-Org": OTHER_ORG})
        yield c
