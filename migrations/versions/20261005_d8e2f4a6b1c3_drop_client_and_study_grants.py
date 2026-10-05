"""drop the client and study grant tables (ADR 0019, plan chunk 6)

Revision ID: d8e2f4a6b1c3
Revises: c5d7e9f1a2b4
Created: 2026-10-05

Since chunk 3 (#105) membership of the organization is the access and nothing reads a grant;
since chunk 4 nothing offers one and since this change nothing writes one. ADR 0019 kept the
tables for one deploy without reads so the change could be rolled back; that deploy has
happened, so they go.

What the rows recorded is not lost: every grant and revocation was also written to
``access_audit`` (CLIENT_GRANT, STUDY_GRANT, CLIENT_SELF_GRANT, CLIENT_REVOKE), which stays.

The downgrade recreates both tables as the first scope migration (6750a204efd9) made them,
**empty**: the rows are not restored, and nothing would read them if they were.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = 'd8e2f4a6b1c3'
down_revision: str | None = 'c5d7e9f1a2b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_study_grants_user', table_name='study_grants')
    op.drop_table('study_grants')
    op.drop_index('ix_client_grants_user', table_name='client_grants')
    op.drop_table('client_grants')


def downgrade() -> None:
    op.create_table(
        'client_grants',
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('granted_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role in ('VIEWER','REVIEWER','RESEARCHER','LEAD')",
            name=op.f('ck_client_grants_client_grant_role_known'),
        ),
        sa.ForeignKeyConstraint(
            ['client_id'],
            ['clients.client_id'],
            name=op.f('fk_client_grants_client_id_clients'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.user_id'],
            name=op.f('fk_client_grants_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('client_id', 'user_id', name=op.f('pk_client_grants')),
    )
    op.create_index('ix_client_grants_user', 'client_grants', ['user_id'], unique=False)
    op.create_table(
        'study_grants',
        sa.Column('study_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('granted_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role in ('VIEWER','REVIEWER','RESEARCHER','LEAD')",
            name=op.f('ck_study_grants_study_grant_role_known'),
        ),
        sa.ForeignKeyConstraint(
            ['study_id'],
            ['studies.study_id'],
            name=op.f('fk_study_grants_study_id_studies'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.user_id'],
            name=op.f('fk_study_grants_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('study_id', 'user_id', name=op.f('pk_study_grants')),
    )
    op.create_index('ix_study_grants_user', 'study_grants', ['user_id'], unique=False)
