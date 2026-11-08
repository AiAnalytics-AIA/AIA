# Rozsah MVP: vizuální vydání v češtině

The MVP scope (`../MVP-SCOPE.md`, session A of `../BRIEF-mvp-r2.md`) as a Czech, figure-led PDF for the product owner
and the methodology owner. The markdown stays the engineering record (code anchors `file:line @ b28ce091`, plan
chunks); this folder is its print. Nothing here says anything the markdown does not.

| | |
|---|---|
| Source | `../MVP-SCOPE.md` at revision `d0c361b1d` (branch `chore/obchodni-model-method-v2`); the cover names it |
| PDF | `AIA_MVP-scope_cs.pdf`, A4, 24 pages, 0 browser errors at build |
| Chapters | `00-cover.html` … `16-otevrena.html`, one HTML fragment each, in reading order: cover; část 1 Rozhodnutí; část 2 the eight-step matrix and one page per step (Zadání, Data, Rešerše, Předpoklady, Model, Výsledky, Sociomapa, Osnova a Zpráva); část 3 Perspektivy (the seven perspectives and the 20 components); část 4 Mapa scénářů vah (the two families, the fan, the ten lines, the engine renders); část 5 Odloženo; část 6 Přijetí (A1–A6, K1–K6); část 7 Vlny; část 8 Otevřená rozhodnutí |
| Figures | hand-written inline SVG in the methodology's colours (`--accent`, `--coral`, `--slate`, `--force` and their washes); the three engine renders of část 4 are `../assets/2e28790a9081a1eb434367f29a82c543.jpg`, `../assets/914872843eaa61eae988d234ac0e095f.jpg`, `../assets/bce0402524962925fab15e08b0684a25.jpg`, the canvas's own images of board MV9. The contour maps of část 2.7 and the fan of část 4 are schematic and say so |
| Styles | `../methodology/style.css` and `../methodology/fonts/` by relative link (nothing copied); `scope.css` adds only the figures' and cards' rules |
| Build | `build.js`, modelled on `../methodology/build.js` |

## Build

```
NODE_PATH=$(npm root -g) node build.js          # the PDF; two passes so the contents carry page numbers (pdftotext)
NODE_PATH=$(npm root -g) node build.js --png    # and every page as PNG under ../../../tmp/scope-pages/ (pdftoppm)
NODE_PATH=$(npm root -g) node build.js --html   # and the assembled document as scope.html, for a browser
```

Needs Node 18+, Playwright with its Chromium, and poppler (`pdftotext`, `pdfinfo`, `pdftoppm`). Nothing is fetched
from the network. The build fails on any browser error or failed request.

## Conventions

Czech throughout: decimal comma, a non-breaking space before units and `%`, „uvozovky“. Plan chunks and files in
`code`; a new chunk (one that exists in no plan file yet) is a filled blue tile, an existing one a grey tile. Czech
terms follow the canvas boards (`../MV0Scope.dc.html`, `../Z0Flow.dc.html`, `../MV9ScenarioWeights.dc.html`,
`../KM12Schedule.dc.html`) and `../methodology/`. Every ChemVitro number is the exemplar's, as the scope cites it.
