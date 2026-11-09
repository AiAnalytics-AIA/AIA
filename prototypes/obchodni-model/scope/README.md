# Rozsah MVP: vydání pro vedení

The MVP scope as a ten-page Czech PDF for the executive who reads it, not for the team that builds it. One idea per
page, one figure per page, no plan or board codes, no file paths. The engineering record stays `../MVP-SCOPE.md`
(version 2: eight steps with code anchors, the chunk ids and their mapping, acceptance, waves); this document says
the same things in the executive's words and leaves out what only the team needs. Nothing here says anything the
markdown does not.

| | |
|---|---|
| Audience | the executive who approved report 2 of the ChemVitro case; the product owner; the methodologist |
| Source | `../MVP-SCOPE.md` version 2 (branch `chore/obchodni-model-scope-v2`) and the owner's decisions of 9 Nov; the stack from the repository's `CLAUDE.md` § Stack |
| PDF | `AIA_MVP-scope_cs.pdf`, A4, 10 pages, 0 browser errors at build |
| Pages | `00-cover` · `01-co-klient-dostane` (the report's anatomy) · `02-jak-studie-probiha` (eight steps, who does what) · `03-dnes-a-nove` (today / new) · `04-mapa-scenaru-vah` (the owner's question) · `05-jak-pozname` (three gates) · `06-plan` (ten weeks, five steps, the honest expectation) · `07-technologie` (the stack as layers, EU residency) · `08-co-se-rozhoduje` (two open items, three asks of the methodologist) · `09-slovnicek` (twelve terms) |
| Figures | hand-written inline SVG in the methodology's colours; schematic, with illustrative numbers where the real ones are not computed yet (the weighting ranking on page 5 says so) |
| Styles | `../methodology/style.css` and `../methodology/fonts/` by relative link; `scope.css` adds the figures' and the executive edition's rules (`body.exec`) |
| Build | `build.js`: one Playwright render, no contents page |

## Build

```
NODE_PATH=$(npm root -g) node build.js          # the PDF
NODE_PATH=$(npm root -g) node build.js --png    # and every page as PNG under ../../../tmp/scope-pages/ (pdftoppm)
NODE_PATH=$(npm root -g) node build.js --html   # and the assembled document as scope.html, for a browser
```

Needs Node 18+, Playwright with its Chromium, and poppler (`pdfinfo`, `pdftoppm`). Nothing is fetched from the
network. The build fails on any browser error or failed request.

## Conventions

Czech throughout: decimal comma, a non-breaking space before units and `%`, „uvozovky“. No chunk, board, plan or
criterion codes; a technical term appears once, defined in the glossary. Every ChemVitro number is the exemplar's or
the case pack's; a figure with illustrative numbers says so. The earlier, detailed Czech editions (versions 1 and 2,
24 and 29 pages) are in git history; the team's detail lives in `../MVP-SCOPE.md`.
