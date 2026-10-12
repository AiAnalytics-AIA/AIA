"""A panel respondent's profile, as 18.6.6 showed it to a model.

A port of ``pipeline.generate_persona_text`` (``legacy/npc-panel-18.6.6/app/pipeline.py:528-784``)
in the one mode 18.6.6 ran: ``calibrated``, which resolves to ``core`` with the adaptive flag
because no calibration profile ships (``persona_calibration.py:135-137``; plan
``panel-grounded-respondents.md`` § 3a). Adaptive mode never shows the HEXACO anchors, traits,
life trajectory, dispositions, attitudes, the legacy social class or the style line, so none of
them is ported. Parity is EXACT against the unit's own function on fictional rows
(``tools/persona_capture.py``; ``tests/fixtures/persona_profile/``).

The profile is ``KEY: value`` lines in the unit's order, turned into first-person prose by
:func:`first_person` and cut at 185 words. A row is a mapping of column to the value
``read_csv`` would hold (:data:`~aia_core.domain.population.audience.Typed`; ``None`` is NaN); a
column the row does not carry is absent from it, as it is absent from the unit's ``row.index``.

The behavioural block (the persona signal catalog, chunk 3d) arrives as ready lines, and the
question's topics (chunk 3c) as a list.

Two deliberate differences, each where the unit stamped a guess on a missing cell
(CLAUDE.md § 8): a missing ``pohlavi`` is "neuvedeno", where the unit's ``str(NaN)`` made it
"žena" (``pipeline.py:561-562``); a missing ``is_student`` is not a student, where the unit's
``bool(NaN)`` made an employed person "Současně: student/ka" (``:598``).

Pure: stdlib only.
"""

from __future__ import annotations

# ruff: noqa: RUF001 - the en dashes are 18.6.6's own Czech text, kept verbatim for EXACT parity
import contextlib
import math
from collections.abc import Mapping, Sequence
from typing import Final

from .population.audience import Typed

__all__ = [
    "MAX_WORDS",
    "PERSONA_MODE",
    "PROFILE_VERSION",
    "age_band",
    "first_person",
    "household_facts",
    "income_band",
    "persona_text",
    "profile_lines",
]

PROFILE_VERSION: Final = "aia-panel-persona-1 (18.6.6 generate_persona_text, calibrated->core)"
PERSONA_MODE: Final = "calibrated->core (no active profile)"
#: ``_first_person_persona(..., max_words=185 if adaptive_persona else 200)`` (``pipeline.py:784``).
MAX_WORDS: Final = 185

Row = Mapping[str, Typed]

_EMPLOYMENT: Final = {
    "employed": "pracuje",
    "unemployed": "nezaměstnaný/á",
    "student": "student/ka",
    "retired": "důchodce/kyně",
    "inactive": "ekonomicky neaktivní",
    "inactive_other": "jiná ekonomická neaktivita",
    "unknown": "neuvedeno",
}
_ISCO_MAJOR: Final = {
    1: "manažeři",
    2: "specialisté",
    3: "techničtí a odborní pracovníci",
    4: "úředníci",
    5: "pracovníci ve službách a prodeji",
    6: "kvalifikovaní pracovníci v zemědělství",
    7: "řemeslníci a opraváři",
    8: "obsluha strojů a zařízení",
    9: "pomocní a nekvalifikovaní pracovníci",
    0: "ozbrojené síly",
}
_HEALTH: Final = {1: "výborné", 2: "velmi dobré", 3: "dobré", 4: "uspokojivé", 5: "špatné"}
_MARITAL: Final = {
    "svobodny": "svobodný(á)",
    "zenaty_vdana": "ženatý/vdaná",
    "rozvedeny": "rozvedený(á)",
    "vdovec_vdova": "ovdovělý(á)",
}
_BRAND_TOPICS: Final = frozenset({"znacka", "kampan", "reklama"})
_BRAND_LINE: Final = (
    "Brand-specific background: NEDODÁN — nepředpokládej předchozí znalost, používání ani "
    "zkušenost s konkrétní značkou; vyhodnocuj pouze stimulus a obecné predispozice."
)
_BIO_KEYS: Final = frozenset(
    {"Pohlaví", "Věk", "Vzdělání", "Kraj", "Příjmové pásmo", "Socioekonomický kontext (odhad)"}
)
_PREFIXES: Final = (
    (
        "Mediální chování [modelovaná intenzita]:",
        "Mediální chování — z médií a platforem je pro mě typické:",
    ),
    (
        "Nákupní a značkový profil [1–10]:",
        "Nákupní a značkový profil — při nákupu je pro mě typické:",
    ),
    (
        "Co typicky rozhoduje při reakci na značku [1–10; predispozice, ne výsledek "
        "konkrétního testu]:",
        "Když reaguji na značku, obvykle rozhoduje:",
    ),
    ("Hodnoty a postoje [1–10]:", "V hodnotách a postojích mám sklon k:"),
    ("Životní/digitální chování [1–10]:", "V běžném a digitálním životě je pro mě typické:"),
    ("Jak odpovídá v dotaznících:", "Když odpovídám v dotazníku,"),
)


def _present(value: Typed) -> bool:
    """``pd.notna``: a typed cell is missing only as ``None`` or NaN."""
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def _number(value: Typed) -> float:
    """``float(value)``, raising as Python does on a non-number."""
    if value is None:
        raise TypeError("missing")
    return float(value)


def age_band(value: Typed) -> str:
    """``_age_band_label`` (``pipeline.py:429-436``)."""
    try:
        age = int(_number(value))
    except (TypeError, ValueError, OverflowError):
        return "věk neuveden"
    for lo, hi in ((18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 74)):
        if lo <= age <= hi:
            return f"{lo}–{hi} let"
    return "75 a více let" if age >= 75 else "méně než 18 let"


def income_band(value: Typed) -> str:
    """``_income_band_label`` (``pipeline.py:439-447``)."""
    try:
        x = _number(value)
    except (TypeError, ValueError):
        return "příjem neuveden"
    if x <= 0:
        return "příjem neuveden"
    if x < 20000:
        return "do 20 tisíc Kč čistého měsíčně"
    if x < 30000:
        return "20–30 tisíc Kč čistého měsíčně"
    if x < 45000:
        return "30–45 tisíc Kč čistého měsíčně"
    if x < 60000:
        return "45–60 tisíc Kč čistého měsíčně"
    return "60 tisíc Kč a více čistého měsíčně"


def household_facts(row: Row, topics: Sequence[str]) -> str:
    """``dispozice.popis_faktu`` (``dispozice.py:579-610``): the F_* facts the topics call for."""
    topic_set = set(topics)
    facts: list[str] = []

    def relevant(*names: str) -> bool:
        return bool(topic_set & set(names))

    marital = row.get("F_rodinny_stav")
    if relevant("vztahy", "bydleni") and _present(marital):
        facts.append(_MARITAL.get(str(marital), str(marital)))
    housing = row.get("F_bydleni")
    if relevant("bydleni", "finance", "energie") and _present(housing):
        facts.append(f"bydlí {housing}")
    if relevant("auto", "doprava") and "F_auto" in row:
        facts.append("auto v domácnosti" if row["F_auto"] == 1 else "bez auta")
    if relevant("vztahy", "bydleni", "potraviny", "nakup") and row.get("F_deti") == 1:
        facts.append("děti v domácnosti")
    if relevant("vztahy", "bydleni") and row.get("F_sam") == 1:
        facts.append("žije sám")
    return ", ".join(facts)


def _int_text(value: Typed) -> int | None:
    """``int(float(value))`` inside the unit's ``try``; None where it raised."""
    try:
        return int(_number(value))
    except (TypeError, ValueError, OverflowError):
        return None


def profile_lines(row: Row, topics: Sequence[str], behaviour: str = "") -> list[str]:
    """The ``KEY: value`` lines ``generate_persona_text`` assembles (``pipeline.py:560-783``)."""
    base: list[tuple[str, str]] = []
    sex = row.get("pohlavi")
    sex_text = str(sex).strip().lower() if _present(sex) else ""
    base.append(
        ("Pohlaví", "muž" if sex_text.startswith("mu") else "žena" if sex_text else "neuvedeno")
    )
    age = row.get("vek")
    if _present(age):
        years = _int_text(age)
        base.append(("Věk", f"{years} let" if years is not None else age_band(age)))
    else:
        base.append(("Věk", "neuvedeno"))
    for column, label in (("vzdelani", "Vzdělání"), ("kraj", "Kraj")):
        value = row.get(column)
        if _present(value) and str(value).strip():
            base.append((label, str(value)))

    income = (
        row["prijem_osobni_mesicni"]
        if "prijem_osobni_mesicni" in row
        else row.get("prijem_cisty_mesicni")
    )
    try:
        has_income = _present(income) and float(income or 0) > 0
    except (TypeError, ValueError):
        has_income = False
    if has_income:
        definition = row.get("prijem_definice")
        definition_text = str(definition) if definition is not None else ""
        label = "Pracovní výdělek" if "work_earnings" in definition_text else "Osobní příjem"
        base.append((label, income_band(income)))
    rank = row.get("prijem_pozice_0_1")
    if _present(rank):
        with contextlib.suppress(TypeError, ValueError, OverflowError):
            base.append(
                (
                    "Relativní příjmová pozice",
                    f"přibližně {round(_number(rank) * 100)}. percentil v harmonizované "
                    "příjmové pozici",
                )
            )
    else:
        decile = row.get("prijem_decile")
        if _present(decile):
            value = _int_text(decile)
            if value is not None:
                base.append(("Příjmová pozice (compatibility proxy)", f"{value}/10"))
    status = row.get("zamestnani_status")
    status_text = str(status) if status is not None else "nan"
    if _present(status) and status_text.strip():
        base.append(("Pracovní status", _EMPLOYMENT.get(status_text, status_text)))
    student = row.get("is_student")
    if _present(student) and bool(student) and status_text == "employed":
        base.append(("Současně", "student/ka"))
    occupation = row.get("occupation_major")
    if _present(occupation):
        major = _int_text(occupation)
        if major is not None:
            base.append(
                (
                    "Aktuální profesní skupina"
                    if status_text == "employed"
                    else "Poslední/uváděná profesní skupina",
                    _ISCO_MAJOR.get(major, f"ISCO {major}"),
                )
            )
    household = row.get("velikost_domacnosti")
    if _present(household):
        size = _int_text(household)
        if size is not None:
            base.append(("Velikost domácnosti", f"{size} osoba/y"))
    children = row.get("pocet_deti_celkem")
    if _present(children):
        count = _int_text(children)
        if count is not None:
            base.append(
                (
                    "Rodičovství",
                    f"uvádí {count} dítě/dětí celkem; nemusí žít ve stejné domácnosti",
                )
            )
    base.extend(_partner(row.get("has_partner"), row.get("partner_cohabiting")))
    if {"zdravi", "mentalni_zdravi"} & set(topics):
        health = row.get("zdravi_sebehodnoceni")
        if _present(health):
            grade = _int_text(health)
            if grade is not None:
                base.append(("Zdraví v core datech", _HEALTH.get(grade, str(health))))
    quality = row.get("kraj_kvalita_zivota_poradi")
    if _present(quality):
        base.append(("Kvalita života v kraji", f"{int(_number(quality))}. místo ze 14"))

    lines = [f"{k}: {v}" for k, v in base]
    if behaviour:
        lines.append("Komplexní behaviorální profil:")
        lines += [f"  {x}" for x in behaviour.splitlines()]
    if set(topics) & _BRAND_TOPICS:
        ready = row.get("brand_specific_background_ready", 0)
        try:
            brand_ready = int(float(ready or 0)) == 1 if _present(ready) else False
        except (TypeError, ValueError):
            brand_ready = False
        if not brand_ready:
            lines.append(_BRAND_LINE)
    if any(str(k).startswith(("D_", "F_")) for k in row):
        facts = household_facts(row, topics)
        if facts:
            lines.append(f"Domácnost: {facts}")
    return lines


def _partner(has_partner: Typed, cohabiting: Typed) -> list[tuple[str, str]]:
    """The partner line (``pipeline.py:621-634``): the unit's branches, evaluated in its order;
    a value that does not parse ends the block with no line, as its ``try`` did."""
    label = "Partnerský status v core datech"

    def equals(value: Typed, target: int) -> bool:
        return _present(value) and int(_number(value)) == target

    try:
        if equals(has_partner, 0):
            return [(label, "nemá stálého partnera/partnerku")]
        if equals(has_partner, 1) and equals(cohabiting, 0):
            return [(label, "má stálého partnera/partnerku, ale nežijí ve společné domácnosti")]
        if equals(cohabiting, 1):
            return [
                (label, "žije s partnerem/manželem či partnerkou/manželkou ve společné domácnosti")
            ]
        if equals(cohabiting, 0):
            return [
                (
                    label,
                    "nežije s partnerem ve společné domácnosti; existence partnera mimo "
                    "domácnost není z tohoto core zdroje jistá",
                )
            ]
    except (TypeError, ValueError, OverflowError):
        pass
    return []


def first_person(lines: Sequence[str], *, max_words: int = MAX_WORDS) -> str:
    """``_first_person_persona`` (``pipeline.py:450-501``): the lines as first-person prose."""
    values: dict[str, str] = {}
    rest: list[str] = []
    for line in lines:
        if ": " in line and not line.startswith("  "):
            key, value = line.split(": ", 1)
            if key in _BIO_KEYS:
                values[key] = value
                continue
        rest.append(line.strip())
    sex = values.get("Pohlaví")
    subject = "Jsem muž" if sex == "muž" else "Jsem žena" if sex == "žena" else "Jsem člověk"
    bio = [subject]
    if values.get("Věk"):
        bio.append(f"ve věku {values['Věk']}")
    sentence = ", ".join(bio) + "."
    if values.get("Vzdělání"):
        sentence += f" Mám {values['Vzdělání'].lower()} vzdělání."
    if values.get("Kraj"):
        sentence += f" Žiju v kraji {values['Kraj']}."
    if values.get("Příjmové pásmo"):
        sentence += f" Můj příjem je zhruba v pásmu {values['Příjmové pásmo']}."
    if values.get("Socioekonomický kontext (odhad)"):
        sentence += (
            f" Můj modelovaný socioekonomický kontext: {values['Socioekonomický kontext (odhad)']}."
        )
    cleaned: list[str] = []
    for x in rest:
        if not x or x == "Komplexní behaviorální profil:" or x.startswith("Poznámka k profilu:"):
            continue
        for old, new in _PREFIXES:
            if x.startswith(old):
                x = new + x[len(old) :]
                break
        if x.startswith("Povaha:"):
            x = "Moje chování v relevantních situacích je vyhraněné takto:" + x.split(":", 1)[1]
        cleaned.append(x)
    text = sentence + " " + " ".join(cleaned)
    words = text.split()
    if len(words) > max_words:
        cut = " ".join(words[:max_words])
        floor = int(len(cut) * 0.55)
        best = max(cut.rfind(". "), cut.rfind("; "))
        if best > floor:
            cut = cut[:best]
        text = cut.rstrip(" ,;—-") + "."
    return text


def persona_text(row: Row, topics: Sequence[str], behaviour: str = "") -> str:
    """The persona a model is shown for one respondent and one block's topics."""
    return first_person(profile_lines(row, topics, behaviour))
