"""the working copy's operation log

Revision ID: 90dc672445b1
Revises: e2a4c6b8d0f1
Created: 2026-10-22

Migration M1 of the MVP's lane (``working-copy-edit-ops`` WCE2b; ADR 0029 decision 3):
``workspace_edit_ops``, every write of a study's working copy, one insert-once row per
``(item, field)`` it touched (``domain/edit_log.py``), sharing a batch and the working revision
it wrote. Nothing writes it until ``apply_edit_ops`` (WCE2c) does.

The actors and sources are listed literally here, as they were when this ran; the model builds
them from ``domain/edit_log.py``. The downgrade refuses while a row is stored: the log is the
record of who changed a study's design.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "90dc672445b1"
down_revision: str | None = "e2a4c6b8d0f1"
branch_labels = None
depends_on = None

_ACTORS = ("person", "lead")
_SOURCES = (
    "ui",
    "lead_turn",
    "proposal_accept",
    "design_research_accept",
    "undo",
    "reuse",
    "authored",
    "migration",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in (" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "workspace_edit_ops",
        sa.Column("op_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=True),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=True),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("field", sa.String(length=48), nullable=True),
        sa.Column(
            "op",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "inverse",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in("actor_kind", _ACTORS),
            name=op.f("ck_workspace_edit_ops_workspace_edit_op_actor_known"),
        ),
        sa.CheckConstraint(
            _in("source", _SOURCES),
            name=op.f("ck_workspace_edit_ops_workspace_edit_op_source_known"),
        ),
        sa.CheckConstraint(
            "(actor_user_id IS NOT NULL AND actor_user_id <> '') OR "
            "(source = 'migration' AND actor_kind = 'person')",
            name=op.f("ck_workspace_edit_ops_workspace_edit_op_author_unless_migrated"),
        ),
        sa.CheckConstraint(
            "base_revision IS NULL OR base_revision >= 1",
            name=op.f("ck_workspace_edit_ops_workspace_edit_op_base_positive"),
        ),
        sa.CheckConstraint(
            "result_revision >= 1",
            name=op.f("ck_workspace_edit_ops_workspace_edit_op_result_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_workspace_edit_ops_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            name=op.f("fk_workspace_edit_ops_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_workspace_edit_ops_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("op_id", name=op.f("pk_workspace_edit_ops")),
    )
    op.create_index(
        "ix_workspace_edit_ops_feed", "workspace_edit_ops", ["study_id", "result_revision"]
    )
    op.create_index(
        "ix_workspace_edit_ops_field", "workspace_edit_ops", ["study_id", "item_key", "field"]
    )


def downgrade() -> None:
    held = op.get_bind().scalar(sa.text("SELECT count(*) FROM workspace_edit_ops"))
    if held:
        raise RuntimeError(
            f"workspace_edit_ops holds {held} logged change(s); the log is insert-once and "
            "the record of who changed a study's design, so it is not dropped"
        )
    op.drop_index("ix_workspace_edit_ops_field", table_name="workspace_edit_ops")
    op.drop_index("ix_workspace_edit_ops_feed", table_name="workspace_edit_ops")
    op.drop_table("workspace_edit_ops")
