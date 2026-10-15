"""A client's own budget

client-budget CB1: client-level AI work (AI proposals from a client's documents) has no
study to pay for it, so the client gets a budget of its own and its spend. Studies keep
theirs; this budget neither caps nor funds them. Existing clients start at 0, so any
client-paid work waits for a person to set one rather than presuming an allowance.

Revision ID: e6a8c0b2d4f1
Revises: d4f6a8c0e2b5
Created: 2026-10-15 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "e6a8c0b2d4f1"
down_revision: str | None = "d4f6a8c0e2b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("clients") as batch:
        batch.add_column(sa.Column("budget_usd", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("spent_usd", sa.Float(), nullable=False, server_default="0"))
        batch.create_check_constraint("client_budget_non_negative", "budget_usd >= 0")
        batch.create_check_constraint("client_spent_non_negative", "spent_usd >= 0")


def downgrade() -> None:
    with op.batch_alter_table("clients") as batch:
        batch.drop_constraint("client_spent_non_negative", type_="check")
        batch.drop_constraint("client_budget_non_negative", type_="check")
        batch.drop_column("spent_usd")
        batch.drop_column("budget_usd")
