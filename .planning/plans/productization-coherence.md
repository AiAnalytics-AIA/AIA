---
status: in-progress
chunks:
  - "[x] PC1. A closed study reads as closed: the frame says delivered / archived / cancelled, editors and work actions are read-only with the reason, downloads and approval stay, and every refusal is study_closed in Czech"
  - "[ ] PC2. Results read the run's own verdicts: an answer to a research question the run recorded as a gap is marked as in the report, and a number the analysis refuses says so beside it"
  - "[ ] PC3. A run's analysis stays repairable after a harness change: a module completed under an earlier harness is asked again over the frozen data, never a paid fieldwork re-run"
  - "[ ] PC4. A run parked for the AI runtime can be resumed by a person once the runtime is on; no copy promises it continues by itself"
  - "[ ] PC5. The stage track follows the run (done), and says when the design changed after the run it shows"
  - "[ ] PC6. Proposal review names what acceptance replaces; rewording a research question says which links it would orphan"
  - "[ ] PC7. Researcher copy agrees with the Sociomap register and ADR 0018: no D6 or 18.6.6 remedies, no stale report sentence"
  - "[x] PC8. The browser journeys pass on today's interface, a label they wait for cannot drift unnoticed, and the coherence journey and report render are committed tools anyone can rerun"
  - "[ ] PC9. Report body and appendices flow: no page break before every chapter (owner D5, 2026-10-17)"
  - "[x] PC10. Dimenze shows and saves only the dimensions a person chose: a new study chose none (owner, 2026-10-18; OI-54)"
  - "[ ] PC11. Product-level acceptance scenarios over the real start, worker and report"
  - "[ ] PC12. Owner decisions recorded with a recommendation each; no code"
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
