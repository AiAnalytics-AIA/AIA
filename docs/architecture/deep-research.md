# Deep Research — the contracts

**State:** registered, parked by default. The executors are in the worker's default registry and
the API route calls the service; a run parks unless `AIA_DEEP_RESEARCH_ENABLED` composes a
runtime. The live search routes are fee-free Czech/English Wikipedia and priced Brave
(Class C, `AIA_DEEP_RESEARCH_WEB_SEARCH`), with Common Crawl's priced URL index and fee-free
archive beside them (`AIA_DEEP_RESEARCH_COMMON_CRAWL`); a priced route runs only once its
organization has signed off (§ 9, ADR 0022), and nothing turns Brave on until its SSM keys are
set (DR-2). Everything else runs on recorded exchanges. The engine is frozen after #166 (ADR 0021).
Decision records: [ADR 0017](adr/0017-deep-research-external-retrieval.md) (*Proposed*,
amended 2026-09-27) for retrieval, grounding and evidence; [ADR 0021](adr/0021-deep-research-purpose-target-lineage.md)
for the two purposes, the typed target and the frozen lineage. Plan and chunk state:
[deep-research.md](../../.planning/plans/deep-research.md) and
[deep-research-web-search.md](../../.planning/plans/deep-research-web-search.md).
Code: `packages/aia_core/src/aia_core/domain/deep_research/` (pure);
`application/web_retrieval.py` (the gate), `application/deep_research.py` (the runs),
`infrastructure/web_retrieval.py` (fetcher and recorded doubles);
`apps/executors/src/aia_executors/deep_research/` (the steps), `deep_research_runtime.py`
(production-shaped composition), `deep_research_recorded.py` (local and test only).

This document is the handoff for whoever connects Deep Research to the rest of the
Study: the shapes it publishes, the rules each consumer must keep, and what it
needs from the platform. Where this document and the code disagree, the code's
tests decide and this document is stale.

## 1. What a run does

`plan → investigate → merge → verify → synthesize → publish`, one Study-scoped
workflow (`deep_research`, `domain/deep_research/workflow.py`) whose engine request is frozen
from one Design Revision and filed under `DEEP_RESEARCH`. With `AIA_DEEP_RESEARCH_FAN_OUT` the
`investigate` step hands each track to a step of its own and joins them
([deep-research-fan-out.md](deep-research-fan-out.md)); with `AIA_DEEP_RESEARCH_AGENT_DIRECTED`
and `AIA_DEEP_RESEARCH_LEAD` investigators and a lead researcher direct the web tracks.

**Not a stage: two checkpoints** (ADR 0021). Every new run is started from a
`DeepResearchRunSpec` (`integration.py`): its **purpose** (`DESIGN_RESEARCH` before the
methodology freeze, advisory, proposals only; `INTERPRETATION_RESEARCH` over immutable results,
no mutation authority), its **target** (a closed `ResearchTargetRef`: a Design Revision; a
question's or battery object's aggregate result; an analysis module; a battery's Sociomap, one
of its objects, or a pair), and its **frozen lineage** (the revision's content SHA256; for
interpretation the producing research run's `compile`, `run`, `aggregate` and target artifacts by
id and SHA256). The engine request inside it is unchanged, so its fingerprint and every track's
are unchanged; the spec's own fingerprint keys the run, and a design run and an interpretation
run over one engine input share the engine's reusable work. `DeepResearchProvenance` names the
sealed bundle (artifact id, row SHA256, seal) beside purpose, target and lineage, without
touching the bundle. A run stored before ADR 0021 reads `legacy-unversioned`.
**Interpretation Research enqueues and executes since chunk 30** (PR #193, `67af44e`; OI-88
closed). Its engine request's subjects are the target's *mission*, built by code
(`domain/deep_research/interpretation.py`, `interpretation_mission`) from the pinned `compile`
specification and the Design Revision the producing run executed; the brief, questionnaire,
knowledge and client terms are frozen from that revision as for a design run. Every subject's
`origin` is `interpretation:<KIND>:<entity>`, so the bundle says what each track researched; the
origin is in no track fingerprint. **No respondent number enters a mission**: a subject names
what a result is about, never a share, mean, coordinate or relation strength.

| Target | Subjects |
|---|---|
| `RESULT_QUESTION` | one `QUESTION`: the survey question's text, framed as the context and benchmarks of its answer |
| `RESULT_BATTERY_OBJECT` | one `OBJECT`: the object's label; one `QUESTION`: the battery's question about it |
| `ANALYSIS_MODULE` | `research_questions`: each research question of the design; `objects`: each tracked object; any other module: one `QUESTION` framing the study's goal for it |
| `SOCIOMAP` | one `OBJECT` per object of the battery; one `QUESTION`: what links them for its family |
| `SOCIOMAP_OBJECT` | one `OBJECT`: the object's label |
| `SOCIOMAP_RELATIONSHIP` | one `QUESTION`: what connects the two objects; one `OBJECT` for each |

The route is `POST /api/v1/studies/{study_id}/deep-research/runs/interpretation` (`target`,
`preset_name`, `channels`, `confirm_cost_usd`, `title`): 201 with the run, 200 when the same
spec's run exists, 404 for a target that is not this Study's, 422 for an entity its artifact
does not hold, a design target, or nothing to research. `_enqueue`, the one enqueue boundary,
refuses a spec whose request is not its own purpose's (`require_interpretation_mission`):
an interpretation request holds only its target's mission, and a design request carries no
interpretation origin, else 409 `interpretation_mission_mismatch`. A retry of an interpretation
run re-freezes the stored target and answers 409 `lineage_changed` when a pin no longer reads as
pinned; it never re-chooses its target. `interpretation_not_ready` no longer exists. Neither purpose
writes a design or a deterministic artifact (`require_may_write`, a `layer_check` rule).

| Phase | Who decides | What it produces |
|---|---|---|
| plan | **code** picks the subjects and tracks; the planner model proposes sub-questions and queries for the web tracks it is shown; code refuses a plan that skips or invents a track | the plan: tracks, fingerprints, reuse, allowances |
| investigate | **code** classifies and sends each query, fetches, snapshots; the investigator proposes findings with verbatim quotes; code grounds each | one artifact per track |
| merge | **code**: declared source scores, dedupe, confirmation, the leakage rule | candidates, quarantine |
| verify | the verifier model judges each candidate against its own excerpt | accepted / quarantined |
| synthesize | the synthesizer writes a brief from accepted evidence only; **code** checks every citation and number | the brief, with exclusions |
| publish | **code** | the sealed evidence bundle |

## 2. The shapes (`contracts.py`)

All closed (`extra="forbid"`) and frozen.

- **`ResearchSubject`** — a research question, a tracked object, or a question ×
  object cross. `key` is `q-`/`o-`/`x-` + 12 hex of its kind and normalised text
  (`subject_key`), so the same question is the same subject in every pass, wherever
  it sits in the design. `origin` says where it was read from.
- **`ResearchTrack`** — one subject on one channel (`INTERNAL` or `WEB`).
  `track_id` = `DRT-<I|W>-<subject key>` (stable across passes); `fingerprint` =
  SHA256 of everything its result depends on (§4).
- **`DeepResearchRequest`** — what a run is frozen to at enqueue: design revision id,
  preset, channels, `BriefDigest`, subjects, the questionnaire as the leakage screen
  reads it (`ScreenQuestion`), `FrozenKnowledge`, client terms. It carries no scope:
  scope comes from the lease.
- **`SourceSnapshot`** — a fetched page: `snapshot_id` = `SNP-` + 24 hex of its
  normalised text (content-addressed), requested/canonical/final URL, redirects,
  title, `retrieved_at`, HTTP status, content type, raw and text SHA256, byte size,
  `truncated`, adapter, provider request id, `retrieval_mode` (`RECORDED` | `LIVE`),
  and every prompt-injection pattern detected.
- **`KnowledgeSource`** — one approved Client Knowledge item at one revision
  (`ref` = `KNW-…@<revision>`), its normalised text, data class, lineage,
  `truncated`, `public`.
- **`EvidenceItem`** — a grounded finding: claim, verbatim quote and its span in the
  source's normalised text, source ref/kind/URL/title, evidence type, and what the
  investigating agent said about it (`agent_outcome_overlap`,
  `agent_recommended_use`, `agent_source_quality` — recorded, never decisive).
  `evidence_id` = `EV-` + 16 hex of (track fingerprint, source, quote, claim).
- **`QuarantinedEvidence`** — a finding kept in the log with one
  `QuarantineReason`: the legacy four (`target_outcome_overlap`,
  `deterministic_target_overlap`, `low_source_quality`,
  `no_independent_confirmation`) and AIA's (`ungrounded_excerpt`,
  `citation_outside_track`, `number_not_in_quote`, `source_contains_instructions`,
  `unsupported_by_verifier`, `overstated_by_verifier`, `unverified`,
  `questionnaire_leakage`).
- **`StopReason`** — exactly one per track: `depth_target_met`, `saturated`,
  `queries_exhausted`, `budget_exhausted`, `all_queries_refused`,
  `no_knowledge_matched`, `single_pass`, `web_retrieval_unavailable`,
  `search_route_refused`, `model_route_refused`, `channel_not_requested`,
  `tool_outcome_uncertain`, `track_limit`, `plan_incomplete`, `context_too_large`.
- **`EvidenceBundle`** (`bundle.py`) — the published result: versions, request
  fingerprint, preset and its status, subjects (crosses included), `TrackRecord`s
  (status, stop reason, the refusing gate in words, reuse, queries with their class
  and decision, snapshots, counts and costs), the coverage matrix and the question ×
  object grid, accepted and quarantined evidence, `SnapshotRef`s, the brief,
  `quality_status` (`GROUNDED` | `PARTIAL` | `NO_EVIDENCE`), `origins`
  (`RECORDED_FIXTURE` | `LIVE_RETRIEVAL` | `CLIENT_KNOWLEDGE`), `fictional_client`,
  `client_facing: false` always, and `sha256` over the rest (`verify()`).

## 3. The rules code keeps

**Grounding** (`grounding.py`, `aia-grounding-1`). A finding is admissible only if
its source is one the same track retrieved (`citation_outside_track`), its quote —
20 to 800 characters after NFKC, quotation-mark and dash folding and whitespace
collapse — occurs in that source (`ungrounded_excerpt`), and every number in the
claim is in the quote (`number_not_in_quote`). A source whose text matches a
prompt-injection pattern is kept for provenance and its findings are quarantined
(`source_contains_instructions`).

**Source quality** (`sources.py`, `aia-source-table-1`). The class comes from the
host of the fetched page through declared tables (official statistics, government
and regulators, peer-reviewed, academic, preprint, industry research, media, forum
and social), or from being approved Client Knowledge. An unknown host scores lowest
(0.2); an undated or future-dated page loses the recency benefit; the threshold is
the unit's 0.55. The agent's own score is never an input. The numbers are a proposal
for the methodology owner.

**Query class** (`classification.py`, `aia-query-classifier-1`). The most restrictive
of: the class of the context the proposing call saw; any client term (client and
study names and slugs, every non-public approved ENTITY/TERM), matched across case,
diacritics, German transliteration, punctuation and spacing (→ at least B); a
five-word run shared with Class A text the run holds (→ A). **Nothing lowers a
class**: a paraphrase with every name removed keeps the class of what it was written
from. A design is Class C only for a client the operator declared fictional
(`agents.design_class`, the design jobs' rule).

**What a fetch may reach** (`web.py`). `http`/`https` on default ports, no
credentials, no internal hostnames, every resolved address globally routable
(private, loopback, link-local and the metadata service, CGNAT, multicast, reserved,
IPv4-mapped forms refused), a host that resolves to nothing refused, the same checks
on every redirect hop (at most 3); kept types and their caps (`MAX_BODY_BYTES_BY_TYPE`):
`text/html`, `text/plain` and `application/xhtml+xml` at 2 MB, PDF at 20 MB, XLSX at 10 MB and
CSV at 5 MB, the documents read in parts (`documents.py`).

**Merge and verification** (`merge.py`, `aia-merge-1`). Declared score, then dedupe
(same source, claim similarity ≥ the unit's 0.42), then independent confirmation
from a different source as a confidence bonus (+0.1 each, at most two, capped at
0.98) — never the gate. Only a verifier verdict of `supported` makes accepted
evidence.

**The leakage rule** is the unit's, exactly (`legacy.py`, EXACT against captures of
the vendored `research_context.py`; gate `research.design/deep-research-leakage-merge`).
In AIA it bars a finding from respondent context rather than discarding it: a finding
that reports a survey question's answer — by the agent's label or by the
deterministic screen against the questionnaire the design holds — stays in the
bundle as alignment evidence for the researcher, marked `EXCLUDED` for respondents.

**The brief** (`synthesis.py`). Findings may cite accepted evidence only
(`citation_not_accepted`), must name a subject of the run (`unknown_subject`), and
may write only numbers their cited quotes carry, except a subject's own range as the
subject writes it (`number_not_in_cited_evidence`). A failing finding is excluded
with its reason; a summary with an unbacked number is withheld; accepted evidence
with no surviving finding makes the brief `BLOCKED`.

## 4. Tracks, fingerprints and reuse (`planning.py`)

Subjects: research questions (`research_plan.research_questions`, or the goal when
there are none yet), then tracked objects (`research_plan.tracked_sets[].objects`,
`tracked_objects`, object batteries in `sections`), then approved ENTITY items the
brief names. One track per subject per requested channel, questions first, internal
before web; crosses only when the preset opens them.

A track's fingerprint covers its subject, channel, depth preset, brief digest, model
policy and prompt version, the grounding and classifier versions, and **either** the
retrieval identity (web: route ids, recorded or live, adapter ids, prices) **or** the
frozen knowledge (internal). It does not cover the other subjects. Consequences, each
tested (`test_deep_research_planning.py`):

- adding an object in a later pass leaves every existing track's fingerprint, and so
  its stored result, valid; only the new object's tracks are researched;
- a knowledge approval changes the internal tracks only; a change of retrieval (a
  recorded route replaced by a live one) changes the web tracks only;
- a changed brief or depth changes every track.

**Depth presets** (`PRESETS`, status `PROPOSED_DR5`): `QUICK`, `STANDARD`, `DEEP`,
each a set of visible numbers — queries per web track, pages per query, evidence
target, knowledge items per track, crosses, saturation window, track limit, run
limits on searches and fetches, verification batch size. A run names one; there is no
default. Tracks beyond the limit are recorded as `track_limit`, never dropped.
`allocate` splits the run's search and fetch limits equally across web tracks (the
remainder to earlier tracks); `stop_reason` ends a track on the depth target,
saturation (no new grounded evidence in the last *k* rounds), its budget share, or
its queries, in that order.

## 5. Internal retrieval (`knowledge_access.py`)

The authorized interface is: **the knowledge frozen at enqueue** from
`ClientKnowledgeRepository.for_study(scope)` under an issued `StudyContext` — the
study's own client's approved items, nothing else — turned into `FrozenKnowledge` by
`freeze_knowledge` (at most 200 items, 128 KB of text, 16 000 characters per item;
omissions named, truncation flagged), and **`retrieve`** over it: lexical, folded,
title words counted double, nothing returned for a subject no item mentions. There is
no live knowledge read during a run and no model chooses what is read.

Classes by kind: SOURCE, DOCUMENT, DATASET, ARTIFACT → Class A; FACT, FINDING, TERM,
ENTITY, DIMENSION, AUDIENCE → Class B. DATASET, ARTIFACT and FINDING carry the named
lineage `unclassified-client-knowledge`, which the licence gate refuses (as for the
design jobs) until lineage is recorded. No route is approved for Class A or B today,
so internal tracks are refused before any call on the current Class C route.

## 6. What consumers may take (`quarantine.py`)

| Consumer | Function | Rule |
|---|---|---|
| Fieldwork (respondents) | `respondent_context(bundle, final_questionnaire)` | Accepted, respondent-eligible evidence only, **re-screened against the final questionnaire** (`questionnaire_leakage`), at most 8 blocks in the unit's `KontextovyBlok` shape, role `EXTERNAL_CONTEXT`. Refuses a recorded bundle unless the caller passes `allow_recorded=True` (tests, workbench). |
| Research design | `design_input(bundle)` | Every accepted finding per subject with quote, source, class, confidence and whether it may reach respondents; subjects with none are gaps. External context, never a measurement. |
| Analysis and report | `analysis_context(bundle)` | External context only; `admissible_as_panel_claim` is always false. A number enters a result only as an `AdmittedClaim` from the population. |
| Anything client-facing | `require_live_evidence(bundle)` | Refuses recorded fixtures and fictional clients. A person still signs off. |

### Combined research report (PR #237)

The results screen's literature panel starts `INTERPRETATION_RESEARCH` over its
pinned `research_questions` analysis, filters reviews to that research run, shows
accepted findings and captured sources, and lets the researcher select a review
explicitly for the report. Start and retry keep the existing cost-confirmation
boundary; selecting a report does not change a study's budget.

`GET /api/v1/studies/{study_id}/research/runs/{run_id}/report/context/download`
requires `deep_research_run_id` and edit permission. It returns fresh branded DOCX
bytes after `application/contextual_report.py` validates the owned runs, completed
status, exact frozen lineage and governed bundle. It preserves the eight admitted
analysis chapters and snapshots of the frozen canonical map. The original report
artifact remains immutable. Pending, foreign, mismatched, corrupt or ungoverned
inputs are refused; export calls no model and writes no report artifact.

The literature chapter publishes only checked synthesis and accepted findings,
separate L source references with available source/capture dates, structured
measures where supported, interpretation/comparability guidance and actual gaps.
It describes a targeted review, not an exhaustive systematic review. `NO_EVIDENCE`
exports an honest coverage limitation; a completed workflow does not imply usable
literature or benchmarks. External numbers never become respondent findings or
inputs to map geometry. Anchors: `application/contextual_report.py:53 @ 96e4f58f`,
`routers/research.py:1005 @ 96e4f58f`; tests: `test_an_empty_bundle_reports_a_gap_instead_of_inventing_a_review`
and the interpretation-target report journey in `test_analysis_executor.py`.

## 7. The cost contract for tools (`tooling.py`, `application/web_retrieval.py`)

Search and fetch are bracketed like a model call: `ToolMeter.reserve` →
`dispatching` (a `DISPATCHED` `ToolUsageEvent`, durable before the call leaves) →
send → `outcome` (`SUCCEEDED` / `FAILED` / `UNCERTAIN` / `REFUSED`). `ToolRoute` binds an
ADR 0008 route to an adapter, a retrieval mode and a price; a recorded route must declare a
price of zero. `InMemoryToolLedger` never charges a study's budget
(`charges_study_budget = False`).

**The gate** (`RetrievalGate`) is the only way a query or URL leaves, in this order:
classify (a URL from a public context, raised by client terms) → refuse Class A → `evaluate_egress`
for the class on the tool's own route → refuse a priced route unless the meter charges the
study (`tool_metering_unavailable`; the worker's `StepToolMeter` does, so in a worker a priced
call is held against the study's budget through `reserve_tool_budget`, marked dispatched before
it leaves and settled once at what the gate charged) → reserve → journal the dispatch → call → journal the
outcome. Every refusal is recorded with its reason; nothing is rerouted. What a call is
charged is decided there, never in AIA's favour: a provider that answered (success or error)
costs the route's price; a failure that sent nothing costs nothing; an uncertain call, and a
page refused after its dispatch (a later hop), cost the ceiling. `refusal_for_class` answers,
without journaling, whether any query of a class could leave.

**In a worker** (`aia_executors.deep_research.StepToolMeter`) every entry is a lease-fenced
progress event named by `TOOL_EVENT_KINDS` (`deep_research_tool_dispatched`, …); the dispatch
is written after a checkpoint and before the call, so a cancelled, stopping or lease-less step
stops first. The journal holds the request's fingerprint, never the query text. Its ceiling is
zero: only a free call can be reserved at all. Recovery reads a model call's dispatch mark but
not these entries, so a step that sends calls builds its meter with `StepToolMeter.resuming`:
it adopts every tool entry the step's earlier attempts journaled (a track's allowance spans
attempts), and a `DISPATCHED` entry with no outcome -- its process died, or lost its lease, in
flight -- is closed `UNCERTAIN` at its ceiling and journaled so. Its track then ends
`INCOMPLETE` without sending anything again. A meter built plainly refuses to dispatch.

**Adapters state their own mode.** A `SearchAdapter` and a `FetchTransport` each say
`RECORDED` or `LIVE`, and a recorded one cannot say anything else; `WebRetrieval` refuses an
adapter whose mode is not its route's, so a replay cannot stand behind a live route.

## 8. Execution (`apps/executors/src/aia_executors/deep_research/`)

A run is enqueued by `DeepResearchRuns.start(design_revision_id, preset_name, channels)`
(`application/deep_research.py`): the request is frozen under the issued `StudyContext` --
the revision, subjects, brief, questionnaire, the Study's own client's approved knowledge
(`ClientKnowledgeRepository.for_study`) and the client terms (client and study names and
slugs, non-public ENTITY/TERM items) -- and the graph is created on the Study's owned design
project with the request's fingerprint as the idempotency key. A run, its bundle
(`bundle`, seal verified) and its snapshots (`snapshot`, only those the bundle cites) are
found only through the Study and the run's type. `retry` starts a failed or cancelled run
again, frozen afresh; nothing stored is bought twice.

| Step | Asks | Stores (`ARTIFACT_TYPES`) | Keyed by |
|---|---|---|---|
| plan | the planner, once, for the web tracks not already stored -- and only when a query of the design's class could leave | `deep_research_plan`: `PlanRecord` (tracks, reuse, planned queries, blocked tracks with their gate, allowances, versions) | this run |
| investigate | per track: the internal investigator once over the knowledge `retrieve` found; the web investigator once per round over the round's new pages | `deep_research_track`: `TrackResult` per track; `deep_research_source_snapshot` per page; `InvestigationRecord` | a COMPLETED track: its fingerprint (any later run); otherwise this run; a snapshot: its content address |
| merge | -- | `MergeRecord`: candidates and every quarantined finding | this run |
| verify | the verifier once per batch (a track's candidates, `verify_batch` at a time) | `VerificationBatch` per batch; `VerifyRecord` | a batch: what the verifier is shown (any later run); the record: this run |
| synthesize | the synthesizer once, when anything was accepted | `SynthesisArtifact` (the checked brief) | what it was shown (any later run) |
| publish | -- | `deep_research_bundle`: `{"bundle": EvidenceBundle}` | this run |

With `AIA_DEEP_RESEARCH_FAN_OUT` on, `investigate` is a join: every track that would make a call
is handed out to a step of its own (`deep_research_investigate_track`, any worker) and the step
runs again to take what they stored; hosts are paced and model requests bounded across worker
processes. Nothing it finds or stores differs. See
[deep-research-fan-out.md](deep-research-fan-out.md).

The shapes are `domain/deep_research/steps.py`. `tally` counts what the run did and spent from
them -- a reused unit costs it nothing -- into the bundle's `counts` (tracks, reused, researched,
blocked, incomplete, beyond the limit, model requests, searches, fetches, refused queries,
snapshots, batches and reused batches, accepted, quarantined) and `spend_usd` (`model_usd`,
`tool_usd`).

A web track runs round by round: the stop rule is checked before each query; a refused query
and a known search failure do not count as rounds; each result is fetched once per track within
the track's allowance and snapshotted; one investigator request reads the round's new pages; an
uncertain search or fetch ends the track `INCOMPLETE` at once (never retried): nothing more is
sent for it, not even the investigator request over pages the round did capture. A track whose
queries were all refused is `BLOCKED` (`all_queries_refused`). Every request is preflighted
first, and a refused one (`model_route_refused`, `context_too_large`) spends nothing. Each step
re-checks that the composition's versions, policy and retrieval are the ones the plan recorded
(`composition_changed`), that the request matches the step's fingerprint (`request_altered`)
and that its Design Revision is the held Study's (`design_not_in_scope`).

## 9. Compositions and configuration

| Composition | Built by | What a run does |
|---|---|---|
| none | `deep_research_registry(runtime=None)` | parks at plan (`RUNTIME_UNAVAILABLE`, `deep_research_unconfigured`); nothing read or sent |
| production-shaped | `deep_research_runtime(settings)` (`deep_research_runtime.py`) | with no search route (`AIA_DEEP_RESEARCH_WEB_SEARCH=off`, or unset with the Wikipedia switch off), web tracks `web_retrieval_unavailable` without a planner call; `wikipedia` or `brave` sends Class C queries to that route only (`deep_research_live.py`), and `AIA_DEEP_RESEARCH_COMMON_CRAWL` adds the archive rung; internal tracks refused by the gateway on a Class C route; a completed bundle that says so |
| recorded | `recorded_runtime(...)` (`deep_research_recorded.py`) | the whole path over a recorded exchange file; refuses unless `AIA_ENV` is `local` or `test`; `layer_check` keeps it out of the API, the worker, the other executors and deployments |

Configuration: **`AIA_DEEP_RESEARCH_ENABLED`** (strict `true`/`false`, default off). On, it
requires `AIA_AI_RUNTIME_ENABLED` and `AIA_AI_RESEARCH_AGENTS_ENABLED` -- the capabilities it
names (`RESEARCH_REASONING`, `CRITIC`) are bound only then -- and uses their output limit and
their per-request reservation (primary plus one repair, checked there against the model's
ceilings); the worker refuses to start otherwise. `AIA_DEEP_RESEARCH_WEB_SEARCH=brave` composes
the Brave adapter (`web_retrieval_brave.py`): it needs the public fetch's contact,
`AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000`, `…_PRICES_AS_OF` and `…_BRAVE_API_KEY`, read as a
reference and never kept, logged or put in a route; the Wikipedia route needs no key.
`AIA_DEEP_RESEARCH_COMMON_CRAWL` composes the Athena index and the archive
([deep-research-common-crawl.md](deep-research-common-crawl.md)). The develop runbook is
`deploy/develop/README.md` § *Deep Research on Brave search* and § *Deep Research on Common Crawl*.

**Wikipedia search scope and language** (PR #237). The public composition's
`wikipedia-cs-en-search-2` adapter implements language-aware search with separately
host-pinned Czech and English transports. An unsupported or unconfigured language
is refused before dispatch; an English request is never silently sent to the Czech
index. The source table is `aia-source-table-1+wikipedia-public-2`, investigator
prompt 5. `agent_directed.py` tells the investigator the active encyclopedia scope;
it starts with concise topic names and follows original literature links before
proposing evidence. This is encyclopedia search with public-page retrieval, not a
whole-web academic search service. Broader paid search still needs a verified
provider plan/storage entitlement and the organization's approved settings.
Anchors: `infrastructure/web_retrieval_live.py:517 @ 96e4f58f`,
`deep_research/agent_directed.py:266 @ 96e4f58f`; English routing and pre-dispatch
refusal tests in `test_web_retrieval_live.py`.

**Settings a run is sized and gated by** (ADR 0022). A run pins its organization's effective
settings at enqueue (`settings_pin`); its model requests and its cost ceiling are sized by the
request limits and route allowances it pinned, never above the code's, and the plan records the
limits for the steps after it (`PlanRecord.request_limits`). Live needs approval for a **priced**
live route (`ToolRoute.needs_sign_off`); the fee-free routes (Czech/English Wikipedia, the public fetch,
the connectors) are exempt by the owner's decision of 2026-10-09. Enqueue answers 409
`live_settings_unapproved` with `missing` and `routes`; the worker's plan step parks with the
same reason before anything is asked. The recorded exchange file's format is in
`deep_research_recorded.py`; its SHA256 is in the adapter ids, so a changed recording changes
every web track's fingerprint.

## 10. What the integrator registers (Job 6)

Items 1–3 are done: `DeepResearchRuns.start` is the entry point (`start_interpretation`
exists and is refused at the enqueue boundary until chunk 30, OI-88), the type built from `deep_research_steps()` rather than a `WORKFLOW_TYPES`
template; `deep_research_registry(..., runtime=deep_research_runtime(settings))` is in
`aia_executors/registry.py`; and `routers/deep_research.py` serves start, get, list, events,
cancel, retry, bundle, snapshot and provenance, a corrupt read answering 409 through
`artifact_corrupt` (OI-77). What remains:

4. The generalized metered ledger (a migration), so `ToolMeter.charges_study_budget` can be
   true and tool spend reach the study's budget; then `EXTERNAL_RETRIEVAL` in `ToolRegistry`.
5. The consumers: `respondent_context` at compile, `design_input` in the design jobs,
   `analysis_context` in analysis and report, each after `require_live_evidence` where the
   output is client-facing.
6. OI-77's worker half reaches these steps: a corrupt upstream record or reused unit fails the
   step `UNKNOWN`, its `CORRUPT` mark rolls back with the step's transaction, and every later run
   that plans the same unit fails the same way (reproduced; `.planning/open-items.md` OI-77).
   When that item's failure class and recompute decision are made, the fix goes into `_Step`
   (`deep_research/_shared.py`) as well as the other executors.

## 11. The recorded acceptance journey

`pytest apps/executors/tests/test_deep_research_journey.py` (17 tests, about 9 s) runs the real
worker, gateway, Bedrock adapter, gate and executors over `fixtures/deep_research/web.json`
and recorded agent answers (`agents.json`), for a fictional client with one FACT and one Class A
DOCUMENT approved. Pass 1: 8 tracks; 13 model requests (planner 1, internal 3, web 4, verifier 4,
synthesizer 1), 6 searches, 8 fetches, 7 findings accepted and 6 quarantined -- one per reason:
a number not in its quote, an invented quote, a citation outside the track, a page carrying
injected instructions, a forum source, an overstated claim; a client-named query (Class B) and
one repeating the Class A plan refused before sending; a private address and (in pass 2) a
metadata-service redirect refused mid-fetch; the survey's own answers accepted but barred from
respondents. Pass 2 adds one object: 6 tracks reused, 5 model requests, 3 searches, 2 fetches,
4 of 5 verification batches reused. Also: the production shape (fictional or not) sends nothing;
a real client's design writes no query; unconfigured parks; a foreign or altered request fails
before anything is sent; cancellation between steps, and before a tool call leaves, stops it; a lost
model answer waits for recovery and is not bought again; a changed composition is refused.
**Completion is recorded/offline**: no provider was called and no page was fetched.

## 12. Decisions live search needs

Before any live search or fetch, each of these needs an owner's decision (none is taken here):

1. **The provider and route per data class** (DR-2): which search API, EU processing, retention,
   training exclusion, and terms that allow storing excerpts; whether any route may carry Class B.
   Planned (2026-10-05): Brave Search API for Class C, inside the design of
   [`.planning/plans/deep-research-web-search.md`](../../.planning/plans/deep-research-web-search.md),
   whose chunk 1 records the terms; Class B stays open.
2. **Metering** (handoff 4 above): tool spend held against the study's budget, and whether a
   provider bills an errored request (the gate charges it the price until its terms say).
3. **DR-2b**: whether a code-built digest of a client's design may travel as Class B; until then a
   real client's queries are Class A and never leave.
4. **Client terms**: which ENTITY/TERM items are public, and whether study names (often generic)
   count -- today they do, so a study named after its topic blocks every query.
5. **Fetch**: a live transport that connects to the checked address (DNS rebinding), a user agent
   and robots policy, and whether a fetch through a provider is billed per hop.
6. **Freshness**: how long a live track result may be reused before it is researched again; today
   a fingerprint match reuses it for ever.
7. **Source tables and presets** (DR-5): the host classes, scores and threshold; the default depth.
8. **D6**: a model route for Class A/B, without which internal tracks, and any real client's, stay
   refused.

## 13. Decisions this depends on

| Id | Decision | Effect until made |
|---|---|---|
| DR-2 | A search provider and route per data class, with terms covering stored excerpts | No search provider is composed: Czech Wikipedia (Class C) is the only live route; everything else replays recordings |
| DR-2b | May a code-built digest of a client's design (questions, object names) travel as Class B? | Queries from a real client's design are Class A and never leave |
| DR-5 | Depth presets and default run budget | A run must name a proposed preset |
| D6 | A model route for Class A/B | Internal tracks, and any real client's tracks, are refused before any call |
| — | Which public terms are harmless (ENTITY/TERM `public`) | Every approved ENTITY/TERM is a client term |
