"""The audience factor catalogue: what a person may filter a study's audience by.

A port of 18.6.6's ``audience_dimensions.catalog(df, include_research_only=True)``
(``legacy/npc-panel-18.6.6/app/audience_dimensions.py:226-264``), the document its
``/api/audience/dimensions`` route served (``ui_server.py:1755``) and its factor editor drew
from. Parity is EXACT against the unit's own function on the audience filter's fictional
panel (``tools/audience_capture.py``; ``tests/fixtures/audience_filter/catalogue.json``).

What each factor says is the unit's: the curated columns per category, then the
deterministic derived dimensions, then the research-only signals (listed, never
filterable); a numeric factor's range and its 10th and 90th percentiles (pandas' linear
quantile), a ``_1_10`` scale's fixed 1-10; any other factor's 60 most frequent values
with their row counts, most frequent first and ties in the order they first appear. A
factor's kind is :func:`~.audience.factor`'s, so the catalogue and the filter cannot
disagree about one.

Three differences, each stated where it shows:

- the Data Library's materialized overlays (category ``custom``) are not here: AIA has
  none yet (P4);
- the unit's ``version``, ``base_columns`` and ``runtime_columns`` are not here; the
  catalogue states :data:`AUDIENCE_CATALOGUE_VERSION` instead, and whoever keeps it names
  the population version it was computed from;
- :func:`with_policy` adds what the unit did not have: each factor's field-policy answer
  for ``AUDIENCE_FILTERING`` in the version it was computed from. A factor the policy
  refuses stays listed; it is not offered as a filter, and :func:`~.audience.select_audience`
  refuses it anyway.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from .audience import (
    CATEGORY_COLUMNS,
    DERIVED_COLUMNS,
    RESEARCH_ONLY,
    _is_na,
    _key,
    _numeric,
    _typed,
    column_type,
    factor,
)
from .policy import FieldUse
from .runtime import Cell, RuntimePopulation

__all__ = [
    "AUDIENCE_CATALOGUE_VERSION",
    "CATEGORY_META",
    "audience_catalogue",
    "catalogue_of",
    "for_the_screen",
    "with_policy",
]

AUDIENCE_CATALOGUE_VERSION: Final = "aia-audience-catalogue-1 (18.6.6 audience_dimensions 17.9.4)"

# --------------------------------------------------------------------------- #
# The unit's words (audience_dimensions.py:24-38, :112-118), verbatim
# --------------------------------------------------------------------------- #

# fmt: off
CATEGORY_META: Final[Mapping[str, tuple[str, str]]] = {
    "demography": (
        "Demografie a životní fáze",
        "Kdo člověk je a v jaké životní situaci se nachází.",
    ),
    "digital": (
        "Digitální chování a zařízení",
        "Používání internetu, zařízení a digitálních služeb.",
    ),
    "social": (
        "Sociální sítě a platformy",
        "Používání konkrétních platforem a způsob sociálního používání.",
    ),
    "media": (
        "Média a zpravodajství",
        "TV, rádio, tisk, online/news a celková mediální pozornost.",
    ),
    "hobby": (
        "Hobby, volný čas a lifestyle",
        "Gaming, cestování, sport, outdoor, kultura, gastronomie, DIY a další aktivity.",
    ),
    "shopping": (
        "Nákupní a značkové chování",
        "Cena, slevy, premium, plánování, recenze, loajalita, convenience a značky.",
    ),
    "advertising": (
        "Reakce na reklamu a komunikaci",
        "Pozornost, skepse, influencer/social proof, reactance a reklamní kanály.",
    ),
    "values": (
        "Hodnoty a životní orientace",
        "Hodnotové orientace, rodina/práce, lokalita a kosmopolitnost.",
    ),
    "finance": (
        "Finance a finanční capability",
        "Rozpočtování, rezervy, investice, znalosti a finanční resilience.",
    ),
    "work": (
        "Práce, profese a role",
        "Ekonomická aktivita, profesní skupiny a pracovní role.",
    ),
    "derived": (
        "Odvozené praktické profily",
        "Deterministické souhrny vytvořené pouze z již existujících respondentních signálů.",
    ),
    "custom": (
        "Nové dimenze z Data Library",
        "Schválené evidence-based dimenze materializované jako auditovaný overlay.",
    ),
    "research_only": (
        "Research-only / citlivé",
        "Dostupné pro metodický research, ale ne jako běžný audience targeting filtr.",
    ),
}

_LABELS: Final[Mapping[str, str]] = {
    "vek": "Věk", "pohlavi": "Pohlaví", "kraj": "Kraj", "region_macro": "Makroregion",
    "vzdelani": "Vzdělání", "vzdelani_isced": "Vzdělání (ISCED)",
    "zamestnani_status": "Ekonomická aktivita", "hlavni_status": "Hlavní životní status",
    "prijem_decile": "Příjmový decil", "prijem_osobni_mesicni": "Osobní měsíční příjem",
    "prijem_domacnosti_mesicni": "Příjem domácnosti", "velikost_domacnosti": "Velikost domácnosti",
    "pocet_deti_celkem": "Počet dětí", "has_partner": "Má partnera", "is_parent": "Rodič",
    "life_stage_derived": "Životní fáze",
    "digital_engagement_tier_derived": "Digitální angažovanost",
    "dominant_media_derived": "Dominantní mediální kanál",
    "dominant_leisure_derived": "Dominantní volnočasová aktivita",
    "shopping_orientation_derived": "Nákupní orientace",
    "ad_receptivity_tier_derived": "Receptivita k reklamě",
    "financial_capability_tier_derived": "Finanční capability tier",
}
# fmt: on

_LOGIC: Final = "OR uvnitř jedné dimenze, AND mezi dimenzemi"
_PANEL: Final = ("PANEL_EXISTING", "Panel v17")
_DERIVED: Final = ("DERIVED_EXISTING_SIGNALS", "Deterministický overlay z existujících signálů")
_RESEARCH: Final = ("PANEL_EXISTING_RESEARCH_ONLY", "Research-only panel signal")
_YEAR: Final = re.compile(r"_(2025|2026|2022)$")
#: Every column the catalogue can list, in no particular order.
_COLUMNS: Final = frozenset(
    (*(c for names in CATEGORY_COLUMNS.values() for c in names), *DERIVED_COLUMNS, *RESEARCH_ONLY)
)
#: ``value_counts().head(60)`` (``audience_dimensions.py:235``).
_TOP_VALUES: Final = 60


def _label(name: str) -> str:
    """``_label`` (``audience_dimensions.py:120``)."""
    if name in _LABELS:
        return _LABELS[name]
    text = _YEAR.sub("", name, count=1)
    text = text.replace("_1_10", "").replace("_0_1", "").replace("_", " ")
    return text[:1].upper() + text[1:]


def _lerp(a: float, b: float, t: float) -> float:
    """NumPy's ``_lerp``, the linear method's interpolation, bit for bit."""
    diff = b - a
    value = a + diff * t
    if t >= 0.5:
        value = b - diff * (1 - t)
    return a if a == b else value


def _quantile(ordered: Sequence[float], q: float) -> float:
    """``Series.quantile(q)`` (linear) of an ascending, NaN-free sequence."""
    index = (len(ordered) - 1) * (q * 100 / 100)
    low = math.floor(index)
    high = min(low + 1, len(ordered) - 1)
    return _lerp(ordered[low], ordered[high], index - low)


def _values(typed: Sequence[Any]) -> list[dict[str, Any]]:
    """``s.dropna().astype(str).value_counts().head(60)``: ties keep first appearance."""
    counts: dict[str, int] = {}
    for value in typed:
        if value is not None:
            key = _key(value)
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: -item[1])
    return [{"value": value, "count": count} for value, count in ranked[:_TOP_VALUES]]


def _factor(
    name: str,
    columns: Mapping[str, Sequence[Cell]],
    category: str,
    *,
    status: tuple[str, str],
    filterable: bool = True,
    sensitive: bool = False,
) -> dict[str, Any] | None:
    """``_factor`` (``audience_dimensions.py:226``)."""
    if name not in columns:
        return None
    described = factor(name, columns)
    assert described is not None  # every catalogue column is one the filter knows
    cells = columns[name]
    kind = column_type(name, cells)
    typed = [_typed(c, kind) for c in cells]
    out: dict[str, Any] = {
        "id": name,
        "column": name,
        "label": _label(name),
        "category": category,
        "category_label": CATEGORY_META[category][0],
        "kind": described.kind,
        "status": status[0],
        "filterable": filterable,
        "sensitive": sensitive,
        "source": status[1],
        "non_null": sum(1 for c in cells if not _is_na(c)),
    }
    if described.kind == "numeric":
        numbers = sorted(n for n in (_numeric(v) for v in typed) if n is not None)
        if numbers:
            out.update(
                {
                    "min": numbers[0],
                    "max": numbers[-1],
                    "p10": _quantile(numbers, 0.1),
                    "p90": _quantile(numbers, 0.9),
                }
            )
        if name.endswith("_1_10"):
            out.update({"min": 1.0, "max": 10.0, "scale_hint": "1–10"})  # noqa: RUF001 - the unit's own text
    else:
        out["values"] = _values(typed)
    return out


def audience_catalogue(columns: Mapping[str, Sequence[Cell]]) -> dict[str, Any]:
    """The catalogue of a population's ANALYSIS view (source and derived columns)."""
    factors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category, names in CATEGORY_COLUMNS.items():
        for name in names:
            x = _factor(name, columns, category, status=_PANEL)
            if x is not None and name not in seen:
                factors.append(x)
                seen.add(name)
    for name in DERIVED_COLUMNS:
        x = _factor(name, columns, "derived", status=_DERIVED)
        if x is not None and name not in seen:
            factors.append(x)
            seen.add(name)
    # As the unit's loop: no ``seen`` check here (no research-only column is curated).
    for name in RESEARCH_ONLY:
        x = _factor(
            name, columns, "research_only", status=_RESEARCH, filterable=False, sensitive=True
        )
        if x is not None:
            factors.append(x)
    categories = []
    for cid, (label, description) in CATEGORY_META.items():
        count = sum(1 for x in factors if x["category"] == cid)
        if count:
            categories.append(
                {
                    "id": cid,
                    "label": label,
                    "description": description,
                    "count": count,
                    "filterable_count": sum(
                        1 for x in factors if x["category"] == cid and x["filterable"]
                    ),
                }
            )
    return {
        "catalogue_version": AUDIENCE_CATALOGUE_VERSION,
        "categories": categories,
        "factors": factors,
        "filterable_count": sum(bool(x["filterable"]) for x in factors),
        "factor_count": len(factors),
        "logic": _LOGIC,
    }


def with_policy(catalogue: Mapping[str, Any], population: RuntimePopulation) -> dict[str, Any]:
    """The catalogue with each factor's ``AUDIENCE_FILTERING`` answer in ``population``."""
    factors = []
    for x in catalogue["factors"]:
        decision = population.decide(x["id"], FieldUse.AUDIENCE_FILTERING)
        factors.append({**x, "policy_allowed": decision.allowed, "policy_reason": decision.reason})
    return {**catalogue, "factors": factors}


def catalogue_of(population: RuntimePopulation) -> dict[str, Any]:
    """A loaded population's catalogue, every factor with its policy answer (what is kept)."""
    carried = set(population.fields)
    columns = {name: population.column(name) for name in _COLUMNS if name in carried}
    return with_policy(audience_catalogue(columns), population)


def for_the_screen(catalogue: Mapping[str, Any]) -> dict[str, Any]:
    """What the audience step is shown: the research-only factors reduced to their count.

    The unit sent them whole and its editor drew only their number
    (``filterCategories``); AIA does not send what is not drawn. Their category, with its
    count, stays.
    """
    factors = [x for x in catalogue["factors"] if x["category"] != "research_only"]
    return {**catalogue, "factors": factors}
