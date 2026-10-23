"""a Lead turn's answered messages and a queued message's withdrawal

Revision ID: 7db4e0f96181
Revises: e5a7c9d1f3b6
Created: 2026-10-22 15:00:00+00:00

lead-conversation LC5a (ADR 0041 decision 7): a message posted while the Lead works is stored at
once and answered by the next turn.

* ``study_lead_turn_answers``: append-only, one row per message a Lead turn was sent, so a
  message no row names is still queued. Backfilled with one row per existing Lead message turn
  for the person message stored just before it, which is how a message was answered until now:
  no stored message reads as queued after the upgrade.
* ``study_lead_turns.parent_turn_id``: nullable, never updated; a ``withdrawal`` names the
  message it withdraws.
* The kind check admits ``withdrawal``, which is the person's, carries no text and names its
  message.

The downgrade refuses while a withdrawal is stored (dropping it would answer a message the
researcher withdrew), and while an answer row is one the backfill would not write again (a turn
that answered several queued messages): a re-upgrade would read those messages as queued and
send them a second time.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "7db4e0f96181"
down_revision: str | None = "e5a7c9d1f3b6"
branch_labels = None
depends_on = None

_KIND = "ck_study_lead_turns_study_lead_turn_kind_known"
_WITHDRAWAL = "ck_study_lead_turns_study_lead_turn_withdrawal_has_parent"
_PARENT = "fk_study_lead_turns_parent_turn_id_study_lead_turns"


def upgrade() -> None:
    op.add_column(
        "study_lead_turns", sa.Column("parent_turn_id", sa.String(length=64), nullable=True)
    )
    op.create_foreign_key(
        op.f(_PARENT),
        "study_lead_turns",
        "study_lead_turns",
        ["parent_turn_id"],
        ["turn_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(op.f(_KIND), "study_lead_turns", type_="check")
    op.create_check_constraint(
        op.f(_KIND), "study_lead_turns", "kind in ('message','greeting','withdrawal')"
    )
    op.create_check_constraint(
        op.f(_WITHDRAWAL),
        "study_lead_turns",
        "kind <> 'withdrawal' OR (actor = 'person' AND text IS NULL"
        " AND parent_turn_id IS NOT NULL)",
    )
    op.create_table(
        "study_lead_turn_answers",
        sa.Column("lead_turn_id", sa.String(length=64), nullable=False),
        sa.Column("person_turn_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_turn_id"],
            ["study_lead_turns.turn_id"],
            name=op.f("fk_study_lead_turn_answers_lead_turn_id_study_lead_turns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_turn_id"],
            ["study_lead_turns.turn_id"],
            name=op.f("fk_study_lead_turn_answers_person_turn_id_study_lead_turns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "lead_turn_id", "person_turn_id", name=op.f("pk_study_lead_turn_answers")
        ),
    )
    op.create_index(
        "ix_study_lead_turn_answers_person", "study_lead_turn_answers", ["person_turn_id"]
    )
    op.create_index(
        "ix_study_lead_turn_answers_scope", "study_lead_turn_answers", ["study_id", "user_id"]
    )
    # Until now a Lead message turn answered the person message stored just before it.
    op.execute(
        "INSERT INTO study_lead_turn_answers"
        " (lead_turn_id, person_turn_id, organization_id, study_id, user_id, created_at)"
        " SELECT lead.turn_id, person.turn_id, lead.organization_id, lead.study_id,"
        " lead.user_id, lead.created_at"
        " FROM study_lead_turns AS lead JOIN study_lead_turns AS person"
        " ON person.study_id = lead.study_id AND person.user_id = lead.user_id"
        " AND person.sequence_no = lead.sequence_no - 1"
        " WHERE lead.actor = 'lead' AND lead.kind = 'message'"
        " AND person.actor = 'person' AND person.kind = 'message' AND person.command IS NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    stored = int(
        bind.exec_driver_sql(
            "SELECT count(*) FROM study_lead_turns WHERE kind = 'withdrawal'"
        ).scalar()
        or 0
    )
    if stored:
        raise RuntimeError(
            f"refusing to drop withdrawals: {stored} queued message(s) were withdrawn"
        )
    beyond = int(
        bind.exec_driver_sql(
            "SELECT count(*) FROM study_lead_turn_answers AS a"
            " JOIN study_lead_turns AS lead ON lead.turn_id = a.lead_turn_id"
            " JOIN study_lead_turns AS person ON person.turn_id = a.person_turn_id"
            " WHERE person.sequence_no <> lead.sequence_no - 1"
        ).scalar()
        or 0
    )
    if beyond:
        raise RuntimeError(
            f"refusing to drop study_lead_turn_answers: {beyond} answer(s) a re-upgrade would"
            " not restore, so their messages would be sent again"
        )
    op.drop_index("ix_study_lead_turn_answers_scope", table_name="study_lead_turn_answers")
    op.drop_index("ix_study_lead_turn_answers_person", table_name="study_lead_turn_answers")
    op.drop_table("study_lead_turn_answers")
    op.drop_constraint(op.f(_WITHDRAWAL), "study_lead_turns", type_="check")
    op.drop_constraint(op.f(_KIND), "study_lead_turns", type_="check")
    op.create_check_constraint(op.f(_KIND), "study_lead_turns", "kind in ('message','greeting')")
    op.drop_constraint(op.f(_PARENT), "study_lead_turns", type_="foreignkey")
    op.drop_column("study_lead_turns", "parent_turn_id")
