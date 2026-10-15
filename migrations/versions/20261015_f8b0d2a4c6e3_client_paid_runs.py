"""Client-paid runs: a study or the client as the payer

client-budget CB2: work on the client itself (AI proposals from its documents) runs
under a client-owned project and is paid by the client's own budget. So a project, a
run, a budget hold, a usage event and an approval may name no study: their payer is
then the client. Every existing row keeps its study, so nothing study-paid changes.

``budget_reservations`` gains ``client_id`` (backfilled from each hold's study), as
every other scoped table has it, so a client's outstanding holds are one indexed sum.
A project names no study exactly when it is the client's own (``client_sources``).

Revision ID: f8b0d2a4c6e3
Revises: e6a8c0b2d4f1
Created: 2026-10-15 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "f8b0d2a4c6e3"
down_revision: str | None = "e6a8c0b2d4f1"
branch_labels = None
depends_on = None

_NULLABLE = ("projects", "workflow_runs", "approval_decisions", "ai_usage_events")


def upgrade() -> None:
    with op.batch_alter_table("budget_reservations") as batch:
        batch.add_column(sa.Column("client_id", sa.String(64), nullable=True))
    op.execute(
        "UPDATE budget_reservations SET client_id = "
        "(SELECT studies.client_id FROM studies "
        "WHERE studies.study_id = budget_reservations.study_id)"
    )
    with op.batch_alter_table("budget_reservations") as batch:
        batch.alter_column("client_id", existing_type=sa.String(64), nullable=False)
        batch.alter_column("study_id", existing_type=sa.String(64), nullable=True)
        batch.create_foreign_key(
            op.f("fk_budget_reservations_client_id_clients"),
            "clients",
            ["client_id"],
            ["client_id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "ix_reservations_client_status", "budget_reservations", ["client_id", "status"]
    )
    for table in _NULLABLE:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("study_id", existing_type=sa.String(64), nullable=True)
    with op.batch_alter_table("projects") as batch:
        batch.create_check_constraint(
            "project_study_unless_client_owned",
            "(study_id is null) = (coalesce(owner, '') = 'client_sources')",
        )


def downgrade() -> None:
    # Refused while client-paid rows exist: they have no study to give back.
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("project_study_unless_client_owned", type_="check")
    for table in (*_NULLABLE, "budget_reservations"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("study_id", existing_type=sa.String(64), nullable=False)
    op.drop_index("ix_reservations_client_status", table_name="budget_reservations")
    with op.batch_alter_table("budget_reservations") as batch:
        batch.drop_constraint(op.f("fk_budget_reservations_client_id_clients"), type_="foreignkey")
        batch.drop_column("client_id")
