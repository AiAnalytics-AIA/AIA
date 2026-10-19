---
status: planned
chunks:
  - "[ ] RQC0. A per-respondent checkpoint (OI-64): each answered respondent is stored under the lease, a retry resumes, a whole-run retry reuses the stored respondents"
  - "[ ] RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker"
  - "[ ] RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity"
  - "[ ] RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)"
  - "[ ] RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination"
  - "[ ] RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers"
  - "[ ] RQC6. Quotas before a run and a support forecast for the panel path"
  - "[ ] RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code"
  - "[ ] RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks"
  - "[ ] RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead"
  - "[ ] RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05"
---
# Run QC and a fieldwork checkpoint

Fieldwork that does not repay on retry, and the run QC that the Fieldwork and Results artifacts show. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-2-sample-execution.md`; OI-64 was owned only by `research-agent-workflows` I4.

**Owner: S2.** Takes the gap rows G26, G27, G29 and interfaces I6, I7 of `mvp-master-plan.md` §6.1 and serves AC-05, AC-06, AC-08 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Respondents are population-built by default; invented respondents only for tests (Q17).
- Straight-liners: no pause after fieldwork; a warning, then the worker proposes keep or flag; replace is a new linked run (F18, Q22).
- Fieldwork that is killed loses no work (AC-06); this is an engineering prerequisite, not a product choice (the owner, 2026-10-19).

## Chunks

**RQC0. A per-respondent checkpoint (OI-64): each answered respondent is stored under the lease, a retry resumes, a whole-run retry reuses the stored respondents**  
Each attempt starts at the first respondent and stores the dataset only at the end (`ai_fieldwork.py:283-326`), `max_attempts=3`, a clean shutdown is a RETRY (`workflow.py:660-686`) and a whole-run retry repays fieldwork (`research.py:834-895`). Shape: the `client_work_journal` pattern. Test: kill the worker mid-fieldwork; the retry spends nothing for respondents already answered. **First S2 item in W1, before any step that runs after fieldwork.**

**RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker**  
There are three definitions today (`sociomap/engine.py:84-109`, the unit QC `qc.py:200-207`, the workbench D17). Interfaces I6.

**RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity**  
`evidence-integrity` 2 and 3 produce the artifact and its display; this chunk puts it in the graph.

**RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)**  
`material_rules.py:59-70` has none. Interfaces I16.

**RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination**  
Per F18 nothing pauses; a proposal waits. The accept destination is a field of the run's QC record.

**RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers**  
Per F18 replacement is a new linked run. The weighting and support meaning of a replacement is a method question; the chunk builds the mechanism the owner decided and labels its limits.

**RQC6. Quotas before a run and a support forecast for the panel path**  
The preview drops the composition and readiness does not call the previewer for the panel; `support_forecast` is unknown for a panel run today.

**RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code**  
Written first by S2; consumed by the Fieldwork artifact (`research-lead-workbench` 19). Interfaces I7.

**RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks**  
The panel default needs the route widened and the API reads no egress key. Shares the composition record of `lead-orchestration#LO12`.

**RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead**  
Four ranges today: web 50-5000, Lead 30-40,000, readiness 20-10,000, the sampler.

**RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05**  
Fictional rows cannot meet the v17 contract, so the existing panel tests inject a loader. Written with the acceptance harness (`mvp-acceptance-harness` 4).

## Open: owner clarifications

- The weighting and support meaning of a replaced respondent (a method question; RQC5 builds the mechanism and labels the limit).
