"""Canonical NPC disposition/dimension catalogue.

This module contains definitions, anchors, provenance roles and eligibility metadata.
Runtime synthesis/scoring lives in ``dispozice.py``. Keeping the catalogue separate
makes data-review diffs auditable without mixing them with algorithms.
"""
from __future__ import annotations

import re

VZDELANI_PORADI = {"základní": 1, "střední bez maturity": 2,
                   "střední s maturitou": 3, "VOŠ/VŠ": 4}

URBANICITA = {
    "Praha": 1.00, "Ústecký": 0.79, "Moravskoslezský": 0.76, "Karlovarský": 0.72,
    "Liberecký": 0.65, "Jihomoravský": 0.64, "Plzeňský": 0.62, "Olomoucký": 0.57,
    "Královehradecký": 0.55, "Královéhradecký": 0.55, "Zlínský": 0.54,
    "Jihočeský": 0.54, "Pardubický": 0.52, "Středočeský": 0.50, "Vysočina": 0.47,
}

AUTO_KRAJ = {
    "Praha": 0.649, "Moravskoslezský": 0.682, "Ústecký": 0.71, "Karlovarský": 0.72,
    "Jihomoravský": 0.735, "Olomoucký": 0.745, "Liberecký": 0.75, "Zlínský": 0.755,
    "Jihočeský": 0.77, "Plzeňský": 0.775, "Královehradecký": 0.78,
    "Královéhradecký": 0.78, "Vysočina": 0.79, "Pardubický": 0.816,
    "Středočeský": 0.827,
}

TRIDA_SKORE = {
    "Zajištěná střední": 1.0, "Nastupující kosmopolitní": 0.9,
    "Třída místních vazeb": 0.2, "Tradiční pracující": 0.0,
    "Ohrožená": -0.7, "Strádající": -1.3,
}

FAKTA_BYDLENI = {"ve vlastním domě": 0.384, "v bytě v osobním vlastnictví": 0.335,
                 "v nájmu": 0.212, "u příbuzných": 0.069}

# sdilene rezidualni faktory — dimenze se stejnym faktorem spolu koreluji
# i nad ramec toho, co vysvetli demografie
FAKTORY = {"hmotna_situace": 0.45, "digitalni": 0.45, "vedoma_spotreba": 0.50,
           "konzervatismus": 0.40, "duvera": 0.40,
           # Pridano 13.8.2026 pri systemove kontrole — tri konstrukty, ktere
           # literatura silne spojuje, ale byly generovany nezavisle
           # (zmereno na panelu: korelace ~0 misto ocekavane):
           "socialni_zapojeni": 0.55,   # osamelost (-) vs siroka_sit (+)
           "dusevni_zdravi": 0.65,      # PHQ-9/GAD-7 komorbidita je jeden
                                        # z nejrobustnejsich nalezu klinicke
                                        # psychologie, typicky r=0,6-0,7
           "rizikove_chovani_zdravi": 0.35}  # kuractvi/alkohol/nadvaha se
                                              # epidemiologicky shlukuji

# --- Provenance / governance (FUZE_QC pravidlo 1, 3, 11, 12; audit "mapa zdroju" 08/2026) ---
# role:    ANCHOR (populacni marginal) | SPECIALIST (kalibrovany na konkretni vyzkum)
#          | OWN_ESTIMATE (nase koeficienty, marginal odhadnut, ne mereny)
# jistota: 0-1, subjektivni confidence do vahy persony (VIZ nize skore_dimenze)
# rok:     rok zdroje kotvy, pro freshness rozpad
# citlive: L07 senzitivni kategorie (politika/zdravi/navykove latky/puvod) —
#          nikdy se neprezentuje jako fakt o realnem cloveku, jen jako syntetická tendence

def _prov(role: str, jistota: float, rok: int, citlive: bool = False,
          unit: str = "person", eligible_population: str = "CR_18+") -> dict:
    return {"zdroj_role": role, "jistota": jistota, "rok": rok, "citlive": citlive,
            "unit": unit, "eligible_population": eligible_population}


DIMENZE: dict[str, dict] = {
    # ---------------- A. EKONOMIKA DOMACNOSTI
    "financni_polstar": dict(
        blok="ekonomika", kotva=0.81, zdroj="ČSÚ SILC 2025", faktor="hmotna_situace",
        marker="zaplatí neočekávaný výdaj 16 800 Kč",
        koef=dict(trida=0.55, vzd=0.35, prijem=0.30, tvrdost=-0.55, urb=0.10, vek=-0.10),
        popis=("na nečekaný výdaj kolem 17 tisíc by peníze našel",
               "na nečekaný výdaj kolem 17 tisíc by neměl, vyjde tak tak"),
        temata=["finance", "cena", "nakup", "bydleni", "sluzby"]),
    "cenova_citlivost": dict(
        blok="ekonomika", kotva=None, zdroj="odvozeno z polštáře", faktor="hmotna_situace",
        marker="rozhoduje se hlavně podle ceny",
        koef=dict(financni_polstar=-1.30, tvrdost=0.35, vzd=-0.15),
        popis=("u nákupů hlídá cenu, srovnává, čeká na akce",
               "cena není to hlavní, radši si připlatí za kvalitu nebo pohodlí"),
        temata=["cena", "nakup", "potraviny", "retail", "sluzby", "predplatne"]),
    "zadluzenost": dict(
        blok="ekonomika", kotva=0.131, zdroj="ČSÚ/CBCB 2025", faktor="hmotna_situace",
        marker="splácí úvěr mimo bydlení",
        koef=dict(financni_polstar=-0.55, vek=-0.35, tvrdost=0.45, trida=-0.20),
        popis=("splácí půjčku mimo bydlení, splátky ho tíží",
               "žádné splátky spotřebitelských úvěrů neřeší"),
        temata=["finance", "cena", "predplatne"]),
    "ochota_priplatit": dict(
        blok="ekonomika", kotva=None, zdroj="bez kotvy", faktor="hmotna_situace",
        marker="připlatí si za vyšší kvalitu",
        koef=dict(financni_polstar=0.75, vzd=0.30, urb=0.20, vek=-0.10),
        popis=("za vyšší kvalitu si připlatí, když ji vidí",
               "za nadstandard platit nebude, stačí mu základ"),
        temata=["cena", "znacka", "potraviny", "sluzby", "premium"]),
    "planovitost_nakupu": dict(
        blok="ekonomika", kotva=None, zdroj="bez kotvy", faktor=None,
        marker="nakupuje podle seznamu a plánu",
        koef=dict(vek=0.30, financni_polstar=-0.15, vzd=0.10),
        popis=("nakupuje podle seznamu, dopředu promyšleně",
               "nakupuje impulzivně, co ho zaujme v regálu"),
        temata=["nakup", "retail", "potraviny", "reklama"]),

    # ---------------- B. KANALY A NAKUPNI CHOVANI
    "digitalni_zivot": dict(
        blok="kanaly", kotva=0.64, zdroj="ČSÚ 2025", faktor="digitalni",
        marker="aspoň základní digitální dovednosti",
        koef={"_fit": "digital", "urb": 0.15},
        popis=("digitálně zdatný, věci běžně řeší přes mobil",
               "s technikou si moc nerozumí, online skoro nic nevyřídí"),
        temata=["online", "technologie", "sluzby", "media", "nakup"]),
    "ecommerce": dict(
        blok="kanaly", kotva=0.75, zdroj="ČSÚ 2025", faktor="digitalni",
        marker="nakupuje na internetu",
        koef=dict(digitalni_zivot=0.95, urb=0.15, vek=-0.10),
        popis=("běžně nakupuje na internetu",
               "na internetu nenakupuje, chce si věc osahat v obchodě"),
        temata=["online", "nakup", "retail", "doruceni", "potraviny"]),
    "adopce_ai": dict(
        blok="kanaly", kotva=0.32, zdroj="ČSÚ 2025", faktor="digitalni",
        marker="používá nástroje umělé inteligence",
        koef={"_fit": "ai", "urb": 0.10},
        popis=("umělou inteligenci už používá",
               "s umělou inteligencí nic nedělá"),
        temata=["technologie", "online", "prace"]),
    "privatni_znacky": dict(
        blok="kanaly", kotva=0.61, zdroj="YouGov Shopper 2025", faktor="hmotna_situace",
        marker="běžně kupuje privátní značky řetězců",
        koef=dict(cenova_citlivost=0.60, vzd=-0.10, vek=-0.05),
        popis=("privátní značky řetězců bere úplně běžně",
               "privátkám se vyhýbá, drží se značek, které zná"),
        temata=["potraviny", "retail", "cena", "znacka", "nakup"]),
    "vernost_znacce": dict(
        blok="kanaly", kotva=None, zdroj="bez kotvy", faktor="konzervatismus",
        marker="drží se osvědčených značek",
        koef=dict(vek=0.35, cenova_citlivost=-0.30, vzd=-0.05),
        popis=("drží se značek, které zná, nerad zkouší jiné",
               "značka mu nic neříká, přebíhá podle nabídky"),
        temata=["znacka", "retail", "potraviny", "reklama", "loajalita"]),
    "vliv_recenzi": dict(
        blok="kanaly", kotva=0.55, zdroj="Nielsen", faktor="digitalni",
        marker="dá víc na recenze než na cenu",
        koef=dict(digitalni_zivot=0.50, vek=-0.25, vzd=0.15),
        popis=("před nákupem čte recenze a dá na ně",
               "recenze neřeší, rozhodne se sám na místě"),
        temata=["nakup", "online", "znacka", "reklama", "sluzby"]),

    # ---------------- C. HODNOTY SPOTREBY
    "zdravy_zivotni_styl": dict(
        blok="hodnoty", kotva=None, zdroj="bez kotvy", faktor="vedoma_spotreba",
        marker="hlídá si složení a zdravý životní styl",
        koef=dict(vzd=0.30, urb=0.20, muz=-0.25, financni_polstar=0.20),
        popis=("hlídá si složení, zdraví řeší aktivně",
               "složení neřeší, jí co mu chutná"),
        temata=["potraviny", "zdravi", "sport", "eko"]),
    "ekologicka_uvedomelost": dict(
        blok="hodnoty", kotva=None, zdroj="bez kotvy", faktor="vedoma_spotreba",
        marker="připlatí si za ekologickou variantu",
        koef=dict(vzd=0.35, urb=0.25, vek=-0.15, financni_polstar=0.20, muz=-0.15),
        popis=("dopad na životní prostředí ho zajímá, třídí a řeší to",
               "ekologii bere jako módu, za zelené si nepřiplatí"),
        temata=["eko", "potraviny", "energie", "doprava", "obaly"]),
    "lokalni_ukotveni": dict(
        blok="hodnoty", kotva=None, zdroj="bez kotvy", faktor="konzervatismus",
        marker="preferuje české a místní",
        koef=dict(vek=0.35, urb=-0.30, vzd=-0.20),
        popis=("drží se českého a místního, na kraj a obec dá",
               "je mu jedno odkud to je, nemá potřebu kupovat české"),
        temata=["potraviny", "znacka", "politika", "retail"]),
    "status_znacka": dict(
        blok="hodnoty", kotva=None, zdroj="bez kotvy", faktor=None,
        marker="značka je pro něj signál postavení",
        koef=dict(vek=-0.30, urb=0.20, financni_polstar=0.25, trida=0.15),
        popis=("na značce a na tom, jak to vypadá, mu záleží",
               "je mu jedno, co si o jeho věcech myslí ostatní"),
        temata=["znacka", "reklama", "premium", "moda", "auto"]),

    # ---------------- D. ZIVOTNI SITUACE
    "casova_tisen": dict(
        blok="situace", kotva=None, zdroj="bez kotvy", faktor=None,
        marker="chronicky nemá čas",
        koef=dict(vek=-0.35, vzd=0.25, urb=0.15, trida=0.15),
        popis=("chronicky nestíhá, za ušetřený čas si připlatí",
               "času má dost, klidně kvůli úspoře objede víc obchodů"),
        temata=["sluzby", "doruceni", "potraviny", "nakup", "doprava"]),
    "zdravotni_omezeni": dict(
        blok="situace", kotva=None, zdroj="bez kotvy", faktor=None,
        marker="má zdravotní omezení",
        koef=dict(vek=0.60, vzd=-0.15, tvrdost=0.25, financni_polstar=-0.15),
        popis=("zdraví ho omezuje v běžném fungování",
               "zdravotně mu nic nebrání"),
        temata=["zdravi", "sluzby", "doprava", "sport"]),

    # ---------------- E. POSTOJE A INFORMACE
    "duvera_instituce": dict(
        blok="postoje", kotva=0.25, zdroj="CVVM 3–4/2026", faktor="duvera",
        marker="důvěřuje vládě",
        koef=dict(trida=0.45, vzd=0.20, urb=0.10, tvrdost=-0.30, vek=0.10),
        popis=("státu a institucím věří, bere je jako funkční",
               "státu a politikům nevěří, počítá s tím, že ho někdo tahá za nos"),
        temata=["politika", "verejne", "energie", "zdravi", "regulace"]),
    "zajem_verejne_deni": dict(
        blok="postoje", kotva=0.56, zdroj="CVVM 3–4/2026", faktor=None,
        marker="zajímá se o politiku",
        koef=dict(vzd=0.35, vek=0.30, muz=0.25, urb=0.10, trida=0.15),
        popis=("sleduje veřejné dění, má na věci názor",
               "o politiku a veřejné dění se nezajímá, nemá k tomu co říct"),
        temata=["politika", "verejne", "media", "regulace"]),
    "duvera_firmam": dict(
        blok="postoje", kotva=None, zdroj="bez kotvy", faktor="duvera",
        marker="věří tomu, co firmy o produktech tvrdí",
        koef=dict(duvera_instituce=0.45, vzd=-0.10, vek=-0.10),
        popis=("reklamě a tvrzením firem celkem věří",
               "reklamě nevěří, počítá s tím, že ho chtějí obalamutit"),
        temata=["reklama", "znacka", "nakup", "media"]),
    "otevrenost_zmene": dict(
        blok="postoje", kotva=None, zdroj="bez kotvy", faktor="-konzervatismus",  # OPRAVENO 13.8.2026: otevrenost vuci zmene je definicne OPAK konzervatismu, ne jeho soucast; mereno r=+0,05 s tradicnimi genderovymi rolemi, mel byt zaporny
        marker="zkusí novinku dřív než většina",
        koef=dict(vek=-0.45, vzd=0.30, urb=0.20, trida=0.20),
        popis=("novinky zkouší mezi prvními",
               "u zavedeného zůstává, novinky si nechá projít"),
        temata=["technologie", "znacka", "sluzby", "predplatne", "nakup"]),
    "media_online": dict(
        blok="postoje", kotva=None, zdroj="bez kotvy", faktor="digitalni",
        marker="informace bere hlavně online",
        koef=dict(digitalni_zivot=0.70, vek=-0.30),
        popis=("zprávy a informace bere z internetu a sociálních sítí",
               "informace bere z televize a rádia, online skoro ne"),
        temata=["media", "reklama", "politika", "online"]),
    "socialni_site": dict(
        blok="postoje", kotva=None, zdroj="bez kotvy", faktor="digitalni",
        marker="aktivní na sociálních sítích",
        koef=dict(digitalni_zivot=0.55, vek=-0.45, muz=-0.10),
        popis=("na sociálních sítích tráví denně dost času",
               "sociální sítě skoro nepoužívá"),
        temata=["media", "reklama", "online", "moda", "socialni_site"]),

    # ---------------- F. POLITIKA (audit "mapa zdroju" v3, DATA_CZ, srpen 2026)
    "ucast_volby": dict(
        blok="politika", kotva=0.6895, zdroj="ČSÚ volby 2025", faktor=None,
        marker="šel by k volbám",
        koef=dict(vek=0.35, vzd=0.30, trida=0.20, urb=0.10),
        popis=("k volbám chodí pravidelně",
               "k volbám nechodí, nebo jen výjimečně"),
        temata=["politika", "verejne"]),
    "pravicova_orientace": dict(
        blok="politika", kotva=0.38, zdroj="CVVM 6/2025 (marginál) + CSES Modul 5 ČR "
                                          "2017+2021 (mikrodata, N=3049, korelace)",
        faktor="konzervatismus",
        marker="řadí se na škále doprava (6-10)",
        # OPRAVENO na skutecnych CSES mikrodatech: vek koreluje SE SEBEURCENIM
        # L-P ZAPORNE (r=-0,23) — mladsi Cesi se v CSES radi vic doprava nez
        # starsi, presny opak puvodniho odhadu (+0,05). Vzdelani +0,145 potvrzuje
        # puvodni smer, jen slabsi silu.
        koef=dict(vzd=0.18, trida=0.30, urb=0.15, vek=-0.25),
        popis=("politicky se řadí spíš doprava",
               "politicky se řadí spíš doleva nebo do středu"),
        temata=["politika", "verejne", "regulace"]),
    "liberalni_orientace": dict(
        blok="politika", kotva=0.25, zdroj="CVVM 6/2025 (škála 0-10)", faktor="-konzervatismus",  # OPRAVENO 13.8.2026: liberal je protipol konzervativce
        marker="řadí se na škále k liberálnímu pólu (6-10)",
        koef=dict(vzd=0.35, urb=0.25, vek=-0.25, trida=0.15),
        popis=("v hodnotách je spíš liberální, otevřený změnám norem",
               "v hodnotách je spíš konzervativní, drží se tradice"),
        temata=["politika", "hodnoty", "verejne"]),
    "duvera_mediim": dict(
        blok="politika", kotva=0.44, zdroj="CVVM 3-4/2026 (veřejnoprávní média)",
        faktor="duvera",
        marker="důvěřuje veřejnoprávním médiím",
        koef=dict(trida=0.30, vzd=0.20, tvrdost=-0.20, vek=0.15),
        popis=("veřejnoprávním médiím jako ČT/ČRo věří",
               "veřejnoprávním médiím nevěří, bere je jako stranické"),
        temata=["media", "politika", "reklama"]),
    "podpora_eu": dict(
        blok="politika", kotva=0.74, zdroj="CVVM 8/2025", faktor="konzervatismus",
        marker="podporuje členství ČR v EU",
        koef=dict(vzd=0.35, urb=0.20, trida=0.25, vek=-0.05),
        popis=("členství v EU podporuje, bere ho jako přínos",
               "k členství v EU je skeptický nebo proti"),
        temata=["politika", "regulace", "verejne"]),
    "organizacni_participace": dict(
        blok="politika", kotva=0.554, zdroj="odvozeno z CVVM podzim 2023 (sportovní 26 %, "
                                           "občanská 19 %, charita 19 %, církev 8 %; "
                                           "P(aspoň jedno) při nezávislosti)",
        faktor=None,
        marker="je členem nějakého spolku či organizace",
        koef=dict(urb=-0.10, vzd=0.15, vek=0.10, trida=0.15),
        popis=("je členem spolku, klubu nebo organizace, kde se pravidelně schází",
               "v žádném spolku ani klubu není"),
        temata=["verejne", "loajalita", "vztahy"]),

    # ---------------- G. PRACE A KARIERA
    "spokojenost_praci": dict(
        blok="prace", kotva=0.3516, zdroj="Eurostat LFS 2021 (ČR)", faktor="hmotna_situace",
        marker="je se svou prací velmi spokojen(a)",
        koef=dict(trida=0.35, financni_polstar=0.30, vek=-0.05),
        popis=("prací je velmi spokojen(a)",
               "prací je spíš nespokojen(a), bere ji jako nutnost"),
        temata=["prace", "sluzby"]),
    "home_office": dict(
        blok="prace", kotva=0.21, zdroj="ČSÚ ICT v podnicích 2024", faktor="digitalni",
        marker="pracuje aspoň částečně z domova",
        koef=dict(vzd=0.45, digitalni_zivot=0.30, urb=0.20, vek=-0.10),
        popis=("pracuje aspoň částečně z domova, home office bere jako běžnou věc",
               "pracuje výhradně na pracovišti, z domova pracovat nemůže nebo nechce"),
        temata=["prace", "technologie", "doprava"]),
    "ai_v_praci": dict(
        blok="prace", kotva=0.20, zdroj="ČSÚ VŠIT 2025 (zaměstnaní)", faktor="digitalni",
        marker="používá AI nástroje pro pracovní účely",
        koef=dict(vzd=0.40, digitalni_zivot=0.45, vek=-0.20, urb=0.10),
        popis=("umělou inteligenci v práci běžně používá",
               "v práci s umělou inteligencí nepracuje"),
        temata=["prace", "technologie", "online"]),
    "vedouci_role": dict(
        blok="prace", kotva=0.1694, zdroj="Eurostat LFS 2021 (ČR)", faktor="hmotna_situace",
        marker="má v práci dohled nad jinými lidmi",
        koef=dict(vzd=0.35, trida=0.35, vek=0.20),
        popis=("v práci vede nebo dohlíží na jiné lidi",
               "v práci nikoho nevede ani na nikoho nedohlíží"),
        temata=["prace", "B2B"]),

    # ---------------- H. VOLNY CAS A ZIVOTNI STYL
    "cetba_knih": dict(
        blok="volny_cas", kotva=0.325, zdroj="ČSÚ Životní podmínky 2022 (5+ knih/rok)",
        faktor="vedoma_spotreba",
        marker="přečte aspoň 5 knih ročně",
        koef=dict(vzd=0.45, urb=0.15, vek=0.10, muz=-0.15),
        popis=("čte hodně, aspoň pár knih měsíčně",
               "knihy skoro nečte"),
        temata=["media", "volny_cas"]),
    "cestovani_zahranici": dict(
        blok="volny_cas", kotva=0.471, zdroj="ČSÚ VŠCR 2024 (5,7 mil. ze 12,2 mil. delších "
                                            "cest bylo do zahraničí)",
        faktor="hmotna_situace",
        marker="jezdí na dovolenou i do zahraničí, ne jen po ČR",
        koef=dict(financni_polstar=0.55, vzd=0.30, urb=0.15, vek=-0.10),
        popis=("na dovolenou jezdí i do zahraničí",
               "na dovolenou jezdí hlavně po Česku, zahraničí si moc nedovolí"),
        temata=["volny_cas", "doprava", "finance"]),
    "aktivni_pohyb": dict(
        blok="volny_cas", kotva=0.153, zdroj="ČSÚ Životní podmínky 2022 (denní pohyb)",
        faktor="vedoma_spotreba",
        marker="ve volném čase se hýbe denně",
        koef=dict(vzd=0.20, vek=-0.20, urb=0.10, financni_polstar=0.15),
        popis=("ve volném čase se pravidelně hýbe, sportuje nebo chodí ven",
               "ve volném čase se moc nehýbe"),
        temata=["zdravi", "volny_cas", "sport"]),
    "ma_mazlicka": dict(
        blok="volny_cas", kotva=0.42, zdroj="FEDIAF 2026 (alespoň pes)", faktor=None,
        marker="má doma psa",
        koef=dict(urb=-0.25, vek=-0.05),
        popis=("doma má psa",
               "žádného psa doma nemá"),
        temata=["volny_cas", "zdravi"]),
    "ma_kocku": dict(
        blok="volny_cas", kotva=0.23, zdroj="FEDIAF 2026 (alespoň kočka)", faktor=None,
        marker="má doma kočku",
        koef=dict(urb=0.05),  # bez publikovane vazby, jen mirna korekce proti psu
        popis=("doma má kočku",
               "žádnou kočku doma nemá"),
        temata=["volny_cas", "zdravi"]),
    "hraje_hry_tydne": dict(
        blok="volny_cas", kotva=0.37, zdroj="Česká spořitelna/NMS 2023 (N=1544, 15-64 let, "
                                           "hraje aspoň týdně)",
        faktor="digitalni",
        marker="hraje počítačové/mobilní hry aspoň jednou týdně",
        koef=dict(vek=-0.45, muz=0.30, digitalni_zivot=0.20),
        popis=("hraje počítačové nebo mobilní hry aspoň jednou týdně",
               "hry nehraje, nebo jen výjimečně"),
        temata=["volny_cas", "technologie", "online"]),

    # ---------------- I. ZDRAVI (L07 senzitivni kategorie — vzdy jen tendence)
    "nadvaha": dict(
        blok="zdravi", kotva=0.665, zdroj="SZÚ EHES 2019 (BMI nad normou, prům. m+ž)",
        faktor="rizikove_chovani_zdravi",  # epidemiologicke shlukovani, viz FAKTORY
        marker="má BMI nad normou",
        koef=dict(vek=0.25, trida=-0.20, muz=0.20),
        popis=("s váhou trochu bojuje, BMI má nad doporučenou hranicí",
               "váhu má v normě"),
        temata=["zdravi", "sport"]),
    "kuractvi": dict(
        blok="zdravi", kotva=0.187, zdroj="SZÚ NAUTA 2025 (denní kuřáci)",
        faktor="rizikove_chovani_zdravi",
        marker="denně kouří",
        koef=dict(vzd=-0.30, trida=-0.25, vek=-0.10, tvrdost=0.25),
        popis=("denně kouří",
               "nekouří"),
        temata=["zdravi"]),
    "rizikove_piti_alkohol": dict(
        blok="zdravi", kotva=0.118, zdroj="SZÚ NAUTA 2025 (rizikové+škodlivé pití)",
        faktor="rizikove_chovani_zdravi",
        marker="pije alkohol rizikově až škodlivě",
        koef=dict(vzd=-0.20, tvrdost=0.30, muz=0.25, vek=-0.10),
        popis=("s alkoholem to občas přežene",
               "alkohol pije jen mírně nebo vůbec"),
        temata=["zdravi"]),
    "preventivni_pece": dict(
        blok="zdravi", kotva=0.465, zdroj="SZÚ EHES 2019 (prohlídka do 1 roku, prům.)",
        faktor="vedoma_spotreba",
        marker="byl(a) na preventivní prohlídce do roka",
        koef=dict(vzd=0.25, vek=0.20, financni_polstar=0.15, muz=-0.15),
        popis=("na preventivní prohlídky chodí pravidelně",
               "na preventivní prohlídky moc nechodí"),
        temata=["zdravi"]),

    # ---------------- J. SOCIALNI VZTAHY A SITE
    "osamelost": dict(
        blok="vztahy", kotva=0.40, zdroj="JRC EU Loneliness Survey 2022 (UCLA-3, ČR mikrodata)",
        faktor="-socialni_zapojeni",  # opak siroka_sit, viz FAKTORY komentar
        marker="na UCLA-3 skóre vychází jako spíš osamělý(á)",
        # OPRAVENO na skutecnych mikrodatech (N=1002, drive jen odhad):
        # UCLA-3 koreluje s vekem -0,23 (mladsi jsou osamelejsi, ne starsi,
        # jak jsem puvodne predpokladal — obraceny smysl), se vzdelanim
        # prakticky vubec (-0,02, puvodni koeficient smazan).
        koef=dict(vek=-0.35, tvrdost=0.30, trida=-0.20),
        popis=("cítí se dost osamělý(á), chybí mu/jí pravidelný kontakt s lidmi",
               "má kolem sebe dost lidí, osamělost neřeší"),
        temata=["vztahy", "zdravi"]),
    "siroka_sit": dict(
        blok="vztahy", kotva=0.60, zdroj="odvozeno z JRC Loneliness Survey 2022",
        faktor="socialni_zapojeni",
        marker="má širokou síť blízkých lidí (rodina i přátelé)",
        koef=dict(urb=-0.10, vek=-0.05, tvrdost=-0.20, trida=0.15),
        popis=("má kolem sebe dost blízkých lidí, na koho se obrátit",
               "blízkých lidí, na které by se mohl(a) obrátit, má málo"),
        temata=["vztahy"]),
    "dobrovolnictvi": dict(
        blok="vztahy", kotva=0.123, zdroj="ČSÚ Životní podmínky 2022", faktor=None,
        marker="věnuje se neformálnímu dobrovolnictví",
        koef=dict(vzd=0.20, vek=0.15, trida=0.15, urb=-0.10),
        popis=("občas pomáhá/dobrovolničí bez nároku na odměnu",
               "dobrovolnictví neřeší"),
        temata=["vztahy", "verejne", "loajalita"]),

    # ---------------- K. Z MIKRODAT — PIAAC 2023 CZ (N=5057) + CSES Modul 5 ČR
    # (N=3049, 2017+2021), skutecna respondent-level data ziskana 13.8.2026.
    # Koeficienty NEJSOU odhadnute — jsou to vazene korelace spoctene primo
    # z mikrodat (viz mikrodata/acquired_data). Marginal (kotva) je take
    # skutecne namereny podil na ceskem vzorku, ne odhad z agregatu.
    "kognitivni_gramotnost": dict(
        blok="dovednosti", kotva=0.244, zdroj="OECD PIAAC 2023 CZ mikrodata (N=5057), "
                                             "PVLIT1<226 = úroveň 1 a nižší",
        faktor=None,
        marker="má nízkou čtenářskou gramotnost (PIAAC úroveň 1 a nižší)",
        # Shoduje se nezavisle s NPI/MSMT tiskovou zpravou 12/2024 ("24 % dospelych").
        koef=dict(vzd=-0.45, vek=0.20),  # r=-0,32 vzdelani, r=+0,14 vek (mereno)
        popis=("se složitějšími texty a formuláři má problém, radši se jim vyhne",
               "s texty a formuláři si poradí bez problémů"),
        temata=["technologie", "finance", "regulace", "sluzby", "verejne"]),
    "socialni_duvera": dict(
        blok="vztahy", kotva=0.257, zdroj="OECD PIAAC 2023 CZ mikrodata (N=5057), "
                                         "škála důvěry 0-10, práh ≥6",
        faktor="duvera",
        marker="lidem obecně spíš důvěřuje (score ≥6/10)",
        koef=dict(vzd=0.30),  # r=0,178 vzdelani (mereno)
        popis=("lidem obecně spíš věří, nepředpokládá nejhorší",
               "lidem obecně moc nevěří, radši je opatrný(á)"),
        temata=["vztahy", "sluzby", "reklama", "online"]),
    "anti_elitismus": dict(
        blok="politika", kotva=0.418, zdroj="CSES Modul 5 ČR mikrodata (N=3049, "
                                           "2017+2021), průměr 3 položek E3004_2/4/7 ≤2",
        faktor="duvera",
        marker="silně souhlasí, že se elity nezajímají o lidi a jsou problém",
        koef=dict(vzd=-0.30, trida=-0.20, tvrdost=0.15),  # r=0,15 vzdelani (obracene, mereno)
        popis=("politiky a elity vnímá jako odtržené od lidí a jako část problému",
               "politikům a elitám v zásadě věří, že se snaží dělat svou práci"),
        temata=["politika", "verejne"]),
    "majoritarianismus": dict(
        blok="politika", kotva=0.443, zdroj="CSES Modul 5 ČR mikrodata (N=3049, "
                                           "2017+2021), E3004_6 ≤2",
        faktor=None,
        marker="souhlasí, že o důležitých otázkách by měli rozhodovat přímo lidé",
        koef=dict(vzd=-0.25, urb=-0.15),  # r=0,123 vzdelani (obracene, mereno)
        popis=("myslí si, že o důležitých věcech by měli rozhodovat přímo lidé, ne politici",
               "myslí si, že složitá rozhodnutí patří odborníkům a zvoleným zástupcům"),
        temata=["politika", "verejne", "regulace"]),
    "silny_vudce": dict(
        blok="politika", kotva=0.260, zdroj="CSES Modul 5 ČR mikrodata (N=3049, "
                                           "2017+2021), E3004_5 ≤2",
        faktor="konzervatismus",
        marker="souhlasí, že silný vůdce může pro zemi ohnout pravidla",
        koef=dict(vzd=-0.20, vek=-0.10, trida=-0.15),  # r=0,082 vzdelani (obracene, mereno)
        popis=("myslí si, že silný vůdce, co ohne pravidla, by zemi prospěl",
               "silného vůdce nad pravidly a zákony si nepřeje"),
        temata=["politika", "verejne"]),

    # ---------------- L. TŘETÍ VLNA REŠERŠE (srpen 2026) — nové kalibrace
    # + doplnění dimenze, která byla v DATA_CZ (D151-156, klima) uz od druhe
    # vlny, ale nikdy se nedostala do dispozice.py.
    "klimaticka_odpovednost": dict(
        blok="hodnoty", kotva=0.32, zdroj="CVVM 6/2025 (cítí osobní odpovědnost za klima)",
        faktor="vedoma_spotreba",
        marker="cítí osobní odpovědnost za klimatickou změnu",
        koef=dict(vzd=0.30, urb=0.20, vek=-0.15, financni_polstar=0.15, muz=-0.15),
        popis=("cítí osobní odpovědnost za klima, snaží se to promítnout do chování",
               "klimatickou změnu bere jako fakt, ale osobní odpovědnost necítí"),
        temata=["eko", "politika", "energie"]),
    "sportuje_pravidelne": dict(
        blok="volny_cas", kotva=0.60, zdroj="ČSÚ 2025 (16-34 let 73 %, 65+ 44 %)",
        faktor="vedoma_spotreba",
        marker="sportuje pravidelně",
        koef=dict(vek=-0.55, vzd=0.15, financni_polstar=0.15),  # realny vekovy sklon 73%->44%
        popis=("pravidelně sportuje",
               "sport neřeší, pohyb má spíš příležitostný"),
        temata=["sport", "zdravi", "volny_cas"]),
    "tradicni_genderove_role": dict(
        blok="hodnoty", kotva=0.66, zdroj="CVVM 2016 (muž má finančně zajistit domácnost)",
        faktor="konzervatismus",
        marker="souhlasí, že muž má finančně zajistit domácnost",
        koef=dict(vzd=-0.30, urb=-0.20, vek=0.30, muz=0.10),
        popis=("v genderových rolích je spíš tradiční — muž živí, žena pečuje",
               "genderové role bere jako věc volby, ne dané dělby"),
        temata=["hodnoty", "politika", "vztahy"]),
    "duvera_ockovani": dict(
        blok="zdravi", kotva=0.64, zdroj="Současná česká rodina 2020", faktor="duvera",
        marker="očkování obecně důvěřuje",
        # POZOR — zdroj popisuje paradox: vzdelanejsi lide maji NIZSI duveru
        # v ockovani, ale VYSSI ochotu se nechat ockovat. Koeficient tu proto
        # jde proti smeru ostatnich "duvera" dimenzi (kde vzdelani obvykle
        # duveru zvysuje) — zaverna, ne chyba.
        koef=dict(vzd=-0.15, financni_polstar=0.10),
        popis=("očkování bere jako bezpečné a užitečné",
               "k očkování je spíš skeptický(á)"),
        temata=["zdravi", "verejne"]),
    "ockovani_chripka": dict(
        blok="zdravi", kotva=0.067, zdroj="Eurostat EHIS 2019 (15+, DATA_CZ D272)",
        faktor=None,
        marker="byl(a) očkován(a) proti chřipce za posledních 12 měsíců",
        koef=dict(vek=0.35, financni_polstar=0.15),  # 15+:6,7 % -> 65+:16,1 % -> 75+:20,4 %
        popis=("proti chřipce se nechává pravidelně očkovat",
               "proti chřipce se neočkuje"),
        temata=["zdravi"]),
    "ovoce_zelenina_5x": dict(
        blok="zdravi", kotva=0.08, zdroj="ČSÚ/EHIS 2019 (5+ porcí ovoce/zeleniny denně)",
        faktor="vedoma_spotreba",
        marker="jí denně aspoň 5 porcí ovoce a zeleniny",
        koef=dict(vzd=0.25, urb=0.15, muz=-0.20, financni_polstar=0.15),
        popis=("na jídelníček s dostatkem ovoce a zeleniny dbá",
               "ovoce a zeleninu do jídelníčku moc nezařazuje"),
        temata=["zdravi", "potraviny"]),
    "internetove_bankovnictvi": dict(
        blok="kanaly", kotva=0.78, zdroj="ČSÚ VŠIT 2025 (16+)", faktor="digitalni",
        marker="používá internetové bankovnictví",
        koef=dict(digitalni_zivot=0.60, vek=-0.20, vzd=0.15),
        popis=("bankovní záležitosti řeší přes internet nebo appku",
               "internetové bankovnictví nepoužívá, chodí na pobočku"),
        temata=["finance", "technologie", "online"]),
    "egovernment_use": dict(
        blok="prace", kotva=0.785, zdroj="ČSÚ/DESI 2024-25 (komunikace s úřady online)",
        faktor="digitalni",
        marker="s úřady komunikuje online",
        koef=dict(digitalni_zivot=0.55, vzd=0.25, vek=-0.15),
        popis=("s úřady si vyřizuje věci online, na přepážku chodí jen když musí",
               "úřední věci raději řeší osobně na přepážce"),
        temata=["verejne", "technologie", "online"]),
    "financni_gramotnost": dict(
        blok="ekonomika", kotva=0.26, zdroj="MF ČR 2025 (skutečná znalost RPSN)",
        faktor=None,
        marker="rozumí finančním pojmům jako RPSN",
        koef=dict(vzd=0.40, financni_polstar=0.20),
        popis=("finančním pojmům jako RPSN nebo úrokům dobře rozumí",
               "finanční pojmy jako RPSN mu/jí moc neříkají"),
        temata=["finance", "regulace"]),
    "konflikt_prace_soukromi": dict(
        blok="prace", kotva=0.52, zdroj="STEM TRENDY 6/2026 (18-29: 63 %, 45-59: 41 %)",
        faktor=None,
        marker="práce mu/jí zasahuje do soukromého života",
        koef=dict(vek=-0.45, vzd=0.10),  # realny vekovy sklon 63%->41%
        popis=("práce mu/jí dost zasahuje do soukromí, těžko to odděluje",
               "práci a soukromí drží celkem oddělené"),
        temata=["prace", "zdravi", "vztahy"]),
    "pracovni_stres": dict(
        blok="prace", kotva=0.72, zdroj="STEM TRENDY 6/2026 (vnímá práci jako stresující)",
        faktor=None,
        marker="práci vnímá jako stresující",
        koef=dict(trida=-0.20, financni_polstar=-0.15, vek=-0.10),
        popis=("práci vnímá jako dost stresující",
               "práci stresující nepovažuje"),
        temata=["prace", "zdravi"]),

    # ---------------- M. QoG EQI 2024 ČR mikrodata (N=5060) + ISSP Family/Health
    # 2022 CZ mikrodata (N=1262), ziskana 13.8.2026. Vazene korelace, ne odhad.
    "nizka_duvera_parlamentu": dict(
        blok="politika", kotva=0.528, zdroj="QoG EQI 2024 ČR mikrodata (N=5060), "
                                           "důvěra parlamentu ≤3/10",
        faktor="-duvera",  # OPRAVENO 13.8.2026: mereno r=+0,10 s duvera_instituce
                          # (melo byt zaporne — vysoka obecna duvera by nemela
                          # souviset s vysokou NEduverou parlamentu). Stejny typ
                          # chyby jako osamelost/siroka_sit, nalezeno pri stejne
                          # systemove kontrole.
        marker="parlamentu vůbec nedůvěřuje (≤3/10)",
        koef=dict(vzd=-0.35, tvrdost=0.15),  # r=-0,169 vzdelani (mereno)
        popis=("parlamentu vůbec nedůvěřuje",
               "k parlamentu má aspoň částečnou důvěru"),
        temata=["politika", "verejne"]),
    "silna_podpora_redistribuce": dict(
        blok="politika", kotva=0.404, zdroj="QoG EQI 2024 ČR mikrodata (N=5060), "
                                           "souhlas se zdaněním bohatých ≥8/10",
        faktor=None,
        marker="silně podporuje přerozdělování skrz daně",
        koef=dict(vzd=-0.28, trida=-0.25),  # r=-0,137 vzdelani (mereno)
        popis=("silně podporuje, aby stát přerozděloval přes daně bohatým ve prospěch chudých",
               "přerozdělování přes daně silně nepodporuje"),
        temata=["politika", "finance", "regulace"]),
    "imigrace_skodi": dict(
        blok="politika", kotva=0.407, zdroj="QoG EQI 2024 ČR mikrodata (N=5060), "
                                           "souhlas že přistěhovalci škodí zemi ≥8/10",
        faktor="konzervatismus",
        marker="silně souhlasí, že přistěhovalci zemi spíš škodí",
        koef=dict(vzd=-0.30, urb=-0.20, vek=0.07),  # r=-0,153 vzdelani (mereno)
        popis=("silně si myslí, že přistěhovalci zemi spíš škodí",
               "s tím, že přistěhovalci zemi škodí, silně nesouhlasí"),
        temata=["politika", "verejne"]),
    "podpora_manzelstvi_gay": dict(
        blok="hodnoty", kotva=0.518, zdroj="QoG EQI 2024 ČR mikrodata (N=5060), "
                                          "souhlas s manželstvím gayů a leseb ≥8/10",
        faktor="-konzervatismus",  # OPRAVENO 13.8.2026: mereno r=+0,13 s tradicnimi genderovymi rolemi, mel byt zaporny — je to progresivni, ne konzervativni pozice
        marker="silně podporuje manželství gayů a leseb",
        koef=dict(vzd=0.02, vek=-0.09),  # vazba na vzdelani mereno prakticky nulova (r=0,011)
        popis=("manželství pro gaye a lesby silně podporuje",
               "manželství pro gaye a lesby silně nepodporuje"),
        temata=["hodnoty", "politika"]),
    "ma_stranickou_preferenci": dict(
        blok="politika", kotva=0.736, zdroj="QoG EQI 2024 ČR mikrodata (N=5060), "
                                           "má konkrétní odpověď na 'koho by volil', "
                                           "ne 'neví/odmítá'",
        faktor=None,
        marker="má jasnou představu, koho by teď volil",
        # POZOR: vazba na vzdelani i vek mereno prakticky nulova (r=-0,01 a -0,03) —
        # rozhodnost nezavisi na demografii tak, jak by clovek cekal.
        koef=dict(zajem_verejne_deni=0.35),
        popis=("kdyby byly volby teď, ví přesně, koho by volil",
               "kdyby byly volby teď, neví, koho by volil, nebo to odmítá říct"),
        temata=["politika", "verejne"]),
    "chronicka_nemoc": dict(
        blok="zdravi", kotva=0.311, zdroj="ISSP Rodina a zdraví 2022 ČR mikrodata (N=1262)",
        faktor=None,
        marker="má dlouhodobou nebo chronickou nemoc či invaliditu",
        koef=dict(vek=0.55, trida=-0.15),  # r=0,429 vek (silne mereno)
        popis=("má nějakou dlouhodobou nebo chronickou nemoc",
               "žádnou dlouhodobou ani chronickou nemoc nemá"),
        temata=["zdravi"]),
    "nespokojenost_zdravotnictvim": dict(
        blok="zdravi", kotva=0.068, zdroj="ISSP Rodina a zdraví 2022 ČR mikrodata (N=1262)",
        faktor="-duvera",  # OPRAVENO 13.8.2026, stejny typ chyby jako u
                          # nizka_duvera_parlamentu — "nespokojenost/neduvera"
                          # nesmi sdilet KLADNY faktor s dimenzemi merici
                          # vysokou duveru.
        marker="je s českým zdravotnictvím nespokojen(a)",
        koef=dict(tvrdost=0.25, financni_polstar=-0.10),
        popis=("s českým zdravotnictvím je celkově nespokojen(a)",
               "s českým zdravotnictvím je celkově spokojen(a)"),
        temata=["zdravi", "verejne"]),

    # ---------------- N. NUDZ CAPI 2022 (N=3063) — plne PHQ-9/GAD-7, jen
    # celkove skore, NIKDY jednotliva polozka (viz SOURCE_AND_USE.md v datech:
    # polozka o sebeposkozeni PHQ-9 #9 se nesmi objevit v personě ani jako
    # latentni marker). Formulace klinicka a neutralni, ne narativni.
    "depresivni_symptomy": dict(
        blok="zdravi", kotva=0.087, zdroj="NÚDZ CAPI 2022 ČR mikrodata (N=3063), "
                                         "PHQ-9 ≥10 (středně těžké a těžší pásmo)",
        faktor="dusevni_zdravi",
        marker="má na škále PHQ-9 skóre odpovídající středně těžké až těžké depresivní symptomatice",
        # Vazby na vek/vzdelani/pohlavi mereno prakticky nulove (vsechny |r|<0,04) —
        # zamerne NEPOUZIVAM silnejsi koeficienty, nez co data skutecne ukazuji.
        koef=dict(tvrdost=0.20, financni_polstar=-0.15),
        popis=("v poslední době se necítí dobře, má víc depresivních symptomů, než je běžné",
               "depresivní symptomy v poslední době nepociťuje"),
        temata=["zdravi"]),
    "uzkostne_symptomy": dict(
        blok="zdravi", kotva=0.042, zdroj="NÚDZ CAPI 2022 ČR mikrodata (N=3063), "
                                         "GAD-7 ≥10 (středně těžké a těžší pásmo)",
        faktor="dusevni_zdravi",  # PHQ-9/GAD-7 komorbidita — viz FAKTORY komentar
        marker="má na škále GAD-7 skóre odpovídající středně těžké až těžké úzkostné symptomatice",
        koef=dict(tvrdost=0.20, financni_polstar=-0.10),
        popis=("v poslední době je hodně úzkostný(á) a napjatý(á)",
               "úzkostné symptomy v poslední době nepociťuje"),
        temata=["zdravi"]),

    # ---------------- O. HFCS 2023 ČR (agregátní domácnostní tabulky, ne mikrodata)
    "ma_penzijni_pripojisteni": dict(
        blok="ekonomika", kotva=0.64, zdroj="HFCS 2023 ČR, tabulka C1 (dobrovolné "
                                           "penzijní připojištění/životní pojištění)",
        faktor="hmotna_situace",
        marker="má penzijní připojištění nebo životní pojištění",
        koef=dict(vek=0.25, financni_polstar=0.25, vzd=0.15),
        popis=("na penzi si spoří přes penzijní připojištění nebo životní pojištění",
               "penzijní připojištění ani životní pojištění nemá"),
        temata=["finance", "prace"]),
    "investuje_na_trhu": dict(
        blok="ekonomika", kotva=0.113, zdroj="HFCS 2023 ČR, tabulka C1 (podílové "
                                            "fondy nebo akcie, P(aspoň jedno))",
        faktor="hmotna_situace",
        marker="investuje do podílových fondů nebo akcií",
        koef=dict(financni_polstar=0.45, vzd=0.35),
        popis=("část úspor má v podílových fondech nebo akciích",
               "do fondů ani akcií neinvestuje, drží se spoření"),
        temata=["finance"]),

    # ---------------- P. CSDA "Public demand for the rule of law" ČR 2024
    # (N=981, CAWI, CC BY 4.0, ziskana 13.8.2026). Doplnuje anti_elitismus/
    # majoritarianismus (CSES) o ustavni protipol — priorita vetsinove vule
    # vs. nezavislosti soudu jako VZAJEMNE KONKURUJICI si polozky v jednom
    # zebricku (6 principu, 1=nejdulezitejsi), ne nezavisle skaly.
    "prioritizuje_vetsinovou_vladu": dict(
        blok="politika", kotva=0.173, zdroj="CSDA Rule of Law ČR 2024 mikrodata "
                                           "(N=981), 'vláda dle vůle většiny' jako "
                                           "TOP priorita ze 6 principů",
        faktor="konzervatismus",
        marker="ze 6 principů demokracie klade na první místo vládu podle vůle většiny",
        koef=dict(vek=0.30, vzd=0.05),  # r=0,133 vek, r=0,047 vzdelani (mereno)
        popis=("nejvíc ze všeho chce, aby vláda dělala to, co chce většina, i na úkor brzd",
               "vládu podle vůle většiny nepovažuje za nejdůležitější princip"),
        temata=["politika", "verejne", "regulace"]),
    "prioritizuje_nezavislost_soudu": dict(
        blok="politika", kotva=0.179, zdroj="CSDA Rule of Law ČR 2024 mikrodata "
                                           "(N=981), 'nezávislé soudy' jako TOP "
                                           "priorita ze 6 principů",
        faktor="duvera",
        marker="ze 6 principů demokracie klade na první místo nezávislé soudy",
        koef=dict(vek=-0.20, vzd=0.30),  # r=-0,093 vek, r=0,147 vzdelani (mereno)
        popis=("nejvíc ze všeho mu/jí záleží na tom, aby se šlo domoct práva u nezávislých soudů",
               "nezávislé soudy nepovažuje za nejdůležitější princip"),
        temata=["politika", "verejne"]),
}

# --- Doplneni provenance ke kazde dimenzi (FUZE_QC #1, #3, #11) ---
# Rok zdroje podle START/ZDROJE listu mapy: CSU SILC/VSIT 2025, CVVM 3-4/2026,
# YouGov 2025, Nielsen bez data (starsi prumysl. cislo -> nizsi jistota).
_ROK_ZDROJE = {
    "ČSÚ SILC 2025": 2025, "ČSÚ 2025": 2025, "ČSÚ/CBCB 2025": 2025,
    "CVVM 3–4/2026": 2026, "YouGov Shopper 2025": 2025, "Nielsen": 2022,
}

def _rok_ze_zdroje(zdroj: str) -> int:
    """Preferuje rok explicitne uvedeny ve zdrojovem labelu.

    V1 davala vetsine SPECIALIST dimenzi fallback 2024 a velke casti BRIDGE
    dokonce 2021 bez ohledu na skutecny label (EQI 2024, NUDZ 2022 atd.).
    Freshness pak byla pocitana z chybne provenance.
    """
    roky = [int(x) for x in re.findall(r"\b20\d{2}\b", str(zdroj))]
    if roky:
        return max(r for r in roky if r <= 2026)
    return _ROK_ZDROJE.get(str(zdroj), 2024)
_CITLIVE_DIM = {"duvera_instituce", "zajem_verejne_deni", "zdravotni_omezeni",
               "duvera_firmam", "ucast_volby", "pravicova_orientace",
               "liberalni_orientace", "duvera_mediim", "podpora_eu",
               "organizacni_participace", "nadvaha", "kuractvi",
               "rizikove_piti_alkohol", "preventivni_pece", "osamelost",
               "klimaticka_odpovednost", "tradicni_genderove_role",
               "duvera_ockovani", "ockovani_chripka"}

# Dimenze, kde jsou z realnych respondent-level mikrodat (ne jen agregatu)
# zmereny SOUCASNE marginal I vazba na demografii — PIAAC 2023 CZ (N=5057) a
# CSES Modul 5 CZ (N=3049), ziskana 13.8.2026. Vyssi jistota nez u SPECIALIST,
# kde byl mereny jen marginal a koeficienty jsem odhadl sam.
_BRIDGE_DIM = {"kognitivni_gramotnost", "socialni_duvera", "anti_elitismus",
              "majoritarianismus", "silny_vudce", "osamelost", "pravicova_orientace",
              "nizka_duvera_parlamentu", "silna_podpora_redistribuce", "imigrace_skodi",
              "podpora_manzelstvi_gay", "ma_stranickou_preferenci", "chronicka_nemoc",
              "nespokojenost_zdravotnictvim", "depresivni_symptomy", "uzkostne_symptomy",
              "prioritizuje_vetsinovou_vladu", "prioritizuje_nezavislost_soudu"}
_CITLIVE_DIM.update({"kognitivni_gramotnost", "anti_elitismus",
                     "majoritarianismus", "silny_vudce",
                     "nizka_duvera_parlamentu", "silna_podpora_redistribuce",
                     "imigrace_skodi", "podpora_manzelstvi_gay",
                     "ma_stranickou_preferenci", "chronicka_nemoc",
                     "depresivni_symptomy", "uzkostne_symptomy",
                     "prioritizuje_vetsinovou_vladu", "prioritizuje_nezavislost_soudu"})

for _dim, _d in DIMENZE.items():
    if _dim in _BRIDGE_DIM:
        _d["prov"] = _prov("BRIDGE", jistota=0.92, rok=_rok_ze_zdroje(_d["zdroj"]),
                           citlive=_dim in _CITLIVE_DIM)
    elif _d["kotva"] is not None:
        _d["prov"] = _prov("SPECIALIST", jistota=0.85, rok=_rok_ze_zdroje(_d["zdroj"]),
                           citlive=_dim in _CITLIVE_DIM)
    else:
        # nase vlastni koeficienty, marginal odhadnut na 50 % -> nizsi jistota
        _d["prov"] = _prov("OWN_ESTIMATE", jistota=0.35, rok=2026,
                           citlive=_dim in _CITLIVE_DIM)

_WORK_DIM = {"spokojenost_praci", "home_office", "ai_v_praci", "vedouci_role",
             "konflikt_prace_soukromi", "pracovni_stres"}
_HOUSEHOLD_CALIBRATED_DIM = {"financni_polstar", "zadluzenost",
                             "ma_penzijni_pripojisteni", "investuje_na_trhu"}
for _dim, _d in DIMENZE.items():
    if _dim in _WORK_DIM:
        _d["prov"]["eligible_population"] = "employed_18+"
        _d["prov"]["eligibility_source"] = (
            "PIAAC 2023 C2_D05 respondent bridge for ages 18-65; "
            "age 66+ remains unknown unless another respondent-level source is supplied")
    if _dim in _HOUSEHOLD_CALIBRATED_DIM:
        _d["prov"]["unit"] = "person_from_household_calibration"
        _d["prov"]["unit_warning"] = (
            "Kotva je household-level; respondent-level interpretace je synteticka.")
del _dim, _d
