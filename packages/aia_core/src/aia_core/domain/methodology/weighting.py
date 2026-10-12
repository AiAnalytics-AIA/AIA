"""Weighting, step by step: which weight each respondent carries, and how it got there.

ADR 0023; plan ``methodology-tab.md`` W1a, W1b. A population's weights are columns of the
panel, one per declared scheme, and the import contract names them. A run's respondent does
not carry that column's value: the sampler (``population/sampling.py``, the port of 18.6.6's
``draw_representative``) floors it, draws the sample by quotas and rakes the sample back to
the audience's own weighted shares, and that raked weight is the respondent's
(``panel_persona.py``). The fieldwork dataset then refuses any weight that is not a positive
finite number, so what the aggregate receives is already valid.

Declared in ``WeightingSpec``, whose preset ``aia-weighting-1`` is built from the Czech import
contract (``population/czech.py``) and is therefore its declaration exactly:

* four schemes, each a role bound to one column;
* the default role a binding records when none is chosen;
* the expected total and tolerance an import is checked against, for the two schemes whose
  total the reference declared (none is invented for the other two).

The sampler's values (the floor, raking's iterations, floor, cap and convergence, the audit's
tolerances) are the unit's constants, shown as constants: nothing reads them as a choice, and
a value shown as editable that a run never reads would be a lie. They become a run's choice
when the panel source reaches fieldwork (plan ``panel-grounded-respondents`` chunk 5) and the
weighting is editable (W1c). Until then no run carries a panel weight: AI respondents weigh 1.

The aggregate's ``clean_weights`` (18.6.6's median for an invalid weight) is shown as what it
is: the unit's port, kept for parity, which a run's dataset never lets fire (W1b removed the
inert median/refuse switch W1a declared for it).

Finding D1 is named on its steps: cleaning rules that impute or refuse the same weight, and
Kish's n computed in four places, equal on positive finite weights and different on any other
(``test_methodology_weighting.py``).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..population.czech import CZ_SYNTHETIC_V17
from ..population.weights import WeightingSpec, weighting_spec
from .catalogue import (
    ConstantRef,
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
_PS: Final = f"{_T}/test_population_sampling.py"
_PP: Final = f"{_T}/test_panel_persona.py"
_S: Final = f"{_P}.sampling"

#: The Czech contract's weighting, exactly (plan W1a).
AIA_WEIGHTING_V1: Final = weighting_spec(CZ_SYNTHETIC_V17, methodology_version="aia-weighting-1")

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
_SAMPLER: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "representative_sampling.py (draw_representative, _rake, _audit); pipeline.py:278",
    "Převzato z 18.6.6: cíle, kvóty, raking a audit EXACT při stejném výběru řádků, "
    "losování vlastností (plán panel-grounded-respondents § 2e).",
)
_DATASET: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "fieldwork.py FieldworkRespondent (plán methodology-tab W1b)",
    "Datová sada běhu odmítne váhu, která není kladné konečné číslo; agregace tak dostane "
    "jen platné váhy a pravidlo mediánu na běhu nikdy nenastane.",
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
_DATASET_TEST: Final = (
    f"{_TW}::test_a_runs_dataset_refuses_every_weight_that_is_not_positive_and_finite"
)
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
        source_sha256="05e603e0a56e37161e45c9befff606f96861437657564e8d8918293b23bee608",
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
    # -------------------------------------------------------------------- sample
    MethodStep(
        id="sample_base",
        title_cs="Základní váha ve výběru",
        formula_latex=(
            r"w^{0}_i = \max\!\left(w_i,\ 10^{-12}\right),\quad "
            r"\textstyle\sum_{i \in A} w_i = 0 \;\Rightarrow\; \text{odmítnuto}"
        ),
        implements=f"{_S}:draw_panel_sample",
        source_sha256="ef9cbd3be56f9929a65bde5b0be214d42e5133bfd75bb6dc6d52e10ed363bc20",
        symbols=(
            Symbol("A", "publikum běhu: řádky panelu po filtru"),
            Symbol("w_i", "váha řádku ze sloupce schématu (analytická váha populace)"),
        ),
        constants=(ConstantRef(f"{_S}:_WEIGHT_FLOOR", "Dolní mez základní váhy"),),
        evidence=(_SAMPLER,),
        tests=(
            f"{_PS}::test_a_zero_weight_row_keeps_the_units_floor_when_it_is_drawn",
            f"{_PS}::test_a_sample_that_cannot_be_drawn_as_asked_is_refused_by_name",
        ),
        note_cs=(
            "Řádek s nulovou vahou se vylosuje jen tehdy, když ho jeho buňka potřebuje. "
            "Publikum, jehož váhy jsou všechny nulové, se odmítne (18.6.6 mu dalo váhy 1)."
        ),
    ),
    MethodStep(
        id="sample_targets",
        title_cs="Cíle: vážené podíly publika",
        formula_latex=(
            r"t_{f,c} = \frac{\sum_{i \in A,\ x_{if} = c} w^{0}_i}{\sum_{i \in A} w^{0}_i}"
        ),
        implements=f"{_S}:targets",
        source_sha256="c7466c00f095703c196356b9da56a538091e0dcf2026502ca7b4900331e82dd0",
        symbols=(
            Symbol("f", "kvótní pole (pohlaví, věková skupina, kraj, vzdělání, zaměstnání)"),
            Symbol("c", "kategorie pole"),
        ),
        evidence=(_SAMPLER,),
        tests=(f"{_PS}::test_targets_and_quota_fields_are_the_units",),
        note_cs="Pole se použije, jen když má v publiku víc než jednu hodnotu.",
    ),
    MethodStep(
        id="rake",
        title_cs="Raking vzorku na cíle",
        formula_latex=(
            r"w_i \leftarrow w_i \cdot \frac{t_{f,c}}{\sum_{j \in c} w_j \,/\, \sum_j w_j}"
            r"\ \ (i \in c),\quad "
            r"w_i \leftarrow \frac{\min\!\left(\max(w_i, \varepsilon),\ "
            r"\max(\kappa\, q_{0{,}99}(w), \varepsilon)\right)}{\bar{w}}"
        ),
        implements=f"{_S}:rake",
        source_sha256="271df8674134cc5ee6ac06a574ff273516249d24ed9fc0d3fad565100987077f",
        symbols=(
            Symbol(r"\varepsilon", "dolní mez váhy při rakingu"),
            Symbol(r"\kappa", "násobek 99. percentilu, horní mez váhy"),
            Symbol(r"q_{0{,}99}(w)", "99. percentil vah (do 20 respondentů maximum)"),
            Symbol(r"\bar{w}", "průměr vah: výsledné váhy mají průměr 1"),
        ),
        constants=(
            ConstantRef(f"{_S}:_RAKE_ITERATIONS", "Nejvýš iterací"),
            ConstantRef(f"{_S}:_RAKE_FLOOR", "Dolní mez váhy (ε)"),
            ConstantRef(f"{_S}:_RAKE_CAP", "Násobek percentilu (κ)"),
            ConstantRef(f"{_S}:_RAKE_CONVERGED", "Konvergence: největší změna váhy"),
        ),
        evidence=(_SAMPLER,),
        tests=(
            f"{_PS}::test_raking_the_units_picks_gives_the_units_weights",
            f"{_PS}::test_raking_where_the_cap_binds_is_the_units",
        ),
        note_cs=(
            "Iterativní proporcionální přizpůsobení (IPF) po polích, v každé iteraci ořez a "
            "normalizace na průměr 1; skončí, když se žádná váha nezmění o víc než mez "
            "konvergence. Toto je jediná kalibrace v AIA; GREG ani jiné odhady vah tu nejsou."
        ),
    ),
    MethodStep(
        id="sample_without_quotas",
        title_cs="Bez kvótního pole: základní váha přes průměr",
        formula_latex=r"w_i = \frac{w^{0}_i}{\overline{w^{0}}}",
        implements=f"{_S}:representative_draw",
        source_sha256="45fcb9c64c6a55b24f3c77cff25abb34b7956ec7501e4630c1c0206098bcfb02",
        evidence=(_SAMPLER,),
        tests=(f"{_PS}::test_with_no_usable_quota_field_the_weight_is_the_base_over_its_mean",),
        note_cs=(
            "Když publikum nemá žádné použitelné kvótní pole, vylosuje se n řádků podle váhy "
            "a raking se nedělá."
        ),
    ),
    MethodStep(
        id="sample_audit",
        title_cs="Audit reprezentativnosti",
        formula_latex=(
            r"\max_{f,c} \left| p^{\mathrm{váž}}_{f,c} - t_{f,c} \right| \le "
            r"\max\!\left(0{,}25,\ \tfrac{100}{n}\right)\ \text{p. b.},\quad "
            r"\max_{f,c} \left| p^{\mathrm{surový}}_{f,c} - t_{f,c} \right| \le "
            r"\max\!\left(0{,}50,\ \tfrac{100}{n}\right)\ \text{p. b.}"
        ),
        implements=f"{_S}:judge",
        source_sha256="862a0c9dd814c8eb4fc7a34c326476272adad3a4de84aa326797c3228a6bed6b",
        symbols=(
            Symbol(r"p_{f,c}", "podíl kategorie ve vzorku, vážený nebo surový", "p. b."),
            Symbol("n", "velikost vzorku"),
        ),
        evidence=(_SAMPLER,),
        tests=(
            f"{_PS}::test_the_verdict_is_the_units",
            f"{_PS}::test_the_tolerances_are_the_units_boundaries",
        ),
        note_cs=(
            "Překročení vážené tolerance vzorek odmítne (sampling_unrepresentative); "
            "překročení surové jen varuje (PASS_WEIGHTED)."
        ),
    ),
    MethodStep(
        id="respondent",
        title_cs="Váha respondenta běhu",
        formula_latex=r"w^{\mathrm{resp}}_i = w_i\ \text{(po rakingu)}",
        implements=f"{_D}.panel_persona:panel_personas",
        source_sha256="137e38c08743b61d500cfc1f00ecaf20de1581e6a941c1bdcb119a6b750c5211",
        evidence=(_SAMPLER,),
        tests=(f"{_PP}::test_every_sampled_row_becomes_a_panel_persona",),
        note_cs=(
            "Respondent postavený z panelu nese váhu vzorku po rakingu. Zdroj panelu ještě "
            "není zapojen do sběru (plán panel-grounded-respondents, část 5); AI "
            "respondenti dnes váží 1 a smyšlení respondenti pracovní plochy svou váhu."
        ),
    ),
    MethodStep(
        id="dataset",
        title_cs="Váha v datové sadě běhu",
        formula_latex=(r"w_i \notin (0, \infty) \;\Rightarrow\; \text{datová sada odmítnuta}"),
        implements=f"{_D}.fieldwork:FieldworkRespondent",
        source_sha256="91578619d19f36fee70b32c46f0622d8816df6adba36a4299bbc1389623b8166",
        evidence=(_DATASET,),
        tests=(_DATASET_TEST,),
        note_cs=(
            "Nula, záporná hodnota, NaN i nekonečno: sběr se odmítne a do agregace nic "
            "nedojde. Nekonečno dříve prošlo a agregace ho nahradila mediánem."
        ),
    ),
    # ------------------------------------------------------------------ cleaning
    MethodStep(
        id="cleaning",
        title_cs="Čištění vah v agregaci (přenos 18.6.6)",
        formula_latex=r"w_k \notin (0, \infty) \Rightarrow w_k := \operatorname{medián}(w)",
        implements=f"{_A}:clean_weights",
        source_sha256="56ef8a81b1df7a44b096d90e1646e52558c4ef132cfccbb6060f27f87f5889ee",
        evidence=(_UNC, _M16, _DATASET),
        tests=(_D1_CLEAN, _DATASET_TEST),
        note_cs=(
            "Přenos 18.6.6 ponechaný kvůli paritě. Na běhu nenastane: datová sada neplatnou "
            "váhu odmítne dřív (krok Váha v datové sadě běhu). Brána důkazů i načítání "
            "populace takovou váhu také odmítají (nález D1); volba mezi mediánem a "
            "odmítnutím proto není potřeba a z deklarace vážení zmizela (W1b)."
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
            "Odmítne i nulovou váhu. Na kladných konečných vahách dávají všechna místa "
            "totéž číslo, na jakýchkoli jiných se liší (nález D1)."
        ),
    ),
    MethodStep(
        id="kish_sample",
        title_cs="Kishovo n vzorku",
        formula_latex=r"n_{\mathrm{Kish}} = \frac{\left(\sum_i w_i\right)^2}{\sum_i w_i^2}",
        implements=f"{_S}:draw_panel_sample",
        source_sha256="ef9cbd3be56f9929a65bde5b0be214d42e5133bfd75bb6dc6d52e10ed363bc20",
        evidence=(_SAMPLER,),
        tests=(f"{_PS}::test_the_verdict_is_the_units",),
        note_cs=(
            "Čtvrté místo, kde se Kishovo n počítá: z vah po rakingu, zapsané do auditu "
            "vzorku (effective_n). Váhy jsou tu kladné z konstrukce (dolní mez rakingu)."
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("M", "Vážení", ("method",)),
    StepGroup("S", "Schéma vah", ("scheme", "parse", "column")),
    StepGroup("T", "Součty populace", ("total",)),
    StepGroup(
        "V",
        "Váha respondenta běhu: vzorek z panelu",
        (
            "sample_base",
            "sample_targets",
            "rake",
            "sample_without_quotas",
            "sample_audit",
            "respondent",
        ),
    ),
    StepGroup("C", "Neplatná váha", ("dataset", "cleaning")),
    StepGroup(
        "K",
        "Kishovo efektivní n na čtyřech místech",
        (
            "kish_aggregate",
            "kish_gate",
            "kish_sociomap",
            "kish_sample",
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
        "Schéma vah je sloupec panelu, který určí importní smlouva. Respondent běhu nese "
        "váhu vzorku: základní váhu s dolní mezí, raking na vážené podíly publika (IPF s "
        "ořezem, průměr 1) a audit reprezentativnosti, vše převzaté z 18.6.6. GREG ani jiná "
        "kalibrace v AIA nejsou. Datová sada běhu odmítne váhu, která není kladné konečné "
        "číslo. Hodnoty výběru jsou konstanty kódu; volbou běhu se stanou, až zdroj panelu "
        "dojde do sběru (W1c). Verze aia-weighting-1 je deklarace smlouvy přesně: čtyři "
        "schémata, výchozí role a dva očekávané součty s tolerancí."
    ),
)
