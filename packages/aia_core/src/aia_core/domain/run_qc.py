"""A run's quality checks, from its stored answers: the unit's ``qc.kontrola``, as warnings.

Plan ``evidence-integrity`` chunk 2a (MVP-24). The unit ran its QC after every run and refused
the client report on a KRITICKE finding (``prototype_server.py:385``); in AIA nothing waits on it
and nothing is refused: every finding is a warning, its level the unit's word kept as data.

Ported EXACT from ``legacy/npc-panel-18.6.6/app/qc.py:70-255`` for the checks a run's stored
dataset and specification answer, held to the unit's own run on captured fictional runs
(``tests/fixtures/run_qc``, ``tools/run_qc_capture.py``). The checks whose input AIA does not keep
are named as not applicable, each with its reason, never passed:

- the technical error rate (``chybovost``): an AI respondent's failed block fails or parks the
  step, it is never stored as a blank row;
- the custom segment's ESS: AIA has no segment mode;
- Cramér's V and the segment ranges by demographics, and the persona's strength over the run:
  the dataset carries no demographic column (chunk 2b, over a panel run's recorded sample);
- entropy, max probability and the behaviour layer's shift: fieldwork does not store each
  draw's record with a research dataset (chunk 2c).

The thresholds are the unit's ``PRAHY`` (``qc.py:25-37``), which it calls its own calibration and
not a standard of the field; they are a parameter and recorded with every result. Whether they,
the dry-mode rule, the ablation flag or the scope of straight-lining should differ for AIA is the
methodology owner's to say (``evidence-integrity`` chunk 2, its divergences).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import numpy as np

from .fieldwork import Answer, FieldworkDataset, validate_dataset
from .research_design import DONT_KNOW, ResearchSpecification
from .straight_lining import AnswerSpread, answer_spread

__all__ = [
    "NOT_APPLICABLE",
    "RUN_QC_VERSION",
    "UNIT_THRESHOLDS",
    "QcCheck",
    "QcFinding",
    "QcLevel",
    "QcQuestion",
    "QcThresholds",
    "RunQc",
    "dataset_qc",
    "run_qc",
]

RUN_QC_VERSION: Final = "aia-run-qc-1"
#: Where the unit files a finding about the run as a whole (``qc.py`` ``"beh"``).
RUN: Final = "beh"
#: The space of answer vectors above which the unit stops multiplying (``qc.py:224``).
_SPACE_CAP: Final = 10_000_000


class QcLevel(StrEnum):
    """The unit's levels, kept as its words; in AIA every one is a warning, none a gate."""

    OK = "OK"
    VAROVANI = "VAROVANI"
    KRITICKE = "KRITICKE"


class QcCheck(StrEnum):
    """Each check's stable id: what a flag, the Lead and the screen name it by."""

    MISSING_ANSWERS = "missing_answers"
    DONT_KNOW_RARE = "dont_know_rare"
    DONT_KNOW_FREQUENT = "dont_know_frequent"
    CONCENTRATED = "concentrated"
    FLAT_SCALE = "flat_scale"
    REPEATED_OPEN_ANSWERS = "repeated_open_answers"
    STRAIGHT_LINING = "straight_lining"
    IDENTICAL_VECTORS = "identical_vectors"
    PERSONA_EFFECT_UNVERIFIED = "persona_effect_unverified"
    # Not applicable in AIA (see NOT_APPLICABLE).
    ERROR_RATE = "error_rate"
    SEGMENT_ESS = "segment_ess"
    DEMOGRAPHIC_DIFFERENTIATION = "demographic_differentiation"
    SEGMENT_SCALE_RANGES = "segment_scale_ranges"
    PERSONA_STRENGTH = "persona_strength"
    PROBABILITY_DIAGNOSTICS = "probability_diagnostics"
    BEHAVIOUR_SHIFT = "behaviour_shift"


#: The unit's checks that read an input AIA does not keep, and why. Never a pass.
NOT_APPLICABLE: Final[Mapping[QcCheck, str]] = {
    QcCheck.ERROR_RATE: (
        "an AI respondent's failed block fails or parks the fieldwork step; no blank row is stored"
    ),
    QcCheck.SEGMENT_ESS: "AIA has no custom segment mode",
    QcCheck.DEMOGRAPHIC_DIFFERENTIATION: (
        "the dataset carries no demographic column (evidence-integrity 2b)"
    ),
    QcCheck.SEGMENT_SCALE_RANGES: (
        "the dataset carries no demographic column (evidence-integrity 2b)"
    ),
    QcCheck.PERSONA_STRENGTH: "the dataset carries no demographic column (evidence-integrity 2b)",
    QcCheck.PROBABILITY_DIAGNOSTICS: (
        "fieldwork does not store each draw's probabilities with the dataset "
        "(evidence-integrity 2c)"
    ),
    QcCheck.BEHAVIOUR_SHIFT: (
        "fieldwork does not store each draw's behaviour shift with the dataset "
        "(evidence-integrity 2c)"
    ),
}


@dataclass(frozen=True, slots=True)
class QcThresholds:
    """The thresholds the checks read; :data:`UNIT_THRESHOLDS` is the unit's ``PRAHY``."""

    missing_max: float
    dont_know_min: float
    dont_know_max: float
    concentration_max: float
    scale_sd_min: float
    open_unique_min: float
    straight_lining_max: float
    straight_lining_min_scales: int
    duplicates_max: float
    duplicates_space_per_respondent: int


#: ``qc.py:25-37`` ``PRAHY`` and the constants written into ``kontrola`` itself (the 20 % of
#: ``:113``, the 0.5 sd of ``:150``, the three scales of ``:200``, the five per respondent of
#: ``:228``). The unit's calibration, "ne standard oboru".
UNIT_THRESHOLDS: Final = QcThresholds(
    missing_max=0.20,
    dont_know_min=0.02,
    dont_know_max=0.35,
    concentration_max=0.90,
    scale_sd_min=0.5,
    open_unique_min=0.70,
    straight_lining_max=0.15,
    straight_lining_min_scales=3,
    duplicates_max=0.10,
    duplicates_space_per_respondent=5,
)


@dataclass(frozen=True, slots=True)
class QcQuestion:
    """A question as the checks read it: its id, the unit's type and its options."""

    id: str
    typ: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QcFinding:
    """One finding: its level and check, where (a question id or ``beh``) and the value it read
    (``None`` where the unit reads none). Its words are the screen's, by its check; the unit's own
    sentence for each check is pinned in the test that holds this port to the unit."""

    level: QcLevel
    check: QcCheck
    where: str
    value: float | None


@dataclass(frozen=True, slots=True)
class RunQc:
    """A run's QC: the unit's level and verdict, findings, metrics and what could not be read.

    ``metrics`` keeps the unit's keys (``per_otazku``, ``straightlining``, …) so it is compared
    with the unit key for key; a value the unit computes as NaN is ``None``, never a number.
    """

    version: str
    level: QcLevel
    verdict: str
    findings: tuple[QcFinding, ...]
    metrics: Mapping[str, object]
    not_applicable: Mapping[QcCheck, str]
    thresholds: QcThresholds


#: ``qc.py:251-255``.
_VERDICTS: Final[Mapping[QcLevel, str]] = {
    QcLevel.OK: "Bez automatickych nalezu; stale jde o syntetickou simulaci, ne lidsky teren.",
    QcLevel.VAROVANI: "Pouzitelne s vyhradou — projdi nalezy nez to posles klientovi.",
    QcLevel.KRITICKE: "NEPOSILAT KLIENTOVI. Panel nebo prompt nefunguje, opakuj beh po oprave.",
}


def _round(value: float | None, places: int) -> float | None:
    if value is None or np.isnan(value):
        return None
    return round(float(value), places)


def run_qc(
    questions: Sequence[QcQuestion],
    answers: Sequence[Mapping[str, Answer]],
    *,
    dry: bool,
    ablation: bool,
    thresholds: QcThresholds = UNIT_THRESHOLDS,
) -> RunQc:
    """The unit's ``kontrola`` over every respondent's answers (a missing key is not answered).

    ``dry``: the unit's dry run (no model call), which rates repeated open answers VAROVANI
    rather than KRITICKE and skips the ablation flag; ``ablation``: whether an ablation test
    verified the persona's effect (the unit's ``v["ablation"]``). Every respondent was asked every
    question: AIA does not route yet (``run-qc-and-checkpoint`` RQC11). A run with no respondent
    is refused: the unit divides by its size.
    """
    n = len(answers)
    if n == 0:
        raise ValueError("a run with no respondent has no quality to check")
    t = thresholds
    findings: list[QcFinding] = []

    def flag(level: QcLevel, check: QcCheck, where: str, value: float | None) -> None:
        findings.append(QcFinding(level, check, where, value))

    columns = {q.id: [row.get(q.id) for row in answers] for q in questions}
    per_question: dict[str, dict[str, object]] = {}
    for q in questions:
        values = columns[q.id]
        given = [v for v in values if v is not None]
        missing = round(1 - len(given) / n, 3)
        m: dict[str, object] = {"n_eligible": n, "n_platnych": len(given), "podil_chybi": missing}
        if missing > t.missing_max:
            flag(
                QcLevel.VAROVANI,
                QcCheck.MISSING_ANSWERS,
                q.id,
                missing,
            )
        if q.typ == "vyber":
            counts = Counter(str(v) for v in given)
            shares = {k: c / len(given) for k, c in counts.items()}
            dont_know = round(float(shares.get(DONT_KNOW, 0.0)), 3)
            concentration = _round(max(shares.values()) if shares else None, 3)
            m["nevim"] = dont_know
            m["koncentrace"] = concentration
            if dont_know < t.dont_know_min:
                flag(
                    QcLevel.VAROVANI,
                    QcCheck.DONT_KNOW_RARE,
                    q.id,
                    dont_know,
                )
            if dont_know > t.dont_know_max:
                flag(
                    QcLevel.VAROVANI,
                    QcCheck.DONT_KNOW_FREQUENT,
                    q.id,
                    dont_know,
                )
            if concentration is not None and concentration > t.concentration_max:
                flag(
                    QcLevel.VAROVANI,
                    QcCheck.CONCENTRATED,
                    q.id,
                    concentration,
                )
        elif q.typ == "skala":
            x = np.asarray([_scale_point(q.id, v) for v in given], float)
            mean = _round(float(x.mean()) if len(x) else None, 2)
            sd = _round(float(x.std(ddof=1)) if len(x) > 1 else None, 2)
            m["prumer"] = mean
            m["sd"] = sd
            if sd is not None and sd < t.scale_sd_min:
                flag(QcLevel.VAROVANI, QcCheck.FLAT_SCALE, q.id, sd)
        elif q.typ == "otevrena":
            texts = [str(v).strip().lower() for v in given]
            if texts:
                unique = round(len(set(texts)) / len(texts), 3)
                m["podil_unikatu"] = unique
                m["prum_slov"] = round(float(np.mean([len(s.split()) for s in texts])), 1)
                if unique < t.open_unique_min:
                    flag(
                        QcLevel.VAROVANI if dry else QcLevel.KRITICKE,
                        QcCheck.REPEATED_OPEN_ANSWERS,
                        q.id,
                        unique,
                    )
        per_question[q.id] = m

    metrics: dict[str, object] = {"per_otazku": per_question}

    scales = [q.id for q in questions if q.typ == "skala"]
    if len(scales) >= t.straight_lining_min_scales:
        liners = sum(
            answer_spread(row.get(qid) for qid in scales)
            in (AnswerSpread.ONE, AnswerSpread.NO_SPREAD)
            for row in answers
        )
        share = round(liners / n, 3)
        metrics["straightlining"] = share
        if share > t.straight_lining_max:
            flag(
                QcLevel.VAROVANI,
                QcCheck.STRAIGHT_LINING,
                RUN,
                share,
            )

    fixed = [q for q in questions if q.typ in ("vyber", "skala")]
    if len(fixed) >= 2:
        space = 1
        for q in fixed:
            if q.typ == "vyber":
                k = max(2, len(q.options))
            else:
                k = max(2, len({v for v in columns[q.id] if v is not None}))
            space *= k
            if space > _SPACE_CAP:
                break
        vectors = {tuple(_key(row.get(q.id)) for q in fixed) for row in answers}
        duplicates = round(1 - len(vectors) / n, 3)
        metrics["podil_duplicitnich_vektoru"] = duplicates
        metrics["response_space_lower_bound"] = space
        if space >= t.duplicates_space_per_respondent * n and duplicates > t.duplicates_max:
            flag(
                QcLevel.VAROVANI,
                QcCheck.IDENTICAL_VECTORS,
                RUN,
                duplicates,
            )

    metrics["persona_effect_verified"] = ablation
    if not ablation and not dry:
        flag(
            QcLevel.VAROVANI,
            QcCheck.PERSONA_EFFECT_UNVERIFIED,
            RUN,
            None,
        )

    level = (
        QcLevel.KRITICKE
        if any(f.level is QcLevel.KRITICKE for f in findings)
        else QcLevel.VAROVANI
        if findings
        else QcLevel.OK
    )
    return RunQc(
        version=RUN_QC_VERSION,
        level=level,
        verdict=_VERDICTS[level],
        findings=tuple(findings),
        metrics=metrics,
        not_applicable=dict(NOT_APPLICABLE),
        thresholds=t,
    )


def _scale_point(qid: str, value: Answer) -> float:
    """A scale answer as a number. The unit coerced anything else to NaN (``pd.to_numeric``,
    ``errors="coerce"``); a validated dataset holds none, so one here is refused by name, as the
    straight-liner rule refuses it, never read as missing or as 1 (a boolean)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{qid}: a scale answer must be a number; got {type(value).__name__}")
    return float(value)


def _key(value: Answer) -> object:
    """An answer as one cell of an answer vector; the unit joins ``str(x)``, which tells the
    same values apart as this does on a validated dataset (text, a scale point, or none)."""
    return tuple(value) if isinstance(value, list) else value


def dataset_qc(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    dry: bool,
    ablation: bool = False,
    thresholds: QcThresholds = UNIT_THRESHOLDS,
) -> RunQc:
    """:func:`run_qc` over a run's stored dataset and the specification it answers.

    The dataset is checked against the specification first (``validate_dataset``): QC over a
    dataset of another specification would read every question as unanswered. A question with a
    display condition is refused: the unit's base is the respondents asked (``_eligible_``), which
    AIA's dataset does not record until fieldwork routes (``run-qc-and-checkpoint`` RQC11).
    """
    validate_dataset(spec, dataset)
    routed = [q.id for q in spec.questions if q.condition is not None]
    if routed:
        raise ValueError(
            f"{', '.join(routed)}: a conditional question's base is the respondents asked, which "
            "the dataset does not record yet"
        )
    questions = tuple(QcQuestion(q.id, q.typ, tuple(q.options)) for q in spec.questions)
    return run_qc(
        questions,
        [r.answers for r in dataset.respondents],
        dry=dry,
        ablation=ablation,
        thresholds=thresholds,
    )
