#!/usr/bin/env python3
"""
npc_validate.py — validace panelu proti reálným marginálům ČSÚ
===============================================================

Tohle je ta kontrola, kterou doporučuju udělat dřív než cokoliv jiného.

Celý stroj stojí na předpokladu, že tabulka 19 020 řádků reprezentuje Česko.
Panel ale vznikl spojením šesti výzkumů s různým designem výběru, takže váhy
opraví jen ty marginály, na které se vážilo. Klasické selhání vypadá takhle:
sedí věk, sedí vzdělání, ale vysokoškoláci nad 60 let v Ústeckém kraji jsou
v panelu třikrát častěji, než mají být — a to nikdo neuvidí, dokud se nepodívá
na PRŮNIKY, ne na jednotlivé proměnné.

Co skript dělá
--------------
  1. Spočítá vážené marginály panelu a porovná je s cílovými (ČSÚ).
  2. Udělá to pro jednorozměrné, dvourozměrné i trojrozměrné průniky.
  3. Vypíše nejhorší buňky seřazené podle odchylky.
  4. Spočítá efektivní velikost vzorku a design effect z rozdělení vah.
  5. Volitelně váhy přepočítá metodou raking (IPF), aby seděly na všechny
     zadané cíle současně.

Použití
-------
    pip install pandas numpy
    python npc_validate.py --panel panel.csv --targets targets.json
    python npc_validate.py --panel panel.csv --targets targets.json --rake --out panel_raked.csv
    python npc_validate.py --demo          # vyrobí syntetický panel a předvede se

Formát targets.json
-------------------
    {
      "vek_kat":  {"18-29": 0.170, "30-44": 0.265, ...},
      "pohlavi":  {"muz": 0.492, "zena": 0.508},
      "vek_kat|pohlavi": {"18-29|muz": 0.087, ...}     # volitelné průniky
    }
Hodnoty jsou podíly, musí dávat součet 1 v rámci každého klíče.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("Chybí závislosti. Spusťte: pip install pandas numpy")

SEP = "|"


# ---------------------------------------------------------------------------
# Diagnostika vah
# ---------------------------------------------------------------------------
def weight_report(w: pd.Series) -> dict:
    """Efektivní velikost vzorku a design effect.

    ESS = (suma vah)^2 / suma(vah^2). Když jsou váhy hodně rozdílné, panel
    o 19 020 řádcích se chová jako podstatně menší — a to je číslo, které
    patří do reportu klientovi místo počtu volání API.
    """
    w = w.astype(float)
    n = len(w)
    ess = (w.sum() ** 2) / (w**2).sum() if (w**2).sum() else 0.0
    return {
        "n_radku": n,
        "ess": round(ess, 1),
        "ess_podil": round(ess / n, 3) if n else 0.0,
        "design_effect": round(n / ess, 3) if ess else float("inf"),
        "vaha_min": round(float(w.min()), 4),
        "vaha_max": round(float(w.max()), 4),
        "vaha_cv": round(float(w.std() / w.mean()), 3) if w.mean() else 0.0,
        "podil_vahy_top1pct": round(
            float(w.nlargest(max(1, n // 100)).sum() / w.sum()), 3
        ),
    }


# ---------------------------------------------------------------------------
# Porovnání marginálů
# ---------------------------------------------------------------------------
def observed(df: pd.DataFrame, cols: list[str], wcol: str) -> pd.Series:
    """Vážený podíl každé kombinace kategorií."""
    key = df[cols[0]].astype(str)
    for c in cols[1:]:
        key = key + SEP + df[c].astype(str)
    s = df.groupby(key)[wcol].sum()
    return s / s.sum()


def compare(df: pd.DataFrame, targets: dict, wcol: str) -> pd.DataFrame:
    rows = []
    for spec, target in targets.items():
        cols = spec.split(SEP)
        missing = [c for c in cols if c not in df.columns]
        if missing:
            print(f"  ! přeskakuji '{spec}': v panelu chybí sloupce {missing}")
            continue
        obs = observed(df, cols, wcol)
        for cat, tgt in target.items():
            o = float(obs.get(cat, 0.0))
            rows.append(
                {
                    "rozmer": spec,
                    "rad": len(cols),
                    "kategorie": cat,
                    "cil": tgt,
                    "panel": round(o, 5),
                    "rozdil_pb": round((o - tgt) * 100, 2),
                    "pomer": round(o / tgt, 3) if tgt else float("inf"),
                }
            )
        # kategorie, které v cíli nejsou, ale v panelu ano
        for cat in obs.index:
            if cat not in target:
                rows.append(
                    {
                        "rozmer": spec,
                        "rad": len(cols),
                        "kategorie": cat,
                        "cil": 0.0,
                        "panel": round(float(obs[cat]), 5),
                        "rozdil_pb": round(float(obs[cat]) * 100, 2),
                        "pomer": float("inf"),
                    }
                )
    return pd.DataFrame(rows)


def derive_interactions(df: pd.DataFrame, targets: dict, dims: list[str], order: int) -> dict:
    """Odvodí cílové průniky z jednorozměrných cílů předpokladem nezávislosti.

    Tohle NENÍ pravda o populaci — vzdělání a věk spolu v realitě korelují.
    Je to referenční bod: velká odchylka od nezávislosti může být buď skutečná
    vlastnost populace, nebo chyba panelu, a skript vás donutí se na to podívat.
    Kde máte skutečné cílové průniky z ČSÚ, vždy použijte je místo tohohle.
    """
    out = {}
    for combo in itertools.combinations(dims, order):
        if not all(d in targets for d in combo):
            continue
        cells = {}
        for vals in itertools.product(*[targets[d].items() for d in combo]):
            key = SEP.join(v[0] for v in vals)
            prob = 1.0
            for v in vals:
                prob *= v[1]
            cells[key] = prob
        out[SEP.join(combo)] = cells
    return out


# ---------------------------------------------------------------------------
# Raking / IPF
# ---------------------------------------------------------------------------
def rake(df: pd.DataFrame, targets: dict, wcol: str, iters: int = 60, tol: float = 1e-6) -> pd.Series:
    """Iterative proportional fitting — přepočítá váhy na všechny cíle současně.

    Bere jen jednorozměrné cíle; průniky se raking nedají vynutit přímo
    (na to by byl potřeba kalibrační odhad s omezeními). Když po rakingu
    průniky pořád nesedí, je to informace: panel v těch buňkách prostě nemá
    koho převážit, a žádná váha to neopraví. To je limit dat, ne nastavení.
    """
    w = df[wcol].astype(float).copy()
    one_way = {k: v for k, v in targets.items() if SEP not in k and k in df.columns}
    if not one_way:
        print("  ! raking: žádné použitelné jednorozměrné cíle")
        return w

    for it in range(iters):
        maxdiff = 0.0
        for col, tgt in one_way.items():
            grp = w.groupby(df[col].astype(str)).sum()
            total = grp.sum()
            for cat, share in tgt.items():
                cur = grp.get(cat, 0.0) / total if total else 0.0
                if cur <= 0:
                    continue
                factor = share / cur
                maxdiff = max(maxdiff, abs(factor - 1.0))
                mask = df[col].astype(str) == cat
                w.loc[mask] *= factor
        if maxdiff < tol:
            print(f"  raking konvergoval po {it + 1} iteracích")
            break
    else:
        print(f"  ! raking nekonvergoval za {iters} iterací (zbytková odchylka {maxdiff:.2e})")

    return w * (len(w) / w.sum())


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def make_demo(n: int = 19020, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    """Syntetický panel se ZÁMĚRNĚ vloženou chybou v průniku.

    Marginály věku i vzdělání sedí, ale vysokoškoláci 60+ v Ústeckém kraji jsou
    přezastoupení. Přesně ten typ vady, který jednorozměrná kontrola nenajde.
    """
    rng = np.random.default_rng(seed)
    vek = ["18-29", "30-44", "45-59", "60+"]
    vek_p = [0.170, 0.265, 0.255, 0.310]
    vzd = ["zakladni", "vyucen", "maturita", "vysokoskolske"]
    vzd_p = [0.120, 0.320, 0.360, 0.200]
    kraj = ["Praha", "Stredocesky", "Ustecky", "Jihomoravsky", "Moravskoslezsky", "Ostatni"]
    kraj_p = [0.125, 0.135, 0.077, 0.114, 0.111, 0.438]

    df = pd.DataFrame(
        {
            "id": np.arange(n),
            "pohlavi": rng.choice(["muz", "zena"], n, p=[0.492, 0.508]),
            "vek_kat": rng.choice(vek, n, p=vek_p),
            "vzdelani": rng.choice(vzd, n, p=vzd_p),
            "kraj": rng.choice(kraj, n, p=kraj_p),
            "vaha": rng.lognormal(0, 0.45, n),
        }
    )
    # vložená vada: ztrojnásobíme váhu problémové buňce
    bad = (df.vek_kat == "60+") & (df.vzdelani == "vysokoskolske") & (df.kraj == "Ustecky")
    df.loc[bad, "vaha"] *= 3.0

    targets = {
        "pohlavi": {"muz": 0.492, "zena": 0.508},
        "vek_kat": dict(zip(vek, vek_p)),
        "vzdelani": dict(zip(vzd, vzd_p)),
        "kraj": dict(zip(kraj, kraj_p)),
    }
    return df, targets


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", help="CSV s panelem")
    ap.add_argument("--targets", help="JSON s cílovými podíly")
    ap.add_argument("--weight", default="vaha", help="název sloupce s váhou (výchozí: vaha)")
    ap.add_argument("--max-order", type=int, default=3, help="do kolikarozměrných průniků jít (výchozí 3)")
    ap.add_argument("--tol-pb", type=float, default=1.0, help="tolerance v procentních bodech (výchozí 1.0)")
    ap.add_argument("--rake", action="store_true", help="přepočítat váhy metodou raking")
    ap.add_argument("--out", help="kam uložit panel s novými vahami")
    ap.add_argument("--demo", action="store_true", help="ukázka na syntetickém panelu")
    a = ap.parse_args()

    if a.demo:
        df, targets = make_demo()
        print("DEMO: syntetický panel se záměrně vloženou vadou v průniku\n")
    else:
        if not a.panel or not a.targets:
            ap.error("zadejte --panel a --targets, nebo --demo")
        df = pd.read_csv(a.panel, dtype=str)
        targets = json.loads(Path(a.targets).read_text(encoding="utf-8"))
        df[a.weight] = pd.to_numeric(df[a.weight], errors="coerce").fillna(0.0)

    wcol = a.weight
    if wcol not in df.columns:
        sys.exit(f"V panelu chybí sloupec s váhou '{wcol}'.")

    # --- 1. váhy ---
    print("=" * 70)
    print("1. DIAGNOSTIKA VAH")
    print("=" * 70)
    wr = weight_report(df[wcol])
    for k, v in wr.items():
        print(f"  {k:22s} {v}")
    if wr["ess_podil"] < 0.5:
        print("\n  ⚠ Efektivní velikost vzorku je pod polovinou počtu řádků.")
        print("    Panel se chová jako výrazně menší. Do reportu klientovi patří ESS, ne počet řádků.")

    if a.rake:
        print("\n  Přepočítávám váhy metodou raking…")
        df[wcol] = rake(df, targets, wcol)
        print("  Po rakingu:")
        for k, v in weight_report(df[wcol]).items():
            print(f"    {k:22s} {v}")

    # --- 2. jednorozměrné ---
    print("\n" + "=" * 70)
    print("2. JEDNOROZMĚRNÉ MARGINÁLY")
    print("=" * 70)
    one = {k: v for k, v in targets.items() if SEP not in k}
    res1 = compare(df, one, wcol)
    if not res1.empty:
        worst = res1.reindex(res1.rozdil_pb.abs().sort_values(ascending=False).index)
        print(worst.head(12).to_string(index=False))
        bad1 = (res1.rozdil_pb.abs() > a.tol_pb).sum()
        print(f"\n  Mimo toleranci ±{a.tol_pb} p.b.: {bad1} z {len(res1)} buněk")

    # --- 3. průniky ---
    explicit = {k: v for k, v in targets.items() if SEP in k}
    dims = list(one.keys())
    all_bad = []
    for order in range(2, a.max_order + 1):
        derived = derive_interactions(df, targets, dims, order)
        derived.update({k: v for k, v in explicit.items() if len(k.split(SEP)) == order})
        if not derived:
            continue
        print("\n" + "=" * 70)
        print(f"3. PRŮNIKY ŘÁDU {order}")
        print("=" * 70)
        res = compare(df, derived, wcol)
        if res.empty:
            continue
        res = res[res.cil > 0.001]  # buňky pod promile nemají statistický smysl
        worst = res.reindex(res.pomer.sub(1).abs().sort_values(ascending=False).index)
        print(worst.head(10).to_string(index=False))
        flag = res[(res.pomer > 1.5) | (res.pomer < 0.67)]
        all_bad.append(flag)
        print(f"\n  Buněk s poměrem mimo 0,67–1,5: {len(flag)} z {len(res)}")

    # --- 4. verdikt ---
    print("\n" + "=" * 70)
    print("4. VERDIKT")
    print("=" * 70)
    bad = pd.concat(all_bad) if all_bad else pd.DataFrame()
    if not bad.empty:
        print(f"  ⚠ {len(bad)} problémových buněk v průnicích. Nejhorší:")
        top = bad.reindex(bad.pomer.sub(1).abs().sort_values(ascending=False).index).head(5)
        for _, r in top.iterrows():
            print(f"    {r.kategorie:45s} panel {r.panel:.4f} vs cíl {r.cil:.4f}  ({r.pomer:.2f}×)")
        print("\n  Pozor na interpretaci: odchylka od nezávislosti nemusí být chyba panelu —")
        print("  vzdělání a věk spolu v populaci opravdu korelují. Kde to jde, nahraďte")
        print("  odvozené cíle skutečnými průniky z ČSÚ. Ale zvětšenou buňku, kterou")
        print("  neumíte vysvětlit reálnou korelací, berte jako vadu.")
    else:
        print("  ✓ Žádný průnik nevybočil z pásma 0,67–1,5.")

    if a.out:
        df.to_csv(a.out, index=False, encoding="utf-8")
        print(f"\n→ {a.out}")


if __name__ == "__main__":
    main()
