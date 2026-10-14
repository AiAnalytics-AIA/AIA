---
status: in-progress
chunks:
  - "[x] 1a. Analysis: a schema failure is stored with the fields that failed, and the repair turn shows the model its own rejected answer"
  - "[x] 1b. Analysis: retry failed modules over the run's frozen dataset and aggregate (no new fieldwork), as a new linked run"
  - "[x] 1c. Web: a blocked module is not \"Hotovo\"; the run offers \"Zopakovat neúspěšné moduly\"; no report download that can only fail"
  - "[x] 2a. Preflight: donor-cluster and support feasibility from the roster rules, before launch"
  - "[x] 2b. Readiness: per planned question, answerable / at risk / unanswerable, in the run screen"
  - "[ ] 3. Proposal editor: research question -> measure -> comparison -> external source, unanswered questions flagged before a paid run"
  - "[ ] 4. Deep Research: source diversity beyond Wikipedia, the exact supporting passage per claim, and every rejection's reason shown"
  - "[ ] 5. Population: a study-scoped, governed source choice; the source and dimensions actually used on the run receipt"
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

Tests:

- `packages/aia_core/tests/test_question_outlook.py`, including
  `test_what_the_outlook_refuses_the_analysis_gate_then_removes`: over a real aggregate,
  a refused question keeps no row in the evidence table and an open question keeps no
  content row.
- `test_readiness_lists_every_question_with_whether_the_run_will_answer_it` (API).
- `research-execution.test.ts` ("which questions a run will answer").
- `ExecutionSteps.test.tsx` ("Run: which questions the run will answer").

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
