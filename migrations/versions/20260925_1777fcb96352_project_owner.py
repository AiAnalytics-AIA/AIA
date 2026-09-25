"""project owner: a Study's design project belongs to the design repository

ADR 0016 decision 1. ``projects.owner`` is NULL for an ordinary project and
``study_design`` for the project that holds a Study's Design Revisions. The
project repository puts the owner in its isolation predicate, so the generic
project routes can neither see nor write a design project, and every revision a
run executes passed the design's validation.

Existing design projects -- every project a ``study_designs`` row points at -- are
backfilled. The downgrade drops the column, which makes design projects ordinary
projects again: the pre-migration state, with its bypass.

Revision ID: 1777fcb96352
Revises: eff3c6ed26b4
Created: 2026-09-25 07:28:25.958779+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '1777fcb96352'
down_revision: str | None = 'eff3c6ed26b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('owner', sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE projects SET owner = 'study_design' "
        "WHERE project_id IN (SELECT project_id FROM study_designs)"
    )


def downgrade() -> None:
    op.drop_column('projects', 'owner')
