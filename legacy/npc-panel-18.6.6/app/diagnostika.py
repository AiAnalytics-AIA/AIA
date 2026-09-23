"""
NPC PANEL — diagnostika.py
Kontrola integrity panelu. Pousti se pri nacteni panelu a pred prvnim
ostrym behem, ne po nem.

    python diagnostika.py FINALNI_KOMPLETNI_PANEL.csv

Hleda veci, ktere v panelu ticha zabijeji vypovidaci hodnotu:
mrtve sloupce, konstantni vrstvy, nesmyslne hodnoty, degenerovane vazby.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

VRSTVY = {
    "dispozice": ("D_",),
    "HEXACO": ("H_", "E_", "X_", "A_", "C_", "O_"),
    "4Elements": ("Air_", "Earth_", "Fire_", "Water_"),
    "TCI-R": ("TCI_",),
    "Schwartz": ("SCHWARTZ_",),
    "spokojenost": ("spokojenost_",),
}
POVINNE = ["pohlavi", "vek", "vzdelani", "kraj", "vaha_kalibrovana"]
# Vrstvy zamerne nepouzivane v produkcni persone nesmi blokovat beh; jejich
# defekty jsou stale reportovany jako VAROVANI, aby se neztratily z backlogu.
NONBLOCKING_PREFIXES = ("SCHWARTZ_", "_donor_", "profile_", "vaha_", "marketing_", "values_", "financial_capability_confidence")
INTENTIONAL_CONSTANTS = {"brand_specific_background_ready"}

# Hierarchical codes are intentionally nested representations of one measured concept,
# not fake independent evidence. They are kept because different product views need
# 1-digit, 2-digit and full ISCO detail.
EXPECTED_HIERARCHICAL_PAIRS = {
    frozenset({'occupation_isco08','occupation_2digit'}),
    frozenset({'occupation_isco08','occupation_major'}),
    frozenset({'occupation_2digit','occupation_major'}),
}
# Explicit compatibility/raw-source aliases are intentionally redundant.  They are
# useful for audit/backward-compatible product views but must not be mistaken for
# two independent evidential variables.
EXPECTED_ALIAS_PAIRS = {
    frozenset({'pocet_deti_celkem','pocet_deti'}),
    frozenset({'core_marital_status','ISSP_B34'}),
    frozenset({'core_religion_group','ISSP_B21'}),
    frozenset({'core_religious_attendance','ISSP_B22'}),
    frozenset({'CSES_E3013_LH_PL','volba_2021_kod'}),
    frozenset({'prijem_decile','prijem_pozice_0_1'}),
    frozenset({'core_religious_attendance','religious_practice_1_10'}),
    frozenset({'ISSP_B22','religious_practice_1_10'}),
    frozenset({'vaha_kalibrovana','vaha_populace_2025_aprox'}),
    frozenset({'private_travel_trips_year_model','travel_intensity_1_10'}),
}
PROVENANCE_NUMERIC = {'core_donor_age','core_match_distance'}


def diagnostika(df: pd.DataFrame, min_vek: int = 18) -> dict:
    n = len(df)
    nalezy: list[tuple[str, str]] = []
    fakta: dict[str, object] = {"n_radku": n, "n_sloupcu": df.shape[1]}

    def flag(uroven: str, text: str) -> None:
        nalezy.append((uroven, text))

    chybi = [c for c in POVINNE if c not in df.columns]
    if not ({"panel_row_id", "respondent_id"} & set(df.columns)):
        chybi = ["panel_row_id/respondent_id"] + chybi
    if chybi:
        flag("KRITICKE", f"chybi povinne sloupce: {chybi}")

    # --- mrtve sloupce (nulovy nebo temer nulovy rozptyl)
    spojite = tuple(p for pref in VRSTVY.values() for p in pref)
    mrtve, skoro = [], []
    for c in df.select_dtypes(include=[np.number]).columns:
        s = df[c].dropna()
        if (len(s) == 0 or s.nunique() <= 1) and c not in INTENTIONAL_CONSTANTS:
            mrtve.append(c)
        elif c.startswith(spojite) and s.nunique() <= 5:
            skoro.append(c)   # spojita psychologicka dimenze s par hodnotami
    fakta["mrtve_sloupce"] = mrtve
    fakta["temer_mrtve_sloupce"] = skoro
    if mrtve:
        blokujici = [c for c in mrtve if not c.startswith(NONBLOCKING_PREFIXES)]
        uroven = "KRITICKE" if blokujici else "VAROVANI"
        flag(uroven, f"{len(mrtve)} sloupcu ma nulovy rozptyl (stejna hodnota "
                     f"u vsech respondentu): {', '.join(mrtve)}")
    if skoro:
        flag("VAROVANI", f"spojite dimenze s nejvyse 5 hodnotami (fakticky mrtve): "
                         f"{', '.join(skoro)}")

    # --- vrstvy: kolik z nich vubec nese informaci
    prehled_vrstev = {}
    for nazev, prefixy in VRSTVY.items():
        cols = [c for c in df.columns if c.startswith(prefixy)
                and pd.api.types.is_numeric_dtype(df[c])]
        zive = [c for c in cols if df[c].dropna().nunique() > 5]
        prehled_vrstev[nazev] = {"sloupcu": len(cols), "zivych": len(zive),
                                 "prum_sd": round(float(np.mean(
                                     [df[c].std() for c in zive])), 3) if zive else 0.0}
        if cols and len(zive) < len(cols):
            sev = "VAROVANI" if nazev == "Schwartz" else (
                "KRITICKE" if len(zive) <= len(cols) / 2 else "VAROVANI")
            flag(sev, f"vrstva {nazev}: jen {len(zive)} z {len(cols)} dimenzi ma rozptyl "
                 f"— zbytek je konstanta a do persony nic nepridava")
    fakta["vrstvy"] = prehled_vrstev

    # --- individualita vs. skupinovy atribut
    for nazev, prefixy in VRSTVY.items():
        cols = [c for c in df.columns if c.startswith(prefixy)]
        if not cols or n == 0:
            continue
        unik = df[cols].drop_duplicates().shape[0]
        if unik <= 12 and len(cols) > 1:
            flag("VAROVANI",
                 f"vrstva {nazev} ma jen {unik} unikatnich kombinaci na {n} "
                 f"respondentu — neni to individualni promenna, ale atribut skupiny")

    # --- sloupce, ktere jsou jen prejmenovanou kopii jineho
    import itertools
    num = df.select_dtypes(include=[np.number])
    num = num[[c for c in num.columns if num[c].dropna().nunique() > 5]]
    if num.shape[1] > 1:
        korel = num.corr().abs()
        kopie = [(a, b, round(float(korel.loc[a, b]), 3))
                 for a, b in itertools.combinations(korel.columns, 2)
                 if korel.loc[a, b] > 0.98]
        fakta["redundantni_pary"] = kopie
        for a, b, r in sorted(kopie, key=lambda x: -x[2]):
            if frozenset({a,b}) in EXPECTED_HIERARCHICAL_PAIRS or frozenset({a,b}) in EXPECTED_ALIAS_PAIRS:
                continue
            if a in PROVENANCE_NUMERIC or b in PROVENANCE_NUMERIC:
                continue
            nonblocking = a.startswith(NONBLOCKING_PREFIXES) or b.startswith(NONBLOCKING_PREFIXES)
            sev = "VAROVANI" if nonblocking else ("KRITICKE" if r > 0.995 else "VAROVANI")
            flag(sev, f"{a} a {b} koreluji na r={r} — druhy sloupec nenese zadnou "
                 "informaci navic, je to prvni sloupec v jine skale")

    # --- vek
    if "vek" in df.columns:
        v = pd.to_numeric(df["vek"], errors="coerce")
        fakta["vek"] = {"min": float(v.min()), "max": float(v.max()),
                        "pod_15": int((v < 15).sum()), "pod_18": int((v < 18).sum()),
                        "nula": int((v == 0).sum()), "chybi": int(v.isna().sum())}
        if fakta["vek"]["nula"]:
            sev = "VAROVANI" if min_vek and min_vek > 0 else "KRITICKE"
            flag(sev, f"{fakta['vek']['nula']} respondentu ma vek 0 "
                      f"— necisteny sentinel; Panel.load(min_vek={min_vek}) je pred behom vyradi")
        if fakta["vek"]["pod_18"]:
            flag("VAROVANI", f"{fakta['vek']['pod_18']} respondentu je mladsich 18 let "
                             "— pro pruzkumy o spotrebe, politice a financich je "
                             "vylucte (Panel.load(min_vek=18))")

    # --- prijem
    if "prijem_cisty_mesicni" in df.columns:
        p = pd.to_numeric(df["prijem_cisty_mesicni"], errors="coerce")
        nenul = int((p > 0).sum())
        fakta["prijem"] = {"vyplneno_pct": round(100 * p.notna().mean(), 1),
                           "nenulovych_pct": round(100 * nenul / n, 1),
                           "nul_mezi_vyplnenymi": int((p == 0).sum())}
        if fakta["prijem"]["nul_mezi_vyplnenymi"] > 0.1 * max(p.notna().sum(), 1):
            flag("VAROVANI",
                 f"{fakta['prijem']['nul_mezi_vyplnenymi']} zaznamu ma prijem presne 0 "
                 "— skutecne pokryti je nizsi, nez naznacuje podil neprazdnych")

    # --- vahy
    if "vaha_kalibrovana" in df.columns:
        w = pd.to_numeric(df["vaha_kalibrovana"], errors="coerce").fillna(0)
        deff = len(w) * (w ** 2).sum() / (w.sum() ** 2) if w.sum() else np.nan
        fakta["vahy"] = {"min": round(float(w.min()), 3), "max": round(float(w.max()), 3),
                         "deff": round(float(deff), 3),
                         "n_efektivni": int(len(w) / deff) if deff else 0}
        if w.min() <= 0:
            flag("VAROVANI", "nektere vahy jsou nulove nebo zaporne")
        if deff > 1.5:
            flag("VAROVANI", f"design efekt {deff:.2f} — intervaly spolehlivosti "
                             "jsou sirsi, nez odpovida velikosti vzorku")

    # --- duplicity
    if "respondent_id" in df.columns:
        dup = int(df["respondent_id"].duplicated().sum())
        if dup:
            flag("KRITICKE", f"{dup} duplicitnich respondent_id")

    uroven = ("KRITICKE" if any(u == "KRITICKE" for u, _ in nalezy)
              else "VAROVANI" if nalezy else "OK")
    return {"uroven": uroven, "nalezy": nalezy, "fakta": fakta}


def tabulka_diagnostiky(d: dict) -> str:
    r = [f"=== DIAGNOSTIKA PANELU: {d['uroven']} ===",
         f"{d['fakta']['n_radku']} radku x {d['fakta']['n_sloupcu']} sloupcu", ""]
    for uroven, text in sorted(d["nalezy"], key=lambda x: x[0] != "KRITICKE"):
        r.append(f"  [{uroven:9}] {text}")
    r += ["", "  vrstva        sloupcu  zivych  prum. SD"]
    for nazev, v in d["fakta"].get("vrstvy", {}).items():
        r.append(f"  {nazev:14}{v['sloupcu']:>6}{v['zivych']:>8}{v['prum_sd']:>10}")
    for k in ("vek", "prijem", "vahy"):
        if k in d["fakta"]:
            r.append(f"  {k}: {d['fakta'][k]}")
    return "\n".join(r)


if __name__ == "__main__":
    cesta = sys.argv[1] if len(sys.argv) > 1 else "FINALNI_KOMPLETNI_PANEL.csv"
    df = pd.read_csv(Path(cesta), low_memory=False)
    print(tabulka_diagnostiky(diagnostika(df)))
