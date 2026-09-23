"""
NPC PANEL — mrp.py
Dva mechanismy inspirovane konkurenci, ktere ADRESUJI (ne jen hlasi) problem
malych podskupin — vec, kterou uz qc.py/dotaznik.py detekuji (n<30 varovani),
ale nic s tim nedelaji.

1. PARTIAL POOLING (zjednodusene MRP)
   Inspirace: Gelman & Little (1997) — multilevel regrese + poststratifikace.
   Buttice & Highton (2013): MRP funguje nejlip se silnymi geografickymi
   kovariatami; kdyz jsou mezi-skupinove rozdily male, MRP nemusi pomoct.

   Plna hierarchicka Bayesovska regrese by vyzadovala PyMC/Stan, coz je
   tezka zavislost pro tenhle projekt. Misto toho: empiricky Bayesovsky
   shrinkage odhad (James-Stein styl) — mala bunka se "stahuje" smerem
   k nadrazenemu prumeru umerne tomu, jak mala je. Je to jadro MRP principu
   (partial pooling) bez plne hierarchicke regrese.

2. FAIRGEN-STYL BOOSTING MALYCH PODSKUPIN
   Inspirace: Fairgen (cistě statisticka metoda, BEZ LLM) — synteticky
   boosting nejmensich podskupin. Validace na 10 % dat, zbytek jako ground
   truth. Klicove zjisteni: jakmile podvzorek dosahne ~150-200 respondentu,
   marginalni zisky mizi. Google/ESOMAR pilot: prumerne zlepseni 23,8 %
   konfidencnich intervalu, boostuje jen segmenty tvorici 1-15 % vzorku
   s base n>=300 v CELEM panelu (ne v malem vyberu).

   Implementace: bootstrap s jitterem — pro malou podskupinu (napr. kraj x
   trida s n<30 VE VYBERU) se vygeneruji dalsi syntetictí clenove
   resamplovanim existujicich radku ZE STEJNE PODSKUPINY V CELEM PANELU
   (ne z vyberu) + maly Gaussovsky jitter na kontinualni D_ latentni skore,
   aby noví clenove nebyli doslovne duplicitni. Kategorialni F_ fakta a
   demografie zustavaji presne, jak byly (bootstrap ze skutecnych radku,
   ne vymyslene).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- partial pooling

def partial_pooling_odhad(
    detail: pd.DataFrame,
    seg: str,
    sloupec_hodnoty: str,
    n_prah: int = 30,
    sila_shrinkage: float = 1.0,
) -> pd.DataFrame:
    """James-Stein styl shrinkage pro male bunky segmentu.

    Misto proste prumeru male bunky (nestabilni pri n<30) vraci vazeny
    prumer bunky a celkoveho prumeru, kde vaha bunky roste s jejim n.
    To je jadro MRP principu (partial pooling) bez plne hierarchicke
    regrese — "vypujcuje silu" napric bunkami, presne jak doporucuje
    Buttice & Highton pro male geograficke/demograficke skupiny.

    vaha_bunky = n_bunky / (n_bunky + k), k je "stahovaci konstanta"
    odvozena z n_prahu — mensi bunky se stahuji vic k celku.
    """
    ok = detail[detail[sloupec_hodnoty].notna()]
    celkovy_prumer = ok[sloupec_hodnoty].mean()
    k = n_prah * sila_shrinkage

    radky = []
    for hod, grp in ok.groupby(seg):
        n = len(grp)
        prumer_bunky = grp[sloupec_hodnoty].mean()
        vaha = n / (n + k)
        odhad = vaha * prumer_bunky + (1 - vaha) * celkovy_prumer
        radky.append({
            seg: hod, "n": n,
            "prumer_bunky_surovy": round(prumer_bunky, 4),
            "prumer_partial_pooling": round(odhad, 4),
            "vaha_bunky": round(vaha, 3),
            "spolehlive": n >= n_prah,
        })
    return pd.DataFrame(radky).sort_values("n", ascending=False)


# ---------------------------------------------------------------- Fairgen boosting

def najdi_male_podskupiny(
    vyber: pd.DataFrame,
    segmenty: list[str],
    n_prah: int = 30,
    podil_max: float = 0.15,
    podil_min: float = 0.01,
) -> list[dict]:
    """Najde kombinace segmentu s malym n VE VYBERU, ktere jsou zaroven
    dost velke v CELEM panelu (1-15 % populace — Fairgen prah), aby melo
    smysl je boostovat. Segment tvoricí <1 % populace se nema boostovat —
    tam uz jde o skutecnou vzacnost, ne o nestesti vyberu.
    """
    n_celkem = len(vyber)
    male = []
    for seg in segmenty:
        if seg not in vyber.columns:
            continue
        counts = vyber[seg].value_counts()
        podily = counts / n_celkem
        for hod in counts.index:
            n = counts[hod]
            podil = podily[hod]
            if n < n_prah and podil_min <= podil <= podil_max:
                male.append({"segment": seg, "hodnota": hod, "n_ve_vyberu": int(n),
                            "podil_ve_vyberu": round(float(podil), 4)})
    return male


def boostuj_male_skupiny(
    vyber: pd.DataFrame,
    panel_df: pd.DataFrame,
    segmenty: list[str],
    n_prah: int = 30,
    cilove_n: int = 40,
    jitter_sd: float = 0.15,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fairgen-styl syntetický boost: pro kazdou malou podskupinu (n<n_prah
    ve vyberu, ale 1-15 % v celem panelu) dotahne dalsi cleny bootstrapem
    z CELEHO panelu (ne jen z vyberu) se stejnou kombinaci segmentu, plus
    maly jitter na D_ sloupcich, aby nesli o doslovne duplicity.

    Vraci (rozsireny_vyber, zprava_o_boostu). Rozsireny vyber ma navic
    sloupec "_boostovano" (1 = synteticky pridany clen, 0 = puvodni).

    DULEZITE: boostovani meni pocet radku, ne vahy. Kdyz se agreguje,
    boostovane radky se MUSI zapocitat s nizsi vahou, jinak boosting
    umele zvedne podil male skupiny v celkovem souctu — to je uloha
    parametru "vaha_boostu" v navratove zprave, aplikuje se v report.py
    az pri agregaci, ne tady.
    """
    rng = np.random.default_rng(seed)
    male = najdi_male_podskupiny(vyber, segmenty, n_prah)
    if not male:
        vyber = vyber.copy()
        vyber["_boostovano"] = 0
        return vyber, pd.DataFrame(columns=["segment", "hodnota", "n_pred",
                                            "n_po", "pridano", "vaha_boostu"])

    d_cols = [c for c in vyber.columns if c.startswith("D_")]
    nove_radky = []
    zprava = []
    for m in male:
        seg, hod, n_pred = m["segment"], m["hodnota"], m["n_ve_vyberu"]
        chybi = max(0, cilove_n - n_pred)
        if chybi == 0:
            continue
        zdroj = panel_df[panel_df[seg] == hod]
        if len(zdroj) == 0:
            continue
        vzorek = zdroj.sample(n=chybi, replace=True, random_state=rng.integers(0, 2**31))
        for c in d_cols:
            if c in vzorek.columns:
                vzorek[c] = vzorek[c] + rng.normal(0, jitter_sd, len(vzorek))
        nove_radky.append(vzorek)
        # Fairgen: zisky mizi kolem n=150-200 CELKEM v podskupine (ne jen
        # ve vyberu) — vaha boostu klesa s tim, jak blizko je puvodni n
        # k tomuhle prahu, aby boost nepredstiral jistotu, kterou nema.
        vaha_boostu = max(0.3, 1.0 - n_pred / 150)
        zprava.append({"segment": seg, "hodnota": str(hod), "n_pred": n_pred,
                       "n_po": n_pred + chybi, "pridano": chybi,
                       "vaha_boostu": round(vaha_boostu, 2)})

    vyber = vyber.copy()
    vyber["_boostovano"] = 0
    if nove_radky:
        vsechny_nove = pd.concat(nove_radky, ignore_index=True).copy()
        vsechny_nove["_boostovano"] = 1
        vyber = pd.concat([vyber, vsechny_nove], ignore_index=True)

    return vyber, pd.DataFrame(zprava)


def aplikuj_vahu_boostu(detail: pd.DataFrame, zprava_boostu: pd.DataFrame) -> pd.Series:
    """Vrati sloupec vah pro agregaci — boostovane radky maji vahu podle
    zpravy_boostu (0,3-1,0), puvodni radky vahu 1,0. Pouzit misto proste
    pocitani radku, jinak boost umele nafoukne podil male skupiny."""
    w = pd.Series(1.0, index=detail.index)
    if "_boostovano" not in detail.columns or zprava_boostu.empty:
        return w
    for _, r in zprava_boostu.iterrows():
        mask = (detail.get(r["segment"]) == r["hodnota"]) & (detail["_boostovano"] == 1)
        w.loc[mask] = r["vaha_boostu"]
    return w
