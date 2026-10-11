"""Audited expiring Deep Research policy proposals and approvals for fictional studies.

Revision ID: b2d4f6a8c0e1
Revises: a7c3e9b1d5f2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2d4f6a8c0e1'
down_revision = 'a7c3e9b1d5f2'
branch_labels = None
depends_on = None
JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table('deep_research_test_policies',
        sa.Column('policy_id', sa.String(64), primary_key=True),
        sa.Column('organization_id', sa.String(64), nullable=False),
        sa.Column('client_id', sa.String(64), nullable=False),
        sa.Column('study_id', sa.String(64), nullable=False),
        sa.Column('values_json', JSON, nullable=False),
        sa.Column('policy_sha256', sa.String(64), nullable=False),
        sa.Column('budget_cap_usd', sa.Float(), nullable=False),
        sa.Column('provider_permission', sa.String(1000), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['study_id'], ['studies.study_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('policy_id', 'organization_id', 'study_id', name='uq_dr_test_policy_scope'),
        sa.CheckConstraint('budget_cap_usd > 0 and budget_cap_usd <= 20', name='dr_test_budget_bounded'),
    )
    op.create_table('deep_research_test_approvals',
        sa.Column('approval_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('policy_id', sa.String(64), nullable=False),
        sa.Column('organization_id', sa.String(64), nullable=False),
        sa.Column('study_id', sa.String(64), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column('approved_by', sa.String(64), nullable=False),
        sa.Column('reason', sa.String(255), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['policy_id', 'organization_id', 'study_id'],
            ['deep_research_test_policies.policy_id', 'deep_research_test_policies.organization_id',
             'deep_research_test_policies.study_id']),
    )
    op.create_index('ix_dr_test_approvals_scope', 'deep_research_test_approvals',
                    ['organization_id', 'study_id', 'approval_id'])


def downgrade() -> None:
    op.drop_index('ix_dr_test_approvals_scope', table_name='deep_research_test_approvals')
    op.drop_table('deep_research_test_approvals')
    op.drop_table('deep_research_test_policies')
