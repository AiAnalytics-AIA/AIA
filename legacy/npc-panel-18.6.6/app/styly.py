"""
NPC PANEL — styly.py
Vrstva odpovedniho stylu (response style).

Proc existuje:
Rozptyl v realnem pruzkumu nevznika jen tim, ze lidi mysli ruzne veci.
Vznika taky tim, ze ruzne ODPOVIDAJI. Nekdo souhlasi s cimkoli, co mu tazatel
nabidne. Nekdo se drzi stredu skaly. Nekdo mackacky 1 a 10. Nekdo prizna
"nevim", jiny si radeji vymysli nazor. Nekdo do otevrene otazky napise vetu,
jiny sest slov.

Bez tehle vrstvy LLM odpovida za vsechny stejnym stylem — vyvazene, stredove,
uvazlive — a rozlozeni je hladsi, nez jake kdy vyslo z realneho terenu.

Poctivost: smery vazeb (nizsi vzdelani -> vyssi akviescence a vic "nevim",
vyssi vzdelani -> delsi otevrene odpovedi) jsou prevzate z literatury o
response stylech. Nejsou kalibrovane na cesky teren — je to informovany
prior, ne mereni. Sila vazeb je zamerne slaba (r kolem 0,2-0,3), vetsina
rozptylu je individualni.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

STYLY = ["souhlasny_sklon", "vyhranenost", "ochota_priznat_nevim", "sdilnost",
          "satisficing", "social_desirability_sensitivity"]


def _z(s: pd.Series) -> np.ndarray:
    x = pd.to_numeric(s, errors="coerce")
    sd = x.std(ddof=0)
    return ((x - x.mean()) / (sd if sd else 1)).fillna(0).to_numpy()


def _stabilni_sum(ids: pd.Series, sul: str) -> np.ndarray:
    """Sum odvozeny z respondent_id — stejny respondent ma vzdy stejny styl."""
    out = np.empty(len(ids))
    for i, rid in enumerate(ids.astype(str)):
        h = hashlib.sha256((rid + sul).encode()).hexdigest()
        u = (int(h[:12], 16) + 0.5) / 16 ** 12
        out[i] = np.clip(u, 1e-9, 1 - 1e-9)
    from scipy.stats import norm
    return norm.ppf(out)


VAZBY = {
    # styl: (koef. vzdelani, koef. veku, koef. muz)
    "souhlasny_sklon":      (-0.30,  0.20,  0.00),
    "vyhranenost":          (-0.10,  0.15,  0.05),
    "ochota_priznat_nevim": (-0.25, -0.10, -0.15),
    "sdilnost":             ( 0.30, -0.10,  0.00),
    # Weak informed priors only; the direction/size of a social-desirability
    # correction is never inferred from these alone and must be declared per question.
    "satisficing":           (-0.25,  0.10,  0.00),
    "social_desirability_sensitivity": (-0.05, 0.05, -0.05),
}

VZDELANI_PORADI = {"základní": 1, "střední bez maturity": 2,
                   "střední s maturitou": 3, "VOŠ/VŠ": 4}


def prirad_styly(df: pd.DataFrame) -> pd.DataFrame:
    """Vrati DataFrame se ctyrmi z-skore stylu, index shodny s df."""
    vzd = _z(df["vzdelani"].map(VZDELANI_PORADI)) if "vzdelani" in df else np.zeros(len(df))
    vek = _z(df["vek"]) if "vek" in df else np.zeros(len(df))
    muz = ((df["pohlavi"].astype(str).str.lower().str.startswith("mu")).astype(float)
           .to_numpy() * 2 - 1) if "pohlavi" in df else np.zeros(len(df))
    ids = (df["respondent_id"] if "respondent_id" in df else
           df["panel_row_id"] if "panel_row_id" in df else pd.Series(df.index.astype(str)))

    out = {}
    for styl, (a, b, c) in VAZBY.items():
        signal = a * vzd + b * vek + c * muz
        sum_ = _stabilni_sum(ids, styl)
        # zbytkovy rozptyl tak, aby vysledek mel SD ~1
        vaha_sumu = np.sqrt(max(1 - np.var(signal), 0.05))
        x = signal + vaha_sumu * sum_
        out[styl] = (x - x.mean()) / (x.std() if x.std() else 1)
    return pd.DataFrame(out, index=df.index)


POPISY = {
    "souhlasny_sklon": (
        "má sklon souhlasit s tím, co mu tazatel nabídne, i když o tom moc nepřemýšlí",
        "nenechá se zatlačit do souhlasu, spíš odmítá"),
    "vyhranenost": (
        "volí krajní hodnoty škál, málokdy střed",
        "drží se středu škál, krajní hodnoty nepoužívá"),
    "ochota_priznat_nevim": (
        "když něco neví, klidně to řekne",
        "nerad přiznává, že něco neví — radši si názor dotvoří na místě"),
    "sdilnost": (
        "u otevřených otázek mluví, rozvede to",
        "u otevřených otázek odbude odpověď pár slovy"),
    "satisficing": (
        "u delších dotazníků má sklon odpovídat úsporně a méně promýšlet každou položku",
        "i delší dotazník vyplňuje soustředěně"),
    "social_desirability_sensitivity": (
        "u citlivých témat hlídá, jak jeho odpověď působí",
        "u citlivých témat se méně řídí tím, co zní společensky žádoucí"),
}


def popis_stylu(styly: pd.Series, prah: float = 0.7) -> str:
    """Textovy popis stylu do persony. Uvadi jen vyhranene stranky."""
    casti = []
    for styl in STYLY:
        v = float(styly.get(styl, 0.0))
        if v >= prah:
            casti.append(POPISY[styl][0])
        elif v <= -prah:
            casti.append(POPISY[styl][1])
    return "; ".join(casti)
