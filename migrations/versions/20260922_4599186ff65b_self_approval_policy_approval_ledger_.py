"""self-approval policy, approval ledger, canonical workflow states

Three related changes, from the Architecture v2.1 reconciliation.

1. **Self-approval policy.** `allow_self_approval` on organizations, clients and
   studies, nullable at every level so the hierarchy inherits rather than
   duplicates: NULL means "ask my parent", and the default when nobody has
   configured anything is false. An explicit false is not inheritance -- a client
   that requires independent review keeps it under an organization that allows
   self-approval.

2. **Approval ledger.** `approval_decisions` is append-only and records every gate
   decision and artifact sign-off with the policy in force at the time and which
   level set it. The gate and artifact rows hold current state; only this table
   can answer what the rules were when a client deliverable was cleared.

3. **Canonical workflow states.** `WAITING_GATE` -> `AWAITING_GATE` and
   `WAITING_BUDGET` -> `AWAITING_BUDGET`, and provider-capacity waits split out of
   `WAITING_PROVIDER` into `WAITING_CAPACITY`. These are plain string columns with
   no check constraint, so this is a data migration and not a schema change.

   The downgrade folds `WAITING_CAPACITY` back into `WAITING_PROVIDER`, because
   the previous vocabulary had no separate capacity state. That is lossy in
   exactly the way the merged vocabulary was, which is why it was split.

Revision ID: 4599186ff65b
Revises: e0e14f1b5e3c
Created: 2026-09-22 10:09:00.757797+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '4599186ff65b'
down_revision: str | None = 'e0e14f1b5e3c'
branch_labels = None
depends_on = None

# (table, column) pairs carrying business workflow state.
_STATE_COLUMNS = (('workflow_runs', 'status'), ('step_runs', 'status'))

_RENAMES = (('WAITING_GATE', 'AWAITING_GATE'), ('WAITING_BUDGET', 'AWAITING_BUDGET'))


def _rename_states(pairs: tuple[tuple[str, str], ...]) -> None:
    """Rewrite persisted state names in place."""
    connection = op.get_bind()
    for table, column in _STATE_COLUMNS:
        for old, new in pairs:
            connection.execute(
                sa.text(f'UPDATE {table} SET {column} = :new WHERE {column} = :old'),
                {'new': new, 'old': old},
            )


def upgrade() -> None:
    op.create_table('approval_decisions',
    sa.Column('decision_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('study_id', sa.String(length=64), nullable=False),
    sa.Column('subject_type', sa.String(length=32), nullable=False),
    sa.Column('subject_id', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=True),
    sa.Column('step_id', sa.String(length=64), nullable=True),
    sa.Column('project_id', sa.String(length=64), nullable=True),
    sa.Column('project_revision', sa.Integer(), nullable=True),
    sa.Column('artifact_type', sa.String(length=64), nullable=False),
    sa.Column('gate_type', sa.String(length=64), nullable=False),
    sa.Column('producer_user_id', sa.String(length=64), nullable=True),
    sa.Column('approver_user_id', sa.String(length=64), nullable=False),
    sa.Column('self_approved', sa.Boolean(), nullable=False),
    sa.Column('self_approval_allowed', sa.Boolean(), nullable=False),
    sa.Column('self_approval_source', sa.String(length=32), nullable=False),
    sa.Column('decision', sa.String(length=64), nullable=False),
    sa.Column('comment', sa.Text(), nullable=False),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("self_approval_source in ('default','organization','client','study')", name=op.f('ck_approval_decisions_approval_self_approval_source_known')),
    sa.CheckConstraint("subject_type in ('gate','artifact')", name=op.f('ck_approval_decisions_approval_subject_type_known')),
    sa.ForeignKeyConstraint(['study_id'], ['studies.study_id'], name=op.f('fk_approval_decisions_study_id_studies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('decision_id', name=op.f('pk_approval_decisions'))
    )
    op.create_index('ix_approval_decisions_study', 'approval_decisions', ['study_id', 'decision_id'], unique=False)
    op.create_index('ix_approval_decisions_subject', 'approval_decisions', ['subject_type', 'subject_id'], unique=False)
    op.add_column('clients', sa.Column('allow_self_approval', sa.Boolean(), nullable=True))
    op.add_column('organizations', sa.Column('allow_self_approval', sa.Boolean(), nullable=True))
    op.add_column('studies', sa.Column('allow_self_approval', sa.Boolean(), nullable=True))

    _rename_states(_RENAMES)


def downgrade() -> None:
    # Reverse the renames, and fold the capacity wait back into the provider wait
    # that used to carry it.
    _rename_states(tuple((new, old) for old, new in _RENAMES))
    _rename_states((('WAITING_CAPACITY', 'WAITING_PROVIDER'),))

    op.drop_column('studies', 'allow_self_approval')
    op.drop_column('organizations', 'allow_self_approval')
    op.drop_column('clients', 'allow_self_approval')
    op.drop_index('ix_approval_decisions_subject', table_name='approval_decisions')
    op.drop_index('ix_approval_decisions_study', table_name='approval_decisions')
    op.drop_table('approval_decisions')
