"""A study's wallet (Peněženka): its cap, its raises and its charges, as values.

ADR 0028 decision 2 (``lead-orchestration`` LO1, migration M4). The rules are ``money.py``'s;
this module holds what the wallet's three tables store and the one derived figure they do not:
the **effective cap**, which no stored row says by itself.

* A wallet is one per open study (``study_wallets``, a partial unique index ``WHERE closed_at
  IS NULL``). It has no expiry and closes with its study.
* A **raise** (``study_wallet_raises``) is the researcher's act, insert-once, ``from`` and
  ``to``; it writes one approval-ledger row (``ApprovalSubject.WALLET``). A raise above the
  client's wallet ceiling is refused, naming who can raise the ceiling (D-03); a raise above the
  study's budget is refused (a wallet is a slice of the budget and never raises it).
* A **charge** (``study_wallet_charges``) is a hold of one started run's **cost ceiling**,
  insert-once, never released and never re-priced: remaining is the effective cap minus the
  charges' ceilings, never their settled spend, so concurrent starts can never exceed the cap
  (ADR 0028 decision 2, "Charge the wallet by settled spend" rejected). Settled spend is read
  from the usage ledger, for display only. A charge is authorised by one approval-ledger row of
  a start that consults the wallet (``CHARGE_AUTHORITIES``), naming the run it charges, used
  once.

The effective cap is the smallest of the wallet's own cap, the client's wallet ceiling (when one
is set) and the study's budget: a ceiling lowered, or a budget cut, after a raise bounds the
wallet at once, never later. No I/O: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import uuid4

from .approval_ledger import ApprovalSubject
from .money import RaiseVerdict, WalletVerdict, wallet_remaining
from .scope import OrganizationRole

__all__ = [
    "CHARGE_AUTHORITIES",
    "CHARGE_DECISION",
    "WALLET_CEILING_SETTERS",
    "ChargeKind",
    "StudyWallet",
    "WalletCharge",
    "WalletChargeRefused",
    "WalletRaise",
    "WalletRaiseRefused",
    "effective_cap",
    "new_wallet_id",
]


def new_wallet_id() -> str:
    """A new wallet id."""
    return "WAL-" + uuid4().hex[:14]


class ChargeKind(StrEnum):
    """What a charge paid for: the four kinds of paid work a plan step or a typed start may
    begin (ADR 0028 decision 4). Deep Research is charged at its ceiling until migration M11
    reconciles its tool spend (D-05)."""

    RESEARCH_RUN = "research_run"
    AGENT_JOB = "agent_job"
    DEEP_RESEARCH = "deep_research"
    INTERPRETATION_RESEARCH = "interpretation_research"


#: The approval-ledger subjects that may authorise a charge: the two starts that consult the
#: wallet (ADR 0028 decision 3). A person's own start on the Run stage does not consult it
#: (``money.start_verdict``, ``StartPath.PERSON``), so it neither needs nor writes a charge.
CHARGE_AUTHORITIES: Final[frozenset[ApprovalSubject]] = frozenset(
    {ApprovalSubject.CHAT_START, ApprovalSubject.PLAN_STEP}
)

#: The decision a start's ledger row records when a person started it (the approving value a
#: ``chat_start`` or ``plan_step`` row carries); any other decision authorises no charge.
CHARGE_DECISION: Final = "start"

#: Who may set ``clients.wallet_ceiling_usd`` (ADR 0028 decision 1), named in a refusal of a
#: raise above it (D-03: there is no approver queue; the refusal says who can raise the ceiling).
WALLET_CEILING_SETTERS: Final[tuple[OrganizationRole, ...]] = (
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
)


def effective_cap(
    cap_usd: float, *, study_budget_usd: float, client_ceiling_usd: float | None
) -> float:
    """What a wallet may hold now: its cap, bounded by the client's wallet ceiling (when set)
    and the study's budget. Never above either, whenever either moved."""
    bounds = [float(cap_usd), float(study_budget_usd)]
    if client_ceiling_usd is not None:
        bounds.append(float(client_ceiling_usd))
    return max(0.0, min(bounds))


@dataclass(frozen=True, slots=True)
class WalletRaise:
    """One change of a wallet's cap, as stored: who, from, to, and its ledger row."""

    raise_id: int
    wallet_id: str
    from_cap_usd: float
    to_cap_usd: float
    raised_by: str
    approval_decision_id: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WalletCharge:
    """One started run's hold on the wallet, at its cost ceiling, as stored."""

    charge_id: int
    wallet_id: str
    run_id: str
    kind: ChargeKind
    ceiling_usd: float
    plan_id: str | None
    plan_step_id: str | None
    approval_decision_id: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StudyWallet:
    """A study's open wallet as a screen reads it (the two meters: the budget spent, and the
    wallet remaining on click). ``remaining_usd`` is by ceilings (ADR 0028 decision 2)."""

    wallet_id: str
    study_id: str
    cap_usd: float
    study_budget_usd: float
    client_ceiling_usd: float | None
    charged_usd: float
    created_at: datetime

    @property
    def effective_cap_usd(self) -> float:
        return effective_cap(
            self.cap_usd,
            study_budget_usd=self.study_budget_usd,
            client_ceiling_usd=self.client_ceiling_usd,
        )

    @property
    def remaining_usd(self) -> float:
        return wallet_remaining(self.effective_cap_usd, [self.charged_usd])


class WalletRaiseRefused(Exception):
    """A raise the rules refuse: above the client's wallet ceiling or the study's budget.

    ``who_can_raise`` names the roles that can raise the client's ceiling (D-03), for the
    refusal above it; empty for a refusal above the study's budget."""

    def __init__(self, verdict: RaiseVerdict, *, to_cap_usd: float, bound_usd: float) -> None:
        if verdict is RaiseVerdict.ALLOWED:
            raise ValueError("an allowed raise is not refused")
        self.verdict = verdict
        self.reason = verdict.value
        self.to_cap_usd = to_cap_usd
        self.bound_usd = bound_usd
        self.who_can_raise: tuple[OrganizationRole, ...] = (
            WALLET_CEILING_SETTERS if verdict is RaiseVerdict.ABOVE_CLIENT_CEILING else ()
        )
        super().__init__(f"{verdict.value}: {to_cap_usd} above {bound_usd}")


class WalletChargeRefused(Exception):
    """A charge that does not fit, or cannot be made: never a zero charge, never an overspend.

    ``reason``: ``no_wallet`` (the study has no open wallet), ``ceiling_unknown`` (an unknown
    ceiling is refused, never read as zero), ``outside_wallet`` (the ceiling exceeds what
    remains). A plan step that meets it parks, a typed start is refused (``money.start_verdict``);
    the wallet's own repository decides neither."""

    def __init__(self, reason: str, *, ceiling_usd: float | None, remaining_usd: float | None):
        self.reason = reason
        self.ceiling_usd = ceiling_usd
        self.remaining_usd = remaining_usd
        super().__init__(f"{reason}: ceiling {ceiling_usd}, remaining {remaining_usd}")

    @classmethod
    def of(
        cls, verdict: WalletVerdict, *, ceiling_usd: float | None, remaining_usd: float
    ) -> WalletChargeRefused:
        if verdict is WalletVerdict.FITS:
            raise ValueError("a charge that fits is not refused")
        reason = "ceiling_unknown" if verdict is WalletVerdict.CEILING_UNKNOWN else "outside_wallet"
        return cls(reason, ceiling_usd=ceiling_usd, remaining_usd=remaining_usd)
