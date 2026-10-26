"""The response process, step by step: how a model's probabilities become one respondent's answer.

ADR 0023; plan ``methodology-tab.md`` R1a. The division of labour is 18.6.6's and it is the
point: the model estimates one respondent's latent preference as a probability vector;
explicit, auditable survey-response mechanisms adjust it by the respondent's style; a seeded
draw by code picks the answer. The model never chooses the answer.

Declared in ``ResponseProcessSpec`` (``respondent_behavior.py``), whose preset
``aia-response-1`` is the unit's values, and read by the code that computes: what the tab
shows is what runs, and the EXACT captures of the unit's own functions hold it there
(``fixtures/response_process``). A run pins it when it starts and a retry keeps it (R1b);
it is editable, and a draft is checked beside the process in force on fixed fictional
questions and respondents (``response_check.py``, R1c).

Not ported, and said so on its step: 18.6.6's dispersion temperature
(``dispersion_calibration``), which AIA has no calibration for; the temperature is 1, the
identity. The model is asked at temperature 0.

Finding D6 is named on its step: a fictional roster draws its donors, with replacement, from a
pool of ``max(3, n // 3)`` ids, so it has fewer distinct donors than that; under
``aia-support-1``'s 25 donors a run of fewer than 75 fictional respondents suppresses every
donor-layer value, and most runs below about 90 do (``test_methodology_response.py``).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..respondent_behavior import AIA_RESPONSE_V1, STYLES, ResponseProcessSpec
from .catalogue import (
    Bound,
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodStep,
    ParameterRef,
    Preset,
    StepGroup,
    Symbol,
    above,
    at_least,
    at_most,
)

__all__ = ["RESPONSE"]

_D: Final = "aia_core.domain"
_B: Final = f"{_D}.respondent_behavior"
_R: Final = f"{_D}.ai_respondent"
_T: Final = "packages/aia_core/tests"
_TB: Final = f"{_T}/test_respondent_behavior.py"
_TA: Final = f"{_T}/test_ai_respondent.py"
_TR: Final = f"{_T}/test_methodology_response.py"

_EXACT: Final = f"{_TB}::test_adjust_probabilities_matches_the_unit"
_STYLES: Final = f"{_TB}::test_styles_match_the_unit"
_DECLARED: Final = f"{_TR}::test_the_preset_is_the_units_values_and_the_code_reads_it"

_BEHAVIOR: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "behavior.py (adjust_probabilities)",
    "Převzato z 18.6.6 řádek po řádku; koeficienty jsou jednotky, záměrně mírné.",
)
_STYLY: Final = Evidence(
    EvidenceKind.LEGACY_PORT,
    "styly.py (prirad_styly, popis_stylu)",
    "Převzato z 18.6.6; scipy.stats.norm.ppf nahrazuje statistics.NormalDist().inv_cdf.",
)
_CAPTURES: Final = Evidence(
    EvidenceKind.FIXTURE,
    "fixtures/response_process (behavior.json, styles.json)",
    "Zachycené výstupy nezměněných funkcí jednotky (tools/respondent_capture.py), EXACT.",
)
_DIVISION: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "docs/architecture/research-agents.md; ai_respondent.py",
    "Model odhaduje pravděpodobnosti jednoho respondenta, odpověď losuje kód. Model "
    "odpověď nikdy nevybírá.",
)
_OI62: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "open-items OI-62",
    "Losování ze standardní knihovny (random.Random), ne z NumPy: stejné rozdělení, jiné "
    "konkrétní losy než v 18.6.6.",
)
_D6: Final = Evidence(
    EvidenceKind.AIA_DECISION,
    "plan methodology-tab, nález D6",
    "Fiktivní soubor losuje dárce s opakováním z fondu max(3, ⌊n/3⌋) identifikátorů, takže "
    "skutečných dárců je méně. S pravidlem aia-support-1 (25 dárců) běh s méně než 75 "
    "fiktivními respondenty potlačí každou hodnotu vrstvy dárců vždy a do zhruba 90 "
    "respondentů většinou.",
)

_STYLE_CS: Final = {
    "souhlasny_sklon": "souhlasný sklon",
    "vyhranenost": "vyhraněnost",
    "ochota_priznat_nevim": "ochota přiznat „nevím“",
    "sdilnost": "sdílnost",
    "satisficing": "satisficing",
    "social_desirability_sensitivity": "citlivost na společenskou žádoucnost",
}
_LINK_CS: Final = (("education", "vzdělání"), ("age", "věk"), ("male", "muž"))

_STRENGTH: Final = Symbol(
    r"\sigma", "síla procesu u otázky (response_process.strength, bez deklarace 1)"
)


def _validate(spec: BaseModel) -> None:
    if not isinstance(spec, ResponseProcessSpec):
        raise TypeError(f"not a response-process specification: {type(spec).__name__}")


_STEPS: Final[tuple[MethodStep, ...]] = (
    MethodStep(
        id="method",
        title_cs="Pojmenování procesu odpovědi",
        formula_latex=r"\text{proces} = \text{methodology\_version}",
        implements=f"{_B}:ResponseProcessSpec",
        source_sha256="e83ea2fd01e11e005ebff5b499228fc0f2bf48e8cb6b8e77e82b20869e052354",
        parameters=(ParameterRef("methodology_version", "Verze procesu odpovědi"),),
        evidence=(_BEHAVIOR,),
        tests=(_DECLARED,),
    ),
    # ------------------------------------------------------------------ the model
    MethodStep(
        id="request",
        title_cs="Pravděpodobnosti od modelu",
        formula_latex=r"p = (p_1, \dots, p_K) \text{ od modelu, jeden respondent, teplota } 0",
        implements=f"{_R}:build_request",
        source_sha256="56d53a0992909f74f30137d293390724b674415e86a6a156114de4ce4523e7cd",
        symbols=(Symbol("K", "počet možností otázky (u škály body a případně „nevím“)"),),
        evidence=(_DIVISION,),
        tests=(f"{_TA}::test_the_request_carries_class_lineage_prompt_and_no_scope",),
        note_cs=(
            "Model dostane profil jednoho respondenta a vrátí pro každou uzavřenou otázku "
            "rozdělení pravděpodobností, nikdy odpověď. Disperzní teplota 18.6.6 "
            "(dispersion_calibration) přenesena není: AIA nemá kalibraci, teplota je 1."
        ),
    ),
    MethodStep(
        id="normalise",
        title_cs="Normalizace",
        formula_latex=r"p_k := \frac{\max(0, p_k)}{\sum_j \max(0, p_j)}",
        implements=f"{_B}:normalise",
        source_sha256="33f01949292172b274eb0f67c46e4cb107251b6f495c013d19e2c1dd856b8276",
        evidence=(_BEHAVIOR,),
        tests=(f"{_TB}::test_a_vector_without_positive_finite_mass_is_refused",),
        note_cs=(
            "Nekonečná hodnota nebo NaN se odmítne ještě před ořezem: max(0, NaN) je 0 a "
            "z rozbité odpovědi by se tiše stala věrohodná."
        ),
    ),
    # ------------------------------------------------------------- the mechanisms
    MethodStep(
        id="reweight",
        title_cs="Měkké převážení",
        formula_latex=(
            r"p_k := \frac{p_k\, e^{\min(L,\ \max(-L,\ \beta s_k))}}"
            r"{\sum_j p_j\, e^{\min(L,\ \max(-L,\ \beta s_j))}}"
        ),
        implements=f"{_B}:_soft_reweight",
        source_sha256="a33179e2b6d74fc8d728435f4b5221bd55fee967b57876611492cadc5d013b19",
        symbols=(
            Symbol(r"\beta", "síla mechanismu u respondenta"),
            Symbol("s_k", "skóre možnosti k ve směru mechanismu"),
            Symbol("L", "mez exponentu"),
        ),
        parameters=(ParameterRef("reweight_limit", "Mez exponentu (L)"),),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT,),
        note_cs="Každý z prvních čtyř mechanismů je jedno takové převážení se svým β a s.",
    ),
    MethodStep(
        id="social_desirability",
        title_cs="Společenská žádoucnost",
        formula_latex=r"\beta = \sigma \left(a + b\, z_{\mathrm{sds}}\right)",
        implements=f"{_B}:adjust_probabilities",
        source_sha256="d7daff2b36cd4baccd9bf8be6da287368845c19ced40286e3468192d5a938632",
        symbols=(
            _STRENGTH,
            Symbol(r"z_{\mathrm{sds}}", "styl: citlivost na společenskou žádoucnost"),
        ),
        parameters=(
            ParameterRef("social_desirability.base", "Základ (a)"),
            ParameterRef("social_desirability.slope", "Sklon se stylem (b)"),
        ),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT, f"{_TB}::test_every_mechanism_is_exercised_by_the_captures"),
        note_cs="Jen když otázka směr žádoucnosti deklaruje; nikdy se nehádá.",
    ),
    MethodStep(
        id="acquiescence",
        title_cs="Souhlasný sklon",
        formula_latex=r"\beta = \sigma\, c\, z_{\mathrm{souhlas}}",
        implements=f"{_B}:adjust_probabilities",
        source_sha256="d7daff2b36cd4baccd9bf8be6da287368845c19ced40286e3468192d5a938632",
        symbols=(_STRENGTH, Symbol(r"z_{\mathrm{souhlas}}", "styl: souhlasný sklon")),
        parameters=(ParameterRef("acquiescence", "Koeficient (c)"),),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT,),
        note_cs="Jen když otázka deklaruje, která odpověď je souhlas.",
    ),
    MethodStep(
        id="extremity",
        title_cs="Vyhraněnost na škále",
        formula_latex=(
            r"s_k = \left|-1 + \frac{2(k-1)}{n-1}\right|,\quad "
            r"\beta = \sigma\, e\, z_{\mathrm{vyhr}}"
        ),
        implements=f"{_B}:adjust_probabilities",
        source_sha256="d7daff2b36cd4baccd9bf8be6da287368845c19ced40286e3468192d5a938632",
        symbols=(
            _STRENGTH,
            Symbol("n", "počet bodů škály (aspoň 3)"),
            Symbol(r"z_{\mathrm{vyhr}}", "styl: vyhraněnost"),
        ),
        parameters=(ParameterRef("extremity", "Koeficient (e)"),),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT,),
        note_cs="„Nevím“ má skóre 0: není střed ani krajnost.",
    ),
    MethodStep(
        id="dont_know",
        title_cs="Ochota přiznat „nevím“",
        formula_latex=(r"s = (0, \dots, 0, 1),\quad \beta = \sigma\, d\, z_{\text{nevím}}"),
        implements=f"{_B}:adjust_probabilities",
        source_sha256="d7daff2b36cd4baccd9bf8be6da287368845c19ced40286e3468192d5a938632",
        symbols=(_STRENGTH, Symbol(r"z_{\text{nevím}}", "styl: ochota přiznat „nevím“")),
        parameters=(ParameterRef("dont_know", "Koeficient (d)"),),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT,),
        note_cs="Jen když otázka „nevím“ připouští; je vždy poslední možností.",
    ),
    MethodStep(
        id="satisficing",
        title_cs="Satisficing",
        formula_latex=(
            r"\lambda = \min\!\left(\lambda_{\max},\ "
            r"\sigma\, \mathrm{clamp}_{[0,1]}\!\left(g + h\, z_{\mathrm{sat}}\right)\right),"
            r"\quad p := \frac{(1-\lambda)\,p + \lambda\, u}{\sum}"
        ),
        implements=f"{_B}:adjust_probabilities",
        source_sha256="d7daff2b36cd4baccd9bf8be6da287368845c19ced40286e3468192d5a938632",
        symbols=(
            _STRENGTH,
            Symbol(r"z_{\mathrm{sat}}", "styl: satisficing"),
            Symbol(
                "u",
                "heuristika otázky: rovnoměrně (výchozí), střed škály, nebo první možnost",
            ),
        ),
        parameters=(
            ParameterRef("satisficing.base", "Základ (g)"),
            ParameterRef("satisficing.slope", "Sklon se stylem (h)"),
            ParameterRef("satisficing.cap", "Strop podílu (λ max)"),
        ),
        evidence=(_BEHAVIOR, _CAPTURES),
        tests=(_EXACT,),
        note_cs="Otázka může heuristiku vypnout (satisficing_strategy: none).",
    ),
    # --------------------------------------------------------------------- the draw
    MethodStep(
        id="draw",
        title_cs="Losování odpovědi kódem",
        formula_latex=(
            r"u \sim U[0, 1),\quad k^{*} = \min\left\{k : \textstyle\sum_{j \le k} p_j > u"
            r"\right\}"
        ),
        implements=f"{_B}:draw_index",
        source_sha256="aa7e348734aaa6a401ea185e126032b2312aa11b54a8447ed2315e559e669deb",
        evidence=(_DIVISION, _OI62),
        tests=(
            f"{_TB}::test_the_draw_is_seeded_and_follows_the_distribution",
            f"{_TA}::test_answers_are_drawn_by_code_reproducibly_and_zero_mass_is_refused",
        ),
        note_cs=(
            "Semínko je pro každého respondenta a otázku vlastní (sha256 ze semínka běhu, "
            "respondenta a otázky): stejný běh vylosuje stejné odpovědi."
        ),
    ),
    # ------------------------------------------------------------------- the styles
    MethodStep(
        id="styles",
        title_cs="Styly respondenta",
        formula_latex=(
            r"x = \alpha z_{\mathrm{vzd}} + \gamma z_{\text{věk}} + \delta m + "
            r"\sqrt{\max\!\left(1 - \operatorname{var}(\text{signál}),\ \phi\right)}\ "
            r"\varepsilon,\quad \text{styl} = z(x)"
        ),
        implements=f"{_B}:assign_styles",
        source_sha256="0ee31228933919923cbead02ee072b3fa59b0456cd930ef4565e092be9280ed7",
        symbols=(
            Symbol(r"z_{\mathrm{vzd}},\ z_{\text{věk}}", "z-skóre vzdělání a věku v souboru"),
            Symbol("m", "pohlaví: muž 1, jinak -1"),
            Symbol(r"\alpha, \gamma, \delta", "vazby stylu na vzdělání, věk a pohlaví"),
            Symbol(r"\phi", "dolní mez váhy šumu"),
            Symbol(r"\varepsilon", "stabilní šum respondenta"),
        ),
        parameters=(
            *(
                ParameterRef(f"style_links.{s}.{leaf}", f"{_STYLE_CS[s]}: {label}")
                for s in STYLES
                for leaf, label in _LINK_CS
            ),
            ParameterRef("style_noise_floor", "Dolní mez váhy šumu (φ)"),
        ),
        evidence=(_STYLY, _CAPTURES),
        tests=(_STYLES,),
        note_cs=(
            "Vazby jsou informované priory, ne měření (říká to i 18.6.6); většina rozptylu "
            "stylu je individuální. Chybějící vzdělání nebo věk nepřispívá ničím; chybějící "
            "pohlaví se počítá jako ne-muž (-1), stejně jako v 18.6.6 (styly.py)."
        ),
    ),
    MethodStep(
        id="noise",
        title_cs="Stabilní šum",
        formula_latex=(
            r"\varepsilon = \Phi^{-1}\!\left(\frac{H_{12}(\text{id} \Vert \text{styl}) + "
            r"\frac{1}{2}}{16^{12}}\right)"
        ),
        implements=f"{_B}:_stable_noise",
        source_sha256="4aac8f1a28ebac394d64c186d208f9342de8f3c6913c1461e840822efffd61f6",
        symbols=(Symbol("H_{12}", "prvních 12 šestnáctkových číslic SHA-256"),),
        evidence=(_STYLY,),
        tests=(
            f"{_TB}::test_a_respondent_keeps_their_style_whoever_else_is_in_the_roster",
            f"{_TR}::test_only_the_noise_is_the_respondents_own_the_style_depends_on_the_roster",
        ),
        note_cs=(
            "Šum závisí jen na respondentovi. Styl jako celek ne: z-skóre vzdělání a věku, "
            "rozptyl signálu i závěrečná standardizace se počítají přes celý soubor, takže "
            "tentýž respondent má v jiném souboru jiný styl."
        ),
    ),
    MethodStep(
        id="describe",
        title_cs="Styl slovy v profilu",
        formula_latex=r"|z| \ge \theta \;\Rightarrow\; \text{popis stylu v profilu}",
        implements=f"{_R}:describe_style",
        source_sha256="3118f0838c18417235f4a50ea2bd6d29720b8e6e00087dba3730c8d2f65cce39",
        symbols=(Symbol(r"\theta", "práh výraznosti stylu"),),
        parameters=(ParameterRef("describe_threshold", "Práh výraznosti (θ)"),),
        evidence=(_STYLY,),
        tests=(f"{_TR}::test_a_style_is_put_into_words_from_the_threshold",),
        note_cs="Slovy se do profilu dostane jen výrazná strana stylu.",
    ),
    # ------------------------------------------------------------- the roster
    MethodStep(
        id="roster",
        title_cs="Fiktivní soubor: dárci a váhy",
        formula_latex=r"D = \max\!\left(3,\ \left\lfloor n/3 \right\rfloor\right),\quad w_i = 1",
        implements=f"{_R}:fictional_roster",
        source_sha256="70f80c16faef7718b30696b87c735b47c6442607ce9eb38ac2da7f1868230bca",
        symbols=(
            Symbol("D", "fond identifikátorů dárců; dárci se z něj losují s opakováním"),
            Symbol("n", "počet respondentů"),
        ),
        evidence=(_D6,),
        tests=(
            f"{_TA}::test_the_roster_is_fictional_deterministic_and_carries_its_lineage",
            f"{_TR}::test_d6_a_fictional_roster_draws_too_few_distinct_donors_for_support",
        ),
        note_cs=(
            "Nález D6: D je fond, ne počet dárců. Dárci se losují s opakováním, takže "
            "skutečných dárců je méně než D: u 75 respondentů jich 25 dosáhne jen asi čtvrtina "
            "souborů. S pravidlem aia-support-1 (25 dárců) běh s méně než 75 fiktivními "
            "respondenty potlačí každou hodnotu vrstvy dárců vždy a do zhruba 90 respondentů "
            "většinou. Fiktivní soubor nese každý AI běh, který nebere respondenty z panelu."
        ),
    ),
)

_GROUPS: Final = (
    StepGroup("M", "Proces odpovědi", ("method",)),
    StepGroup("P", "Pravděpodobnosti od modelu", ("request", "normalise")),
    StepGroup(
        "B",
        "Mechanismy odpovědi",
        (
            "reweight",
            "social_desirability",
            "acquiescence",
            "extremity",
            "dont_know",
            "satisficing",
        ),
    ),
    StepGroup("D", "Losování", ("draw",)),
    StepGroup("S", "Styly respondenta", ("styles", "noise", "describe")),
    StepGroup("F", "Fiktivní soubor", ("roster",)),
)

_PROCESS: Final = f"{_D}.respondent_behavior:ResponseProcessSpec"
#: The range each check holds a field to (F13); a coefficient is held only to be finite.
_BOUNDS: Final = (
    Bound("satisficing.cap", (at_least(0), at_most(1)), f"{_D}.respondent_behavior:Satisficing"),
    Bound("reweight_limit", (above(0),), _PROCESS),
    Bound("style_noise_floor", (above(0), at_most(1)), _PROCESS),
    Bound("describe_threshold", (above(0),), _PROCESS),
)

RESPONSE: Final = MethodModule(
    id="response",
    title_cs="Odpověď respondenta: od pravděpodobností modelu k odpovědi",
    steps=_STEPS,
    presets=(Preset("aia-response-1", AIA_RESPONSE_V1, _validate),),
    in_force="aia-response-1",
    groups=_GROUPS,
    editable=True,
    bounds=_BOUNDS,
    note_cs=(
        "Model odhadne pravděpodobnosti jednoho respondenta, mechanismy odpovědi je podle "
        "jeho stylu upraví a odpověď vylosuje kód; model odpověď nikdy nevybírá. Verze "
        "aia-response-1 jsou hodnoty 18.6.6 a kód je čte, takže zobrazené je počítané. "
        "Každý běh si proces odpovědi zapamatuje a opakování ho drží. Úpravu lze před "
        "uvedením v platnost porovnat na pevných fiktivních otázkách a respondentech."
    ),
)
