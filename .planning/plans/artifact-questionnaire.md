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
  - "[ ] QST10. One comparison set shared by Návrh and Dotazník ('Objekty', data-aia set:<id>), seen from both stages (spec navrh D6 + Q8; W2, after working-copy-edit-ops WCE8b)"
  - "[x] QST11. The respondent preview at the real scale range, saying what was left out (spec navrh Q5; W1)"
  - "[ ] QST12. One questionnaire editor: the Způsob radiogroup (Nahrát Excel / Sestavit ručně / Sestavit s AI) removed, the one editor working on an empty questionnaire too (Nigel, 26 Oct; W1, ships with lead-orchestration#LO18b)"
  - "[x] QST13. build_questionnaire and optimize_questionnaire read every verified finding of the newest Design Research run, as a frozen external layer labelled not respondent evidence; a prompt and harness bump (Nigel, 26 Oct: \"All verified findings\"; W1)"
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

*Finding QF-6 (browser audit, 2026-10-22):* the outline's rows only scroll. Focus stays on the
outline, so a keyboard user Tabs through every earlier question to reach the one they picked. From
the respondent preview, which draws no editor, a row does nothing at all
(`QuestionnaireStep.tsx:562 @ b6ac25c5`, `jumpTo` = `scrollToPlace`). Reproduction: focus Q3 in the
outline, press Enter, press Tab. Fix (fix/questionnaire-outline-focus): a row opens Upravit if
needed, then scrolls to the card or set and focuses it (`openPlace`), so Tab goes on from there.
Test: `QuestionnaireStep.test.tsx` (QF-6); seen in a browser at 1440 and 390 px.

## 7. Chunks

**QST1. Contract.** `lib/artifacts/questionnaire.ts`. Depends on `research-lead-workbench#14`,
`#16`.

- *Progress (feature/questionnaire-lead-targets):* the pointable ids alone, on the contract the
  integration coordinator landed in `lib/workbench-artifacts.ts` (#563): each block and tracked set
  carries `data-aia="section:<id>"`, each question `question:<id>`, through `aiaId` by the item's
  stored id; an item without a valid id carries none. `lib/lead.ts`'s focus and pointing read the
  mark (#599). `set:<id>` and `option:<question>.<n>` are not marked: the contract names only
  section and question for Dotazník. Test: `QuestionnaireLeadTargets.test.tsx`. The view operations
  as data (`show_changes`, `show_coverage`) stay with QST1, behind `#14` and `#16`; QST1 stays unticked.

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

## Browser-audit findings

QF-1 to QF-3 sit under QST8 and QF-6 under §6 (Input interactions).

*Finding QF-4 (2026-10-22):* "Sestavit s AI" on a questionnaire that already has items answers
the click with nothing. The view stays the editor (`questionnaire.ts:79 @ b6ac25c5`), and in the
workbench the toolbar's optimize button is hidden too, so only the segment and a save move.
Reproduction: the fixture study's Dotazník, click "Sestavit s AI". Fix (fix/questionnaire-ai-mode):
a note says the AI will not build it anew and what it does instead; in the workbench, "Požádat
Vedoucího" sends the Lead "Navrhni úpravy dotazníku." in words, and nothing starts from the stage.
Tests: `QuestionnaireAiMode.workbench.test.tsx`, `QuestionnaireStep.test.tsx` (QF-4, QF-5).

*Finding QF-5 (2026-10-22):* two sentences say what is not true. The AI card says "Provider/model
můžete změnit přímo zde." (`QuestionnaireStep.tsx:257 @ b6ac25c5`), but AIA offers no provider choice.
The preview says "technický editor je pod ní" (`QuestionnaireStep.tsx:453 @ b6ac25c5`), but the preview
replaces the editor. Fix: the first is dropped; the second says the preview is the respondent's
view, and that editing happens under Upravit. Test: `QuestionnaireStep.test.tsx`.

*Finding QF-7 (2026-10-22):* the question's × is named by the stored id, "Odebrat otázku Q_wb1",
and a screen reader hears the id again after the card's number ("Q1 Q_wb1";
`QuestionnaireStep.tsx:772,783 @ eaf9eeaa`). Fix (fix/questionnaire-remove-label): the × is named by
the number on the card, "Odebrat otázku Q1", and the hidden id is gone (the badge's title keeps it).
Test: `QuestionnaireUndo.test.tsx` (QF-7).

*Finding QF-8 (2026-10-22):* Závislosti says a set reaches no stage when the compiler would take it.
It holds a set outside 4-15 distinct objects (`readers.ts:69 @ af91be23`). The compiler refuses only
outside the hard 3-40 (`research_design.py:830 @ af91be23`, battery_size); 4-15 is a readiness
warning. So a set of 3, or of 16-40, was listed as feeding nothing. Fix (Q75 (a), the product owner,
2026-10-22): the readers use the hard range; the editors allow 16-40 with a warning in words, refuse
only the 41st, and keep refusing under four. Tests: `readers.test.ts`, `questionnaire-set-limits.test.ts`
(the four limits held to TRACKED_SET_LIMITS), `QuestionnaireFields.test.tsx`, `PlanStep.test.tsx`.

*Finding QF-9 (browser audit, 2026-10-22):* at 390 px a question's × falls to a row of its own,
130 px below its number: the type chips wrap and `ml-auto` takes the × with them
(`QuestionnaireStep.tsx:869-880 @ 54c44279`). Fix (fix/questionnaire-audit-390): the card's top row
is a grid, the number and the × at its ends, each a chip's height (TOUCH), and the chips wrapping
between them. Test: the journey
asserts the × overlaps its number's row at 1440, 1100, 768 and 390 px (130 px apart before the fix).

*Finding QF-10 (browser audit, 2026-10-22):* a set's output note ends "pokud projde validačním
gate", half English and naming no rule a person can check (`cs.ts:2230 @ 54c44279`). Fix: "mapa
položek, když sada projde Kontrolou a odpovědí na mapu bude dost" (Kontrola refuses a set by its
size or familiarity; the map needs enough answers per pair, readiness's sociomap_support). Test: `QuestionnaireFields.test.tsx`.

*Finding QF-11 (browser audit 2, 2026-10-22):* at 390 px a question's right scale label wraps to a
row of its own under the left one, away from the end it names: the ends and the boxes are one wrapping
flex row (`ScaleEditor.tsx:231-249 @ 9607ee09`). Fix (fix/questionnaire-audit-2): on a phone the
boxes take the first row and each label sits under its end. Test: the journey asserts at 390 px the boxes
above both labels, the labels on one row, each at its end (36 px apart vertically before the fix).

*Finding QF-12 (browser audit 2, 2026-10-22):* the topic and market research card on Dotazník is
half English ("hluboký research", "price/value", "Outcome benchmarky", "Existing research") and
promises a model choice and an explicit update the panel does not offer (`cs.ts:2236-2241 @ 9607ee09`).
Its intro also kept 18.6.6's topic list (motivations, barriers, competition, price, segments, foreign
markets), which no Design Research track researches. Fix: the card is "Před uzavřením dotazníku", its
intro in Czech, saying only what holds: the research looks into the study's research questions and
tracked objects, in approved client knowledge and on the web (`deep_research/contracts.py` `SubjectKind`,
`Channel`), and AIA itself never shows respondents a finding's outcome numbers (the leakage rule); the
line promising a model choice and an update is gone, with the four unused half-English keys beside it. Test: `QuestionnaireStep.test.tsx`.

*Finding QF-15 (browser audit 3, 2026-10-22):* loading a questionnaire file replaces every block, question
and set already there, with no word before and no way back (`QuestionnaireStep.tsx:456-458 @ 382b418a`):
a person with a questionnaire who tries the template loses it on the first file. Fix
(fix/questionnaire-import-undo): the upload card says a file replaces the questionnaire there is (any
section, a block with no questions yet included: `hasQuestionnaire`), and an import over one is offered
back with Vrátit (input standard I6): the sections and the plan's status as they were, the rest of the plan
as it now is, and only while the questionnaire is still the file's, else it says it cannot. Tests:
`QuestionnaireStep.test.tsx`.

*Finding QF-14 (browser audit 2, 2026-10-22):* the respondent preview numbers its items with
18.6.6's running count over questions and sets, so after four questions the set reads "Sledovaná sada 5"
where the editor says Sada 1, and a question after a set skips a number (`QuestionnaireStep.tsx:554,573
@ 9607ee09`). Fix: `respondentPreview` gives each item its `number` as the editor numbers it, questions
and every section that is not questions each counted on its own, beside the parity-tested `index`; the
preview shows it. Tests: `questionnaire-preview.test.ts`, `QuestionnaireStep.test.tsx` (a set before the
questions read Sledovaná sada 1, Otázka 2, Otázka 3 before the fix; the existing preview test had pinned
"Sledovaná sada 3" beside the outline's S1, and now reads 1).

*Question QF-13 (browser audit 2, 2026-10-22), for the PM:* in the workbench Dotazník shows its own
"Spustit veřejný výzkum" (`QuestionnaireStep.tsx:351-359 @ 9607ee09`, `DeepResearchPanel`), although
a stage in the workbench shows no AI start of its own (#550) and the Lead's contract lists
`design_research` among Dotazník's starts (`lead_artifacts.py:280-285 @ 9607ee09`). No typed command
or Lead card starts Design Research yet, so hiding the button would leave no way to run it. Left as is.

*Finding QF-16 (audit 3, 2026-10-22):* a questionnaire file that fails to import for any reason
but the import's own rules is said in the API's English: an empty or over-25 MB file reads "The request
body or parameters are invalid." (the schema's 422) and a dropped connection "Failed to fetch"
(`QuestionnaireStep.tsx:461 @ 82541803`, the raw `e.message`); the template's download too
(`:470`). Fix (fix/questionnaire-audit-3): an empty or too large file is refused before it is sent; a
422 the import gave keeps its Czech words, and anything else is said in the Brief's upload words
(`research/brief-upload.ts`), named by the file; a file the browser could not read is said as such,
never as a lost connection; a refused template download names its code. The import's one English
message (`questionnaire_import.py:324`, unreachable) is Czech too. Tests: `QuestionnaireStep.test.tsx`
"says an empty file, a refusal without words of its own and a lost connection in Czech" and "says a
template the API would not give in Czech".

*Finding QF-17 (OI-52, the data owner's answer, 2026-10-25 (b)):* a questionnaire made only of tracked
sets is not complete; it needs at least one plain question. Before, readiness's `questionnaire` check always
passed (`research_design.py:1457-1463 @ f7762d72`), Dotazník's track read a sets-only questionnaire as done
(`lane.ts:63 @ f7762d72`) and its dock said "Dotazník je připravený" once the editor was open (`QuestionnaireStep.tsx:259 @ f7762d72`).
Fix (fix/questionnaire-plain-question): the check FAILs with words that say why, the track reads "· bez běžné
otázky", and the dock is not ready and says why; `assess_readiness` re-pinned in Metodika. Tests:
`test_research_design.py` "a questionnaire of tracked sets only is not ready", `lane.test.ts`, `QuestionnaireStep.test.tsx`.

*Finding QF-18 (keyboard audit, 2026-10-25):* a question's display condition editor drops keyboard focus to
the page: "Podmínka zobrazení" and "Upravit podmínku" unmount as the form replaces them, and Uložit, Zrušit,
Escape and Odebrat podmínku unmount what had focus in turn (`QuestionCondition.tsx:69 @ ffce5c72`), so a keyboard user starts again
from the top. Fix (fix/questionnaire-condition-focus): the form opens with focus on the chosen question (or the
first), and every way out (Uložit, Zrušit, Escape, Odebrat podmínku) puts focus on the first enabled button
left in the condition's box, else to the question's wording (never a type chip). Test: `QuestionnaireStep.test.tsx` "moves focus
into the condition form and back to its button when it closes" (all four ways out).

*QST11, the respondent preview at the real range (spec navrh/Q5; the chunk is in #923):* the preview drew every
scale 1-10 (`ScaleBoxes` defaulted to 1..10 and was called without a range, `QuestionnaireStep.tsx:366` @ 6ac58d51)
and cut at fourteen items, eight options and two set rows without a word (`questionnaire.ts:113-160` @ 6ac58d51).
Change (feature/questionnaire-preview-range): `previewQuestion` carries the stored range as the editor reads it
(`readRange`; one it would not read is said, never guessed), the options past eight, and whether the question
has a display condition; `previewBattery` the set's object count; `previewLeftOut` the items past the fourteen.
The preview draws the scale at its range (a range over eleven points as its ends either side of "…"), the
condition line, "a stejně pro dalších n položek" under a set, and "+ n dalších položek dotazníku". 18.6.6's
fields stay as ported (parity unchanged). Tests: `questionnaire-preview.test.ts` "a 1–7 scale previews at 1–7…",
"a cut list says how many it left out…"; `QuestionnaireStep.test.tsx` "previews a scale at its own range and
says what the preview leaves out (QST11)"; `questionnaire_journey.mjs` at 1440/1100/768/390.

*QST4, spec navrh/Q4 (R9: what a run cannot do shown disabled, with the reason):* with routing off a
question's display condition was simply absent (`QuestionCondition.tsx:72-75` @ 25ce6493), and a tracked set
offered a familiarity switch that readiness then FAILs (`QuestionnaireStep.tsx:1225` @ f7b2f381, readiness
battery_familiarity at `research_design.py:1501` @ f7b2f381). Change (feature/questionnaire-unavailable-disabled): with `/config` routing known to be off,
a question that has an earlier choice question shows "Podmínka zobrazení", why, and an aria-disabled "Zapnout"
described by it, still focusable (nothing while the switch is unread or cannot be read); a stored condition still shows and can be removed. The
familiarity switch is gone: a set says why, and one stored with it says the run will refuse it, with
"Vypnout". Tests: `QuestionnaireStep.test.tsx` "offers no condition to set without the routing switch…"
(extended), "offers no familiarity switch a run would refuse…"; `questionnaire_journey.mjs` at 1440/1100/768/390.
*QST2, spec navrh/Q3 ("Měří" as short VO toggles):* each question and set listed every research question in
full as its link chips (`QuestionnaireStep.tsx` `ResearchQuestionLinks` @ 25ce6493). Change
(feature/questionnaire-vo-chips): each chip reads "VO n" (the strip's numbering), named "VO n: <question>"
(the visible label in the name) with the question as its tooltip; the linked ones are written out under the
chips, for touch. Once any item declares a link, an item linked to none says so in words, with what to do
(before that, coverage is unknown for every item, coverageOf, never a gap on each card). Dangling links stay coral. Tests:
`QuestionnaireStep.test.tsx` "shows a question's links as VO chips…"; `questionnaire_journey.mjs` at
1440/1100/768/390. QST2 stays open (Q1 and Q2 remain).

*QST2, spec navrh/Q2 (part: section numbers and the card's "měří"):* the editor headed a block "Blok n · k
otázek" and a set "SADA n", while its own outline (and the board) number them B n and S n
(`QuestionnaireStep.tsx:863`, `:1159` @ 25ce6493). Change (feature/questionnaire-sheets): a block is headed "B n"
with its count beside it and a set "S n", each spoken as "Blok n" / "Sada n". Not in this change: the card header
"Q n · type tag · měří VO n" with the type chips behind the tag in a menu, left for its own chunk so the type
control's tests and journeys move once (a "měří" line alone would repeat the list under the VO chips). Tests:
`QuestionnaireStep.test.tsx` "numbers blocks B n and sets S n as the outline does…"; `questionnaire_journey.mjs` at
1440/1100/768/390.

## Doc follow-up

- open-items.md: number QF-7 (the question's × named by its stored id), closed by fix/questionnaire-remove-label.
- open-items.md: number QF-8 (Závislosti held sets the compiler takes), closed by feature/questionnaire-set-hard-max.
- open-items.md: number QF-9 (a question's × on a row of its own at 390 px) and QF-10 ("validačním gate"), closed by fix/questionnaire-audit-390.
- open-items.md: number QF-11 (a scale's right label apart from its end at 390 px), QF-12 (the research card half English) and QF-14 (the preview's running numbers), closed by fix/questionnaire-audit-2; QF-13 (Dotazník's own Design Research start in the workbench) open, for the PM.
- open-items.md: number QF-16 (an import's failure said in English), closed by fix/questionnaire-audit-3.
- open-items.md: OI-52 answered by the data owner (2026-10-25, (b)) and closed by fix/questionnaire-plain-question (QF-17).
- open-items.md: number QF-18 (the condition editor drops keyboard focus), closed by fix/questionnaire-condition-focus.
- Register this plan and its chunks. `research-lead-workbench#7`'s questionnaire half is QST5.
- open-items.md: number QF-15 (an import replaced the questionnaire with no way back), closed by fix/questionnaire-import-undo.
- CLAUDE.md § 2 map, QuestionCondition.tsx: with routing known off, a question that could take a condition shows it disabled with the reason (QST4, R9). Tracked sets: no familiarity switch; a stored one says the run refuses it, with Vypnout.
- CLAUDE.md § map, domain/research_agents.py: "build and optimize read external_context_not_evidence (with_external_context, EXTERNAL_ACTIONS; trimmed to the 64 KB bound, a bundle that does not read named), the newest Design Research findings, never evidence, with EXTERNAL_RAIL on the system prompt whenever the layer is there (QST13)"; application/research.py: "ResearchAgentJobs(external_store=): with the API's AIA_AI_ANALYSIS_EXTERNAL_CONTEXT a questionnaire job freezes the study's pinned Design Research findings, read by analysis_results._external_context".

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**QST10. The shared set** (spec `navrh/D6` and `navrh/Q8`, one chunk; no backend; W2, lane E). `set_edit` (WCE3a), after `working-copy-edit-ops#WCE8b`. The set's scale (the board's presets, or fixed 1-10 for the Sociomap) awaits the methodology owner (OQ9).

**QST11. Respondent preview** (spec `navrh/Q5`; W1, lane E). Labels the server would leave out are named, as ScaleEditor does.

**Notes.**
- QST2 carries `navrh/Q1`, `navrh/Q2`, `navrh/Q3`; the strip moves to the inspector (register contradiction 7).
- QST4 carries `navrh/Q4`: routing and familiarity shown disabled with the reason until `run-qc-and-checkpoint#RQC11` (contradiction 6).
- QST5 carries `navrh/Q6` (per-item accept), now W1 with `working-copy-edit-ops#WCE8b` moved to W1.
- QST6 carries `navrh/Q7`, with `research-lead-workbench#26f.1`.

**QST12. One questionnaire editor** (Nigel, 26 Oct 2026 ~01:41 UTC, relayed by the PM coordinator: "its important that in the questionnaire there is no nahrat excel, sestavit rucne, sestavit with ai, becuse we only need one interface to create the question, and the user can create it manually, but can also upload an excel to the lead researcehr and the lead researcehr will create the questionnaire, if no excel is used the user can still use the lead researcher to help create it based on the previous stage inputs, client knowledgebase and deep research."). W1, lane E. Dotazník loses its "Způsob" radiogroup (`apps/web/src/i18n/cs.ts:2587-2591 @ 2e7fc1dd`, pathUpload / pathManual / pathAi) and keeps one editor, which also works on an empty questionnaire. Excel import moves to the Lead, as one use of any file given to the Lead (`lead-orchestration#LO18a`-`LO18b`), and AI drafting to the Lead's questionnaire job (`lead-orchestration#LO27`, with QST13). Ships in the same PR as LO18b, or after it, so the Excel import is never missing in between (planning's default and the Lead worker's; Nigel may split them). It belongs with #808 / QF-13, which already hides Dotazník's own workbench start. Test: Dotazník on an empty study shows the editor and no path choice; the import route stays (`apps/api/src/aia_api/routers/workspace.py:2318`).

**QST13. Verified Design Research findings in the questionnaire jobs** (Nigel, 26 Oct 2026 ~01:47 UTC, relayed by the PM coordinator: "All verified findings"). W1, for `lead-orchestration#LO27`. The two questionnaire contracts (`domain/research_agents.py`) read every verified finding of the Study's newest finished Design Research run, frozen at enqueue and labelled external context, never respondent evidence, as the Lead's `external_context_not_evidence` layer and Analýza's external context already are. A prompt version and harness bump, the frozen findings in the job's input fingerprint. Today the jobs read Design Research only where a person accepted it into the design. Test: a job enqueued after a sealed run carries its verified findings in the frozen context, and its fingerprint changes when a newer run seals.

*QST13, built (feature/questionnaire-jobs-external-context).*
- The layer: `with_external_context` (`domain/research_agents.py`) adds `external_context_not_evidence`
  (`{pin, findings}`) to a build or optimize job's frozen snapshot, so it is in `snapshot_hash` and the
  job fingerprint. A newer sealed run is a new job.
- One reader: `ResearchAgentJobs._with_external` reads the pin through `ResearchRuns.design_research_pin`
  and its lines through `analysis_results._external_context`, the reader Analýza and the Lead use. The
  pin is the newest finished Design Research bundle, public Class C findings. It is read once per
  request, so a typed start's probe and its start share one read.
- A bundle that does not read is said in the layer (`unavailable: <reason>`), as the Lead's is, never
  read as no research. The job still starts.
- Findings that would take the context past 64 KB are left out from the end and counted (`omitted`),
  so turning the switch on never refuses a job the design alone fits.
- The rule that the findings are not evidence is a fixed rail (`EXTERNAL_RAIL`), appended to the system
  prompt whenever the layer is present, after the task wording, so a stored prompt edit cannot drop it.
- No prompt or harness version bump, departing from the PM's "bump the prompt and harness version".
  - The task wording is unchanged.
  - The rail rides only with the layer, and the layer only exists with the switch on, so a job queued
    before is byte for byte what it was.
  - The layer is already in the fingerprint.
  - A harness bump fails every queued or budget-parked job of all eight actions ("harness version
    changed").
- Provenance: a proposal's provenance records `external_context` (`external_record`): the pin, the
  findings shown and left out, the reason a bundle did not read; null without the layer.
- Switch: only with `AIA_AI_ANALYSIS_EXTERNAL_CONTEXT`, which stays off. The stage's start and rebuild
  routes pass the store. The typed "Navrhni dotazník" (`approve_chat_start`) takes it from its
  `RunStartSettings` (`external_context`, `store`).
- Departure from "All verified findings": the shared reader shows at most `MAX_EXTERNAL_ITEMS` (24)
  findings, each claim cut at 400 characters (`domain/analysis/external.py:33-35`). One reader means
  the same cap Analýza's modules and the Lead see.
- The Lead's card approval of a model-prepared job (`application/research_lead.py`
  `approve_request`) passes the Lead's own `external_store`. That is one line in the coordinator's
  file, with the integration coordinator's agreement. The Lead's request route (`routers/lead.py`
  `approve_request`) gives the Lead that store under the switch, as the turn route does; the stand-in
  found it missing, so the line had no effect in production.
- Tests:
  - `test_research_agents.py::test_external_context_frames_the_findings_and_trims_them_to_the_bound`
  - `test_research_agents.py::test_the_external_rail_rides_the_system_prompt_whenever_the_layer_does`
  - `test_research_agents.py::test_questionnaire_jobs_freeze_the_pinned_findings_only_when_given_a_store`
  - `test_research_agent_jobs_api.py::test_a_questionnaire_job_reads_external_context_only_with_the_analysis_switch_on`
  - `test_lead_chat_start_api.py::test_a_typed_questionnaire_job_reads_external_context_only_with_the_analysis_switch_on`
  - `test_research_lead_application.py::test_an_approved_questionnaire_job_reads_external_context_only_with_the_leads_store`
  - `test_research_lead_api.py::test_a_card_approved_questionnaire_job_reads_external_context_only_with_the_switch_on`
