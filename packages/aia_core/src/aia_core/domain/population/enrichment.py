"""The seven runtime dimensions the ANALYSIS population view carries: 18.6.6's ``attach_derived``.

A port of ``audience_dimensions.attach_derived``
(``legacy/npc-panel-18.6.6/app/audience_dimensions.py:137-182``), the derivation OI-7 recorded as
lost in the withheld archive; the vendored file is that archive file, byte-identical (SHA256
``6ae1d1f8…c754bf``). ``enrich_panel`` also runs ``attach_evidence_overlays``, which adds nothing
without Data Library overlay metadata, and the vendored unit carries none, so this is the whole of
it. Parity is EXACT against the unit's own ``enrich_panel`` on fictional rows
(``tools/enrichment_capture.py``; ``tests/fixtures/enrichment/``).

:class:`AudienceDimensionsEnricher` is the ``Enricher`` ``PopulationRuntime`` asks for before it
loads the ANALYSIS view (``application/population.py``, ``_enrich``). It produces text cells,
``None`` where the unit holds NA.

What the unit does, kept exactly:

* every input is read as ``pd.to_numeric(errors="coerce")`` of the column as the unit loads it
  (:func:`.audience.numeric_column`);
* a mean is over the inputs a row has (``DataFrame.mean(axis=1)``: missing ones skipped, none
  present is NA), summed in column order;
* a tier is ``pd.cut`` at ``(-inf, 3] (3, 5.5] (5.5, 7.5] (7.5, inf)``; NA stays NA;
* a "dominant" field is the first column holding the row's maximum (``idxmax``); a row with no
  value falls back to its label. On pandas 2, which the unit pins (``pandas>=2.1,<3``), ``idxmax``
  over an all-NA row returns NA with a deprecation warning; pandas 3 would raise. The fixture is
  captured on pandas 2 and this keeps that behaviour;
* the life stage is assigned in the unit's order, a later rule overriding an earlier one.

One deliberate difference: the unit fails with an ``AttributeError`` when a flag column
(``is_parent``, ``is_student``, ``is_employed``, ``has_partner``) is absent (a scalar default
has no ``fillna``, ``audience_dimensions.py:141-144``); this refuses with
:class:`EnrichmentInputMissing` and names the columns. ``vek`` and every score column may be
absent, as in the unit.

Pure: stdlib only.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from .audience import numeric_column
from .errors import PopulationError
from .runtime import Cell
from .table import ParsedPanel

__all__ = [
    "AUDIENCE_DIMENSIONS_ENRICHER_ID",
    "DERIVED_FIELDS",
    "AudienceDimensionsEnricher",
    "EnrichmentInputMissing",
    "derive_audience_dimensions",
]

AUDIENCE_DIMENSIONS_ENRICHER_ID: Final = "aia-audience-dimensions-1 (18.6.6 attach_derived 17.9.3)"

DERIVED_FIELDS: Final = (
    "life_stage_derived",
    "digital_engagement_tier_derived",
    "dominant_media_derived",
    "dominant_leisure_derived",
    "shopping_orientation_derived",
    "ad_receptivity_tier_derived",
    "financial_capability_tier_derived",
)

_FLAGS: Final = ("is_parent", "is_student", "is_employed", "has_partner")
_TIERS: Final = ("Nízká", "Střední", "Vysoká", "Velmi vysoká")
_DIGITAL: Final = (
    "smartphone_use_intensity_1_10",
    "computer_use_intensity_1_10",
    "digital_communication_intensity_1_10",
    "online_information_intensity_1_10",
    "online_entertainment_intensity_1_10",
    "online_transactions_intensity_1_10",
    "digital_personal_management_intensity_1_10",
)
_MEDIA: Final = (
    ("TV", "tv_intensity_1_10"),
    ("Rádio", "radio_intensity_1_10"),
    ("Tisk", "print_intensity_1_10"),
    ("Sociální sítě", "social_media_intensity_1_10"),
    ("Online zprávy", "online_information_intensity_1_10"),
    ("Online video", "online_entertainment_intensity_1_10"),
)
_LEISURE: Final = (
    ("Gaming", "gaming_intensity_1_10"),
    ("Cestování", "travel_intensity_1_10"),
    ("Sport", "sport_activity_1_10"),
    ("Outdoor", "outdoor_activity_1_10"),
    ("Socializace", "socializing_offline_1_10"),
    ("Restaurace", "dining_out_1_10"),
    ("Kultura", "culture_activity_1_10"),
    ("Nightlife", "nightlife_1_10"),
    ("DIY / domov", "diy_home_activity_1_10"),
    ("Vaření", "cooking_activity_1_10"),
)
_POSITIVE: Final = (
    "social_proof_susceptibility_1_10",
    "influencer_receptivity_1_10",
    "authority_receptivity_1_10",
    "scarcity_response_1_10",
    "tv_ad_attention_1_10",
    "social_ad_attention_1_10",
    "search_ad_attention_1_10",
)
_RESISTANCE: Final = ("advertising_skepticism_1_10", "reactance_1_10", "ad_avoidance_1_10")

Numbers = tuple[float | None, ...]


class EnrichmentInputMissing(PopulationError):
    """A column the derivation cannot do without is absent; the view does not load."""

    reason = "enrichment_input_missing"


def _tier(value: float | None) -> str | None:
    """``pd.cut(x, [-inf, 3.0, 5.5, 7.5, inf], labels=...)``: right-closed bins."""
    if value is None or value == -math.inf:
        return None
    if value <= 3.0:
        return _TIERS[0]
    if value <= 5.5:
        return _TIERS[1]
    if value <= 7.5:
        return _TIERS[2]
    return _TIERS[3]


def _mean(columns: Sequence[Numbers], rows: int) -> Numbers:
    """``pd.concat(cols, axis=1).mean(axis=1)``: present values summed in column order."""
    if not columns:
        return (None,) * rows
    out: list[float | None] = []
    for i in range(rows):
        total = 0.0
        count = 0
        for column in columns:
            value = column[i]
            if value is not None:
                total += value
                count += 1
        out.append(total / count if count else None)
    return tuple(out)


def _dominant(labelled: Sequence[tuple[str, Numbers]], rows: int, fallback: str) -> tuple[str, ...]:
    """``DataFrame.idxmax(axis=1).fillna(fallback)``: the first label holding the row's maximum."""
    out: list[str] = []
    for i in range(rows):
        best: str | None = None
        best_value = -math.inf
        for label, column in labelled:
            value = column[i]
            if value is not None and (best is None or value > best_value):
                best, best_value = label, value
        out.append(best if best is not None else fallback)
    return tuple(out)


def derive_audience_dimensions(
    has: Callable[[str], bool], column: Callable[[str], Sequence[Cell]], rows: int
) -> dict[str, tuple[Cell, ...]]:
    """The seven fields ``attach_derived`` adds, as text cells, for a panel of ``rows`` rows."""
    missing = [flag for flag in _FLAGS if not has(flag)]
    if missing:
        raise EnrichmentInputMissing(
            f"the audience dimensions need the columns {missing}; the panel lacks them"
        )

    def numbers(name: str) -> Numbers:
        return numeric_column(name, column(name)) if has(name) else (None,) * rows

    def present(names: Sequence[str]) -> list[Numbers]:
        return [numbers(n) for n in names if has(n)]

    def flag(name: str) -> tuple[bool, ...]:
        return tuple((v if v is not None else 0.0) > 0 for v in numbers(name))

    age = numbers("vek")
    parent, student, partner = flag("is_parent"), flag("is_student"), flag("has_partner")
    life: list[str] = []
    for i in range(rows):
        a = age[i]
        stage = "Dospělý / ostatní"
        if a is not None and a >= 65:
            stage = "Senior 65+"
        if a is not None and a < 30 and student[i]:
            stage = "Student / mladý dospělý"
        if a is not None and a < 35 and not student[i] and not parent[i]:
            stage = "Mladý bez dětí"
        if parent[i]:
            stage = "Rodič"
        if a is not None and 35 <= a <= 64 and not parent[i] and partner[i]:
            stage = "Střední věk · partner bez dětí v domácnosti"
        life.append(stage)

    digital = _mean(present(_DIGITAL), rows)
    media = [(label, numbers(name)) for label, name in _MEDIA if has(name)]
    leisure = [(label, numbers(name)) for label, name in _LEISURE if has(name)]

    shopping = [
        ("Value / slevy", _mean(present(("price_sensitivity_1_10", "deal_proneness_1_10")), rows)),
        (
            "Premium / status",
            _mean(present(("premium_willingness_1_10", "status_consumption_1_10")), rows),
        ),
        (
            "Research / recenze",
            _mean(present(("research_orientation_1_10", "review_reliance_1_10")), rows),
        ),
        ("Convenience", _mean(present(("convenience_orientation_1_10",)), rows)),
    ]

    positive = _mean(present(_POSITIVE), rows)
    resistance = _mean(present(_RESISTANCE), rows)
    adscore: list[float | None] = []
    for p, r in zip(positive, resistance, strict=True):
        adscore.append(
            None if p is None or r is None else min(max(p - (r - 5.5) * 0.55, 1.0), 10.0)
        )

    finance = numbers("financial_capability_1_10")
    return {
        "life_stage_derived": tuple(life),
        "digital_engagement_tier_derived": tuple(_tier(v) for v in digital),
        "dominant_media_derived": _dominant(media, rows, "Bez dominantního kanálu"),
        "dominant_leisure_derived": _dominant(leisure, rows, "Bez dominantní aktivity"),
        "shopping_orientation_derived": _dominant(shopping, rows, "Vyvážená"),
        "ad_receptivity_tier_derived": tuple(_tier(v) for v in adscore),
        "financial_capability_tier_derived": tuple(_tier(v) for v in finance),
    }


class AudienceDimensionsEnricher:
    """The ``Enricher`` for a population whose contract declares :data:`DERIVED_FIELDS`."""

    enricher_id: str = AUDIENCE_DIMENSIONS_ENRICHER_ID

    def derive(self, panel: ParsedPanel) -> Mapping[str, Sequence[Cell]]:
        return derive_audience_dimensions(panel.has, panel.column, panel.row_count)
