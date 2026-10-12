"""Weighting, step by step: which weight each respondent carries, and what is done with a bad one.

ADR 0023; plan ``methodology-tab.md`` W1a. AIA does not compute weights: a population's weights
are columns of the panel, one per declared scheme, and the import contract names them. There
is no calibration, raking or GREG step. What weighting decides is which column, what an import
must sum to, and what happens to a weight that is not a positive finite number.

All of it is declared in ``WeightingSpec``, whose preset ``aia-weighting-1`` is built from the
Czech import contract (``population/czech.py``) and is therefore its declaration exactly:

* four schemes, each a role bound to one column;
* the default role a binding records when none is chosen;
* the expected total and tolerance an import is checked against, for the two schemes whose
  total the reference declared (none is invented for the other two);
* what the aggregate does with an invalid weight: the unit's median, today.

Nothing reads the specification yet: the contract decides the schemes, and the aggregate
cleans as 18.6.6 did. A run pins the weighting in force from W1b, when the cleaning becomes a
choice it reads; it is editable from W1c.

Finding D1 is named on its steps: three cleaning rules (the aggregate imputes the median, the
evidence gate and the population loader refuse) and Kish's n computed in three places, equal
on positive finite weights and different on any other (``test_methodology_weighting.py``).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..population.czech import CZ_SYNTHETIC_V17
from ..population.weights import WeightCleaning, WeightingSpec, weighting_spec
from .catalogue import (
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodStep,
    ParameterRef,
    Preset,
    StepGroup,
    Symbol,
)

__all__ = ["AIA_WEIGHTING_V1", "WEIGHTING"]

_D: Final = "aia_core.domain"
_P: Final = f"{_D}.population"
_A: Final = "aia_core.domain.research_aggregate"
_T: Final = "packages/aia_core/tests"
_TW: Final = f"{_T}/test_methodology_weighting.py"
_PC: Final = f"{_T}/test_population_contract.py"

#: The Czech contract's weighting, exactly, and the unit's cleaning (plan W1a).
AIA_WEIGHTING_V1: Final = weighting_spec(
    CZ_SYNTHETIC_V17,
    methodology_version="aia-weighting-1",
    aggregate_cleaning=WeightCleaning.MEDIAN,
)

_CONTRACT: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "docs/architecture/population.md; population/czech.py CZ_SYNTHETIC_V17",
    "Schémata, výchozí role i součty jsou deklarace importní smlouvy, ověřené proti "
    "referenci (F11).",
)
_M01: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "population/weights.py (methodology-ledger M01, fixture F11)",
    "Reference měla čtyři nezávislé cesty k váze a každá selhávala jinak (náhradní "
    "sloupec, váhy 1, fillna(0)). AIA má jednu: role určí sloupec, nebo se načtení odmítne. "
    "Záměrný rozdíl (INTENTIONAL_DIFFERENCE).",
)
_UNC: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "uncertainty.py (clean_weights, kish_effective_n)",
    "Převzato z 18.6.6 přesně (EXACT).",
)
_M16: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "evidence/support.py (methodology-ledger M06, M16)",
    "Brána důkazů váhy nečistí: do analýzy mají přijít už jako deklarované schéma.",
)
_Q6: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "plan sociomap-signed-relations, rozhodnutí Q6",
    "Kishovo n páru v Fisherově intervalu: přiblížení schválené jako rozhodnutí AIA.",
)

_ROLES: Final = tuple(AIA_WEIGHTING_V1.schemes)
_ROLE_CS: Final = {
    "default_current": "výchozí (struktura 2025)",
    "demographic_current_approx": "demografické (populace 2025, přibližně)",
    "census_2021": "Sčítání 2021",
    "party_2021_aggregate": "volby 2021 (srovnání)",
}

_D1_KISH: Final = f"{_TW}::test_kish_is_computed_three_times_and_agrees_only_on_valid_weights"
_D1_CLEAN: Final = f"{_TW}::test_three_cleaning_rules_impute_or_refuse_the_same_weight"
_DECLARED: Final = f"{_TW}::test_the_preset_is_the_contracts_declaration_exactly"


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, WeightingSpec):
        raise TypeError(f"not a weighting specification: {type(spec).__name__}")


_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="method",
        title_cs="Pojmenování vážení",
        formula_latex=r"\text{vážení} = \text{methodology\_version}",
        implements=f"{_P}.weights:WeightingSpec",
        source_sha256="388bcbb83712a16ad64102a6128e751eec50beee59cbd2d8ea52d31c40e972d5",
        parameters=(ParameterRef("methodology_version", "Verze vážení"),),
        evidence=(_CONTRACT,),
        tests=(_DECLARED,),
    ),
    # ------------------------------------------------------------------- schemes
    MethodStep(
        id="scheme",
        title_cs="Schéma: role určí sloupec",
        formula_latex=(
            r"w_i = \text{panel}\left[i,\ \text{sloupec}(r)\right],\quad "
            r"r = \text{role běhu, jinak výchozí role}"
        ),
        implements=f"{_P}.weights:resolve_weight_scheme",
        source_sha256="c387afd2b0977a0c8d33348890c301cbce620dcbdc0a2fd520880bf4758aecb2",
        symbols=(Symbol("r", "role vah, kterou si vazba populace zapamatuje"),),
        parameters=(
            ParameterRef("contract_id", "Importní smlouva"),
            ParameterRef("default_role", "Výchozí role"),
            *(ParameterRef(f"schemes.{r}.column", f"Sloupec: {_ROLE_CS[r]}") for r in _ROLES),
        ),
        evidence=(_CONTRACT, _M01),
        tests=(
            f"{_PC}::test_default_role_resolves_to_its_declared_column",
            f"{_PC}::test_an_unknown_role_is_an_error_not_the_census_weight",
            _DECLARED,
        ),
        note_cs=(
            "Nedeklarovaná role se odmítne; náhradní sloupec ani váhy 1 neexistují. Výchozí "
            "role je sama deklarací smlouvy a vazba populace ji zapisuje, není to záloha."
        ),
    ),
    MethodStep(
        id="parse",
        title_cs="Čtení jedné váhy",
        formula_latex=r"w = \text{desetinné číslo},\quad w \in [0, \infty)",
        implements=f"{_P}.weights:parse_weight",
        source_sha256="28a3cbf048b457a9cecc10a1a1d73d7c1dbd175c604dd12f957f87a92118c644",
        evidence=(_M01,),
        tests=(f"{_PC}::test_parse_weight_refuses_anything_else",),
        note_cs=("Jen prosté desetinné číslo: „nan“, „inf“, podtržítka ani mezery nejsou váha."),
    ),
    MethodStep(
        id="column",
        title_cs="Sloupec vah pro analýzu",
        formula_latex=(
            r"\exists i:\ w_i \text{ chybí nebo je neplatná} \;\lor\; \textstyle\sum_i w_i \le 0"
            r"\;\Rightarrow\; \text{odmítnuto}"
        ),
        implements=f"{_P}.weights:analysis_weights",
        source_sha256="bd255e3b9db802617439d546d79f7ae92c257534d889534a1b8f85c94e25ed6a",
        evidence=(_M01,),
        tests=(f"{_PC}::test_analysis_weights_refuse_an_unusable_column", _D1_CLEAN),
        note_cs=(
            "Odmítne se celý sloupec a chyba spočítá každou vadu. Reference prázdnou nebo "
            "zápornou váhu nulovala (fillna(0).clip(0)) a respondenta tím tiše vyřadila."
        ),
    ),
    # --------------------------------------------------------------------- totals
    MethodStep(
        id="total",
        title_cs="Kontrola součtu vah při importu",
        formula_latex=r"\left|\textstyle\sum_i w_i - T\right| \le \tau",
        implements=f"{_P}.validation:validate_import",
        source_sha256="d56289c2f42d88c58362e3d70f06b13f04397fb1451aa691cbe673781a971ae0",
        symbols=(
            Symbol("T", "očekávaný součet (velikost populace)", "osob"),
            Symbol(r"\tau", "tolerance", "osob"),
        ),
        parameters=tuple(
            ParameterRef(f"schemes.{r}.{leaf}", f"{label}: {_ROLE_CS[r]}", "osob")
            for r in _ROLES
            for leaf, label in (("expected_total", "Očekávaný součet"), ("tolerance", "Tolerance"))
        ),
        evidence=(_CONTRACT,),
        tests=(f"{_PC}::test_a_weight_total_outside_tolerance_fails", _DECLARED),
        note_cs=(
            "Kontroluje se jen tam, kde reference součet deklarovala; u ostatních schémat se "
            "žádný nevymýšlí."
        ),
    ),
    # ------------------------------------------------------------------ cleaning
    MethodStep(
        id="cleaning",
        title_cs="Čištění vah v agregaci",
        formula_latex=r"w_k \notin (0, \infty) \Rightarrow w_k := \operatorname{medián}(w)",
        implements=f"{_A}:clean_weights",
        source_sha256="56ef8a81b1df7a44b096d90e1646e52558c4ef132cfccbb6060f27f87f5889ee",
        parameters=(ParameterRef("aggregate_cleaning", "Čištění neplatné váhy"),),
        evidence=(_UNC, _M16),
        tests=(_D1_CLEAN,),
        note_cs=(
            "Tři pravidla pro tutéž váhu (nález D1): agregace ji nahradí mediánem platných "
            "(median, přenos 18.6.6), brána důkazů i načítání populace ji odmítnou. Volba je "
            "deklarovaná; běh ji začne číst ve W1b a refuse pak agregaci s neplatnou vahou "
            "odmítne."
        ),
    ),
    # ---------------------------------------------------------------------- Kish
    MethodStep(
        id="kish_aggregate",
        title_cs="Kishovo n v agregaci",
        formula_latex=(
            r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2},"
            r"\quad w_k > 0"
        ),
        implements=f"{_A}:kish_effective_n",
        source_sha256="c5e86670bfde71a59b9b4652115f646573f0e6b611407a223b6506b40f5a4565",
        evidence=(_UNC,),
        tests=(_D1_KISH,),
        note_cs=(
            "Čte váhy už vyčištěné; nekladnou nebo neplatnou váhu vynechá. Vzorec lze upravit "
            "v modulu Agregace (agg.kish)."
        ),
    ),
    MethodStep(
        id="kish_gate",
        title_cs="Kishovo n v bráně důkazů",
        formula_latex=r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2}",
        implements=f"{_D}.evidence.support:kish_effective_n",
        source_sha256="dd0bd83ed33fce776c48ee8111788ff6418084214626c468c7f8dda0e5d5f08c",
        evidence=(_M16,),
        tests=(_D1_KISH,),
        note_cs="Zápornou nebo neplatnou váhu odmítne; nulová nic nepřidá.",
    ),
    MethodStep(
        id="kish_sociomap",
        title_cs="Kishovo n páru v Sociomapě",
        formula_latex=r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2}",
        implements=f"{_D}.sociomap.relations:kish_effective_n",
        source_sha256="2d4204cd233819cef21a50c5e473912eb93f6e719c0fc87302c88572bcfa2d20",
        evidence=(_Q6,),
        tests=(_D1_KISH,),
        note_cs=(
            "Odmítne i nulovou váhu. Na kladných konečných vahách dávají všechna tři místa "
            "totéž číslo, na jakýchkoli jiných se liší (nález D1)."
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("M", "Vážení", ("method",)),
    StepGroup("S", "Schéma vah", ("scheme", "parse", "column")),
    StepGroup("T", "Součty populace", ("total",)),
    StepGroup("C", "Neplatná váha", ("cleaning",)),
    StepGroup(
        "K",
        "Kishovo efektivní n na třech místech",
        (
            "kish_aggregate",
            "kish_gate",
            "kish_sociomap",
        ),
    ),
)

WEIGHTING: Final = MethodModule(
    id="weighting",
    title_cs="Vážení: která váha patří respondentovi a co s neplatnou",
    steps=_STEPS,
    presets=(Preset("aia-weighting-1", AIA_WEIGHTING_V1, _validate),),
    in_force="aia-weighting-1",
    groups=_GROUPS,
    note_cs=(
        "AIA váhy nepočítá: každé schéma je sloupec panelu, který určí importní smlouva. "
        "Kalibrace, raking ani GREG v AIA nejsou. Verze aia-weighting-1 je deklarace "
        "smlouvy přesně: čtyři schémata, výchozí role a dva očekávané součty s tolerancí. "
        "Čištění neplatné váhy v agregaci je volba; dnes medián jako v 18.6.6. Běh si "
        "vážení zapamatuje od W1b, upravit ho půjde od W1c."
    ),
)
