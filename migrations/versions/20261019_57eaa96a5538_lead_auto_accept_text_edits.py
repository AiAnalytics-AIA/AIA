"""a researcher may let their Lead's text edits be accepted without a click

Revision ID: 57eaa96a5538
Revises: 7b3c32892aa9
Created: 2026-10-19

``researcher_leads.auto_accept_text_edits``: the researcher's standing choice to have the Lead's
edits that change wording only (``set_text``, ``list_replace``, a ``question_edit`` of the text
alone) accepted without a click (plan inline-decisions chunk 2; ADR 0026: an explicit standing
choice by the researcher is the person's decision). Off for every existing Lead: the column is
added with a server default to fill existing rows, which is then dropped (AGENTS.md § Alembic).

Downgrade drops the column. Accepts already made under the choice stay in the approval ledger
with ``"auto": true`` in their comment.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "57eaa96a5538"
down_revision: str | None = "7b3c32892aa9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "researcher_leads",
        sa.Column(
            "auto_accept_text_edits", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("researcher_leads", "auto_accept_text_edits", server_default=None)


def downgrade() -> None:
    op.drop_column("researcher_leads", "auto_accept_text_edits")
