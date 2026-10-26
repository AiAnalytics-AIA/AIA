"""The ONLY reader and writer of a study's wallet: ``study_wallets``, ``study_wallet_raises`` and
``study_wallet_charges`` (ADR 0028 decision 2, ``lead-orchestration`` LO1; ``make layer_check``).

**Atomic against concurrent overspend.** Every write that compares an amount (a cap change, a
charge) first takes a blocking ``SELECT … FOR UPDATE`` on the **study row**, then reads the open
wallet and the charges' sum, decides, and inserts, all in the caller's transaction. A second
writer of the same study waits on the row lock and, once the first commits, re-reads the sum the
first one left (READ COMMITTED takes a new snapshot per statement), so two charges can never both
fit the same remainder. The study row is locked rather than the wallet row because a wallet may
not exist yet when the first raise creates it, and a lock on a row that does not exist protects
nothing. SQLite has no ``FOR UPDATE`` and serialises writers.

**Lock order: the run, then the study that pays** -- the order every path that settles money
already keeps (``workflow_repository.py`` ``lock_run``, ``application/research.py``'s budget lift,
``application/client_work.py``). Nothing here locks a run or a client row. A caller that holds a
run's lock may call :meth:`StudyWalletRepository.charge` or ``quote`` (run, then study); a caller
must **never lock an existing run after** ``quote`` or ``charge`` in the same transaction (study,
then run, the reverse of the worker's attempt, run, study: a deadlock). A run the same transaction
just created is invisible to every other transaction, so creating it between ``quote`` and
``charge`` takes no lock anyone else can wait on.

**The study must be open.** Every amount-comparing write reads the study's status from the locked
row, so a study delivered, archived or cancelled meanwhile refuses the raise or the charge
(``study_closed``); the status change itself closes the wallet (``application/wallet.py``
``set_study_status``).

**A charge is a hold at the run's cost ceiling**, insert-once, never released and never
re-priced: remaining is the effective cap minus the charges' ceilings (``domain/money.py``
``wallet_remaining``). An unknown ceiling is refused, never charged as zero.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.approval_ledger import ApprovalSubject
from ..domain.money import RaiseVerdict, WalletVerdict, wallet_raise_verdict, wallet_verdict
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyStatus
from ..domain.wallet import (
    CHARGE_AUTHORITIES,
    CHARGE_DECISION,
    ChargeKind,
    StudyWallet,
    WalletCharge,
    WalletChargeRefused,
    WalletRaise,
    WalletRaiseRefused,
    new_wallet_id,
)
from .tables import (
    ClientRow,
    StudyRow,
    StudyWalletChargeRow,
    StudyWalletRaiseRow,
    StudyWalletRow,
    WorkflowRunRow,
    as_utc,
)
from .workflow_repository import WorkflowRepository

__all__ = ["StudyWalletRepository"]


class StudyWalletRepository:
    """A study's wallet, under the study's own context: no id parameter names another study."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("StudyWalletRepository requires a StudyContext")
        self._session = session
        self._scope = scope

    # ------------------------------------------------------------------ reads --

    def wallet(self) -> StudyWallet | None:
        """The study's open wallet with its bounds and the sum of its charges, or ``None``
        when the researcher has set none (then nothing starts without its own card)."""
        study = self._study(lock=False)
        row = self._open_row()
        return None if row is None else self._view(row, study)

    def raises(self) -> list[WalletRaise]:
        """Every change of the open wallet's cap, oldest first."""
        row = self._open_row()
        if row is None:
            return []
        rows = self._session.scalars(
            select(StudyWalletRaiseRow)
            .where(
                StudyWalletRaiseRow.wallet_id == row.wallet_id,
                StudyWalletRaiseRow.study_id == self._scope.study_id,
            )
            .order_by(StudyWalletRaiseRow.raise_id)
        ).all()
        return [
            WalletRaise(
                raise_id=r.raise_id,
                wallet_id=r.wallet_id,
                from_cap_usd=r.from_cap_usd,
                to_cap_usd=r.to_cap_usd,
                raised_by=r.raised_by,
                approval_decision_id=r.approval_decision_id,
                created_at=as_utc(r.created_at),
            )
            for r in rows
        ]

    def charges(self) -> list[WalletCharge]:
        """Every hold on the open wallet, oldest first."""
        row = self._open_row()
        if row is None:
            return []
        rows = self._session.scalars(
            select(StudyWalletChargeRow)
            .where(
                StudyWalletChargeRow.wallet_id == row.wallet_id,
                StudyWalletChargeRow.study_id == self._scope.study_id,
            )
            .order_by(StudyWalletChargeRow.charge_id)
        ).all()
        return [_charge(r) for r in rows]

    # ----------------------------------------------------------------- writes --

    def set_cap(self, to_cap_usd: float) -> StudyWallet:
        """Set the wallet's cap: the researcher's act, inside the client's wallet ceiling and
        the study's budget (``money.wallet_raise_verdict``; D-03), recorded once in the
        approval ledger (``wallet``) and once as a raise. Opens the study's wallet when it has
        none; the first cap is recorded whatever it is, USD 0 included, because opening a wallet
        is a person's act. Lowering the cap below what is charged is allowed: nothing remains,
        nothing already charged is undone. The same cap again on an open wallet writes nothing.
        A closed study refuses (``study_closed``).

        Needs ``APPROVE_BUDGET`` (the ledger row's permission), which the worker's scope does
        not hold. Raises :class:`WalletRaiseRefused` above either bound."""
        self._scope.require(Permission.APPROVE_BUDGET)
        to_cap = float(to_cap_usd)
        if isinstance(to_cap_usd, bool) or to_cap != to_cap or to_cap < 0:
            raise ValueError("a wallet's cap is a non-negative number of USD")
        study = self._study(lock=True, open_study=True)
        ceiling = self._client_ceiling()
        verdict = wallet_raise_verdict(
            to_cap, study_budget_usd=study.budget_usd, client_ceiling_usd=ceiling
        )
        if verdict is not RaiseVerdict.ALLOWED:
            bound = ceiling if verdict is RaiseVerdict.ABOVE_CLIENT_CEILING else study.budget_usd
            assert bound is not None
            raise WalletRaiseRefused(verdict, to_cap_usd=to_cap, bound_usd=bound)
        row = self._open_row()
        opened = row is None
        if row is None:
            row = StudyWalletRow(
                wallet_id=new_wallet_id(),
                organization_id=self._scope.organization_id,
                client_id=self._scope.client_id,
                study_id=self._scope.study_id,
                cap_usd=0.0,
            )
            self._session.add(row)
            self._session.flush()
        if not opened and row.cap_usd == to_cap:
            return self._view(row, study)
        decision_id = WorkflowRepository(self._session, self._scope).record_wallet_raise(
            row.wallet_id,
            from_cap_usd=row.cap_usd,
            to_cap_usd=to_cap,
            study_budget_usd=study.budget_usd,
            client_ceiling_usd=ceiling,
        )
        self._session.add(
            StudyWalletRaiseRow(
                wallet_id=row.wallet_id,
                study_id=self._scope.study_id,
                from_cap_usd=row.cap_usd,
                to_cap_usd=to_cap,
                raised_by=self._scope.actor_id,
                approval_decision_id=decision_id,
            )
        )
        row.cap_usd = to_cap
        self._session.flush()
        return self._view(row, study)

    def quote(self, ceiling_usd: float | None) -> tuple[WalletVerdict, float | None]:
        """Whether a start whose run can cost ``ceiling_usd`` fits the wallet now, and what
        remains (``None``: no wallet). Takes the study row's lock, so a caller that quotes,
        creates its run and then :meth:`charge`\\ s it in the same transaction sees no other
        charge land in between. Charges nothing."""
        self._scope.require(Permission.RUN_WORKFLOW)
        study = self._study(lock=True, open_study=True)
        row = self._open_row()
        if row is None:
            return WalletVerdict.OUTSIDE, None
        remaining = self._view(row, study).remaining_usd
        return wallet_verdict(ceiling_usd, remaining), remaining

    def charge(
        self,
        *,
        run_id: str,
        kind: ChargeKind,
        ceiling_usd: float | None,
        approval_decision_id: int,
        plan_id: str | None = None,
        plan_step_id: str | None = None,
    ) -> WalletCharge:
        """Hold ``ceiling_usd`` of the wallet for one started run of this study, once.

        Under the study row's lock, in an open study: the run must be this study's, and the
        authorising decision must be **this run's**: a ``chat_start``, ``plan_step`` or
        ``lead_card`` row of this study (``CHARGE_AUTHORITIES``) whose ``run_id`` is ``run_id``
        and whose decision is ``start`` (``CHARGE_DECISION``), used by no other charge (a unique
        key). A ``plan_step`` row names its step as its subject, and the charge names the same
        step and its plan (``plan_step_id``, ``plan_id``); a ``chat_start`` or ``lead_card``
        charge names neither. The ceiling must
        fit what remains. A run already charged returns its charge and charges nothing
        again. Raises :class:`WalletChargeRefused` (``no_wallet``, ``ceiling_unknown``,
        ``outside_wallet``) rather than charge zero or overspend; what the start does with the
        refusal (park a plan step, refuse a typed start) is its own rule.

        Needs ``RUN_WORKFLOW``, not an approval: the plan authority (LO3) holds no approval and
        charges as a step starts, under the decision a person already made."""
        self._scope.require(Permission.RUN_WORKFLOW)
        study = self._study(lock=True, open_study=True)
        kind = ChargeKind(kind)
        existing = self._session.scalar(
            select(StudyWalletChargeRow).where(StudyWalletChargeRow.run_id == run_id)
        )
        if existing is not None:
            if existing.study_id != self._scope.study_id:
                raise ScopeDenied("not found", reason="unknown_run")
            return _charge(existing)
        if (
            self._session.scalar(
                select(WorkflowRunRow.run_id).where(
                    WorkflowRunRow.run_id == run_id,
                    WorkflowRunRow.study_id == self._scope.study_id,
                    WorkflowRunRow.client_id == self._scope.client_id,
                )
            )
            is None
        ):
            raise ScopeDenied("not found", reason="unknown_run")
        self._authorised(
            approval_decision_id, run_id=run_id, plan_id=plan_id, plan_step_id=plan_step_id
        )
        row = self._open_row()
        if row is None:
            raise WalletChargeRefused("no_wallet", ceiling_usd=ceiling_usd, remaining_usd=None)
        remaining = self._view(row, study).remaining_usd
        verdict = wallet_verdict(ceiling_usd, remaining)
        if verdict is not WalletVerdict.FITS:
            raise WalletChargeRefused.of(verdict, ceiling_usd=ceiling_usd, remaining_usd=remaining)
        assert ceiling_usd is not None
        charge = StudyWalletChargeRow(
            wallet_id=row.wallet_id,
            study_id=self._scope.study_id,
            run_id=run_id,
            kind=kind.value,
            ceiling_usd=float(ceiling_usd),
            plan_id=plan_id,
            plan_step_id=plan_step_id,
            approval_decision_id=approval_decision_id,
        )
        self._session.add(charge)
        self._session.flush()
        return _charge(charge)

    def close(self) -> bool:
        """Close the study's open wallet, in the transaction that closes the study
        (``application/wallet.py`` ``set_study_status``). ``False`` when it had none. Its raises
        and charges stay; a raise after the study reopens opens a new wallet. Needs what the
        status change needs: ``EDIT_STUDY``, or ``SIGN_OFF_DELIVERABLE`` for a delivery."""
        if not self._scope.has(Permission.SIGN_OFF_DELIVERABLE):
            self._scope.require(Permission.EDIT_STUDY)
        self._study(lock=True)
        row = self._open_row()
        if row is None:
            return False
        row.closed_at = datetime.now(UTC)
        self._session.flush()
        return True

    # ---------------------------------------------------------------- helpers --

    def _authorised(
        self,
        decision_id: int,
        *,
        run_id: str,
        plan_id: str | None,
        plan_step_id: str | None,
    ) -> None:
        def refuse(why: str) -> ScopeDenied:
            return ScopeDenied(f"a wallet charge is not authorised: {why}", reason=why)

        entry = WorkflowRepository(self._session, self._scope).ledger_entry(decision_id)
        if entry is None or entry.subject not in CHARGE_AUTHORITIES:
            raise refuse("not_a_start_decision")
        if entry.run_id != run_id:
            raise refuse("decision_names_another_run")
        if entry.decision != CHARGE_DECISION:
            raise refuse("decision_not_a_start")
        if entry.subject is ApprovalSubject.PLAN_STEP:
            if plan_id is None or plan_step_id is None or entry.subject_id != plan_step_id:
                raise refuse("plan_step_mismatch")
        elif plan_id is not None or plan_step_id is not None:
            raise refuse("chat_start_names_a_plan")
        used = self._session.scalar(
            select(StudyWalletChargeRow.charge_id).where(
                StudyWalletChargeRow.approval_decision_id == decision_id
            )
        )
        if used is not None:
            raise refuse("decision_already_used")

    def _study(self, *, lock: bool, open_study: bool = False) -> StudyRow:
        query = select(StudyRow).where(
            StudyRow.study_id == self._scope.study_id,
            StudyRow.client_id == self._scope.client_id,
            StudyRow.organization_id == self._scope.organization_id,
        )
        if lock:
            # Blocking FOR UPDATE, never skip_locked: a concurrent writer waits, then re-reads.
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self._session.scalar(query)
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")
        if open_study and not StudyStatus(row.status).accepts_work:
            # The locked row's status, not the context's: a study closed since the context was
            # issued refuses too.
            raise ScopeDenied(
                f"study is {row.status} and accepts no further work", reason="study_closed"
            )
        return row

    def _client_ceiling(self) -> float | None:
        return self._session.scalar(
            select(ClientRow.wallet_ceiling_usd).where(
                ClientRow.client_id == self._scope.client_id,
                ClientRow.organization_id == self._scope.organization_id,
            )
        )

    def _open_row(self) -> StudyWalletRow | None:
        return self._session.scalar(
            select(StudyWalletRow)
            .where(
                StudyWalletRow.study_id == self._scope.study_id,
                StudyWalletRow.client_id == self._scope.client_id,
                StudyWalletRow.closed_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )

    def _charged(self, wallet_id: str) -> float:
        """The charges' ceilings summed as decimals, never in the database's binary floats
        (USD 0.10 + 0.20 is 0.30, not 0.30000000000000004)."""
        ceilings = self._session.scalars(
            select(StudyWalletChargeRow.ceiling_usd).where(
                StudyWalletChargeRow.wallet_id == wallet_id
            )
        ).all()
        return float(sum((Decimal(repr(float(c))) for c in ceilings), Decimal(0)))

    def _view(self, row: StudyWalletRow, study: StudyRow) -> StudyWallet:
        return StudyWallet(
            wallet_id=row.wallet_id,
            study_id=row.study_id,
            cap_usd=row.cap_usd,
            study_budget_usd=study.budget_usd,
            client_ceiling_usd=self._client_ceiling(),
            charged_usd=self._charged(row.wallet_id),
            created_at=as_utc(row.created_at),
        )


def _charge(row: StudyWalletChargeRow) -> WalletCharge:
    return WalletCharge(
        charge_id=row.charge_id,
        wallet_id=row.wallet_id,
        run_id=row.run_id,
        kind=ChargeKind(row.kind),
        ceiling_usd=row.ceiling_usd,
        plan_id=row.plan_id,
        plan_step_id=row.plan_step_id,
        approval_decision_id=row.approval_decision_id,
        created_at=as_utc(row.created_at),
    )
