#!/usr/bin/env python3
"""
npc_fetch.py — stahování zeleného koše datových zdrojů pro NPC Panel
====================================================================

Co to dělá
----------
Stáhne české a evropské datové zdroje, u kterých je OVĚŘENO, že je smíte použít
komerčně, a převede je do dvou tabulek, které se dají rovnou napojit na panel:

  1. eurostat_margins.csv  — dlouhý formát: kód, dimenze, kategorie, hodnota.
     Tohle jsou marginální a společná rozdělení (cesta "b"): kalibrujete podle nich
     dimenzní sloupce tak, aby seděly na reálná česká čísla.

  2. obce_features.csv     — široký formát: jeden řádek = jedna obec, sloupce =
     ukazatele. Tohle je cesta "c": připojíte na obec (nebo agregujete na kraj)
     a dimenzi odvodíte z místa, aniž byste se kohokoli ptali.

Proč je to rozdělené na "discover" a "fetch"
--------------------------------------------
U Eurostatu je API stabilní a kódy jsou ověřené, takže se stahuje přímo.
U českých zdrojů se konkrétní názvy souborů mění mezi ročníky a vydáními.
Skript proto URL NEHÁDÁ — nejdřív je vyhledá v katalozích (NKOD, DCAT) a vypíše
je ke kontrole. Radši jeden ruční pohled než tiše stažený špatný soubor.

Použití
-------
    pip install requests pandas
    python npc_fetch.py eurostat            # stáhne ověřené Eurostat kódy
    python npc_fetch.py discover            # najde URL českých zdrojů, vypíše je
    python npc_fetch.py fetch               # stáhne české zdroje podle sources.json
    python npc_fetch.py build               # složí obce_features.csv
    python npc_fetch.py all

Licenční poznámka
-----------------
Všechny zdroje níže mají ověřeno, že komerční užití povolují. Eurostat vyžaduje
uvedení zdroje; ČSÚ vyžaduje uvést "Český statistický úřad" a nezměnit význam
údajů; EKČR je CC BY 4.0. Skript proto do každého výstupu zapisuje sloupec
`source` a vedle něj soubor ATTRIBUTION.txt — needitujte ho pryč, je to podmínka
licence, ne dekorace.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
    import pandas as pd
except ImportError:
    sys.exit("Chybí závislosti. Spusťte: pip install requests pandas")

RAW = Path("data/raw")
OUT = Path("data/out")
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "NPC-Panel-datafetch/1.0 (Artchain s.r.o.)"}
TIMEOUT = 60


# ---------------------------------------------------------------------------
# 1. EUROSTAT — ověřené kódy
# ---------------------------------------------------------------------------
# Ověřeno živým dotazem na disseminační API, všechny vrací česká data.
# Přípona kódu určuje členění:
#   e = vzdělání (ISCED 2011)   i = příjmový kvintil   u = urbanizace
#   b = země narození           c = občanství          d = míra postižení
# Chcete-li jiné členění, změňte poslední písmeno — ale ověřte si, že varianta
# existuje, ne všechny kombinace jsou naplněné.

EUROSTAT = {
    # --- ZDRAVÍ (EHIS, vlny 2014 a 2019) ---
    "hlth_ehis_bm1e": "BMI podle pohlaví, věku a vzdělání",
    "hlth_ehis_sk1e": "Kouření tabákových výrobků",
    "hlth_ehis_sk3e": "Denní kuřáci cigaret",
    "hlth_ehis_sk6e": "Elektronické cigarety (jen 2019)",
    "hlth_ehis_al1e": "Frekvence konzumace alkoholu",
    "hlth_ehis_al2e": "Rizikoví konzumenti alkoholu (jen 2014)",
    "hlth_ehis_pe9e": "Pohybová aktivita prospěšná zdraví",
    "hlth_ehis_pe2e": "Čas strávený aerobní pohybovou aktivitou",
    "hlth_ehis_fv1e": "Frekvence konzumace ovoce a zeleniny",
    "hlth_ehis_fv3e": "Denní konzumace ovoce a zeleniny (porce)",
    "hlth_ehis_am2e": "Návštěvy lékaře (praktik vs. specialista)",
    "hlth_ehis_un1e": "Neuspokojené potřeby zdravotní péče a jejich důvody",
    "hlth_ehis_pa1e": "Očkování proti chřipce",
    "hlth_ehis_pa5e": "Poslední screening kolorektálního karcinomu",
    "hlth_ehis_pa6e": "Poslední kolonoskopie",
    "hlth_ehis_pa7e": "Poslední mamografie (jen ženy, bez dimenze sex)",
    "hlth_ehis_pa8e": "Poslední cytologie (jen ženy, bez dimenze sex)",
    "hlth_ehis_ss1e": "Vnímaná sociální opora — škála Oslo-3",
    "hlth_ehis_ic1e": "Poskytování neformální péče alespoň týdně",
    "hlth_ehis_pl1e": "Funkční omezení",
    "hlth_ehis_mh1e": "Depresivní symptomy — škála PHQ-8",
    "hlth_ehis_cd1e": "Chronická onemocnění (16 diagnóz)",
    # Sebehodnocené zdraví NENÍ v EHIS — bere se z EU-SILC. Roční řada.
    "hlth_silc_02": "Sebehodnocené zdraví (EU-SILC, roční řada)",
    # --- VOLNÝ ČAS (modul EU-SILC 2022, další vlna cca 2028) ---
    "ilc_scp03": "Účast na kulturních a sportovních aktivitách",
    "ilc_scp05": "Neúčast na aktivitách a její důvody",
    "ilc_scp07": "Provozování umělecké činnosti",
    "ilc_scp27": "Čtení knih a počet přečtených knih",
    # --- CESTOVNÍ RUCH (pozor: členění podle vzdělání NEEXISTUJE) ---
    "tour_dem_toage": "Účast na cestovním ruchu podle věku",
    "tour_dem_tosex": "Účast na cestovním ruchu podle pohlaví",
    "tour_dem_tttot": "Cesty podle délky, účelu a destinace",
    # --- DIGITÁLNÍ ŽIVOT / GAMING ---
    "isoc_ci_ac_i": "Internetové aktivity (ukazatel I_IUPDG = hraní her)",
}

EUROSTAT_API = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}"
    "?format=JSON&lang=EN&geo=CZ"
)


def parse_jsonstat(payload: dict, code: str) -> pd.DataFrame:
    """Rozloží JSON-stat 2.0 na dlouhou tabulku: jeden řádek = jedna buňka.

    JSON-stat ukládá hodnoty v jednom plochém slovníku, klíčem je index
    spočítaný z pozic v jednotlivých dimenzích. Musíme ten index rozmotat zpět.
    """
    dims = payload["id"]
    sizes = payload["size"]
    values = payload.get("value", {})
    if not values:
        return pd.DataFrame()

    # Pro každou dimenzi: pořadí kategorií podle indexu + čitelné popisky
    cats, labels = [], []
    for d in dims:
        meta = payload["dimension"][d]
        idx = meta["category"]["index"]
        if isinstance(idx, dict):
            ordered = sorted(idx, key=lambda k: idx[k])
        else:  # některé datasety vrací index jako seznam
            ordered = list(idx)
        cats.append(ordered)
        labels.append(meta["category"].get("label", {}))

    # Násobiče pro převod plochého indexu na souřadnice
    strides, acc = [], 1
    for n in reversed(sizes):
        strides.insert(0, acc)
        acc *= n

    rows = []
    for flat, val in values.items():
        if val is None:
            continue
        i = int(flat)
        row = {"code": code}
        for d, cat, lab, stride in zip(dims, cats, labels, strides):
            pos = (i // stride) % len(cat)
            key = cat[pos]
            row[d] = key
            row[f"{d}_label"] = lab.get(key, key)
        row["value"] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    df["source"] = "Eurostat"
    return df


def fetch_eurostat() -> None:
    frames, failed = [], []
    for code, desc in EUROSTAT.items():
        url = EUROSTAT_API.format(code=code)
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code == 404:
                failed.append((code, "404 — kód neexistuje"))
                print(f"  ✗ {code:22s} 404")
                continue
            r.raise_for_status()
            df = parse_jsonstat(r.json(), code)
            if df.empty:
                failed.append((code, "prázdné hodnoty pro CZ"))
                print(f"  ✗ {code:22s} prázdné")
                continue
            df["description"] = desc
            frames.append(df)
            print(f"  ✓ {code:22s} {len(df):6d} buněk   {desc}")
        except Exception as e:  # noqa: BLE001
            failed.append((code, str(e)[:80]))
            print(f"  ✗ {code:22s} {e}")
        time.sleep(0.4)  # slušnost vůči API

    if frames:
        out = pd.concat(frames, ignore_index=True)
        path = OUT / "eurostat_margins.csv"
        out.to_csv(path, index=False, encoding="utf-8")
        print(f"\n→ {path}  ({len(out):,} řádků, {out['code'].nunique()} datasetů)")
    if failed:
        print("\nNepodařilo se:")
        for c, why in failed:
            print(f"  {c:22s} {why}")


# ---------------------------------------------------------------------------
# 2. ČESKÉ ZDROJE — discovery, ne hádání URL
# ---------------------------------------------------------------------------

CZ_SOURCES = {
    "volby_ps2025": {
        "label": "Volby do PS 2025 — okrsková data",
        "index": "https://volby.gov.cz/opendata/ps2025/ps2025_opendata.htm",
        "match": r"\.(zip|csv|xml)$",
        "note": "Chcete soubor s okrskovými výsledky. Zkontrolujte, že jde o okrsky, ne obce.",
        "licence": "CC BY 4.0, ČSÚ — komerční užití povoleno",
    },
    "volby_ps2021": {
        "label": "Volby do PS 2021 — okrsková data",
        "index": "https://volby.gov.cz/opendata/ps2021/ps2021_opendata.htm",
        "match": r"\.(zip|csv|xml)$",
        "note": "Druhá vlna pro časový trend.",
        "licence": "CC BY 4.0, ČSÚ",
    },
    "mos": {
        "label": "Databáze MOS — 792 ukazatelů × obce",
        "index": "https://csu.gov.cz/databaze-mos-otevrena-data-dokumentace",
        "match": r"\.(csv|zip)$",
        "note": "CSV je UTF-8 bez BOM, oddělovač čárka, konce řádků CRLF.",
        "licence": "CC BY 4.0, ČSÚ",
    },
    "ekcr": {
        "label": "Exekuce — Exekutorská komora ČR",
        "dcat": "https://statistiky.ekcr.info/otevrena-data/katalog.jsonld",
        "note": "Chcete sadu s počtem osob v exekuci podle obcí.",
        "licence": "CC BY 4.0 mezinárodní, výslovně vč. komerčního užití",
    },
    "sldb": {
        "label": "Sčítání 2021 — otevřená data",
        "index": "https://csu.gov.cz/vysledky-scitani-2021-otevrena-data-dokumentace",
        "match": r"\.(csv|zip)$",
        "note": "Rodinný stav, domácnosti, děti, národnost, mateřský jazyk, náboženství.",
        "licence": "CC BY 4.0, ČSÚ",
    },
}

NKOD_API = "https://data.gov.cz/api/3/action/package_search"


def discover() -> None:
    """Najde konkrétní URL souborů a uloží je do sources.json ke kontrole."""
    found: dict[str, dict] = {}

    for key, spec in CZ_SOURCES.items():
        print(f"\n[{key}] {spec['label']}")
        links: list[str] = []

        if "dcat" in spec:
            try:
                r = requests.get(spec["dcat"], headers=UA, timeout=TIMEOUT)
                r.raise_for_status()
                blob = json.dumps(r.json())
                links = sorted(set(re.findall(r'https?://[^"\s]+\.(?:csv|json)', blob)))
            except Exception as e:  # noqa: BLE001
                print(f"  ! DCAT katalog nedostupný: {e}")
        else:
            try:
                r = requests.get(spec["index"], headers=UA, timeout=TIMEOUT)
                r.raise_for_status()
                hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.text, re.I)
                links = sorted({
                    urljoin(spec["index"], h) for h in hrefs
                    if re.search(spec["match"], h, re.I)
                })
            except Exception as e:  # noqa: BLE001
                print(f"  ! Stránka nedostupná: {e}")

        if links:
            for l in links[:15]:
                print(f"    {l}")
            if len(links) > 15:
                print(f"    … a dalších {len(links) - 15}")
        else:
            print("    (nic nenalezeno — otevřete stránku ručně a URL doplňte)")

        found[key] = {
            "label": spec["label"],
            "note": spec.get("note", ""),
            "licence": spec["licence"],
            "candidates": links,
            "chosen": links[0] if len(links) == 1 else None,
        }

    path = Path("sources.json")
    path.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {path}")
    print("Projděte kandidáty, u každého zdroje vyplňte pole \"chosen\", pak spusťte: python npc_fetch.py fetch")


def fetch_cz() -> None:
    path = Path("sources.json")
    if not path.exists():
        sys.exit("Nejdřív spusťte: python npc_fetch.py discover")
    spec = json.loads(path.read_text(encoding="utf-8"))

    for key, s in spec.items():
        url = s.get("chosen")
        if not url:
            print(f"  – {key}: přeskočeno, není vyplněno \"chosen\"")
            continue
        dest = RAW / f"{key}{Path(url).suffix or '.dat'}"
        if dest.exists():
            print(f"  = {key}: už staženo ({dest})")
            continue
        try:
            with requests.get(url, headers=UA, timeout=300, stream=True) as r:
                r.raise_for_status()
                with dest.open("wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            print(f"  ✓ {key}: {dest} ({dest.stat().st_size:,} B)")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {key}: {e}")


# ---------------------------------------------------------------------------
# 3. BUILD — spojení na kód obce
# ---------------------------------------------------------------------------
# Klíč je šestimístný kód obce podle ČSÚ. V různých souborech se sloupec jmenuje
# různě, proto kandidáti níže. Kód se všude normalizuje na string bez mezer,
# protože jinak se pandas při spojení rozejde (int vs. str).

OBEC_KEYS = ["KOD_OBEC", "kod_obce", "KODOBEC", "OBEC", "obec_kod", "ICOB", "kod"]


def _read_any(path: Path) -> pd.DataFrame | None:
    for enc in ("utf-8", "utf-8-sig", "cp1250"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep, dtype=str, low_memory=False)
                if df.shape[1] > 1:
                    return df
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def _find_key(df: pd.DataFrame) -> str | None:
    upper = {c.upper(): c for c in df.columns}
    for cand in OBEC_KEYS:
        if cand.upper() in upper:
            return upper[cand.upper()]
    return None


def build() -> None:
    files = sorted(RAW.glob("*.csv")) + sorted(RAW.glob("*.CSV"))
    if not files:
        sys.exit("V data/raw nejsou žádná CSV. Spusťte discover a fetch.")

    base: pd.DataFrame | None = None
    for f in files:
        df = _read_any(f)
        if df is None:
            print(f"  ✗ {f.name}: nepodařilo se přečíst")
            continue
        key = _find_key(df)
        if not key:
            print(f"  – {f.name}: nenalezen sloupec s kódem obce, přeskakuji")
            print(f"      sloupce: {list(df.columns)[:12]}")
            continue
        df[key] = df[key].astype(str).str.strip()
        df = df.rename(columns={key: "kod_obce"})
        df = df.add_prefix(f"{f.stem}__").rename(
            columns={f"{f.stem}__kod_obce": "kod_obce"}
        )
        base = df if base is None else base.merge(df, on="kod_obce", how="outer")
        print(f"  ✓ {f.name}: {len(df):,} řádků, {df.shape[1] - 1} sloupců")

    if base is None:
        sys.exit("Nic se nespojilo.")

    out = OUT / "obce_features.csv"
    base.to_csv(out, index=False, encoding="utf-8")
    n = base["kod_obce"].nunique()
    print(f"\n→ {out}  ({n:,} obcí, {base.shape[1]} sloupců)")
    if not 6000 <= n <= 6500:
        print(f"  ⚠ Pozor: očekáváno zhruba 6 258 obcí, spojilo se {n:,}.")
        print("    Nejčastější příčina je nesourodý formát kódu obce mezi soubory.")


ATTRIBUTION = """Zdroje dat a povinné uvedení
============================
Eurostat — © European Union. Reuse authorised provided the source is acknowledged.
  Komerční šíření je výslovně povoleno.
Český statistický úřad — CC BY 4.0. Podmínkou je uvedení "Český statistický úřad"
  jako zdroje a zákaz změny významu údajů.
Exekutorská komora ČR — CC BY 4.0 mezinárodní, výslovně včetně komerčního užití.

Tento soubor nemažte. Uvedení zdroje je licenční podmínka, ne formalita.
"""


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    (OUT / "ATTRIBUTION.txt").write_text(ATTRIBUTION, encoding="utf-8")

    if cmd in ("eurostat", "all"):
        print("\n=== EUROSTAT ===")
        fetch_eurostat()
    if cmd in ("discover", "all"):
        print("\n=== DISCOVERY ČESKÝCH ZDROJŮ ===")
        discover()
    if cmd == "fetch":
        print("\n=== STAHOVÁNÍ ČESKÝCH ZDROJŮ ===")
        fetch_cz()
    if cmd == "build":
        print("\n=== SPOJENÍ NA KÓD OBCE ===")
        build()
    if cmd not in ("eurostat", "discover", "fetch", "build", "all"):
        print(__doc__)


if __name__ == "__main__":
    main()
