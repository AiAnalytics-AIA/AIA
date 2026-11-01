"""a smoke result may be NOT_READY: an activation row not switched on (mvp-master-plan MP6)

Revision ID: 2bcb06c19987
Revises: 184381bbcfef
Created: 2026-10-27

The smoke reports each row of the MVP's activation profile READY or NOT_READY, and Settings →
Stav systému shows the latest run's checks, so the kept result may be NOT_READY too. The downgrade
restores the three results; it fails while a NOT_READY row is kept, rather than drop it.
"""

from __future__ import annotations

from alembic import op

revision: str = "2bcb06c19987"
down_revision: str | None = "184381bbcfef"
branch_labels = None
depends_on = None

_NAME = "ck_deploy_smoke_results_status_known"


def _statuses(allowed: str) -> None:
    with op.batch_alter_table("deploy_smoke_results") as batch:
        batch.drop_constraint(op.f(_NAME), type_="check")
        batch.create_check_constraint(op.f(_NAME), f"status in ({allowed})")


def upgrade() -> None:
    _statuses("'ok', 'FAIL', 'NOT_READY', 'NOT_RUNNABLE'")


def downgrade() -> None:
    _statuses("'ok', 'FAIL', 'NOT_RUNNABLE'")
