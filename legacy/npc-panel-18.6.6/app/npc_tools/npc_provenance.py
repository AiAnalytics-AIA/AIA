#!/usr/bin/env python3
"""
npc_provenance.py — původ dat, verzování panelu a výpočet moatu
================================================================

Tři věci, které rozhodnou o enterprise prodeji a o tom, jestli víte, kde stojíte.

1. PROVENIENCE
   Tabulka dimenze → zdroj → licence → datum kalibrace. Je to zároveň
   compliance artefakt (u farmy nebo energetiky přijde vendor due diligence)
   a prodejní argument. Generuje se z katalogu zdrojů, takže nemůže zastarat
   nezávisle na něm.

2. VERZOVÁNÍ A REPRODUKOVATELNOST
   Když klient pustí stejnou studii za půl roku a dostane jiné číslo, musíte
   umět vysvětlit proč. Snapshot panelu + manifest s hashem = schopnost říct
   "tenhle výsledek pochází z panelu v2.3" a dokázat to.

3. MOAT
   Kolik z toho, co jde do promptu, pochází z vašich vlastních dat a kolik
   z veřejných zdrojů, které si stáhne kdokoliv. Tohle číslo si spočítejte,
   i když se vám odpověď nebude líbit — zvlášť když se vám nebude líbit.

Použití
-------
    python npc_provenance.py init                  # vyrobí šablonu mapování
    python npc_provenance.py table                 # vygeneruje provenance.csv
    python npc_provenance.py snapshot --panel panel.csv --version 2.3
    python npc_provenance.py moat --odpovedi vysledek.odpovedi.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

CATALOG = Path("data.js")
MAPPING = Path("dimenze_mapovani.csv")
PROVENANCE = Path("provenance.csv")

# Třídy původu — tohle je ta osa, na které se měří moat.
TRIDA = {
    "vlastni": "Vlastní panel (proprietární, nikdo jiný nemá)",
    "verejny": "Veřejný zdroj (stáhne si kdokoliv)",
    "licencovany": "Komerčně licencovaný (kdokoliv si může koupit)",
    "odvozeny": "Odvozený výpočtem z jiných dimenzí",
}


def load_catalog() -> list[dict]:
    """Vytáhne zdroje z data.js. Není to plný JS parser — bere jen pole,
    která potřebujeme, a je odolný vůči tomu, když nějaké chybí."""
    if not CATALOG.exists():
        sys.exit(f"Nenalezen katalog {CATALOG}. Musí ležet vedle skriptu.")
    txt = CATALOG.read_text(encoding="utf-8")
    out = []
    for blok in re.findall(r"\{\s*id:\s*'([^']+)'(.*?)\n  \}", txt, re.S):
        sid, body = blok
        def field(name: str) -> str:
            m = re.search(rf"{name}:\s*'((?:[^'\\]|\\.)*)'", body, re.S)
            return m.group(1).replace("\\'", "'") if m else ""
        out.append({
            "id": sid,
            "nazev": field("name"),
            "vlastnik": field("owner"),
            "url": field("url"),
            "licence": field("licence"),
            "stav": field("status"),
        })
    return out


def cmd_init() -> None:
    """Šablona mapování dimenzí na zdroje — tu vyplníte ručně, jinak to nejde."""
    if MAPPING.exists():
        print(f"{MAPPING} už existuje, nepřepisuji.")
        return
    try:
        sys.path.insert(0, ".")
        from npc_study import DIMENZE, STYL  # noqa: PLC0415
        dims = list(DIMENZE) + list(STYL)
    except Exception:  # noqa: BLE001
        dims = ["D_priklad_dimenze"]

    with MAPPING.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dimenze", "zdroj_id", "trida", "datum_kalibrace", "poznamka"])
        for d in dims:
            w.writerow([d, "", "", "", ""])
    print(f"→ {MAPPING}")
    print("\nVyplňte sloupce:")
    print("  zdroj_id        id zdroje z katalogu (ehis, volby, mos, ekcr, ilc_scp, …)")
    print("                  nebo 'vlastni_panel' u dimenzí z vašich šesti výzkumů")
    print("  trida           " + " | ".join(TRIDA))
    print("  datum_kalibrace YYYY-MM — vintage dat, ne datum, kdy jste to počítali")
    print("\nPak: python npc_provenance.py table")


def cmd_table() -> None:
    if not MAPPING.exists():
        sys.exit("Nejdřív spusťte: python npc_provenance.py init")
    cat = {s["id"]: s for s in load_catalog()}
    rows, chybi = [], []
    with MAPPING.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sid = (r.get("zdroj_id") or "").strip()
            if not sid:
                chybi.append(r["dimenze"])
                continue
            src = cat.get(sid, {})
            if sid == "vlastni_panel":
                src = {"nazev": "Vlastní panel Artchain", "vlastnik": "Artchain s.r.o.",
                       "url": "—", "licence": "Vlastní data — souhlas respondentů musí pokrývat komerční užití",
                       "stav": "vlastni"}
            elif not src:
                chybi.append(f"{r['dimenze']} (neznámé zdroj_id '{sid}')")
                continue
            rows.append({
                "dimenze": r["dimenze"],
                "trida": r.get("trida", ""),
                "zdroj": src.get("nazev", sid),
                "vlastnik": src.get("vlastnik", ""),
                "licence": src.get("licence", ""),
                "licencni_kos": src.get("stav", ""),
                "datum_kalibrace": r.get("datum_kalibrace", ""),
                "url": src.get("url", ""),
                "poznamka": r.get("poznamka", ""),
            })

    if rows:
        with PROVENANCE.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"→ {PROVENANCE}  ({len(rows)} dimenzí)")

        # kontrola, že tam není nic z červeného koše
        cerne = [r for r in rows if r["licencni_kos"] == "red"]
        if cerne:
            print("\n  ⚠⚠ POZOR: dimenze postavené na právně uzavřeném zdroji:")
            for r in cerne:
                print(f"     {r['dimenze']:32s} ← {r['zdroj']}")
            print("     Tohle musí z panelu ven, než se produkt prodá.")

        # staré dimenze
        dnes = dt.date.today()
        stare = []
        for r in rows:
            m = re.match(r"(\d{4})-(\d{2})", r["datum_kalibrace"] or "")
            if m:
                vek = (dnes.year - int(m.group(1))) * 12 + (dnes.month - int(m.group(2)))
                if vek > 48:
                    stare.append((r["dimenze"], r["datum_kalibrace"], vek // 12))
        if stare:
            print("\n  ⚠ Dimenze starší čtyř let:")
            for d, kdy, let in stare:
                print(f"     {d:32s} {kdy}  ({let} let)")
            print("     Do výstupu klientovi patří datum kalibrace. Panel stárne a klient má právo to vědět.")

    if chybi:
        print(f"\n  Nevyplněno u {len(chybi)} dimenzí: {', '.join(chybi[:8])}"
              + (" …" if len(chybi) > 8 else ""))


def cmd_snapshot(panel: str, version: str) -> None:
    p = Path(panel)
    if not p.exists():
        sys.exit(f"Nenalezen {panel}")
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    snap = Path(f"snapshots/panel_v{version}.csv")
    snap.parent.mkdir(exist_ok=True)
    snap.write_bytes(p.read_bytes())

    man = {
        "verze": version,
        "vytvoreno": dt.datetime.now().isoformat(timespec="seconds"),
        "soubor": str(snap),
        "sha256": h,
        "radku": sum(1 for _ in p.open(encoding="utf-8")) - 1,
        "provenience": str(PROVENANCE) if PROVENANCE.exists() else None,
    }
    Path(f"snapshots/manifest_v{version}.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {snap}")
    print(f"→ snapshots/manifest_v{version}.json")
    print(f"  sha256 {h[:16]}…")
    print("\n  Do každého výstupu klientovi tiskněte verzi panelu. Až se za půl roku")
    print("  zeptá, proč vyšlo jiné číslo, budete umět odpovědět.")


def cmd_moat(odpovedi: str) -> None:
    """Spočítá, kolik vět v promptech pochází z vašich dat a kolik z veřejných."""
    p = Path(odpovedi)
    if not p.exists():
        sys.exit(f"Nenalezen {odpovedi}. Vzniká při běhu npc_study.py.")
    if not MAPPING.exists():
        sys.exit("Nejdřív vyplňte dimenze_mapovani.csv (npc_provenance.py init).")

    trida = {}
    with MAPPING.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            trida[r["dimenze"]] = (r.get("trida") or "nezarazeno").strip() or "nezarazeno"

    pocty: dict[str, int] = {}
    celkem = 0
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for tok in (r.get("dimenze_v_promptu") or "").split(";"):
                tok = tok.strip().rstrip("+-")
                if not tok:
                    continue
                t = trida.get(tok, "nezarazeno")
                pocty[t] = pocty.get(t, 0) + 1
                celkem += 1

    if not celkem:
        print("V odpovědích nejsou žádné dimenze — pouštěl se dry-run?")
        return

    print("PODÍL VĚT V PROMPTU PODLE PŮVODU DAT")
    print("=" * 60)
    for t, n in sorted(pocty.items(), key=lambda x: -x[1]):
        print(f"  {TRIDA.get(t, t):48s} {n / celkem:6.1%}  ({n})")

    vlastni = pocty.get("vlastni", 0) / celkem
    print("\n" + "=" * 60)
    print(f"  MOAT = {vlastni:.1%} vět pochází z dat, která nikdo jiný nemá.")
    if vlastni < 0.25:
        print("\n  Pod čtvrtinou. Příběh 'máme unikátní psychometrická data' přestává")
        print("  odpovídat tomu, co produkt reálně dělá. Neznamená to, že je produkt")
        print("  špatný — znamená to, že se moat přesunul jinam: do datové vrstvy,")
        print("  kalibrace a doménové specializace. Přeformulujte podle toho i pitch,")
        print("  ať netvrdíte něco, co vám konkurence rozebere jednou otázkou.")
    elif vlastni < 0.5:
        print(f"\n  Necelá polovina ({vlastni:.0%}). Obhajitelné, ale v pitchi mluvte o kombinaci")
        print("  vlastních dat A datové vrstvy, ne o vlastních datech samotných.")
    else:
        print("\n  Většina. Původní příběh o USP sedí — a máte to čím doložit.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("table")
    s = sub.add_parser("snapshot"); s.add_argument("--panel", required=True); s.add_argument("--version", required=True)
    m = sub.add_parser("moat"); m.add_argument("--odpovedi", required=True)
    a = ap.parse_args()

    if a.cmd == "init":
        cmd_init()
    elif a.cmd == "table":
        cmd_table()
    elif a.cmd == "snapshot":
        cmd_snapshot(a.panel, a.version)
    elif a.cmd == "moat":
        cmd_moat(a.odpovedi)


if __name__ == "__main__":
    main()
