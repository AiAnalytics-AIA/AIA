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
  - "[x] PC9. Report body and appendices flow: no page break before every chapter (owner D5, 2026-10-17)"
  - "[x] PC10. Dimenze shows and saves only the dimensions a person chose: a new study chose none (owner, 2026-10-18; OI-54)"
  - "[x] PC11. Product-level acceptance scenarios over the real start, worker and report"
  - "[x] PC12. Owner decisions recorded with a recommendation each; no code"
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

**Follow-up (journey review).** The read-only fieldset first wrapped every stage, open or closed, so
an editable stage gained an unnamed group and the audience journey's own fieldset lookups found it
first. `ReadOnly` (`Inspector.tsx`) renders the fieldset only on a closed study, `role="none"`;
ResearchScreen "wraps an editable stage in nothing".

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

## PC9 — the report flows (owner D5)

**Superseded on merge.** #478 implemented the same decision (a6fdd48, research-integrity-report chunk
12: a page breaks only where the page furniture changes) and its `styles.py` replaced this chunk's
when develop was merged in (aff7ecb). PC9's test passes under it; the page counts below are this
chunk's own, measured before the merge.

**Problem.** Every chapter and appendix heading carried a page break (`report_docx/styles.py:177,
180 @ 20b24bb`), so short chapters stood alone on near-empty pages: the three journey reports rendered
27, 29 and 29 pages with pages of 6 and 11 lines (runtime finding R7; #477's render, "short chapters
alone on a page (D5)", `research-integrity-report.md:181`). The owner's answer (2026-10-17,
`research-integrity-report.md:448`): "Remove automatic page breaks before chapters. Keep headings with
the following text, avoid orphaned lines, and keep figures with their captions where practical. Give the
branded cover its own page; let the report body and appendices flow."

**Change.** The chapter and appendix heading styles break no page; they keep with the following
paragraph and take 28 pt above them instead. Already true and now pinned: body text has widow control,
a caption keeps with its figure and the figure with its source line. Each Word section still starts a
page: the cover, the front matter, the body, the appendices and every landscape page (an orientation
change needs one).

**Measured** (`make report-journey`, LibreOffice, the same three DOCX): 21, 23 and 23 pages (from 27, 29,
29). Lines per page, first report: `11 18 40 15 30 28 28 27 35 33 26 25 5 21 26 26 6 10 18 9 23`. The two
short pages left close a section: the body's last chapter before the appendices begin, and Příloha A
before the landscape evidence table.

**Tests.** `test_chapters_flow_with_their_headings_kept_to_their_text`.

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
`ux_journey.mjs` and `make ui-coherence` (16 checks) pass on the workbench (the intake journey
now waits for the image's row before counting it: it raced the tables' reading); `make report-journey`
renders three DOCX (27, 29, 29 pages; 21, 23, 23 after PC9).

**Not done.** A check that every label a journey waits for exists in the web source: 19 of 194
literals are composed from templates, fixture data or server-served titles, so it would need an
allowlist that drifts itself. Running one journey in CI is the owner's call (decisions, below).

## PC11 — the surfaces agree: product acceptance

**Problem.** Every surface had its suite and nothing held the surfaces to one another. PC2 is the
proof: Results read an answer to a research question the run had recorded as unanswerable as
measured, while the report printed "Bez doložené odpovědi" beside the same answer, and every suite
was green. None of the assignment's six scenarios was a test.

**Change.** `apps/executors/tests/test_product_acceptance.py`: one test per scenario, through the
calls the browser makes -- the API app (`create_app`) over the worker's database and artifact store,
signed in as the study's lead -- the real worker and executors, and the stored DOCX read back. The
answerability gate is on, as D-2 recommends. Fictional designs and respondents; the model is
`scripted_bedrock.py`, the analysis suite's Bedrock double moved out of
`test_analysis_executor.py` unchanged so both suites share one (that suite: 44 passed after the
move). USD 0, nothing leaves the process. 26 s on SQLite, 35 s on PostgreSQL 16.

| Scenario | Test | Held across surfaces | Not covered here |
|---|---|---|---|
| 1-2. A research question supported / unsupported | `test_a_measured_and_an_unmeasured_research_question_read_the_same_from_readiness_to_report` | Readiness: the measured question ANSWERABLE (n 200; at n 150 support makes it AT_RISK), the other UNANSWERABLE, one gap (`unmeasured`). The start refused with the same gaps and digest, then started on a recorded reason; the run's record equals readiness's and is unchanged after the worker. Results: `gap` on every answer to the unmeasured question, on none to the measured one. The report: one "Bez doložené odpovědi", the same words as Results, the reason, "běh na ni mohl odpovědět" | The web's rendering of these fields (component tests); a panel run (`test_ai_fieldwork.py`'s grounded runs) |
| 3. A report with contextual research | Not repeated: `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs[deep-research-and-internal-report]` (the chosen interpretation, the draft stored once, one seal printed twice, the prepared draft is the one read) and `apps/api/tests/test_report_variant_api.py` (the status names the prepared draft and its PDF; the DOCX served is that draft; the PDF waits for its rendering) | -- | One HTTP walk from choosing a review to its PDF |
| 4. A revision changes | `test_a_runs_results_and_report_stay_its_revisions_when_the_design_changes` | After revision 2 measures the question run 1 could not answer, run 1 keeps revision 1 and its recorded gap on the run, on Results and in its report (same artifact, same bytes); revision 2 is judged alone (no gap); its start is a new run (`created`), revision 2, no gap in its report; the run list names each run's revision, newest first | The stage track still calls Výsledky "Revize N" without saying the design changed since (PC5's second half, R7) |
| 5. A provider fails, then recovers | `test_a_throttled_module_waits_visibly_and_the_same_run_finishes_paying_each_call_once` | A 429 on one module: the step WAITING_PROVIDER / QUOTA, the run WAITING, not terminal, not retryable; the report step BLOCKED (never failed, nothing stored); resume refused (`runtime_park_not_resumable`) and retry refused (`run_not_retryable`): nothing a person presses pays again. After the reset the worker's own sweep offers the step; the same run completes with its report; that module asked twice, every other once; its ledger DISPATCHED, FAILED, DISPATCHED, SUCCEEDED; the run's cost eight calls | A lost (uncertain) call: `test_an_uncertain_turn_waits_for_a_person_and_recovery_replays_what_was_answered`; a runtime park and its resume (PC4): `test_a_run_parked_for_the_runtime_goes_on_when_a_person_resumes_it`. While it waits, the report card reads "Zpráva se ještě skládá." (R8) |
| 6. A study is delivered | `test_a_delivered_study_keeps_its_results_and_refuses_new_work_under_one_code` | The frame: `can_edit` false, `can_review` true, `delivered_at`. Allowed: the run, its analysis, the report's status and download (same bytes), approval, a knowledge proposal to the client (the client's, decided by a person; whether delivery should freeze it is D-1's). Refused, each 403 `study_closed`, on a failed run that an open study would retry and whose analysis it would ask again: saving content, importing a questionnaire, attaching a file, submitting a design, starting, retrying the run, retrying its analysis, resuming, lifting a budget wait, an AI agent job, Deep Research. Nothing made; reopening restores the start | Cancelling a running run on a closed study (allowed, PC1: `can_review`) is not walked |

**Found.** Nothing contradicted between surfaces in these walks once PC1, PC2 and PC14 were in. Two
readings are recorded for later: the report card's "still composing" while the run waits for a
provider (R8), and knowledge proposals from a delivered study (D-1).

**Not done.** No scenario runs in a browser in CI (D-8); the web's reading of each field is its
component tests'.

## Decision ledger (owner questions, 2026-10-18)

Each question is stated so it can be answered without reading the code; the recommendation is mine,
the decision is the owner's. Findings it covers are in the ledger below (Next: "owner decision D-n").

| # | Kind | Question | Recommendation |
|---|---|---|---|
| D-1 | product | What does "Předáno" mean? Today it is a free, audited label set only in Settings; it names no report, freezes nothing in flight, and any member may reopen. PC1 made the screens honour it. | A "Předat klientovi" action on Výsledky that names the approved report artifact(s), stamps `delivered_at` on first delivery and sets DELIVERED; "Znovu otevřít" with a reason, audited; Settings keeps archive and cancel only. |
| D-2 | product | D1 asked for an explicit, recorded "continue with limitations". It exists only with `AIA_RESEARCH_ANSWERABILITY_GATE` on, which ships off (CI pins it off). Turn it on for develop? | **Decided and done in #478** (d7fcf09, research-integrity-report chunk 14): on for develop, off in tests and the workbench, ADR 0025 Accepted. |
| D-3 | product + data owner | AI fieldwork and analysis of every new or edited Design Revision need an operator to hash it into `AIA_AI_MATERIAL_CLASSIFICATIONS` and restart the worker (two P1 findings). Should classifying a revision's material be an audited in-product act by an authorised person? | Yes, as ADR 0020 does for prompts: bound to the revision's `material_sha256`, recorded in the approval ledger. Until then: show the digest and the classification state on the Run stage and in the park, and add the key to the runbook's table. |
| D-4 | product | One approved DATASET or FINDING item (unresolved licence lineage) parks every design AI job of that client's studies, with no item named. Keep the licence rule and... | ...leave such items out of the design snapshot, named in AI pomoc as omitted with the reason (option a); a person records lineage later (lifecycle K3/K4). |
| D-5 | product | "Nová simulace" creates a study nothing can act on, counted as active work. S0 (what a simulation is in AIA) is undecided (D9). | Until S1: keep the entry but say before creating that the workflow is not in AIA yet, and do not count simulations as active work; decide S0 separately. |
| D-6 | product + methodology | A run "over" a materialized child draws the same respondents as over LIVE (no step reads the added column) and is a second paid run; the MVP gate's "new LIVE revision" contradicts M5. | Until a consumer exists, say on the Run stage and in the report that the dimension is recorded and read by no respondent (or hide the picker); restate the MVP gate under M5. |
| D-7 | product | After LIVE is promoted, a panel start of an unchanged design returns the run drawn from the superseded LIVE. | Put the resolved LIVE version in a panel run's key (a child selection already is); PC13 already says when a start found a run. |
| D-8 | engineering policy | No browser journey runs in CI, and they drift with the interface's words (three did; OI-106 two more). | Run the research and coherence journeys nightly on the workbench (no secrets, USD 0), not on every PR. |
| D-9 | product (D2) | An approved report's files still print "KONCEPT — NESCHVÁLENO", and a newer unapproved draft (after a contract bump) replaces the approved one with no route to it. | **First half done in #478** (cb62426, 06da982, 594e21d, chunk 13): an approved version downloads stamped SCHVÁLENO, DOCX and PDF alike, and the card reads it again after approving. Still open: list a run's report versions and say when a newer draft exists. |
| D-10 | product | Does D2's draft/approved status cover ADR 0019 gate 3 for the client report? Today the client report leaves AIA with no release gate, approving it says "interní použití", and "independent review" governs report approval but not design acceptance. | Give the client report its own approval wording and require it before the client download (or record every export); name the decisions independent review governs; record the run's starter, not the downloader, as the producer of a composed report. |
| D-11 | product | A number the aggregate's rating refuses (absolute WTP, market size) is shown on Results, now labelled (PC2); the report omits it. | Keep it shown and labelled for researchers; it never reaches a client surface. |
| D-12 | product | "Použít ve zprávě" is offered for a Deep Research run that sent no query (PC18 now says so). | Disable it when no query was sent. |
| D-13 | product | Retire the transitional: the non-Bedrock model adapters (unreachable), the walking skeleton's /studies pages and their legacy route-ledger credits. | Retire with a one-line ADR note each; keep the recorded doubles for tests. |
| D-14 | product | OI-58: the live 18.6.6 content migration is not recorded as run. | Record it (date, operator, report) in the migration status doc, or run it. |
| D-15 | product + data protection | Every picked or dropped client file is kept for ever, with no list and no delete (a wrong-client file stays). | A per-client source list with delete-when-unreferenced, audited. |
| D-16 | product | Archiving a client fails every in-flight run of its studies, unconfirmed, and hides its delivered work. | Answer 409 with the running work unless confirmed; decide whether an archived client's delivered studies stay readable. |
| D-17 | product | The run's cost ceiling ("horní mez") is not a bound: retries and parks repeat paid fieldwork (OI-64). | Fix OI-64 (per-respondent checkpoint, planned) rather than reword the approval. |
| D-18 | methodology | The tracked-set size rule has three readings; the interval ordering rule lives only in the browser; K100's interval cannot be reached on develop and is not pinned; a superseded preset is still offered as a base; modules without inputs gate the report. (D4's topical relevance and document types were decided and implemented in #478, chunks 10-11.) | Decide each with the methodology owner; none is changed here. |
| D-20 | product | An analysis built under an earlier harness is hidden until repaired (PC3). Show it, labelled with its harness, instead? | Keep it hidden: it is text today's gate has not judged; the repair is one confirmed action over the frozen data. |

## Remaining plan, ranked (value × confidence ÷ complexity)

Safe engineering, no owner decision needed; each would be a chunk of this plan or the next.

1. **R1 (PC16).** Carry a research question's links when it is reworded, or name what it orphans
   before saving (`domain/research_trace.py:140, 241-263`).
2. **R2.** A module the preflight blocked says why in Czech, with its fix, and is never offered as a
   repeatable model failure; when every block is a preflight block the whole-run retry is not the
   primary action (`analysis_results.py:713`, `research-execution.ts` reportHolds).
3. **R3.** A whole-run retry of a run that failed at aggregate, Sociomap or report reuses its dataset
   (`FrozenDataset`), as the analysis retry does, instead of paying for fieldwork again.
4. **R4.** Member offboarding: deactivate a member under `require_administer`, never the last owner,
   from Settings with a confirmation (`no-member-offboarding`, P2).
5. **R5.** Approval provenance (who, when, why) on the report routes and the card; the note the API
   already accepts sent by the card (`approval-provenance-invisible`).
6. **R6.** Czech words for the API's remaining refusal codes (about 45 of 64), research screens first.
7. **R7 (PC5, second half).** The stage track says when the design changed after the run it shows; needs
   the design content's digest compared on the server, not in the browser.
8. **R8.** The small P3 readers (the report card re-read after approval is done in #478, 594e21d): `pdf_disabled` not offered
   again until PDF is configured, failed modules not read as "Čeká", run lists that say they are
   truncated, `cancel_requested` shown, working-content history reachable, Settings' AI switches
   complete (FAST_EXTRACTION, panel personas, the answerability gate), and the report card's "Zpráva
   se ještě skládá." while the run waits for a provider (`report-status.ts` reads BLOCKED as composing;
   PC11 scenario 5).

## Doc follow-up (for the docs PR; this PR edits no shared document)

- `CLAUDE.md` § 3: `make ui-coherence` and `make report-journey` (rows as in the PR description).
- `CLAUDE.md` § 2, `routers/workspace`: `can_edit` (permission and the study accepts work),
  `can_review`, `delivered_at`; `study_closed` refusal.
- `CLAUDE.md` § 2, `routers/research`: `POST …/research/runs/{id}/resume`,
  `POST …/research/agent-jobs/{id}/budget`; a step's `recovery_reason`; each analysis answer's `gap`;
  `GET …/analysis/retryable` answers `stale`. `routers/deep_research`: `POST …/runs/{id}/resume` and
  `…/budget`. `routers/client_sources`: a proposals run's `resumable`.
- `CLAUDE.md` § 2, `application/research.py`: `lift_study_budget_waits` and `resume_runtime_parks`, the
  one lift and the one resume of a Study's work; an agent ask that ended without a proposal is a new
  round. `infrastructure/workflow_repository.py`: `resume_client_runtime_park`.
- `CLAUDE.md` § 2, `apps/web`: `BudgetLift.tsx`, `DeepResearchWaits.tsx`, `AgentBudgetWaits.tsx`,
  `SearchedNothing.tsx`; `lib/research-execution.ts` `willNotRun`, `fidelityRefusal`;
  `research/proposal-diff.ts` `questionnaireReplacement`; `research/persona.ts` `chosenDimensions`.
- `ARCHITECTURE.md` (report rendering): no automatic page break before a chapter (D5); each Word
  section still starts a page.
- `open-items.md`: OI-54 decided (an empty Dimenze approval stays empty, 2026-10-18); OI-106 three more
  journey drifts fixed; OI-64 cited by D-17; new items from the ledger's open P2s, numbered there.
- `overview.md` history: this pass, its 142 verified findings, 35 fixed here, 19 owner questions.

## Findings ledger (verified, 2026-10-18)

142 findings from sixteen subsystem audits, each re-read by an adversarial verifier (one refuted and
dropped; a P0 was looked for and none found). Severity is the verifier's. "This PR" names the chunk
that fixed it; "Next" is the owner decision, the plan or OI it is already registered under, or the
action the verifier recommends. Anchors are at the base, 20b24bb.

| # | Sev | Verdict | Area | Finding | Anchor (@ 20b24bb) | This PR | Next |
|---|---|---|---|---|---|---|---|
| F001 | P1 | confirmed | analysis | `harness-change-darkens-analysis`: Any harness, prompt or policy change makes every earlier run's analysis unreadable and unrepairable, and strands runs in flight | `packages/aia_core/src/aia_core/application/analysis_results.py:775-783` | fixed: PC3 |  |
| F002 | P1 | partially confirmed | fieldwork | `design-classification-operator-only`: Each new or edited design needs an operator to hash it into worker env and restart the worker before AI fieldwork or analysis can run; no in-product path, and the design's digest is never shown | `apps/executors/src/aia_executors/ai_fieldwork.py:421-433` |  | owner decision D-3 |
| F003 | P1 | confirmed | flags | `material-classification-is-host-config-per-revision`: Every AI call on a design needs an operator to hash that exact revision into the worker's environment; a researcher cannot run a study alone | `apps/executors/src/aia_executors/ai_fieldwork.py:425-434` |  | owner decision D-3 |
| F004 | P1 | confirmed | webia | `budget-wait-dead-end-agents-dr`: A research agent job or Deep Research run stopped at the study's budget cannot be let through, and every new study starts at USD 0 | `packages/aia_core/src/aia_core/application/research.py:1149-1154` | fixed: PC4 |  |
| F005 | P2 | confirmed | analysis | `analysis-switch-never-reaches-existing-runs`: Turning analysis on later reaches no existing run: parked modules never resume, and runs started without it can never be analysed | `apps/executors/src/aia_executors/analysis.py:140-143` | fixed: PC4 for a parked module; a run started without analysis stays without |  |
| F006 | P2 | confirmed | analysis | `preflight-blocked-dead-end`: A module blocked by code before any call is shown as a repeatable model failure; the only offered action is a paid full re-run that blocks again | `packages/aia_core/src/aia_core/domain/analysis/native.py:612-620` |  | next safe chunk (R2 below) |
| F007 | P2 | confirmed | analysis | `results-answers-ignore-recorded-gaps`: Results prints analysis answers to research questions the run recorded as gaps as plain answers; the report marks them | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1668` | fixed: PC2 |  |
| F008 | P2 | confirmed | analysis | `results-shows-refused-numbers-as-supported`: Results' Data view labels fidelity-refused and analysis-excluded numbers 'Podložené v rámci běhu' while the analysis, the report and the pre-run outlook refuse them | `packages/aia_core/src/aia_core/domain/research_aggregate.py:279-293` | fixed: PC2 (labelled; hiding it is D-11) |  |
| F009 | P2 | partially confirmed | deepresearch | `d4-relevance-doctype-placement`: D4's relevance and document-type rules belong in the engine's admission step, and the source-table approval is not tied to a table version | `packages/aia_core/src/aia_core/domain/deep_research/merge.py:1-16` |  | owner decision D-18 |
| F010 | P2 | confirmed | deepresearch | `design-panel-shows-interpretation-runs`: The design stage's Deep Research panel lists, opens and retries Interpretation Research runs as if they were design research | `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:37` | fixed: PC18 |  |
| F011 | P2 | partially confirmed | deepresearch | `design-proposal-accept-unwired`: Design Research findings cannot be taken into the design from the UI: the accept route has no caller | `apps/api/src/aia_api/routers/deep_research.py:646` |  | registered: mvp-workflow-assurance.md:449 ('no screen yet (ADR 0019 gate 1 has no  |
| F012 | P2 | confirmed | deepresearch | `no-recovery-verbs`: A Deep Research run stopped by something a person or operator later fixes cannot be continued or redone from the UI | `apps/executors/src/aia_executors/deep_research/_shared.py:41-44,74-78` | fixed: PC4 (resume, budget lift) |  |
| F013 | P2 | confirmed | deepresearch | `nothing-searched-reads-searched`: A review that searched nothing reads as one that searched and found nothing verifiable | `apps/web/src/components/rehome/research/InterpretationResearch.tsx:154` | fixed: PC18 (said; gating is D-12) |  |
| F014 | P2 | confirmed | deepresearch | `refusals-english-undetailed`: Deep Research refusals reach the researcher as raw English server sentences, with the actionable details dropped | `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:22-26` |  | safe engineering, S: Map the Deep Research refusal codes to Czech (codeWords). Render details.missing as the setting labels from GET /deep-research/settings with a link to |
| F015 | P2 | confirmed | deepresearch | `variant-approval-invisible`: Which report a run ended in is page state: the chosen review is forgotten on reload, and an approved literature variant is invisible to the run's labels | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1414` |  | safe engineering, M: Owner product call: one concluding report per run, or several approved variants. Either way, load the prepared variants on mount and preselect an appr |
| F016 | P2 | confirmed | design | `conditional-question-dead-end`: A migrated conditional question blocks the run with a remedy that no longer exists, and nothing in Dotazník shows or removes it | `packages/aia_core/src/aia_core/domain/research_design.py:868-876` | fixed: PC15 |  |
| F017 | P2 | confirmed | design | `hypotheses-never-analysed`: Hypotheses the researcher writes reach no analysis, yet the hypotheses module runs on every analysed run | `packages/aia_core/src/aia_core/application/analysis_results.py:570-578` |  | registered: research-integrity-report chunk 8 and its lineage-matrix row (hypothes |
| F018 | P2 | confirmed | design | `proposal-review-hides-replacement`: Accepting an AI questionnaire proposal replaces every own question while the review says the questionnaire does not change | `packages/aia_core/src/aia_core/domain/research_agents.py:711-737` | fixed: PC6 |  |
| F019 | P2 | partially confirmed | design | `rq-identity-by-text`: Rewording or re-analysing a research question silently unlinks every item that measured it | `packages/aia_core/src/aia_core/domain/research_trace.py:140` |  | registered: Partly: run-recovery-and-truth 3b 'Not done' (.planning/plans/run-reco |
| F020 | P2 | confirmed | errors | `preflight-blocked-module-dead-end`: A module the preflight blocked is called 'model failed, can be repeated', but the repair excludes it and the finished run offers no action | `packages/aia_core/src/aia_core/application/analysis_results.py:701-715` |  | safe engineering, S: Expose whether a BLOCKED outcome came from preflight (attempts == 0) on the step or the analysis response. Word it separately and point to the violati |
| F021 | P2 | confirmed | errors | `recovery-reaches-no-one`: RECOVERY_REQUIRED (money possibly spent) reaches no operator: not reported, not listed, not resolvable | `apps/worker/src/aia_worker/worker.py:473-493` |  | 1. Report a step entering RECOVERY_REQUIRED, from both the worker and the reconciler, once per run and step. 2. Expose a minimal operator surface: a c |
| F022 | P2 | confirmed | fieldwork | `fieldwork-retry-repays`: A fieldwork attempt that resumes or retries asks every respondent again and pays again for answers already received | `apps/executors/src/aia_executors/ai_fieldwork.py:282-321` |  | registered: OI-64 |
| F023 | P2 | partially confirmed | fieldwork | `panel-path-unreachable-on-class-c-route`: Panel-grounded respondents can never run on the deployed route: every panel request is Class A while the route is Class C only, yet the switch is planned as an operator flip and the API would make the panel the default | `packages/aia_core/src/aia_core/domain/panel_persona.py:295` |  | registered: D6 (overview.md:772) covers the route decision in general. The panel's |
| F024 | P2 | partially confirmed | fieldwork | `readiness-blind-to-worker-egress`: Readiness says ready and Start takes a cost confirmation for runs the worker will park, because the API never reads the keys that decide egress | `deploy/develop/docker-compose.yml:121-188` |  | safe engineering, M: The API already reads the worker's reservation and price keys so it can show a ceiling (config.py:116-149). Have it also read the egress keys from the |
| F025 | P2 | confirmed | fieldwork | `runtime-park-no-way-out`: A research run parked at fieldwork can only be cancelled; its message says to start again, which returns the same parked run, and it leaks the gateway's English internals | `packages/aia_core/src/aia_core/domain/research.py:56-63` | fixed: PC4 |  |
| F026 | P2 | partially confirmed | flags | `activation-does-not-resume-parked-work`: Work parked because a switch was off never resumes when the switch is turned on; only agent jobs have a resume, and client-source proposals and materializations are a permanent dead end | `packages/aia_core/src/aia_core/domain/workflow.py:797-798` | fixed: PC4 (research, Deep Research, client sources; materialization has no screen) |  |
| F027 | P2 | confirmed | flags | `answerability-gate-off-after-d1`: The owner's D1 answer asks for an explicit, recorded 'continue with limitations', but AIA_RESEARCH_ANSWERABILITY_GATE stays off everywhere with no activation or retirement step | `apps/api/src/aia_api/config.py:92-97` |  | owner decision D-2 |
| F028 | P2 | confirmed | governance | `answerability-decision-invisible`: The 'continue with limitations' decision is recorded but never shown after start, and with the switch still off nobody makes it | `apps/api/src/aia_api/routers/research.py:376` |  | owner decision D-2 |
| F029 | P2 | partially confirmed | governance | `approval-ledger-write-only`: Who accepted, confirmed, acknowledged or approved a study's decisions is written to a ledger that nothing reads | `packages/aia_core/src/aia_core/infrastructure/tables.py:1460` |  | safe engineering, M: Add a read-only, study-scoped decision history: GET /studies/{id}/decisions over approval_decisions, plus the client's knowledge decisions from access |
| F030 | P2 | confirmed | governance | `approved-file-prints-unapproved`: An approved report's DOCX and PDF still print 'KONCEPT — NESCHVÁLENO … Nepředávejte ji jako finální' | `packages/aia_core/src/aia_core/infrastructure/report_docx/layout.py:129` |  | owner decision D-9 |
| F031 | P2 | confirmed | governance | `budget-wait-unliftable-dr-agents`: A Deep Research run or AI design job stopped at the study's budget cannot be let through | `packages/aia_core/src/aia_core/application/research.py:1152` | fixed: PC4 |  |
| F032 | P2 | confirmed | governance | `client-release-ungated`: The client report leaves AIA with no release gate, and approving it records and says 'internal use only' | `.planning/plans/two-roles-human-ai-gates.md:13` |  | owner decision D-10 |
| F033 | P2 | partially confirmed | governance | `self-approval-partial-enforcement`: Turning self-approval off does not stop the starter accepting an AI design proposal, yet it blocks report approval, and the client Profile calls it knowledge-only | `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:2425` |  | owner decision D-10 |
| F034 | P2 | confirmed | knowledge | `parked-client-work-never-resumes`: A document asked about while AI extraction was off, or its route not yet cleared, can never be asked again once it is on | `apps/executors/src/aia_executors/client_source_proposals.py:104-110` | fixed: PC4 |  |
| F035 | P2 | confirmed | knowledge | `source-retention-no-delete`: Every picked or dropped file is stored permanently under the client, even when removed from the sheet, with no list or delete anywhere | `apps/web/src/components/aia/clients/IntakeSheet.tsx:126,177-180` |  | owner decision D-15 |
| F036 | P2 | partially confirmed | knowledge | `unresolved-lineage-blocks-design-ai`: One approved DATASET or FINDING item makes every design AI job of the client's studies wait forever on the licence gate | `packages/aia_core/src/aia_core/domain/research_agents.py:639-641` |  | owner decision D-4 |
| F037 | P2 | already fixed | lifecycle | `closed-study-looks-editable`: A delivered, archived or cancelled study looks fully editable; every save fails with a role error and the edits are lost | `apps/api/src/aia_api/routers/workspace.py:1976` | fixed: PC1 |  |
| F038 | P2 | partially confirmed | lifecycle | `lifecycle-is-an-unbound-label`: Study status is a manual label set only in Settings, with no transition rules, no tie to a report, and nothing in the flow updates it | `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:637-668` |  | owner decision D-1 |
| F039 | P2 | confirmed | lifecycle | `no-member-offboarding`: An administrator cannot remove or deactivate a member, although membership is access to every client's data | `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:252-272` |  | registered: related: OI-22 (in-flight runs of a revoked user); the missing capabil |
| F040 | P2 | confirmed | population | `child-dimension-read-by-nothing`: A run 'over' a materialized child draws the same respondents as over LIVE: no step reads the added dimension, yet the UI and report present the child as the run's population, and choosing it pays for a second run | `packages/aia_core/src/aia_core/domain/panel_persona.py:225-229` |  | owner decision D-6 |
| F041 | P2 | confirmed | reports | `approval-provenance-invisible`: Who approved a report, when and why is recorded but readable nowhere; the UI never asks why and offers approval before the draft was opened | `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:563` |  | safe engineering, S: Read the approval from the ledger (subject_id = artifact id) and return {approved_by, approved_at, note} from GET …/report, …/report/context and the c |
| F042 | P2 | partially confirmed | reports | `approved-file-says-unapproved`: An approved report's files still print "KONCEPT — NESCHVÁLENO … Nepředávejte ji jako finální"; the client report can never leave AIA approved | `packages/aia_core/src/aia_core/infrastructure/report_docx/layout.py:129` |  | owner decision D-9 |
| F043 | P2 | confirmed | reports | `approved-version-shadowed`: An approved report version is not addressable: the newest draft silently replaces it (client report on #477's contract bump, re-prepared literature variant) | `packages/aia_core/src/aia_core/application/client_report.py:62` |  | owner decision D-9 |
| F044 | P2 | confirmed | reports | `composed-report-producer-is-downloader`: For the client report and the literature variant, separation of duties compares the approver with whoever first downloaded or prepared the file, not with who did the work | `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:383` |  | owner decision D-10 |
| F045 | P2 | confirmed | reports | `context-refusal-loses-reason`: Preparing the report with literature is refused with an English internal message and no reason code, so the researcher gets no remedy (e.g. after any analysis harness change) | `apps/api/src/aia_api/routers/research.py:2035` | fixed: PC17 |  |
| F046 | P2 | intentional by decision | reports | `no-document-without-ai-analysis`: A run's deterministic results (question tables, maps, design, method) reach no internal document unless all eight AI modules complete | `packages/aia_core/src/aia_core/application/report.py:158` |  | intentional (recorded decision) |
| F047 | P2 | confirmed | runs | `budget-wait-not-liftable-outside-research-runs`: AWAITING_BUDGET can be lifted only for research runs and client work; Deep Research runs and research-agent jobs that hit the study's cap wait forever | `packages/aia_core/src/aia_core/application/research.py:925-958` | fixed: PC4 |  |
| F048 | P2 | confirmed | runs | `cost-ceiling-not-a-bound`: The cost 'ceiling' a person confirms counts one pass of fieldwork, but every resume or retry of the fieldwork attempt asks every respondent again | `packages/aia_core/src/aia_core/domain/run_cost.py:111` |  | owner decision D-17 |
| F049 | P2 | confirmed | runs | `failed-run-leaves-live-steps`: A FAILED run is terminal while sibling steps are RUNNABLE or RUNNING: the screen shows work that will never finish, the report 'is still composing', and cancel does nothing | `packages/aia_core/src/aia_core/domain/workflow.py:853` | fixed: PC14 (read honestly; the engine still leaves the steps) |  |
| F050 | P2 | confirmed | runs | `idempotent-start-returns-dead-runs`: Asking for the same agent job or materialization again returns the earlier run whatever its state, so a failed, cancelled, recovery-required or parked one can never be asked for again | `packages/aia_core/src/aia_core/application/research.py:1268` | fixed: PC13 for agent jobs; materialization has no screen |  |
| F051 | P2 | confirmed | runs | `recovery-required-unreadable-unrecoverable`: A research run in RECOVERY_REQUIRED reads as a plain 'waiting' with no reason, cannot be retried, and has no operator path | `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1913` | fixed: PC14 (the reason said; recovery is cancel and retry) |  |
| F052 | P2 | confirmed | runs | `whole-retry-rebuys-fieldwork`: After a deterministic downstream failure (aggregate, sociomap, report) the only recovery is 'Spustit znovu', which quietly buys new AI fieldwork and a different dataset | `apps/executors/src/aia_executors/research.py:443` |  | registered: partly: .planning/plans/run-recovery-and-truth.md finding 3 / chunk 1b |
| F053 | P2 | partially confirmed | simulation | `sim-scope-undecided`: Simulation's MVP scope contradicts itself across records, and the studio plan has no owner | `.planning/plans/mvp-workflow-assurance.md:27-30` |  | owner decision D-5 |
| F054 | P2 | confirmed | sociomap | `client-report-promises-absent-maps`: The client report says it contains object maps when it contains none | `packages/aia_core/src/aia_core/application/client_report.py:186-193` | fixed: PC17 |  |
| F055 | P2 | confirmed | sociomap | `edited-method-silently-loses-client-approval`: Activating any Sociomap version on Metodika silently withdraws client approval of every new run's maps | `packages/aia_core/src/aia_core/domain/sociomap_register.py:52-86` | fixed: PC17 (said at activation; the register rule is unchanged) |  |
| F056 | P2 | confirmed | webia | `api-refusals-lose-words-and-detail`: Code-only API errors reach the web as an empty message (the report card loads forever), and most other refusals arrive as English text without their details or request id | `apps/api/src/aia_api/observability.py:226` | fixed: PC18 (no empty message); Czech words for ~45 codes open |  |
| F057 | P2 | confirmed | webia | `questionnaire-dr-panel-mixes-purposes`: The questionnaire's Deep Research panel lists and preselects Interpretation Research runs as if they were design research | `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:37` | fixed: PC18 |  |
| F058 | P2 | confirmed | webia | `tracked-set-rule-three-truths`: The web enforces 18.6.6's 4–15 tracked-set rule and silently truncates sets to 15, while the server runs the organization's pinned readiness limits (3–40 hard by default) | `packages/aia_core/src/aia_core/domain/research_design.py:86` |  | owner decision D-18 |
| F059 | P3 | confirmed | analysis | `failed-modules-read-as-waiting`: On a finished run, the Results analysis panel calls FAILED or CANCELLED modules 'Čeká' and says the rest 'ještě čekají na dokončení' | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1622-1627` |  | safe engineering, S: Word the nav label and the overview from analysis.pending's state (FAILED, CANCELLED, WAITING_*) and the run's is_terminal, and link to Průběh's repai |
| F060 | P3 | intentional by decision | analysis | `holdout-validation-test-only`: Holdout validation is reachable only from tests; nothing can preregister, start or record one, and analysis hard-codes no validation | `packages/aia_core/src/aia_core/application/validation.py:128` |  | intentional (recorded decision) |
| F061 | P3 | partially confirmed | analysis | `interval-order-rule-browser-only`: The 'an order only where 95 % intervals part' rule exists only in the browser; analysis prose is not held to it and the model is never given intervals | `apps/web/src/lib/result-reading.ts:2-9` |  | owner decision D-18 |
| F062 | P3 | partially confirmed | analysis | `modules-without-inputs-gate-report`: Hypotheses, segments and audience modules are paid model calls that never receive their inputs, yet each must COMPLETE for a report | `packages/aia_core/src/aia_core/domain/analysis/prompt.py:147-173` |  | owner decision D-18 |
| F063 | P3 | confirmed | deepresearch | `interpretation-list-20`: The literature panel reads 20 Deep Research runs while the report card reads 100, so a review the card offers can be missing from the panel below it | `apps/web/src/components/rehome/research/InterpretationResearch.tsx:49` |  | safe engineering, S: Read 100 runs (or a purpose- and target-filtered list from the API) in InterpretationResearch, as the card does. |
| F064 | P3 | confirmed | deepresearch | `sandbox-grant-reads-as-org-approval`: A study sandbox test grant is pinned as an organization approval, and the report says the organization approved the source table | `packages/aia_core/src/aia_core/infrastructure/deep_research_settings_repository.py:209-235` |  | safe engineering, S: Pin a test grant's origin distinctly (its own Origin, or the receipt carried into read_pin), and have _table_note say 'schváleno jen pro testovací stu |
| F065 | P3 | confirmed | deepresearch | `ui-hides-topic-and-score-meaning`: The screens where literature is judged show neither the topic each claim was searched for nor what the score means | `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:133-139` |  | safe engineering, S: Show each claim's subject text (bundle.subjects by subject_key) and the source class in Czech words labelled 'podle domény', and drop or explain the b |
| F066 | P3 | partially confirmed | design | `answerability-gate-off-after-d1`: The owner's D1 decision (continue with limitations, recorded) is not in force: the gate still ships off | `apps/api/src/aia_api/config.py:93-97` |  | owner decision D-2 |
| F067 | P3 | confirmed | design | `fix-links-misroute`: 'Opravit' links send the researcher to the wrong stage, or offer a fix where none exists | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:367-371,487-491,767,1183` |  | safe engineering, S: Map sociomap_support and dimensions to persona, route the no_research_questions gap to plan, hide 'Opravit' for UNKNOWN, and add fixStep tests. |
| F068 | P3 | partially confirmed | design | `lane-readiness-two-truths`: Stage track and 'Do spuštění zbývá' use browser rules that contradict server readiness in both directions | `apps/web/src/research/lane.ts:28-30,38-44,63-70,100-115,121-136` |  | safe engineering, M: Read the last server readiness and answerability for the latest submitted revision into the lane (or fetch it on stage change), and map each FAIL and  |
| F069 | P3 | confirmed | design | `rq-cap-silent`: A ninth research question silently disappears from the trace, the gate, the analysis and the report, and its links are called stale | `packages/aia_core/src/aia_core/domain/analysis/native.py:100,157` |  | safe engineering, S: Say the limit of 8 in ProposalEditor. Make research questions beyond 8 a readiness check or answerability gap ('not read by the analysis'; new rules i |
| F070 | P3 | confirmed | design | `run-stage-stale-copy`: The Run stage can run a copy of the design that a colleague has already replaced, without saying so | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:621-640` |  | safe engineering, S: Before submitting, compare the store's revision with the working content's current revision (a cheap GET or a base_revision field on the design submit |
| F071 | P3 | partially confirmed | design | `unrunnable-controls-offered`: Dotazník and the AI agents offer a familiarity check and segment comparison that AIA always refuses, said only on Spuštění | `apps/web/src/components/rehome/research/QuestionnaireStep.tsx:953-954,600-602` |  | safe engineering, S: Annotate the familiarity switch when on ('AIA zatím neumí položit; běh se nespustí') and mark the compare_segments option as not answerable yet. In Pr |
| F072 | P3 | confirmed | errors | `500-loses-request-id`: A 500 tells the person to quote a request id that neither its body nor its headers carry | `apps/api/src/aia_api/observability.py:95-136,232-247` |  | registered: OI-125 (hypothesis; this reproduces it and adds the missing header) |
| F073 | P3 | confirmed | errors | `api-messages-unworded`: API refusals reach the Czech UI as English developer sentences, and their codes and reasons have no words | `apps/api/src/aia_api/routers/research.py:571-594,669-699,1001-1025` |  | safe engineering, M: Add one client helper, refusalWords(e), that maps ApiError.code (and details.reason) through codeWords and keeps the message under technical details.  |
| F074 | P3 | confirmed | errors | `client-proposals-uncertain-dead-end`: A document's AI proposals stuck on an uncertain call can never be asked again, while the UI promises an administrator will verify it | `packages/aia_core/src/aia_core/application/source_proposals.py:148-151` |  | safe engineering, S: Ship the operator resolution from recovery-reaches-no-one and let a resolved call make the run restartable. Until then, reword the copy to say no one  |
| F075 | P3 | confirmed | errors | `corrupt-report-loading-forever`: A corrupt stored report makes the report card read 'Načítám projekt…' for ever while the run still says REPORT_READY, with no way to recompose | `apps/api/src/aia_api/routers/research.py:1639-1677` | fixed: PC18 (the refusal is said, not 'loading') |  |
| F076 | P3 | confirmed | errors | `progress-polling-stops-on-error`: One transient error stops a run's Progress polling for good, leaving a stale 'Běží' | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:940-986` |  | safe engineering, S: In the catch, schedule the next read (for example at pollMs(run) × 2, capped) when the last known run still shouldPoll and the error is not a 4xx. |
| F077 | P3 | partially confirmed | errors | `provider-text-over-words`: The provider's raw error text replaces AIA's Czech wait words, and failure_class is never read, so permanent configuration failures look retryable | `packages/aia_core/src/aia_core/infrastructure/model_adapters/bedrock.py:144-146,333-366` |  | safe engineering, S: In waitingDetail and failedAt, prefer worded known reasons and failure classes (codeWords over research.exec.wait.* and a new research.exec.failure.*) |
| F078 | P3 | partially confirmed | errors | `runtime-park-never-resumes`: Runtime parks are worded as waits that will clear, but nothing resumes a research run, Deep Research run or client-source proposals run once the runtime exists | `packages/aia_core/src/aia_core/domain/workflow.py:768-813` | fixed: PC4 |  |
| F079 | P3 | partially confirmed | errors | `step-reason-projection-lossy`: Research and Deep Research steps lose their own stop reason; a run in RECOVERY_REQUIRED reads as an ordinary 'Čeká' | `apps/api/src/aia_api/routers/research.py:854-878` | fixed: PC14 in part (recovery_reason) |  |
| F080 | P3 | confirmed | fieldwork | `child-population-under-roster`: The Run stage offers a client's materialized dimension as the run's population even when the fictional roster answers; it becomes a separate run but changes nothing | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:784` |  | safe engineering, S: Enable PopulationChoice only when the selected persona source is panel, and say why otherwise. Optionally have the API refuse population_version_id un |
| F081 | P3 | confirmed | fieldwork | `settings-misdescribes-runtime`: Settings tells admins FAST_EXTRACTION has no native step while the worker binds it to send clients' documents; the activity and the panel switch are missing | `apps/executors/src/aia_executors/ai_runtime.py:463-464` |  | safe engineering, S: Add a client_source_proposals activity (FAST_EXTRACTION; switches AIA_AI_RUNTIME_ENABLED and AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED) and the panel swi |
| F082 | P3 | partially confirmed | flags | `analysis-switch-decides-report-silently`: The API's AIA_AI_ANALYSIS_ENABLED silently decides whether a run will ever have analysis or any report, including its deterministic chapters | `apps/api/src/aia_api/routers/research.py:1173` |  | safe engineering, S: Expose analysis_enabled (and sociomapping_enabled) on the readiness response and say it on the Run stage and on the report card's NONE state. Product  |
| F083 | P3 | partially confirmed | flags | `api-worker-split-switches-unchecked`: Switches that the API and the worker must agree on have no agreement check, and one rule is duplicated in both processes | `apps/api/src/aia_api/config.py:87-102` |  | safe engineering, S: Move the search-route resolution into aia_core.domain (as deployment.py did for fictional material) and use it from both processes. Add a Compose test |
| F084 | P3 | partially confirmed | flags | `connectedness-interval-unreachable-and-unpinned`: The K100 bootstrap switch cannot reach the develop worker, is not pinned on the run, and its F9 parameters stay editable in Metodika | `apps/executors/src/aia_executors/registry.py:57-75` |  | owner decision D-18 |
| F085 | P3 | confirmed | flags | `settings-page-says-fast-extraction-unused`: Nastavení → AI says FAST_EXTRACTION is called by nothing while the worker binds it and sends client documents (Class A) to the model | `apps/executors/src/aia_executors/ai_runtime.py:463-464` |  | safe engineering, S: Add a client_source_proposals NativeActivity (FAST_EXTRACTION, switches RUNTIME + AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED) and hand that switch to the  |
| F086 | P3 | intentional by decision | governance | `dr-test-policy-operator-only`: A study-scoped Deep Research test approval overrides the organization's settings with no route, no UI and no mark on the run | `packages/aia_core/src/aia_core/infrastructure/deep_research_settings_repository.py:209` |  | intentional (recorded decision) |
| F087 | P3 | confirmed | governance | `oi82-ai-knowledge-accept-not-in-ledger`: OI-82's trigger has happened: AI now writes Knowledge proposals, and accepting one is still not a gate-1 ledger row | `apps/executors/src/aia_executors/client_source_proposals.py:271` |  | registered: OI-82 |
| F088 | P3 | confirmed | governance | `settings-omit-runtime-switches`: Settings claims to list every control but omits the switches that decide what a person is asked or offered | `apps/api/src/aia_api/routers/settings.py:182` |  | safe engineering, S: Add the API's own switches with their values, and the worker's switch names, to the settings document. Add a test comparing the AIA_* switches Compose |
| F089 | P3 | confirmed | knowledge | `ai-grounding-lost-after-accept`: An accepted AI-extracted item no longer shows its quote, locator or document, and its history does not say AI wrote it | `apps/executors/src/aia_executors/client_source_proposals.py:266` |  | registered: partly: lifecycle K2f/K3 (typed provenance); this gap: no |
| F090 | P3 | partially confirmed | knowledge | `client-budget-decisions-without-numbers`: Client-paid AI asks and lifts show no cost, no remaining budget and no later record | `apps/web/src/components/aia/clients/SourceProposals.tsx:68-95` |  | registered: client-budget CB5 is open (proof only); this UX gap: no |
| F091 | P3 | partially confirmed | knowledge | `competitors-become-client-terms`: Competitors recorded on Profil silently stop Deep Research from searching the web about them | `apps/web/src/components/aia/clients/ProfileArea.tsx:35,107` |  | Data-owner decision (DR-2 list): offer the existing public flag when an ENTITY is recorded, with the owner choosing the default for role=competitor an |
| F092 | P3 | confirmed | knowledge | `data-tab-dead-end`: The Data tab lists datasets that nothing can use, and does not say so | `apps/web/src/components/aia/clients/DataArea.tsx:17-63` |  | registered: client-workspace C8 (open) |
| F093 | P3 | confirmed | knowledge | `knowledge-window-silent-truncation`: Knowledge beyond the 200 newest items is dropped from design and Deep Research context without being named, and the researcher never sees what a job used | `packages/aia_core/src/aia_core/infrastructure/client_knowledge_repository.py:67,185,270-28` |  | registered: lifecycle K4 (selection); the silent omission itself: no |
| F094 | P3 | partially confirmed | knowledge | `review-queue-at-ai-volume`: Ke schválení cannot handle AI volume or edits: it caps silently at 200, has no batch, shows no diff, and the starter of an AI run gets a 403 the UI did not predict | `apps/web/src/components/aia/clients/KnowledgeArea.tsx:47-140,111,114` |  | registered: client-workspace C6, lifecycle K2f (open); the SoD two-truths: no |
| F095 | P3 | confirmed | knowledge | `title-only-dimension-offered`: A title-only client DIMENSION is offered in Dimenze as a selectable dimension that fieldwork never applies | `apps/web/src/research/persona.ts:53-60` |  | registered: client-knowledge-lifecycle F-K2 (plan only; no OI) |
| F096 | P3 | confirmed | legacy | `metodika-note-stale-d6`: Settings → Metodika says the Sociomap is internal only while D6 is open, contradicting the register that made aia-sociomap-3 client-facing on 2026-10-13 | `packages/aia_core/src/aia_core/domain/methodology/sociomap.py:819` | fixed: PC7 |  |
| F097 | P3 | partially confirmed | legacy | `non-bedrock-adapters-unreachable`: The Anthropic, OpenAI and Claude Code CLI adapters are maintained but no deployed composition can build them | `packages/aia_core/src/aia_core/infrastructure/model_adapters/__init__.py:21` |  | owner decision D-13 |
| F098 | P3 | partially confirmed | legacy | `oi58-live-migration-unrecorded`: The one-off 18.6.6 content migration has been deployed for 18 days and nothing records whether it ever ran; the product keeps its whole path and no surface says whether any Study still waits | `.planning/open-items.md:1944` |  | owner decision D-14 |
| F099 | P3 | confirmed | legacy | `oracle-ci-job-cannot-execute`: The CI oracle-parity job runs on every code PR but can never reach the oracle | `.github/workflows/ci.yml:379` |  | owner decision D-8 |
| F100 | P3 | partially confirmed | legacy | `prototype-stage-rows-every-save`: Every working-content revision writes 13 prototype project_stages rows and an impact record that no product surface reads | `packages/aia_core/src/aia_core/infrastructure/study_workspace_repository.py:298` |  | safe engineering, M: When owner is set, skip writing stages and the model field for owned projects. Alternatively, if the generic routes are retired, stop writing stage ro |
| F101 | P3 | confirmed | legacy | `route-ledger-credits-walking-skeleton`: The parity ledgers credit develop_snapshot-only generic routes as AIA's equivalent of the unit's research run, and report shipped capabilities as not started | `docs/migration/legacy-route-ledger.json:1974` |  | safe engineering, S: Re-point the run, workflow, artifact and job-feed rows to the research routes (scope: study), or mark them RETIRED with a decision. Update project.mem |
| F102 | P3 | confirmed | legacy | `stale-plan-front-matter`: The mandated session-start status (tools/progress.py) gives obsolete or already-shipped 'Next' chunks for at least seven in-progress plans | `.planning/plans/research-lane-redesign.md:13` |  | safe engineering, S: In one docs-only PR: mark superseded chunks '[-]' (interface-skin 6, legacy-strangler 3, interface-rehome 2 and 5+, research-flow-rehome 12, design-sy |
| F103 | P3 | confirmed | legacy | `walking-skeleton-studies-surface`: The walking-skeleton /studies pages and generic project and run routes are still reachable and write unowned projects into real Studies that /app never shows | `deploy/develop/Caddyfile:49` |  | owner decision D-13 |
| F104 | P3 | confirmed | lifecycle | `client-archive-fails-running-work`: Archiving a client from Settings, unconfirmed, permanently fails every in-flight run of its studies and hides all its work from members | `apps/web/src/components/aia/settings/ControlPanel.tsx:340-346` |  | owner decision D-16 |
| F105 | P3 | partially confirmed | lifecycle | `delivery-freezes-nothing-in-flight`: Marking a study DELIVERED stops new work only: in-flight runs keep spending, and new report drafts and approvals land after delivery | `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:640-641` |  | owner decision D-1 |
| F106 | P3 | confirmed, partly fixed (#715 deleted ResolvedAccess) | lifecycle | `grant-era-remnants-in-auth-core`: Docstrings and dead types in the authorization core still describe grants, and a self-approval default of False | `packages/aia_core/src/aia_core/domain/scope.py:7` |  | safe engineering, S: Correct the docstrings and delete ResolvedAccess, ScopeRole.from_stored with its test, and the study-only branches (client_role always RESEARCHER). |
| F107 | P3 | partially confirmed | lifecycle | `simulation-create-dead-end`: 'Nová simulace' creates a study that can never be set up or run, and cannot be removed | `apps/web/src/components/aia/clients/ClientContext.tsx:135-138` |  | owner decision D-5 |
| F108 | P3 | partially confirmed | lifecycle | `study-closed-error-semantics`: The same 'study closed' refusal reaches the browser five different ways, including a 404, a 500 and a role error | `apps/api/src/aia_api/routers/workspace.py:626-630` | fixed: PC1 for the workspace routes; other routers still word it differently |  |
| F109 | P3 | confirmed | population | `child-definition-unverified-and-not-kept`: A child's evidence anchor is never checked against the client's knowledge, and its definition survives only in one study's run input | `packages/aia_core/src/aia_core/domain/population/definition.py:71-83` |  | safe engineering, M: In prepare_materialization, read the anchor through ClientKnowledgeRepository with the study's ClientContext and refuse by name (evidence_unknown, evi |
| F110 | P3 | confirmed | population | `data-tab-inert`: The client's Data tab lists dataset items with nothing to open or do, and omits the client's own derived population | `apps/web/src/components/aia/clients/DataArea.tsx:17-63` |  | registered: client-workspace C8 (open) |
| F111 | P3 | partially confirmed | population | `materialize-unreachable-from-ui`: A researcher cannot materialize a dimension from AIA; the child listing and the Run-stage picker are fed only by a hand-written API call | `apps/api/src/aia_api/routers/materialize.py:215` |  | owner decision D-6 |
| F112 | P3 | partially confirmed | population | `mvp-new-live-revision-vs-m5`: The MVP's data-library gate requires a materialized dimension to become a new LIVE revision; the owner's M5 forbids that, and no validation or calibration step exists | `.planning/plans/mvp-workflow-assurance.md:61` |  | owner decision D-6 |
| F113 | P3 | partially confirmed | population | `operator-lifecycle-shell-only-unattributed`: Every population decision is a shell command whose actor is a self-asserted email, and the product hides who made it | `apps/executors/src/aia_executors/population_ops.py:139-158` |  | registered: partially: OI-96 (the import ran as the AWS root user); the unverified |
| F114 | P3 | confirmed | population | `panel-run-identity-ignores-live-version`: After LIVE is promoted, starting the same design as a panel run silently returns the run drawn from the superseded LIVE; nothing lets it run over the new LIVE | `packages/aia_core/src/aia_core/application/research.py:318-339` |  | owner decision D-7 |
| F115 | P3 | confirmed | reports | `d5-chapter-page-breaks`: Owner D5 not yet applied: every chapter and appendix starts on a new page | `packages/aia_core/src/aia_core/infrastructure/report_docx/styles.py:177` | fixed: PC9 |  |
| F116 | P3 | partially confirmed | reports | `delivered-report-not-recorded`: Which report a run delivered is recorded nowhere: the variant choice is page state, and project memory reads only the base report's approval | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1414` |  | owner decision D-1 |
| F117 | P3 | confirmed | reports | `pdf-disabled-offered-again`: With the PDF converter off, the card says PDF is off in this deployment and still offers 'Vytvořit PDF znovu', which always fails | `packages/aia_core/src/aia_core/application/report_variants.py:101` |  | safe engineering, S: Leave pdf_disabled unaskable from the card (the operator turns the converter on, and the next prepare asks again), or drop 'Můžete ho nechat vytvořit  |
| F118 | P3 | confirmed | reports | `report-panel-stale-after-approval`: After approving in the card, the report tab still says "Koncept čeká na schválení." | `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1482` |  | safe engineering, S: Lift the base report status into RunResults (one read, passed to both) or re-read it after an approval. |
| F119 | P3 | confirmed | runs | `polling-stops-on-attention-with-live-siblings`: Progress stops reading a run once any step needs a person, though its other steps are still running | `apps/web/src/lib/research-execution.ts:82-93` | fixed: PC14 |  |
| F120 | P3 | confirmed | runs | `restart-same-revision-silent`: Starting a revision that already has a run asks the person to confirm a cost, starts nothing, and lands on the newest run without saying so | `apps/api/src/aia_api/routers/research.py:1038-1124` | fixed: PC13 (said after the click, not before) |  |
| F121 | P3 | partially confirmed | runs | `results-run-two-truths`: The stage track and the Results stage pick different runs, and a run cancelled after fieldwork hides its standing results | `apps/web/src/research/lane.ts:126` |  | safe engineering, S: Have the lane return the run id it counts, link Výsledky with ?run=<that id>, and let runState read a terminal CANCELLED run with an aggregate artifac |
| F122 | P3 | confirmed | runs | `runtime-park-never-resumes`: A research run (or materialization, or Deep Research run) parked because the AI runtime was unavailable stays parked after the runtime is enabled, and only agent jobs have a resume route | `packages/aia_core/src/aia_core/domain/workflow.py:797` | fixed: PC4 |  |
| F123 | P3 | confirmed | simulation | `open-count-includes-closed`: 'otevřených: N' on the Výzkumy and Simulace tabs counts delivered and cancelled studies | `apps/api/src/aia_api/routers/workspace.py:861-870` |  | safe engineering, S: Count with OPEN_STATUSES in client_workspace, matching the overview and directory. Cross-cutting: client workspace. |
| F124 | P3 | partially confirmed | simulation | `sim-plan-endpoint-not-usable`: Even S1-S7 end on a hand-authored fictional world model; what a simulation result may claim is undecided | `.planning/plans/simulation-studio.md:64-67` |  | registered: partially: simulation-studio.md 'Later, out of this plan'; D10, D11 an |
| F125 | P3 | partially confirmed | simulation | `sim-two-discriminators`: Two unrelated markers say what a simulation is: Study.kind and generic Project.project_type | `apps/api/src/aia_api/schemas/projects.py:27` |  | safe engineering, S: In S1, derive the owned working project's project_type from Study.kind and refuse a mismatch on the generic projects route. Record the choice in the p |
| F126 | P3 | confirmed | simulation | `sim-ui-implies-workflow`: The UI invites creating simulations, then shows the dead-end study as active work with 'Pokračovat' | `apps/web/src/components/aia/clients/ClientContext.tsx:136-138` |  | owner decision D-5 |
| F127 | P3 | intentional by decision | simulation | `study-status-hand-set`: A study's status is a hand-set label, so a simulation that produced nothing can be marked 'Předáno' | `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:637-668` |  | intentional (recorded decision) |
| F128 | P3 | confirmed | sociomap | `empty-maps-tab-without-reason`: A run with no tracked set shows an empty Sociomapy tab with map instructions and never the stored reason | `packages/aia_core/src/aia_core/domain/research_sociomap.py:587` | fixed: PC17 |  |
| F129 | P3 | partially confirmed | sociomap | `no-real-data-preview-of-a-method-change`: A method change can be seen on real data only through a new paid run whose answers also change | `packages/aia_core/src/aia_core/domain/methodology/sociomap_check.py:12, 235-243` |  | Product decision. One option is a 're-map' restart that mirrors retry_analysis: the frozen dataset, the methodology now in force, no fieldwork, no spe |
| F130 | P3 | partially confirmed | sociomap | `pin-resolution-errors-unmapped`: Hypothesis: an in-force Sociomap version that stops resolving gives a generic 500 on every start and readiness check, and a failed step cannot be recovered from the UI | `packages/aia_core/src/aia_core/application/research.py:497, 993, 1110-1135` |  | safe engineering, S: Map these exceptions to a 409 with the module's name. Optionally check versions in force at API start-up. Add the code's words to reason-words. |
| F131 | P3 | confirmed | sociomap | `report-pair-table-drops-q6-gates`: The report's relationship table omits the effective-n basis and the effect floor that aia-sociomap-3 judges each pair by | `packages/aia_core/src/aia_core/application/report_maps.py:163-196` |  | registered: research-integrity-report F5 / chunk 7 (English status words, n basis) |
| F132 | P3 | confirmed | sociomap | `reuse-key-omits-object-map-engine`: The Sociomap step's reuse key tracks the legacy engine's version but not the canonical object-map engine's | `apps/executors/src/aia_executors/research.py:640-670` |  | safe engineering, S: Add OBJECT_MAP_IMPLEMENTATION_VERSION to the step's input fingerprint, and extend the existing test to the object-map engine. |
| F133 | P3 | partially confirmed | sociomap | `role-and-rating-universe-declarations-unreachable`: Context objects and standalone rating items, which the approved map relies on, cannot be declared anywhere in the product | `packages/aia_core/src/aia_core/domain/research_design.py:247-275, 484, 562-563` |  | registered: documented in research-journey.md:417 and sociomap-formula-corrections |
| F134 | P3 | partially confirmed | sociomap | `stale-internal-labels-vs-register`: Six surfaces still say every Sociomap is internal (D6 open) while the register approves aia-sociomap-3 | `packages/aia_core/src/aia_core/domain/research_sociomap.py:513-514, 573` | fixed: PC7 |  |
| F135 | P3 | confirmed | sociomap | `superseded-preset-still-a-base`: aia-sociomap-2 is still accepted as the base of a new version, and new runs would pin it | `packages/aia_core/src/aia_core/domain/methodology/sociomap.py:808-812` |  | owner decision D-18 |
| F136 | P3 | partially confirmed | webia | `cancel-requested-ignored`: After 'Zrušit běh' the run keeps reading Běží with an active cancel button until the step's next checkpoint | `apps/api/src/aia_api/routers/research.py:418` |  | safe engineering, S: Read cancel_requested in runState or ProgressActions: say 'Ruší se' and disable the button. Add the field to the Deep Research run response. |
| F137 | P3 | partially confirmed | webia | `dr-design-gate-and-provenance-api-only`: Deep Research's design-proposal accept (a human gate) and its provenance, coverage and captured snapshots exist only in the API | `apps/api/src/aia_api/routers/deep_research.py:665` |  | registered: deep-research-web-search.md chunk 24 (screen); snapshot linking not re |
| F138 | P3 | intentional by decision | webia | `materialization-api-only`: A client dimension can be materialized only by a raw API call, yet the Run stage offers the result and the Intelligence page says it is not in AIA | `apps/api/src/aia_api/routers/materialize.py:215` |  | intentional (recorded decision) |
| F139 | P3 | confirmed | webia | `run-lists-silently-truncated`: Run lists are cut at the API's default of 20 with no cursor or total, and screens on one page read different windows | `apps/api/src/aia_api/routers/research.py:1218-1219` |  | safe engineering, S: Add has_more or next to both list responses. Read one shared window for Deep Research runs on Results, and offer 'starší běhy' paging where history is |
| F140 | P3 | intentional by decision | webia | `simulation-cta-creates-inert-study`: 'Nová simulace' is a primary action that creates a study which can do nothing | `apps/web/src/components/aia/clients/ClientContext.tsx:136-138` |  | owner decision D-5 |
| F141 | P3 | confirmed | webia | `studies-live-pages-transitional`: The /studies 'live' pages and the 18.6.6-shaped generic project/run routes remain a second, client-less product on the product hostname | `deploy/develop/Caddyfile:49` |  | owner decision D-13 |
| F142 | P3 | confirmed | webia | `working-content-history-unreachable`: A study's working-content history is recorded but can be neither read nor restored | `apps/api/src/aia_api/routers/workspace.py:2070` |  | safe engineering, M: Add GET …/workspace/revisions/{n} (content) and a restore that saves it as a new revision (stale-checked like any save), plus a history drawer on the  |

## Capability map (at 20b24bb)

224 capabilities as the readers found them: 66 usable, 72 partial, 32 not built, 23 not usable, 18
operator-only, 13 workbench or test only. Rows changed by this PR are named in the findings above.

| Area | Capability | Usable | UI | API | Gap |
|---|---|---|---|---|---|
| design | Study working content: load once per study session, 1.8 s autosave, stale save refused (409 stale_revision), visible save state | yes | store.ts ResearchStore; SaveIndicator |  | None for a single editor. With two editors, a copy that never tried to save after a colleague's save can still be submitted to run (F10). |
| design | Design Revisions: immutable, owned, deduplicated against the newest; proposal acceptance only against an unchanged baseline under the Study row lock | yes |  | POST/GET /design/revisions (routers/research.py:771-827) | Infrastructural. No UI lists or restores revisions or working-content history (no restore found). |
| design | Plan narrative editing (research questions, objectives, hypotheses) | partial | PlanStep.tsx, ProposalEditor.tsx, plan-edit.ts |  | Hypotheses reach no analysis (F6). Rewording a research question orphans its links and comparison (F1). More than 8 research questions are silently truncated (F7). |
| design | Item to research-question links and declared comparisons (Dotazník) | partial | QuestionnaireStep.tsx:580-605, :758-800; trace.ts |  | Links are by exact text, with no carry-over on edit. compare_segments is offered though always unanswerable. Stale comparison keys are invisible. |
| design | Native AI design agents (analyze, build, optimize, audience, dimensions) with inline ProposalReview and gate-1 acceptance | partial |  |  | The review states the questionnaire does not change while build/optimize replace every own section (F5). Analyze acceptance orphans links (F1). Agents may propose familiarity sets and compare_segments (F2). The worker ne |
| design | Server readiness (compile + structural checks under the pinned or in-force readiness methodology) | yes |  | GET /research/readiness (routers/research.py:1038-1124) | The conditional_questions FAIL names a remedy that no longer exists (F3). Check ids route to the wrong fix stage (F9). |
| design | Question outlook and support forecast before start | yes |  |  | The forecast is unknown for panel or non-AI sources by design. Every such RQ then shows an 'Opravit' link with nothing to fix (F9). |
| design | Research trace, answerability and acknowledgement gate (#477) | partial | AnswerabilityGate.tsx, lib/answerability.ts |  | The gate is off by default everywhere, develop included, so the owner's D1 'continue with limitations, recorded' is not in force (F8). Text-keyed links make gaps appear after harmless rewording (F1). |
| design | Stage track and Inspector design status ('Do spuštění zbývá') | partial | lane.ts, StageTrack.tsx, Inspector.tsx |  | Re-derived in the browser with rules that differ from server readiness and answerability (F4). |
| design | Run start over the exact revision shown (cost confirmation, persona source, population child, idempotent per revision) | yes |  | POST /research/runs (routers/research.py:1147-1199) | F10 race between editors only. |
| design | Conditional questions (filtr) and familiarity-required sets | not_built |  |  | Always FAIL at readiness. The UI offers the familiarity switch and cannot show or remove a migrated condition (F2, F3). |
| design | compare_segments comparison | not_built |  |  | Always a gap (segments_unavailable), yet offered in Dotazník and to the AI agent (F2). |
| lifecycle | Create a client (any member) | yes | ClientDirectory 'Nový klient' | POST /api/v1/workspace/clients | none |
| lifecycle | Create a research study | yes | ClientContext 'Nový výzkum' | POST /api/v1/clients/{id}/studies | starts DRAFT with budget 0; first paid step waits for a budget raise |
| lifecycle | Create a simulation study | partial | ClientContext.tsx:135-138, SimulationFrame.tsx | POST /api/v1/clients/{id}/studies kind=SIMULATION | creates a record that can never be set up or run; frame says notInAia only after creation; cannot be deleted |
| lifecycle | Change study lifecycle status (deliver, archive, cancel, reopen) | partial | ControlPanel.tsx:394 | PUT /api/v1/studies/{id}/status | only from Nastavení → Studie; no transition rules; consequences not explained; delivered_at survives reopen; nothing in the flow sets it |
| lifecycle | Deliver a study (bind and freeze the approved report) | not_built |  |  | DELIVERED is a label; ArtifactRepository.freeze has no product caller; delivery binds no run or artifact |
| lifecycle | Closed-study enforcement (backend) | yes |  | require_open_study, workflow_repository.py:509 backstop | in-flight runs not stopped; report composition and approval still allowed |
| lifecycle | Closed-study presentation (UI) | no | ResearchStudy.tsx:45; workspace.py:1976,2004 |  | accepts_work ignored in /app; can_edit stays true; actions fail with a misleading English role message |
| lifecycle | Archive / unarchive a client | partial | ControlPanel.tsx:340-346 (admin) | PUT /api/v1/clients/{id}/status | no confirmation; silently fails all in-flight runs of its studies; client becomes invisible to members |
| lifecycle | Study budget | yes | ControlPanel.tsx:402; ExecutionSteps BudgetLift | PUT /studies/{id}/budget; POST …/steps/{node}/budget | set in Settings or by raising it on a waiting step only |
| lifecycle | Study spend-confirm limit | yes | Run stage CostCard (ExecutionSteps.tsx:221-300) | PUT /studies/{id}/spend-confirm | none |
| lifecycle | Client budget | yes | ProfileArea | GET/PUT /clients/{id}/budget | none |
| lifecycle | Self-approval levels | yes | Settings approvals (admin) | GET/PUT /self-approval | not applied to study delivery |
| lifecycle | Add member / change role | yes | ControlPanel members (admin) | POST /api/v1/members | no guard against demoting the last administrator |
| lifecycle | Remove or deactivate a member | no |  | none | ScopeRepository.deactivate_user has no route or UI and is not scoped to the organization |
| lifecycle | Access audit | yes | Settings audit (admin) | GET /api/v1/access-audit | none |
| lifecycle | Worker execution scope (lease-bound, approvals withheld) | yes |  |  | does not re-check the triggering user (OI-22) or study status |
| runs | Start a research run over a Design Revision | yes | Run stage Start (ExecutionSteps.tsx:672 @ 20b24bb) | POST /studies/{id}/research/runs (apps/api/src/aia_api/routers/researc | Readiness does not say that a run already exists. The start returns an existing run in any state (a cancelled one included) after the person has confirmed a cost, and does not say that nothing started. |
| runs | Retry a whole research run | partial | Progress 'Spustit znovu' (ExecutionSteps.tsx:1169-1177 @ 20b24bb) | POST …/research/runs/{id}/retry (routers/research.py:1348) | Only FAILED or CANCELLED runs can be retried (domain/research.py:56). The retry always buys AI fieldwork again (executors/research.py:443), and the button says so only when analysis modules are repairable. |
| runs | Retry failed analysis modules over frozen data | yes | AnalysisRepair card on Progress | POST …/analysis/retry, GET …/analysis/retryable | Only analysis modules qualify. A failed aggregate, sociomap or report has no frozen-data retry. |
| runs | Cancel a research run | partial | Progress 'Zrušit' while !is_terminal | POST …/cancel (routers/research.py:1267) | It does nothing on a FAILED run whose siblings are still RUNNABLE or RUNNING (workflow_repository.py:2539). |
| runs | Lift a budget wait (research run) | yes | BudgetLift under the AWAITING_BUDGET step | POST …/steps/{node}/budget (routers/research.py:1296) | None for research runs. |
| runs | Lift a budget wait (Deep Research, research-agent jobs) | no |  |  | There is no route. resume_budget_wait is called only from research.py:955 and client_work.py. Raising the study budget does not resume these steps. |
| runs | Resume a runtime park after the runtime is enabled | partial | agent jobs only (useResearchAgents.tsx) | POST /research/agent-jobs/{id}/resume only (routers/research.py:2500) | Research runs, materializations and Deep Research runs parked with ai_runtime_unavailable never resume (domain/workflow.py:797) and have no resume route. |
| runs | Resolve RECOVERY_REQUIRED (uncertain paid call / attempts exhausted) | partial | Step chip 'Potřebuje zásah', run chip 'Čeká', no reason |  | waiting_reason is not stored (workflow_repository.py:1913). Retry is refused. The only way out is Cancel then retry, and the screen does not say so. force_step_status and runs_needing_attention have no caller, and error  |
| runs | Progress page live state | partial | useRun + shouldPoll/pollMs (research-execution.ts:82-101) |  | Polling stops when any step needs a person, or the run is FAILED, even while other steps are still running. |
| runs | Run cost ceiling and spend confirmation | partial | CostCard and confirm (cs.ts:2450-2452 @ 20b24bb) |  | It counts one pass of fieldwork, but resumes and retries ask every respondent again (OI-64). The text calls it an upper bound. |
| runs | research_agent jobs (design AI help) | partial | useResearchAgents | /research/agent-jobs (start, get, cancel, resume, result, accept) | A failed, recovery-required, budget-parked or cancelled job is returned again for the same design, instruction and context. There is no retry and no budget lift. |
| runs | Deep Research workflow | partial | DeepResearchPanel, InterpretationResearch | /research/deep-research/runs … | No budget lift. A runtime park never resumes. Retry works for FAILED and CANCELLED only. |
| runs | report_pdf workflow | yes | report card |  | Asking again after a dead job starts a new round. This is the model the other workflow types should follow. |
| runs | client_source_proposals workflow | yes | SourceProposals |  | Restartable rule plus client budget lift (OI-121 closed). |
| runs | population_materialize workflow | operator_only | No web caller starts it. The Run stage only selects children that alre | POST/GET /studies/{id}/population/materializations (routers/materializ | No cancel, retry or resume. A parked or failed run is found again by its key (application/materialize.py:114-121) forever within that study. |
| runs | develop_snapshot workflow | operator_only | /studies live page (not linked from /app) | POST /studies/{id}/projects/{pid}/runs (Literal develop_snapshot) | It exists to prove the deploy (smoke.py). |
| runs | respondent_validation workflow | not_built |  |  | No route or CLI creates it. Executors are registered (registry.py:116). Plan chunks 7f-7h are open. |
| runs | Engine gates (AWAITING_GATE, decide_gate) | workbench_or_test_only |  |  | No executor returns NeedsApproval, and there is no route or screen to decide a gate (two-roles-human-ai-gates.md:196). |
| runs | Worker reconcile and recovery (leases, resume_due, uncertain calls) | yes |  |  | Sound. The gap is in what reaches people afterwards (see the findings). |
| fieldwork | AI respondent fieldwork, fictional roster (SYNTHETIC_AI_FICTIONAL) | operator_only | Run stage, Progress, Results | POST /studies/{id}/research/runs (fieldwork source from API settings,  | Runs only after an operator puts the exact Design Revision's material SHA-256 into the worker's AIA_AI_MATERIAL_CLASSIFICATIONS and restarts the worker. Any edit to the design makes a new digest. Readiness cannot predict |
| fieldwork | Panel-grounded AI respondents (MODELLED_AI_PANEL) | workbench_or_test_only |  |  | Every panel request is Class A by construction. The only deployed route (ADR 0010) is approved for Class C only, with retention unspecified. Only tests that approve CLASS_A with retention 0 run it (test_ai_fieldwork.py _ |
| fieldwork | Persona source choice (Kdo bude odpovídat) | partial | RespondentChoice in ExecutionSteps.tsx:777 | readiness persona_sources, start persona_source (409 persona_source_un | Offered and made the default from the API's switch alone. The API cannot see the route's classes, so with the switch on, every default run parks. |
| fieldwork | Run population choice (a client's materialized child) | partial | PopulationChoice ExecutionSteps.tsx:784 |  | Shown and accepted whatever the persona source, so under the fictional roster it is recorded and keyed but never read. Under the panel it is blocked by the Class A route. |
| fieldwork | Respondent receipt (Kdo odpovídal) | yes | RespondentsReceipt ExecutionSteps.tsx:180 |  | none material: compares the pinned source with the observed origin, names a mismatch, and says when the population was recorded but not read |
| fieldwork | Fieldwork runtime park: visibility and recovery | partial | Progress park banner + waitingDetail | GET run (waiting_reason, error_message only); cancel; retry refused 40 | Visible, with the executor's text. There is no resume action for research runs (agent jobs have one), and the advice 'start again' returns the same parked run. The specific reason code is dropped by the API, and English  |
| fieldwork | GovernedModelGateway: resolution, residency, licence, reservation, journal | yes |  |  | infrastructural; sound |
| fieldwork | Design material classification for model egress | operator_only |  |  | Exact-content approvals live only in worker env. No route or screen shows a design's digest; only prompts show theirs. There is no in-product, audited act, and the runbook omits the key. |
| fieldwork | Settings: AI runtime description | partial | ControlPanel AI section | GET /settings native runtime | FAST_EXTRACTION is listed as having no native step even though client-document proposals bind it. That activity and the panel switch are absent. The page is otherwise honest that it never verifies. |
| fieldwork | Anthropic / OpenAI / Claude Code model adapters | workbench_or_test_only |  |  | No composition imports them, and NATIVE_PROVIDERS is Bedrock only (providers.py:72). Only test_model_adapters.py uses them. |
| fieldwork | Light triage model (RESEARCH_TRIAGE) | not_built |  |  | LightModelSettings exists, but no environment key or composition constructs it (ai_runtime.py:143-205), and it is marked Proposed. |
| analysis | Deterministic aggregation (research_aggregate, aggregate step) | yes | Výsledky > Data (ExecutionSteps.tsx aggregateMeasures/readMeasure) |  | Results shows the aggregate's support_status only; its stored fidelity rating (REFUSE for absolute WTP/market size) is never shown |
| analysis | Evidence admission for native runs (native_evidence, instrument policy -1/-2, support, intervals, admit_numeric_claims) | yes |  | internal (no route of its own) | Internal surface only (by design); client-facing analysis waits for a holdout |
| analysis | Eight analysis modules: draft, gate, repair, BLOCKED, checkpoints, rounds | partial |  |  | Needs AIA_AI_ANALYSIS_ENABLED in both API and worker plus a valid AI runtime. A parked module never resumes once configured, and its copy promises it will. Three modules (hypotheses, segments, audience) never receive the |
| analysis | Reading a run's analysis (GET …/research/runs/{id}/analysis, reconstruct_run) | partial | Výsledky > Analýza; Interpretation Research readiness | GET /api/v1/studies/{id}/research/runs/{run_id}/analysis (routers/rese | All or nothing: any module whose harness, prompt, policy, method status or evidence adapter moved refuses the whole run with a 409 and an English message. No repair exists when every module had completed. |
| analysis | Analysis retry over the frozen dataset (POST …/analysis/retry, GET …/analysis/retryable) | partial | Průběh: 'Analýza potřebuje opravu' card | POST/GET …/research/runs/{run_id}/analysis/retry\|retryable (routers/r | Covers model-BLOCKED and FAILED/CANCELLED modules only. A preflight-BLOCKED module, and a run whose modules all completed under an earlier harness (including one whose report step ran after a deploy), get nothing_to_retr |
| analysis | Results reading in words (readMeasure, compareObjects, citedMeasure) | yes | apps/web/src/lib/result-reading.ts |  | The interval-ordering rule lives only in the browser, outside the methodology catalogue. The analysis prose is not held to it (the model receives no intervals). Fidelity-refused and analysis-excluded numbers read as 'Pod |
| analysis | Resuming a research run's runtime park after the operator enables the runtime | no | none (Cancel, then analysis retry, is the undocumented exit) | none for research runs | WorkflowRepository.resume_runtime_park exists, but only agent jobs expose it (application/research.py:1340-1352 @ 20b24bb, steps[0] only). Research runs have no route and resume_due never resumes a runtime park. |
| analysis | Client-facing analysis modules | not_built |  |  | Every run's steps are INTERNAL (application/research.py:706 @ 20b24bb). The client-facing preflight blocks until a holdout lifts -2's INTERNAL_ONLY. The client report uses the owner's lift instead. |
| analysis | Holdout validation: preregistration, confirmation run, scoring | workbench_or_test_only |  |  | ValidationRuns.start and HoldoutRepository.record_preregistration have no caller outside tests (no route, CLI or UI). The executors are registered in the default worker registry. |
| analysis | Recording a validation verdict and analysis reading it (7f) | not_built |  |  | prepare_module passes validation=None (application/analysis_results.py:568 @ 20b24bb); panel-grounded-respondents 7f is open |
| sociomap | Map computed automatically for every research run (each tracked set) | yes |  |  | The researcher cannot declare context objects or standalone rating items (see the role-declarations finding). |
| sociomap | Method pinned at start from the methodology in force; retry keeps the pin | yes |  |  | An in-force version that stops validating after a code change gives a generic 500 (hypothesis); the failed-pin step code has no Czech words. |
| sociomap | Which method computed the map is visible | yes | ResultsWorkspace.tsx:63 Metodika běhu; ObjectMapView.tsx:555 method +  |  | The register's approval note is shown only as a hover title on Results. |
| sociomap | Object map view on Results (top/3D, pairs, two-gate links, terraces) | yes | ObjectMapView.tsx, ObjectMapTerrain.tsx, lib/object-map-view.ts |  | The no-map state is not said; the PNG export is stamped internal even when the map is approved. |
| sociomap | Register approval status per map | partial |  | GET /api/v1/studies/{id}/research/sociomap-register (routers/research. | Results reads the register correctly, but the stored artifact status, the Progress step name, project memory, the PNG label and the Metodika note all say internal / D6 open. |
| sociomap | Maps in the internal report (DOCX/PDF) | partial |  |  | The pair table prints raw n and English status, without Kish n or the effect floor (research-integrity-report F5/chunk 7 covers part of this). |
| sociomap | Approved maps in the client report | partial |  |  | Maps are omitted with no note while the introduction promises them; the report card says the maps are in the client version. |
| sociomap | Edit, check, compare, store and activate the Sociomap methodology (Metodika) | yes | settings/MethodologyPanel, MethodologyVersions, MethodologyComparison | routers/methodology.py check/compare/versions/activation | Compare uses fictional panels only; activation shows no client-approval consequence; the reason is optional; superseded base aia-sociomap-2 is still offered (OI-102). |
| sociomap | Approve an edited Sociomap method for client use | operator_only |  |  | Requires a code change to SOCIOMAP_REGISTER (sociomap_register.py:52-69) and a release; there is no in-product register. |
| sociomap | Compare one run's map under two methods, or across runs/waves | not_built |  |  | retry and retry_analysis keep every pin; there is no re-map over a frozen dataset; align_to_reference is used only by the Metodika draft check (sociomap_check.py:243). Engine plan chunk 10 (waves) is planned. |
| sociomap | Scenarios and drag overrides on a map | not_built |  |  | domain/sociomap/view.py apply_view_overrides / view_terrain / apply_scenario exist for contract-2 artifacts only, with tests as their only caller; the UI says they are not available (cs.ts:2692). |
| sociomap | Respondent placement map (F10) and regions/segment tests (F14/F15) | not_built |  |  | Contract-3 respondents are NotComputed (models_v3.py:313). Blocked on owner/author decisions: formula-corrections chunks 3 and 4d, engine plan 8 (M8). |
| sociomap | K100 connectedness with bootstrap interval (F9) | workbench_or_test_only |  |  | AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED is off in every deployment (absent from deploy/develop compose); nothing on Results or in the report reads K100; OI-92 is open. |
| sociomap | Experimental H-Model Sociomapping and its draft DOCX | partial | SociomappingView.tsx |  | Flag-gated and internal only; its parameters come from the executor default and are not pinned at run start; SOMECS equivalence is unverified (engine plan 0c/0d). |
| sociomap | Interpretation Research over a map, object or pair | partial |  |  | The API accepts SOCIOMAP / SOCIOMAP_OBJECT / SOCIOMAP_RELATIONSHIP targets (deep_research/integration.py:216-262; routers/deep_research.py:119-124), but the web starts only ANALYSIS_MODULE research_questions (lib/api.ts: |
| sociomap | Draft check against the audit's printed checks C1-C16/P4-P14 | not_built |  |  | Blocked: the inputs are with the audit's author (methodology-tab S4d, formula-corrections 0a). |
| reports | Internal report of the run (DOCX, worker step) | yes | CompleteReport card on Výsledky | GET …/report, GET …/report/download | Only after all eight AI modules complete; a BLOCKED module leaves no document even though the deterministic chapters exist |
| reports | PDF of a stored report (report_pdf workflow) | partial | Formát PDF, Vytvořit PDF znovu | POST …/report/pdf, …/report/context/pdf, GET …/pdf/download | Develop only (converter off by default); with it off the card keeps offering 'Vytvořit PDF znovu', which always fails pdf_disabled |
| reports | Report with a chosen literature review (variant) | yes | Varianta select + Připravit zprávu s rešerší; InterpretationResearch ' | POST/GET …/report/context, …/context/download, …/context/pdf/download | Refusals reach the researcher as English internals; re-preparing shadows an approved earlier draft |
| reports | Client report (modelled runs) | operator_only | Verze 'Pro klienta' | GET …/report/client/download | Needs a MODELLED_AI_PANEL run (AIA_AI_POPULATION_PERSONAS_ENABLED off by default + an established population); DOCX only; always prints KONCEPT — NESCHVÁLENO / 'Nepředávejte ji jako finální'; approval worded as internal; |
| reports | Report approval (human sign-off) | partial | Schválit pro interní použití | POST …/report/approve | Bound to artifact id; who/when/note recorded in approval_decisions but never readable; UI sends no note; file unchanged; independence for composed reports compares against the first downloader |
| reports | Approved export (D2: the approved version exported consistently) | not_built | none | none | No code sets ReportMeta.approvals; the renderer support (layout.py:129-130, 316-326 @ 20b24bb) is unused |
| reports | Which report a run delivered / report versions | no | none | none | Variant choice is React state; project memory reads the base report only; no list of a run's report versions with their approval; downloads serve the newest only |
| reports | Experimental Sociomapping DOCX | workbench_or_test_only | SociomappingView download | GET …/sociomapping/report(/download) | Internal draft only; never approvable (by design) |
| reports | Report lineage / provenance view | partial | InternalReport panel provenance line | no lineage route | Printed: run id, evidence fingerprint, module SHAs, method record; the internal panel shows artifact id/SHA. No view of the approval or the version history; the design revision id is not printed |
| reports | Report layout (D5) | partial |  |  | Every chapter and appendix forced onto a new page (styles.py:177,180 @ 20b24bb); widow control, keep-with-next and the separate cover are already in place |
| deepresearch | Start Design Research over the current design | partial | DeepResearchPanel.tsx:73-92 @ 20b24bb | POST /studies/{id}/deep-research/runs (routers/deep_research.py) | Questionnaire stage only, inside the editor view; fixed QUICK preset, WEB channel only; no cost shown unless the spend limit asks; offered even when the worker's switch is off |
| deepresearch | Follow progress, cancel, retry a failed or cancelled run | yes | DeepResearchPanel.tsx:94-127; InterpretationResearch.tsx:104-147 | GET runs, events; POST cancel, retry | Retry only for FAILED/CANCELLED (domain/research.py:56-63) |
| deepresearch | Resume a run parked for an absent runtime, lift its budget wait, or start a new pass over the same revision | no |  |  | No resume (unlike ResearchAgentJobs.resume_runtime_park, application/research.py:1340), no Deep Research budget lift (lift accepts RESEARCH runs only, application/research.py:1149-1154), and start is idempotent per spec  |
| deepresearch | Review Design Research findings | partial | DeepResearchPanel.tsx:130-142; ExecutionSteps.tsx:410-445, 584-586 |  | Design panel shows accepted findings with a bare host score, no topic, no rejection reasons or gaps, and mixes in interpretation runs; the Run-stage trace card shows findings per research question correctly |
| deepresearch | Accept a Design Research proposal into a new Design Revision (ADR 0019 gate 1) | no |  | GET/POST …/design-proposal[/accept] (routers/deep_research.py:646, 665 | API and tests exist; no web caller (api.ts:1283-1318 has designProposal only); accepted block would also be dropped by the next working-copy submit unless the working copy is replaced |
| deepresearch | Interpretation Research over the research_questions analysis module | yes | InterpretationResearch.tsx | POST …/deep-research/runs/interpretation | QUICK/STANDARD only; reads only 20 runs (InterpretationResearch.tsx:49) |
| deepresearch | Interpretation Research over a question result, battery object, Sociomap battery/object/pair; Research Lens | no |  |  | Targets validated and tested in the API (ResearchTargetRef, _require_entity); web always sends ANALYSIS_MODULE research_questions (api.ts:1284-1290); the Research Lens sidecar (ADR 0021 decision 6) is not built |
| deepresearch | Report with a chosen literature review (DOCX and PDF of one stored draft, approve) | partial |  | POST/GET …/report/context, …/context/pdf, …/download (routers/research | One coherent path; but the chosen review is page state (ExecutionSteps.tsx:1414) and an approved variant is invisible to run labels/project memory |
| deepresearch | Coverage ledger (searched / opened / refused / set aside) and provenance | no |  | routers/deep_research.py:612, 629, 690 | GET …/coverage and …/provenance and …/snapshots/{id} have no web caller; the report prints the run id and the bundle seal |
| deepresearch | Organization approval of Deep Research settings (ADR 0022) | yes | DeepResearchSettingsPanel.tsx | /deep-research/settings[/{key}/versions\|/approval] | Works for OWNER/ADMIN; a STATUS approval (e.g. sources.tiers) is not bound to the table version it signs off |
| deepresearch | Study-scoped sandbox test grant (fictional study, ≤7 days, ≤USD 20) | operator_only |  |  | propose_test_policy/approve_test_policy have no route, command or UI (called only by tests); the grant is pinned as if organization-approved |
| deepresearch | Live-route refusal explained to the researcher | no |  |  | 409 live_settings_unapproved shown as an English sentence; details.missing and routes dropped; no link to settings |
| deepresearch | Internal channel (research over the client's approved knowledge) | no |  |  | Supported by the engine; the API defaults to WEB and the web always sends ['WEB'] (routers/deep_research.py:101; api.ts:1287, 1306) |
| knowledge | Knowledge library: add, edit as new revision, folders, labels, history, stale-edit guard | yes | KnowledgeArea, KnowledgeLibrary | /clients/{id}/knowledge*, /knowledge/proposals, /placement, /items/{id | No retire or correct (C9/K6). Accepted AI items lose their visible grounding. |
| knowledge | File intake (documents, tables, pasted text) into client sources with reading and locators | yes | IntakeSheet, SourceCard | POST/GET /clients/{id}/sources, /{source_id}, /original, /reading | Uploads happen at pick or drop time, with no list and no delete. URL capture (K2e) is not built. The reread route has no UI caller. |
| knowledge | AI knowledge proposals from a client document (K2d), paid by the client | partial |  |  | Off by default (operator flag plus a Class A route). A run parked before activation is never resumable. No cost is shown before asking. Tables are refused. |
| knowledge | Review queue (Ke schválení) with citation | partial | KnowledgeArea Pending |  | One proposal at a time, at most the 200 newest without notice. No diff or edit marker for revising proposals. No edit-before-accept. Bare 'Schválit' (C6/K2f). |
| knowledge | Approved knowledge reaching research design agents | partial |  |  | Title and summary only, up to the 200 newest, 20 KB in id order. Items beyond 200 are omitted silently. Which items were used is not shown. One DATASET, FINDING or ARTIFACT item parks every job on the licence gate. |
| knowledge | Approved knowledge reaching Deep Research (internal channel, client terms) | partial |  |  | Needs a Class A/B route (none approved today, per the docs). Unresolved-lineage kinds are refused. Competitors on Profil become client terms that refuse web queries naming them. Usage is not shown to the researcher. |
| knowledge | Client knowledge reaching fieldwork, analysis, report, Sociomap or simulation | not_built |  |  | Lifecycle K4/K5/K7. Nothing outside design agents and Deep Research reads for_study. |
| knowledge | Client datasets (Data tab) usable downstream | no |  |  | Stored and previewed only. No study, population or analysis consumer. The Data tab does not say 'V AIA zatím není' (C8, D8). |
| knowledge | Web/URL intake and Deep Research evidence import (K2e) | not_built |  |  | 'Vložit odkaz' is disabled with 'v AIA zatím není'. |
| knowledge | Project memory search (one client's past designs) | yes | MemorySearch on Projektová paměť and Výzkumy | GET /clients/{id}/memory/search | Designs, drafts and names only. Results, reports, maps and knowledge are not searched (owner M0.2). |
| knowledge | Past research read-only and design reuse with citation and labels | yes | MemoryStudy, DesignSourceNote | POST /clients/{id}/memory/reuse, GET /studies/{id}/design/source | The labels are frozen at reuse time. The approved report is reachable only via 'Otevřít' to the study itself. |
| knowledge | Reuse of approved results, reports or maps as client knowledge | not_built |  |  | Owner decision M0.2 kept it out of the MVP. The ARTIFACT kind has no creator. |
| knowledge | Client budget: see, set, lift a waiting run | partial | ProfileArea Budget, SourceProposals lift | GET/PUT /clients/{id}/budget, POST /clients/{id}/work/runs/{run}/steps | Profil card plus an inline lift. No ceiling or remaining budget is shown before an ask. Lifts and budget changes are absent from the visible history. CB5's PostgreSQL proof is open. |
| knowledge | Client dimensions as executable persona dimensions | not_built |  |  | A title-only DIMENSION is offered in Dimenze. Fieldwork never applies it (F-K2, K5). |
| knowledge | Retire, restore or delete knowledge items and sources | not_built |  |  | RETIRED has no writer. A revision keeps its kind. No source delete (C9/K6, retention open). |
| knowledge | Client profile and contacts | yes |  |  | None material for this audit. |
| population | Import a population version (bundle validated under the v17 contract) | operator_only | none; the result appears as REGISTERED on /app/intelligence | none (by design: routers/population.py docstring 'Nothing here writes' | CLI only (population_ops import --as) on the host via SSM; the stored validation record and imported_by never reach a screen |
| population | Attach companions / record dictionary / record audience catalogue | operator_only |  |  | attach is CLI only; dictionary and catalogue are recorded automatically on deploy (deploy.sh:121,135), and the catalogue job is still being fixed under audience-catalogue-cpu chunk 4 |
| population | Establish STATIC/LIVE and promote LIVE (compare-and-set) | operator_only | read-only history on /app/intelligence | none | Host shell only. The actor is self-asserted. History shows the reason and time but not the actor (GlobalPages.tsx:98-110). No in-product comparison of a candidate with LIVE before promotion |
| population | Read the registry: versions, status, history, children | yes | /app/intelligence (GlobalPages.tsx IntelligencePage) | GET /api/v1/population | no actor or validation record shown; a child is listed by its raw dimension_id with no construct or definition |
| population | Read a version's characteristics (weights, blocks, fields and permitted uses, subpanels) | yes | PopulationCharacteristics.tsx on /app/intelligence | GET /api/v1/population/versions/{id}/characteristics | for a child, the added field is shown as allowed for persona construction and audience filtering although nothing uses it for either (see finding child-dimension-read-by-nothing) |
| population | Audience filters from LIVE's catalogue, subpanels and feasibility preview | partial | AudienceStep.tsx | GET /population/audience-catalogue, POST /population/audience-preview | Needs a kept catalogue (develop: pending audience-catalogue-cpu chunk 4) and AIA_POPULATION_ASSET_ROOT on the API. Always counts current LIVE, even when the run will draw from a child's older base or a found run's supers |
| population | Materialize a client dimension into an owned child | no | none | routers/materialize.py:215 | POST /studies/{id}/population/materializations works and the worker step runs, but no web caller exists and the body is a full K5 definition with raw field names. client-knowledge-lifecycle K5 is open; population-operati |
| population | Follow a materialization run (waiting/refusal reasons) | no | none | routers/materialize.py:262,278 | GET …/materializations[/{run_id}] has no UI. A FAILED run is returned again on every re-ask from the same study, with no retry route |
| population | Select a client's child as a run's population | partial | ExecutionSteps.tsx PopulationChoice | POST …/research/runs {population_version_id} | The UI exists ('Populace běhu', ExecutionSteps.tsx:784), but there is no UI to create a child. When one is chosen, the added column reaches no respondent, and the choice starts a second paid run |
| population | Use a materialized dimension in audience filtering or persona construction | not_built |  |  | The audience factor catalogue is the unit's fixed list (audience.py:205-208) and persona columns are fixed (panel_persona.py:225-229). The M3 policy permits these uses, but no consumer exists (sociomap-formula-correction |
| population | Turn a validated derived dimension into a new LIVE revision | not_built |  |  | Excluded by owner decision M5 (children never promoted) while mvp-workflow-assurance.md:61 requires it; no validation/calibration step beyond target_met |
| population | Panel-grounded respondents drawn from the run's recorded population | partial |  |  | AIA_AI_POPULATION_PERSONAS_ENABLED is off on develop (complete-study-report B6 awaits audience-catalogue-cpu chunk 4); a run's identity ignores LIVE's version (finding panel-run-identity-ignores-live-version) |
| population | See the run's population binding at results and report time | yes | ExecutionSteps.tsx:189 populationNote; report_method.py:443-458 |  | label only (hash in version_id, not shown); for a child, the dimension, its construct and evidence are not stated |
| population | Client Data tab | partial | apps/web/src/components/aia/clients/DataArea.tsx |  | read-only list of DATASET/ARTIFACT items with no open, columns or action; the client's children not shown; tracked as client-workspace C8 |
| population | Run against the STATIC reference | not_built |  |  | STATIC is established but no run selector or consumer reads it; its only roles are to block LIVE from pointing at it and to anchor 18.6.6's subpanel counts |
| simulation | Create a simulation Study from the client workspace | partial | ClientContext.tsx:135-138 (Nová simulace), useStartStudy :78-98 | workspace.py:1050-1064 start_study | Creation works end to end (POST /clients/{id}/studies kind SIMULATION), but the result is a record nothing can act on. No caveat is shown before creating it. |
| simulation | List and count simulation studies (Simulace tab, Přehled, client directory) | yes | StudyList.tsx, ClientOverview.tsx:33-49, ClientDirectory.tsx:37-45 | workspace.py:828, 869-870, 1087, 1148 | DRAFT and ACTIVE simulations are shown as active work with Pokračovat and counted as aktivní or otevřených, although no work is possible. |
| simulation | Open a simulation study | partial | SimulationFrame.tsx:15-45 |  | A notice only: no stages, no content and no archive action. The body is empty when the kind or client does not match (SimulationFrame.tsx:33). |
| simulation | Simulation working content (context, baseline, scenario drafting) | not_built |  |  | Refused for non-research studies (not_research). Plan S1. |
| simulation | World-model generation or authoring | not_built |  |  | There is no generation behind the gateway and no authoring UI. Even S3 plans only a hand-authored fictional fixture; generation is 'Later, out of this plan' (simulation-studio.md:66, 81). |
| simulation | World-model validation (reject-not-clip, bounds, markers) | workbench_or_test_only |  |  | Pure domain code with no production caller. |
| simulation | Scenario contract and approval bound to the contract SHA-256 | workbench_or_test_only |  |  | No route stores or approves a contract, and approval is not in the approval ledger. Plan S3. |
| simulation | Population adapter (RuntimePopulation to SimulationPopulation and PanelSchema via decide(field, SIMULATION)) | not_built |  |  | The core takes a caller-built SimulationPopulation and PanelSchema (inoculation.py:139, world_model.py:65). Nothing derives them from PopulationRuntime.load_for_run (application/population.py:671) or from FieldUse.SIMULA |
| simulation | Variant run (worlds, inoculation, ensemble) | workbench_or_test_only |  |  | Exists only as domain functions. There is no workflow type (workflow_templates.py:80) and no executor (aia_executors/registry.py). Plan S4. |
| simulation | Variant comparison | workbench_or_test_only |  |  | No artifact or route. Plan S5. |
| simulation | Frozen prediction, write-once truth, scoring | workbench_or_test_only |  |  | Write-once is only a function contract: record_truth takes 'existing' from a repository that does not exist. No table and no unique constraint (engine doc §8). |
| simulation | Simulation report with review state | not_built |  |  | application/report.py and executors/report.py are research-only. Plan S6. |
| simulation | Simulation constants and stages in Settings | yes | ControlPanel.tsx:686, 780 | settings.py:418-435, 547 | Displayed as configuration in force, but nothing reads them. |
| simulation | F13 numerical parity of FS_* against 18.6.6 | not_built |  |  | Fixture uncaptured; D11 is open. OI-27. |
| simulation | Retire a mistakenly created simulation study | partial | ControlPanel.tsx:394 | PUT /studies/{id}/status (scope.py:457-478) | Possible only through Nastavení → Studie status. There is no action on the study or the list. |
| webia | Client-first navigation: Klienti → client areas → study → stages; legacy /app/projects, /app/research and /classic land somewhere honest | yes | AppShell, ClientContext, ResearchStudy, app-routes.ts | GET /workspace/clients, /clients/{id}, /studies/{id}/workspace | none for navigation; verify/next step keys exist only as unlinked placeholders |
| webia | Stage track and Inspector blockers (design lane) | partial | StageTrack.tsx, research/lane.ts, Inspector.tsx |  | design-stage rules are re-implemented in the web (4–15 sets) and diverge from the server's in-force readiness methodology |
| webia | Run stage state from runs (run/progress/results lanes) | partial | StageTrack.tsx:58, lane.ts:124-136 | GET /studies/{id}/research/runs (limit 20 default) | reads only the API's default 20 newest runs; no cursor or total |
| webia | Budget lift for a research run stopped at the study cap | yes | ExecutionSteps.tsx:1288 BudgetLift | POST …/research/runs/{id}/steps/{node}/budget | none |
| webia | Budget lift for a research agent job or Deep Research run stopped at the study cap | no | none | none | no route and no UI; ResearchRuns.get rejects non-RESEARCH workflow types (application/research.py:1149-1154); raising the budget in Settings does not resume a parked step |
| webia | Study budget setting | partial | ControlPanel.tsx:402 |  | only in global Nastavení → Studie; a new study starts at 0 and nothing on the study says so |
| webia | Materialize a client dimension (owned population child) | operator_only | none (Intelligence lists children; Run stage picks one) | POST/GET /studies/{id}/population/materializations | API complete (P4d4a) but no web caller; only raw API calls create children that the Run stage then offers |
| webia | Choose a materialized child for a run | partial | ExecutionSteps.tsx:597-609 |  | works only for children made outside the UI |
| webia | Apply a Design Research proposal into a new Design Revision (ADR 0019 gate 1 / ADR 0021) | not_built |  | POST …/deep-research/runs/{id}/design-proposal/accept | API accept exists; UI is deliberately review-only; plan deep-research-web-search chunk 24 open |
| webia | Deep Research provenance, coverage and captured snapshots | not_built |  | GET …/provenance, …/coverage, …/snapshots/{id} | routes have no caller; source links go to the live URL, not the content-addressed snapshot |
| webia | Working-content history and restore | no |  | GET /studies/{id}/workspace/revisions | history route returns metadata only and has no caller; no route reads or restores an earlier working revision |
| webia | Cancel a research run | partial |  |  | cancel_requested is never read; the UI shows Běží and an active cancel until the checkpoint |
| webia | API refusals in the researcher's words | partial |  |  | 52 of 65 literal API codes have no Czech words; code-only errors arrive empty; details and request id dropped on research screens |
| webia | Simulation study | no |  |  | creatable from a primary CTA, then inert (simulation-studio plan, status planned) |
| webia | /studies live pages (generic projects, develop_snapshot runs) | operator_only |  |  | transitional develop proof, still routed on the product hostname; writes synthetic projects into real studies |
| flags | Turn an AI activity or product switch on/off for a deployment | operator_only | none (operator) |  | SSM + write-env.sh + compose restart; no in-app control (by design). A key that Compose does not list never reaches the process (no env_file) |
| flags | See which AI activities are on and what is sent to a model (Nastavení → AI) | partial | settings/ControlPanel.tsx:578-609 | GET /api/v1/settings ai_runtime | Display of the web container's env, never verified. Omits client-source proposals (FAST_EXTRACTION is shown as unused while bound), panel personas, the answerability gate, experimental Sociomapping, K100 and PDF |
| flags | Classify design material so a model may receive it | operator_only |  |  | A per-Design-Revision SHA-256 in AIA_AI_MATERIAL_CLASSIFICATIONS (worker env); every edit needs a new entry and a worker restart; the UI shows no digest and no action |
| flags | Recover work parked because a switch, runtime or classification was missing | partial |  |  | Agent jobs have a resume (POST …/agent-jobs/{id}/resume). Research and Deep Research runs need an undocumented cancel then retry. Client-source proposals and materializations have no way out |
| flags | Answerability gate (explicit continue with limitations, recorded) | partial |  |  | Built and tested, off everywhere (AIA_RESEARCH_ANSWERABILITY_GATE=false). The owner's D1 answer (2026-10-17) asks for the on behaviour, but no activation chunk or retirement condition exists |
| flags | Respondents drawn from the population (panel personas) | partial |  |  | Built. Off on develop until the operator's call (complete-study-report B6). With it off, no run is modelled, so the client report (modelled runs only) cannot be produced |
| flags | AI knowledge proposals from a client document | partial |  |  | Built, off on develop (owner's activation, client-knowledge-lifecycle K2d6). Asking while off creates a run that is never resumed after activation |
| flags | Analysis modules and the internal report | partial |  |  | Whether a run has analysis and any report is decided by the API's switch at start. The Run stage does not say so, and a run started without it can never get a report (analysis_not_in_run) |
| flags | Report PDF beside the DOCX | yes |  |  | Off by code default and on for develop (worker image with LibreOffice). The off path says pdf_disabled in words |
| flags | K100 connectedness interval (F9 bootstrap) | not_built |  |  | Code exists and is tested, but develop Compose does not pass the switch to the worker, so it cannot be turned on. Its F9 parameters stay editable in Metodika |
| flags | Experimental Sociomapping and its internal report | operator_only |  |  | Pinned per run by the API's switch. Invisible on Settings and the Run stage |
| flags | Deep Research live routes and modes | partial |  |  | Worker switches (web search, Common Crawl, fan-out, agent-directed, lead, connectors) stay off on develop until deep-research-web-search chunk 27. Priced routes also need in-app approvals on Settings → Deep Research |
| flags | Model request events in a step's activity feed | yes |  |  | On for develop since 2026-10-13 (README:412-419). A kill switch with no retirement condition |
| governance | Gate 1: accept an AI design proposal (ResearchAgentJobs.accept) | yes | ProposalReview / AgentProposalDialog: 'Použít návrh' / 'Ponechat souča | POST /studies/{id}/research/agent-jobs/{run_id}/accept | Not refused when the client or study has self-approval off. The accepted state is not readable later: no revision provenance, nothing on the job, rejection unrecorded. |
| governance | Gate 1: accept a Design Research proposal | yes |  | POST /studies/{id}/deep-research/runs/{run_id}/design-proposal/accept | Same as the design accept: observe only, ledger unreadable. |
| governance | Gate 1: accept an AI-written Knowledge proposal | yes | KnowledgeArea 'Ke schválení' (quote, locator, source) | POST /clients/{id}/knowledge/proposals/{pid}/decision | Recorded in a different log from design accepts. Independence is enforced here but not for design accepts. The refusal is in English. |
| governance | Gate 2: spend confirmation | yes | Run stage cost card + confirm dialog (budget-line withBudget); DR star | start/retry with confirm_cost_usd; PUT /studies/{id}/spend-confirm | Only asks when a study spend limit is set (no default, as ADR 0019 leaves open). The confirmation is not visible after start. |
| governance | Gate 3: client-facing release | not_built |  |  | Plan two-roles 5b.4 is still marked blocked on a contract that now exists (client_report.py:62). The client report downloads ungated, and its approval is recorded as APPROVED_INTERNAL. |
| governance | Budget lift: research run step | yes | Progress: 'Zvýšit rozpočet a pokračovat' | POST /studies/{id}/research/runs/{run_id}/steps/{node_key}/budget | none for research runs |
| governance | Budget lift: client's own work (source proposals) | yes |  | POST /clients/{id}/work/runs/{run_id}/steps/{node_key}/budget | none found |
| governance | Budget lift: Deep Research run / AI design job | no |  |  | No route. ResearchRuns.get refuses non-RESEARCH runs (application/research.py:1152). The UI shows the wait with only cancel. |
| governance | Report approval (internal, with review, client) | partial | CompleteReport 'Schválit pro interní použití' | POST /studies/{id}/research/runs/{run_id}/report/approve | No approver or time shown. The client report's approval is labelled internal. The file is never re-rendered as approved. No note or reason is captured. |
| governance | Answerability acknowledgement (#477, ADR 0025) | partial | AnswerabilityGate on the Run stage | readiness answerability.acknowledgement_required; start/retry acknowle | Off everywhere after the owner's D1. Never shown after start (Progress/Results), only in the DOCX method chapter. |
| governance | Knowledge proposal approval with a stale base (F-K1) | yes | KnowledgeArea stale alert + 'Schválit místo revize N' |  | none found |
| governance | Self-approval (independent review) policy | partial | Settings → Přístup (levels table), client Profile toggle | GET/PUT /self-approval | Enforced inconsistently across decisions and scopes, and described as knowledge-only on the Profile. |
| governance | Deep Research settings approvals (ADR 0022) | yes | Settings → Deep Research: propose, approve/withdraw with reason, histo | POST /deep-research/settings/{key}/versions, PUT …/approval | Independence is resolved at organization level only. |
| governance | Deep Research study test policy (sandbox approval) | operator_only |  |  | Repository seam only (deep_research_settings_repository.py:437, 510). No route or UI. It overrides org settings for one study and nothing on screen shows it. |
| governance | Methodology version activation (ADR 0023) | yes | Settings → Metodika: check, compare, save, activate with reason, histo | PUT /methodology/{module_id}/activation | Reason optional. No independence check even when the organization turned independent review on. |
| governance | System prompt activation (ADR 0020) | yes | Settings → Prompty: save, test via pinned job, activate with reason, h | PUT /system-prompts/{id}/active | Independence at organization level only (ADR 0020 says organization, client or study). |
| governance | Approval ledger read / decision history | no |  |  | approval_decisions has no reader. The Settings audit tab reads access_audit only (admin only, 50 rows). |
| governance | Generic workflow gates (open_gate/decide_gate) | not_built |  |  | No executor returns NeedsApproval and no route decides a gate. Engine-only. |
| governance | Settings document (GET /settings + /config) | partial | Settings → Reference / AI |  | Omits at least 9 runtime switches, including the answerability gate and the persona source. |
| errors | Researcher sees why a research step waits or failed | partial | ProgressStep, runState, waitingDetail | GET /studies/{id}/research/runs/{run_id} | Only the generic waiting_reason, the last attempt's raw message and an ignored failure_class reach the UI. Specific park codes and the RECOVERY_REQUIRED reason are dropped (research.py:854-878 @ 20b24bb). |
| errors | Researcher recovers a run stuck in RECOVERY_REQUIRED | partial | ProgressActions | POST …/research/runs/{id}/cancel, …/retry | Only Cancel then Retry (a new paid run). No reason, no billing-uncertainty notice, no resolution of the uncertain call. |
| errors | Resolve an uncertain paid call (ledger and study spend) | no |  |  | AIUsageRepository.resolve_uncertain exists but no route, CLI or screen calls it. Spend stays at the conservative exposure. |
| errors | Operator view of stuck or parked runs across studies | not_built |  |  | No cross-study listing. runs_needing_attention is study-scoped and uncalled. Only the database. |
| errors | Error tracking of run failures and API 500s | partial |  |  | FAILED steps and 500s are reported. RECOVERY_REQUIRED (exhausted retries, lapsed paid call) and reconciler outcomes are not. |
| errors | Stale save conflict on study working content | yes | research/store.ts, SaveIndicator | PUT /studies/{id}/workspace/content | none material; non-conflict save failures show English API text |
| errors | Budget stop and lift (AWAITING_BUDGET) | yes | BudgetLift | POST …/research/runs/{id}/steps/{node_key}/budget | none found |
| errors | Resume a runtime park after the runtime is enabled | partial |  | POST /research/agent-jobs/{run_id}/resume only | Agent jobs have POST …/agent-jobs/{id}/resume. Research runs, Deep Research and client-source proposals have no resume, so the researcher must cancel and retry or repair, and the copy does not say so. |
| errors | Repair a finished run's blocked analysis modules | partial | AnalysisRepair, reportHolds | GET …/analysis/retryable, POST …/analysis/retry | Model-blocked modules work. Preflight-blocked ones are excluded silently, with copy that says they can be repeated. |
| errors | Recover a corrupt stored report or result artifact | no |  | GET …/report → 409 report_artifact_invalid with empty message | Mark persisted (OI-77), but there is no recompose route for a completed run. The report card shows loading for ever and the run still reads REPORT_READY. |
| errors | Quote a request id for a 500 | no |  |  | A 500 body has request_id null and no X-Request-ID header (reproduced); research screens never display a request id. |
| errors | Workflow approval gates (AWAITING_GATE) | not_built |  |  | No executor returns NeedsApproval and no route decides a gate; the UI only words the wait. |
| legacy | Open a Study whose content still waits for the 18.6.6 migration | partial | ResearchScreen.tsx:162-170 (AWAITING_MIGRATION / UNRECOVERABLE notices | GET /api/v1/studies/{id}/workspace/content (content_state) | The UI says plainly why the Study is read-only, but no surface gives the waiting count or a timeline, and the live migration run is not recorded |
| legacy | Migrate 18.6.6 working content into AIA (legacy_workspace) | operator_only |  |  | Code deployed since run 43 (2026-09-29); live dry run and apply on develop unrecorded (OI-58 open) |
| legacy | Old 18.6.6 entry points (/classic, /app/projects, /app/research) | yes | app/classic/page.tsx, app/app/projects/[[...rest]]/page.tsx, app/app/r |  | none; tiny retirement page and redirects |
| legacy | Differential parity against the running 18.6.6 unit (oracle) | operator_only |  |  | The CI oracle-parity job (ci.yml:379-434) cannot reach the host loopback; only 3 HTTP tests exist (test_legacy_oracle.py:465-492); api.http stays NOT_EXECUTED |
| legacy | Function-level parity against the vendored unit (EXACT Python ports, ui_app.html under Node) | workbench_or_test_only |  |  | none for its purpose; it pins the stage logic to the unit's document shape (see transitional) |
| legacy | Migration and parity ledgers (route ledger, interface screens, parity matrix) | workbench_or_test_only |  |  | The route ledger maps the unit's research run, workflow, artifact and job-feed routes to generic develop_snapshot-only routes; parity-matrix project.memory reads NOT_STARTED although it shipped; screen notes cite /classi |
| legacy | Generic project lifecycle and develop_snapshot run (/studies live pages) | partial | apps/web/src/app/studies/**, components/live/* | /api/v1/studies/{id}/projects/** (routers/projects.py, routers/runs.py | Reachable by URL only and invisible in /app. It writes unowned projects into real Studies. Its real users are the CI startup-smoke (HTTP) and the deploy smoke (application layer, no HTTP) |
| legacy | Non-Bedrock model routes (Anthropic, OpenAI, Claude Code CLI) | no |  |  | Adapters exist (model_adapters/anthropic.py, openai.py, claude_code.py: 738 lines) but no composition builds them; ai_runtime.py:62-67 imports only Bedrock and the pinned adapter |
| legacy | Historical provider fields in Settings (ai_history) | yes | ControlPanel.tsx:634,776-854 | GET /api/v1/settings (routers/settings.py:234-260) | Read-only, technical mode only, never offered; the generic PATCH still accepts the fields (OI-74) |
| legacy | Pre-ADR-0021 Deep Research runs (legacy-unversioned) | yes |  |  | none: read as legacy-unversioned, never back-filled; a retry or interpretation refuses with RunNotGoverned |
| legacy | Sociomap comparison map (aia-sociomap-1, contract 2) | yes | ExecutionSteps.tsx:1939-1946 |  | Computed on every run because read_methods requires exactly one contract-2 method; shown only as a collapsed comparison table, INTERNAL_ONLY |
| legacy | Plan status at session start (tools/progress.py) | partial |  |  | Front-matter of several in-progress plans is stale: next chunks already shipped elsewhere or obsolete since ADR 0018 |
