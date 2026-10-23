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
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..domain.approval_ledger import subject_check_sql
from ..domain.edit_log import ActorKind, OpSource
from ..domain.wallet import ChargeKind

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
    # NULL only for a client-owned project (``client_sources``, client-budget CB2): work on
    # the client itself, paid by the client's own budget; never an ordinary project.
    study_id: Mapped[str | None] = mapped_column(String(64))
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
        # A project belongs to a study, except the client's own (client-budget CB2).
        CheckConstraint(
            "(study_id is null) = (coalesce(owner, '') = 'client_sources')",
            name="project_study_unless_client_owned",
        ),
        # Portfolio listing is the hottest read path: newest first, within a
        # study, excluding archived and trashed rows.
        Index("ix_projects_study_modified", "study_id", "modified_at"),
        Index("ix_projects_client_modified", "client_id", "modified_at"),
        Index("ix_projects_org_status", "organization_id", "status"),
        # One project of the client's own work per client: two first requests at once
        # cannot both create one (client-budget CB3b).
        Index(
            "uq_projects_client_work",
            "client_id",
            unique=True,
            postgresql_where=text("owner = 'client_sources'"),
            sqlite_where=text("owner = 'client_sources'"),
        ),
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
    # Deactivated in this organization (D-27, settings-backends SB2): the member resolves no
    # scope here while set; their membership elsewhere and the account are untouched.
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_by: Mapped[str | None] = mapped_column(String(64))
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
    # The profile (client-workspace C5). Empty is "not filled in".
    short_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="", server_default=""
    )
    industry: Mapped[str] = mapped_column(
        String(120), nullable=False, default="", server_default=""
    )
    market: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # The client's own budget (client-budget CB1): what work on the client itself may
    # cost, never its studies'. 0 until a person sets it, so client AI work waits for one.
    # `spent_usd` is maintained from settled holds, never set by hand.
    budget_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    spent_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    # The bound on every open wallet of the client's studies (ADR 0028 decision 1, lead-
    # orchestration LO1): set by an organization OWNER or ADMIN; NULL means a wallet may not
    # exceed its study's budget. Spends nothing itself.
    wallet_ceiling_usd: Mapped[float | None] = mapped_column(Float)
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
        CheckConstraint("budget_usd >= 0", name="client_budget_non_negative"),
        CheckConstraint("spent_usd >= 0", name="client_spent_non_negative"),
        CheckConstraint(
            "wallet_ceiling_usd is null or wallet_ceiling_usd >= 0",
            name="client_wallet_ceiling_non_negative",
        ),
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


class StudyDesignSourceRow(Base):
    """Where a research Study's design came from, when it was reused. **Insert-once.**

    Project memory M3 (plans/project-memory-reuse.md): a past study's design may start a new
    or empty research Study of the same client. The citation belongs to the Study, not to one
    revision -- every later revision descends from the reused one -- and is found only
    through the Study (all three scope columns). ``labels`` are derived by one rule from every
    run of the source revision (``aia_core.domain.design_reuse``) and keep the run and report
    artifact ids they were read from. The source columns are a record, not a reference: no
    foreign key, so the citation stays what it was whatever later happens to the source.
    Written only by ``StudyDesignRepository``.
    """

    __tablename__ = "study_design_sources"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The target's first Design Revision: the reused design itself.
    revision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint("source_study_id <> study_id", name="study_design_source_not_itself"),
    )


class StudyLeadTurnRow(Base):
    """One turn of a researcher's conversation with their Research Lead in a Study.
    **Append-only.**

    ADR 0026 decision 8, per researcher (the product owner, 2026-10-19): a Study has one
    conversation per researcher, keyed by ``(study_id, user_id)``, numbered by
    ``sequence_no``. A person's turn holds their message; a Lead turn names the
    ``research_lead`` run that answers it, and its reply is read from that run's step
    output, never copied here. Read and written only by ``StudyLeadRepository``, under an
    issued ``StudyContext`` and always for the calling researcher.
    """

    __tablename__ = "study_lead_turns"

    turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The researcher whose conversation this is.
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    focus: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    run_id: Mapped[str | None] = mapped_column(String(64))
    workspace_revision: Mapped[int | None] = mapped_column(Integer)
    design_revision_id: Mapped[str | None] = mapped_column(String(64))
    #: The typed start the server matched in a person's message (lead-orchestration LO5,
    #: ``domain/lead_commands.py``), or NULL. Only a person's turn names one.
    command: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        UniqueConstraint("study_id", "user_id", "sequence_no", name="study_lead_turn_sequence"),
        # A typed command is a person's: the Lead's model never names a start (D22).
        CheckConstraint(
            "command IS NULL OR actor = 'person'", name="study_lead_turn_command_is_a_persons"
        ),
        CheckConstraint("actor in ('person','lead')", name="study_lead_turn_actor_known"),
        CheckConstraint("kind in ('message','greeting')", name="study_lead_turn_kind_known"),
        CheckConstraint("sequence_no >= 1", name="study_lead_turn_sequence_positive"),
        # A Lead turn is answered by its run; a person's turn names none.
        CheckConstraint(
            "(actor = 'lead') = (run_id IS NOT NULL)", name="study_lead_turn_run_iff_lead"
        ),
        CheckConstraint(
            "text IS NULL OR length(text) <= 4000", name="study_lead_turn_text_bounded"
        ),
        Index("ix_study_lead_turns_actor", "organization_id", "user_id", "created_at"),
    )


@event.listens_for(StudyLeadTurnRow, "before_update")
def _lead_turns_are_never_updated(_mapper: Any, _connection: Any, row: StudyLeadTurnRow) -> None:
    """A turn is what was said; the conversation is append-only (ADR 0026 decision 8)."""
    raise RuntimeError(f"lead turn {row.turn_id} is immutable; append a new one")


class ResearcherLeadRow(Base):
    """A researcher's own Research Lead, hatched once per organization and user.

    The product owner, 2026-10-19: a personal agent attached to the account, OpenClaw-style
    files -- ``name``, ``soul`` (its personality and working style, markdown) and
    ``user_profile`` (what it knows of how this researcher works, markdown). The researcher
    reads them; they change only through the Lead's ``self_update`` in chat, each change's
    previous text kept in ``researcher_lead_revisions``. Read and written only by
    ``ResearcherLeadRepository``, always for the calling researcher.
    """

    __tablename__ = "researcher_leads"

    lead_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    soul: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    #: The researcher's standing choice to have the Lead's text edits accepted without a click
    #: (plan inline-decisions chunk 2). Off unless they turn it on.
    auto_accept_text_edits: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Sealed when its researcher's membership is deactivated (ADR 0030, settings-backends SB2):
    #: from then no route or worker reads it, the researcher included, until a reactivation
    #: before ``erase_after`` unseals it; after that date the retention sweep erases it.
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erase_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        UniqueConstraint("organization_id", "user_id", name="researcher_lead_once"),
        Index("ix_researcher_leads_erase_after", "erase_after"),
        CheckConstraint("length(soul) <= 2000", name="researcher_lead_soul_bounded"),
        CheckConstraint("length(user_profile) <= 2000", name="researcher_lead_user_bounded"),
    )


class ResearcherLeadRevisionRow(Base):
    """One change to a Lead's file, with the text it replaced. **Insert-once.**

    So a change can be shown and reverted later, through chat. ``field`` is ``name``,
    ``soul`` or ``user``; ``source_turn_id`` is the Lead turn that made it.
    """

    __tablename__ = "researcher_lead_revisions"

    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str] = mapped_column(String(16), nullable=False)
    previous: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_turn_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["lead_id"], ["researcher_leads.lead_id"], ondelete="CASCADE"),
        CheckConstraint("field in ('name','soul','user')", name="researcher_lead_field_known"),
        Index("ix_researcher_lead_revisions_lead", "lead_id", "created_at"),
    )


@event.listens_for(ResearcherLeadRevisionRow, "before_update")
def _lead_revisions_are_never_updated(
    _mapper: Any, _connection: Any, row: ResearcherLeadRevisionRow
) -> None:
    """The record of what a file said before; never rewritten."""
    raise RuntimeError(f"lead revision {row.revision_id} is immutable")


class ResearcherLeadMemoryRow(Base):
    """One note in a Lead's memory. Append-only: forgetting sets ``forgotten_at``.

    ``scope`` is ``personal`` (working style and preferences, loaded into every turn of
    this researcher) or ``client`` (``client_id`` required: loaded only into a turn of that
    client's study, by the query, never by the prompt). Written by the Lead's
    ``self_update`` (``created_by = 'lead'``) through ``ResearcherLeadRepository``.
    """

    __tablename__ = "researcher_lead_memories"

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    source_turn_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    forgotten_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["lead_id"], ["researcher_leads.lead_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint("scope in ('personal','client')", name="researcher_lead_memory_scope"),
        # A client note names its client; a personal note names none.
        CheckConstraint(
            "(scope = 'client') = (client_id IS NOT NULL)",
            name="researcher_lead_memory_client_iff_scope",
        ),
        CheckConstraint(
            "created_by in ('lead','person')", name="researcher_lead_memory_author_known"
        ),
        Index("ix_researcher_lead_memories_lead", "lead_id", "created_at"),
    )


class HoldoutPreregistrationRow(Base):
    """A validation Study's preregistration (panel-grounded-respondents 7a, 7e2). **Insert-once.**

    One per Study, fixed before its confirmation run's first call: the record's canonical JSON
    bytes, kept as written so the hash read back is the hash stored, beside the respondent
    system it validates. Written and read only by ``HoldoutRepository``, through the Study.
    """

    __tablename__ = "holdout_preregistrations"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    respondent_system_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    population_version: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        Index(
            "ix_holdout_preregistrations_system", "organization_id", "respondent_system_fingerprint"
        ),
    )


class HoldoutConfirmationRow(Base):
    """A validation Study's confirmation run, started (panel-grounded-respondents 7e3).
    **Insert-once.**

    A respondent system is confirmed once in an organization: the unique constraint refuses a
    second Study's confirmation of the same fingerprint, so several preregistrations of one
    system cannot each be run and the passing one kept. Written and read only by
    ``HoldoutRepository``.
    """

    __tablename__ = "holdout_confirmations"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    respondent_system_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    preregistration_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_by: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["study_id"], ["holdout_preregistrations.study_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint(
            "organization_id",
            "respondent_system_fingerprint",
            name="holdout_confirmation_once_per_system",
        ),
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


class ClientContactRow(Base):
    """A person at a client (client-workspace C5): on the client record, read by no model."""

    __tablename__ = "client_contacts"

    contact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    receives_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        Index("ix_client_contacts_client", "client_id"),
    )


class ClientSourceRow(Base):
    """A client's stored original (lifecycle K2a): one per client and SHA-256.

    The bytes and the reading are objects in the artifact store under the client's
    prefix (``storage_key``, ``reading_key``); this row is what AIA knows of them. A
    source is not knowledge: no study context reads it.
    """

    __tablename__ = "client_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    family: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    reading_key: Mapped[str | None] = mapped_column(String(512))
    reading_sha256: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64))
    reader: Mapped[str | None] = mapped_column(String(32))
    characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    #: A person marked it "Interní dokument" (an internal AIA document, Class C by the owner's
    #: rule of 2026-10-19): who and when, both null while it is the client's (Class A).
    internal_marked_by: Mapped[str | None] = mapped_column(String(64))
    internal_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "sha256", name="client_source_sha_unique"),
        CheckConstraint(
            "(internal_marked_by is null) = (internal_marked_at is null)",
            name="internal_mark_whole",
        ),
    )


class ClientSourceOccurrenceRow(Base):
    """One time someone added a client's source: the name it came under, who, when."""

    __tablename__ = "client_source_occurrences"

    occurrence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    added_by: Mapped[str] = mapped_column(String(64), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["source_id"], ["client_sources.source_id"], ondelete="CASCADE"),
        Index("ix_client_source_occurrences_source", "source_id"),
        Index("ix_client_source_occurrences_client", "client_id", "added_at"),
    )


class ClientKnowledgeFolderRow(Base):
    """A folder of one client's knowledge (client-workspace C3): organization, not knowledge."""

    __tablename__ = "client_knowledge_folders"

    folder_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # The name as compared: two folders of one client may not share it.
    name_key: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "name_key", name="uq_client_knowledge_folders_name"),
    )


class ClientKnowledgeLabelRow(Base):
    """A label of one client's knowledge (client-workspace C3): organization, not knowledge."""

    __tablename__ = "client_knowledge_labels"

    label_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_key: Mapped[str] = mapped_column(String(80), nullable=False)
    colour: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "name_key", name="uq_client_knowledge_labels_name"),
        CheckConstraint(
            "colour in ('BLUE','TEAL','GREEN','ORANGE','VIOLET','SLATE')",
            name="knowledge_label_colour_known",
        ),
    )


class ClientKnowledgeItemFolderRow(Base):
    """Which folder an item is filed in, if any.

    Kept apart from the item row on purpose: filing is not a change to the
    knowledge, so it must not touch the item's ``modified_at`` or revision. The
    row goes with its folder (an item then has no folder) and with its item.
    """

    __tablename__ = "client_knowledge_item_folders"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    folder_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["item_id"], ["client_knowledge_items.item_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["folder_id"], ["client_knowledge_folders.folder_id"], ondelete="CASCADE"
        ),
        Index("ix_client_knowledge_item_folders_folder", "folder_id"),
    )


class ClientKnowledgeItemLabelRow(Base):
    """One label on one item; both of the same client."""

    __tablename__ = "client_knowledge_item_labels"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["item_id"], ["client_knowledge_items.item_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["label_id"], ["client_knowledge_labels.label_id"], ondelete="CASCADE"
        ),
        Index("ix_client_knowledge_item_labels_label", "label_id"),
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


class ClientKnowledgeSelectionRow(Base):
    """One item chosen for one study at one revision (lifecycle K4, "use in this study").

    A study holds at most one selection per item; choosing again replaces it. The revision is
    an exact revision of the item, never "whichever is current". The row goes with its study
    and with its item.
    """

    __tablename__ = "client_knowledge_selections"

    study_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_by: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        # The exact revision chosen; it goes with its item (a revision goes with its item).
        ForeignKeyConstraint(
            ["item_id", "revision"],
            ["client_knowledge_revisions.item_id", "client_knowledge_revisions.revision"],
            ondelete="CASCADE",
        ),
        CheckConstraint("revision >= 1", name="knowledge_selection_revision_positive"),
        Index("ix_client_knowledge_selections_item", "item_id"),
    )


class FieldworkJournalRow(Base):
    """One answered respondent block of a research run's fieldwork, kept the moment it returns.

    Keyed by the study, the run's lineage (the run a retry chain began with) and a fingerprint
    of exactly what was sent, so an interrupted attempt or a retry of the run replays what was
    answered and pays only for what was not (run-qc-and-checkpoint RQC0, OI-64). Written once;
    ``run_id`` names the run that paid for it.
    """

    __tablename__ = "fieldwork_journal"

    journal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lineage_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        UniqueConstraint(
            "study_id", "lineage_run_id", "request_key", name="fieldwork_journal_request"
        ),
    )


class ClientWorkJournalRow(Base):
    """One answered model request of the client's own work, kept the moment it returns.

    Keyed by the client and a fingerprint of exactly what was sent, so a step resumed
    after a budget lift or a worker's release -- or a new run over the same reading --
    replays what was answered and pays only for what was not (lifecycle K2d). Written
    once; ``run_id`` names the run that paid for it.
    """

    __tablename__ = "client_work_journal"

    journal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        UniqueConstraint("client_id", "request_key", name="client_work_journal_request"),
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
    # The item revision a revising proposal was written from (F-K1); null for a new item and
    # for a revision filed before this column, which an approval treats as stale.
    base_revision: Mapped[int | None] = mapped_column(Integer)
    # The run of the client's own work that proposed it (lifecycle K2d2): an AI proposal from a
    # client's document. A run writes its proposals once; null for every other proposal.
    run_id: Mapped[str | None] = mapped_column(String(64))
    # Typed (lifecycle K3): who wrote it (``domain.knowledge.KnowledgeAuthor``); null for a
    # proposal filed before this column, read from its provenance's markers or as unknown.
    author: Mapped[str | None] = mapped_column(String(16))
    # What was decided (``KnowledgeDecision``); null while pending and for a decision made
    # before this column.
    decision: Mapped[str | None] = mapped_column(String(16))
    # The item revision the reviewer named when deciding; null when they named none.
    reviewed_revision: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["item_id"], ["client_knowledge_items.item_id"], ondelete="CASCADE"),
        CheckConstraint(f"kind in {_KINDS_SQL}", name="knowledge_proposal_kind_known"),
        CheckConstraint(
            "status in ('PROPOSED','APPROVED','REJECTED')", name="knowledge_proposal_status_known"
        ),
        CheckConstraint(
            "author is null or author in ('PERSON','STUDY','AI')",
            name="knowledge_proposal_author_known",
        ),
        # A decision agrees with the status it settled: a rejection rejected, an approval one
        # of the three ways in; nothing pending carries one.
        CheckConstraint(
            "decision is null"
            " or (status = 'REJECTED' and decision = 'REJECTED')"
            " or (status = 'APPROVED' and decision in ('AUTHORED','ACCEPTED','ACCEPTED_OVER'))",
            name="knowledge_proposal_decision_known",
        ),
        Index("ix_client_knowledge_proposals_client", "client_id", "status"),
        Index("ix_client_knowledge_proposals_run", "run_id"),
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
    # The payer: the study, or, when NULL, the client (client-budget CB2).
    study_id: Mapped[str | None] = mapped_column(String(64))
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
    # must become RECOVERY_REQUIRED -- the double-billing guard. The second is a
    # record of the per-hold truth (budget_reservations.paid_call_in_flight),
    # rewritten from it on every metering write; decisions read the holds.
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
    """A hold against a study's budget, or the client's own, for one attempt.

    Reservations count as spent so that concurrent workers cannot each pass the
    budget check and collectively overspend. ``SETTLED_UNCERTAIN`` is the state a
    reservation enters when a paid call's billing status cannot be determined.
    """

    __tablename__ = "budget_reservations"

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # The payer: the study, or, when NULL, the client (client-budget CB2). ``client_id``
    # is always the hold's client, denormalised as everywhere else.
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str | None] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(64))
    step_id: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(String(64))

    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    settled_amount_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESERVED")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # A paid call against this hold has been dispatched and its outcome is not yet
    # recorded. Per hold, not per attempt: an attempt that sends two calls at once
    # has two questions open, and answering one must not close the other. An
    # attempt's outcome is known only when none of its open holds says this.
    paid_call_in_flight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The person this hold is booked to (Q40, develop-spend-attribution 7): whoever approved or
    # started the paid work, by ``domain/spend_attribution.py`` ``charged_to``, set when the hold
    # is made and never from a request body or a model. NULL: no such person (unattributed), or a
    # hold made before the column that the approval ledger does not name exactly.
    charged_to_user_id: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint("amount_usd >= 0", name="reservation_amount_non_negative"),
        CheckConstraint(
            "status in ('RESERVED','SETTLED','RELEASED','SETTLED_UNCERTAIN')",
            name="reservation_status_known",
        ),
        # The outstanding-reservation sum, used by every budget check.
        Index("ix_reservations_study_status", "study_id", "status"),
        Index("ix_reservations_client_status", "client_id", "status"),
        Index("ix_reservations_attempt", "attempt_id"),
        # Per-researcher spend (develop-spend-attribution 7).
        Index("ix_reservations_charged_to", "charged_to_user_id", "status"),
        # One run's spend, read on every poll of its Progress (artifact-fieldwork FLD4).
        Index("ix_reservations_run", "run_id"),
    )


class StudyWalletRow(Base):
    """A study's wallet (Peněženka, ADR 0028 decision 2, lead-orchestration LO1): what paid work
    may start without a further card, a slice of the study's budget.

    One open wallet per study (a partial unique index); no expiry; ``closed_at`` set when the
    study closes. ``cap_usd`` is the cap its newest raise set; what it may hold now is bounded by
    the client's wallet ceiling and the study's budget too (``domain/wallet.py``
    ``effective_cap``). Only ``StudyWalletRepository`` reads or writes it (``make layer_check``).
    """

    __tablename__ = "study_wallets"

    wallet_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cap_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        CheckConstraint("cap_usd >= 0", name="study_wallet_cap_non_negative"),
        Index(
            "uq_study_wallets_open",
            "study_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
    )


class StudyWalletRaiseRow(Base):
    """**Insert-once**: one change of a wallet's cap, by the researcher, with the approval-ledger
    row (``ApprovalSubject.WALLET``) that records it (ADR 0028 decision 2)."""

    __tablename__ = "study_wallet_raises"

    raise_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_cap_usd: Mapped[float] = mapped_column(Float, nullable=False)
    to_cap_usd: Mapped[float] = mapped_column(Float, nullable=False)
    raised_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_decision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["wallet_id"], ["study_wallets.wallet_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        # NO ACTION, not RESTRICT: checked at the statement's end, so a study's delete cascades
        # through both the ledger and this row.
        ForeignKeyConstraint(["approval_decision_id"], ["approval_decisions.decision_id"]),
        CheckConstraint("from_cap_usd >= 0", name="wallet_raise_from_non_negative"),
        CheckConstraint("to_cap_usd >= 0", name="wallet_raise_to_non_negative"),
        UniqueConstraint("approval_decision_id", name="wallet_raise_decision_once"),
        Index("ix_study_wallet_raises_wallet", "wallet_id", "raise_id"),
    )


class StudyWalletChargeRow(Base):
    """**Insert-once**: one started run's hold on its study's wallet, at its **cost ceiling**,
    never released and never re-priced (ADR 0028 decision 2), with the approval-ledger row that
    authorised the start (a ``chat_start`` or ``plan_step``) and the plan, if any.

    One charge per run (unique ``run_id``): a start that finds its run already there charges
    nothing again. ``plan_id`` names a ``lead_plans`` row once LO3 creates that table; until then
    it is a bare id with no foreign key.
    """

    __tablename__ = "study_wallet_charges"

    charge_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    ceiling_usd: Mapped[float] = mapped_column(Float, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(64))
    # The plan step that started the run (a ``plan_step`` charge only; the ledger row's subject).
    plan_step_id: Mapped[str | None] = mapped_column(String(64))
    approval_decision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["wallet_id"], ["study_wallets.wallet_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
        CheckConstraint(
            "(plan_id is null) = (plan_step_id is null)", name="wallet_charge_plan_and_step"
        ),
        # One start decision authorises one charge, of one run.
        UniqueConstraint("approval_decision_id", name="wallet_charge_decision_once"),
        # NO ACTION, not RESTRICT: checked at the statement's end, so a study's delete cascades
        # through both the ledger and this row.
        ForeignKeyConstraint(["approval_decision_id"], ["approval_decisions.decision_id"]),
        CheckConstraint("ceiling_usd >= 0", name="wallet_charge_ceiling_non_negative"),
        CheckConstraint(
            "kind in (" + ",".join(f"'{k.value}'" for k in ChargeKind) + ")",
            name="wallet_charge_kind_known",
        ),
        UniqueConstraint("run_id", name="wallet_charge_run_once"),
        Index("ix_study_wallet_charges_wallet", "wallet_id"),
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

    # Scope. Denormalised so an audit query needs no join, as everywhere else. A NULL
    # study is a decision about the client's own work (client-budget CB2).
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str | None] = mapped_column(String(64))

    # What was decided on: a workflow gate, an artifact sign-off, a budget lift, a spend
    # confirmation, the accept of an AI proposal (subject_id = the agent job's run id), or the
    # accept of a Design Research proposal (subject_id = the selection's id, run_id = the run),
    # or a run started over research questions it cannot all answer (subject_id = the run), or
    # a Research Lead's proposed edit (subject_id = "<turn_id>:<index>") or prepared paid job
    # (subject_id = the Lead turn) or the self-update it left waiting (subject_id = the Lead
    # turn), each decided by a person (ADR 0026). The closed set, with what each subject_id
    # names and who writes it, is domain/approval_ledger.py's ApprovalSubject.
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
        # Exactly the closed set of subjects (domain/approval_ledger.py); migration
        # 5054d4d610c2 is the last to change it (lead-orchestration LO16, lane M3).
        CheckConstraint(subject_check_sql(), name="approval_subject_type_known"),
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
    # NULL: a call the client's own budget paid for (client-budget CB2).
    study_id: Mapped[str | None] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    step_id: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(String(64))
    reservation_id: Mapped[str | None] = mapped_column(String(64))
    # The person the call is booked to (Q40): its hold's ``charged_to_user_id``, copied when the
    # row is appended. Not ``actor_id``, which is the scope's actor -- for a worker the run's
    # starter, else ``worker:<id>`` -- and for a resolution the person who resolved it. NULL:
    # unattributed, or a row from before the column the approval ledger does not name.
    charged_to_user_id: Mapped[str | None] = mapped_column(String(64))

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
        Index("ix_usage_run", "run_id"),
        Index("ix_usage_provider_request", "provider_request_id"),
        # Per-researcher spend: by person over time, and "which holds the ledger names".
        Index("ix_usage_charged_to", "organization_id", "charged_to_user_id", "occurred_at"),
        Index("ix_usage_reservation", "reservation_id"),
    )


# --------------------------------------------------------------------------- #
# Population registry
#
# Platform reference data, not client data: a shared version carries no
# organization, client or study, because it is shared by every study. The one
# exception is a materialized child (population-operations P4c): it names the
# organization and client it belongs to and the contract extension that declares
# its added fields, and only that organization reads it. What *is* study-scoped is
# which population a run used -- ``run_population_bindings`` hangs off
# ``workflow_runs`` and inherits its scope.
#
# Semantics live in ``aia_core.domain.population``; these tables only hold them.
# --------------------------------------------------------------------------- #


class PopulationContractExtensionRow(Base):
    """The fields a materialized child adds to its base, by hash. **Insert-once.**

    ``payload`` is the extension's canonical stored form
    (``domain.population.materialized.PopulationContractExtension.payload``) and
    ``extension_sha256`` the SHA256 of its canonical JSON; the repository re-hashes it
    on every read and refuses a payload that no longer matches its key. One extension
    may be named by several children (the same added fields over the same base).
    """

    __tablename__ = "population_contract_extensions"

    extension_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)


class PopulationDatasetVersionRow(Base):
    """One immutable, content-addressed dataset version.

    **Insert-only.** The repository has no update path for this table: a corrected
    dataset is a new version whose parent is this one. Within the shared versions, and
    within one owner's, the same bytes can never be registered twice and a label can
    never name two byte sequences (partial unique indexes below). A shared version's id
    is its content; an owned child's is its content qualified by its owner
    (``owned_version_id``), so two clients' identical children are two versions.

    The owner columns and ``extension_sha256`` are all set or all NULL, and an owned
    version always has a parent.
    """

    __tablename__ = "population_dataset_versions"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
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
    # Set only on a materialized child (P4c): who it belongs to, and what it adds.
    owner_organization_id: Mapped[str | None] = mapped_column(String(64))
    owner_client_id: Mapped[str | None] = mapped_column(String(64))
    extension_sha256: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        # No cascade: a version with descendants cannot be deleted out from under
        # them. The default NO ACTION (checked at statement end) rather than
        # RESTRICT, so one statement may still remove a whole lineage in tests.
        ForeignKeyConstraint(["parent_version_id"], ["population_dataset_versions.version_id"]),
        # No cascade either: a run may have been computed over an owned child.
        ForeignKeyConstraint(["owner_organization_id"], ["organizations.organization_id"]),
        ForeignKeyConstraint(["owner_client_id"], ["clients.client_id"]),
        ForeignKeyConstraint(
            ["extension_sha256"], ["population_contract_extensions.extension_sha256"]
        ),
        CheckConstraint(
            "(owner_organization_id IS NULL AND owner_client_id IS NULL"
            " AND extension_sha256 IS NULL)"
            " OR (owner_organization_id IS NOT NULL AND owner_client_id IS NOT NULL"
            " AND extension_sha256 IS NOT NULL AND parent_version_id IS NOT NULL)",
            name="population_version_owned_child",
        ),
        Index(
            "uq_population_version_shared_content",
            "content_sha256",
            unique=True,
            postgresql_where=text("owner_client_id IS NULL"),
            sqlite_where=text("owner_client_id IS NULL"),
        ),
        Index(
            "uq_population_version_owned_content",
            "owner_client_id",
            "content_sha256",
            unique=True,
            postgresql_where=text("owner_client_id IS NOT NULL"),
            sqlite_where=text("owner_client_id IS NOT NULL"),
        ),
        Index(
            "uq_population_version_shared_label",
            "dataset_id",
            "label",
            unique=True,
            postgresql_where=text("owner_client_id IS NULL"),
            sqlite_where=text("owner_client_id IS NULL"),
        ),
        Index(
            "uq_population_version_owned_label",
            "owner_client_id",
            "dataset_id",
            "label",
            unique=True,
            postgresql_where=text("owner_client_id IS NOT NULL"),
            sqlite_where=text("owner_client_id IS NOT NULL"),
        ),
        Index("ix_population_versions_owner", "owner_organization_id", "dataset_id"),
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


class PopulationVersionDictionaryRow(Base):
    """The field dictionary a dataset version was imported with. **Insert-once.**

    The version row keeps the dictionary's hash and location; this keeps its bytes, so
    a version's characteristics (each field's block, evidence and permitted uses) can be
    read without the asset source and without a respondent row. Stored only after the
    bytes have hashed to the version's ``dictionary_sha256``, and re-hashed on every read.
    """

    __tablename__ = "population_version_dictionaries"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["population_dataset_versions.version_id"]),
        CheckConstraint("byte_size > 0", name="population_dictionary_bytes_positive"),
    )


class PopulationVersionAudienceCatalogueRow(Base):
    """The audience factor catalogue computed from one dataset version. **Insert-once.**

    Computed once from the version's ANALYSIS view (``population_ops record-catalogue``,
    ``domain.population.audience_catalogue``) and kept as canonical JSON with its hash, so
    the API serves it without loading a respondent row. A new catalogue version is a new
    row beside the old, never an update.
    """

    __tablename__ = "population_version_audience_catalogues"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    catalogue_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["population_dataset_versions.version_id"]),
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


# --------------------------------------------------------------------------- #
# Deep Research settings (ADR 0022, plan chunk 41)
# --------------------------------------------------------------------------- #


class DeepResearchCompositionRow(Base):
    """What one worker's Deep Research composition reached, recorded at its start
    (deep-research-web-search 52). Deployment-wide; Settings reads the newest. ``routes``
    holds ``domain.deep_research_reach.reach_record``'s list."""

    __tablename__ = "deep_research_compositions"

    composition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker: Mapped[str] = mapped_column(String(128), nullable=False)
    build_sha: Mapped[str | None] = mapped_column(String(64))
    composed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_directed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    class_gates: Mapped[str | None] = mapped_column(String(16))
    routes: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)

    __table_args__ = (Index("ix_deep_research_compositions_composed_at", "composed_at"),)


class DeepResearchSettingVersionRow(Base):
    """One proposed value of a Deep Research setting. Immutable (ADR 0022).

    A version is never updated or deleted: a change is a new row, so what a run pinned can
    always be read back. ``version_number`` counts per organization and setting from 1; the
    code's proposed default is not a row. ``value`` holds ``{"value": ...}``, already
    validated against the catalogue (``domain.deep_research.settings``).
    """

    __tablename__ = "deep_research_setting_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    value_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Where the value comes from: a terms page, a quota letter, a decision document.
    source_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "setting_key", "version_number", name="uq_dr_setting_version"
        ),
        CheckConstraint("version_number >= 1", name="dr_setting_version_positive"),
        Index("ix_dr_setting_versions_key", "organization_id", "setting_key", "version_number"),
    )


class DeepResearchSettingApprovalRow(Base):
    """Which version of a setting is in force for an organization. Append-only.

    The newest row for a setting wins. ``version_number`` NULL means the code's proposed
    default: withdrawing an approval is a new row, never a delete, so the record of what was
    in force, approved by whom and when, is complete. A run does not read this table: it
    pinned its settings when it was enqueued.
    """

    __tablename__ = "deep_research_setting_approvals"

    approval_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer)
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "setting_key", "version_number"],
            [
                "deep_research_setting_versions.organization_id",
                "deep_research_setting_versions.setting_key",
                "deep_research_setting_versions.version_number",
            ],
        ),
        Index("ix_dr_setting_approvals_key", "organization_id", "setting_key", "approval_id"),
    )


# --------------------------------------------------------------------------- #
# Methodology versions (ADR 0023, plan methodology-tab A3)
# --------------------------------------------------------------------------- #


class MethodologyVersionRow(Base):
    """One edited methodology of a method module. Immutable (ADR 0023 decision 3).

    A version is never updated or deleted, so what a run pinned can always be read back.
    ``version_number`` counts per organization and module from 1; the code's preset is not a
    row. ``payload`` is the validated whole specification and the replaced formulas
    (``domain.methodology.versions.version_payload``); ``payload_sha256`` its digest.
    """

    __tablename__ = "methodology_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_preset: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "module_id", "version_number", name="uq_methodology_version"
        ),
        CheckConstraint("version_number >= 1", name="methodology_version_positive"),
        Index("ix_methodology_versions_module", "organization_id", "module_id", "version_number"),
    )


class MethodologyActivationRow(Base):
    """Which version of a module is in force for an organization. Append-only.

    The newest row for a module wins. ``version_number`` NULL means the code's preset: going
    back is a new row, never a delete, so the record of what was in force, put there by whom
    and when, is complete. A run does not read this table once started: it pins its
    methodology when it starts (chunk A4).
    """

    __tablename__ = "methodology_activations"

    activation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer)
    activated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "module_id", "version_number"],
            [
                "methodology_versions.organization_id",
                "methodology_versions.module_id",
                "methodology_versions.version_number",
            ],
        ),
        Index("ix_methodology_activations_module", "organization_id", "module_id", "activation_id"),
    )


# --------------------------------------------------------------------------- #
# Fan-out coordination (Deep Research chunk 21)
# --------------------------------------------------------------------------- #


class DeepResearchTestPolicyRow(Base):
    """Immutable operator proposal for one fictional study, never an organization policy."""

    __tablename__ = "deep_research_test_policies"
    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    values_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_cap_usd: Mapped[float] = mapped_column(Float, nullable=False)
    provider_permission: Mapped[str] = mapped_column(String(1000), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    __table_args__ = (
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        UniqueConstraint(
            "policy_id", "organization_id", "study_id", name="uq_dr_test_policy_scope"
        ),
        CheckConstraint(
            "budget_cap_usd > 0 and budget_cap_usd <= 20", name="dr_test_budget_bounded"
        ),
    )


class DeepResearchTestApprovalRow(Base):
    """Append-only approval or withdrawal; newest study row wins, including expiry."""

    __tablename__ = "deep_research_test_approvals"
    approval_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["policy_id", "organization_id", "study_id"],
            [
                "deep_research_test_policies.policy_id",
                "deep_research_test_policies.organization_id",
                "deep_research_test_policies.study_id",
            ],
        ),
        Index("ix_dr_test_approvals_scope", "organization_id", "study_id", "approval_id"),
    )


class HostPolitenessRow(Base):
    """One public host's turn: who is requesting it now, and when it may be asked next.

    Written only by ``fan_out_coordination.SharedHostPacer``. Keyed by host alone, not
    by run: a crawl delay is owed by AIA's user agent, which every run shares
    (``docs/architecture/deep-research-fan-out.md`` § 3). A host name and instants --
    no run, study or client.
    """

    __tablename__ = "host_politeness"

    host: Mapped[str] = mapped_column(String(255), primary_key=True)
    #: The earliest instant the next request may start: the end of the last one plus
    #: the interval the host is owed. NULL: never requested.
    next_allowed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: The request in flight now, and when its hold lapses should its process die.
    holder_token: Mapped[str | None] = mapped_column(String(64))
    held_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (Index("ix_host_politeness_updated", "updated_at"),)


class ModelConcurrencySlotRow(Base):
    """One slot of a model concurrency pool: free, or held by one request of one attempt.

    Written only by ``fan_out_coordination.ModelSlots``. A held slot is free again once
    its holder attempt no longer holds its lease, so a killed worker's slots return
    when its step could be recovered.
    """

    __tablename__ = "model_concurrency_slots"

    pool: Mapped[str] = mapped_column(String(128), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    holder_attempt_id: Mapped[str | None] = mapped_column(String(64))
    holder_token: Mapped[str | None] = mapped_column(String(64))
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("slot >= 0", name="model_slot_non_negative"),)


class WorkspaceEditOpRow(Base):
    """One logged change of a Study's working copy: an ``(item, field)`` one write touched (M1).
    **Insert-once.**

    ADR 0029 decision 3 (working-copy-edit-ops WCE2): every write of the working copy logs one
    row per ``(item, field)`` it touched, sharing a ``batch_id`` and the working revision it
    wrote (``domain/edit_log.py``). Read and written only by ``WorkspaceEditRepository``, under
    an issued ``StudyContext``; kept with its study until the study is deleted (Q27).
    """

    __tablename__ = "workspace_edit_ops"

    op_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_id: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The working revision the write was made from; NULL: the study had no copy, or only the
    #: bare template a server writer saved (``workspace.edited_from_current``).
    base_revision: Mapped[int | None] = mapped_column(Integer)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The person, or the researcher whose Lead made it; NULL only for a revision migrated from
    #: 18.6.6, whose author the unit did not record. No foreign key: the log keeps who wrote it.
    actor_user_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(64))
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    field: Mapped[str | None] = mapped_column(String(48))
    op: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    inverse: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.organization_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["client_id"], ["clients.client_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["study_id"], ["studies.study_id"], ondelete="CASCADE"),
        CheckConstraint(
            "actor_kind in (" + ",".join(f"'{k.value}'" for k in ActorKind) + ")",
            name="workspace_edit_op_actor_known",
        ),
        CheckConstraint(
            "source in (" + ",".join(f"'{s.value}'" for s in OpSource) + ")",
            name="workspace_edit_op_source_known",
        ),
        CheckConstraint(
            # WriteBy's rule, held by the table too: an author always, and never empty, but for
            # a person's revision migrated from 18.6.6 (the unit had no Lead).
            "(actor_user_id IS NOT NULL AND actor_user_id <> '') OR "
            f"(source = '{OpSource.MIGRATION.value}' AND actor_kind = '{ActorKind.PERSON.value}')",
            name="workspace_edit_op_author_unless_migrated",
        ),
        CheckConstraint(
            "base_revision IS NULL OR base_revision >= 1",
            name="workspace_edit_op_base_positive",
        ),
        CheckConstraint("result_revision >= 1", name="workspace_edit_op_result_positive"),
        Index("ix_workspace_edit_ops_feed", "study_id", "result_revision"),
        Index("ix_workspace_edit_ops_field", "study_id", "item_key", "field"),
    )


@event.listens_for(WorkspaceEditOpRow, "before_update")
def _edit_ops_are_never_updated(_mapper: Any, _connection: Any, row: WorkspaceEditOpRow) -> None:
    """A logged change is what was written; the log is insert-once (ADR 0029 decision 3)."""
    raise RuntimeError(f"edit op {row.op_id} is immutable; log a new one")


class DocsTicketSpendRow(Base):
    """A spent ticket to the report editor's origin (plan report-editor-hosting, chunk 3).

    The ticket is signed and carries its own expiry (``aia_api.docs_pass``); this row is
    what makes it single use across processes, by its primary key. Written only by
    ``DocsTicketRepository``, which deletes a row a day after its ticket expired.
    """

    __tablename__ = "docs_ticket_spends"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        Index("ix_docs_ticket_spends_expires", "expires_at"),
    )
