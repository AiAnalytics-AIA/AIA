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

Each gate names observable evidence. I-0 is planning/tooling readiness; I-1 to I-3 are incremental integration gates, not a PASS for an entire acceptance criterion. I-R and I-4 also need live evidence; I-5 needs full tier A, tier B and production release. A checkbox or an HTTP result cannot substitute for browser or live evidence. The predecessor table is [mvp-execution-contracts.md](mvp-execution-contracts.md).

| Gate | Holds when | Criteria (`MVP-ACCEPT-2`, #495) |
|---|---|---|
| **I-0 Ready to build** | the open PRs are merged; one migration head; the acceptance tree runs in CI; the surface owners are named | none yet |
| **I-1 The Lead drives a study** | Brief to Sample worked through the Lead on recorded doubles: edit operations, per-change accept, a plan card inside a wallet, two researchers on one study | AC-01, 02, 03, 04, 05 (start), 07 |
| **I-2 Results are seen** | respondent and segment maps, filters, the internal drill-down, the Lead reading results; map snapshots approvable | AC-05, 08 (QC), 09 |
| **I-3 Evidence is complete** | every key finding cites an admitted claim; a client dataset graded client-reported beside modelled results; analysis and report artifacts with the approve and export panel | AC-08, 10, 13 |
| **I-R Reach** (W1) | a Deep Research run for an OPEN client on develop reaches the routes the build can run, live (Brave, public fetch, the connectors probed live, the archive); Settings → Deep Research lists each route and connector as active or refused with the reason (`deep-research-web-search` 52), so no document has to say what is on | AC-11 (first half) |
| **I-4 Deep Research live** | a live run on the full design of an OPEN client through Brave; one-click source into knowledge | AC-11 |
| **I-5 Acceptance** | tier A blocking in CI with all fifteen criteria; tier B once on develop within USD 25; production released | AC-01 to 15 |

### Reach is not a late wave (owner, 2026-10-19)

The owner: "we need to get rid of this limitation once and for all, i never want to hear that this
limitation exists." The point of Deep Research is to look everywhere, the non-indexed web included.
Checked against `develop` @ `769917f` and traced end to end (`mvp-master-plan.md` §7), **more is built
than the owner was told and less than I first said.** Built: Wikipedia, Brave, and fetch from any public
host (HTML, text, PDF, XLSX, CSV). Built but never run live, their interfaces labelled UNVERIFIED: the ČSÚ
DataStat, open-data catalogue, Eurostat, OpenAlex, Wayback and ARES connectors, and Common Crawl's index and
archive (no AWS side in Terraform); the connectors, Wayback and Common Crawl run only when
`AIA_DEEP_RESEARCH_AGENT_DIRECTED=true`, which defaults false and no MVP document named. Not usable: the
procurement connector has no live source (`deep_research_live.py:364-366`), the focused crawler `SiteCrawl`
has no caller, and the triage readers have no caller and no key that builds the light model. **None is
switched on by default, and every one is Class C only**, so a design-derived query (Class B by rule since
2026-10-19) could use none of them. "Only Wikipedia" was a stale status table (`deep-research.md`), not the code.
The classification is what blocked it, and the owner has deferred it (below). So: one flag replaces
it, the switch is thrown, and the state is made visible:

| Step | Chunk | Wave | Owner |
|---|---|---|---|
| Sign-off: Brave on a plan that allows AI use and storing results (plan, terms URL and date, price), budgets, the light model, quotas | `deep-research-web-search` 1 | W0 | owner signs, S2 prepares |
| **Switch on:** the Class C routes, the connector list and Common Crawl on develop for fictional and public-topic runs, inside ADR 0022's guards | `deep-research-web-search` 51 **New** | W0 | S2 |
| **Open posture:** one flag per client replaces classification in the MVP (decision below) | `deep-research-web-search` 53 **New**; migration M10 | W0, W1 | S2 (column S3) |
| **Probe and name the switch:** each connector run live once, `aia_deep_research_agent_directed` named in the activation matrix, Common Crawl's AWS side in Terraform or kept out of the first activation | `deep-research-web-search` 54 **New** | W0 | S2 (infra S3) |
| **Visibility:** Settings lists every route and connector as built, approved, active or refused by class, with the reason, read from the composition, never written by hand | `deep-research-web-search` 52 **New** | W1 | S2 |
| **Contract door, after the MVP:** a Class B route (Linkup is the candidate), the design's class by rule, the derived-query content rule, all part of the classification redesign | `class-b-search-route` 0-6 | after the MVP | S2 |
| Wider reach, in order of value: documents in parts, structured capture and records, then pages that need a browser | `deep-research-web-search` 6, 33-37, 38 | W2 to W4 | S2 |

**Decided later the same day (owner, 2026-10-19): go with Brave, and classification leaves the MVP's
path.** In the owner's words: "all these classifications, honestly lets get rid of them for now and
build them later. theyre a huge blocker in general and we can better design it, once we have a fully
functioning mvp." Brave stays a Class C route (US-based, query logs up to 90 days:
`deep-research-web-search.md:497`), and the earlier plan to change the classifier first
(`aia-query-classifier-2`, a content rule, three review rounds of findings) is **deferred**, not built.

Scope, as read: Deep Research and its search routes, where classification is asked in six places (the
plan step's `classify_material`, `plan.py:163`, and five `classify_query` calls in the retrieval gate,
`web_retrieval.py:788, 882, 1177, 1275, 1365`). In the MVP they are replaced by **one declared posture
per client**, `OPEN` or `CLASSIFIED` (the default). A run pins its client's posture in its request at
enqueue, like ADR 0022's settings pin, so a run never changes posture mid-flight and a retry keeps it.
An OPEN client's design and queries are not classified and may go to any composed route (Brave, the
connectors, Common Crawl, the crawler). A CLASSIFIED client behaves exactly as today, with
`aia-query-classifier-1` untouched, which means **its web tracks stay parked: a real, confidential
client gets no web search in the MVP** until classification is redesigned, unless an organization OWNER
or ADMIN marks it OPEN, an audited act that is the organization's statement that the client's material
may be used in public search queries. Operator-declared fictional clients behave as before.

Not touched in code: EU residency of models and storage (the Bedrock EU route, EU S3), the model
gateway and `material_rules` for model calls, the evidence gates. **The model route's classes are widened
by configuration, not code:** the owner decided on 2026-10-19 that `bedrock-eu-primary` may carry
Classes A, B and C (ADR 0010 amendment), and it takes effect only when an operator confirms the Bedrock
retention and sets four SSM parameters (`deploy/develop/README.md` § AI route classes). Until then the
route is Class C only, and **every** design job and Lead turn parks with
`egress_route_not_approved_for_class` (a design is Class B by rule and approved knowledge Class A,
`research_agents.py:675-686`), as do panel fieldwork (Class A, `ai_fieldwork.py:418-432`) and a modelled
run's analysis (`harness.py:192-203`): the Dimenze "optimize with AI" button fails that way on develop
today. It is a W0 item, below. **A second finding:** the stage's error ("AI návrh čeká na povolenou trasu nebo
licenci: route … is not approved for CLASS_A_CLIENT_CONFIDENTIAL") says what is refused and not who can
fix it. It should say the route is approved only for internal material and that an operator widens it
(the runbook), with a link; Settings → AI is read-only and shows the classes (`routers/settings.py`), it
widens nothing. The chunk for that message is not yet in `research-lead-workbench` 11's text and has to
be added. ADR 0008 is a frozen invariant, so the open
posture and the deferral are recorded as the owner's amendment to it (an ADR in W0). Post-MVP, the
redesign starts from `class-b-search-route` 6's content rule, kept there as a design note with the
review findings it collected.

**What this costs, stated:** an OPEN client's queries and fetches carry no confidentiality check, and
Brave can see everything an OPEN client's design makes a researcher search for, names included.
Marking a client OPEN is the only guard. A real client left CLASSIFIED cannot use Deep Research's web
tracks in the MVP. Doc follow-up: `MVP-27` and `AC-11` say the route is "approved for Class B under an
EU processing agreement"; they become "for an OPEN client, the route is Brave, and the run's queries
are the ones the Lead's design makes".

**What this does not loosen:** grounding (a quote must be in a captured source), adversarial
verification, the evidence gate and the EU residency of models and storage. Reach changes where the
engine may look, not what it may claim. Retrieval, routes and connectors are **no longer frozen**
for this work (a docs follow-up amends CLAUDE.md §2 and ADR 0021's wording); verification and grounding
change only on a finding, as before. Deep Research moves from S3 to S2, whose W4 was empty and S3's the
heaviest.

## 2. Three sessions and the surfaces they own

A session is one chat session working one branch at a time. A surface has **one owner**; another
session that needs a change in it opens a small PR the owner reviews first (`mvp-cohesion.md` F8).

| Session | Builds | Owns these surfaces |
|---|---|---|
| **S1 Workbench and Lead** | the workbench frame and eleven artifacts, the Lead's commands, workers, plan card, the shared edit vocabulary, presence, per-change accept, the Lead's lifecycle | `domain/research_lead.py`, `domain/research_agents.py`, `domain/edit_ops.py` ◇, `apps/web/src/components/workbench/`, `lib/lead.ts`, `routers/lead.py`, `routers/settings.py`, `aia_executors/research_lead.py`, `research_agents.py` |
| **S2 Population, maps, evidence, Deep Research** | population and respondents, the Sociomap (object, respondent, segment), filters and drill-down, evidence integrity, run QC, the client-data evidence, **Deep Research reach** | `domain/fieldwork.py`, `domain/evidence/`, `domain/sociomap/`, `sociomap_register.py`, `domain/population/`, `aia_executors/ai_fieldwork.py`, `analysis.py`, `research.py` (steps), `domain/deep_research/` and `deep_research_live.py` (retrieval and routes open for reach; verification and grounding by finding only), `deep-research-web-search`, `class-b-search-route` |
| **S3 Data, delivery, infrastructure, acceptance** | client knowledge and sources, client data and the contract, reports and approvals, Terraform, deployment, the acceptance harness | `application/client_report.py`, `report_*`, `client_*`, `infra/`, `deploy/`, `.github/workflows/`, `tests/acceptance/`, `tables.py` migrations lane |

**Shared surfaces that three sessions edit, and who owns them** (`mvp-master-plan.md` §5, I16, I17, I24):

| Surface | Owner | Rule for the others |
|---|---|---|
| `domain/material_rules.py`, `domain/residency.py` | S1 | a small PR S1 reviews first |
| the classification code in `web_retrieval.py`, `application/deep_research.py`, `aia_executors/deep_research/*` | S2 | the same |
| `workflow_repository.py` (ledger writers) | S3, the lane owner | the same |
| `domain/workflow_templates.py`, `aia_executors/registry.py` | S3 reviews | each session registers its own kind |
| `apps/web/src/lib/api.ts`, `i18n/cs.ts` | S1 for refusal wording | others edit their own area only |
| `routers/settings.py` | S1 | the Reach panel is S2's, behind a worker-published record the API reads |

S1 and S2 meet at the Lead's results context and the Sociomap artifact; S2 and S3 meet at the client
dataset's evidence and the report's marks. Each meeting is a **contract** written first (below), not a
shared edit.

## 3. The waves

Each row names the plan and chunk that carries the work. **New** means the chunk is added to that
plan (or to a new plan from #497) before the wave starts.

### W0 · Ready to build (gate I-0)

| S | Work |
|---|---|
| S3 | Merge #493, #494, #495, #491, #496, #497 in that order; apply the docs follow-ups; add `prototypes/` to the docs-only path list (`ci-skip-docs-only`); `mvp-acceptance-harness` 1-4, 8-9 and 14 (budget, inputs, harness, shared doubles, parity reporting, marker, acceptance reconciliation); `infra/production` skeleton and `develop-spend-attribution` 5 compatibility contract before 1-2 (tagged profiles); migration **M3** (all ledger subject types, §4); **operator, first:** confirm the Bedrock retention evidence and set the four route parameters on develop (`deploy/develop/README.md` § AI route classes) so no AI step in any stage parks on `egress_route_not_approved_for_class`; and the stage error says who can fix it (`lead-orchestration` LO12a, static copy; below) |
| S1 | The spend-limit fix in `ResearchAgentJobs.start` and `rebuild` (`lead-orchestration` LO15; a fix, F5); the worker row (`lead-orchestration` LO9a, `research-lead-workbench` 11's first deliverable, which W1 depends on); `lead-orchestration` LO0 (money and orchestration ADR), `working-copy-edit-ops` WCE0 (full edit contract, including structural operations with text-only automatic default); ADRs written and proposed, and accepted before dependent behavior |
| S2 | `run-qc-and-checkpoint` RQC9-RQC10 (one n authority, population double); `audience-catalogue-cpu` 4; `complete-study-report` B6 (the operator flag); `evidence-integrity` 1 (findings cite all) and 5 (one authority); **reach**: `deep-research-web-search` 1, 51, 53, 54 and 55, the ADR 0008 amendment (open posture) |

**Exit I-0:** one Alembic head; named lane/surface owners; the acceptance tree and registered marker collect in CI using shared recorded doubles; existing runnable cases execute. AC-06 remains FAIL/NOT_EXECUTED until the W1 checkpoint and kill/recovery proof; AC-07 remains incomplete until the W1 working-revision path. Merely collecting a criterion is never its PASS.

### W1 · The Lead drives a study (gate I-1)

| S | Work |
|---|---|
| S1 | **New** shared edit vocabulary, `workspace_edit_ops` (M1) and `apply_edit_ops`; presence (M2) and the change feed; per-change accept (M6); `research-lead-workbench` 11 (command registry), 14-16 (view vocabulary, frame, pointing with id and revision), 17 (Questionnaire artifact, AI buttons removed), 18-19 (Brief, Design, Sample, Fieldwork); the wallet and plan card (M4, M5) behind `AIA_LEAD_PLANS_ENABLED`; `assumptions-and-open-answer-coding` AOC1 (the assumption item kind on the shared vocabulary, status values after AOC0); `research-lead-workbench` 26-27 (the Lead reachable at 1099, 768 and 390 px, the honest fallback with the switch or the kill switch off: MVPQ-11) |
| S2 | `run-qc-and-checkpoint` RQC0 first, then RQC1-RQC3, RQC4a and RQC6-RQC8 (QC contracts/node, cost/support outlook and Fieldwork events before the UI); population-built respondents as the default path and its screens; `evidence-integrity` 2-3 (run QC stored and shown); **reach**: `deep-research-web-search` 52 and 53 in code, and `lead-orchestration` LO12b (the composition record the Lead pane and Settings read, with 52); `assumptions-and-open-answer-coding` AOC0 (the assumptions contract) and AOC4 (the coding method, written for the methodology owner's approval: `MVPQ-02b`), with `evidence-integrity` 9a (a module with no supported finding stores a diagnostic; its composition, approval and export refusal 9b is W3: MVPQ-04) |
| S3 | `client-budget` CB5; `client-knowledge-lifecycle` K2e, K2f, K3, K4, K8; `clients.wallet_ceiling_usd` (in M4); **production applied**: RDS, Cognito, buckets, tagged Bedrock profiles, `deploy-production.yml` |

**Exit I-1:** W1 checks the available design workers and existing prompt pins, not all eleven workers or the eight analysis pins (full AC-03 is W3/W5). `lead-orchestration` LO10 binds approval to the card revision; LO13 records the client-level exception if accepted; LO14 provides the turn-cost/budget line. `working-copy-edit-ops` WCE10 supplies Audience/Dimensions/Sample operations and WCE12 the two-person journey. Two sessions edit one study in the acceptance run, the second edit merges or conflicts
on one item only; a plan inside a wallet starts a run and a gate it does not cover parks.

**Exit I-R:** on develop, with `aia_deep_research_agent_directed` on, a Deep Research run for an OPEN
client reaches Brave, one connector that has been probed live, and the archive, each named in the run's
record (`deep-research-web-search` 51, 54); the crawler joins when chunk 36 wires it;
Settings → Deep Research lists every route and connector as active or refused, with the reason (52);
an edited design with no operator record runs its web tracks for an OPEN client and still parks
`egress_unclassified_material` for a CLASSIFIED one, and a run keeps the posture it pinned (53).
W2 does not start until I-1 and I-R both hold.

### W2 · Results are seen (gate I-2)

| S | Work |
|---|---|
| S2 | `sociomap-formula-corrections` I0-I5, 3 (respondent map), 4d; `segment-maps-and-drilldown` 1-6; the results-context **provider** for maps; **reach**: `deep-research-web-search` 6 and 33-37 in order; `assumptions-and-open-answer-coding` AOC2 (assumption evidence) and AOC5 (coding storage and node), each after its ADR |
| S1 | The Lead's results-context consumers (LO8 contract already W1, F4); `research-lead-workbench` 20 (Results and Sociomap with filters and drill-down), 22 (Audience, Dimensions); the Lead's lifecycle (M7): signals, proposed updates, admin read |
| S3 | `client-knowledge-lifecycle` K5 (an owned child; K4 frozen context already W1); own-dimension chips; map-snapshot approval (`two-roles-human-ai-gates` 5b.4, **New** chunk); the Report artifact's Approve and Export panel |

**Contract before W2 work starts:** `ResultsContext` (admitted claims, pair statuses, module text, report
draft ids, QC, bounded and classified), owned by S1, with a provider function from each of S2 and S3.

### W3 · Evidence is complete (gate I-3)

| S | Work |
|---|---|
| S2 | `run-qc-and-checkpoint` RQC4-RQC5 (worker flag/accept path, then linked replacement after its methodology decision and ADR); `evidence-integrity` 4, the client-data evidence admission (`client-data-in-analysis` 4-5 once its policy is decided); `assumptions-and-open-answer-coding` AOC6 (coded counts as admitted claims), AOC8 (their Results and analysis consumers) |
| S3 | `client-data-in-analysis` 0-9 (4-5 with S2, 8a contract already W0, M8); `client-knowledge-lifecycle` K6 (correction/retirement); `deep-research` 4 with S2 (tool ledger, M11); `research-integrity-report` 6-8; `two-roles-human-ai-gates` 5b.4 closes with `report-delivery` RD2-RD4 in W2 (not W3); `report-delivery` RD9 and RD10 (the assumptions and open-answer coding chapters) |
| S1 | `research-lead-workbench` 21 (Analysis, Report), the three new workers (`interpret_map`, `polish_report`, `flag_straightliners`), `system-prompts-settings` 7 and 13 (the eight analysis pins; method slots read-only); `lead-orchestration` LO9b after RD6's accept contracts; `assumptions-and-open-answer-coding` AOC3 (assumption consumers) and AOC7 (the coder, only if the method permits one: a twelfth worker row) |

### W4 · Deep Research live (gate I-4)

| S | Work |
|---|---|
| S3 | the report's research-context chapter; Deep Research's sealed bundle into the report (`research-integrity-report`) |
| S1 | Deep Research cards in the conversation (`research-lead-workbench` 23); Deep Research reachable from every stage (25) is **after** the MVP |
| S2 | `deep-research-web-search` 27 (the live acceptance) and 38 (pages that need a browser); the acceptance run's findings |

### W5 · Acceptance (gate I-5)

S3 leads: every criterion wired in tier A (`mvp-acceptance-harness` 5-6, 15: the assumptions and open-answer coding journey); tier B on develop within USD
25 with the AWS-tagged reconciliation (`develop-spend-attribution` 3, `mvp-acceptance-harness` 7);
production released by the release PR after a restore test, a rollback rehearsal and the **delete path** (a client's or study's rows and S3 prefixes removed, the RDS snapshot window stated); runbooks. S1 and
S2 fix what the runs find.

## 4. The migration lane

One Alembic head at all times (`migrations/versions`, 47 files, head `20261019_57eaa96a5538 @ 085abe0`).
**The owner of the lane is S3.** A PR with a migration names its `down_revision` in the description,
is rebased on `develop` immediately before merge, and migration PRs merge one at a time.

| # | Migration | Session | Wave |
|---|---|---|---|
| M3 | `approval_decisions.subject_type` check extended: `wallet`, `lead_plan`, `plan_step`, `chat_start`, `data_contract`, `map_snapshot`, `sociomap_unlock` | S3 | W0 (first, so no later migration edits the same constraint) |
| M1 | `workspace_edit_ops` | S1 | W1 |
| M2 | `study_presence` | S1 | W1 |
| M4 | `study_wallets`, `study_wallet_raises`, `study_wallet_charges`, `clients.wallet_ceiling_usd` | S1 (ceiling column S3) | W1 |
| M5 | `lead_plans`, `lead_plan_steps` | S1 | W1 |
| M6 | `proposal_change_decisions` | S1 | W1 |
| M7 | `researcher_lead_signals`, `researcher_leads.archived_at`, `derived_from_lead_id` | S1 | W2 |
| M8 | `client_data_contracts`, `client_dataset_copies` | S3 | W3 |
| M9 | ◇ `ai_usage_events.inference_profile_arn` (only if `develop-spend-attribution` 5a finds the model fields do not carry it) | S3 | W0, after M3 and before profiles 1-2 are configured |
| M10 | `clients.data_posture` (`CLASSIFIED` default, `OPEN`), audited by who and when | S3 | W1 |
| M11 | Tool-usage ledger storage, only the schema `deep-research#4` actually needs; no duplicate charge | S2 producer, S3 migration review | W3 before final AC-15 |
| M12 | Deletion FK rules, only after `study-data-lifecycle#SDL0` settles the ledger/audit disposition | S3 | before W5 |

Each migration lands with its repository, its tests (round-trip, isolation predicate, concurrent
access: `ARCHITECTURE.md` §7) and its `layer_check` rule in the same PR.

## 5. Contracts written before the work that needs them

| Contract | Written by | Needed by | Content |
|---|---|---|---|
| Edit vocabulary (`domain/edit_ops.py` ◇) | S1, W0 | S1, S2 (QC, locks), S3 (client data) | the closed text and structural operations, validation and lock rule; text-only automatic acceptance is the default, not a limit on manual edits |
| `LeadWorkerSpec` row | S1, W0 | S1, S2 (straight-liner), S3 (report writer) | the worker row of `mvp-cohesion.md` F5 |
| `ResultsContext` | S1, before W2 | S2, S3 | what the Lead may read of results, classified |
| Plan authority capability | S1 with S3's ledger, before W1 plan code | S1 | issued by `ScopeResolver`, no `APPROVE_GATE` |
| Origin `CLIENT_REPORTED` and the evidence policy | S2 | S3 | `domain/fieldwork.py`, `domain/evidence/`, the pending policy decision |
| Acceptance fixtures and the scripted provider | S3, W0 | all | one provider double, one set of fictional inputs |

## 6. ADRs this plan needs (each Proposed, each a docs PR)

| ADR | Decides | Before |
|---|---|---|
| Orchestration scope, the wallet and the plan card | the plan authority, what a plan may start, what parks, the ledger rows; the typed `start_run` command for a by-request start and its security condition; supersedes MVP-13 | W1 plan code |
| The working copy's operation log, merge and per-change accept | the vocabulary, the conflict rule, undo, presence, `proposal_change_decisions` | W1 |
| The Lead over time and its files | proposed updates, signals, admin read, handover, privacy of turns; amends ADR 0026 decision 8 | W2 M7 |
| Production environment | a separate environment on the one-host pattern with RDS, in the same AWS account with the mitigations of architecture §6.2; supersedes the "undecided" in ADR 0009 | W1 infra apply |
| Open posture, classification deferred (amends ADR 0008) | one flag per client in place of classification for Deep Research in the MVP; what CLASSIFIED means for web tracks; the post-MVP redesign note | W0 |
| Assumption evidence; open-answer coding; semantic report edits; respondent replacement (ADR 0026 decision 4 requires each) | the deterministic admission rule for each, before a command exists | before `report-delivery` RD6 and `run-qc-and-checkpoint` RQC5 |
| Client data's evidence policy (amends ADR 0027) | the policy source for client columns | W3 |

## 7. Order inside the critical path

The longest chain, which sets the date: **edit vocabulary → operations log and merge → per-change accept
and presence → the Questionnaire artifact → plan card → the Lead's results context → Results and
Sociomap artifacts → Analysis and Report artifacts → tier A on all criteria → tier B → release**. Its
owner is S1, which is why S1 carries the fewest side tasks. The chains that run beside it and can slip
without moving the date, until W5: client data (S3), the **live acceptance** of Deep Research
(`deep-research-web-search` 27, after the evaluations 25, 26 and 39; **Deep Research reach is not one of
them: gate I-R blocks W2**), segment maps and
clustering (S2, waits on the method owner).

## 8. What can stop the plan

| Risk | Effect | Mitigation |
|---|---|---|
| The method owner's answers (clustering, register entries) arrive late | no segment map in client output; AC-09 partial | segment maps ship internal-only first (the register defaults to `INTERNAL_ONLY`); a dated ask now |
| A real, confidential client is CLASSIFIED and gets no web search in the MVP | AC-11 runs for a fictional or an OPEN client only | the owner marks the clients that may use search OPEN; real-client search returns with the classification redesign after the MVP |
| The plan authority takes longer than planned | no autopilot-lite; every paid job needs a card (MVP-13 returns by default) | the wallet without plans is a smaller first step; cards stay as the fallback |
| Migrations collide | blocked merges | one lane, one owner, rebase before merge, M3 first |
| Production shares develop's AWS account | an account-level mistake or the shared Bedrock quota reaches production | tag-conditioned IAM with a permission boundary, per-environment state and KMS (architecture §6.2); tier B outside working hours; revisit at the first incident |
| RDS or Cognito setup for production slips | no production at the date, and **no release**: gate I-5 reads "production released" and a passing tier B on develop does not release | production is a blocker, not a follow-up: restore, rollback, delete path and the activation profile are evidenced first (`production-environment` PE9, `mvp-acceptance-harness` 12); the date moves, the gate does not |
| The first acceptance run exceeds USD 25 | the budget table was wrong | the allocation is checked before the recorded run (`mvp-acceptance-harness` 1) |
| One session is the whole critical path | a stall in S1 stalls the date | S2 and S3 take defects and review capacity once W3 starts |

## 9. What this plan does not do

The wave table is amended by the exact predecessors in `mvp-execution-contracts.md`; the master and child plans carry the same wave changes. Prototype choices and methodology decisions are tracked in `mvp-owner-decisions.md`. A blocked decision stops its dependent behavior, not unrelated contract, fixture or infrastructure preparation.

It does not name the sessions' people or dates, does not decide the open items in
`mvp-target-architecture.md` §9, does not change a plan file, and does not start any chunk. The
follow-ups are in `mvp-cohesion.md` §6.

