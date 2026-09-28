# Deep Research — the contracts

**State:** recorded/offline core, not registered, not deployed, not enabled. No live
search or fetch exists; no search provider, route or account is approved (DR-2).
Decision record: [ADR 0017](adr/0017-deep-research-external-retrieval.md) (*Proposed*,
amended 2026-09-27). Plan and chunk state: [deep-research.md](../../.planning/plans/deep-research.md).
Code: `packages/aia_core/src/aia_core/domain/deep_research/` (pure).

This document is the handoff for whoever connects Deep Research to the rest of the
Study: the shapes it publishes, the rules each consumer must keep, and what it
needs from the platform. Where this document and the code disagree, the code's
tests decide and this document is stale.

## 1. What a run does

`plan → investigate → merge → verify → synthesize → publish`, one Study-scoped
workflow (`deep_research`, `domain/deep_research/workflow.py`) pinned to one Design
Revision and filed under `DEEP_RESEARCH`.

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
  `tool_outcome_uncertain`, `track_limit`.
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
on every redirect hop (at most 3), at most 2 MB, only `text/html`, `text/plain` and
`application/xhtml+xml`.

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

## 7. The cost contract for tools (`tooling.py`)

Search and fetch are bracketed like a model call: `ToolMeter.reserve` →
`dispatching` (a `DISPATCHED` `ToolUsageEvent`, durable before the call leaves) →
send → `outcome` (`SUCCEEDED` / `FAILED` / `UNCERTAIN` / `REFUSED`). An uncertain call
is charged its ceiling, never treated as free. `ToolRoute` binds an ADR 0008 route to
an adapter, a retrieval mode and a price; a recorded route must declare a price of
zero. `InMemoryToolLedger` never charges a study's budget
(`charges_study_budget = False`); until the generalized metered ledger exists, a route
with a price must be refused by whatever runs tools.

## 8. Decisions this depends on

| Id | Decision | Effect until made |
|---|---|---|
| DR-2 | A search provider and route per data class, with terms covering stored excerpts | No live search exists; only recorded retrieval runs |
| DR-2b | May a code-built digest of a client's design (questions, object names) travel as Class B? | Queries from a real client's design are Class A and never leave |
| DR-5 | Depth presets and default run budget | A run must name a proposed preset |
| D6 | A model route for Class A/B | Internal tracks, and any real client's tracks, are refused before any call |
| — | Which public terms are harmless (ENTITY/TERM `public`) | Every approved ENTITY/TERM is a client term |
