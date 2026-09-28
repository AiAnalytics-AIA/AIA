"""``python -m aia_executors.smoke --expect-build <sha>``: the deployed slice, end to end.

Run by ``deploy/develop/bin/smoke.sh`` inside the worker image, against the
running deployment. It proves, in order:

1. **Storage** -- a synthetic object round-trips through the configured
   :class:`ArtifactStore` (S3 in develop) and is hash-verified on read.
2. **Seed** -- the develop world exists (idempotent; creates it on first run).
3. **Worker + slice** -- a fresh ``develop_snapshot`` run is created as the smoke's
   own synthetic owner, in the seed's smoke organization (never the operator's,
   so nothing a person archives in their workspace can stop it), through the
   same use case the API calls; the *running* worker
   claims and executes it, and its step output names the deployed build; the
   artifact is read back from the store and hash-verified. A freshly stored
   artifact carries the deployed build as its ``runtime_version``; one reused
   by content fingerprint keeps the build that first produced it, and the
   check says so instead of failing (reuse is the design, ``snapshot.py``).
4. **AI** -- reported ``NOT_RUNNABLE`` until a Bedrock adapter and governed
   route are wired into the deployed revision (ADR 0010). Printed, never
   counted as a pass.

Output is one ``ok``/``FAIL``/``NOT_RUNNABLE`` line per check, in the same shape
as ``smoke.sh``; exit status is non-zero on any ``FAIL``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

from aia_core.application.develop_seed import seed_develop, seeded_study_scope
from aia_core.application.workflows import start_workflow
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.build_identity import parse_build_sha
from aia_core.infrastructure.storage import ArtifactStore, build_storage_key, sha256_bytes
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from sqlalchemy.orm import Session, sessionmaker

from ._db import engine_from_env

__all__ = ["main", "storage_round_trip", "wait_for_snapshot"]


class Report:
    """Collects check lines and remembers whether any failed."""

    def __init__(self, out: Callable[[str], None] = print) -> None:
        self._out = out
        self.failed = False

    def ok(self, label: str) -> None:
        self._out(f"ok    {label}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failed = True
        self._out(f"FAIL  {label}")
        if detail:
            self._out(f"      {detail}")

    def not_runnable(self, label: str, detail: str) -> None:
        self._out(f"NOT_RUNNABLE  {label}")
        self._out(f"      {detail}")


def storage_round_trip(store: ArtifactStore, report: Report) -> None:
    """Put, read back with hash verification, and delete one synthetic object."""
    key = build_storage_key(
        organization_id="smoke",
        client_id="smoke",
        study_id="smoke",
        project_id="smoke",
        revision=0,
        stage_type="SMOKE",
        artifact_id=f"SMK-{uuid.uuid4().hex[:12]}",
    )
    body = f'{{"smoke": true, "nonce": "{uuid.uuid4().hex}"}}'.encode()
    try:
        stored = store.put(key, body, content_type="application/json")
        if stored.sha256 != sha256_bytes(body):
            report.fail("storage: put returns the content hash", stored.sha256)
            return
        read = store.get(key, expected_sha256=stored.sha256)
        if read != body:
            report.fail("storage: read returns the bytes written")
            return
        store.delete(key)
        if store.exists(key):
            report.fail("storage: delete removes the object")
            return
        report.ok("storage: put, hash-verified get and delete round-trip")
    except Exception as exc:
        report.fail("storage: round trip", f"{type(exc).__name__}: {exc}")


def wait_for_snapshot(
    sessions: sessionmaker[Session],
    *,
    run_id: str,
    timeout_s: float,
    poll_s: float = 1.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Poll the run until it is terminal or ``timeout_s`` passes; return it."""
    deadline = clock() + timeout_s
    while True:
        with sessions() as session:
            scope = seeded_study_scope(session)
            run = WorkflowRepository(session, scope).get_run(run_id)
        if WorkflowRunStatus(run["status"]).is_terminal or clock() >= deadline:
            return run
        sleep(poll_s)


def slice_check(
    sessions: sessionmaker[Session],
    *,
    store: ArtifactStore,
    owner_email: str,
    expect_build: str | None,
    timeout_s: float,
    report: Report,
) -> None:
    with sessions() as session:
        seed = seed_develop(session, owner_email=owner_email)
        session.commit()
    report.ok(f"seed: develop world present (study {seed.study_id})")

    # A fresh key per invocation: the point is a *new* execution by the running
    # worker, not the reuse of a run an earlier deploy already completed.
    nonce = uuid.uuid4().hex[:12]
    with sessions() as session:
        scope = seeded_study_scope(session)
        started = start_workflow(
            session,
            scope,
            project_id=seed.project_id,
            workflow_type=DEVELOP_SNAPSHOT,
            idempotency_key=f"smoke:{expect_build or 'local'}:{nonce}",
            metadata={"smoke": True},
        )
        session.commit()
    report.ok(f"slice: run {started.run_id} created as the smoke's own owner")

    run = wait_for_snapshot(sessions, run_id=started.run_id, timeout_s=timeout_s)
    status = WorkflowRunStatus(run["status"])
    if status is not WorkflowRunStatus.COMPLETED:
        step = run["steps"][0] if run["steps"] else {}
        report.fail(
            f"slice: the running worker completed run {started.run_id}",
            f"status {status.value}; step {step.get('status')}, "
            f"attempts {step.get('attempts_recorded')}, last error "
            f"{(step.get('attempts') or [{}])[-1].get('error')}",
        )
        return
    report.ok("slice: the running worker claimed and completed the run")

    output = run["steps"][0]["output"]
    artifact_id = output.get("artifact_id")
    with sessions() as session:
        scope = seeded_study_scope(session)
        artifacts = ArtifactRepository(session, scope, store)
        artifact = artifacts.get(artifact_id)
        payload = artifacts.read_json(artifact_id)
    report.ok(f"slice: artifact {artifact_id} read back from the store, hash verified")

    # Two different facts, checked separately. The step output names the build
    # that *executed* this run: that must be the deployed one. The artifact names
    # the build that *produced* its bytes, which is older whenever the content
    # fingerprint already had a VALID artifact -- reuse is the design
    # (snapshot.py), and a second deploy over the unchanged seed hits it every
    # time. Run 35869042785 failed by conflating the two.
    executed_by = output.get("runtime_version")
    reused = bool(output.get("reused"))
    if expect_build is not None and executed_by != expect_build:
        report.fail(
            "slice: the run was executed by the deployed build",
            f"step output runtime_version {executed_by!r}, expected {expect_build!r}",
        )
    elif reused:
        report.ok(
            f"slice: artifact reused from build {artifact.runtime_version} "
            f"(same content fingerprint); executed by build {executed_by}"
        )
    elif expect_build is not None and artifact.runtime_version != expect_build:
        report.fail(
            "slice: the artifact was produced by the deployed build",
            f"runtime_version {artifact.runtime_version!r}, expected {expect_build!r}",
        )
    else:
        report.ok(f"slice: artifact provenance names build {artifact.runtime_version}")
    if payload.get("project_id") != seed.project_id:
        report.fail("slice: the snapshot describes the seeded project", str(payload)[:200])


def describe_failure(exc: Exception) -> str:
    """One line for an unexpected slice error, with a denial's reason.

    A ``ScopeDenied`` says "not found" whatever the cause, so that a request
    learns nothing; the operator reading the smoke needs the reason to know
    which row to look at (membership, user, client, grant).
    """
    if isinstance(exc, ScopeDenied):
        return f"ScopeDenied: {exc} (reason: {exc.reason})"
    return f"{type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-build", default=None, help="the git SHA the deployment runs")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="seconds to wait for the worker"
    )
    parser.add_argument("--owner-email", default=os.environ.get("AIA_SEED_OWNER_EMAIL", ""))
    args = parser.parse_args(argv)

    report = Report()
    try:
        expect_build = parse_build_sha(args.expect_build)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not args.owner_email:
        print("AIA_SEED_OWNER_EMAIL (or --owner-email) is required", file=sys.stderr)
        return 2

    store = build_artifact_store(StorageSettings.from_env())
    storage_round_trip(store, report)

    engine, sessions = engine_from_env()
    try:
        slice_check(
            sessions,
            store=store,
            owner_email=args.owner_email,
            expect_build=expect_build,
            timeout_s=args.timeout,
            report=report,
        )
    except Exception as exc:
        report.fail("slice: unexpected error", describe_failure(exc))
    finally:
        engine.dispose()

    report.not_runnable(
        "ai: governed model call through ModelGateway -> bedrock-eu-primary",
        "ModelGateway exists, but no Bedrock adapter or live governed route "
        "is wired (ADR 0010 is Proposed)",
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
