"""``python -m aia_worker`` / ``aia-worker``: run one worker process.

Signals:

* first ``SIGTERM`` or ``SIGINT`` -- stop claiming; the executing step is asked to
  stop at its next checkpoint and is **released** to another worker (or
  ``RECOVERY_REQUIRED`` if a paid call is in flight). The process then exits 0.
  ECS sends ``SIGTERM`` and waits ``stopTimeout`` before ``SIGKILL``;
* a second signal -- exit now. The attempt stays held, its lease lapses, and any
  worker's reconciler recovers it -- the same path as ``SIGKILL`` or a crash.

Exit codes: 0 clean stop, 2 invalid configuration, 130 forced stop.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from types import FrameType

from aia_core.infrastructure.db import create_app_engine, create_session_factory

from .observability import configure_logging
from .registry import load_executors
from .settings import WorkerSettings
from .worker import Worker

log = logging.getLogger("aia_worker")


def _install_signal_handlers(worker: Worker) -> None:
    def handle(signum: int, _frame: FrameType | None) -> None:
        if worker.stopping:
            log.warning("second signal; exiting without releasing", extra={"fields": {}})
            raise SystemExit(130)
        log.info("stop requested", extra={"fields": {"signal": signal.Signals(signum).name}})
        worker.request_stop()

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)


def main() -> int:
    """Run a worker until signalled. Returns the process exit code."""
    try:
        settings = WorkerSettings.from_env()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    configure_logging(worker_id=settings.worker_id, level=os.environ.get("AIA_LOG_LEVEL", "INFO"))
    try:
        executors = load_executors(settings.executors)
    except (ImportError, ValueError) as error:
        log.error("invalid executor configuration: %s", error)
        return 2

    # A worker needs one connection for its loop and one for the heartbeat, plus
    # headroom for a retry; it does not need the API's pool.
    engine = create_app_engine(settings.database_url, pool_size=3, max_overflow=2)
    try:
        worker = Worker(
            session_factory=create_session_factory(engine),
            executors=executors,
            settings=settings,
        )
        _install_signal_handlers(worker)
        worker.run_forever()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
