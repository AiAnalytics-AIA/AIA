"""The Sociomap's reference map (contract 2, ``aia-sociomap-1``), step by step.

ADR 0023; plan ``methodology-tab.md`` S1b. Every new run pins this map beside the object map:
it is 18.6.6's computation kept EXACT (the golden fixtures F1-F9 and the unit's captures pin
it), so the two can be compared. The audit names several of its formulas as faulty; each step
says which point criticises it, and the object map (module ``sociomap``) is the correction.

Editing this map would make it stop being the reference (ADR 0023 decision 4), so it is shown
and not offered for editing; a copy of it can be the base of an edited method.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..sociomap.specification import (
    AIA_SOCIOMAP_V1,
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

__all__ = ["SOCIOMAP_REFERENCE"]

_S: Final = "aia_core.domain.sociomap"
_T: Final = "packages/aia_core/tests"


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, SociomapSpec | SociomapSpecV3):
        raise TypeError(f"not a Sociomap specification: {type(spec).__name__}")
    require_supported(spec)


def _rule(rule_id: str, note_cs: str = "") -> Evidence:
    return Evidence(EvidenceKind.REGISTER_RULE, rule_id, note_cs)


def _fixture(name: str) -> Evidence:
    return Evidence(EvidenceKind.FIXTURE, name, "packages/aia_core/tests/fixtures/sociomap/")


def _legacy(where: str) -> Evidence:
    return Evidence(EvidenceKind.LEGACY_PORT, where, "Převzato z 18.6.6 přesně (EXACT).")


_D6: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "docs/architecture/sociomapa-methodology-decision.md § 1",
    "Rozhodnutí AIA, ne převzatá funkce.",
)

_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="method",
        title_cs="Pojmenování metody",
        formula_latex=r"\text{metoda} = \text{methodology\_version}",
        implements=f"{_S}.specification:SociomapSpec",
        source_sha256="70e2ca702cea3acaf42d4c9e082e25456752fb130bcff8a79edf82a6400154e8",
        parameters=(ParameterRef("methodology_version", "Verze metodiky"),),
        evidence=(_D6,),
        tests=(f"{_T}/test_sociomap_methods.py::test_the_v1_preset_fingerprint_has_not_moved",),
    ),
    # ------------------------------------------------------------------ inputs
    MethodStep(
        id="weights",
        title_cs="Váhy respondentů",
        formula_latex=r"w_k \leftarrow w_k \cdot \frac{N}{\sum_l w_l}",
        implements="aia_core.domain.research_sociomap:battery_sociomap",
        source_sha256="da40e7aa1a961d47d191e425dbb923f20af780e718e7fae597138a5d57ccc3db",
        symbols=(Symbol(r"N", "počet respondentů baterie"),),
        evidence=(_rule("LEGACY-R2"), _legacy("project_engine.py:34-35 (vaha)")),
        tests=(
            f"{_T}/test_research_sociomap.py::test_the_map_is_the_engines_under_the_adopted_preset_and_internal_only",
        ),
        note_cs="Neplatná (nekonečná) váha se v matici vztahů čte jako 1.",
    ),
    MethodStep(
        id="scale",
        title_cs="Deklarovaná škála hodnocení",
        formula_latex=(
            r"a_{kj} \in [s^{\min}, s^{\max}],\quad "
            r"a_{kj} \notin [s^{\min}, s^{\max}] \Rightarrow \text{odmítnuto, ne oříznuto}"
        ),
        implements=f"{_S}.engine:_check_scale",
        source_sha256="eedd2d4a2d4df28cf781e29e3ae834f9c144a748f8a739292752dff829866352",
        parameters=(
            ParameterRef("ratings.rating_scale_min", "Dolní konec škály", "body škály"),
            ParameterRef("ratings.rating_scale_max", "Horní konec škály", "body škály"),
        ),
        evidence=(
            _rule(
                "AUDIT-F1", "Deklarované konce škály; referenční mapa hodnocení na 0-1 nepřevádí."
            ),
            _fixture("F1"),
            _fixture("F8"),
        ),
        tests=(
            f"{_T}/test_sociomap_engine.py::test_a_rating_off_the_declared_scale_is_refused",
            f"{_T}/test_research_sociomap.py::test_the_battery_scale_is_the_datas_and_is_recorded",
        ),
        note_cs=(
            "Výzkumný krok přepíše oba konce škálou baterie, takže mapa běhu nese škálu dat, "
            "ne 1-10 z presetu."
        ),
    ),
    MethodStep(
        id="placeability",
        title_cs="Kdo se dá umístit",
        formula_latex=(
            r"k \text{ neumístěn} \iff \#\{j : a_{kj} \text{ pozorováno}\} < 2"
            r"\;\vee\; \max_j a_{kj} = \min_j a_{kj}"
        ),
        implements=f"{_S}.engine:_placeability",
        source_sha256="80baacdb7e98e699f6a02ae6c7bf33ccd79e0cb6ec322aabb92ad47d5ebd0cd2",
        evidence=(_rule("AUDIT-F11"),),
        tests=(
            f"{_T}/test_sociomap_engine.py::test_a_straight_liner_below_the_top_is_not_placed",
            f"{_T}/test_sociomap_engine.py::test_every_respondent_is_placed_or_excluded",
        ),
    ),
    # ------------------------------------------------------------------ relations
    MethodStep(
        id="relation_matrix",
        title_cs="Matice vztahů objektů (stupnice 1-10)",
        formula_latex=(
            r"\text{rel}_{ij} = \begin{cases} 5{,}5 & \text{méně než 5 společných hodnotitelů} \\"
            r" \operatorname{clip}_{[1,10]}\!\left(1 + 9\,\frac{r_{ij} + 1}{2}\right)"
            r" & \text{jinak} \end{cases}"
        ),
        implements=f"{_S}.pairs:derive_relation_matrix",
        source_sha256="f108245e0be7e8016248075efa15e8bcc985f7e26202b4088b26e289235c7bec",
        symbols=(Symbol(r"r_{ij}", "vážená Pearsonova korelace na surových hodnoceních"),),
        evidence=(
            _legacy("sociomap.py:derive_relation_matrix"),
            _rule("AUDIT-F2", "Audit: korelace na surových hodnoceních nese hodnoticí zvyklosti."),
            _rule("AUDIT-F3", "Audit: 5,5 zapisuje „nevíme“ jako středně silný vztah."),
            _rule("AUDIT-F4", "Audit: stupnice 1-10 skrývá směr vztahu."),
        ),
        tests=(
            f"{_T}/test_research_sociomap.py::test_the_relation_matrix_is_exact_against_the_unit",
            f"{_T}/test_research_sociomap.py::test_too_few_common_ratings_is_the_units_neutral_relation",
        ),
        note_cs="Hranice 5 hodnotitelů a hodnota 5,5 jsou přímo v kódu převzaté funkce.",
    ),
    MethodStep(
        id="coercion",
        title_cs="Převod matice na stupnici 1-10",
        formula_latex=(
            r"R'_{ij} = \begin{cases} 1 + 9x & \text{všechny mimo diagonálu v } [0,1] \\"
            r" 1 + 9\,\frac{x+1}{2} & \text{všechny v } [-1,1] \\"
            r" \operatorname{clip}_{[1,10]}(x) & \text{jinak} \end{cases},"
            r"\quad R'_{ii} = 0"
        ),
        implements=f"{_S}.relations:coerce_relation_scale_1_10",
        source_sha256="ce1e1a5b6543131758bc4e42a05ff0ce4d1263a6e1157d15cea9fb8f84eacf4f",
        parameters=(
            ParameterRef("relation.scale_coercion", "Převod matice"),
            ParameterRef("relation.missing_data_policy", "Chybějící buňka matice"),
        ),
        constants=(
            ConstantRef(f"{_S}.relations:_NAN_SENTINEL", "Náhrada za NaN"),
            ConstantRef(f"{_S}.relations:_POS_INF_SENTINEL", "Náhrada za +∞"),
            ConstantRef(f"{_S}.relations:_NEG_INF_SENTINEL", "Náhrada za -∞"),
            ConstantRef(f"{_S}.relations:MIN_RELATION_OBJECTS", "Nejméně objektů"),
        ),
        evidence=(
            _fixture("F1"),
            _rule("AUDIT-F5", "Audit: typ matice se hádá z hodnot; má být deklarován."),
        ),
        tests=(
            f"{_T}/test_sociomap_relations.py::test_f1_coercion_matches_the_reference",
            f"{_T}/test_sociomap_relations.py::test_f1_covers_every_branch",
            f"{_T}/test_sociomap_engine.py::test_a_missing_relation_cell_is_refused_by_default",
        ),
    ),
    MethodStep(
        id="projection",
        title_cs="Vzájemný vztah pro polohu",
        formula_latex=(
            r"\mu_{ij} = \operatorname{clip}_{[0,1]}"
            r"\!\left(\frac{(R'_{ij} + R'_{ji})/2 - 1}{9}\right)"
        ),
        implements=f"{_S}.relations:mutual_from_1_10",
        source_sha256="d5ae50da12aedcbe09ad71770657ee3f630d1b3d8275376791bffaa3dd312434",
        parameters=(ParameterRef("relation.position_projection", "Projekce pro polohu"),),
        evidence=(_rule("LEGACY-R3"), _fixture("F2")),
        tests=(f"{_T}/test_sociomap_relations.py::test_f2_mutual_relation_matches_the_reference",),
        note_cs="Ukládá se, ale polohu neurčuje: tu dává rozvinutí hodnocení níže.",
    ),
    # ------------------------------------------------------------------ layout
    MethodStep(
        id="dissimilarity",
        title_cs="Cíl rozvinutí z hodnocení",
        formula_latex=r"\delta_{kj} = s^{\max} - a_{kj}\quad\text{přes pozorované buňky}",
        implements=f"{_S}.layout:scale_top_dissimilarity",
        source_sha256="bec759d7150e79f0dd9ff838d9eced4e30ee23976405546a2ce5984ac9ed8121",
        parameters=(
            ParameterRef("ratings.dissimilarity", "Cíl rozvinutí"),
            ParameterRef("ratings.ipsatize", "Ipsatizace"),
            ParameterRef("ratings.missing_data_policy", "Chybějící hodnocení"),
        ),
        evidence=(_D6, _fixture("F4"), _rule("AUDIT-F16")),
        tests=(f"{_T}/test_sociomap_layout.py::test_scale_top_dissimilarity",),
        note_cs="Ipsatizace (F3) je převzatá, ale s tímto cílem ji specifikace odmítne.",
    ),
    MethodStep(
        id="unfolding",
        title_cs="Řádkově podmíněné rozvinutí (respondenti i objekty)",
        formula_latex=(
            r"\hat d_{kj} = b_k \delta_{kj},\ \sum_k b_k^2 \lVert\delta_k\rVert^2 = C;\quad "
            r"\min \sum_{k,j} (\hat d_{kj} - \lVert x_k - y_j\rVert)^2;\quad "
            r"\frac{\sigma_{t-1} - \sigma_t}{C} < \varepsilon"
        ),
        implements=f"{_S}.layout:fit_rowcond_unfolding",
        source_sha256="b6636d7c1a6f71421fcc3c8d5b1237c8cd27cc5c164b5f0e8c28c1582e2926fc",
        symbols=(
            Symbol(r"b_k", "měřítko řádku respondenta k"),
            Symbol(r"C", "počet pozorovaných buněk"),
            Symbol(r"x_k, y_j", "poloha respondenta a objektu"),
        ),
        parameters=(
            ParameterRef("layout.algorithm", "Algoritmus rozložení"),
            ParameterRef("layout.parameters.dimensions", "Rozměry"),
            ParameterRef("layout.parameters.max_iterations", "Nejvýše iterací"),
            ParameterRef("layout.parameters.convergence_tolerance", "Tolerance zastavení"),
            ParameterRef("layout.seed", "Semínko"),
        ),
        evidence=(_D6, _rule("AUDIT-F16")),
        tests=(
            f"{_T}/test_sociomap_layout.py::test_recovers_the_geometry_that_generated_the_data",
            f"{_T}/test_sociomap_layout.py::test_stress_never_increases_with_more_iterations",
            f"{_T}/test_sociomap_layout.py::test_gauge_is_fixed",
            f"{_T}/test_sociomap_engine.py::test_golden_layout_and_terrain_are_reproduced",
        ),
        note_cs=(
            "Start: klasické škálování profilů, respondenti jako vážený průměr objektů. Kroky: "
            "majorizace respondentů, objektů, pak měřítek řádků. Výsledek se vycentruje, otočí "
            "do hlavních os a zrcadlí podle třetího momentu. Bez náhody (semínko null)."
        ),
    ),
    MethodStep(
        id="stress",
        title_cs="Stress-1 rozvinutí",
        formula_latex=(
            r"\text{Stress-1} = \sqrt{\frac{\sum (\hat d_{kj} - d_{kj})^2}{\sum d_{kj}^2}}"
            r"\quad\text{přes pozorované buňky}"
        ),
        implements=f"{_S}.layout:stress_1",
        source_sha256="6fc92ed373138105d47a1d9d37572d7cc3b5ceab7cc9af82295acfbb49e53512",
        evidence=(_rule("AUDIT-F7"),),
        tests=(
            f"{_T}/test_sociomap_layout.py::test_reported_stress_matches_the_returned_configuration",
        ),
    ),
    MethodStep(
        id="frame",
        title_cs="Rámec mapy",
        formula_latex=r"s = \frac{\text{rozsah}}{\max |c|}\quad\text{přes všechny souřadnice}",
        implements=f"{_S}.engine:compute_sociomap",
        source_sha256="4352fbe2f1cfa7f1c92688466a81a59542bbad6adf810bb9086ea9fb44572189",
        parameters=(
            ParameterRef("layout.map_frame.method", "Rámec mapy"),
            ParameterRef("layout.map_frame.extent", "Rozsah", "mapové jednotky"),
        ),
        evidence=(
            _D6,
            _rule("AUDIT-F6", "Audit: natažení na poloměr brání porovnání map."),
        ),
        tests=(f"{_T}/test_sociomap_engine.py::test_coordinates_fit_the_declared_map_frame",),
    ),
    # ------------------------------------------------------------------ scores
    MethodStep(
        id="object_metric",
        title_cs="Která metrika dává výšku a barvu objektu",
        formula_latex=r"\text{výška}_j, \text{barva}_j \in \{\text{zvolená metrika objektu}\}",
        implements=f"{_S}.metrics:object_metric",
        source_sha256="bfbefd65abf19999eb6a07b0b0903274fe09cb1e4c516f0caa48f3a444bdc00e",
        parameters=(
            ParameterRef("metrics.object_height_metric", "Metrika výšky"),
            ParameterRef("metrics.object_colour_metric", "Metrika barvy"),
        ),
        evidence=(_rule("LEGACY-R4"), _fixture("F6")),
        tests=(
            f"{_T}/test_sociomap_metrics.py::test_unknown_metric_id_is_refused_not_turned_into_a_tscore",
        ),
    ),
    MethodStep(
        id="relation_classic",
        title_cs="Celkové relační skóre",
        formula_latex=r"\text{classic}_i = \sum_j \left(R'_{ij} + R'_{ji}\right)",
        implements=f"{_S}.metrics:relation_classic",
        source_sha256="75349f84132a258a653947e8cb284455fc087ac9631cc32fdca50e3be28cac2c",
        evidence=(
            _fixture("F6"),
            _rule("AUDIT-F8", "Audit: kontextové objekty mění pořadí; má jít o PRIMÁRNÍ páry."),
        ),
        tests=(f"{_T}/test_sociomap_metrics.py::test_f6_object_metrics_match_the_reference",),
    ),
    MethodStep(
        id="tscore",
        title_cs="Normativní skóre (T-skór)",
        formula_latex=(
            r"T_i = 50 + 10\,\frac{v_i - \mu}{\sigma},\quad \sigma \text{ populační};"
            r"\quad \sigma < \varepsilon \Rightarrow T_i = 50"
        ),
        implements=f"{_S}.metrics:tscore",
        source_sha256="a5f543b6740edec57cff7419cf8eeb48b5ac57bfe2d9196657712f4c2637bb28",
        constants=(
            ConstantRef(f"{_S}.metrics:ZERO_VARIANCE_EPSILON", "Nulový rozptyl pod"),
            ConstantRef(f"{_S}.metrics:TSCORE_ZERO_VARIANCE", "T-skór při nulovém rozptylu"),
        ),
        evidence=(
            _fixture("F6"),
            _rule("AUDIT-F9", "Audit: relativní skóre; má jít o pevnou škálu 0-100 s intervalem."),
        ),
        tests=(f"{_T}/test_sociomap_metrics.py::test_tscore_has_mean_fifty_and_sd_ten",),
    ),
    MethodStep(
        id="mean_rating",
        title_cs="Průměrné hodnocení objektu",
        formula_latex=r"\bar a_j = \frac{1}{n_j}\sum_{k} a_{kj},\quad n_j = \#\text{pozorovaných}",
        implements=f"{_S}.metrics:object_rating_summaries",
        source_sha256="6532c9f3db04cc9df23cce989217acddb488be1ec30acdfe6beb040ef6582a1b",
        evidence=(_rule("LEGACY-R7"), _D6),
        tests=(f"{_T}/test_sociomap_metrics.py::test_rating_summaries_use_observed_cells_only",),
        note_cs="Nevážený průměr; matice vztahů výše počítá vážený.",
    ),
    # ------------------------------------------------------------------ terrain
    MethodStep(
        id="terrain_respondents",
        title_cs="Terén hustoty respondentů",
        formula_latex=(
            r"h(q) = \sum_{k} \kappa(q, x_k),\quad "
            r"\kappa = e^{-\lVert q - x\rVert^2 / 2\sigma^2}\ (\text{vynechá se pod prahem}),"
            r"\quad z = \operatorname{norm}(h)\cdot z_{\text{scale}}"
        ),
        implements=f"{_S}.terrain:compute_terrain",
        source_sha256="879f9f3fe2dc085c2cc8fa13182c34c83aa53deff8cbaace16d3fc6e01683ad4",
        parameters=(
            ParameterRef("terrain.respondent.grid_resolution", "Rozlišení mřížky N"),
            ParameterRef("terrain.respondent.half_extent", "Poloviční rozsah", "mapové jednotky"),
            ParameterRef("terrain.respondent.sigma", "Šířka jádra", "mapové jednotky"),
            ParameterRef("terrain.respondent.kernel_cutoff", "Práh jádra"),
            ParameterRef("terrain.respondent.z_scale", "Převýšení"),
        ),
        evidence=(_rule("LEGACY-R5"), _fixture("F7")),
        tests=(
            f"{_T}/test_sociomap_terrain.py::test_f7_every_sample_matches",
            f"{_T}/test_sociomap_terrain.py::test_empty_terrain_is_flat_at_zero_not_a_plateau",
        ),
    ),
    MethodStep(
        id="terrain_objects",
        title_cs="Terén objektů (vážený průměr)",
        formula_latex=(
            r"h(q) = \frac{\sum_j \kappa(q, y_j)\, v_j}{\sum_j \kappa(q, y_j)},"
            r"\quad \sum_j \kappa = 0 \Rightarrow \text{bez výšky}"
        ),
        implements=f"{_S}.terrain:_accumulate",
        source_sha256="1a6e72708598c90ab95ad49c7e7677737bc28297733ff41742d14d5626c5e541",
        parameters=(
            ParameterRef("terrain.object.grid_resolution", "Rozlišení mřížky N"),
            ParameterRef("terrain.object.half_extent", "Poloviční rozsah", "mapové jednotky"),
            ParameterRef("terrain.object.sigma", "Šířka jádra", "mapové jednotky"),
            ParameterRef("terrain.object.kernel_cutoff", "Práh jádra"),
            ParameterRef("terrain.object.z_scale", "Převýšení"),
        ),
        evidence=(
            _fixture("F8"),
            _rule("AUDIT-F12", "Audit: průměr kopců stírá výšky; má jít o obálku."),
        ),
        tests=(
            f"{_T}/test_sociomap_terrain.py::test_f8_height_to_elevation_chain",
            f"{_T}/test_sociomap_terrain.py::test_weighted_mean_lies_between_the_object_values",
        ),
    ),
    MethodStep(
        id="normaliser",
        title_cs="Normalizace výšky terénu",
        formula_latex=(
            r"\operatorname{norm}(x) = \begin{cases}"
            r"\operatorname{clip}_{[0,1]}\frac{x - lo}{hi - lo}\ (0{,}5 \text{ při } hi = lo)"
            r" & \text{range} \\"
            r"\operatorname{clip}_{[0,1]}\frac{x - a}{b - a} & \text{absolute} \\"
            r"\operatorname{clip}_{[0,1]}\left(0{,}5 + \frac{z}{5}\right),"
            r"\ z = \frac{x-\mu}{\sigma} & \text{sigma} \\"
            r"\#\{v \le x\} / n & \text{percentile} \end{cases}"
        ),
        implements=f"{_S}.metrics:build_normalizer",
        source_sha256="22fafbf0d80250de2e10eae2af0f31f1f4c33319b3f267c3e8a96e09a4f77e40",
        parameters=(ParameterRef("terrain.normalization", "Normalizace"),),
        evidence=(_rule("LEGACY-R6"), _fixture("F5")),
        tests=(
            f"{_T}/test_sociomap_metrics.py::test_f5_normaliser_matches_the_reference",
            f"{_T}/test_sociomap_metrics.py::test_sigma_mode_spans_plus_minus_two_and_a_half_sd",
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("M", "Metoda", ("method",)),
    StepGroup("V", "Vstupy a škála", ("weights", "scale", "placeability")),
    StepGroup("R", "Vztahy objektů", ("relation_matrix", "coercion", "projection")),
    StepGroup("L", "Rozvinutí a rámec", ("dissimilarity", "unfolding", "stress", "frame")),
    StepGroup("S", "Skóre objektů", ("object_metric", "relation_classic", "tscore", "mean_rating")),
    StepGroup("T", "Terén", ("terrain_respondents", "terrain_objects", "normaliser")),
)

SOCIOMAP_REFERENCE: Final = MethodModule(
    id="sociomap_reference",
    title_cs="Sociomapa: referenční mapa (18.6.6)",
    steps=_STEPS,
    presets=(Preset("aia-sociomap-1", AIA_SOCIOMAP_V1, _validate),),
    in_force="aia-sociomap-1",
    groups=_GROUPS,
    note_cs=(
        "Výpočet 18.6.6 zachovaný přesně (fixtury F1-F9), aby šel porovnat s objektovou mapou. "
        "Audit u několika kroků uvádí vadu; náprava je objektová mapa. Referenční mapa se "
        "needituje, aby zůstala referencí."
    ),
)
