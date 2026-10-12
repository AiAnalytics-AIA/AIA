"""Support and suppression, step by step: which number a person may see (plan G1a).

ADR 0023; plan ``methodology-tab.md`` G1a. Two rule sets decide today, and the tab shows both
side by side, because they disagree (finding D2):

* **The unit's rule** (``research_aggregate.donor_support``, an EXACT port of 18.6.6's
  ``agreguj_otazku``) gives every aggregate cell its ``support_status`` from the number of
  unique donors alone. Results shows this status.
* **AIA's evidence gate** (``evidence.support.assess_support``, the methodology ledger's M16)
  re-assesses that cell for analysis on its raw n, its effective n and its donors, and the
  stricter of the two wins (``analysis.native._support``).

So a cell can read INDIKATIVNÍ in Results while analysis suppresses it. Which single rule
holds is the methodologist's decision, made in this tab once support is declared (G1b) and
put in force (G1c); until then this module only documents. It has no specification: every
value is a code constant, read where it is used.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from .catalogue import (
    ConstantRef,
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodStep,
    StepGroup,
    Symbol,
)

__all__ = ["SUPPORT"]

_A: Final = "aia_core.domain.research_aggregate"
_E: Final = "aia_core.domain.evidence.support"
_T: Final = "packages/aia_core/tests"

_UNIT: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "dotaznik.py agreguj_otazku + fidelity.py donor_support",
    "Převzato z 18.6.6 přesně (EXACT).",
)
_M16: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "methodology ledger M16 (dotaznik.agreguj_otazku, uncertainty.py, fidelity.evidence_rating)",
    "Prahy z ledgeru; práh 50 dárců pro indikativní je čtení prahu, ne převzatý kód.",
)
_D2: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    ".planning/plans/methodology-tab.md, finding D2",
    "Dvě sady pravidel; jednu vybere metodik (G1c).",
)

_STEPS: Final[tuple[MethodStep, ...]] = (
    # ------------------------------------------------------- the unit's rule (Results)
    MethodStep(
        id="unit_weights",
        title_cs="Čištění vah",
        formula_latex=r"w_k \notin (0, \infty) \Rightarrow w_k := \operatorname{medián}(w)",
        implements=f"{_A}:clean_weights",
        source_sha256="56ef8a81b1df7a44b096d90e1646e52558c4ef132cfccbb6060f27f87f5889ee",
        evidence=(_UNIT,),
        tests=(
            f"{_T}/test_research_aggregate.py::test_kish_and_donor_support_follow_the_units_thresholds",
        ),
        note_cs=(
            "Neplatnou váhu nahradí medián platných (bez platných: všechny 1). Brána AIA "
            "takové váhy odmítá místo čištění (nález D1)."
        ),
    ),
    MethodStep(
        id="unit_kish",
        title_cs="Kishovo efektivní n (jednotka)",
        formula_latex=r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2}",
        implements=f"{_A}:kish_effective_n",
        source_sha256="3c90e9ebf0d24ff28d466cade217baac2b55e31c13c86b0d23cbc0191e4fee70",
        evidence=(_UNIT,),
        tests=(
            f"{_T}/test_research_aggregate.py::test_kish_and_donor_support_follow_the_units_thresholds",
        ),
    ),
    MethodStep(
        id="unit_donors",
        title_cs="Dárci, efektivní n buňky a podíl největšího dárce",
        formula_latex=(
            r"n_D = |\{d_k\}|,\quad n_{\mathrm{eff}} = \min\!\left(n_{\mathrm{Kish}}"
            r"\tfrac{n_D}{n},\ n_{\mathrm{Kish}},\ n_D,\ n_{\mathrm{core}}\right),\quad "
            r"s_{\max} = \max_d \tfrac{n_d}{n}"
        ),
        implements=f"{_A}:donor_support",
        source_sha256="1d0b5d8ab8b72a76ec3102b62575338039236e3573849a111b59282a29586211",
        symbols=(
            Symbol("n_D", "počet různých dárců (vrstva core)"),
            Symbol(r"s_{\max}", "podíl největšího dárce"),
        ),
        evidence=(_UNIT,),
        tests=(
            f"{_T}/test_research_aggregate.py::test_kish_and_donor_support_follow_the_units_thresholds",
            f"{_T}/test_research_aggregate.py::test_estimates_support_and_suppression_are_exact_against_the_unit",
        ),
        note_cs=(
            "Efektivní n se zaokrouhlí na jedno desetinné místo. Podíl největšího dárce se "
            "spočítá a uloží, ale žádné pravidlo ho nečte (nález D4)."
        ),
    ),
    MethodStep(
        id="unit_status",
        title_cs="Stav podpory podle jednotky (ukazují ho Výsledky)",
        formula_latex=(
            r"n_D < 25 \Rightarrow \text{POTLAČIT};\quad n_D < 50 \Rightarrow "
            r"\text{INDIKATIVNÍ};\quad \text{jinak REPORTOVATELNÉ}"
        ),
        implements=f"{_A}:donor_support",
        source_sha256="1d0b5d8ab8b72a76ec3102b62575338039236e3573849a111b59282a29586211",
        constants=(
            ConstantRef(f"{_A}:_SUPPRESS_BELOW", "Potlačit pod", "dárců"),
            ConstantRef(f"{_A}:_REPORTABLE_FROM", "Reportovatelné od", "dárců"),
        ),
        evidence=(_UNIT, _D2),
        tests=(
            f"{_T}/test_research_aggregate.py::test_estimates_support_and_suppression_are_exact_against_the_unit",
        ),
        note_cs="Rozhoduje jen počet dárců: surové n ani efektivní n stav nemění.",
    ),
    # --------------------------------------------------- AIA's evidence gate (analysis)
    MethodStep(
        id="gate_kish",
        title_cs="Kishovo efektivní n (brána AIA)",
        formula_latex=(
            r"n_{\mathrm{Kish}} = \frac{\left(\sum_k w_k\right)^2}{\sum_k w_k^2},\quad "
            r"w_k \notin (0, \infty) \Rightarrow \text{odmítnuto}"
        ),
        implements=f"{_E}:kish_effective_n",
        source_sha256="dd0bd83ed33fce776c48ee8111788ff6418084214626c468c7f8dda0e5d5f08c",
        tests=(
            f"{_T}/test_evidence_support.py::test_kish_effective_n",
            f"{_T}/test_evidence_support.py::test_kish_refuses_weights_it_would_otherwise_have_to_clean",
        ),
        note_cs="Stejný vzorec jako u jednotky, ale neplatné váhy odmítne (nález D1).",
    ),
    MethodStep(
        id="gate_assess",
        title_cs="Brána důkazů AIA",
        formula_latex=(
            r"n < n_{\mathrm{cell}} \lor n_{\mathrm{eff}} < n_{\mathrm{guard}} \lor "
            r"n_D < D_{\min} \Rightarrow \text{POTLAČIT};\ "
            r"n_{\mathrm{eff}} < n_{\mathrm{ind}} \lor n_D < D_{\mathrm{ind}} \Rightarrow "
            r"\text{INDIKATIVNÍ};\ \text{neznámé} \Rightarrow \text{POTLAČIT}"
        ),
        implements=f"{_E}:assess_support",
        source_sha256="efc2dedce537d3a68222f2439210ab09b5a7c187451a19d551e28a80073459ee",
        constants=(
            ConstantRef(f"{_E}:REFERENCE_THRESHOLDS.min_cell", "Nejmenší surové n buňky"),
            ConstantRef(f"{_E}:REFERENCE_THRESHOLDS.n_guard", "Potlačit pod efektivním n"),
            ConstantRef(f"{_E}:REFERENCE_THRESHOLDS.indicative", "Indikativní pod efektivním n"),
            ConstantRef(f"{_E}:REFERENCE_THRESHOLDS.min_layer_donors", "Potlačit pod", "dárců"),
            ConstantRef(
                f"{_E}:REFERENCE_THRESHOLDS.indicative_layer_donors", "Indikativní pod", "dárců"
            ),
        ),
        evidence=(_M16,),
        tests=(
            f"{_T}/test_evidence_support.py::test_reference_thresholds",
            f"{_T}/test_evidence_support.py::test_support_decisions",
            f"{_T}/test_evidence_support.py::test_donor_layer_support",
            f"{_T}/test_evidence_support.py::test_default_assessment_is_suppress",
        ),
        note_cs="Bez důkazů je stav vždy POTLAČIT; vyšší stav vydá jen tato funkce.",
    ),
    MethodStep(
        id="gate_reassess",
        title_cs="Analýza přehodnotí stav jednotky branou AIA",
        formula_latex=(
            r"\text{stav}_{\mathrm{analýza}} = \text{přísnější z}\ "
            r"\left(\text{stav}_{\mathrm{jednotka}},\ \text{brána}(n, n_{\mathrm{eff}}, n_D)\right)"
        ),
        implements="aia_core.domain.analysis.native:_support",
        source_sha256="8cec538199db79932651b8640e3486e4e197cb966d0affa5f57ff7993e2af06f",
        evidence=(_D2,),
        tests=(
            f"{_T}/test_analysis_native.py::test_support_is_the_units_reassessed_by_aias_stricter_thresholds",
        ),
        note_cs=(
            "Brána dostává jako efektivní n kombinované efektivní n jednotky zaokrouhlené na "
            "jedno místo, ne Kishovo (nález D3). Buňka tak může být ve Výsledcích "
            "INDIKATIVNÍ a v analýze potlačená (nález D2)."
        ),
    ),
)

_GROUPS: Final = (
    StepGroup(
        "U",
        "Pravidlo jednotky 18.6.6 (Výsledky)",
        ("unit_weights", "unit_kish", "unit_donors", "unit_status"),
    ),
    StepGroup("A", "Brána důkazů AIA (analýza)", ("gate_kish", "gate_assess", "gate_reassess")),
)

SUPPORT: Final = MethodModule(
    id="support",
    title_cs="Podpora a potlačení: kdy se číslo smí ukázat",
    steps=_STEPS,
    groups=_GROUPS,
    note_cs=(
        "Dnes rozhodují dvě pravidla. Výsledky ukazují stav podle jednotky 18.6.6 (jen počet "
        "dárců, 25/50); analýza ho přehodnotí branou AIA (surové n 50, efektivní n 25/50, "
        "dárci 25/50) a platí přísnější. Buňka tak může být na obrazovce INDIKATIVNÍ a "
        "v analýze potlačená. Které jedno pravidlo bude platit, rozhodne metodik zde, až "
        "budou prahy deklarované (G1b) a jedna verze v platnosti (G1c)."
    ),
)
