"""each researcher's Research Lead: its conversations, its files and its notes

ADR 0026 and the product owner's 2026-10-19 decisions. A Lead turn is a durable worker step;
these tables hold what is not a run:

* ``study_lead_turns``: one researcher's conversation in one Study, append-only, numbered per
  (study, user). A Lead turn names its ``research_lead`` run; its reply is that run's step
  output, never copied here.
* ``researcher_leads``: one Lead per (organization, user), with its OpenClaw-style files: a
  name, a SOUL and a USER profile, each bounded.
* ``researcher_lead_revisions``: the text a file change replaced, insert-once.
* ``researcher_lead_memories``: the Lead's notes, personal or bound to one client; forgetting
  sets ``forgotten_at`` and deletes nothing.

``approval_decisions.subject_type`` also admits ``'lead_edit'`` (a person's accept or dismiss
of one edit a Lead turn proposed) and ``'lead_job_request'`` (a person's approval of the paid
job a Lead turn prepared). The constraint is named with ``op.f`` on drop and on create
(AGENTS.md § Alembic).

Downgrade drops the four tables and what they hold, and refuses while the append-only ledger
holds a Lead decision.

Revision ID: 7b3c32892aa9
Revises: bd44c92f1fb7
Created: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7b3c32892aa9"
down_revision: str | None = "bd44c92f1fb7"
branch_labels = None
depends_on = None

_LEDGER = "ck_approval_decisions_approval_subject_type_known"
_BEFORE = "('gate','artifact','budget','spend','ai_proposal','design_research','answerability')"
_AFTER = (
    "('gate','artifact','budget','spend','ai_proposal','design_research','answerability',"
    "'lead_edit','lead_job_request')"
)


def upgrade() -> None:
    op.create_table(
        "researcher_leads",
        sa.Column("lead_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("soul", sa.Text(), nullable=False),
        sa.Column("user_profile", sa.Text(), nullable=False),
        sa.Column("hatched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(soul) <= 2000", name=op.f("ck_researcher_leads_researcher_lead_soul_bounded")
        ),
        sa.CheckConstraint(
            "length(user_profile) <= 2000",
            name=op.f("ck_researcher_leads_researcher_lead_user_bounded"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            name=op.f("fk_researcher_leads_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_researcher_leads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("lead_id", name=op.f("pk_researcher_leads")),
        sa.UniqueConstraint("organization_id", "user_id", name="researcher_lead_once"),
    )
    op.create_table(
        "researcher_lead_memories",
        sa.Column("memory_id", sa.String(length=64), nullable=False),
        sa.Column("lead_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("source_turn_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forgotten_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(scope = 'client') = (client_id IS NOT NULL)",
            name=op.f("ck_researcher_lead_memories_researcher_lead_memory_client_iff_scope"),
        ),
        sa.CheckConstraint(
            "created_by in ('lead','person')",
            name=op.f("ck_researcher_lead_memories_researcher_lead_memory_author_known"),
        ),
        sa.CheckConstraint(
            "scope in ('personal','client')",
            name=op.f("ck_researcher_lead_memories_researcher_lead_memory_scope"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_researcher_lead_memories_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["researcher_leads.lead_id"],
            name=op.f("fk_researcher_lead_memories_lead_id_researcher_leads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("memory_id", name=op.f("pk_researcher_lead_memories")),
    )
    op.create_index(
        "ix_researcher_lead_memories_lead",
        "researcher_lead_memories",
        ["lead_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "researcher_lead_revisions",
        sa.Column("revision_id", sa.String(length=64), nullable=False),
        sa.Column("lead_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=16), nullable=False),
        sa.Column("previous", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_turn_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "field in ('name','soul','user')",
            name=op.f("ck_researcher_lead_revisions_researcher_lead_field_known"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["researcher_leads.lead_id"],
            name=op.f("fk_researcher_lead_revisions_lead_id_researcher_leads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("revision_id", name=op.f("pk_researcher_lead_revisions")),
    )
    op.create_index(
        "ix_researcher_lead_revisions_lead",
        "researcher_lead_revisions",
        ["lead_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "study_lead_turns",
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("focus", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("workspace_revision", sa.Integer(), nullable=True),
        sa.Column("design_revision_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(actor = 'lead') = (run_id IS NOT NULL)",
            name=op.f("ck_study_lead_turns_study_lead_turn_run_iff_lead"),
        ),
        sa.CheckConstraint(
            "actor in ('person','lead')",
            name=op.f("ck_study_lead_turns_study_lead_turn_actor_known"),
        ),
        sa.CheckConstraint(
            "kind in ('message','greeting')",
            name=op.f("ck_study_lead_turns_study_lead_turn_kind_known"),
        ),
        sa.CheckConstraint(
            "sequence_no >= 1", name=op.f("ck_study_lead_turns_study_lead_turn_sequence_positive")
        ),
        sa.CheckConstraint(
            "text IS NULL OR length(text) <= 4000",
            name=op.f("ck_study_lead_turns_study_lead_turn_text_bounded"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_study_lead_turns_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            name=op.f("fk_study_lead_turns_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.run_id"],
            name=op.f("fk_study_lead_turns_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_study_lead_turns_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_study_lead_turns_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("turn_id", name=op.f("pk_study_lead_turns")),
        sa.UniqueConstraint("study_id", "user_id", "sequence_no", name="study_lead_turn_sequence"),
    )
    op.create_index(
        "ix_study_lead_turns_actor",
        "study_lead_turns",
        ["organization_id", "user_id", "created_at"],
        unique=False,
    )

    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", f"subject_type in {_AFTER}")


def downgrade() -> None:
    held = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM approval_decisions "
            "WHERE subject_type IN ('lead_edit','lead_job_request')"
        )
        .scalar()
    )
    if held:
        raise RuntimeError(
            f"{held} Research Lead decision(s) are in the approval ledger, which is "
            "append-only; downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", f"subject_type in {_BEFORE}")
    op.drop_index("ix_study_lead_turns_actor", table_name="study_lead_turns")
    op.drop_table("study_lead_turns")
    op.drop_index("ix_researcher_lead_revisions_lead", table_name="researcher_lead_revisions")
    op.drop_table("researcher_lead_revisions")
    op.drop_index("ix_researcher_lead_memories_lead", table_name="researcher_lead_memories")
    op.drop_table("researcher_lead_memories")
    op.drop_table("researcher_leads")
