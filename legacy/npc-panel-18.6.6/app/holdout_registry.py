"""
NPC PANEL — holdout_registry.py
Electric Twin princip: prisne oddelit data pouzita na stavbu persony od dat
pouzitych k overeni. Bez tohohle by holdout validace mohla nevedomky merit,
jak dobre panel reprodukuje data, na kterych byl sam kalibrovan — coz neni
validace, je to jen echo.

Tenhle modul NEDELA validaci (to je validace.py). Dela jedinou vec: drzi
seznam zdroju, ktere jsou VYHRAZENE pro holdout, a da se proti nemu zkontrolovat
kazdy novy zdroj pridavany do dispozice.py, driv nez se pouzije ke kalibraci.

    from holdout_registry import zkontroluj_pred_kalibraci
    zkontroluj_pred_kalibraci("Election_2025_CZ okrskove vysledky")
    # -> vyhodi vyjimku, pokud je zdroj v HOLDOUT_ZDROJE
"""

from __future__ import annotations

# Zdroje vyhrazene VYHRADNE pro holdout validaci (validace.py). Nikdy se
# nesmi objevit jako "zdroj" u zadne DIMENZE v dispozice.py — kdyby ano,
# validace by merila echo, ne skutecnou presnost.
#
# Kazdy zaznam ma "instituce" (organizace, ktera data vydava — CVVM, CSU...)
# a "presna_citace" (konkretni vlna/zprava, kterou uz mame k dispozici jako
# ground truth). Instituce SAMA O SOBE neni duvod zdroj zakazat — CVVM vydava
# desitky nezavislych vln rocne a pouzit vlnu z kvetna ke kalibraci a jinou
# vlnu z listopadu k validaci je v poradku. Presna_citace je duvod zakazat
# vzdy — to uz je doslova stejne cislo pouzite dvakrat.
HOLDOUT_ZDROJE: dict[str, dict] = {
    "PS2025_okrsky": dict(
        instituce="ČSÚ/volby.cz",
        presna_citace=["PS2025 okrskové výsledky", "Election_2025_CZ"],
        popis="Election_2025_CZ — okrskové výsledky voleb 2025, ground truth "
             "pro F_strana a politické dimenze"),
    "CVVM_casove_rady": dict(
        instituce="CVVM",
        presna_citace=[],  # zadna konkretni vlna jeste neni "spotrebovana"
        popis="CVVM dlouhodobé řady důvěry institucím/spokojenosti — ground "
             "truth pro FUTURE vlny, ne pro vlny uz pouzite ke kalibraci "
             "(viz KALIBRACNI_ZDROJE_POUZITE — 9 dimenzi cerpa z konkretnich "
             "vln CVVM 2025/2026 a to je v poradku, pokud validace cili na "
             "JINOU vlnu nez kalibrace)"),
    "Novotny_diplomka_bloky": dict(
        instituce="Novotný (diplomová práce)",
        presna_citace=["volební přesuny 2021→2025", "bloky Česko A/B"],
        popis="Volební přesuny 2021->2025, bloky Česko A/B — ground truth "
             "pro politické chování a polarizaci"),
    "trendy_ceska_2019": dict(
        instituce="Kantar CZ",
        presna_citace=["trendy_ceska_casova_rada.csv"],
        popis="Měsíční volební preference 2019, ground truth pro validaci "
             "trendu"),
}

# Zdroje POUZITE ke kalibraci (vyplnovat rucne pri pridani nove dimenze do
# dispozice.py — jednoducha, ale funkcni pojistka proti nechtenemu prekryvu).
KALIBRACNI_ZDROJE_POUZITE: set[str] = {
    "ČSÚ SILC 2025", "ČSÚ 2025", "ČSÚ/CBCB 2025", "CVVM 3–4/2026",
    "YouGov Shopper 2025", "Nielsen", "ČSÚ volby 2025", "CVVM 6/2025",
    "CVVM 8/2025", "Eurostat LFS 2021", "ČSÚ ICT v podnicích 2024",
    "ČSÚ VŠIT 2025", "ČSÚ Životní podmínky 2022", "FEDIAF 2026",
    "SZÚ EHES 2019", "SZÚ NAUTA 2025", "OECD PIAAC 2023 CZ mikrodata",
    "CSES Modul 5 ČR mikrodata", "JRC EU Loneliness Survey 2022",
    "QoG EQI 2024 ČR mikrodata", "ISSP Rodina a zdraví 2022 ČR mikrodata",
    "NÚDZ CAPI 2022 ČR mikrodata", "HFCS 2023 ČR", "CSDA Rule of Law ČR 2024",
    "ČSÚ SLDB2021", "STEM TRENDY 6/2026", "MF ČR 2025", "Současná česká rodina 2020",
    "ČS�ú VŠCR 2024", "Česká spořitelna/NMS 2023", "CVVM 2016", "CVVM podzim 2023",
}

# Instituce, ktere se objevuji na obou stranach (kalibrace i holdout) — NENI
# to chyba, je potreba jen u kazde nove pridavane dimenze rucne overit, ze
# jde o jinou vlnu/metriku nez ta, kterou pozdeji pouzijeme k validaci.
_INSTITUCE_HOLDOUT = {v["instituce"] for v in HOLDOUT_ZDROJE.values()}


def zkontroluj_pred_kalibraci(popis_zdroje: str) -> str | None:
    """Vrati "REVIEW: ..." (jen upozorneni) nebo None (cisto). Vyhodi
    ValueError jen pri tvrde shode (presna_citace).

    FAIL (vyjimka): presna_citace z holdout zdroje se doslova objevuje
    v popisu — to uz je stejne cislo pouzite dvakrat.
    REVIEW (jen navratova hodnota, zadna vyjimka): shoduje se instituce
    (napr. CVVM), ale ne presna citace — neni to automaticky chyba
    (instituce vydava desitky nezavislych vln rocne), ale vyzaduje to
    lidske overeni, ze jde o jinou vlnu/metriku nez pozdejsi holdout cil.
    """
    nizky = popis_zdroje.lower()
    for klic, d in HOLDOUT_ZDROJE.items():
        for citace in d["presna_citace"]:
            if citace.lower() in nizky:
                raise ValueError(
                    f"FAIL: zdroj '{popis_zdroje}' doslova obsahuje presnou "
                    f"citaci '{citace}' vyhrazenou pro holdout ('{klic}': "
                    f"{d['popis']}). Stejne cislo pouzite ke kalibraci "
                    f"i k validaci — vyhod ho z jedne strany."
                )
        if d["instituce"].lower() in nizky:
            return (f"REVIEW: zdroj '{popis_zdroje}' je od instituce "
                   f"'{d['instituce']}', ktera je i zdrojem holdout dat "
                   f"('{klic}'). Over rucne, ze jde o jinou vlnu/otazku, "
                   f"ne o to same cislo pouzite dvakrat.")
    return None


def zkontroluj_cely_slovnik(dimenze: dict) -> dict[str, list[str]]:
    """Projede cely DIMENZE slovnik z dispozice.py.

    Vraci {"fail": [...], "review": [...]}. FAIL musi byt vzdy prazdny seznam
    pred jakymkoli ostrym behem. REVIEW je normalni a ocekavany — jen rika,
    ktere dimenze sdileji instituci s holdout zdrojem a stoji za rucni
    kontrolu pri pristi aktualizaci dat.

    Pouziti: python -c "from dispozice import DIMENZE; from holdout_registry
    import zkontroluj_cely_slovnik; print(zkontroluj_cely_slovnik(DIMENZE))"
    """
    vysledek: dict[str, list[str]] = {"fail": [], "review": []}
    for jmeno, d in dimenze.items():
        try:
            r = zkontroluj_pred_kalibraci(d.get("zdroj", ""))
            if r:
                vysledek["review"].append(f"{jmeno}: {r}")
        except ValueError as e:
            vysledek["fail"].append(f"{jmeno}: {e}")
    return vysledek


def assert_holdout_clean() -> dict[str, list[str]]:
    """Hard gate pred buildem nebo ostrym behom.

    Presna shoda s holdout zdrojem je build-breaking. Institucni prekryv
    zustava REVIEW, protoze jina vlna teze instituce muze byt legitimni.
    """
    from dispozice import DIMENZE
    vysledek = zkontroluj_cely_slovnik(DIMENZE)
    if vysledek["fail"]:
        raise RuntimeError("HOLDOUT LEAKAGE:\n" + "\n".join(vysledek["fail"]))
    return vysledek
