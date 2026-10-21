"""A study's wallet (Peněženka) behind its switch (ADR 0028 decision 2, ``lead-orchestration`` LO1).

``AIA_STUDY_WALLET_ENABLED`` (off by default, off in test, absent from the develop Compose file)
decides whether anything reads or writes the wallet. Off, every call here raises
:class:`WalletDisabled` before the repository is built, so no wallet row is read or written and
no existing spend path changes: a person's start on the Run stage never consults the wallet
either way (``money.start_verdict``, ``StartPath.PERSON``). The starts that do consult it, the
typed chat start (LO5) and the plan step (LO3/LO4), call :meth:`StudyWallets.charge` inside the
transaction that creates their run, after :meth:`StudyWallets.quote` under the same study lock.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.money import WalletVerdict
from ..domain.scope import StudyContext
from ..domain.wallet import (
    ChargeKind,
    StudyWallet,
    WalletCharge,
    WalletChargeRefused,
    WalletRaise,
    WalletRaiseRefused,
)
from ..infrastructure.study_wallet_repository import StudyWalletRepository

__all__ = [
    "StudyWallets",
    "WalletChargeRefused",
    "WalletDisabled",
    "WalletRaiseRefused",
]


class WalletDisabled(Exception):
    """The wallet is switched off (``AIA_STUDY_WALLET_ENABLED``): nothing is read or written."""

    reason = "wallet_disabled"


class StudyWallets:
    """The wallet of the study in ``scope``, or nothing when the switch is off."""

    def __init__(self, session: Session, scope: StudyContext, *, enabled: bool) -> None:
        self._session = session
        self._scope = scope
        self._enabled = enabled

    def _repository(self) -> StudyWalletRepository:
        if not self._enabled:
            raise WalletDisabled("the study wallet is switched off (AIA_STUDY_WALLET_ENABLED)")
        return StudyWalletRepository(self._session, self._scope)

    def read(self) -> tuple[StudyWallet | None, list[WalletRaise], list[WalletCharge]]:
        """The open wallet (``None``: none set), its raises and its charges."""
        repo = self._repository()
        return repo.wallet(), repo.raises(), repo.charges()

    def set_cap(self, cap_usd: float) -> StudyWallet:
        """The researcher sets the wallet's cap; :class:`WalletRaiseRefused` above a bound."""
        return self._repository().set_cap(cap_usd)

    def quote(self, ceiling_usd: float | None) -> tuple[WalletVerdict, float | None]:
        """Whether a ceiling fits now, under the study lock; charges nothing."""
        return self._repository().quote(ceiling_usd)

    def charge(
        self,
        *,
        run_id: str,
        kind: ChargeKind,
        ceiling_usd: float | None,
        approval_decision_id: int,
        plan_id: str | None = None,
    ) -> WalletCharge:
        """Hold a started run's ceiling; :class:`WalletChargeRefused` when it does not fit."""
        return self._repository().charge(
            run_id=run_id,
            kind=kind,
            ceiling_usd=ceiling_usd,
            approval_decision_id=approval_decision_id,
            plan_id=plan_id,
        )
