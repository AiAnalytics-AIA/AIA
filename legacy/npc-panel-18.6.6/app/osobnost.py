"""
NPC PANEL — osobnost.py
Prerozdeleni osobnostnich vrstev tak, aby korelovaly s demografii.

PROBLEM, KTERY TO RESI
V puvodnim panelu je HEXACO/4E/TCI nalosovane nezavisle na vsem krome pohlavi.
Korelace s vekem i vzdelanim je 0,00-0,03. Dvacetilety vysokoskolak z Prahy ma
stejne rozdeleni osobnosti jako sedmdesatilety vyuceny z Usti. Rozptyl v panelu
tim vznika, ale nekoreluje s nicim realnym — a kdyz se pak agreguje odpoved
podle vzdelani nebo veku, osobnost se vyrusi a zbyde ciste demografie.

CO TO DELA
Pregeneruje osobnostni skore jako: demograficky signal + reziduum.
  - demograficky signal ma silu podle publikovanych efektu (viz EFEKTY)
  - reziduum ma takovou kovariancni strukturu, aby VYSLEDNE vzajemne korelace
    rysu zustaly stejne jako v puvodnim panelu (tedy ceske normy)
  - vysledek se kvantilove namapuje zpet na puvodni rozdeleni sloupce, takze
    prumer, SD i tvar (vcetne mezi 1-5 u HEXACO) zustavaji presne stejne

Jinymi slovy: agregatni normy se nemeni, meni se JEN to, kdo ktere skore dostane.

ZDROJE EFEKTU
  Moshagen, Thielmann, Hilbig & Zettler (2019), Zeitschrift fur Psychologie
    227(3), meta-analyza 549 vzorku / 316 133 osob:
    - nejsilnejsi vazba veku je Poctivost-pokora, r = 0,25
    - Extraverze, Svedomitost a Otevrenost maji taky kladnou, ale mensi vazbu
    - vazby na vzdelani jsou celkove slabe
  Lee & Ashton, meta-analyza genderovych rozdilu (k = 78, N = 135 959):
    d (zeny - muzi) = 1,03 Emocionalita | 0,45 Poctivost-pokora |
    0,16 Svedomitost | 0,09 Otevrenost | -0,03 Extraverze | -0,01 Privetivost
  Urbanicita: geograficke studie osobnosti (Rentfrow a nasl.) davaji rozdily
    mezi regiony radove 0,05-0,15 SD; pouzity odpovidajici slabe koeficienty.

CO JE ODHAD, NE MERENI
  - presna sila vazby veku u X, C, O (meta-analyza uvadi "mensi kladna",
    bez cisla) — dosazeno 0,05-0,12
  - vsechny koeficienty pro 4Elements: pro cesky 4E nejsou publikovane
    demograficke vazby, odvozeno z obsahu dimenzi
  - podil mestskeho obyvatelstva podle kraju je priblizny

    python osobnost.py FINALNI_KOMPLETNI_PANEL.csv -o PANEL_v2.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- efekty
# cilove korelace rysu s demografickymi promennymi (ne regresni koeficienty —
# ty se z nich dopocitaji s ohledem na to, ze demografie sama koreluje)
# poradi: vek, vek^2, muz, vzdelani, urbanicita

EFEKTY: dict[str, dict[str, float]] = {
    # HEXACO — Moshagen 2019 (vek), Lee & Ashton (pohlavi), oboji meta-analyza
    "H_Poctivost_pokora":         {"vek": 0.25, "muz": -0.22, "vzd": -0.05, "urb": -0.04},
    "E_Emocionalita":             {"vek": -0.05, "muz": -0.46, "vzd": -0.05, "urb": 0.00},
    "X_Extraverze":               {"vek": 0.05, "muz": 0.02, "vzd": 0.07, "urb": 0.05},
    "A_Privetivost":              {"vek": 0.10, "muz": 0.00, "vzd": -0.03, "urb": -0.06},
    "C_Svedomitost":              {"vek": 0.12, "muz": -0.08, "vzd": 0.06, "urb": -0.04},
    "O_Otevrenost":               {"vek": 0.05, "muz": -0.04, "vzd": 0.14, "urb": 0.08},
    # 4Elements — bez publikovanych demografickych vazeb, odvozeno z obsahu
    "Fire_Ohen":                  {"vek": -0.15, "muz": 0.15, "vzd": 0.05, "urb": 0.05},
    "Air_Vzduch":                 {"vek": -0.15, "muz": 0.00, "vzd": 0.15, "urb": 0.08},
    "Earth_Zeme":                 {"vek": 0.20, "muz": -0.05, "vzd": -0.05, "urb": -0.06},
    "Water_Voda":                 {"vek": 0.05, "muz": -0.35, "vzd": 0.00, "urb": 0.00},
}

# kvadraticky clen veku — jen tam, kde ma smysl (nelinearni prubeh)
EFEKTY_VEK2 = {"X_Extraverze": -0.06, "O_Otevrenost": -0.08, "Fire_Ohen": -0.05}

VZDELANI_PORADI = {"základní": 1, "střední bez maturity": 2,
                   "střední s maturitou": 3, "VOŠ/VŠ": 4}

# priblizny podil mestskeho obyvatelstva podle kraje (0-1)
URBANICITA = {
    "Praha": 1.00, "Ústecký": 0.79, "Moravskoslezský": 0.76, "Karlovarský": 0.72,
    "Liberecký": 0.65, "Jihomoravský": 0.64, "Plzeňský": 0.62, "Olomoucký": 0.57,
    "Královehradecký": 0.55, "Královéhradecký": 0.55, "Zlínský": 0.54,
    "Jihočeský": 0.54, "Pardubický": 0.52, "Středočeský": 0.50, "Vysočina": 0.47,
}


# ---------------------------------------------------------------- nastroje

def _z(x: pd.Series | np.ndarray) -> np.ndarray:
    x = pd.to_numeric(pd.Series(np.asarray(x, dtype=float)), errors="coerce")
    x = x.fillna(x.mean())
    sd = x.std(ddof=0)
    return ((x - x.mean()) / (sd if sd else 1.0)).to_numpy()


def _psd_cholesky(S: np.ndarray) -> np.ndarray:
    """Choleskyho rozklad odolny vuci mirne nepozitivne definitni matici."""
    vals, vecs = np.linalg.eigh(S)
    vals = np.clip(vals, 1e-8, None)
    return vecs @ np.diag(np.sqrt(vals))


def _kvantilove_mapovani(nove_z: np.ndarray, puvodni: np.ndarray) -> np.ndarray:
    """Priradi hodnoty z puvodniho rozdeleni podle poradi v novem skore.

    Zaruceno: vysledek ma PRESNE stejne rozdeleni (prumer, SD, tvar, meze)
    jako puvodni sloupec. Meni se jen to, kdo kterou hodnotu dostane.
    """
    poradi = np.argsort(np.argsort(nove_z))
    serazene = np.sort(np.asarray(puvodni, dtype=float))
    return serazene[poradi]


# ---------------------------------------------------------------- jadro

def prerozdel_osobnost(
    df: pd.DataFrame,
    seed: int = 20260812,
    tichy: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vrati (novy panel, zprava o dosazenych korelacich)."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    log = (lambda *a: None) if tichy else print

    # --- design matrix
    vek = _z(df["vek"])
    X = {
        "vek": vek,
        "vek2": _z(vek ** 2),
        "muz": _z((df["pohlavi"].astype(str).str.lower().str.startswith("mu")).astype(float)),
        "vzd": _z(df["vzdelani"].map(VZDELANI_PORADI)),
        "urb": _z(df["kraj"].map(URBANICITA)),
    }
    jmena_x = list(X)
    Xm = np.column_stack([X[k] for k in jmena_x])
    Rxx = np.corrcoef(Xm, rowvar=False)

    rysy = [c for c in EFEKTY if c in df.columns]
    if not rysy:
        raise ValueError("V panelu nejsou zadne sloupce z EFEKTY.")

    # --- cilove korelace -> regresni koeficienty (ocisteno o vazby uvnitr demografie)
    B = np.zeros((len(jmena_x), len(rysy)))
    for j, rys in enumerate(rysy):
        r = np.array([EFEKTY[rys].get(k, 0.0) if k != "vek2"
                      else EFEKTY_VEK2.get(rys, 0.0) for k in jmena_x])
        B[:, j] = np.linalg.solve(Rxx, r)

    # --- cilova korelacni matice rysu = ta, kterou ma panel ted (ceske normy)
    R_cil = np.corrcoef(df[rysy].to_numpy(dtype=float), rowvar=False)

    # --- rezidualni kovariance tak, aby soucet dal R_cil
    S_signal = B.T @ Rxx @ B
    var_signal = np.diag(S_signal)
    prilis = var_signal >= 0.9
    if prilis.any():
        skala = np.ones(len(rysy))
        skala[prilis] = np.sqrt(0.9 / var_signal[prilis])
        B = B * skala
        S_signal = B.T @ Rxx @ B
        var_signal = np.diag(S_signal)
        log(f"[osobnost] zeslabeno {int(prilis.sum())} rysu — signal by prekrocil "
            "90 % rozptylu")

    S_rezid = R_cil - S_signal
    vals = np.linalg.eigvalsh(S_rezid)
    if vals.min() < 1e-8:
        # zeslabit signal globalne, dokud rezidualni matice neni pouzitelna
        for krok in np.linspace(0.95, 0.3, 14):
            S_rezid = R_cil - krok ** 2 * S_signal
            if np.linalg.eigvalsh(S_rezid).min() > 1e-8:
                B = B * krok
                S_signal = B.T @ Rxx @ B
                log(f"[osobnost] signal zeslaben na {krok:.2f} kvuli zachovani "
                    "korelacni struktury rysu")
                break

    L = _psd_cholesky(S_rezid)
    E = rng.standard_normal((len(df), len(rysy))) @ L.T
    Znove = Xm @ B + E

    # --- zpet na puvodni rozdeleni
    for j, rys in enumerate(rysy):
        out[rys] = _kvantilove_mapovani(Znove[:, j], df[rys].to_numpy(dtype=float))

    # --- TCI se dopocita z noveho 4E stejnym vztahem, jaky ma panel ted
    ctyri = [c for c in ("Air_Vzduch", "Earth_Zeme", "Fire_Ohen", "Water_Voda")
             if c in df.columns]
    tci = [c for c in df.columns if c.startswith("TCI_")]
    if ctyri and tci:
        A_stare = np.column_stack([np.ones(len(df))] + [df[c].to_numpy(float) for c in ctyri])
        A_nove = np.column_stack([np.ones(len(df))] + [out[c].to_numpy(float) for c in ctyri])
        for c in tci:
            y = df[c].to_numpy(float)
            koef, *_ = np.linalg.lstsq(A_stare, y, rcond=None)
            rezid = y - A_stare @ koef
            out[c] = _kvantilove_mapovani(A_nove @ koef + rezid, y)
        log(f"[osobnost] TCI-R prepocitano z noveho 4E puvodnim vztahem "
            f"({len(tci)} dimenzi)")

    # --- zprava
    radky = []
    for rys in rysy + tci:
        zaznam = {"rys": rys}
        for k in ("vek", "muz", "vzd", "urb"):
            zaznam[f"cil_{k}"] = EFEKTY.get(rys, {}).get(k, np.nan)
            zaznam[f"pred_{k}"] = round(float(np.corrcoef(X[k], df[rys])[0, 1]), 3)
            zaznam[f"po_{k}"] = round(float(np.corrcoef(X[k], out[rys])[0, 1]), 3)
        radky.append(zaznam)
    zprava = pd.DataFrame(radky)
    return out, zprava


def kontrola_zachovani(pred: pd.DataFrame, po: pd.DataFrame) -> pd.DataFrame:
    """Overi, ze se nezmenila agregatni rozdeleni ani vzajemne korelace rysu."""
    rysy = [c for c in EFEKTY if c in pred.columns]
    tci = [c for c in pred.columns if c.startswith("TCI_")]
    r = []
    for c in rysy + tci:
        r.append({"sloupec": c,
                  "prumer_pred": round(pred[c].mean(), 4),
                  "prumer_po": round(po[c].mean(), 4),
                  "sd_pred": round(pred[c].std(), 4),
                  "sd_po": round(po[c].std(), 4)})
    tab = pd.DataFrame(r)
    R1 = np.corrcoef(pred[rysy].to_numpy(float), rowvar=False)
    R2 = np.corrcoef(po[rysy].to_numpy(float), rowvar=False)
    tab.attrs["max_zmena_korelace_rysu"] = round(float(np.abs(R1 - R2).max()), 3)
    return tab


def main() -> int:
    ap = argparse.ArgumentParser(description="Prerozdeleni osobnosti podle demografie")
    ap.add_argument("panel", help="vstupni CSV")
    ap.add_argument("-o", "--out", default="PANEL_OSOBNOST_v2.csv")
    ap.add_argument("--seed", type=int, default=20260812)
    a = ap.parse_args()

    df = pd.read_csv(a.panel, low_memory=False)
    novy, zprava = prerozdel_osobnost(df, seed=a.seed)

    print("\n=== dosazene korelace s demografii (pred -> po, cil) ===")
    for _, r in zprava.iterrows():
        for k in ("vek", "muz", "vzd", "urb"):
            cil = r[f"cil_{k}"]
            if pd.isna(cil) or abs(cil) < 0.03:
                continue
            print(f"  {r['rys']:28} {k:4} {r[f'pred_{k}']:+.3f} -> "
                  f"{r[f'po_{k}']:+.3f}   (cil {cil:+.2f})")

    kontrola = kontrola_zachovani(df, novy)
    print(f"\n=== zachovani agregatu ===")
    print(f"  max zmena prumeru: "
          f"{(kontrola.prumer_po - kontrola.prumer_pred).abs().max():.6f}")
    print(f"  max zmena SD:      "
          f"{(kontrola.sd_po - kontrola.sd_pred).abs().max():.6f}")
    print(f"  max zmena vzajemnych korelaci rysu: "
          f"{kontrola.attrs['max_zmena_korelace_rysu']}")

    novy.to_csv(a.out, index=False)
    print(f"\n[ulozeno] {a.out}  ({novy.shape[0]} x {novy.shape[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
