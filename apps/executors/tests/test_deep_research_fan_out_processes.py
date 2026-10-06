"""Deep Research fan-out across real worker processes, on PostgreSQL (chunk 21).

``python -m aia_worker`` processes run the real Deep Research executors over the synthetic
world of ``fan_out_world.py`` (``AIA_WORKER_EXECUTORS=fan_out_world:build_registry``):
recorded search and pages, recorded agents with an injected latency, the shared host
pacer and model slots in this database, and a ledger every process appends each model
request, search and page request to. Assertions are on those ledgers and on the database
-- never on what a worker says it did.

* **50 tracks never exceed either limit.** Four processes share the run's 50 track steps;
  the model requests in flight never exceed the pool's limit (and do run concurrently);
  each host's requests never overlap and each starts no sooner than the host's interval
  after the previous one ended -- across processes, since each host is asked by several.
* **Every interrupted track recovers.** A worker killed (``SIGKILL``) inside a track's
  page request: another worker takes the track's step once its lease lapses, closes the
  request as uncertain without sending it again, and the run completes; nothing is asked
  or charged twice.

**PostgreSQL only** (``AGENTS.md`` § SQLAlchemy): skipped without it, failed instead with
``AIA_REQUIRE_POSTGRES=1``. Waits are generous (``CLAUDE.md`` § 7): they bound a slow
runner; the limits are asserted from the ledgers, not from timing.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import fan_out_world as fw  # type: ignore[import-not-found]
import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.contracts import (
    Channel,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
    track_id,
)
from aia_core.domain.deep_research.workflow import INVESTIGATE_TRACK_KIND
from aia_core.domain.workflow import AttemptStatus, StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.storage import FilesystemArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import BudgetReservationRow
from sqlalchemy import select
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    read,
    research,  # noqa: F401  (a fixture)
)

pytestmark = pytest.mark.postgres

WAIT = 240.0
LEASE_SECONDS = 3
TESTS = Path(__file__).parent


@pytest.fixture(autouse=True)
def _require_postgres(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        message = "fan-out process tests need PostgreSQL; set DATABASE_URL to a postgresql:// URL"
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)


class WorkerProcess:
    """One ``python -m aia_worker`` over the synthetic world, logging to a file."""

    def __init__(self, name: str, *, env: dict[str, str], log_dir: Path) -> None:
        self.name = name
        self.log_path = log_dir / f"{name}.log"
        self._log = self.log_path.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "aia_worker"],
            env={**env, "AIA_WORKER_ID": name},
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(10)
        self._log.close()

    def log(self) -> str:
        return self.log_path.read_text(errors="replace")


@pytest.fixture
def spawn(database_url: str, tmp_path: Path) -> Iterator[Callable[..., WorkerProcess]]:
    started: list[WorkerProcess] = []

    def start(name: str, **world: str) -> WorkerProcess:
        path = os.pathsep.join(p for p in (str(TESTS), os.environ.get("PYTHONPATH", "")) if p)
        env = {
            **os.environ,
            "PYTHONPATH": path,
            "DATABASE_URL": database_url,
            "AIA_ENV": "test",
            "AIA_WORKER_EXECUTORS": "fan_out_world:build_registry",
            "AIA_WORKER_LEASE_SECONDS": str(LEASE_SECONDS),
            "AIA_WORKER_HEARTBEAT_SECONDS": "0.5",
            "AIA_WORKER_POLL_SECONDS": "0.05",
            "AIA_WORKER_MAINTENANCE_SECONDS": "0.5",
            "AIA_WORKER_CAPACITY_BACKOFF_SECONDS": "0",
            "AIA_LOG_LEVEL": "WARNING",
            **world,
        }
        worker = WorkerProcess(name, env=env, log_dir=tmp_path)
        started.append(worker)
        return worker

    try:
        yield start
    finally:
        for worker in started:
            worker.close()


def _wait_for(condition: Callable[[], bool], *, what: str, timeout: float = WAIT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}")


def _start(world: ResearchWorld, n: int) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=fw.design(n), source_stage="brief"
        )
        run = DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            preset_name="STANDARD",
            channels=(Channel.WEB,),
        )
        session.commit()
        return run.run_id


def _run(world: ResearchWorld, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        run: dict[str, Any] = DeepResearchRuns(session, world.lead_scope(session)).get(run_id)
        return run


def _failures(run: dict[str, Any]) -> list[tuple[str, Any]]:
    """Each attempt that did not succeed, by its step: what an assertion message shows."""
    return [
        (s["node_key"], a["status"], a["failure_class"], a["error"])
        for s in run["steps"]
        for a in s["attempts"]
        if a["status"] not in (AttemptStatus.SUCCEEDED, AttemptStatus.DEFERRED)
    ]


def _status(world: ResearchWorld, run_id: str) -> WorkflowRunStatus:
    return WorkflowRunStatus(_run(world, run_id)["status"])


def _world_env(directory: Path, world: ResearchWorld, n: int, **extra: str) -> dict[str, str]:
    return {
        "AIA_TEST_FAN_OUT_DIR": str(directory),
        "AIA_TEST_FAN_OUT_TRACKS": str(n),
        "AIA_TEST_FAN_OUT_CLIENT": world.client_id,
        **extra,
    }


def peak(intervals: list[tuple[float, float]]) -> int:
    """The most intervals open at one instant (an end before a start at a tie)."""
    edges = sorted([(s, 1) for s, _ in intervals] + [(e, -1) for _, e in intervals])
    level = highest = 0
    for _, step in edges:
        level += step
        highest = max(highest, level)
    return highest


def _budget(world: ResearchWorld) -> dict[str, float]:
    from aia_core.infrastructure.workflow_repository import WorkflowRepository

    with world.sessions() as session:
        position: dict[str, float] = WorkflowRepository(
            session, world.lead_scope(session)
        ).budget_position()
        return position


def _open_holds(world: ResearchWorld) -> int:
    with world.sessions() as session:
        return len(
            session.scalars(
                select(BudgetReservationRow).where(BudgetReservationRow.status == "RESERVED")
            ).all()
        )


# --------------------------------------------------------------------------- #
# Fifty tracks, four processes, two limits
# --------------------------------------------------------------------------- #


def test_fifty_tracks_across_four_processes_never_exceed_either_limit(
    research: ResearchWorld,  # noqa: F811
    spawn: Callable[..., WorkerProcess],
    tmp_path: Path,
) -> None:
    n, limit, interval = 50, 3, 0.05
    directory = tmp_path / "world"
    directory.mkdir()
    fw.write_world(directory, n)
    run_id = _start(research, n)
    env = _world_env(
        directory,
        research,
        n,
        AIA_TEST_FAN_OUT_MODEL_LIMIT=str(limit),
        AIA_TEST_FAN_OUT_MODEL_LATENCY="0.05",
        AIA_TEST_FAN_OUT_FETCH_LATENCY="0.02",
        AIA_TEST_FAN_OUT_HOST_INTERVAL=str(interval),
    )
    workers = [spawn(f"fan-{i}", **env) for i in range(4)]

    _wait_for(
        lambda: _status(research, run_id).is_terminal,
        what="the run to finish",
    )
    for w in workers:
        w.process.send_signal(signal.SIGTERM)
    for w in workers:
        assert w.process.wait(60) == 0, w.log()

    run = _run(research, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED, _failures(run)
    _, bundle = read(research, run_id, FilesystemArtifactStore(directory / "store"))
    assert bundle.verify()
    assert len(bundle.tracks) == n
    assert {t.status for t in bundle.tracks} == {TrackStatus.COMPLETED}
    assert sorted(a.evidence.claim for a in bundle.accepted) == sorted(
        fw.sentence(i) for i in range(n)
    )

    # Every track in a step of its own, each run once, by more than one process.
    children = [s for s in run["steps"] if s["kind"] == INVESTIGATE_TRACK_KIND]
    assert len(children) == n
    assert all(s["status"] is StepRunStatus.SUCCEEDED for s in children)
    assert all(len(s["attempts"]) == 1 for s in children), "no track ran twice"
    assert len({s["attempts"][0]["worker_id"] for s in children}) >= 2

    # The model limit: never more requests in flight than the pool's slots.
    models = fw.ledger(directory / "models.jsonl")
    assert len(models) == bundle.counts["model_requests"], "nothing asked twice"
    in_flight = peak([(m["start"], m["end"]) for m in models])
    assert in_flight <= limit, f"{in_flight} model requests in flight, limit {limit}"
    assert in_flight >= 2, "the requests did run concurrently"
    assert len({m["pid"] for m in models}) >= 2

    # The hosts: one request at a time, each an interval after the last one ended.
    fetches = [f for f in fw.ledger(directory / "fetches.jsonl") if "end" in f]
    assert len(fetches) == bundle.counts["fetches"] == n
    shared = 0
    for host in {f["host"] for f in fetches}:
        requests = sorted((f["start"], f["end"], f["pid"]) for f in fetches if f["host"] == host)
        gaps = [b[0] - a[1] for a, b in pairwise(requests)]
        assert min(gaps) >= interval * 0.9, f"{host}: a request {min(gaps):.3f} s after the last"
        shared += len({pid for _s, _e, pid in requests}) >= 2
    assert shared >= 1, "a host was asked by several processes"
    searches = fw.ledger(directory / "searches.jsonl")
    assert Counter(s["query"] for s in searches) == Counter(fw.subject(i) for i in range(n))

    budget = _budget(research)
    assert budget["uncertain_usd"] == pytest.approx(0.0)
    assert budget["reserved_usd"] == pytest.approx(0.0)
    assert budget["spent_usd"] == pytest.approx(bundle.spend_usd["model_usd"])
    assert _open_holds(research) == 0


# --------------------------------------------------------------------------- #
# A worker killed mid-track
# --------------------------------------------------------------------------- #


def test_a_track_whose_worker_is_killed_mid_request_is_recovered_by_another(
    research: ResearchWorld,  # noqa: F811
    spawn: Callable[..., WorkerProcess],
    tmp_path: Path,
) -> None:
    n, doomed_track = 6, 3
    directory = tmp_path / "world"
    directory.mkdir()
    fw.write_world(directory, n)
    run_id = _start(research, n)
    env = _world_env(
        directory,
        research,
        n,
        AIA_TEST_FAN_OUT_MODEL_LIMIT="2",
        AIA_TEST_FAN_OUT_MODEL_LATENCY="0.02",
    )
    hang = fw.url(doomed_track)
    doomed = spawn("doomed", **env, AIA_TEST_FAN_OUT_HANG=hang)
    _wait_for(
        lambda: any(f.get("hang") for f in fw.ledger(directory / "fetches.jsonl")),
        what="the doomed worker to be inside the track's page request",
    )
    doomed.process.send_signal(signal.SIGKILL)
    doomed.process.wait(10)
    survivors = [spawn(f"survivor-{i}", **env) for i in range(2)]

    _wait_for(lambda: _status(research, run_id).is_terminal, what="the run to finish")
    for w in survivors:
        w.process.send_signal(signal.SIGTERM)
    for w in survivors:
        assert w.process.wait(60) == 0, w.log()

    run = _run(research, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED, _failures(run)
    _, bundle = read(research, run_id, FilesystemArtifactStore(directory / "store"))
    assert bundle.verify()
    tracks = {t.track_id: t for t in bundle.tracks}
    doomed_id = tracks[
        track_id(subject_key(SubjectKind.QUESTION, fw.subject(doomed_track)), Channel.WEB)
    ]
    assert doomed_id.status is TrackStatus.INCOMPLETE
    assert doomed_id.stop_reason is StopReason.TOOL_OUTCOME_UNCERTAIN
    assert {t.status for k, t in tracks.items() if k != doomed_id.track_id} == {
        TrackStatus.COMPLETED
    }

    # The killed track's step: expired with the doomed worker, finished by a survivor.
    by_key = {s["node_key"]: s for s in run["steps"]}
    step = by_key[f"investigate/{doomed_id.track_id}"]
    assert [(a["status"], a["worker_id"] == "doomed") for a in step["attempts"]] == [
        (AttemptStatus.EXPIRED, True),
        (AttemptStatus.SUCCEEDED, False),
    ]
    others = [s for s in run["steps"] if s["kind"] == INVESTIGATE_TRACK_KIND and s is not step]
    assert all(len(s["attempts"]) == 1 for s in others), "no other track ran again"

    # Nothing sent twice: the page left in flight, its track's search, any model request.
    fetches = fw.ledger(directory / "fetches.jsonl")
    assert [f["url"] for f in fetches].count(hang) == 1
    searches = Counter(s["query"] for s in fw.ledger(directory / "searches.jsonl"))
    assert set(searches.values()) == {1}
    models = fw.ledger(directory / "models.jsonl")
    assert len(models) == bundle.counts["model_requests"]
    # Nothing charged twice, and nothing uncertain: the killed request was a free one.
    budget = _budget(research)
    assert budget["uncertain_usd"] == pytest.approx(0.0)
    assert budget["spent_usd"] == pytest.approx(bundle.spend_usd["model_usd"])
    assert _open_holds(research) == 0
