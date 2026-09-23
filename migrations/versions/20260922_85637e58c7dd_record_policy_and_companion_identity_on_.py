"""record policy and companion identity on run bindings

Four facts every run binding now carries, so a run names exactly which claim
rules and which joint certificate its population was computed under:
``dictionary_sha256``, ``field_policy_version``, ``companion_set_sha256`` and
``joint_state``.

**No backfill, by design.** A binding recorded before this revision cannot say
which policy or certificate applied, and stamping today's values onto it would be
a guess presented as provenance. The upgrade therefore refuses to run while any
binding row exists; nothing has been deployed that could have written one. If
this ever fires, the rows need a human decision, not a default.

Revision ID: 85637e58c7dd
Revises: cadbca872dc5
Created: 2026-09-22 22:18:42.265214+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '85637e58c7dd'
down_revision: str | None = 'cadbca872dc5'
branch_labels = None
depends_on = None


_JOINT_STATES = "('CERTIFIED','NOT_THIS_PANEL','UNKNOWN_STATUS','UNPARSEABLE','MISSING')"


def upgrade() -> None:
    existing = op.get_bind().execute(sa.text('SELECT count(*) FROM run_population_bindings')).scalar()
    if existing:
        raise RuntimeError(
            f'{existing} run_population_bindings rows predate policy identity; they cannot be '
            'backfilled without guessing which policy and certificate applied'
        )
    op.add_column('run_population_bindings', sa.Column('dictionary_sha256', sa.String(length=64), nullable=False))
    op.add_column('run_population_bindings', sa.Column('field_policy_version', sa.String(length=64), nullable=False))
    op.add_column('run_population_bindings', sa.Column('companion_set_sha256', sa.String(length=64), nullable=False))
    op.add_column('run_population_bindings', sa.Column('joint_state', sa.String(length=32), nullable=False))
    op.create_check_constraint(
        op.f('ck_run_population_bindings_run_population_joint_state_known'),
        'run_population_bindings',
        f'joint_state in {_JOINT_STATES}',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('ck_run_population_bindings_run_population_joint_state_known'),
        'run_population_bindings',
        type_='check',
    )
    op.drop_column('run_population_bindings', 'joint_state')
    op.drop_column('run_population_bindings', 'companion_set_sha256')
    op.drop_column('run_population_bindings', 'field_policy_version')
    op.drop_column('run_population_bindings', 'dictionary_sha256')
