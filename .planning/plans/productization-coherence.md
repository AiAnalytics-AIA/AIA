---
status: in-progress
chunks:
  - "[x] PC1. A closed study reads as closed: the frame says delivered / archived / cancelled, editors and work actions are read-only with the reason, downloads and approval stay, and every refusal is study_closed in Czech"
  - "[ ] PC2. Results read the run's own verdicts: an answer to a research question the run recorded as a gap is marked as in the report, and a number the analysis refuses says so beside it"
  - "[ ] PC3. A run's analysis stays repairable after a harness change: a module completed under an earlier harness is asked again over the frozen data, never a paid fieldwork re-run"
  - "[ ] PC4. A run parked for the AI runtime can be resumed by a person once the runtime is on; no copy promises it continues by itself"
  - "[ ] PC5. The stage track follows the run, and says when the design changed after the run it shows"
  - "[ ] PC6. Proposal review names what acceptance replaces; rewording a research question says which links it would orphan"
  - "[ ] PC7. Researcher copy agrees with the Sociomap register and ADR 0018: no D6 or 18.6.6 remedies, no stale report sentence"
  - "[ ] PC8. The browser journeys pass on today's interface, and a label they wait for cannot drift unnoticed"
  - "[ ] PC9. Report body and appendices flow: no page break before every chapter (owner D5, 2026-10-17)"
  - "[ ] PC10. Product-level acceptance scenarios over the real start, worker and report"
  - "[ ] PC11. Owner decisions recorded with a recommendation each; no code"
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
