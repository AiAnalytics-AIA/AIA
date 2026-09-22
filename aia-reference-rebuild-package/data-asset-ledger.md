# Data asset ledger

**Evidence mode: MANIFEST.** Identity (path + SHA256) is established.
**Shape, schema, row count, field count, size, lineage and consumers are NOT** —
they require the bytes. Every such column below reads `UNKNOWN (needs tree)`
rather than an estimate.

The task brief cites ~18,766 rows x ~400 fields for the population panel, ~33 MB
for the demo library and ~7.3 MB of audit reference material. **None of those
numbers are confirmed here** and they are not repeated as fact: the manifest
records no sizes. They are recorded as claims to verify.

## Core registered assets

| Path | SHA256 | Kind | Size | Schema | Note |
|---|---|---|---|---|---|
| `FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz` | `864f8dbcd101e4be…` | population panel | UNKNOWN | UNKNOWN | latest generation present |
| `FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz` | `d6a9ef120b81982e…` | population panel | UNKNOWN | UNKNOWN | prior generation |
| `audit_reference/FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz` | `5300c1aeeef4ead1…` | population panel | UNKNOWN | UNKNOWN | base/reference generation |
| `LIVE_POPULATION_TARGETS_18_5.csv` | `b8adb939975d6615…` | calibration target | UNKNOWN | UNKNOWN | named LIVE — likely the active target set |
| `BACKBONE_CENSUS_2021_TARGETS.csv` | `c24faf7a94b6d954…` | calibration target | UNKNOWN | UNKNOWN | census 2021 backbone |
| `CENSUS_LABOUR_FORCE_TARGETS_v17.csv` | `748c6a0ec6a4e742…` | calibration target | UNKNOWN | UNKNOWN | labour force |
| `DONOR_BLOCK_REGISTRY.json` | `6dcf142131ea36ce…` | donor fusion | UNKNOWN | UNKNOWN | registry of donor blocks |
| `DONOR_COVERAGE_MATRIX_v17_1.csv` | `11fdfce2c003feb9…` | donor fusion | UNKNOWN | UNKNOWN | coverage matrix |
| `DONOR_SUPPORT_SUMMARY_v17_1.csv` | `95cf7ef3ef0837cf…` | donor fusion | UNKNOWN | UNKNOWN | support summary |
| `CALIBRATION_REGISTRY.csv` | `1b0d9cea2f7a0962…` | calibration | UNKNOWN | UNKNOWN | registry |
| `CALIBRATION_REPRODUCTION_CHECK_v17_1.csv` | `d06d62988812dad8…` | calibration | UNKNOWN | UNKNOWN | reproducibility check |
| `AI_PANEL_CALIBRATION_TEMPLATE.csv` | `9c3ad26ce9e53a06…` | calibration | UNKNOWN | UNKNOWN | template (csv) |
| `AI_PANEL_CALIBRATION_TEMPLATE.json` | `2b1532af94fed498…` | calibration | UNKNOWN | UNKNOWN | template (json) |
| `BUILTIN_SUBPANELS_v17.json` | `bcc0cead3fe4d06c…` | subpanel | UNKNOWN | UNKNOWN | built-in subpanel definitions |
| `SPECIAL_PANEL_REGISTRY_v17.json` | `6dd240f585138dea…` | subpanel | UNKNOWN | UNKNOWN | special panel registry (json) |
| `SPECIAL_PANEL_REGISTRY_v17.csv` | `a398cf4ce4d83478…` | subpanel | UNKNOWN | UNKNOWN | special panel registry (csv) |
| `SPECIAL_PANEL_QC_SOURCE_v17.csv` | `07f9540e1c5a1f14…` | subpanel | UNKNOWN | UNKNOWN | QC source |
| `SUBPANEL_SUPPORT_v17.csv` | `74550307946d13ba…` | subpanel | UNKNOWN | UNKNOWN | support |
| `LATENT_FACTOR_AUDIT_v17_1.csv.gz` | `7473e4e57ff78233…` | methodology audit | UNKNOWN | UNKNOWN | latent factor audit |
| `CONDITIONAL_AXIS_HOLDOUT.csv` | `96a8cd8da944b371…` | validation | UNKNOWN | UNKNOWN | holdout — validation evidence |
| `BENCHMARKS_FINANCE_SPECIAL_v17.csv` | `6f83a5401ffd8c5b…` | benchmark | UNKNOWN | UNKNOWN | finance benchmark |

## Special panels (18)

Segment-specific panels, all gzipped CSV, all canonical manifest entries.
Grouped by the directory the prototype itself used:

**foreigners** (5)

- `SPECIAL_PANELS/foreigners/foreign_russian.csv.gz` — `2b4ee69ce631f2d2…`
- `SPECIAL_PANELS/foreigners/foreign_slovak.csv.gz` — `419fb54bd68749af…`
- `SPECIAL_PANELS/foreigners/foreign_ukrainian.csv.gz` — `13d9acc0a92387f3…`
- `SPECIAL_PANELS/foreigners/foreign_vietnamese.csv.gz` — `b27730f690505e7c…`
- `SPECIAL_PANELS/foreigners/foreigners_overall_top4_proxy.csv.gz` — `d3e91c9e2e001d36…`

**industry** (5)

- `SPECIAL_PANELS/industry/construction_ecosystem.csv.gz` — `dc56f79205477033…`
- `SPECIAL_PANELS/industry/healthcare_clinical_professionals.csv.gz` — `72b5380cc8580616…`
- `SPECIAL_PANELS/industry/healthcare_material_ecosystem.csv.gz` — `c5010a7ff4025719…`
- `SPECIAL_PANELS/industry/procurement_buyers.csv.gz` — `20a579666a13e9e3…`
- `SPECIAL_PANELS/industry/real_estate_professionals.csv.gz` — `2b218e56ebc39896…`

**minorities** (8)

- `SPECIAL_PANELS/minorities/minority_german.csv.gz` — `29a2e386632d5676…`
- `SPECIAL_PANELS/minorities/minority_moravian.csv.gz` — `1dde4b9045ccebe4…`
- `SPECIAL_PANELS/minorities/minority_polish.csv.gz` — `dc2e6ab83147d534…`
- `SPECIAL_PANELS/minorities/minority_roma_selfdeclared.csv.gz` — `c1c2306f75cb14ef…`
- `SPECIAL_PANELS/minorities/minority_silesian.csv.gz` — `353000f86b6ec5ca…`
- `SPECIAL_PANELS/minorities/minority_slovak_declared.csv.gz` — `eb2ab15e082b2461…`
- `SPECIAL_PANELS/minorities/minority_ukrainian_declared.csv.gz` — `032fa6ea8fc4063f…`
- `SPECIAL_PANELS/minorities/minority_vietnamese_declared.csv.gz` — `32f7bfce96f87c89…`

## What is NOT covered by this ledger

The manifest excludes runtime-generated directories, so no produced report,
simulation run output, log or cache appears here. If the rebuild needs examples
of what the system actually emitted, they must come from the original ZIP.

`demo_library/` (622 files) is inventoried by path and hash but not characterised.
It is the largest single zone in the reference and likely contains worked
end-to-end examples — which would be the highest-value behavioural evidence in
the whole package, since a worked example shows inputs and outputs together.
Reading it is a priority when the tree arrives.

## Lineage

Not established. `BUILD_MARKETING_LATENT_v17_1.py` is present in the manifest and
its name suggests it *generates* a latent-factor asset; if so it is a lineage
record for `LATENT_FACTOR_AUDIT_v17_1.csv.gz`. That is a hypothesis from a
filename, not a finding, and is listed for confirmation.

Until lineage is established, **every asset here must be treated as
IRREPLACEABLE**: an asset that cannot be proven reproducible is, for planning
purposes, not reproducible.
