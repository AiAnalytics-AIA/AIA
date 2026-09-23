"""
NPC PANEL — kontext.py
Sdileny kontext pro survey runtime. V prototype-10.3+ se NIKDY nepridava
implicitne: caller musi explicitne predat kontextove bloky. Research Context OFF
tedy znamena nulovy externi i vestaveny aktualni kontext.

PROC TO EXISTUJE
Persona = KDO je respondent (relativne stabilni, meni se pomalu).
Kontext  = CO SE DEJE VE SVETE prave ted (meni se rychle, stejne pro vsechny).

Kdyz je kontext explicitne zapnuty, muze aktualizovat fakticke prostredi, ktere
model z treninku nemusi znat. Kdyz zapnuty neni, runtime zamerne nic nedohledava
a nepouziva ani katalog nize.

TRI ODLISNE MECHANISMY (nepliet dohromady):
  1. HYPOTETICKE OTAZKY — otazka sama obsahuje podminku ("kdyby byla valka...").
     Reseni: typ otazky, viz Otazka.hypoteticka v dotaznik.py. Zadna nova
     architektura, jen upozorneni v systemovem promptu a v QC.
  2. VSTRIKNUTI KONTEXTU DO PROMPTU — respondent MA VEDET o udalosti, i kdyz
     se ho otazka na ni primo neptá (ekonomicka situace, aktualni cena energii,
     nova regulace). Reseno timto modulem.
  3. POSUN KALIBRACNICH CILU PO SOKU — sok muze zmenit CELKOVOU hladinu
     nejake dimenze v populaci (napr. valka -> skokem nizsi financni_polstar,
     vyssi duvera_instituce nebo naopak). Tohle NENI totez jako bod 2 —
     bod 2 informuje personu o udalosti, bod 3 meni SAMOTNA CISLA v panelu.
     Reseno funkci `aplikuj_posun()` nize — docasny, verzovany posun,
     ne trvala zmena CSV.

RIZIKO, KTERE MUSI KAZDY POUZIVATEL VEDET
Vstriknuti kontextu tlaci model k "modalni" odpovedi — co by rekl generovy
"typicky Cech" o teto udalosti — a presne tohle je opak ucelu panelu.
Bisbee et al. (2024): syntetika systematicky snizuje varianci uz bez kontextu;
sdileny kontext pridany vsem stejne tohle riziko jeste zvysuje, protoze je to
JEDINA cast promptu, kterou maji vsichni respondenti identickou. System prompt
proto vyzaduje explicitni: "posud dopad na TEBE, konkretniho cloveka podle
profilu, ne na prumerneho Cecha" — jinak kontext personu prevalcuje.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class KontextovyBlok:
    id: str
    text: str
    temata: list[str]                 # stejny slovnik jako TEMATA_KLICE v dispozice.py
    datum: str                        # kdy byla informace ověřena, YYYY-MM-DD
    zdroj: str                        # url nebo citace
    platnost_do: str | None = None    # None = bez expirace, jinak YYYY-MM-DD
    jistota: float = 0.7              # jak moc je udalost jista/ustalena (viz priklad EV nize)
    posun: dict[str, float] = field(default_factory=dict)  # volitelny docasny posun D_ sloupcu

    def je_platny(self, k_datu: str | None = None) -> bool:
        if self.platnost_do is None:
            return True
        k_datu = k_datu or _dt.date.today().isoformat()
        return k_datu <= self.platnost_do


# ---------------------------------------------------------------- legacy/manual katalog udalosti
# NENI pouzit automaticky. Caller jej musi explicitne predat.
# Kazdy zaznam MUSI mit datum overeni a zdroj. Bez toho se nepridava.
# Priklad EV nize ukazuje, proc: puvodni "tvrdy zakaz 2035" uz od prosince 2025
# neplati v puvodni podobe — Komise cil zmekcila na 90% snizeni emisi misto
# 100% zakazu, revizni klauzule se posunula. Kdyby tohle bylo v panelu napsane
# jako trvaly fakt bez data, za pul roku by uvadelo respondenty v omyl.

KONTEXT_UDALOSTI: list[KontextovyBlok] = [
    KontextovyBlok(
        id="eu_spalovaci_motory_2035",
        text=(
            "Původní plán EU na tvrdý zákaz prodeje nových aut se spalovacím "
            "motorem od 2035 byl v prosinci 2025 zmírněn: místo 100% zákazu "
            "má jít o 90% snížení emisí u nových vozů, zbytek lze dorovnat "
            "e-palivy nebo nízkouhlíkovou ocelí. Europarlament navíc "
            "zpochybnil, že elektromobily jsou skutečně bezemisní. Definitivní "
            "schválení se očekává v průběhu 2026. Elektromobily zůstávají "
            "výrazně dražší než srovnatelná spalovací auta."
        ),
        temata=["auto", "doprava", "eko", "regulace", "energie"],
        datum="2026-08-13",
        zdroj="EON, Info.cz, Autojournal.cz — souhrn stavu k prosinci 2025 / srpnu 2026",
        platnost_do="2026-12-31",   # ocekavane definitivni schvaleni, pak potreba obnovit
        jistota=0.6,                # aktivne se meni, neni to usazeny fakt
    ),
]


# ---------------------------------------------------------------- vyber a sestaveni

def vyber_kontext(temata: list[str] | None, k_datu: str | None = None,
                  udalosti: list[KontextovyBlok] | None = None) -> list[KontextovyBlok]:
    """Relevantni a nevyprsele udalosti pro dana temata otazky."""
    zdroj = udalosti if udalosti is not None else KONTEXT_UDALOSTI
    out = [u for u in zdroj if u.je_platny(k_datu)]
    if temata:
        out = [u for u in out if set(u.temata) & set(temata)]
    return out


def sestav_kontext_text(bloky: list[KontextovyBlok]) -> str:
    """Text bloku pro system/uzivatelsky prompt. Prazdny retezec, kdyz nic neplati."""
    if not bloky:
        return ""
    radky = []
    for b in bloky:
        znacka = "" if b.jistota >= 0.8 else " (situace se vyvíjí, není to ustálený stav)"
        radky.append(f"- {b.text}{znacka} [ověřeno {b.datum}]")
    return (
        "AKTUÁLNÍ SITUACE VE SVĚTĚ (platí pro všechny respondenty stejně):\n"
        + "\n".join(radky)
        + "\n\nDŮLEŽITÉ: posuď dopad téhle situace na KONKRÉTNÍHO člověka podle jeho "
          "profilu níže — jeho příjem, věk, hodnoty, opatrnost. Neopakuj obecný "
          "\"typický\" názor. Dva různí lidé na stejnou zprávu reagují různě."
    )


# ---------------------------------------------------------------- docasny posun dimenzi

def aplikuj_posun(
    df: pd.DataFrame,
    bloky: list[KontextovyBlok],
    sila: float = 1.0,
) -> pd.DataFrame:
    """Vrati KOPII panelu s docasne posunutymi D_ sloupci podle udalosti.

    Nemeni puvodni CSV. Pouziva se jen pro dobu behu jednoho pruzkumu, kdyz
    sok meni CELKOVOU hladinu dimenze v populaci, ne jen to, o cem respondent
    vi (to resi sestav_kontext_text). Priklad: valka -> posun financni_polstar
    dolu o 0.3 SD u vsech. `sila` skaluje vsechny posuny najednou (0-1),
    pro postupne "doznivani" soku v case.
    """
    out = df.copy()
    for b in bloky:
        for dim, posun in b.posun.items():
            col = f"D_{dim}"
            if col in out.columns:
                out[col] = out[col] + posun * sila
    return out
