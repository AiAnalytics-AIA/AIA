"""What an edited aggregation does, before it is put in force (ADR 0023 decision 7, plan G3b).

The draft and the aggregation in force aggregate the same fixed fictional panels side by side,
through ``research_aggregate.aggregate_dataset`` itself -- the function a run's aggregate step
calls -- and every reported estimate is compared: each scale question's mean and top box, each
option's share, each with its 95 % interval. Each question's support status is compared too,
under the support rules in force: an edited Kish formula moves the effective n a status is
decided by. Every row that moved and every status that changed is named; what did not move
says so.

The panels are generated here from fixed seeds (``random.Random``), so the check is the same
every time it is asked. They are AIA's own invention, never a client's data, and are computed
in memory only: nothing here is stored or reaches a run.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from ..evidence.support import SupportSpec
from ..fieldwork import DataOrigin, FieldworkDataset, FieldworkRespondent, FieldworkSource
from ..research_aggregate import aggregate_dataset
from ..research_design import ResearchSpecification, compile_design
from .pins import aggregation_pin_for, read_aggregation_pin

__all__ = [
    "AGGREGATION_CHECK_PANELS",
    "AggregationComparison",
    "CheckPanel",
    "EstimateRow",
    "PanelComparison",
    "compare_aggregation",
    "compare_aggregation_with_in_force",
]

#: The questionnaire every panel answers: two scales, one single and one multiple choice.
_DESIGN: Final[dict[str, Any]] = {
    "title": "Kontrola agregace (fiktivní)",
    "n": 1,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "spokojenost",
                    "text": "Jak jste spokojeni?",
                    "typ": "skala",
                    "skala": [1, 5],
                },
                {
                    "id": "doporuceni",
                    "text": "Doporučili byste nás?",
                    "typ": "skala",
                    "skala": [1, 10],
                },
                {
                    "id": "volba",
                    "text": "Kterou značku kupujete nejčastěji?",
                    "typ": "vyber",
                    "kategorie": ["Alfa", "Beta", "Gama"],
                },
                {
                    "id": "kanaly",
                    "text": "Kde nakupujete?",
                    "typ": "multi",
                    "kategorie": ["obchod", "e-shop", "trh", "jinde"],
                },
            ],
        }
    ],
}
_GENERATOR: Final = "aia-methodology-aggregation-check-1"


@dataclass(frozen=True, slots=True)
class CheckPanel:
    """A fixed fictional panel: how many answer, from how many donors, how weighted."""

    id: str
    label_cs: str
    seed: int
    respondents: int
    donors: int
    weights: tuple[float, float] | None  # None: equal weights

    def dataset(self, spec: ResearchSpecification) -> FieldworkDataset:
        """The panel's answers, drawn by its seed: each scale leans towards its upper half,
        each choice towards its first option, so the estimates are far from trivial."""
        rng = random.Random(self.seed)
        people: list[FieldworkRespondent] = []
        for k in range(self.respondents):
            answers: dict[str, Any] = {}
            for q in spec.questions:
                if q.typ == "skala" and q.scale is not None:
                    low, high = q.scale
                    lean = rng.triangular(low, high, high - (high - low) / 4)
                    answers[q.id] = None if rng.random() < 0.05 else round(lean)
                elif q.typ == "vyber":
                    answers[q.id] = rng.choices(q.options, weights=range(len(q.options), 0, -1))[0]
                elif q.typ == "multi":
                    answers[q.id] = [
                        o for o in q.options if rng.random() < 0.6 / (1 + q.options.index(o))
                    ]
            people.append(
                FieldworkRespondent(
                    respondent_id=f"r{k}",
                    donor_id=f"d{rng.randrange(self.donors)}",
                    weight=1.0 if self.weights is None else rng.uniform(*self.weights),
                    answers=answers,
                )
            )
        return FieldworkDataset(
            dataset_version=_GENERATOR,
            source=FieldworkSource.SYNTHETIC_FIXTURE,
            origin=DataOrigin.SYNTHETIC_FIXTURE,
            spec_fingerprint=spec.fingerprint(),
            seed=self.seed,
            generator=_GENERATOR,
            respondents=tuple(people),
        )


#: The panels every draft is checked on, in the order they are shown.
AGGREGATION_CHECK_PANELS: Final = (
    CheckPanel("maly", "Malý panel (fiktivní)", 20261013, 60, 24, None),
    CheckPanel("vazeny", "Silně vážený panel (fiktivní)", 20261014, 240, 40, (0.2, 4.0)),
    CheckPanel("velky", "Velký panel (fiktivní)", 20261015, 500, 160, (0.6, 1.6)),
)


@dataclass(frozen=True, slots=True)
class EstimateRow:
    """One reported estimate under the aggregation in force and under the draft:
    ``(value, low, high)`` each, ``None`` where the aggregate reports none."""

    question: str
    measure: str  # "prumer", "top2box", or "share:<option>"
    in_force: tuple[float | None, float | None, float | None]
    draft: tuple[float | None, float | None, float | None]

    @property
    def moved(self) -> bool:
        return self.in_force != self.draft


@dataclass(frozen=True, slots=True)
class PanelComparison:
    panel: str
    label_cs: str
    respondents: int
    rows: tuple[EstimateRow, ...]
    statuses: tuple[tuple[str, str, str], ...]  # (question, in force, draft)
    effective_n: tuple[tuple[str, float, float], ...]  # (question, in force, draft)

    @property
    def moved(self) -> tuple[EstimateRow, ...]:
        return tuple(r for r in self.rows if r.moved)

    @property
    def status_changes(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(s for s in self.statuses if s[1] != s[2])


@dataclass(frozen=True, slots=True)
class AggregationComparison:
    in_force: str
    draft: str
    panels: tuple[PanelComparison, ...]


def _interval(raw: Any) -> tuple[float | None, float | None]:
    if not isinstance(raw, Mapping):
        return None, None
    return raw.get("low"), raw.get("high")


def _rows(question: str, cell: Mapping[str, Any]) -> dict[str, tuple[Any, Any, Any]]:
    """Every estimate one aggregated question reports, by measure."""
    if cell["typ"] == "skala":
        return {
            "prumer": (cell.get("prumer"), *_interval(cell.get("prumer_interval_95"))),
            "top2box": (cell.get("top2box_pct"), *_interval(cell.get("top2box_interval_95"))),
        }
    intervals = cell.get("intervaly_95") or {}
    return {
        f"share:{option}": (value, *_interval(intervals.get(option)))
        for option, value in (cell.get("celkem_pct") or {}).items()
    }


def compare_aggregation(
    in_force: Mapping[str, Any],
    draft: Mapping[str, Any],
    *,
    support: SupportSpec,
    panels: tuple[CheckPanel, ...] = AGGREGATION_CHECK_PANELS,
) -> AggregationComparison:
    """``draft`` beside ``in_force`` (each an aggregation pin, ``{"spec", "formulas"}``) on
    every panel, statuses decided by ``support``."""
    spec, problems = compile_design(_DESIGN)
    assert spec is not None, problems  # the check's own questionnaire compiles
    before_method, before_slots = read_aggregation_pin(in_force)
    after_method, after_slots = read_aggregation_pin(draft)
    out: list[PanelComparison] = []
    for panel in panels:
        dataset = panel.dataset(spec)
        before = aggregate_dataset(
            spec, dataset, support=support, method=before_method, slots=before_slots
        )["questions"]
        after = aggregate_dataset(
            spec, dataset, support=support, method=after_method, slots=after_slots
        )["questions"]
        rows: list[EstimateRow] = []
        for qid in before:
            a, b = _rows(qid, before[qid]), _rows(qid, after[qid])
            for measure in a:
                rows.append(EstimateRow(qid, measure, a[measure], b.get(measure, (None,) * 3)))
        out.append(
            PanelComparison(
                panel=panel.id,
                label_cs=panel.label_cs,
                respondents=panel.respondents,
                rows=tuple(rows),
                statuses=tuple(
                    (q, str(before[q]["support_status"]), str(after[q]["support_status"]))
                    for q in before
                ),
                effective_n=tuple(
                    (q, float(before[q]["effective_n"]), float(after[q]["effective_n"]))
                    for q in before
                ),
            )
        )
    return AggregationComparison(
        in_force=before_method.methodology_version,
        draft=after_method.methodology_version,
        panels=tuple(out),
    )


def compare_aggregation_with_in_force(
    stored: Mapping[str, Any] | None, draft: Mapping[str, Any], *, support: SupportSpec
) -> AggregationComparison:
    """A draft version payload beside what a run started now would pin: ``stored`` is the
    version in force's payload, ``None`` when the code's preset is in force."""
    return compare_aggregation(
        aggregation_pin_for(stored), aggregation_pin_for(draft), support=support
    )
