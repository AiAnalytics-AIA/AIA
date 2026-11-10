# Průzkum pracovníků chemického průmyslu, říjen 2026: dotazník a kódy

Fiktivní průzkum pro případovou studii AIA. 300 pracovníků chemického průmyslu v Česku, Německu a Polsku, online panel personální agentury ChemStaff (fiktivní, Brno), 5.–23. 10. 2026. Odpovídali v češtině, němčině nebo polštině.
Soubor: `pruzkum_pracovniku_2026.csv` (oddělovač `;`, UTF-8). Prázdná buňka = otázka bez odpovědi, nikdy ne 0.

## Profil

| Sloupec | Význam | Hodnoty |
|---|---|---|
| `id_respondenta` | pseudonymní kód | W001–W300 |
| `zeme` | země bydliště | Česko, Německo, Polsko |
| `region` | kraj / Land / województwo | |
| `vek` | věk v letech | |
| `profese` | současná práce | operátor, technik, laborant, údržba |
| `praxe_let` | roky praxe v chemii | |

## Otázka 1: lákavost práce v novém závodě

> Firma staví nový chemický závod. Jak lákavé by pro vás bylo v něm pracovat, kdyby stál v této lokalitě?
> Ohodnoťte na škále 1–10, kde **1 = vůbec nelákavé** a **10 = velmi lákavé**.

Respondent viděl název obce, region a vzdálenost od svého bydliště. Pořadí lokalit se střídalo náhodně.

| Sloupec | Lokalita |
|---|---|
| `CZ1_atraktivita` | Vrbice (Ústecký kraj) |
| `CZ2_atraktivita` | Lipová (Olomoucký kraj) |
| `CZ3_atraktivita` | Kamenec (Moravskoslezský kraj) |
| `DE1_atraktivita` | Wendelstedt (Sachsen-Anhalt) |
| `DE2_atraktivita` | Lindenau (Sachsen) |
| `DE3_atraktivita` | Eschfeld (Bayern) |
| `PL1_atraktivita` | Odrzyca (Opolskie) |
| `PL2_atraktivita` | Bory (Śląskie) |

## Otázka 2: přestěhování

> Přestěhoval(a) byste se kvůli takové práci?

`ochota_prestehovat_1_5`: **1 = určitě ne**, 2 = spíše ne, 3 = nevím, 4 = spíše ano, **5 = určitě ano**.

## Otázka 3: dojíždění

> Kolik kilometrů jste ochoten/ochotna denně dojíždět do práce (jedním směrem)?

`dojizdka_max_km`: celé km.

## Otázka 4: mzda

> Jakou hrubou měsíční mzdu byste za takovou práci očekával(a)?

`ocekavana_hruba_mzda` v měně ze sloupce `mena` (CZK, EUR, PLN).
