"""A research run's experimental Sociomapping: declared relations, an AIA H-Model, heights.

Beside the run's existing Sociomap (``research_sociomap.py``, the unit's relations under the
``aia-sociomap-1`` preset), never instead of it. For each tracked object set:

1. **Inputs.** Each respondent's answers to the set's objects. RTS collects every answer, so
   the relations are computed over respondents who answered every object of the set; the
   others are excluded and counted, per object (an AIA rule, AIA-D2; M5). Unweighted: no
   source weights a Sociomap (M7), so the respondents' weights are recorded as not applied.
2. **Declared relationship matrix.** RTS object correlations: answers on the set's scale
   (RTS-N1), Pearson between objects (RTS-O1), signed, with every undefined pair named
   (AIA-D1). Nothing is clipped, shifted or filled.
3. **Layout.** The experimental AIA H-Model ``aia_hmodel_candidate_v1`` (AIA-H9). Objects
   with no defined relation are listed unplaced with the reason.
4. **Heights.** Each object's average answer on the set's own scale (RTS-W3).
5. **Coherences** only where a 0-1 relation matrix exists: every correlation defined and
   non-negative (RTS-O2). Otherwise the reason (M12), and the negative pairs stay visible.

**Status never upgrades itself.** Every result is ``EXPERIMENTAL_AIA`` and ``client_facing``
is ``False``; there is no input that changes either. :func:`require_not_client_facing`
is what a client surface calls, and it always refuses.

Not here, each blocked by an open question: respondents on the map (STORM placement, M3), an
interpolated height surface (WIND, M4), significance (M15), adequacy (M14).

Pure: no I/O.
"""

from __future__ import annotations

from typing import Any, Final

from .fieldwork import NON_EVIDENCE_ORIGINS, FieldworkDataset
from .research_design import ResearchSpecification, SpecBattery
from .sociomap.coherence import CoherenceTree, coherences
from .sociomap.declared import declared_from_correlations
from .sociomap.fuzzy import (
    FuzzyMatrixError,
    MethodologyUndetermined,
    rts_fuzzy_from_correlations,
    rts_object_correlations,
    rts_scale_answers,
)
from .sociomap.heights import object_average_answers
from .sociomap.hmodel import EVALUATOR_VERSION
from .sociomap.hmodel_candidate import (
    CANDIDATE_METHOD,
    CANDIDATE_STATUS,
    CandidateParameters,
    HModelLayout,
    fit_hmodel_candidate,
)
from .sociomap.models import RatingsMatrix

__all__ = [
    "METHOD_STATUS",
    "SOCIOMAPPING_VERSION",
    "ExperimentalNotClientFacing",
    "battery_sociomapping",
    "require_not_client_facing",
    "research_sociomappings",
]

SOCIOMAPPING_VERSION: Final = "aia-research-sociomapping-1"
METHOD_STATUS: Final = CANDIDATE_STATUS  # "EXPERIMENTAL_AIA"
_COMPLETE_CASES_RULE: Final = "AIA-D2"
#: Below this many placed objects the result says that a high accuracy says little.
_FEW_OBJECTS: Final = 6


class ExperimentalNotClientFacing(PermissionError):
    """An experimental Sociomapping reached a client-facing surface."""


def require_not_client_facing(result: dict[str, Any]) -> None:
    """What a client-facing surface calls before rendering this. Always refuses."""
    raise ExperimentalNotClientFacing(
        f"{result.get('method', {}).get('name', CANDIDATE_METHOD)} is an experimental AIA "
        "method; it is not approved for client use"
    )


def _limitation(code: str, detail: str, question: str | None = None) -> dict[str, Any]:
    return {"code": code, "detail": detail, "question": question}


def _standing_limitations() -> list[dict[str, Any]]:
    return [
        _limitation(
            "EXPERIMENTAL_METHOD",
            "The layout is AIA's experimental H-Model candidate; SOMECS's fitting objective is "
            "not documented, and nothing here is a verified reconstruction of it.",
            "M2",
        ),
        _limitation(
            "NO_RESPONDENT_PLACEMENT",
            "Respondents are not placed on the map: SOMECS's STORM placement is not documented.",
            "M3",
        ),
        _limitation(
            "NO_HEIGHT_SURFACE",
            "Heights are shown at the objects only; no surface is interpolated between them "
            "(SOMECS's WIND interpolation is not documented).",
            "M4",
        ),
        _limitation(
            "UNWEIGHTED",
            "Relations and heights are unweighted: no source weights a Sociomap.",
            "M7",
        ),
        _limitation(
            "ADEQUACY_NOT_ASSESSED",
            "Whether the support is enough for these correlations or this map to mean something "
            "is not assessed; a computable statistic is not an adequate one.",
            "M14",
        ),
        _limitation(
            "NO_SIGNIFICANCE",
            "The fit is not tested against random matrices of the same size.",
            "M15",
        ),
    ]


def _coherence_body(tree: CoherenceTree) -> dict[str, Any]:
    return {
        "available": True,
        "written": tree.written(),
        "algorithm": tree.algorithm,
        "matrix_fingerprint": tree.matrix_fingerprint,
        "rules": list(tree.rules),
        "ties": [
            {
                "level": t.level,
                "candidates": [[list(a), list(b)] for a, b in t.candidates],
                "chosen": [list(t.chosen[0]), list(t.chosen[1])],
                "candidates_overlap": t.candidates_overlap,
            }
            for t in tree.ties
        ],
        "flattened_levels": list(tree.flattened_levels),
    }


def _layout_body(layout: HModelLayout) -> dict[str, Any]:
    accuracy = layout.accuracy
    return {
        "element_ids": list(layout.element_ids),
        "positions": [list(p) for p in layout.positions],
        "unplaced": [u.model_dump(mode="json") for u in layout.unplaced],
        "accuracy": {
            "overall": accuracy.accuracy,
            "overall_undefined": accuracy.accuracy_undefined,
            "per_point": list(accuracy.per_point),
            "per_point_undefined": list(accuracy.per_point_undefined),
            "mean_per_point": accuracy.mean_per_point,
            "ordered_pairs": accuracy.ordered_pairs,
            "undefined_pairs": accuracy.undefined_pairs,
            "evaluator": accuracy.evaluator,
        },
        "starts": [s.model_dump(mode="json") for s in layout.starts],
        "chosen_start": layout.chosen_start,
        "baseline_classical_mds": layout.baseline_classical_mds,
        "relations_fingerprint": layout.relations_fingerprint,
        "frame": layout.frame,
        "rules": list(layout.rules),
    }


def _not_mapped(head: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    return {**head, "status": "NOT_MAPPED", "reason": reason, "layout": None, **extra}


def battery_sociomapping(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    parameters: CandidateParameters | None = None,
) -> dict[str, Any]:
    """One tracked set's experimental Sociomapping, as an internal artifact body."""
    params = parameters or CandidateParameters()
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    low, high = battery.scale
    complete_ids: list[str] = []
    complete_rows: list[tuple[int, ...]] = []
    missing_by_object = dict.fromkeys(object_ids, 0)
    for respondent in dataset.respondents:
        row: list[int | None] = []
        for oid, q in zip(object_ids, qids, strict=True):
            value = respondent.answers.get(q)
            usable = isinstance(value, int) and not isinstance(value, bool)
            row.append(value if usable else None)  # type: ignore[arg-type]
            if not usable:
                missing_by_object[oid] += 1
        if all(v is not None for v in row):
            complete_ids.append(respondent.respondent_id)
            complete_rows.append(tuple(v for v in row if v is not None))
    total = len(dataset.respondents)
    limitations = _standing_limitations()
    head: dict[str, Any] = {
        "battery_id": battery.id,
        "title": battery.title,
        "family": battery.family,
        "objects": [{"id": o.id, "label": o.label} for o in battery.objects],
        "rating_scale": [low, high],
        "scale_labels": list(battery.scale_labels),
        "support": {
            "respondents_total": total,
            "respondents_complete": len(complete_ids),
            "respondents_excluded": total - len(complete_ids),
            "exclusion_rule": _COMPLETE_CASES_RULE,
            "exclusion_reason": "did not answer every object of the set (RTS collects every "
            "answer; AIA keeps only complete respondents and counts the rest)",
            "missing_by_object": missing_by_object,
            "weighting": "UNWEIGHTED",
            "weights_not_applied": "no source weights a Sociomap (M7)",
        },
        "limitations": limitations,
    }
    if total - len(complete_ids):
        limitations.append(
            _limitation(
                "COMPLETE_RESPONDENTS_ONLY",
                f"{total - len(complete_ids)} of {total} respondents did not answer every "
                "object and are not in the relations or heights.",
                "M5",
            )
        )
    if len(object_ids) < 3:
        return _not_mapped(head, "a map needs at least three objects in the set")
    if len(complete_ids) < 2:
        return _not_mapped(
            head,
            f"insufficient support: {len(complete_ids)} respondent(s) answered every object; "
            "a correlation needs at least two",
        )
    try:
        answers = RatingsMatrix(
            respondent_ids=tuple(complete_ids),
            object_ids=tuple(object_ids),
            values=tuple(complete_rows),
        )
        scaled = rts_scale_answers(answers, (low, high))
    except (FuzzyMatrixError, ValueError) as exc:
        return _not_mapped(head, f"the answers do not fit the set's scale: {exc}")
    correlations = rts_object_correlations(scaled)
    declared = declared_from_correlations(correlations)
    heights = object_average_answers(scaled)
    negative = declared.negative_pairs()
    relations_body = {
        "scale": declared.scale.value,
        "matrix": [list(row) for row in declared.values],
        "undefined": [list(u) for u in declared.undefined],
        "negative_pairs": [list(p) for p in negative],
        "support": correlations.support,
        "rules": list(declared.rules),
        "fingerprint": declared.fingerprint(),
        "answers_fingerprint": correlations.answers_fingerprint,
    }
    heights_body = {
        "kind": heights.kind.value,
        "values": list(heights.values),
        "on_scale": list(heights.on_scale(low, high)),
        "rules": list(heights.rules),
        "input_fingerprint": heights.input_fingerprint,
    }
    try:
        fuzzy = rts_fuzzy_from_correlations(correlations)
        fuzzy_body: dict[str, Any] = {
            "available": True,
            "fingerprint": fuzzy.fingerprint(),
            "rules": list(fuzzy.rules),
        }
        coherence_body = _coherence_body(coherences(fuzzy))
    except (FuzzyMatrixError, MethodologyUndetermined) as exc:
        fuzzy_body = {"available": False, "reason": str(exc)}
        coherence_body = {"available": False, "reason": str(exc)}
    if negative:
        limitations.append(
            _limitation(
                "NEGATIVE_CORRELATIONS_KEPT",
                f"{len(negative)} object pair(s) correlate negatively. They are kept signed and "
                "laid out by their order; no 0-1 relation matrix or coherence levels exist "
                "for this set while RTS's handling of a negative correlation is open.",
                "M12",
            )
        )
    head = {
        **head,
        "relations": relations_body,
        "heights": heights_body,
        "fuzzy": fuzzy_body,
        "coherences": coherence_body,
    }
    try:
        layout = fit_hmodel_candidate(declared, params)
    except FuzzyMatrixError as exc:
        return _not_mapped(head, f"no layout: {exc}")
    placed = len(layout.element_ids)
    if placed < _FEW_OBJECTS:
        pairs = placed * (placed - 1) // 2
        limitations.append(
            _limitation(
                "FEW_OBJECTS",
                f"{placed} objects on the map make {pairs} pairs: an accuracy near 1 is easy to "
                "reach with so few and says little about the structure.",
            )
        )
    if layout.unplaced:
        limitations.append(
            _limitation(
                "UNPLACED_OBJECTS",
                "Not on the map: "
                + "; ".join(f"{u.element_id} ({u.reason})" for u in layout.unplaced),
            )
        )
    rules: list[str] = []
    sources: tuple[tuple[str, ...] | list[str], ...] = (
        layout.rules,
        declared.rules,
        heights.rules,
        [str(r) for r in coherence_body.get("rules", [])],
        [_COMPLETE_CASES_RULE, "AIA-D1"],
    )
    for source in sources:
        for rule in source:
            if rule not in rules:
                rules.append(rule)
    return {
        **head,
        "status": "MAPPED",
        "reason": None,
        "layout": _layout_body(layout),
        "rules": rules,
    }


def research_sociomappings(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    parameters: CandidateParameters | None = None,
) -> dict[str, Any]:
    """Every tracked set's experimental Sociomapping. A design without one has none, and says so."""
    params = parameters or CandidateParameters()
    origin = dataset.origin.value if dataset.origin else None
    return {
        "sociomapping_version": SOCIOMAPPING_VERSION,
        "method": {
            "name": CANDIDATE_METHOD,
            "status": METHOD_STATUS,
            "evaluator": EVALUATOR_VERSION,
            "parameters": params.model_dump(mode="json"),
            "description": "experimental AIA H-Model candidate; not a verified reconstruction "
            "of SOMECS",
        },
        "method_status": METHOD_STATUS,
        "client_facing": False,
        "data_origin": origin,
        "synthetic_data": dataset.origin in NON_EVIDENCE_ORIGINS,
        "batteries": [battery_sociomapping(b, dataset, params) for b in spec.batteries],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; mapa nevznikla.",
    }
