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
    event,
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


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC timestamp, as it was written.

    ``DateTime(timezone=True)`` round-trips aware on PostgreSQL but comes back
    **naive** on SQLite, which has no timestamp type. Every value this schema writes
    is UTC (see :func:`utcnow`), so a naive read is UTC by construction. Domain
    types that refuse naive timestamps are built through this at the row boundary.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
    # The repository that owns this project, when it is not an ordinary one:
    # ``study_design`` for a Study's design project (ADR 0016). NULL is an ordinary
    # project. Part of the isolation predicate, so an owned project is invisible
    # to every repository that does not name its owner.
    owner: Mapped[str | None] = mapped_column(String(32))

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


@event.listens_for(ProjectRevisionRow, "before_update")
def _revisions_are_never_updated(_mapper: Any, _connection: Any, row: ProjectRevisionRow) -> None:
    """A revision is what a run executed; rewriting one would change history under it.

    Fires on any ORM flush that would UPDATE a revision row. A bulk ``update()``
    bypasses the ORM, which is why ``make layer_check`` forbids one.
    """
    raise RuntimeError(
        f"project revision {row.project_id} r{row.revision} is immutable; save a new one"
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
    # Self-approval policy, nullable at every level so that the hierarchy
    # *inherits* rather than duplicates: NULL means "ask my parent". The resolved
    # value reaches an approval only on a server-issued StudyContext, never as a
    # call argument. See aia_core.domain.scope.resolve_self_approval_policy.
    allow_self_approval: Mapped[bool | None] = mapped_column(Boolean)
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
    # Overrides the organization setting; NULL inherits it.
    allow_self_approval: Mapped[bool | None] = mapped_column(Boolean)
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
    # RESEARCH or SIMULATION (ADR 0015): the same object either way; only the
    # workflow beneath the study differs.
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="RESEARCH", server_default="RESEARCH"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")

    # Budget lives here because a study is what gets quoted to a client.
    # `spent_usd` is maintained from the immutable AI usage ledger, not trusted
    # as an independent figure.
    budget_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spent_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # The cost ceiling at or above which starting a run asks for confirmation. NULL: never asks.
    spend_confirm_usd: Mapped[float | None] = mapped_column(Float)

    # Most specific level of the self-approval hierarchy; NULL inherits the
    # client's setting, then the organization's, then the default of false.
    allow_self_approval: Mapped[bool | None] = mapped_column(Boolean)

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
        CheckConstraint(
            "spend_confirm_usd is null or spend_confirm_usd >= 0",
            name="study_spend_confirm_non_negative",
        ),
        CheckConstraint("spent_usd >= 0", name="study_spent_non_negative"),
        CheckConstraint(
            "status in ('DRAFT','ACTIVE','IN_REVIEW','DELIVERED','ARCHIVED','CANCELLED')",
            name="study_status_known",
        ),
        CheckConstraint("kind in ('RESEARCH','SIMULATION')", name="study_kind_known"),
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


WORKSPACE_CONTENT_STATES = (
    "EMPTY",
    "NATIVE",
    "MIGRATED",
    "RECOVERED",
    "UNRECOVERABLE",
    "AWAITING_MIGRATION",
)


class StudyWorkspaceRow(Base):
    """A research Study's workspace: its working content's state, project and lineage.

    ADR 0018, open item OI-58. The research stages keep their working content in
    the Study's *working project* (``projects.owner = study_workspace``), which is
    found only through this row -- all three scope columns, under an issued
    ``StudyContext`` -- and ``project_id`` is unique, so a working project can never
    serve two Studies.

    ``unit_project_id`` is **lineage only**: the 18.6.6 project a Study's content
    was bound to before ADR 0018, kept so the migration knows what to bring over and
    the Study keeps where its content came from. Nothing loads content by it and no
    query looks a Study up by it; it is unique, so one 18.6.6 project was never two
    Studies'. ``content_state`` names where the content stands
    (``aia_core.domain.workspace.ContentState``).
    """

    __tablename__ = "study_workspaces"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content_state: Mapped[str] = mapped_column(String(32), nullable=False)
    # The AIA working project holding the content; NULL until the Study has any.
    project_id: Mapped[str | None] = mapped_column(String(64))
    unit_project_id: Mapped[str | None] = mapped_column(String(160))
    # Migration provenance: source, source revisions and hashes, who migrated and when.
    lineage: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    # The stage the study was last opened on, for "continue where you left off".
    last_stage: Mapped[str | None] = mapped_column(String(32))
    bound_by: Mapped[str] = mapped_column(String(64), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        # RESTRICT: a Study's working content may not vanish from under its workspace.
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        UniqueConstraint("unit_project_id", name="study_workspace_unit_project_unique"),
        UniqueConstraint("project_id", name="study_workspace_project_unique"),
        CheckConstraint(
            "content_state in (" + ",".join(f"'{s}'" for s in WORKSPACE_CONTENT_STATES) + ")",
            name="content_state_known",
        ),
        # A state with content has a working project, and one without has none.
        CheckConstraint(
            "(content_state in ('NATIVE','MIGRATED','RECOVERED')) = (project_id IS NOT NULL)",
            name="content_state_matches_project",
        ),
        Index("ix_study_workspaces_client", "client_id", "modified_at"),
    )


class StudyDesignRow(Base):
    """The AIA project holding a research Study's Design Revisions (ADR 0016 decision 1).

    One per research Study, created on the first submitted design. The project's
    immutable ``project_revisions`` are the Design Revisions a run executes; the
    revision's ``revision_id`` is the Design Revision ID. Unlike
    ``study_workspaces`` this is not a bridge: it is where the design lives in AIA,
    and where the editing copy moves when OI-58 retires the unit store. Found only
    through the Study (all three scope columns); ``project_id`` is unique so a
    design project can never serve two Studies.
    """

    __tablename__ = "study_designs"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        # RESTRICT: the design a run executed may not vanish from under the run.
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        UniqueConstraint("project_id", name="study_design_project_unique"),
    )


# Client Knowledge (ADR 0015 decision 7). Client-scoped, not study-scoped: the
# narrow amendment to ADR 0004 rule 1. Every row carries organization_id and
# client_id and is reached only through ClientKnowledgeRepository, which takes an
# issued ClientContext or StudyContext; `make layer_check` forbids these tables
# anywhere else. A study never writes an item: it proposes, a person decides,
# and an approval appends a revision.

KNOWLEDGE_KINDS = (
    "SOURCE",
    "DOCUMENT",
    "DATASET",
    "FACT",
    "FINDING",
    "TERM",
    "ENTITY",
    "DIMENSION",
    "AUDIENCE",
    "ARTIFACT",
)
_KINDS_SQL = "(" + ",".join(f"'{k}'" for k in KNOWLEDGE_KINDS) + ")"


class ClientKnowledgeItemRow(Base):
    """One approved piece of a client's knowledge, at its current revision."""

    __tablename__ = "client_knowledge_items"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint(f"kind in {_KINDS_SQL}", name="knowledge_item_kind_known"),
        CheckConstraint("status in ('ACTIVE','RETIRED')", name="knowledge_item_status_known"),
        CheckConstraint("current_revision >= 1", name="knowledge_item_revision_positive"),
        Index("ix_client_knowledge_items_client", "client_id", "kind", "status"),
    )


class ClientKnowledgeRevisionRow(Base):
    """An approved revision of one item: append-only, with its provenance.

    ``context_revision`` numbers the client's knowledge as a whole: every
    approval advances it by one, so "the client context at revision N" is a
    question with one answer.
    """

    __tablename__ = "client_knowledge_revisions"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    # Where it came from: the proposal, and through it the study, project and run.
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    proposal_id: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["item_id"], ["client_knowledge_items.item_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "context_revision", name="knowledge_context_revision_unique"),
        CheckConstraint("status in ('ACTIVE','RETIRED')", name="knowledge_revision_status_known"),
    )


class ClientKnowledgeProposalRow(Base):
    """A proposed addition or change to a client's knowledge, awaiting a person.

    From a study (``study_id`` set: a finding offered for reuse) or from the
    client workspace (``study_id`` null). It changes nothing until approved.
    """

    __tablename__ = "client_knowledge_proposals"

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str | None] = mapped_column(String(64))
    # Set when the proposal revises an existing item; null for a new one.
    item_id: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PROPOSED")
    proposed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # The item revision an approval produced.
    revision: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["item_id"], ["client_knowledge_items.item_id"], ondelete="CASCADE"),
        CheckConstraint(f"kind in {_KINDS_SQL}", name="knowledge_proposal_kind_known"),
        CheckConstraint(
            "status in ('PROPOSED','APPROVED','REJECTED')", name="knowledge_proposal_status_known"
        ),
        Index("ix_client_knowledge_proposals_client", "client_id", "status"),
    )


# --------------------------------------------------------------------------- #
# Durable workflow engine: runs, steps, attempts, reservations, gates
#
# PostgreSQL is authoritative *and*, for v0.1, is the queue: workers claim
# runnable steps transactionally with `SELECT ... FOR UPDATE SKIP LOCKED`. There
# is no external broker, so there is no second place where work can be lost.
# See docs/architecture/adr/0002.
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


class ApprovalDecisionRow(Base):
    """**Append-only** record of every approval and gate decision.

    Separate from the gate and artifact rows because those hold *current* state:
    a gate keeps the decision that stands, and an artifact keeps ``is_approved``.
    Neither can answer "under what policy was this cleared, by whom, and was it
    self-approved" after the configuration has since changed.

    Every field needed to reconstruct a decision is denormalised onto the row on
    purpose. Resolving the policy again at read time would answer what the policy
    is *now*, not what it was when somebody signed off a client deliverable.
    """

    __tablename__ = "approval_decisions"

    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Scope. Denormalised so an audit query needs no join, as everywhere else.
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # What was decided on: a workflow gate or an artifact sign-off.
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Where it sat. Nullable because a gate has a run and a step while an
    # artifact has a project and a revision; neither has both.
    run_id: Mapped[str | None] = mapped_column(String(64))
    step_id: Mapped[str | None] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(64))
    project_revision: Mapped[int | None] = mapped_column(Integer)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Who, and whether the two were the same person.
    producer_user_id: Mapped[str | None] = mapped_column(String(64))
    approver_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    self_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # The policy in force at the moment of the decision, and which level set it.
    self_approval_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    self_approval_source: Mapped[str] = mapped_column(String(32), nullable=False, default="default")

    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        CheckConstraint(
            "subject_type in ('gate','artifact','budget','spend')",
            name="approval_subject_type_known",
        ),
        CheckConstraint(
            "self_approval_source in ('default','organization','client','study')",
            name="approval_self_approval_source_known",
        ),
        Index("ix_approval_decisions_study", "study_id", "decision_id"),
        Index("ix_approval_decisions_subject", "subject_type", "subject_id"),
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


class AIUsageEventRow(Base):
    """The AI usage ledger. **Append-only**: one row per ledger entry, never edited.

    Every model call writes a ``DISPATCHED`` row before it is sent and a terminal
    row after. A correction -- the resolution of an uncertain call -- is a new
    ``COMPENSATION`` row naming what it ``supersedes``, so the sum of ``cost_usd``
    over a call is the truth and the history of how it was reached survives.
    Nothing in the repository updates or deletes a row.

    The study foreign key deliberately does **not** cascade. A study with ledger
    entries cannot be deleted out from under its accounting record.

    Attribution columns are copied from the egress decision, which was computed
    from an issued ``StudyContext``; they are never taken from a request body or
    a model's output.
    """

    __tablename__ = "ai_usage_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)

    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    step_id: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(String(64))
    reservation_id: Mapped[str | None] = mapped_column(String(64))

    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    served_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    route_id: Mapped[str] = mapped_column(String(128), nullable=False)
    data_class: Mapped[str] = mapped_column(String(64), nullable=False)
    residency_zone: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))

    error_kind: Mapped[str | None] = mapped_column(String(32))
    failure_class: Mapped[str | None] = mapped_column(String(32))
    finish_reason: Mapped[str | None] = mapped_column(String(32))

    # NULL is "not reported", which is not zero.
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_input_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_input_tokens: Mapped[int | None] = mapped_column(Integer)

    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    ceiling_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    schema_fingerprint: Mapped[str | None] = mapped_column(String(80))
    input_fingerprint: Mapped[str | None] = mapped_column(String(80))
    # NULL is "not recorded" (every row before this column), never "no system prompt".
    system_prompt_sha256: Mapped[str | None] = mapped_column(String(64))
    substituted_from: Mapped[str | None] = mapped_column(String(128))
    fallback_from: Mapped[str | None] = mapped_column(String(255))
    fallback_authorised_by: Mapped[str | None] = mapped_column(String(64))

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    supersedes_event_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"]),
        ForeignKeyConstraint(["supersedes_event_id"], ["ai_usage_events.event_id"]),
        # One entry of each kind per call: one dispatch, one terminal outcome, one
        # resolution. A second of any would double-count.
        UniqueConstraint("call_id", "outcome", name="usage_call_outcome_unique"),
        CheckConstraint(
            "outcome in ('DISPATCHED','SUCCEEDED','FAILED','UNCERTAIN',"
            "'RESOLVED_BILLED','RESOLVED_NOT_BILLED')",
            name="usage_outcome_known",
        ),
        CheckConstraint(
            "cost_basis in ('SUBSCRIPTION','METERED','CEILING','COMPENSATION')",
            name="usage_cost_basis_known",
        ),
        # Only a compensating entry may reduce a total.
        CheckConstraint(
            "cost_usd >= 0 OR cost_basis = 'COMPENSATION'", name="usage_cost_non_negative"
        ),
        CheckConstraint("ceiling_usd >= 0", name="usage_ceiling_non_negative"),
        Index("ix_usage_study_time", "study_id", "occurred_at"),
        Index("ix_usage_call", "call_id"),
        Index("ix_usage_attempt", "attempt_id"),
        Index("ix_usage_provider_request", "provider_request_id"),
    )


# --------------------------------------------------------------------------- #
# Population registry
#
# Platform reference data, not client data: these rows carry no organization,
# client or study, because the population is shared by every study. What *is*
# study-scoped is which population a run used -- ``run_population_bindings`` hangs
# off ``workflow_runs`` and inherits its scope.
#
# Semantics live in ``aia_core.domain.population``; these tables only hold them.
# --------------------------------------------------------------------------- #


class PopulationDatasetVersionRow(Base):
    """One immutable, content-addressed dataset version.

    **Insert-only.** The repository has no update path for this table: a corrected
    dataset is a new version whose parent is this one. ``content_sha256`` is unique
    so the same bytes can never be registered twice, and ``(dataset_id, label)`` is
    unique so a label can never name two different byte sequences.
    """

    __tablename__ = "population_dataset_versions"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dictionary_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    field_names_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(String(128))
    storage_location: Mapped[str] = mapped_column(Text, nullable=False)
    dictionary_location: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # The full import report the version was accepted on, kept with it.
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        # No cascade: a version with descendants cannot be deleted out from under
        # them. The default NO ACTION (checked at statement end) rather than
        # RESTRICT, so one statement may still remove a whole lineage in tests.
        ForeignKeyConstraint(["parent_version_id"], ["population_dataset_versions.version_id"]),
        UniqueConstraint("dataset_id", "label", name="population_version_label"),
        CheckConstraint("byte_size > 0", name="population_version_bytes_positive"),
        CheckConstraint("row_count > 0", name="population_version_rows_positive"),
        CheckConstraint("column_count > 0", name="population_version_columns_positive"),
        CheckConstraint(
            "parent_version_id IS NULL OR parent_version_id <> version_id",
            name="population_version_not_own_parent",
        ),
        Index("ix_population_versions_dataset", "dataset_id", "imported_at"),
    )


class PopulationRow(Base):
    """A named population (STATIC or LIVE) and the version it resolves to.

    ``current_version_id`` is the single authority for "which version is in use"
    (R4). It moves only through the registry's compare-and-set promotion, and a
    STATIC row has no path that moves it at all.
    """

    __tablename__ = "populations"

    population_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    current_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    established_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    established_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["current_version_id"], ["population_dataset_versions.version_id"]),
        CheckConstraint("kind in ('STATIC','LIVE')", name="population_kind_known"),
        # One STATIC and one LIVE per dataset.
        UniqueConstraint("dataset_id", "kind", name="population_one_per_kind"),
    )


class PopulationPromotionRow(Base):
    """**Append-only** history of every establish and promote.

    ``from_version_id`` is NULL for the establishing entry. A version that appears
    here as a target but is no longer current is SUPERSEDED -- derived from this
    table, never stored as a status that could disagree with it.
    """

    __tablename__ = "population_promotions"

    promotion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    population_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version_id: Mapped[str | None] = mapped_column(String(128))
    to_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["population_id"], ["populations.population_id"]),
        ForeignKeyConstraint(["to_version_id"], ["population_dataset_versions.version_id"]),
        Index("ix_population_promotions_population", "population_id", "promoted_at"),
    )


class RunPopulationBindingRow(Base):
    """The population a workflow run is computed over. One per run, never updated.

    Every field of the domain ``PopulationBinding`` is denormalised here, so the
    record still says exactly what the run used after any later promotion. The
    version foreign key does not cascade: a version a run was computed over cannot
    be deleted.
    """

    __tablename__ = "run_population_bindings"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    population_id: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_role: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_column: Mapped[str] = mapped_column(String(128), nullable=False)
    view: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Which claim rules and which certificate the run was computed under.
    dictionary_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    field_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    companion_set_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    joint_state: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["version_id"], ["population_dataset_versions.version_id"]),
        CheckConstraint(
            "resolution in ('LIVE_CURRENT','STATIC_REFERENCE','PINNED')",
            name="run_population_resolution_known",
        ),
        CheckConstraint("view in ('BASE','ANALYSIS')", name="run_population_view_known"),
        CheckConstraint(
            "joint_state in "
            "('CERTIFIED','NOT_THIS_PANEL','UNKNOWN_STATUS','UNPARSEABLE','MISSING')",
            name="run_population_joint_state_known",
        ),
        Index("ix_run_population_version", "version_id"),
    )


class PopulationCompanionSetRow(Base):
    """The validated companion set of one dataset version. **Insert-once.**

    A version is usable only with its complete companion set, when its contract
    declares one. The set is attached once -- at import or afterwards -- and never
    replaced: a different set is a different version's business. ``report_json``
    keeps every companion check and the joint-certificate evaluation it passed on.
    """

    __tablename__ = "population_companion_sets"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    set_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    joint_state: Mapped[str] = mapped_column(String(32), nullable=False)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attached_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["population_dataset_versions.version_id"]),
        CheckConstraint(
            "joint_state in "
            "('CERTIFIED','NOT_THIS_PANEL','UNKNOWN_STATUS','UNPARSEABLE','MISSING')",
            name="population_companion_joint_state_known",
        ),
    )


class PopulationCompanionAssetRow(Base):
    """One companion asset of a version: its identity and where its bytes live."""

    __tablename__ = "population_companion_assets"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["population_companion_sets.version_id"]),
        CheckConstraint("byte_size > 0", name="population_companion_bytes_positive"),
    )


class PromptVersionRow(Base):
    """One stored edit of a system prompt's instruction. Immutable (ADR 0020).

    A version is never updated or deleted: a change is a new row, so what a run was
    queued with can always be read back. ``version_number`` counts per organization
    and prompt from 1; the baseline (the wording shipped in code) is not a row.
    """

    __tablename__ = "ai_prompt_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # What this was edited from: "baseline" or an earlier version label. Context for
    # a reader, not a constraint -- a version never depends on another's row.
    based_on: Mapped[str] = mapped_column(String(64), nullable=False, default="baseline")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    # The author's recorded declaration that this text holds no client data (ADR 0020
    # decision 8): the class they declared, who, and when. NULL on a version saved before
    # declarations existed -- "no declaration", never "declared" -- so such a version has no
    # class until an operator gives it one.
    declared_class: Mapped[str | None] = mapped_column(String(64))
    declared_by: Mapped[str | None] = mapped_column(String(64))
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "prompt_id", "version_number", name="uq_ai_prompt_version"
        ),
        CheckConstraint("version_number >= 1", name="ai_prompt_version_positive"),
        Index("ix_ai_prompt_versions_prompt", "organization_id", "prompt_id", "version_number"),
    )


class PromptActivationRow(Base):
    """Which version an organization runs for a prompt. Append-only.

    The active version is the newest row for the prompt. ``version_number`` NULL means
    the baseline wording in code: rolling back is a new row, never a delete, so the
    history of what ran is complete. A queued job does not read this table: it was
    given its pin when it was queued.
    """

    __tablename__ = "ai_prompt_activations"

    activation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer)
    activated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "prompt_id", "version_number"],
            [
                "ai_prompt_versions.organization_id",
                "ai_prompt_versions.prompt_id",
                "ai_prompt_versions.version_number",
            ],
        ),
        Index("ix_ai_prompt_activations_prompt", "organization_id", "prompt_id", "activation_id"),
    )
