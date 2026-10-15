---
status: in-progress
chunks:
  - "[x] 1a. Analysis: a schema failure is stored with the fields that failed, and the repair turn shows the model its own rejected answer"
  - "[x] 1b. Analysis: retry failed modules over the run's frozen dataset and aggregate (no new fieldwork), as a new linked run"
  - "[x] 1c. Web: a blocked module is not \"Hotovo\"; the run offers \"Zopakovat neúspěšné moduly\"; no report download that can only fail"
  - "[x] 2a. Preflight: donor-cluster and support feasibility from the roster rules, before launch"
  - "[x] 2b. Readiness: per planned question, answerable / at risk / unanswerable, in the run screen"
  - "[x] 3a. Design: a question or tracked set names the research questions it measures; readiness traces each research question to its measures and flags one nothing measures"
  - "[x] 3b. Dotazník: link each question and tracked set to research questions; the Run screen shows the chain"
  - "[x] 3c. Comparison: each research question declares its comparison, and readiness checks its measures can carry it"
  - "[x] 3d. External source: the Deep Research evidence and gaps cited against each research question, shown in the chain"
  - "[x] 3e. The questionnaire agent proposes the links; a person accepts them with the proposal"
  - "[ ] 4. Deep Research: source diversity beyond Wikipedia, the exact supporting passage per claim, and every rejection's reason shown"
  - "[x] 5a. Population: a person chooses who answers a run (fictional roster or the population) before it starts; the deployment only says what it offers"
  - "[x] 5b. Population: the run receipt says who answered, from which population, and which selected dimensions and filters were applied"
  - "[ ] 5c. Population: selected dimensions applied to panel respondents as 18.6.6 applied them, the topic allowlist (product owner, 2026-10-15)"
  - "[ ] 6. Desktop UX: one state vocabulary (ready, running, needs repair, evidence unavailable, report ready), plain reasons, question text, cost remaining"
---

# Run recovery and truthful run state

Two fictional Fio runs on develop (50 and 200 respondents) were reviewed end to end
on 2026-10-14. This plan takes the six findings in the order of their cost to a
researcher. Every gate that held in those runs stays: the report's integrity gate
(`application/report.py`, "all eight analysis modules must be complete"), the
evidence gate, the citation gate of Deep Research, and the fail-closed population
rules. What changes is what happens *after* a gate refuses, and what the screen says.

## Findings

1. **A schema failure was recorded as "the draft is not a JSON object".** When the
   gateway refuses an answer against the output contract, the analysis runner got an
   `InvalidStructuredOutput` and `check_analysis_draft` reported one violation,
   `SCHEMA_INVALID draft: the draft is not a JSON object`
   (`packages/aia_core/src/aia_core/domain/analysis/draft.py:274-279 @ 5d545eb`).
   The stored BLOCKED outcome therefore never said which field failed; the per-field
   violations lived only in the turn checkpoints.
2. **The repair turn hid the model's own answer.** A repair turn after a schema
   failure sent `(no draft: the previous answer did not match the output schema)` as
   the assistant message (`domain/analysis/harness.py:92,183-188 @ 5d545eb`), because
   the gateway's `ModelCallFailed` did not carry the rejected text
   (`application/model_gateway.py:654-665 @ 5d545eb`). The model was told which paths
   were wrong but not shown what it wrote, so each repair was a fresh draft and could
   fail the same way. A truncated answer got no instruction to be shorter.
3. **A blocked module could not be retried without paying for fieldwork again.**
   `ResearchRuns.retry` starts a new run (`application/research.py:377-404 @ 5d545eb`)
   whose AI fieldwork keys its dataset on the attempt
   (`apps/executors/src/aia_executors/research.py:368-371 @ 5d545eb`): 200 respondents
   are bought again to re-ask three modules.
4. **A blocked module shows "Hotovo".** `stepTone` maps SUCCEEDED to done and never
   reads `output.outcome` (`apps/web/src/lib/research-execution.ts:42-53 @ 5d545eb`).

## 1a — diagnostics and an informed repair

- `InvalidStructuredOutput` moves into the domain's draft module (re-exported by the
  harness) and `check_analysis_draft` turns it into one `SCHEMA_INVALID` violation
  per failed path, so the stored outcome names the fields. The violations are paths
  and validator messages, never values.
- `ModelCallFailed.rejected_output`: the gateway's rejected text on a schema failure,
  bounded (`MAX_REJECTED_OUTPUT_CHARS`). The turn checkpoint keeps it
  (`TurnArtifact.rejected_output`, optional, so stored turns still parse), so a
  replayed repair sends exactly what the original did.
- The repair turn shows the rejected answer as the assistant message when there is
  one, and after a truncation asks for a shorter answer instead. Harness version
  `aia-analysis-harness-2`: every module's reuse key moves, so no earlier BLOCKED
  outcome is reused under the new repair.

Trade-off: a new harness version means completed modules over the same sources are
not reused across the change; runs on AI fieldwork never reuse across runs anyway.

## 1b — retry failed modules

`POST /studies/{id}/research/runs/{run}/analysis/retry`: a new run, linked by
`retry_of`, whose `run` step takes the original run's dataset by artifact id and
SHA-256 instead of producing one (`frozen_dataset` in its step input; verified on
read, refused on mismatch). The aggregate then recomputes to the same bytes and is
reused; COMPLETED modules are reused by their reuse key and cost nothing; each
module that a *model* blocked is asked again in a new round (`analysis_round`, part
of its turn keys and its blocked outcome's key, so a crash inside the round still
replays and a new round never does). A module the preflight blocked stays blocked:
code refused it, and nothing new would be learnt. The cost ceiling counts only the
modules that will be asked.

Landed as designed, with two findings on the way:

- `ArtifactRepository.put` reuses by fingerprint, so a retry round that stored its
  COMPLETED outcome under the module's reuse key got the earlier BLOCKED artifact back
  while its step output said COMPLETED. A round stores with `reuse=False`, and
  `find_reusable` now orders newest first within a revision (`created_at`, then id) so
  the lookup is deterministic when one key holds two outcomes.
- The cost ceiling of a retry counts the retried modules plus any completed module whose
  stored harness is not today's (its reuse key moved and it will be asked again), and no
  fieldwork.

Tests: `test_retrying_failed_modules_asks_only_them_over_the_same_data`,
`test_a_retry_round_asks_again_what_the_model_refused_and_replays_nothing_old`,
`test_a_retry_whose_dataset_does_not_match_its_bytes_is_refused_not_collected_again`,
`test_a_retry_refuses_a_run_that_has_not_finished_or_ran_no_analysis`
(`apps/executors/tests/test_analysis_executor.py`);
`test_retrying_analysis_says_why_a_run_has_nothing_to_ask_again` (API);
`test_an_analysis_retry_buys_no_fieldwork_and_only_the_modules_it_asks`,
`test_a_retry_round_is_its_own_turn_key_and_round_zero_keeps_the_old_one`.

Review findings (Codex on #405), both fixed:

- The retry read outcomes through `reconstruct_run`, which refuses any outcome whose
  stored harness is not today's (`fingerprint_mismatch`), so every run stored under
  harness 1 -- the very runs this repairs -- got a 409. The retry now reads outcomes as
  stored (`stored_analysis`: bytes verified, contract parsed, nothing re-judged), and
  the screen asks `GET …/analysis/retryable`, which does the same.
  Test: `test_a_run_stored_under_the_previous_harness_can_still_be_repaired`.
- A run cancelled after fieldwork had its cancelled modules counted as retryable while
  the run status was refused. CANCELLED is finished for an analysis retry.
  Test: `test_a_run_cancelled_after_fieldwork_has_its_cancelled_modules_asked_over_its_data`.

## 1c — the run screen

- Each step of `GET …/research/runs/{id}` carries `analysis_outcome` (COMPLETED /
  BLOCKED for an analysis step). A BLOCKED module's step reads "Potřebuje opravu" in the
  fault tone, not "Hotovo" (`needsRepair`, `research-execution.test.ts`).
- `GET …/analysis/retryable` lists the modules a retry would ask. A finished run with any shows a card
  saying the data stands, which modules a model could not complete, and the action
  "Zopakovat neúspěšné moduly"; the whole-run retry beside it is demoted and says it
  collects the data again.
- The internal report already offers its download only when the report is READY
  (`ExecutionSteps.tsx` `InternalReport`). The download that could only fail is the
  contextual report's, in `InterpretationResearch.tsx`: chunk 6.

## 2a — support forecast before launch

The 50-respondent run's 15 donors were not bad luck. Fieldwork seeds its roster from the
specification (`fieldwork_seed`, now in `domain/ai_respondent.py`) and draws donors with
replacement from `max(3, n // 3)` ids (`domain/ai_respondent.py` `fictional_roster`; the
Metodika tab already records it as D6, `test_d6_a_fictional_roster_draws_too_few_distinct_donors_for_support`).
So the donors a run will have are known from its design.

`domain/support_forecast.py` draws that roster and runs it through the aggregate's own
`donor_support` (results rule) and the analysis gate's `reassess_support` (analysis rule),
both under the support rules a start would pin. `ResearchRuns.readiness` adds a
`support_forecast` check for an `ai_runtime` run:

- **SUPPRESS (analysis)**: WARN. Every number will be suppressed for analysis, so neither
  the analysis nor the report will be produced. The check names the smallest n, everything
  else unchanged, that the gate admits; the search goes up to `max(4n, n + 200)`.
- **INDICATIVE**: WARN, and the numbers will show with weak support.
- **REPORTABLE**: PASS, as long as respondents do not skip answers.
- **A panel run**: WARN that the count is unknown until fieldwork draws respondents (the
  audience preview shows the selected donors). An unknown count is never scored as good.

A forecast never FAILs. It says what the run will show; whether to pay for that is still
the person's call. It is an upper bound, because an empty answer lowers a question's donors.

Review (Codex on #416):
- **The aggregation formulas a start would pin are applied.** `ResearchRuns._aggregation`
  is compiled with `read_aggregation_pin`, so a version replacing Kish's formula changes
  the forecast as it changes the aggregate.
  Test: `test_the_aggregation_formulas_a_start_would_pin_are_applied`.
- **The search for a sufficient n is bounded.** It draws at most 40,000 respondents over
  all its candidates, about 1 s, so one readiness read stays bounded whatever rules are in
  force. Test: `test_the_search_for_a_sufficient_n_is_bounded_whatever_the_rules`.
- **The test's design is its own.** It is no longer imported from another test module
  (`AGENTS.md` § pytest).

Tests:
- `packages/aia_core/tests/test_support_forecast.py`
- `test_the_support_forecast_is_what_the_aggregate_then_computes[50|150]`: a real AI-runtime
  run's aggregate carries exactly the forecast's donors and status.
- `test_readiness_forecasts_whether_a_runs_numbers_will_be_shown` (API)

## 2b — which questions a run will answer

2a gives one status for every question, because every question is asked of every
respondent. A design can pass it and still pay for questions that come back empty, for
reasons just as certain before launch:

- the unit's fidelity rule refuses a question about absolute willingness to pay or market
  size (`research_aggregate.evidence_rating`, mode `REFUSE`);
- the analysis gate then removes every row of that question (`analysis/native.py`
  `_fidelity_refusal`);
- an open question's verbatims are never evidence.

The Run screen named none of this.

`domain/question_outlook.py` gives every item a respondent will answer (each question,
and each object of each tracked set, worded as fieldwork asks it) one verdict, with every
reason behind it:

- **UNANSWERABLE**:
  - `conditional` and `familiarity`: it cannot be asked;
  - `fidelity_refused`;
  - `support_suppressed`, from the 2a forecast.
- **AT_RISK**: `open_ended`, or `support_indicative`.
- **UNKNOWN**: `support_unknown`. This covers a panel run, and a source with no forecast
  (the workbench's fixture). Unknown is never answerable.
- **ANSWERABLE**: none of these reasons applies. This is still an upper bound.

The worst verdict wins. The reasons are codes, and the screen words them
(`research.exec.outlook.reason.*`).

`ResearchRuns.outlook` returns the specification, the readiness and the outlook from one
forecast; `readiness` reads it. `GET …/research/readiness` carries `question_outlook`.
The outlook is kept out of `Readiness` on purpose: the preflight step stores `Readiness`
in its artifact, and a new field would change every preflight artifact's bytes.

The Run screen's card "Na co běh odpoví":

- the counts per verdict;
- every item the run will not fully answer, worst first, by its wording, with the reasons
  in words and a fix link (the questionnaire for a question's own fault, Dimenze for
  support);
- what it will answer, folded away.

Review (Codex on #419): a version whose results rule is looser than its analysis rule
shows a question's numbers on Results while the analysis suppresses them. That is now
`support_analysis_excluded` (AT_RISK, "Results shows them, the analysis may not cite
them"), and `support_suppressed` stays for numbers Results hides too. Test:
`test_numbers_results_shows_but_the_analysis_may_not_cite_are_at_risk_not_suppressed`.

Tests:

- `packages/aia_core/tests/test_question_outlook.py`, including
  `test_what_the_outlook_refuses_the_analysis_gate_then_removes`: over a real aggregate,
  a refused question keeps no row in the evidence table and an open question keeps no
  content row.
- `test_readiness_lists_every_question_with_whether_the_run_will_answer_it` (API).
- `research-execution.test.ts` ("which questions a run will answer").
- `ExecutionSteps.test.tsx` ("Run: which questions the run will answer").

## 3a — each research question traced to its measures

The analysis module `research_questions` must answer every research question the design
states (`analysis/draft.py`: `RESEARCH_QUESTION_UNANSWERED`). It can cite only the numbers
the run produces. Until now, nothing tied a measure to a research question:

- research questions are plain strings (`research_agents.py` `BriefAnalysis`);
- a question carries no link (`questionnaire.ts` `Question`);
- `compile_design` never reads `research_plan`.

So a research question nothing measured was found only after fieldwork, as a blocked
module.

- **The link is a declaration on the item.** A question, or a tracked-set section, may
  carry `research_questions`: the texts of the research questions it measures, as the
  plan states them.
  - `compile_design` reads it into `SpecQuestion.research_questions` and
    `SpecBattery.research_questions`, with whitespace collapsed, each once, in order.
  - Anything but a list of texts is a compile problem (`invalid_research_question_links`).
    It is never guessed.
  - An empty or absent declaration stays out of the fingerprint, as `rating_item` does:
    a design without links compiles to the fingerprint it always had (pinned in
    `test_a_link_is_compiled_as_declared_and_an_undeclared_one_keeps_the_fingerprint`).
  - It links by text, not id, because research questions have no ids. The analysis gate
    matches by text too. A link whose text is no longer stated is reported as dangling,
    never re-pointed.
- **`domain/research_trace.py`** traces each research question, as the analysis will read
  it (`research_questions_of`), to the items that declare it. It takes the best verdict
  among them from the 2b outlook (a research question is as answerable as its best
  measure):
  - with no measure: UNANSWERABLE, reason `unmeasured`;
  - in a design that declares no link at all: UNKNOWN for every research question, reason
    `unlinked_design`, never covered.
- **Readiness** adds `research_question_coverage`. It is a WARN, never a FAIL, when:
  - there are no research questions (the module will block);
  - there are no links;
  - a research question is unmeasured;
  - every measure of a research question is unanswerable;
  - a link is dangling.
  It is a PASS when every research question is measured.
- **`ResearchRuns.outlook`** returns the trace beside the outlook, and
  `GET …/research/readiness` carries `research_trace`.

Review (Codex on #421), both fixed:

- **A question whose id equals a set item's generated id** (`<set>_obj_<object>`) took that
  item's links in the trace. Worse, it shared the item's column in fieldwork, because a
  respondent's answers are kept by item id (`ai_respondent.py` `answers[item.item_id]`).
  The compiler now refuses such a design (`item_id_collision`, the question named).
  Test: `test_a_question_whose_id_is_a_set_items_id_is_refused_not_merged`.
- **The Run card hid dangling links** when the plan stated no research question. It now
  shows while either list has entries. Test: `ExecutionSteps.test.tsx` ("keeps the card
  for stale links").

Tests:

- `packages/aia_core/tests/test_research_trace.py`
- `test_readiness_traces_each_research_question_to_the_questions_that_measure_it` (API)

## 3b — the link in Dotazník and the chain on the Run screen

- **`src/research/trace.ts`**, pure:
  - `researchQuestionsOf` reads research questions as the server's `research_questions_of`
    does: the plan's research questions, else its objectives, else the goal; at most eight.
  - `linksOf` and `danglingLinks` read an item's declaration.
  - `toggleQuestionLink` and `toggleSectionLink` write it. An empty declaration is
    removed, not written as `[]`.
- **Dotazník:** every question card and tracked set shows "Odpovídá na výzkumné otázky",
  a toggle per stated research question (`aria-pressed`). A link the plan no longer states
  is shown in the warning tone, to remove. Saves use the reason `questionnaire_links`.
- **Run screen:** a "Výzkumné otázky a jejich měření" card lists each research question
  with:
  - its verdict;
  - its reasons in words;
  - its measures by their wording, a tracked set listed once with its object count and
    best verdict (`traceMeasures`);
  - a fix link to Dotazník for any research question not answerable.
  Dangling links are listed under it.
- **Not done:** editing a research question's text in the plan does not carry its links
  along. Matching by index breaks when questions are inserted or reordered, so the link
  goes dangling where the person sees it.

Tests:

- `trace.test.ts`
- `QuestionnaireStep.test.tsx` ("says which research question a question and a set
  measure")
- `research-execution.test.ts` ("a research question's measures in words")
- `ExecutionSteps.test.tsx` ("traces each research question to its measures")

## 3c — how each research question is answered

The product owner chose a closed set, checked against what the run can produce
(2026-10-15, in session). Free text was the alternative, but it could not flag anything
before a paid run.

- **The declaration.** `research_plan.research_question_comparisons` maps a research
  question's text (whitespace collapsed, as links match) to one of `describe`,
  `rank_objects`, `compare_segments` or `ab_test`. It lives in the working content, not in
  the specification. The run executes nothing differently, so no fingerprint moves.
- **The check.** `domain/research_trace.py` (`comparisons_of`, `Comparison`) checks each
  declared comparison against the research question's measures:
  - `describe`: any measure.
  - `rank_objects`: a tracked set with at least two primary objects among the measures.
    The verdict is that set's, not the best of every measure.
    Otherwise `comparison_needs_tracked_set`.
  - `ab_test`: a `test_konceptu` set of at least two concepts. Otherwise
    `comparison_needs_concept_set`.
  - `compare_segments`: always `segments_unavailable`, UNANSWERABLE. No native run gives its
    analysis segment evidence, and the segments module says segmentation cannot be assessed
    without it (`analysis/modules.py` SEGMENTS).
  - A kind AIA does not know is `comparison_unknown`, UNKNOWN. An undeclared comparison is
    not checked.
- **Readiness.** The `research_question_coverage` check names each comparison failure in
  its own words, apart from "measured only by questions the run will not answer".
- **API and web.** `research_trace.questions[].comparison` carries the declared kind.
  - Dotazník opens with "Jak výzkumné otázky zodpovíme": one choice per research question,
    saved with the reason `research_question_comparison`.
  - The Run card shows "Odpověď: …" and the reason in words.

Tests:

- `test_research_trace.py`: comparisons read, ranking, A/B, segments, unknown and
  undeclared.
- The API trace test, 3c part.
- `trace.test.ts` (setComparison / comparisonOf).
- `QuestionnaireStep.test.tsx` ("declares how each research question is answered").
- `ExecutionSteps.test.tsx` (the trace card's comparison row).

## 3d — what Design Research found for each research question

A Design Research run already researches each research question as a subject:

- the subject's origin is `research_plan.research_questions[i]` (`planning.py` `extract_subjects`);
- its proposal lists, per subject, the accepted findings (EVIDENCE) or none (GAP)
  (`design_proposals.py` `design_research_proposal`);
- its bundle keeps every quarantined finding with its reason.

None of this was shown beside the research question. The panel in Dotazník showed accepted
findings in one list and only a count of the rejected.

- **`src/lib/design-evidence.ts`** (pure):
  - `latestDesignRun` returns the study's newest finished `DESIGN_RESEARCH` run, never an
    interpretation run.
  - `questionEvidence` joins one research question, by its text as the run studied it, to:
    - its findings;
    - every rejection on it or on a question × object cross of it, counted by reason;
    - whether the run studied it at all. A research question added after the run reads
      "nezkoumal", never as a gap.
- **The Run card** reads the run, its proposal and its bundle through the existing routes,
  which need EDIT_STUDY; a reader sees the trace without them. Under each research
  question it shows:
  - up to three findings, each with its quote and source;
  - or the gap, or that the run did not study it;
  - "Zamítnuto: N× <reason>" for the rejected.
  The card says this is external context for the design, never respondent evidence.
- **Reason words.** The sixteen quarantine reasons have Czech words, held equal to
  `QuarantineReason` by `test_every_quarantine_reason_has_words_on_the_run_screen`.

Not done: source diversity beyond Wikipedia, which is priority 4's own engine work and needs
the priced routes signed off (ADR 0022).

Tests:

- `design-evidence.test.ts`
- `test_quarantine_reason_words.py`
- `ExecutionSteps.test.tsx` ("shows what Design Research found per research question")

## 3e — the questionnaire agent proposes the links

3a–3c let a person link each item to the research questions it measures and declare how
each research question is answered. The agent that writes the questionnaire knew which
research question each question was for, and said nothing. Every link was typed by hand.

- **The contract** (`domain/research_agents.py`, harness 3). Every field stays required,
  so the contract stays strict-compatible (`schema_supports_strict`):
  - `Question.research_questions` and `BatterySection.research_questions`: the research
    questions the item measures, by text.
  - `BatterySection.output_type`: `pozicni_mapa` or `test_konceptu`. Without it, the
    agent cannot propose the set an A/B answer needs.
  - `QuestionnaireProposal.comparisons`: one `{research_question, comparison}` per research
    question, from the closed set of 3c.
- **The mapping** (`proposal_result`). Code keeps a link only when it names a research
  question the design states (`research_questions_of`, compared as links compare). Any other
  link is dropped and named in the result (`dropped_links`): an agent never invents a
  research question by linking to it. An empty list is no declaration, so the key is left
  out. Proposed comparisons replace the declared ones for the research questions they name;
  the rest stay.
- **The prompt.** The build and optimize task wording says to link every item to the stated
  research questions and to declare each comparison. Those two prompts move to baseline
  version 3; the others stay at 2. A stored edit keeps its own wording, and its model still
  sees the fields in the schema.
- **The review.** The inline proposal review lists each research question with what the
  proposal measures it by and how it would be answered. It names any research question
  the proposal leaves unmeasured. Accepting the proposal accepts the links with it: the
  same one decision, recorded once (ADR 0019 gate 1).

Tests:

- `test_research_agents.py`: links kept by text, an unstated link dropped and named,
  comparisons merged, the contract strict-compatible.
- `test_prompt_upgrade.py`: each action's baseline version.
- `trace.test.ts` (`proposedTrace`).
- `ProposalReview` test: the research questions in the review.

## 5 — who answered, chosen and said

The 200-respondent Fio run recorded LIVE as its population, but its answers came from the
fictional roster. Six dimensions were selected and saved, and none was applied. Both were
true and both were said only in small print: the run's population note
(`research-execution.ts` `populationNote`) and a readiness WARN (`research_design.py`
`dimensions`).

The persona source was one deployment switch, `AIA_AI_POPULATION_PERSONAS_ENABLED`, applied
to every run (`routers/research.py` `_persona_source`). A study could not choose, and a
person starting a run never saw that a choice existed.

- **5a — the choice.**
  - Readiness takes `persona_source` (the source to assess the design under) and answers
    `persona_sources`: each source with whether the deployment offers it, and the reason it
    doesn't. The roster is always offered under `ai_runtime`; the panel only with the switch on.
  - Start takes `persona_source`. A source the deployment does not offer is refused by name
    (409 `persona_source_unavailable`) and nothing starts; it is never swapped for the other.
  - Omitted, it is the deployment's default, so an older client keeps today's behaviour. The
    switch now means "the panel is offered and is the default", not "every run is panel".
  - The Run stage's "Kdo bude odpovídat" shows both, with the offered one preselected. It
    re-reads readiness under the chosen source, since the support forecast and the audience
    check differ, and sends the choice.
- **5b — the receipt.**
  - A start records what the design selected (`selection`: dimensions, audience filters) and
    what was applied: filters only under the panel source, dimensions never yet (5c), each with
    its reason.
  - The run response carries it. The Run, Progress and Results screens show one receipt:
    - who answered: the pinned source beside the origin its fieldwork data reports, with a
      mismatch named, never resolved by picking one;
    - the population recorded, and whether fieldwork read it;
    - each selected dimension and the filters, applied or not, and why.
  - A run started before 5b says the selection was not recorded, never "none".
- **5c — dimensions on respondents.** The product owner decided on 2026-10-15, in session,
  that a study's selected dimensions are applied to the respondents drawn from the population.
  18.6.6 applied them in one way, and AIA ports exactly that:
  - The approved dimensions became the run's `persona_topic_allowlist`
    (`legacy/npc-panel-18.6.6/app/research_project.py:440`).
  - In a block request, each question's topics were filtered to the allowlist before the
    block's union (`dotaznik.py:937-948`). A respondent's profile and catalog signals are then
    drawn from those topics only. A block left with no topic gets the core profile.
  - The dimension ids are the persona topic keys (`media`, `nakup`, `finance`, …;
    `persona_topics.py`, the web's `PERSONA_DIM_LABELS`). An id that is no topic filters
    every topic out, as the unit's set test did.

  In AIA:
  - `persona_topics.block_topics(…, allowlist=)` filters per question, as the unit did.
  - `PanelPersonas.plan` reads the allowlist from the specification's selection.
  - A panel run with selected dimensions is its own identity
    (`:persona-topics:<fingerprint>`), so a start never returns a panel run computed before
    the allowlist applied.
  - The receipt says dimensions await the draw, as filters do, and are applied once the
    population draw has succeeded. The roster has no topic signals, so a roster run says the
    dimensions need a population draw.
  - **One deviation from 18.6.6** (product owner, 2026-10-15, after Codex on #447): the
    catalogue's `ekologie` is not a topic key, so in the unit it let nothing through; AIA maps
    it to `eko` (`persona_topics.DIMENSION_TOPICS`, `test_persona_topics_allowlist.py`). Any
    other id that is no topic -- `komunikace` today -- still lets nothing through, and the
    receipt names it (`dimensions_unmatched`); a drawn run with only such ids says
    `dimensions_not_persona_topics`, never applied. `komunikace` awaits the owner's mapping.
- **4 — sign-off.** On 2026-10-15, in session, the product owner signed off on building the
  priced search routes (ADR 0022). Each organization still approves its live settings on
  Settings → Deep Research before a priced route runs.

## Doc follow-up

- `CLAUDE.md` § map, `analysis.py`: "a schema failure is stored per field; the
  repair turn shows the model its rejected answer (harness 2); `analysis_round`: a
  person's retry is a new round".
- `CLAUDE.md` § map, `application/analysis_results.py` (new line):
  "retry_failed_modules: a finished run's failed modules asked again as a new linked
  run over its frozen dataset (no fieldwork); completed modules reused".
- `CLAUDE.md` § map, routers/research: "POST …/runs/{id}/analysis/retry".
- `ARCHITECTURE.md` / `CLAUDE.md` § research run: the fieldwork step may take a frozen
  dataset (`frozen_dataset`: artifact id + SHA-256, verified, never substituted).
- `AGENTS.md`: a strict Pydantic validation error's `msg` carries no input value,
  but `str(ValidationError)` does; diagnostics are built from `loc` + `msg` only.
- (1a–1c above applied by AiAnalytics-AIA/AIA#414.)
- 2a, `CLAUDE.md` § map, domain (new line after `ai_respondent.py`):
  "support_forecast.py: a run's evidence support forecast from the roster fieldwork will
  draw (fieldwork_seed + fictional_roster through donor_support and reassess_support,
  under the pinned support rules); unknown for a panel run, never good; readiness adds
  it as the support_forecast check (WARN, never FAIL) for an ai_runtime run".
- 2a, `CLAUDE.md` § map, `ai_respondent.py`: append "fieldwork_seed: the roster and
  draw seed from the specification (moved from the executor)".
- 2a, `CLAUDE.md` § map, `application/research.py`: "readiness(…, fieldwork_source=):
  with ai_runtime, the support forecast under the support rules a start would pin".
- 2b, `CLAUDE.md` § map, domain (new line after `support_forecast.py`):
  "question_outlook.py: before a run, every item a respondent will answer with one verdict
  (ANSWERABLE / AT_RISK / UNKNOWN / UNANSWERABLE) and its reasons (conditional,
  familiarity, fidelity_refused, open_ended, support_*), by the rules that decide after
  the run; unknown never answerable".
- 2b, `CLAUDE.md` § map, `application/research.py`: "outlook(): the specification,
  readiness and question outlook from one forecast (RunOutlook); readiness reads it".
- 2b, `CLAUDE.md` § map, routers/research: "GET …/research/readiness carries
  question_outlook"; web `ExecutionSteps.tsx`: "the Run stage's 'Na co běh odpoví' card".
- 3a, `CLAUDE.md` § map, domain (new line after `question_outlook.py`): "research_trace.py:
  each research question (as research_questions_of reads it) traced to the items that
  declare they measure it (research_questions on a question or a tracked set, by text), as
  answerable as its best measure; unmeasured, unlinked (unknown) and dangling links named;
  readiness's research_question_coverage (WARN, never FAIL)".
- 3a, `CLAUDE.md` § map, `research_design.py`: append "a question's or set's
  research_questions: the research questions it measures, by text; out of the fingerprint
  when empty; a question whose id is a set item's id refused (item_id_collision)".
- 3a, `CLAUDE.md` § map, routers/research: "GET …/research/readiness carries
  research_trace".
- 3b, `CLAUDE.md` § map, web `src/research/`: "trace.ts: which research question each
  questionnaire item measures (researchQuestionsOf, as the server reads them; the link
  read and toggled)"; `QuestionnaireStep`: "Odpovídá na výzkumné otázky on every question
  and tracked set"; `ExecutionSteps.tsx`: "the Run stage's 'Výzkumné otázky a jejich
  měření' card"; `research-execution.ts`: "traceMeasures".
- 3c, `CLAUDE.md` § map, `research_trace.py`: append "; research_plan.research_question_comparisons
  (describe / rank_objects / compare_segments / ab_test, by text) checked against the
  measures: ranking needs a tracked set, A/B a concept-test set, segments unavailable,
  unknown never answerable (comparisons_of)"; web `trace.ts`: "comparisonOf /
  setComparison"; Dotazník: "Jak výzkumné otázky zodpovíme".
- 3d, `CLAUDE.md` § map, web `src/lib/`: "design-evidence.ts: what the newest finished
  Design Research run found per research question (latestDesignRun, questionEvidence:
  findings, gap or not studied, rejections by reason)"; `ExecutionSteps.tsx`: the trace
  card shows it under each research question; `api.ts`: `deepResearch.designProposal`.
- 3e, `CLAUDE.md` § map, `research_agents.py`: "Eight closed Research task contracts …";
  append "; the questionnaire contract (harness 3) proposes each item's research_questions,
  a set's output_type and each research question's comparison; proposal_result keeps only
  links to stated research questions (dropped_links names the rest); prompt_version_for:
  build/optimize at 3, the rest at 2". Web `trace.ts`: append "proposedTrace (a proposal's
  links, read on the inline review)"; `ProposalReview`: "a questionnaire proposal's research
  questions, their measures and answers, before it is accepted".
- 5a, `CLAUDE.md` § map, routers/research: "readiness and start take persona_source; readiness
  answers persona_sources (offered, reason, default); an unoffered source is 409
  persona_source_unavailable". `CLAUDE.md` § A research run (the persona-source paragraph):
  "AIA_AI_POPULATION_PERSONAS_ENABLED offers the panel and makes it the default; a person
  chooses per run on the Run stage ('Kdo bude odpovídat')".
- 5b, `CLAUDE.md` § map, `research_design.py`: append "selection_receipt: what a run records
  of its design's selection, dimensions never applied yet, filters only by a population draw";
  routers/research: "a run's selection"; web `research-execution.ts`: "respondentReceipt: the
  pinned source beside the fieldwork data's origin, a mismatch named"; `ExecutionSteps.tsx`:
  "'Kdo odpovídal' on Progress and Results replaces the population note".
- 5c (open, for `open-items.md`): applying a selected dimension to panel respondents needs the
  product owner's decision; no persona reads a materialized dimension
  (`panel_persona.py` `panel_personas`, `wanted`).
