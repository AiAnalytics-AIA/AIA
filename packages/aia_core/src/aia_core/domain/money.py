"""The money a study's paid work is held against: five amounts, four of them named on
screen, and one precedence.

ADR 0028 decision 1 (lead-orchestration LO0; the product owner's names of 2026-10-20, D-01):

=====================  ============================  ===================  =========================
amount                 column                        on screen            what it does
=====================  ============================  ===================  =========================
the client's budget    ``clients.budget_usd``        Rozpočet klienta     the cap of the client's
                                                                          own work (source
                                                                          proposals), outside
                                                                          every study and wallet
the study's budget     ``studies.budget_usd``        Rozpočet studie      **the cap**: a
                                                                          reservation that does
                                                                          not fit parks
                                                                          ``AWAITING_BUDGET``
the wallet             ``study_wallets.cap_usd``     Peněženka            what paid work may start
                                                                          without a further card;
                                                                          a slice of the study's
                                                                          budget
the threshold          ``studies.spend_confirm_usd`` Práh potvrzení       a per-start confirmation:
                                                                          a start whose ceiling
                                                                          reaches it asks; null
                                                                          never asks
=====================  ============================  ===================  =========================

``clients.wallet_ceiling_usd`` bounds every open wallet of the client's studies (set by an
organization OWNER or ADMIN); null means a wallet may not exceed its study's budget. A wallet
never exceeds its study's budget either way, and never raises it.

**One precedence.** The study's budget stops spending, at every reservation, whatever started the
work; the wallet decides what may start without a card; the threshold decides what asks again.
The threshold is **never a cap** and is never called a hard stop: with it unset, nothing asks and
the budget still stops spending.

**A cost is a ceiling, never a guess.** A start is judged by its run's cost ceiling
(``domain/run_cost.py``), an upper bound; an unknown ceiling is refused wherever a rule needs it,
never read as zero (ARCHITECTURE.md §10, A4). A retried attempt is judged by its own full ceiling
again: until a fieldwork attempt keeps the respondents it already paid for (OI-64,
``run-qc-and-checkpoint`` RQC0), a retry may pay them again, so nothing here assumes it reuses
them.

The wallet itself is built by LO1 (migration M4), the plan step by LO3/LO4 and the typed chat
start by LO5; this module is their shared rule, written first so each implements the same one.
Pure: stdlib only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "MONEY",
    "PRECEDENCE",
    "AmountRole",
    "AmountSpec",
    "MoneyAmount",
    "RaiseVerdict",
    "StartPath",
    "StartVerdict",
    "StartVerdictKind",
    "ThresholdVerdict",
    "WalletVerdict",
    "start_verdict",
    "threshold_verdict",
    "wallet_raise_verdict",
    "wallet_remaining",
    "wallet_verdict",
]


class MoneyAmount(StrEnum):
    """One of the amounts paid work is held against."""

    CLIENT_BUDGET = "client_budget"
    STUDY_BUDGET = "study_budget"
    WALLET = "wallet"
    CONFIRM_THRESHOLD = "confirm_threshold"
    WALLET_CEILING = "wallet_ceiling"


class AmountRole(StrEnum):
    """What an amount does to a start or a spend."""

    #: Stops spending: a reservation that does not fit parks.
    CAP = "cap"
    #: Decides what may start without a further card.
    ALLOWANCE = "allowance"
    #: Decides what asks the person again before it starts.
    THRESHOLD = "threshold"
    #: Bounds another amount; spends nothing itself.
    BOUND = "bound"


@dataclass(frozen=True, slots=True)
class AmountSpec:
    """One amount: where it is stored, its name on screen, what it does and who sets it.

    ``czech`` is ``None`` where the owner has named no screen label (the wallet ceiling): a
    screen says nothing rather than invent one."""

    amount: MoneyAmount
    column: str
    czech: str | None
    role: AmountRole
    set_by: str
    null_means: str


MONEY: Final[Mapping[MoneyAmount, AmountSpec]] = MappingProxyType(
    {
        MoneyAmount.CLIENT_BUDGET: AmountSpec(
            MoneyAmount.CLIENT_BUDGET,
            "clients.budget_usd",
            "Rozpočet klienta",
            AmountRole.CAP,
            "a member (client-budget CB1)",
            "never null: 0 pays for nothing",
        ),
        MoneyAmount.STUDY_BUDGET: AmountSpec(
            MoneyAmount.STUDY_BUDGET,
            "studies.budget_usd",
            "Rozpočet studie",
            AmountRole.CAP,
            "a member (ADR 0019)",
            "never null: 0 pays for nothing",
        ),
        MoneyAmount.WALLET: AmountSpec(
            MoneyAmount.WALLET,
            "study_wallets.cap_usd",
            "Peněženka",
            AmountRole.ALLOWANCE,
            "the researcher, up to the wallet ceiling (lead-orchestration LO1)",
            "no wallet: nothing starts without its own card",
        ),
        MoneyAmount.CONFIRM_THRESHOLD: AmountSpec(
            MoneyAmount.CONFIRM_THRESHOLD,
            "studies.spend_confirm_usd",
            "Práh potvrzení",
            AmountRole.THRESHOLD,
            "a member (ADR 0019 gate 2)",
            "never asks",
        ),
        MoneyAmount.WALLET_CEILING: AmountSpec(
            MoneyAmount.WALLET_CEILING,
            "clients.wallet_ceiling_usd",
            None,
            AmountRole.BOUND,
            "an organization OWNER or ADMIN (client-knowledge-lifecycle K11)",
            "a wallet may not exceed its study's budget",
        ),
    }
)

#: The order a study's paid work meets the amounts: the budget stops spending, then the wallet
#: decides what starts without a card, then the threshold decides what asks again.
PRECEDENCE: Final[tuple[MoneyAmount, ...]] = (
    MoneyAmount.STUDY_BUDGET,
    MoneyAmount.WALLET,
    MoneyAmount.CONFIRM_THRESHOLD,
)


# --------------------------------------------------------------------------- the threshold


class ThresholdVerdict(StrEnum):
    """What the confirmation threshold says of one start."""

    #: No threshold, or the ceiling is below it: nothing to ask.
    NOT_ASKED = "not_asked"
    #: The ceiling reaches the threshold and the person confirmed at least the ceiling.
    CONFIRMED = "confirmed"
    #: The ceiling reaches the threshold and nothing covering it was confirmed.
    ASK = "ask"
    #: A threshold is set and the ceiling cannot be worked out: the start is not let by.
    CEILING_UNKNOWN = "ceiling_unknown"


def _usd(value: float | None, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or value != value:
        raise ValueError(f"{what} must be a number of USD")
    if value < 0:
        raise ValueError(f"{what} must not be negative")
    return float(value)


def threshold_verdict(
    ceiling_usd: float | None, threshold_usd: float | None, confirmed_usd: float | None = None
) -> ThresholdVerdict:
    """The confirmation rule of ADR 0019 gate 2, as a start applies it.

    A start whose cost ceiling **reaches** the threshold (``>=``) asks, unless the person
    confirmed at least that ceiling; with no threshold nothing asks, whatever the ceiling; with a
    threshold and an unknown ceiling the start is refused, never let by as if it cost nothing."""
    ceiling = _usd(ceiling_usd, "the ceiling")
    threshold = _usd(threshold_usd, "the threshold")
    confirmed = _usd(confirmed_usd, "the confirmed amount")
    if threshold is None:
        return ThresholdVerdict.NOT_ASKED
    if ceiling is None:
        return ThresholdVerdict.CEILING_UNKNOWN
    if ceiling < threshold:
        return ThresholdVerdict.NOT_ASKED
    if confirmed is not None and confirmed >= ceiling:
        return ThresholdVerdict.CONFIRMED
    return ThresholdVerdict.ASK


# --------------------------------------------------------------------------- the wallet


class WalletVerdict(StrEnum):
    """Whether a start fits what remains of the study's wallet."""

    FITS = "fits"
    OUTSIDE = "outside"
    CEILING_UNKNOWN = "ceiling_unknown"


def wallet_remaining(cap_usd: float, charges_usd: Iterable[float]) -> float:
    """What remains of a wallet: its cap minus the **ceilings** of the runs charged to it (ADR
    0028 decision 2), never their settled spend, so concurrent starts can never exceed the cap.
    Never negative."""
    cap = _usd(cap_usd, "the wallet's cap")
    assert cap is not None
    spent = 0.0
    for charge in charges_usd:
        value = _usd(charge, "a charge")
        if value is None:
            raise ValueError("a charge is a known ceiling: an unknown one is refused at start")
        spent += value
    return max(0.0, cap - spent)


def wallet_verdict(ceiling_usd: float | None, remaining_usd: float) -> WalletVerdict:
    """Whether a start whose run can cost ``ceiling_usd`` fits ``remaining_usd`` of the wallet.
    An unknown ceiling never fits (``CostCeilingUnknown``, ADR 0028 decision 2)."""
    ceiling = _usd(ceiling_usd, "the ceiling")
    remaining = _usd(remaining_usd, "the wallet's remaining")
    assert remaining is not None
    if ceiling is None:
        return WalletVerdict.CEILING_UNKNOWN
    return WalletVerdict.FITS if ceiling <= remaining else WalletVerdict.OUTSIDE


class RaiseVerdict(StrEnum):
    """Whether a researcher may set a wallet's cap to a new amount."""

    ALLOWED = "allowed"
    #: Above the client's wallet ceiling: refused, naming who can raise the ceiling (an
    #: organization OWNER or ADMIN on Profil → Pravidla); there is no approver queue (D-03).
    ABOVE_CLIENT_CEILING = "above_client_ceiling"
    #: Above the study's budget: a wallet is a slice of it and never raises it.
    ABOVE_STUDY_BUDGET = "above_study_budget"


def wallet_raise_verdict(
    to_cap_usd: float, *, study_budget_usd: float, client_ceiling_usd: float | None
) -> RaiseVerdict:
    """The rule for a wallet's new cap (ADR 0028 decisions 1 and 2; the owner's D-03)."""
    to_cap = _usd(to_cap_usd, "the wallet's cap")
    budget = _usd(study_budget_usd, "the study's budget")
    ceiling = _usd(client_ceiling_usd, "the client's wallet ceiling")
    assert to_cap is not None and budget is not None
    if ceiling is not None and to_cap > ceiling:
        return RaiseVerdict.ABOVE_CLIENT_CEILING
    if to_cap > budget:
        return RaiseVerdict.ABOVE_STUDY_BUDGET
    return RaiseVerdict.ALLOWED


# --------------------------------------------------------------------------- one start


class StartPath(StrEnum):
    """Who starts paid work in a study (ADR 0028 decision 3)."""

    #: A person on the Run stage (or a job's own button): their act is the card.
    PERSON = "person"
    #: A person's typed request in the composer, matched by the server (``chat_start``).
    CHAT_START = "chat_start"
    #: A step of an approved plan, under the plan authority (``plan_step``).
    PLAN_STEP = "plan_step"


class StartVerdictKind(StrEnum):
    START = "start"
    #: Ask the person who is starting it, in the same exchange.
    ASK = "ask"
    #: A plan step stops and shows a card (``AWAITING_GATE``, its reason named).
    PARK = "park"
    #: Not started; the reason says why.
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class StartVerdict:
    kind: StartVerdictKind
    #: A stable word: ``ceiling_unknown``, ``outside_wallet``, ``ceiling_grew``,
    #: ``not_confirmed``, ``confirm``, or ``None`` for a plain start.
    reason: str | None = None


def start_verdict(
    path: StartPath,
    *,
    ceiling_usd: float | None,
    threshold_usd: float | None,
    confirmed_usd: float | None = None,
    wallet_remaining_usd: float | None = None,
    shown_ceiling_usd: float | None = None,
) -> StartVerdict:
    """What the precedence says of one start of paid work, before anything is reserved.

    * ``PERSON``: the threshold alone (today's rule); the wallet is not consulted, because the
      person's own act is the card the wallet saves.
    * ``CHAT_START``: inside the wallet only (``wallet_remaining_usd``; ``None``: no wallet, so
      refused); a ceiling reaching the threshold asks the person in the same exchange.
    * ``PLAN_STEP``: inside the wallet, else it parks; the plan's approval confirmed the ceiling
      its card showed (``shown_ceiling_usd``, D-02), so a step whose ceiling did not grow past it
      starts without asking again, and one whose ceiling grew and reaches the threshold parks.
      A plan step never asks and never confirms: ``confirmed_usd`` is refused for it.

    The study's budget is not consulted here: it stops spending at each reservation, for every
    path (``workflow_repository``), whatever this says."""
    if path is StartPath.PERSON:
        verdict = threshold_verdict(ceiling_usd, threshold_usd, confirmed_usd)
        if verdict is ThresholdVerdict.CEILING_UNKNOWN:
            return StartVerdict(StartVerdictKind.REFUSED, "ceiling_unknown")
        if verdict is ThresholdVerdict.ASK:
            return StartVerdict(StartVerdictKind.ASK, "confirm")
        return StartVerdict(StartVerdictKind.START)

    if path is StartPath.PLAN_STEP and confirmed_usd is not None:
        raise ValueError("a plan step never supplies a confirmation: only a person does")
    in_wallet = (
        wallet_verdict(ceiling_usd, wallet_remaining_usd)
        if wallet_remaining_usd is not None
        else None
    )
    blocked = StartVerdictKind.PARK if path is StartPath.PLAN_STEP else StartVerdictKind.REFUSED
    if in_wallet is WalletVerdict.CEILING_UNKNOWN or (in_wallet is None and ceiling_usd is None):
        return StartVerdict(blocked, "ceiling_unknown")
    if in_wallet is not WalletVerdict.FITS:
        return StartVerdict(blocked, "outside_wallet")

    if path is StartPath.CHAT_START:
        verdict = threshold_verdict(ceiling_usd, threshold_usd, confirmed_usd)
        if verdict is ThresholdVerdict.ASK:
            return StartVerdict(StartVerdictKind.ASK, "confirm")
        return StartVerdict(StartVerdictKind.START)

    shown = _usd(shown_ceiling_usd, "the ceiling the card showed")
    verdict = threshold_verdict(ceiling_usd, threshold_usd, shown)
    if verdict is ThresholdVerdict.ASK:
        # The card showed no ceiling, or a smaller one than the run's now: nobody confirmed it.
        return StartVerdict(
            StartVerdictKind.PARK, "not_confirmed" if shown is None else "ceiling_grew"
        )
    return StartVerdict(StartVerdictKind.START)
