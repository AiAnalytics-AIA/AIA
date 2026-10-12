#!/usr/bin/env python3
"""Capture persona-profile fixtures from the vendored 18.6.6 unit (chunk 3b).

18.6.6 showed a model ``pipeline.generate_persona_text(row, temata=topics,
persona_mode="calibrated")`` (``pipeline.py:528-784``), which resolves to ``core`` with the
adaptive flag because no calibration profile ships (plan § 3a). Two steps, two environments:

    python tools/persona_capture.py inputs
        (repo environment) write fictional rows and the cases (a row and its topics) to
        packages/aia_core/tests/fixtures/persona_profile/

    <a venv with pandas>=2.1,<3 and numpy>=1.26,<3>/bin/python tools/persona_capture.py capture
        (the unit's environment) read the rows as ``pipeline.Panel.from_csv`` does and run the
        unit's own, unmodified ``generate_persona_text`` on every case, with the signal catalog
        pointed at a path that does not exist, so the behavioural block (chunk 3d) is empty, as
        ``persona_grounded._catalog`` makes it without the file. Writes ``expected.json``: each
        case's text, and the unit's ``_first_person_persona`` on line lists that reach its prefix
        rewrites and its word cap; and ``dispozice.odvod_temata`` on fictional questions, their
        union over a block (``dotaznik.py:937-948``) and the unit's keyword table itself; and,
        with a fictional signal catalog (``catalog.csv``) and the unit's own value labels, its
        ``grounded_profile_text`` and the whole persona on fictional rows carrying the signals
        (``signals.csv``); all pinned to the inputs and the unit sources by SHA256.

No network and no real panel data: every row is fictional.
"""

from __future__ import annotations

# ruff: noqa: RUF001 - the en dashes are 18.6.6's own Czech text, kept verbatim for EXACT parity
import argparse
import csv
import hashlib
import io
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "persona_profile"
UNIT_SOURCES = (
    "pipeline.py",
    "persona_calibration.py",
    "persona_depth.py",
    "persona_grounded.py",
    "dispozice.py",
    "audience_profile.py",
    "product_policy.py",
    "PRODUCT_POLICY.json",
    "PERSONA_VALUE_LABELS_v17.json",
)

HEADER = (
    "panel_row_id",
    "core_source",
    "pohlavi",
    "vek",
    "vzdelani",
    "kraj",
    "trida_spolecenska",
    "prijem_osobni_mesicni",
    "prijem_definice",
    "prijem_pozice_0_1",
    "prijem_decile",
    "zamestnani_status",
    "is_student",
    "occupation_major",
    "velikost_domacnosti",
    "pocet_deti_celkem",
    "has_partner",
    "partner_cohabiting",
    "zdravi_sebehodnoceni",
    "kraj_kvalita_zivota_poradi",
    "brand_specific_background_ready",
    "F_rodinny_stav",
    "F_bydleni",
    "F_auto",
    "F_deti",
    "F_sam",
)
KRAJE = ("Hlavní město Praha", "Jihomoravský kraj", "Zlínský kraj", "Karlovarský kraj")
VZDELANI = ("základní", "střední bez maturity", "střední s maturitou", "VOŠ/VŠ")
STATUS = ("employed", "unemployed", "student", "retired", "inactive", "inactive_other", "unknown")
DEFINICE = ("personal_net_income", "work_earnings_net", "")
RODINNY = ("svobodny", "zenaty_vdana", "rozvedeny", "vdovec_vdova", "druh_druzka")
BYDLENI = ("v rodinném domě", "v bytě v osobním vlastnictví", "v nájemním bytě")
TOPICS = (
    [],
    ["finance"],
    ["zdravi"],
    ["mentalni_zdravi", "vztahy"],
    ["vztahy", "bydleni"],
    ["auto", "doprava"],
    ["potraviny", "nakup"],
    ["znacka"],
    ["reklama", "energie"],
    ["kampan", "zdravi", "bydleni", "auto", "vztahy"],
    ["doprava"],
    ["energie"],
    ["nakup"],
)
#: Incomes exactly on each band's edge (``pipeline.py:439-447``).
EDGE_INCOMES = ("20000", "30000", "45000", "60000", "19999.5", "1")


def _blank(rng: random.Random, value: str, p: float = 0.12) -> str:
    return "" if rng.random() < p else value


def _rows(n: int = 80, seed: int = 20261012) -> list[list[str]]:
    rng = random.Random(seed)
    rows: list[list[str]] = []
    for i in range(n):
        age = rng.randint(18, 92)
        status = rng.choice(STATUS)
        partner = rng.choice(("0", "1", ""))
        rows.append(
            [
                f"FIC-ROW-{i + 1:04d}",
                "core_v17" if i % 4 else "",
                rng.choice(("muž", "žena", "Muž", "žena")),
                _blank(rng, str(age), 0.05),
                _blank(rng, rng.choice(VZDELANI), 0.05),
                _blank(rng, rng.choice(KRAJE), 0.05),
                rng.choice(("nižší střední", "vyšší střední", "")),
                _blank(rng, rng.choice(("0", str(rng.randint(8000, 90000)))), 0.15),
                rng.choice(DEFINICE),
                _blank(rng, f"{rng.random():.3f}", 0.3),
                str(rng.randint(1, 10)),
                status,
                rng.choice(("0", "1")),
                _blank(rng, str(rng.randint(0, 9)), 0.25),
                _blank(rng, str(rng.randint(1, 6)), 0.1),
                _blank(rng, str(rng.randint(0, 4)), 0.2),
                partner,
                "" if partner == "" else rng.choice(("0", "1")),
                _blank(rng, str(rng.randint(1, 5)), 0.15),
                str(rng.randint(1, 14)),
                rng.choice(("0", "1")),
                _blank(rng, rng.choice(RODINNY), 0.2),
                _blank(rng, rng.choice(BYDLENI), 0.2),
                _blank(rng, rng.choice(("0", "1")), 0.2),
                rng.choice(("0", "1")),
                rng.choice(("0", "1")),
            ]
        )
    for k, income in enumerate(EDGE_INCOMES):
        edge = list(rows[k])
        edge[0] = f"FIC-ROW-EDGE-{k + 1}"
        edge[HEADER.index("prijem_osobni_mesicni")] = income
        rows.append(edge)
    return rows


def _prose() -> list[dict[str, Any]]:
    """Line lists fed to the unit's ``_first_person_persona`` directly: the prefixes it rewrites,
    the lines it drops, and texts past the 185-word cap, with and without a late clause."""
    rng = random.Random(7)
    words = ("nákup", "značka", "cena", "kvalita", "zpráva", "televize", "sport", "rodina")
    long_lines = [
        f"Signál {i}: "
        + " ".join(rng.choice(words) for _ in range(rng.randint(3, 9)))
        + rng.choice((";", ".", ",", ""))
        for i in range(40)
    ]
    return [
        {
            "id": "F01_prefixes",
            "lines": [
                "Pohlaví: žena",
                "Věk: 31 let",
                "Vzdělání: VOŠ/VŠ",
                "Kraj: Zlínský kraj",
                "Příjmové pásmo: 20–30 tisíc Kč čistého měsíčně",
                "Socioekonomický kontext (odhad): střední vrstva",
                "Komplexní behaviorální profil:",
                "  Mediální chování [modelovaná intenzita]: TV 8/10 (hodně)",
                "  Nákupní a značkový profil [1–10]: slevy 9/10",
                "  Co typicky rozhoduje při reakci na značku [1–10; predispozice, ne výsledek"
                " konkrétního testu]: cena 8/10",
                "  Hodnoty a postoje [1–10]: tradice 7/10",
                "  Životní/digitální chování [1–10]: online 9/10",
                "  Poznámka k profilu: interní",
                "Povaha: klidný; pečlivý",
                "Jak odpovídá v dotaznících: odpovídá rychle",
                "",
            ],
        },
        {"id": "F02_no_sex", "lines": ["Pohlaví: neuvedeno", "Věk: neuvedeno"]},
        {"id": "F03_long", "lines": ["Pohlaví: muž", "Věk: 52 let", *long_lines]},
        {
            "id": "F04_long_no_clause",
            "lines": ["Pohlaví: muž", "Věk: 52 let", "Dlouhé: " + " ".join(["slovo"] * 260)],
        },
        {
            # The last "; " sits at about 51 % of the cut: below the 55 % floor, so the unit
            # keeps the whole cut.
            "id": "F05_clause_below_the_floor",
            "lines": [
                "Pohlaví: muž",
                "Věk: 52 let",
                "Dlouhé: " + " ".join(["slovo"] * 88) + "; " + " ".join(["slovo"] * 200),
            ],
        },
        {
            "id": "F06_clause_above_the_floor",
            "lines": [
                "Pohlaví: muž",
                "Věk: 52 let",
                "Dlouhé: " + " ".join(["slovo"] * 110) + "; " + " ".join(["slovo"] * 200),
            ],
        },
    ]


QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Kolik korun měsíčně utratíte za potraviny a nápoje?", ("do 3000", "3000 a více")),
    ("Jak často nakupujete v supermarketu nebo diskontní prodejně?", ("denně", "týdně")),
    ("Objednáváte zboží přes e-shop nebo mobilní aplikaci?", ("ano", "ne")),
    ("Jak důležité je pro vás doručení kurýrem domů?", ()),
    ("Která značka kávy je vaše nejoblíbenější?", ("Značka A", "Značka B")),
    ("Viděl(a) jste v poslední době reklamní spot nebo kampaň s influencerem?", ("ano", "ne")),
    ("Kolik času denně trávíte u televize, rádia nebo na YouTube?", ()),
    ("Jak hodnotíte svůj zdravotní stav a péči lékaře?", ("dobře", "špatně")),
    ("Jak často sportujete, cvičíte nebo jezdíte na kole?", ()),
    ("Třídíte odpad a záleží vám na udržitelnosti a klimatu?", ()),
    ("Kupujete nápoje v plastových nebo zálohovaných obalech?", ()),
    ("Kolik platíte za elektřinu, plyn a teplo?", ()),
    ("Jezdíte do práce autem, vlakem nebo MHD?", ("autem", "vlakem", "MHD")),
    ("Automaticky obnovujete předplatné?", ("ano", "ne")),
    ("Bydlíte v bytě nebo v rodinném domě?", ("byt", "dům")),
    ("Může se to být stát kdykoli?", ()),
    ("Máte hypotéku, úvěr nebo spoříte?", ()),
    ("Důvěřujete vládě, parlamentu a politickým stranám?", ()),
    ("Jaká je role státu v ekonomice?", ()),
    ("Jaké hodnoty a tradice jsou pro vás důležité?", ()),
    ("Jak hodnotíte služby obecního úřadu ve vašem městě?", ()),
    ("Obecně řečeno, souhlasíte s novým zákonem o daních?", ()),
    ("Využíváte prémiové nebo luxusní služby a zákaznický servis?", ()),
    ("Kolik utratíte za oblečení, obuv a kosmetiku?", ()),
    ("Pracujete z domova (home office) nebo v kanceláři?", ()),
    ("Co děláte ve volném čase: kino, koncert, divadlo, četba?", ()),
    ("Máte psa nebo kočku?", ("pes", "kočka", "nemám")),
    ("Jste firemní zákazník s rozhodovací pravomocí o nákupu pro firmu?", ()),
    ("Doporučil(a) byste nás přátelům? Jak hodnotíte věrnostní program?", ()),
    ("Používáte umělou inteligenci, AI nebo chytré technologie?", ()),
    ("Jak snadné je pro vás vyplnění formuláře a porozumění textu?", ()),
    ("Sdílíte příspěvky na sociálních sítích, Facebooku nebo TikToku?", ()),
    ("Jak spokojený(á) jste ve vztahu s partnerem a rodinou?", ()),
    ("Cítil(a) jste v posledních týdnech úzkost, stres nebo depresi?", ()),
    ("Důvěřujete soudům, policii a dalším institucím?", ()),
    ("Jak vnímáte migraci a uprchlíky?", ()),
    ("Cítíte se ve svém okolí bezpečně? Bojíte se kriminality?", ()),
    ("Jak se vyvíjí inflace a životní úroveň v ČR?", ()),
    ("Kolik máte dětí a jak často vídáte rodiče?", ()),
    ("Zapojujete se do komunity, se sousedy nebo dobrovolnictví?", ()),
    ("Podle čeho se rozhodujete, kterou možnost vybrat?", ()),
    ("Jak byste popsal(a) svou povahu a osobnost?", ()),
    ("Používáte mobilní bankovnictví a platby kartou?", ()),
    ("Jaký význam má pro vás víra a náboženství?", ()),
    ("Víte, co je RPSN a máte finanční rezervu?", ()),
    ("Co si myslíte o slogan a claim nové kampaně?", ()),
    ("Kupujete stavební materiál pro stavby?", ()),
    ("Jednal(a) jste s realitním makléřem o nemovitosti?", ()),
    ("Používáte zdravotnický materiál nebo zdravotnické pomůcky?", ()),
    ("Účastníte se jako nákupčí výběrového řízení nebo tendru?", ()),
    ("Hlásíte se k národnostní menšině?", ("moravská", "slezská", "romská")),
    ("Romantický film nebo seriál?", ()),
    ("Jaké je počasí?", ("hezky", "ošklivě")),
    # "volný čas" is a phrase: "volný den" alone must not reach volny_cas.
    ("Kdy máte volný den?", ()),
    # More than five topics: the cap keeps the five with most hits, ties by name.
    (
        "Kolik korun utratíte online za potraviny v obchodě, za auto, bydlení, zdraví a sport?",
        (),
    ),
    ("", ()),
)
BLOCKS: tuple[tuple[int, ...], ...] = ((0, 1, 2), (12, 13, 14, 15), (52, 53), (5, 45, 4, 5))


#: A fictional signal catalog (chunk 3d) in the unit's columns: every ``kind``, every evidence
#: role, a block holding more than three signals, a repeated concept, a modelled prior (never
#: shown), empty cells, a column no row carries, and four real column names that the unit's own
#: value labels describe (by values, values with a direction, anchors, generic anchors).
CATALOG_HEADER = (
    "column",
    "label",
    "topics",
    "source",
    "wave",
    "evidence_role",
    "block",
    "kind",
    "priority",
    "min_abs_z",
    "concept",
)
CATALOG: tuple[tuple[str, ...], ...] = (
    (
        "SIG_bfi_extr",
        "extraverze",
        "vztahy|media",
        "PIAAC",
        "2023",
        "MEASURED_DERIVED",
        "core",
        "bfi_z",
        "1.4",
        "0.5",
        "bfi",
    ),
    (
        "SIG_bfi_cons",
        "svědomitost",
        "prace|finance",
        "PIAAC",
        "2023",
        "MEASURED_DERIVED",
        "core",
        "bfi_z",
        "1.3",
        "",
        "bfi_c",
    ),
    (
        "SIG_trust_gov",
        "důvěra vládě",
        "politika|instituce|duvera",
        "ISSP",
        "2021",
        "MATCHED_DONOR_BLOCK",
        "issp",
        "scale10",
        "3.0",
        "",
        "trust",
    ),
    (
        "SIG_trust_courts",
        "důvěra soudům",
        "instituce|duvera",
        "ISSP",
        "2021",
        "MATCHED_DONOR_BLOCK",
        "issp",
        "scale10",
        "2.9",
        "",
        "trust",
    ),
    (
        "SIG_trust_police",
        "důvěra policii",
        "instituce|bezpecnost",
        "ISSP",
        "2021",
        "MATCHED_DONOR_BLOCK",
        "issp",
        "scale5",
        "2.8",
        "",
        "",
    ),
    (
        "SIG_vote",
        "účast ve volbách",
        "politika",
        "ISSP",
        "2021",
        "MATCHED_WHOLE_BLOCK_CANONICAL",
        "issp",
        "yesno",
        "2.7",
        "",
        "",
    ),
    (
        "SIG_news",
        "sledování zpráv",
        "media|politika",
        "ISSP",
        "2021",
        "MATCHED_DONOR_BLOCK",
        "issp",
        "frequency5",
        "2.6",
        "",
        "",
    ),
    (
        "SIG_health",
        "zdraví",
        "zdravi",
        "EHIS",
        "2019",
        "MATCHED_DONOR_BLOCK",
        "ehis",
        "health5",
        "1.1",
        "",
        "",
    ),
    (
        "SIG_phq",
        "PHQ",
        "mentalni_zdravi|zdravi",
        "EHIS",
        "2019",
        "MATCHED_DONOR_BLOCK",
        "ehis",
        "phq9",
        "1.2",
        "",
        "",
    ),
    (
        "SIG_gad",
        "GAD",
        "mentalni_zdravi",
        "EHIS",
        "2019",
        "MATCHED_DONOR_BLOCK",
        "ehis",
        "gad7",
        "1.2",
        "",
        "",
    ),
    (
        "SIG_sport_min",
        "sport",
        "sport|zdravi",
        "EHIS",
        "2019",
        "CALIBRATED_BEHAVIOR_MODEL",
        "",
        "minutes_day",
        "0.8",
        "",
        "",
    ),
    (
        "SIG_read_hours",
        "čtení",
        "volny_cas",
        "JRC",
        "2022",
        "MODELED_VALUE_PROXY",
        "jrc",
        "hours_week",
        "0.7",
        "",
        "",
    ),
    (
        "SIG_risk01",
        "ochota riskovat",
        "finance|rozhodovani",
        "JRC",
        "2022",
        "CALIBRATED_MODELED_COMPOSITE",
        "jrc",
        "scale01",
        "",
        "",
        "",
    ),
    (
        "SIG_debt",
        "dluhy",
        "finance",
        "JRC",
        "2022",
        "CALIBRATED_MODELED_BINARY",
        "jrc",
        "scale4",
        "1.0",
        "",
        "",
    ),
    (
        "SIG_stress6",
        "stres",
        "mentalni_zdravi|prace",
        "JRC",
        "2022",
        "SOMETHING_ELSE",
        "jrc",
        "scale6",
        "1.0",
        "",
        "",
    ),
    (
        "SIG_bank",
        "banka",
        "bankovnictvi|finance",
        "JRC",
        "2022",
        "MEASURED_JOINT",
        "core",
        "categorical",
        "1.0",
        "",
        "",
    ),
    (
        "SIG_lonely",
        "osamělost",
        "vztahy|mentalni_zdravi",
        "JRC",
        "2022",
        "MATCHED_DONOR_BLOCK",
        "jrc",
        "text",
        "1.1",
        "",
        "",
    ),
    (
        "SIG_prior",
        "modelový sklon",
        "nakup|znacka|finance",
        "MODEL",
        "2024",
        "MODELED_BEHAVIOR_PRIOR",
        "model",
        "scale10",
        "9",
        "",
        "",
    ),
    (
        "SIG_brand",
        "věrnost značce",
        "znacka|nakup|loajalita",
        "JRC",
        "2022",
        "CALIBRATED_BEHAVIOR_MODEL",
        "brand",
        "scale10",
        "1.0",
        "",
        "",
    ),
    ("SIG_raw", "syrové", "nakup", "X", "", "MEASURED_DERIVED", "brand", "", "1.0", "", ""),
    (
        "SIG_absent",
        "chybí",
        "nakup|finance",
        "X",
        "",
        "MEASURED_DERIVED",
        "brand",
        "scale10",
        "1.0",
        "",
        "",
    ),
    (
        "SIG_no_topics",
        "bez témat",
        "",
        "X",
        "",
        "MEASURED_DERIVED",
        "brand",
        "scale10",
        "1.0",
        "",
        "",
    ),
    (
        "PIAAC_I2_Q02",
        "politický zájem",
        "politika|instituce",
        "PIAAC",
        "2023",
        "MEASURED_DERIVED",
        "core",
        "scale10",
        "1.0",
        "",
        "",
    ),
    (
        "PIAAC_I2_Q03",
        "vliv",
        "politika|duvera",
        "PIAAC",
        "2023",
        "MEASURED_DERIVED",
        "core",
        "scale10",
        "1.0",
        "",
        "",
    ),
    (
        "PIAAC_I2_Q01a",
        "vliv na vládu",
        "politika|verejne",
        "PIAAC",
        "2023",
        "MEASURED_DERIVED",
        "core",
        "scale10",
        "1.0",
        "",
        "",
    ),
    (
        "smartphone_use_intensity_1_10",
        "smartphone",
        "online|technologie|media",
        "MODEL",
        "2024",
        "CALIBRATED_BEHAVIOR_MODEL",
        "digital",
        "scale10",
        "1.0",
        "",
        "",
    ),
)
SIGNAL_COLUMNS = tuple(c[0] for c in CATALOG if c[0] != "SIG_absent")
SIGNAL_TOPICS = (
    ["politika"],
    ["instituce", "duvera", "bezpecnost"],
    ["zdravi", "mentalni_zdravi"],
    ["finance", "nakup"],
    ["vztahy", "media", "volny_cas", "sport", "znacka", "bankovnictvi"],
    ["prace", "rozhodovani"],
    ["online", "technologie"],
    ["kampan", "zdravi", "bydleni", "auto", "vztahy"],
    ["cena"],
    # Five ISSP signals, a budget of six: the three-per-block cap decides.
    ["politika", "instituce", "duvera", "bezpecnost", "media"],
    # "online" is generic, "media" specific: the multiplier orders these.
    ["online", "media", "vztahy"],
)
#: Inputs fed to the unit's ``_compact_anchor`` directly: (label, low, high, direction).
ANCHORS: tuple[tuple[str, str, str, str], ...] = (
    ("vliv na vládu", "0 = vůbec nesouhlasí", "10 = zcela souhlasí", "vyšší hodnota = více"),
    ("souhlas", "0 = rozhodně ne souhlas", "10 = rozhodně ne souhlas", ""),
    ("důvěra", "0 = žádná důvěra", "10 = plná důvěra", "obrácená škála: nižší je lepší"),
    ("x", "", "10 = hodně", "opačný směr škály"),
    (
        "hodnocení zdraví",
        "1 = výborné zdraví",
        "5 = špatné zdraví",
        "jedna dva tři čtyři pět šest sedm",
    ),
    ("stres", "0=nikdy", "10=neustále v práci i doma a o víkendech a svátcích", "méně je lépe"),
)


def _signal_value(rng: random.Random, column: str) -> str:
    kind = next(c[7] for c in CATALOG if c[0] == column)
    if rng.random() < 0.12:
        return ""
    if column == "PIAAC_I2_Q02":
        return str(rng.randint(1, 4))
    if column == "PIAAC_I2_Q03":
        return str(rng.randint(1, 5))
    if kind == "bfi_z":
        return f"{rng.gauss(0, 1):.3f}"
    if kind == "categorical":
        return rng.choice(("Komerční banka", "ČSOB", "unknown", "Fio"))
    if kind == "text":
        return rng.choice(
            ("Most of the time", "More than once a week", "Never", "refused", "občas")
        )
    if kind == "yesno":
        return rng.choice(("0", "1"))
    if kind in {"scale5", "frequency5", "health5"}:
        return str(rng.randint(1, 5))
    if kind == "scale4":
        return str(rng.randint(1, 4))
    if kind == "scale6":
        return str(rng.randint(1, 6))
    if kind == "minutes_day":
        return str(rng.choice((0, 15, 45, 120, 240)))
    if kind == "hours_week":
        return f"{rng.uniform(0, 20):.1f}"
    if kind == "scale01":
        return f"{rng.random():.3f}"
    if kind == "phq9":
        return str(rng.randint(0, 27))
    if kind == "gad7":
        return str(rng.randint(0, 21))
    if kind == "":
        return "7"
    return str(rng.randint(0, 10)) if rng.random() < 0.8 else f"{rng.uniform(0, 10):.1f}"


def _signal_rows(base: list[list[str]], seed: int = 20261013) -> list[list[str]]:
    rng = random.Random(seed)
    out = []
    for row in base[:40]:
        quality = rng.choice(("vysoká", "střední", ""))
        out.append([*row, quality, *(_signal_value(rng, c) for c in SIGNAL_COLUMNS)])
    return out


def _cases(rows: int) -> list[dict[str, Any]]:
    cases = [
        {"id": f"P{i + 1:03d}", "row": i, "topics": list(TOPICS[i % len(TOPICS)])}
        for i in range(rows)
    ]
    # The same row under every topic set: what changes with the topics alone.
    cases += [{"id": f"T{j + 1:02d}", "row": 3, "topics": list(t)} for j, t in enumerate(TOPICS)]
    return cases


def rows_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(_rows())
    return buffer.getvalue().encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _csv(header: tuple[str, ...], rows: list[list[str]] | tuple[tuple[str, ...], ...]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def write_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = rows_csv()
    (OUT / "rows.csv").write_bytes(data)
    (OUT / "catalog.csv").write_bytes(_csv(CATALOG_HEADER, CATALOG))
    (OUT / "signals.csv").write_bytes(
        _csv((*HEADER, "_donor_issp_quality", *SIGNAL_COLUMNS), _signal_rows(_rows()))
    )
    (OUT / "cases.json").write_text(
        json.dumps(
            {
                "profiles": _cases(data.count(b"\n") - 1),
                "prose": _prose(),
                "questions": [{"text": t, "options": list(o)} for t, o in QUESTIONS],
                "blocks": [list(b) for b in BLOCKS],
                "signal_cases": [
                    {"row": i % 40, "topics": list(SIGNAL_TOPICS[i % len(SIGNAL_TOPICS)])}
                    for i in range(60)
                ],
                "anchors": [list(a) for a in ANCHORS],
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'rows.csv'} and {OUT / 'cases.json'}")


def capture() -> None:
    import pandas as pd  # the unit's environment only

    sys.path.insert(0, str(UNIT))
    import persona_grounded
    from pipeline import _first_person_persona, generate_persona_text

    persona_grounded.CATALOG = OUT / "no-catalog-in-3b.csv"  # the behavioural block: chunk 3d
    persona_grounded._catalog.cache_clear()

    rows_bytes = (OUT / "rows.csv").read_bytes()
    cases_bytes = (OUT / "cases.json").read_bytes()
    df = pd.read_csv(
        io.BytesIO(rows_bytes), low_memory=False, dtype={"occupation_isco08": "string"}
    )
    out = []
    cases = json.loads(cases_bytes)
    prose = [
        {"id": c["id"], "text": _first_person_persona(c["lines"], max_words=185)}
        for c in cases["prose"]
    ]
    from dispozice import TEMATA_KLICE, odvod_temata

    topics = [odvod_temata(q["text"] + " " + " ".join(q["options"])) for q in cases["questions"]]
    blocks = []
    for block in cases["blocks"]:  # dotaznik.py:937-948, the union over a block's questions
        union: list[str] = []
        for i in block:
            for topic in topics[i]:
                if topic not in union:
                    union.append(topic)
        blocks.append(union)
    from persona_grounded import grounded_profile_text

    persona_grounded.CATALOG = OUT / "catalog.csv"  # the fictional catalog, the unit's labels
    persona_grounded._catalog.cache_clear()
    signal_bytes = (OUT / "signals.csv").read_bytes()
    sdf = pd.read_csv(
        io.BytesIO(signal_bytes), low_memory=False, dtype={"occupation_isco08": "string"}
    )
    catalog = persona_grounded._catalog()
    parsed = [{**m, "topics": sorted(m["topics"])} for m in catalog]
    renders = []
    for i in range(len(sdf)):
        row = sdf.iloc[i]
        out_row = []
        for m in catalog:
            rr = persona_grounded._render(m, row)
            out_row.append(None if rr is None else [rr[0], rr[1]])
        renders.append(out_row)
    anchors = [persona_grounded._compact_anchor(*a) for a in cases["anchors"]]
    signals = []
    for case in cases["signal_cases"]:
        row = sdf.iloc[case["row"]]
        signals.append(
            {
                "grounded": grounded_profile_text(row, case["topics"]),
                "persona": generate_persona_text(
                    row, temata=case["topics"], persona_mode="calibrated"
                ),
            }
        )
    persona_grounded.CATALOG = OUT / "no-catalog-in-3b.csv"
    persona_grounded._catalog.cache_clear()

    for case in cases["profiles"]:
        row = df.iloc[case["row"]]
        text = generate_persona_text(row, temata=case["topics"], persona_mode="calibrated")
        out.append({"id": case["id"], "text": text})
    expected = {
        "captured_with": {"pandas": pd.__version__},
        "rows_sha256": _sha(rows_bytes),
        "cases_sha256": _sha(cases_bytes),
        "unit_sources": {name: _sha((UNIT / name).read_bytes()) for name in UNIT_SOURCES},
        "cases": out,
        "prose": prose,
        "question_topics": topics,
        "block_topics": blocks,
        "topic_keys": TEMATA_KLICE,
        "signals": signals,
        "catalog_parsed": parsed,
        "renders": renders,
        "anchors": anchors,
        "catalog_sha256": _sha((OUT / "catalog.csv").read_bytes()),
        "signal_rows_sha256": _sha(signal_bytes),
    }
    (OUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'expected.json'}: {len(out)} cases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("inputs", "capture"))
    args = parser.parse_args()
    write_inputs() if args.step == "inputs" else capture()


if __name__ == "__main__":
    main()
