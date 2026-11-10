# Průzkum zákazníků Velis, říjen 2026: dotazník a kódy

Fiktivní průzkum pro případovou studii AIA. 800 zákazníků, kteří nakoupili v roce 2025, online, 12.–26. 10. 2026.
Soubor: `pruzkum_zakazniku_2026.csv` (oddělovač `;`, UTF-8). Prázdná buňka = otázka bez odpovědi, nikdy ne 0.

## Profil (z CRM, ne z dotazníku)

| Sloupec | Význam | Hodnoty |
|---|---|---|
| `id_respondenta` | pseudonymní kód respondenta | R0001–R0800 |
| `vek` | věková skupina | 18–24, 25–34, 35–44, 45–54, 55+ |
| `kraj` | kraj bydliště | 14 krajů ČR |
| `velke_mesto` | bydlí v Praze, Brně, Ostravě nebo Plzni | ano / ne |
| `cetnost_nakupu` | objednávky v roce 2025 | 1, 2–3, 4+ |

## Otázka 1: jak lákavé jsou tyto způsoby doručení

> Jak lákavý by pro vás byl tento způsob doručení při vašem příštím nákupu u Velis?
> Ohodnoťte na škále 1–10, kde **1 = vůbec nelákavý** a **10 = velmi lákavý**.

| Sloupec | Způsob doručení, jak ho respondent viděl |
|---|---|
| `O1_atraktivita` | Doručení druhý pracovní den po objednání |
| `O2_atraktivita` | Doručení do 2 pracovních dnů |
| `O3_atraktivita` | Doručení do 3 pracovních dnů |
| `O4_atraktivita` | Expresní doručení ve velkých městech: objednáte dnes, máte zítra |
| `O5_atraktivita` | Doprava za 79 Kč (dnešní cena) |
| `O6_atraktivita` | Doprava za 59 Kč, ale doručení o den delší než dnes |
| `O7_atraktivita` | Vyzvednutí ve výdejním boxu nebo na výdejním místě |
| `O8_atraktivita` | Doprava zdarma při nákupu nad 1 500 Kč |

Pořadí způsobů se respondentům náhodně střídalo.

## Otázka 2: zpoždění

> Představte si, že vaše objednávka přijde o jeden den později, než jsme slíbili.
> Objednal(a) byste u Velis znovu?

Sloupec `q_zpozdeni_objednal_znovu_1_5`: **1 = určitě ne**, 2 = spíše ne, 3 = nevím, 4 = spíše ano,
**5 = určitě ano**.

## Otázka 3: příplatek za doručení druhý den

> Kolik byste byl(a) ochoten/ochotna připlatit, aby objednávka přišla druhý pracovní den místo do dvou dnů?
> Napište částku v Kč; 0 znamená nic.

Sloupec `q_priplatek_za_druhy_den_kc`: celé Kč, 0 a více.
