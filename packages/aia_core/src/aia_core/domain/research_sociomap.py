"""A research run's Sociomap: integrated, computed, and not exposed (ADR 0016 decision 6).

PR C chunk 6. For each tracked object set of the specification:

1. **the relation matrix** -- ported from the unit, ``sociomap.py``
   ``derive_relation_matrix``: object x object weighted Pearson correlation of the
   respondents' ratings, mapped onto 1-10 (``corr = -1 -> 1``, ``0 -> 5.5``,
   ``+1 -> 10``), fewer than five common ratings -> 5.5, diagonal 0; and each
   object's weighted mean rating. Weighted by ``_analysis_weight`` normalised to
   sum N, as the unit's ``project_engine._battery_dataset`` builds ``vaha``;
2. **the map** -- AIA's deterministic engine, ``compute_sociomap``, under the
   preset ``AIA_SOCIOMAP_V1`` adopted by name, with only the rating scale taken
   from the battery (a property of the data, recorded on the artifact).

**Integration is not exposure.** The preset carries four AIA methodology
declarations that PROGRESS D6 has not approved, so every Sociomap this module
builds is ``INTERNAL_ONLY``: the Study's researchers may inspect it; no
client-facing surface, export or report may render it. :func:`require_client_facing`
is the one check such a surface calls, and it refuses while D6 is open.

Pure: no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Final

from .fieldwork import FieldworkDataset
from .research_design import ResearchSpecification, SpecBattery
from .sociomap import AIA_SOCIOMAP_V1, compute_sociomap
from .sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from .sociomap.workspace import compute_workspace

__all__ = [
    "D6_OPEN",
    "RELATION_SOURCE",
    "SOCIOMAP_VERSION",
    "MethodologyStatus",
    "SociomapNotApproved",
    "battery_sociomap",
    "derive_relation_matrix",
    "require_client_facing",
    "research_sociomaps",
]

SOCIOMAP_VERSION: Final = "aia-research-sociomap-1"
RELATION_SOURCE: Final = "DERIVED_FROM_COMMON_RESPONDENT_RATINGS"

#: PROGRESS D6: the four AIA Sociomap declarations await the methodology owner.
#: Flipping this is a methodology decision recorded in PROGRESS, never a fix.
D6_OPEN: Final = True


class MethodologyStatus(StrEnum):
    #: The Study's researchers may look at it; nobody else, nowhere else.
    INTERNAL_ONLY = "INTERNAL_ONLY"
    #: D6 approved: a client-facing surface may render it.
    CLIENT_FACING = "CLIENT_FACING"


class SociomapNotApproved(PermissionError):
    """A Sociomap reached a client-facing surface while its methodology is not approved."""


def require_client_facing(sociomap: dict[str, Any]) -> None:
    """The check every client-facing surface, export and report makes. Fails closed."""
    if sociomap.get("methodology_status") != MethodologyStatus.CLIENT_FACING.value:
        raise SociomapNotApproved(
            "this Sociomap is INTERNAL_ONLY: its methodology (PROGRESS D6) is not approved "
            "for client use"
        )


def _methodology_status() -> MethodologyStatus:
    return MethodologyStatus.INTERNAL_ONLY if D6_OPEN else MethodologyStatus.CLIENT_FACING


def derive_relation_matrix(
    ratings: Sequence[Sequence[float | None]], weights: Sequence[float]
) -> tuple[list[list[float]], list[float | None]]:
    """``sociomap.py`` ``derive_relation_matrix``: relations and scores from ratings.

    ``ratings[r][j]`` is respondent ``r``'s rating of object ``j`` (``None`` unrated).
    Returns the symmetric 1-10 relation matrix with a zero diagonal, and each
    object's weighted mean rating (``None`` where nobody rated it).
    """
    m = len(ratings[0]) if ratings else 0

    def column(j: int) -> list[float]:
        out: list[float] = []
        for row in ratings:
            value = row[j]
            out.append(math.nan if value is None else float(value))
        return out

    cols = [column(j) for j in range(m)]
    w = [x if math.isfinite(x) else 1.0 for x in weights]

    scores: list[float | None] = []
    for j in range(m):
        pairs = [(x, ww) for x, ww in zip(cols[j], w, strict=True) if math.isfinite(x) and ww > 0]
        scores.append(
            sum(x * ww for x, ww in pairs) / sum(ww for _, ww in pairs) if pairs else None
        )

    relation = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            ok = [
                (a, b, ww)
                for a, b, ww in zip(cols[i], cols[j], w, strict=True)
                if math.isfinite(a) and math.isfinite(b) and math.isfinite(ww) and ww > 0
            ]
            if len(ok) < 5:
                rel = 5.5
            else:
                sw = sum(ww for _, _, ww in ok) or 1.0
                ma = sum(ww * a for a, _, ww in ok) / sw
                mb = sum(ww * b for _, b, ww in ok) / sw
                va = sum(ww * (a - ma) ** 2 for a, _, ww in ok) / sw
                vb = sum(ww * (b - mb) ** 2 for _, b, ww in ok) / sw
                cov = sum(ww * (a - ma) * (b - mb) for a, b, ww in ok) / sw
                corr = cov / max((va * vb) ** 0.5, 1e-12)
                corr = max(-1.0, min(1.0, corr))
                rel = 1.0 + 9.0 * ((corr + 1.0) / 2.0)
            relation[i][j] = relation[j][i] = float(min(10.0, max(1.0, rel)))
    return relation, scores


def battery_sociomap(
    battery: SpecBattery, dataset: FieldworkDataset, *, workspace_enabled: bool = False
) -> dict[str, Any]:
    """One tracked set's relation matrix and its Sociomap, as an internal artifact body."""
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    raw = [r.weight for r in dataset.respondents]
    total = sum(raw) or 1.0
    weights = [w * (len(raw) / total) for w in raw]  # project_engine.py:34-35, "vaha"
    ratings: list[list[float | None]] = []
    for r in dataset.respondents:
        row: list[float | None] = []
        for q in qids:
            value = r.answers.get(q)
            row.append(
                float(value) if isinstance(value, int) and not isinstance(value, bool) else None
            )
        ratings.append(row)
    relation, scores = derive_relation_matrix(ratings, weights)

    low, high = battery.scale
    spec = AIA_SOCIOMAP_V1.model_copy(
        update={
            "ratings": AIA_SOCIOMAP_V1.ratings.model_copy(
                update={"rating_scale_min": float(low), "rating_scale_max": float(high)}
            )
        }
    )
    inputs = SociomapInputs(
        ratings=RatingsMatrix(
            respondent_ids=tuple(r.respondent_id for r in dataset.respondents),
            object_ids=tuple(object_ids),
            values=tuple(tuple(row) for row in ratings),
        ),
        object_relation=RelationMatrix(
            entity_ids=tuple(object_ids), values=tuple(tuple(row) for row in relation)
        ),
    )
    artifact = compute_sociomap(inputs, spec)
    return {
        "battery_id": battery.id,
        "title": battery.title,
        "family": battery.family,
        "objects": [{"id": o.id, "label": o.label} for o in battery.objects],
        "methodology_status": _methodology_status().value,
        "methodology_decision": "PROGRESS D6: the four AIA Sociomap declarations, open",
        "preset": AIA_SOCIOMAP_V1.methodology_version,
        "rating_scale": [low, high],
        "relation": {
            "source": RELATION_SOURCE,
            "ported_from": "legacy/npc-panel-18.6.6/app/sociomap.py derive_relation_matrix",
            "matrix": relation,
            "scores": scores,
        },
        "sociomap": artifact.model_dump(mode="json"),
        "workspace": compute_workspace(inputs.ratings, (low, high)).model_dump(mode="json")
        if workspace_enabled
        else None,
    }


def research_sociomaps(
    spec: ResearchSpecification, dataset: FieldworkDataset, *, workspace_enabled: bool = False
) -> dict[str, Any]:
    """Every tracked set's Sociomap. A specification without one has none, and says so."""
    return {
        "sociomap_version": SOCIOMAP_VERSION,
        "methodology_status": _methodology_status().value,
        "data_origin": dataset.origin.value if dataset.origin else None,
        "batteries": [
            battery_sociomap(b, dataset, workspace_enabled=workspace_enabled)
            for b in spec.batteries
        ],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; Sociomapa nevznikla.",
    }
