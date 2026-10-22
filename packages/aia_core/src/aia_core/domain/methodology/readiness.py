"""Study readiness, step by step: the limits a design must keep before a run starts (V1a).

Plan ``methodology-tab.md`` V1a (owner, 2026-10-14: the readiness bounds are editable as a
version). Two rules of AIA's structural readiness read a number a methodologist may want to
move, and both are declared in one specification, ``research_design.ReadinessSpec``:

* **the sample size** -- outside ``sample_size.min``-``sample_size.max`` the readiness check
  fails and no run starts;
* **the size of a tracked set** -- outside ``tracked_set.min``-``tracked_set.max`` the design
  does not compile; outside the recommended range readiness only warns.

The preset ``aia-readiness-1`` is 18.6.6's product policy (``PRODUCT_POLICY.json``
``research_design``), bit for bit. A run pins the limits in force when it starts and its
compile and preflight steps read the pin. What stays code: a missing n always blocks, and a
tracked set never has fewer than three items (fewer give no map, :func:`_validate`).

The pair n_min the Sociomap warning reads belongs to the Sociomap module and is edited there.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel

from ..research_design import (
    AIA_READINESS_V1,
    ReadinessSpec,
    prepare,
    readiness_problems,
)
from .catalogue import (
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodStep,
    ParameterEffect,
    ParameterRef,
    Preset,
    PreviewLine,
    StepGroup,
    Symbol,
)

__all__ = ["READINESS", "ReadinessRuleRefused"]

_R: Final = "aia_core.domain.research_design"
_T: Final = "packages/aia_core/tests"

_POLICY: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "PRODUCT_POLICY.json research_design.sample_size + tracked_set",
    "Meze převzaté z produktové politiky 18.6.6.",
)
_V1A: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    ".planning/plans/methodology-tab.md, V1a",
    "Meze připravenosti jsou upravitelné jako verze (vlastník, 2026-10-14).",
)


class ReadinessRuleRefused(ValueError):
    """Limits the module will not put in force; ``unsupported`` names each field and why, as
    :func:`..versions.validate_version` reports a module's refusal."""

    def __init__(self, unsupported: Mapping[str, str]) -> None:
        self.unsupported = dict(unsupported)
        super().__init__("; ".join(f"{k}: {v}" for k, v in sorted(self.unsupported.items())))


def _validate(spec: BaseModel) -> None:
    """Refuse limits no design could keep, or that would let a set too small for a map by."""
    if not isinstance(spec, ReadinessSpec):
        raise TypeError(f"not a readiness specification: {type(spec).__name__}")
    problems = readiness_problems(spec)
    if problems:
        raise ReadinessRuleRefused(problems)


_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="method",
        title_cs="Pojmenování mezí",
        formula_latex=r"\text{meze} = \text{methodology\_version}",
        implements=f"{_R}:ReadinessSpec",
        source_sha256="bcafdb6691eb2df280a3b524b70c5644c3ddad15a49ba61a2385f5c4e8e0a4c4",
        parameters=(ParameterRef("methodology_version", "Verze mezí připravenosti"),),
        evidence=(_V1A,),
        tests=(f"{_T}/test_methodology_readiness.py::test_the_preset_is_the_units_policy",),
        role_cs="Pojmenuje meze, se kterými kontrola připravenosti studii posoudí.",
        source_cs="verze v platnosti pro organizaci, nebo základ z kódu",
        effect_cs="kontrola připravenosti každé studie od aktivace; běh si meze nese",
    ),
    MethodStep(
        id="sample_size",
        title_cs="Velikost vzorku",
        formula_latex=r"n_{\min} \le n \le n_{\max}",
        implements=f"{_R}:assess_readiness",
        source_sha256="551e7d395f7c8da780872fd208ab12aa984583cf25ea056a2ef8b221edfdacff",
        symbols=(Symbol("n", "velikost vzorku zadaná v návrhu", "respondenti"),),
        parameters=(
            ParameterRef(
                "sample_size.min", "Nejmenší vzorek", "respondenti", ParameterEffect.BLOCKS_RUN
            ),
            ParameterRef(
                "sample_size.max", "Největší vzorek", "respondenti", ParameterEffect.BLOCKS_RUN
            ),
        ),
        evidence=(_POLICY,),
        tests=(
            f"{_T}/test_research_design.py::test_readiness_is_named_checks_and_a_fail_blocks",
            f"{_T}/test_research_design.py::test_the_one_rule_for_a_valid_n_refuses_and_never_clamps",
            f"{_T}/test_methodology_readiness.py::test_the_limits_in_force_decide_the_checks",
        ),
        role_cs=(
            "Kolik respondentů smí studie mít. Mimo rozsah AIA běh nespustí: výzkumník "
            "musí vzorek upravit."
        ),
        source_cs="n zadané v kroku Dimenze a vzorek",
        effect_cs=(
            "Kontrola a spuštění: řádek „Velikost vzorku“; tlačítko Spustit zůstane zablokované"
        ),
        note_cs=(
            "Obě meze zahrnuté. Bez zadaného n studii spustit nelze nikdy. Sociomapa "
            "upozorní, je-li n pod nejmenším n páru; to pravidlo patří Sociomapě."
        ),
        reading_cs="{sample_size.min} ≤ n ≤ {sample_size.max}",
        keeps_cs=(
            "nejmenší je menší než největší",
            "celá čísla, nejméně 1",
            "chybějící n blokuje vždy",
        ),
    ),
    MethodStep(
        id="tracked_set",
        title_cs="Počet položek v sadě",
        formula_latex=(
            r"k_{\min} \le k \le k_{\max},\quad \text{doporučeno}\ "
            r"k^{\mathrm{dop}}_{\min} \le k \le k^{\mathrm{dop}}_{\max}"
        ),
        implements=f"{_R}:_battery",
        source_sha256="4f83d0bb95488d3997d74ddfd7021b5f320a5e645b1145b033514025fabebd49",
        symbols=(Symbol("k", "počet srovnatelných položek jedné sledované sady", "položky"),),
        parameters=(
            ParameterRef(
                "tracked_set.min", "Nejméně položek", "položky", ParameterEffect.BLOCKS_DESIGN
            ),
            ParameterRef(
                "tracked_set.max", "Nejvíce položek", "položky", ParameterEffect.BLOCKS_DESIGN
            ),
            ParameterRef(
                "tracked_set.recommended_min",
                "Doporučeno nejméně",
                "položky",
                ParameterEffect.WARNS,
            ),
            ParameterRef(
                "tracked_set.recommended_max",
                "Doporučeno nejvíce",
                "položky",
                ParameterEffect.WARNS,
            ),
        ),
        evidence=(_POLICY,),
        tests=(
            f"{_T}/test_methodology_readiness.py::test_the_limits_in_force_decide_the_checks",
            f"{_T}/test_methodology_readiness.py::test_a_set_compiles_under_the_limits_it_is_given",
        ),
        role_cs=(
            "Kolik srovnatelných položek (značek, médií, emocí) smí mít jedna sledovaná sada. "
            "Mimo pevné meze se návrh nesestaví; mimo doporučené kontrola jen upozorní."
        ),
        source_cs="položky každé sledované sady v dotazníku",
        effect_cs=(
            "Návrh: sestavení se zastaví s chybou u sady · Kontrola a spuštění: upozornění u sady"
        ),
        note_cs=(
            "Pevné meze čte sestavení návrhu, doporučené kontrola připravenosti. Doporučený "
            "rozsah leží uvnitř pevného."
        ),
        reading_cs=(
            "{tracked_set.min} ≤ počet ≤ {tracked_set.max}, doporučeno "
            "{tracked_set.recommended_min}\u2013{tracked_set.recommended_max}"
        ),
        keeps_cs=(
            "nejméně 3 položky: méně mapu nedá",
            "doporučený rozsah uvnitř pevného",
            "nejmenší je menší než největší",
            "celá čísla",
        ),
    ),
)

#: The fictional designs the preview checks: a sample of 12 and of 450, a tracked set of 18
#: items and of 41, each line exactly as Kontrola a spuštění or the compile writes it.
_PREVIEW_SAMPLES: Final = (12, 450)
_PREVIEW_SETS: Final = (18, 41)


_SAMPLE_DESIGN: Final[dict[str, object]] = {
    "title": "Ukázka (fiktivní)",
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Jak hodnotíte?", "typ": "skala", "skala": [1, 5]}],
        }
    ],
}


def _preview_design(n: int, items: int) -> dict[str, object]:
    return {
        "title": "Ukázka (fiktivní)",
        "n": n,
        "sections": [
            {
                "type": "object_battery",
                "title": "Značky",
                "object_family": "značky",
                "objects": [f"Značka {i}" for i in range(1, items + 1)],
            }
        ],
    }


def _preview(spec: BaseModel) -> tuple[PreviewLine, ...]:
    """What a person meets under ``spec`` in Kontrola a spuštění: the code's own checks of
    fixed fictional designs, never a message written here."""
    if not isinstance(spec, ReadinessSpec):
        raise TypeError(f"not a readiness specification: {type(spec).__name__}")
    lines: list[PreviewLine] = []
    for n in _PREVIEW_SAMPLES:
        # One question and no tracked set: the sample's line depends on no other limit, and
        # the preview's size on no value of the draft.
        _, readiness = prepare(_SAMPLE_DESIGN | {"n": n}, pair_n_min=1, limits=spec)
        check = next(c for c in readiness.checks if c.id == "sample_size")
        lines.append(PreviewLine("sample_size", check.status.value, check.message))
    for items in _PREVIEW_SETS:
        _, readiness = prepare(_preview_design(450, items), pair_n_min=1, limits=spec)
        check = next(
            c
            for c in readiness.checks
            if c.id.startswith(("compile:", "battery_size:")) or c.id == "sociomap_input"
        )
        lines.append(PreviewLine("tracked_set", check.status.value, check.message))
    return tuple(lines)


_GROUPS: Final = (
    StepGroup("M", "Meze připravenosti", ("method",)),
    StepGroup("N", "Vzorek", ("sample_size",)),
    StepGroup("S", "Sledovaná sada", ("tracked_set",)),
)

READINESS: Final = MethodModule(
    id="readiness",
    title_cs="Připravenost studie: kdy lze běh spustit",
    steps=_STEPS,
    presets=(Preset("aia-readiness-1", AIA_READINESS_V1, _validate),),
    in_force="aia-readiness-1",
    editable=True,
    groups=_GROUPS,
    preview=_preview,
    preview_title_cs="Jak to uvidí výzkumník v Kontrole a spuštění",
    note_cs=(
        "Meze, které kontrola připravenosti čte: velikost vzorku a počet položek ve "
        "sledované sadě. Základ z kódu jsou hodnoty 18.6.6. Verze v platnosti platí pro "
        "kontrolu každé studie od aktivace; běh, který už začal, si své meze nese a nemění "
        "se. Nejmenší n páru pro Sociomapu se upravuje v oblasti Sociomapa."
    ),
)
