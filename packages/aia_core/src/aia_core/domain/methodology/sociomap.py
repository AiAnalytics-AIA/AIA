"""The Sociomap's object map (contract 3), step by step, in the audit's order F1-F16.

ADR 0023; plan ``methodology-tab.md`` S1. The audit *NPC Sociomapa: faulty formulas in the
code* (A. Bahbouh, 2026-10-06) is the canonical methodology (the owner's rule of
2026-10-07). This catalogue shows how AIA computes each of its sixteen points today, under
``aia-sociomap-3`` (the preset every new run pins beside the reference map) and its
predecessor ``aia-sociomap-2``. A point the code does not compute yet (F5 for this map,
F10's placement, F14, F15, F16) is shown with the audit's proposed formula and says so.

Every formula is written from the function it names; each function is pinned by the SHA256
of its source (``test_methodology.py`` fails with the new hash when one changes, until the
step is re-read). Values are read from the presets and constants, never copied.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..sociomap.specification import (
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    SociomapSpec,
    SociomapSpecV3,
    require_supported,
)
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
from .sociomap_formulas import SOCIOMAP_FORMULAS

__all__ = ["SOCIOMAP"]

_S: Final = "aia_core.domain.sociomap"
_T: Final = "packages/aia_core/tests"


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, SociomapSpec | SociomapSpecV3):
        raise TypeError(f"not a Sociomap specification: {type(spec).__name__}")
    require_supported(spec)


def _rule(rule_id: str) -> Evidence:
    return Evidence(EvidenceKind.REGISTER_RULE, rule_id)


_Q6: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "sociomap-formula-corrections.md § 4a, Q6 (2026-10-09)",
    "Dvě brány, nikdy jedna: dostatečnost důkazu (stav páru) a praktická velikost (práh "
    "účinku), obě deklarované a zaznamenané u každého páru.",
)
_Q7: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "sociomap-formula-corrections.md § 4a, Q7 (2026-10-09)",
    "Výška objektu je jeho vážený průměr hodnocení na deklarované škále 0-1.",
)

_STEPS: Final[tuple[MethodStep, ...]] = (
    # ------------------------------------------------------------------ the method
    MethodStep(
        id="method",
        title_cs="Pojmenování metody",
        formula_latex=r"\text{metoda} = \text{methodology\_version}",
        implements=f"{_S}.specification:SociomapSpecV3",
        source_sha256="a6306dbbc93aa77f0908bd5321d83d90083487d6943d90282b40fe83c62896ee",
        parameters=(ParameterRef("methodology_version", "Verze metodiky"),),
        evidence=(
            Evidence(
                EvidenceKind.AIA_DECISION,
                "docs/architecture/sociomapa-methodology-decision.md",
                "Každá mapa nese jméno a otisk metodiky, podle které byla spočtena.",
            ),
        ),
        tests=(f"{_T}/test_sociomap_object_map.py::test_the_presets_fingerprints",),
        note_cs="Běh si metodiku připne při spuštění; změna metodiky mění jméno i otisk.",
    ),
    # ------------------------------------------------------------------ F1
    MethodStep(
        id="f1_declared_scale",
        title_cs="Hodnocení na společné škále 0-1",
        formula_latex=(
            r"\tilde a_{kc} = \frac{a_{kc} - s^{\min}_c}{s^{\max}_c - s^{\min}_c} \in [0, 1],"
            r"\qquad a_{kc} \notin [s^{\min}_c, s^{\max}_c] \Rightarrow \text{odmítnuto}"
        ),
        implements=f"{_S}.engine_v2:_scaled",
        source_sha256="87ba2885568f944ceb4c7e2e4db4ebdf8e87a6d0289b2954ee32c300a85274d4",
        symbols=(
            Symbol(r"a_{kc}", "hodnocení respondenta k u položky c", "body škály"),
            Symbol(r"s^{\min}_c, s^{\max}_c", "deklarované konce škály položky c", "body škály"),
            Symbol(r"\tilde a_{kc}", "totéž hodnocení na společné škále 0-1"),
        ),
        parameters=(ParameterRef("ratings.scale_normalization", "Převod na škálu 0-1"),),
        evidence=(_rule("AUDIT-F1"),),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_items_with_different_ends_compare_on_their_own_scales",
            f"{_T}/test_sociomap_object_map.py::test_a_rating_off_its_declared_scale_is_refused",
        ),
        note_cs=(
            "Hodnocením je jen položka, kterou dotazník deklaruje jako škálu; nic se neodhaduje "
            "z hodnot sloupce."
        ),
    ),
    # ------------------------------------------------------------------ F2
    MethodStep(
        id="f2_person_minmax",
        title_cs="Každý respondent na své vlastní škále",
        formula_latex=(
            r"\tilde a_{ki} = \frac{a_{ki} - \min_l a_{kl}}{\max_l a_{kl} - \min_l a_{kl}},"
            r"\qquad l \in \text{všechny položky, které } k \text{ hodnotil}"
        ),
        implements=f"{_S}.relations:person_minmax",
        source_sha256="986d2b7017c7ac1b5647edab1e9fad0b2b5da295a322cac50d6ae9e26e0496be",
        symbols=(
            Symbol(r"a_{ki}", "hodnocení respondenta k u objektu i (po F1)"),
            Symbol(r"\tilde a_{ki}", "totéž na vlastní škále respondenta: nejnižší 0, nejvyšší 1"),
        ),
        parameters=(ParameterRef("ratings.person_normalization", "Normalizace na osobu"),),
        evidence=(_rule("AUDIT-F2"),),
        tests=(
            f"{_T}/test_sociomap_person_minmax.py::test_each_rating_is_placed_between_the_persons_own_lowest_and_highest",
            f"{_T}/test_sociomap_person_minmax.py::test_a_persons_scale_spans_every_item_they_rated_not_only_the_family_mapped",
            f"{_T}/test_sociomap_object_map.py::test_the_rating_habit_is_removed_through_the_engine",
        ),
        note_cs="Štědrý a přísný hodnotitel, kteří mají rádi totéž, pak vypadají stejně.",
    ),
    # ------------------------------------------------------------------ F3
    MethodStep(
        id="f3_correlation",
        title_cs="Vážená Pearsonova korelace dvou objektů",
        formula_latex=(
            r"\bar a = \frac{\sum_k w_k \tilde a_{ki}}{\sum_k w_k},\quad "
            r"\operatorname{cov} = \frac{\sum_k w_k (\tilde a_{ki}-\bar a)(\tilde a_{kj}-\bar b)}"
            r"{\sum_k w_k},\quad "
            r"r_{ij} = \operatorname{clip}_{[-1,1]}"
            r"\frac{\operatorname{cov}}{\max\left(\sqrt{v_i v_j},\,10^{-12}\right)}"
        ),
        implements=f"{_S}.pairs:derive_pair_relations",
        source_sha256="65c960383625ff990b9bfc07bc45713a3f1620ab6c6d9f90503485e3a13c2d80",
        symbols=(
            Symbol(r"k", "respondenti, kteří hodnotili oba objekty a mají kladnou váhu"),
            Symbol(r"w_k", "váha respondenta (normalizovaná na součet N)"),
            Symbol(r"v_i, v_j", "vážené rozptyly obou sloupců"),
            Symbol(r"r_{ij}", "korelace objektů i a j; konstantní sloupec korelaci nemá"),
        ),
        parameters=(ParameterRef("relation.estimator", "Odhad vztahu"),),
        evidence=(_rule("AUDIT-F2"), _rule("AUDIT-F3")),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_every_number_is_the_landed_functions_on_the_same_input",
        ),
    ),
    MethodStep(
        id="f3_effective_n",
        title_cs="Velikost vzorku páru",
        formula_latex=(
            r"n_{ij} = \begin{cases} \#\{k\} & \text{počet respondentů} \\"
            r" \dfrac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2} & \text{Kishovo efektivní } n"
            r"\end{cases}"
        ),
        implements=f"{_S}.relations:kish_effective_n",
        source_sha256="2d4204cd233819cef21a50c5e473912eb93f6e719c0fc87302c88572bcfa2d20",
        symbols=(Symbol(r"n_{ij}", "vzorek, ze kterého páru čte interval a stav"),),
        parameters=(ParameterRef("relation.basis", "Základ n"),),
        evidence=(_rule("AUDIT-F3"), _Q6),
        tests=(
            f"{_T}/test_sociomap_evidence_policy.py::test_kish_n_is_the_count_under_equal_weights_and_less_under_unequal",
            f"{_T}/test_sociomap_evidence_policy.py::test_kish_n_widens_the_interval_it_reads",
        ),
    ),
    MethodStep(
        id="f3_interval",
        title_cs="Fisherův interval korelace",
        formula_latex=(
            r"\left[\tanh\!\left(\operatorname{atanh} r - \frac{z_c}{\sqrt{n-3}}\right),\;"
            r"\tanh\!\left(\operatorname{atanh} r + \frac{z_c}{\sqrt{n-3}}\right)\right],"
            r"\qquad z_c = \Phi^{-1}\!\left(\tfrac12 + \tfrac c2\right)"
        ),
        implements=f"{_S}.relations:fisher_interval",
        source_sha256="667142a630eedf3933a101cfff9669882e28f661c2feb1c4d93d7dc80ce0dcca",
        symbols=(
            Symbol(r"c", "hladina spolehlivosti"),
            Symbol(r"n", "vzorek páru (výše)"),
        ),
        parameters=(ParameterRef("relation.confidence", "Hladina spolehlivosti"),),
        constants=(ConstantRef(f"{_S}.relations:_FISHER_MIN_N", "Nejmenší n s intervalem"),),
        evidence=(_rule("AUDIT-F3"),),
        tests=(
            f"{_T}/test_sociomap_relations.py::test_the_chance_band_is_the_audits",
            f"{_T}/test_sociomap_relations.py::test_the_fisher_interval_needs_four_raters",
            f"{_T}/test_sociomap_relations.py::test_a_perfect_correlation_is_its_own_interval",
        ),
        note_cs="Při |r| = 1 je interval bodem (r, r); pod čtyřmi hodnotiteli interval není.",
    ),
    MethodStep(
        id="f3_status",
        title_cs="Stav páru: neznámý, slabý, spolehlivý",
        formula_latex=(
            r"\text{stav}_{ij} = \begin{cases}"
            r"\text{UNKNOWN} & r_{ij} \text{ neexistuje nebo } n_{ij} < n_{\min} \\"
            r"\text{RELIABLE} & 0 \notin \text{interval} \\"
            r"\text{WEAK} & \text{jinak} \end{cases}"
        ),
        implements=f"{_S}.relations:pair_status",
        source_sha256="281eae379eae55c16e61af140e030ea6c95e318243636a20391a9981894ef5f7",
        parameters=(ParameterRef("relation.n_min", "Nejmenší n páru", "respondenti"),),
        constants=(ConstantRef(f"{_S}.specification:_V3_N_MIN_FLOOR", "Nejnižší přípustné n_min"),),
        evidence=(_rule("AUDIT-F3"), _Q6),
        tests=(
            f"{_T}/test_sociomap_relations.py::test_below_n_min_a_pair_is_unknown_whatever_its_number_says",
            f"{_T}/test_sociomap_relations.py::test_reliable_means_the_interval_excludes_zero",
        ),
        note_cs="Neznámý pár se nikdy nezapíše jako „žádný vztah“: na mapě nepůsobí.",
    ),
    MethodStep(
        id="f3_effect_floor",
        title_cs="Práh praktické velikosti",
        formula_latex=r"\text{dosahuje prahu}_{ij} = \left(|r_{ij}| \ge r_{\min}\right)",
        implements=f"{_S}.relations:meets_effect_floor",
        source_sha256="a1f1186816f6aebe935a6a62b0c9f852e37066ddcc7e15af70617363cd31d57a",
        symbols=(Symbol(r"r_{\min}", "práh účinku"),),
        parameters=(ParameterRef("relation.effect_floor", "Práh účinku"),),
        evidence=(_Q6,),
        tests=(
            f"{_T}/test_sociomap_evidence_policy.py::test_a_precisely_small_relation_is_reliable_and_below_the_floor",
            f"{_T}/test_sociomap_evidence_policy.py::test_the_floor_is_recorded_beside_the_status_never_inside_it",
        ),
        note_cs=(
            "Zaznamenává se vedle stavu, nikdy do něj: pár může být spolehlivý a malý, nebo "
            "velký a nejistý."
        ),
    ),
    # ------------------------------------------------------------------ F4
    MethodStep(
        id="f4_strength",
        title_cs="Síla vztahu a jeho směr",
        formula_latex=r"s_{ij} = |r_{ij}|,\qquad \operatorname{sgn} r_{ij} \text{ jako barva}",
        implements=f"{_S}.engine_v2:compute_object_map",
        source_sha256="deb3c4c93cf57ca3ac2b4c7f3d537a89a19772d70ed442c2a23c2ace9505ce6e",
        evidence=(_rule("AUDIT-F4"),),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_every_number_is_the_landed_functions_on_the_same_input",
        ),
        note_cs=(
            "Šipky (audit: jen spolehlivé vztahy) AIA zatím nekreslí. Stupnice 1-10 se pro "
            "objektovou mapu nepoužívá."
        ),
    ),
    # ------------------------------------------------------------------ F6
    MethodStep(
        id="f6_mappable",
        title_cs="Lze objekty zmapovat?",
        formula_latex=(
            r"m \ge m_{\min} \;\wedge\; \exists\, \text{známý pár} \;\wedge\;"
            r"\text{graf známých párů je souvislý}"
        ),
        implements=f"{_S}.engine_v2:_unreached",
        source_sha256="316d808ab33bd28141fc3a012a8b1fd3f98884de5987199d395615d8824cd86b",
        symbols=(
            Symbol(r"m", "počet objektů v rodině"),
            Symbol(r"m_{\min}", "nejmenší počet objektů, který mapa potřebuje"),
        ),
        parameters=(ParameterRef("layout.min_objects", "Nejméně objektů na mapě"),),
        constants=(
            ConstantRef(f"{_S}.specification:LEGACY_MIN_OBJECTS", "Minimum před aia-sociomap-4"),
        ),
        evidence=(_rule("AUDIT-F6"),),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_too_few_objects_is_not_mappable",
            f"{_T}/test_sociomap_object_map.py::test_a_sample_below_n_min_is_not_mappable_however_large_its_numbers",
        ),
        note_cs=(
            "Známý pár je spolehlivý nebo slabý. Minimum objektů deklaruje aia-sociomap-4 "
            "(nejméně 3: dva body nemají tvar); běh připnutý dřív počítá s konstantou 3."
        ),
    ),
    MethodStep(
        id="f6_distance",
        title_cs="Cílová vzdálenost z korelace",
        formula_latex=(
            r"\delta_{ij} = \sqrt{\max\left(0,\; 2\,(1 - r_{ij})\right)}"
            r"\quad\text{pro známé páry, jinak bez váhy}"
        ),
        implements=f"{_S}.layout:correlation_distance",
        source_sha256="299af337e48cbeba8044760465d6fd134b99f956576f69e0d6eee21e15d33f35",
        symbols=(Symbol(r"\delta_{ij}", "vzdálenost dvou standardizovaných proměnných"),),
        parameters=(ParameterRef("layout.dissimilarity", "Cílová vzdálenost"),),
        evidence=(_rule("AUDIT-F6"),),
        tests=(
            f"{_T}/test_sociomap_smacof_objects.py::test_the_ruler_is_the_distance_between_standardised_variables",
            f"{_T}/test_sociomap_smacof_objects.py::test_an_unknown_pair_pulls_nothing",
        ),
    ),
    MethodStep(
        id="f6_smacof",
        title_cs="Rozložení objektů (SMACOF na pevném pravítku)",
        formula_latex=(
            r"\min_X \sigma(X) = \sum_{i<j} w_{ij}"
            r"\left(\lVert x_i - x_j\rVert - \delta_{ij}\right)^2,"
            r"\quad X \leftarrow V^{+} B(X)\, X,"
            r"\quad \sigma_{t-1} - \sigma_t \le \varepsilon \max(\sigma_t, 10^{-300})"
        ),
        implements=f"{_S}.layout:fit_smacof_objects",
        source_sha256="241827c0a6e4990ed89dff5a0258fcec75374f61866b79e538a197900e871f77",
        symbols=(
            Symbol(r"w_{ij}", "1 pro známý pár, 0 pro neznámý"),
            Symbol(r"V^{+}", "pseudoinverze matice vah"),
            Symbol(r"B(X)", "Guttmanova matice: -\\delta_{ij}/d_{ij}"),
            Symbol(r"\varepsilon", "relativní tolerance zastavení"),
        ),
        parameters=(
            ParameterRef("layout.algorithm", "Algoritmus rozložení"),
            ParameterRef("layout.max_iterations", "Nejvýše iterací"),
            ParameterRef("layout.tolerance", "Tolerance zastavení"),
            ParameterRef("layout.map_frame.method", "Rámec mapy"),
            ParameterRef("layout.map_frame.extent", "Rozsah pravítka", "jednotky vzdálenosti"),
        ),
        constants=(ConstantRef(f"{_S}.specification:FIXED_RULER_EXTENT", "Pevné pravítko"),),
        evidence=(_rule("AUDIT-F6"),),
        tests=(
            f"{_T}/test_sociomap_smacof_objects.py::test_a_planted_configuration_is_recovered_exactly",
            f"{_T}/test_sociomap_smacof_objects.py::test_each_iteration_never_raises_the_stress",
            f"{_T}/test_sociomap_smacof_objects.py::test_the_map_is_never_stretched_to_a_radius",
        ),
        note_cs=(
            "Start: Torgerson (neznámému páru se jen pro start doplní průměr známých \u03b4²). "
            "Poté se mapa vycentruje, otočí do hlavních os a zrcadlí podle třetího momentu; "
            "nikdy se nenatahuje na poloměr."
        ),
    ),
    # ------------------------------------------------------------------ F7
    MethodStep(
        id="f7_stress",
        title_cs="Stress-1: jak věrně mapa drží vzdálenosti",
        formula_latex=(
            r"\text{Stress-1} = \sqrt{\frac{\sum_{i<j} (d_{ij} - \delta_{ij})^2}"
            r"{\sum_{i<j} \delta_{ij}^2}}\quad\text{přes známé páry}"
        ),
        implements=f"{_S}.layout:_object_stress",
        source_sha256="1eb3fa7ad0e52bd548350370d187308bc414561d15f2fa2d90a324cc6c989a3f",
        symbols=(Symbol(r"d_{ij}", "vzdálenost na mapě"),),
        evidence=(_rule("AUDIT-F7"),),
        tests=(
            f"{_T}/test_sociomap_smacof_objects.py::test_each_iteration_never_raises_the_stress",
        ),
    ),
    MethodStep(
        id="f7_quality",
        title_cs="Slovní hodnocení věrohodnosti",
        formula_latex=(
            r"\text{kvalita} = \begin{cases} \text{dobrá} & \text{Stress-1} < b_1 \\"
            r" \text{ucházející} & < b_2 \\ \text{slabá} & < b_3 \\"
            r" \text{2D obraz nespolehlivý} & \text{jinak} \end{cases}"
        ),
        implements=f"{_S}.view:stress_quality",
        source_sha256="6a54c13d05342bde4d30ffd8bd768b43da0fe645650eeb826d8b06fd5085f3f0",
        symbols=(Symbol(r"b_1, b_2, b_3", "horní hranice pásem dobrá, ucházející, slabá"),),
        parameters=(ParameterRef("layout.stress_bands", "Hranice pásem b₁, b₂, b₃"),),
        constants=(
            ConstantRef(f"{_S}.view:STRESS_QUALITY_BANDS", "Hranice pásem před aia-sociomap-4"),
        ),
        evidence=(_rule("AUDIT-F7"),),
        tests=(
            f"{_T}/test_sociomap_alignment_quality.py::test_every_stress_carries_the_audits_label",
        ),
        note_cs=("Zarovnání na referenční mapu (Procrustes) je pohled a výpočet mapy nemění."),
    ),
    # ------------------------------------------------------------------ F8
    MethodStep(
        id="f8_scores",
        title_cs="Souhlasnost a propojenost objektu",
        formula_latex=(
            r"A_i = \frac{1}{k_i}\sum_{j \in \mathcal{K}_i} r_{ij},\qquad "
            r"K_i = \frac{1}{k_i}\sum_{j \in \mathcal{K}_i} |r_{ij}|"
        ),
        implements=f"{_S}.metrics:primary_scores",
        source_sha256="521da7e15361047c5c6ef793197310f57f1c6d4924ba85d101026517910ee021",
        symbols=(
            Symbol(r"\mathcal{K}_i", "známí PRIMÁRNÍ partneři objektu i"),
            Symbol(r"k_i", "jejich počet; bez partnera skóre není (ne nula)"),
        ),
        evidence=(_rule("AUDIT-F8"),),
        tests=(
            f"{_T}/test_sociomap_primary_scores.py::test_the_scores_are_the_audits_formula_on_a_hand_computed_example",
            f"{_T}/test_sociomap_primary_scores.py::test_a_secondary_object_never_moves_a_primary_score_where_it_reshuffles_classic",
        ),
        note_cs="Kontextový (SEKUNDÁRNÍ) objekt skóre PRIMÁRNÍHO nikdy nepohne.",
    ),
    MethodStep(
        id="f8_height",
        title_cs="Výška objektu",
        formula_latex=r"h_j = \frac{\sum_k w_k \tilde a_{kj}}{\sum_k w_k}\quad\text{(F1, před F2)}",
        implements=f"{_S}.engine_v2:_heights",
        source_sha256="b92511a1a55691a948eed0d03f1e4509a5d4bb2537edafb21e089e6e51494560",
        symbols=(Symbol(r"k", "všichni, kdo objekt hodnotili, i neumístění"),),
        parameters=(ParameterRef("scores.height", "Výška objektu"),),
        evidence=(_rule("AUDIT-F8"), _Q7),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_a_straight_liner_is_not_placed_but_their_ratings_count_in_the_heights",
        ),
    ),
    # ------------------------------------------------------------------ F9
    MethodStep(
        id="f9_k100",
        title_cs="Propojenost 0-100 a její bootstrap",
        formula_latex=(
            r"K^{100}_i = 100\,K_i,\qquad K^{100,(b)}_i \text{ pro } b = 1..B"
            r"\text{ (respondenti tažení s vracením)}"
        ),
        implements=f"{_S}.metrics:connectedness_100",
        source_sha256="e9302e1647a2b1318d3bbe60018fdb8133fd2783eed8e380fd687d776e11189a",
        symbols=(Symbol(r"B", "počet převzorkování"),),
        parameters=(
            ParameterRef("connectedness.resamples", "Počet převzorkování B"),
            ParameterRef("connectedness.seed", "Semínko generátoru"),
            ParameterRef("connectedness.quantiles", "Kvantily intervalu"),
        ),
        constants=(
            ConstantRef(
                f"{_S}.metrics:CONNECTEDNESS_QUANTILES", "Kvantily intervalu před aia-sociomap-4"
            ),
            ConstantRef(f"{_S}.metrics:CONNECTEDNESS_BOOTSTRAP_GENERATOR", "Generátor"),
        ),
        evidence=(_rule("AUDIT-F9"),),
        tests=(
            f"{_T}/test_sociomap_connectedness_100.py::test_k100_is_a_hundred_times_connectedness_and_its_interval_contains_it",
            f"{_T}/test_sociomap_connectedness_100.py::test_the_same_seed_is_bit_identical_and_another_seed_is_not",
        ),
        note_cs=(
            "Stavy párů zůstávají z plného vzorku; převzorkování, které pár nespočte, objekt "
            "neskóruje. Počítá se jen se zapnutým AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED."
        ),
    ),
    MethodStep(
        id="f9_quantile",
        title_cs="Lineární kvantil (typ 7)",
        formula_latex=(
            r"Q(q) = x_{(\lfloor h\rfloor)} + (h - \lfloor h\rfloor)"
            r"\left(x_{(\lfloor h\rfloor + 1)} - x_{(\lfloor h\rfloor)}\right),\quad h = (B'-1)\,q"
        ),
        implements=f"{_S}.metrics:linear_quantile",
        source_sha256="95872353dfb1d33bacbeb502807d592ddb0710cc90117171edba39e2cec74048",
        symbols=(Symbol(r"B'", "počet převzorkování, která objekt skórovala"),),
        evidence=(_rule("AUDIT-F9"),),
        tests=(
            f"{_T}/test_sociomap_connectedness_100.py::test_the_interval_is_the_linear_quantile_of_the_resampled_scores_by_hand",
        ),
    ),
    MethodStep(
        id="f9_rank",
        title_cs="Pořadí jen tam, kde se intervaly nepřekrývají",
        formula_latex=r"i \succ j \iff \text{dolní}_i > \text{horní}_j",
        implements=f"{_S}.metrics:rank_with_ties",
        source_sha256="750854455d8377bd7c8d313acdb0be1b34fa823f20d7387206c6f14b09cebbc0",
        evidence=(_rule("AUDIT-F9"),),
        tests=(
            f"{_T}/test_sociomap_connectedness_100.py::test_intervals_that_do_not_overlap_are_ordered",
            f"{_T}/test_sociomap_connectedness_100.py::test_intervals_that_overlap_or_touch_are_tied",
        ),
        note_cs="Dotýkající se intervaly se překrývají a jsou nerozhodné.",
    ),
    # ------------------------------------------------------------------ F10
    MethodStep(
        id="f10_placement",
        title_cs="Umístění respondentů (navrženo, zatím se nepočítá)",
        formula_latex=(
            r"x_k = \arg\min_x \sum_{j \in \mathcal{P}}"
            r" \left(\lVert x - y_j\rVert - \delta_{kj}\right)^2,"
            r"\quad \delta_{kj} = D\,(1 - \tilde a_{kj}),"
            r"\quad e_k = \sqrt{\frac{\sum_j (\lVert x_k - y_j\rVert - \delta_{kj})^2}"
            r"{\sum_j \delta_{kj}^2}}"
        ),
        implements=f"{_S}.specification:_require_supported_v3",
        source_sha256="8250a494e70414dd677225cc2c3d3ed2b51dd96ebeaa27bf1e41b35a484ed70c",
        symbols=(
            Symbol(r"D", "průměr mapy (2 na pravítku F6)"),
            Symbol(r"e_k", "nesoulad respondenta: jak dobře jej mapa vystihne"),
        ),
        parameters=(ParameterRef("respondent_placement", "Umístění respondentů"),),
        evidence=(_rule("AUDIT-F10"),),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_contract_3_refuses_what_it_cannot_compute_by_name",
        ),
        note_cs=(
            "V AIA zatím není: specifikace musí uvést null a jinou hodnotu odmítne. Vzorec je "
            "návrh auditu; práh nesouladu je otevřený (sociomap-formula-corrections.md, krok 3)."
        ),
    ),
    # ------------------------------------------------------------------ F11
    MethodStep(
        id="f11_not_placed",
        title_cs="Respondent bez rozptylu není umístěn",
        formula_latex=r"\max_l a_{kl} = \min_l a_{kl} \;\Rightarrow\; k \text{ NEUMÍSTĚN}",
        implements=f"{_S}.relations:person_minmax",
        source_sha256="986d2b7017c7ac1b5647edab1e9fad0b2b5da295a322cac50d6ae9e26e0496be",
        evidence=(_rule("AUDIT-F11"),),
        tests=(
            f"{_T}/test_sociomap_person_minmax.py::test_a_row_with_no_spread_is_excluded_never_divided_by_zero",
            f"{_T}/test_sociomap_object_map.py::test_a_straight_liner_is_not_placed_but_their_ratings_count_in_the_heights",
        ),
        note_cs="Je vyloučen ze vztahů a z terénu, ale počítá se do výšek a je sečten.",
    ),
    MethodStep(
        id="support",
        title_cs="Na čem mapa stojí",
        formula_latex=(
            r"n_{\text{eff}} = \frac{\left(\sum_{k \in U} w_k\right)^2}{\sum_{k \in U} w_k^2},"
            r"\quad U = \text{umístění respondenti}"
        ),
        implements=f"{_S}.engine_v2:_support",
        source_sha256="9a71aaf6b5538d7f9df8df8a3d2a0c29183d34c17c00d17377d62d622e5f382d",
        evidence=(_rule("AUDIT-F11"),),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_the_map_says_what_it_rests_on_and_how_weights_entered_it",
        ),
        note_cs="Mapa uvádí počet respondentů, umístěných, neumístěných, efektivní n a dárce.",
    ),
    # ------------------------------------------------------------------ F12 / F13
    MethodStep(
        id="f12_envelope",
        title_cs="Terén jako obálka kopců",
        formula_latex=(
            r"z(q) = \max_{j \in \mathcal{P},\, h_j \ne \varnothing}"
            r" h_j \exp\!\left(-\frac{\lVert q - y_j\rVert^2}{2\sigma^2}\right),"
            r"\quad g_t = -S + t\,\frac{2S}{N},\; t = 0..N"
        ),
        implements=f"{_S}.terrain:envelope_at",
        source_sha256="8672f6dc43b2c181319e75a62724dad7138ece866ec1628d6f1a29f2b755e254",
        symbols=(
            Symbol(r"\sigma", "šířka kopce", "jednotky vzdálenosti"),
            Symbol(r"S, N", "poloviční rozsah a rozlišení mřížky"),
        ),
        parameters=(
            ParameterRef("terrain.method", "Metoda terénu"),
            ParameterRef("terrain.sigma", "Šířka kopce \u03c3", "jednotky vzdálenosti"),
            ParameterRef("terrain.sigma_basis", "Původ šířky \u03c3"),
            ParameterRef("terrain.grid_resolution", "Rozlišení mřížky N"),
            ParameterRef("terrain.half_extent", "Poloviční rozsah S", "jednotky vzdálenosti"),
            ParameterRef("terrain.kernel_cutoff", "Práh jádra"),
        ),
        evidence=(_rule("AUDIT-F12"), _rule("AUDIT-F13")),
        tests=(
            f"{_T}/test_sociomap_envelope.py::test_each_hill_is_exactly_its_height_and_a_high_neighbour_does_not_pull_it",
            f"{_T}/test_sociomap_envelope.py::test_far_from_every_hill_there_is_nothing_not_a_height_of_zero",
            f"{_T}/test_sociomap_envelope.py::test_the_provisional_width_keeps_its_definition",
        ),
        note_cs=(
            "Buňka, kam žádný kopec nedosáhne (jádro pod prahem), nemá výšku, ne nulu. "
            "\u03c3 = 0,25 je prozatímní (√0,4 / √(2 ln 20), zaokrouhleno dolů)."
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("M", "Metoda", ("method",)),
    StepGroup("F1", "F1 Které položky jsou hodnocení", ("f1_declared_scale",)),
    StepGroup("F2", "F2 Hodnoticí zvyklosti", ("f2_person_minmax",)),
    StepGroup(
        "F3",
        "F3 Vztah dvou objektů a jeho spolehlivost",
        ("f3_correlation", "f3_effective_n", "f3_interval", "f3_status", "f3_effect_floor"),
    ),
    StepGroup("F4", "F4 Síla vztahu a šipky", ("f4_strength",)),
    StepGroup(
        "F5",
        "F5 Typ dodané matice",
        (),
        "Objektová mapa počítá vztahy z hodnocení, dodanou matici nečte. Deklarovaný typ "
        "matice platí pro referenční mapu.",
    ),
    StepGroup("F6", "F6 Vzdálenost a rozložení", ("f6_mappable", "f6_distance", "f6_smacof")),
    StepGroup("F7", "F7 Jedno rozložení a jeho věrohodnost", ("f7_stress", "f7_quality")),
    StepGroup("F8", "F8 Skóre objektů a výška", ("f8_scores", "f8_height")),
    StepGroup("F9", "F9 Propojenost 0-100", ("f9_k100", "f9_quantile", "f9_rank")),
    StepGroup("F10", "F10 Umístění respondentů", ("f10_placement",)),
    StepGroup("F11", "F11 Respondenti, které nelze umístit", ("f11_not_placed", "support")),
    StepGroup("F12", "F12-F13 Terén", ("f12_envelope",)),
    StepGroup(
        "F14",
        "F14 Testy při porovnání oblastí",
        (),
        "V AIA zatím není (sociomap-formula-corrections.md, krok 4d). Návrh auditu: testovat "
        "jen proměnné, které neurčily polohu, a korigovat Holmem: zamítnout H_(k), právě když "
        "p_(l) ≤ \u03b1 / (|V_test| - l + 1) pro všechna l ≤ k, \u03b1 = 0,05; "
        "nejdřív Cohenovo d s intervalem.",
    ),
    StepGroup(
        "F15",
        "F15 Pořadí hlavních rozdílů",
        (),
        "V AIA zatím není (krok 4d). Návrh auditu: |d| = |x̄_A - x̄_B| / s_pooled pro čísla, "
        "|h| = |2 arcsin √\u03c0_A - 2 arcsin √\u03c0_B| pro kategorie (maximum přes kategorie).",
    ),
    StepGroup(
        "F16",
        "F16 Cíle rozvinutí po respondentech",
        (),
        "Otevřené (krok 4c). Týká se referenční mapy. Návrh auditu: \u03b4_kj = (s_max - a_kj) / "
        "(s_max - s_min) a skutečné řádkově podmíněné rozvinutí se sklonem a posunem na "
        "respondenta a penalizací proti degeneraci.",
    ),
)

SOCIOMAP: Final = MethodModule(
    id="sociomap",
    title_cs="Sociomapa: objektová mapa",
    steps=_STEPS,
    presets=(
        Preset("aia-sociomap-4", AIA_SOCIOMAP_V4, _validate),
        Preset("aia-sociomap-3", AIA_SOCIOMAP_V3, _validate),
        Preset("aia-sociomap-2", AIA_SOCIOMAP_V2, _validate),
    ),
    in_force="aia-sociomap-3",
    groups=_GROUPS,
    formulas=SOCIOMAP_FORMULAS,
    editable=True,
    note_cs=(
        "Mapa auditu NPC Sociomapa (kanonická metodika). Každý nový běh si připne "
        "aia-sociomap-3 vedle referenční mapy aia-sociomap-1. Mapa je zatím jen interní "
        "(D6 otevřené). aia-sociomap-4 počítá totéž, jen má v metodice i hodnoty, které "
        "-3 drží v kódu (minimum objektů, pásma Stress, kvantily K100); úprava z něj vychází."
    ),
)
