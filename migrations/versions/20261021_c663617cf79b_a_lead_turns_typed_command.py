"""a Lead turn's typed command

Revision ID: c663617cf79b
Revises: 60ccc9ff42cf
Created: 2026-10-21 14:30:00+00:00

lead-orchestration LO5: the composer's typed start commands are matched by code on the server
(``domain/lead_commands.py``) and stored on the person's own turn, so a card can be told apart
from Lead output by what is stored, never by a request body (research-lead-workbench D22).

* ``study_lead_turns.command``: nullable, the start's name (``agent_job:<action>``,
  ``research_run``); NULL on every existing turn.
* ``ck_study_lead_turns_study_lead_turn_command_is_a_persons``: only a person's turn names one.

The downgrade refuses while a turn names a command: dropping it would turn a person's typed
start, which a ``chat_start`` ledger row may name, back into a plain message.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c663617cf79b"
down_revision: str | None = "60ccc9ff42cf"
branch_labels = None
depends_on = None

_CHECK = "ck_study_lead_turns_study_lead_turn_command_is_a_persons"


def upgrade() -> None:
    op.add_column("study_lead_turns", sa.Column("command", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        op.f(_CHECK), "study_lead_turns", "command IS NULL OR actor = 'person'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    stored = int(
        bind.exec_driver_sql(
            "SELECT count(*) FROM study_lead_turns WHERE command IS NOT NULL"
        ).scalar()
        or 0
    )
    if stored:
        raise RuntimeError(
            f"refusing to drop study_lead_turns.command: {stored} turn(s) name a typed command"
        )
    op.drop_constraint(op.f(_CHECK), "study_lead_turns", type_="check")
    op.drop_column("study_lead_turns", "command")
