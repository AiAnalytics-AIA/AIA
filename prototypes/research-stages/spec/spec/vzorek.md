# Vymezení vzorku: Cílová skupina, Dimenze, Vzorek

This section of the build spec turns three approved prototype boards into the product:
`canvas/project/Audience.dc.html`, `Dimensions.dc.html` and `Sample.dc.html`, with decisions R1–R16
from `Main.dc.html:154-169`.

**Code anchors.** All anchors are `@ bd0d1ad6` (develop) unless marked. Abbreviations:
- `R/` = `apps/web/src/components/rehome/research/`
- `WB/` = `apps/web/src/components/workbench/`
- `D/` = `packages/aia_core/src/aia_core/domain/`
- `API/` = `apps/api/src/aia_api/routers/`

**The boards' own critiques.** The "Dnes v AIA" lists anchor d5d36b25. I re-checked them on
bd0d1ad6. Where develop has moved since, this file says so.

**Scope.** This file covers each stage's body, its header action and its Lead `+` menu. It does
not cover the shell, the Lead conversation, the phase navigator or the budget meter: those belong
to the shared frame (`WB/Workbench.tsx:820-852`). Visual tokens are out of scope. Only missing
layout primitives are listed (§0.3).

---

## 0. Cross-cutting

### 0.1 Decisions that apply here

**R3: N is set on Vzorek** (`Main.dc.html:156`).
- What changes:
  - The sample-size stepper moves off Dimenze. Today it is at `R/PersonaStep.tsx:332-369`, marked
    `sample:n`.
  - It goes onto Vzorek §01. Today that section is read-only, with "Upravit v Dimenzích" at
    `WB/SampleView.tsx:126-132`.
- What follows from it:
  - **The Lead's `set_n` lands on Vzorek.** Today `editStage` sends `set_n` to `"dimensions"`
    (`apps/web/src/lib/lead.ts:470`), so the Návrhy Vedoucího bar (`WB/Workbench.tsx:879`,
    mounted `:846`) shows the change on Dimenze.
  - **The contract row must change.** `ARTIFACTS.sample` has `edits=False`
    (`D/lead_artifacts.py:322-333`; web mirror `apps/web/src/lib/workbench-artifacts.ts:104-105`).
    Change it to `edits=True`. Then decide what `dimensions.edits` means while `dimensions_set` is
    still DECLARED (`D/edit_ops.py:853-854`). Recommendation: keep `edits=True`, because WCE10
    owns it.
  - **The sample:n target needs no change.** `stage_of("sample")` is already `sample`
    (`D/lead_artifacts.py:428-434`), and `sampleAia.n()` already lives on Vzorek
    (`apps/web/src/lib/artifacts/sample.ts:25-26`).

**R4: Cílová skupina is one choice of three** (`Main.dc.html:157`).
- The three options:
  - **Celá ČR 18+** is `chooseAudience(…, "population")`.
  - **Zúžit** is `"filters"`.
  - **Najít ve výsledcích** is `"discover"`. It is shown disabled, with the reason "AIA tuto cestu
    zatím neumí".
- Backing: `apps/web/src/research/audience.ts:77-91`.
- **Two questions on today's screen disappear.**
  - "Odkud mají respondenti pocházet" (own / analytics) and "Která populace" (cz18 / cz_coming /
    special) are gone (`R/AudienceStep.tsx:171-228`).
  - Both are `ui_state` only (`audience.ts:64-106`). The new screen always writes
    `audience_entry: "analytics"` and `analytics_choice: "cz18"`, so `audienceReady` stays true
    (`audience.ts:46-55`).
- **Stored studies the new screen must still read.** A study can be stored with any of:
  - `audience_entry: "own"` plus a `dataset_id`;
  - `analytics_choice: "special"` plus `builtin_subpanel`;
  - `strategy: "discover"`.

  The rule: a stored `builtin_subpanel` reads as Zúžit with that subpanel's filters, which are
  already copied there (`audience.ts:129-155`). A stored own dataset or a stored discover strategy
  shows a one-line note that it is kept but not used. That note replaces today's `NotInAia`
  (`R/AudienceStep.tsx:96`).

**Related decisions.**
- **R9** (unsupported features are disabled with a reason) also hits Vzorek's brand-pair forecast
  (§3.4, gap V-1).
- **R13** (the amount is bold inside the button) applies to "Zvýšit na N 500 · strop +x USD".
- **R15** (the `+` menu actions follow `lead_artifacts.py`) is checked in §0.2.

### 0.2 The Lead's per-stage contract against the prototype

| Stage | Contract today (`D/lead_artifacts.py`, mirror `workbench-artifacts.ts:86-110`) | Prototype shows | Delta |
|---|---|---|---|
| audience | `:298-308`: edits **False**; view `open_stage, focus`; targets `audience`; starts `propose_audience`, `answer_memory`; refusal "náhled vrací jen počty" | `+` menu: "Navrhni audienci", "Zeptej se na klientské znalosti". Lead card "Návrh audience" with Popis before/after and Kritéria, accepted *on the card* (Odložit / Přijmout / Vrátit) | Starts match. Card accept is backed: the AUD5 diff (`apps/web/src/research/audience-proposal.ts:31-40`) via ResearchAgentJobs.accept. Gap: the prototype's criteria read like filters ("+ Konzumace piva: aspoň 1× týdně"), but the worker proposes the description plus text inclusion/exclusion criteria, never filters (`audience-proposal.ts:1-4`; master plan G23, `.planning/plans/mvp-master-plan.md:474`). Show criteria as text until WCE10's `audience_set` (`D/edit_ops.py:851`, DECLARED). "Vrátit" after an accept is **NO BACKEND** (no undo of an accept; see A-gap 4). New parts: `audience:strategy` (hypothesis id) and the `audience:preview` that becomes the Proveditelnost section. `_AUDIENCE_PARTS` must stay in sync (`D/research_lead.py:610`) |
| dimensions | `:310-320`: edits True; view `+show_diff`; targets `dimension`, `own_dimension`; starts `suggest_dimensions`, memory | `+` menu: "Navrhni dimenze", memory. Lead reply with "Ukázat: Reakce na reklamu" (a catalogue dimension that is **not chosen**) and the follow "Navrhni dimenze z celého návrhu". Edits bar "Vedoucí navrhuje 1 změnu · Přidat dimenzi … · Přijmout vše" | Starts match. Focusing a catalogue row needs `dimension:<id>` on catalogue rows too; today only chosen rows are marked (`R/PersonaStep.tsx:240`). The edits bar exists (`WB/Workbench.tsx:879-892`), but no applied op adds a dimension: `dimensions_set` is DECLARED (`D/edit_ops.py:853`), and `suggest_dimensions` returns an empty list (G23). So "Přijmout vše" on a dimension is **NO BACKEND** until WCE10 |
| sample | `:322-333`: edits **False**; view `+inspect`; targets `sample`; starts memory only | `+` menu: memory only. Reply with "Ukázat: Odhad dat" (`sample:forecast:support`) and "Ukázat: Velikost vzorku" (`sample:n`) | Starts and targets match. With R3, `edits` becomes True and `set_n` is listed here (fixture `packages/aia_core/tests/fixtures/lead_artifacts/contract.json`, test `packages/aia_core/tests/test_lead_artifacts.py`, web `workbench-artifacts.test.ts`) |

The `+` menu prices ("do 0,30 USD", "do 0,20 USD") are a **hypothesis**. A worker's reservation
probably comes from `AIA_AI_RESEARCH_RESERVATION_USD`. Show what the server quotes, never a
constant.

### 0.3 Missing layout primitives (no tokens proposed)

1. **Numbered section with a header aside.** The `sec / sh / num` pattern draws "01 Title ·
   aside". `StepSection` deliberately does not draw `n` (`apps/web/src/components/rehome/step.tsx:21-22`).
   `SampleView` has its own `Sec` that does (`WB/SampleView.tsx:37-48`). Unify them into one
   primitive used by all three stages.
2. **List row** (`li`): a leading glyph or icon, a title with a muted suffix and a caption line,
   and a trailing action (a remove "×" or a button). Each stage hand-rolls this today.
3. **KPI tiles** (`kpis / kpi`): caption, big value, caption. Used by Proveditelnost and by
   Vzorek §02. Absent today.
4. **Link card**: a row with an icon, title, caption and chevron. Used by Vzorek §01 for Cílová
   skupina and Dimenze.
5. **Legend row** for the three check states (Vzorek §03).
6. **Segmented single choice with a disabled option.** `ChoiceChips` with `disabled` per option
   (`apps/web/src/components/ui/ChoiceChips.tsx:16`) covers it. The disabled option's reason is a
   caption below, not a tooltip.
7. **Undo toast.** It exists: `UndoToast` / `useUndo` (`apps/web/src/components/ui/UndoToast.tsx:29,36`).

### 0.4 One stage header (all three)

**Prototype.** `h1`, then "Uloženo", then the stage's own status, then a primary "next stage ›"
button.

**Today.**
- The frame header has the title, save state and the Připravenost toggle
  (`WB/Workbench.tsx:822-834`).
- The forward action is in each stage's `ActionDock` at the page foot:
  - `R/AudienceStep.tsx:248-258`;
  - `R/PersonaStep.tsx:410-420`;
  - `WB/SampleView.tsx:195`, "Pokračovat na Sběr dat".

**Chunk H1 (new).** Render `FrameNavigation.next` (`apps/web/src/components/rehome/step.tsx`,
`FrameNavigation`) as the header's primary button inside the workbench, and drop the dock button
there.
- Stage status slot:
  - Dimenze shows "N dimenzí včetně sociodemografie";
  - Vzorek shows the readiness pill (§3).
- Test: `ResearchScreen.workbench.test.tsx` gets "the header's next opens the frame's next stage;
  no dock button inside the workbench".

---

## 1. Cílová skupina (Audience)

### 1.1 What the prototype shows (`Audience.dc.html`, body `<main class="art">`)

0. **Header.** "Cílová skupina", Uloženo, and the primary button "Dimenze ›".
1. **Source note** (`note sig`). "Respondenti: AI respondenti z populace AIA · Česko 18+, živá
   verze." with the caption "Vlastní panely a speciální skupiny AIA zatím nemá." No version ids, no
   badges.
2. **§01 Koho mají výsledky reprezentovat?**
   - A segmented radiogroup: **Celá ČR 18+** / **Zúžit** / **Najít ve výsledcích** (disabled).
   - A caption that explains the chosen option. The disabled one says why.
   - The field "Popis vlastními slovy" (free text).
3. **§02 Zúžení** (only under Zúžit). The aside shows "N faktory".
   - **Filter rows.** Each row has an icon, then "**Factor** · value", the caption "samo vybere
     X lidí · kliknutím upravíte", and "×" to remove (undo toast "… odebrán." with Vrátit).
   - **Clicking a row edits it in place.**
     - A numeric factor gets two steppers, Od and Do, with "meze populace 18–80".
     - A categorical factor gets value chips (`aria-pressed`).
   - **"Přidat faktor"** offers chips for a few likely factors.
   - **Catalogue search** is a real `type=search` field: "nebo hledat v katalogu (48 faktorů)…".
     - Each result has a Přidat button, disabled with "Přidáno" or "Nelze filtrovat" and its
       reason (e.g. "zatím jen pro výzkum, ne k filtrování").
     - No match reads "V katalogu není „q“… popište ho slovy v popisu".
   - **Mismatch note.** When the description stops matching the filters, a neutral warning glyph
     appears with the sentence and an "Upravit popis" button.
   - **"Hotové skupiny"** are chips for the built-in subpanels, e.g. "Pivaři (časté pití)".
4. **§03 Proveditelnost.** It is `aria-live`, with the aside "přepočítává se při každé změně".
   Three KPI tiles:
   - "V populaci vybráno: 3 690 · lidí z 9 840";
   - "Vzorek: N 400 · upravit na Vzorku" (a link);
   - "Lze vytáhnout: **Ano** / **Těsně** / **Ne**", each with a glyph (done / neutral warn /
     fault) and a reason ("N 400 vytáhneme s rezervou" / "kvóty nemusí vyjít…" / "méně lidí než
     vzorek; uberte faktor").
5. **Lead card** (left pane) "Návrh audience": eyebrow "Návrhová úloha · hotovo · stálo 0,22 USD",
   Popis struck-through then the new one, Kritéria +/−, and the buttons Odložit / Přijmout.
   After a decision it shows a note and Vrátit.

### 1.2 Today on develop

**Which component renders what.**
- **`AudienceStep`** (`R/AudienceStep.tsx:134-262`) draws three `StepSection`s:
  - "Odkud…" with radio cards own / analytics (`:171-193`);
  - "Která populace" with cz18 / cz_coming / special (`:196-227`);
  - strategy population / filters / discover (`:231-246`), with discover **enabled**.
- **`Summary`** sits in the inspector slot (`:160-162`, `:660-701`).
- **The banner** shows for analytics (`:165-170`).

**Filters.**
- `FilterEditor` (`:285-375`): the description field plus an AI start hidden under
  `leadOwnsAiStarts` (`:330-333`); chips with "×" (`:338-357`); `filterProblems` notes
  (`:358-371`).
- `LiveFilters` (`:378-412`): category chips, a search field, and **the whole catalogue of
  `FactorEditor`s rendered as a list** (`:404-410`), with `Preview` at the bottom (`:411`).
- Per-factor editors already exist: `RangeEditor` with bounded steppers (`:423`) and `ValueChips`
  (`:503`).

**Preview.** `Preview` (`:544-582`) runs **on a button press only** (`:564-566`) and keeps a stale
answer after a filter changes. Its words are `liveVerdict` (`apps/web/src/research/audience.ts:695-707`).
**Per-filter counts are already served and shown as text lines** (`filterCountLines`,
`audience.ts:687-693`) when there are two or more filters.

**Subpanels.** `Subpanels` (`:585-619`) show only under "special", as radio cards with
"measured by 18.6.6" counts.

**API.**
- `GET /population/audience-catalogue` (`API/population.py:479-556`).
- `POST /population/audience-preview` (`API/population.py:617-662`). It answers:
  - `population_rows`, `selected_rows`, `selected_donors`;
  - `per_filter` (`:609`, domain `D/population/audience_preview.py:70-74`);
  - `sample.ok` / `status` `PASS` | `PASS_WEIGHTED` (`D/population/sampling.py:460-474`), and
    `cells`.

**Differences from the prototype.**
- three questions instead of one choice;
- the whole catalogue instead of chosen rows plus "Přidat faktor";
- a manual preview instead of a live one;
- subpanels under "special" instead of presets inside Zúžit;
- no per-row count or in-place edit;
- no description/filter mismatch check;
- no undo on remove;
- discover is enabled where R4 says disabled.

### 1.3 Build chunks

Run these after `artifact-audience` AUD2 (open) and in place of its body. Each step names its
plan id where one exists.

**A1. One strategy choice (R4).** Plan: AUD2, re-scoped.
- **What changes.**
  - `R/AudienceStep.tsx` drops the sections at `:171-228`.
  - §01 becomes `ChoiceChips` with three options, `discover` disabled.
  - The caption comes from `cs.ts` `research.audience.strategy*Text`, rewritten.
  - The "Popis vlastními slovy" `TextInput` saves `audience.description` through `store.update`,
    debounced like the rest of the copy.
  - A pure `research/audience.ts` `normalizeEntry(p)` writes `analytics/cz18` on the first edit
    and reads the legacy states listed in §0.1.
- **Backed?** Yes: `chooseAudience` (`audience.ts:77-91`), no server change. A stored discover
  strategy still compiles; how the run treats it is unchanged.
- **Test.** `AudienceStep.test.tsx`:
  - "offers three strategies; Najít ve výsledcích is disabled with its reason and cannot be
    chosen";
  - "a study stored as own/special/discover opens readable and says what is kept".

  Pure: `audience.test.ts` `normalizeEntry`.

**A2. The source note.** Plan: new (AUD2 part).
- **What changes.** One line above §01, built from the catalogue's `version_label`
  (`API/population.py:526`) and the readiness `persona_sources` default (see §3). The version id
  stays out of the line; per the prototype it reads "živá verze". The `bannerPopulation` block
  (`:165-170`) is removed.
- **Backed?** Yes.
- **Test.** "the note names the default persona source; without the catalogue it says the
  population is unavailable".

**A3. Chosen filters as rows, with an in-place edit and undo.** Plans: AUD2, `input-interactions#5`.
- **What changes.** In `FilterEditor`, chips (`:338-357`) become rows:
  - "**label** · value text" (`filterChips`, `audience.ts:411`);
  - the caption "samo vybere {per_filter[id]} lidí";
  - the problem state from `filterProblems` stays on the row (`audience.ts:465`).
- **Click to open.** A click opens the existing `RangeEditor` / `ValueChips` inline (one open at a
  time).
- **Undo.** "×" calls `removeAudienceFactor` (`audience.ts:404`) and offers `useUndo`, which
  restores the factor's stored value.
- **Backed?** Yes. `per_filter` comes from A5's preview.
- **Test.**
  - "a filter row opens its editor in place and saves through setRange / setAudienceCategory";
  - "remove offers Vrátit and Vrátit restores the stored values";
  - "the row's count is the preview's per_filter for that factor; unknown says nezjištěno, never
    0".

**A4. "Přidat faktor" plus a real search, replacing the full catalogue.** Plan: new (AUD2).
- **What changes.** `LiveFilters` stops rendering every `FactorEditor` (`:404-410`). It renders:
  - (a) up to three suggestion chips;
  - (b) one search field over `filterableFactors` (`audience.ts:262`). Results are rows with
    Přidat, disabled as "Přidáno" or with the `factorRefusal` reason (`audience.ts:590`). No match
    gives the sentence.

  Adding a factor opens its editor in place (A3). Category chips go away; search covers them.
- **Backed?** Partly. The catalogue is backed. **Which three factors to suggest: NO BACKEND.**
  The prototype's picks are hand-made. Proposal: the catalogue's first filterable factors in
  catalogue order, labelled "časté". A ranking from the brief needs a new API, or the Lead (AUD5).
- **Test.**
  - "search finds Vzdělání and says why it cannot filter";
  - "no match says so in a status region";
  - "the catalogue is not rendered whole".

**A5. Live Proveditelnost.** Plan: new (it supersedes the AUD2 preview wording).
- **What changes.**
  - `Preview` (`:544-582`) loses its button. A `useAudiencePreview(filters, n)` hook (new,
    `R/useAudiencePreview.ts`) calls `population.audiencePreview` 400 ms after the last filter or
    n change, drops stale answers (request id), and keeps the previous answer dimmed while busy.
  - Three KPI tiles:
    - `selected_rows` of `population_rows`;
    - stored N, with a link that opens Vzorek via `frameNav` / `onOpen("sample")`;
    - feasibility.
  - Pure `research/audience.ts` `feasibility(r)`:
    - `sample.ok && status === "PASS"` gives **Ano**;
    - `status === "PASS_WEIGHTED"` gives **Těsně**, with "reprezentativní až po kalibraci vah";
    - `!sample.ok` or `!audience.ok` gives **Ne**, with `verdictWords` (`audience.ts:672`);
    - no n or no preview gives **neznámé**.

    The Těsně mapping is a **hypothesis about meaning**. The prototype's caption "kvóty nemusí
    vyjít" is not what PASS_WEIGHTED says (`D/population/sampling.py:470-474`: raw deviation over
    tolerance, calibrated within it). Use the server's meaning.
  - A 503 `audience_preview_unavailable` or `population_unavailable` says so in the tile.
- **Backed?** Yes: `API/population.py:617-662`.
- **Cost.** Every filter edit costs one POST. The previewer loads LIVE once per process and
  version (CLAUDE.md §2, `application/audience_preview.py`), so each POST is a count plus one
  draw. **Measure the p95 on develop before merge.** If it exceeds 400 ms, the hook keeps the
  previous answer and says "přepočítávám".
- **Test.**
  - `useAudiencePreview.test.ts`: debounce, a stale answer dropped, an error kept as words;
  - `audience.test.ts` `feasibility` for each case, unknown never Ano.

**A6. Built-in subpanels as "Hotové skupiny" inside Zúžit.** Plan: new.
- **What changes.** The `Subpanels` radio cards (`:585-619`) become chips under §02. Choosing one
  calls `applyPopulationSubpanel` (`audience.ts:129-155`), which already sets strategy `filters`
  and copies the filters, so the rows (A3) show what it set. An unusable subpanel is a disabled
  chip with its reason. The "measured by 18.6.6" text leaves the chip and stays in a details
  disclosure, worded without "18.6.6" (the critique's point d4).
- **Backed?** Yes: the catalogue's `subpanels` (`API/population.py:533-554`).
- **Test.**
  - "a subpanel chip sets its filters as rows; an unusable one is disabled with its reason";
  - `audience_journey.mjs`: the subpanel steps move from "special" to Zúžit.

**A7. Description-filter mismatch note.** Plan: new.
- **What changes.** A neutral note under the rows, with "Upravit popis", which writes a
  description generated from the rows (`humanFilters`, `audience.ts:504`).
- **Backed?** **NO BACKEND, and not deterministic.** The prototype matches free text with regex
  heuristics. Proposal: say only what code can prove, which is that the description was written
  before the last filter change. Track this with `audience.description_rev` against the filter
  edit, plus a new `ui_state` field. Semantic mismatch is the Lead's job (`propose_audience`).
  **Owner question Q-A1:** accept the provable version, or drop it?
- **Test.** "after a filter change the note offers Upravit popis; Upravit popis writes the
  filters in words".

**A8. The Lead's card on Cílová skupina.** Plan: AUD5.
- **What changes.** The card shows Popis before/after and inclusion/exclusion criteria (text), from
  `audienceProposalDiff` (`audience-proposal.ts:31`). "Přijmout" accepts through the existing
  agent-job accept. "Odložit" maps to dismiss (R8 wording). No in-stage AI start is left
  (`R/AudienceStep.tsx:330` is already gated).
- **Backed?** Yes, except that "Vrátit" after an accept is **NO BACKEND** (A-gap 4). Criteria as
  filters are **NO BACKEND** until WCE10 `audience_set` is APPLIED (`D/edit_ops.py:851`).
- **Test.** The 26f guard; "an audience card's criteria are listed as text, not as filter rows".

**A9. Journey.** Plan: AUD6.
- `tools/ui_workbench/audience_journey.mjs` at 1440, 1100, 768 and 390:
  - strategy choice, discover disabled;
  - a filter added by search, edited in place, removed and restored;
  - Proveditelnost changing without a click;
  - a subpanel chip;
  - zero paid jobs.

### 1.4 Backend gaps (Audience)

| # | Gap | Anchor | Owner |
|---|---|---|---|
| A-gap 1 | Suggested factors for "Přidat faktor" have no ranking source | catalogue answers order only, `API/population.py:524-531` | new; or the Lead |
| A-gap 2 | No proposal edits filters: `propose_audience` proposes a description plus text criteria; `audience_set` is DECLARED | `D/edit_ops.py:851-852`; `audience-proposal.ts:1-4` | `working-copy-edit-ops#WCE10` |
| A-gap 3 | A description-vs-filters check: nothing compares them | none | new (Q-A1) |
| A-gap 4 | An accepted proposal cannot be undone; Vrátit would be a person's write restoring the prior values (as the auto-accept Vrátit does, CLAUDE.md §2 LeadPane) | hypothesis: no accept-undo route in `API/research.py` | new |
| A-gap 5 | "Najít ve výsledcích" (discover) is not executable | R4 | after MVP |
| A-gap 6 | Assumptions §3 of V2 (AUD4) are not on the approved board; keep AUD4 parked or place it under §01 (owner) | `.planning/plans/artifact-audience.md` AUD4 | Q-A2 |

---

## 2. Dimenze (Dimensions)

### 2.1 What the prototype shows (`Dimensions.dc.html`)

0. **Header.** "Dimenze", Uloženo, the count "4 dimenze včetně sociodemografie" (correct Czech
   plural), and the primary "Vzorek ›".
1. **Edits bar** (`role=region "Návrhy Vedoucího"`): "Vedoucí navrhuje 1 změnu · nic se nezmění,
   dokud ji nepřijmete", Zahodit vše / Přijmout vše, and a change row "Přidat dimenzi Reakce na
   reklamu · Proč: …".
2. **Intro line.** "Dimenze říkají, podle čeho AI respondenti odpovídají… Velikost vzorku je teď
   na Vzorku" (a link).
3. **§01 Co dimenze podpoří** (aside "výzkumné otázky z Návrhu"). One row per research question:
   - a done or attention glyph, "VO1 text";
   - the caption "opírá se o: Vztah ke značkám", or "žádná vybraná dimenze ji nepodpoří; v
     katalogu: X".
4. **§02 Dimenze respondentů** (aside count).
   - A locked row "Sociodemografie · vždy zapnuto: věk, pohlaví, kraj, vzdělání · podpoří VO2".
   - Chosen rows: done glyph, "**name** · doporučeno | z katalogu", the caption "podpoří …", and
     "×" with an undo toast.
   - Requested rows: a parked glyph, "vaše žádost · čeká na schválení ve Znalostech klienta".
   - "Přidat dimenzi": three chips, ranked with RQ-supporting dimensions first.
   - A search field: "nebo hledat v katalogu (N dalších)…". Results are rows with Přidat. No match
     gives "V katalogu není „q“" plus "Požádat o dimenzi", which files a request (toast plus
     Vrátit).
5. **§03 Vlastní dimenze klienta.** A row: done glyph, name, "cíl 0,32 · dosaženo 0,31 · v
   toleranci", and a toggle "Použít v běhu" / "Použije se" (`aria-pressed`) with a note on what it
   does.
6. **No sample size, no AI start button, no "Faktory společnosti" card.**

### 2.2 Today on develop

**`PersonaStep`** (`R/PersonaStep.tsx:125-424`) draws, in order:
1. **"Vybrané dimenze"** (`:230-270`):
   - base row (`:232-235`);
   - chosen rows with source (hard-coded fallback **"Systém"**, `:242`), the persona-topic chip
     (`:243-245`, DIM2 part 1), and "×" with focus handling (`:211-220`) but **no undo**;
   - waiting requests (`:260-268`).
2. **`OwnDimensions`** (`:272`; component `R/OwnDimensions.tsx:18-54`): read-only list; status via
   `CodedWords` (`:34`); a link "use in run" to Sběr dat (`:47-51`).
3. **Catalogue** (`:274-309`): search, then groups Doporučené (with "Použít doporučené",
   `:296`) and Katalog as **toggle checklists**, so a chosen dimension appears both here and in
   "Vybrané" (the critique's duplication).
4. **AI suggestion card** "nové dimenze" (`:311-330`).
5. **Sample size** (`:332-369`):
   - `Stepper` with `data-aia sample:n` (`:335`), bounded by `/research/limits`
     (`R/useSampleLimits.ts`; `API/research.py:1327-1340`);
   - "Použít doporučené N" from the browser's `recommendedSample` (`apps/web/src/research/persona.ts:160-170`).
6. **"Vlastní dimenze" request form** (`:371-402`) and the **dead "Faktory společnosti" card**
   (`:404-407`).
7. **Dock** with `dockNote` "{d} dimenzí · N={n}" (`:410-420`).

**API.**
- `GET …/research/persona-topics` (`API/research.py:1719-1738`) maps through
  `DIMENSION_TOPICS`, which has 2 entries (`D/persona_topics.py:313`).
- Materializations: `POST`/`GET` `…/materializations` (`API/materialize.py:219-283`).
- The run's population choice is a start parameter, `population_version_id`
  (`API/research.py:332`), chosen in `PopulationChoice` (`R/ExecutionSteps.tsx:930`).

**Differences from the prototype.**
- N is here (R3);
- the catalogue is duplicated as a checklist;
- no "Co dimenze podpoří";
- no per-dimension "podpoří …";
- no undo;
- requests come from a separate form, not from an empty search;
- the own dimension cannot be chosen here;
- the dead card;
- "Systém" is hard-coded.

### 2.3 Build chunks

**D1. Remove N from Dimenze (R3, half 1).** Plan: new (it reverses the DIM3 placement; DIM3's
stepper is reused by V1).
- **What changes.**
  - In `R/PersonaStep.tsx`, delete `:332-369`, the `useSampleLimits` and `recommendedSample`
    uses, and `applyRecommendedSample`.
  - The intro line links to Vzorek.
  - Change `dockNote` / the header count to "N dimenzí včetně sociodemografie" with `plural`
    (`apps/web/src/lib/format.ts`). The `cs.ts` key `research.persona.dockNote` is rewritten.
- **Ships with V1, in one PR.** That way N is never on neither stage.
- **Backed?** n/a.
- **Test.** `PersonaStep.test.tsx` "Dimenze has no sample size control; it links to Vzorek". The
  DIM3 tests move to the Vzorek tests (V1).

**D2. One selection list, plus "Přidat dimenzi" and search, with requests from an empty search.**
Plans: DIM2 (part 2), `input-interactions#5`.
- **What changes.**
  - Delete the `DimensionGroup` checklists (`:274-309`, `:427-472`) and the request form
    (`:371-402`).
  - Under the chosen rows: up to three chips from `catalogEntries` minus chosen, recommended
    (`suggestedPersonaDims`) first, then a search over `matchesDimensionSearch`.
  - Results are rows with Přidat. An empty result shows "V katalogu není…" plus "Požádat o
    dimenzi", which calls the existing `request(label, "document_or_research", …)` (`:162-178`).
  - Remove and request both offer `useUndo`. Undoing a request is **NO BACKEND** (D-gap 4); offer
    Vrátit only on remove.
  - The source suffix reads "doporučeno" or "z katalogu" (or the client library label), never
    "Systém".
- **Backed?** Yes: the catalogue is from client knowledge (`useClientDimensions`, `:79-95`) and
  requests go through `workspace.proposeFromStudy`.
- **Test.**
  - "a chosen dimension is listed once; the search does not list chosen ones";
  - "an empty search offers Požádat o dimenzi and files a proposal";
  - "remove offers Vrátit and Vrátit restores it in place";
  - "no row reads Systém".

**D3. "podpoří …" per dimension, and §01 Co dimenze podpoří.** Plan: new (it extends DIM2).
- **Backed?** **NO BACKEND.** Nothing links a dimension to a research question or to questions:
  - a dimension is only a persona-topic allowlist entry (`D/persona_topics.py:313-321`;
    master plan I5 and G30, `mvp-master-plan.md:406, 491`);
  - only 2 dimensions map to a topic at all (`D/persona_topics.py:313`).
- **What can be served honestly.** For each chosen or catalogue dimension, the questions whose
  derived topics (`question_topics`, `D/persona_topics.py:281`) contain `dimension_topic(d)`. RQs
  then follow by the research trace (each item's `research_questions`,
  `D/research_trace.py`). This needs a new field on `GET …/research/persona-topics`:
  `feeds: {question_ids, research_questions}`, computed on the working revision. A dimension with
  no topic reads "v tomto dotazníku nic nepodpoří (bez tématu persony)". Most dimensions will read
  that until the topic map grows, so it is not a guess.
- **Prerequisite:** owner/methodology answer **I5** (what a dimension is; `mvp-master-plan.md:406`).
  Until it is answered, §01 is shown with "nezjištěno", never "opírá se o".
- **What changes.** `PersonaStep` gets §01 (`R/DimensionSupport.tsx`, new) and a caption per row.
  `lib/api.ts` `research.personaTopics` gains `feeds`.
- **Test.**
  - API: "ekologie feeds the questions whose topics include eko; an unmatched dimension feeds
    none";
  - Vitest: "an RQ with no supporting dimension reads the catalogue's candidate only when the
    server names one; unknown never reads supported".

**D4. Vlastní dimenze: chosen here.** Plan: DIM4.
- **What changes.**
  - `R/OwnDimensions.tsx` rows gain "Použít v běhu".
  - Statuses are in words, not `CodedWords` (`:34`, critique d3).
  - The outcome uses `targetVerdict` (already in `lib/own-dimensions.ts`).
- **Backed?** **NO BACKEND for a choice stored before the run.** Today the child is a start
  parameter (`API/research.py:332`) chosen on Sběr dat (`R/ExecutionSteps.tsx:930`). The toggle
  needs:
  - a working-copy field, e.g. `persona.population_version_id`, saved like any edit;
  - readiness (`API/research.py:1397`, which already takes `population_version_id`) and start
    reading it as their default.
- **G28 (`mvp-master-plan.md:484`).** A run over a child draws the same personas, because personas
  read a fixed column list. So "Použije se" must not promise different respondents until G28 is
  closed. **Owner question Q-D1:** ship the toggle before G28, or keep the link to Sběr dat?
- **Test.** "the toggle stores the child; Sběr dat's PopulationChoice opens on it; an unknown
  target never reads v toleranci".

**D5. The Lead on Dimenze.** Plans: DIM5, WCE10.
- **What changes.** Catalogue rows carry `dimensionAia(id)` (`apps/web/src/lib/artifacts/dimensions.ts:10`)
  so "Ukázat: <catalogue dimension>" can focus. The EditsBar renders a `dimensions_set` change row
  once WCE10 applies it.
- **Backed?** Focus on a catalogue row is backed: the grammar only, with no stored-copy check for
  `dimension:` (`D/research_lead.py:614-640`). Edits are **NO BACKEND**:
  - `dimensions_set` is DECLARED (`D/edit_ops.py:853`);
  - `suggest_dimensions` returns no dimensions (G23).
- **Test.** The 26f guard; "a Lead focus on an unchosen catalogue dimension scrolls to its search
  row".

**D6. Remove the dead card and the AI suggestion card.** Plan: new.
- **What changes.** Delete `:404-407`. The `per-new` card (`:311-330`) is the AI start's output:
  under `leadOwnsAiStarts` its content moves to the Lead card (R12/R15).
- **Test.** "no Faktory společnosti card".

**D7. Journey.** Plan: DIM6.
- `tools/ui_workbench/dimensions_journey.mjs` at 4 widths:
  - add by chip and by search;
  - remove plus Vrátit;
  - request from an empty search;
  - no N on the page;
  - zero paid.
- **Rewrite** today's stepper steps (`dimensions_journey.mjs`, "sample size one stepper") to run
  on Vzorek.

### 2.4 Backend gaps (Dimensions)

| # | Gap | Anchor | Owner |
|---|---|---|---|
| D-gap 1 | A dimension has no link to questions or RQs; only 2 topic mappings | `D/persona_topics.py:313`; `mvp-master-plan.md:406` (I5) | new field on persona-topics (D3) after I5 |
| D-gap 2 | Own-dimension choice is a start parameter, not stored in the working copy | `API/research.py:332`; `R/ExecutionSteps.tsx:930` | new (D4) |
| D-gap 3 | An own dimension changes no persona (G28) | `mvp-master-plan.md:484` | `client-knowledge-lifecycle#K5`, `research-lead-workbench#22` |
| D-gap 4 | A dimension request cannot be withdrawn from the study (a knowledge proposal, no withdraw route) | hypothesis: `workspace.proposeFromStudy` has no inverse | new |
| D-gap 5 | No applied Lead edit for dimensions; `suggest_dimensions` is empty | `D/edit_ops.py:853`; G23 | WCE10 |

---

## 3. Vzorek (Sample)

### 3.1 What the prototype shows (`Sample.dc.html`)

0. **Header.** "Vzorek", Uloženo, then the readiness pill:
   - "Lze spustit · 1 upozornění" (done glyph);
   - or "Nelze spustit: rozpočet" (fault).

   Then the primary "Sběr dat ›".
1. **§01 Velikost a složení.**
   - **Size row** (it takes the `mark` highlight when the Lead points at it):
     - "Velikost vzorku";
     - the caption "meze 300–2 000 po 50 · doporučeno 500, aby mapa měla dost dat u všech
       dvojic";
     - the caption "Strop běhu při N 400: **13,80 USD** (horní mez, ne odhad) · ve studii zbývá
       38,80 USD";
     - a stepper "N 400" (−/+ 50, disabled at the bounds).
   - **Two link cards:** "Cílová skupina · Pijáci ležáku 18–65 · 2 faktory" and "Dimenze · names".
   - **Quota table** "Složení podle kvót · pohlaví × věk × kraj": Skupina / Podíl / Respondentů,
     6 rows, the line "Dalších 34 skupin", and the caption "Kvóta říká, kolik lidí každé skupiny
     vytáhneme; neříká, že odpoví na každou otázku." The counts recompute with N.
2. **§02 Kolik dat bude za čísly** (`#forecast`, aside "odhad před během, ne výsledek").
   - **A note** (warn or ok): "**Mapa značek:** 2 z 21 dvojic budou mít méně než 30 lidí
     (Zlatá Hora × Radegast, …)", plus the sentence on what 30 means, plus the button "Zvýšit na
     **N 500** · strop +3,45 USD".
   - **KPI tiles:** Zodpověditelné otázky 18 / Ohrožené 3 "málo lidí zná značku" / Nelze říct
     předem 1 "otevřená otázka".
3. **§03 Připravenost ke spuštění.**
   - A legend: V pořádku / Upozornění: běh poběží / Brání spuštění.
   - Check rows: glyph, text, caption in words, and at most one fix (a link "Opravit v Dotazníku",
     or the action "Zvýšit na N 500").
   - The budget check is **"Brání spuštění"** when the ceiling exceeds what remains.
4. **§04 Kdo bude odpovídat.** One row: "AI respondenti z populace · výchozí · Česko 18+, živá
   verze. Fiktivní respondenti jsou jen pro zkoušku." and "Změnit ve Sběru dat".

### 3.2 Today on develop

**`SampleView`** / `SampleArtifact` (`WB/SampleView.tsx:31-158`) is read-only by design
(`:3-7`). It is mounted at `WB/Workbench.tsx:849`, with Dimenze hidden beside it (`:850-851`).

**§1** (`:126-143`):
- "N = n" with "Upravit v Dimenzích" (`:131`);
- the browser recommendation (`:130`);
- the audience description and filter count, with a link (`:133-137`);
- dimension chips from `PERSONA_DIM_LABELS` (`:140`; an own dimension's raw id, critique d2);
- `Composition` (`:83-111`) from `compositionOf` (`apps/web/src/lib/sample-view.ts:150`): 10 cells
  plus `<details>`.

**§2** (`:144-151`):
- "Opora výsledků" from `supportForecastOf` (`sample-view.ts:27`), the server's
  `support_forecast` check;
- "Na co běh odpoví" from `outlookSummary` (`sample-view.ts:40`), four verdicts.

**§3 `Ready`** (`:162-200`):
- checks with glyph tones; the `title` is PASS / WARN / FAIL (`:182`, critique d4);
- a stage link per check (`checkStage`, `sample-view.ts:91`);
- "Pokračovat na Sběr dat".

**§4 `Respondents`** (`:239-274`): every source, and "Změnit ve Spuštění" (`:269`). The same step
also goes by "Sběr dat" (critique d3).

**Data.** `useSampleReadiness` (`WB/useSampleReadiness.ts:33-66`) flushes the person's pending
save and reads `GET …/research/readiness/working` (`API/research.py:1386`) whenever the revision
moves. The readiness body (`apps/web/src/lib/api.ts:997-1034`) carries:
- `cost_ceiling_usd` / `cost_ceiling_unknown`;
- `spend_confirm_usd`;
- `question_outlook`;
- `persona_sources`;
- `sample_composition` (filled at `API/research.py:1475-1520`).

The study's `remaining_usd` is on the Study (`apps/web/src/lib/budget-line.ts:9`).

**Differences from the prototype.**
- no N control (R3);
- no ceiling or remaining beside N;
- no pair forecast;
- the recommendation is the browser's;
- checks are worded as status codes, with links only;
- the budget is not a check;
- §4 lists every source instead of the default;
- two names for one step.

### 3.3 Build chunks

**V1. N stepper on Vzorek (R3, half 2).** Plans: new; the DIM3 stepper moves here; SMP2 reopens.
- **What changes.**
  - `WB/SampleView.tsx` §1 replaces `:127-132` with the `Stepper` from `R/PersonaStep.tsx:336-345`
    (bounded by `useSampleLimits`, step 50, refused outside, never clamped, `data-aia
    sample:n`). It writes through `setSampleSize` (`apps/web/src/research/persona.ts`), using
    `store`, which `SampleView` already receives (`:32`).
  - **The SampleArtifact read-only rule is dropped for N only.** Update the comment at `:3-7`.
  - Bound text "meze {min}–{max} po 50" comes from `/research/limits`, never the prototype's 300–2
    000 (the server's absolute bounds are `D/research_design.py:98`, 20–10 000; methodology limits
    narrow them).
  - The browser's `recommendedSample` (`persona.ts:160-170`) is removed from Vzorek (V3 replaces
    it).
  - Contract: `ARTIFACTS.sample.edits = True`, `ARTIFACTS.dimensions` unchanged (§0.1), and
    `lib/lead.ts:470` `set_n` maps to `"sample"`. The contract fixture and the TS mirror are
    updated together.
- **Ships with D1.**
- **Backed?** Yes. `set_n` is APPLIED (`D/edit_ops.py:821-822`), and readiness re-reads on the
  new revision (`WB/useSampleReadiness.ts:53-65`).
- **Test.**
  - `SampleView.test.tsx` "N steps by 50 within the server's limits, 5001 refused at the field
    and not saved; readiness is read again on the new revision";
  - `test_lead_artifacts.py` / `workbench-artifacts.test.ts`: the sample row edits;
  - `lead.test.ts`: "set_n's edit is shown on Vzorek";
  - `lead_journey.mjs` or `workbench_journey.mjs`: the Lead's set_n appears in Vzorek's
    EditsBar.

**V2. Ceiling and remaining beside N.** Plan: new.
- **What changes.** The caption "Strop běhu při N {n}: {cost_ceiling_usd} (horní mez, ne odhad) ·
  ve studii zbývá {remaining_usd}". An unknown ceiling reads `cost_ceiling_unknown` in words, never
  0. Reuse `budgetLine` (`apps/web/src/lib/budget-line.ts:21`) for the remainder, and read the
  Study the way `BudgetLift.tsx:61` does.
- **Backed?** Yes: `API/research.py:1488-1489`.
- **Test.** "the ceiling follows N after the readiness re-read; unknown never 0,00 USD".

**V3. Server recommendation and the "Zvýšit na N x" action.** Plan: new (SMP3 follow-up).
- **What changes.** "doporučeno {x}" plus a button "Zvýšit na **N x** · strop +Δ USD" (R13) on
  §02's note and on the matching §03 check. A click calls `setSampleSize(x)`.
- **Backed?** **Partly.**
  - The smallest sufficient n exists only inside a check message: `reportable_n`
    (`D/support_forecast.py:87, 198, 226`). It is for per-question donor support, **not** for map
    pairs. Expose it as a field (`support_forecast.reportable_n`) on readiness.
  - **The Δ ceiling at another n is NO BACKEND.** The ceiling is computed for the stored n only
    (`API/research.py:1465-1473`). The web must not extrapolate. Proposal: a new query
    `…/research/readiness/working?n=` that returns `cost_ceiling_usd` without writing, or drop the
    Δ and show the new ceiling after the re-read.
- **Test.** API: "reportable_n is served when the forecast finds one, null otherwise". Vitest:
  "the action shows the server's n; with none, no recommendation is shown".

**V4. §02 Kolik dat bude za čísly.** Plan: SMP3 rework.
- **What changes.**
  - Retitle the section.
  - The KPI tiles come from `outlookSummary` (ANSWERABLE → Zodpověditelné, AT_RISK → Ohrožené,
    UNKNOWN → Nelze říct předem; **UNANSWERABLE is kept as a fourth tile when it is non-zero**,
    since the prototype omits it). A tile's caption is the dominant reason from `question_outlook`
    reasons, in words.
  - "Opora výsledků" is reworded (the critique's point d4) as the sentence from the
    `support_forecast` check.
- **The "Mapa značek: k z m dvojic pod 30 lidmi (A × B…)" note is NO BACKEND and contradicts
  R9.**
  - Pair support from people who know both brands needs a familiarity forecast.
  - AIA cannot ask a familiarity-gated set (`D/question_outlook.py:57-58`).
  - The only map check is n against `pair_n_min` (`D/research_design.py:1524-1537`).
  - **What to build now:** the `sociomap_support` check's own sentence. Label pair-level support
    "ověří se až z dat (Sociomapa)", as `WB/SampleView.tsx:146-150` does today.
  - **Owner question Q-V1:** keep the pair note as a disabled-with-reason line (R9), or wait for a
    pair-forecast API?
- **Test.**
  - "tiles count the server's verdicts, UNANSWERABLE shown when non-zero, unknown when the
    outlook is absent";
  - "no pair count is shown without a server field".

**V5. §03 Připravenost in words, with one fix per check.** Plan: SMP4 rework.
- **What changes.**
  - In `Ready`, the legend becomes `PASS` → "V pořádku", `WARN` → "Upozornění · běh poběží",
    `FAIL` → "Brání spuštění". The glyph `title` loses the codes (`:182`).
  - Each row gets a caption, and a fix button named "Opravit v {stage}" where `checkStage` names a
    stage (`sample-view.ts:91`), or the V3 action for the support/sociomap checks.
  - The aside becomes the header pill (H1): "Lze spustit · k upozornění" / "Nelze spustit:
    {first blocking}", from `readinessSummary` (`sample-view.ts:112`). The server's `ready`
    decides.
- **Budget row.** Add a client-side row from `cost_ceiling_usd` against `remaining_usd`.
  - **It must not say "Brání spuštění".** The start does not consult the study budget: it stops at
    reservation and parks for a lift (`D/money.py:333-336`, docstring "The study's budget is not
    consulted here").
  - Proposal: WARN, "Strop běhu je víc, než ve studii zbývá: běh se zastaví a počká na navýšení
    rozpočtu", with a link to the budget lift. When the wallet is on, a start can be refused
    `outside_wallet` (`D/money.py:357-358`); show that as blocking only from a server field.
  - **Settled Q-V2 (B1, Nigel, 26 Oct): yes.** The study budget stops a run before it starts: a FAIL
    readiness check "Brání spuštění" when the run's ceiling exceeds what remains in the study, and
    the start refuses the same way. Backend change: a new readiness check and the start's own check
    (`D/money.py:333-336` today consults no budget).
- **Test.**
  - "checks read in words, never PASS/WARN/FAIL";
  - "a check with a stage has one Opravit button that opens it";
  - "a ceiling above the remainder is a warning that says the run will wait, not a block".

**V6. Composition table and link cards.** Plan: SMP2 rework.
- **What changes.**
  - Columns are renamed Skupina / Podíl / Respondentů. The first 6 rows show, then the "Dalších k
    skupin" disclosure. The caption is the prototype's.
  - The heading lists the quota fields from `sample_composition.quota_fields`. It recomputes after
    N because readiness re-reads.
  - Link cards for Cílová skupina (description · k faktory) and Dimenze (names) replace the text
    blocks at `:133-141`.
  - Dimension names come from the labels Dimenze uses (`dimensionLabels`), and an own dimension
    from its materialization name, never the raw id (critique d2).
- **Backed?** Yes (`apps/web/src/lib/api.ts:1036-1047`). Own-dimension names need
  `population.materializations` (`API/materialize.py:266`).
- **Test.**
  - `sample-view.test.ts`: "rows past six fold";
  - `SampleView.test.tsx`: "the Dimenze card names an own dimension by name".

**V7. §04 one line.** Plan: SMP5 rework.
- **What changes.** Show the default offered source (`personaSourcesOf`, `sample-view.ts:52`), its
  help text, and "Změnit ve Sběru dat" (one name; `:269` "Spuštění" becomes "Sběr dat"). The
  non-default sources fold into a details disclosure, which keeps the unoffered reasons readable.
- **Backed?** Yes.
- **Test.** "the default source is the one row; the rest are in Další zdroje; the step is named
  Sběr dat".

**V8. Journey.** Plans: SMP6, `sample_panel_journey.mjs`.
- At 1440, 1100, 768 and 390 px:
  - N stepped, then the ceiling, the composition and the forecast re-read;
  - Lead focus on `sample:n` and `sample:forecast:support` highlights the element;
  - zero paid jobs.

### 3.4 Backend gaps (Sample)

| # | Gap | Anchor | Owner |
|---|---|---|---|
| V-gap 1 | No brand-pair support forecast; familiarity cannot be asked | `D/question_outlook.py:57-58`; `D/research_design.py:1524-1537` | new, after R9 is lifted (Q-V1) |
| V-gap 2 | `reportable_n` only inside a message | `D/support_forecast.py:87, 198, 226` | new field (V3) |
| V-gap 3 | Ceiling at a hypothetical n | `API/research.py:1465-1473` | new query (V3) |
| V-gap 4 | The budget is not a readiness check; the start does not consult it | `D/money.py:333-336` | Settled (B1): make it one |
| V-gap 5 | The contract row `sample.edits=False` vs R3 | `D/lead_artifacts.py:322-333` | V1 (fixture plus mirror) |

---

## 4. Order and owner questions

**Order.**
1. H1.
2. A1 → A2 → A3 → A5 → A4 → A6 → A8 → A9 (A7 waits on Q-A1).
3. D1 + V1 together.
4. Then: D2 → D6 → V2 → V5 → V6 → V7 → V4 → D5 → D7 → V8.
5. Behind backend work:
   - D3 (I5 plus a new field);
   - D4 (Q-D1, D-gap 2);
   - V3 (V-gaps 2 and 3).

**Open owner questions.**
- **Q-A1:** the mismatch note, provable-only or dropped.
- **Q-A2:** Předpoklady (AUD4) are absent from the board.
- **Q-D1:** the own-dimension toggle before G28.
- **Q-V1:** the brand-pair note under R9.
- ~~Q-V2~~ settled (B1, 26 Oct): the budget blocks a start.
