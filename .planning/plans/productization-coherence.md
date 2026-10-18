---
status: in-progress
chunks:
  - "[x] PC1. A closed study reads as closed: the frame says delivered / archived / cancelled, editors and work actions are read-only with the reason, downloads and approval stay, and every refusal is study_closed in Czech"
  - "[x] PC2. Results read the run's own verdicts: an answer to a research question the run recorded as a gap is marked as in the report, and a number the analysis refuses says so beside it"
  - "[x] PC3. A run's analysis stays repairable after a harness change: a module completed under an earlier harness is asked again over the frozen data, never a paid fieldwork re-run"
  - "[x] PC4. Work that waits for a person can go on: a run, Deep Research run or client-source proposals parked for the AI runtime resumes on a person's action once it is on, an agent job or Deep Research run stopped at the budget cap is lifted like a research run's step, and no copy promises it continues by itself"
  - "[ ] PC5. The stage track follows the run (done), and says when the design changed after the run it shows"
  - "[x] PC6. Proposal review names what acceptance replaces"
  - "[x] PC7. Researcher copy agrees with the Sociomap register and ADR 0018: no D6 or 18.6.6 remedies, no stale report sentence"
  - "[x] PC8. The browser journeys pass on today's interface, a label they wait for cannot drift unnoticed, and the coherence journey and report render are committed tools anyone can rerun"
  - "[ ] PC9. Report body and appendices flow: no page break before every chapter (owner D5, 2026-10-17)"
  - "[x] PC10. Dimenze shows and saves only the dimensions a person chose: a new study chose none (owner, 2026-10-18; OI-54)"
  - "[ ] PC11. Product-level acceptance scenarios over the real start, worker and report"
  - "[ ] PC12. Owner decisions recorded with a recommendation each; no code"
  - "[x] PC13. A start that finds the run a design already has says so, and an AI ask that ended without a proposal is asked again as a new round"
  - "[x] PC14. A finished run reads as finished: its untouched steps say they will not run, its report is not 'composing', a run waiting for a person beside steps still running is read, and a step stopped for recovery says why"
  - "[x] PC15. A question carrying an 18.6.6 display condition says so in Dotazník and the condition can be removed there; readiness no longer sends anyone to the retired classic interface"
  - "[ ] PC16. Rewording a research question carries its links to the questions that measure it, or names the ones it would orphan, before the change is saved"
  - "[x] PC17. Reports and maps say what they contain: the client report promises maps only when it has them, a run without maps says why, putting an edited Sociomap in force says its maps will be internal, and a literature report refused for a stale analysis says so in Czech"
  - "[x] PC18. Deep Research and refusals say what happened: the questionnaire's panel shows only design-checkpoint runs, a run that sent no query never reads as a search that found nothing, and no refusal reaches the screen as an empty message"
---
# Productization and system coherence

Owner's request (2026-10-17, in session): after #477, find whether AIA forms one coherent,
efficient and trustworthy internal research product end to end, decide the work worth doing next,
and implement what is safe without owner methodology or product decisions.

This plan is written before the code (CLAUDE.md § 4). Its findings ledger, decision ledger and
the evidence behind each chunk are filled in as the audit lands; every claim about code is
anchored `file:line @ 20b24bb` (#477's head, the base of this branch) unless it says otherwise.

## Method

- Sixteen read-only subsystem audits, each followed by an adversarial verifier that tried to refute
  every finding against the code, and a second skeptic for every surviving P0/P1.
- The product walked at runtime on the UI workbench (local API, worker and web on SQLite, the
  workbench composition: fictional respondents, no model, USD 0), with screenshots.
- Reports rendered from the executor journey (scripted models, recorded web, USD 0) and converted
  by LibreOffice, then read.

## Constraints this work keeps

- No paid call, no deploy, no AWS change, no approval of a source, report or population.
- No methodology change: no formula, default, evidence rule, field policy or population construction
  moves. Where a finding touches one, it is a decision for the owner below, not a chunk.
- #477 is not regressed: its answerability, report-variant and literature work is read, never
  rewritten; its own remaining chunks (5-9) stay its own.
- Feature PR rules (CLAUDE.md § 1): no shared document is edited here; what they must say is under
  Doc follow-up.

## PC1 — a closed study reads as closed

**Problem.** A delivered, archived or cancelled study opened fully editable. Every autosave was
refused as `insufficient_role` with "Your role on this study does not permit that." and a
"Zkusit znovu" that could never succeed; the Run stage offered "Spustit výzkum" and failed in
English. Reproduced on the workbench (seeded DELIVERED study: 403 `PUT …/workspace/content`).

**Proof.** `can_edit` read only `EDIT_STUDY` (`routers/workspace.py:1976, 2004 @ 20b24bb`), which every
member holds since ADR 0019, while every write refuses a closed study (`require_open_study`,
`domain/scope.py:740-750`); the workspace router's `_forbidden` named every refusal a role
(`routers/workspace.py:626-630`). The frame read `can_edit` alone (`ResearchStudy.tsx:45`) and the
same flag gated report download and approval (`CompleteReport.tsx:351, 376`), so folding the status
into it alone would have taken a delivered study's report away.

**Change.** The API says two things: `can_edit` (may change and start work now: the permission on
a study that accepts work, also on the working content) and `can_review` (may read, download,
approve, stop what runs: the permission alone), plus the study's `delivered_at`. A closed study's
refusal is `study_closed`. The frame carries `closed`; every stage says once what the study is, what
still works and where it is reopened (Settings → Studie a rozpočty: the only place a status changes
today); the design stages and their inspector column are one disabled fieldset; the store neither
changes nor saves read-only content and stops, without a retry, when a study is closed under it.
Download, approval, choosing a literature review, preparing a variant and cancelling a run follow
`can_review`, which is what the API allows on a closed study.

**Invariant kept.** No server rule moved: what a closed study refuses and allows is exactly what
`require_open_study` and the routes already decided; the browser now says it.

**Tests.** `test_a_closed_study_reads_as_closed_and_its_refusal_names_the_closure` (×3 statuses);
store "never changes or saves content that may not change here", "stops saving a study closed after
it was opened"; ResearchScreen "says a delivered study is closed…"; ExecutionSteps "still downloads
and approves the report of a delivered study". Runtime: the workbench's persona study delivered,
then Zadání / Kontrola / Výsledky read; reopened afterwards.

**Not changed (owner decisions, below).** What delivery means (which report it names, whether it
freezes anything, who may reopen) and whether report approval and new drafts are allowed after it.

## PC5 — the stage track follows the run

**Problem.** On the workbench a run finished ("Výsledky jsou hotové", 7 of 7 steps) while the stage
track above it still said "Průběh — Běh 1: běží" and "Výsledky — Zatím nic", until a reload.

**Proof.** The track read the study's runs once per study and stage
(`StageTrack.tsx:53-64 @ 20b24bb`); Progress reads its own run by `shouldPoll` / `pollMs`
(`research-execution.ts`). Two readers of one run, one of them never refreshed.

**Change.** The track reads the runs again while one of them can still change on its own, by the same
rule and at the same pace as Progress; a run waiting for a person is read on the next stage change only.

**Tests.** `StageTrack.test.tsx`: follows a running run to its results without a reload (fails on the
old track), stops reading once nothing can change, keeps reading a provider wait and not a budget wait.

**Second half, open.** The track also calls Spuštění "done" and Výsledky "Revize N" when the design
has changed since that run; saying "the design changed after this run" needs the working content's
revision beside the run's (see the findings ledger, F-design-lane), not a browser guess.

## PC18 — Deep Research and refusals say what happened

**Problem.**
- The Deep Research panel on Dotazník -- the design checkpoint (ADR 0021) -- listed every Deep Research
  run of the study and preselected the newest, an Interpretation Research run included, labelled only by
  its date (`DeepResearchPanel.tsx:36-50, 116 @ 20b24bb`); it then loaded that run's bundle and offered
  Opakovat and Zrušit on it. The other readers filter by purpose (`InterpretationResearch.tsx:50`,
  `design-evidence.ts:19-21`) (Deep Research and web audits, P2).
- A run on a deployment with no search route completes with every web track blocked, no query sent and
  no finding (`test_deep_research_journey.py:1040-1055`), and Interpretation Research said "Rešerše
  dokončila hledání, ale žádné externí tvrzení neprošlo ověřením" -- a search that found nothing, which
  it was not (`nothing-searched-reads-searched`, P2).
- An error raised with a code and no message reached the web with message `""`
  (`observability.py:222-229`, reproduced), and the web kept the empty string (`api.ts:48`): the report
  card showed "Načítám…" for ever when a stored report was missing or invalid, and its download and
  approval failures said nothing (`api-refusals-lose-words-and-detail`, P2).

**Change.** The design panel reads design-checkpoint runs only (`isDesignRun`: Design Research, or a run
from before purposes were recorded). A finished run whose coverage says no query left (`GET
…/coverage`, `searchedNothing`) says so beside its bundle, in both panels: how many tracks were blocked,
and that an empty result does not mean the sources say nothing. The API's error handler gives a
code-only refusal its code as its message, and the web reads an empty message as the code.

**Tests.** `design-evidence.test.ts` "isDesignRun", `reason-words.test.ts` "searchedNothing",
`DeepResearchWaits.test.tsx` "a Deep Research run that searched nothing" (unknown coverage says
nothing); `test_a_refusal_raised_with_only_a_code_keeps_its_code_as_its_message`; `api-refusal.test.ts`.

**Not changed.** Whether "Použít ve zprávě" should be offered for a run that searched nothing is the
owner's (a report variant over it prints no literature); about 45 of the API's 64 refusal codes still
have no Czech words, which is incremental work recorded below.

## PC17 — reports and maps say what they contain

**Problem.** Four places promised or hid what a report or map holds.

- The client report's introduction always said it contains "mapy hodnocených objektů"
  (`application/client_report.py:187-193 @ 20b24bb`), while `compose_map_sections(…, client=True)`
  returns no chapter when no map is approved or drawn (`report_maps.py:84-85, 198-199, 212-213`). The
  executor test's own panel run is such a report: no map chapter, maps promised (Sociomap audit
  `client-report-promises-absent-maps`, P2).
- A run whose design has no tracked set stores the note "Návrh nemá sledovanou sadu; Sociomapa
  nevznikla" with no battery (`domain/research_sociomap.py:587`); Results' Sociomapy tab printed how to
  read and use a map over nothing and never read the note (`empty-maps-tab-without-reason`).
- Putting any stored Sociomap version in force -- even an unchanged copy, since the editor starts from
  aia-sociomap-4 -- makes new runs pin aia-sociomap-1 and `<base>+e<n>`, both INTERNAL_ONLY in the
  register, so their client reports have no maps; the Metodika tab never said so
  (`methodology/pins.py:84-95`, `sociomap_register.py:52-69`; `edited-method-silently-loses-client-approval`,
  P2). The register's exact-spec rule is deliberate (B4, ADR 0023) and is not changed.
- A report with literature refused because the run's analysis was built under an earlier harness came
  back as `context_report_refused` with the English message and no reason
  (`routers/research.py:1892-1902, 2035-2038`; reports audit `context-refusal-loses-reason`, P2).

**Change.** The client report's introduction names the maps only when a map chapter was composed, and
otherwise says it has none and why. Results shows the stored note when no battery was mapped and drops
the map instructions. Activating an edited Sociomap version says, before it is confirmed, that its maps
will be internal and the client report will carry none, and that the code's aia-sociomap-3 is one button
away. A context-report refusal carries its reason when the refusal names one (`details.reason`), and the
report card says a `fingerprint_mismatch` in the Czech PC3 uses, pointing to the repair.

**Tests.** `test_a_panel_run_has_a_client_report_of_admitted_modelled_numbers_and_a_fictional_none` (no map
chapter, no maps promised); ExecutionSteps "says why a run has no Sociomap…" and the variant refusal now
read in words; MethodologyVersions (the warning on activating an edit, none on the reset);
`report-status.test.ts` "approvalRefusal"; the interpretation API test (no reason invented).

**Not changed.** Keeping an approved client report reachable after its contract or evidence fingerprint
moves (`approved-version-shadowed`) and showing who approved a report and why
(`approval-provenance-invisible`) are findings below: both need the approval ledger read on the report
routes, and the first a product rule for which version is offered.

## PC6 — a proposal says what it replaces

**Problem.** A questionnaire proposal (build or optimise) replaces every own question block and object
battery of the design with its own and keeps only other sections and library instruments
(`domain/research_agents.py:711-737 @ 20b24bb`; the optimise prompt asks for "úplnou náhradu vlastních
sekcí", `:285`), and accepting it replaces the working content (`useResearchAgents.tsx:87-90`). The
inline review listed research questions, sets and links, and its footer promised "Již vytvořený
dotazník se nemění" (`ProposalReview.tsx`): a person accepting an optimisation lost their own
questions with nothing saying so (design audit `proposal-review-hides-replacement`, P2).

**Change.** `questionnaireReplacement` (pure, beside `proposalDiff`) reads the current and the proposed
project by the agent's own rule and says how many own blocks are replaced and how many other sections
stay, then lists each own question or battery item the proposal does not carry again (by wording),
each new one, and how many are kept. The review shows it as "Co se stane s dotazníkem" and its footer
says the own blocks are replaced; a proposal that does not touch the questionnaire keeps the old line.

**Tests.** `proposal-diff.test.ts` "questionnaireReplacement"; `ProposalReview.test.tsx` "says what
accepting a questionnaire proposal replaces…", "keeps the old promise for a proposal that does not
touch the questionnaire".

**Split off (PC16, open).** Research questions are identified by their wording: rewording one in the
plan orphans every link a question or set declares to it (`domain/research_trace.py:140, 241-263`;
design audit `rq-identity-by-text`). Carrying the links with the rewording, or naming what it would
orphan before saving, is an editor change of its own.

## PC15 — a conditional question has a way out in AIA

**Problem.** A question carrying a display condition (`filtr`, from a study migrated from 18.6.6) fails
readiness with "Spusťte tento návrh v klasickém rozhraní" (`domain/research_design.py:868-876 @ 20b24bb`),
an interface ADR 0018 retired, and no AIA screen showed or removed a question's condition
(`git grep filtr apps/web/src`: none): the study could never run (design audit
`conditional-question-dead-end`, P2).

**Change.** Dotazník marks a question with a condition, quotes it, says AIA cannot yet ask a question of
only those it is meant for, and offers "Odebrat podmínku" (`questionCondition` / `removeCondition`, the
server's own test of a condition); readiness's failure now says to remove it in Dotazník or delete the
question. Asking a conditional question of only its respondents stays not in AIA.

**Tests.** `test_what_the_unit_does_and_aia_does_not_yet_is_refused_not_skipped` (the message names
Dotazník, never the classic interface); QuestionnaireStep "shows a question's display condition from
18.6.6 and removes it…" (the saved question carries no condition and keeps its wording).

## PC14 — a finished run reads as finished

**Problem.** Four readings of a run's state contradicted the run.

- *Steps that will never run.* A run that fails while sibling steps wait keeps them RUNNABLE or
  BLOCKED for good: FAILED outranks every other step state (`domain/workflow.py:853-861 @ 20b24bb`),
  `claim_next` skips a failed run (`workflow_repository.py:921-929`) and nothing settles the rest.
  Průběh still showed them "Připraveno" in the running tone, and the report card said "Zpráva se ještě
  skládá" (runs audit `failed-run-leaves-live-steps`).
- *A run that waits for a person while other steps run.* `shouldPoll` stopped reading any run with
  `needs_attention` (`research-execution.ts:85`), so the map beside an analysis module stopped at the
  budget, or the modules beside one stopped for recovery, finished unseen until a reload; the event
  feed under the stale RUNNING row kept polling every 1.5 s regardless (runs audit
  `polling-stops-on-attention-with-live-siblings`; F9/F43 had covered the self-clearing waits only).
- *A step stopped for recovery.* RECOVERY_REQUIRED keeps no waiting reason
  (`workflow_repository.py:1913`; `domain/workflow.py:225-231`), so a step stopped mid paid call --
  realistic on develop, which redeploys on every green head -- read "Potřebuje zásah" with no reason
  and no way on but a cancel (runs audit `recovery-required-unreadable-unrecoverable`).

**Change.** `willNotRun`: a step that had not started (PENDING, RUNNABLE, BLOCKED) in a run that has
ended reads "Nespustí se" in a neutral tone on Průběh, in the report's holds and on Results'
module pane; `reportStatus(…, runEnded)` reads such a report step NOT_MADE. A run waiting for a
person is read again while any of its steps runs or is runnable. The API projects each step's
`recovery_reason` from its attempts (`paid_call_uncertain` first, then `attempts_exhausted`; none
when the attempts were not read, as in a listing), and Průběh words it: a paid call of unknown
outcome is why nothing repeats the step, and what a person decides on.

**Invariants kept.** The engine's precedence and its refusal to repeat an uncertain paid call are
untouched; this is how the run is read. A step still RUNNING after its run failed is said to run,
and its report may still be composing: both can finish.

**Tests.** `research-execution.test.ts` "says a step that had not started when its run ended will not
run…", "says why a step stopped for recovery…", `shouldPoll` with live siblings under
`needs_attention`; `report-status.test.ts` "says a finished run's report step that never started…";
API `test_a_step_stopped_for_recovery_says_why_where_its_attempts_are_read`.

**Not changed.** Settling a failed run's untouched steps in the engine (marking them SKIPPED) would
make every reader agree by construction; it changes `_refresh_run`'s contract and is left for the
engine's owner. A whole-run retry of a run that failed at aggregate, Sociomap or report still
collects fieldwork again (runs audit `whole-retry-rebuys-fieldwork`): extending `FrozenDataset`
to those steps is the fix, a chunk of its own.

## PC13 — asking again says what it found

**Problem.** Two idempotent starts answered a person's new click with an old run in silence.

- *Spustit výzkum on a design that already ran.* A start whose key exists returns that run
  (`application/research.py:513-566 @ 20b24bb`), in any state, and skips the spend confirmation
  (`:629`). The Run stage said nothing and went to Průběh without `?run=` (`ExecutionSteps.tsx:717`);
  only a start that carried an acknowledgement was told (`:708-715`, research-integrity-report F12).
  A person who pressed Start on an unchanged design after a cancelled run saw that cancelled run as if
  they had just started it (runtime finding R3, runs audit `restart-same-revision-silent`).
- *An AI ask that ended without a proposal.* An agent job's key is the revision and a digest of the
  ask (`application/research.py:1265-1270`) and its template has one attempt
  (`workflow_templates.py:188`), so once cancelled or failed, every later identical ask returned the
  dead job and the stage repeated its error; only a changed design or instruction got past it (runs
  audit `idempotent-start-returns-dead-runs`).

**Change.** A start that finds its run opens Průběh on that run (`?run=…&found=1`) and Průběh says
nothing new was started or paid for, and what starts a new one; a lost-answer re-ask that finds its own
acknowledged run is followed plainly, as before. An agent ask whose newest job failed, was cancelled,
or stopped for recovery with no paid call of unknown outcome starts a new round
(`<key>:again-<n>`, `metadata.round`), the precedent `request_report_pdf` and OI-121 set; a job still
queued, running, waiting or done is followed, and one with a call of unknown outcome is never asked
again.

**Not changed.** The research run's key: a design run once is still not run twice by a click (that is
the point of the key; a retry or a changed design starts another). Readiness does not yet say before
the click that the design has a run, which would need the start's key computed without starting
(the key is built inline in `start`); the cost question can therefore still be asked before a start
that finds its run, when the study's limit is at or below the ceiling.

**Tests.** Web: "opens a run the start found instead of starting one…", "says on Průběh that the run
was found, not started…"; API: `test_asking_again_after_a_job_ended_without_a_proposal_starts_a_new_round`
(cancelled, then failed, then done), `test_a_job_stopped_with_a_paid_call_of_unknown_outcome_is_never_asked_again`.

## PC7 — the copy agrees with what was decided

**Problem.** After the owner approved `aia-sociomap-3` for reports (D6, 2026-10-13, recorded in
`domain/sociomap_register.py:52-57 @ 20b24bb`) and B4 put the register's approval on every map, several
fixed strings still said every Sociomap is internal, so an approved map read "Metodika schválena pro
zprávy" and "Interní · nesmí ke klientovi" on one screen: the readiness check "N sad pro Sociomapu
(interní, D6)" (`domain/research_design.py:899`), the Metodika module note "Mapa je zatím jen interní
(D6 otevřené)" (`domain/methodology/sociomap.py:817-822`, and four times in the web fixture), the map
snapshot's caption and file name on every map (`ObjectMapView.tsx:270`, `cs.ts:2748-2749`), the
Progress step "Sociomapa (interní)" and its progress line "Sociomapa spočtena (interní)"
(`cs.ts:2358`, `aia_executors/research.py:743`), and project memory's "Interní: Sociomapa, analýza a
zpráva nejsou pro klienta" (`cs.ts:666`). Results also said, for a run started without analysis,
"Klientský report (DOCX) zatím v AIA není" (`cs.ts:2698`) under a card that offers the client report
(`application/client_report.py`). Runtime finding R4/R5; sociomap and legacy audits.

**Change.** Each sentence now says what is true: the readiness line names the batteries and leaves
approval to the register, read where the map is read; the Metodika note says -3 is approved and an
edited version in force is internal until the register approves it (fixture regenerated with
`tools/methodology_fixture.py`); a snapshot's caption and file name follow the map's own approval
(`snapshotNaming`); the step is "Sociomapa"; project memory names analysis and the internal report as
internal and a Sociomap only when its method is not approved; the no-report sentence says why (the
run was started without AI analysis) and where a client report is.

**Invariants kept.** No gate moved: the client report's maps still pass `require_client_facing`; every
change errs neither toward approval nor away from it, it follows the register.

**Tests.** ObjectMapView "a map's snapshot is named by the map's own approval…"; the step label and
Progress list assertions follow the new words; `test_methodology_api` holds the regenerated fixture.

**Not changed.** The 18.6.6 notices ADR 0018 asks for ("V AIA zatím není" where a person meets it) stay:
they are true. The Data Library notice stays (the shared-source library is not in AIA). Settings'
"FAST_EXTRACTION nic nevolá" is latent while the client-source proposals switch is off; its fix needs
the switch carried to the web through Compose and `/config`, so it is a finding below, not copy.

## PC2 — Results say what the run and the analysis already decided

**Problem.** Two verdicts every governed surface applies were missing on Results, so the screen
contradicted the report and the analysis below it.

- *An answer to a research question the run recorded as a gap.* The run records its answerability at
  start whether or not the gate is on (`application/research.py:404-417, 597-626 @ 20b24bb`); the
  internal report marks every answer to such a question ("Při spuštění běh zaznamenal: …",
  `application/report.py:168-175, 350-365`). `GET …/analysis` returned each answer as question, answer
  and claims only (`routers/research.py:1583-1592`), and Results printed it unmarked
  (`ExecutionSteps.tsx:1668`): an answer the run itself said it could not support read as measured.
- *A number the aggregate's own rating refuses.* The aggregate stores each question's fidelity rating,
  REFUSE for an absolute willingness to pay or market size (`domain/research_aggregate.py:279-293,
  711`); the analysis drops every row of such a question (`domain/analysis/native.py:277-283, 372`),
  the report prints only admitted cells and the Run stage's outlook says beforehand that nothing will
  cite it. Results' Data card read only `support_status` and badged the number "Podložené v rámci
  běhu" (`ExecutionSteps.tsx:1699-1703, 1845-1854`), with no sign of the refusal.

**Change.** The analysis route projects, per answer, `gap`: the run's recorded words for that
question (`report_method.research_question_gap`, the report's own match), and Results shows them
above the answer in the report's words. The Data card reads the rating the aggregate stored beside the
number (`fidelityRefusal`) and, for REFUSE, says "Analýza ani zpráva toto číslo necitují: …" with the
stored reason. Both are read from what was stored; nothing is recomputed in the browser.

**Invariants kept.** No evidence rule moves; the number is still shown (whether a refused number
should be hidden on Results, as in the report, is the owner's call). Only an explicit REFUSE is
named; a missing rating, which the analysis also refuses, is not guessed at on the card.

**Tests.** The executor journey (`test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs`)
now reads `run_analysis` and checks every answer to a recorded gap carries the report's words
(fails on the old route: no `gap`); `test_each_recorded_gap_is_worded_for_the_answer_it_qualifies`
covers the match; web: "marks an answer to a research question the run recorded as a gap…", "says
beside a number the analysis and report never cite that they do not…", `fidelityRefusal`.

**Not changed.** The analysis-support exclusion (`support_analysis_excluded`: shown on Results by
design, not citable by the analysis) is not yet named on the card; it needs the API to project the
analysis-support decision per measure rather than the browser re-deriving it (analysis audit,
`interval-order-rule-browser-only` is the same shape and stays open).

## PC3 — an analysis an earlier harness built stays repairable

**Problem.** Results, Interpretation Research, the report with literature and the report step read a
run's analysis through `reconstruct_run`, which re-judges every module under today's harness, prompt
wording, policy and evidence and refuses the whole run if one moved
(`application/analysis_results.py:775-783, 940-964 @ 20b24bb`: `fingerprint_mismatch`). The repair
(`retry_failed_modules` over the run's frozen dataset) offered only BLOCKED or failed modules
(`_retryable`, `:701-716`), so a run whose eight modules all completed before a harness or prompt
change could not show its analysis, prepare its literature variant or use an Interpretation
Research, and nothing offered to repair it: `nothing_to_retry`, and the web asked only for runs with
a blocked or failed module (`research-execution.ts mayRetryAnalysis`). Results said the API's English
refusal; Interpretation Research said "Obnovte stránku a zkuste to znovu". The only way out was a
whole new run, paying for fieldwork again. A deploy between the modules and the report step left the
same dark run. The analysis audit rated it P1, to be fixed before research-integrity-report chunk 8
changes the analysis inputs (which will move every run's fingerprints).

**Change.** A module a model completed under a harness that is not today's is *stale* (`_stale`: the
same test the retry already used to decide what it reuses, `_reused`), and retryable: the retry asks
it again over the same dataset, as it would have anyway once started (the ceiling already counted
it). `GET …/analysis/retryable` names them (`stale`). Progress asks for any finished run with
analysis, and its repair card says why: an earlier version of AIA built these modules and today's
cannot re-check them, not that a model failed. Results' analysis tab and Interpretation Research say
the same in Czech and link to the repair.

**Invariants kept.** No evidence rule moves: a stale draft is never shown or re-admitted; it is asked
again under today's harness and judged by today's gate. A module the preflight blocked is still not
retryable. The retry still collects nothing (the dataset by id and SHA-256), still needs the
person's confirmation over the spend limit, and the report's gate is unchanged.

**Tests.** `test_a_run_whose_every_module_an_earlier_harness_completed_is_repaired_over_its_data`
(fails on the old code: nothing retryable); `test_a_run_stored_under_the_previous_harness_can_still_be_repaired`
now also names the stale modules; the route's shape (`stale`). Web: Progress "offers to repair a run
whose modules an earlier version of AIA completed…", Results "says an analysis an earlier version of
AIA built cannot be shown…", `mayRetryAnalysis` for any finished run with analysis.

**Not changed (owner decision).** Whether a stale analysis should be *shown*, labelled with the harness
that built it, instead of hidden until repaired. It is the only product question here; showing it
would show text today's gate has not judged.

## PC4 — work that waits for a person can go on

**Problem.** Two kinds of wait never clear by themselves, and for most of AIA's work nothing let a
person clear them.

- *A park for the AI runtime* (`WAITING_PROVIDER` / `ai_runtime_unavailable`: the runtime not
  composed on the worker, or its gateway refusing before any call). `resume_due` never resumes it
  (`domain/workflow.py:797-798 @ 20b24bb`), `retryable` refuses a waiting run
  (`domain/research.py:56-63`), and a start on the same revision returns the same run
  (`application/research.py:513`). Only agent jobs had a resume (`application/research.py:1340-1352`,
  `routers/research.py:2500-2507`). So a research run parked at fieldwork or analysis, a Deep
  Research run parked at its plan, and AI proposals from a client's document asked while they were
  off (`application/source_proposals.py:148-152, 197-200`: asking again returned the parked run, and
  the web hid the button, `source-proposals.ts:57-59`) waited for ever once the operator turned the
  runtime on. The analysis park's own words promised the opposite ("modul čeká, dokud ji
  provozovatel nezapne", `aia_executors/analysis.py:141`); the fieldwork park said "spusťte běh
  znovu" (`ai_fieldwork.py:120`), which returned the same parked run. Verified by the runs, flags,
  fieldwork, knowledge and analysis audits.
- *A stop at the study's budget cap* (`AWAITING_BUDGET`). Only a research run's step could be lifted:
  `ResearchRuns.lift_budget_wait` reads the run through `get`, which refuses any other workflow type
  (`application/research.py:925-958, 1149-1154`). An agent job stopped at the cap (every UI-created
  study starts at budget 0) waited until cancelled, and asking the same action again returned it; a
  Deep Research step stopped at the cap had no lift either (webia audit, P1 once the agent and Deep
  Research switches are on, their intended production state).

**Change.** One rule each, shared by every kind of a Study's work:
`application/research.py lift_study_budget_waits` (the research step's lift, generalised: the same
permissions, the same refusals, one approval per step in the ledger) and `resume_runtime_parks`
(every step of a run parked for the runtime through `WorkflowRepository.resume_runtime_park`, which
already refuses a step that sent a paid call, is being cancelled or has no attempt left). Routes:
`POST …/research/runs/{id}/resume`, `POST …/research/agent-jobs/{id}/budget`,
`POST …/deep-research/runs/{id}/resume` and `…/budget`. Client-source proposals: asking again about
a run parked for the runtime before it sent anything offers the same run again
(`WorkflowRepository.resume_client_runtime_park`, the client-work twin, as `resume_client_budget_wait`
is) and the API says `resumable`; a new run beside it would park the same way and leave the first
waiting. The web: Průběh's parked banner says the run will not go on by itself and offers
"Pokračovat v běhu"; the Deep Research panel and Interpretation Research offer the same and the
budget lift (`DeepResearchWaits`); a stage lists an AI job stopped at the cap with the lift
(`AgentBudgetWaits`); the source's "Pokračovat". One budget form (`BudgetLift.tsx`) serves all three.
The park messages say to go on from Průběh once the runtime is on.

**Invariants kept.** Nothing resumes by itself and nothing new starts: the same run keeps its
revision, pins, frozen spec and confirmed ceiling. A step that dispatched a paid call is never
offered again here. A step resumed while the runtime is still off parks again without spending an
attempt. The cap stays hard; a lift is a person's approval (`APPROVE_BUDGET` +
`MANAGE_STUDY_BUDGET`), which a worker's scope does not hold. A closed study refuses both
(`study_closed`).

**Tests.** API: `test_a_run_parked_for_the_runtime_goes_on_when_a_person_resumes_it` (park, resume,
park again while off, go on when on: the same run, compile and preflight once),
`test_resuming_a_run_refuses_one_that_waits_for_nothing_and_a_closed_study`,
`test_a_job_stopped_at_the_budget_cap_goes_on_when_a_person_lifts_it`, Deep Research
`test_a_run_parked_for_the_runtime_goes_on_when_a_person_resumes_it` and
`test_a_run_stopped_at_the_budget_cap_goes_on_when_a_person_lifts_it`, client sources
`test_a_run_parked_for_the_runtime_goes_on_when_asked_again`. Web: ExecutionSteps "lets a run parked
for the AI runtime go on…", "offers no way on for a run parked on a study that may not change";
`DeepResearchWaits.test.tsx` (five cases: resume, lift, nothing for a self-clearing wait, an ended
run or a read-only study; an agent job's lift); source-proposals "asks again about a run parked for
the AI runtime". Each fails on the code before this chunk (no route, no button, `mayAsk` false).

**Not changed.** Materializations park the same way (`aia_executors/materialize.py:66-69`) and have no
web caller at all (population audit); their resume waits for a screen that starts one. Whether AIA
should tell the researcher that the runtime is on before they press "Pokračovat" needs the worker's
configuration on the API, which it does not read (Settings shows it as configured, never verified).

## PC10 — Dimenze shows and saves only what a person chose

**Reported by the owner, 2026-10-18:** "when starting a new study, the dimenze are prefilled".

**Problem.** A new study's Dimenze stage and its stage track read "4 dimenze · N=300" though nobody had
chosen a dimension. The template stores none (`research_template.py:77 @ 20b24bb`: `approved: []`).
The screen read the approval through the classic's `personaApproved` port (`withApproval`,
`apps/web/src/research/persona.ts:117 @ 20b24bb`), which draws an empty approval as the recommended
set (OI-54), and every save from the stage built on that refill: the sample size, "Další · kontrola",
the AI suggestion's payload and a dimension request (`persona.ts:161, 166, 171, 188, 239`). So the
first save on Dimenze stored four dimensions as chosen, while a study whose Dimenze was never
touched ran with none -- an empty selection filters no persona topic
(`domain/persona_topics.py:323-346`). The Run stage's receipt counted the refill too
(`ExecutionSteps.tsx:388`). Screen and run disagreed either way.

**Change.** `chosenDimensions` reads the approval as stored; every change on the stage saves only
what was chosen; the track says "Bez dimenzí" for none; the receipt counts what the run will record.
The recommended set is still drawn as a recommendation and applied by one action ("Použít
doporučené"). `withApproval` stays as the classic's reading, the reference the parity suite pins.

**Deviation from 18.6.6, recorded.** `persona.parity.test.ts` still runs every classic function; where
the classic refilled (add, remove, the sample input, the AI suggestion's payload, a request's
record), the test now asserts the classic's refill and AIA's chosen-only result side by side.
`personaApproved` is not one of the 88 research functions of the UI ledger.

**Tests.** lane "says a new study chose no dimension…" (fails on the old code); PersonaStep's four
screen tests now assert the empty selection, its save and the one-click recommendation; the parity
cases above. **Doc follow-up:** OI-54 decided by the owner (2026-10-18): an empty approval stays empty.

## PC8 — the journeys pass, and the pass can be repeated

**Problem.** None of the browser journeys runs in CI, and three had drifted from the interface:
`make ui-research` and `make ui-sociomapping` waited for "Dokončeno", the run state #458 renamed
(`research_journey.mjs:46 @ 20b24bb`); the client journey for "Přidat znalost", which the intake
sheet replaced with "Napsat znalost" on Znalosti; the sociomapping journey read the first of two
copies of its fictional-data notice, the hidden one, and counted the documented "404 = nothing
here" of `/design/source` (a study with no reused design) as an error. OI-106 recorded two earlier
drifts of the same kind.

**Change.** The three journeys wait for what the screens say today (a finished run's state,
"Napsat znalost", the card's own notice, `design/source` among the nothing-here reads). The pass
itself is committed: `make ui-coherence` (`tools/ui_workbench/coherence_journey.mjs`) walks the
product as one researcher and keeps every page as image and text with its checks in
`report.json`; `make report-journey` (`report_preview.py --journey` with
`tools/report_journey_capture.py`) renders the reports a run composes and prints the lines per page.
The workbench README says how to repeat it and what it cannot repeat (the model).

**Verified, 2026-10-18.** `make ui-research`, `make ui-sociomapping`, `client_journey.mjs`,
`workspace_journey.mjs`, `intake_journey.mjs`, `audience_journey.mjs`, `settings_journey.mjs`,
`ux_journey.mjs` and `make ui-coherence` (16 checks) pass on the workbench; `make report-journey`
renders three DOCX (27, 29, 29 pages).

**Not done.** A check that every label a journey waits for exists in the web source: 19 of 194
literals are composed from templates, fixture data or server-served titles, so it would need an
allowlist that drifts itself. Running one journey in CI is the owner's call (decisions, below).
