"""the study wallet, its raises and charges

Revision ID: 60ccc9ff42cf
Revises: b5d7f9a1c3e6
Created: 2026-10-21 04:47:39.960899+00:00

Migration M4 of the MVP's lane (``lead-orchestration`` LO1; ADR 0028 decision 2): the wallet
(Peněženka), what a study's paid work may start without a further card.

* ``study_wallets``: one open wallet per study (``uq_study_wallets_open``, partial on
  ``closed_at IS NULL``), its cap;
* ``study_wallet_raises``: insert-once, each change of the cap with the approval-ledger row
  (``wallet``, admitted by M3) that records it;
* ``study_wallet_charges``: insert-once, one per started run (``run_id`` unique), at its cost
  ceiling, with the ledger row that authorised the start;
* ``clients.wallet_ceiling_usd``: nullable, the bound on every open wallet of the client's
  studies.

Nothing writes them unless ``AIA_STUDY_WALLET_ENABLED`` is on (off by default). The charge kinds
are listed literally here, as they were when this ran; the model builds them from
``domain/wallet.py`` ``ChargeKind``. The downgrade refuses while a raise or a charge is stored:
both are insert-once records of a person's decision and a run's hold.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "60ccc9ff42cf"
down_revision: str | None = "b5d7f9a1c3e6"
branch_labels = None
depends_on = None

_KINDS = ("research_run", "agent_job", "deep_research", "interpretation_research")
_CLIENT_CEILING = "ck_clients_client_wallet_ceiling_non_negative"


def upgrade() -> None:
    op.create_table(
        "study_wallets",
        sa.Column("wallet_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("cap_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "cap_usd >= 0", name=op.f("ck_study_wallets_study_wallet_cap_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_study_wallets_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_study_wallets_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wallet_id", name=op.f("pk_study_wallets")),
    )
    op.create_index(
        "uq_study_wallets_open",
        "study_wallets",
        ["study_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "study_wallet_raises",
        sa.Column("raise_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("from_cap_usd", sa.Float(), nullable=False),
        sa.Column("to_cap_usd", sa.Float(), nullable=False),
        sa.Column("raised_by", sa.String(length=64), nullable=False),
        sa.Column("approval_decision_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "from_cap_usd >= 0", name=op.f("ck_study_wallet_raises_wallet_raise_from_non_negative")
        ),
        sa.CheckConstraint(
            "to_cap_usd >= 0", name=op.f("ck_study_wallet_raises_wallet_raise_to_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["approval_decision_id"],
            ["approval_decisions.decision_id"],
            name=op.f("fk_study_wallet_raises_approval_decision_id_approval_decisions"),
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_study_wallet_raises_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["study_wallets.wallet_id"],
            name=op.f("fk_study_wallet_raises_wallet_id_study_wallets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("raise_id", name=op.f("pk_study_wallet_raises")),
        sa.UniqueConstraint("approval_decision_id", name="wallet_raise_decision_once"),
    )
    op.create_index(
        "ix_study_wallet_raises_wallet",
        "study_wallet_raises",
        ["wallet_id", "raise_id"],
        unique=False,
    )
    op.create_table(
        "study_wallet_charges",
        sa.Column("charge_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ceiling_usd", sa.Float(), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=True),
        sa.Column("plan_step_id", sa.String(length=64), nullable=True),
        sa.Column("approval_decision_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind in (" + ",".join(f"'{k}'" for k in _KINDS) + ")",
            name=op.f("ck_study_wallet_charges_wallet_charge_kind_known"),
        ),
        sa.CheckConstraint(
            "ceiling_usd >= 0",
            name=op.f("ck_study_wallet_charges_wallet_charge_ceiling_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["approval_decision_id"],
            ["approval_decisions.decision_id"],
            name=op.f("fk_study_wallet_charges_approval_decision_id_approval_decisions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.run_id"],
            name=op.f("fk_study_wallet_charges_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_study_wallet_charges_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["study_wallets.wallet_id"],
            name=op.f("fk_study_wallet_charges_wallet_id_study_wallets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("charge_id", name=op.f("pk_study_wallet_charges")),
        sa.UniqueConstraint("run_id", name="wallet_charge_run_once"),
        sa.UniqueConstraint("approval_decision_id", name="wallet_charge_decision_once"),
        sa.CheckConstraint(
            "(plan_id is null) = (plan_step_id is null)",
            name=op.f("ck_study_wallet_charges_wallet_charge_plan_and_step"),
        ),
    )
    op.create_index(
        "ix_study_wallet_charges_wallet", "study_wallet_charges", ["wallet_id"], unique=False
    )
    op.add_column("clients", sa.Column("wallet_ceiling_usd", sa.Float(), nullable=True))
    op.create_check_constraint(
        op.f(_CLIENT_CEILING),
        "clients",
        "wallet_ceiling_usd is null or wallet_ceiling_usd >= 0",
    )


def downgrade() -> None:
    bind = op.get_bind()
    held = sum(
        int(bind.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar() or 0)
        for table in ("study_wallet_raises", "study_wallet_charges")
    )
    if held:
        raise RuntimeError(
            f"{held} wallet raise(s) or charge(s) are stored, which are insert-once records; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_CLIENT_CEILING), "clients", type_="check")
    op.drop_column("clients", "wallet_ceiling_usd")
    op.drop_index("ix_study_wallet_charges_wallet", table_name="study_wallet_charges")
    op.drop_table("study_wallet_charges")
    op.drop_index("ix_study_wallet_raises_wallet", table_name="study_wallet_raises")
    op.drop_table("study_wallet_raises")
    op.drop_index(
        "uq_study_wallets_open",
        table_name="study_wallets",
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.drop_table("study_wallets")
