# Trace 5: Deep Research, client data and knowledge, delivery infrastructure

Read-only cohesion audit of `/home/user/AIA`, branch `chore/mvp-master-plan`. Anchors are `file:line @ 82be9e03`
(`git rev-parse --short HEAD`). HEAD adds only `.planning/plans/mvp-master-plan.md` over `f7e80bb9`, so every
code anchor is also true at `f7e80bb9`. `◇` marks a hypothesis: a claim I did not open the code for, or
one that needs a live system to confirm.

**Status vocabulary.** EXISTS (anchor opened), PARTIAL (what is there, what is not), MISSING (plan and chunk,
or NONE), CONTRADICTION (both sides quoted with anchors).

**What I could not verify.** (1) The actual state of develop: every Deep Research switch lives in SSM
parameters under `/aia/develop/` written by hand (`deploy/develop/bin/write-env.sh:1-12`); the repository holds
only the Compose defaults, so "what is on today" is unverifiable from here. (2) Whether any live adapter
(Brave, the connectors, Athena) works against its real endpoint: `docs/architecture/deep-research-common-crawl.md:85-86`
says the Athena adapter "has not been run against AWS", and `docs/architecture/deep-research-connectors.md:20-30`
labels its interface facts UNVERIFIED. (3) I ran no tests and no CI. (4) GitHub's behaviour of a pending
workflow in a concurrency group is general knowledge, not from this repository (◇).

---

## 1. A Deep Research run, start to sealed bundle, and which routes are really on

**Verdict.** The six-step engine and the sealed bundle exist and are tested on recorded doubles. "Every route
family is built" (`mvp-development-plan.md:33-38`) is only partly true: procurement has no live source, the
focused crawler and the triage readers have no caller, and the connectors, the archive and Common Crawl run only
in agent-directed mode, a switch that no MVP document names. Nothing is on by default. The "only Wikipedia"
table is `docs/architecture/deep-research.md:519`; it contradicts its own header (`:3-9`) and the code.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Screen: Design Research panel starts a run | EXISTS | `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:91-97`; Interpretation: `InterpretationResearch.tsx` |
| Routes: start, interpretation start, get, events, cancel, retry, bundle, coverage, provenance, snapshot | EXISTS | `apps/api/src/aia_api/routers/deep_research.py:517, 550, 600, 678, 705, 715, 732, 865` |
| Application: one enqueue boundary, settings pin, live-approval gate, cost ceiling and confirmation | EXISTS | `packages/aia_core/src/aia_core/application/deep_research.py:572-704` (pin `:617-619`, `LiveNotApproved` `:625-631`, ceiling `:634-651`) |
| Six step kinds plus the handed-out track kind registered | EXISTS | `apps/executors/src/aia_executors/deep_research/__init__.py:65-84`, `packages/aia_core/src/aia_core/domain/deep_research/workflow.py:55` |
| Plan, investigate, merge, verify, synthesize, publish executors | EXISTS | `plan.py:80`, `investigate.py:97`, `review.py:89, 210`, `publish.py:75, 416` (all under `apps/executors/src/aia_executors/deep_research/`) |
| Composition from the environment, strict switches, fail-closed start | EXISTS | `apps/executors/src/aia_executors/deep_research_runtime.py:426-573`; built into the registry at `apps/executors/src/aia_executors/registry.py:219` |
| Defaults: everything off | EXISTS | `deploy/develop/docker-compose.yml:101-103, 168-181, 263-287` (ENABLED, WEB_SEARCH, COMMON_CRAWL, CONNECTORS, AGENT_DIRECTED, LEAD, FAN_OUT all `false` or empty) |
| What develop actually runs | PARTIAL | not verifiable: SSM only (`write-env.sh:20-37`). Master plan chunk 6 (activation profile) is meant to make it declared |
| Brave search route, priced, Class C only | EXISTS | `apps/executors/src/aia_executors/deep_research_live.py:201-246` (route `approved_for` C: `:104-116`); composed `deep_research_runtime.py:517-524` |
| Brave sign-off (plan, terms, price, quotas) | MISSING | `deep-research-web-search` chunk 1 (open, owner signs); README recipe `deploy/develop/README.md:578-600` |
| Fetch from any public host, robots.txt, PDF/XLSX/CSV kept | EXISTS | `deep_research_live.py:161-198`; `packages/aia_core/src/aia_core/domain/deep_research/web.py:72` |
| Documents "read in parts, tables as tables" | MISSING | `deep-research-web-search` chunk 6 (W2) |
| Connectors: ČSÚ DataStat, NKOD, Eurostat, ARES, OpenAlex, Crossref, Wayback | EXISTS | `deep_research_live.py:312-357`; each fee-free, Class C, pinned host (`:369-402`) |
| Connector interfaces proven against the live services | PARTIAL | facts labelled UNVERIFIED (`deep-research-connectors.md:20-30`); no live evidence exists (`.planning/evidence/` holds only `client-knowledge-review`) |
| Procurement connector | CONTRADICTION | dev plan: "every route family is built ... the ČSÚ ..., ARES and procurement connectors" (`mvp-development-plan.md:33-38`) and chunk 16 `[x]`, vs `deep_research_live.py:364-366` `UNAVAILABLE_CONNECTORS["procurement"] = "no live notice source exists yet ... recorded only"`; listing it stops the worker (`deep_research_runtime.py:290-292`) |
| Ladder that actually calls connectors, Wayback and Common Crawl | PARTIAL | only in agent-directed mode: `deep_research/agent_directed.py:466-528`, `deep_research/_shared.py:69-71`; planned mode (the default) never calls `gate.dataset` or `gate.archive` (`investigate.py` has no ladder). `AIA_DEEP_RESEARCH_AGENT_DIRECTED` is `false` in Compose (`docker-compose.yml:102`). No MVP document names it (grep of `mvp-*.md` and `mvp-master-plan.md`: no match). Chunk 51 and the activation matrix (`mvp-master-plan.md:119-131`) list "connectors, Common Crawl keys" only |
| Focused crawler | CONTRADICTION | dev plan `:33-38` lists it as built and I-R (`:143-146`) requires a run to reach "the focused crawler" in W1; `SiteCrawl` (`packages/aia_core/src/aia_core/application/site_crawl.py:189`) is imported only by its own test (`packages/aia_core/tests/test_site_crawl.py:21`); the plan says "Built; not yet called. Chunk 36 calls it" (`deep-research-web-search.md:645-647`); chunk 36 is W2-W4 |
| Common Crawl index and archive composed | EXISTS | `deep_research_live.py:255-302`; `deep_research_runtime.py:535-538` |
| Common Crawl AWS side (results bucket, workgroup, table, instance-role grants) | MISSING | NONE. `deep-research-common-crawl.md:123-141` "nothing here is applied", no Terraform (EU-only validation `infra/develop/variables.tf:7`); the instance role has no Athena or Glue statement (`infra/develop/main.tf:352-396`); adapter never run against AWS (`:85-86`). Dev plan puts Common Crawl in W0 chunk 51 |
| Triage readers on the light model | CONTRADICTION | chunks 20 and 23 are `[x]`, but `triage_pages` has no caller (`packages/aia_core/src/aia_core/application/deep_research_triage.py:263`), `LightModelSettings` says "No environment key builds one yet ... chunk 23 adds the switch" (`apps/executors/src/aia_executors/ai_runtime.py:187-198`), and the API's own price table says "Triage and the focused crawl are composed by no deployment yet" (`routers/deep_research.py:297-300`). Chunk 23's `AIA_DEEP_RESEARCH_CRAWL/TRIAGE/EXTRACTION` keys (`deep-research-web-search.md:671-674`) do not exist in `deep_research_runtime.py` |
| Tool spend held against the study before a call leaves | EXISTS | `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1184-1206` (`payee=tool:<route>`), `deep_research/runtime.py:359-369` |
| Tool spend in a ledger | MISSING | `deep-research` chunk 4 "Tool usage in the ledger (migration)" open and in no wave (`mvp-master-plan.md:90` calls it "not in the lane"); `ai_usage_events` records model calls only (`tables.py:1752-1833`) |
| Sealed bundle, coverage ledger, provenance | EXISTS | `publish.py:416`; routes `deep_research.py:705-732`; recorded journey `apps/executors/tests/test_deep_research_journey.py` (not run here) |
| Settings states each route as built, approved, active or refused | MISSING | `deep-research-web-search` chunk 52 (W1). Design gap: the API cannot see the worker's environment (`routers/settings.py:12-17, 99-107`); it holds its own env copy for pricing (`apps/api/src/aia_api/config.py:155-170`, `routers/deep_research.py:292-340`), so "read from the composition" (plan `:1641-1645`) has no channel today |
| Lead can see or start Deep Research | MISSING | `research-lead-workbench` 23 (W4); no occurrence of Deep Research in `application/research_lead.py` or `domain/research_lead.py` (grep) |

---

## 2. Classification today, and everything the planned OPEN posture must touch

**Verdict.** The plan counts six asks (plan step plus five `classify_query` calls). The code has more refusal
points, three gate constructions, and one `design_class` field that serves both searches and model requests.
Chunk 53 as written would leave an OPEN client refused in two places (the fictional-client flag, and the
model-class label) and does not say how a retry keeps its posture.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Plan step: design classified by an operator's exact-bytes record only | EXISTS | `apps/executors/src/aia_executors/deep_research/plan.py:163-174` (`classify_material`). A design with no record: the whole run is `Failed(RUNTIME_UNAVAILABLE, egress_unclassified_material)`, before any track is built |
| Docs say a CLASSIFIED client's "web tracks stay parked" | CONTRADICTION | dev plan `:64-70` ("its web tracks stay parked") and plan `:1664-1665` vs `plan.py:166-174`: every track, internal ones included, never starts |
| Query classifier `aia-query-classifier-1`: context floor, client terms, Class A 5-gram overlap | EXISTS | `packages/aia_core/src/aia_core/domain/deep_research/classification.py:110-137` |
| The five `classify_query` calls | EXISTS | `packages/aia_core/src/aia_core/application/web_retrieval.py:788` (search), `:882` (fetch URL), `:1177` (URL index), `:1275` (archived fetch), `:1365` (datasets and archives) |
| Refusals that follow the classifier and are not `classify_query` | PARTIAL | `refusal_for_class` (`web_retrieval.py:618-632`, called `plan.py:260`), `class_a_query` / `class_a_url` literals (`:797, :896, :1187, :1291, :1401`), `dataset_class_c_only` (`:1403`), `_refusal` to `evaluate_egress` (`:608-616`). All are satisfied only if the replaced classification returns C; chunk 53 names only "the plan step and every query" |
| Gate construction sites that must receive the posture | MISSING | three: `plan.py:249`, `investigate.py:296`, `standing.py:78`. Chunk 53 text names none |
| `clients.data_posture` column and migration M10 | MISSING | `deep-research-web-search` 53; dev plan `:195, 201`. `grep data_posture` finds only plan files; not in `tables.py` or `migrations/versions` (47 files) |
| Setter route, owner-or-admin permission, audit row, profile display, api-contract entry | MISSING | NONE. Chunk 53 says "Only an organization OWNER or ADMIN sets it ... audited ... shown on the client's profile" but names no route; the target-architecture route table (`mvp-target-architecture.md:260-275`) has none. Audit pattern exists: `access_audit` free-text action (`infrastructure/client_source_repository.py:471`) |
| Where the posture is frozen | EXISTS (place) | `_frozen_request` (`application/deep_research.py:296-346`, reads `scopes.client_of_study` at `:322`) serves both purposes; request pattern for an optional field: `settings_method` (`domain/deep_research/contracts.py:286, 295-300`) |
| "A retry keeps the original's posture" | CONTRADICTION | plan `:1660-1661` "like ADR 0022's settings pin; a retry keeps it" vs `retry` "Frozen afresh ... what changed since ... is in the new engine request" (`application/deep_research.py:716-725`, `start` at `:759`) and `_enqueue` re-reading settings in force at `:617`. A retry re-freezes from the current client row, and the existing settings pin does the same. The posture needs the original run's metadata passed to `start` |
| One `design_class` serves search context and model requests | CONTRADICTION | chunk 53 "the design is treated as Class C" (plan `:1662-1663`) vs dev plan "Not touched in code: ... the model gateway and `material_rules` for model calls" (`:72-73`) and "a design is Class B by rule" (`domain/material_rules.py`). `plan.design_class` feeds `context_class=` at `investigate.py:548`, `agent_directed.py:423, 509` and `data_class=` of every model request (`plan.py:302`, `agent_directed.py:273-293`, `lead.py:505-529`, `investigate.py:723-744`). One field cannot be C for Brave and B for Bedrock; chunk 53 does not say which |
| Fictional-client flag and what it gates | MISSING | NONE. `fictional` comes only from an operator approval with `synthetic=True` (`plan.py:175-178`). It decides `bundle.fictional_client` (`domain/deep_research/quarantine.py:70-77` refuses a fictional client's bundle client-facing; `design_proposals.py:176-181` refuses recorded evidence for a non-fictional client). Under OPEN no approval is read, so `fictional` becomes false for the acceptance client: tier A's recorded run would get `admissible=False`. `fictional_client_ids` is carried in the runtime config and read nowhere (`deep_research/runtime.py:79`). `domain/deep_research/agents.py:723 design_class(fictional_client=)` has no caller |
| Class A text protection for an OPEN client | PARTIAL | the 5-gram overlap that stops client confidential text reaching a query (`classification.py:133-136`) is among what OPEN removes. The plan states the cost as "names included" (`deep-research-web-search.md:1671-1672`, dev plan `:88-90`), not the verbatim-text case |
| Class A knowledge reaching a model still needs the route widened | PARTIAL | `request_class` (`domain/deep_research/agents.py:731-733`, used `investigate.py:374`) takes the most restrictive of design and sources; route approved for C only until the W0 operator step (`deploy/develop/README.md:394-395, 412-472`; dev plan `:126`). A plan, contingent on an operator act |
| Respondent-context leakage screen stays whatever the posture | EXISTS | `review.py:151`, `application/contextual_report.py:232`; chunk 53 does not mention it, so a reader could remove it as "classification" (◇) |
| Track reuse across postures | PARTIAL ◇ | `track_fingerprint` keys on `method_identity()`, not posture or design class (`domain/deep_research/planning.py:349-392`); a CLASSIFIED run in the same study could reuse web tracks gathered under OPEN. Plan says "CLASSIFIED: unchanged" (`:1664`) |
| ADR 0008 amendment recording the open posture and the deferral | MISSING | dev plan §6 and W0; `mvp-master-plan` chunk 5. Not written |
| Plan statement that the class-by-rule classification is mandatory | CONTRADICTION | `class-b-search-route.md:61` "3. **Classification (mandatory: it does not wait for a Class B route)**" vs its front-matter line 7 "`(after the MVP)` ... once a Class B route exists" and its "Deferred (2026-10-19)" section (`:116-124`) |
| Acceptance wording | CONTRADICTION | `docs/migration/parity-matrix.json:4067` and `docs/migration/mvp-acceptance.md:86` AC-11: "through the search route approved for Class B under an EU processing agreement" vs Brave Class C plus OPEN (`mvp-development-plan.md:53-64, 91-93`). Doc follow-up named, not applied |
| Web intake of a client's URL (K2e) through the gate | MISSING | `client-knowledge-lifecycle` K2e (W1, open). `_fetch_admission` classifies the URL against client terms (`web_retrieval.py:877-898`): a URL naming the client is Class B and the fetch route is C-only, so a client's own website would be refused for a CLASSIFIED client. K2e does not mention posture or classification |

---

## 3. Design Research, Interpretation Research, and "Ověřeno, přidat zdroj"

**Verdict.** The integration is built and layered (a proposal never writes a design except through a person's
accept). Three plans each claim to move Deep Research evidence into Client Knowledge, and the report's cited
context needs a second Deep Research run that the acceptance wording and budget do not mention.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Design Research proposal built by code from the sealed bundle | EXISTS | `domain/deep_research/design_proposals.py:165-195`; routes `routers/deep_research.py:749, 768` |
| Accept into a Design Revision, one transaction, item-level stale rule | EXISTS | `application/proposal_accept.py` (CLAUDE.md map); layer rule `tools/layer_check.sh` ("only the person's accept applies a Design Research proposal") |
| Interpretation Research start, mission by code, lineage pinned | EXISTS | `application/deep_research.py:382-435, 538-570`; route `deep_research.py:550` |
| Doc says interpretation start is "refused at the enqueue boundary until chunk 30" | CONTRADICTION | `docs/architecture/deep-research.md:451-453` vs `application/deep_research.py:538-570` (live) and plan chunk 30 `[x]` |
| One-click source into client knowledge | EXISTS | `application/verified_sources.py:44-80`, route `deep_research.py:799`; plan `inline-decisions` chunk 1 (done) |
| Item class of that source | PARTIAL ◇ | `KnowledgeKind.SOURCE` is Class A (`domain/deep_research/knowledge_access.py:57`), whatever the page's publicity; a public page added by the click becomes Class A material for the next run's overlap check and any model request |
| Three owners of "Deep Research evidence into knowledge" | CONTRADICTION | `inline-decisions` 1 (done, writes knowledge at once, `verified_sources.py:1-12`), `client-knowledge-lifecycle` K2e "each becomes a proposal ... no model call" (`:558-564`, open), `deep-research-web-search` 37 "a Client Knowledge DATASET proposal a person accepts" (`:982-986`, open). Same surface, different semantics (item now vs proposal) |
| Accepted findings as cited context in the report | PARTIAL | only the "with research" variant (`contextual_report.py:985` requires `INTERPRETATION_RESEARCH`); the client report has no literature content (`client_report.py`: no match). AC-11 says "Design Research runs live" and "accepted findings appear as cited context in the report" (`mvp-acceptance.md:86`): the second half needs a second, post-results live run |
| Budget and gate for that second run | MISSING | NONE. `mvp-acceptance-harness` chunk 1 lists "live Deep Research (its own pinned allowance)" once (`:46-50`); gate I-4 names one run (`mvp-development-plan.md:30`) |
| Manual start button vs "every AI action through the Lead" (AC-02) | PARTIAL | `DeepResearchPanel.tsx:91-97` starts a paid run directly; removal and cards are `research-lead-workbench` 23 (W4); "reachable from every stage" 25 is after the MVP |
| Deep Research findings in the Lead's context | MISSING | the `ResultsContext` contract (`mvp-development-plan.md:211-214`) lists admitted claims, pair statuses, module text, report draft ids, QC; no external-evidence provider. AC-02 "the Lead quotes no number its context does not hold" |

---

## 4. Client knowledge lifecycle: sources, datasets, the data contract, intake

**Verdict.** The source store, readers, AI proposals, folders, labels and intake exist. Everything after
"a person accepts knowledge" (revisions, context snapshot, dimensions as executable objects, the data contract,
the dataset copy) is unbuilt, and the two plans that would carry it disagree about permission and about what
"a run with a cost" means.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Client source store, dedupe per client, readers PDF/DOCX/DOC/ODT/PPTX/TXT/MD/CSV/XLSX/XLS/ODS | EXISTS | `domain/client_sources.py:84-118`, `infrastructure/source_reading.py`, routes `routers/client_sources.py:249-538` |
| Dataset preview, personal columns masked by hint | EXISTS | `domain/client_datasets.py:1-30` (hints "err towards flagging") |
| AI proposals from a document, paid by the client | EXISTS | `apps/executors/src/aia_executors/client_source_proposals.py`; off by default (`docker-compose.yml:254`), in the activation matrix |
| Folders, labels, placement; intake sheet | EXISTS | `routers/workspace.py:1618-1760`, `infrastructure/client_knowledge_repository.py:425-570`, `apps/web/src/components/aia/clients/IntakeSheet.tsx` |
| Intake makes a DOCUMENT item holding only `source_id` | EXISTS | `apps/web/src/lib/intake.ts:200` (`content: withSource({}, source_id)`) |
| Consumers read the document's text | PARTIAL | `freeze_knowledge._source` reads `content["text"]`, title and summary only (`knowledge_access.py:75-90`); a file-backed item has none, so Deep Research's knowledge and its Class A overlap texts do not hold the file. Resolving knowledge into one snapshot is K4 (W2, open) |
| Web intake beneath a study, Deep Research evidence imported | MISSING | `client-knowledge-lifecycle` K2e (W1, S3) |
| Review payload with evidence, connected acceptance | MISSING | K2f (W1) |
| Typed revisions against the reviewed base | PARTIAL | K3a done (stale refusal, `client_knowledge_repository.py`); K3 open (W1) |
| Executable client dimension from a knowledge item, own-dimension chip | PARTIAL | materialization route takes a definition body whose evidence names `knowledge_item_id` (`routers/materialize.py:60-90`); item-to-definition link, F-K2 and chips are K5 (W2) and the Brief/Dimensions artifacts (S1 chunk 22) |
| "The build is a run with a cost, refused when the envelope has no room" | CONTRADICTION | `mvp-cohesion.md` F19 vs `application/materialize.py` (no cost, budget or ceiling anywhere: grep) |
| Data contract, accept route, allowlist analysis copy | MISSING | `client-data-in-analysis` 2-3, M8 (W3). No `client_data_contracts` or `client_dataset_copies` in `tables.py` or migrations |
| Permission to accept a data contract | CONTRADICTION | `client-data-in-analysis.md` chunk 2 "an accept route under `APPROVE_GATE` writing an approval-ledger row" vs `mvp-target-architecture.md:273` "`PROPOSE_CLIENT_KNOWLEDGE` ◇". `APPROVE_GATE` is a study permission; client-level permissions are `ClientPermission` (`domain/scope.py:221-240`). A ledger row with no study is allowed (`approval_decisions.study_id` nullable, `tables.py:1665-1668`) |
| Evidence policy for client columns, origin `CLIENT_REPORTED` | MISSING | `client-data-in-analysis` 0-1; decision deferred (`mvp-cohesion.md` F3); no `CLIENT_REPORTED` in code (grep) |
| Delete or retire a source, item, client | MISSING | NONE as a plan with a service; `productization-coherence` D-15 and F035 "no list or delete anywhere" (`:612, 707`); K6 retirement open; only contact, folder, label deletes exist (`workspace.py:1514, 1674, 1758`) |
| Owned child version deletable | CONTRADICTION | FK `population_dataset_versions.owner_client_id -> clients` has no `ondelete` (`tables.py:1938-1939`) and IAM grants no delete on the population bucket (`infra/develop/main.tf:364-368`: "No delete: a child a run was computed over must stay readable") vs retention decision "kept until a person deletes it" (`mvp-target-architecture.md:433`) |

---

## 5. Project memory search and reuse

**Verdict.** Complete for the MVP scope (design reuse within one client). AC-12 is built and needs only the
release run. Nothing found contradicts it.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Search one client's studies, scoped per study | EXISTS | `application/project_memory.py:77-117`; route `routers/workspace.py:931-932` |
| Reuse a past design into a new or empty study, citation insert-once | EXISTS | `application/design_reuse.py`, route `workspace.py:998`; `project-memory-reuse` M0-M4 all `[x]` |
| Labels carried (synthetic, draft, internal only) | EXISTS | `domain/design_reuse.py` (derive_source_labels) |
| Another client or organization refused | EXISTS | `project-memory-reuse` M4 `[x]`; ScopeResolver per study (`project_memory.py:103-108`) |
| Memory answer worker | EXISTS | `ResearchAction.MEMORY` (`domain/research_agents.py:44`) |
| Reuse of results or Deep Research evidence | MISSING (by decision) | out of the MVP (`project-memory-reuse.md` M0.2); consistent with the dev plan |

---

## 6. The report's research-context chapter and the dataset of a run's sources

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Literature chapter, every claim beside its verbatim passage, source table | EXISTS | `application/contextual_report.py:235` (`literature_sections`); `research-integrity-report` 2-3 `[x]` |
| Variant stored once per exact source set, DOCX and PDF | EXISTS | `stored_contextual_report` (`contextual_report.py:864`); artifact `research_internal_docx_with_research` |
| Dev plan W4: S3 builds "the report's research-context chapter; DR's sealed bundle into the report" | CONTRADICTION | `mvp-development-plan.md:171-173` vs the above (already built, done). What remains is `research-integrity-report` 6-8 (lineage matrix, reading notes, association questions) |
| Requires a selected completed interpretation run | EXISTS | `contextual_report.py:985` |
| Client report carries the research context | MISSING | NONE; `client_report.py` has no literature content. AC-11 wording ("in the report") and AC-13 ("no analysis prose") do not say which report |
| "The run's sources are kept as a dataset" | PARTIAL ◇ | the sealed bundle's snapshots and coverage ledger exist (`deep_research.py:715`); the dataset artifact is chunk 37 (W2-W4), defined per inventory subject (`deep-research-web-search.md:982-986`) and needs 33-36. A design run with no inventory subject (a library-services study) may produce no dataset, so AC-11's clause is unproven for the acceptance brief |
| Provenance lineage matrix | MISSING | `research-integrity-report` 6 (W3) |

---

## 7. AWS and deployment

**Verdict.** The develop root is coherent and least-privilege for what exists. The production plan has no plan file; the
MVP documents contradict the code about tags, ARN support, CI checks and deletion, and the delete path is
blocked by four independent things.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| One Terraform root, buckets, ECR, SSM, EC2, Cognito, DLM, alarms, budget | EXISTS | `infra/develop/main.tf` (buckets `:106-140`, IAM `:352-396`, host `:417-446`, alarms `:541-594`, budget `:597-619`); state backend `versions.tf:21-27` |
| Deploy workflow: build SHA, push, SSM run, one deploy at a time | EXISTS | `.github/workflows/deploy-develop.yml:30-32` (`group: deploy-develop`, `cancel-in-progress: false`); host lock `deploy/develop/bin/deploy.sh:43-44` |
| CI cancels a superseded push's run and its dispatch | PARTIAL | `ci.yml:17-19` `cancel-in-progress: true` per ref; dispatch at `ci.yml:978-993`. Intended; a rapid migration lane (M1-M10) will skip intermediate deploys ◇ |
| Tier B during auto-deploys | MISSING | NONE. Every green push to develop dispatches a deploy that restarts containers; nothing freezes deploys during a live acceptance run (harness chunk 7 does not mention it) |
| Backups: nightly and pre-deploy `pg_dump`, EBS snapshots, restore rehearsal by hand | EXISTS | `deploy/develop/README.md:331-355`; ops lifecycle 30 days, noncurrent 7 (`main.tf:193-221`) |
| Restore rehearsal exercised once, timed, alarmed | MISSING | `mvp-master-plan` chunk 9 (checklist only, no code) |
| `infra/production` second root, RDS, own Cognito, buckets, host, OIDC role, `deploy-production.yml`, manual gate | MISSING | NONE as a plan file: grep of `.planning/plans/` for `infra/production` and `deploy-production` finds nothing; they appear only in `mvp-target-architecture.md` and `mvp-development-plan.md` (W0 skeleton, W1 applied) |
| Copy hazards for production | PARTIAL | `create_github_oidc_provider` defaults true and an account holds one (`infra/develop/github.tf:19-31`): a second root must set false, and destroying develop would delete the provider production's deploy role trusts; buckets are `force_destroy = true` "synthetic data only" (`main.tf:106, 112, 117`) and README `:1071-1075`; provider `default_tags Environment = "develop"` (`versions.tf:34-40`) |
| CI validates Terraform | CONTRADICTION | `infra/develop/README.md:36-38` "`terraform fmt -check` is the only check the repository runs" and `mvp-target-architecture.md:414-415` "`infra/production` validated by `terraform validate` in the docs-and-config job" vs `.github/workflows/ci.yml`: no `terraform` and no `docs-and-config` job (grep). Jobs are `docs-checks` and `develop-host-config` |
| IAM per environment, tag-conditioned with permission boundary | MISSING | NONE as a chunk (`mvp-target-architecture.md:316-322`). Develop's role is ARN-scoped, not tag-conditioned (`main.tf:352-396`); IMDS hop limit 2 so containers reach the role (`main.tf:434`) |
| Secrets: SSM SecureString read at deploy into a root-only `.env`, Brave key to the worker only | EXISTS | `write-env.sh:20-37`, `docker-compose.yml:276`; one role reads every `/aia/develop/*` (`main.tf:385-388`) |
| Tagged Bedrock application profiles per tier | MISSING | `develop-spend-attribution` 1-2 (W0-W1) |
| That plan's premise "no `Environment` tag" | CONTRADICTION | `develop-spend-attribution.md:28` vs provider `default_tags` (`versions.tf:34-40`) and the budget already filtering `user:Environment$develop` (`main.tf:597-607`). Only the billing activation is a human act. Consequence: every taggable resource carries the tag, so the reconciliation must filter to Bedrock, which chunk 3 does not say |
| Profile ARN accepted by the model settings | CONTRADICTION | plan chunk 1 "One Terraform change ... their ARNs replace the ids in the settings the worker reads" vs `ai_runtime.py:254` and `:516` (`model_id.startswith("eu.")`, `":" in model_id`) and the Lead's `_lead_eu_profile` (`:261-270`): an `arn:` id is refused at worker start |
| Reconciliation of ledger against the AWS tagged cost | MISSING | `develop-spend-attribution` 3-4; and tool spend (Brave, Athena) is not in `ai_usage_events` (see §1), so AC-15's "spend reconciles" covers model spend only |
| Production egress: forward proxy with hostname allow-list | CONTRADICTION | `mvp-target-architecture.md:365-369` "the worker reaches search hosts only through a forward proxy ... allowing 443 only to the proxy" vs `public_retrieval` fetching "any public host" and the owner's "non-indexed web included" (`deep_research_live.py:161-198`, dev plan `:33-38`). No chunk |
| Activation visible on deploy | MISSING | `mvp-master-plan` 6; today `apps/executors/src/aia_executors/smoke.py:207-214` reports the AI check `NOT_RUNNABLE` |
| `develop` is a fictional-data environment | EXISTS | `packages/aia_core/src/aia_core/domain/deployment.py:9-10, 36-44`; README `:1104-1108` "Synthetic data only". Not contradicted by the plans (the acceptance client is internal), but production needs its own ADR 0022 approvals per organization: not in the release checklist (`mvp-master-plan.md:195-200`) |

---

## 8. CI tiers and the acceptance harness

**Verdict.** Today's blocking set matches `ARCHITECTURE.md` §8. The acceptance tree does not exist and CI does
not collect it. Two of the harness's eight chunks (4 and 8) are in no wave, and chunk 7 waits on a plan the
owner deferred past the MVP.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Blocking jobs and the deploy dispatch need | EXISTS | `ci.yml:978-993` needs backend, parity, golden-fixtures, oracle-parity, parity-status, api-contract, frontend, startup-smoke, develop-host-config, security; `ARCHITECTURE.md:640-695` |
| Parity status fails the job on any FAIL | EXISTS | `ci.yml:436-478`, `tools/parity_status.py:600-601` (exit 1). In practice the reference jobs skip (`NOT_EXECUTED`) |
| "Parity never blocks" | MISSING | `mvp-acceptance-harness` 8; not in any wave of `mvp-development-plan.md:122-182` (W0 names 1-3, W5 names 5-7) |
| `tests/acceptance/` and a CI step collecting it | MISSING | directory absent; `ci.yml:200` collect-only names four trees; harness 3 (W0) |
| The `acceptance` marker | MISSING | `pyproject.toml:276-282` has `--strict-markers` and four markers, no `acceptance`; chunk 3 does not list registering it |
| Recorded retrieval double behind the gate | EXISTS | `apps/executors/src/aia_executors/deep_research_recorded.py`; layer rule keeps it out of `src` and `deploy` only (`tools/layer_check.sh:547-553`), so an acceptance world under `tests/` may name it |
| Recorded doubles for the Lead, every worker, respondents, analysis | MISSING | harness 4 (planned) and in no wave |
| Fifteen criteria wired, acceptance record, parity line | MISSING | harness 5-6 (W5; first batch AC-01, 06, 07, 12, 14 in W0 per exit I-0) |
| Tier B on develop | CONTRADICTION | `mvp-acceptance-harness.md:75-83` "Chunk 7 needs `class-b-search-route`" vs `class-b-search-route.md` "Deferred (2026-10-19): every chunk is after the MVP" and dev plan `:50` |
| Tier A can pass AC-11 as worded | CONTRADICTION | AC-11 requires "the search route approved for Class B" (`mvp-acceptance.md:86`); the MVP route is Class C |
| Doc follow-up for ARCHITECTURE §8 "blocking on FAIL" cells | MISSING | `mvp-cohesion.md` §6; applied in the docs PR |

---

## 9. Data lifecycle: retention and the delete path

**Verdict.** The owner decided "kept until a person deletes it" and a "documented delete path before production"
(`mvp-target-architecture.md:433`). No code or plan builds a delete. Four existing structures block a database
cascade plus prefix delete as the plan describes it.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Delete service for a client or study (DB and S3, audited) | MISSING | NONE as a chunk; dev plan W5 and `mvp-master-plan` 9 list it as a release item. Only `ProjectRepository.purge` (rows, trashed project, `infrastructure/repositories.py:658-669`) exists |
| Database cascade | CONTRADICTION | most tables cascade, but `ai_usage_events.study_id -> studies` has no `ondelete` (`tables.py:1833`) and `population_dataset_versions.owner_client_id -> clients` has none (`:1938-1939`); a delete is refused by the database. The usage ledger is also what AC-15 reconciles |
| S3 prefix delete | MISSING | the `ArtifactStore` protocol has `delete(key)` only (`infrastructure/storage.py:171-214`); `delete_prefix` exists only on the filesystem store (`:366`); the S3 store has per-key delete (`:482`) |
| Key layout supports it | EXISTS | `build_storage_key` `org/<org>/client/<client>/study/...` (`storage.py:123-160`); client sources `.../sources/<sha>` (`client_source_repository.py:96`); the planned dataset copy `.../datasets/<sha>` |
| Versioned buckets make a delete reversible for 30 days | PARTIAL | artifacts bucket noncurrent expiry 30 days (`main.tf:178-191`); IAM has `s3:DeleteObject` but not `DeleteObjectVersion` or `ListBucketVersions` (`main.tf:352-357`); population bucket has no noncurrent expiry (`main.tf:223-232`) and no delete grant |
| Backups hold deleted data | PARTIAL | develop: `pg_dump` 30 days, EBS snapshots 7 (README `:331-335`); production: RDS 14 days stated. Restoring a pre-delete dump brings the rows back with their S3 objects gone (`artifact_corrupt` reads); nothing re-applies a deletion after a restore |
| Audit rows after deletion | MISSING | `access_audit` has no foreign key (`tables.py:590-618`) and its payload is structured before/after data; `approval_decisions` cascades with the study (`tables.py:1707`). Which survives is undecided |
| Other stores that hold client-derived data | MISSING | GlitchTip's own PostgreSQL (`deploy/develop/errors/`), CloudWatch logs, Brave's query logs (90 days, `deep-research-web-search.md:500`): not in the delete path's scope |
| Deep Research snapshot retention job | MISSING | `deep-research-web-search` chunk 24 (open: "the snapshot and dataset retention job", `:688`) |

---

# Lists

## (A) GAPS: a link MISSING with no plan

- **A1.** `AIA_DEEP_RESEARCH_AGENT_DIRECTED` gates the ladder, hence connectors, Wayback and Common Crawl (`agent_directed.py:466-528`); default false (`docker-compose.yml:102`). No MVP document or chunk 51 names it. Owner: S2 (add to chunk 51 and the activation matrix).
- **A2.** `clients.data_posture` has no setter route, permission test, audit row, profile UI or api-contract entry; the target-architecture route table omits it. Owner: S3 (route and UI, with M10), S2 (reads it).
- **A3.** Under OPEN `plan.fictional_client` becomes false (`plan.py:175-178`), flipping `quarantine.require_live_evidence` and `design_proposals.admissible` for fictional clients, tier A included. Needs a source other than the operator record (for example `AIA_AI_FICTIONAL_CLIENT_IDS`, now unread, `deep_research/runtime.py:79`). Owner: S2.
- **A4.** One `design_class` field drives both search egress and model requests; chunk 53 must specify C for queries and B-by-rule for model requests, or accept a C stamp on B material. Owner: S2 with the ADR 0008 amendment.
- **A5.** Common Crawl's AWS side (workgroup, results bucket, Athena and Glue grants, us-east-1 residency exception) has no Terraform and no plan; the adapter has never run against AWS. Owner: S3 (infra) with the owner's residency call.
- **A6.** Triage readers and the light model are unwired (no env keys, no caller) while chunks 20 and 23 are ticked. Owner: S2; fix the ticks or add the wiring chunk.
- **A7.** Delete path: no service, no `delete_prefix` on S3, no `DeleteObjectVersion` grant, no decision on `access_audit`, backups, GlitchTip, logs. Owner: S3 (new plan file, before W5).
- **A8.** `infra/production`, `deploy-production.yml`, RDS, production Cognito: no plan file. Owner: S3 (new plan `production-environment`).
- **A9.** Egress hostname allow-list proxy and tag-conditioned IAM with permission boundary: described in `mvp-target-architecture.md:316-322, 365-369`, no chunk. Owner: S3.
- **A10.** No Terraform validation in CI. Owner: S3 (harness or ci-skip plan).
- **A11.** Freeze of auto-deploys during a tier B run. Owner: S3.
- **A12.** Tool spend (Brave, Athena) is in `budget_reservations` and the event feed, not in a ledger row; AC-15 "spend reconciles" is model-only. `deep-research` chunk 4 is in no wave. Owner: S2 (ledger), S3 (reconciliation).
- **A13.** Harness chunks 4 (doubles for Lead and workers) and 8 (parity never blocks) are in no wave; the `acceptance` marker is unregistered. Owner: S3.
- **A14.** A second live Deep Research run (Interpretation) is needed for "cited context in the report"; absent from AC-11's wording, gate I-4 and the USD 25 budget table. Owner: S2 and S3.
- **A15.** Lead has no Deep Research context provider or card; `ResultsContext` has no external-evidence slot. Owner: S1 with S2.
- **A16.** Per-connector live probes before sign-off: every connector interface is UNVERIFIED. I-R is the first live use of most routes. Owner: S2.
- **A17.** Production needs its own ADR 0022 approvals per organization; not in the release checklist. Owner: S3 and an operator.

## (B) CONTRADICTIONS

- **B1.** "Every route family is built" (`mvp-development-plan.md:33-38`) vs procurement (`deep_research_live.py:364-366`), crawler (no caller, `deep-research-web-search.md:645-647`), triage (`ai_runtime.py:187-198`); I-R (`:143-146`) needs the crawler in W1, chunk 36 is W2-W4.
- **B2.** CLASSIFIED "web tracks stay parked" (dev plan `:64-70`) vs `plan.py:166-174` failing the whole run.
- **B3.** "A retry keeps the original's posture ... like ADR 0022's pin" (`deep-research-web-search.md:1660-1661`) vs `application/deep_research.py:716-725, 617`: retry re-freezes and re-pins current values.
- **B4.** "design treated as Class C" (plan `:1662-1663`) vs "material_rules for model calls not touched" (dev plan `:72-73`).
- **B5.** `class-b-search-route.md:61` "mandatory" vs its front-matter line 7 and Deferred section.
- **B6.** AC-11 and MVP-27 still say Class B (`parity-matrix.json:4067`, `mvp-acceptance.md:86`); harness chunk 7 depends on the deferred plan (`mvp-acceptance-harness.md:75-83`).
- **B7.** `docs/architecture/deep-research.md:519` ("Czech Wikipedia is the only live route"), `:503-504, :520` ("a real client's queries are Class A") and `:451-453` ("interpretation refused until chunk 30") vs its own `:3-9` and the code.
- **B8.** `develop-spend-attribution.md:28` "no Environment tag" vs `versions.tf:34-40`, `main.tf:597-607`; "ARNs replace the ids" vs `ai_runtime.py:254, 516`.
- **B9.** `infra/develop/README.md:36-38` and `mvp-target-architecture.md:414-415` assume Terraform checks in CI; `ci.yml` has none.
- **B10.** Data-contract permission: `APPROVE_GATE` (`client-data-in-analysis.md` 2) vs `PROPOSE_CLIENT_KNOWLEDGE` (`mvp-target-architecture.md:273`).
- **B11.** F19 "a run with a cost" vs `application/materialize.py` (no cost).
- **B12.** Population IAM "no delete" and non-cascading FKs (`main.tf:364-368`, `tables.py:1833, 1938-1939`) vs the retention and delete decision.
- **B13.** Dev plan W4 assigns S3 a research-context chapter already built (`contextual_report.py:235`); K2e vs `verified_sources.py` vs chunk 37 (three semantics for evidence into knowledge).
- **B14.** Production allow-list proxy (`mvp-target-architecture.md:365-369`) vs fetch from any public host (`deep_research_live.py:161-198`).
- **B15.** Chunk 16 `[x]` and chunk 23 `[x]` vs the code (procurement and keys above).

## (C) INTERFACES crossing plans or sessions with no owner

- **C1.** The classification code sits in surfaces no session owns in `mvp-development-plan.md:107-111`: `application/web_retrieval.py`, `application/deep_research.py`, `aia_executors/deep_research/*`, `routers/deep_research.py`, `ClientRow` and `scope_repository`. Proposed owner: S2, with S3 reviewing the column and S3 owning the setter route.
- **C2.** Chunk 52 (S2) edits Settings, whose router S1 owns (`routers/settings.py`), and needs the worker's composition, which the API cannot read. Proposed: S2 writes a worker-published composition record, S1 reviews the Settings change.
- **C3.** Evidence into Client Knowledge has three plans (§3). Proposed: S3 owns the knowledge side (K2e), S2 supplies the bundle reader; one semantics (item or proposal) decided once.
- **C4.** A plan step (S1, worker) must start Deep Research with the same cost ceiling as the API, but the pricing function lives in `routers/deep_research.py:292-340` and reads the API's env copy. Proposed: S2 moves it to the application layer; S1 consumes it.
- **C5.** Lead results context and Deep Research bundle (S1 and S2): add an external-evidence provider to `ResultsContext`, labelled L, never respondent evidence.
- **C6.** Client source text and the knowledge consumers: Deep Research's `freeze_knowledge` (S2) vs K4 (S3). Proposed owner: S3; S2 reads the snapshot.
- **C7.** Delete path vs spend reconciliation vs backups (all S3): the ledger FK, the audit rows and a restore after deletion need one rule.
- **C8.** Tier B and auto-deploys, and production's own org approvals (S3 and an operator).
- **C9.** Tool spend vs AC-15 (S2 ledger, S3 reconciliation).
- **C10.** Posture and web intake (S3 K2e) share the gate; K2e must state what it does for CLASSIFIED and OPEN clients.
