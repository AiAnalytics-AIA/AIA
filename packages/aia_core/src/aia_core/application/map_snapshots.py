"""A map snapshot: one stored object map drawn on the server, an approvable artifact
(report-delivery RD4).

The Sociomap screen's snapshot was the browser's canvas saved as a PNG: bytes AIA never saw, so
nothing could be approved or exported as the map. A snapshot is now drawn here from the run's
stored contract-3 map, read through :func:`read_object_maps` (every fingerprint verified), by
the report's own figure functions at their fixed print cameras: nothing is laid out, fitted or
computed again, and the same map and view give the same bytes. It is stored once per map,
battery, method, view and renderer, as an artifact of the run's design project.

``camera`` is recorded as ``None``: no person chose one; the print camera is the renderer's
(RD4b adds the screen's camera once the Sociomap screen's function takes it). Its status is the
Sociomap register's for the map's method, read at every read and never stored, as every map's
is (``domain/sociomap_register.py``): a snapshot of a method the register does not approve is
internal, approved or not.

A snapshot is approved as any stored deliverable is (``ArtifactRepository.approve``, subject
``artifact``): one ledger shape. Code drew it from the run, so no person is its producer; the
person who started the run is, as for the run's reports (RD8).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from sqlalchemy.orm import Session

from aia_core.application.report import SOCIOMAP_ARTIFACT
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.scope import Permission, StudyContext
from aia_core.domain.sociomap import read_object_maps
from aia_core.domain.sociomap.models import ArtifactIntegrityError
from aia_core.domain.sociomap_register import MethodologyStatus, recorded_statuses
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactStatus
from aia_core.infrastructure.storage import ArtifactStore

MAP_SNAPSHOT_ARTIFACT_TYPE: Final = "research_map_snapshot"
MAP_SNAPSHOT_MEDIA_TYPE: Final = "image/png"
#: What a snapshot shows: the object map from above or from the side.
SnapshotView = Literal["top", "3d"]
#: The renderer's identity in the snapshot's key: a change to how a map is drawn draws it anew.
RENDERER: Final = "aia-map-snapshot-1"
_STAGE: Final = "REPORT"


class SnapshotRefused(Exception):
    """No snapshot of what was asked: ``reason`` says why, in a word the API answers."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class MapSnapshot:
    artifact: Artifact
    #: The Sociomap register's status for the map's method, read now.
    status: MethodologyStatus


def _run_map(
    session: Session, scope: StudyContext, store: ArtifactStore, run_id: str
) -> tuple[Mapping[str, Any], Artifact]:
    """The run and its stored Sociomap artifact (the run's own step's), checked."""
    run = ResearchRuns(session, scope).get(run_id)
    map_id = next(
        (
            (s.get("output") or {}).get("artifact_id")
            for s in run["steps"]
            if s["node_key"] == "sociomap"
        ),
        None,
    )
    if not map_id:
        raise SnapshotRefused("no_map", "běh nemá uloženou sociomapu")
    repo = research_artifacts(session, scope, store)
    stored = repo.get(str(map_id))
    if stored.artifact_type != SOCIOMAP_ARTIFACT or stored.status is not ArtifactStatus.VALID:
        raise SnapshotRefused("no_map", "uložená sociomapa běhu není platná")
    return run, stored


def _status(body: Mapping[str, Any], method: str) -> MethodologyStatus:
    approval = recorded_statuses(body).get(method)
    return MethodologyStatus.INTERNAL_ONLY if approval is None else approval.status


def map_snapshot(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    battery_id: str,
    method: str,
    view: SnapshotView,
    build: str = "",
) -> tuple[MapSnapshot, bool]:
    """The snapshot of one stored map's ``view``, drawn and stored the first time it is asked
    (``True``), else the one stored. Refused by name (:class:`SnapshotRefused`) for a run with
    no map, a battery or method it did not map, or a view the map cannot show."""
    from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshot

    scope.require(Permission.EXPORT_DELIVERABLE)
    run, stored = _run_map(session, scope, store, run_id)
    repo = research_artifacts(session, scope, store)
    body = repo.read_json(stored.artifact_id)["sociomap"]
    battery = next(
        (b for b in body.get("batteries", []) if b.get("battery_id") == battery_id), None
    )
    if battery is None:
        raise SnapshotRefused("no_battery", f"běh nemá sadu {battery_id}")
    try:
        found = dict(read_object_maps(battery)).get(method)
    except ArtifactIntegrityError as exc:
        raise SnapshotRefused("map_invalid", "uložená mapa neprošla kontrolou integrity") from exc
    if found is None:
        raise SnapshotRefused("no_method", f"sada {battery_id} nemá mapu metodou {method}")
    key = fingerprint(
        {
            "map": stored.sha256,
            "battery": battery_id,
            "method": method,
            "view": view,
            "camera": None,
            "renderer": RENDERER,
        }
    )
    reused = repo.find_reusable(
        project_id=str(run["project_id"]),
        stage_type=_STAGE,
        artifact_type=MAP_SNAPSHOT_ARTIFACT_TYPE,
        input_fingerprint=key,
    )
    if reused is not None:
        return MapSnapshot(reused, _status(body, method)), False
    labels = {o["id"]: o["label"] for o in battery["objects"]}
    png = object_map_snapshot(found, labels, view)
    if png is None:
        raise SnapshotRefused("view_unavailable", f"mapu nelze ukázat v pohledu {view}")
    artifact, _created = repo.put(
        project_id=str(run["project_id"]),
        revision=int(run["project_revision"]),
        stage_type=_STAGE,
        artifact_type=MAP_SNAPSHOT_ARTIFACT_TYPE,
        data=png,
        content_type=MAP_SNAPSHOT_MEDIA_TYPE,
        input_fingerprint=key,
        runtime_version=build,
        metadata={
            "run_id": run_id,
            "battery_id": battery_id,
            "method": method,
            "spec_fingerprint": found.spec_fingerprint,
            "view": view,
            "camera": None,
            "renderer": RENDERER,
            "map_artifact_id": stored.artifact_id,
            "map_sha256": stored.sha256,
        },
        depends_on=[stored.artifact_id],
        by_person=False,
    )
    return MapSnapshot(artifact, _status(body, method)), True


def stored_map_snapshot(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str, artifact_id: str
) -> MapSnapshot:
    """A stored snapshot of this run's map, found through the run, with its status read now.
    Raises ``ArtifactNotFound`` for anything else."""
    from aia_core.infrastructure.artifact_repository import ArtifactNotFound

    _run, stored = _run_map(session, scope, store, run_id)
    repo = research_artifacts(session, scope, store)
    snapshot = repo.get(artifact_id)
    if (
        snapshot.artifact_type != MAP_SNAPSHOT_ARTIFACT_TYPE
        or snapshot.metadata.get("run_id") != run_id
        or snapshot.metadata.get("map_artifact_id") != stored.artifact_id
        or snapshot.status is not ArtifactStatus.VALID
    ):
        raise ArtifactNotFound(artifact_id)
    body = repo.read_json(stored.artifact_id)["sociomap"]
    return MapSnapshot(snapshot, _status(body, str(snapshot.metadata.get("method"))))


def approve_map_snapshot(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    artifact_id: str,
    note: str = "",
) -> MapSnapshot:
    """A person approves a stored snapshot of the run's map, once (approving again changes
    nothing). The run's starter is its producer: with independent review on, they may not."""
    found = stored_map_snapshot(session, scope, store, run_id=run_id, artifact_id=artifact_id)
    repo = research_artifacts(session, scope, store)
    if found.artifact.is_approved:
        frozen = found.artifact if found.artifact.is_frozen else repo.freeze(artifact_id)
        return MapSnapshot(frozen, found.status)
    run = ResearchRuns(session, scope).get(run_id)
    starter = run.get("triggered_by")
    repo.approve(artifact_id, note=note, co_producers={str(starter)} if starter else ())
    return MapSnapshot(repo.freeze(artifact_id), found.status)
