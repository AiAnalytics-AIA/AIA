---
status: in-progress
chunks:
  - "[x] 0. This plan, first draft: the goal, the document map, the plan register, the activation matrix, the execution protocol"
  - "[ ] 1. Fold the five cohesion traces: the gap register (§6) and the interface register (§5), anchors spot-checked"
  - "[ ] 2. Add each gap's chunk to its plan (the plan's owner reviews; a gap with no plan gets one)"
  - "[ ] 3. Disposition edits: close or re-scope the plans §3 marks 'close' or 'fold' (each plan's owner confirms)"
  - "[ ] 4. Contracts written before the work that needs them (mvp-development-plan.md §5): edit vocabulary, LeadWorkerSpec, ResultsContext, plan authority, CLIENT_REPORTED, acceptance fixtures"
  - "[ ] 5. The ADRs (mvp-development-plan.md §6) and the ADR 0008 amendment for the open posture"
  - "[ ] 6. The activation profile: deploy/develop declares the MVP switches and the smoke reports each READY or NOT_READY without a paid call"
  - "[ ] 7. The operator runbook run once on develop: AI route classes, Brave sign-off, secrets, the reach switches, with the evidence recorded"
  - "[ ] 8. A register check: a stdlib script beside progress.py fails when an active plan is missing from §3 or a wave names a chunk that does not exist"
  - "[ ] 9. The production release checklist exercised once on develop: delete path, backups and restore, alarms, rollback"
  - "[ ] 10. This plan re-verified at each gate (I-0 to I-5), its register and gap list brought up to date"
---
# The MVP master plan

Written 2026-10-19 on the owner's request: "ensure all the plans work together towards the same goal,
write the master plan". Written against `develop` @ `769917f` plus #500 (the reach plan, not yet merged).
**Owner: the owner of the lane, S3 (`mvp-development-plan.md` §2), who keeps §3, §5 and §6 true.**
Every claim about code carries `file:line @ SHA`; one without is a hypothesis, marked ◇.

## 1. What this plan is

AIA has 96 plan files, 31 of them not done, with 158 open chunks. Each is a good plan for its own
feature. What did not exist is one place that says which of them are the MVP, in what order, who owns
what, what each hands to the next, and what has to be switched on for any of it to work. This is
that place. It does **not** copy any plan's chunks: a chunk is built from its own plan. It owns four
things: the **register** (§3), the **activation matrix** (§4), the **interfaces between plans** (§5)
and the **gaps** (§6), plus the **protocol** the sessions work by (§8).

**The goal, in one sentence.** A researcher, with their own Lead, takes a study from brief to an
approved client deliverable: respondents built from the population, Deep Research reaching the open
web, the client's own data in the analysis, every number and quote traceable to its origin, inside a
spend limit the researcher set. It is done when `MVP-ACCEPT-2`'s fifteen criteria pass in CI (tier A),
once live on develop within USD 25 (tier B), and the system is released to production.

**The document map.** One document owns each kind of question; on a disagreement the owner of that
kind wins, and the others are stale until fixed.

| Question | Owner | Document |
|---|---|---|
| What is the MVP, and what is out | the product owner's decisions MVP-1 to 33 | `overview.md` § MVP roadmap, `mvp-consolidation.md` |
| How is it accepted | the fifteen criteria and two tiers | `docs/migration/mvp-acceptance.md`, `parity-matrix.json` |
| What was decided, and what was found inconsistent | the decision register F1 to F19, Q1 to Q29 | `mvp-cohesion.md` |
| What is the shape: tables, workers, routes, AWS | the target architecture | `mvp-target-architecture.md` |
| In what order, by whom, behind which gate | gates, sessions, waves, the migration lane | `mvp-development-plan.md` |
| Which plan is in play, what links to what, what is missing, how sessions work | **this plan** | `mvp-master-plan.md` |
| How a chunk is built | each feature plan | `.planning/plans/<feature>.md` |
| Why a rule is what it is | ADRs | `docs/architecture/adr/` |

## 2. The three failures this plan exists to prevent

1. **A plan that is right and not connected.** `deep-research.md`'s status table said Wikipedia was the
   only live search route while every route family was built; the owner was told "only Wikipedia".
   Rule: a status that a machine can read is read by a machine (chunk 52 of
   `deep-research-web-search`), and a status a person writes names its SHA.
2. **A switch nobody threw.** Every AI button in every stage fails on develop with `route
   bedrock-eu-primary is not approved for CLASS_A_CLIENT_CONFIDENTIAL`, because the route is approved
   for Class C only until an operator records the Bedrock retention and sets four parameters
   (`deploy/develop/README.md` § AI route classes), and the deploy's smoke never looks:
   `smoke.py:207-214 @ 769917f` reports the AI check "not runnable ... never a pass". A green deploy
   hid a product that could not run. Rule: §4's activation matrix is declared in the repository and
   checked on every deploy (chunk 6).
3. **Two plans owning one surface.** `client-workspace` C8 says a dataset's use in a study is "V AIA
   zatím není"; `client-data-in-analysis` builds exactly that. Rule: §3 names one owner per surface
   and one disposition per plan; a plan that disagrees is re-scoped, not left to win by being later.

## 3. The plan register

**Role.** `CORE`: carries an MVP gate. `SUPPORT`: needed, gates nothing alone. `CLOSE`: finished or
superseded, to be verified and closed by its owner. `FOLD`: its remaining work belongs inside another
plan. `POST`: after the MVP, by decision. The dispositions of plans outside the development plan are
**proposed** (◇): each plan's owner confirms in chunk 3.

### 3.1 Core: named in the development plan (17)

| Plan | Open | Session | Waves | Gate | Needs first |
|---|---|---|---|---|---|
| `research-lead-workbench` | 15/26 | S1 | W0 (11), W1 (11, 14-19), W2 (20, 22), W3 (21), W4 (23) | I-1 to I-4 | edit vocabulary, `LeadWorkerSpec` |
| `evidence-integrity` | 5/5 | S2 | W0 (1, 5), W1 (2-3), W3 (4) | I-3 | none |
| `sociomap-formula-corrections` | 12/24 | S2 | W2 | I-2 | method owner (0a) |
| `segment-maps-and-drilldown` | 9/9 | S2 | W2 | I-2 | method owner, register entries |
| `audience-catalogue-cpu` | 1/4 | S2 | W0 (4) | I-0 | none |
| `complete-study-report` | 1/11 | S2 | W0 (B6) | I-0 | the AI route widened (§4), audience 4 |
| `deep-research-web-search` | 19/56 | S2 | W0 (1, 51, 53), W1 (52), W2 (6, 33-37), W4 (27, 38) | I-R, I-4 | Brave sign-off (owner) |
| `deep-research` | 1/12 | S2 | with the above | I-4 | chunk 4 (a ledger migration) is not in the lane (§6) |
| `client-budget` | 1/6 | S3 | W1 (CB5) | I-1 | none |
| `client-knowledge-lifecycle` | 8/21 | S3 | W1 (K2e, K2f, K3), W2 (K4, K5) | I-3 | none |
| `client-data-in-analysis` | 8/8 | S3 (4-5 S2) | W3 | I-3 | ADR 0027 policy decision |
| `research-integrity-report` | 4/14 | S3 | W3 (6-8) | I-3 | none |
| `two-roles-human-ai-gates` | 2/12 | S3 | W2, W3 (5b.4) | I-2, I-3 | a client-report contract |
| `develop-spend-attribution` | 4/4 | S3 | W0 (1-2) | I-0 | none |
| `mvp-acceptance-harness` | 8/8 | S3 | W0 (1-3), then every wave | I-0, I-5 | #495 merged |
| `system-prompts-settings` | 1/12 | S1 | W3 (7) | I-3 | worker row |
| `class-b-search-route` | 7/7 | S2 | **after the MVP** (deferred 2026-10-19, owner) | none | none |

### 3.2 Outside the development plan (14), proposed disposition

| Plan | Open | Proposed role | Why | Action |
|---|---|---|---|---|
| `productization-coherence` | 2/18 | SUPPORT (S1) | PC5 (stage track says the design changed after the run) and PC16 (rewording a question keeps its links) land inside artifacts 17-18 | add to workbench 17-18 as acceptance lines |
| `client-workspace` | 4/13 | FOLD into `client-knowledge-lifecycle` (S3) | C6-C9 overlap K3, K2, K6; C8 contradicts ADR 0027 and F19 | re-scope C8, point C6-C9 at the lifecycle chunks |
| `architecture-enforcement` | 4/11 | SUPPORT (S3) | the new tables must pass its contracts; chunk 9 (a digest on scope and claims) is security | schedule beside M1-M6; not gating |
| `ai-research-activation` | 1/4 | FOLD into §4 and chunk 7 | its open chunk is the activation the AI route still lacks | close when chunk 7 here is done |
| `run-recovery-and-truth` | 1/19 | CLOSE | chunk 4 (search beyond Wikipedia) is `deep-research-web-search` 51-52 | owner closes with a pointer |
| `research-agent-workflows` | 4/9 | CLOSE (verify) | 5-8 are covered by D17's workers, Interpretation Research (30) and `evidence-integrity` | owner closes with a pointer |
| `mvp-workflow-assurance` | 3/13 | CLOSE A4, A5; keep A3 optional | A4-A5 define an older four-area MVP including Simulation; `mvp-acceptance-harness` replaces them | owner re-scopes, A3 is measured simplification |
| `connected-research-assurance`, `contextual-research-settings-ux`, `desktop-ux-overhaul-handoff` | 1, 1, 3 | CLOSE (verify) | housekeeping chunks ("release checks, deploy, reconcile documentation") of finished work | owners verify against `develop`, close |
| `methodology-tab` | 3/45 | POST | S4d waits on the audit's author, W1c on panel source weighting, X1 is Simulation | none |
| `panel-grounded-respondents` | 3/44 | POST | 7f-7h are the holdout validation that lifts client-facing analysis prose; the MVP's client report carries none (AC-13) | none |
| `sociomapping-engine` | 14/27 | POST | the SOMECS engine depends on the method owner's exports and decisions; the MVP uses `aia-sociomap-3` | none |
| `simulation-studio` | 8/8 | POST | Simulation is out of the MVP (`mvp-acceptance.md`) | S0 recorded as deferred |

A plan not in §3 is a defect of this plan: chunk 8's check fails on it.

## 4. The activation matrix: what must be switched on, and who throws it

A feature that is built and not switched on does not exist for the owner. Each row is a switch, the
gate that needs it, who sets it, and the evidence that it is on. **Chunk 6 declares this profile in
the repository and makes the smoke report each row `READY` or `NOT_READY` with the reason, never a
paid call**, so a green deploy can no longer hide a dead product.

| Switch or parameter | Needed by | Set by | Evidence |
|---|---|---|---|
| `aia_ai_runtime_enabled`, route id, model and prices | every AI step (AC-03) | operator, SSM | Settings → AI |
| **`aia_ai_route_approved_for` = A, B, C** with `..._retention_days`, `..._eu_processing_approved`, `..._excluded_from_training` | **every design job** (the design is Class B by rule, approved knowledge Class A: `research_agents.py:675-686 @ 769917f`) | operator after the retention evidence | Settings → AI shows three classes; smoke `READY` |
| `aia_ai_research_agents_enabled` and its token and reservation limits | the workers (AC-03) | operator | Settings → AI |
| `aia_ai_research_lead_enabled` and the Lead's model keys | the Lead (AC-02) | operator | a Lead turn answers |
| `aia_ai_population_personas_enabled` | population-built respondents (AC-05) | operator, after `audience-catalogue-cpu` 4 | the Run stage offers the panel |
| `aia_ai_analysis_enabled` | the eight analysis modules (AC-08) | operator | a module is not `analysis_unconfigured` |
| `aia_ai_client_source_proposals_enabled` | AI proposals from a client document (AC-10) | operator | `client_source_proposals_unconfigured` gone |
| `aia_deep_research_enabled`, `..._web_search=brave`, key, price, `..._connectors`, Common Crawl keys | Deep Research reach (AC-11) | operator, owner signs the Brave plan | Settings → Deep Research lists each route active |
| ADR 0022 approvals on Nastavení → Deep Research | any priced route | an organization approver | `live_settings_unapproved` gone |
| `aia_web_research_workbench` | the workbench (AC-02) | operator | `/config` |
| `AIA_LEAD_PLANS_ENABLED` (new, off) | the plan card and envelope (AC-04) | S1 on develop when built | the I-1 exit passes |
| `aia_report_pdf_enabled` | the PDF beside the DOCX (AC-13) | operator, on for develop | a report has a PDF artifact |
| `clients.data_posture` per client | web search for a real client (AC-11) | an organization OWNER or ADMIN | the client's profile |
| Cognito, Google callbacks, population assets, the error tracker | sign-in, respondents, diagnostics | operator | `smoke.sh`, `/health` |

## 5. The interfaces between plans

An interface is something one plan produces and another consumes: a table, a route, an event, a file,
an enum value, a prompt. Each has one producer, one consumer, one owner, a test, and a wave. **The
contract is written before either side builds** (`mvp-development-plan.md` §5 lists six). The
traces (§7) add the ones below that had no owner.

<!-- §5 is completed from the traces in chunk 1 -->

## 6. The gap register

<!-- completed from the traces in chunk 1 -->

## 7. How this was checked

Five read-only traces followed each stage and each cross-cutting capability down and back up the stack
(screen, route, service, rule, table, worker, external call, artifact, back to the screen and the
Lead), one line per link: EXISTS with an anchor, PARTIAL, MISSING with the plan chunk that builds it
or NONE, CONTRADICTION. They are kept as evidence under `.planning/evidence/mvp-master-traces/` with
the SHA they were run at. They are an audit, not a proof: each finding names its anchor and a person
can reproduce it with one `git show`.

## 8. The execution protocol

**Environments.** `local` (the UI workbench, SQLite, fictional respondents, USD 0) → **CI tier A** (every
PR; `ci.yml` jobs: What changed, Backend, Frontend, API contract, Application starts, Security and
dependency scan, Documentation checks on a docs-only PR, and the parity jobs, informational by the
owner's decision of 2026-10-19) → **develop** (deployed when CI is green on a push to `develop`:
the `Dispatch verified develop deployment` job; `deploy-develop.yml` serialises deploys with
`concurrency: deploy-develop, cancel-in-progress: false`, `:30-32 @ 769917f`) → **tier B** (the live
acceptance on develop, within USD 25, run by a person) → **production** (a second Terraform root and
workflow in the same AWS account, with RDS; manual release).

**Branches and merges.** One prefixed branch per chunk group from a fresh `origin/develop`; a PR into
`develop`; never a direct commit to `develop` or `main`. A feature PR edits only its own plan file;
the shared files (CLAUDE.md, ARCHITECTURE.md, AGENTS.md, `overview.md`, `open-items.md`, the indexes)
change in a docs PR that applies the merged PRs' Doc follow-ups. **Merge order inside a wave:** the
contract, then its producer, then its consumer.

**The migration lane.** One Alembic head. S3 owns the lane. A migration PR names its `down_revision`,
is rebased on `develop` immediately before merge, and migration PRs merge one at a time (`§4` of the
development plan lists M1 to M10).

**Gates.** A wave ends when its gate passes in CI over HTTP, not when its chunks are ticked
(`mvp-development-plan.md` §1). A gate that needs a switch (§4) says so in its exit line.

**Definition of done for a chunk.** Its tests pass, including a test of the refusal path; `make
verify` is green; its anchors are in its plan; any shared-file change is written as Doc follow-up; its
switch, if any, is in §4 with its evidence; the plan's front matter is ticked.

**Status.** Progress lives only in plan front matter and the PR body (`python tools/progress.py`).
This plan's register is re-verified at every gate (chunk 10), and a session that finds a plan not in
§3, or a chunk a wave names that does not exist, fixes §3 in its PR, never in chat.

**Incidents and rollback.** A bad deploy is rolled back by the workflow's own input (an older
schema-compatible SHA with migrations unchecked, `deploy-develop.yml:24`); the runbook is
`deploy/develop/README.md`. Production adds the same with an RDS snapshot first.

**Who throws a switch.** An operator, from the runbook, with the evidence written down (chunk 7). A
session never asks for credentials in chat: a read-only credential goes in the environment's secrets,
and a write step is a person's.

## 9. The release to production

Before the first release: the delete path (database cascade, S3 prefixes, backups, with RDS snapshot
retention of 14 days stated), backups and a restore exercised once, the cost alarms and the tagged
Bedrock profiles reconciling to the usage ledger within USD 0.01 (AC-15), the cutover rollback
rehearsed on develop, the Cognito and Google callbacks for the production hostname, and the
activation profile of §4 `READY` on the production host. The hostname, RDS sizing and Bedrock quota are
still the owner's and an operator's (`mvp-target-architecture.md` §9).

## 10. Risks of the whole

| Risk | Consequence | What holds it |
|---|---|---|
| A built feature stays switched off | the owner sees a broken product (§2.2) | §4 and chunk 6 |
| S1 is the critical path and carries the Lead, the artifacts and the plan card | the date slips | the fewest side tasks; S2 and S3 carry everything that can wait |
| The method owner has not answered | segment maps, clustering and register entries wait | decisions named in `mvp-cohesion.md`; no dates yet |
| Classification is deferred and a client is marked OPEN | an OPEN client's queries reach Brave unchecked | the audited flag is the only guard, stated |
| Plans drift again | this plan goes stale | chunk 8, and the rule in §8 |
