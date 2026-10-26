---
status: in-progress
chunks:
  - "[x] SOC1. Sociomapa's contract as data: the closed display operations (view, labels, weak links, mode, battery, selection), pointable ids (object, pair, respondent, segment) and V2's interaction contract; any operation that would write is refused"
  - "[ ] SOC2. The artifact hosts sociomap-5-web's panel in the frame, in Results and project memory alike, with the old-method text for a -1/-3 run"
  - "[x] SOC3. The four-way legend and the display filter bar: frozen result, display, labelled interpretation, external context"
  - "[ ] SOC4. Object, pair and respondent detail in the item inspector, from the stored map only"
  - "[ ] SOC5. Interpretation on the map: the map interpreter's labelled output and a pair's Interpretation Research as Lead cards, never an input to the map"
  - "[ ] SOC6. Segment maps, filters and the respondent drill-down hosted here"
  - "[ ] SOC7. The map snapshot's approval slot"
  - "[ ] SOC8. Journey: Sociomapa at 1440, 1100, 768 and 390 px on a fictional run, zero paid jobs"
  - "[x] SOC9. The workbench's Sociomapa stage is the map: no Výsledky tabs, no guide, no other results card; the map first at the pane's width"
  - "[x] SOC10. Below the map, in order: what it shows (tiles), the strongest relations, the objects, respondents and segments, its reliability, how it was computed (folded)"
  - "[x] SOC11. Plain Czech on the stage: no artifact, run, method or spec id outside Technické údaje"
  - "[x] SOC12. No amber notice frame on the stage: amber means only a person is waited on"
  - "[x] SOC13. The map's overlays: one bar with popovers, a view rail bottom right, the legend as a chip, the side sheet beside the map, fading while the map moves, keys"
  - "[x] SOC11b. A copy pass on the stage: Stress-1, PROGRESS D6, Top vztahy, a dead key (reopens SOC11; spec szz S1; W2)"
  - "[x] SOC14. One sentence that the map's taste segments are descriptive (spec szz S2; W2)"
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
- The old-method text is #598's (`signed-off-sociomap-method#8`: `olderMethodOnly`,
  "Mapa ze starší metody; spusťte nový běh", a battery with no `-5` map); SOC2 shows that text,
  keyed off the same condition, and writes no second notice (PM, 2026-10-21).
- Delivered so far: the `-5` panel's elements carry the SOC1 ids (`data-aia`): every listed object
  `object:<battery>/<object>` (its one element, selected or not), and the detail card's selected
  relation `pair:<battery>/<a>~<b>`. Tests: `ObjectMapPanel.test.tsx` › "the Lead's names on the map". The
  frame itself waits for `research-lead-workbench#15`.
- Delivered (2026-10-26): the Lead's map views on the `-5` panel (`research-lead-workbench` 14, "For Sociomapa
  (2)"). `SociomapStage` routes them, since it knows every map it draws (the signed-off panel with its
  terrain, each with the objects it places): once its artifact is read it listens for `LEAD_MAP_VIEW` and
  takes the view sent before (`takeLeadMapView`); each is checked with `readMapOp` against all its maps and
  handed to the map that owns it (`routeToMap`), to every map for a stage-wide filter (view, mode; stand-in
  review P2, #939), or refused once by the stage in words (`sociomap-lead-note`, reset with the run on
  screen): an element no map here places, a view no map here receives (a stage that draws no signed-off
  map, a stage-wide filter included; stand-in review P2 on 7a8172ca), the respondent map when no map stores
  one (said once, not once per map), and `labels` / `hide_weak`, which the panel has no control for (SOC3
  finding). `ObjectMapPanel` applies what is routed to its battery,
  once, as it arrives, to the picture only:
  - `select` on `object:` or `pair:` opens that element's detail on the object map;
  - `filter` `view` sets the camera (top: 2D, relief: 3D), `mode` the map (objects / respondents),
    `battery` brings that battery's map into view;
  - what this map cannot do (the respondent map it does not store) is said in its own live region
    (`object-map-lead-note`); nothing changes;
  - a view from above that arrives before the canvas is measured is drawn when it is, at the measured
    size, whatever it measures; the rest apply at once.
  `LEAD_REVEAL` on a `pair:` target opens the relation's detail on the object map, so its id is there to be
  shown; the respondent map is left as the person has it.
  Tests: `ObjectMapPanel.test.tsx` › "the Lead's map views" (each failing on develop) and `ExecutionSteps.test.tsx` › "the Lead's map views" (the stage's routing; the P2 case fails on 34846ff3);
  `sociomap_journey.mjs` sends the workbench's event at 1440 and 390 px. The server half (the views live
  in `LeadOutput`) is the integration session's, after this.
  - The refusal is read out but not drawn: whether the panel shows it is the methodology owner's call
    (the panel's visual decisions are his).

**SOC3. Legend and filter bar.** Test: with weak links hidden the bar says what did not change.
- Delivered on the `-5` panel: the filter bar (`lib/sociomap-display.ts` `displayChanges`: what the
  toolbar changed against the opening -- the respondent map, Absolutní, Vybraný / Vše -- in words, then
  "Výpočet, polohy objektů, výšky, vztahy a věrohodnost mapy beze změny.", and "Zrušit filtr" back to
  the opening), and "Co je co", the four registers, beside the map. Tests: `sociomap-display.test.ts`,
  `ObjectMapPanel.test.tsx` › "the filter bar and the four registers".
- The plan's test names hidden weak links, which the `-5` panel does not offer (the panel's rule:
  its relation display is Top / Vybraný / Vše); the same test runs on the panel's own display
  choices. Finding for SOC1's live filters: the registry's `labels` and `hide_weak` filters
  (`VIEW_FILTERS.sociomap`) have no control on the `-5` panel, and `view: top|relief` is the
  panel's 2D / 3D camera, not a toggle. Until the panel offers them (the methodology owner's call,
  as every visual decision inside the panel), a Lead `filter` on `labels` or `hide_weak` has
  nothing to set; SOC2's wiring refuses it by name rather than ignore it.

**SOC4. Detail in the inspector.**
- `ItemInspector` (mounted by chunk 15) shows the object, pair and respondent detail of
  `ObjectMapPanel`'s cards.
- Test: a pair with an undefined r reads UNKNOWN, not 0.
- Done ahead of the inspector, on the panel's own card (browser audit, 2026-10-22): a pair's detail opened only by a
  click on its line on the canvas, which takes no keyboard. The object card's listed relations are now buttons that
  open the pair as that click does, and close it again (`ObjectMapPanel.tsx` `ObjectCard`). Test:
  `ObjectMapPanel.test.tsx` › "opens a relation from the object's card, a focusable button named by what it shows, and
  closes it again". The card lists the object's 5 strongest reliable relations, as the panel does; a drawn link beyond
  those still opens only on the canvas.
- Delivered (2026-10-26, spec `szz/S3`): the item inspector draws a map's object and relation
  (`MapInspect.tsx`, registered for the `object` and `pair` kinds in `ItemInspectBody.tsx`), so the Lead's
  "Detail dvojice" (`inspect` on a `pair:` target) and any opened map item read the stored pair through the
  panel's own cards (`RelationBlock`, `ObjectCard`, in an `.omw` wrapper, no second copy of their words): r
  with its interval, N and the verdict, an undefined r "Vztah nelze určit" with its reason, never 0; an
  object: its rating, connectedness and strongest reliable relations, each opening its pair in the drawer.
  The maps are the ones `SociomapStage` draws (`setShownMaps`, from the same reading that decides which
  maps take the Lead's views), "Mapa se ještě načítá." until the stage has read them, and none once it
  leaves, so the drawer never opens another run's map. Each shown map carries the register's approval of its
  method, so the drawer, read on its own, says "Jen pro výzkumníky studie" or "Metodika schválena pro
  zprávy" as `MapExplained` does (stand-in review P2, #979). A stage whose artifact could not be read says so
  in the drawer ("Mapu tohoto běhu se nepodařilo načíst."), and the object card's relations there are buttons
  that open the pair, not unpressed toggles. The Lead's "Vybrat"
  is #939's listener. Tests: `MapInspect.test.tsx` (the plan's test: "reads a pair with an undefined r as
  unknown, never as 0"); `ExecutionSteps.test.tsx` › "lets the item inspector open a relation of the map it
  draws, until it leaves". Still open: a respondent's detail in the inspector (no `respondent:` target yet,
  SOC6), and a person's way into the drawer from the map itself (inside the panel's drawing, the
  methodology owner's).

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
- Delivered so far: `tools/ui_workbench/sociomap_journey.mjs`, a journey of its own:
  `sociomapping_journey.mjs` covers the experimental Sociomapping document, not this stage.
  `--prepare` runs one fictional `-5` run in the local workbench only (putting a version of the
  `aia-sociomap-5` preset in force while `-5` is not what a new run pins), and an older method's run
  first only while an older method is still in force. The journey checks:
  - the `-5` map at 1440, 1100, 768 and 390 px with no page overflow;
  - each listed object's Lead name, once, on its button;
  - the selection reset between Objekty and Respondenti, and full screen's five strongest (#562);
  - the filter bar, "Zrušit filtr" and the four registers (SOC3);
  - every pressed control's colour apart from its background on the `-5` map (#591);
  - an older method's run reads "Mapa ze starší metody; spusťte nový běh" and draws no map, at 1440,
    1100, 768 and 390 px (#598). No new run can pin an older method, so on a workbench without one
    from before, the `-5` run is read as one: its Sociomap artifact answered in the browser with no
    map in it (the "none" case of `olderMethodOnly`; a battery holding a `-3` map is
    `object-map-view.test.ts`'s). Before this, the check took either a notice or a drawn older map,
    so an older map drawn again would have passed it. Fails with `olderMethodOnly` made false;
  - no page error, no write but the stage opened, zero paid jobs.
- Still to come: `select_pair` by the scripted Lead (once `select` is live, research-lead-workbench
  14b) and the inspector's pair detail (SOC4).

**SOC9-SOC13. The stage is the map** (Nigel, 2026-10-22, from the artifact
<https://claude.ai/artifact/QWDidu8ztrcuiBNL5Sa4Vy> v4, "Návrh: zaměřeno na mapu" with "Překryvy: nové").
- SOC9: on the workbench's Sociomapa stage (`#maps`, `useOnSociomapStage`) `RunResults` renders
  `SociomapStage` instead of `ResultsWorkspace`: the run's notices (origin, a moved design), then each set's
  map at the pane's width, then `MapExplained`, then the run's experimental Sociomapping with its review
  (`#res-sociomapping` opens the stage too). The stage follows navigation (hashchange, popstate), never a
  tab of Výsledky that rewrites the hash in place. Výsledky keeps its tabs; the classic layout keeps
  Sociomapy as a tab. An older method's set says "Mapa ze starší metody; spusťte nový
  běh" and draws nothing; a map that is not the signed-off method's is drawn as Výsledky draws it.
- SOC10: `MapExplained` over `lib/map-explained.ts` (`explainMap`, pure): Co mapa ukazuje (sentence, approval
  badge, four tiles), Nejsilnější vztahy (six, signed bars), Objekty (rating and connectedness bars),
  Respondenti a segmenty (placement and segment bars), Jak spolehlivá je mapa (three gauges, one sentence
  each), Jak byla spočtena (folded, Technické údaje last). Every number is the stored map's.
- SOC11: the main view prints no id; the ⓘ box carries one plain sentence on the stage.
- SOC12: the stage has no `Card tone="notice"`; the result cards on Výsledky keep theirs (design system v2).
- SOC13: `ObjectMapPanel`'s overlays: one bar top left (Objekty / Respondenti, Nastavení mapy and Nástroje
  as popovers, ⓘ with the map's quality, the filter as a chip in an always-present live region), one view
  rail bottom right, the legend as a chip, Správa objektů and the detail as the tabs of one side sheet
  beside the map (the canvas re-frames to the width left), overlays fading to 40 % while the map is dragged,
  rotated or zoomed, keys O / R / L / I / F / + / − / 0, Esc in order. `ObjectMapWindows.tsx` (floating,
  dragged, resized windows) is gone; nothing else used it.
- Tests: `lib/map-explained.test.ts`; `ExecutionSteps.test.tsx` › "the workbench's Sociomapa stage";
  `ObjectMapPanel.test.tsx` › "the map's overlays (artifact-sociomap SOC13)" and its follow-ups;
  `sociomap_journey.mjs` on the bar, popovers and sheet.

## 8. Owner questions

None new. OQ-ED1 (map values as ledger refs) and MVPQ-12 (the audit's Q5-Q7) are already with the
owner and A. Bahbouh.

## Doc follow-up

- Register this plan and its chunks. `research-lead-workbench#20`'s D-13 text is met by
  `sociomap-5-web` and SOC2.

## Findings

- **For the methodology owner: the stage's plain-language method text (SOC10) is new wording.** "Jak byla
  spočtena" (`cs.ts` `research.exec.mapStage.how*`) and the gauges' sentences restate the signed-off method:
  person-mean centring, the baseline-corrected correlation with n ≥ `n_min`, false-discovery control and the
  noise test, the soft-rank layout (else "rozmístil výpočet"), the relative terrain whose lowest hill is 15 %
  of the highest, split-half agreement and bootstrap uncertainty. "± N %" reads `credibility.uncertainty_radius`
  as a share of the typical distance between objects, as the artifact type documents it. To confirm the words.
- **Fixed on the Sociomapa stage: an older method's run was told how to use a map it does not draw** (the
  "Open, SOC2" entry below). The stage prints no map hint and no guide; the notice alone. Test:
  `ExecutionSteps.test.tsx` › "says a set stored under an older method draws no map, with no map hint above the
  notice". Výsledky's Sociomapy tab still prints `mapToolNotInAia` above an older method's notice: Výsledky's to fix.
- **Fixed by SOC13 (the two "for the methodology owner" items below):** at 390 px the legend is a chip until
  opened, and the view controls moved to a rail bottom right, off the labels at the top right.
- **Open: object labels near the map's edge can still pass under the bar or the legend chip.**
  `drawObjectMap` (`lib/object-map-panel.ts`) places labels without insets. Smallest fix: an `insets`
  parameter to its projection (centre shifted, scale reduced). Test: a label's box never meets the bar's.

Browser audit, 2026-10-21, on the local workbench (`AIA_WEB_RESEARCH_WORKBENCH=true`, a fictional eight-brand run on
`aia-sociomap-5` and one on `-3`), 1440 / 1100 / 768 / 390 px:

- **Fixed (this PR): the map did not fit where it is read.** `ObjectMapPanel.tsx:330 @ bfe6d15b` gave the stage a fixed
  700 px height.
  - At 1440 px in the workbench, the toolbar plus the canvas took 788 px of a 755 px pane, so the toolbar left the view
    while the map was read, and the detail card sat below it.
  - At 390 px the canvas was 308 × 700 px. The map is drawn at the scale of its shorter side, so the top 230 px were
    empty, and the list and detail were a screen further down.
  - Now measured: `stageHeight(pane, above, width)` in `lib/sociomap-display.ts`, the least of 700 px, what the pane
    leaves under the toolbar and filter bar, and max(360, 1.1 × the stage's width), floored at 120 px. The pane is the
    workbench's `.artbody`, else the window less the shell's sticky header; full screen still takes the screen.
  - A first fix, a CSS guess of the chrome (`min(700px, max(320px, 100dvh − 260px), max(360px, 110vw))`), still
    overflowed a short screen (Codex, #637): 408 px in a 245 px pane at 844 × 390, 500 in 406 at 390 × 600.
  - Test: `sociomap_journey.mjs` checks the fit at 1440, 1100, 768 and 390 px wide, at 844 × 390 and 390 × 600, and in
    project memory's classic layout at 1366 × 768 (under the sticky header), and that a canvas is no taller than
    1.5 × its width. Each short screen failed on the CSS guess; the memory case fails without the header subtracted
    (752 > 640 px). `sociomap-display.test.ts` holds `stageHeight`.
- **Fixed by #773 (merged as `d71b1738`), was SOC2's: the Sociomapa stage opened on Výsledky's other cards.** A view
  named by the address now opens scrolled to its tabs (`ResultsWorkspace.tsx:36-48 @ 382b418a`;
  `ResultsWorkspace.test.tsx` "opens a view named by the address scrolled to its tabs…"). As recorded: The
  stage is Výsledky's maps view (`workbench-stages.ts`, view `maps`), and `ResultsWorkspace` puts "Kdo odpovídal",
  "Kompletní zpráva studie" and the results tabs above the maps panel. The map starts 2,174 px into a 755 px pane at
  1440 px. SOC2's frame shows the map alone; until then a person scrolls three screens to the map. The Výsledky screen
  owns `ResultsWorkspace`, so this is not patched here.
- **For the methodology owner (inside the panel's drawing, not changed):**
  - at 390 px the legend card (260 px wide, bottom-left) covers the lower third of the map;
  - the tool column (top-right) covers object labels near the right edge ("Borealis").
  Both follow the AIA panel's layout.
- **Known, already with the methodology owner:** Iris's label is dropped beside Halo (`placeLabels`, Q50 (b)),
  still seen in every width.
- **Fixed: the object list on the respondent map offered a selection it could not show.** Browser audit,
  2026-10-21. On Respondenti, a click on a listed object set the selection (`aria-pressed`, `data-selected`), but
  nothing a person could see changed: the respondent card stayed, and the markers do not react
  (`ObjectMapPanel.tsx:349 @ bfe6d15b`, `onChoose={choose}` on both maps). Selection is the object map's, so on the
  respondent map the list is read-only: `aria-disabled`, no `aria-pressed`, no "Vybrat" label, no hover. Not the
  native `disabled` (Codex, #639): a disabled button takes no focus and fires no click, so the Lead's `focus` on an
  `object:` target and the "@" pick would break on the respondent map. Test: `ObjectMapPanel.test.tsx` › "the object
  list on the respondent map".
- **Fixed: the map's side column was a landmark of its own.** axe (`landmark-complementary-is-top-level`, moderate) on
  the `-5` panel's Objekty and Respondenti at 1440 and 390 px: the side column was an unnamed `<aside>` inside the
  page's main landmark (`ObjectMapPanel.tsx:77 @ 03989975`), and the older methods' view had the same
  (`ObjectMapView.tsx:342 @ 03989975`). Both are layout, so `<div>`; the panel's component is `SideColumn`. Test:
  `ObjectMapPanel.test.tsx` › "adds no landmark of its own beside the map, on the signed-off map and an older method's"
  (fails on either view's `<aside>`). axe on the `-5` panel now reports nothing at either width; the older view was not
  scanned in a browser (no `-3` run was prepared), only by the test.
- **Open, for the methodology owner: a respondent's detail is reached only by a click on the canvas.**
  1. On Respondenti the "Respondent" card fills only from a canvas hit; no control opens it from the keyboard.
  2. `ObjectMapPanel.tsx:262 @ 03989975` (`setPerson` only in `onUp`'s hit test); the canvas takes no keyboard.
  3. On a `-5` run, Respondenti, Tab through the panel: no stop opens a respondent's card (checked on the local
     workbench, 2026-10-22).
  4. A keyboard or screen-reader user reads the counts and the segments but no single respondent's placement.
  5. A way to reach a respondent without the pointer, e.g. a list or a "next respondent" control beside the map: a
     layout decision inside the panel (Aram's rule), so recorded here, not built.
  6. A test that Tabs on Respondenti and expects a control naming a respondent.
- **Open, SOC2: an older method's run is told how to use a map it does not draw.** Browser, 2026-10-22, 390 px:
  the Sociomapa card prints `mapToolNotInAia` ("Mapu můžete prohlížet shora nebo jako 3D terén, otáčet…",
  `ExecutionSteps.tsx:1666 @ 9607ee09`) above every battery, and a battery with no `-5` map says "Mapa ze
  starší metody; spusťte nový běh" below it. A person on such a run reads how to turn a map that is not there.
  Reproduction: `node tools/ui_workbench/sociomap_journey.mjs` (after `--prepare`), then
  `tmp/ui-workbench/sociomap-journey/390-older-method.png`. Smallest fix: print the hint only when some battery draws a map (`!olderMethodOnly(b)` for one). Test: the
  `ExecutionSteps.test.tsx` older-method case expects no `mapToolNotInAia`. Left for SOC2, which hosts the
  panel and writes no second notice; ExecutionSteps is Výsledky's.
- **Open, not this plan's code: two of `sociomap_journey.mjs`'s checks fail on develop @ `ce25a1b8`.**
  1. "no run or method id outside Technické údaje": the stage renders the experimental Sociomapping view
     (`ExecutionSteps.tsx:1664 @ ce25a1b8`), whose provenance row (`SociomappingView.tsx:318 @ ce25a1b8`,
     `ART-… · SHA256 … · RUN-…`) and report line (`SociomappingView.tsx:383 @ ce25a1b8`) print the run id
     outside `map-tech`. Reproduction: `node tools/ui_workbench/sociomap_journey.mjs` after `--prepare` on a
     fresh workbench. Smallest fix: on the stage, those two lines go inside a Technické údaje disclosure.
     The test that catches it is this journey check. Owner: the map-first stage (SOC9-SOC11).
  2. "nothing written but the stage opened": opening Výsledky now POSTs `…/report/editor` twice
     (`lib/api.ts:1428 @ ce25a1b8`, the report editor). The same reproduction. Smallest fix: open the editor
     session on the person's action, not on the page's load; the same journey check catches it. Owner: the
     report editor.
  Both fail with develop's own journey on the same workbench; neither is changed here.
- **Open, Sociomapa's to fix: `ux_journey.mjs`'s classic 3D-camera check fails on every run since #598.**
  1. `tools/ui_workbench/ux_journey.mjs:91-101 @ ddecb4e4` clicks "3D terén", opens "Ovládání 3D pohledu" and
     "Otočit vpravo" on `object-map-3d`: the older map's controls (`ObjectMapView`). A new run pins
     `aia-sociomap-5` (#598), drawn by `ObjectMapPanel`, which has none of them: its camera is the view rail's
     2D / 3D and a drag on the canvas, its state `data-camera` on `object-map-canvas`.
  2. Reproduction: `node tools/ui_workbench/ux_journey.mjs` after `make ui-fixtures` + `make ui-research` on a
     fresh workbench (reported by the Výsledky session, 2026-10-26).
  3. Consequence: the journey stops at the map, so its later checks (keyboard, reload, the mobile menu) are
     not run on develop.
  4. Smallest fix: on the `-5` map, press the rail's "3D", drag the canvas, read `object-map-canvas`'s
     `data-camera`, switch tabs and back, and expect the same camera.
  5. Test: the journey itself.

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**SOC11b. Copy pass** (spec `szz/S1`; reopens SOC11; W2, lane F).
- Delivered (2026-10-26): no Stress-1 on the stage (the older view's badge says the fit in words only;
  `fitMeaning` explains it without the statistic's name); no "PROGRESS D6" in the internal note; "Top vztahy"
  is "Nejsilnější vztahy na mapě"; "potvrzené v kroku 3" is "kterou sada uvádí v Dotazníku"; the Q5-Q7 and
  audit-author wording of the provisional note is plain. `registerComputed` is not dead (the ⓘ box builds the
  key, `ObjectMapPanel.tsx` `Registers`): its "Deterministický výsledek" reads "Spočtený výsledek". Tests:
  `ObjectMapPanel.test.tsx` › "speaks to a researcher, not in the workshop's jargon";
  `ObjectMapView.test.tsx` › "labels the fit in words…". Not here: Settings → Metodika keeps Stress-1 (the
  methodologist's); Zpráva's map caption (`ReportDocumentView.tsx:655`) is Zpráva's.

**SOC14. Segments are descriptive** (spec `szz/S2`; W2, lane F). Beside SOC6.
- Delivered (2026-10-26): under the found segments, below the map (`MapExplained`), "Skupiny jen popisují, jak se
  respondenti na této mapě liší; srovnání segmentů AIA zatím neumí a analýza s nimi nepracuje.", matching
  readiness's `segments_unavailable`. A map without segments says nothing of them. Test: `MapExplained.test.tsx` ›
  "the taste segments, as what they are". The same sentence in the `-5` panel's own segment legend
  (`ObjectMapPanel.tsx` `segmentLines`, also drawn into the PNG export's legend card) is the methodology owner's
  call, inside the panel's drawing: put to him, not built.

**Notes.**
- SOC4 carries `szz/S3`; SOC5 `szz/S4` (with `artifact-report#RPT10`, `lead-orchestration#LO5a.3`); SOC8 `szz/S6`.
