---
status: in-progress
chunks:
  - "[x] SOC1. Sociomapa's contract as data: the closed display operations (view, labels, weak links, mode, battery, selection), pointable ids (object, pair, respondent, segment) and V2's interaction contract; any operation that would write is refused"
  - "[ ] SOC2. The artifact hosts sociomap-5-web's panel in the frame, in Results and project memory alike, with the old-method text for a -1/-3 run"
  - "[ ] SOC3. The four-way legend and the display filter bar: frozen result, display, labelled interpretation, external context"
  - "[ ] SOC4. Object, pair and respondent detail in the item inspector, from the stored map only"
  - "[ ] SOC5. Interpretation on the map: the map interpreter's labelled output and a pair's Interpretation Research as Lead cards, never an input to the map"
  - "[ ] SOC6. Segment maps, filters and the respondent drill-down hosted here"
  - "[ ] SOC7. The map snapshot's approval slot"
  - "[ ] SOC8. Journey: Sociomapa at 1440, 1100, 768 and 390 px on a fictional run, zero paid jobs"
---
# Artifact: Sociomapa (Sociomap)

Umbrella: `research-lead-workbench#20` (with Výsledky). The `-5` drawing is A. Bahbouh's lane:
[`sociomap-5-web.md`](sociomap-5-web.md) (#517), and the method is
[`signed-off-sociomap-method.md`](signed-off-sociomap-method.md). This plan builds the artifact
around them and never redraws them. Chain: [`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md).
Anchors `@ 25f26232`; prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: the frozen map of the run, shown so that a person can read it and nothing they do
changes it.**

V2: `SociomapArt` (`EvidenceStages.tsx`, the Sociomap section).
- The toolbar: Shora / Reliéf, Popisky, Skrýt slabé vztahy and Jak číst mapu. A filter bar appears
  when a display filter is on: "Výpočet, pozice objektů a Stress-1 beze změny".
- The map: terrain, pairs (selectable) and objects (selectable), with `data-aia`
  `sociomap.object.<id>` and `sociomap.pair.<a>~<b>`.
- The four-way legend: deterministic result, display, interpretation, external context.
- Objects by height, fit, people, method and the method's status; "Zeptat se na …".
- Contract `CONTRACTS.sociomap` (`fixture.ts:413`): a display filter does not change the computation;
  external context does not enter it.

## 2. What exists today

- `SociomapView` (`ExecutionSteps.tsx:1928`) → `ObjectMapView` (`ObjectMapView.tsx:65`: `MappedView`
  `:168`, `PairCard` `:475`, `Ranked` `:507`, `Facts` `:554`, `snapshotNaming` `:596`).
- The `-5` panel `ObjectMapPanel` (`ObjectMapPanel.tsx:50`):
  - `#object-map-panel`, the unplaced objects (`:93`), the respondent counts (`:546`) and the
    segments (`:502`);
  - details (`:583-668`).
- The experimental `SociomappingView` (`SociomappingView.tsx:47`).
- Register: `GET /research/sociomap-register` (`routers/research.py:1302`); `lib/object-map-view.ts`
  `mapApproval`.

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| M-1 | The `-5` panel: built (`sociomap-5-web` 1-5); detail on click (`sociomap-5-web#6`) and the figure (`#7`) to come | data exists |
| M-2 | `-5` the only method of new runs (`signed-off-sociomap-method#8`); old-method text "Mapa ze starší metody; spusťte běh znovu" (Q2) | data exists |
| M-3 | The four-way legend and the display filter bar | data exists (static words) |
| M-4 | The map interpreter's output: its accept destination (`report-delivery#RD6`) and its worker (`lead-orchestration#LO9b`, `#LO9c`) | needs a new API (owned there) |
| M-5 | A pair's Interpretation Research (target: a Sociomap object pair, ADR 0021) as Lead cards (`research-lead-workbench#23b`, `#23c`) | data exists (engine); cards new |
| M-6 | Segment maps, filters and drill-down (`segment-maps-and-drilldown#5`-`#8`) | needs a new API (owned there) |
| M-7 | Snapshot approval (`report-delivery#RD4`) | needs a new API (owned there) |
| M-8 | Map values as ledger refs: OQ-ED1 (the owner and A. Bahbouh) | needs an owner decision (recorded) |
| M-9 | Lead targets: the map's elements carry ids, but no `data-aia` (G11) | needs a new API (the target grammar) |

## 4. The Lead on this artifact

- **View operations** (a closed set; each changes the picture only):
  - `open_stage(sociomap)`;
  - `map_view(top|relief)`, `map_labels(on|off)` and `map_hide_weak(on|off)`;
  - `map_mode(objects|respondents)` and `map_battery(<id>)`;
  - `select_object(<id>)` and `select_pair(<a>,<b>)`;
  - `open_method()`.

  A request to move a node, change a threshold or recompute is refused, and the refusal points to
  Metodika (D-40: map node drag is out).
- **Pointing** (agreed with the integration coordinator, 2026-10-21, registry #563):
  `object:<battery>/<object>` and `pair:<battery>/<a>~<b>`, the pair's ends in the map's own order.
  Respondent and segment targets are requested from the coordinator with SOC6.
- **As the registry names them:** `map_view`, `map_labels`, `map_hide_weak`, `map_mode` and
  `map_battery` are the one display-only `filter` operation with the names `view`, `labels`,
  `hide_weak`, `mode` and `battery`; `select_object` / `select_pair` are `select` on an object or pair
  target; `open_method` is `inspect`, on a `method:<id>` target the coordinator adds when it is needed.
- **Edit operations:** none.
- **Workers and cards:**
  - the map interpreter (`lead-orchestration#LO9b`), a proposal card: its output is an unapproved,
    labelled interpretation, never an input to the map;
  - Interpretation Research on an object or a pair (`lead-orchestration#LO5a.1`).
- **Inline proposals:** an interpretation shown in the legend's "Výklad" register, next to its pair.

## 5. Inputs and outputs

- **Reads:** the run's Sociomap artifact (id + SHA-256, verified against the dataset and the
  specification, `report_chapters.py:70-107`); the register; the pinned methods.
- **Hands on:**
  - the verified map body, to the report's map chapters (`ch-native-map-<n>`, `report_maps.py:125`) and to their figures
    (`object_map_snapshots`);
  - the map's id and SHA, to the report's audit (`map_sha256`).
  - The experimental Sociomapping DOCX is its own document and reaches no internal report section
    (G6 of the chain plan); `artifact-chain-to-draft-report#CHN6` names it in the audit and the
    coverage record.
  - Respondent and segment figures wait for `signed-off-sociomap-method#9` and
    `segment-maps-and-drilldown#9`.

## 6. Input interactions

- B27 (view toggles, relief: display only).
- Primitives: `Segmented` and `Switch`.

## 7. Chunks

**SOC1. Contract.** `lib/artifacts/sociomap.ts`. Test: a `move_object` request is refused by name.
Depends on `research-lead-workbench#14`, `#16`.
- Delivered: `objectTarget`, `pairTarget`, `readTarget` and `targetWords` (null for an id outside
  the grammar or an element the run lacks, never a guessed id); `FILTER_VALUES`, held to the
  registry's `VIEW_FILTERS`; `readMapOp`, which takes only the row's operations in the map's form on
  this run's batteries and refuses the rest by name (`writes_the_map` for any `move_`, `set_`,
  `recompute`… name, pointing to Metodika); `SOCIOMAP_INTERACTION`, V2's contract. Tests:
  `lib/artifacts/sociomap.test.ts`. No screen reads it yet: SOC2 puts the ids on the map's elements.

**SOC2. Host the panel.**
- In the artifact frame (`research-lead-workbench#15`), in Results and in project memory
  (`MemoryStudy`).
- Test: a `-1` run reads the old-method text.
- Depends on `sociomap-5-web#6`, `signed-off-sociomap-method#8`.

**SOC3. Legend and filter bar.** Test: with weak links hidden the bar says what did not change.

**SOC4. Detail in the inspector.**
- `ItemInspector` (mounted by chunk 15) shows the object, pair and respondent detail of
  `ObjectMapPanel`'s cards.
- Test: a pair with an undefined r reads UNKNOWN, not 0.

**SOC5. Interpretation.** Test: an interpretation is labelled "Výklad · od Vedoucího" and absent from
the map's numbers. Depends on `lead-orchestration#LO9b`, `report-delivery#RD6`,
`research-lead-workbench#23b`, `#23c`.

**SOC6. Segments and drill-down.** Depends on `segment-maps-and-drilldown#8`, and on `#0` (the
method owner).

**SOC7. Snapshot slot.** Depends on `report-delivery#RD4`.

**SOC8. Journey.**
- Extends `tools/ui_workbench/sociomapping_journey.mjs` at 1440, 1100, 768 and 390 px:
  - `select_pair` by the scripted Lead;
  - relief on and off with the filter bar;
  - the inspector's pair detail.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

None new. OQ-ED1 (map values as ledger refs) and MVPQ-12 (the audit's Q5-Q7) are already with the
owner and A. Bahbouh.

## Doc follow-up

- Register this plan and its chunks. `research-lead-workbench#20`'s D-13 text is met by
  `sociomap-5-web` and SOC2.
