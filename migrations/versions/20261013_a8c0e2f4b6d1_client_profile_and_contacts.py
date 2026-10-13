"""A client's profile on its record, and its contacts

Client-workspace C5 (decision D5: the profile lives on the client record). ``clients``
gains a short code, the industry, the market and a description, each empty until a
person fills it in; ``client_contacts`` keeps the people at the client who receive
results. Neither is Client Knowledge and no model reads either. Existing clients keep
everything they had, with an empty profile and no contacts.

Revision ID: a8c0e2f4b6d1
Revises: f2a4c6e8b0d9
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a8c0e2f4b6d1"
down_revision: str | None = "f2a4c6e8b0d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients", sa.Column("short_code", sa.String(length=16), nullable=False, server_default="")
    )
    op.add_column(
        "clients", sa.Column("industry", sa.String(length=120), nullable=False, server_default="")
    )
    op.add_column(
        "clients", sa.Column("market", sa.String(length=120), nullable=False, server_default="")
    )
    op.add_column("clients", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "client_contacts",
        sa.Column("contact_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("receives_reports", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_client_contacts_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("contact_id", name=op.f("pk_client_contacts")),
    )
    op.create_index("ix_client_contacts_client", "client_contacts", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_client_contacts_client", table_name="client_contacts")
    op.drop_table("client_contacts")
    op.drop_column("clients", "description")
    op.drop_column("clients", "market")
    op.drop_column("clients", "industry")
    op.drop_column("clients", "short_code")
