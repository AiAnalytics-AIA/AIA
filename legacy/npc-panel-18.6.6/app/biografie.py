"""
NPC PANEL — biografie.py
Strukturovana zivotni trajektorie — spojuje UZ EXISTUJICI atributy panelu do
souvisleho naracniho fragmentu, MISTO volneho LLM-generovaneho backstory.

PROC STRUKTUROVANE, NE VOLNE GENEROVANE
Park et al. 2024 (Stanford, arXiv:2411.10109): agenti z 2hodinovych rozhovoru
reprodukuji odpovedi lidi o 14-15 procentnich bodu presneji nez agenti
postaveni jen na demografii — bohaty individualni kontext hodne pomaha.

ALE Özkan 2026 a CoMPosT (Cheng/Piccardi/Yang 2023) varuji: LLM-generovany
VOLNY backstory u silnych modelu skodi (na survey −11 bodu, kolaps diverzity)
— model si domysli detaily nesouvisejici s daty a persony zestereotypnji,
misto aby zbohatly.

RESENI TETO PRACE: trajektorie se sklada z UZ EXISTUJICICH, REALNYCH atributu
panelu (celil_tvrdosti_10let je merena promenna z "Rozdeleni svobodou", ne muj
odhad) PRAVIDLOVOU logikou, ne volnou generaci LLM. Kazda veta je zpetne
auditovatelna — da se dohledat presne, ktera kombinace dat ji vyrobila. Zadne
LLM volani, zadna fabulace, jen skladani toho, co uz je v panelu, do casove
a pricinne souvislosti.

DVE VRSTVY TRAJEKTORIE:
  1. FINANCNI TRAJEKTORIE — z celil_tvrdosti_10let (10 let zpet) x
     D_financni_polstar (dnes) x trida_spolecenska (strukturalni pozice)
  2. ZIVOTNI FAZE — z veku x F_deti x F_sam (rodinna situace, ne stav v case,
     ale aspon rozliseni fazi zivota)

CO TOHLE NENI: neni to nahrada za skutecny rozhovor nebo panelova data s
casovou znackou (as_of_date, viz FUZE_QC #3). Je to nejlepsi dostupna
aproximace trajektorie z prurezovych dat, ktera panel ma.
"""

from __future__ import annotations

import pandas as pd


def trajektorie_financni(row: pd.Series) -> str | None:
    """Kombinuje tvrdost za poslednich 10 let s dnesnim financnim polstarem.

    celil_tvrdosti_10let je REALNA merena promenna (exekuce/nezamestnanost/
    ztrata bydleni/chudoba za 10 let), ne odhad — proto se pouziva bez ohledu
    na jistotu, na rozdil od OWN_ESTIMATE dispozicnich dimenzi.
    """
    tvrdost = str(row.get("celil_tvrdosti_10let", "")).strip().lower() in ("1", "ano", "true")
    polstar = row.get("D_financni_polstar")
    if pd.isna(polstar) if polstar is not None else True:
        ma_polstar = None
    else:
        ma_polstar = float(polstar) > 0

    if tvrdost and ma_polstar is True:
        return "posledních deset let měl(a) finančně těžké období, teď se situace stabilizovala"
    if tvrdost and ma_polstar is False:
        return "posledních deset let čelil(a) vážným finančním potížím a stále z toho není venku"
    if tvrdost and ma_polstar is None:
        return "za posledních deset let zažil(a) vážné finanční potíže"
    if not tvrdost and ma_polstar is False:
        return "vážnou krizi zatím nezažil(a), ale finančně to má na hraně"
    return None  # stabilni bez vyrazne udalosti — nema smysl to psat, je to defaultni stav


def zivotni_faze(row: pd.Series) -> str | None:
    """Rodinna/vekova faze slozena z realnych faktu domacnosti.

    OPRAVENO 13.8.2026: puvodni verze ignorovala F_rodinny_stav a mohla
    vyrobit "zenaty/vdana" + "zije sam, bez rodinnych zavazku" v jedne
    persone. Ted se zenaty/vdana stav bere jako silnejsi signal nez samotne
    F_sam (ktere u nich uz ma tvrdou penalizaci pri generovani, ale zbytkova
    pravdepodobnost — odloucene souziti — porad existuje).
    """
    vek = row.get("vek")
    deti = row.get("F_deti") == 1
    sam = row.get("F_sam") == 1
    zenaty = row.get("F_rodinny_stav") == "zenaty_vdana"
    if pd.isna(vek):
        return None
    vek = float(vek)

    if deti and vek < 40:
        return "je v období s malými dětmi, život se točí kolem rodiny a času"
    if deti and vek >= 40:
        return "má už odrostlejší děti, domácnost je zaběhnutá"
    if sam and zenaty:
        return "aktuálně žije odděleně od manžela/manželky"
    if sam and vek < 35:
        return "žije sám/sama, zatím bez rodinných závazků"
    if sam and vek >= 65:
        return "žije sám/sama, děti (pokud jsou) už mají vlastní domácnosti"
    if sam:
        return "žije sám/sama"
    return None


def sestav_trajektorii(row: pd.Series, temata: list[str] | None = None) -> str:
    """Tematicky minimalni trajektorie. [] znamena core-only, None legacy all."""
    tem = set(temata or []) if temata is not None else None
    casti = []
    if tem is None or tem & {"finance", "cena", "bydleni", "nakup"}:
        t = trajektorie_financni(row)
        if t:
            casti.append(t)
    if tem is None or tem & {"vztahy", "bydleni", "potraviny", "nakup"}:
        t = zivotni_faze(row)
        if t:
            casti.append(t)
    return "; ".join(casti)
