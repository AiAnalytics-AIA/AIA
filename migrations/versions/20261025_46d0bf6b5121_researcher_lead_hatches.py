"""a researcher's hatch while it waits for their yes (lead-identity LI1)

Revision ID: 46d0bf6b5121
Revises: ba1e7fa927af
Created: 2026-10-25 23:51:35+00:00

The product owner, 2026-10-25: the model writes the Lead's SOUL and USER at hatching, and the
person accepts them before they are kept (ADR 0030 decision 2). ``researcher_lead_hatches`` holds
what the person wrote and what the model answered until then; at most one is pending per
researcher. A hatch is no decision of record once it is accepted or discarded (the Lead and its
revisions are), so the downgrade drops the table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "46d0bf6b5121"
down_revision: str | None = "ba1e7fa927af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "researcher_lead_hatches",
        sa.Column("hatch_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "input_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column(
            "output_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'discarded')",
            name=op.f("ck_researcher_lead_hatches_researcher_lead_hatch_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            name=op.f("fk_researcher_lead_hatches_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_researcher_lead_hatches_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hatch_id", name=op.f("pk_researcher_lead_hatches")),
    )
    op.create_index(
        "uq_researcher_lead_hatches_one_pending",
        "researcher_lead_hatches",
        ["organization_id", "user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_researcher_lead_hatches_one_pending",
        table_name="researcher_lead_hatches",
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_table("researcher_lead_hatches")
