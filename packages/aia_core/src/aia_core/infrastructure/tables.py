"""SQLAlchemy table definitions for the durable project graph.

PostgreSQL is the production store. The column types are declared portably --
``JSONB`` on PostgreSQL, ``JSON`` elsewhere -- so the same schema and the same
repository code run against SQLite in unit tests. Tests that depend on
PostgreSQL-specific behaviour are marked ``postgres`` and run in CI.

Design notes:

* A revision is immutable. There is no ``UPDATE`` path for ``project_revisions``
  or ``project_artifacts`` content; corrections create a new revision.
* Stages are stored per ``(project_id, revision)``, not per project, because
  "what was the state of stage X at revision N" is a question the product asks.
* Artifact *bytes* never live here. This table holds metadata and a storage key;
  the blob lives in object storage. See ``docs/architecture/artifacts.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Explicit naming convention so Alembic generates stable, reviewable constraint
# names instead of database-assigned ones.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Portable JSON: JSONB on PostgreSQL (indexable, binary) and JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    """Return an aware UTC timestamp.

    Timestamps are always timezone-aware. The prototype stored naive local-time
    strings, which made cross-timezone scheduling and audit ordering ambiguous.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base carrying the shared metadata and naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ProjectRow(Base):
    """Mutable project header. Content lives in revisions, not here."""

    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    project_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    last_completed_stage: Mapped[str | None] = mapped_column(String(64))
    parent_project_id: Mapped[str | None] = mapped_column(String(64))

    # Ownership and isolation. Every client-derived object resolves to a client
    # and a study; see docs/architecture/scope-and-authorization.md. client_id is
    # denormalised next to study_id deliberately, so the isolation predicate is a
    # single condition on this row and needs no join -- a missed join is exactly
    # how cross-tenant leaks happen.
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64))

    preferred_provider: Mapped[str] = mapped_column(
        String(64), nullable=False, default="claude_code_subscription"
    )
    provider_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CLAUDE_CODE_ONLY"
    )
    max_api_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    revisions: Mapped[list[ProjectRevisionRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint("current_revision >= 0", name="current_revision_non_negative"),
        CheckConstraint("max_api_cost_usd >= 0", name="budget_non_negative"),
        CheckConstraint("project_type in ('research','simulation')", name="project_type_known"),
        # Portfolio listing is the hottest read path: newest first, within a
        # study, excluding archived and trashed rows.
        Index("ix_projects_study_modified", "study_id", "modified_at"),
        Index("ix_projects_client_modified", "client_id", "modified_at"),
        Index("ix_projects_org_status", "organization_id", "status"),
    )


class ProjectRevisionRow(Base):
    """An immutable content snapshot of a project.

    ``content_sha256`` is unique per ``(project_id, revision)`` and is the
    deduplication key: an autosave matching the current revision's hash creates no
    new row.
    """

    __tablename__ = "project_revisions"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    parent_revision: Mapped[int | None] = mapped_column(Integer)
    branch_id: Mapped[str | None] = mapped_column(String(64))

    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    changed_fields: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    impact: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="autosave")
    questionnaire_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    panel_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    created_by: Mapped[str | None] = mapped_column(String(64))

    project: Mapped[ProjectRow] = relationship(back_populates="revisions")
    stages: Mapped[list[ProjectStageRow]] = relationship(
        back_populates="revision_row", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="revision_starts_at_one"),
        Index("ix_project_revisions_sha", "project_id", "content_sha256"),
    )


class ProjectStageRow(Base):
    """One stage's durable state within one revision."""

    __tablename__ = "project_stages"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_type: Mapped[str] = mapped_column(String(64), primary_key=True)

    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # The reuse key: artifacts are valid only while the stage's material inputs
    # still hash to this value.
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    current_job_id: Mapped[str | None] = mapped_column(String(64))
    last_checkpoint: Mapped[str | None] = mapped_column(Text)
    waiting_reason: Mapped[str | None] = mapped_column(String(128))
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_ids: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    revision_row: Mapped[ProjectRevisionRow] = relationship(back_populates="stages")

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "revision"],
            ["project_revisions.project_id", "project_revisions.revision"],
            ondelete="CASCADE",
        ),
        Index("ix_project_stages_lookup", "project_id", "revision", "ordinal"),
    )


class ProjectArtifactRow(Base):
    """Metadata and provenance for one produced artifact.

    The bytes live in object storage under ``storage_key``. ``sha256`` is verified
    on read so a silently corrupted or replaced object is detected rather than
    served as valid research output.
    """

    __tablename__ = "project_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)

    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False, default="application/json"
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VALID")

    # Provenance. Every generated output must be able to answer "what produced
    # this, from what inputs, on which provider and model".
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    produced_by_job_id: Mapped[str | None] = mapped_column(String(64))
    # Who produced this. Required for the separation-of-duties check on approval:
    # producer_user_id != approving_user_id. Written from the authorised scope,
    # never from a caller argument, so it cannot be spoofed to defeat the check.
    produced_by_user_id: Mapped[str | None] = mapped_column(String(64))
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )

    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        # The artifact-reuse lookup: "is there a valid artifact of this type for
        # this stage with this exact input fingerprint?"
        Index(
            "ix_artifacts_reuse",
            "project_id",
            "stage_type",
            "artifact_type",
            "input_fingerprint",
        ),
        Index("ix_artifacts_revision", "project_id", "revision", "stage_type"),
    )


class ProjectArtifactDependencyRow(Base):
    """Edge in the artifact dependency graph, for evidence tracing."""

    __tablename__ = "project_artifact_dependencies"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    depends_on_artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id"], ["project_artifacts.artifact_id"], ondelete="CASCADE"
        ),
    )


class ProjectEventRow(Base):
    """Append-only project history and audit trail.

    Never updated or deleted. This is what answers "why did project X stop during
    stage Y" without opening files on a server.
    """

    __tablename__ = "project_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int | None] = mapped_column(Integer)
    stage_type: Mapped[str | None] = mapped_column(String(64))

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    actor_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        Index("ix_project_events_project", "project_id", "event_id"),
    )


class ProviderEventRow(Base):
    """Audited record of provider usage and every provider switch.

    ``explicit_user_action`` is the field that proves the no-silent-fallback rule
    was honoured: a switch with this false and a cost attached is a bug.
    """

    __tablename__ = "project_provider_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int | None] = mapped_column(Integer)
    stage_type: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(String(64))

    from_provider: Mapped[str | None] = mapped_column(String(64))
    to_provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    explicit_user_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        UniqueConstraint("project_id", "event_id", name="provider_event_unique"),
        Index("ix_provider_events_project", "project_id", "created_at"),
    )


# --------------------------------------------------------------------------- #
# Scope: organizations, users, clients, studies and grants
# --------------------------------------------------------------------------- #


class OrganizationRow(Base):
    """The AIA team. The outermost tenant boundary."""

    __tablename__ = "organizations"

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class UserRow(Base):
    """A person who can sign in.

    ``external_subject`` is the identity provider's immutable subject claim
    (Cognito ``sub``). It is stored separately from ``user_id`` so that changing
    identity provider does not rewrite every foreign key in the database, and so
    that an email change does not orphan a user's work.
    """

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_users_subject", "external_subject"),)


class OrganizationMemberRow(Base):
    """A user's membership of an organization, with an administrative role."""

    __tablename__ = "organization_members"

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="MEMBER")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        CheckConstraint("role in ('OWNER','ADMIN','MEMBER')", name="org_role_known"),
        Index("ix_org_members_user", "user_id"),
    )


class ClientRow(Base):
    """A paying client. A hard confidentiality boundary."""

    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    reference: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        # A slug is unique per organization, not globally: two organizations may
        # each have a client called "acme".
        UniqueConstraint("organization_id", "slug", name="client_slug_unique"),
        CheckConstraint("status in ('ACTIVE','DORMANT','ARCHIVED')", name="client_status_known"),
        Index("ix_clients_org", "organization_id", "status"),
    )


class StudyRow(Base):
    """One client engagement: the unit of budget, delivery and access."""

    __tablename__ = "studies"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")

    # Budget lives here because a study is what gets quoted to a client.
    # `spent_usd` is maintained from the immutable AI usage ledger, not trusted
    # as an independent figure.
    budget_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spent_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "slug", name="study_slug_unique"),
        CheckConstraint("budget_usd >= 0", name="study_budget_non_negative"),
        CheckConstraint("spent_usd >= 0", name="study_spent_non_negative"),
        CheckConstraint(
            "status in ('DRAFT','ACTIVE','IN_REVIEW','DELIVERED','ARCHIVED','CANCELLED')",
            name="study_status_known",
        ),
        Index("ix_studies_client", "client_id", "status"),
        Index("ix_studies_org_modified", "organization_id", "modified_at"),
    )


class ClientGrantRow(Base):
    """A user's role on a client, applying to all of that client's studies."""

    __tablename__ = "client_grants"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        CheckConstraint(
            "role in ('VIEWER','REVIEWER','RESEARCHER','LEAD')", name="client_grant_role_known"
        ),
        Index("ix_client_grants_user", "user_id"),
    )


class StudyGrantRow(Base):
    """A user's role on one study. Authoritative over a client grant."""

    __tablename__ = "study_grants"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        CheckConstraint(
            "role in ('VIEWER','REVIEWER','RESEARCHER','LEAD')", name="study_grant_role_known"
        ),
        Index("ix_study_grants_user", "user_id"),
    )


class AccessAuditRow(Base):
    """Append-only record of access grants, revocations and denials.

    Grants are security-relevant: an administrator granting themselves access to a
    client is legitimate but must be visible afterwards. Denials are recorded too,
    because a pattern of denials is a signal.
    """

    __tablename__ = "access_audit"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(64))
    study_id: Mapped[str | None] = mapped_column(String(64))
    subject_user_id: Mapped[str | None] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(64))

    action: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Structured before/after record. A grant audit entry must be readable years
    # later without reconstructing what the roles were at the time.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (Index("ix_access_audit_org", "organization_id", "event_id"),)


# --------------------------------------------------------------------------- #
# Durable workflow engine: runs, steps, attempts, reservations, gates
#
# PostgreSQL is authoritative. SQS carries an identifier, never state, so losing
# the queue loses no work. See docs/architecture/adr/0002.
# --------------------------------------------------------------------------- #


class WorkflowRunRow(Base):
    """One execution of a pipeline against a project revision.

    Carries business state -- what a researcher is waiting for -- and the scope
    every client-derived object must resolve to.
    """

    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Scope. Denormalised so the isolation predicate needs no join, exactly as
    # for projects.
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # Idempotency at the run level: re-submitting the same logical run returns the
    # existing one rather than starting a second, duplicate pipeline.
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[StepRunRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        CheckConstraint("project_revision >= 1", name="run_revision_positive"),
        Index("ix_runs_study", "study_id", "created_at"),
        Index("ix_runs_status", "status", "priority"),
    )


class StepRunRow(Base):
    """One pipeline node within one run. The record that a step is done."""

    __tablename__ = "step_runs"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)

    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="BLOCKED")
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    stage_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    artifact_target: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    interaction_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")

    # The artifact-reuse key. A step whose inputs still hash to this may reuse its
    # previous artifacts instead of recomputing.
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Two counters, because one cannot serve both purposes.
    #
    # `attempts_recorded` is monotonic and never decremented: it numbers the
    # append-only StepAttempt rows, so attempt 3 is always attempt 3.
    #
    # `attempts_consumed` counts only failures that should count against
    # `max_attempts`. A quota park, a budget park and a gate do not consume an
    # attempt -- none is a failure of the work -- so this can be lower than
    # `attempts_recorded`, and it is what the retry limit is checked against.
    attempts_recorded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Set when a step is parked. `runnable_after` is how a quota park becomes a
    # resume: the reconciler will not consider the step before this instant.
    waiting_reason: Mapped[str | None] = mapped_column(String(128))
    runnable_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[WorkflowRunRow] = relationship(back_populates="steps")
    attempts: Mapped[list[StepAttemptRow]] = relationship(
        back_populates="step", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        UniqueConstraint("run_id", "node_key", name="step_node_unique"),
        CheckConstraint("max_attempts >= 1", name="step_max_attempts_positive"),
        CheckConstraint("attempts_recorded >= 0", name="step_attempts_recorded_non_negative"),
        CheckConstraint("attempts_consumed >= 0", name="step_attempts_consumed_non_negative"),
        # The claim query: runnable steps, by priority then creation order.
        Index("ix_steps_claimable", "status", "runnable_after", "priority"),
        Index("ix_steps_run", "run_id", "ordinal"),
    )


class StepDependencyRow(Base):
    """An edge in a run's DAG."""

    __tablename__ = "step_dependencies"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    depends_on_step_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(["step_id"], ["step_runs.step_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["depends_on_step_id"], ["step_runs.step_id"], ondelete="CASCADE"),
        Index("ix_step_deps_reverse", "depends_on_step_id"),
    )


class StepAttemptRow(Base):
    """One execution attempt. **Append-only history, never overwritten.**

    The prototype kept a counter and only the latest error. Each attempt now has
    its own row, so a step that failed three different ways retains all three --
    with each attempt's provider, model, cost and timing.
    """

    __tablename__ = "step_attempts"

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    # Lease. `lease_until` is the deadline a reconciler compares against; a
    # CLAIMED or EXECUTING attempt with no deadline is treated as expired.
    worker_id: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Whether a metered provider call was dispatched, and whether its outcome is
    # known. Together these decide whether a lapsed attempt may be retried or
    # must become RECOVERY_REQUIRED -- the double-billing guard.
    paid_call_dispatched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_call_outcome_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))

    failure_class: Mapped[str | None] = mapped_column(String(32))
    error_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    step: Mapped[StepRunRow] = relationship(back_populates="attempts")

    __table_args__ = (
        ForeignKeyConstraint(["step_id"], ["step_runs.step_id"], ondelete="CASCADE"),
        UniqueConstraint("step_id", "attempt_number", name="attempt_number_unique"),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint("estimated_cost_usd >= 0", name="attempt_estimate_non_negative"),
        CheckConstraint("actual_cost_usd >= 0", name="attempt_actual_non_negative"),
        Index("ix_attempts_step", "step_id", "attempt_number"),
        # The reconciler's query: live leases past their deadline.
        Index("ix_attempts_lease", "status", "lease_until"),
    )


class BudgetReservationRow(Base):
    """A hold against a study's budget for one attempt.

    Reservations count as spent so that concurrent workers cannot each pass the
    budget check and collectively overspend. ``SETTLED_UNCERTAIN`` is the state a
    reservation enters when a paid call's billing status cannot be determined.
    """

    __tablename__ = "budget_reservations"

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    step_id: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(String(64))

    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    settled_amount_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESERVED")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        CheckConstraint("amount_usd >= 0", name="reservation_amount_non_negative"),
        CheckConstraint(
            "status in ('RESERVED','SETTLED','RELEASED','SETTLED_UNCERTAIN')",
            name="reservation_status_known",
        ),
        # The outstanding-reservation sum, used by every budget check.
        Index("ix_reservations_study_status", "study_id", "status"),
        Index("ix_reservations_attempt", "attempt_id"),
    )


class WorkflowGateRow(Base):
    """A human decision a run is waiting on.

    Distinct from a step status: the gate carries the question, the permitted
    options and the decision, and it survives a deploy because it may sit
    unanswered for days.
    """

    __tablename__ = "workflow_gates"

    gate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False, default="approval")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    decision_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    # Who produced the work under review, and who decided. The
    # separation-of-duties invariant is producer != decider.
    produced_by_user_id: Mapped[str | None] = mapped_column(String(64))
    decided_by_user_id: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["step_id"], ["step_runs.step_id"], ondelete="CASCADE"),
        CheckConstraint(
            "status in ('PENDING','DECIDED','CANCELLED','EXPIRED')",
            name="gate_status_known",
        ),
        Index("ix_gates_pending", "run_id", "status"),
    )


class WorkflowEventRow(Base):
    """Append-only run history and the progress feed.

    Monotonic ``event_id`` is what lets a reconnecting client resume without gaps
    or duplicates.
    """

    __tablename__ = "workflow_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(String(64))

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        Index("ix_workflow_events_run", "run_id", "event_id"),
    )
