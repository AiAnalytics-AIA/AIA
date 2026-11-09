# Rozsah MVP: studie pro obchodní rozhodnutí

The MVP scope as a ten-page Czech PDF for executives (version 4, 9 Nov 2026, with the owner's afternoon decisions). It follows the common structure of an
MVP definition: the problem and the user, the riskiest assumptions the MVP tests, the core workflow, what is in scope
with an acceptance criterion per item, what is out of scope and why, success and exit criteria (built versus
validated), the non-functional requirements, the stack, team and timeline, and the risks and open decisions. It
states scope, criteria and decisions; it names no case, site or person, and an illustrative number is labelled. The
engineering record stays `../MVP-SCOPE.md` (version 3: the steps with code anchors, the plan chunks, acceptance,
waves); this document carries none of its codes.

| | |
|---|---|
| Audience | executives deciding on the MVP; the product owner; the methodologist |
| Source | `../MVP-SCOPE.md` version 3 and the owner's decisions of 9 Nov; the stack from the repository's `CLAUDE.md` § Stack |
| PDF | `AIA_MVP-scope_cs.pdf`, A4, 10 pages, 0 browser errors at build |
| Pages | `00-cover` · `01-problem` (problem, user, reader, the job) · `02-hypotezy` (four assumptions, their evidence, what changes if refuted) · `03-prubeh` (eight steps, who does what) · `04-v-rozsahu` (in scope, acceptance criterion, existing or new) · `05-mimo-rozsah` (not in this release, why) · `06-kriteria` (three gates; built versus validated) · `07-nasazeni` (EU data, no training on client data, access, audit, reproducibility, cost limits) · `08-technologie-plan` (stack, team, five two-week steps, effort range) · `09-rizika` (risks with mitigation, the decisions taken, the one open decision on capacity, what the methodologist is asked for) |
| Targets | the tolerance of the control examples (0,001), the decision-maker test (two executives decide from a trial report), the study time (10 working days): adopted by the owner on 9 Nov (R2-Q18) |
| Styles | `../methodology/style.css` and `../methodology/fonts/` by relative link; `scope.css` adds the figures' and tables' rules (`body.exec`) |
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
criterion codes; no case or site names; terms are defined where they first appear. Earlier Czech editions (24, 29 and
10 pages) are in git history.
