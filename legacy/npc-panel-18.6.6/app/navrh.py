"""
NPC PANEL — navrh.py
Z jednovete klientske otazky udela hotovy dotaznik.

    python navrh.py "Chceme vedet, jestli lidi koupi predplatne na dorucovani
                     potravin za 299 Kc mesicne" -o brief.json
    python run.py brief.json

Nebo z kodu:
    from navrh import navrhni_dotaznik
    brief = navrhni_dotaznik("...zadani...", pocet_otazek=6)

Model dostane instrukce, jak se pise dotaznik, ktery neznehodnoti data:
zadne navodne otazky, zadne dvojotazky, screener napred, citliva otazka nakonec.
"""

from __future__ import annotations
from provider_auth import get_ai_provider
from runtime_config import RUN_DEFAULTS

from provider_auth import create_anthropic_client

from anthropic_compat import create_message

import argparse
import json
import re
import sys
from pathlib import Path

SYSTEM_NAVRH = """Jsi seniorní metodik kvantitativního výzkumu trhu s praxí v české agentuře.
Z klientského zadání sestavíš dotazník pro reprezentativní populační průzkum ČR.

Metodická pravidla, která musíš dodržet:
- Žádné návodné otázky. Ne „Souhlasíte, že je služba výhodná?“, ale „Jak hodnotíte cenu?“
- Žádné dvojotázky. Jeden dotaz = jedna věc.
- Screener první: odfiltruj lidi, pro které téma nedává smysl, a další otázky jim odfiltruj.
- Nabídkové možnosti musí být vyčerpávající a vzájemně se vylučující.
- U ochoty platit nabízej konkrétní cenová pásma, ne „kolik byste dal“.
- Znalost/užívání ptej dřív než postoj, postoj dřív než záměr koupě.
- Jednu otevřenou otázku na konec — proč, vlastními slovy.
- Citlivé otázky (příjem, politika) až nakonec.
- Formuluj mluvenou češtinou, jak by to řekl tazatel do telefonu. Krátce.

Typy otázek:
  "vyber"    — jedna možnost; pole "kategorie"
  "multi"    — více možností; pole "kategorie"
  "skala"    — číselná škála; pole "skala": [1,10] a "popisky_skaly": ["...","..."]
  "otevrena" — vlastními slovy; pole "max_slov"

Větvení: pole "filtr" s podmínkou na dřívější otázku, např. "O1 != 'nikdy'".

- Ke KAŽDÉ otázce přidej pole "topics": 1–4 tematické štítky pouze z tohoto seznamu:
  cena, potraviny, retail, nakup, online, doruceni, znacka, reklama, media, zdravi, sport, eko, obaly, energie, doprava, auto, bydleni, finance, politika, hodnoty, verejne, regulace, sluzby, predplatne, premium, moda, prace, volny_cas, B2B, loajalita, technologie, dovednosti, socialni_site, vztahy.
- Topics popisují obsah otázky, ne očekávanou odpověď. Když si nejsi jistý, použij méně štítků, ne více.

Odpovíš výhradně jedním JSON objektem, bez markdownu a bez komentáře:
{"nazev": "...", "otazky": [ {...}, ... ], "poznamka_metodika": "max 2 věty"}"""

UZIV_NAVRH = """ZADÁNÍ KLIENTA:
{zadani}

Navrhni {pocet} otázek.{cil}

Odpověz JSON."""

POVOLENE = {"id", "text", "typ", "kategorie", "skala", "popisky_skaly",
            "max_slov", "povolit_nevim", "filtr", "topics"}


def _validuj(brief: dict) -> dict:
    """Odstrani neznama pole, doplni chybejici, overi konzistenci."""
    if not isinstance(brief.get("otazky"), list) or not brief["otazky"]:
        raise ValueError("Model nevratil pole 'otazky'.")
    ciste = []
    for i, o in enumerate(brief["otazky"], 1):
        o = {k: v for k, v in o.items() if k in POVOLENE}
        o.setdefault("id", f"O{i}")
        o.setdefault("typ", "vyber")
        if o["typ"] not in ("vyber", "multi", "skala", "otevrena"):
            o["typ"] = "vyber"
        if not o.get("text"):
            continue
        if o["typ"] in ("vyber", "multi"):
            kat = [str(k) for k in (o.get("kategorie") or []) if str(k).strip()]
            if len(kat) < 2:
                continue
            o["kategorie"] = kat
        if o["typ"] == "skala":
            s = o.get("skala") or [1, 10]
            o["skala"] = [int(s[0]), int(s[1])]
            o["popisky_skaly"] = list(o.get("popisky_skaly") or
                                      ["rozhodně ne", "rozhodně ano"])[:2]
        if o["typ"] == "otevrena":
            o["max_slov"] = int(o.get("max_slov") or 25)
        if "topics" in o:
            allowed_topics = {"cena","potraviny","retail","nakup","online","doruceni","znacka","reklama","media","zdravi","sport","eko","obaly","energie","doprava","auto","bydleni","finance","politika","hodnoty","verejne","regulace","sluzby","predplatne","premium","moda","prace","volny_cas","B2B","loajalita","technologie","dovednosti","socialni_site","vztahy"}
            o["topics"] = list(dict.fromkeys(str(x).strip() for x in (o.get("topics") or []) if str(x).strip() in allowed_topics))[:4]
        ciste.append(o)
    if not ciste:
        raise ValueError("Po validaci nezbyla zadna pouzitelna otazka.")
    ids = [o["id"] for o in ciste]
    if len(set(ids)) != len(ids):
        for i, o in enumerate(ciste, 1):
            o["id"] = f"O{i}"
    brief["otazky"] = ciste
    return brief


def navrhni_dotaznik(
    zadani: str,
    pocet_otazek: int = 6,
    *,
    cilova_skupina: str | None = None,
    model: str = RUN_DEFAULTS["model"],
    n: int = 500,
    mode: str = RUN_DEFAULTS["mode"],
    vystup_xlsx: str | None = None,
    provider: str | None = None,
) -> dict:
    """Vrati kompletni brief pripraveny pro run.py."""
    from runtime_config import resolve_model

    model = resolve_model(model)
    tool = {
        "name": "submit_questionnaire",
        "description": "Submit the complete Czech quantitative research questionnaire.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nazev": {"type": "string"},
                "poznamka_metodika": {"type": "string"},
                "otazky": {
                    "type": "array", "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"}, "text": {"type": "string"},
                            "typ": {"type": "string", "enum": ["vyber", "multi", "skala", "otevrena"]},
                            "kategorie": {"type": "array", "items": {"type": "string"}},
                            "skala": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer"}},
                            "popisky_skaly": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
                            "max_slov": {"type": "integer", "minimum": 5, "maximum": 100},
                            "povolit_nevim": {"type": "boolean"},
                            "filtr": {"type": "string"},
                            "topics": {"type": "array", "minItems": 1, "maxItems": 4,
                                       "items": {"type": "string", "enum": ["cena","potraviny","retail","nakup","online","doruceni","znacka","reklama","media","zdravi","sport","eko","obaly","energie","doprava","auto","bydleni","finance","politika","hodnoty","verejne","regulace","sluzby","predplatne","premium","moda","prace","volny_cas","B2B","loajalita","technologie","dovednosti","socialni_site","vztahy"]}}
                        },
                        "required": ["id", "text", "typ", "topics"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["nazev", "otazky"],
            "additionalProperties": False
        }
    }
    from ai_router import call_structured
    rr=call_structured(system=SYSTEM_NAVRH,messages=[{"role":"user","content":UZIV_NAVRH.format(
            zadani=zadani,pocet=pocet_otazek,cil=f" Cílová skupina: {cilova_skupina}." if cilova_skupina else "")}],
            schema=tool["input_schema"],schema_name=tool["name"],anthropic_model=model,max_tokens=3000,prefer=(provider or get_ai_provider()),allow_fallback=False)
    brief = dict(rr["data"]); brief["_ai"]={"provider":rr.get("provider"),"model":rr.get("model"),"fallback_used":rr.get("fallback_used",False)}

    brief = _validuj(brief)
    nazev = brief.get("nazev") or zadani[:60]
    brief.update({
        "nazev": nazev, "n": n, "mode": mode, "seed": 42,
        "model": model, "response_mode": RUN_DEFAULTS["response_mode"], "persona_mode": RUN_DEFAULTS["persona_mode"],
        "filtry": {},
        "vystup": vystup_xlsx or
                  f"vystupy/{re.sub(r'[^a-zA-Z0-9]+', '_', nazev)[:40]}.xlsx",
        "_zadani_klienta": zadani,
    })
    return brief


def main() -> int:
    ap = argparse.ArgumentParser(description="Zadani -> dotaznik")
    ap.add_argument("zadani", help="klientske zadani jednou vetou")
    ap.add_argument("-o", "--out", default="brief.json", help="kam ulozit brief")
    ap.add_argument("-q", "--otazek", type=int, default=6)
    ap.add_argument("-n", type=int, default=500, help="velikost vzorku do briefu")
    ap.add_argument("--cil", help="cilova skupina")
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()

    brief = navrhni_dotaznik(a.zadani, a.otazek, cilova_skupina=a.cil,
                             model=a.model, n=a.n)
    Path(a.out).write_text(json.dumps(brief, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"[navrh] {len(brief['otazky'])} otazek -> {a.out}")
    for o in brief["otazky"]:
        print(f"  [{o['id']}] ({o['typ']}) {o['text']}")
    if brief.get("poznamka_metodika"):
        print(f"\n  metodika: {brief['poznamka_metodika']}")
    print(f"\nDalsi krok:  python run.py {a.out} --dry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
