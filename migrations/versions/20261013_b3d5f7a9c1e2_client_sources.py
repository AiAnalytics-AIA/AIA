"""A client's sources and every time one was added

Lifecycle K2a. ``client_sources`` keeps one row per client and SHA-256: the original's
size and type, where its bytes and its reading are in the artifact store, and what
reading it produced. ``client_source_occurrences`` keeps each time someone added it.
A source is not Client Knowledge; nothing existing changes.

Revision ID: b3d5f7a9c1e2
Revises: a8c0e2f4b6d1
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5f7a9c1e2"
down_revision: str | None = "a8c0e2f4b6d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_sources",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("family", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("reading_key", sa.String(length=512), nullable=True),
        sa.Column("reading_sha256", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("reader", sa.String(length=32), nullable=True),
        sa.Column("characters", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_client_sources_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", name=op.f("pk_client_sources")),
        sa.UniqueConstraint("client_id", "sha256", name="client_source_sha_unique"),
    )
    op.create_table(
        "client_source_occurrences",
        sa.Column("occurrence_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=160), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("added_by", sa.String(length=64), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["client_sources.source_id"],
            name=op.f("fk_client_source_occurrences_source_id_client_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("occurrence_id", name=op.f("pk_client_source_occurrences")),
    )
    op.create_index(
        "ix_client_source_occurrences_source",
        "client_source_occurrences",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_client_source_occurrences_client",
        "client_source_occurrences",
        ["client_id", "added_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_source_occurrences_client", table_name="client_source_occurrences")
    op.drop_index("ix_client_source_occurrences_source", table_name="client_source_occurrences")
    op.drop_table("client_source_occurrences")
    op.drop_table("client_sources")
