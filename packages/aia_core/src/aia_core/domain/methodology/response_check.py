"""What an edited response process does, before it is put in force (plan ``methodology-tab`` R1c).

The draft and the process in force answer the same fixed fictional questions for the same
fixed fictional roster, side by side, through the functions a run answers with:
``fictional_roster`` assigns each respondent's styles under each process and
``adjust_probabilities`` turns one fixed probability vector per question -- standing in for
the model, which is never called here -- into each respondent's answer distribution. What is
compared is the roster's mean distribution per question, not a draw: the check shows what a
process does to the answers' probabilities, with no seeded luck in between. Every question
lists the share each option gets under both processes and the largest move, in percentage
points; the roster's styles show how many respondents a profile describes in words.

The questions are AIA's own invention and say so; no client's data is read.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from ..ai_respondent import describe_style, fictional_roster
from ..respondent_behavior import ResponseProcessSpec, ResponseQuestion, adjust_probabilities
from .pins import response_spec_for

__all__ = [
    "RESPONSE_CHECK_QUESTIONS",
    "RESPONSE_CHECK_RESPONDENTS",
    "CheckQuestion",
    "QuestionComparison",
    "ResponseComparison",
    "compare_response",
    "compare_response_with_in_force",
]

#: The fixed fictional roster every check answers with.
RESPONSE_CHECK_RESPONDENTS: Final = 80
_SEED: Final = 20261012


@dataclass(frozen=True, slots=True)
class CheckQuestion:
    """One fictional question: what it declares, and the probabilities standing in for a model."""

    id: str
    label_cs: str
    question: ResponseQuestion
    probabilities: tuple[float, ...]


RESPONSE_CHECK_QUESTIONS: Final[tuple[CheckQuestion, ...]] = (
    CheckQuestion(
        "souhlas",
        "Škála 1-5 s „nevím“, souhlas deklarovaný u 4 a 5",
        ResponseQuestion(
            typ="skala",
            labels=("1", "2", "3", "4", "5", "nevím"),
            scale=(1, 5),
            allow_dont_know=True,
            process={"agreement_scores": [0, 0, 0, 1, 1, 0]},
        ),
        (0.10, 0.20, 0.30, 0.20, 0.10, 0.10),
    ),
    CheckQuestion(
        "zadoucnost",
        "Volba ze čtyř s „nevím“, společensky žádoucí je první",
        ResponseQuestion(
            typ="vyber",
            labels=("třídím odpad", "občas", "spíš ne", "netřídím", "nevím"),
            allow_dont_know=True,
            process={"social_desirability_scores": [1, 0.5, 0, 0, 0]},
        ),
        (0.30, 0.25, 0.20, 0.15, 0.10),
    ),
    CheckQuestion(
        "skala7",
        "Škála 1-7 bez „nevím“, nic deklarovaného",
        ResponseQuestion(typ="skala", labels=tuple(str(i) for i in range(1, 8)), scale=(1, 7)),
        (0.05, 0.10, 0.15, 0.40, 0.15, 0.10, 0.05),
    ),
    CheckQuestion(
        "prvni",
        "Volba ze tří, satisficing k první možnosti",
        ResponseQuestion(
            typ="vyber",
            labels=("A", "B", "C"),
            process={"satisficing_strategy": "first_option"},
        ),
        (0.20, 0.50, 0.30),
    ),
)


@dataclass(frozen=True, slots=True)
class QuestionComparison:
    """One question's mean answer distribution under the process in force and the draft."""

    question: str
    label_cs: str
    labels: tuple[str, ...]
    model: tuple[float, ...]
    in_force: tuple[float, ...]
    draft: tuple[float, ...]
    #: How far one respondent's distribution is from the model's, on average (half the L1
    #: distance, in percentage points). Styles are centred, so the mean distribution hides
    #: what each respondent's style does; this shows it.
    shift_in_force: float
    shift_draft: float

    @property
    def moved_pp(self) -> float:
        """The largest change in any option's share, in percentage points."""
        return round(max(abs(a - b) for a, b in zip(self.in_force, self.draft, strict=True)), 2)


@dataclass(frozen=True, slots=True)
class ResponseComparison:
    """The draft beside the process in force, on the fixed roster and questions."""

    draft: str
    respondents: int
    questions: tuple[QuestionComparison, ...]
    #: How many respondents' profiles put a style into words, under each process.
    described_in_force: int
    described_draft: int


def _answered(spec: ResponseProcessSpec, q: CheckQuestion) -> tuple[tuple[float, ...], float]:
    """The roster's mean shares in percent, and its mean shift from the model in points."""
    roster = fictional_roster(RESPONSE_CHECK_RESPONDENTS, seed=_SEED, response=spec)
    model = [p / sum(q.probabilities) for p in q.probabilities]
    totals = [0.0] * len(model)
    shift = 0.0
    for persona in roster:
        p, _ = adjust_probabilities(q.probabilities, q.question, persona.style, spec)
        totals = [t + x for t, x in zip(totals, p, strict=True)]
        shift += sum(abs(a - b) for a, b in zip(p, model, strict=True)) / 2
    n = len(roster)
    return tuple(round(100 * t / n, 2) for t in totals), round(100 * shift / n, 2)


def _compare(
    q: CheckQuestion, in_force: ResponseProcessSpec, draft: ResponseProcessSpec
) -> QuestionComparison:
    (shares_a, shift_a), (shares_b, shift_b) = _answered(in_force, q), _answered(draft, q)
    return QuestionComparison(
        question=q.id,
        label_cs=q.label_cs,
        labels=q.question.labels,
        model=tuple(round(100 * p, 2) for p in q.probabilities),
        in_force=shares_a,
        draft=shares_b,
        shift_in_force=shift_a,
        shift_draft=shift_b,
    )


def _described(spec: ResponseProcessSpec) -> int:
    roster = fictional_roster(RESPONSE_CHECK_RESPONDENTS, seed=_SEED, response=spec)
    return sum(1 for p in roster if describe_style(p.style, spec.describe_threshold))


def compare_response(
    in_force: ResponseProcessSpec, draft: ResponseProcessSpec
) -> ResponseComparison:
    """The draft beside ``in_force`` on every fixed question, as shares in percent."""
    return ResponseComparison(
        draft=draft.methodology_version,
        respondents=RESPONSE_CHECK_RESPONDENTS,
        questions=tuple(_compare(q, in_force, draft) for q in RESPONSE_CHECK_QUESTIONS),
        described_in_force=_described(in_force),
        described_draft=_described(draft),
    )


def compare_response_with_in_force(
    stored: Mapping[str, Any] | None, draft: Mapping[str, Any]
) -> ResponseComparison:
    """The draft version payload beside the stored payload in force (``None``: the code's)."""
    return compare_response(response_spec_for(stored), response_spec_for(draft))
