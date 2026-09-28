---
status: in-progress
chunks:
  - "[x] R0. This plan"
  - "[x] R1. Print tokens"
  - "[x] R2. Fonts and embedding"
  - "[x] R3. Document model"
  - "[ ] R4. Style sheet and furniture (started; paused 2026-09-27, see Handoff)"
  - "[ ] R5. Text and report components"
  - "[ ] R6. Tables"
  - "[ ] R7. Figures and evidence marks"
  - "[ ] R8. Templates"
  - "[ ] R9. Verification tooling"
  - "[ ] R10. Composition from analysis results (needs the agreed contract)"
  - "[ ] R11. The REPORT step"
---
# Plan: the report output stage — DOCX from the design system

**Status:** R0–R9 done (2026-09-27); R10–R11 planned, waiting on other contexts' contracts. See **Handoff** at the end. **Owner:** product-surface (A9).
**Realises:** chunk 10 "Deliverable" of [`design-system.md`](design-system.md).
**Brief:** [`docs/design/aia-design-system-brief.md`](../../docs/design/aia-design-system-brief.md) §4.9.
Anchors are against `develop` @ b3bd42f unless stated.

## What this is

The research ends in a document a client paid a consultancy for (brief `:500`).
The output is **always DOCX** (the user's instruction; `delivery.format` is
`docx` in `packages/aia_core/tests/conftest.py:247-249`). This plan builds the
report as a **system**: one typed document model, one set of components, one
style sheet generated from the design tokens, and templates that compose the
components. Nothing hand-formats a paragraph.

What exists today: nothing on the AIA side. `reports.generation` is NOT_STARTED
and blocks the MVP release (AC-11, `docs/migration/parity-matrix.json:2731-2765`).
The legacy product writes DOCX with python-docx defaults — Word's built-in styles,
Aptos 10.5 pt, no cover, no table of contents, no figures (its `maps=` argument is
accepted and ignored) (`legacy/npc-panel-18.6.6/app/client_report_v2.py:143-158`,
`final_client_report.py`, `workflow_report.py`). **Parity is on content — the
section set, the evidence and claim fields and the gates — not on appearance.**
The report DATA assembly is EXACT parity and the prose SEMANTIC
(`parity-matrix.json:2731-2765`).

## Rules the renderer obeys (not owned here — rendered faithfully)

| Rule | Source |
|---|---|
| A number reaches a report only as an admitted claim; the renderer **never originates a number**. Numbers it prints itself (a caption's n, a table's base) come from the claim's `EvidenceRow` (`effective_n`, `support`), never recomputed. | `ARCHITECTURE.md:163-168`, `domain/evidence/admission.py:121-142`, AC-13 |
| Suppressed cells are **removed, not greyed**, and the removal is stated. | `domain/evidence/support.py:1-8,157-183` |
| A client-facing estimate carries its interval; a value without one is not shown. | `admission.py:269-274`; legacy `report_html.py` |
| The disclosures a row carries (`SCOPE`, `MODELED_VALUE`, `HISTORICAL`) are printed. | `domain/evidence/claims.py:83-88,148-167` |
| The method status is written by code and printed on the page, plainly. | `domain/evidence/validation.py:68-75`; brief `:337-339` |
| An unknown evidence role renders `?`, never the strongest grade. | OI-9 |
| A Sociomap enters a client deliverable only through `require_client_facing`, which fails closed. | `domain/research_sociomap.py:51-73`; OI-17 |
| A client variant never shows internals (provider, model, QA). | legacy `tests/test_release_core.py:22` |
| What-if results are never printed as results without saying so. | brief `:323-324` |

## Architecture

```
apps/web/src/design/tokens.json         the ONE source; gains a `print` section
  └─ scripts/build-tokens.mjs           also emits → aia_core/domain/report/print_tokens.py (drift-checked)

packages/aia_core/src/aia_core/
  domain/report/                        PURE (stdlib + Pydantic)
    print_tokens.py                     GENERATED: colours, type scale in pt, page geometry
    model.py                            the document model: metadata + blocks
    blocks.py                           every component, as data
    numbers.py                          Czech number/percent/interval/n formatting
    evidence.py                         evidence grades for print (OI-9 fallback "?")
    templates.py                        client / final / internal / documentation recipes
    validation.py                       what a document must satisfy before it renders
    copy.py                             Czech report vocabulary (Obsah, Graf, Zdroj…)
  infrastructure/report_docx/           I/O — python-docx, matplotlib, lazy imports
    renderer.py                         DocxRenderer implements domain ReportRenderer protocol
    styles.py                           styles.xml from print tokens; theme fonts stripped
    fields.py                           TOC, PAGE, NUMPAGES, SEQ, PAGEREF, bookmarks
    sections.py                         cover / front matter / body / appendix sections
    blocks/                             one renderer per block kind
    charts.py                           chart specs → SVG + PNG fallback, from tokens
    marks.py                            evidence marks as vector images
    fonts/                              upstream TTFs + licences + SHA256SUMS
    embed.py                            ECMA-376 §17.8.1 obfuscated font embedding
tools/report_preview.py                 manual: DOCX → PDF → PNG via LibreOffice
```

The report depends on nothing above the domain for its rules. The renderer is an
infrastructure adapter behind a protocol (`ARCHITECTURE.md:220-222`), with
python-docx and matplotlib as a declared optional extra `aia-core[report]`,
imported lazily (`AGENTS.md`, optional dependencies).

## The components — the full inventory

**Document furniture**
- Page: A4 portrait; a landscape section for wide tables and figures.
- Sections: cover (no running heads), front matter (roman page numbers), body (arabic), appendix (Příloha A…), colophon.
- Running heads: report title / chapter; footer: classification, page "X z Y".
- Document properties: title, subject, language `cs-CZ`, custom `study_id`, report revision, content fingerprint. No internals in the client variant.
- Fonts embedded (Source Serif 4, IBM Plex Sans, IBM Plex Mono), so the document looks the same on any machine.

**Front matter**
- Cover: report kind, title, subtitle, client, study, date, revision, classification, method-status stamp, the AIA cover field (`public/skin/brand/report-cover-field.svg`).
- Document control: revision history, sign-off (reviewer, date), distribution, identifiers (internal variant: run ids, fingerprints, population version).
- Table of contents (levels 1–3), list of figures, list of tables, abbreviations.

**Body text**
- Headings, numbered 1 / 1.1 / 1.1.1; appendix headings lettered.
- Paragraph, lede (the headline answer), bullet and numbered lists (two levels).
- Inline: emphasis, strong, Czech numbers with NBSP, footnote reference, citation, cross-reference ("viz graf 3"), inline evidence mark, hyperlink.

**Report components**
- Decision answer ("Odpověď pro rozhodnutí") with its evidence grade.
- Key finding (headline, finding, evidence, meaning, confidence, grade).
- Research-question answer (question, answer, evidence strength).
- Recommendation (action, why, priority).
- Callouts: method status, limitation, what-if / provisional, note.
- Verbatim quote, labelled synthetic.
- KPI row (stat tiles), each with n and grade.

**Tables**
- The data table: numbers right-aligned in Plex Sans tabular, units in the header, header row repeats across pages, base n, and a stated note for suppressed rows.
- Variants: crosstab with column n, research questions, sample support (raw n / Kish n / donors / effective n / support), triangulation, evidence appendix, data dictionary.

**Figures**
- Types: horizontal bar, grouped bar, stacked 100 %, diverging (Likert), line (trend), dot plot with intervals, heatmap table, small multiples, and the Sociomap (gated).
- Every figure has a caption ("Graf N — …" with n and grade), source line, notes and alt text.
- Figures are vector SVG with a PNG fallback. Modelled series are hatched, and grades are marked.

**Evidence**
- Inline marks and a persistent key.
- The evidence appendix: one row per cited claim, from `EvidenceRow.canonical()`.
- The method-status block.

**Back matter**
- Methodology, limitations, questionnaire, glossary, sources, audit (internal only), colophon.

## Chunks

| # | Chunk | Proves |
|---|---|---|
| R0 | This plan. | — |
| R1 | **Print tokens.** A `print` section in `tokens.json` (page, margins, type scale in pt). The generator emits `domain/report/print_tokens.py`, and `tokens:check` covers it. | drift check; tests read the generated module |
| R2 | **Fonts.** Vendor the upstream TTFs, unmodified, with licences and SHA256SUMS. Obfuscated embedding per ECMA-376 §17.8.1. | round-trip test de-obfuscates to the original bytes; LibreOffice renders them with no fonts installed |
| R3 | **Document model.** Blocks, metadata, Czech number formatting, print evidence grades, validation. Pure. | unit tests: zero ≠ null ≠ suppressed; unknown grade is `?`; a figure without alt text or a source is refused |
| R4 | **Style sheet and furniture.** Every style from tokens, theme fonts stripped, numbering, sections, running heads, fields, properties. | structural tests on the package XML |
| R5 | **Text and report components.** Paragraphs, lists, callouts, findings, recommendations, footnotes, cross-refs. | structural tests; no direct formatting outside named styles |
| R6 | **Tables.** Every table variant; suppression notes; repeating headers; landscape. | structural tests |
| R7 | **Figures and evidence marks.** Chart library from the viz tokens (validated palette, fixed order, direct labels, one axis); SVG + PNG; Sociomap behind `require_client_facing`. | tests plus rendered previews, including greyscale |
| R8 | **Templates.** Client report (the legacy v2 section set, extended to the demo's ~50-page structure), final client report, internal report, study documentation. Cover, control page, TOC, lists, appendices. Client-variant hiding rules. | a sample report per template renders; the client variant carries no internal strings |
| R9 | **Verification tooling.** `tools/report_preview.py` (LibreOffice → PDF → PNG), greyscale and +35 % Czech stress, and a DOCX lint in CI. | the tools run; evidence screenshots |
| R10 | **Composition from analysis results.** `application/report.py` builds a document from `AnalysisModuleResult`s and provenance. **Coordinated with analysis-governance.** | integration tests on stored results |
| R11 | **The REPORT step.** An executor renders and stores `final_docx` with provenance through `ArtifactRepository`; the web results step lists it and offers download. **Coordinated with platform-runtime.** | executor test; download gated by `EXPORT_DELIVERABLE` |

R1–R9 are product-surface's and land here. R10–R11 depend on other contexts'
contracts and start when those are agreed.

## Decisions

| # | Question | Recommendation |
|---|---|---|
| R-D1 | Figures as vector images, or native editable Word charts? | **Vector images now** (SVG with PNG fallback). They are exact to the design system and render identically everywhere. Native charts are a later, separate component if clients need to edit them. |
| R-D2 | Embed the fonts (about 2 MB per report) or rely on installed fonts? | **Embed.** A report opened on a client's machine without Plex or Source Serif would otherwise fall back to Calibri or Times, and the design system would be lost. |
| R-D3 | Does the client's logo appear on the cover? | The design system keeps client colour to scope chrome. **A client logo is allowed on the cover only, from typed `report_branding`**; never in running heads or figures. |
| R-D4 | How are the 22 `EvidenceStatus` values mapped to the five print grades? | **analysis-governance's decision (OI-9).** Until it is made, only the four documented roles grade, and everything else prints `?`. |

## Chunk log

- **R1 — print tokens.** `tokens.json` gains a `print` section: A4 geometry, the
  weight → Word-font map (`faces`) and the print palette. The Deliverable group
  gains print metrics in points on its 7 styles and 10 print-only styles
  (subtitle, kicker, h3, meta, running, table, table-head, kpi, quote, mono), 17
  in all. There is a new `doc-wash` colour for callout grounds.
  `build-tokens.mjs` emits `domain/report/print_tokens.py` (stdlib-only
  dataclasses), and `tokens:check` fails on drift.
  Tests: `test_report_print_tokens.py`, 7 tests. They check that every style
  resolves to an embeddable font, the 7.5 pt legibility floor, headings in real
  semibold faces rather than synthetic bold, A4, and that the module is
  stdlib-only.
  `check:design` now runs 170 contrast checks with 0 failures; there are 3 new
  `doc-wash` pairs.
  **Weight 600 maps to its own face** ("Source Serif 4 Semibold", "IBM Plex Sans
  SmBld"), because Word has no weight axis and the fonts' Reserved Font Names
  forbid renaming a face into another family.

- **R2 — fonts and embedding.** Twelve upstream TTFs are vendored unmodified in
  `infrastructure/report_docx/fonts/`, 2.6 MB:
  - Source Serif 4: Regular, It, Bold, BoldIt, Semibold, Display Semibold.
  - IBM Plex Sans: Regular, Italic, Bold, BoldItalic, SemiBold.
  - IBM Plex Mono: Regular.

  Their provenance, tarball hashes and licences are in the fonts' README, and
  every file is pinned in SHA256SUMS. `embed.py` implements ECMA-376 §17.8.1
  obfuscation with keys derived from each file's SHA-256, so the output is
  byte-reproducible. It inserts `w:embedTrueTypeFonts` in schema order.

  python-docx is the new `report` extra, installed by `make deps` and every CI
  job that collects the test tree. The security audit covers it, and
  `types-lxml` is in dev. `layer_check` gains "domain imports no document, XML
  or plotting library", now 59 rules.

  Tests: `test_report_fonts.py`, 16 tests. They cover checksums, that the
  vendored set equals `print_tokens.FONTS`, and that each file's family name
  equals the Word name with `fsType` 0 and TrueType outlines. They also cover
  the standard's key order, and that the embedded parts de-obfuscate back to the
  vendored bytes.

  The prototype rendered them in LibreOffice with no fonts installed. The
  automated render check is R9.

- **R3 — the document model.** `domain/report/`:

  - `model.py` holds the document, metadata, sections and 15 block kinds, plus
    inline text, value, footnote, cross-reference and link.
  - `evidence.py` holds `EvidenceLedger` and print grades.
  - `validation.py` holds 22 problem codes. `validate` lists every one;
    `require_valid` raises.
  - `numbers.py` does Czech formatting.
  - `copy.py` holds the report's Czech vocabulary.

  **No block carries a number.** A value is an `evidence_ref` that resolves in a
  ledger built only from `AdmittedClaim`s, for one surface. An internal claim in
  a client ledger is refused, not filtered.

  A suppressed ref may appear in a table or chart, where it is removed and
  counted. It is refused in prose, a KPI, a callout or a caption's base.

  The validator enforces, for client kinds:

  - client-facing claims only;
  - an interval on every estimate;
  - the method status as an on-page callout;
  - no audit block, no identifiers, and no internal term such as "provider" or
    "quality gate" (legacy `test_release_core.py:22`);
  - Sociomaps only when `CLIENT_FACING`.

  It also enforces, for every kind:

  - complete figures and tables (title, source and alt text);
  - one unit per chart, at most 6 series, and hatching that matches the grade;
  - unique ids and resolved cross-references;
  - no skipped heading level, and lists at most two deep.

  **Grades changed during the chunk.** The first rule ("measured only if joint")
  would have printed every single-field measured share as `?`. Whether a
  measured field is measured or calibrated depends on its `EvidenceStatus`, so
  grades now come from `EvidenceLedger.field_grades`, the OI-9 mapping, supplied
  as data. The rules: MODELED prints as modelled; several non-joint fields never
  print as measured; otherwise the weakest field grade; an ungraded field prints
  `?`. OI-9 is updated.

  Tests: `test_report_model.py`, 30 tests. They cover formatting (NBSP grouping,
  decimal comma, true minus, en-dash intervals, effective n rounded down, the
  genitive month, and refusing unrounded values), grades, the ledger, and every
  validation rule. The shared `report_ledger` fixture admits a study's evidence
  through the real gate.

- **R4 — style sheet and furniture (started, not finished).** Landed, tested and
  unwired:
  - `domain/report/outline.py` computes every printed number: chapters 1..n,
    appendices A..Z..AA, headings 1.1 and 1.1.1, figures and tables numbered
    continuously, and the cross-reference labels ("graf 3", "oddíl 2.1").
  - `infrastructure/report_docx/styles.py` holds the whole Word style sheet
    built from `print_tokens` (`S` names every style), the data-table style
    (rules, not boxes), and theme fonts stripped from every style in the sheet.
  - `ooxml.py` holds fields with cached results (TOC, PAGE, STYLEREF, SEQ),
    bookmarks, internal hyperlinks, and schema-ordered insertion.
  - `numbering.py` holds bullets and numbered lists that restart per list.
  - `footnotes.py` writes the footnotes part python-docx lacks, with the
    separators and `footnotePr`.

  Tests: `test_report_docx_styles.py`, 4 tests. They found that Word's
  untouched default styles (Heading 4–9) also carry theme fonts, so the
  stripping is now sheet-wide.

- **R4 — finished (the renderer).** `infrastructure/report_docx/renderer.py`:
  `DocxRenderer.render(doc) -> bytes` runs `require_valid`, then
  `build_outline`, writes the sections and finishes the package. `layout.py`:
  - cover (no header; a draft's cover footer carries only the draft notice),
    front matter paged `lowerRoman` from i, body `decimal` from 1, and an
    appendix section that continues the numbering with its own
    `STYLEREF "AIA Appendix Heading"` header;
  - body header "title ⇥ `STYLEREF "Heading 1"`", footer
    "classification ⇥ `PAGE`"; **with no approvals every footer starts
    "KONCEPT — NESCHVÁLENO"**;
  - document control (meta table, approvals or the draft notice, history;
    study id and identifiers only for internal kinds), then Obsah, Seznam grafů
    and Seznam tabulek as TOC fields pre-filled with the outline's entries (a
    hyperlink to the bookmark plus a `PAGEREF`);
  - core properties (cs-CZ, dated by `issued_on`), the 12 faces embedded,
    `w:mirrorMargins` and `w:updateFields` in settings order, rsids dropped;
  - **deterministic bytes**: the zip is rewritten with fixed timestamps.

  `blocks.py` renders headings (number in `AIA Heading Number`, bookmarked),
  paragraphs, page breaks and callouts (the METHOD callout always prints
  `copy.method_status_text`). `lint.py` is the DOCX lint (no direct
  formatting; settings and sectPr in schema order). Validation now also refuses
  a method status with no printed wording, and `cited_refs(doc)` lists the refs
  the evidence appendix prints. `domain/report/rendering.py` is the
  `ReportRenderer` protocol.

  Tests: `test_report_docx_render.py`, 14 tests. The LibreOffice render showed
  `w:ptab` is ignored (header tab moved into the style) and that a TOC's cached
  page numbers stay empty until Word updates fields (AGENTS.md § DOCX).

- **R5 — text and report components.** `blocks.py` renders every text block:
  paragraphs and ledes; inline values (`value_text`: exactly `row.value` at
  `row.decimals`, and **in a client report an estimate always prints its
  interval**, whatever the block asked); the grade mark after every value, and
  "orientační" for INDICATIVE support; bullet and numbered lists (two levels,
  each ordered list restarting); quotes in Czech quotation marks with
  "syntetický respondent"; callouts with the marks of their refs; key findings
  and recommendations with the legacy labels; KPI tiles (a borderless
  `AIA KPI Table`, the interval and `n` from the row under each value); the
  evidence key (all five grades); the evidence appendix (one row per
  `cited_refs`, suppressed refs never listed, disclosures as short labels
  explained under the table); the audit block. `marks.py` draws one glyph per
  grade in `evidence-mark` ink (disc, ring+dot, hatched ring, half disc) with
  matplotlib, embedded once as SVG with a PNG fallback (`images.py`); **the
  unknown grade has no glyph — it prints `?`**. matplotlib joined the `report`
  extra. Tests: `test_report_docx_blocks.py`, 8 tests. The LibreOffice render
  found that inline pictures get ~3 mm of padding unless `distL/R` are 0
  (AGENTS.md § DOCX).

- **R6 — tables.** `tables.py`: the caption above ("Tabulka N — title
  (n = …; grade)") with the number as `SEQ Tabulka` (the list of tables collects
  it) and bookmarked for cross-references; n from `base_ref`'s effective n,
  **rounded down**; the grade in the caption when every number shares one,
  otherwise a mark per cell. `AIA Data Table`, full width, the header row
  repeating and unsplittable, the unit in the header (never in each cell),
  numbers right-aligned with the interval beneath. **A row citing a suppressed
  ref is removed**, and the source line states "Potlačeno pro nedostatečnou
  efektivní velikost vzorku: N." INDICATIVE cells carry a dagger explained
  under the table; an empty cell prints its reason ("chybí"). A landscape
  table gets its own section, with `AIA Header/Footer Landscape` styles so the
  running head right-aligns at that width; the portrait section after it sets
  its heads again. Block dispatch moved to `dispatch.py` (tables import
  blocks). Tests: `test_report_docx_tables.py`, 5 tests.

- **R7 — figures and marks.** `charts.py` draws all seven `ChartKind`s with
  matplotlib from the ledger: values are `row.value`, labels
  `numbers.with_unit` of the same row. `viz-cat-1..6` in fixed order, the
  diverging ramp symmetric about its grey for Likert, the sequential ramp in
  7 bins for heatmaps. One axis, hairline grid, direct labels at the tips, a
  legend for two or more series; **modelled series are hatched (lines dashed)
  and labelled "(modelováno)"**. A suppressed point is left out, a category
  left with nothing is removed, and the source line counts them. Text is
  converted to paths; SVG with a PNG fallback, sized from the PNG, never wider
  than the text block. `figures.py` captions ("Graf N — …" as `SEQ Graf`) and
  sources them; the alt text is `wp:docPr/@descr`. **A Sociomap in a client
  report goes through `require_client_facing`** even after validation (a test
  bypasses validation to prove it); an internal report prints an INTERNAL_ONLY
  map with a caption saying so, and every map prints `stres 1`. The token
  palette passes the dataviz validator (CVD ΔE 9.2 worst adjacent; two hues
  under 3:1 contrast, relieved by the direct labels). Tests:
  `test_report_docx_figures.py`, 8 tests. The render found exact leading crops
  pictures (AGENTS.md § DOCX).

- **R8 — templates.** `domain/report/templates.py` (pure): `ReportContent`
  (the legacy client-report fields as typed prose and blocks),
  `FinalContent`, `DocumentationContent`, and four recipes. `client_report`
  keeps the legacy order (`client_report_v2.py:149-158`): Shrnutí pro vedení
  (lede, method callout, KPIs), Odpověď pro rozhodnutí, Výzkumné otázky (a
  table), Co jsme zjistili (findings, then exhibits), Doporučení, Jak výsledky
  zapadají do dostupné externí evidence, Jistota závěrů (with the evidence key),
  Metodika, Limity, Závěr; then the appendices and the evidence appendix.
  `final_report` inserts Externí kontext a triangulace and Efektivní podpora
  vzorku after the external-evidence chapter. `internal_report` adds the Audit
  appendix; `study_documentation` is purpose, design, population, support,
  method, limits, evidence appendix, audit. A recipe refuses the wrong
  `ReportKind`. `tests/report_samples.py` builds one sample per template (and
  `stretch` lengthens prose for the stress check). Tests:
  `test_report_templates.py`, 11 tests: every sample validates, renders and
  lints clean; the section orders; **the client and final samples contain no
  internal string** (provider, model, QA, run and study ids, "Audit"); the
  internal sample carries them. Rendered: client 16 pages, final 18, internal
  17, documentation 11. The render found a table row splitting from its
  interval across a page (every data row is now `cantSplit`).

- **R9 — verification tooling.** `tools/report_preview.py`: DOCX → PDF →
  PNG through LibreOffice (a private profile per run), a contact sheet per
  document, `--grey` twins, `--stress` (+35 % Czech prose, through
  `report_samples.stretch`), `--samples` (the four templates, written by their
  own test with `AIA_REPORT_SAMPLES_DIR`), and the lint on every file; exit 1
  on a lint problem or a failed conversion. `make report-preview` runs it. The
  DOCX lint itself (`lint.py`) runs in CI through every renderer test.
  Verified by eye 2026-09-27 (LibreOffice 24.2, poppler 24.02): all four
  samples in colour, greyscale and stress. Greyscale: hatching and the mark
  shapes carry the modelled/measured distinction without colour. Stress: no
  overflow; tables break between rows with the header repeated.

## R10–R11 — planned, not built

These depend on contracts other contexts own. They are planned here so the
shape is agreed before anything is built; **nothing below exists yet**.

**R10 — composition from analysis results** (with analysis-governance).
`application/report.py`, `compose_report(kind, study, results, provenance)`:

1. Input: the study's `AnalysisModuleResult`s (the eight modules,
   `domain/analysis/`), each holding only admitted claims, plus the run's
   provenance (population binding, fingerprints) for the internal kinds.
2. The ledger: `EvidenceLedger.from_claims` over every admitted claim the
   results cite, for the report's surface (client kinds: `CLIENT_FACING`, so an
   internal claim fails the composition, it is not filtered), with the
   suppressed refs of the evidence table and `field_grades` from OI-9.
3. The content: a mapping from each module's draft fields to
   `ReportContent` — executive summary, decision answer, research-question
   answers, key findings, implications, validation / confidence / method
   summaries, limitations, closing — which is the part to agree: **which module
   owns which field**, and where exhibits (figures and tables) come from.
4. Output: a `ReportDocument` through `templates.*`, validated.

Open questions for analysis-governance: the field → module map; whether
exhibits are declared by a module or chosen by the template; OI-9's grades.

**R11 — the REPORT workflow step** (with platform-runtime). A `report`
executor in `apps/executors` that loads the results, composes (R10), renders
with `DocxRenderer`, and stores `final_docx` through `ArtifactRepository`
with its provenance (the document's fingerprint = the DOCX's SHA-256, stable
because rendering is deterministic). The web results stage lists it and
offers download, gated by `EXPORT_DELIVERABLE`. The worker image installs the
`report` extra. Open questions for platform-runtime: the step's place in the
`research` workflow and its inputs; the artifact kind name; whether an
unapproved revision may be downloaded (the draft footer already says so).

## Handoff — where to pick up

**State.** R0–R9 are done: a validated `ReportDocument` renders to a
deterministic, lint-clean DOCX with embedded fonts, every component, tables,
charts and marks, and four templates. R0–R4 (styles, fields) were PRs #53 and
#58; R4 (renderer) to R9 are the follow-up PR from
`claude/focused-edison-wglopy`.

**Next steps, in order.**

1. **Agree R10 with analysis-governance** (the questions above), then build
   `application/report.py` and its integration tests on stored results.
2. **Agree R11 with platform-runtime**, then the executor, the artifact and the
   download.
3. **OI-9** decides `field_grades`; until then every measured number prints
   `?` in a real report (the samples pass `{"vek": MEASURED}` explicitly).
4. Not done in R0–R9, deliberately small follow-ups:
   - the cover's AIA field image (`public/skin/brand/report-cover-field.svg`) is
     not on the cover: it needs a PNG fallback rasterised from the SVG, which
     the renderer cannot make without a new dependency; vendoring a
     pre-rendered PNG beside it is the likely answer;
   - custom document properties (`study_id`, revision, content fingerprint)
     need a `docProps/custom.xml` part python-docx lacks;
   - the contents' page numbers are filled by Word on open (updateFields);
     a LibreOffice preview shows them empty (AGENTS.md § DOCX);
   - a landscape section's running heads use their own styles; a report that
     mixes several landscape blocks back to back gets one section per block.

**Gotchas already paid for** are in AGENTS.md § DOCX: WOFF2 can't be embedded,
fonts are matched by family name, theme fonts win over explicit fonts, Word
enforces schema order, LibreOffice needs Writer, ignores `w:ptab`, pads
pictures without `distL/R`, crops pictures under exact leading, and shows a
TOC's cached page numbers as they are. The file-writing tool turns `\u00a0`
escapes into literal characters: grep new files before ruff.
