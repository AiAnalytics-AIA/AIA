"""The money vocabulary and its one precedence (domain/money.py; lead-orchestration LO0, ADR 0028).

The names are the owner's (D-01) and are held to the case file the web's copy module is held to
(tests/fixtures/money/vocabulary.json). The rules are the threshold's (today's, ADR 0019 gate 2),
the wallet's (ADR 0028 decision 2, the owner's D-03) and one start's precedence across the three
paths a start can come from (ADR 0028 decision 3, the owner's D-02). And nothing in the code or
the authoritative documents calls the confirmation threshold a hard stop.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from aia_core.domain.money import (
    MONEY,
    PRECEDENCE,
    AmountRole,
    MoneyAmount,
    RaiseVerdict,
    StartPath,
    StartVerdict,
    StartVerdictKind,
    ThresholdVerdict,
    WalletVerdict,
    start_verdict,
    threshold_verdict,
    wallet_raise_verdict,
    wallet_remaining,
    wallet_verdict,
)

REPO = Path(__file__).resolve().parents[3]
VOCABULARY = json.loads(
    (Path(__file__).parent / "fixtures/money/vocabulary.json").read_text(encoding="utf-8")
)


# --------------------------------------------------------------------------- the vocabulary


def test_every_amount_is_the_case_file_s() -> None:
    by_amount = {a["amount"]: a for a in VOCABULARY["amounts"]}
    assert set(by_amount) == {m.value for m in MoneyAmount} == {m.value for m in MONEY}
    for amount, spec in MONEY.items():
        case = by_amount[amount.value]
        assert spec.amount is amount
        assert (spec.column, spec.czech, spec.role.value) == (
            case["column"],
            case["czech"],
            case["role"],
        )
        assert spec.set_by and spec.null_means


def test_the_four_names_are_the_owner_s() -> None:
    names = {a: MONEY[a].czech for a in MoneyAmount}
    assert names == {
        MoneyAmount.CLIENT_BUDGET: "Rozpočet klienta",
        MoneyAmount.STUDY_BUDGET: "Rozpočet studie",
        MoneyAmount.WALLET: "Peněženka",
        MoneyAmount.CONFIRM_THRESHOLD: "Práh potvrzení",
        MoneyAmount.WALLET_CEILING: None,  # the owner named no label: none is invented
    }
    assert all(MONEY[a].czech not in VOCABULARY["retired_names"] for a in MoneyAmount)


def test_the_precedence_is_budget_then_wallet_then_threshold() -> None:
    assert [a.value for a in PRECEDENCE] == VOCABULARY["precedence"]
    assert MONEY[MoneyAmount.STUDY_BUDGET].role is AmountRole.CAP
    assert MONEY[MoneyAmount.CONFIRM_THRESHOLD].role is AmountRole.THRESHOLD  # never a cap


# --------------------------------------------------------------------------- the threshold


@pytest.mark.parametrize(
    ("ceiling", "threshold", "confirmed", "verdict"),
    [
        (None, None, None, ThresholdVerdict.NOT_ASKED),  # unset: nothing asks, whatever it costs
        (999.0, None, None, ThresholdVerdict.NOT_ASKED),
        (4.99, 5.0, None, ThresholdVerdict.NOT_ASKED),
        (5.0, 5.0, None, ThresholdVerdict.ASK),  # reaching it asks
        (5.0, 5.0, 4.99, ThresholdVerdict.ASK),  # a confirmation below the ceiling covers nothing
        (5.0, 5.0, 5.0, ThresholdVerdict.CONFIRMED),
        (5.0, 5.0, 9.0, ThresholdVerdict.CONFIRMED),
        (None, 5.0, 9.0, ThresholdVerdict.CEILING_UNKNOWN),  # never let by as if free
        (0.0, 0.0, None, ThresholdVerdict.ASK),  # a zero threshold asks for everything
    ],
)
def test_the_threshold_asks_when_the_ceiling_reaches_it(
    ceiling: float | None,
    threshold: float | None,
    confirmed: float | None,
    verdict: ThresholdVerdict,
) -> None:
    assert threshold_verdict(ceiling, threshold, confirmed) is verdict


@pytest.mark.parametrize("bad", [-1.0, float("nan"), True])
def test_an_amount_that_is_not_money_is_refused(bad: float) -> None:
    with pytest.raises(ValueError):
        threshold_verdict(bad, 5.0)
    with pytest.raises(ValueError):
        threshold_verdict(1.0, bad)


# --------------------------------------------------------------------------- the wallet


def test_the_wallet_remaining_is_its_cap_less_the_ceilings_charged() -> None:
    assert wallet_remaining(10.0, []) == 10.0
    assert wallet_remaining(10.0, [4.8, 0.9]) == pytest.approx(4.3)
    assert wallet_remaining(1.0, [0.6, 0.6]) == 0.0  # never negative
    with pytest.raises(ValueError):
        wallet_remaining(10.0, [None])  # type: ignore[list-item]


def test_a_start_fits_the_wallet_only_with_a_known_ceiling_inside_it() -> None:
    assert wallet_verdict(4.3, 4.3) is WalletVerdict.FITS
    assert wallet_verdict(4.31, 4.3) is WalletVerdict.OUTSIDE
    assert wallet_verdict(None, 100.0) is WalletVerdict.CEILING_UNKNOWN


@pytest.mark.parametrize(
    ("to_cap", "budget", "ceiling", "verdict"),
    [
        (15.0, 50.0, 20.0, RaiseVerdict.ALLOWED),
        (25.0, 50.0, 20.0, RaiseVerdict.ABOVE_CLIENT_CEILING),  # D-03: refused, no queue
        (20.0, 50.0, 20.0, RaiseVerdict.ALLOWED),
        (60.0, 50.0, None, RaiseVerdict.ABOVE_STUDY_BUDGET),  # null: up to the budget
        (60.0, 50.0, 100.0, RaiseVerdict.ABOVE_STUDY_BUDGET),  # a wallet never raises the budget
        (50.0, 50.0, None, RaiseVerdict.ALLOWED),
    ],
)
def test_a_wallet_raise_stays_inside_the_client_ceiling_and_the_budget(
    to_cap: float, budget: float, ceiling: float | None, verdict: RaiseVerdict
) -> None:
    assert (
        wallet_raise_verdict(to_cap, study_budget_usd=budget, client_ceiling_usd=ceiling) is verdict
    )


# --------------------------------------------------------------------------- one start

START = StartVerdict(StartVerdictKind.START)


def test_a_person_s_start_meets_the_threshold_alone() -> None:
    def person(ceiling: float | None, confirmed: float | None = None) -> StartVerdict:
        return start_verdict(
            StartPath.PERSON,
            ceiling_usd=ceiling,
            threshold_usd=5.0,
            confirmed_usd=confirmed,
            wallet_remaining_usd=0.0,  # the person's own act is the card: the wallet is not read
        )

    assert person(4.0) == START
    assert person(6.0) == StartVerdict(StartVerdictKind.ASK, "confirm")
    assert person(6.0, 6.0) == START
    assert person(None) == StartVerdict(StartVerdictKind.REFUSED, "ceiling_unknown")
    assert (
        start_verdict(StartPath.PERSON, ceiling_usd=None, threshold_usd=None) == START
    )  # no threshold: as today, the budget alone stops spending


def test_a_chat_start_runs_inside_the_wallet_and_asks_at_the_threshold() -> None:
    def chat(ceiling: float | None, remaining: float | None) -> StartVerdict:
        return start_verdict(
            StartPath.CHAT_START,
            ceiling_usd=ceiling,
            threshold_usd=5.0,
            wallet_remaining_usd=remaining,
        )

    assert chat(4.0, 10.0) == START
    assert chat(6.0, 10.0) == StartVerdict(StartVerdictKind.ASK, "confirm")
    assert chat(4.0, 3.0) == StartVerdict(StartVerdictKind.REFUSED, "outside_wallet")
    assert chat(4.0, None) == StartVerdict(StartVerdictKind.REFUSED, "outside_wallet")
    assert chat(None, 10.0) == StartVerdict(StartVerdictKind.REFUSED, "ceiling_unknown")


def test_a_plan_step_starts_on_the_ceiling_its_card_showed_and_parks_otherwise() -> None:
    def step(ceiling: float | None, shown: float | None, remaining: float = 10.0) -> StartVerdict:
        return start_verdict(
            StartPath.PLAN_STEP,
            ceiling_usd=ceiling,
            threshold_usd=5.0,
            wallet_remaining_usd=remaining,
            shown_ceiling_usd=shown,
        )

    assert step(4.8, 4.8) == START  # below the threshold
    assert step(5.7, 5.7) == START  # D-02: the card showed it, so it does not ask again
    assert step(5.9, 5.7) == StartVerdict(StartVerdictKind.PARK, "ceiling_grew")
    assert step(5.9, None) == StartVerdict(StartVerdictKind.PARK, "not_confirmed")
    assert step(4.0, 5.7) == START  # grew smaller: still covered
    assert step(4.0, 4.0, remaining=3.0) == StartVerdict(StartVerdictKind.PARK, "outside_wallet")
    assert step(None, 4.0) == StartVerdict(StartVerdictKind.PARK, "ceiling_unknown")
    with pytest.raises(ValueError, match="only a person"):
        start_verdict(
            StartPath.PLAN_STEP,
            ceiling_usd=1.0,
            threshold_usd=5.0,
            confirmed_usd=1.0,
            wallet_remaining_usd=10.0,
        )


# --------------------------------------------------------------------------- the words

#: Where the threshold is described: the code and the documents that govern it. The planning
#: record is left out on purpose: its plans and evidence quote the wrong statement to correct it.
_SCANNED = (
    "ARCHITECTURE.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/architecture",
    "packages/aia_core/src",
    "apps/api/src",
    "apps/worker/src",
    "apps/executors/src",
    "apps/web/src",
)
_HARD_STOP = re.compile(r"hard[ -]stop|tvrdý strop|tvrdá zarážka", re.IGNORECASE)
_THRESHOLD = re.compile(
    r"spend_confirm|spend-confirm|spendConfirm|spend limit|confirmation threshold|"
    r"Práh potvrzení|limit studie",
    re.IGNORECASE,
)
_NEGATED = re.compile(r"\b(never|not|no)\b[^.]*(hard[ -]stop|tvrdý strop)", re.IGNORECASE)


def _calls_the_threshold_a_hard_stop(sentence: str) -> bool:
    return bool(
        _HARD_STOP.search(sentence)
        and _THRESHOLD.search(sentence)
        and not _NEGATED.search(sentence)
    )


def test_the_check_sees_the_statement_g11_found_and_not_its_correction() -> None:
    assert _calls_the_threshold_a_hard_stop(
        "The spend limit (`PUT /studies/{id}/spend-confirm`) stays the hard stop for everything."
    )
    assert _calls_the_threshold_a_hard_stop("Práh potvrzení je tvrdý strop.")
    assert not _calls_the_threshold_a_hard_stop(
        "A wallet never raises the budget, and the spend limit is never called a hard stop."
    )
    assert not _calls_the_threshold_a_hard_stop("A residency denial is a hard stop.")


def _sentences(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    paragraphs = re.split(r"\n\s*\n", text)
    return [s for p in paragraphs for s in re.split(r"(?<=[.!?])\s+", " ".join(p.split()))]


def test_nothing_calls_the_confirmation_threshold_a_hard_stop() -> None:
    """LO0: the spend limit is a per-start confirmation (``spend_confirm_usd``, null never asks);
    the cap that stops spending is ``budget_usd``. A sentence calling the threshold a hard stop
    is the statement the master plan's gap G11 found wrong."""
    files = [
        f
        for root in _SCANNED
        for f in ([REPO / root] if (REPO / root).is_file() else sorted((REPO / root).rglob("*")))
        if f.is_file()
        and f.suffix in {".md", ".py", ".ts", ".tsx"}
        and "node_modules" not in f.parts
    ]
    assert len(files) > 100  # the roots exist and were read
    wrong = [
        f"{f.relative_to(REPO)}: {s[:160]}"
        for f in files
        for s in _sentences(f)
        if _calls_the_threshold_a_hard_stop(s)
    ]
    assert wrong == []
