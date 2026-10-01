"""Artifact metadata, provenance and reuse.

This is where the durability model pays for itself. Before running an expensive
stage, a caller asks :meth:`ArtifactRepository.find_reusable` whether a valid
artifact already exists for the same stage inputs. If it does, no AI call is
made.

The write order matters and is enforced here rather than left to callers:

1. hash the bytes;
2. look for a reusable artifact and return it if found;
3. upload to object storage;
4. verify the stored object;
5. **then** commit the metadata row.

A metadata row must never reference an object that does not exist, because the
row is what the rest of the system trusts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.pipeline import resolve_stage
from ..domain.providers import Provider
from ..domain.scope import (
    Permission,
    ScopeDenied,
    StudyContext,
    require_approval_independence,
)
from .storage import ArtifactStore, IntegrityError, ObjectNotFound, build_storage_key
from .tables import (
    ApprovalDecisionRow,
    ProjectArtifactDependencyRow,
    ProjectArtifactRow,
    ProjectRow,
)

__all__ = [
    "Artifact",
    "ArtifactNotFound",
    "ArtifactRepository",
    "ArtifactStatus",
    "new_artifact_id",
]


_ARTIFACT_ID = re.compile(r"^ART-[0-9a-f]{16}$")


def new_artifact_id() -> str:
    """Return a new artifact id."""
    return "ART-" + uuid4().hex[:16]


class ArtifactNotFound(LookupError):
    """The artifact does not exist, or is not in the caller's scope.

    Indistinguishable on purpose: acknowledging an artifact the caller may not
    read would disclose another client's work.
    """


class ArtifactStatus(StrEnum):
    """Lifecycle of an artifact."""

    VALID = "VALID"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    CORRUPT = "CORRUPT"

    @property
    def is_reusable(self) -> bool:
        """Only a VALID artifact may satisfy a reuse check."""
        return self is ArtifactStatus.VALID


@dataclass(frozen=True, slots=True)
class Artifact:
    """Artifact metadata and provenance.

    Carries everything needed to answer "what produced this, from what inputs, on
    which provider and model, and when". ``storage_key`` is deliberately present
    here but never serialised into an API response.
    """

    artifact_id: str
    project_id: str
    revision: int
    stage_type: str
    artifact_type: str
    storage_key: str
    content_type: str
    sha256: str
    size_bytes: int
    status: ArtifactStatus
    input_fingerprint: str
    provider: Provider | None
    model: str
    prompt_version: str
    runtime_version: str
    produced_by_job_id: str | None
    produced_by_user_id: str | None
    metadata: dict[str, Any]
    is_approved: bool
    is_frozen: bool
    created_at: datetime | None

    @property
    def is_reusable(self) -> bool:
        """True when this artifact may be reused for a matching fingerprint."""
        return self.status.is_reusable


def _to_domain(row: ProjectArtifactRow) -> Artifact:
    """Map an artifact row to the domain model."""
    return Artifact(
        artifact_id=row.artifact_id,
        project_id=row.project_id,
        revision=row.revision,
        stage_type=row.stage_type,
        artifact_type=row.artifact_type,
        storage_key=row.storage_key,
        content_type=row.content_type,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        status=ArtifactStatus(row.status),
        input_fingerprint=row.input_fingerprint,
        provider=Provider(row.provider) if row.provider else None,
        model=row.model,
        prompt_version=row.prompt_version,
        runtime_version=row.runtime_version,
        produced_by_job_id=row.produced_by_job_id,
        produced_by_user_id=row.produced_by_user_id,
        metadata=dict(row.artifact_metadata or {}),
        is_approved=row.is_approved,
        is_frozen=row.is_frozen,
        created_at=row.created_at,
    )


class ArtifactRepository:
    """Stores and retrieves artifacts within one authorised study scope.

    Constructed from a :class:`StudyContext`, so there is no code path that reads
    or writes an artifact without an authorisation decision having been made.
    """

    def __init__(
        self,
        session: Session,
        scope: StudyContext,
        store: ArtifactStore,
        *,
        owner: str | None = None,
    ) -> None:
        """``owner`` is the project owner this repository acts for (``projects.owner``).

        As in :class:`~aia_core.infrastructure.repositories.ProjectRepository`, an
        ordinary caller sees only the artifacts of ordinary projects: a research
        run's artifacts live on the Study's owned design project, and are read only
        through the run that produced them (ADR 0016).
        """
        if not isinstance(scope, StudyContext):
            raise TypeError(
                "ArtifactRepository requires a StudyContext issued by the "
                "authorization layer; unscoped access is not permitted"
            )
        self._session = session
        self._scope = scope
        self._store = store
        self._owner = owner

    # ---------------------------------------------------------------- helpers --

    def _project_filter(self) -> tuple[Any, ...]:
        """The isolation predicate on the owning project, owner included."""
        return (
            ProjectRow.organization_id == self._scope.organization_id,
            ProjectRow.client_id == self._scope.client_id,
            ProjectRow.study_id == self._scope.study_id,
            ProjectRow.owner.is_(None) if self._owner is None else ProjectRow.owner == self._owner,
        )

    def _owned_project(self, project_id: str) -> ProjectRow:
        """Fetch a project inside the authorised scope, or raise."""
        row = self._session.scalar(
            select(ProjectRow).where(
                ProjectRow.project_id == project_id,
                *self._project_filter(),
            )
        )
        if row is None:
            raise ArtifactNotFound(project_id)
        return row

    def _row(self, artifact_id: str) -> ProjectArtifactRow:
        """Fetch an artifact inside the authorised scope, or raise.

        Joined through ``projects`` so the scope predicate applies to the artifact
        too. An artifact is never addressable by id alone.
        """
        row = self._session.scalar(
            select(ProjectArtifactRow)
            .join(ProjectRow, ProjectRow.project_id == ProjectArtifactRow.project_id)
            .where(
                ProjectArtifactRow.artifact_id == artifact_id,
                *self._project_filter(),
            )
        )
        if row is None:
            raise ArtifactNotFound(artifact_id)
        return row

    # ------------------------------------------------------------------ reuse --

    def find_reusable(
        self,
        *,
        project_id: str,
        stage_type: str,
        artifact_type: str,
        input_fingerprint: str,
        across_revisions: bool = True,
    ) -> Artifact | None:
        """Return a valid artifact for these exact stage inputs, or None.

        This is the money-saving query. ``across_revisions`` is true by default
        because that is the whole point: editing a late stage must not re-run the
        early ones, and their artifacts live on the *previous* revision.

        An empty fingerprint never matches. A stage whose fingerprint could not be
        computed must recompute rather than reuse whatever happens to share the
        blank value.
        """
        if not input_fingerprint:
            return None

        self._owned_project(project_id)

        stmt = select(ProjectArtifactRow).where(
            ProjectArtifactRow.project_id == project_id,
            ProjectArtifactRow.stage_type == stage_type,
            ProjectArtifactRow.artifact_type == artifact_type,
            ProjectArtifactRow.input_fingerprint == input_fingerprint,
            ProjectArtifactRow.status == ArtifactStatus.VALID.value,
        )
        if not across_revisions:
            project = self._owned_project(project_id)
            stmt = stmt.where(ProjectArtifactRow.revision == project.current_revision)

        row = self._session.scalar(stmt.order_by(ProjectArtifactRow.revision.desc()))
        if row is None:
            return None

        # The row claims the object exists. Verify that before letting a caller
        # skip an expensive recomputation on the strength of it.
        if not self._store.exists(row.storage_key):
            row.status = ArtifactStatus.CORRUPT.value
            self._session.flush()
            return None

        return _to_domain(row)

    # ------------------------------------------------------------------ writes --

    def put(
        self,
        *,
        project_id: str,
        revision: int,
        stage_type: str,
        artifact_type: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        input_fingerprint: str = "",
        provider: Provider | None = None,
        model: str = "",
        prompt_version: str = "",
        runtime_version: str = "",
        produced_by_job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        depends_on: list[str] | None = None,
        reuse: bool = True,
        artifact_id: str | None = None,
    ) -> tuple[Artifact, bool]:
        """Store an artifact, reusing an existing one when the inputs match.

        Returns ``(artifact, created)``. ``created is False`` means an existing
        artifact satisfied the request and nothing was uploaded -- the normal,
        desirable outcome when a step re-runs after a duplicate queue delivery.

        The upload happens before the metadata row is committed, so a crash
        between the two leaves an orphaned object (harmless, reaped later) rather
        than a row pointing at nothing (which the system would trust).

        ``artifact_id`` is for a caller that must name the artifact before it is
        stored -- the 18.6.6 migration writes a revision citing a file in the same
        transaction -- and is one :func:`new_artifact_id` made; any other is refused.
        """
        self._scope.require(Permission.EDIT_STUDY)
        if artifact_id is not None and not _ARTIFACT_ID.fullmatch(artifact_id):
            raise ValueError("an artifact id is ART- and 16 hex characters")

        project = self._owned_project(project_id)
        stage = resolve_stage(project.project_type, stage_type)

        if reuse and input_fingerprint:
            existing = self.find_reusable(
                project_id=project_id,
                stage_type=stage,
                artifact_type=artifact_type,
                input_fingerprint=input_fingerprint,
            )
            if existing is not None:
                return existing, False

        artifact_id = artifact_id or new_artifact_id()
        key = build_storage_key(
            organization_id=self._scope.organization_id,
            client_id=self._scope.client_id,
            study_id=self._scope.study_id,
            project_id=project_id,
            revision=revision,
            stage_type=stage,
            artifact_id=artifact_id,
        )

        stored = self._store.put(
            key,
            data,
            content_type=content_type,
            metadata={
                "artifact_type": artifact_type,
                "stage_type": stage,
                "project_id": project_id,
            },
        )

        # Read back and verify before recording the row. Without this, a backend
        # that silently truncated or transformed the body would produce a row
        # asserting an integrity guarantee that does not hold.
        self._store.get(key, expected_sha256=stored.sha256)

        row = ProjectArtifactRow(
            artifact_id=artifact_id,
            project_id=project_id,
            revision=revision,
            stage_type=stage,
            artifact_type=artifact_type,
            storage_key=key,
            content_type=content_type,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            status=ArtifactStatus.VALID.value,
            input_fingerprint=input_fingerprint,
            provider=provider.value if provider else None,
            model=model,
            prompt_version=prompt_version,
            runtime_version=runtime_version,
            produced_by_job_id=produced_by_job_id,
            # Recorded from the authorised scope, never from a caller argument,
            # so the separation-of-duties check cannot be defeated by passing
            # someone else's id.
            produced_by_user_id=self._scope.actor_id,
            artifact_metadata=metadata or {},
        )
        self._session.add(row)
        self._session.flush()

        for dependency in depends_on or []:
            # Validate each dependency is in scope, so an evidence chain cannot
            # be made to reference another client's artifact.
            self._row(dependency)
            self._session.add(
                ProjectArtifactDependencyRow(
                    artifact_id=artifact_id, depends_on_artifact_id=dependency
                )
            )
        self._session.flush()

        return _to_domain(row), True

    def put_json(self, *, payload: Any, **kwargs: Any) -> tuple[Artifact, bool]:
        """Store a JSON artifact.

        Serialisation is canonical -- sorted keys, no incidental whitespace -- so
        that logically identical payloads hash identically and therefore
        deduplicate.
        """
        data = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        kwargs.setdefault("content_type", "application/json")
        return self.put(data=data, **kwargs)

    # ------------------------------------------------------------------- reads --

    def get(self, artifact_id: str) -> Artifact:
        """Return artifact metadata."""
        return _to_domain(self._row(artifact_id))

    def read(self, artifact_id: str) -> bytes:
        """Return the artifact bytes, verified against the recorded hash.

        A hash mismatch or a missing object marks the artifact CORRUPT and raises.
        Serving content that may have been altered as a research finding is worse
        than failing.

        The mark is flushed into the caller's transaction, like every write here,
        so it lasts only if that transaction commits. A caller whose unit of work
        rolls back on the exception loses it; one that answers the error commits
        first, as the API does before its 409.
        """
        row = self._row(artifact_id)
        try:
            return self._store.get(row.storage_key, expected_sha256=row.sha256)
        except IntegrityError:
            row.status = ArtifactStatus.CORRUPT.value
            self._session.flush()
            raise
        except ObjectNotFound:
            row.status = ArtifactStatus.CORRUPT.value
            self._session.flush()
            raise

    def read_json(self, artifact_id: str) -> Any:
        """Return a JSON artifact's decoded payload."""
        return json.loads(self.read(artifact_id).decode("utf-8"))

    def download_url(self, artifact_id: str, *, expires_seconds: int = 300) -> str | None:
        """Return a short-lived download URL, or None when streaming is required.

        Requires export authority: handing out a URL is handing out the content,
        so it is gated like an export rather than like a read.
        """
        self._scope.require(Permission.EXPORT_DELIVERABLE)
        row = self._row(artifact_id)
        return self._store.presigned_url(row.storage_key, expires_seconds=expires_seconds)

    def recent(self, *, limit: int = 5) -> list[Artifact]:
        """The study's most recent artifacts, newest first: metadata only, for an overview."""
        self._scope.require(Permission.VIEW_RESULTS)
        rows = self._session.scalars(
            select(ProjectArtifactRow)
            .join(ProjectRow, ProjectRow.project_id == ProjectArtifactRow.project_id)
            .where(
                *self._project_filter(),
            )
            .order_by(ProjectArtifactRow.created_at.desc())
            .limit(max(1, min(limit, 50)))
        ).all()
        return [_to_domain(r) for r in rows]

    def list_for_stage(self, *, project_id: str, revision: int, stage_type: str) -> list[Artifact]:
        """Return the artifacts a stage produced in one revision."""
        self._owned_project(project_id)
        rows = self._session.scalars(
            select(ProjectArtifactRow)
            .where(
                ProjectArtifactRow.project_id == project_id,
                ProjectArtifactRow.revision == revision,
                ProjectArtifactRow.stage_type == stage_type,
            )
            .order_by(ProjectArtifactRow.created_at)
        ).all()
        return [_to_domain(r) for r in rows]

    def dependencies(self, artifact_id: str) -> list[Artifact]:
        """Return the artifacts this one was derived from.

        This is the evidence trace: "which evidence did this report section rest
        on" is a query rather than an investigation.
        """
        self._row(artifact_id)
        rows = self._session.scalars(
            select(ProjectArtifactRow)
            .join(
                ProjectArtifactDependencyRow,
                ProjectArtifactDependencyRow.depends_on_artifact_id
                == ProjectArtifactRow.artifact_id,
            )
            .where(ProjectArtifactDependencyRow.artifact_id == artifact_id)
            .order_by(ProjectArtifactRow.created_at)
        ).all()
        return [_to_domain(r) for r in rows]

    # -------------------------------------------------------------- lifecycle --

    def invalidate_stage(self, *, project_id: str, revision: int, stage_type: str) -> int:
        """Mark a stage's artifacts INVALIDATED. Returns the count.

        Frozen artifacts are skipped: a deliverable a client has been shown is not
        retroactively invalidated by a later edit.
        """
        self._scope.require(Permission.EDIT_STUDY)
        self._owned_project(project_id)

        rows = self._session.scalars(
            select(ProjectArtifactRow).where(
                ProjectArtifactRow.project_id == project_id,
                ProjectArtifactRow.revision == revision,
                ProjectArtifactRow.stage_type == stage_type,
                ProjectArtifactRow.status == ArtifactStatus.VALID.value,
                ProjectArtifactRow.is_frozen.is_(False),
            )
        ).all()
        for row in rows:
            row.status = ArtifactStatus.INVALIDATED.value
        self._session.flush()
        return len(rows)

    def approve(self, artifact_id: str, *, note: str = "") -> Artifact:
        """Record human sign-off on an artifact.

        Two independent checks, because either alone is insufficient:

        1. ``SIGN_OFF_DELIVERABLE`` authority, which the worker's context does not
           hold.
        2. Independence of the producer, where the scope requires it. A Researcher
           holds *both* ``EDIT_STUDY`` and ``SIGN_OFF_DELIVERABLE`` (ADR 0019), so
           the permission alone would let one person author a deliverable and clear
           its own gate.

        Self-approval is allowed by default (ADR 0019). Independent review applies
        where self-approval has been turned off for the organization, client or
        study, and then the producer may not sign off. That policy arrives on the
        :class:`StudyContext`, resolved from persisted state -- a caller cannot
        pass it in. The permission requirement is unaffected either way.

        The decision, the policy and its source are appended to
        ``approval_decisions``, so a sign-off remains reconstructible after the
        configuration changes.
        """
        self._scope.require(Permission.SIGN_OFF_DELIVERABLE)
        row = self._row(artifact_id)
        independence = require_approval_independence(
            producer_user_id=row.produced_by_user_id,
            approving_user_id=self._scope.actor_id,
            policy=self._scope.self_approval,
            what=f"artifact {row.artifact_type}",
        )
        row.is_approved = True
        self._session.add(
            ApprovalDecisionRow(
                organization_id=self._scope.organization_id,
                client_id=self._scope.client_id,
                study_id=self._scope.study_id,
                subject_type="artifact",
                subject_id=artifact_id,
                project_id=row.project_id,
                project_revision=row.revision,
                artifact_type=row.artifact_type,
                decision="APPROVED",
                comment=note,
                request_id=self._scope.request_id,
                **independence.audit_fields(),
            )
        )
        self._session.flush()
        return _to_domain(row)

    def freeze(self, artifact_id: str) -> Artifact:
        """Freeze an artifact so it can no longer be superseded in place.

        Used for simulation frozen results and approved deliverables. Freezing is
        one-way: unfreezing would let delivered work change under a client.

        Freezing is not a review decision -- it is a mechanical consequence of one
        -- so it does not carry the independence requirement that
        :meth:`approve` does.
        """
        self._scope.require(Permission.SIGN_OFF_DELIVERABLE)
        row = self._row(artifact_id)
        row.is_frozen = True
        self._session.flush()
        return _to_domain(row)

    def delete(self, artifact_id: str) -> None:
        """Delete an artifact's metadata and its object.

        The row goes first: an orphaned object is reaped later and harms nothing,
        whereas a row pointing at a deleted object would be trusted and served.
        Frozen artifacts are refused.
        """
        self._scope.require(Permission.DELETE_STUDY)
        row = self._row(artifact_id)
        if row.is_frozen:
            raise ScopeDenied("a frozen artifact cannot be deleted", reason="artifact_frozen")

        key = row.storage_key
        self._session.delete(row)
        self._session.flush()
        self._store.delete(key)

    def verify_all(self, *, project_id: str) -> dict[str, list[str]]:
        """Verify every artifact of a project against its recorded hash.

        Returns ``{"valid": [...], "corrupt": [...]}``. Intended for an operator
        integrity check, not the request path -- it reads every object.
        """
        self._owned_project(project_id)
        rows = self._session.scalars(
            select(ProjectArtifactRow).where(
                ProjectArtifactRow.project_id == project_id,
                ProjectArtifactRow.status == ArtifactStatus.VALID.value,
            )
        ).all()

        result: dict[str, list[str]] = {"valid": [], "corrupt": []}
        for row in rows:
            try:
                self._store.get(row.storage_key, expected_sha256=row.sha256)
                result["valid"].append(row.artifact_id)
            except (IntegrityError, ObjectNotFound):
                row.status = ArtifactStatus.CORRUPT.value
                result["corrupt"].append(row.artifact_id)
        if result["corrupt"]:
            self._session.flush()
        return result
