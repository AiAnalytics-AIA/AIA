"""A question's topics, as 18.6.6 routed them: which parts of a persona a question calls for.

A port of ``dispozice.odvod_temata`` and its keyword table ``TEMATA_KLICE``
(``legacy/npc-panel-18.6.6/app/dispozice.py:348-438``), and of the block union ``run_dotaznik``
built when it asked several questions in one request (``dotaznik.py:937-948``): each question's
topics in order, the block's union in first-seen order. A question with no topic gets none: the
persona is then its core only. Parity is EXACT against the unit's own function
(``tools/persona_capture.py``; ``tests/fixtures/persona_profile/``), and the table is compared with
the unit's own dictionary there.

AIA's questions declare no topics (``research_design.SpecQuestion``), so every question's topics
are derived from its text and its options, as the unit derived them for a question without
``topics`` (``dotaznik.py:1046-1050``).

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Final

__all__ = ["MAX_TOPICS", "TOPIC_KEYS", "block_topics", "question_topics"]

#: ``odvod_temata(text, max_temat=5)``.
MAX_TOPICS: Final = 5

TOPIC_KEYS: Final[Mapping[str, tuple[str, ...]]] = {
    "cena": (
        "cena",
        "cenu",
        "ceny",
        "drah",
        "levn",
        "sleva",
        "slev",
        "akce",
        "připlat",
        "kolik",
        "korun",
        "zaplat",
        "rozpoč",
        "úspor",
    ),
    "potraviny": (
        "potravin",
        "jídl",
        "jidl",
        "nápoj",
        "napoj",
        "maso",
        "mléč",
        "pečiv",
        "zelenin",
        "ovoce",
        "vaři",
        "restaurac",
        "káv",
    ),
    "retail": ("obchod", "prodejn", "řetěz", "supermarket", "diskont", "regál"),
    "nakup": ("nakup", "nákup", "koupit", "koupil", "pořídit", "zboží", "objedn"),
    "online": ("online", "internet", "e-shop", "eshop", "web", "aplikac", "mobil"),
    "doruceni": ("doruč", "rozvoz", "závoz", "kurýr", "výdejn", "dovezl"),
    "znacka": ("značk", "brand", "logo", "výrobc"),
    "reklama": ("reklam", "kampaň", "spot", "influenc", "sponzor"),
    "media": (
        "televiz",
        "rádi",
        "zprávy",
        "média",
        "media",
        "sociální sít",
        "youtube",
        "facebook",
        "instagram",
        "podcast",
    ),
    "zdravi": ("zdrav", "lék", "nemoc", "doktor", "pacient", "pojišť", "výživ"),
    "sport": ("sport", "cvič", "fitn", "běh", "kolo"),
    "eko": ("ekolog", "udržiteln", "recykl", "tříd", "bio", "uhlík", "klima"),
    "obaly": ("obal", "plast", "zálohov"),
    "energie": ("energi", "elektřin", "plyn", "teplo", "solár", "fotovolt"),
    "doprava": ("doprav", "vlak", "mhd", "jízd", "cest", "palivo"),
    "auto": ("auto", "auta", "autem", "autu", "automobil", "vůz", "vozu", "vozidl", "elektromobil"),
    "bydleni": ("bydl", "byt", "dům", "nájem", "hypoté", "nemovit"),
    "finance": ("banka", "úvěr", "půjč", "spoř", "investic", "pojist", "splátk", "příjm"),
    # Samotne slovo "stat" je v cestine vysoce polysémni ("může se to stát").
    # Politiku proto spousti jen jednoznacnejsi tvary/kontexty.
    "politika": (
        "polit",
        "vlád",
        "volb",
        "stran",
        "prezident",
        "parlament",
        "státní",
        "statni",
        "státu",
        "statu",
        "role státu",
        "role statu",
    ),
    "hodnoty": (
        "hodnot",
        "morálk",
        "etik",
        "tradice",
        "genderov",
        "manželství",
        "rovnost pohlaví",
        "liberáln",
        "konzervativn",
    ),
    "verejne": ("obec", "město", "kraj", "úřad", "veřejn", "samospráv"),
    "regulace": ("zákon", "regulac", "povinn", "zákaz", "daň", "poplat"),
    "sluzby": ("služb", "servis", "zákaznick", "rezervac"),
    "predplatne": ("předplat", "tarif", "měsíčně", "členstv"),
    "premium": ("prémi", "luxus", "kvalit", "nadstandard"),
    "moda": ("oblečen", "móda", "obuv", "kosmetik"),
    "prace": ("prac", "práce", "zaměstn", "kolega", "kancelář", "home office"),
    "volny_cas": (
        "volný čas",
        "koníček",
        "hobby",
        "kniha",
        "čtení",
        "dovolen",
        "cestování",
        "výlet",
        "mazlíček",
        "pes",
        "kočka",
        "kino",
        "kina",
        "film",
        "seriál",
        "serial",
        "divadl",
        "koncert",
        "hudb",
        "stream",
    ),
    "B2B": (
        "dodavatel",
        "firemní zákazník",
        "rozhodovací pravomoc",
        "rozpočet firmy",
        "nákup pro firmu",
    ),
    "loajalita": ("věrnost", "loajal", "věrnostn", "doporučil"),
    "technologie": ("technolog", " ai", "umělá inteligence", "chytr", "digitál", "software"),
    "dovednosti": (
        "gramotnost",
        "čtení textu",
        "vyplnění formuláře",
        "porozumění textu",
        "orientace v textu",
    ),
    "socialni_site": (
        "sociální sít",
        "facebook",
        "instagram",
        "tiktok",
        "x (twitter)",
        "sdílí",
        "sdílet",
        "lajk",
        "komentář na síti",
        "influencer",
        "story",
        "příspěvek",
    ),
    "vztahy": (
        "vztah",
        "partner",
        "manžel",
        "rodin",
        "přátel",
        "kamarád",
        "osamě",
        "blízk",
        "kontakt s lidmi",
    ),
    # v15.2: témata používaná evidence-aware retrieverem nad skutečnými donor bloky.
    "mentalni_zdravi": (
        "psychick",
        "duševn",
        "dusevn",
        "úzkost",
        "uzkost",
        "depres",
        "stres",
        "phq",
        "gad",
        "wellbeing",
        "well-being",
        "vyhořen",
        "vyhoren",
    ),
    "instituce": (
        "instituc",
        "soud",
        "justice",
        "policie",
        "ústavn",
        "ustavn",
        "demokrac",
        "korupc",
    ),
    "duvera": ("důvěr", "duver", "nedůvěr", "neduver"),
    "migrace": ("migrac", "imigr", "uprchl", "cizinc"),
    "bezpecnost": ("bezpeč", "bezpec", "kriminal", "násil", "nasil"),
    "ekonomika": ("ekonom", "inflac", "hospodář", "hospodar", "životní úroveň", "zivotni uroven"),
    "rodina": (
        "rodin",
        "dítě",
        "dite",
        "děti",
        "deti",
        "rodič",
        "rodic",
        "partner",
        "manžel",
        "manzel",
    ),
    "komunita": ("komunit", "soused", "dobrovol", "místní vaz", "mistni vaz"),
    "rozhodovani": ("rozhod", "volba", "vybral", "vybrat", "prefer"),
    "osobnost": ("povah", "osobnost", "charakter", "temperament"),
    "bankovnictvi": ("bankovnict", "bankovní", "bankovni", "platb", "fintech"),
    "vira": ("víra", "vira", "nábožen", "nabozen", "církev", "cirkev", "religio"),
    "nabozenstvi": ("nábožen", "nabozen", "víra", "vira", "duchovn"),
    "gramotnost": (
        "finanční gramotnost",
        "financni gramotnost",
        "rpsn",
        "finanční znalost",
        "rozpočet",
        "rezerva",
    ),
    "kampan": ("kampaň", "kampan", "reklam", "kreativ", "spot", "claim", "slogan", "brand asset"),
    "stavebnictvi": ("stavebn", "stavební materiál", "stavby", "stavari"),
    "reality": ("realit", "makléř", "makler", "nemovitost", "developer nemovit"),
    "zdravotnicky_material": (
        "zdravotnický materiál",
        "zdravotnicke pomucky",
        "medical device",
        "medical material",
    ),
    "procurement": (
        "procurement",
        "nákupčí",
        "nakupci",
        "tendr",
        "výběrové řízení",
        "verejne zakazk",
    ),
    "mensiny": ("menšin", "mensin", "národnost", "narodnost", "rom", "moravan", "slezan"),
}

_BYT: Final = re.compile(r"(?<![\wá-ž])byt(?![\wá-ž])")
_NON_WORD: Final = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> tuple[str, list[str]]:
    """``_normalizuj_text``: lower case, diacritics removed, runs of other characters a space."""
    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = _NON_WORD.sub(" ", t).strip()
    return t, t.split()


def question_topics(text: str, max_topics: int = MAX_TOPICS) -> list[str]:
    """``odvod_temata``: the topics a question's text names, most hits first, ties by name."""
    raw = str(text).lower()
    t, tokens = _normalize(text)
    score: dict[str, int] = {}
    for topic, keys in TOPIC_KEYS.items():
        n = 0
        for key in keys:
            kn, kt = _normalize(key)
            if not kn:
                continue
            if len(kt) > 1:
                n += t.count(kn)
            else:
                stem = kt[0]
                if stem == "byt":
                    n += len(_BYT.findall(raw))
                elif stem in {"auto", "obec"}:
                    n += sum(tok == stem for tok in tokens)
                else:
                    n += sum(
                        tok == stem if len(stem) <= 3 else tok.startswith(stem) for tok in tokens
                    )
        if n:
            score[topic] = n
    return [topic for topic, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:max_topics]]


def block_topics(questions: Sequence[tuple[str, Sequence[str]]]) -> list[str]:
    """One request's topics: each question's (text and options) in order, first seen first."""
    union: list[str] = []
    for text, options in questions:
        for topic in question_topics(text + " " + " ".join(options)):
            if topic not in union:
                union.append(topic)
    return union
