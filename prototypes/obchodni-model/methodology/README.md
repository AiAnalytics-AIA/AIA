# The business-decision study: methodology, version 3

The methodology PDF of the report-2 MVP (`../BRIEF-mvp-r2.md`, session F): how AIA takes a client's decision from
*Zadání* to a report in which every number carries its source and its grade, written bottom up from the ChemVitro
exemplar (`../exemplar/ChemVitro_2_model-lokality_nigel.pdf`, 44 pages, 5 Nov 2026).

| | |
|---|---|
| Version | 3, 8 November 2026, working version. Version 2 (36 pages, 5 Nov 2026) recorded the methodology review R1–R10 and is not in the repository |
| PDF | `AIA_business-decision-study_methodology_v3.pdf`, A4, 35 pages |
| Sources | one HTML fragment per chapter, `00-cover.html` … `15-appendices.html`, in reading order; `style.css`; `build.js` |
| Fonts | `fonts/`: IBM Plex Sans, IBM Plex Mono and Source Serif 4, the report's own faces, copied unmodified from `packages/aia_core/src/aia_core/infrastructure/report_docx/fonts/` with their SIL OFL licences |

## Build

```
node build.js            # the PDF; two passes so the contents carry page numbers (pdftotext)
node build.js --png      # and every page as PNG under ../../../tmp/methodology-pages/ (pdftoppm), to check them
node build.js --html     # and the assembled document as methodology.html, for a browser
```

Needs Node 18+, Playwright with its Chromium, and poppler (`pdftotext`, `pdfinfo`, `pdftoppm`). Nothing is fetched
from the network. The build fails on any browser error or failed request. Tables repeat their header on a new page;
a heading never stands alone at a page foot (`break-after: avoid`).

## What is in it

Cover and *What this is*; chapter 1 the spine; chapters 2–9 one step each (*Zadání · Data · Rešerše · Předpoklady ·
Model · Výsledky · Sociomapa · Osnova a Zpráva*), all in the same seven parts: what goes in, what comes out, checks,
how the exemplar did it, in AIA today, new, ChemVitro acceptance; chapter 10 built vs designed; chapter 11 the seven
business perspectives, their components and the two maps (the futures map and the weighting-scenario map); chapter 12
grades, sources, the provisional state and the release gate (R9, proposed); chapter 13 governance; appendices: glossary,
the exemplar in numbers (T1, T4, T6, T7, T8 condensed), the board index.

## Conventions

English prose; Czech on-screen and report terms in italics; files, modules and plan chunks in `code`. Every ChemVitro
number is the exemplar's or the case pack's. "The review" is ADR 0046 § The methodology review (R1–R10, K1–K6);
"the answer key" is `prototypes/case-chemvitro/ANSWER-KEY.md` on branch `chore/case-chemvitro`.

## Folding in the other sessions

Sessions A–E change boards while this document is written (appendix C marks them "in revision"). When their branches
land, the chapters that cite those boards are aligned to them, chapter 11 to A's perspectives in `MVP-SCOPE.md` and
D's MV9 first, and the PDF is rebuilt and checked page by page before the push.
