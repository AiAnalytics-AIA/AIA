"""``develop_snapshot``: record what a project revision looks like, as an artifact.

The develop vertical slice's one step. Deterministic, no model, no population:
it reads the project's content and stage states under the lease-issued scope,
writes a JSON artifact through :class:`ArtifactRepository` -- so the real
:class:`ArtifactStore`, artifact reuse and provenance are all exercised -- and
returns the artifact's identity as the step's output for the browser to read.

Idempotent by construction (``executor.py``: execution is at-least-once). The
artifact's reuse key is the fingerprint of the content it describes, so a re-run
after a crash finds the artifact the first run stored and uploads nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from aia_core.domain.pipeline import fingerprint
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import StepContext, StepInput, StepOutcome, Succeeded

__all__ = ["ARTIFACT_TYPE", "KIND", "SnapshotExecutor", "snapshot_payload"]

KIND: Final = DEVELOP_SNAPSHOT
ARTIFACT_TYPE: Final = "develop_snapshot"
SNAPSHOT_SCHEMA_VERSION: Final = 1


def snapshot_payload(
    *,
    step: StepInput,
    content: dict[str, Any],
    stages: list[dict[str, Any]],
    build: BuildIdentity,
    now: datetime,
) -> dict[str, Any]:
    """The artifact body. Pure, so it is testable without a database."""
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "project_id": step.project_id,
        "project_revision": step.project_revision,
        "content_fingerprint": fingerprint(content),
        "content_keys": sorted(content),
        "stages": stages,
        "produced_by": {
            "run_id": step.run_id,
            "step_id": step.step_id,
            "attempt_id": step.attempt_id,
            "attempt_number": step.attempt_number,
            "kind": step.kind,
        },
        "runtime_version": build.sha,
        "created_at": now.isoformat(),
    }


class SnapshotExecutor:
    """Executes ``develop_snapshot`` steps against one artifact store."""

    def __init__(self, *, store: ArtifactStore, build: BuildIdentity) -> None:
        self._store = store
        self._build = build

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        content_fingerprint = step.input_fingerprint

        with context.transaction() as (session, _workflow):
            projects = ProjectRepository(session, context.scope)
            content = projects.content(step.project_id, step.project_revision)
            stages = [
                {"stage_type": s.stage_type, "status": s.status.value, "ordinal": s.ordinal}
                for s in projects.stages(step.project_id, step.project_revision)
            ]
            payload = snapshot_payload(
                step=step,
                content=content,
                stages=stages,
                build=self._build,
                now=datetime.now(UTC),
            )
            artifacts = ArtifactRepository(session, context.scope, self._store)
            artifact, created = artifacts.put_json(
                payload=payload,
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=ARTIFACT_TYPE,
                input_fingerprint=content_fingerprint or payload["content_fingerprint"],
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={"run_id": step.run_id, "step_id": step.step_id},
            )

        context.progress(
            "snapshot stored" if created else "snapshot reused",
            artifact_id=artifact.artifact_id,
            reused=not created,
        )
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "artifact_type": ARTIFACT_TYPE,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "reused": not created,
                "runtime_version": self._build.sha,
            }
        )
