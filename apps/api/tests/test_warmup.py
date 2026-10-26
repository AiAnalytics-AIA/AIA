"""The object map's kernels compiled in the background after start (AIA_SOCIOMAP_WARMUP_ENABLED)."""

from __future__ import annotations

import logging
import sys
import time

import pytest
from fastapi.testclient import TestClient

from aia_api import main as api_main
from aia_api.config import Settings
from aia_api.warmup import WARM_COMMAND, start_object_map_warmup


def test_the_warm_up_runs_apart_and_says_how_long_it_took(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A child process does the work (numba compiles holding the GIL); a daemon thread waits."""
    with caplog.at_level(logging.INFO, logger="aia.warmup"):
        warmup = start_object_map_warmup((sys.executable, "-c", "print(3)"))
        warmup.thread.join(timeout=60)
    assert warmup.thread.daemon and not warmup.thread.is_alive()
    warm = [r for r in caplog.records if r.getMessage() == "sociomap kernels warm"]
    assert warm and warm[0].context["panels"] == "3"  # type: ignore[attr-defined]


def test_a_failed_warm_up_is_logged_and_changes_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="aia.warmup"):
        warmup = start_object_map_warmup((sys.executable, "-c", "raise SystemExit(1)"))
        warmup.thread.join(timeout=60)
        missing = start_object_map_warmup(("/nonexistent/python",))
        missing.thread.join(timeout=60)
    failed = [r for r in caplog.records if r.getMessage() == "sociomap warm-up failed"]
    assert len(failed) == 2


def test_the_warm_command_runs_the_domain_warm_up() -> None:
    assert "warm_object_maps" in WARM_COMMAND[-1] and WARM_COMMAND[0] == sys.executable


@pytest.mark.parametrize("enabled", [True, False])
def test_the_api_starts_the_warm_up_only_when_switched_on(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    """Off by default and in test; on, started from the lifespan, while health answers."""
    events: list[str] = []

    class Fake:
        def stop(self) -> None:
            events.append("stopped")

    def start() -> Fake:
        events.append("started")
        return Fake()

    monkeypatch.setattr(api_main, "start_object_map_warmup", start)
    app = api_main.create_app(settings.model_copy(update={"sociomap_warmup_enabled": enabled}))
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert events == (["started"] if enabled else [])
    # Shutting the API down stops a warm-up it started (review of #871).
    assert events == (["started", "stopped"] if enabled else [])


def test_stopping_terminates_a_running_warm_up_and_its_thread_ends(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A warm-up still compiling when the API shuts down does not outlive it."""
    with caplog.at_level(logging.INFO, logger="aia.warmup"):
        warmup = start_object_map_warmup((sys.executable, "-c", "import time; time.sleep(600)"))
        for _ in range(200):
            if warmup.child is not None:
                break
            time.sleep(0.05)
        child = warmup.child
        assert child is not None and child.poll() is None
        started = time.monotonic()
        warmup.stop()
        assert child.poll() is not None and time.monotonic() - started < 10
    assert not warmup.thread.is_alive()
    assert any(r.getMessage() == "sociomap warm-up stopped" for r in caplog.records)
    assert not any(r.getMessage() == "sociomap kernels warm" for r in caplog.records)


def test_the_switch_is_off_by_default() -> None:
    assert Settings.model_fields["sociomap_warmup_enabled"].default is False
