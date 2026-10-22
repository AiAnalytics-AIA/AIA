"""A study's chosen client knowledge: one exact revision per item

Lifecycle K4 (client-knowledge-lifecycle), "use in this study". A study read every active
item of its client, whatever was accepted last, so what a job or a turn read was whatever
happened to be current. ``client_knowledge_selections`` records a person's choice of one
item for one study at one exact revision, which the study's frozen context reads.

A new table, written by nothing before this; the downgrade drops it and the choices with it.

Revision ID: b5d7f9a1c3e6
Revises: a3c5e7f9b1d4
Created: 2026-10-21 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "b5d7f9a1c3e6"
down_revision: str | None = "a3c5e7f9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_knowledge_selections",
        sa.Column("study_id", sa.String(64), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("selected_by", sa.String(64), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision >= 1",
            name=op.f("ck_client_knowledge_selections_knowledge_selection_revision_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_client_knowledge_selections_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "revision"],
            ["client_knowledge_revisions.item_id", "client_knowledge_revisions.revision"],
            name=op.f("fk_client_knowledge_selections_item_id_client_knowledge_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "study_id", "item_id", name=op.f("pk_client_knowledge_selections")
        ),
    )
    op.create_index(
        "ix_client_knowledge_selections_item", "client_knowledge_selections", ["item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_client_knowledge_selections_item", table_name="client_knowledge_selections")
    op.drop_table("client_knowledge_selections")
