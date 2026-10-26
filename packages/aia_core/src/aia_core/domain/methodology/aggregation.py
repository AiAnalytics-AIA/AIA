"""Aggregation, step by step: how a question's answers become a number with its interval (G2a).

ADR 0023; plan ``methodology-tab.md`` G2a. ``research_aggregate`` is an EXACT port of 18.6.6's
``dotaznik.agreguj_otazku`` and ``uncertainty.py``. Each cell's estimate, Kish n, donor support
and suppression are identical to the unit's; each interval bound lies within the unit's own
seed-to-seed spread (OI-62: AIA draws with its own generator).

The values the unit wrote inline are declared in ``AggregationSpec``, whose preset
``aia-aggregate-1`` is the unit's literals, bit for bit:

* the bootstrap's replicates (400; 350 per option of a multiple choice);
* its seeds (20260816, + the option's index; 20260818 for the top box);
* its percentile quantiles (0.025, 0.975);
* the top-2-box width.

Its estimators -- the weighted mean, the share, the top box, Kish n and the variance -- are
formula slots (G2b, :mod:`.aggregation_formulas`), each with the expression the aggregate
computes bit for bit.

A run pins the aggregation version in force when it starts, and a retry keeps it (G3a); with
nothing stored that is ``aia-aggregate-1``. It is editable (G3b): any declared value and any
estimator slot, checked first on fixed fictional panels (:mod:`.aggregation_check`). An aggregate
computed under any changed value or replaced formula is no longer the unit's port and says so
(G2c): its ``deviation`` names each change, and Results shows it above the numbers. A version
that only renames computes the unit's numbers and claims nothing.

The findings this module carries are named on their steps:

* **D1.** Weight cleaning imputes the median, where the evidence gate refuses.
* **D5.** The interval is a fixed-weight percentile interval, a method the unit never declared.
* **D7.** Plain Czech keyword lists decide which questions are refused.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..report.numbers import number
from ..research_aggregate import AIA_AGGREGATE_V1, MAX_DECIMALS, AggregationSpec
from .aggregation_formulas import AGGREGATION_FORMULAS
from .catalogue import (
    Bound,
    ConstantRef,
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
    at_least,
    at_most,
)

__all__ = ["AGGREGATION"]

_A: Final = "aia_core.domain.research_aggregate"
_T: Final = "packages/aia_core/tests"

_UNC: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "uncertainty.py (clean_weights, kish_effective_n, weighted_*, bootstrap_weighted_*)",
    "Převzato z 18.6.6 přesně (EXACT).",
)
_AGG: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "dotaznik.py agreguj_otazku",
    "Převzato z 18.6.6 přesně (EXACT); hodnoty, které jednotka psala přímo do kódu, jsou "
    "deklarované v aia-aggregate-1.",
)
_FID: Final = Evidence(EvidenceKind.LEGACY_PORT, "fidelity.py classify_question, evidence_rating")
_CAPTURES: Final = Evidence(
    EvidenceKind.FIXTURE,
    "fixtures/research_aggregate (zachyceno na jednotce 18.6.6)",
    "Odhady, Kishovo n, podpora a potlačení přesně; meze intervalů v rozptylu jednotky "
    "mezi semínky.",
)
_OI62: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    ".planning/open-items.md OI-62",
    "Generátor AIA (random.Random, index klastru floor(u·m)) místo PCG64 NumPy: stejné "
    "vstupy a semínko dávají stejné meze na každém stroji.",
)

_AGG_TESTS: Final = f"{_T}/test_research_aggregate.py"
_EXACT: Final = f"{_AGG_TESTS}::test_estimates_support_and_suppression_are_exact_against_the_unit"
_SPREAD: Final = (
    f"{_T}/test_research_aggregate.py::test_every_bound_lies_within_the_units_own_seed_spread"
)
_SELF: Final = f"{_T}/test_research_aggregate.py::test_aias_own_bounds_are_pinned"
_FORMULAS: Final = (
    f"{_T}/test_methodology_aggregation_formulas.py"
    "::test_every_fixture_aggregates_identically_through_its_built_in_expressions"
)
_ROUNDED: Final = (
    f"{_T}/test_methodology_rounding.py"
    "::test_the_aggregate_stores_its_numbers_at_the_versions_places"
)
_DECLARED: Final = (
    f"{_T}/test_methodology_aggregation.py::test_the_preset_is_the_units_literals_bit_for_bit"
)


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, AggregationSpec):
        raise TypeError(f"not an aggregation specification: {type(spec).__name__}")


_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="method",
        title_cs="Pojmenování agregace",
        formula_latex=r"\text{agregace} = \text{methodology\_version}",
        implements=f"{_A}:AggregationSpec",
        source_sha256="0366231c59589dc23ae7c9f7aaa9f81038147f8ec1a942e32bef7dbf5766cf31",
        parameters=(ParameterRef("methodology_version", "Verze agregace"),),
        evidence=(_AGG,),
        tests=(
            _DECLARED,
            f"{_T}/test_aggregate_deviation.py::test_a_changed_value_is_named_and_the_numbers_follow_it",
        ),
    ),
    # ------------------------------------------------------------------- weights
    MethodStep(
        id="weights",
        title_cs="Čištění vah",
        formula_latex=r"w_k \notin (0, \infty) \Rightarrow w_k := \operatorname{medián}(w)",
        implements=f"{_A}:clean_weights",
        source_sha256="56ef8a81b1df7a44b096d90e1646e52558c4ef132cfccbb6060f27f87f5889ee",
        evidence=(_UNC,),
        tests=(_EXACT,),
        note_cs=(
            "Neplatnou váhu nahradí medián platných (bez platných: všechny 1). Brána AIA "
            "a populační váhy takové váhy odmítají místo čištění (nález D1). Na běhu "
            "nenastane: datová sada běhu neplatnou váhu odmítne dřív (modul Vážení)."
        ),
    ),
    MethodStep(
        id="kish",
        title_cs="Kishovo efektivní n",
        formula_latex=r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2}",
        implements=f"{_A}:kish_effective_n",
        source_sha256="c5e86670bfde71a59b9b4652115f646573f0e6b611407a223b6506b40f5a4565",
        evidence=(_UNC,),
        tests=(
            _FORMULAS,
            f"{_T}/test_research_aggregate.py::test_kish_and_donor_support_follow_the_units_thresholds",
        ),
        note_cs="Podporu buňky z něj počítá modul Podpora a potlačení.",
    ),
    # ----------------------------------------------------------------- estimates
    MethodStep(
        id="share",
        title_cs="Podíl odpovědi (výběr jedné možnosti)",
        formula_latex=(
            r"p_c = 100\,\frac{\sum_k w_k\,[x_k = c]}{\sum_k w_k}"
            r"\quad\text{(na 1 desetinné místo)}"
        ),
        implements=f"{_A}:bootstrap_weighted_distribution",
        source_sha256="ccbf0a5f0ad9a737ed5ae6e741a9ddee5cbe183015a658f7a22abdb276f4e25a",
        symbols=(Symbol("p_c", "podíl možnosti c", "%"),),
        evidence=(_UNC, _CAPTURES),
        tests=(
            _FORMULAS,
            _EXACT,
        ),
        note_cs="Odhad i meze se zaokrouhlí na jedno desetinné místo.",
    ),
    MethodStep(
        id="mean",
        title_cs="Průměr škály",
        formula_latex=(
            r"\bar{x} = \frac{\sum_k w_k x_k}{\sum_k w_k}\quad\text{(na 2 desetinná místa)}"
        ),
        implements=f"{_A}:bootstrap_weighted_mean",
        note_cs=(
            "Stejný vážený průměr počítá i podíl top boxu a podíl každé možnosti u výběru více "
            "možností (průměr ukazatelů 0/1) a každou replikaci bootstrapu. Úprava vzorce "
            "průměru proto mění i je."
        ),
        source_sha256="91e8c6f4c2d0216e310f68038d5be443312ee9d324f55dc469f87e9dac00726d",
        evidence=(_UNC, _CAPTURES),
        tests=(
            _FORMULAS,
            _EXACT,
        ),
    ),
    MethodStep(
        id="median",
        title_cs="Medián škály",
        formula_latex=(
            r"F_j = \frac{\sum_{i \le j} w_{(i)}}{\sum_i w_i},\quad "
            r"\tilde{x} = \operatorname{interp}\!\left(0{,}5;\ F;\ x_{(\cdot)}\right)"
        ),
        implements=f"{_A}:weighted_quantile",
        source_sha256="2c10357e72def048928949d3a726a20cd4c3a46fefaab70b853dc35e34ace9a3",
        symbols=(Symbol("F_j", "kumulativní podíl vah seřazených odpovědí"),),
        evidence=(_UNC,),
        tests=(
            f"{_T}/test_research_aggregate.py::test_the_weighted_median_interpolates_like_numpy",
        ),
        note_cs="Lineární interpolace jako np.interp; mimo rozsah se drží krajní hodnoty.",
    ),
    MethodStep(
        id="sd",
        title_cs="Směrodatná odchylka škály",
        formula_latex=(
            r"s = \sqrt{\frac{\sum_k w_k (x_k - \bar{x})^2}{\sum_k w_k}}"
            r"\quad\text{(ddof 0, na 2 desetinná místa)}"
        ),
        implements=f"{_A}:weighted_variance",
        source_sha256="3d8e38e6261391bd78ef35b58ef5407f44a66a26c38f900801586dc80d4838c2",
        evidence=(_UNC, _CAPTURES),
        tests=(
            _FORMULAS,
            _EXACT,
        ),
        note_cs="Vážená populační odchylka; pod dvěma platnými odpověďmi se nepočítá.",
    ),
    MethodStep(
        id="top_box",
        title_cs="Top box škály",
        formula_latex=(r"T = 100\,\frac{\sum_k w_k\,[x_k \ge \max - (b - 1)]}{\sum_k w_k}"),
        implements=f"{_A}:aggregate_question",
        source_sha256="d028b86b424ef08f51a1ab7adb400bb2f6b828a39fc4a0d84ca35044a6f448c9",
        symbols=(Symbol("b", "šířka top boxu", "bodů škály"),),
        parameters=(
            ParameterRef("top_box", "Šířka top boxu", "bodů škály"),
            ParameterRef("bootstrap.seed_top_box", "Semínko bootstrapu top boxu"),
        ),
        evidence=(_AGG, _CAPTURES),
        tests=(_FORMULAS, _EXACT, _DECLARED),
        note_cs="Interval top boxu má vlastní semínko, ostatní nastavení bootstrapu sdílí.",
    ),
    MethodStep(
        id="multi",
        title_cs="Podíl možnosti (výběr více možností)",
        formula_latex=(
            r"p_i = 100\,\frac{\sum_k w_k\,[i \in x_k]}{\sum_k w_k},\quad "
            r"\text{semínko}_i = \text{semínko} + i"
        ),
        implements=f"{_A}:aggregate_question",
        source_sha256="d028b86b424ef08f51a1ab7adb400bb2f6b828a39fc4a0d84ca35044a6f448c9",
        parameters=(ParameterRef("bootstrap.reps_multi", "Replikace bootstrapu na možnost"),),
        evidence=(_AGG, _CAPTURES),
        tests=(_EXACT, _DECLARED),
        note_cs=(
            "Součet podílů přesahuje 100 %. Každá možnost má vlastní bootstrap: semínko "
            "základního bootstrapu plus pořadí možnosti."
        ),
    ),
    # ----------------------------------------------------------------- bootstrap
    MethodStep(
        id="resample",
        title_cs="Převzorkování dárců",
        formula_latex=(
            r"m^{(r)}_d = \#\{\,j \le M : \lfloor u^{(r)}_j M \rfloor = d\,\},\quad "
            r"w^{(r)}_k = m^{(r)}_{d_k} w_k,\quad r = 1 \dots R"
        ),
        implements=f"{_A}:_multipliers",
        source_sha256="33dc067b0b09ab9cacfabf79e80f1c1d56badaec811bc1fafeac15b6f719fa2f",
        symbols=(
            Symbol("M", "počet různých dárců (klastrů) v buňce"),
            Symbol("R", "počet replikací"),
            Symbol(r"u^{(r)}_j", "rovnoměrné číslo z generátoru se semínkem"),
        ),
        parameters=(
            ParameterRef("bootstrap.reps", "Replikace bootstrapu"),
            ParameterRef("bootstrap.seed", "Semínko bootstrapu"),
        ),
        evidence=(_UNC, _OI62),
        tests=(_SPREAD, _SELF),
        note_cs=(
            "Převzorkují se klastry dárců, ne řádky. Při jediném dárci se interval nepočítá "
            "a meze se rovnají odhadu (replikací 0)."
        ),
    ),
    MethodStep(
        id="interval",
        title_cs="Interval z kvantilů replikací",
        formula_latex=(
            r"[\,Q_{q_1}(\hat\theta^{(1..R)}),\ Q_{q_2}(\hat\theta^{(1..R)})\,]"
            r"\quad\text{(lineární kvantil, jako np.quantile)}"
        ),
        implements=f"{_A}:_quantile",
        source_sha256="947a26dd2691f27ea728bf3079aa32d0c768b5a255b1c1cd7d39eba1447746a2",
        symbols=(Symbol(r"\hat\theta^{(r)}", "odhad v replikaci r"),),
        parameters=(ParameterRef("bootstrap.quantiles", "Kvantily intervalu"),),
        evidence=(_UNC,),
        tests=(_SPREAD, _SELF, _DECLARED),
        note_cs=(
            "Percentilový interval s pevnými vahami respondentů: převzorkuje se jen výběr "
            "dárců, váhy se znovu nekalibrují. Jednotka tuto metodu nikde nedeklarovala "
            "(nález D5); 0,025 a 0,975 dávají 95% interval."
        ),
    ),
    # ------------------------------------------------------------------ fidelity
    MethodStep(
        id="classify",
        title_cs="Typ otázky podle textu",
        formula_latex=(
            r"\text{absolutní hodnota} \succ \text{otevřená} \succ \text{relativní srovnání} "
            r"\succ \text{škála} \succ \text{rozdělení}"
        ),
        implements=f"{_A}:classify_question",
        source_sha256="27a2c1fce0ce919467230fa1dfa8c71a1157a0bf905e62c07f5de42e50cb149f",
        constants=(
            ConstantRef(f"{_A}:_ABSOLUTE_PATTERNS", "Vzory absolutní hodnoty (regex)"),
            ConstantRef(f"{_A}:_RELATIVE_PATTERNS", "Vzory relativního srovnání (regex)"),
        ),
        evidence=(_FID,),
        tests=(
            f"{_T}/test_methodology_aggregation.py::test_the_keyword_lists_decide_what_is_refused",
        ),
        note_cs=(
            "O typu rozhodnou prosté české seznamy klíčových slov v textu otázky (nález D7): "
            "otázku na absolutní cenu nebo velikost trhu, napsanou jinými slovy, nepoznají."
        ),
    ),
    MethodStep(
        id="fidelity",
        title_cs="Hodnocení věrohodnosti",
        formula_latex=(
            r"\text{absolutní} \Rightarrow \text{RED, REFUSE};\ "
            r"\text{validováno} \Rightarrow \text{GREEN};\ \text{jinak AMBER}"
        ),
        implements=f"{_A}:evidence_rating",
        source_sha256="4a0f0d8a177bc045c96b874a168430e2039c910841b6e891532c9e072127dfdf",
        evidence=(_FID,),
        tests=(
            f"{_T}/test_methodology_aggregation.py::test_the_keyword_lists_decide_what_is_refused",
        ),
        note_cs=(
            "Relativní srovnání se doporučuje (RECOMMEND), ostatní se jen ukáže (JUST_SHOW). "
            "AIA nemá validovaný holdout, takže bez validace je hodnocení vždy AMBER."
        ),
    ),
)

_ROUNDING_KEEPS: Final = (
    "celé číslo od 0 do 3",
    "meze intervalu na stejný počet míst jako odhad",
    "analýza a zpráva převezmou uložené číslo, znovu nezaokrouhlují",
    "jiný počet míst než 18.6.6 se u běhu uvede jako odchylka",
)

_ROUNDING_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="round_share",
        title_cs="Podíly v procentech",
        formula_latex=r"p^{*} = \operatorname{round}(p,\ d_p)",
        implements=f"{_A}:aggregate_question",
        source_sha256="d028b86b424ef08f51a1ab7adb400bb2f6b828a39fc4a0d84ca35044a6f448c9",
        symbols=(Symbol("d_p", "počet desetinných míst podílu", "míst"),),
        parameters=(
            ParameterRef(
                "rounding.share_decimals",
                "Desetinná místa podílů",
                "místa",
                ParameterEffect.CHANGES_STORED,
            ),
        ),
        evidence=(_AGG,),
        tests=(_EXACT, _ROUNDED),
        role_cs=(
            "Na kolik desetinných míst se uloží podíl odpovědi a podíl top boxu. Uloží se "
            "s výsledkem běhu; analýza a zpráva číslo převezmou a znovu ho nezaokrouhlují."
        ),
        source_cs="podíly odpovědí (jedna i více odpovědí), podíl top boxu, meze intervalu",
        effect_cs="Výsledky: tabulky a grafy otázek · Analýza: čísla, která smí převzít · Zpráva",
        note_cs="Na nejbližší hodnotu. Meze intervalu na stejný počet míst jako odhad.",
        reading_cs="desetinná místa podílu = {rounding.share_decimals}",
        keeps_cs=_ROUNDING_KEEPS,
    ),
    MethodStep(
        id="round_mean",
        title_cs="Průměry a směrodatná odchylka",
        formula_latex=r"\bar{x}^{*} = \operatorname{round}(\bar{x},\ d_m),\quad "
        r"s^{*} = \operatorname{round}(s,\ d_m)",
        implements=f"{_A}:aggregate_question",
        source_sha256="d028b86b424ef08f51a1ab7adb400bb2f6b828a39fc4a0d84ca35044a6f448c9",
        symbols=(Symbol("d_m", "počet desetinných míst průměru a SD", "míst"),),
        parameters=(
            ParameterRef(
                "rounding.mean_decimals",
                "Desetinná místa průměrů a SD",
                "místa",
                ParameterEffect.CHANGES_STORED,
            ),
        ),
        evidence=(_AGG,),
        tests=(_EXACT, _ROUNDED),
        role_cs=(
            "Na kolik desetinných míst se uloží průměr škálové otázky, meze jeho intervalu "
            "a směrodatná odchylka."
        ),
        source_cs="průměr škály, meze jeho 95% intervalu, směrodatná odchylka",
        effect_cs="Výsledky: řádek škálové otázky · Analýza: čísla, která smí převzít · Zpráva",
        note_cs="Medián se nezaokrouhluje: je to vždy bod škály.",
        reading_cs="desetinná místa průměru a SD = {rounding.mean_decimals}",
        keeps_cs=_ROUNDING_KEEPS,
    ),
)

#: Fictional numbers the preview rounds: each as the aggregate computes it, unrounded.
_SHARES: Final = (
    ("Ranní nápoj: Kávu", 38.461538, 34.082117, 42.937746),
    ("Ranní nápoj: Čaj", 27.272727, 23.041208, 31.763891),
)
_MEANS: Final = (("Spokojenost (škála 1\u201310)", 7.432187, 7.209143, 7.651227, 1.817669),)


def _preview(spec: BaseModel) -> tuple[PreviewLine, ...]:
    """How Results and the report write fictional numbers under ``spec``: rounded by the
    aggregate's ``round`` at the draft's places, written as the report writes them."""
    if not isinstance(spec, AggregationSpec):
        raise TypeError(f"not an aggregation specification: {type(spec).__name__}")
    d_p, d_m = spec.rounding.share_decimals, spec.rounding.mean_decimals

    def at(value: float, d: int) -> str:
        return number(round(value, d), d)

    lines = [
        PreviewLine(
            "round_share",
            "",
            f"{label}: {at(p, d_p)} % ({at(lo, d_p)}\u2013{at(hi, d_p)} %)",
        )
        for label, p, lo, hi in _SHARES
    ]
    lines += [
        PreviewLine(
            "round_mean",
            "",
            f"{label}: průměr {at(m, d_m)} ({at(lo, d_m)}\u2013{at(hi, d_m)}), SD {at(sd, d_m)}",
        )
        for label, m, lo, hi, sd in _MEANS
    ]
    return tuple(lines)


_GROUPS: Final = (
    StepGroup("M", "Agregace", ("method",)),
    StepGroup("V", "Váhy", ("weights", "kish")),
    StepGroup("O", "Odhady", ("share", "mean", "median", "sd", "top_box", "multi")),
    StepGroup("B", "Interval: bootstrap dárců", ("resample", "interval")),
    StepGroup("F", "Věrohodnost otázky", ("classify", "fidelity")),
    StepGroup("Z", "Zobrazení čísel", ("round_share", "round_mean")),
)

_A_SPEC: Final = f"{_A}:AggregationSpec"
_A_BOOTSTRAP: Final = f"{_A}:BootstrapSpec"
_A_ROUNDING: Final = f"{_A}:RoundingSpec"
#: The range each check holds a field to (F13); the quantiles are a pair, held as one.
_BOUNDS: Final = (
    Bound("top_box", (at_least(1),), _A_SPEC),
    Bound("bootstrap.reps", (at_least(1),), _A_BOOTSTRAP),
    Bound("bootstrap.reps_multi", (at_least(1),), _A_BOOTSTRAP),
    Bound("bootstrap.seed", (at_least(0),), _A_BOOTSTRAP),
    Bound("bootstrap.seed_top_box", (at_least(0),), _A_BOOTSTRAP),
    Bound("rounding.share_decimals", (at_least(0), at_most(MAX_DECIMALS)), _A_ROUNDING),
    Bound("rounding.mean_decimals", (at_least(0), at_most(MAX_DECIMALS)), _A_ROUNDING),
)

AGGREGATION: Final = MethodModule(
    id="aggregation",
    title_cs="Agregace: z odpovědí odhad s intervalem",
    steps=_STEPS + _ROUNDING_STEPS,
    presets=(Preset("aia-aggregate-1", AIA_AGGREGATE_V1, _validate),),
    in_force="aia-aggregate-1",
    groups=_GROUPS,
    formulas=AGGREGATION_FORMULAS,
    editable=True,
    bounds=_BOUNDS,
    preview=_preview,
    preview_title_cs="Jak to uvidí výzkumník ve Výsledcích a ve zprávě",
    note_cs=(
        "Přesný přenos agregace 18.6.6: odhady, Kishovo n, podpora a potlačení jsou shodné "
        "s jednotkou, meze intervalů leží v jejím rozptylu mezi semínky (generátor AIA, "
        "OI-62). Hodnoty, které jednotka psala přímo do kódu (replikace, semínka, kvantily "
        "intervalu, šířka top boxu), jsou deklarované ve verzi aia-aggregate-1. Běh si "
        "při spuštění zapamatuje verzi agregace v platnosti. Metodik může upravit hodnoty "
        "i vzorce; kontrola návrhu je nejdřív ukáže na fiktivních panelech. "
        "Agregace se změněnou hodnotou nebo nahrazeným vzorcem už není přenosem 18.6.6 "
        "a říká to: Výsledky nad čísly ukážou Odchylku od 18.6.6 i s tím, co se změnilo."
    ),
)
