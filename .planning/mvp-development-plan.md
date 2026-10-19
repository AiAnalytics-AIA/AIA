# MVP development plan (Proposed, 2026-10-19)

**What this is.** The build order for the MVP: who builds what, in which wave, on which migration,
and what must be true before the next wave starts. It sits between the roadmap
(`overview.md` § MVP roadmap, #493), the cohesion findings and decisions (`mvp-cohesion.md`, #496),
the target design (`mvp-target-architecture.md`) and the plan files (each feature's chunks and
status). It is **not a backlog**: a chunk's status stays in its own plan's front-matter, and where
this file disagrees with a plan, the plan wins and this file is stale (CLAUDE.md §4). Written from
`origin/develop` @ `085abe0`.

**Decided and not repeated.** Target: end of Q1 2027 (MVP-11). Two to three sessions build in
parallel. Production is a separate environment on the one-host pattern with RDS; develop is staging.
No dates are set here: the waves are ordered by dependency, and a wave ends when its gate holds.

---

## 1. The gates

Five gates, each an observable test. A wave is done when its gate passes in CI over HTTP (tier A,
`mvp-acceptance-harness`), not when its chunks are ticked.

| Gate | Holds when | Criteria (`MVP-ACCEPT-2`, #495) |
|---|---|---|
| **I-0 Ready to build** | the open PRs are merged; one migration head; the acceptance tree runs in CI; the surface owners are named | none yet |
| **I-1 The Lead drives a study** | Brief to Sample worked through the Lead on recorded doubles: edit operations, per-change accept, a plan card inside an envelope, two researchers on one study | AC-01, 02, 03, 04, 05 (start), 07 |
| **I-2 Results are seen** | respondent and segment maps, filters, the internal drill-down, the Lead reading results; map snapshots approvable | AC-05, 08 (QC), 09 |
| **I-3 Evidence is complete** | every key finding cites an admitted claim; a client dataset graded client-reported beside modelled results; analysis and report artifacts with the approve and export panel | AC-08, 10, 13 |
| **I-4 Deep Research live** | a live run on the full design through the Class B provider; derived-query class decided; one-click source into knowledge | AC-11 |
| **I-5 Acceptance** | tier A blocking in CI with all fifteen criteria; tier B once on develop within USD 25; production released | AC-01 to 15 |

## 2. Three sessions and the surfaces they own

A session is one chat session working one branch at a time. A surface has **one owner**; another
session that needs a change in it opens a small PR the owner reviews first (`mvp-cohesion.md` F8).

| Session | Builds | Owns these surfaces |
|---|---|---|
| **S1 Workbench and Lead** | the workbench frame and eleven artifacts, the Lead's commands, workers, plan card, the shared edit vocabulary, presence, per-change accept, the Lead's lifecycle | `domain/research_lead.py`, `domain/research_agents.py`, `domain/edit_ops.py` ◇, `apps/web/src/components/workbench/`, `lib/lead.ts`, `routers/lead.py`, `routers/settings.py`, `aia_executors/research_lead.py`, `research_agents.py` |
| **S2 Population, maps, evidence** | population and respondents, the Sociomap (object, respondent, segment), filters and drill-down, evidence integrity, run QC, the client-data evidence | `domain/fieldwork.py`, `domain/evidence/`, `domain/sociomap/`, `sociomap_register.py`, `domain/population/`, `aia_executors/ai_fieldwork.py`, `analysis.py`, `research.py` (steps) |
| **S3 Data, delivery, infrastructure, acceptance** | client knowledge and sources, client data and the contract, reports and approvals, Deep Research and the Class B route, Terraform, deployment, the acceptance harness | `application/client_report.py`, `report_*`, `client_*`, `infra/`, `deploy/`, `.github/workflows/`, `tests/acceptance/`, `domain/deep_research/` (defect only: the engine is frozen), `tables.py` migrations lane |

S1 and S2 meet at the Lead's results context and the Sociomap artifact; S2 and S3 meet at the client
dataset's evidence and the report's marks. Each meeting is a **contract** written first (below), not a
shared edit.

## 3. The waves

Each row names the plan and chunk that carries the work. **New** means the chunk is added to that
plan (or to a new plan from #497) before the wave starts.

### W0 · Ready to build (gate I-0)

| S | Work |
|---|---|
| S3 | Merge #493, #494, #495, #491, #496, #497 in that order; apply the docs follow-ups; add `prototypes/` to the docs-only path list (`ci-skip-docs-only`); `mvp-acceptance-harness` 1-3 (budget table, inputs, harness with its CI step); `infra/production` skeleton and `develop-spend-attribution` 1-2 (tagged profiles); migration **M3** (all ledger subject types, §4) |
| S1 | The spend-limit fix in `ResearchAgentJobs.start` (a fix, F5); the worker row (`research-lead-workbench` 11, first deliverable); ADRs for the edit vocabulary and the orchestration scope written and proposed |
| S2 | `audience-catalogue-cpu` 4; `complete-study-report` B6 (the operator flag); `evidence-integrity` 1 (findings cite all) and 5 (one authority) |

**Exit I-0:** `alembic heads` single; the acceptance tree collects and runs AC-01, 06, 07, 12, 14.

### W1 · The Lead drives a study (gate I-1)

| S | Work |
|---|---|
| S1 | **New** shared edit vocabulary, `workspace_edit_ops` (M1) and `apply_edit_ops`; presence (M2) and the change feed; per-change accept (M6); `research-lead-workbench` 11 (command registry), 14-16 (view vocabulary, frame, pointing with id and revision), 17 (Questionnaire artifact, AI buttons removed), 18-19 (Brief, Design, Sample, Fieldwork); the envelope and plan card (M4, M5) behind `AIA_LEAD_PLANS_ENABLED` |
| S2 | Population-built respondents as the default path and its screens; `evidence-integrity` 2-3 (run QC stored and shown) |
| S3 | `client-budget` CB5; `client-knowledge-lifecycle` K2e, K2f, K3; `clients.envelope_ceiling_usd` (in M4); `class-b-search-route` 0-2 (provider, route, sign-off); **production applied**: RDS, Cognito, buckets, tagged Bedrock profiles, `deploy-production.yml` |

**Exit I-1:** two sessions edit one study in the acceptance run, the second edit merges or conflicts
on one item only; a plan inside an envelope starts a run and a gate it does not cover parks.

### W2 · Results are seen (gate I-2)

| S | Work |
|---|---|
| S2 | `sociomap-formula-corrections` I0-I5, 3 (respondent map), 4d; `segment-maps-and-drilldown` 1-6; the results-context **provider** for maps |
| S1 | **New** the Lead's results context (contract first, F4); `research-lead-workbench` 20 (Results and Sociomap with filters and drill-down), 22 (Audience, Dimensions); the Lead's lifecycle (M7): signals, proposed updates, admin read |
| S3 | `client-knowledge-lifecycle` K4, K5 (an owned child); own-dimension chips; map-snapshot approval (`two-roles-human-ai-gates` 5b.4, **New** chunk); the Report artifact's Approve and Export panel |

**Contract before W2 work starts:** `ResultsContext` (admitted claims, pair statuses, module text, report
draft ids, QC, bounded and classified), owned by S1, with a provider function from each of S2 and S3.

### W3 · Evidence is complete (gate I-3)

| S | Work |
|---|---|
| S2 | `evidence-integrity` 4 (the straight-liner check, after the replace decision), the client-data evidence admission (`client-data-in-analysis` 4-5 once its policy is decided) |
| S3 | `client-data-in-analysis` 0-3, 6-7 (M8); `research-integrity-report` 6-8; `two-roles-human-ai-gates` 5b.4 |
| S1 | `research-lead-workbench` 21 (Analysis, Report), the three new workers (`interpret_map`, `polish_report`, `flag_straightliners`), `system-prompts-settings` 7 (every worker's prompt editable) |

### W4 · Deep Research live (gate I-4)

| S | Work |
|---|---|
| S3 | `class-b-search-route` 3-6 (design class by rule, journey test, activation, derived-query class once amended); `deep-research-web-search` 1, 27, 37; the report's research-context chapter |
| S1 | Deep Research cards in the conversation (`research-lead-workbench` 23); Deep Research reachable from every stage (25) is **after** the MVP |
| S2 | none planned: capacity for defects and the acceptance run's findings |

### W5 · Acceptance (gate I-5)

S3 leads: every criterion wired in tier A (`mvp-acceptance-harness` 5-6); tier B on develop within USD
25 with the AWS-tagged reconciliation (`develop-spend-attribution` 3, `mvp-acceptance-harness` 7);
production released by the release PR after a restore test, a rollback rehearsal and the **delete path** (a client's or study's rows and S3 prefixes removed, the RDS snapshot window stated); runbooks. S1 and
S2 fix what the runs find.

## 4. The migration lane

One Alembic head at all times (`migrations/versions`, 47 files, head `20261019_57eaa96a5538 @ 085abe0`).
**The owner of the lane is S3.** A PR with a migration names its `down_revision` in the description,
is rebased on `develop` immediately before merge, and migration PRs merge one at a time.

| # | Migration | Session | Wave |
|---|---|---|---|
| M3 | `approval_decisions.subject_type` check extended: `envelope`, `lead_plan`, `plan_step`, `chat_start`, `data_contract`, `map_snapshot`, `sociomap_unlock` | S3 | W0 (first, so no later migration edits the same constraint) |
| M1 | `workspace_edit_ops` | S1 | W1 |
| M2 | `study_presence` | S1 | W1 |
| M4 | `study_envelopes`, `study_envelope_raises`, `study_envelope_charges`, `clients.envelope_ceiling_usd` | S1 (ceiling column S3) | W1 |
| M5 | `lead_plans`, `lead_plan_steps` | S1 | W1 |
| M6 | `proposal_change_decisions` | S1 | W1 |
| M7 | `researcher_lead_signals`, `researcher_leads.archived_at`, `derived_from_lead_id` | S1 | W2 |
| M8 | `client_data_contracts`, `client_dataset_copies` | S3 | W3 |
| M9 | ◇ `ai_usage_events.inference_profile_arn` (only if the model fields do not carry it) | S3 | W1 |

Each migration lands with its repository, its tests (round-trip, isolation predicate, concurrent
access: `ARCHITECTURE.md` §7) and its `layer_check` rule in the same PR.

## 5. Contracts written before the work that needs them

| Contract | Written by | Needed by | Content |
|---|---|---|---|
| Edit vocabulary (`domain/edit_ops.py` ◇) | S1, W0 | S1, S2 (QC, locks), S3 (client data) | the closed operations, their validation, the lock rule, text-only |
| `LeadWorkerSpec` row | S1, W0 | S1, S2 (straight-liner), S3 (report writer) | the worker row of `mvp-cohesion.md` F5 |
| `ResultsContext` | S1, before W2 | S2, S3 | what the Lead may read of results, classified |
| Plan authority capability | S1 with S3's ledger, before W1 plan code | S1 | issued by `ScopeResolver`, no `APPROVE_GATE` |
| Origin `CLIENT_REPORTED` and the evidence policy | S2 | S3 | `domain/fieldwork.py`, `domain/evidence/`, the pending policy decision |
| Acceptance fixtures and the scripted provider | S3, W0 | all | one provider double, one set of fictional inputs |

## 6. ADRs this plan needs (each Proposed, each a docs PR)

| ADR | Decides | Before |
|---|---|---|
| Orchestration scope, the envelope and the plan card | the plan authority, what a plan may start, what parks, the ledger rows; the typed `start_run` command for a by-request start and its security condition; supersedes MVP-13 | W1 plan code |
| The working copy's operation log, merge and per-change accept | the vocabulary, the conflict rule, undo, presence, `proposal_change_decisions` | W1 |
| The Lead over time and its files | proposed updates, signals, admin read, handover, privacy of turns; amends ADR 0026 decision 8 | W2 M7 |
| Production environment | a separate environment on the one-host pattern with RDS, in the same AWS account with the mitigations of architecture §6.2; supersedes the "undecided" in ADR 0009 | W1 infra apply |
| Derived-query class (amends ADR 0017 and 0008) | provenance-based lowering; the data owner's confirmation | W4 |
| Client data's evidence policy (amends ADR 0027) | the policy source for client columns | W3 |

## 7. Order inside the critical path

The longest chain, which sets the date: **edit vocabulary → operations log and merge → per-change accept
and presence → the Questionnaire artifact → plan card → the Lead's results context → Results and
Sociomap artifacts → Analysis and Report artifacts → tier A on all criteria → tier B → release**. Its
owner is S1, which is why S1 carries the fewest side tasks. The chains that run beside it and can slip
without moving the date, until W5: client data (S3), Deep Research live (S3), segment maps and
clustering (S2, waits on the method owner).

## 8. What can stop the plan

| Risk | Effect | Mitigation |
|---|---|---|
| The method owner's answers (clustering, register entries) arrive late | no segment map in client output; AC-09 partial | segment maps ship internal-only first (the register defaults to `INTERNAL_ONLY`); a dated ask now |
| The Class B provider is not contracted | AC-11 cannot pass live | a recorded tier A pass proves the route; tier B waits on the contract; owner names a date |
| The plan authority takes longer than planned | no autopilot-lite; every paid job needs a card (MVP-13 returns by default) | the envelope without plans is a smaller first step; cards stay as the fallback |
| Migrations collide | blocked merges | one lane, one owner, rebase before merge, M3 first |
| Production shares develop's AWS account | an account-level mistake or the shared Bedrock quota reaches production | tag-conditioned IAM with a permission boundary, per-environment state and KMS (architecture §6.2); tier B outside working hours; revisit at the first incident |
| RDS or Cognito setup for production slips | no production at the date | develop carries tier B; production release can follow the acceptance without moving the gate |
| The first acceptance run exceeds USD 25 | the budget table was wrong | the allocation is checked before the recorded run (`mvp-acceptance-harness` 1) |
| One session is the whole critical path | a stall in S1 stalls the date | S2 and S3 take defects and review capacity once W3 starts |

## 9. What this plan does not do

It does not name the sessions' people or dates, does not decide the open items in
`mvp-target-architecture.md` §9, does not change a plan file, and does not start any chunk. The
follow-ups are in `mvp-cohesion.md` §6.
