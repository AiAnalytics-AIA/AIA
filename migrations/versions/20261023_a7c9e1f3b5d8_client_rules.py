"""A client's data posture, and who last set its rules

Plan settings-backends SB7 (deep-research-web-search 53, client-knowledge-lifecycle K11): the
client's data posture, OPEN or CLASSIFIED, beside the wallet ceiling it already has
(``wallet_ceiling_usd``), both set by an organization OWNER or ADMIN on Profil → Pravidla.
NULL posture is "not set" and reads as CLASSIFIED, never open; who set the rules and when are
kept on the row, every change in the audit with its from and to.

Revision ID: a7c9e1f3b5d8
Revises: f6b8d0e2a4c7
Created: 2026-10-23 04:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1f3b5d8"
down_revision: str | None = "f6b8d0e2a4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("data_posture", sa.String(16), nullable=True))
    op.add_column("clients", sa.Column("rules_set_by", sa.String(64), nullable=True))
    op.add_column("clients", sa.Column("rules_set_at", sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_check_constraint(
            op.f("ck_clients_data_posture_known"),
            "clients",
            "data_posture is null or data_posture in ('OPEN', 'CLASSIFIED')",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(op.f("ck_clients_data_posture_known"), "clients", type_="check")
    op.drop_column("clients", "rules_set_at")
    op.drop_column("clients", "rules_set_by")
    op.drop_column("clients", "data_posture")
