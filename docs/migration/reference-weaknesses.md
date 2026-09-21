# Weaknesses and known deviations in the reference implementation

Defects found in the NPC Panel prototype during migration, and what we did about
each.

**The reference is not modified to make our test environment look clean.** Where a
workaround is applied on our side, it is recorded here. If the reference is ever
changed, that change must be tracked as a deliberate, listed edit rather than
made silently — otherwise the parity suite stops comparing against the thing the
team actually validated.

Reference location: `../npc-panel-reference`, pointed at by
`AIA_LEGACY_REFERENCE`. Never committed to this repository. No `.git`, so there is
no history and no upstream to send a patch to.

## W1 — `python-pptx` is an undeclared dependency

**Severity:** low for the reference, relevant to anyone reproducing its baseline.

`output_pack.py` imports `pptx` at four points:

```
output_pack.py:31: from pptx import Presentation
output_pack.py:32: from pptx.util import Inches, Pt
output_pack.py:33: from pptx.dml.color import RGBColor
output_pack.py:34: from pptx.enum.shapes import MSO_SHAPE
```

`python-pptx` is **not** in `requirements.txt`. On a clean install the suite fails:

```
tests/test_release_core.py::test_client_exports_hide_internal
ModuleNotFoundError: No module named 'pptx'
```

**Effect.** The advertised baseline is unreachable from a clean checkout, and the
management-deck export path is silently unavailable at runtime until someone
happens to have the package. It fails at export time — the worst moment — rather
than at startup.

**Our action.** None to the reference. We install `python-pptx` in the
verification environment and report the baseline as *394 passed with
`python-pptx` installed*, stating the caveat wherever the number appears. We have
not edited `requirements.txt`.

**For the new system.** Every import is a declared dependency, and CI installs
only from declared dependencies, so this class of defect fails the build rather
than a client export.

## W2 — `impact_preview` raises `ValueError` on a cross-pipeline field

**Severity:** high. Reachable from the project save path.

Changing `scenario` on a research project maps through `IMPACT_ROOTS` to
`SCENARIO_CONTRACT`, which is not in `RESEARCH_STAGES`. `ids.index(root)` then
raises, and the exception escapes through `project_store._save_normalized` — so a
save fails rather than a stage being mis-routed. The mirror case
(`questionnaire` on a simulation project) behaves the same way.

Verified:

```python
>>> project_pipeline.impact_preview('research', ['scenario'])
ValueError: list.index(x): x not in list
```

**Our action.** Deviation D1 in [parity-matrix.md](parity-matrix.md). The port
resolves such a root through `STAGE_EQUIVALENTS` — the mechanism the prototype
already uses for cross-pipeline routing — and drops it if it still does not
resolve. Two tests assert the legacy behaviour is still what we believe, so the
suite will tell us if the reference ever changes.

## W3 — `api_budget_check` reports more remaining budget than the cap

**Severity:** medium. Wrong figure shown to users; the allow/deny decision is
unaffected.

Negatives are clamped when computing `projected_usd` but not `remaining_usd`, so
a spend of `-3.0` against a $10 cap reports **$13 remaining**.

**Our action.** Deviation D3 in [parity-matrix.md](parity-matrix.md). Clamping is
consistent and reported headroom never exceeds the cap. Parity on the allow/deny
decision is still asserted.

## W4 — An unrecognised stage provider override silently breaks policy

**Severity:** medium. Cost and provenance consequences.

`provider_for_stage` accepted any truthy `stage_override` and normalised an
unrecognised value to Claude Code. A typo on a project pinned to
`CLAUDE_API_ONLY` therefore moved that stage onto the subscription runtime,
changing both what it cost and what produced it.

**Our action.** Deviation D2 in [parity-matrix.md](parity-matrix.md). Only a
recognised override is honoured; otherwise the policy decides.

## W5 — `PRODUCT_POLICY.json` disagrees with itself about the production panel

**Severity:** low, but it is a data-provenance field.

```json
"production_panel": "FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz",
"data_core": { "production_panel": "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz" }
```

`DATA_CONTRACT_v17.json` says `v17_4_0`, and `v17_4_0` is the file actually
present (18,766 rows × 400 columns).

**Our action.** Treat `v17_4_0` as authoritative. The stale
`data_core.production_panel` key must be resolved when the methodology contract is
migrated in Phase 6, and the resolution recorded rather than assumed.

## W6 — Structural characteristics, not defects

Recorded so they are not mistaken for things to preserve. Full detail in
[legacy-system-map.md](legacy-system-map.md).

- 136 API routes dispatched through `if`/`elif` chains on path prefixes, with no
  request validation or schema.
- `ui_app.html`: one 896 KB file, 176 script blocks, ~1,040 functions, element ids
  suffixed by build number (`anthKey1790`, `assistantDrawer1791`).
- SQLite as the application store: single-writer, blocking concurrent workers.
- Artifacts addressed by filesystem path under the application directory.
- No authentication, and no concept of a user, tenant, client or study.
- Naive local-time timestamps, making audit ordering ambiguous across timezones.
- Czech code identifiers (`dotaznik`, `dispozice`, `navrh`, `kalibrace`,
  `vystupy`, `osobnost`, `biografie`).
- Several coexisting generations of the same feature, e.g. `report.py` /
  `client_report_v2.py` / `final_client_report.py`.

## How to add to this file

When migration finds another reference defect:

1. Reproduce it against the reference and record the exact reproduction.
2. Decide whether to preserve, deviate or work around.
3. If deviating, add a test that asserts the *legacy* behaviour too, so the
   deviation is revisited if the reference changes.
4. Record it here and, if it changes behaviour, in
   [parity-matrix.md](parity-matrix.md).
