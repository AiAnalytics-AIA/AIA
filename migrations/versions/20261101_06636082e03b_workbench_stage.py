"""The workbench stage a study was left on, beside its classic step

Plan client-pages-redesign CPR23 (the product owner, 1 Nov 2026: "Server chunk first"): a study's
last_stage keeps the classic step alone, so the client pages could name only seven of the research
workbench's eleven stages (Vzorek read as Dimenze; Sociomapa, Analýza and Zpráva as Výsledky).
study_workspaces.last_workbench_stage keeps the stage beside it. Nullable: a row written before
records none, and reads as not recorded.

Revision ID: 06636082e03b
Revises: 5cc62edde24e
Created: 2026-11-01 15:30:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "06636082e03b"
down_revision: str | None = "5cc62edde24e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "study_workspaces", sa.Column("last_workbench_stage", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("study_workspaces", "last_workbench_stage")
