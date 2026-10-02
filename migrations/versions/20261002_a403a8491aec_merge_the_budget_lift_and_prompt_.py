"""merge the budget-lift and prompt-declaration heads

Revision ID: a403a8491aec
Revises: 8c2f4a6d1b3e, b3e8f1a47c60
Created: 2026-10-02 19:29:39.222636+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'a403a8491aec'
down_revision: str | None = ('8c2f4a6d1b3e', 'b3e8f1a47c60')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
