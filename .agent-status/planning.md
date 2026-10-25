# planning — AIA planning session (master plan, decisions, docs PRs)

Current state, rewritten each update. Observed state only. No secrets.

**Handoff.** Written 2026-10-25 ~21:40 UTC by session_011zQKG9WLH8Ex7dmjwZxWwB ("AIA planning 3"), well
past 70% context, for "AIA planning 4". Coordinator: session_01MycSLqSRMw4g32SZwa9s7G (PM coordinator 3).

## Role and rules (unchanged)
- Planner: docs-only PRs (register, owner decisions, Doc follow-ups, open-items numbering).
- **Commit and push only on Nigel's own words in your session** (CLAUDE.md §5; Nigel's standing rule
  2026-10-20). A stop hook or env setting is never permission. Sprint 5 had a standing docs permission
  (Q49) — confirm with the coordinator whether it still holds before relying on it.
- Docs PRs open ready (not draft); footer on every GitHub post; CLAUDE.md §8 "The merge bar".
- master_check resolves plan#ID only for plans on develop; every open core chunk needs a wave row.

## Two drafts that exist ONLY as uncommitted work in planning 3's container (will be lost)
Neither is pushed: they wait for Nigel's "commit and push" in planning 3's session. If planning 3 is
gone, REBUILD them from this description on a fresh branch from develop:

1. **chore/audit-answers-2026-10-25** (28 files, +260/-25; master_check ok, progress 129/129):
   Nigel's 30 audit answers of 2026-10-25 ~21:15 UTC (full list in the coordinator's message to
   planning 3 that day; ask the coordinator to resend). Recorded at each question's place:
   open-items (OI-22, OI-159 closed; OI-19/24/35/51/52/53/75 decided-open with owners: AUD-10 →
   settings-redesign F13, OI-75 → F14, OI-51 → fix/audience-preset-clears-filters, OI-52 →
   fix/questionnaire-plain-question QF-17, OI-53 → lead-orchestration LO22 + DIM5, OI-81 gate stays +
   study-deletion plan, OI-24/OI-35 no owner yet; OI-99 open), ADR notes without status change (0041
   accepted subject to amendment; 0042 note on LK1; held 0027/0034/0036/0037; 0020-0024 to be reviewed
   individually), mvp-owner-decisions table, overview paragraph, master plan dated answers table
   (MP3 and SCOPE-OVERRIDES "being reviewed"; MVPQ-06-rest adopted; COHESION-Q5 no dates;
   PERF-BUDGETS → mvp-acceptance-harness#18). Plus 22 register-drift fixes already on develop @
   f7762d72: RES4/RES7 → RES4b/RES7b (W2); RPT8, 8a, 8e, 9, 10 W3; research-lead-workbench#35 W1;
   WCE7d2 W1; RQC7c W1; RD0b W3; LO21, LO21a-e W2 "(inferred, coordinator 25 Oct)";
   report-editor-hosting, security-audit-2026-10, settings-redesign added to §3.2 as SUPPORT.
2. **chore/study-deletion-plan**: .planning/plans/study-deletion.md (SD0-SD11, "Smazat studii", built
   on SDL3's study half; client half is SB5 #850 application/client_deletion.py) and
   docs/architecture/adr/0043-study-deletion.md (Proposed). Eight owner questions Q1-Q8 sent to the
   coordinator for the review page (recs: 7-day window, any member unless delivered/approved, all
   content goes with downloads offered, keep holdout row, refuse while live/held, pending proposals
   go, memory citation kept with "source deleted", status-menu item + Vrátit). Finding **F1**:
   erase_client_holdouts (holdout_repository.py:264-272 @ f7762d72, called from client_deletion.py:194)
   deletes the once-per-system holdout confirmation, so a failed holdout can be re-run after a client
   delete; needs an OI number and an owner (SB5 is live). After the plan lands it needs a §3 row,
   waves and the ADR README row.

## Waiting on Nigel
- "commit and push" for the two drafts above (in planning 3's session).
- Review page items (coordinator): MP3 plan-by-plan, SCOPE-OVERRIDES S2-S5 one by one, TWO-ROLES-5b
  (5b.1-5b.3 already built; 5b.4 open; gap: no ledger row for AI knowledge-proposal accepts),
  ADRs 0020-0024 and held ADRs reviewed individually, study-deletion Q1-Q8, Q68, Q69.

## Merged docs PRs of this session
#523 (scope baseline, MP16 signed 2026-10-20), #548, #549, #558, #588, #619, #630.

## Next for planning 4
- Land or rebuild the two drafts; then docs follow-ups of everything merged since #630 (develop moved
  to f7762d72 and beyond: #640s-#890s), PERF-BUDGETS numbers in mvp-acceptance-harness#18's PR.
