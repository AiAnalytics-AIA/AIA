"""The experimental Sociomapping (``aia_hmodel_candidate_v1``), step by step.

ADR 0023; plan ``methodology-tab.md`` S1c. A run computes it beside its Sociomap when the
study asks for it (``research_sociomapping.py``): declared relations, AIA's own H-Model
layout, heights and coherences. SOMECS does not document how it searches for a layout
(AIA-H8), so the layout is AIA's candidate (AIA-H9, proposed); every result says
``EXPERIMENTAL_AIA`` and is never client facing.

Shown, not edited: the candidate is an experiment whose objective and search are open
questions, not a methodology a run adopts (ADR 0023 decision 4). Its parameters are
``CandidateParameters``, the values every result records.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..sociomap.hmodel_candidate import CANDIDATE_METHOD, CandidateParameters
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

__all__ = ["SOCIOMAPPING"]

_S: Final = "aia_core.domain.sociomap"
_R: Final = "aia_core.domain.research_sociomapping"
_C: Final = f"{_S}.hmodel_candidate"
_T: Final = "packages/aia_core/tests"


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, CandidateParameters):
        raise TypeError(f"not the H-Model candidate's parameters: {type(spec).__name__}")


def _rule(rule_id: str, note_cs: str = "") -> Evidence:
    return Evidence(EvidenceKind.REGISTER_RULE, rule_id, note_cs)


_DOC: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "docs/architecture/sociomapping-hmodel.md § 4",
    "Kandidát AIA, ne metoda SOMECS.",
)

_STEPS: Final[tuple[MethodStep, ...]] = (
    # ------------------------------------------------------------------ inputs
    MethodStep(
        id="complete_cases",
        title_cs="Jen úplní respondenti, bez vah",
        formula_latex=(r"K = \{k : a_{kj}\ \text{zodpovězeno pro všechna}\ j\},\quad w_k = 1"),
        implements=f"{_R}:battery_sociomapping",
        source_sha256="fcb6824892daa480e982997811092e2d0a22b358fc439ed7ec8cafdec99172cc",
        symbols=(Symbol("K", "respondenti, kteří ohodnotili každý objekt sady"),),
        constants=(
            ConstantRef(f"{_R}:_COMPLETE_CASES_RULE", "Pravidlo vyřazení"),
            ConstantRef(f"{_R}:_FEW_OBJECTS", "Méně umístěných objektů: mapa se označí"),
        ),
        evidence=(
            _rule("AIA-D2", "RTS sbírá každou odpověď; AIA drží jen úplné a ostatní počítá."),
        ),
        tests=(
            f"{_T}/test_research_sociomapping.py::test_difficult_answers_are_kept_named_and_explained",
            f"{_T}/test_research_sociomapping.py::test_insufficient_support_is_not_mapped_and_says_why",
        ),
        note_cs=(
            "Váhy respondentů se nepoužijí (žádný zdroj Sociomapu neváží, M7). Sada pod tři "
            "objekty nebo pod dva úplné respondenty se nemapuje a výsledek řekne proč."
        ),
    ),
    MethodStep(
        id="scale",
        title_cs="Odpovědi na škále sady",
        formula_latex=r"x_{kj} = \frac{a_{kj} - s^{\min}}{s^{\max} - s^{\min}}",
        implements=f"{_S}.fuzzy:rts_scale_answers",
        source_sha256="fd203e7bb93a530834f36c900900efe2fa447fe037ca4a6bb298a7361fc6963d",
        evidence=(_rule("RTS-N1"),),
        tests=(
            f"{_T}/test_research_sociomapping.py::test_relations_and_heights_match_an_independent_computation",
        ),
    ),
    # --------------------------------------------------------------- relations
    MethodStep(
        id="correlations",
        title_cs="Korelace objektů",
        formula_latex=r"v_{rs} = \operatorname{corr}(x_{\cdot r}, x_{\cdot s})",
        implements=f"{_S}.fuzzy:rts_object_correlations",
        source_sha256="ba7df2fbc7f3aecf9d52e0131eaf2eb2621ea5ec8bf7015d4fc190da8ca14dc5",
        evidence=(_rule("RTS-O1"),),
        tests=(
            f"{_T}/test_research_sociomapping.py::test_relations_and_heights_match_an_independent_computation",
        ),
        note_cs="Pearsonova korelace se znaménkem; nic se neořezává ani neposouvá.",
    ),
    MethodStep(
        id="declared",
        title_cs="Deklarovaná matice vztahů",
        formula_latex=(
            r"V = (v_{rs}),\quad v_{rs}\ \text{nedefinováno} \Rightarrow \text{pojmenováno, "
            r"nedoplněno}"
        ),
        implements=f"{_S}.declared:declared_from_correlations",
        source_sha256="3272d6d6c5471734c704d77a23ef8a2824fe27f6802f6279db5f5ad545ee25a9",
        evidence=(_rule("AIA-D1"),),
        tests=(
            f"{_T}/test_sociomapping_declared.py::test_correlations_stay_signed_and_undefined_pairs_keep_their_reason",
        ),
    ),
    # ------------------------------------------------------------------ layout
    MethodStep(
        id="accuracy",
        title_cs="Přesnost rozložení (cíl hledání)",
        formula_latex=(
            r"A = \rho_S\big(v_{rs},\ -d_{rs}\big)\quad\text{přes definované uspořádané páry}"
        ),
        implements=f"{_S}.hmodel:hmodel_accuracy",
        source_sha256="a3936fe51d510e607147c6a41f6c86d8537ca4a23e1217ffd650db77dd030cda",
        symbols=(
            Symbol(r"\rho_S", "Spearmanova korelace s průměrnými pořadími"),
            Symbol(r"d_{rs}", "vzdálenost objektů na mapě"),
        ),
        evidence=(_rule("SOMECS-H3"), _rule("QED-H2")),
        tests=(
            f"{_T}/test_sociomapping_hmodel_accuracy.py::test_somecs_fig22_layout_scores_as_somecs_lists_it",
            f"{_T}/test_sociomapping_hmodel_accuracy.py::test_accuracy_ignores_rotation_translation_reflection_and_scale",
        ),
        note_cs="Všechny body váží stejně; důležitost bodu (SOMECS, s. 56) se nemodeluje.",
    ),
    MethodStep(
        id="placeable",
        title_cs="Objekty, které nejde umístit",
        formula_latex=r"j\ \text{bez definovaného vztahu} \Rightarrow \text{neumístěn, s důvodem}",
        implements=f"{_C}:_placeable",
        source_sha256="1dd0accd503b2417744a16fd92494bce71fa8f5529f169ef63c6377df6fe3a3c",
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_a_constant_object_is_listed_unplaced_with_its_reason",
        ),
        note_cs="Nikdy se nevypustí potichu ani nepoloží na výchozí místo.",
    ),
    MethodStep(
        id="starts",
        title_cs="Starty hledání",
        formula_latex=(
            r"\text{klasické MDS na pořadích} \;\cup\; \{U(\text{seed} + k)\}_{k=1}^{R}"
        ),
        implements=f"{_C}:_classical_start",
        source_sha256="ac386127825d1a1716f19d111a363c19a99f1682cedd943527cba58a383199e8",
        symbols=(Symbol("R", "počet náhodných startů"),),
        parameters=(
            ParameterRef("seed", "Semínko náhodných startů"),
            ParameterRef("random_starts", "Počet náhodných startů"),
        ),
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_random_matrices_never_end_below_the_classical_mds_baseline",
        ),
        note_cs=(
            "Vyhrává nejvyšší konečná přesnost, při shodě dřívější start. Přesnost startu "
            "klasickým MDS se uvádí jako základna."
        ),
    ),
    MethodStep(
        id="smooth",
        title_cs="Hladká fáze",
        formula_latex=r"\max\ \operatorname{corr}(L, -D)",
        implements=f"{_C}:_smooth",
        source_sha256="b5b2e6cd75f10b7b666479aadd7c924eb7542bf542b0c13247f27a0613071b78",
        symbols=(Symbol("L", "pevná průměrná pořadí definovaných vztahů"),),
        parameters=(ParameterRef("smooth_iterations", "Iterace hladké fáze"),),
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_planted_symmetric_relations_are_recovered_exactly",
        ),
        note_cs="Gradientní výstup: po úspěchu krok krát 1,2, po neúspěchu poloviční.",
    ),
    MethodStep(
        id="ordinal",
        title_cs="Ordinální větev",
        formula_latex=(
            r"\min \sum (d_{rs} - \hat d_{rs})^2,\quad \hat d\ \text{izotonní, ostře rostoucí "
            r"o mezeru}\ g"
        ),
        implements=f"{_C}:_ordinal",
        source_sha256="ffe73908e9ce18203c4dc26883a6e8c5d7ff1e6691c8b10d8e3686c443134e34",
        symbols=(Symbol("g", "mezera mezi po sobě jdoucími cíli"),),
        parameters=(
            ParameterRef("ordinal_iterations", "Iterace ordinální fáze"),
            ParameterRef("ordinal_gap", "Mezera g"),
        ),
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_planted_symmetric_relations_are_recovered_exactly",
        ),
        note_cs="Z hladkého rozložení vedou dvě větve, přímá a ordinální; ponechá se lepší.",
    ),
    MethodStep(
        id="exact",
        title_cs="Přesná fáze",
        formula_latex=(
            r"\text{bod po bodu: nejlepší z}\ m\ \text{posunů o}\ \delta\ \text{zvyšující}\ A;"
            r"\quad \delta \leftarrow \delta/2\ \text{až po}\ \delta_{\min}"
        ),
        implements=f"{_C}:_exact",
        source_sha256="cf676542df87449d4a63cd6aa558075caa8b04ad71ca4dfacb996743047bac2d",
        symbols=(Symbol("m", "počet směrů"), Symbol(r"\delta", "krok")),
        parameters=(
            ParameterRef("exact_max_sweeps", "Nejvýše průchodů"),
            ParameterRef("directions", "Počet směrů m"),
            ParameterRef("initial_step", "Počáteční krok", "násobek RMS poloměru startu"),
            ParameterRef("min_step", "Nejmenší krok"),
        ),
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_fig22_a_provisional_comparison_not_a_target",
        ),
    ),
    MethodStep(
        id="repair",
        title_cs="Oprava párů mimo pořadí",
        formula_latex=(
            r"\text{kloub s malou rezervou na párech mimo pořadí;}\ "
            r"\text{ponechán jen když}\ A\uparrow"
        ),
        implements=f"{_C}:_repair",
        source_sha256="5f563d9afac07b0a38e3fa6abfedc9444629dcd8a1bf5629f53b9536efd1d432",
        parameters=(ParameterRef("repair_rounds", "Kola opravy"),),
        evidence=(_rule("AIA-H9"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_asymmetric_planted_relations_expose_pooled_versus_per_point",
        ),
    ),
    MethodStep(
        id="frame",
        title_cs="Rámec mapy",
        formula_latex=(
            r"\text{vystředit, otočit na hlavní osy, třetí moment} \ge 0,\ "
            r"\text{měřítko do}\ [0{,}05;\ 0{,}95]"
        ),
        implements=f"{_C}:_frame",
        source_sha256="09aed091ddb59aa9ea274bc29ed37784d6f7ae6243974ef3523c3df15f4cd6fd",
        constants=(ConstantRef(f"{_C}:_FRAME", "Rozsah rámce"),),
        evidence=(_rule("SOMECS-H7"),),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_the_result_is_deterministic_framed_and_says_what_it_is",
        ),
        note_cs="Přesnost A se rámcem nemění.",
    ),
    MethodStep(
        id="search",
        title_cs="Hledání jako celek a jeho status",
        formula_latex=(
            r"\text{výsledek} = \arg\max_{\text{starty, větve}} A,\ "
            r"\text{status EXPERIMENTAL\_AIA}"
        ),
        implements=f"{_C}:fit_hmodel_candidate",
        source_sha256="18d30f799fb56f8be4e8c28ed42303a57cfc180556fd304eabd07b6582cda8d8",
        constants=(
            ConstantRef(f"{_C}:CANDIDATE_METHOD", "Verze metody"),
            ConstantRef(f"{_C}:CANDIDATE_STATUS", "Status"),
        ),
        evidence=(
            _rule("AIA-H8", "Jak SOMECS hledá rozložení, není zdokumentováno."),
            _rule("AIA-H9"),
            _rule("SOMECS-H6"),
            _DOC,
        ),
        tests=(
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_reordered_objects_give_the_same_map_reported_in_the_callers_order",
            f"{_T}/test_sociomapping_hmodel_candidate.py::test_the_result_is_deterministic_framed_and_says_what_it_is",
        ),
        note_cs=(
            "Objekty se zpracují v kanonickém pořadí (podle id), takže jiné pořadí na vstupu "
            "dá stejnou mapu."
        ),
    ),
    # ------------------------------------------------------ heights, coherences
    MethodStep(
        id="heights",
        title_cs="Výšky objektů",
        formula_latex=r"h_j = \frac{1}{|K|}\sum_{k \in K} x_{kj}",
        implements=f"{_S}.heights:object_average_answers",
        source_sha256="fb41ccae8efa407c138ce56b940de34836a30564b5aebfb10a3d988b5aaa244e",
        evidence=(_rule("RTS-W3"),),
        tests=(
            f"{_T}/test_research_sociomapping.py::test_relations_and_heights_match_an_independent_computation",
        ),
    ),
    MethodStep(
        id="fuzzy",
        title_cs="Matice vztahů 0-1",
        formula_latex=(
            r"v_{rs} \in [0, 1]\ \text{jen když každá korelace je definovaná a nezáporná}"
        ),
        implements=f"{_S}.fuzzy:rts_fuzzy_from_correlations",
        source_sha256="a5821d213d6799adec929c857854886614b864d6ff58f95e9dc4af7d8402cf30",
        evidence=(_rule("RTS-O2"),),
        tests=(
            f"{_T}/test_research_sociomapping.py::test_negative_correlations_alone_block_the_0_1_matrix_by_name_not_the_map",
        ),
        note_cs="Jinak se uvede důvod (M12) a záporné páry zůstanou vidět.",
    ),
    MethodStep(
        id="coherences",
        title_cs="Koherence",
        formula_latex=r"\text{třídy}\ \alpha\text{-řezů matice 0-1, od nejvyšší úrovně}",
        implements=f"{_S}.coherence:coherences",
        source_sha256="e50ba558dee1b2a40ae742da63d04b8b704e2b8814ac5855cd524afa81bb9b67",
        evidence=(_rule("SOMECS-C1"),),
        tests=(
            f"{_T}/test_sociomap_coherence.py::test_the_help_example_is_reproduced_exactly",
            f"{_T}/test_sociomap_coherence.py::test_alpha_cuts_are_the_classes_at_each_level",
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("V", "Vstupy", ("complete_cases", "scale")),
    StepGroup("R", "Vztahy objektů", ("correlations", "declared")),
    StepGroup(
        "H",
        "Rozložení (H-Model, kandidát AIA)",
        (
            "accuracy",
            "placeable",
            "starts",
            "smooth",
            "ordinal",
            "exact",
            "repair",
            "frame",
            "search",
        ),
    ),
    StepGroup("S", "Výšky a koherence", ("heights", "fuzzy", "coherences")),
)

SOCIOMAPPING: Final = MethodModule(
    id="sociomapping",
    title_cs="Sociomapping: experimentální H-Model (kandidát AIA)",
    steps=_STEPS,
    presets=(Preset(CANDIDATE_METHOD, CandidateParameters(), _validate),),
    in_force=CANDIDATE_METHOD,
    groups=_GROUPS,
    note_cs=(
        "Experiment AIA, ne metoda SOMECS: jak SOMECS hledá rozložení, není zdokumentováno "
        "(AIA-H8). Každý výsledek nese status EXPERIMENTAL_AIA a nikdy nejde ke klientovi. "
        "Parametry hledání se ukazují, needitují."
    ),
)
