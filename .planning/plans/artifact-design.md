---
status: in-progress
chunks:
  - "[x] DSN1. Návrh's contract as data: view operations, pointable ids (rq, objective, hypothesis, set, assumption) and V2's interaction contract, in research-lead-workbench 14's and 16's tables"
  - "[x] DSN2. Research questions with their coverage on the working revision: measures, items, comparison and gaps from research_trace, pokryto / částečně / mezera by the trace's own verdict"
  - "[x] DSN3. The narrative as items: problem summary, objectives, hypotheses and comparable measurements edited in place and autosaved, ProposalEditor and MeasurementEditor retired"
  - "[x] DSN3b. Select-to-comment on part of a narrative item, beside its direct in-place editing through the store, with stable item ids and the Lead's edit ops kept (the product owner, Q68 (b), 2026-10-22)"
  - "[ ] DSN4. Ve zprávě: each research question's report chapter and the analysis module answering it, from the newest run's stored report model"
  - "[ ] DSN5. Design Research in Návrh: findings per research question as external context, the review of its proposal (7b) mounted at the question, the panel moved here from Dotazník as a reader"
  - "[ ] DSN6. Tracked assumptions in Návrh, from the one assumption item contract"
  - "[ ] DSN7. The Lead on Návrh: analyze_brief, critique_design and design_copilot as cards, their proposals inline, PlanStep's AI starts removed"
  - "[ ] DSN8. Journey: Návrh at 1440, 1100, 768 and 390 px, zero paid jobs"
  - "[x] DSN2b. Research-question rows with their coverage inline; the DesignCoverage block retired (reopens DSN2 and DSN3; spec navrh D3; W1)"
  - "[ ] DSN3c. Návrh's header: counts and 'Dotazník ›'; the tinted intro, JumpChips and dock removed (reopens DSN3; spec navrh D1; W1)"
  - "[ ] DSN9. An objective's '→ VO n' link: objective_ids on research questions, an edit op, analyze_brief proposing it (spec navrh B4; W2)"
  - "[ ] DSN10. Rozsah as a segmented choice: a variant recommends N for Vzorek and never applies it; applyVariant stops writing n (spec navrh D2; W1, with artifact-sample SMP7)"
  - "[ ] DSN11. 'k cíli' on each research question; objectives leave Návrh for Zadání (spec navrh D4; W2, after DSN9)"
  - "[x] DSN12. Hypotheses as their own section on Návrh (spec navrh D5; W1)"
  - "[ ] DSN12b. A hypothesis's 'ověří S1' verdict: the hypothesis-to-measure link and research_trace's verdict (spec navrh D5; W2)"
  - "[ ] DSN13. Follow-up answers saved per question in the working copy (spec navrh D7; W1)"
  - "[ ] DSN14. Comments with undo, no false 'upraveno', their target and author (spec navrh D8; W1)"
  - "[ ] DSN15. The edits bar keeps the turn's decided rows: Přijato and Zahozeno as pills, Vrátit on an accepted text edit through AutoBar's revert, Vrátit on a dismissed one only once working-copy-edit-ops#WCE16 serves it (spec navrh D9; W1, with research-lead-workbench#7)"
---
# Artifact: Návrh (Research design)

Umbrella: `research-lead-workbench#18` (with Zadání). Chain: [`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md).
Anchors `@ 25f26232`; prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: say what the study must answer and how each answer will be measured.** It is the
research questions with their measures, the hypotheses and objectives, and the comparisons each
question needs.

V2: `DesignArt` (`prototypes/research-lead-v2/src/artifacts/DesignStages.tsx:37-91`).
- §1 "Výzkumné otázky a jejich pokrytí", with the aside "pokrytí počítá AIA (research_trace)". Each RQ
  carries a status chip (pokryto / částečně / mezera, `:33-35`) and a coverage grid: Rozhodnutí,
  Měření, Položky dotazníku with stage links, then, expanded, Analýza, Očekávaná odpověď, Hotovo,
  když, Ve zprávě and Mezery (`:58-69`).
- §2-3 Metody and Nevyřešené volby (`fixture.ts:88-93`).
- §4 Hloubkový výzkum pro návrh: DESIGN_RESEARCH only proposes (`:86-88`).
- Contract `CONTRACTS.design` (`fixture.ts:406`).

**Settled reduction:** D-44 takes the question chain out (`working-copy-edit-ops.md`, "WCE1 gains
no decision, expected-answer or done-when kinds"). So Rozhodnutí, Očekávaná odpověď and Hotovo,
když are not built. What stays is code-derived: measures, items, comparison, analysis and report.

## 2. What exists today

- `PlanStep` (`apps/web/src/components/rehome/research/PlanStep.tsx:79`):
  - `Understanding`, the narrative behind "Upravit text návrhu" (`:349`, `#plan-understanding`);
  - `Sets` and `SetCard`, the comparable measurements (`:402`, `:473`, `#plan-sets`), with
    `MeasurementEditor` (`:565`);
  - `Variants` (`:292`) and `FollowUps` (`:595`, `#plan-questions`);
  - `Comments` (`:697`).
- Its AI starts: `PlanStep.tsx:636` (answer the follow-ups) and `:756` (process comments).
- The trace: `research_trace` is computed in readiness (`apps/api/src/aia_api/routers/research.py:1131`;
  `application/research.py:1203`) and shown on Spuštění only (`ResearchTraceCard`,
  `ExecutionSteps.tsx:468`). The web reads links with `apps/web/src/research/trace.ts`. Design
  Research evidence per RQ: `apps/web/src/lib/design-evidence.ts`.
- Design Research's panel sits on Dotazník (`QuestionnaireStep.tsx:271`, `DeepResearchPanel.tsx:34`).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| D-1 | Coverage per RQ in Návrh. Readiness needs a submitted Design Revision; coverage on the working revision is `working-copy-edit-ops#WCE7` | needs a new API (owned there) |
| D-2 | Status pokryto / částečně / mezera from the trace's verdict (no new rule) | data exists |
| D-3 | Comparison per RQ, "Metody" (`comparison_set`, `research_trace.comparisons_of`) | data exists |
| D-4 | Ve zprávě: an RQ's report chapter. There is no stored report model (`report-delivery#RD5a`) | needs a new API |
| D-5 | The analysis module answering an RQ (RESEARCH_QUESTIONS; gaps recorded at start, `report_method.py:151`) | data exists after a run |
| D-6 | Nevyřešené volby = analyze_brief's follow-up questions and variants | data exists |
| D-7 | Design Research proposal review inside the artifact (F-DRL-1, `research-lead-workbench#7b`) | data exists (route); web new |
| D-8 | Assumptions (`assumptions-and-open-answer-coding#AOC1`, `#AOC3`) | needs a new API (owned there) |
| D-9 | Narrative edited in place (audit A29-A36) on the server's vocabulary (`working-copy-edit-ops#WCE3a`) | needs a new API (owned there) |

## 4. The Lead on this artifact

- **View operations:**
  - `open_stage(design)`;
  - `focus(target)`;
  - `expand_chain(rq id)`, V2's "Celý řetěz" (`DesignStages.tsx:71`), display only;
  - `show_changes`, `show_tab`.
- **Pointing:** `rq:<id>`, `objective:<id>`, `hypothesis:<id>`, `set:<id>`, `assumption:<id>` and
  `plan:<part>` (today's form, `lib/lead.ts:428-431`). `data-aia` is `design.<section>.<id>`.
- **Edit operations.**
  - Text: `list_replace` on RQs, objectives and hypotheses; `set_text` on `plan.problem_summary`.
  - Structure: `list_add` / `list_remove`; `set_add` / `set_edit` / `set_remove` and `comparison_set`
    (WCE3a); `assumption_*` (AOC1). `set_edit` is ruled text only for its title (`edit_ops.py:775`,
    by payload).
- **Workers:**
  - `analyze_brief` (a proposal);
  - `critique_design`, `design_copilot` and `answer_memory` (advice);
  - Design Research on named RQs (`lead-orchestration#LO5a.1`), with its request, running and finished
    cards (`research-lead-workbench#23b`, `#23c`).
- **Inline proposals:** analyze_brief's plan changes at their items, and a Design Research proposal's
  EVIDENCE items at their RQ (7b). A GAP item has no checkbox.

## 5. Inputs and outputs

- **Reads:** the Brief (goal, objectives, decision_use) and Dotazník's links to RQs
  (`research_questions` on questions and sets), plus the newest finished Design Research run.
- **Hands on:**
  - `plan.research_questions`, a typed list by text, read by `research_questions_of`
    (`domain/analysis/native.py:141`), by every analysis module and by the report's `intro` and
    `ch-design`;
  - `plan.hypotheses`, which the analysis does not receive today (AOC3, a Q12 gap);
  - `research_question_comparisons`, read by readiness;
  - sets, compiled into `spec.batteries`;
  - Design Research accepted items, as a ledger ref (`design_research` row) and a Design Revision.

  The report prints none of the Design Research a design was built on
  (`artifact-chain-to-draft-report#CHN4`).

## 6. Input interactions

- A29-A36 (variants, the narrative and its lists, sets, the measurement editor, follow-ups, comments,
  the leave guard).
- Primitives: `InlineText`, `InlineCreateRow`, `UndoToast`, `ChoiceChips` (comparison) and
  `RadioCard` (variants).

## 7. Chunks

**DSN1. Contract.** `lib/artifacts/design.ts` with its Vitest (as BRF1). Depends on
`research-lead-workbench#14`, `#16`.
- Progress (2026-10-21, `feature/design-lead-targets`): the screen carries the targets. Each
  narrative item has `data-aia`: an objective as the Brief's `objective:<id>`, a research
  question `rq:<id>` and a hypothesis `hypothesis:<id>`, all by item_ids' id (stored, else
  derived from the wording, so with AIA_WEB_STABLE_ITEM_IDS off a reword moves it), never by
  position (`plan-narrative.ts` `itemTargets`; `plan-narrative.test.ts` "each item's Lead target",
  `PlanStep.test.tsx` "marks each narrative item"). The section anchors stay the ids
  `lib/lead.ts` focusSelector already maps.

**DSN2. Research questions with their coverage.**
- Each RQ shows its measures by wording (`traceMeasures`), the items linking to Dotazník, the
  comparison and its gaps; the status comes from `research_trace`'s verdict.
- Tests: Vitest with a trace fixture (an unmeasured RQ reads mezera; an unknown link reads
  "neznámé", never pokryto, §8 of CLAUDE.md); the API test of WCE7's working-revision readiness.
- Depends on `working-copy-edit-ops#WCE7`. Until then the coverage reads from the newest Design
  Revision and says so.
- Progress (2026-10-21, `feature/design-rq-coverage`): the interim form landed. `DesignCoverage`
  reads the newest Design Revision's readiness `research_trace` (a GET), says which revision and
  whether the working copy moved since (`revisionIsCurrent`), and reads a question the revision does
  not hold as neznámé (`lib/design-coverage.ts`; `design-coverage.test.ts`, `PlanStep.test.tsx`
  "Návrh: Výzkumné otázky a jejich pokrytí"). Stays open for WCE7's working-revision coverage, the
  per-question `rq:<id>` target (WCE1's stable ids) and V2's "Celý řetěz" (needs `expand_chain` in
  `ARTIFACTS.design`).
- Done (2026-10-22, `feature/design-coverage-working`): `DesignCoverage` reads readiness on the
  working revision (`GET …/research/readiness/working`, WCE7) through `useSampleReadiness`: a
  waiting edit saved first, nothing submitted, read again when the revision moves
  (`PlanStep.test.tsx` "reads the coverage again once a research question's edit is saved"). It
  never flushes a save and re-reads only when the research questions, their comparisons or the
  questionnaire changed (`design-coverage.ts` `coverageInputs`), so a comment's save costs no
  readiness. The per-question `rq:<id>` target is on the narrative's items (#702); V2's "Celý
  řetěz" is DSN4's.

**DSN3. The narrative as items.**
- Replaces `ProposalEditor` and `MeasurementEditor`'s explicit save (A30, A33) with autosaved items.
- Test: `PlanStep.test.tsx`: an RQ edited in place keeps its id; a set's items reach 15 and stop.
- Depends on `input-interactions#4` and `working-copy-edit-ops#WCE3a`.
- Progress (2026-10-21, `feature/design-narrative-items`): the narrative half landed on today's
  store path. `PlanNarrative` edits the problem summary and each research question, objective and
  hypothesis in place (`InlineText`), adds them in their list (`InlineCreateRow`) and takes a
  removal back (`UndoToast`); `ProposalEditor` is retired (`research/plan-narrative.ts`,
  `plan-narrative.test.ts`, `PlanStep.test.tsx`). A value edited in place is a button, in which a
  browser selects no text, so a narrative item is commented on by its own "Komentovat" (quoting the
  item whole); selection still comments elsewhere (A35). Stays open for `MeasurementEditor` folded
  into the set card (A33) and the move onto WCE3a's vocabulary.
- Progress (2026-10-22, `feature/design-set-card-in-place`): the measurement half. Each set's
  title, purpose, question and scale ends are edited on its card (`InlineText`), one field per
  store update. A question without `{object}` or an empty field is refused at the field
  (`plan-edit.ts` `setFieldProblem`), and a repeated item or one past the full set at the chip
  (`objectProblem`, `ChipInput` `refuse`; the full set is the limits in force, `readySetLimits`'s
  `max`, which `addObject` refuses at too; above the recommendation only #736's warning, Q75 (a)). Each item is reworded in its place, its order kept
  (`ChipInput` `rename`, `withObject`), as the retired editor's textarea allowed. A scale end
  written on a set that states no ends keeps the other end the person saw (`withSetField`). A field
  opened and left unchanged sends nothing. Since every field saves itself, only a draft refused at
  its field is unsaved; while one is on the stage, every way out (a link, the workbench's
  navigation, "Další · dotazník", a reload) asks first, and so does a change that would remount
  it: adding or removing a set (every other card) or removing an item (that set's chips), since sets
  and their items carry no id to key them by. `MeasurementEditor`, its leave guard and "Nejprve
  použijte nebo zrušte rozepsané úpravy" are retired, and with them the form-only
  `validMeasurement` and `lines` (`plan-edit.test.ts`, `PlanStep.test.tsx` "edits a set's
  measurement field by field…", `proposal_prompt_journey.mjs`). Moving the store's writes onto the
  server vocabulary is `working-copy-edit-ops#WCE3a`'s work, not this chunk's.

**DSN3b. Select to comment, edit in place (Q68).**
- The product owner answered Q68 with (b): a person selects part of an item's words to comment on
  it, and still edits the item where it is shown.
- `InlineText` takes `selectable`: the value is drawn as a focusable `role="button"` span, because
  a browser selects no text inside a `<button>`. A single click opens the field once it settles
  with nothing selected (`SELECT_SETTLE_MS`, 300 ms), so neither a drag nor a double-click on a word
  opens it. Enter, F2 and Space open it at once. Disabled, it is the words alone and takes no focus.
  The hidden "Upravit: …" label is never part of a selection.
- The stage's Commentable picks up the selection. The item's own "Komentovat" stays, so a touch or
  keyboard reader can quote the whole item. Edits keep going through `applyNarrative`, so the stable
  item ids and the Lead's edit operations are unchanged.
- Tests: `InlineText.test.tsx` "InlineText selectable"; `PlanStep.test.tsx` "comments on a part of
  a narrative item selected in place"; `proposal_prompt_journey.mjs`, a real drag in Chromium.

**DSN4. Ve zprávě.**
- From the newest completed run's stored report model: the section id (`ch-2`, and any
  `ch-questions` table holding its measures) and title answering each RQ.
- Test: an RQ the report marks "bez doložené odpovědi" shows it.
- Depends on `report-delivery#RD5a` and `artifact-chain-to-draft-report#CHN3`.

**DSN5. Design Research in Návrh.**
- `DesignResearchReview` (7b) is mounted at each RQ; `DeepResearchPanel` moves here as a reader
  (26f.1 removes its start).
- Test: a finding is labelled "Externí kontext", never coverage.
- Depends on `research-lead-workbench#7b`, `#26f.1`, `#12a` (journey).

**DSN6. Assumptions.** One list with Cílová skupina, on the same contract. Test: UNTESTED shows as
untested. Depends on `assumptions-and-open-answer-coding#AOC1`.

**DSN7. The Lead on Návrh.**
- Cards for the three workers (#550), proposals inline (chunk 7); `PlanStep.tsx:636, 756` removed
  under `leadOwnsAiStarts`.
- Tests: the 26f guard; a stale proposal is refused in words (`proposal-items.ts`).
- Depends on #550 (`research-lead-workbench#23`), `#7`, `#26f` and `lead-orchestration#LO5`.

**DSN8. Journey** at 1440, 1100, 768 and 390 px:
- an RQ edited in place and reloaded;
- `expand_chain` by the scripted Lead;
- a Design Research card on 12a's recorded web, accepted at its RQ;
- zero paid jobs.

768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## Findings

- **F-DSN-1 (2026-10-21; refuted, kept as a regression test).**
  1. *Claim (from #609):* after the Brief's goal edit drops the analysis (`brief.ts` `editBrief`),
     Návrh's "Přidat sadu" seeds `objectives: [goal]` over the plan's objectives (`plan.ts:86-93
     @ bfe6d15`, `addSet`).
  2. *Anchor:* the only caller, `PlanStep.tsx` Sets `create` (`:400-403 @ bfe6d15`), passes
     `proposalAnalysis(store.get())` (the plan when there is no analysis) and writes only
     `applyPlanSets(s, trackedSets(next))`.
  3. *Reproduction:* `PlanStep.test.tsx` "keeps objectives typed without an analysis when a set is
     added" passes. With the caller changed to pass the raw analysis, the same test fails.
  4. *Consequence:* none through the screen. Only a direct `addSet(s, …)` with analysis null returns
     `[goal]`, and nothing in the app calls it that way.
  5. *Fix:* none. `addSet` stays the parity-tested port, and its parity case "without an analysis,
     one is started from the goal" holds.
  6. *Test:* the regression test above.

- **F-DSN-2.** Komentáře's hint sends a person to "oddílu 2 nebo 3" (`cs.ts:2011 @ 9eb78f6c`), but
  Návrh's sections draw no number (`StepSection`, `step.tsx`: `n` "is not drawn"), so the hint points
  nowhere. Fixed on `fix/design-comments-hint`: it names them as the page's jump chips do,
  "Porozumění nebo Sady" (`PlanStep.test.tsx` "names the sections a comment quotes as the page names
  them…"). The same audit: "Komentovat" takes a third of a narrative item's row at 390 px; in a
  narrow column (a container query, so a narrow workbench pane too) it is now its own glyph at 44 px
  (`proposal_prompt_journey.mjs`). The undrawn `n` props remain, `StepSection`'s callers' to remove.

- **F-DSN-3.** Saving Návrh's follow-up answers twice puts the same "Doplnění k analýze" block in the
  brief twice. Anchor: `apps/web/src/research/plan.ts:189 @ 491024f1` (`answerFollowUps` appends to
  `briefing.what_is_known`, as the classic did), with `PlanStep.tsx`'s submit clearing the fields
  afterwards, so the same answers can be typed and saved again. Reproduction: answer a follow-up,
  "Uložit odpovědi", type the same answer, save again; `what_is_known` holds the block twice.
  Consequence: a duplicated block in the brief the Lead and the analysis read (a reworded answer
  sits beside the old one). Smallest fix: `answerFollowUps` replaces its own earlier "Doplnění k
  analýze" block instead of appending, recorded as a parity deviation (a product call; parity kept
  for now, the coordinator 2026-10-22). Test: `plan.test.ts`, the same answers applied twice leave
  one block. Keeping the saved answers in their fields was tried and dropped: positional answers
  under changed questions and a refused save read as saved (code review).

- **F-DSN-4.** Návrh's research-question list hides research questions the server reads. The list
  reads the analysis alone (`narrativeOf`, `apps/web/src/research/plan-narrative.ts:25 @ 25ce6493`,
  through `proposalAnalysis`, which prefers `state.analysis`), while readiness traces
  `research_plan.research_questions` (`researchQuestionsOf`). Reproduction: the workbench's
  `deep_research` fixture (`tools/ui_workbench/fixture_project.py:316 @ 25ce6493`; two questions in
  research_plan, none in its analysis) shows "Zatím žádné" in the list. Consequence: a person sees
  no questions and adds them again, while the run answers the ones they cannot see. DSN2b shows the
  traced ones under the list, with their coverage ("Co AIA čte jako výzkumné otázky mimo tento
  seznam"; `PlanStep.test.tsx` "lists what the server reads as a research question that the list does
  not show…", `workbench_journey.mjs`), so nothing is hidden. Smallest fix, not made here: the list
  falls back to research_plan's questions when the analysis states none. That changes what an edit
  writes, so it is DSN3's to decide.

## 8. Owner questions

None: D-44 settled the chain's reduction; MVPQ-02 the assumptions.

## Doc follow-up

- Register this plan and its chunks in `mvp-master-plan.md` §3 and `mvp-execution-contracts.md`.

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**DSN2b. Coverage inline** (spec `navrh/D3`; reopens DSN2 and DSN3; W1, lane E). Each research question a row with its coverage from the working readiness; `DesignCoverage` retired. Test: a question's row shows pokryto / částečně / mezera from the trace, and no separate coverage block renders.

**DSN3c. Návrh's header** (spec `navrh/D1`; reopens DSN3; W1, lane E). On `research-lead-workbench#36`.

**DSN9. Objective → research question** (spec `navrh/B4`, no backend today; W2, lane E). `objective_ids` on a research question, an edit operation in the `working-copy-edit-ops` vocabulary (after WCE3a), and an analyze_brief harness bump that proposes it.

**DSN10. Rozsah** (spec `navrh/D2`; W1, lane E, one release with `artifact-sample#SMP7`). Decided by default (planning, open to Nigel's override): a variant recommends N and never applies it; N is set on Vzorek (Nigel P1, 26 Oct 2026). `applyVariant` stops writing n; the recommendation is read as "Vzorku doporučí N" (a `recommended_n` field is a hypothesis until built).

**DSN11. 'k cíli'** (spec `navrh/D4`, no backend; W2, lane E). After DSN9.

**DSN12. Hypotheses section** (spec `navrh/D5`, the section; W1, lane E).

**DSN12b. Hypothesis verdict** (spec `navrh/D5`, the verdict; no backend; W2, lane E). A new link and a trace verdict; unknown never answerable.

**DSN13. Follow-up answers** (spec `navrh/D7`, no backend; W1, lane E). After `working-copy-edit-ops#WCE3a`; analyze_brief harness bump.

**DSN14. Comments** (spec `navrh/D8`; W1, lane E). `useUndo` (`input-interactions#1`); the author from the session (a new field). The UI part is built on `feature/design-comments-undo`: a removed comment comes back with Vrátit through the stage's one undo offer, saving comments for the Lead marks nothing "upraveno", and the section says a comment changes nothing (`ResearchScreen.workbench.test.tsx` "a removed comment comes back with Vrátit; saving comments marks nothing changed"). Open: "k sadě … · Jana Malá" needs `{target, author}` on a stored comment, the author from the session (a backend field; the store is `{quote, comment}` in `ui_state`). *Lost work, not built (PM coordinator, 26 Oct 2026).* That open part was started on `feature/design-comment-author` in the Návrh session, left uncommitted with its tests failing when its permission was withdrawn at 13:10 UTC, and lost with the session's container at its archive (23:19 UTC). Nothing of it is on any branch; the UI part above is on develop (`feature/design-comments-undo` @ 5439fbe2, merged). The open part starts again from this entry.

**Notes.**
- DSN5 keeps the Design Research card on Návrh (decided by default by planning, 26 Oct 2026, open to Nigel's override; OQ22); its "+" items in the Lead's menu are disabled with a reason until `lead-orchestration#LO5a.3`.
- `navrh/D10` (the plan card 'Od návrhu ke sběru dat') is `lead-orchestration#LO3`, `#LO4`, `#LO21e`.

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**DSN15. Decided rows in the edits bar** (W1, lane E). Spec `navrh/D9`: `EditsBar` keeps the turn's decided edits with
a pill; Vrátit on an accepted text edit reuses `AutoBar`'s revert (`Workbench.tsx:915 @ bd0d1ad6`); on a dismissed edit
no Vrátit until `working-copy-edit-ops#WCE16`. The note above that `navrh/D9` is #7 with WCE9 stands for the server
side; this is the bar itself. Test: an accepted edit stays as Přijato with Vrátit, and Vrátit restores the before text.
