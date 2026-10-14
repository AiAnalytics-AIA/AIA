"""The object map's formulas as editable slots, each with the expression the engine computes.

ADR 0023 decision 4; plan ``methodology-tab.md`` S3. Every expression here is written the way
the named engine function computes, operation for operation, so it gives the engine's exact
bits; ``test_methodology_sociomap_formulas.py`` proves each against that function on random
and boundary inputs. A stored edit (chunk A3) replaces an expression; the slot's properties
are what any replacement must keep.

What is an algorithm rather than a formula stays code and has no slot: a pair's status (a
classification), the linear quantile (it indexes a sorted list), the ranking, SMACOF, the
mappability test and the envelope's maximum over hills.

Pure: stdlib only.
"""

from __future__ import annotations

from typing import Final

from .catalogue import BuiltinFormula
from .expressions import Property, PropertyKind, Slot, Variable

__all__ = ["SOCIOMAP_FORMULAS"]

_P: Final = PropertyKind
_Z95: Final = 1.959963984540054  # sample only; the engine computes z_c from the confidence

_F1 = Slot(
    id="f1.scale",
    title_cs="Hodnocení na škále 0-1",
    variables=(
        Variable("a", r"a_{kc}", "hodnocení", (1.0, 3.0, 5.0), "body škály"),
        Variable("lo", r"s^{\min}_c", "dolní konec škály", (0.0, 1.0), "body škály"),
        Variable("hi", r"s^{\max}_c", "horní konec škály", (5.0, 10.0), "body škály"),
    ),
    properties=(
        Property(_P.WITHIN, lo=0.0, hi=1.0, description_cs="hodnocení na škále leží v [0, 1]"),
        Property(_P.EQUALS_AT, at={"a": 1.0, "lo": 1.0, "hi": 10.0}, value=0.0),
        Property(_P.EQUALS_AT, at={"a": 5.0, "lo": 0.0, "hi": 5.0}, value=1.0),
        Property(_P.NON_DECREASING_IN, variable="a"),
    ),
)
_F2 = Slot(
    id="f2.person",
    title_cs="Hodnocení na škále respondenta",
    variables=(
        Variable("a", r"a_{ki}", "hodnocení (po F1)", (0.2, 0.5, 0.8)),
        Variable("low", r"\min_l a_{kl}", "nejnižší hodnocení respondenta", (0.0, 0.2)),
        Variable("high", r"\max_l a_{kl}", "nejvyšší hodnocení respondenta", (0.8, 1.0)),
    ),
    properties=(
        Property(_P.WITHIN, lo=0.0, hi=1.0),
        Property(_P.NON_DECREASING_IN, variable="a"),
        Property(_P.EQUALS_AT, at={"a": 0.2, "low": 0.2, "high": 0.8}, value=0.0),
    ),
)
_WEIGHTS = Variable(
    "w",
    "w",
    "váhy respondentů, kteří hodnotili oba objekty",
    ((1.0, 1.0, 1.0), (0.5, 2.0, 1.0, 3.0), (1e-3, 5.0), (2.5,)),
    vector=True,
)
_F3_N = Slot(
    id="f3.effective_n",
    title_cs="Kishovo efektivní n",
    variables=(_WEIGHTS,),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(_P.AT_MOST_VARIABLE, variable="w", description_cs="nejvýš počet hodnotitelů"),
    ),
)
_INTERVAL_VARS = (
    Variable("r", "r", "korelace páru", (-1.0, -0.9, -0.2, 0.0, 0.4, 0.95, 1.0)),
    Variable("n", "n", "vzorek páru", (4.0, 30.0, 512.5)),
    Variable("z", "z_c", "kvantil normálního rozdělení", (_Z95, 2.5758293035489004)),
)
_F3_LOW = Slot(
    id="f3.interval_low",
    title_cs="Dolní mez Fisherova intervalu",
    variables=_INTERVAL_VARS,
    properties=(
        Property(_P.WITHIN, lo=-1.0, hi=1.0),
        Property(_P.AT_MOST_VARIABLE, variable="r", description_cs="dolní mez nepřesáhne r"),
        Property(_P.NON_DECREASING_IN, variable="r"),
    ),
)
_F3_HIGH = Slot(
    id="f3.interval_high",
    title_cs="Horní mez Fisherova intervalu",
    variables=_INTERVAL_VARS,
    properties=(
        Property(_P.WITHIN, lo=-1.0, hi=1.0),
        Property(_P.AT_LEAST_VARIABLE, variable="r", description_cs="horní mez není pod r"),
        Property(_P.NON_DECREASING_IN, variable="r"),
    ),
)
_F3_FLOOR = Slot(
    id="f3.effect_floor",
    title_cs="Dosahuje pár prahu účinku?",
    variables=(
        Variable("r", "r", "korelace páru", (-0.8, -0.1, 0.0, 0.05, 0.1, 0.5)),
        Variable("floor", r"r_{\min}", "práh účinku", (0.1, 0.3)),
    ),
    properties=(Property(_P.WITHIN, lo=0.0, hi=1.0, description_cs="ano (1) nebo ne (0)"),),
)
_F6 = Slot(
    id="f6.distance",
    title_cs="Cílová vzdálenost z korelace",
    variables=(Variable("r", "r_{ij}", "korelace páru", (-1.0, -0.5, 0.0, 0.3, 0.99, 1.0)),),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(_P.EQUALS_AT, at={"r": 1.0}, value=0.0),
        Property(_P.NON_INCREASING_IN, variable="r"),
        Property(_P.WITHIN, lo=0.0, hi=2.0, description_cs="nejvýš pevné pravítko"),
    ),
)
_F7 = Slot(
    id="f7.stress_1",
    title_cs="Stress-1",
    variables=(
        Variable(
            "d", "d", "vzdálenosti na mapě (známé páry)", ((1.0, 2.0), (0.5, 1.5)), vector=True
        ),
        Variable("delta", r"\delta", "cílové vzdálenosti", ((1.0, 2.0), (1.2, 1.0)), vector=True),
    ),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(_P.EQUALS_AT, at={"d": (1.0, 2.0), "delta": (1.0, 2.0)}, value=0.0),
    ),
)
_KNOWN_R = Variable(
    "r",
    "r_{ij}",
    "korelace se známými PRIMÁRNÍMI partnery",
    ((0.5,), (0.3, -0.6, 0.9), (-1.0, 1.0), (0.0, 0.0)),
    vector=True,
)
_F8_A = Slot(
    id="f8.alignment",
    title_cs="Souhlasnost A_i",
    variables=(_KNOWN_R,),
    properties=(Property(_P.WITHIN, lo=-1.0, hi=1.0),),
)
_F8_K = Slot(
    id="f8.connectedness",
    title_cs="Propojenost K_i",
    variables=(_KNOWN_R,),
    properties=(Property(_P.WITHIN, lo=0.0, hi=1.0),),
)
_F8_H = Slot(
    id="f8.height",
    title_cs="Výška objektu",
    variables=(
        Variable(
            "a", r"\tilde a_{kj}", "hodnocení na škále 0-1", ((0.0, 1.0), (0.4, 0.6)), vector=True
        ),
        Variable("w", "w_k", "váhy hodnotitelů", ((1.0, 1.0), (0.5, 3.0)), vector=True),
    ),
    properties=(Property(_P.WITHIN, lo=0.0, hi=1.0),),
)
_F9 = Slot(
    id="f9.k100",
    title_cs="Propojenost na škále 0-100",
    variables=(Variable("k", "K_i", "propojenost", (0.0, 0.25, 1.0)),),
    properties=(
        Property(_P.WITHIN, lo=0.0, hi=100.0),
        Property(_P.NON_DECREASING_IN, variable="k"),
    ),
)
_F12 = Slot(
    id="f12.kernel",
    title_cs="Jádro kopce",
    variables=(
        Variable("h", "h_j", "výška objektu", (0.0, 0.3, 1.0)),
        Variable(
            "d2",
            r"\lVert q - y_j\rVert^2",
            "čtverec vzdálenosti buňky od objektu",
            (0.0, 0.01, 0.25, 1.0, 4.0),
        ),
        Variable("sigma", r"\sigma", "šířka kopce", (0.1, 0.25, 1.0)),
    ),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(
            _P.EQUALS_AT,
            at={"h": 1.0, "d2": 0.0, "sigma": 0.25},
            value=1.0,
            description_cs="kopec má ve svém středu přesně svou výšku",
        ),
        Property(_P.NON_INCREASING_IN, variable="d2"),
        Property(_P.NON_DECREASING_IN, variable="h"),
    ),
)
_SUPPORT_N = Slot(
    id="support.effective_n",
    title_cs="Efektivní n umístěných respondentů",
    variables=(_WEIGHTS,),
    properties=(Property(_P.NON_NEGATIVE), Property(_P.AT_MOST_VARIABLE, variable="w")),
)

# What each slot does not cover, as the engine keeps it (the anchor beside each).
_KEPT_F1: Final = (
    # engine_v2._scaled
    (
        "Hodnocení mimo deklarovanou škálu [s_min, s_max] kód odmítne a výpočet zastaví; výraz ho "
        "nikdy nedostane."
    ),
    "Nehodnocená položka zůstane prázdná.",
)
_KEPT_F2: Final = (
    # relations.person_minmax, over research_sociomap.rating_universe
    (
        "low a high počítá kód z hodnocení respondenta přes všechny hodnocené položky studie (každá"
        " baterie a deklarované hodnoticí otázky), ne jen mapovanou baterii."
    ),
    (
        "Respondenta, jehož hodnocení se neliší (high = low), kód vyřadí ještě před výrazem: výraz "
        "nikdy nedělí nulou."
    ),
    "Nehodnocená položka zůstane prázdná.",
)
_KEPT_F3_N: Final = (
    # pairs.derive_pair_relations
    (
        "Výraz nahrazuje jen Kishovu větev. Kterou větev pár použije, určuje metodika (základ "
        "důkazů): při počtu respondentů je n počet společných hodnotitelů a výraz se nepoužije."
    ),
    (
        "Váhy w jsou jen respondenti s platným hodnocením obou objektů a kladnou vahou; pár bez "
        "nich má n podle kódu."
    ),
)
_KEPT_INTERVAL: Final = (
    # relations.slot_interval, status_of_interval
    "Pod čtyřmi společnými hodnotiteli interval nevzniká.",
    "z_c spočítá kód z hladiny spolehlivosti metodiky.",
    (
        "Stav páru z intervalu čte kód: neznámý bez r nebo pod n_min, spolehlivý, když interval "
        "vylučuje nulu, jinak slabý."
    ),
)
_KEPT_FLOOR: Final = (
    # pairs.derive_pair_relations
    "Pár bez korelace výraz nedostane.",
    "Výsledek se zapíše vedle stavu páru; stav nemění.",
)
_KEPT_F6: Final = (
    # layout.correlation_distances
    "Jen známé páry (spolehlivé nebo slabé); neznámý pár vzdálenost nemá a rozložení netáhne.",
    "Vzdálenost objektu od sebe je 0.",
)
_KEPT_F7: Final = (
    # engine_v2 (stress_terms), metrics.stress_quality
    "d bere kód z hotového rozložení a δ jen ze známých párů.",
    "Slovní hodnocení věrohodnosti z výsledku čte kód podle pásem metodiky.",
)
_KEPT_F8: Final = (
    # metrics.primary_scores
    "r jen ze známých párů hlavních objektů; neznámé páry a kontextové objekty se nečtou.",
    "Objekt bez známého páru skóre nemá.",
)
_KEPT_HEIGHT: Final = (
    # engine_v2._heights
    "Přes všechny, kdo objekt hodnotili (i neumístěné respondenty), na škále 0-1 z F1, ne z F2.",
    "Objekt, který nikdo nehodnotil, výšku nemá.",
)
_KEPT_K100: Final = (
    # metrics (bootstrap of K100)
    (
        "Platí pro K_i z celého vzorku, a je-li bootstrap zapnutý, i z každého jeho vzorku; "
        "kvantily intervalu a pořadí počítá kód."
    ),
)
_KEPT_KERNEL: Final = (
    # terrain.envelope_at
    "Zda kopec v bodě sahá, rozhoduje kód: jádro při výšce 1 proti prahu.",
    "Z více kopců platí v bodě nejvyšší; objekt bez výšky kopec nemá.",
)
_KEPT_SUPPORT: Final = (
    # engine_v2 (support)
    "Váhy jen umístěných respondentů; bez kladné váhy efektivní n není a výraz se nepoužije.",
)

SOCIOMAP_FORMULAS: Final[tuple[BuiltinFormula, ...]] = (
    BuiltinFormula("f1_declared_scale", _F1, "(a - lo) / (hi - lo)", kept_cs=_KEPT_F1),
    BuiltinFormula("f2_person_minmax", _F2, "(a - low) / (high - low)", kept_cs=_KEPT_F2),
    BuiltinFormula("f3_effective_n", _F3_N, "sum(w) ** 2 / sum(w * w)", kept_cs=_KEPT_F3_N),
    BuiltinFormula(
        "f3_interval",
        _F3_LOW,
        "r if abs(r) == 1 else tanh(atanh(r) - z / sqrt(n - 3))",
        "Při |r| = 1 je mez sama korelace.",
        kept_cs=_KEPT_INTERVAL,
    ),
    BuiltinFormula(
        "f3_interval",
        _F3_HIGH,
        "r if abs(r) == 1 else tanh(atanh(r) + z / sqrt(n - 3))",
        kept_cs=_KEPT_INTERVAL,
    ),
    BuiltinFormula("f3_effect_floor", _F3_FLOOR, "abs(r) >= floor", kept_cs=_KEPT_FLOOR),
    BuiltinFormula("f6_distance", _F6, "sqrt(max(0, 2 * (1 - r)))", kept_cs=_KEPT_F6),
    BuiltinFormula(
        "f7_stress",
        _F7,
        "sqrt(sum((d - delta) ** 2) / sum(delta * delta)) if sum(delta * delta) > 0 else 0",
        kept_cs=_KEPT_F7,
    ),
    BuiltinFormula("f8_scores", _F8_A, "sum(r) / count(r)", kept_cs=_KEPT_F8),
    BuiltinFormula("f8_scores", _F8_K, "sum(abs(r)) / count(r)", kept_cs=_KEPT_F8),
    BuiltinFormula("f8_height", _F8_H, "sum(a * w) / sum(w)", kept_cs=_KEPT_HEIGHT),
    BuiltinFormula("f9_k100", _F9, "100 * k", kept_cs=_KEPT_K100),
    BuiltinFormula(
        "f12_envelope", _F12, "h * exp(-d2 / (2 * sigma * sigma))", kept_cs=_KEPT_KERNEL
    ),
    BuiltinFormula("support", _SUPPORT_N, "sum(w) ** 2 / sum(w * w)", kept_cs=_KEPT_SUPPORT),
)
