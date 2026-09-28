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

**Status:** paused at a checkpoint (2026-09-27); R0–R3 done, R4 started. See **Handoff** at the end. **Owner:** product-surface (A9).
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

## Handoff — where to pick up

**State.** R0–R2 are merged to `develop` (#53). R3 (`37a1c29`) and the R4 modules
above are on `feature/report-docx`, in the follow-up PR. Nothing renders a whole
report yet: there is no `renderer.py`.

**Next steps, in order.**

1. **`infrastructure/report_docx/renderer.py`** — `DocxRenderer.render(doc) -> bytes`:
   1. Run `require_valid(doc)`, then `build_outline(doc)`.
   2. Build the sections in `layout.py`: cover (no running heads), front
      matter (`pgNumType lowerRoman`), and body (`decimal`, restarting at 1).
      The body header is the report title plus a tab plus
      `STYLEREF "Heading 1"`. The body footer is the classification plus a tab
      plus `PAGE`.
   3. **With no `meta.approvals`, every footer says "KONCEPT — NESCHVÁLENO".**
   4. Front matter: the document-control page (the meta table, approvals and
      revision history; identifiers only for internal kinds), then Obsah, the
      list of figures and the list of tables. Each is a TOC field
      (`TOC \o "1-3" \h \z \u`, and `TOC \h \z \c "Graf"` / `"Tabulka"`)
      pre-filled with the outline's entries as cached results.
   5. Chapters: `Heading 1` gets the text "{number} {title}", with the number
      in a doc-accent character style, and is bookmarked by its anchor. The
      first H1 after the body section break must not also break the page.
   6. Finally, run `Footnotes.finish()`, set the core properties (title,
      subject, `language cs-CZ`, author "AIA"), call
      `embed.embed_fonts(doc, print_tokens.FONTS)`, and add
      `w:updateFields true` (in settings order) so Word refreshes the TOC.
2. **R5 — block renderers** (`blocks.py`, one function per model block):
   - Paragraph, lede, lists (through `Numbering`), and quote with attribution
     and a "syntetický respondent" label.
   - Callouts are paragraph shading `doc-wash` plus a left bar; METHOD always
     uses `copy.t("method_status_*")`.
   - KeyFinding and Recommendation use the legacy field labels.
   - A KPI row is a borderless table.
   - `Value` inline prints `numbers.with_unit(row.value, row.decimals, row.unit)`,
     plus a grade mark and "orientační" when `ledger.is_indicative`.
   - Footnote and CrossRef use the outline label.
3. **R6 — tables.** Use `S.DATA_TABLE`, with the header row repeating
   (`w:tblHeader`) and numbers right-aligned in `S.TABLE_NUMBER`. **A row with a
   suppressed ref is dropped**, and the source line says "Potlačeno …: N". The
   caption is above ("Tabulka N — title (n = …)"), with n from
   `numbers.base_n(ledger.row(base_ref).support.effective_n)`. A landscape
   table gets its own section.
4. **R7 — figures and marks.**
   - Charts are matplotlib (add it to the `report` extra), and axis and label
     text are converted to paths. Use the `viz-*` colours in fixed order, direct
     labels, one axis, and hatch modelled series.
   - Embed as SVG plus a PNG fallback. `/tmp` prototype code:
     `asvg:svgBlip` inside `a:extLst` of the PNG's `a:blip`, and set
     `wp:docPr/@descr` to the alt text.
   - Evidence marks are the same technique at about 2.5 mm, using the shapes in
     the web `EvidenceMark` (on `feature/web-first-slice`).
   - A SociomapFigure prints `stress_1` in its caption and is refused unless
     `CLIENT_FACING`, which validation already enforces.
5. **R8 — templates** (`domain/report/templates.py`): client report (the legacy
   v2 section order, `client_report_v2.py:149-158`), final report (triangulation
   and effective support), internal report (plus the audit block), and study
   documentation.
6. **R9 — `tools/report_preview.py`**: DOCX → PDF → PNG via LibreOffice (needs
   `libreoffice-writer`; see AGENTS.md). Check greyscale and +35 % Czech text.
7. **R10–R11** remain as the table above describes: coordinate them with
   analysis-governance and platform-runtime.

**Gotchas already paid for** are in AGENTS.md § DOCX: WOFF2 can't be embedded,
fonts are matched by family name, theme fonts win over explicit fonts, Word
enforces schema order, and LibreOffice needs Writer. The file-writing tool in
this session turned `\u00a0` escapes into literal characters. Keep NBSP and
en dash as escapes (AGENTS.md § ruff and Czech text).

