"""study working content in AIA: the workspace row names a working project and a state

ADR 0018, OI-58. A research Study's working content moves from the 18.6.6 unit's
project store into AIA: an owned project (``projects.owner = study_workspace``)
found only through the Study's ``study_workspaces`` row. The row gains

* ``content_state`` -- where the content stands, by name (``ContentState``);
* ``project_id`` -- the AIA working project, unique, RESTRICT on delete;
* ``lineage`` -- migration provenance.

``unit_project_id`` becomes nullable and lineage only: a Study started in AIA has
none. Every existing row is a Study bound to an 18.6.6 project whose content has
not been migrated, so it becomes ``AWAITING_MIGRATION``; nothing is copied here.
The content itself is brought over by ``python -m aia_executors.legacy_workspace``,
an explicit operator command with a report (``deploy/develop/README.md``).

The downgrade is refused while any Study has content in AIA: dropping the columns
would orphan its working project, and making ``unit_project_id`` required again
would drop the Studies started in AIA. It is reversible on a database that only
holds rows this upgrade wrote.

Revision ID: 5b1d0f3e9a21
Revises: 1777fcb96352
Created: 2026-09-27 15:40:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '5b1d0f3e9a21'
down_revision: str | None = '1777fcb96352'
branch_labels = None
depends_on = None

_STATES = "('EMPTY','NATIVE','MIGRATED','RECOVERED','UNRECOVERABLE','AWAITING_MIGRATION')"
_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _recreate() -> str:
    # SQLite cannot ALTER a column or a constraint in place; PostgreSQL can.
    return "always" if op.get_bind().dialect.name == "sqlite" else "auto"


def upgrade() -> None:
    with op.batch_alter_table('study_workspaces', schema=None, recreate=_recreate()) as batch_op:
        # Every existing row is a binding to an unmigrated 18.6.6 project.
        batch_op.add_column(
            sa.Column(
                'content_state',
                sa.String(length=32),
                nullable=False,
                server_default='AWAITING_MIGRATION',
            )
        )
        batch_op.add_column(sa.Column('project_id', sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column('lineage', _JSON, nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.alter_column(
            'unit_project_id', existing_type=sa.String(length=160), nullable=True
        )
    # The defaults only backfilled the existing rows; new rows name their state and
    # lineage explicitly, as the model does.
    with op.batch_alter_table('study_workspaces', schema=None, recreate=_recreate()) as batch_op:
        batch_op.alter_column('content_state', server_default=None)
        batch_op.alter_column('lineage', server_default=None)
        batch_op.create_foreign_key(
            batch_op.f('fk_study_workspaces_project_id_projects'),
            'projects',
            ['project_id'],
            ['project_id'],
            ondelete='RESTRICT',
        )
        batch_op.create_unique_constraint('study_workspace_project_unique', ['project_id'])
        batch_op.create_check_constraint(
            'content_state_known', f"content_state in {_STATES}"
        )
        batch_op.create_check_constraint(
            'content_state_matches_project',
            "(content_state in ('NATIVE','MIGRATED','RECOVERED')) = (project_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    in_aia = bind.execute(
        sa.text(
            "SELECT count(*) FROM study_workspaces "
            "WHERE project_id IS NOT NULL OR unit_project_id IS NULL"
        )
    ).scalar_one()
    if in_aia:
        raise RuntimeError(
            f"{in_aia} Study workspace(s) hold content in AIA or have no 18.6.6 project; "
            "downgrading would orphan or drop them. Export them first."
        )
    with op.batch_alter_table('study_workspaces', schema=None, recreate=_recreate()) as batch_op:
        batch_op.drop_constraint('content_state_matches_project', type_='check')
        batch_op.drop_constraint('content_state_known', type_='check')
        batch_op.drop_constraint('study_workspace_project_unique', type_='unique')
        batch_op.drop_constraint(
            batch_op.f('fk_study_workspaces_project_id_projects'), type_='foreignkey'
        )
        batch_op.alter_column(
            'unit_project_id', existing_type=sa.String(length=160), nullable=False
        )
        batch_op.drop_column('lineage')
        batch_op.drop_column('project_id')
        batch_op.drop_column('content_state')
