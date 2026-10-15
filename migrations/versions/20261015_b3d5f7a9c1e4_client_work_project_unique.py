"""One project of the client's own work per client

client-budget CB3b: the client's own work runs in one project per client (owner
``client_sources``, no study). Creating it on first use was a read then an insert, so
two first requests at once could each create one. A partial unique index holds the one;
the losing insert is refused and answered with the project the other made.

Nothing before this migration starts client work through a route, so no client has two
such projects to refuse the index.

Revision ID: b3d5f7a9c1e4
Revises: f8b0d2a4c6e3
Created: 2026-10-15 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "b3d5f7a9c1e4"
down_revision: str | None = "f8b0d2a4c6e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_projects_client_work",
        "projects",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("owner = 'client_sources'"),
        sqlite_where=sa.text("owner = 'client_sources'"),
    )


def downgrade() -> None:
    op.drop_index("uq_projects_client_work", table_name="projects")
