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
    content: Mapped[dict] = mapped_column(JSONType, nullable=False)
    analysis: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    changed_fields: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    impact: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

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
    artifact_metadata: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

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
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

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
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (Index("ix_access_audit_org", "organization_id", "event_id"),)
