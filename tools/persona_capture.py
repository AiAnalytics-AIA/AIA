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
        rewrites and its word cap, pinned to the inputs and the unit sources by SHA256.

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


def write_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = rows_csv()
    (OUT / "rows.csv").write_bytes(data)
    (OUT / "cases.json").write_text(
        json.dumps(
            {"profiles": _cases(data.count(b"\n") - 1), "prose": _prose()},
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
