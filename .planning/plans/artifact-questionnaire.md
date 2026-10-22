---
status: in-progress
chunks:
  - "[ ] QST1. Dotazník's contract as data: view operations, pointable ids (question, section, set, option) and V2's interaction contract"
  - "[ ] QST2. The body as V2 draws it: the strip (items, length, coverage per research question), blocks and items with type, options and research-question pills, edited in place"
  - "[ ] QST3. Protected Sociomap inputs: the lock line and every writer's refusal shown at the item"
  - "[ ] QST4. Routing and stimulus shown and edited at the question"
  - "[ ] QST5. Proposals inline (research-lead-workbench 7 lands here): a change block per item with research-question coverage gained, lost and kept, per-change accept, stale refused, protected inputs kept"
  - "[ ] QST6. The Lead on Dotazník: build_questionnaire and optimize_questionnaire as cards, the stage's AI starts removed, Design Research moved to Návrh"
  - "[ ] QST7. The questionnaire's length, by the rule the owner chooses"
  - "[x] QST8. Závislosti: what reads each set and question downstream (Sociomap, Results, Analysis), from the specification"
  - "[ ] QST9. Journey: Dotazník at 1440, 1100, 768 and 390 px, zero paid jobs"
---
# Artifact: Dotazník (Questionnaire)

Umbrella: `research-lead-workbench#17` (and `#7`, which lands here). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: the exact items respondents answer, each tied to the research question it measures.**

V2: `QuestionnaireArt` (`DesignStages.tsx:95-142`).
- The strip: the item count; "≈ min", with the accepted revision's figure beside it; one
  coverage pill per RQ, "is-gap" when no item measures it (`:103-107`).
- Blocks B1… with a lock line on a protected set ("Vstup Sociomapy · chráněno",
  `fixture.ts:115`).
- Items with id, wording, type word (`:93`), options, routing "zobrazit, pokud …", lock reason, RQ
  pills and seconds (`:110-128`).
- "Závislosti" (`:132-139`): Sada 1 feeds the Sociomap and Results, Q8 routes Q9, and Q9 is open
  ("data, ne připuštěná evidence").
- Contract `CONTRACTS.questionnaire` (`fixture.ts:407`): a proposal carries baseRev and a stale one is
  refused; Sada 1 and Q19 are protected; accept by a person only.

## 2. What exists today

- `QuestionnaireStep` (`QuestionnaireStep.tsx:100`):
  - `Choose` (Excel / ručně / AI, `:320`), `Upload` (`:355`) and `Preview` (`:437`);
  - `Outline` (`:504`), `Editor` (`:579`, `#q-editor`) and `ResearchQuestionComparisons` (`:613`);
  - `QuestionBlock` (`:662`, `#qblock_<id>`), `QuestionCard` (`:701`, `#qedit_<id>`),
    `ResearchQuestionLinks` (`:806`), `OptionRows` (`:850`) and `TrackedSet` (`:907`).
- AI starts: build (`:252`, `runJob("researchBuildQuestionnaire")` `:126`) and optimize (`:238`,
  `:149`). Design Research is mounted at `:271`.
- Proposals: `ProposalReview` is mounted above the stage (`ResearchScreen.tsx:370, 387`), not at the
  items. Import: `workspace.py:2255`.
- The domain: questions, sets, scale labels (`input-interactions#3b1`, done) and links
  (`research_design.py` `research_questions`).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| Q-1 | Coverage pills per RQ from the items' links (`trace.ts` `researchQuestionsOf`) | data exists |
| Q-2 | Length estimate: AIA has no per-item duration | needs an owner decision (§8) |
| Q-3 | The lock and its refusal at the item (`edit_ops.lock_refusal`; the declarations' editor `working-copy-edit-ops#WCE8`) | needs a new API (owned there) |
| Q-4 | Routing (`working-copy-edit-ops#WCE13`; fieldwork `run-qc-and-checkpoint#RQC11`) | needs a new API (owned there) |
| Q-5 | Stimulus (`working-copy-edit-ops#WCE14`) | needs a new API (owned there) |
| Q-6 | Inline proposals per item with coverage (chunk 7), per-change accept (`working-copy-edit-ops#WCE6`), the proposal keeping protected inputs (`#WCE8b`) | needs a new API (owned there) |
| Q-7 | Manual operations on the server vocabulary (`working-copy-edit-ops#WCE3b`) | needs a new API (owned there) |
| Q-8 | Závislosti derived from the specification (sets → `sociomap_rating`/batteries → Sociomap; open questions → Analysis) | data exists |
| Q-9 | Scale presets and per-point labels in the editor (`input-interactions#3b2`) | data exists (3b1) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(questionnaire)`; `focus(target)`; `show_changes` (V2's "show
  diff"); `show_coverage(rq id)`, which highlights the items measuring an RQ (display only).
- **Pointing:** `question:<id>` and `section:<id>` (today, `lib/lead.ts:425-426`), plus `set:<id>`
  and `option:<question id>.<n>`. `data-aia` is `questionnaire.<section>.<item>`.
- **Edit operations.**
  - Text: `question_edit` of the wording alone (`edit_ops.py:302`).
  - Structure: `question_add`, `question_remove`, `question_move`, `question_merge`, `section_*`,
    `link_set`, `scale_set`, `route_set`, `stimulus_set` and `sociomap_declare`.
  - A locked item refuses every writer, the Lead's and a person's alike (WCE8).
- **Workers:** `build_questionnaire` and `optimize_questionnaire` (proposal cards,
  `workers.json:6-7`); `critique_design` (advice).
- **Inline proposals:** questionnaire proposals at their items, with coverage gained, lost and kept
  (chunk 7).

## 5. Inputs and outputs

- **Reads:** Návrh's RQs and sets; the accepted Brief (LO9d); readiness; the question outlook.
- **Hands on:** questions and sets as typed design items, compiled into `spec.questions` and
  `spec.batteries` (`research_design.py:408-418`). These feed:
  - fieldwork (respondent items);
  - the aggregate;
  - the Sociomap (`rating_universe`);
  - the report's design chapter (`ch-design`) and questionnaire appendix (`app-questionnaire`)
    (`report_design.py:114`);
  - per-question tables (`report_tables.py:130`).

  - Routing has no reader in fieldwork yet (RQC11); `evidence-integrity#10` is the filtered base.
  - In the draft, the chain plan's manifest (`artifact-chain-to-draft-report#CHN1`) names
    `spec.questions` and `spec.batteries` as the sources of `ch-design`, `app-questionnaire` and the
    question tables.

## 6. Input interactions

- A1-A21: wording, type, options, block, quick adds, sets, scales, comparisons, links, prices, delete
  and undo, the import.
- Primitives: `InlineText`, `Segmented`, `InlineCreateRow`, `ChipInput`, `UndoToast`,
  `InlineConfirm`, `Stepper` (scale) and `ChoiceChips`.

## 7. Chunks

**QST1. Contract.** `lib/artifacts/questionnaire.ts`. Depends on `research-lead-workbench#14`,
`#16`.

**QST2. Body.**
- The strip and the item rows over today's data; `AskDialog` prompts retired (A6-A8).
- Tests: `QuestionnaireStep.test.tsx`: the strip's coverage pill is a gap for an unmeasured RQ; ten
  Enters make ten options.
- Depends on `input-interactions#1`, `#3` and `working-copy-edit-ops#WCE3b`.
- *Progress (feature/questionnaire-strip):* the strip alone, which needs none of those: the items a
  respondent answers and coverage per stated research question (`trace.ts` `coverageOf`), read as
  `research_trace.py:242-259` reads it: unknown until an item declares a link, never a gap; the
  length says "Délka zatím neodhadnuta" until QQ1/QST7. Tests: `trace.test.ts`,
  `QuestionnaireStrip.test.tsx`. The rows edited in place and the item pills stay open, behind the
  dependencies above; QST2 stays unticked.

**QST3. Protected inputs.**
- The lock line and the server's refusal text at the item.
- Test: Vitest over `tests/fixtures/edit_ops/cases.json`'s lock cases.
- Depends on `working-copy-edit-ops#WCE8`.

**QST4. Routing and stimulus.**
- Test: a route naming a later question is refused at the field (I9).
- Depends on `working-copy-edit-ops#WCE13`, `#WCE14`.

**QST5. Proposals inline.**
- `ChangeBlock`s replace the stage-level `ProposalReview` for questionnaire jobs.
- Tests:
  - `useResearchAgents.test.tsx`: a change accepted alone posts its change id (WCE6);
  - `proposal-diff.items.test.ts`'s shared cases;
  - coverage lost is shown before an accept.
- Depends on `research-lead-workbench#7`, `working-copy-edit-ops#WCE5`, `#WCE6`, `#WCE8b`.

**QST6. The Lead on Dotazník.**
- `QuestionnaireStep.tsx:238, 252` are removed under `leadOwnsAiStarts`; the Design Research panel
  moves to Návrh (`artifact-design#DSN5`).
- Test: the 26f guard.
- Depends on #550, `research-lead-workbench#26f`, `#26f.1` and `lead-orchestration#LO5`.

**QST7. Length.** By §8's answer. Test: the estimate's rule is shown in the inspector, and an
unknown duration is never zero.

- *Progress (feature/questionnaire-length):* the Dotazník side. `research/length.ts`
  (`readRule`, `questionnaireLength`) prices each question by its type and each distinct set object;
  the strip reads the rule from `…/research/limits` `questionnaire_length` and says "pravidlo v
  Metodice zatím není nastaveno" while it is absent (today), "nepodařilo načíst" when the route
  fails, "Délka neznámá" when an item's type has no price, else "≈ N min" with the rule in its title
  and the study type's limit beside it: "limit N min", "nad limitem N min" or "limit nenastaven".
  Tests: `length.test.ts`, `QuestionnaireStrip.test.tsx`. Open: the server field, with Aram's
  Metodika entry; the rule in the inspector. QST7 stays unticked.

**QST8. Závislosti.** Test: a set declared as a Sociomap input lists Sociomapa.

*Delivered (feature/questionnaire-dependencies):* `src/research/readers.ts` reads the working copy,
not a compiled specification: readiness exists only for a submitted Design Revision
(`routers/research.py` `ReadinessResponse`), and Dotazník edits the working copy. Each rule cites
the server line it mirrors, and an item's readers are what it feeds once it compiles, never a
verdict that it will (Kontrola decides). Tests: `readers.test.ts`,
`QuestionnaireDependencies.test.tsx`; journey `tools/ui_workbench/questionnaire_journey.mjs`
(1440, 1100, 768, 390 px; zero paid jobs).

*Finding QF-1:* the outline is `sticky` at every width (`QuestionnaireStep.tsx:545 @ 25f26232`).
Wrapped under the editor, it covers about half the viewport at 390 px and in the workbench at 1100
px, Závislosti included. Reproduction: the journey's `390-dependencies-section.png`. Fix: sticky only
while it sits beside the editor (a container query). Test: a journey assertion that the section is
not covered at 390 px.

*Finding QF-2 (browser audit, 2026-10-22):* Dotazník writes every count in the genitive plural
whatever the number, and the outline's kicker is English: "4 otázek · 1 sledovaných sad", "Blok 1 ·
4 otázek", "GUIDED EDITOR", "měří jeden outcome" (`QuestionnaireStep.tsx:562,688 @ bfe6d15b`, the
strings in `cs.ts`). The import's note prints "Načteno: undefined otázek" when the answer carries no
summary (`questionnaire.ts:404 @ bfe6d15b`). Reproduction: the fixture study's Dotazník. Fix
(fix/questionnaire-czech-counts): `countWords` / `countsWords`, the word by its number, and the
import's note counted from the sections kept. Test: `questionnaire-counts.test.ts`.

*Finding QF-3 (browser audit, 2026-10-22):* at 390 px the tracked set's name shrinks to 80 px
("Sledovan…") beside its badge, count and Smazat, one row that never wraps
(`QuestionnaireStep.tsx:922 @ bfe6d15b`). Fix: the row wraps and the name keeps 12rem. Test: the
journey asserts the name is at least 160 px wide at every width (failed at 390 before the fix).

**QST9. Journey** at 1440, 1100, 768 and 390 px:
- an item edited in place;
- the Lead focusing `question:<id>`;
- a recorded optimize proposal accepted per change;
- zero paid jobs.

768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

**QQ1. How should Dotazník estimate the questionnaire's length?**
V2 shows "≈ N min" from fixture seconds per item. AIA stores no duration, and an invented figure
reads as data (D13).
- (a) A declared rule per item type: seconds for a single, multi, scale and open question, and per
  item of a tracked set. It is shown as "odhad" with the rule in the inspector, and its constants are
  set by the methodology owner on Metodika.
- (b) No length until a method for it exists. The strip says "délka zatím neodhadnuta".
- (c) The 18.6.6 unit's estimate, if it has one: to be checked in the oracle first.

**Recommendation: (a)**, with the constants proposed by A. Bahbouh. It is a rule, cheap to
compute, and honest because it is labelled. (b) is the fallback if he declines.

**Decided (the product owner, 2026-10-21, Q53 on /pmstatus): (a).** The questionnaire's length is
a declared rule set by the methodology owner on Metodika: seconds per answer by question type and per
tracked-set object (the estimate), and the most a questionnaire may take per study type (the limit;
the PM's reading of Q53, 2026-10-21). Until he sets them Dotazník says the rule or the limit is
unset and shows no number. The Metodika entry is his to make (the request below); Dotazník only
reads it.

*Request to A. Bahbouh (methodology owner), sent through the PM and the product owner:*

> Na Metodice, v modulu připravenosti (ten za `GET …/research/limits`,
> `domain/methodology/readiness.py`), prosím skupinu **Délka dotazníku**. Všechny hodnoty jsou
> v sekundách, každá číslo ≥ 0, **bez výchozí hodnoty**: dokud je nenastavíte, Dotazník napíše, že
> nastavené nejsou, a žádné číslo nedosadí.
>
> 1. **Odhad, sekundy na jednu odpověď:** jedna odpověď (`vyber`), více odpovědí (`multi`), škála
>    (`skala`), otevřená odpověď (`otevrena`) a jedna položka sledované sady (`set_object`).
> 2. **Limit, nejvýše sekund na celý dotazník, pro každý typ studie** (`StudyKind`: výzkum
>    `RESEARCH`, simulace `SIMULATION`).
>
> Trasa limitů pak pro danou studii vrátí `questionnaire_length: {seconds: {vyber, multi, skala,
> otevrena, set_object}, max_seconds, version}`: `max_seconds` je limit pro typ té studie (nebo
> `null`, dokud ho nenastavíte) a `version` verze metodiky v platnosti. Dokud chybí kterákoli
> z pěti cen, vrátí `null`. Jiný typ otázky se necení: Dotazník pak délku označí za neznámou
> a s limitem ji neporovná.

## Doc follow-up

- Register this plan and its chunks. `research-lead-workbench#7`'s questionnaire half is QST5.
