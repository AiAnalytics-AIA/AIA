"""Typed worker settings, validated on construction.

Invalid configuration fails at startup, not at the first claim -- the same rule
the API's ``Settings`` follows (``AGENTS.md`` § Pydantic settings). A plain frozen
dataclass rather than ``pydantic-settings``: the worker reads nine values and
should not need a second settings framework to do it.

Every number is parsed with a guard (``ARCHITECTURE.md`` A7): a malformed or
out-of-range value names its variable and stops the process, rather than
becoming a zero-second heartbeat or a lease shorter than the heartbeat that is
supposed to keep it alive.
"""

from __future__ import annotations

import os
import socket
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from aia_core.domain.workflow import (
    DEFAULT_CAPACITY_BACKOFF_SECONDS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_QUOTA_FALLBACK_SECONDS,
)
from aia_core.infrastructure.build_identity import parse_build_sha

__all__ = ["WorkerSettings", "default_worker_id"]

# `step_attempts.worker_id` is VARCHAR(128).
_MAX_WORKER_ID = 128


def default_worker_id() -> str:
    """``host:pid:nonce`` -- unique per process, and readable in an attempt row.

    The nonce matters: a container restarted with the same hostname and pid 1 must
    not share an identity with its previous life, or it could heartbeat a lease
    that life held.
    """
    return f"{socket.gethostname()[:80]}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    """What one worker process needs to run.

    ``heartbeat_seconds`` must be well under ``lease_seconds``: a lease survives
    only while heartbeats arrive, and one delayed heartbeat must not cost it. The
    rule enforced is at least two heartbeats per lease.
    """

    database_url: str
    executors: str
    worker_id: str = field(default_factory=default_worker_id)
    lease_seconds: int = DEFAULT_LEASE_SECONDS
    heartbeat_seconds: float = 30.0
    poll_seconds: float = 2.0
    maintenance_seconds: float = 30.0
    capacity_backoff_seconds: int = DEFAULT_CAPACITY_BACKOFF_SECONDS
    quota_fallback_seconds: int = DEFAULT_QUOTA_FALLBACK_SECONDS
    finish_attempts: int = 5
    #: The git commit this worker was built from (``AIA_BUILD_SHA``), logged at
    #: start so a running container can be matched to a revision. None when the
    #: deployment did not say; never a placeholder.
    build_sha: str | None = None

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not self.database_url.strip():
            problems.append("DATABASE_URL is required; a worker never defaults to SQLite")
        if ":" not in self.executors:
            problems.append("AIA_WORKER_EXECUTORS must be 'package.module:factory'")
        if not self.worker_id or len(self.worker_id) > _MAX_WORKER_ID:
            problems.append(f"worker id must be 1-{_MAX_WORKER_ID} characters")
        if self.lease_seconds < 2:
            problems.append("AIA_WORKER_LEASE_SECONDS must be at least 2")
        if not 0 < self.heartbeat_seconds <= self.lease_seconds / 2:
            problems.append(
                "AIA_WORKER_HEARTBEAT_SECONDS must be positive and at most half the lease, "
                f"got {self.heartbeat_seconds} for a {self.lease_seconds}s lease"
            )
        if self.poll_seconds <= 0:
            problems.append("AIA_WORKER_POLL_SECONDS must be positive")
        if self.maintenance_seconds <= 0:
            problems.append("AIA_WORKER_MAINTENANCE_SECONDS must be positive")
        if self.capacity_backoff_seconds < 0 or self.quota_fallback_seconds < 0:
            problems.append("back-off seconds must not be negative")
        if self.finish_attempts < 1:
            problems.append("finish_attempts must be at least 1")
        if problems:
            raise ValueError("invalid worker configuration: " + "; ".join(problems))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> WorkerSettings:
        """Build settings from the environment, failing on anything malformed."""
        source = os.environ if env is None else env
        problems: list[str] = []

        def number(name: str, default: float, *, integer: bool) -> float:
            raw = source.get(name, "").strip()
            if not raw:
                return default
            try:
                return int(raw) if integer else float(raw)
            except ValueError:
                problems.append(f"{name} must be {'an integer' if integer else 'a number'}")
                return default

        lease = int(number("AIA_WORKER_LEASE_SECONDS", DEFAULT_LEASE_SECONDS, integer=True))
        heartbeat = number("AIA_WORKER_HEARTBEAT_SECONDS", 30.0, integer=False)
        poll = number("AIA_WORKER_POLL_SECONDS", 2.0, integer=False)
        maintenance = number("AIA_WORKER_MAINTENANCE_SECONDS", 30.0, integer=False)
        capacity = int(
            number(
                "AIA_WORKER_CAPACITY_BACKOFF_SECONDS",
                DEFAULT_CAPACITY_BACKOFF_SECONDS,
                integer=True,
            )
        )
        quota = int(
            number(
                "AIA_WORKER_QUOTA_FALLBACK_SECONDS", DEFAULT_QUOTA_FALLBACK_SECONDS, integer=True
            )
        )
        try:
            build_sha = parse_build_sha(source.get("AIA_BUILD_SHA"))
        except ValueError as error:
            problems.append(str(error))
            build_sha = None
        if problems:
            raise ValueError("invalid worker configuration: " + "; ".join(problems))

        return cls(
            database_url=source.get("DATABASE_URL", "").strip(),
            build_sha=build_sha,
            executors=source.get("AIA_WORKER_EXECUTORS", "").strip(),
            worker_id=source.get("AIA_WORKER_ID", "").strip() or default_worker_id(),
            lease_seconds=lease,
            heartbeat_seconds=heartbeat,
            poll_seconds=poll,
            maintenance_seconds=maintenance,
            capacity_backoff_seconds=capacity,
            quota_fallback_seconds=quota,
        )
