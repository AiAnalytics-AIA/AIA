"""18.6.6's 18 built-in subpanels, adopted as AIA's catalogue (population-operations P7b).

A subpanel is a named view of the population: one filter on one field (an age range, or an
``is_*`` flag equal to 1), with the topics it is meant for and how well the population
supports it. The owner adopted them on 2026-10-11. They are a copy of
``legacy/npc-panel-18.6.6/app/BUILTIN_SUBPANELS_v17.json``, the companion the Czech contract
pins by hash (``czech.py``); ``tests/test_population_subpanels.py`` holds this module equal
to that file, field by field.

What is copied is 18.6.6's word, labelled as such. The counts (rows, weighted population,
donor support) are what 18.6.6 measured on ``17.1.2`` under ``vaha_strukturalni_2025``; AIA
recomputes none of them, because that would read respondent rows. Whether a subpanel can be
used on a given version is AIA's own decision: :func:`check_subpanel` asks that version's
field policy whether its filter field may serve ``AUDIENCE_FILTERING``.

Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Names and descriptions are 18.6.6's, verbatim; their en dashes are written as \u2013
# so the source stays ASCII-unambiguous (ruff RUF001).
from .policy import FieldPolicy, FieldUse

__all__ = [
    "BUILTIN_SUBPANELS",
    "MEASURED_ON",
    "MEASURED_UNDER_WEIGHT",
    "SUBPANEL_NOTE",
    "BuiltinSubpanel",
    "SubpanelCheck",
    "SubpanelFilter",
    "UnitMeasurement",
    "check_subpanel",
]

#: The version 18.6.6 measured the counts on, and the weight it measured them under.
MEASURED_ON: Final = "17.1.2"
MEASURED_UNDER_WEIGHT: Final = "vaha_strukturalni_2025"

#: 18.6.6's note on every subpanel, verbatim.
SUBPANEL_NOTE: Final = (
    "Donor support je autoritativní; počet syntetických řádků není totéž co informační kapacita."
)


@dataclass(frozen=True, slots=True)
class SubpanelFilter:
    """One field: a closed numeric range, or a value it must equal."""

    field: str
    minimum: int | None = None
    maximum: int | None = None
    equals: int | None = None

    def __post_init__(self) -> None:
        ranged = self.minimum is not None and self.maximum is not None
        if ranged == (self.equals is not None):
            raise ValueError(f"subpanel filter on {self.field}: a range or a value, not both")
        if (
            ranged
            and self.minimum is not None
            and self.maximum is not None
            and (self.minimum > self.maximum)
        ):
            raise ValueError(f"subpanel filter on {self.field}: an empty range")


@dataclass(frozen=True, slots=True)
class UnitMeasurement:
    """What 18.6.6 counted for a subpanel on :data:`MEASURED_ON`. Never AIA's measurement."""

    rows: int
    weighted_population: float
    unique_core_donors: int
    effective_core_donors: float
    max_core_reuse: int


@dataclass(frozen=True, slots=True)
class BuiltinSubpanel:
    """One built-in subpanel, as 18.6.6 declared it."""

    key: str
    name: str
    description: str
    filter: SubpanelFilter
    focus_domains: tuple[str, ...]
    #: 18.6.6's ``ready`` or ``proxy`` (a stand-in for the group it names).
    status: str
    #: 18.6.6's donor-support tier: ROBUST, GOOD, MODERATE, LIMITED, EXPERIMENTAL_LOW_SUPPORT.
    support_tier: str
    measured: UnitMeasurement


@dataclass(frozen=True, slots=True)
class SubpanelCheck:
    """Whether a subpanel's filter may be applied on one version, and why not."""

    key: str
    usable: bool
    #: ``None`` when usable; otherwise the field policy's reason (``unknown_field``, ...).
    reason: str | None


def check_subpanel(subpanel: BuiltinSubpanel, policy: FieldPolicy) -> SubpanelCheck:
    """May ``subpanel``'s filter field serve audience filtering under ``policy``?"""
    decision = policy.decide(subpanel.filter.field, FieldUse.AUDIENCE_FILTERING)
    if decision.allowed:
        return SubpanelCheck(subpanel.key, True, None)
    return SubpanelCheck(subpanel.key, False, decision.reason)


BUILTIN_SUBPANELS: Final[tuple[BuiltinSubpanel, ...]] = (
    BuiltinSubpanel(
        key="young_18_29",
        name="Mladí 18\u201329",
        description="Vestavěný pohled na kanonický panel: Mladí 18\u201329.",
        filter=SubpanelFilter(field="vek", minimum=18, maximum=29),
        focus_domains=("media", "socialni_site", "nakup", "hodnoty"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=2785,
            weighted_population=1340427.0,
            unique_core_donors=983,
            effective_core_donors=687.4,
            max_core_reuse=12,
        ),
    ),
    BuiltinSubpanel(
        key="students",
        name="Studenti",
        description="Vestavěný pohled na kanonický panel: Studenti.",
        filter=SubpanelFilter(field="is_student", equals=1),
        focus_domains=("vzdelani", "media", "finance"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=869,
            weighted_population=403371.2,
            unique_core_donors=334,
            effective_core_donors=240.1,
            max_core_reuse=10,
        ),
    ),
    BuiltinSubpanel(
        key="working_students",
        name="Pracující studenti",
        description="Vestavěný pohled na kanonický panel: Pracující studenti.",
        filter=SubpanelFilter(field="is_working_student", equals=1),
        focus_domains=("prace", "vzdelani", "finance"),
        status="ready",
        support_tier="MODERATE",
        measured=UnitMeasurement(
            rows=238,
            weighted_population=119586.1,
            unique_core_donors=115,
            effective_core_donors=83.3,
            max_core_reuse=7,
        ),
    ),
    BuiltinSubpanel(
        key="young_students",
        name="Mladí studenti",
        description="Vestavěný pohled na kanonický panel: Mladí studenti.",
        filter=SubpanelFilter(field="is_young_student", equals=1),
        focus_domains=("vzdelani", "media"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=866,
            weighted_population=402355.9,
            unique_core_donors=332,
            effective_core_donors=238.8,
            max_core_reuse=10,
        ),
    ),
    BuiltinSubpanel(
        key="young_workers",
        name="Mladí pracující",
        description="Vestavěný pohled na kanonický panel: Mladí pracující.",
        filter=SubpanelFilter(field="is_young_worker", equals=1),
        focus_domains=("prace", "media", "finance"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=1795,
            weighted_population=890035.6,
            unique_core_donors=635,
            effective_core_donors=432.1,
            max_core_reuse=12,
        ),
    ),
    BuiltinSubpanel(
        key="seniors_66_79",
        name="Senioři 66\u201379",
        description="Vestavěný pohled na kanonický panel: Senioři 66\u201379.",
        filter=SubpanelFilter(field="is_senior_66_79", equals=1),
        focus_domains=("zdravi", "media", "finance"),
        status="ready",
        support_tier="GOOD",
        measured=UnitMeasurement(
            rows=3422,
            weighted_population=1689334.3,
            unique_core_donors=292,
            effective_core_donors=193.0,
            max_core_reuse=51,
        ),
    ),
    BuiltinSubpanel(
        key="seniors_80_plus",
        name="Senioři 80+",
        description="Vestavěný pohled na kanonický panel: Senioři 80+.",
        filter=SubpanelFilter(field="is_senior_80_plus", equals=1),
        focus_domains=("zdravi", "media"),
        status="proxy",
        support_tier="LIMITED",
        measured=UnitMeasurement(
            rows=1422,
            weighted_population=436061.4,
            unique_core_donors=48,
            effective_core_donors=20.7,
            max_core_reuse=142,
        ),
    ),
    BuiltinSubpanel(
        key="parents",
        name="Rodiče",
        description="Vestavěný pohled na kanonický panel: Rodiče.",
        filter=SubpanelFilter(field="is_parent", equals=1),
        focus_domains=("rodina", "nakup", "finance"),
        status="proxy",
        support_tier="LIMITED",
        measured=UnitMeasurement(
            rows=14083,
            weighted_population=6675995.3,
            unique_core_donors=3177,
            effective_core_donors=955.0,
            max_core_reuse=142,
        ),
    ),
    BuiltinSubpanel(
        key="employed",
        name="Pracující",
        description="Vestavěný pohled na kanonický panel: Pracující.",
        filter=SubpanelFilter(field="is_employed", equals=1),
        focus_domains=("prace", "finance"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=11397,
            weighted_population=5636699.8,
            unique_core_donors=3456,
            effective_core_donors=2154.4,
            max_core_reuse=52,
        ),
    ),
    BuiltinSubpanel(
        key="unemployed",
        name="Nezaměstnaní",
        description="Vestavěný pohled na kanonický panel: Nezaměstnaní.",
        filter=SubpanelFilter(field="is_unemployed", equals=1),
        focus_domains=("prace", "finance"),
        status="ready",
        support_tier="GOOD",
        measured=UnitMeasurement(
            rows=475,
            weighted_population=241084.0,
            unique_core_donors=179,
            effective_core_donors=125.0,
            max_core_reuse=12,
        ),
    ),
    BuiltinSubpanel(
        key="teachers",
        name="Učitelé",
        description="Vestavěný pohled na kanonický panel: Učitelé.",
        filter=SubpanelFilter(field="is_teacher", equals=1),
        focus_domains=("prace", "vzdelani"),
        status="ready",
        support_tier="GOOD",
        measured=UnitMeasurement(
            rows=569,
            weighted_population=400621.4,
            unique_core_donors=207,
            effective_core_donors=141.4,
            max_core_reuse=19,
        ),
    ),
    BuiltinSubpanel(
        key="ict_specialists",
        name="ICT specialisté",
        description="Vestavěný pohled na kanonický panel: ICT specialisté.",
        filter=SubpanelFilter(field="is_ict_specialist", equals=1),
        focus_domains=("prace", "technologie"),
        status="ready",
        support_tier="MODERATE",
        measured=UnitMeasurement(
            rows=275,
            weighted_population=180479.3,
            unique_core_donors=76,
            effective_core_donors=57.7,
            max_core_reuse=9,
        ),
    ),
    BuiltinSubpanel(
        key="managers",
        name="Manažeři",
        description="Vestavěný pohled na kanonický panel: Manažeři.",
        filter=SubpanelFilter(field="is_manager", equals=1),
        focus_domains=("prace", "B2B"),
        status="ready",
        support_tier="GOOD",
        measured=UnitMeasurement(
            rows=503,
            weighted_population=284670.3,
            unique_core_donors=147,
            effective_core_donors=106.4,
            max_core_reuse=12,
        ),
    ),
    BuiltinSubpanel(
        key="science_engineering",
        name="Věda a technické specializace",
        description="Vestavěný pohled na kanonický panel: Věda a technické specializace.",
        filter=SubpanelFilter(field="is_science_engineering", equals=1),
        focus_domains=("prace", "technologie"),
        status="ready",
        support_tier="MODERATE",
        measured=UnitMeasurement(
            rows=306,
            weighted_population=195730.7,
            unique_core_donors=76,
            effective_core_donors=57.3,
            max_core_reuse=12,
        ),
    ),
    BuiltinSubpanel(
        key="business_admin_specialists",
        name="Business a administrativní specialisté",
        description="Vestavěný pohled na kanonický panel: Business a administrativní specialisté.",
        filter=SubpanelFilter(field="is_business_admin_specialist", equals=1),
        focus_domains=("prace", "finance"),
        status="ready",
        support_tier="MODERATE",
        measured=UnitMeasurement(
            rows=275,
            weighted_population=192894.7,
            unique_core_donors=103,
            effective_core_donors=80.0,
            max_core_reuse=7,
        ),
    ),
    BuiltinSubpanel(
        key="service_sales",
        name="Služby a prodej",
        description="Vestavěný pohled na kanonický panel: Služby a prodej.",
        filter=SubpanelFilter(field="is_service_sales", equals=1),
        focus_domains=("prace", "retail"),
        status="ready",
        support_tier="ROBUST",
        measured=UnitMeasurement(
            rows=2058,
            weighted_population=839625.0,
            unique_core_donors=701,
            effective_core_donors=482.5,
            max_core_reuse=16,
        ),
    ),
    BuiltinSubpanel(
        key="health_professionals",
        name="Zdravotničtí profesionálové",
        description="Vestavěný pohled na kanonický panel: Zdravotničtí profesionálové.",
        filter=SubpanelFilter(field="is_healthcare_profession_current", equals=1),
        focus_domains=("zdravi", "prace"),
        status="ready",
        support_tier="MODERATE",
        measured=UnitMeasurement(
            rows=260,
            weighted_population=143806.8,
            unique_core_donors=104,
            effective_core_donors=69.4,
            max_core_reuse=10,
        ),
    ),
    BuiltinSubpanel(
        key="medical_doctors",
        name="Lékaři",
        description="Vestavěný pohled na kanonický panel: Lékaři.",
        filter=SubpanelFilter(field="is_medical_doctor", equals=1),
        focus_domains=("zdravi", "prace"),
        status="proxy",
        support_tier="EXPERIMENTAL_LOW_SUPPORT",
        measured=UnitMeasurement(
            rows=29,
            weighted_population=19842.5,
            unique_core_donors=9,
            effective_core_donors=6.3,
            max_core_reuse=7,
        ),
    ),
)
