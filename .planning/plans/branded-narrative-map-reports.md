---
status: in-progress
chunks:
  - "[x] 1. Restore the original AIA cover and semantic typography"
  - "[x] 2. Compose coherent chapters and include frozen sociomap snapshots"
  - "[x] 3. Verify every rendered page and report lineage"
  - "[ ] 4. Publish, verify develop and reconcile documentation"
---
# Branded narrative reports with sociomap snapshots

Implement the user's authorized report upgrade using the original Claude Design Deliverable components and assets as the visual authority. Use normal prose for analysis, concise section headings, study title on the cover, the AIA population-field motif, readable captions and body typography. Preserve admitted analysis words, numbers, evidence references and all internal/synthetic/methodology disclosures.

The main internal report includes deterministic top-view and 3D snapshots from each run's stored object-map artifact. Image projection changes presentation only; no new terrain, coordinates, relationships or research results are calculated. Missing/not-mappable maps are explained. Report inputs and stored dependencies include the map SHA; historical frozen reports are not overwritten. Bump report contracts for changed exports.

Verify semantic styles, exact frozen inputs, refusal paths, image embedding and deterministic bytes. Render the realistic frozen sandbox report and inspect every page, plus long-title and empty-map cases. Run repository checks before publication and exact-SHA CI before deploy. Record the template and map-export behavior in a separate docs PR.

## Implementation and verification (2026-10-10)

The renderer follows the original ReportCover/ReportPage Claude Design sources. The packaged cover-field SVG is byte-identical to the original motif; its derived print background is transparent so Word's footer remains visible. Study titles, client/classification, revision and signature state stay editable. Body prose carries admitted evidence references; only actual chapter/subsection headings use heading styles. The wide evidence appendix returns to portrait for the audit.

New native report contract `aia-internal-report-3` depends on eight admitted analysis artifacts plus the run's sociomap artifact. The executor verifies the frozen dataset SHA and specification fingerprint before embedding top/3D views. Stored map positions, heights, grid gaps and relation signs remain unchanged. The experimental companion report contract becomes `aia-sociomapping-report-2` because its shared renderer changes. No model call, live research run, budget mutation or replacement of historical frozen reports occurred.

Final realistic example: 16 rendered pages, every page visually inspected, two 300-dpi PNG map snapshots, clear signed relationship table, landscape evidence ledger, portrait audit. The initial 3D legend collision and orphaned note were corrected and the affected pages re-rendered. The sample uses admitted frozen analysis and an explicitly labelled offline reproduction from the saved ratings and exact run method pins; the old native map JSON could not be downloaded with the expired local AWS session. Production reads the stored artifact without recomputation. DOCX bytes reproduce exactly. One warmed sequential export of four objects and a 65×65 stored grid took 0.467s for the two snapshots and 0.435s for the 2,068,190-byte DOCX: $0 incremental model spend. This is worker export work, not request-path computation.

Checks: strict mypy 313 files; lint, format, layer (101 rules), exposure (7 rules) and design checks pass. Latest report rendering/style/map targets: 25 pass; report/executor integration targets: 76 pass. Full local API: 356 pass; worker: 54 pass/8 unavailable PostgreSQL skips; executors: 385 pass/2 unavailable PostgreSQL skips. Full web: 668 pass; its first run failed the existing async unknown-configuration alert test, so the failure remains recorded rather than hidden. Full local core: 5499 pass/104 skip, one unchanged strict stored object-map fixture failure from platform floating-point differences (previously measured ≤7.11e-15); no fixture regeneration, test skipping or weakened assertion. Linux blocking CI must pass before merging.

## Findings and Doc follow-up

- `styles.py: _apply_paragraph`: python-docx starter `Title` retains a blue theme border/shading unless explicitly cleared. Wrong: change only the font/color; right: remove inherited `w:pBdr`, `w:shd`, `w:contextualSpacing` before applying declared AIA tokens. The injected-theme test prevents recurrence. The result otherwise visibly introduces an unbranded blue title underline.
- `cover.py: add_cover_field`: an opaque full-page background anchored in the body can cover the Word footer even with `behindDoc=1`. Wrong: retain the SVG paper rectangle; right: keep the original vendored SVG unchanged but remove that rectangle from the derived vector/PNG background. Visual QA on the rendered cover is the reproduction and catches the missing draft footer.
- Document `application/report_maps.py`, print `cover.py`/`object_map_figure.py`, native report contract/dependencies, signed relationship reading guide and the unchanged frozen historical exports in CLAUDE.md and ARCHITECTURE.md. Record the two observed python-docx/Word layout gotchas in AGENTS.md in a separate docs-only PR after merge. Do not edit shared documents in this feature PR.

## Publication

Feature PR #228 merged at `7ce1d5a9f3cc3e5e9b2e3d0d8f8eafa92663012c` after every blocking Linux PR check passed (CI run 38042498428). The strict map fixture passes on Linux. Exact merged-SHA CI run 38043332219 is the deployment gate; do not dispatch or bypass it. A built wheel was inspected and contains the original cover SVG and snapshot renderer. A separate 104-character Czech title cover rendered cleanly on one page. Documentation is prepared on its own branch; completion follows deployment verification.
