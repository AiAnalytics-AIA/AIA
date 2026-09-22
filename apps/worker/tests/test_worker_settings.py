"""Worker configuration: invalid settings stop the process at startup.

Every number is a boundary parse (``ARCHITECTURE.md`` A7), so each malformed or
implausible value gets a test naming what it must not become.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from aia_worker.registry import load_executors
from aia_worker.settings import WorkerSettings, default_worker_id
from aia_worker.testing import KIND, ScriptedExecutor

BASE = {
    "DATABASE_URL": "postgresql+psycopg://u:p@db/aia",
    "AIA_WORKER_EXECUTORS": "aia_worker.testing:build_registry",
}


def test_defaults_are_valid() -> None:
    settings = WorkerSettings.from_env(BASE)
    assert settings.lease_seconds == 120
    assert settings.heartbeat_seconds <= settings.lease_seconds / 2
    assert settings.worker_id


def test_values_are_read_from_the_environment() -> None:
    settings = WorkerSettings.from_env(
        {
            **BASE,
            "AIA_WORKER_ID": "w-1",
            "AIA_WORKER_LEASE_SECONDS": "60",
            "AIA_WORKER_HEARTBEAT_SECONDS": "10",
            "AIA_WORKER_POLL_SECONDS": "0.5",
            "AIA_WORKER_MAINTENANCE_SECONDS": "15",
            "AIA_WORKER_CAPACITY_BACKOFF_SECONDS": "30",
            "AIA_WORKER_QUOTA_FALLBACK_SECONDS": "600",
        }
    )
    assert (settings.worker_id, settings.lease_seconds, settings.heartbeat_seconds) == (
        "w-1",
        60,
        10.0,
    )
    assert settings.capacity_backoff_seconds == 30
    assert settings.quota_fallback_seconds == 600


def test_a_worker_never_defaults_to_sqlite() -> None:
    """The API may fall back to in-memory SQLite for development. A worker may not:
    it would claim nothing and report healthy."""
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        WorkerSettings.from_env({"AIA_WORKER_EXECUTORS": BASE["AIA_WORKER_EXECUTORS"]})


def test_executors_must_be_named() -> None:
    with pytest.raises(ValueError, match="AIA_WORKER_EXECUTORS"):
        WorkerSettings.from_env({"DATABASE_URL": BASE["DATABASE_URL"]})


@pytest.mark.parametrize(
    ("name", "value", "complaint"),
    [
        ("AIA_WORKER_LEASE_SECONDS", "two minutes", "must be an integer"),
        ("AIA_WORKER_LEASE_SECONDS", "1", "at least 2"),
        ("AIA_WORKER_HEARTBEAT_SECONDS", "0", "at most half the lease"),
        ("AIA_WORKER_HEARTBEAT_SECONDS", "90", "at most half the lease"),
        ("AIA_WORKER_POLL_SECONDS", "-1", "must be positive"),
        ("AIA_WORKER_MAINTENANCE_SECONDS", "0", "must be positive"),
        ("AIA_WORKER_CAPACITY_BACKOFF_SECONDS", "-5", "must not be negative"),
        ("AIA_WORKER_ID", "x" * 129, "1-128 characters"),
    ],
)
def test_implausible_values_are_refused(name: str, value: str, complaint: str) -> None:
    with pytest.raises(ValueError, match=complaint):
        WorkerSettings.from_env({**BASE, name: value})


def test_default_worker_ids_are_unique_per_call() -> None:
    """A restarted container with the same host and pid must not reuse an identity."""
    assert default_worker_id() != default_worker_id()


# --------------------------------------------------------------------------- #
# Registry loading
# --------------------------------------------------------------------------- #


def _module(name: str, **attributes: Any) -> None:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


def test_the_testing_registry_loads() -> None:
    registry = load_executors("aia_worker.testing:build_registry")
    assert list(registry) == [KIND]
    assert isinstance(registry[KIND], ScriptedExecutor)


@pytest.mark.parametrize(
    ("factory", "complaint"),
    [
        (lambda: {}, "non-empty dict"),
        (lambda: [ScriptedExecutor()], "non-empty dict"),
        (lambda: {"": ScriptedExecutor()}, "blank or non-string"),
        (lambda: {"k": object()}, "no execute"),
    ],
)
def test_an_unusable_registry_is_refused(factory: Any, complaint: str) -> None:
    _module("aia_worker_test_factories", build=factory)
    try:
        with pytest.raises(ValueError, match=complaint):
            load_executors("aia_worker_test_factories:build")
    finally:
        del sys.modules["aia_worker_test_factories"]


@pytest.mark.parametrize("spec", ["no_colon", ":build", "aia_worker.testing:"])
def test_a_malformed_factory_path_is_refused(spec: str) -> None:
    with pytest.raises(ValueError):
        load_executors(spec)


def test_a_missing_module_fails_loudly() -> None:
    with pytest.raises(ImportError):
        load_executors("aia_worker_no_such_module:build")


def test_a_non_callable_factory_is_refused() -> None:
    with pytest.raises(ValueError, match="not callable"):
        load_executors("aia_worker.testing:KIND")
