# The business-decision study: methodology, version 5

How AIA takes a client's decision from *Zadání* to a report in which every number carries its source and its grade.
The method is described generically: no case, no case appendix, no worked example. Its numbers are rules, clearly
illustrative values, or the toy oracle fixtures of chapter 14.

| | |
|---|---|
| Version | 5, 9 November 2026, working version. Replaces version 4 (case-based, same date): every case reference is removed, and the owner's map decisions of the same day are applied (two map types, five configurations, the respondent map out) |
| PDF | `AIA_business-decision-study_methodology_v5.pdf`, A4, 45 pages |
| Sources | one HTML fragment per chapter, `00-cover.html` … `16-appendices.html`, in reading order; `style.css`; `build.js` |
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

Cover and *What this is*; chapter 1 the spine; chapter 2 the analytical contract (seven defaults, two release states);
chapters 3–10 one step each (*Zadání · Data · Rešerše · Předpoklady · Model · Výsledky · Sociomapa · Osnova a Zpráva*),
all in the same six parts: what goes in, what comes out, checks, in AIA today, new, acceptance (chapter 9 holds the two
map types); chapter 11 built vs designed and what is not in this release; chapter 12 the business perspectives as a disjoint cost partition, one
scoring structure for every option, and the weight settings; chapter 13 grades with lineage, uncertainty and validation
apart, sources, the provisional state and the release gate; chapter 14 governance, the owner's decisions of
9 November, oracle-first acceptance and the review's evidence; appendix A, the glossary.

## Conventions

English prose; Czech on-screen and report terms in italics; files, modules and plan chunks in `code`. Plan chunk
ids appear only in the *New* parts and the built-vs-designed table. Acceptance is described generically: the oracle
fixtures first, then a frozen test case with planted errors, then the independent review.

## Agreement with the scope

Version 5 is written to the owner's decisions of 9 November, as `MVP-SCOPE.md` version 2 is. Where the scope on
`develop` still reads as version 1, this document is ahead of it until that revision lands.
