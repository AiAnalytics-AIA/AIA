"""Record a respondent system's validation verdict, as a person recorded it

Panel-grounded respondents 7f1 (plans/panel-grounded-respondents.md). When a validation Study's
confirmation run has scored, a researcher records its verdict: ``respondent_validations`` keeps
it once per Study, copied from the run's verdict artifact (never chosen), with the hashes it
rests on. A ``PASS`` is the system's ``HOLDOUT_VALIDATED`` state; a ``FAIL`` is kept as well.
``approval_decisions.subject_type`` admits ``'validation'``, so the person's act is in the same
append-only ledger as every other decision. The ledger constraint is named with ``op.f`` on
drop and on create (AGENTS.md § Alembic). Nothing existing changes.

Revision ID: d8f0b2c4e6a9
Revises: a8c0e2f4b6d1
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d8f0b2c4e6a9"
down_revision: str | None = "a8c0e2f4b6d1"
branch_labels = None
depends_on = None

_LEDGER = "ck_approval_decisions_approval_subject_type_known"


def upgrade() -> None:
    op.create_table(
        "respondent_validations",
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("respondent_system_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("truth", sa.String(length=32), nullable=False),
        sa.Column("preregistration_sha256", sa.String(length=64), nullable=False),
        sa.Column("verdict_artifact_id", sa.String(length=64), nullable=False),
        sa.Column("verdict_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "verdict in ('PASS','FAIL')",
            name=op.f("ck_respondent_validations_respondent_validation_verdict"),
        ),
        sa.CheckConstraint(
            "(verdict = 'PASS' and status = 'HOLDOUT_VALIDATED') or "
            "(verdict = 'FAIL' and status = 'NOT_VALIDATED')",
            name=op.f("ck_respondent_validations_respondent_validation_status_is_the_verdict"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_respondent_validations_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["holdout_confirmations.study_id"],
            name=op.f("fk_respondent_validations_study_id_holdout_confirmations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("study_id", name=op.f("pk_respondent_validations")),
    )
    op.create_index(
        "ix_respondent_validations_system",
        "respondent_validations",
        ["organization_id", "respondent_system_fingerprint"],
        unique=False,
    )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(
        op.f(_LEDGER),
        "approval_decisions",
        "subject_type in ('gate','artifact','budget','spend','ai_proposal','design_research',"
        "'validation')",
    )


def downgrade() -> None:
    held = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM approval_decisions WHERE subject_type = 'validation'"
        )
        .scalar()
    )
    if held:
        raise RuntimeError(
            f"{held} validation record(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(
        op.f(_LEDGER),
        "approval_decisions",
        "subject_type in ('gate','artifact','budget','spend','ai_proposal','design_research')",
    )
    op.drop_index("ix_respondent_validations_system", table_name="respondent_validations")
    op.drop_table("respondent_validations")
