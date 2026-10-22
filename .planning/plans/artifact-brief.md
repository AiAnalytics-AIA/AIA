---
status: in-progress
chunks:
  - "[x] BRF1. The Brief's contract as data: its view operations, its pointable element ids and V2's interaction contract, registered in research-lead-workbench 14's vocabulary and 16's target table"
  - "[ ] BRF2. The Brief body as V2 draws it: Cíle, Rozhodnutí, Kontext and Podklady as items edited in place over the working copy, autosaved"
  - "[ ] BRF3. Podklady with their data class: the attachments and picked client sources served with the class material_rules gives them, shown as chips; links and removal with undo"
  - "[ ] BRF4. The Lead on the Brief: analyze_brief as a Lead card, its proposal inline, the stage's own AI start removed"
  - "[ ] BRF5. What the Brief hands on, in its inspector (Vstupy, závislosti a původ): the readers of each field, from the chain manifest"
  - "[x] BRF6. Journey: the Brief at 1440, 1100, 768 and 390 px with the scripted Lead and zero paid jobs"
---
# Artifact: Zadání (Brief)

Umbrella: `research-lead-workbench#18` (with Návrh). The chain this artifact feeds into the draft
report is [`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md).
Anchors are `file:line @ 25f26232` (origin/develop) unless stated; the prototype is
`prototypes/research-lead-v2 @ 9b50963f`.

## 1. What it is, and its single job

**Its job: state what the client needs to decide, and what the study has to work from.** Every
later stage reads it; nothing it holds is a result.

V2 draws it in `BriefArt` (`prototypes/research-lead-v2/src/artifacts/DesignStages.tsx:12-31`)
over the fixture's `BRIEF` (`src/model/fixture.ts:37-60`). It has five numbered sections:

- Cíle (`obj`), movable items;
- Rozhodnutí, která má výzkum podpořit (`dec`);
- Kontext (`ctx`);
- Podklady (`mat`), each with its data-class chip and the aside "třída dat určuje, kam smí". The
  upload itself is marked `Unavailable kind="simulated"`: in AIA it goes through Přidat podklady;
- Předpoklady (`ass`).

Every item is an `Item` (`src/components/ui.tsx:52`): edit in place, remove, move, and `AddItem`
(`ui.tsx:108`). The AI contract is `CONTRACTS.brief` (`fixture.ts:405`):
- readable: objectives, decisions, context, materials with their class, assumptions;
- visual: `open(brief)`, `focus(item)`;
- domain: `propose(brief, ops)`, `working.save`, `working.accept`;
- refusal: a confidential material is never sent to a public search.

## 2. What exists today

- **The screen.** `BriefStep` (`apps/web/src/components/rehome/research/BriefStep.tsx:79`):
  - the goal textarea (`#brief-goal`, `:144`), the title with "Navrhnout z cíle" (`:170`) and the
    problem type grid (`#brief-type`, `:185`);
  - five optional context fields (`ContextFields`, `:300`, `#brief-context`), files and links
    (`Attachments`, `:424`, `#brief-files`), and a readiness score (`Readiness`, `:244`);
  - the stage's own AI start, "Analyzovat zadání" (`AiButton`, `:135`). It starts the
    `analyze_brief` job, whose result fills the plan.
- **The data.** The study's working content, loaded and saved through
  `GET`/`PUT /studies/{id}/workspace/content` (`apps/api/src/aia_api/routers/workspace.py:2078,
  2093`) by the store (`apps/web/src/research/store.ts`, a 1.8 s autosave). The brief's model is
  `apps/web/src/research/brief.ts`. Files are working-project artifacts
  (`workspace.py:2174`).
- **What V2 places in the Brief but AIA keeps in Návrh.** Objectives, research questions and
  hypotheses are `plan.objectives`, `plan.research_questions` and `plan.hypotheses`
  (`packages/aia_core/src/aia_core/domain/edit_ops.py:181`), with stable ids (`working-copy-edit-ops#WCE1`,
  done). "Rozhodnutí" is the one text field `decision_use` (`edit_ops.py:174`).
- **Today's pointing.** The Lead focuses `brief:<field>` (`domain/research_lead.py:205`), and the web
  maps it to `#brief-<field>` (`apps/web/src/lib/lead.ts:422-433`).

## 3. Gaps between today and V2

| # | Gap | Kind |
|---|---|---|
| B-1 | Cíle shown in the Brief, as items, from `plan.objectives` (today only in Návrh's narrative) | data exists |
| B-2 | Rozhodnutí as an item: `decision_use`, one text (D-44 took the question chain out, so no decision list is added) | data exists |
| B-3 | Kontext: the goal and the four `briefing.*` fields as items edited in place (I1), not raw textareas | data exists |
| B-4 | Podklady with their data class. The class is computed on the server (`domain/material_rules.py`) and not served with an attachment or a picked client source | needs a new API |
| B-5 | A client dataset or document picked as material, with its contract version (`client-data-in-analysis#8`) | needs a new API (owned there) |
| B-6 | Předpoklady: the canonical V2 draws them in the Brief, but the plan places them in Návrh and Cílová skupina (research-lead-workbench, *Assumption panel*, MVPQ-02). The Brief links to them | data exists once `assumptions-and-open-answer-coding#AOC1` lands |
| B-7 | The store on the server's edit vocabulary for the Brief (`working-copy-edit-ops#WCE3a`) | needs a new API (owned there) |
| B-8 | Pracovní kopie / Historie / Původ and the revision stepper (`research-lead-workbench#15`) | data exists (working revisions; `WCE9` for reading an old one) |

## 4. The Lead on this artifact

- **View operations** (proposed to chunk 14's closed set):
  - `open_stage(brief)`;
  - `focus(target)` over the ids below;
  - `show_changes(on|off)` for a pending proposal's change blocks;
  - `show_tab(working|history|provenance)` (chunk 15).
- **What it can point at** (chunk 16):
  - `brief:goal`, `brief:title`, `brief:type`, `brief:decision_use`, `brief:briefing.<field>`;
  - `objective:<id>`;
  - `material:<attachment or source id>`.

  `FOCUS_ID` (`domain/research_lead.py:205`) gains `objective` and `material`. The `data-aia` ids are
  `brief.<section>.<item>`, as V2's (`DesignStages.tsx:18`).
- **Edit operations.**
  - Text: `set_text` on `title`, `goal`, `decision_use` and `briefing.*`; `list_replace` on
    `plan.objectives`. These are what an automatic accept may take (`edit_ops.py:302`).
  - Structure: `list_add` and `list_remove` on `plan.objectives`.
  - Nothing edits a file or its class.
- **Workers and their cards.**
  - `analyze_brief` (`packages/aia_core/tests/fixtures/lead_workers/workers.json:5`): a proposal card
    from #550's `lib/lead-cards.ts`. Its result is the plan, so it is reviewed on Návrh.
  - `critique_design` and `answer_memory`: advice cards, nothing accepted.
- **Inline proposals** (chunk 7). A change to the goal or to the objectives renders in place as a
  change block. The rest of `analyze_brief`'s result renders on Návrh (`artifact-design`).

## 5. Inputs and outputs

- **Reads:**
  - the client (name, approved knowledge titles in the worker's context, `research_agents.py`
    `context_snapshot`);
  - the client's sources picked as material (B-5);
  - project memory when a design is reused (`application/design_reuse.py`).
- **Hands on.** All of it as typed fields of the working copy, frozen into the Design Revision a run
  executes:
  - `goal`, `title`, `decision_use` and `briefing.*` to `analyze_brief`'s context and to the Lead;
  - `plan.objectives` to Návrh;
  - attachment records to the brief signature (`domain/design_items.py` `brief_signature`).

  **Today none of these reaches the draft report**: the analysis reads the research questions only
  (`application/analysis_results.py:575`). The chain closes that in
  `artifact-chain-to-draft-report#CHN2`.
- **Q12.** `lead-orchestration#LO9d` gives every downstream worker the accepted Brief by reference.
  `working-copy-edit-ops#WCE7` flags a pending proposal built on an older brief.

## 6. Input interactions

- Audit rows (`.planning/evidence/input-interactions-audit.md` §3 A):
  - A22 (goal), A23 (title in the artifact header), A24 (type as toggle chips), A25 (context fields);
  - A26 (link row), A27 (files), A28 (remove with undo).
- Chunk-1 primitives (`input-interactions#1`): `InlineText`, `ChoiceChips`, `InlineCreateRow` and
  `UndoToast`.

## 7. Chunks

**BRF1. The contract as data.**
- New `apps/web/src/lib/artifacts/brief.ts`: the view operations, target kinds and the selector of
  each target. Its Vitest checks that every target resolves to one element, and that an unknown target
  is refused, never guessed (D10).
- Depends on `research-lead-workbench#14` and `#16`. It lands as their first consumer if they ship
  together.

- *Landed* (`apps/web/src/lib/artifacts/brief.ts`): `brief:<field>` for every field and section
  (`briefing.<field>` as the Lead's edits name it) and `material:<attachment_id>` for a file kept in
  AIA, each one element by the screen's `brief-<field>` id or the row's `data-aia`; an empty context
  field is named by its chip. Agreed with the integration coordinator: the target kinds are
  `objective` and `material` of their own (#563), not `brief.<section>.<item>`. `objective:<id>`
  joins with BRF2. A link has no stable id and is not a target yet.

**BRF2. The body as V2 draws it.**
- `BriefStep` keeps its data and its save; its layout becomes V2's four sections (Předpoklady is a
  link, B-6) built from the existing primitives.
- Cíle reads and writes `plan.objectives` by item id.
- Tests:
  - `BriefStep.test.tsx`: each section renders from a fixture study; editing an objective in place
    changes only that item's text in the saved copy; Esc restores it.
  - A study that has no objectives yet shows "Zatím prázdné", not a placeholder (D13).
- Depends on `input-interactions#1` and `#4`, and on `working-copy-edit-ops#WCE3a`.

- *Landed, Cíle* (`apps/web/src/research/brief-objectives.ts`, BriefStep `Objectives`): the
  objectives as items on the Brief, read and written where Návrh keeps them (`research_plan` and
  the analysis together, as `plan-edit.ts` does), each `objective:<item id>`, edited in place
  (InlineText), added in the list (InlineCreateRow), removed with Vrátit (UndoToast); none reads
  "Zatím prázdné". On today's whole-copy store; WCE3a moves it onto the edit vocabulary.
- *Landed, Rozhodnutí and Kontext* (BriefStep `Decision`, `Context`): `decision_use` as one item
  (D-44) and the four `briefing.*` fields as items, each edited in place (InlineText; Esc restores,
  clearing saves empty), every field always shown with its example; the open/close chips are gone.
  The screen's order is V2's: Cíl, Cíle, Rozhodnutí, Kontext, then Typ problému and Podklady (V2 has
  no problem types; AIA keeps them). Deviation from B-3: the goal stays the stage's first field, a
  textarea with its sentence starters and count, not a Kontext item -- it is what a new study is
  written from. Still to come in BRF2: Předpoklady as a link (B-6, after AOC1).

- *Landed, Typ problému as toggle chips* (audit A24): the shared ChoiceChips (I3): one Tab stop,
  arrows move, a press toggles one type through `toggleProblemType` (an empty goal still filled
  with its default); each chip's description kept as its title and in its accessible name. At
  390 px the section is about 260 px tall instead of about 600.

**BRF3. Podklady with their class.**
- API: the attachments listing and the brief's picked sources answer each item's `data_class` and
  `class_source` (`rule:<name>` or `operator`), by `classify_by_rule`. An unknown class reads as
  unknown, never C.
- Web: a chip per material; "Interní dokument" sources marked.
- Tests:
  - API: an attachment is Class B by rule and a client source Class A; a source marked internal is C.
  - Vitest: an unknown class prints "třída neznámá".
- Depends on `client-data-in-analysis#8` for picked datasets.

- *Landed, removal with undo* (audit A28): a file or link removed from Podklady goes at once,
  with Vrátit for 8 s putting its record back in place (`research/brief.ts` restoreAttachment); the
  stored file was never deleted, only its record. Still to come in BRF3: picked client sources
  (client-data-in-analysis#8).

**BRF4. The Lead on the Brief.**
- `analyze_brief` is reachable only through a Lead card or a typed start (`lead-orchestration#LO5`).
  `BriefStep.tsx:135` is removed under `leadOwnsAiStarts` (`research-lead-workbench#26f`).
- The goal and objectives changes of its proposal render inline (chunk 7).
- Tests:
  - the static guard of 26f lists `BriefStep` as having no AI start;
  - `LeadPane.test.tsx`: a card for `analyze_brief` shows its ceiling (#550).
- Depends on #550 (`research-lead-workbench#23`), `research-lead-workbench#7`, `#26f` and LO5.

**BRF5. What the Brief hands on.**
- The inspector's Původ tab lists, per field, its readers as the chain manifest names them
  (`artifact-chain-to-draft-report#CHN1`). A field no reader takes says so.
- Test: Vitest over the manifest fixture.
- Depends on CHN1 and `research-lead-workbench#15`.

**BRF6. Journey.**
- *Landed* (`workspace_journey.mjs`, `lead_journey.mjs`; zero paid jobs):
  - an objective added in the list, read back after a reload as one `objective:<id>` target and
    reworded in place;
  - "@" then a tap on an objective sets the chip, naming that objective and no other, at 1440 and
    1100 (split), 768 (drawer) and 390 (sheet);
  - a message about the goal makes the scripted Lead focus the first objective
    (`aia_executors/workbench.py:179 @ 36e18caa`). At 1440 and 1100 the objective is marked and scrolled
    into view while the conversation stays beside it. At 768 and 390 the conversation steps aside to
    `peek` and focus follows;
  - no overflow at any of them.
- Deviations from the plan as written:
  - The steps live in `lead_journey.mjs`, not `workbench_journey.mjs`: they need a hatched Lead, so they
    pass once per workbench (OI-133).
  - "Paid rows unchanged" is checked as the journey's existing check: no request to a path that starts
    paid work (`/research/runs`, `/agent-jobs`, `/deep-research/runs`, a turn's `/request`). The usage
    ledger itself is not read.
- These steps run after the 1099 px drawer loop, so F-BRF-2 can stop a run before them (§ 7a). The final
  version passed on 2 of 2 fresh workbenches; with the expected objective swapped for the last one it
  fails: "1440: expected the Lead to point at objective:… ; it pointed at objective:…".

## 7a. Findings

- F-BRF-1 (UX, asked of the coordinator 2026-10-21, #647): a picked objective's chip reads its raw id
  ("Cíl obj_6393c6bada"), not its words.
  - Anchor: `apps/web/src/lib/lead.ts:516 @ b1a73536`. `targetOfElement` appends only a heading or
    label inside a `data-aia` element, and an item row has none.
  - Repro: `node tools/ui_workbench/lead_journey.mjs`, then `tmp/ui-workbench/lead-journey/390-brief-picked.png`.
  - Consequence: the person sees an id where the objective's words belong.
  - Fix: read the row's InlineText value. Not the row's whole text, which carries the number, the
    screen-reader "Upravit: Cíl N" and the "×".
  - Test: a `lead.test.ts` case over an objective row.
  - Status: fixed by #647 (merged as `9076d0f8`): an item row names itself by its own words, never its
    id (`apps/web/src/lib/lead.ts:615-618 @ 382b418a`); `lead.test.ts:143-147` holds an objective row.
- F-BRF-2 (journey flake, reported to the coordinator 2026-10-22): the drawer step's wait for the
  composer's focus times out intermittently at 1099 px.
  - Anchor: `tools/ui_workbench/lead_journey.mjs:198 @ b1a73536`, the wait
    `waitForFunction(() => document.activeElement?.id === "composer", …, { timeout: 10000 })` after the
    launcher opens the dialog.
  - Repro: `python tools/ui_workbench/workbench.py up --fresh` (with `AIA_WEB_RESEARCH_WORKBENCH=true`),
    `make ui-fixtures`, `node tools/ui_workbench/lead_journey.mjs`. It failed in 2 of 3 fresh runs with
    "page.waitForFunction: Timeout 10000ms exceeded", before any Zadání step. A fourth fresh run
    passed that wait but failed the next one at 1099 px, at `lead_journey.mjs:220 @ be85b470`: "Tab stays
    inside the open conversation", with focus on the page's body.
  - Consequence: the journey fails on a sound build, so a real regression after line 198 (the BRF6 step
    included) goes unseen in that run.
  - Fix (hypothesis, unmeasured): the dialog takes focus before the composer is enabled. Wait for the
    composer to be enabled after the dialog opens, then for focus. Owner: the workbench journey's owner,
    routed by the PM.
  - Test: the journey passes 5 of 5 fresh runs at 1099 px.
  - *Not reproduced since* (2026-10-22): `lead_journey.mjs` passed 5 of 5 fresh runs on develop @
    248729cc, the `:198` wait and the Tab trap every time. The cause is not confirmed. The wait for an
    enabled composer existed before; #678 (8e7347b2) rewrote it as a locator wait and changed the
    drawer's focus recovery. The pass may be timing, so if it returns, it is this finding, not a new one.
- F-BRF-3 (UX, audit 2026-10-22, fixed): an empty new objective is refused with "Napište název."
  ("write a name"), the folder-and-label wording of the shared create row.
  - Anchor: `apps/web/src/components/ui/InlineCreateRow.tsx:54 @ 248729cc` (`nameProblemWords` for
    every caller).
  - Repro: on Zadání, "Přidat cíl", then Enter on the empty row.
  - Consequence: the Brief asks for a name where it wants a goal.
  - Fix: `InlineCreateRow`'s optional `emptyWords`, which the Brief passes as "Napište cíl."; other
    callers are unchanged.
  - Test: `InlineCreateRow.test.tsx` ("in the caller's words") and `BriefStep.test.tsx` ("an empty new
    objective"), both failing before the fix; a `workspace_journey.mjs` step.

## 8. Owner questions

None. Where assumptions are shown (B-6) and the absence of a decision list (B-2, D-44) are settled.

Settled 2026-10-22 (the product owner, through the PM): the Brief may hold no objective while it is
drafted, so removing the last one stays allowed there; only Návrh requires an objective
(`research.plan.requiredObjectives`). A repeated objective is refused on both, in Návrh's words (#795).

## Doc follow-up

- `mvp-master-plan.md` §3 and `mvp-execution-contracts.md`: register this plan and its chunks (see the
  PR body).
- `open-items.md`: F-BRF-1, the objective chip reads its raw id (§ 7a).
- `open-items.md`: F-BRF-2, `lead_journey.mjs:198` composer-focus timeout at 1099 px (§ 7a), not reproduced in 5 fresh runs after #678; cause unconfirmed.
- `open-items.md`: F-BRF-3, an empty new objective said as a name (§ 7a), fixed.
- `CLAUDE.md` § 2, when BRF1 lands: `apps/web/src/lib/artifacts/` (one contract per artifact).
