# The business-decision study: methodology, version 4

The methodology PDF of the report-2 MVP (`../BRIEF-mvp-r2.md`, session F): how AIA takes a client's decision from
*Zadání* to a report in which every number carries its source and its grade, written bottom up from the ChemVitro
exemplar (`../exemplar/ChemVitro_2_model-lokality_nigel.pdf`, 44 pages, 5 Nov 2026).

| | |
|---|---|
| Version | 4, 9 November 2026, working version. Replaces version 3 (37 pages, 8 Nov 2026, kept beside it as `AIA_business-decision-study_methodology_v3.pdf`); version 2 (36 pages, 5 Nov 2026) recorded the methodology review R1–R10 and is not in the repository |
| PDF | `AIA_business-decision-study_methodology_v4.pdf`, A4, 43 pages |
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
all in the same seven parts: what goes in, what comes out, checks, how the exemplar did it, in AIA today, new,
ChemVitro acceptance; chapter 11 built vs designed and what is not in this release; chapter 12 the seven business
perspectives as a disjoint cost partition, one scoring structure for every option, and the two maps; chapter 13
grades with lineage and validation apart, sources, the provisional state and the release gate (R9, adopted); chapter
14 governance, the owner's decisions of 9 November, oracle-first acceptance and the review's evidence; appendices:
glossary, the exemplar in numbers, the board index.

## What changed in version 4

An external review of 9 November (ChatGPT, on the full MVP package) and the owner's decisions on it the same day.
The two weighting families are replaced by a partition: every cash-flow line to one leaf under one perspective, one
value function and one weight vector for all sites, NPV beside; the owner's 0,20 · 0,50 · 0,30 is admitted. Seven
contract defaults are the baseline for the methodologist: cost basis, parameter manifest, rule freeze, endpoint
semantics, convergence by doubling under repeated-look bounds (0,797 against 0,80 on 20 000 draws is unresolved),
enquiry updating, release eligibility apart from document approval (R9 adopted). Acceptance is an independent oracle
first (O-CF, O-INFO, O-CHEM), the answer key second. Grades print origin or method; lineage, uncertainty and
validation travel separately. Counts come from the manifest (T9: 67 rows). Open after version 4: R2-Q02 (the
comparables' cost basis) and R2-Q04 (empty perspectives).

## Conventions

English prose; Czech on-screen and report terms in italics; files, modules and plan chunks in `code`. Every ChemVitro
number is the exemplar's or the case pack's. "The review" is ADR 0046 § The methodology review (R1–R10, K1–K6);
"the answer key" is `prototypes/case-chemvitro/ANSWER-KEY.md` on branch `chore/case-chemvitro`.

## Agreement with the scope

Version 4 is written to the owner's decisions of 9 November; `MVP-SCOPE.md` version 2 follows them too. Where the
scope on `develop` still reads as version 1 (the two families, the ±0,5 pp stopping rule, the answer key as the only
test), this document is ahead of it until that revision lands. Board MV9 and the counts on MV0, MV4 and MV5 predate
version 4 and are corrected at the next canvas version.

## Folding in the other sessions

Sessions A, B, C and E landed on 8 Nov and are folded in (appendix C says which board each changed); D (the maps,
MV3, MV9, SI1–SI4) landed last and is folded in; the board index names every board's file and state. When a branch lands, the chapters that cite
its boards are aligned to it and the PDF is rebuilt and checked page by page before the push.
