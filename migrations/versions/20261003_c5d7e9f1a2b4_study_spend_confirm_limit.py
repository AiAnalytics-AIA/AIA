"""a study's spend-confirm limit, and a spend confirmation in the approval ledger

Revision ID: c5d7e9f1a2b4
Revises: a403a8491aec
Created: 2026-10-03

Two changes for one feature (the spend confirmation of ADR 0019 gate 2):

* ``studies.spend_confirm_usd``: the cost ceiling at or above which starting a run asks for
  confirmation. NULL means it never asks, so every existing study keeps today's behaviour.
* ``approval_decisions.subject_type`` admits ``'spend'``, so the confirmation is recorded in the
  same append-only ledger as every other decision. The constraint is named with ``op.f`` on drop
  and on create: the metadata's naming convention would otherwise prefix the existing name a
  second time (AGENTS.md § Alembic).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = 'c5d7e9f1a2b4'
down_revision: str | None = 'a403a8491aec'
branch_labels = None
depends_on = None

_LEDGER = 'ck_approval_decisions_approval_subject_type_known'
_STUDY = 'ck_studies_study_spend_confirm_non_negative'


def upgrade() -> None:
    op.add_column('studies', sa.Column('spend_confirm_usd', sa.Float(), nullable=True))
    op.create_check_constraint(
        op.f(_STUDY), 'studies', 'spend_confirm_usd is null or spend_confirm_usd >= 0'
    )
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER), 'approval_decisions', "subject_type in ('gate','artifact','budget','spend')"
    )


def downgrade() -> None:
    held = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM approval_decisions WHERE subject_type = 'spend'"
    ).scalar()
    if held:
        raise RuntimeError(
            f"{held} spend confirmation(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER), 'approval_decisions', "subject_type in ('gate','artifact','budget')"
    )
    op.drop_constraint(op.f(_STUDY), 'studies', type_='check')
    op.drop_column('studies', 'spend_confirm_usd')
