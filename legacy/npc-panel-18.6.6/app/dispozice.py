"""
NPC PANEL — dispozice.py
Vlastni vrstva latentnich dispozic + fakta o domacnosti.
24 dimenzi v 5 blocich, stavene pro spotrebitelsky a trzni vyzkum.

PROC VLASTNI VRSTVA
HEXACO a 4Elements meri to, co zajima psychologa. Odpoved v pruzkumu trhu
nepredpovidaji skoro vubec. Tahle vrstva je stavena obracene: nejdriv otazka
"co rozhoduje o tom, jak Cech odpovi na otazku o produktu, cene nebo znacce",
pak dimenze. Vetsina je KALIBROVANA na publikovany cesky marginal, takze se
da overit — na rozdil od simulovaneho HEXACO, ktere overit nejde.

JAK SE TO NEPREKLOPI DO NECITELNEHO PROMPTU
24 dimenzi se do persony nevypisuje. `popis_dispozic(row, temata=[...])`
vybere jen ty, ktere se tykaji tematu dotazniku, a z nich nejvyhranenejsi.
Temata odvozuje `odvod_temata()` ze zneni otazek. Panel je siroky, prompt uzky.

KOTVY
  CSU SILC 2025 — necekany vydaj 16 800 Kc nezvladne 19 % domacnosti;
    bydleni: vlastni dum 38,4 %, byt v OV 33,5 %, najem 21,2 %, u pribuznych 6,9 %;
    auto v domacnosti 73,8 % (Praha 64,9 %, Stredocesky 82,7 %, MSK 68,2 %);
    domacnosti s detmi ~31 %, jednoclenne domacnosti 32 %
  CSU 2025 (VSIT) — zakladni digitalni dovednosti 64 %, online nakup 75 %,
    AI 32 % (16-24 let 78 %, 65+ 4 %, produktivni vek zakladni 16 %, VS 60 %)
  CVVM 3-4/2026 — duvera vlade 25 %, zajem o politiku 56 %
  YouGov Shopper 2025 — privatni znacka se objevila v 61 % nakupu
  Nielsen — pro vic nez polovinu spotrebitelu maji recenze vetsi vliv nez cena
  CSU/CBCB 2025 — 13,1 % domacnosti splaci uver mimo bydleni

    python dispozice.py PANEL.csv -o PANEL_v3.csv
"""

from __future__ import annotations

import argparse
import re
import sys

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.stats import norm

from dimension_catalog import (
    AUTO_KRAJ, DIMENZE, FAKTA_BYDLENI, FAKTORY, TRIDA_SKORE,
    URBANICITA, VZDELANI_PORADI, _WORK_DIM,
)



# ---------------------------------------------------------------- nastroje

def _z(x) -> np.ndarray:
    x = pd.to_numeric(pd.Series(np.asarray(x, dtype=float)), errors="coerce")
    x = x.fillna(x.mean())
    sd = x.std(ddof=0)
    return ((x - x.mean()) / (sd if sd else 1.0)).to_numpy()


def _sigm(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _kalibruj_intercept(lin: np.ndarray, cil: float, w: np.ndarray) -> float:
    lo, hi = -25.0, 25.0
    for _ in range(90):
        stred = (lo + hi) / 2
        if np.average(_sigm(lin + stred), weights=w) < cil:
            lo = stred
        else:
            hi = stred
    return (lo + hi) / 2


def _fit_logit(body: list[tuple[np.ndarray, float]], n_param: int) -> np.ndarray:
    def zbytek(k):
        return [float(_sigm(x @ k) - c) for x, c in body]
    return least_squares(zbytek, np.zeros(n_param)).x


def _latent(p: np.ndarray, faktor: np.ndarray | None, lam: float,
            rng: np.random.Generator) -> np.ndarray:
    """Latentni skore se SD 1, u ktereho plati P(skore > 0) = p pro kazdeho."""
    q = norm.ppf(np.clip(p, 1e-4, 1 - 1e-4))
    sigma = 1.0 / np.sqrt(1.0 + np.var(q))
    if faktor is None:
        e = rng.standard_normal(len(q))
    else:
        e = lam * faktor + np.sqrt(max(1 - lam ** 2, 0.0)) * rng.standard_normal(len(q))
    return sigma * (q + e)


# ---------------------------------------------------------------- jadro

def sestav_dispozice(df: pd.DataFrame, seed: int = 20260812,
                     tichy: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    from holdout_registry import zkontroluj_cely_slovnik
    _holdout = zkontroluj_cely_slovnik(DIMENZE)
    if _holdout["fail"]:
        raise RuntimeError("HOLDOUT LEAKAGE pred kalibraci:\n" + "\n".join(_holdout["fail"]))

    rng = np.random.default_rng(seed)
    log = (lambda *a: None) if tichy else print
    n = len(df)
    w = pd.to_numeric(df.get("vaha_kalibrovana", pd.Series(np.ones(n))),
                      errors="coerce").fillna(1.0).to_numpy()

    vek = pd.to_numeric(df["vek"], errors="coerce").fillna(50).to_numpy()
    vzd_o = df["vzdelani"].map(VZDELANI_PORADI).fillna(2.5).to_numpy(float)
    prijem = pd.to_numeric(df.get("prijem_cisty_mesicni", pd.Series([np.nan] * n)),
                           errors="coerce").to_numpy()
    X = {
        "vek": _z(vek),
        "vzd": _z(vzd_o),
        "urb": _z(df["kraj"].map(URBANICITA).fillna(0.6).to_numpy(float)),
        "muz": (df["pohlavi"].astype(str).str.lower()
                .str.startswith("mu")).to_numpy(float) * 2 - 1,
        "trida": df.get("trida_spolecenska", pd.Series([""] * n))
                   .map(TRIDA_SKORE).fillna(0.0).to_numpy(),
        "tvrdost": pd.to_numeric(df.get("celil_tvrdosti_10let", pd.Series(np.zeros(n))),
                                 errors="coerce").fillna(0).to_numpy(),
        "prijem": np.where(np.isfinite(prijem) & (prijem > 0),
                           _z(np.where(prijem > 0, prijem, np.nan)), 0.0),
    }

    faktory = {k: rng.standard_normal(n) for k in FAKTORY}
    vek_zp = lambda r: (r - vek.mean()) / vek.std()
    vzd_zp = lambda s: (s - vzd_o.mean()) / vzd_o.std()
    FITY = {
        "digital": _fit_logit([
            (np.array([1.0, vek_zp(20), vzd_zp(2.6)]), 0.92),
            (np.array([1.0, vek_zp(80), vzd_zp(2.2)]), 0.11),
            (np.array([1.0, vek_zp(45), vzd_zp(1.0)]), 0.46),
            (np.array([1.0, vek_zp(45), vzd_zp(4.0)]), 0.95)], 3),
        "ai": _fit_logit([
            (np.array([1.0, vek_zp(20), vzd_zp(2.6)]), 0.78),
            (np.array([1.0, vek_zp(72), vzd_zp(2.2)]), 0.04),
            (np.array([1.0, vek_zp(45), vzd_zp(1.0)]), 0.16),
            (np.array([1.0, vek_zp(45), vzd_zp(4.0)]), 0.60)], 3),
    }

    # Generovane D_/M_ sloupce sbirame nejprve bokem a pripojime je jednim
    # concat-em. Predchozi verze vkladala ~150 sloupcu postupne do DataFrame,
    # coz vedlo k silne fragmentaci pandas a zbytecne pomalemu buildu.
    generated: dict[str, np.ndarray] = {}
    latent: dict[str, np.ndarray] = {}
    zprava = []

    # Eligibility pracovnich dimenzi musi byt znama PRED kalibraci markeru.
    # Jinak bychom kalibrovali napr. 21 % home-office mezi vsemi dospelymi
    # a az potom vyhodili nezamestnane, cimz by prevalence mezi zamestnanymi
    # prestala odpovidat kotve.
    _employment_known = False
    _employment_mask = np.zeros(n, dtype=bool)
    for _ec in ("zamestnan", "zamestnany", "pracuje", "ekonomicky_aktivni"):
        if _ec not in df.columns:
            continue
        _raw = df[_ec]
        _num = pd.to_numeric(_raw, errors="coerce")
        if _num.notna().any():
            _employment_known = True
            _employment_mask = _num.eq(1).to_numpy()
        else:
            _sv = _raw.astype(str).str.strip().str.lower()
            _known = ~_sv.isin({"", "nan", "none", "<na>"})
            if _known.any():
                _employment_known = True
                _employment_mask = _sv.isin({"1", "true", "ano", "yes", "zamestnan",
                                               "zaměstnán", "pracuje"}).to_numpy()
        break

    for dim, d in DIMENZE.items():
        lin = np.zeros(n)
        for k, v in d["koef"].items():
            if k == "_fit":
                kf = FITY[v]
                lin += kf[0] + kf[1] * X["vek"] + kf[2] * X["vzd"]
            elif k in X:
                lin += v * X[k]
            elif k in latent:
                lin += v * latent[k]
            else:
                raise KeyError(f"{dim}: neznamy prediktor '{k}' "
                               "(dimenze musi byt definovana driv)")
        cil = d["kotva"] if d["kotva"] is not None else 0.50
        f = d.get("faktor")
        # Podpora zaporneho zatizeni: faktor="-nazev" znamena, ze dimenze
        # koreluje se sdilenym faktorem OPACNE (napr. osamelost vs siroka_sit).
        znamenko = -1.0 if f and f.startswith("-") else 1.0
        f_cisty = f[1:] if f and f.startswith("-") else f

        _eligible = (_employment_mask if dim in _WORK_DIM
                     else np.ones(n, dtype=bool))
        if dim in _WORK_DIM and (not _employment_known or not _eligible.any()):
            latent[dim] = np.full(n, np.nan)
            d_arr = np.full(n, np.nan)
            m_arr = np.full(n, np.nan)
            dosazeno = np.nan
        elif dim in _WORK_DIM:
            # Kotva je definovana MEZI ZAMESTNANYMI. Kalibrujeme tedy intercept
            # pouze na eligible podmnozine a mimo ni nechavame atribut missing.
            inter = _kalibruj_intercept(lin[_eligible], cil, w[_eligible])
            p_el = _sigm(lin[_eligible] + inter)
            factor_el = (faktory[f_cisty][_eligible] if f_cisty else None)
            lat_el = _latent(p_el, factor_el,
                             znamenko * FAKTORY.get(f_cisty, 0.0), rng)
            latent[dim] = np.full(n, np.nan)
            latent[dim][_eligible] = lat_el
            d_arr = np.full(n, np.nan)
            d_arr[_eligible] = np.round(lat_el, 4)
            m_arr = np.full(n, np.nan)
            m_arr[_eligible] = (lat_el > 0).astype(int)
            dosazeno = round(float(np.average(m_arr[_eligible], weights=w[_eligible])), 3)
        else:
            p = _sigm(lin + _kalibruj_intercept(lin, cil, w))
            latent[dim] = _latent(p, faktory[f_cisty] if f_cisty else None,
                                  znamenko * FAKTORY.get(f_cisty, 0.0), rng)
            d_arr = np.round(latent[dim], 4)
            m_arr = (latent[dim] > 0).astype(int)
            dosazeno = round(float(np.average(m_arr, weights=w)), 3)

        generated[f"D_{dim}"] = d_arr
        generated[f"M_{dim}"] = m_arr
        zprava.append({"blok": d["blok"], "dimenze": dim, "marker": d["marker"],
                       "cil": d["kotva"], "zdroj": d["zdroj"],
                       "dosazeno": dosazeno})

    out = pd.concat([df.copy(), pd.DataFrame(generated, index=df.index)], axis=1)

    # ---------------- fakta o domacnosti
    p_auto = df["kraj"].map(AUTO_KRAJ).fillna(0.738).to_numpy(float)
    p_auto = np.clip(p_auto + 0.09 * X["trida"] - 0.07 * np.maximum(X["vek"], 0), 0.05, 0.97)
    out["F_auto"] = (rng.random(n) < p_auto).astype(int)

    kat = list(FAKTA_BYDLENI)
    vahy = np.log(np.array([FAKTA_BYDLENI[k] for k in kat]))[None, :] + np.stack([
        0.30 * (-X["urb"]) + 0.15 * X["vek"],
        0.25 * X["urb"] + 0.05 * X["vek"],
        0.20 * X["urb"] - 0.25 * X["vek"] - 0.25 * X["trida"],
        -0.35 * X["vek"] - 0.20 * X["trida"],
    ], axis=1)
    P = np.exp(vahy - vahy.max(1, keepdims=True))
    P = P / P.sum(1, keepdims=True)
    out["F_bydleni"] = [kat[i] for i in (P.cumsum(1) > rng.random((n, 1))).argmax(1)]

    lin = -2.2 * ((vek - 38) / 14) ** 2
    out["F_deti"] = (rng.random(n) < _sigm(lin + _kalibruj_intercept(lin, 0.31, w))).astype(int)

    # F_rodinny_stav — SKUTECNA vekove podminena data (ne odhadnuty logit jako
    # u ostatnich fakt). Zdroj: CSU SLDB2021, plna krizova tabulka rodinny
    # stav x vek (5leta pasma) x pohlavi za celou CR, ziskana jako mikrodata
    # 13.8.2026 (Census_2021_anchors/sldb2021_stav_vek5_pohlavi.csv).
    # Interpolace primo z realnych bodu, zadny vymysleny koeficient.
    # POZOR na poradi: musi bezet PRED F_sam, jinak vznikaji nekonzistence
    # typu "zenaty/vdana" + "zije sam, bez rodinnych zavazku" (objeveno pri
    # QC 13.8.2026 — F_sam byl puvodne nezavisly na rodinnem stavu).
    _RS_VEK = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]
    _RS_KAT = ["svobodny", "zenaty_vdana", "rozvedeny", "vdovec_vdova"]
    _RS_P = {  # % podle veku, z realne tabulky
        "svobodny":     [96.5, 79.8, 59.0, 44.3, 31.2, 19.5, 11.7, 8.2, 6.2, 4.6, 3.3, 2.5, 2.1, 1.8, 1.8, 2.7],
        "zenaty_vdana": [3.3, 18.9, 37.0, 47.3, 53.3, 56.6, 58.5, 60.9, 63.4, 63.2, 59.7, 51.7, 40.0, 26.4, 14.6, 6.7],
        "rozvedeny":    [0.2, 1.2, 3.8, 8.2, 15.0, 22.8, 27.6, 26.9, 22.9, 19.2, 15.2, 11.8, 8.5, 7.0, 6.3, 5.8],
        "vdovec_vdova": [0.0, 0.0, 0.1, 0.2, 0.5, 1.1, 2.1, 3.9, 7.5, 13.1, 21.8, 33.9, 49.5, 64.9, 77.4, 84.7],
    }
    vek_clip = np.clip(vek, 20, 95)
    P_rs = np.stack([np.interp(vek_clip, _RS_VEK, _RS_P[k]) for k in _RS_KAT], axis=1)
    P_rs = P_rs / P_rs.sum(1, keepdims=True)
    rs = np.array([_RS_KAT[i] for i in (P_rs.cumsum(1) > rng.random((n, 1))).argmax(1)])
    out["F_rodinny_stav"] = rs

    # F_sam ("zije sam") ted zavisi na rodinnem stavu: zenaty/vdana prakticky
    # nikdy "sam" (jen zbytkova pravdepodobnost — odloucene souziti), ostatni
    # kategorie podle puvodni logiky (vek, urbanicita), deti vzdy vyluci "sam".
    lin = 0.45 * np.abs(X["vek"]) + 0.30 * X["urb"]
    zenaty = (rs == "zenaty_vdana")
    lin = np.where(zenaty, lin - 4.0, lin)  # tvrda penalizace, ne uplne vyloucit
    sam = (rng.random(n) < _sigm(lin + _kalibruj_intercept(lin, 0.32 / 0.69, w))).astype(int)
    out["F_sam"] = np.where(out["F_deti"].to_numpy() == 1, 0, sam)   # s detmi nezije sam

    # F_strana — hypoteticka stranicka preference "kdyby byly volby ted".
    # Zdroj: QoG EQI 2024 CR mikrodata (N=5060), Q22 dekodovano primo z value
    # labels oficialniho .dta (13.8.2026) — NE odhad, NE prevzeti okrskovych
    # vysledku PS2025 (ktere by bylo ekologickym klamem, viz PERSONA_MAP.md
    # v acquired_data). Marginal i smer/sila koeficientu vek a vzdelani jsou
    # skutecne vazene korelace z EQI, ne muj odhad. NEVÍ/ODMÍTL a JINÁ jsou
    # ponechany jako vlastni kategorie, ne rozpocitany mezi zname strany.
    _STRANA_ZAKLAD = {  # % z Q22, vazeno PSweight_o
        "ANO": 26.8, "NEVÍ/ODMÍTL": 23.9, "ODS": 9.9, "SPD": 7.5, "PIRÁTI": 7.3,
        "STAN": 4.4, "SOCDEM/ČSSD": 3.4, "ZELENÍ": 3.1, "TOP 09": 2.8, "KSČM": 2.8,
        "JINÁ": 2.5, "KDU-ČSL": 2.1, "PŘÍSAHA": 1.5, "PRO": 1.5, "TRIKOLORA": 0.6,
    }
    # (koef_vek, koef_vzdelani) — realne vazene korelace z EQI pro strany s
    # dostatecnym N; zbytek necha na zakladnim podilu (koef 0,0).
    _STRANA_KOEF = {
        "ANO": (0.10, -0.40), "ODS": (-0.04, 0.33), "SPD": (-0.07, -0.26),
        "PIRÁTI": (-0.20, 0.14), "STAN": (-0.09, 0.25), "SOCDEM/ČSSD": (0.07, 0.08),
        "KSČM": (0.05, -0.17), "TOP 09": (-0.06, 0.23), "ZELENÍ": (-0.04, -0.02),
        "KDU-ČSL": (-0.02, 0.13),
    }
    kat_s = list(_STRANA_ZAKLAD)
    zaklad_s = np.array([_STRANA_ZAKLAD[k] for k in kat_s])
    posun_s = np.zeros((n, len(kat_s)))
    for j, k in enumerate(kat_s):
        kv, kz = _STRANA_KOEF.get(k, (0.0, 0.0))
        posun_s[:, j] = kv * X["vek"] + kz * X["vzd"]
    vahy_s = np.log(zaklad_s)[None, :] + posun_s
    Ps = np.exp(vahy_s - vahy_s.max(1, keepdims=True))
    Ps = Ps / Ps.sum(1, keepdims=True)
    out["F_strana"] = [kat_s[i] for i in (Ps.cumsum(1) > rng.random((n, 1))).argmax(1)]

    # ---------------- denominator guard: pracovně podmíněné dimenze
    # LFS/Home-office tabulky v dodaných datech jsou kalibrace MEZI ZAMESTNANYMI,
    # nikoli mezi vsemi dospelymi. Pokud backbone nema respondent-level
    # employment status, je metodicky lepsi nechat tyto dimenze missing nez
    # generovat vedouci/home-office/AI praci duchodcum a nezamestnanym.
    _emp_cols = [c for c in ("zamestnan", "zamestnany", "pracuje", "ekonomicky_aktivni")
                 if c in out.columns]
    if not _emp_cols:
        for _wd in _WORK_DIM:
            out[f"D_{_wd}"] = np.nan
            out[f"M_{_wd}"] = np.nan
        for _zr in zprava:
            if _zr["dimenze"] in _WORK_DIM:
                _zr["dosazeno"] = np.nan
                _zr["poznamka"] = "NEAKTIVNI: chybi explicitni employment status"
    else:
        _ec = _emp_cols[0]
        _num = pd.to_numeric(out[_ec], errors="coerce")
        if _num.notna().any():
            _emp = _num.eq(1)
        else:
            _sv = out[_ec].astype(str).str.strip().str.lower()
            _emp = _sv.isin({"1", "true", "ano", "yes", "zamestnan", "zaměstnán", "pracuje"})
        for _wd in _WORK_DIM:
            out.loc[~_emp, f"D_{_wd}"] = np.nan
            out.loc[~_emp, f"M_{_wd}"] = np.nan

    for z in zprava:
        if z["cil"] is not None:
            z["odchylka_pb"] = round(100 * (z["dosazeno"] - z["cil"]), 1)
    log(f"[dispozice] {len(DIMENZE)} dimenzi v "
        f"{len({d['blok'] for d in DIMENZE.values()})} blocich + 5 fakt domacnosti/stranicke preference")
    return out, pd.DataFrame(zprava)


# ---------------------------------------------------------------- do persony

TEMATA_KLICE = {
    "cena": ["cena", "cenu", "ceny", "drah", "levn", "sleva", "slev", "akce", "připlat",
             "kolik", "korun", "zaplat", "rozpoč", "úspor"],
    "potraviny": ["potravin", "jídl", "jidl", "nápoj", "napoj", "maso", "mléč", "pečiv",
                  "zelenin", "ovoce", "vaři", "restaurac", "káv"],
    "retail": ["obchod", "prodejn", "řetěz", "supermarket", "diskont", "regál"],
    "nakup": ["nakup", "nákup", "koupit", "koupil", "pořídit", "zboží", "objedn"],
    "online": ["online", "internet", "e-shop", "eshop", "web", "aplikac", "mobil"],
    "doruceni": ["doruč", "rozvoz", "závoz", "kurýr", "výdejn", "dovezl"],
    "znacka": ["značk", "brand", "logo", "výrobc"],
    "reklama": ["reklam", "kampaň", "spot", "influenc", "sponzor"],
    "media": ["televiz", "rádi", "zprávy", "média", "media", "sociální sít", "youtube",
              "facebook", "instagram", "podcast"],
    "zdravi": ["zdrav", "lék", "nemoc", "doktor", "pacient", "pojišť", "výživ"],
    "sport": ["sport", "cvič", "fitn", "běh", "kolo"],
    "eko": ["ekolog", "udržiteln", "recykl", "tříd", "bio", "uhlík", "klima"],
    "obaly": ["obal", "plast", "zálohov"],
    "energie": ["energi", "elektřin", "plyn", "teplo", "solár", "fotovolt"],
    "doprava": ["doprav", "vlak", "mhd", "jízd", "cest", "palivo"],
    "auto": ["auto", "auta", "autem", "autu", "automobil", "vůz", "vozu", "vozidl", "elektromobil"],
    "bydleni": ["bydl", "byt", "dům", "nájem", "hypoté", "nemovit"],
    "finance": ["banka", "úvěr", "půjč", "spoř", "investic", "pojist", "splátk", "příjm"],
    # Samotne slovo "stat" je v cestine vysoce polysémni ("může se to stát").
    # Politiku proto spousti jen jednoznacnejsi tvary/kontexty.
    "politika": ["polit", "vlád", "volb", "stran", "prezident", "parlament",
                 "státní", "statni", "státu", "statu", "role státu", "role statu"],
    "hodnoty": ["hodnot", "morálk", "etik", "tradice", "genderov", "manželství",
               "rovnost pohlaví", "liberáln", "konzervativn"],
    "verejne": ["obec", "město", "kraj", "úřad", "veřejn", "samospráv"],
    "regulace": ["zákon", "regulac", "povinn", "zákaz", "daň", "poplat"],
    "sluzby": ["služb", "servis", "zákaznick", "rezervac"],
    "predplatne": ["předplat", "tarif", "měsíčně", "členstv"],
    "premium": ["prémi", "luxus", "kvalit", "nadstandard"],
    "moda": ["oblečen", "móda", "obuv", "kosmetik"],
    "prace": ["prac", "práce", "zaměstn", "kolega", "kancelář", "home office"],
    "volny_cas": ["volný čas", "koníček", "hobby", "kniha", "čtení", "dovolen",
                 "cestování", "výlet", "mazlíček", "pes", "kočka", "kino", "kina",
                 "film", "seriál", "serial", "divadl", "koncert", "hudb", "stream"],
    "B2B": ["dodavatel", "firemní zákazník", "rozhodovací pravomoc", "rozpočet firmy",
           "nákup pro firmu"],
    "loajalita": ["věrnost", "loajal", "věrnostn", "doporučil"],
    "technologie": ["technolog", " ai", "umělá inteligence", "chytr", "digitál", "software"],
    "dovednosti": ["gramotnost", "čtení textu", "vyplnění formuláře", "porozumění textu",
                  "orientace v textu"],
    "socialni_site": ["sociální sít", "facebook", "instagram", "tiktok", "x (twitter)",
                      "sdílí", "sdílet", "lajk", "komentář na síti", "influencer",
                      "story", "příspěvek"],
    "vztahy": ["vztah", "partner", "manžel", "rodin", "přátel", "kamarád", "osamě",
              "blízk", "kontakt s lidmi"],
    # v15.2: témata používaná evidence-aware retrieverem nad skutečnými donor bloky.
    "mentalni_zdravi": ["psychick", "duševn", "dusevn", "úzkost", "uzkost", "depres", "stres",
                         "phq", "gad", "wellbeing", "well-being", "vyhořen", "vyhoren"],
    "instituce": ["instituc", "soud", "justice", "policie", "ústavn", "ustavn", "demokrac", "korupc"],
    "duvera": ["důvěr", "duver", "nedůvěr", "neduver"],
    "migrace": ["migrac", "imigr", "uprchl", "cizinc"],
    "bezpecnost": ["bezpeč", "bezpec", "kriminal", "násil", "nasil"],
    "ekonomika": ["ekonom", "inflac", "hospodář", "hospodar", "životní úroveň", "zivotni uroven"],
    "rodina": ["rodin", "dítě", "dite", "děti", "deti", "rodič", "rodic", "partner", "manžel", "manzel"],
    "komunita": ["komunit", "soused", "dobrovol", "místní vaz", "mistni vaz"],
    "rozhodovani": ["rozhod", "volba", "vybral", "vybrat", "prefer"],
    "osobnost": ["povah", "osobnost", "charakter", "temperament"],
    "bankovnictvi": ["bankovnict", "bankovní", "bankovni", "platb", "fintech"],
    "vira": ["víra", "vira", "nábožen", "nabozen", "církev", "cirkev", "religio"],
    "nabozenstvi": ["nábožen", "nabozen", "víra", "vira", "duchovn"],
    "gramotnost": ["finanční gramotnost", "financni gramotnost", "rpsn", "finanční znalost", "rozpočet", "rezerva"],
    "kampan": ["kampaň", "kampan", "reklam", "kreativ", "spot", "claim", "slogan", "brand asset"],
    "stavebnictvi": ["stavebn", "stavební materiál", "stavby", "stavari"],
    "reality": ["realit", "makléř", "makler", "nemovitost", "developer nemovit"],
    "zdravotnicky_material": ["zdravotnický materiál", "zdravotnicke pomucky", "medical device", "medical material"],
    "procurement": ["procurement", "nákupčí", "nakupci", "tendr", "výběrové řízení", "verejne zakazk"],
    "mensiny": ["menšin", "mensin", "národnost", "narodnost", "rom", "moravan", "slezan"],
}


def _normalizuj_text(text: str) -> tuple[str, list[str]]:
    """Lowercase + odstraneni diakritiky pro konzistentni ceske stem matching."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t, t.split()


def odvod_temata(text: str, max_temat: int = 5) -> list[str]:
    """Konzervativni tematicky router pro jednu konkretni otazku.

    Nepouziva libovolny substring pres celou vetu. Klicova slova se
    normalizuji a jednoslovne klice se porovnavaji jako prefix tokenu;
    vice-slove fraze jako fraze. Nezname tema vraci [] = core-only persona.
    """
    raw = str(text).lower()
    t, tokeny = _normalizuj_text(text)
    skore: dict[str, int] = {}
    for tema, klice in TEMATA_KLICE.items():
        n = 0
        for k in klice:
            kn, kt = _normalizuj_text(k)
            if not kn:
                continue
            if len(kt) > 1:
                n += t.count(kn)
            else:
                stem = kt[0]
                # Ambiguous Czech words must never use prefix matching. In
                # particular auto!=automaticky, obec!=obecne and byt (flat)
                # must not be confused with the verb být after diacritic removal.
                if stem == "byt":
                    n += len(re.findall(r"(?<![\wá-ž])byt(?![\wá-ž])", raw))
                elif stem in {"auto", "obec"}:
                    n += sum(tok == stem for tok in tokeny)
                else:
                    n += sum(tok == stem if len(stem) <= 3 else tok.startswith(stem)
                             for tok in tokeny)
        if n:
            skore[tema] = n
    return [tema for tema, _ in sorted(skore.items(), key=lambda x: (-x[1], x[0]))[:max_temat]]


KOLIZE = [("financni_polstar", "cenova_citlivost"),
          ("cenova_citlivost", "ochota_priplatit"),
          ("vernost_znacce", "otevrenost_zmene"),
          ("media_online", "socialni_site"),
          ("majoritarianismus", "prioritizuje_vetsinovou_vladu"),
          ("silny_vudce", "prioritizuje_nezavislost_soudu")]


def _freshness(rok: int, aktualni_rok: int = 2026) -> float:
    """Rozpad jistoty se starnutim zdroje. FUZE_QC #11, START pozn. 28:
    'nejisty nebo stary extrem se nema propsat do persony jako fakt'."""
    return max(0.3, 1.0 - 0.06 * max(0, aktualni_rok - rok))


def skore_dimenze(row: pd.Series, dim: str) -> float | None:
    """relevance (mimo tuhle fci, viz temata) x magnitude x jistota x freshness.

    Bez kalibrovane kotvy (OWN_ESTIMATE, jistota 0.35) potrebuje dimenze skoro
    trojnasobne vyhraneny signal, aby se dostala do persony, nez kalibrovana
    (SPECIALIST, jistota 0.85) — presne to, co FUZE_QC #11 pozaduje.
    """
    v = row.get(f"D_{dim}")
    if v is None or pd.isna(v):
        return None
    p = DIMENZE[dim].get("prov", {"jistota": 0.5, "rok": 2024})
    return abs(float(v)) * p["jistota"] * _freshness(p["rok"])


def popis_dispozic(row: pd.Series, temata: list[str] | None = None,
                   prah: float = 0.5, max_polozek: int = 6,
                   allow_own_estimates: bool = False) -> str:
    """Text do persony — jen dimenze relevantni k tematu, vazene skore napred.

    Filtr uz neni ciste |D| > prah, ale relevance x magnitude x jistota x
    freshness (FUZE_QC #11) — nejisty/odhadnuty extrem se hur probije do
    persony nez stejne velky, ale kalibrovany signal.
    """
    sila, skore = {}, {}
    for dim, d in DIMENZE.items():
        v = row.get(f"D_{dim}")
        if v is None or pd.isna(v):
            continue
        if not je_dimenze_eligible(row, dim):
            continue
        if (not allow_own_estimates and
                DIMENZE[dim].get("prov", {}).get("zdroj_role") == "OWN_ESTIMATE"):
            continue
        s = skore_dimenze(row, dim)
        # DULEZITE: threshold je na confidence-weighted skore. V1 nasobila
        # jistotu i na prave strane, cimz se vykrátila a OWN_ESTIMATE nebyl
        # nijak penalizovan. Ted 0.35-confidence signal potrebuje ~3x vyssi
        # magnitude nez 0.92 BRIDGE signal.
        if s is None or s < prah:
            continue
        if temata is not None and not set(d["temata"]) & set(temata):
            continue
        sila[dim] = float(v)
        skore[dim] = s
    # Bezpecny fallback: kdyz pro tema nic nemame, nevymyslime globalni
    # profil. Prazdny vysledek je lepsi nez nerelevantni politicke/financni
    # stereotypy.
    if not sila:
        return ""
    # u vzacneho markeru nese informaci jen kladna strana a naopak — "nesplaci
    # zadny uver" plati o 87 % lidi a v persone jen zabira misto
    for dim in list(sila):
        k = DIMENZE[dim]["kotva"]
        if k is not None and ((k < 0.25 and sila[dim] < 0) or (k > 0.75 and sila[dim] > 0)):
            sila.pop(dim)
            skore.pop(dim, None)
    for a, b in KOLIZE:
        if a in sila and b in sila and (sila[a] > 0) == (sila[b] > 0):
            slabsi = a if skore.get(a, 0) < skore.get(b, 0) else b
            sila.pop(slabsi, None)
            skore.pop(slabsi, None)
    poradi = sorted(skore.items(), key=lambda x: -x[1])[:max_polozek]
    return "; ".join(DIMENZE[d]["popis"][0 if sila[d] > 0 else 1] for d, _ in poradi)


def _pracovni_status(row: pd.Series) -> bool | None:
    """Vrati True/False jen z explicitniho respondent-level atributu.

    V12 ekonomickou aktivitu nema. V takovem pripade vraci None a pracovnim
    dispozicim se nesmi dovolovat vystupovat jako fakta "mezi zamestnanymi".
    """
    for col in ("zamestnan", "zamestnany", "pracuje", "ekonomicky_aktivni"):
        if col not in row.index or pd.isna(row.get(col)):
            continue
        raw = row.get(col)
        try:
            num = float(raw)
            if np.isfinite(num):
                if num == 1:
                    return True
                if num == 0:
                    return False
        except (TypeError, ValueError):
            pass
        v = str(raw).strip().lower()
        if v in {"1", "1.0", "true", "ano", "yes", "zamestnan", "zaměstnán", "pracuje"}:
            return True
        if v in {"0", "0.0", "false", "ne", "no", "nezamestnan", "nezaměstnán", "duchodce", "důchodce"}:
            return False
    return None


def je_dimenze_eligible(row: pd.Series, dim: str) -> bool:
    """Hard denominator guard pro atributy podminene pracovnim statusem."""
    if dim in _WORK_DIM:
        return _pracovni_status(row) is True
    return True


def popis_faktu(row: pd.Series, temata: list[str] | None = None) -> str:
    """Fakta do persony pouze kdyz jsou relevantni pro konkretni otazku."""
    tem = set(temata or []) if temata is not None else None
    c = []
    _RS_TEXT = {"svobodny": "svobodný(á)", "zenaty_vdana": "ženatý/vdaná",
               "rozvedeny": "rozvedený(á)", "vdovec_vdova": "ovdovělý(á)"}

    def relevant(*xs: str) -> bool:
        return tem is None or bool(tem & set(xs))

    if relevant("vztahy", "bydleni") and pd.notna(row.get("F_rodinny_stav")):
        c.append(_RS_TEXT.get(row["F_rodinny_stav"], str(row["F_rodinny_stav"])))
    if relevant("bydleni", "finance", "energie") and pd.notna(row.get("F_bydleni")):
        c.append(f"bydlí {row['F_bydleni']}")
    if relevant("auto", "doprava") and "F_auto" in row.index:
        c.append("auto v domácnosti" if row["F_auto"] == 1 else "bez auta")
    if relevant("vztahy", "bydleni", "potraviny", "nakup") and row.get("F_deti") == 1:
        c.append("děti v domácnosti")
    if relevant("vztahy", "bydleni") and row.get("F_sam") == 1:
        c.append("žije sám")
    zaklad = ", ".join(c)

    # F_strana je odvozena z EQI Q22 (hypoteticka preference v roce 2024).
    # Nesmime ji v roce 2026 prepsat na tvrzeni "volil by ted". Presna strana
    # zustava internim kalibracnim/validacnim atributem; do live persony se
    # bez explicitni temporalni aktualizace NEVYPISUJE. Politicke otazky maji
    # stale k dispozici latentni osy (zajem, trust, L/R, EU, populismus...).
    return zaklad


def main() -> int:
    ap = argparse.ArgumentParser(description="Vrstva latentnich dispozic")
    ap.add_argument("panel")
    ap.add_argument("-o", "--out", default="PANEL_DISPOZICE_v3.csv")
    ap.add_argument("--seed", type=int, default=20260812)
    a = ap.parse_args()

    df = pd.read_csv(a.panel, low_memory=False)
    novy, zprava = sestav_dispozice(df, seed=a.seed)

    print(f"\n{'blok':11}{'dimenze':24}{'marker':44}{'cíl':>6}{'dosaž.':>8}  zdroj")
    for _, r in zprava.iterrows():
        cil = f"{r.cil:.2f}" if r.cil is not None else "   —"
        print(f"{r.blok:11}{r.dimenze:24}{r.marker[:44]:44}{cil:>6}{r.dosazeno:8.3f}  {r.zdroj}")

    novy.to_csv(a.out, index=False)
    print(f"\n[ulozeno] {a.out}  ({novy.shape[0]} x {novy.shape[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
