#!/usr/bin/env python3
"""
npc_lint.py — kontrola autenticity českých odpovědí syntetických respondentů
=============================================================================

Detekuje jazykové příznaky toho, že model překládá z angličtiny místo aby
uvažoval česky, a porušení registru, která českému čtenáři okamžitě prozradí
strojový původ.

Pravidla vycházejí z ověřených zdrojů, ne z dojmu:
  • NESČ (Nový encyklopedický slovník češtiny, ÚJČ AV ČR) — obecná čeština,
    středomoravská nářeční skupina, částice
  • Slovo a slovesnost (ÚJČ) — empirický výzkum tykání a vykání

Proč to existuje
----------------
Ověřili jsme, že NEEXISTUJE žádný český benchmark, který by testoval sociální
a kulturní uvažování místo syntaxe. Nic v českém ekosystému nechytí model, který
mluví bezchybnou češtinou a uvažuje jako Američan. Tenhle skript ten problém
neřeší celý — je to levné síto na jazykové příznaky, ne na kulturní znalost.
Tu si budete muset otestovat vlastní evaluační sadou.

Poctivé omezení
---------------
Jsou to regulární výrazy, ne morfologický analyzátor. Chytí hrubé a časté
příznaky, ne jemné. Falešně pozitivní nálezy budou. Berte to jako screening,
který zvedne podezřelé odpovědi k ručnímu pohledu, ne jako soudce.

Použití
-------
    python npc_lint.py --demo
    python npc_lint.py --odpovedi vysledek.odpovedi.csv --sloupec duvod
    python npc_lint.py --odpovedi vysledek.odpovedi.csv --kraj-sloupec kraj
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Chybí pandas. Spusťte: pip install pandas")

# --------------------------------------------------------------------------
# PRAVIDLA
# --------------------------------------------------------------------------

# 1. Tykání směrem k tazateli. Ověřeno ze Slova a slovesnosti: v institucionálním
#    kontaktu s neznámým člověkem je vykání jednoznačné. Respondent, který tazateli
#    tyká, je okamžitý prozrazovač. Hledáme oslovení ve 2. os. j. č.
TYKANI = re.compile(
    r"\b(myslíš|víš|chceš|můžeš|máš|jsi|seš|budeš|řekni|podívej|hele\s+ty|"
    r"tvůj|tvoje|tvoji|tvá|tvého|tobě|tebe|tebou)\b", re.I)

# 2. Nadužití podmětových zájmen. Čeština je pro-drop; angličtina ne.
#    Generování z angličtiny je systematicky přesypává. Jeden z nejspolehlivějších
#    příznaků překladu.
ZAJMENA = re.compile(r"\b(já|ty|on|ona|ono|my|vy|oni|ony)\b", re.I)

# 3. Knižní tvary, které podle NESČ v obecné češtině NEJSOU. V přímé řeči
#    respondenta působí jako tisková zpráva.
KNIZNI = [
    (re.compile(r"\b\w+[ea]jíc[íe]?\b"), "přechodník"),
    (re.compile(r"\bjes[tm]\w*\s+\w+[áé]n[ao]?\b"), "opisné pasivum"),
    (re.compile(r"\bbyl[aoiy]?\s+by\s+\w+l[aoiy]?\b"), "minulý kondicionál"),
    (re.compile(r"\b(nicméně|tudíž|jelikož|dozajista|kterýžto|nechť|zdali)\b", re.I), "knižní spojka"),
]

# 4. Částice a hedging. NESČ: částice jsou v mluvené řeči výrazně častější než
#    v psané. Nula působí přeloženě, moc působí jako karikatura.
CASTICE = re.compile(
    r"\b(no|prostě|vlastně|tak|přece|asi|snad|spíš|spíše|teda|hele|"
    r"jako|nějak|docela|celkem|řekl\s+bych|řekla\s+bych)\b", re.I)

# 5. Anglicismy a kalky — obraty, které v češtině existují jen jako překlad.
KALKY = [
    (re.compile(r"\bna\s+konci\s+dne\b", re.I), "at the end of the day"),
    (re.compile(r"\bdělá\s+to\s+smysl\b", re.I), "makes sense (správně: dává smysl)"),
    (re.compile(r"\bjsem\s+dobrý\b", re.I), "I'm good"),
    (re.compile(r"\bmít\s+dopad\s+na\b", re.I), "have an impact on"),
    (re.compile(r"\bv\s+neposlední\s+řadě\b", re.I), "last but not least (nadužívané)"),
    (re.compile(r"\bosobně\s+si\s+myslím\b", re.I), "I personally think"),
    (re.compile(r"\bna\s+denní\s+bázi\b", re.I), "on a daily basis"),
    (re.compile(r"\badresovat\s+(problém|otázku)\b", re.I), "address the issue"),
    (re.compile(r"\bsdílet\s+(názor|pocit)\b", re.I), "share an opinion"),
]

# 6. Meta-komentář a převyprávění otázky — typický LLM tvar odpovědi.
META = [
    (re.compile(r"^(jako\s+)?(respondent|osoba|člověk|muž|žena)\b", re.I), "mluví o sobě ve třetí osobě"),
    (re.compile(r"\b(vzhledem\s+k\s+(mé|mému|mojí)|na\s+základě\s+(mého|mé))\b", re.I), "zdůvodňuje se profilem"),
    (re.compile(r"\b(ptáte\s+se|otázka\s+zní|k\s+vaší\s+otázce)\b", re.I), "převypráví otázku"),
    (re.compile(r"\b(celkově\s+vzato|abych\s+to\s+shrnul|závěrem)\b", re.I), "shrnuje"),
]

# 7. Regionální marker s nejvyšší hodnotou. NESČ: v Čechách se pomocné sloveso
#    v 1. os. minulého času vypouští (já přijel), na střední Moravě se drží
#    (já sem to viděl). Je to kategorické, opačné mezi regiony a pro model
#    překládající z angličtiny neviditelné.
PRICESTI = re.compile(r"\b\w{3,}l[aoiy]?\b", re.I)      # minulé příčestí: přijel, zkoušela…
POMOCNE = re.compile(r"\b(sem|jsem|sme|jsme)\b", re.I)   # pomocné sloveso 1. os.
JA = re.compile(r"\b(já|my)\b", re.I)


def _aux_pravidlo(t: str) -> str | None:
    """Vrátí 'drzi', 'vypusten' nebo None.

    Hledá věty, kde je 1. osoba (já/my) a minulé příčestí. Pokud v takové větě
    chybí pomocné sloveso, jde o české vypuštění (já přijel); pokud tam je,
    jde o moravské podržení (já sem přijel). Ostatní věty ignorujeme —
    pravidlo se týká jen 1. osoby minulého času.
    """
    for veta in re.split(r"[.!?;]", t):
        if JA.search(veta) and PRICESTI.search(veta):
            return "drzi" if POMOCNE.search(veta) else "vypusten"
    return None

MORAVA = {"jihomoravsky", "olomoucky", "zlinsky", "moravskoslezsky", "vysocina",
          "jihomoravský", "olomoucký", "zlínský", "moravskoslezský", "vysočina"}


def norm(s: str) -> str:
    t = str(s or "").lower()
    for a, b in zip("áčďéěíňóřšťúůýž", "acdeeinorstuuyz"):
        t = t.replace(a, b)
    return t


def zkontroluj(text: str, kraj: str | None = None) -> dict:
    t = str(text or "").strip()
    if not t:
        return {"prazdne": True, "nalezy": [], "skore": 0}

    slova = re.findall(r"\w+", t)
    n = len(slova)
    nalezy = []

    if TYKANI.search(t):
        nalezy.append(("KRITICKÉ", "tykání tazateli", TYKANI.search(t).group(0)))

    # Práh je záměrně shovívavý: v krátké odpovědi je jedno zájmeno normální,
    # příznakem je až jejich hromadění v delším textu.
    zaj = len(ZAJMENA.findall(t))
    if n >= 12 and zaj >= 2 and zaj / n > 0.10:
        nalezy.append(("VYSOKÉ", f"nadužití podmětových zájmen ({zaj} z {n} slov)", ""))

    for rx, nazev in KNIZNI:
        m = rx.search(t)
        if m:
            nalezy.append(("STŘEDNÍ", f"knižní tvar: {nazev}", m.group(0)))

    cast = len(CASTICE.findall(t))
    if cast == 0 and n >= 8:
        nalezy.append(("STŘEDNÍ", "žádná částice ani hedging — působí přeloženě", ""))
    elif cast >= 4:
        nalezy.append(("NÍZKÉ", f"příliš mnoho částic ({cast}) — působí jako karikatura", ""))

    for rx, nazev in KALKY:
        m = rx.search(t)
        if m:
            nalezy.append(("VYSOKÉ", f"anglicismus: {nazev}", m.group(0)))

    for rx, nazev in META:
        m = rx.search(t)
        if m:
            nalezy.append(("VYSOKÉ", f"meta-komentář: {nazev}", m.group(0)))

    if n > 45:
        nalezy.append(("STŘEDNÍ", f"příliš dlouhá odpověď ({n} slov) — v dotazníku lidé takhle nemluví", ""))

    if kraj:
        je_morava = norm(kraj) in {norm(x) for x in MORAVA}
        aux = _aux_pravidlo(t)
        if je_morava and aux == "vypusten":
            nalezy.append(("STŘEDNÍ", "moravská persona vypouští pomocné sloveso (to je české pravidlo)", ""))
        if not je_morava and aux == "drzi":
            nalezy.append(("NÍZKÉ", "česká persona drží pomocné sloveso (to je moravské pravidlo)", ""))

    vaha = {"KRITICKÉ": 10, "VYSOKÉ": 4, "STŘEDNÍ": 2, "NÍZKÉ": 1}
    return {"prazdne": False, "nalezy": nalezy,
            "skore": sum(vaha[s] for s, _, _ in nalezy), "slov": n, "castic": cast}


DEMO = [
    ("Cena je ok, ale nejsem si jistej, jestli to budu potřebovat.", "Praha"),
    ("Na základě mého profilu a vzhledem k mé finanční situaci si osobně myslím, že na konci dne to nedělá smysl.", "Praha"),
    ("Myslíš, že bych to fakt využil? Já nevím.", "Praha"),
    ("Já sem to zkoušel a nebylo to špatný.", "Jihomoravsky"),
    ("Já to zkoušel a nebylo to špatný.", "Jihomoravsky"),
    ("Jelikož jsem osobou preferující úsporná řešení, je mnou tato nabídka vnímána jako nevýhodná.", "Ostatni"),
    ("No asi bych to spíš nebral, prostě to teď neřeším.", "Ustecky"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--odpovedi", help="CSV z npc_study.py")
    ap.add_argument("--sloupec", default="duvod", help="sloupec s textem odpovědi")
    ap.add_argument("--kraj-sloupec", default="kraj")
    ap.add_argument("--prah", type=int, default=4, help="od jakého skóre nahlásit")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        data = [{"duvod": t, "kraj": k} for t, k in DEMO]
        df = pd.DataFrame(data)
        col, kcol = "duvod", "kraj"
    else:
        if not a.odpovedi:
            ap.error("zadejte --odpovedi, nebo --demo")
        df = pd.read_csv(a.odpovedi)
        col, kcol = a.sloupec, a.kraj_sloupec
        if col not in df.columns:
            sys.exit(f"V souboru chybí sloupec '{col}'. Dostupné: {list(df.columns)[:15]}")

    vysledky = [zkontroluj(r[col], r.get(kcol) if kcol in df.columns else None)
                for _, r in df.iterrows()]

    typy = Counter()
    for v in vysledky:
        for zav, popis, _ in v["nalezy"]:
            typy[(zav, popis.split(":")[0].split("(")[0].strip())] += 1

    podezrele = [(i, v) for i, v in enumerate(vysledky) if v["skore"] >= a.prah]

    print(f"Zkontrolováno {len(df)} odpovědí · podezřelých {len(podezrele)} "
          f"({len(podezrele)/max(1,len(df)):.0%}) při prahu {a.prah}\n")

    if typy:
        print("NEJČASTĚJŠÍ NÁLEZY")
        print("=" * 62)
        for (zav, popis), n in typy.most_common(12):
            print(f"  {zav:9s} {popis:44s} {n:5d}×")

    if podezrele:
        print("\nNEJPODEZŘELEJŠÍ ODPOVĚDI")
        print("=" * 62)
        for i, v in sorted(podezrele, key=lambda x: -x[1]["skore"])[:10]:
            print(f"\n  [skóre {v['skore']}] „{str(df.iloc[i][col])[:95]}“")
            for zav, popis, ukazka in v["nalezy"]:
                u = f"  → „{ukazka}“" if ukazka else ""
                print(f"      {zav:9s} {popis}{u}")

    prum_cast = sum(v.get("castic", 0) for v in vysledky) / max(1, len(vysledky))
    bez_castic = sum(1 for v in vysledky if v.get("castic", 0) == 0)
    print("\n" + "=" * 62)
    print(f"  Průměrný počet částic na odpověď: {prum_cast:.2f}")
    print(f"  Odpovědí zcela bez částic: {bez_castic} ({bez_castic/max(1,len(vysledky)):.0%})")
    if prum_cast < 0.5:
        print("\n  ⚠ Málo hedgingu. Čeština v mluveném projevu částice používá výrazně")
        print("    víc než psaná — nula na odpověď je nejspolehlivější příznak toho,")
        print("    že model generuje přes angličtinu. Zkuste to zmínit v systémovém pokynu.")

    print("\n  Poznámka: jsou to regulární výrazy, ne morfologický analyzátor.")
    print("  Falešně pozitivní nálezy budou. Používejte jako síto, ne jako soudce.")


if __name__ == "__main__":
    main()
