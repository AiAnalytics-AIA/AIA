"""The audience filter: which population rows a study's audience selects.

A port of 18.6.6's ``audience.sanitize_filters`` and ``audience._mask``
(``legacy/npc-panel-18.6.6/app/audience.py:217`` and ``:34``), kept as **one** function
pair so a preview and the fieldwork sample cannot disagree -- the bug 18.6.6 records at
``pipeline.py:255-257``. Parity is EXACT against the unit's own functions on a fictional
panel (``tools/audience_capture.py``; ``tests/fixtures/population_audience/``).

The filter's language is the unit's, unchanged: AND across dimensions, OR within one
dimension; a numeric dimension takes ``{"min", "max"}``, a two-item pair, or a single
number; any other dimension takes a value or a list of values, matched against the
values the panel actually holds.

**Which dimensions may filter** is the unit's catalogue, ported verbatim
(``audience_dimensions.CATEGORY_COLUMNS``, ``DERIVED_COLUMNS``, ``RESEARCH_ONLY``,
``audience_dimensions.py:42-118``). **A dimension's kind** -- numeric, binary or
category -- is the unit's rule (``_kind``, ``audience_dimensions.py:213``) applied to the
column as pandas types it when the unit reads the panel CSV (``pipeline.py:192``:
``read_csv(low_memory=False, dtype={'occupation_isco08': 'string'})``). AIA's population
holds every cell as its exact text, so :func:`column_type` reproduces that typing, and a
value's key is the ``str`` of its typed value: on a column with an empty cell pandas
reads ``1`` as ``1.0``, and the unit matches ``"1.0"``, not ``"1"`` (fixture C12-C14).
The kind is a property of the column, never of the filter value's shape: a two-item
list is an interval on a numeric dimension and a value list on any other, exactly as in
the unit.

One deliberate difference, in :func:`select_audience` only: the unit drops a filter it
cannot honour and goes on with the rest (``sanitize_filters`` returns ``dropped``);
AIA refuses the whole selection and names every reason, as ``sample_representative``
itself does (``pipeline.py:259-260``). It also asks the field policy for every
filtered dimension (:class:`~.policy.FieldUse` ``AUDIENCE_FILTERING``), which the unit
did not have.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from .errors import PopulationError
from .policy import FieldUse
from .runtime import Cell, RuntimePopulation
from .subpanels import BuiltinSubpanel

__all__ = [
    "AUDIENCE_FILTER_VERSION",
    "CATEGORY_COLUMNS",
    "DERIVED_COLUMNS",
    "RESEARCH_ONLY",
    "UNIT_TEXT_COLUMNS",
    "AudienceFilter",
    "AudienceRefused",
    "AudienceSelection",
    "Factor",
    "audience_mask",
    "column_type",
    "factor",
    "sanitize_filters",
    "select_audience",
    "subpanel_filters",
]

AUDIENCE_FILTER_VERSION: Final = "aia-audience-filter-1 (18.6.6 audience 17.9.4)"

# --------------------------------------------------------------------------- #
# The unit's catalogue (audience_dimensions.py:42-118), verbatim
# --------------------------------------------------------------------------- #

# fmt: off
CATEGORY_COLUMNS: Final[Mapping[str, tuple[str, ...]]] = {
    "demography": (
        "vek", "pohlavi", "kraj", "region_macro", "vzdelani", "vzdelani_isced",
        "zamestnani_status", "hlavni_status", "prijem_decile", "prijem_osobni_mesicni",
        "prijem_domacnosti_mesicni", "velikost_domacnosti", "pocet_deti_celkem",
        "has_partner", "partner_cohabiting", "is_parent", "is_student", "is_employed",
        "is_unemployed", "vek_skupina",
    ),
    "digital": (
        "internet_user_2025", "mobile_internet_user_2025", "online_shopper_2025",
        "internet_banking_user_2025", "online_video_user_2025", "online_music_user_2025",
        "online_news_user_2025", "ai_user_2025", "smartphone_use_intensity_1_10",
        "tablet_use_intensity_1_10", "computer_use_intensity_1_10",
        "digital_communication_intensity_1_10", "online_information_intensity_1_10",
        "online_entertainment_intensity_1_10", "online_transactions_intensity_1_10",
        "digital_personal_management_intensity_1_10",
    ),
    "social": (
        "social_network_user_2025", "facebook_regular_user_2026",
        "instagram_regular_user_2026", "tiktok_regular_user_2026",
        "youtube_regular_user_2026", "whatsapp_user_2026", "messenger_user_2026",
        "x_regular_user_2026", "linkedin_affinity_1_10", "social_media_minutes_day",
        "social_media_intensity_1_10", "facebook_minutes_day", "instagram_minutes_day",
        "tiktok_minutes_day", "youtube_minutes_day", "whatsapp_minutes_day",
        "messenger_minutes_day", "x_minutes_day", "social_passive_consumption_1_10",
        "social_public_interaction_1_10", "social_private_sharing_1_10",
        "social_algorithm_discovery_1_10", "social_relaxation_use_1_10",
    ),
    "media": (
        "tv_weekly_reach", "tv_daily_reach", "tv_minutes_day", "tv_intensity_1_10",
        "radio_weekly_reach", "radio_daily_reach", "radio_minutes_day",
        "radio_intensity_1_10", "print_period_reach", "print_minutes_day",
        "print_intensity_1_10", "news_tv_weekly", "news_print_weekly",
        "news_online_weekly", "news_social_weekly", "media_fragmentation_1_10",
        "old_new_media_orientation_1_10", "media_multitasking_1_10",
        "media_gross_minutes_day", "media_net_attention_minutes_day",
    ),
    "hobby": (
        "gaming_weekly", "gaming_hours_week", "gaming_intensity_1_10",
        "private_travel_trips_year_model", "travel_intensity_1_10",
        "sport_activity_1_10", "outdoor_activity_1_10", "socializing_offline_1_10",
        "dining_out_1_10", "culture_activity_1_10", "nightlife_1_10",
        "diy_home_activity_1_10", "cooking_activity_1_10",
        "physical_retail_activity_1_10", "commute_intensity_1_10",
        "caregiving_intensity_1_10",
    ),
    "shopping": (
        "price_sensitivity_1_10", "deal_proneness_1_10", "premium_willingness_1_10",
        "purchase_planning_1_10", "impulse_buying_1_10", "research_orientation_1_10",
        "review_reliance_1_10", "novelty_orientation_1_10", "risk_aversion_1_10",
        "brand_consciousness_1_10", "brand_loyalty_general_1_10",
        "convenience_orientation_1_10", "local_brand_preference_1_10",
        "sustainability_orientation_1_10", "status_consumption_1_10",
        "category_knowledge_general_1_10", "market_knowledge_general_1_10",
    ),
    "advertising": (
        "privacy_concern_1_10", "persuasion_knowledge_1_10",
        "advertising_skepticism_1_10", "reactance_1_10", "need_for_cognition_1_10",
        "need_for_affect_1_10", "social_proof_susceptibility_1_10",
        "influencer_receptivity_1_10", "authority_receptivity_1_10",
        "scarcity_response_1_10", "ad_avoidance_1_10", "tv_ad_attention_1_10",
        "social_ad_attention_1_10", "search_ad_attention_1_10",
        "audio_ad_attention_1_10", "print_ad_attention_1_10", "ooh_ad_attention_1_10",
        "advertising_literacy_1_10",
    ),
    "values": (
        "value_self_direction_1_10", "value_stimulation_1_10", "value_hedonism_1_10",
        "value_achievement_1_10", "value_power_1_10", "value_security_1_10",
        "value_conformity_1_10", "value_tradition_1_10", "value_benevolence_1_10",
        "value_universalism_1_10", "value_openness_to_change_1_10",
        "value_conservation_1_10", "value_self_enhancement_1_10",
        "value_self_transcendence_1_10", "family_centrality_1_10",
        "work_centrality_1_10", "local_attachment_1_10",
        "cosmopolitan_orientation_1_10", "authority_orientation_1_10",
    ),
    "finance": (
        "financial_daily_decision_role", "financial_budgeting", "financial_goal_set",
        "financial_unexpected_14k_capable", "financial_income_loss_without_loan",
        "financial_regular_reserve", "financial_income_covers_costs",
        "financial_saves_bank_product", "financial_invests_stocks_funds",
        "financial_crypto_saving", "financial_mobile_payment", "financial_knowledge_1_10",
        "financial_behavior_1_10", "financial_resilience_1_10",
        "financial_planning_1_10", "financial_capability_1_10",
    ),
    "work": (
        "occupation_major", "occupation_2digit", "is_teacher", "is_ict_specialist",
        "is_science_engineering", "is_business_admin_specialist", "is_manager",
        "is_service_sales", "is_health_professional", "is_medical_doctor",
        "is_health_associate_professional", "is_healthcare_profession_current",
        "is_construction_ecosystem_current", "is_real_estate_professional_current",
        "is_procurement_buyer_current",
    ),
}
# fmt: on

#: Runtime dimensions the unit attaches (``attach_derived``); filterable.
DERIVED_COLUMNS: Final = (
    "life_stage_derived",
    "digital_engagement_tier_derived",
    "dominant_media_derived",
    "dominant_leisure_derived",
    "shopping_orientation_derived",
    "ad_receptivity_tier_derived",
    "financial_capability_tier_derived",
)

#: Inspectable, never a targeting filter (``audience_dimensions.py:98-103``).
RESEARCH_ONLY: Final = (
    "core_religion_group",
    "core_religious_attendance",
    "religious_affiliation_group",
    "religious_practice_1_10",
    "PHQ9_2022",
    "GAD7_2022",
    "mentalni_zdravi_sebehodnoceni_2022",
    "fyzicke_zdravi_sebehodnoceni_2022",
    "volba_2021_strana",
    "politicky_zajem_2021",
    "redistribuce_podpora_2021",
    "BFI_EXTR",
    "BFI_AGRE",
    "BFI_CONS",
    "BFI_EMOS",
    "BFI_OPEM",
)

#: Columns the unit reads as text whatever they hold (``pipeline.py:192``).
UNIT_TEXT_COLUMNS: Final = frozenset({"occupation_isco08"})

_FILTERABLE: Final = frozenset(
    (*(c for cols in CATEGORY_COLUMNS.values() for c in cols), *DERIVED_COLUMNS)
)
_NOT_FILTERABLE: Final = frozenset(RESEARCH_ONLY) - _FILTERABLE

# --------------------------------------------------------------------------- #
# How pandas types a column the unit reads
# --------------------------------------------------------------------------- #

#: pandas' default ``na_values`` for ``read_csv`` (an empty cell is ``None`` already).
# fmt: off
_NA_TOKENS: Final = frozenset(
    {
        "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
        "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a",
        "nan", "null",
    }
)
# fmt: on
_TRUE: Final = frozenset({"True", "TRUE", "true"})
_FALSE: Final = frozenset({"False", "FALSE", "false"})
_INT: Final = re.compile(r"[+-]?\d+")
_FLOAT: Final = re.compile(r"[+-]?(\d+\.?\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?|inf|Infinity)")
_INT64: Final = 2**63

ColumnType = Literal["int", "float", "bool", "text"]
Kind = Literal["numeric", "binary", "category"]

#: A typed cell: what pandas would hold. ``None`` is NaN.
Typed = int | float | bool | str | None


def _is_na(cell: Cell) -> bool:
    return cell is None or cell in _NA_TOKENS


def column_type(name: str, cells: Sequence[Cell]) -> ColumnType:
    """The dtype ``read_csv(low_memory=False)`` gives this column, as the unit loads it.

    int64 when every cell is an integer and none is missing; float64 when every present
    cell is a number (an empty one makes an integer column float, as pandas does), or
    when nothing is present at all; bool when every cell is a boolean and none is
    missing (a missing one leaves it text); text otherwise, and always for
    :data:`UNIT_TEXT_COLUMNS`.
    """
    if name in UNIT_TEXT_COLUMNS:
        return "text"
    present = [c for c in cells if c is not None and c not in _NA_TOKENS]
    missing = len(present) != len(cells)
    if not present:
        return "float"
    if all(c in _TRUE or c in _FALSE for c in present):
        return "text" if missing else "bool"
    if not missing and all(_INT.fullmatch(c) and abs(int(c)) < _INT64 for c in present):
        return "int"
    if all(_FLOAT.fullmatch(c) for c in present):
        return "float"
    return "text"


def _typed(cell: Cell, kind: ColumnType) -> Typed:
    if _is_na(cell):
        return None
    assert cell is not None
    if kind == "int":
        return int(cell)
    if kind == "float":
        return float(cell)
    if kind == "bool":
        return cell in _TRUE
    return cell


def _numeric(value: Typed) -> float | None:
    """``pd.to_numeric(errors="coerce")`` of one typed cell."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        number = float(value)
        return None if math.isnan(number) else number
    try:
        number = float(value)
    except ValueError:
        return None
    return None if math.isnan(number) else number


def _key(value: Typed) -> str:
    """``str`` of a typed cell, as the unit's lookup keys it."""
    return str(value)


# --------------------------------------------------------------------------- #
# The factor map (audience_dimensions._factor / _kind)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Factor:
    """One dimension as ``audience_dimensions.factor_map`` describes it."""

    name: str
    kind: Kind
    filterable: bool
    minimum: float | None = None
    maximum: float | None = None


def _kind(values: Sequence[Typed], column: ColumnType) -> Kind:
    present = [v for v in values if v is not None]
    if not present:
        return "category"
    if column == "text":
        return "category"
    unique = list(dict.fromkeys(present))
    keys = {str(float(v)).rstrip("0").rstrip(".") for v in unique[:50]}
    if len(unique) <= 2 and keys <= {"0", "1"}:
        return "binary"
    return "numeric"


def factor(name: str, columns: Mapping[str, Sequence[Cell]]) -> Factor | None:
    """The factor the unit's catalogue has for ``name``, or ``None`` when it has none."""
    if name not in columns or (name not in _FILTERABLE and name not in _NOT_FILTERABLE):
        return None
    cells = columns[name]
    column = column_type(name, cells)
    typed = [_typed(c, column) for c in cells]
    kind = _kind(typed, column)
    filterable = name in _FILTERABLE
    if kind != "numeric":
        return Factor(name, kind, filterable)
    numbers = [n for n in (_numeric(v) for v in typed) if n is not None]
    low, high = (min(numbers), max(numbers)) if numbers else (None, None)
    if name.endswith("_1_10"):
        low, high = 1.0, 10.0
    return Factor(name, kind, filterable, low, high)


# --------------------------------------------------------------------------- #
# sanitize_filters + _mask
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AudienceFilter:
    """One kept dimension: a closed interval, or the panel values it may equal."""

    field: str
    interval: tuple[float, float] | None = None
    values: tuple[Typed, ...] = ()

    def as_json(self) -> dict[str, Any]:
        if self.interval is not None:
            return {"min": self.interval[0], "max": self.interval[1]}
        return {"values": [_key(v) for v in self.values]}


def sanitize_filters(
    columns: Mapping[str, Sequence[Cell]], raw: Mapping[str, Any] | None
) -> tuple[dict[str, AudienceFilter], list[str]]:
    """``audience.sanitize_filters``: the filters the panel can honour, and why the rest not.

    The reasons are the unit's own sentences, so a refusal reads as 18.6.6 said it.
    """
    clean: dict[str, AudienceFilter] = {}
    dropped: list[str] = []
    for key, value in (raw or {}).items():
        spec = factor(key, columns)
        if spec is None or not spec.filterable:
            dropped.append(f"{key}: není podporovaná filtrační dimenze")
            continue
        if spec.kind == "numeric":
            interval = _interval(value, spec)
            if isinstance(interval, str):
                dropped.append(f"{key}: {interval}")
            else:
                clean[key] = AudienceFilter(key, interval=interval)
            continue
        kept = _values(value, columns[key], key)
        if not kept:
            dropped.append(f"{key}: žádná zadaná hodnota v panelu neexistuje")
        else:
            clean[key] = AudienceFilter(key, values=tuple(kept))
    return clean, dropped


def _interval(value: Any, spec: Factor) -> tuple[float, float] | str:
    low: Any
    high: Any
    if isinstance(value, dict) and ("min" in value or "max" in value):
        low, high = value.get("min", spec.minimum), value.get("max", spec.maximum)
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = value
    elif isinstance(value, (int, float)):
        low = high = value
    else:
        return "očekáván interval min/max"
    try:
        lo, hi = float(low), float(high)
    except (TypeError, ValueError):
        return "neplatný číselný interval"
    return (hi, lo) if hi < lo else (lo, hi)


def _values(value: Any, cells: Sequence[Cell], name: str) -> list[Typed]:
    column = column_type(name, cells)
    lookup: dict[str, Typed] = {}
    for cell in cells:
        typed = _typed(cell, column)
        if typed is not None:
            lookup.setdefault(_key(typed), typed)
    numeric_binary = bool(lookup) and set(lookup) <= {"0", "1", "0.0", "1.0", "True", "False"}
    asked = list(value) if isinstance(value, (list, tuple, set)) else [value]
    keys: list[str] = []
    for item in asked:
        if isinstance(item, bool) and numeric_binary:
            keys.extend([str(int(item)), str(item)])
        else:
            keys.append(str(item))
    kept: list[Typed] = []
    for key in keys:
        if key in lookup and lookup[key] not in kept:
            kept.append(lookup[key])
    return kept


def audience_mask(
    columns: Mapping[str, Sequence[Cell]], clean: Mapping[str, AudienceFilter]
) -> tuple[int, ...]:
    """``audience._mask``: the row positions every kept filter admits (AND across, OR within)."""
    if not columns:
        return ()
    rows = len(next(iter(columns.values())))
    admitted = [True] * rows
    for name, rule in clean.items():
        cells = columns[name]
        column = column_type(name, cells)
        if rule.interval is not None:
            lo, hi = rule.interval
            for i, cell in enumerate(cells):
                number = _numeric(_typed(cell, column))
                if number is None or not lo <= number <= hi:
                    admitted[i] = False
        else:
            wanted = set(rule.values)
            for i, cell in enumerate(cells):
                typed = _typed(cell, column)
                if typed is None or typed not in wanted:
                    admitted[i] = False
    return tuple(i for i, ok in enumerate(admitted) if ok)


def subpanel_filters(subpanel: BuiltinSubpanel) -> dict[str, Any]:
    """A built-in subpanel as the filter it is: ``population_subpanels.runtime_filters``.

    18.6.6 hands a subpanel to the same filter as any audience (``project_patch`` puts
    ``runtime_filters(spec)`` in the project; ``apply`` masks with ``audience._mask``),
    so a subpanel is selected exactly as the equivalent filter is, and refused by the
    same rules.
    """
    rule = subpanel.filter
    if rule.equals is not None:
        return {rule.field: rule.equals}
    return {rule.field: [rule.minimum, rule.maximum]}


# --------------------------------------------------------------------------- #
# The selection a run records
# --------------------------------------------------------------------------- #


class AudienceRefused(PopulationError):
    """The audience cannot be selected as asked; every reason is named."""

    reason = "sampling_filter_invalid"

    def __init__(self, message: str, *, reason: str, reasons: Sequence[str]) -> None:
        super().__init__(message, reason=reason)
        self.reasons = tuple(reasons)


@dataclass(frozen=True, slots=True)
class AudienceSelection:
    """The rows an audience selects from one population, and the filters as applied."""

    filters: tuple[AudienceFilter, ...]
    rows: tuple[int, ...]
    population_rows: int
    version: str = AUDIENCE_FILTER_VERSION

    def filters_json(self) -> dict[str, Any]:
        return {f.field: f.as_json() for f in self.filters}


class _Columns(Mapping[str, Sequence[Cell]]):
    """A population's text columns, read on demand, for the fields it carries."""

    def __init__(self, population: RuntimePopulation) -> None:
        self._population = population
        self._names = frozenset(population.fields) - {"_analysis_weight"}
        self._cache: dict[str, Sequence[Cell]] = {}

    def __getitem__(self, name: str) -> Sequence[Cell]:
        if name not in self._names:
            raise KeyError(name)
        if name not in self._cache:
            self._cache[name] = self._population.column(name)
        return self._cache[name]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._names))

    def __len__(self) -> int:
        return len(self._names)


def select_audience(
    population: RuntimePopulation, raw: Mapping[str, Any] | None
) -> AudienceSelection:
    """The audience a study asked for, from the population its run recorded -- or a refusal.

    Refuses (never narrows silently) when any filter cannot be honoured
    (``sampling_filter_invalid``), when the field policy does not allow a filtered
    dimension for audience filtering (``sampling_field_refused``), and when nothing
    is left (``sampling_empty``).
    """
    columns = _Columns(population)
    clean, dropped = sanitize_filters(columns, raw)
    if dropped:
        raise AudienceRefused(
            "the audience filter cannot be applied as asked: " + "; ".join(dropped),
            reason="sampling_filter_invalid",
            reasons=dropped,
        )
    refused = [
        f"{name}: {decision.reason}"
        for name in clean
        if not (decision := population.decide(name, FieldUse.AUDIENCE_FILTERING)).allowed
    ]
    if refused:
        raise AudienceRefused(
            "the field policy does not allow these dimensions for audience filtering: "
            + "; ".join(refused),
            reason="sampling_field_refused",
            reasons=refused,
        )
    rows = audience_mask(columns, clean)
    if not rows:
        raise AudienceRefused(
            "the audience filter selects no row of this population",
            reason="sampling_empty",
            reasons=(),
        )
    return AudienceSelection(
        filters=tuple(clean.values()), rows=rows, population_rows=population.row_count
    )
