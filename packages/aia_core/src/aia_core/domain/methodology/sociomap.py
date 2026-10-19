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

from dataclasses import dataclass, replace
from typing import Final

from pydantic import BaseModel

from ..sociomap.specification import (
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
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

_SIGNED_OFF: Final = _rule("AIA-SIGNED-OFF-INPUTS")
_SIGNED_OFF_TESTS: Final = (
    f"{_T}/test_sociomap_signed_off_inputs.py::test_the_port_reproduces_every_output_of_the_methodologys_own_code",
)
_SIGNED_OFF_MAP_TEST: Final = (
    f"{_T}/test_sociomap_signed_off_inputs.py::"
    "test_the_object_map_records_the_baseline_corrected_relations_under_aia_sociomap_5"
)

_SIGNED_OFF_LAYOUT: Final = _rule("AIA-SIGNED-OFF-LAYOUT")
_LAYOUT_TEST: Final = f"{_T}/test_sociomap_signed_off_layout.py::"
_LAYOUT_MAP_TEST: Final = (
    f"{_LAYOUT_TEST}test_the_object_map_records_the_signed_off_positions_under_aia_sociomap_5"
)

_SIGNED_OFF_TERRAIN: Final = _rule("AIA-SIGNED-OFF-TERRAIN")
_TERRAIN_TEST: Final = f"{_T}/test_sociomap_signed_off_terrain.py::"
_TERRAIN_PARITY_TEST: Final = (
    f"{_TERRAIN_TEST}test_height_frame_and_terrain_match_the_methodologys_own_code"
)
_TERRAIN_MAP_TEST: Final = (
    f"{_TERRAIN_TEST}test_the_object_map_stores_the_framed_terrain_under_aia_sociomap_5"
)

_CATALOGUE: Final[tuple[MethodStep, ...]] = (
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
    MethodStep(
        id="person_centring",
        title_cs="Hodnocení vztažená k průměru respondenta",
        formula_latex=(
            r"\tilde a_{ki} = a_{ki} - \frac{1}{L_k}\sum_{l} a_{kl},"
            r"\qquad L_k < 2 \;\lor\; \max_l |\tilde a_{kl}| \le 10^{-12}"
            r" \;\Rightarrow\; k \text{ NEUMÍSTĚN}"
        ),
        implements=f"{_S}.signed_off_inputs:centre",
        source_sha256="82d0a21ac3d0abd73d9677c18462b3e302c04e85010ded26eded58456f75a995",
        symbols=(
            Symbol(r"a_{ki}", "surové hodnocení mapovaného objektu i respondentem k", "body škály"),
            Symbol(r"L_k", "počet mapovaných objektů, které respondent k hodnotil"),
            Symbol(r"\tilde a_{ki}", "hodnocení vztažené k průměru respondenta"),
        ),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _SIGNED_OFF_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5 (normalizace na osobu person_mean_centring): čte surová "
            "hodnocení mapovaných objektů na jejich vlastní škále, bez vah respondentů."
        ),
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
        note_cs=(
            "Při |r| = 1 je interval bodem (r, r); pod čtyřmi hodnotiteli interval není. "
            "aia-sociomap-5 interval nečte: hladina zůstává 0,95 jako v aia-sociomap-4."
        ),
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
        evidence=(_rule("AUDIT-F3"), _Q6),
        tests=(
            f"{_T}/test_sociomap_evidence_policy.py::test_a_precisely_small_relation_is_reliable_and_below_the_floor",
            f"{_T}/test_sociomap_evidence_policy.py::test_the_floor_is_recorded_beside_the_status_never_inside_it",
        ),
        note_cs=(
            "Zaznamenává se vedle stavu, nikdy do něj: pár může být spolehlivý a malý, nebo "
            "velký a nejistý."
        ),
    ),
    MethodStep(
        id="baseline_corrected_relation",
        title_cs="Korelace očištěná o úroveň nesouvisejících objektů",
        formula_latex=(
            r"r_{ij} = \operatorname{clip}_{[-0{,}999999,\,0{,}999999]}"
            r"\frac{\operatorname{cov}(\tilde a_i, \tilde a_j)}{\sqrt{v_i v_j}},\quad "
            r"r^0_{ij} = -\frac{1}{n_{ij}} \sum_{k} \frac{1}{L_k - 1},\quad "
            r"\tilde r_{ij} = \frac{r_{ij} - r^0_{ij}}{1 - r^0_{ij}},\quad "
            r"p_{ij} = 2\left(1 - \Phi\!\left(\left|\left(\operatorname{atanh} r_{ij}"
            r" - \operatorname{atanh} \operatorname{clip}_{[-0{,}999,\,0{,}999]} r^0_{ij}\right)"
            r"\sqrt{\max(n_{ij} - 3,\, 10^{-9})}\right|\right)\right)"
        ),
        implements=f"{_S}.signed_off_inputs:pair_stats",
        source_sha256="b98912c0d589bd634ac6dcecad6783ade10863841b2e553ff47bda22b8b0faef",
        symbols=(
            Symbol(r"k", "respondenti, kteří hodnotili oba objekty (každý jednou, bez vah)"),
            Symbol(r"n_{ij}", "počet těchto respondentů: podpora páru"),
            Symbol(
                r"r^0_{ij}", "korelace, kterou by dva nesouvisející objekty měly jen z centrování"
            ),
            Symbol(r"\tilde r_{ij}", "vztah objektů i a j očištěný o tuto úroveň"),
            Symbol(r"p_{ij}", "Fisherovo p proti úrovni nesouvisejících objektů"),
        ),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _SIGNED_OFF_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5 (odhad baseline_corrected_pearson). Pár je známý, když jej "
            "hodnotilo aspoň n_min respondentů (práh stavu, krok Stav páru) a oba sloupce mají "
            "rozptyl nad 10^-12; jinak je neznámý a nemá žádnou hodnotu."
        ),
    ),
    MethodStep(
        id="reliable_by_fdr",
        title_cs="Spolehlivý pár: Benjaminiho-Hochbergova kontrola falešných objevů",
        formula_latex=(
            r"p_{(1)} \le \dots \le p_{(m)},\quad "
            r"k^{*} = \max\left\{k : p_{(k)} \le \tfrac{k}{m}\, q\right\},\qquad "
            r"\text{stav}_{ij} = \begin{cases}"
            r"\text{RELIABLE} & \text{pár mezi } (1) \dots (k^{*}) \;\land\;"
            r" |\tilde r_{ij}| > \tau_{ij} \\"
            r"\text{WEAK} & \text{známý, ale ne spolehlivý} \\"
            r"\text{UNKNOWN} & \text{neznámý pár} \end{cases}"
        ),
        implements=f"{_S}.signed_off_inputs:bh",
        source_sha256="75c7c81904bf58099bfa11254f1ead3af33e70f89cd8893bb153670120a96c3a",
        symbols=(
            Symbol(r"m", "počet známých párů, každý jednou"),
            Symbol(r"q", "míra falešných objevů"),
            Symbol(r"\tau_{ij}", "práh pravidla šumu (další krok); bez pravidla šumu se nečte"),
        ),
        parameters=(ParameterRef("relation.false_discovery_rate", "Míra falešných objevů q"),),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _SIGNED_OFF_MAP_TEST),
        note_cs="Jen aia-sociomap-5. Neznámý pár se netestuje a do m se nepočítá.",
    ),
    MethodStep(
        id="noise_rule",
        title_cs="Pravidlo šumu: vztah silnější než po zamíchání objektu",
        formula_latex=(
            r"\tau_{ij} = Q_{0{,}95}\left(\left\{|\tilde r^{(b,t)}_{ij}| :"
            r" b \in \{i, j\},\ t = 1 \dots T\right\}\right),"
            r"\qquad \text{RELIABLE vyžaduje } |\tilde r_{ij}| > \tau_{ij}"
        ),
        implements=f"{_S}.signed_off_inputs:noise_q95_fast",
        source_sha256="ca6a162c426eb14fbbe9ee890cd6f91ca67a8b5251aa2306cefcb851998b2a27",
        symbols=(
            Symbol(
                r"\tilde r^{(b,t)}_{ij}",
                "očištěný vztah po t-tém zamíchání objektu b mezi respondenty",
            ),
            Symbol(r"T", "počet zamíchání na objekt"),
        ),
        parameters=(
            ParameterRef("relation.noise_rule.enabled", "Pravidlo šumu zapnuto"),
            ParameterRef("relation.noise_rule.permutations", "Počet zamíchání na objekt T"),
            ParameterRef("relation.noise_rule.seed", "Semínko generátoru"),
        ),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _SIGNED_OFF_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5. Po každém zamíchání se hodnocení znovu vztáhnou k průměrům "
            "respondentů a známé páry se určí podle prahu stavu n_min ze specifikace (původní "
            "kód jej měl pevně 10; při výchozí hodnotě je výsledek stejný); kvantil je výchozí "
            "lineární kvantil numpy. U úplných dat rychlý výpočet s T zamícháními a bez "
            "minimálního počtu hodnot; u neúplných ⌊T/2⌋ zamíchání a práh jen tam, kde je aspoň "
            "⌊T/2⌋ konečných hodnot."
        ),
    ),
    MethodStep(
        id="layout_pairs",
        title_cs="Páry pro rozložení: nižší práh a váha podle počtu hodnotitelů",
        formula_latex=(
            r"w^{L}_{ij} = \begin{cases}"
            r"\min\!\left(1, \max\!\left(0, \dfrac{n_{ij} - 3}{n_{\text{plná}} - 3}\right)\right)"
            r" & n_{ij} \ge n_L \;\land\; v_i, v_j > 10^{-12} \\"
            r"0 & \text{jinak} \end{cases}"
        ),
        implements=f"{_S}.signed_off_inputs:layout_weights",
        source_sha256="e7584558e8d0322348789fc63092895555855296e9ace2da8fdf7e6fb3a06643",
        symbols=(
            Symbol(r"n_L", "práh páru pro rozložení", "respondenti"),
            Symbol(
                r"n_{\text{plná}}", "počet hodnotitelů, od kterého má pár plnou váhu", "respondenti"
            ),
        ),
        parameters=(
            ParameterRef("layout.layout_floor", "Práh páru pro rozložení n_L", "respondenti"),
            ParameterRef("layout.layout_weight_full_at", "Plná váha páru od n_plná", "respondenti"),
        ),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _LAYOUT_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5. Páry pod prahem jsou pro rozložení maskované, ne "
            "„nesouvisející“. Váhy w^L čte rozložení měkkých pořadí (BB1), cíle a váhy "
            "přesnosti Interval MDS (kroky v části Rozložení na mapě)."
        ),
    ),
    MethodStep(
        id="sparse_design",
        title_cs="Poznámka o řídkém designu",
        formula_latex=(
            r"\text{řídký design} \Leftrightarrow "
            r"\frac{\#\{i < j : w^{L}_{ij} = 0\}}{\binom{M}{2}} > s"
            r" \;\lor\; \exists i : \#\{j : w^{L}_{ij} > 0\} < p_{\min}"
        ),
        implements=f"{_S}.signed_off_inputs:sparse_design",
        source_sha256="2fc44816cbfa9cc1a52435caea85434f7479d686dd3792bdc885d49d5501fd88",
        symbols=(
            Symbol(r"M", "počet mapovaných objektů"),
            Symbol(r"s", "nejvyšší podíl párů pod prahem rozložení"),
            Symbol(r"p_{\min}", "nejmenší počet partnerů objektu pro rozložení"),
        ),
        parameters=(
            ParameterRef("layout.sparse_share", "Podíl párů pod prahem s"),
            ParameterRef("layout.min_layout_partners", "Nejmenší počet partnerů p_min"),
        ),
        evidence=(_SIGNED_OFF,),
        tests=(*_SIGNED_OFF_TESTS, _SIGNED_OFF_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5. Mapa ji zapíše (sparse_design) i s objekty, které mají málo "
            "partnerů."
        ),
    ),
    # ------------------------------------------------------------------ F4
    MethodStep(
        id="f4_strength",
        title_cs="Síla vztahu a jeho směr",
        formula_latex=r"s_{ij} = |r_{ij}|,\qquad \operatorname{sgn} r_{ij} \text{ jako barva}",
        implements=f"{_S}.engine_v2:compute_object_map",
        source_sha256="382029e868916940931916cad0ccbd86f750f01a7a1ec13e6da808b727c54324",
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
            "(nejméně 3: dva body nemají tvar); běh připnutý dřív počítá s konstantou 3. "
            "aia-sociomap-5 deklaruje nejméně 2 objekty (Interval MDS nakreslí dva v jejich "
            "cílové vzdálenosti) a známý pár ani souvislost nežádá: rozložení umístí i objekty "
            "bez párů (krok Volba rozložení podle počtu objektů). Mapuje jen PRIMARY objekty "
            "sady; kontextové objekty na jeho mapě nejsou (jak je ukáže, je otevřená otázka)."
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
        note_cs=(
            "aia-sociomap-5 tento vzorec nečte: cíle jeho rozložení jsou δ z r̃ nad prahem "
            "rozložení (krok Páry pro rozložení), a náhradní vzorec proto odmítne."
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
            "nikdy se nenatahuje na poloměr. aia-sociomap-5 deklaruje algoritmus "
            "aia_soft_rank_spearman_or_interval_mds_v1 (další kroky); iterace a toleranci "
            "SMACOF nečte a drží je na hodnotách aia-sociomap-4."
        ),
    ),
    MethodStep(
        id="object_count_rule",
        title_cs="Volba rozložení podle počtu objektů",
        formula_latex=(
            r"\text{rozložení} = \begin{cases}"
            r"\text{Spearman měkkých pořadí s Coulombovým odpuzováním (BB1)}"
            r" & M_{\min} \le M \le M_{\max} \\"
            r"\text{Interval MDS} & \text{jinak} \end{cases},"
            r"\qquad \nexists\, i < j : n_{ij} \ge n_L \;\Rightarrow\; \text{nelze zmapovat}"
        ),
        implements=f"{_S}.engine_v2:_signed_off_layout",
        source_sha256="287f5dc1b6ecd888b5c5331412e3691f1ebf58f595a583d4d703bf09a34c17ca",
        symbols=(
            Symbol(r"M", "počet mapovaných objektů"),
            Symbol(
                r"M_{\min}, M_{\max}",
                "nejméně a nejvýše objektů pro rozložení BB1 (hodnoty u dalšího kroku)",
            ),
        ),
        evidence=(_SIGNED_OFF_LAYOUT,),
        tests=(
            f"{_LAYOUT_TEST}test_the_fixed_object_count_rule",
            f"{_LAYOUT_TEST}test_no_pair_at_the_layout_floor_is_not_mappable",
            _LAYOUT_MAP_TEST,
        ),
        note_cs=(
            "Jen aia-sociomap-5. Pod 4 objekty nemá BB1 člen pořadí (objekt potřebuje 3 "
            "partnery); nad 163 objektů je pomalé (odhad 1,07·10⁻³·M^2,46 s na jádro, 10 "
            "restartů souběžně, nejvýše 30 s při pevně 10 jádrech). Pevné číslo dává stejnou "
            "mapu na každém stroji. Která metoda mapu nakreslila, zapíše mapa (layout.method). "
            "Bez jediného páru nad prahem rozložení nic objekty neumístí a mapa nevznikne."
        ),
    ),
    MethodStep(
        id="soft_rank_spearman_layout",
        title_cs="Rozložení podle pořadí: Spearman měkkých pořadí s Coulombovým odpuzováním",
        formula_latex=(
            r"f(X) = \frac{1}{2 N_A} \sum_{i \in \mathcal{A}} \left(1 + "
            r"\operatorname{corr}_{w^L_i}\!\left(\operatorname{SR}_i(A),"
            r" \operatorname{SR}_i(D)\right)\right) + \lambda\, \frac{\rho}{P}"
            r" \sum_{i<j} \frac{q_{ij}}{d_{ij}},\quad "
            r"\operatorname{SR}_i(v)_j = \sum_{k \ne j} \sigma\!\left(\frac{v_{ij} - v_{ik}}"
            r"{\tau}\right),\quad \tau = \frac{1}{\min(M, 50)^2},\quad "
            r"\sigma(z) = 0 \text{ či } 1 \text{ pro } |z| \ge 40,\quad "
            r"q_{ij} = \left(\tfrac{1 - \tilde r_{ij}}{2}\right)^2,\quad "
            r"\rho = \sqrt{\tfrac{1}{P} \textstyle\sum_{i<j} d_{ij}^2};\quad "
            r"x_k \leftarrow \operatorname{clip}_{[0,1]^2}\!\left(x_k - a_k"
            r" \frac{g_k}{\lVert g_k \rVert}\right),\ "
            r"a_k = \operatorname{clip}_{[10^{-6}, 1]}\!\left(c_k \frac{s^\top s}{s^\top y}"
            r"\right),\ f_{\text{nový}} \le f - 10^{-4} a_k \lVert g_k \rVert"
            r" \text{ (nejvýše 8 zkrácení)};\quad "
            r"\hat X = \arg\max_{\text{restart}} \overline{\rho^{S}}"
        ),
        implements=f"{_S}.signed_off_layout:soft_rank_spearman",
        source_sha256="72616a9efcd9c6019b0568bf680374deac82f0427ac86e544ca38f3fb44c8f5b",
        symbols=(
            Symbol(
                r"A",
                "vztahy r̃ párů pro rozložení (neznámý pár 0), v každém řádku min-max do "
                "[10⁻⁶, 1 - 10⁻⁶]",
            ),
            Symbol(r"D", "vzdálenosti na mapě"),
            Symbol(
                r"\mathcal{A}, N_A",
                "objekty s aspoň p_min partnery pro rozložení (krok Poznámka o řídkém "
                "designu) a jejich počet; při plných vahách všechny",
            ),
            Symbol(r"w^L_i", "váhy páru pro rozložení v řádku i; nulová váha řádek nehodnotí"),
            Symbol(r"P", "počet párů M(M - 1)/2"),
            Symbol(r"\lambda", "váha Coulombova odpuzování"),
            Symbol(r"s, y", "poslední krok objektu k a změna jeho gradientu (Barzilai-Borwein)"),
            Symbol(r"c_k", "násobek kroku: 0,5 po 4 a více zkráceních, 1,1 po nejvýše jednom"),
            Symbol(r"\overline{\rho^{S}}", "průměrný Spearman tvrdých pořadí A a D po řádcích"),
        ),
        parameters=(
            ParameterRef("layout.soft_rank_spearman.min_objects", "BB1 od M_min objektů"),
            ParameterRef("layout.soft_rank_spearman.max_objects", "BB1 do M_max objektů"),
            ParameterRef("layout.soft_rank_spearman.repulsion_weight", "Váha odpuzování λ"),
            ParameterRef(
                "layout.soft_rank_spearman.restarts_below_ten_objects",
                "Restartů pod 10 objekty",
            ),
            ParameterRef("layout.soft_rank_spearman.restarts", "Restartů od 10 objektů"),
            ParameterRef("layout.soft_rank_spearman.seed", "Semínko náhodných startů"),
            ParameterRef("layout.soft_rank_spearman.max_passes", "Nejvýše průchodů"),
        ),
        evidence=(_SIGNED_OFF_LAYOUT,),
        tests=(
            f"{_LAYOUT_TEST}test_the_deterministic_parts_match_the_methodologys_own_code_exactly",
            f"{_LAYOUT_TEST}test_the_soft_rank_layout_recovers_the_planted_map",
            f"{_LAYOUT_TEST}test_the_soft_rank_layout_is_deterministic_and_honours_its_restarts_and_seed",
        ),
        note_cs=(
            "Jen aia-sociomap-5. První restart startuje z klasického škálování (1 - A)², "
            "ostatní z náhodných bodů v jednotkovém čtverci; restarty běží souběžně a "
            "výsledek na počtu vláken nezávisí. Průchod končí, když se žádný objekt nepohne "
            "nebo když se f za 30 průchodů zlepší relativně o méně než 3·10⁻⁴. Kritérium je "
            "velmi členité: na jednom stroji je mapa vždy stejná, mezi platformami se může "
            "lišit v posledních bitech výpočtu a tím i výsledkem (shoda se ověřuje "
            "statisticky)."
        ),
    ),
    MethodStep(
        id="interval_mds_layout",
        title_cs="Rozložení podle vzdáleností: Interval MDS s jednostrannou podlahou",
        formula_latex=(
            r"\min_{X} \sum_{i<j} w_{ij} \left(\hat d_{ij} - d_{ij}(X)\right)^2,\quad "
            r"\hat d_{ij} = c\, \max\!\left(0,\, m_d + b\,(\delta_{ij} - m_\delta)\right),\quad "
            r"w_{ij} = \frac{\max\!\left(\pi_{ij}, \max \pi / C\right)}"
            r"{\overline{w}},\ "
            r"\pi_{ij} = \frac{2 n_{ij}}{(1 - \tilde r_{ij})(1 + \tilde r_{ij})^2};\quad "
            r"n_{ij} < n_L:\ \hat d_{ij} = \max\!\left(d_{ij},\, \kappa\, \hat d(\sqrt 2)"
            r"\right),\ w_{ij} = 1;\quad "
            r"X \leftarrow V^{+} B(X)\, X \text{ (nejvýše 1500 iterací, stop při relativním "
            r"zlepšení} < 10^{-8} \text{ po 5 iteracích)}"
        ),
        implements=f"{_S}.signed_off_layout:interval_mds",
        source_sha256="e3acc16205487d887282faf9e3242e399ee3c06c67a17c29c16055c25f480baf",
        symbols=(
            Symbol(r"\delta_{ij}", "cíl √(2(1 - r̃)) páru pro rozložení"),
            Symbol(r"m_d, m_\delta, b", "vážená regrese vzdáleností na cíle (b ≤ 0: konstanta)"),
            Symbol(r"c", "normování, aby Σ w d̂² byl počet párů"),
            Symbol(r"\tilde r_{ij}", "vztah páru, pro váhu oříznutý na ±0,95"),
            Symbol(r"C", "strop poměru vah přesnosti"),
            Symbol(r"\kappa", "podíl vzdálenosti nesouvisejících objektů, pod který pár nesmí"),
        ),
        parameters=(
            ParameterRef("layout.interval_mds.random_starts", "Náhodných startů"),
            ParameterRef("layout.interval_mds.floor_fraction", "Podlaha κ"),
            ParameterRef("layout.precision_weight_cap", "Strop vah přesnosti C"),
        ),
        evidence=(_SIGNED_OFF_LAYOUT,),
        tests=(
            f"{_LAYOUT_TEST}test_interval_mds_matches_the_methodologys_own_code",
            _LAYOUT_MAP_TEST,
        ),
        note_cs=(
            "Jen aia-sociomap-5. Starty: Torgerson (nenapasovaný pár dostane průměrný cíl, "
            "znaménka os podle třetího momentu, posun 10⁻⁶ z generátoru 0) a náhodné starty z "
            "generátorů 1001, 1002, …; ponechá se start s nejnižším normovaným stresem. Pár "
            "pod prahem rozložení netlačí, dokud není blíž než κ násobek vzdálenosti "
            "nesouvisejících objektů."
        ),
    ),
    MethodStep(
        id="ruler_scale",
        title_cs="Převod na pravítko: jedno společné měřítko",
        formula_latex=(
            r"X \leftarrow (X - \bar X)\, \frac{\sum_{(i,j) \in \mathcal{L}} d_{ij}\,\delta_{ij}}"
            r"{\sum_{(i,j) \in \mathcal{L}} d_{ij}^2},\qquad "
            r"\mathcal{L} = \emptyset \;\Rightarrow\; X \leftarrow (X - \bar X)\,"
            r"\frac{\sqrt 2}{\sqrt{\overline{d^2}}}"
        ),
        implements=f"{_S}.signed_off_layout:to_ruler",
        source_sha256="2fe04133d6db97dcb38dde6681e8dbbf6b36e120873418016dd2c618b3942d4e",
        symbols=(
            Symbol(r"\mathcal{L}", "páry pro rozložení"),
            Symbol(r"\delta_{ij}", "cíl √(2(1 - r̃)) v jednotkách pravítka"),
        ),
        evidence=(_SIGNED_OFF_LAYOUT,),
        tests=(
            f"{_LAYOUT_TEST}test_the_ruler_scale_matches_the_methodologys_own_code",
            _LAYOUT_MAP_TEST,
        ),
        note_cs=(
            "Jen aia-sociomap-5. Jen posun a jedno měřítko, bez otočení: mapa se nenatahuje "
            "do tvaru. Souřadnice v jednotkách pravítka zapíše mapa."
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
            _LAYOUT_MAP_TEST,
        ),
        note_cs=(
            "aia-sociomap-5 Stress-1 nepočítá: je to míra SMACOF a metodika posuzuje mapu "
            "kontrolou dělených polovin. Náhradní vzorec proto odmítne."
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
        note_cs=(
            "Zarovnání na referenční mapu (Procrustes) je pohled a výpočet mapy nemění. "
            "aia-sociomap-5 pásma nemá (Stress-1 nepočítá)."
        ),
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
        evidence=(_rule("AUDIT-F8"), _Q7, _SIGNED_OFF_TERRAIN),
        tests=(
            f"{_T}/test_sociomap_object_map.py::test_a_straight_liner_is_not_placed_but_their_ratings_count_in_the_heights",
            f"{_TERRAIN_TEST}test_the_height_is_survey_weighted_and_the_relations_are_not",
            _TERRAIN_PARITY_TEST,
        ),
        note_cs=(
            "aia-sociomap-5 počítá výšku stejně, s váhami respondentů, jako schválená metodika; "
            "vztahy a polohy objektů jsou u něj nevážené."
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
        source_sha256="e669b6c80a18559ac344fcefee924594143c213478d891d0138990aca0510f30",
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
        id="relative_heights",
        title_cs="Relativní výška kopce",
        formula_latex=(
            r"t_j = f + (1 - f)\,\frac{h_j - \min_l h_l}{\max_l h_l - \min_l h_l},\qquad "
            r"\max_l h_l - \min_l h_l < 10^{-15} \;\Rightarrow\; t_j = \tfrac12,\qquad "
            r"h_j = \varnothing \;\Rightarrow\; h_j = \min_{l:\, h_l \ne \varnothing} h_l"
        ),
        implements=f"{_S}.engine_v2:_relative_heights",
        source_sha256="7ec4119557d8a0a85dd11cf36515a7fb902f08ef1a5af634ac5c73589f910879",
        symbols=(
            Symbol(r"h_j", "výška objektu j: průměr hodnocení na škále 0-1"),
            Symbol(r"l", "PRIMÁRNÍ objekty mapy"),
            Symbol(r"f", "nejnižší relativní výška (hodnota u kroku terénu)"),
            Symbol(r"t_j", "relativní výška kopce objektu j, v [f, 1]"),
        ),
        constants=(
            ConstantRef(
                f"{_S}.engine_v2:EQUAL_RELATIVE_HEIGHT", "Výška kopců, když se výšky neliší"
            ),
        ),
        evidence=(_SIGNED_OFF_TERRAIN,),
        tests=(_TERRAIN_PARITY_TEST, _TERRAIN_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5. Objekt, který nikdo nehodnotil, stojí na nejnižší výšce; jeho "
            "výška zůstane prázdná, takže ho mapa může ukázat šedě. Nehodnotil-li nikdo nic, "
            "stojí všechny kopce na 0,5. Kontextový (SEKUNDÁRNÍ) objekt kopec nemá a rozpětí "
            "výšek nemění. Relativní výšky zapíše mapa (heights.relative)."
        ),
    ),
    MethodStep(
        id="terrain_frame",
        title_cs="Rám terénu podle mapy",
        formula_latex=(
            r"c = \tfrac12\left(\min_j x_j + \max_j x_j\right),\qquad "
            r"H = \frac{\max_j \lVert x_j - c\rVert_\infty}{v},\qquad "
            r"\max_j \lVert x_j - c\rVert_\infty \le 10^{-12}/27 \;\Rightarrow\; H = H_0"
        ),
        implements=f"{_S}.terrain:fit_frame",
        source_sha256="ef12f067a9941dde1a6a821f31dc40561f9128b9d2f1f0b8b2746c728f9a76b0",
        symbols=(
            Symbol(r"x_j", "poloha objektu j na pravítku (všechny umístěné objekty)"),
            Symbol(r"c", "střed mřížky terénu"),
            Symbol(r"H", "poloviční šířka mřížky", "jednotky vzdálenosti"),
            Symbol(r"v", "podíl poloviční šířky, který objekty vyplní (hodnota u kroku terénu)"),
        ),
        constants=(
            ConstantRef(
                f"{_S}.terrain:ONE_POINT_HALF_EXTENT",
                "H₀: poloviční šířka, stojí-li všechny objekty v jednom bodě",
                "jednotky vzdálenosti",
            ),
        ),
        evidence=(_SIGNED_OFF_TERRAIN,),
        tests=(_TERRAIN_PARITY_TEST, _TERRAIN_MAP_TEST),
        note_cs=(
            "Jen aia-sociomap-5. Střed je střed obdélníku kolem objektů, ne jejich průměr. Rám "
            "kryje všechny umístěné objekty, i kontextové, aby každý nakreslený objekt stál na "
            "mřížce; kopce dávají jen PRIMÁRNÍ objekty. Střed a poloviční šířku zapíše mapa "
            "(terrain.parameters.centre a half_extent). H₀ = 62/27 je rám metodiky v jejích "
            "kreslicích jednotkách (62 jednotek, 27 na jednotku pravítka)."
        ),
    ),
    MethodStep(
        id="f12_envelope",
        title_cs="Terén jako obálka kopců",
        formula_latex=(
            r"z(q) = \max_{j \in \mathcal{P},\, h_j \ne \varnothing}"
            r" h_j \exp\!\left(-\frac{\lVert q - y_j\rVert^2}{2\sigma^2}\right),"
            r"\quad g_t = -S + t\,\frac{2S}{N},\; t = 0..N"
        ),
        implements=f"{_S}.terrain:envelope_at",
        source_sha256="90f0abfb8e149f1e7c0ba9d8f799ad13d006df46a662dab4da0d66cc2382915f",
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
            ParameterRef("terrain.frame_fill", "Podíl rámu vyplněný objekty v"),
            ParameterRef("terrain.relative_height_floor", "Nejnižší relativní výška f"),
        ),
        evidence=(_rule("AUDIT-F12"), _rule("AUDIT-F13")),
        tests=(
            f"{_T}/test_sociomap_envelope.py::test_each_hill_is_exactly_its_height_and_a_high_neighbour_does_not_pull_it",
            f"{_T}/test_sociomap_envelope.py::test_far_from_every_hill_there_is_nothing_not_a_height_of_zero",
            f"{_T}/test_sociomap_envelope.py::test_the_provisional_width_keeps_its_definition",
        ),
        note_cs=(
            "Buňka, kam žádný kopec nedosáhne (jádro pod prahem), nemá výšku, ne nulu. "
            "\u03c3 = 0,25 je prozatímní (√0,4 / √(2 ln 20), zaokrouhleno dolů). "
            "aia-sociomap-5 (metoda framed_relative_envelope) staví kopce v relativních výškách "
            "t_j na mřížce g_t = c - H + t·2H/N z rámu mapy a práh jádra nemá: dosáhne každý "
            "kopec, každá buňka má výšku. Poloviční rozsah S a práh jádra proto nedeklaruje; "
            "\u03c3 = 0,25 je i šířka metodiky (6,75 k jejích jednotek při 27 k na jednotku "
            "pravítka)."
        ),
    ),
)


# Where each step sits in the computation, as a methodologist reads it (product owner,
# 2026-10-14): what it is for, the steps it reads, and the audit's point it implements. The
# steps that read a step are derived from these inputs (catalogue.feeds_of).
@dataclass(frozen=True, slots=True)
class _Context:
    role_cs: str
    inputs: tuple[str, ...] = ()
    source_cs: str = ""
    audit: str = ""


#: The new method's steps implement no point of the audit: they are the signed-off AIA
#: Sociomapa methodology's.
_SIGNED_OFF_POINT: Final = "— schválená metodika AIA Sociomapa"

_CONTEXT: Final[dict[str, _Context]] = {
    "method": _Context(
        role_cs="Jméno a otisk metodiky, které si běh připne; podle nich je u každé mapy "
        "vidět, čím byla spočtena.",
        source_cs="metodika v platnosti při spuštění běhu",
    ),
    "f1_declared_scale": _Context(
        role_cs="Převede každé hodnocení na společnou škálu 0-1. Na těchto hodnotách stojí "
        "vše další; výšky objektů je berou přímo.",
        source_cs="odpovědi respondentů a škály, které dotazník deklaruje",
        audit="F1",
    ),
    "f2_person_minmax": _Context(
        role_cs="Srovná přísné a štědré hodnotitele, aby korelace zachytila, co lidé hodnotí "
        "podobně, ne jak přísně.",
        inputs=("f1_declared_scale",),
        audit="F2",
    ),
    "person_centring": _Context(
        role_cs="Odečte od hodnocení každého respondenta jeho vlastní průměr, aby vztahy "
        "zachytily, co lidé hodnotí podobně, ne jak štědře. Kdo nemá rozptyl, vypadne.",
        source_cs="surová hodnocení mapovaných objektů, bez vah respondentů",
        audit=_SIGNED_OFF_POINT,
    ),
    "f11_not_placed": _Context(
        role_cs="Kdo dal všem objektům stejné hodnocení, nenese informaci o vztazích: vypadne "
        "z korelací a terénu, výšky ho ale započtou.",
        inputs=("f1_declared_scale",),
        audit="F11",
    ),
    "f3_correlation": _Context(
        role_cs="Jádro mapy: jak podobně lidé hodnotí dva objekty. Z korelace se počítá "
        "vzdálenost, skóre i stav páru.",
        inputs=("f2_person_minmax", "f11_not_placed"),
        audit="F3",
    ),
    "f3_effective_n": _Context(
        role_cs="Kolik respondentů pár skutečně nese; při vážení méně než počet lidí.",
        # Who rated both objects is read from the person-scaled ratings (pairs.py), not F11.
        inputs=("f2_person_minmax", "f11_not_placed"),
        audit="F3",
    ),
    "f3_interval": _Context(
        role_cs="Nejistota korelace; rozhoduje, zda je pár spolehlivý.",
        inputs=("f3_correlation", "f3_effective_n"),
        audit="F3",
    ),
    "f3_status": _Context(
        role_cs="Třídí páry na spolehlivé, slabé a neznámé. Neznámý pár mapu netvaruje a do "
        "skóre nevstupuje.",
        inputs=("f3_correlation", "f3_effective_n", "f3_interval"),
        audit="F3",
    ),
    "f3_effect_floor": _Context(
        role_cs="Označí páry s prakticky malým vztahem; stav páru nemění, ukáže se vedle něj.",
        inputs=("f3_correlation",),
        audit="F3",
    ),
    "baseline_corrected_relation": _Context(
        role_cs="Jádro mapy podle schválené metodiky: jak podobně lidé hodnotí dva objekty, "
        "očištěno o zápornou korelaci, kterou vytvoří samo centrování.",
        inputs=("person_centring",),
        audit=_SIGNED_OFF_POINT,
    ),
    "reliable_by_fdr": _Context(
        role_cs="Třídí známé páry na spolehlivé a slabé tak, aby mezi spolehlivými bylo "
        "falešných nanejvýš zhruba q.",
        inputs=("baseline_corrected_relation", "noise_rule"),
        audit=_SIGNED_OFF_POINT,
    ),
    "noise_rule": _Context(
        role_cs="Spolehlivý pár musí být silnější, než co dá náhoda po zamíchání jednoho z "
        "objektů.",
        inputs=("baseline_corrected_relation",),
        audit=_SIGNED_OFF_POINT,
    ),
    "layout_pairs": _Context(
        role_cs="Které páry smějí tvarovat rozložení a jakou vahou: i řidčeji hodnocené, "
        "s menší vahou.",
        inputs=("baseline_corrected_relation",),
        audit=_SIGNED_OFF_POINT,
    ),
    "sparse_design": _Context(
        role_cs="Upozorní, když je hodnocení tak řídké, že rozložení stojí na málo párech.",
        inputs=("layout_pairs",),
        audit=_SIGNED_OFF_POINT,
    ),
    "f4_strength": _Context(
        role_cs="Síla a směr vztahu pro výklad mapy; rozložení ani skóre nemění.",
        inputs=("f3_correlation", "f3_status"),
        audit="F4",
    ),
    "f6_mappable": _Context(
        role_cs="Rozhodne, zda se z rodiny objektů dá mapa nakreslit. Když ne, běh to řekne "
        "místo kreslení.",
        inputs=("f3_status",),
        audit="F6",
    ),
    "f6_distance": _Context(
        role_cs="Převede korelaci na vzdálenost, kterou se mapa snaží dodržet: podobně "
        "hodnocené objekty leží blízko sebe.",
        inputs=("f3_correlation", "f3_status"),
        audit="F6",
    ),
    "f6_smacof": _Context(
        role_cs="Najde polohy objektů, které cílové vzdálenosti drží nejlépe. To jsou "
        "souřadnice na mapě.",
        inputs=("f6_distance", "f6_mappable"),
        audit="F6",
    ),
    "object_count_rule": _Context(
        role_cs="Podle počtu objektů vybere, která ze dvou metod mapu nakreslí, a ověří, že "
        "ji vůbec nějaký pár tvaruje.",
        inputs=("layout_pairs",),
        audit=_SIGNED_OFF_POINT,
    ),
    "soft_rank_spearman_layout": _Context(
        role_cs="Rozloží objekty tak, aby u každého pořadí vzdáleností co nejvíc odpovídalo "
        "pořadí jeho vztahů; nesouvisející objekty od sebe odtlačí.",
        inputs=("object_count_rule", "layout_pairs"),
        audit=_SIGNED_OFF_POINT,
    ),
    "interval_mds_layout": _Context(
        role_cs="Pro velmi malé a velmi velké mapy: rozloží objekty tak, aby vzdálenosti "
        "lineárně sledovaly cílové vzdálenosti.",
        inputs=("object_count_rule", "layout_pairs"),
        audit=_SIGNED_OFF_POINT,
    ),
    "ruler_scale": _Context(
        role_cs="Převede mapu na pravítko, aby vzdálenosti byly ve stejných jednotkách jako "
        "cílové vzdálenosti. To jsou souřadnice na mapě.",
        inputs=("soft_rank_spearman_layout", "interval_mds_layout"),
        audit=_SIGNED_OFF_POINT,
    ),
    "f7_stress": _Context(
        role_cs="Měří, kolik musela mapa vzdálenosti zkreslit, aby se vešla do roviny.",
        inputs=("f6_smacof", "f6_distance"),
        audit="F7",
    ),
    "f7_quality": _Context(
        role_cs="Převede Stress-1 na slovo, které vidí čtenář výsledků.",
        inputs=("f7_stress",),
        audit="F7",
    ),
    "f8_scores": _Context(
        role_cs="Jak objekt souvisí s ostatními; podklad pro propojenost 0-100.",
        inputs=("f3_correlation", "f3_status"),
        audit="F8",
    ),
    "f8_height": _Context(
        role_cs="Průměrné hodnocení objektu; výška jeho kopce v terénu.",
        inputs=("f1_declared_scale",),
        audit="F8",
    ),
    "f9_k100": _Context(
        role_cs="Propojenost na stupnici 0-100 s intervalem z převzorkování respondentů.",
        inputs=("f8_scores",),
        audit="F9",
    ),
    "f9_quantile": _Context(
        role_cs="Z převzorkovaných hodnot vybere meze intervalu.",
        inputs=("f9_k100",),
        audit="F9",
    ),
    "f9_rank": _Context(
        role_cs="Seřadí objekty jen tam, kde se jejich intervaly neprotínají.",
        inputs=("f9_quantile",),
        audit="F9",
    ),
    "relative_heights": _Context(
        role_cs="Převede výšky objektů na výšky kopců: nejnižší objekt stojí na prahu, "
        "nejvyšší na 1, aby byl terén čitelný i při malých rozdílech.",
        inputs=("f8_height",),
        audit=_SIGNED_OFF_POINT,
    ),
    "terrain_frame": _Context(
        role_cs="Vybere čtverec, který terén pokryje: kolem objektů, s okrajem, aby se mapa "
        "vešla celá.",
        inputs=("ruler_scale",),
        audit=_SIGNED_OFF_POINT,
    ),
    "f12_envelope": _Context(
        role_cs="Krajina, kterou čtenář vidí: z poloh objektů a jejich výšek vytvoří kopce.",
        inputs=("f6_smacof", "ruler_scale", "f8_height", "relative_heights", "terrain_frame"),
        audit="F12-F13",
    ),
    "f10_placement": _Context(
        role_cs="Návrh: kde by na mapě ležel každý respondent. Zatím se nepočítá.",
        inputs=("f6_smacof", "f2_person_minmax"),
        audit="F10",
    ),
    "support": _Context(
        role_cs="Počty, které mapa uvádí: kdo ji nese, kdo vypadl a jaké je efektivní n.",
        inputs=("f11_not_placed",),
        audit="F11",
    ),
}

_STEPS: Final[tuple[MethodStep, ...]] = tuple(
    replace(
        step,
        role_cs=_CONTEXT[step.id].role_cs,
        inputs=_CONTEXT[step.id].inputs,
        source_cs=_CONTEXT[step.id].source_cs,
        audit=_CONTEXT[step.id].audit,
    )
    for step in _CATALOGUE
)

# The page follows the computation by its stages (product owner, 2026-10-14), no longer the
# audit's F1-F16; each step keeps its audit point (MethodStep.audit). What AIA does not compute
# yet closes the outline, one group per audit point, its proposal in the note.
_GROUPS: Final = (
    StepGroup("M", "Metoda", ("method",)),
    StepGroup(
        "S1",
        "Vstupní hodnocení",
        ("f1_declared_scale", "f2_person_minmax", "person_centring", "f11_not_placed"),
        "Z odpovědí na škálách se stanou čísla 0-1, na kterých stojí vše další.",
    ),
    StepGroup(
        "S2",
        "Vztahy mezi objekty",
        (
            "f3_correlation",
            "f3_effective_n",
            "f3_interval",
            "f3_status",
            "f3_effect_floor",
            "baseline_corrected_relation",
            "reliable_by_fdr",
            "noise_rule",
            "layout_pairs",
            "sparse_design",
            "f4_strength",
        ),
        "Jak podobně lidé hodnotí každé dva objekty, a jak moc se tomu dá věřit.",
    ),
    StepGroup(
        "S3",
        "Rozložení na mapě",
        (
            "f6_mappable",
            "f6_distance",
            "f6_smacof",
            "object_count_rule",
            "soft_rank_spearman_layout",
            "interval_mds_layout",
            "ruler_scale",
        ),
        "Ze vztahů se stanou vzdálenosti a z nich polohy objektů na mapě.",
    ),
    StepGroup(
        "S4",
        "Věrohodnost mapy",
        ("f7_stress", "f7_quality"),
        "Jak věrně mapa v rovině drží vzdálenosti, které měla dodržet.",
    ),
    StepGroup(
        "S5",
        "Skóre a výška objektů",
        ("f8_scores", "f8_height", "f9_k100", "f9_quantile", "f9_rank"),
        "Co mapa o každém objektu říká číslem: souhlasnost, propojenost a výška.",
    ),
    StepGroup(
        "S6",
        "Terén",
        ("relative_heights", "terrain_frame", "f12_envelope"),
        "Krajina kopců nad mapou, kterou vidí čtenář výsledků.",
    ),
    StepGroup(
        "S7",
        "Respondenti a podpora mapy",
        ("f10_placement", "support"),
        "Kde by leželi respondenti a na kolika lidech mapa stojí.",
    ),
    StepGroup(
        "F5",
        "Zatím v AIA není: typ dodané matice (F5)",
        (),
        "Objektová mapa počítá vztahy z hodnocení, dodanou matici nečte. Deklarovaný typ "
        "matice platí pro referenční mapu.",
    ),
    StepGroup(
        "F14",
        "Zatím v AIA není: testy při porovnání oblastí (F14)",
        (),
        "V AIA zatím není (sociomap-formula-corrections.md, krok 4d). Návrh auditu: testovat "
        "jen proměnné, které neurčily polohu, a korigovat Holmem: zamítnout H_(k), právě když "
        "p_(l) ≤ \u03b1 / (|V_test| - l + 1) pro všechna l ≤ k, \u03b1 = 0,05; "
        "nejdřív Cohenovo d s intervalem.",
    ),
    StepGroup(
        "F15",
        "Zatím v AIA není: pořadí hlavních rozdílů (F15)",
        (),
        "V AIA zatím není (krok 4d). Návrh auditu: |d| = |x̄_A - x̄_B| / s_pooled pro čísla, "
        "|h| = |2 arcsin √\u03c0_A - 2 arcsin √\u03c0_B| pro kategorie (maximum přes kategorie).",
    ),
    StepGroup(
        "F16",
        "Zatím v AIA není: cíle rozvinutí po respondentech (F16)",
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
        # Last, so an edit still starts from aia-sociomap-4 (the page offers the first preset).
        Preset("aia-sociomap-5", AIA_SOCIOMAP_V5, _validate),
    ),
    in_force="aia-sociomap-3",
    groups=_GROUPS,
    formulas=SOCIOMAP_FORMULAS,
    editable=True,
    note_cs=(
        "Mapa auditu NPC Sociomapa (kanonická metodika). Každý nový běh si připne "
        "aia-sociomap-3 vedle referenční mapy aia-sociomap-1. Mapu aia-sociomap-3 schválil "
        "vlastník produktu pro zprávy (2026-10-13, registr Sociomap); upravená verze v platnosti "
        "je interní, dokud ji registr neschválí. aia-sociomap-4 počítá totéž, jen má v metodice "
        "i hodnoty, které -3 drží v kódu (minimum objektů, pásma Stress, kvantily K100); úprava "
        "z něj vychází. aia-sociomap-5 počítá vstupy, vztahy, polohy objektů, jejich výšky a "
        "terén podle schválené metodiky AIA Sociomapa (kroky označené „Jen aia-sociomap-5“)."
    ),
)
