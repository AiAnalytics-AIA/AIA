"""Folders and labels for a client's knowledge

Client-workspace C3. A client's knowledge can be filed: each client has its own
folders and labels; an item sits in at most one folder (``client_knowledge_item_folders``,
kept apart from the item so filing never touches its revision or ``modified_at``) and
carries any number of labels (``client_knowledge_item_labels``). Nothing existing
changes: every item starts in no folder and with no label.

Revision ID: e8a0c2e4f6b8
Revises: d6f8a0c2e4b6
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "e8a0c2e4f6b8"
down_revision: str | None = "d6f8a0c2e4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_knowledge_folders",
        sa.Column("folder_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_client_knowledge_folders_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("folder_id", name=op.f("pk_client_knowledge_folders")),
        sa.UniqueConstraint("client_id", "name_key", name="uq_client_knowledge_folders_name"),
    )
    op.create_table(
        "client_knowledge_labels",
        sa.Column("label_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("colour", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "colour in ('BLUE','TEAL','GREEN','ORANGE','VIOLET','SLATE')",
            name=op.f("ck_client_knowledge_labels_knowledge_label_colour_known"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_client_knowledge_labels_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("label_id", name=op.f("pk_client_knowledge_labels")),
        sa.UniqueConstraint("client_id", "name_key", name="uq_client_knowledge_labels_name"),
    )
    op.create_table(
        "client_knowledge_item_folders",
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("folder_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["client_knowledge_folders.folder_id"],
            name=op.f("fk_client_knowledge_item_folders_folder_id_client_knowledge_folders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["client_knowledge_items.item_id"],
            name=op.f("fk_client_knowledge_item_folders_item_id_client_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id", name=op.f("pk_client_knowledge_item_folders")),
    )
    op.create_index(
        "ix_client_knowledge_item_folders_folder",
        "client_knowledge_item_folders",
        ["folder_id"],
        unique=False,
    )
    op.create_table(
        "client_knowledge_item_labels",
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("label_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["client_knowledge_items.item_id"],
            name=op.f("fk_client_knowledge_item_labels_item_id_client_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["label_id"],
            ["client_knowledge_labels.label_id"],
            name=op.f("fk_client_knowledge_item_labels_label_id_client_knowledge_labels"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "item_id", "label_id", name=op.f("pk_client_knowledge_item_labels")
        ),
    )
    op.create_index(
        "ix_client_knowledge_item_labels_label",
        "client_knowledge_item_labels",
        ["label_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_knowledge_item_labels_label", table_name="client_knowledge_item_labels"
    )
    op.drop_table("client_knowledge_item_labels")
    op.drop_index(
        "ix_client_knowledge_item_folders_folder", table_name="client_knowledge_item_folders"
    )
    op.drop_table("client_knowledge_item_folders")
    op.drop_table("client_knowledge_labels")
    op.drop_table("client_knowledge_folders")
