"""A ticket into the report editor's origin is spent once

Plan report-editor-hosting chunk 3: ONLYOFFICE Docs is served at docs.<hostname> behind a
gate of its own, reached by a signed 60-second ticket the API spends for a docs cookie. The
ticket expires on its own; this table is what makes it single use across API processes, by
its primary key. A person's rows are deleted a day after their tickets expired.

Revision ID: f4b6d8a0c2e3
Revises: 90dc672445b1
Created: 2026-10-22 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f4b6d8a0c2e3"
down_revision: str | None = "90dc672445b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "docs_ticket_spends",
        sa.Column("ticket_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_docs_ticket_spends_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_docs_ticket_spends_expires", "docs_ticket_spends", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_docs_ticket_spends_expires", table_name="docs_ticket_spends")
    op.drop_table("docs_ticket_spends")
