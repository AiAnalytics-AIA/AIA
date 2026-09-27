"""
NPC PANEL — kalibrace.py
Rakovani / Iterative Proportional Fitting.

Dve pouziti:
  1. prepocet vah panelu na aktualni marginaly CSU (kdyz vyjdou nova data)
  2. dovazeni CILENEHO podvzorku na klientske kvoty
     (napr. "chci jen Prahu, ale se spravnym rozlozenim veku a vzdelani")

    from kalibrace import raking_weights, kontrola_marginalu
    w = raking_weights(df, {"kraj": {...}, "pohlavi": {...}}, )
    print(kontrola_marginalu(df, w, cile))
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def raking_weights(
    df: pd.DataFrame,
    cile: dict[str, dict[str, float]],
    vychozi_vaha: np.ndarray | pd.Series | None = None,
    *,
    max_iter: int = 100,
    tol: float = 1e-6,
    strop: float = 8.0,
    normovat_na_n: bool = True,
) -> np.ndarray:
    """IPF na libovolnem poctu marginalu soucasne.

    cile: {"kraj": {"Praha": 12.3, ...}, "pohlavi": {"muz": 49.0, ...}}
          hodnoty v % nebo v absolutnich poctech — normuje se automaticky.
    strop: orezani extremnich vah (design efekt); 8.0 = max 8x prumer.
    """
    n = len(df)
    w = (np.ones(n) if vychozi_vaha is None
         else np.asarray(vychozi_vaha, dtype=float).copy())

    normy = {}
    for sloupec, t in cile.items():
        if sloupec not in df.columns:
            raise KeyError(f"Sloupec '{sloupec}' neni v datech.")
        chybi = set(t) - set(df[sloupec].dropna().unique())
        if chybi:
            raise ValueError(f"{sloupec}: cile pro chybejici kategorie {chybi}")
        s = sum(t.values())
        normy[sloupec] = {k: v / s for k, v in t.items()}

    for it in range(max_iter):
        zmena = 0.0
        for sloupec, t in normy.items():
            akt = pd.Series(w).groupby(df[sloupec].values).sum()
            celkem = akt.sum()
            for kat, podil in t.items():
                soucasny = akt.get(kat, 0.0)
                if soucasny <= 0:
                    continue
                faktor = (podil * celkem) / soucasny
                w[df[sloupec].values == kat] *= faktor
                zmena = max(zmena, abs(faktor - 1))
        if zmena < tol:
            break

    w = np.clip(w, 0, strop * w.mean())
    if normovat_na_n:
        w = w * n / w.sum()
    return w


def kontrola_marginalu(
    df: pd.DataFrame,
    w: np.ndarray,
    cile: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Vrati tabulku cil vs. dosazeno v p.b. — kontrola, ze kalibrace sedla."""
    radky = []
    for sloupec, t in cile.items():
        s = sum(t.values())
        akt = pd.Series(w).groupby(df[sloupec].values).sum()
        celkem = akt.sum()
        for kat, v in t.items():
            cil = 100 * v / s
            doslo = 100 * akt.get(kat, 0.0) / celkem
            radky.append({"promenna": sloupec, "kategorie": kat,
                          "cil_pct": round(cil, 2), "dosazeno_pct": round(doslo, 2),
                          "odchylka_pb": round(doslo - cil, 3)})
    return pd.DataFrame(radky)


def design_efekt(w: np.ndarray) -> dict[str, float]:
    """Kishovo deff a efektivni velikost vzorku.

    deff > 1.5 = vahy jsou rozjete, intervaly spolehlivosti se realne siri.
    """
    w = np.asarray(w, dtype=float)
    deff = len(w) * (w ** 2).sum() / (w.sum() ** 2)
    return {"deff": round(float(deff), 3),
            "n_efektivni": int(len(w) / deff),
            "vaha_min": round(float(w.min()), 3),
            "vaha_max": round(float(w.max()), 3)}
