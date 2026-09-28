---
status: in-progress
chunks:
  - "[x] 0. Plan and workflow/reference mapping"
  - "[x] 1. Closed task contracts, versioned prompts, bounded context"
  - "[x] 2. Durable Study-scoped jobs over Design Revisions"
  - "[x] 3. Bedrock executor composition through StepModelCaller"
  - "[x] 4. Native Research screens: enqueue, follow, restore, review"
  - "[ ] 5. Evidence-backed interpretation and reports"
  - "[ ] 6. Deep Research integration"
  - "[ ] 7. Meaningful tests: isolation, duplicates, frozen memory, stale state"
  - "[ ] 8. Documentation, owned PR, deployment, fictional acceptance"
---
# Research agents through the complete Study workflow

Owner: Codex. User direction 2026-09-27: implement the full process, not only respondents.
Base refreshed to develop 043b0dd after PRs #55, #57, #58 and #59 merged.

## Reference and decisions

NPC Panel 18.6.6 archive SHA256 86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216.
Vendored research_designer, research_copilot, analysis_agent, project_memory,
research_context and dotaznik match the supplied archive. Reference code is frozen.

MemoHarness (supplied preprint): use six explicit harness dimensions (context,
tools, generation, orchestration, memory, output validation). This does not
justify automatic production prompt changes. A job freezes its context and harness;
client memory remains scoped, approved and versioned. Offline evaluations precede
promotion. No global bank of raw client trajectories. No model may widen scope,
licence, route, tool permissions or budgets.

## Chunks and acceptance

- [x] 0. Plan and workflow/reference mapping, tracker.
- [x] 1. Closed task contracts, versioned prompts and bounded immutable context.
      Brief analysis, questionnaire build/optimization, audience proposals,
      dimension proposals, design critique, copilot and memory answers.
- [x] 2. Durable Study-scoped jobs over Design Revisions, idempotent creation,
      scoped retrieval/cancellation/results, artifact provenance. Reviewed proposals
      create a revision; stale baselines refuse application. Never change a run's input.
- [x] 3. Bedrock executor composition through StepModelCaller; explicit capability
      bindings, worst-case reservations, preflight and uncertain-cost recovery.
      Disabled capability parks honestly. No legacy provider login or API keys.
- [x] 4. Native Research screens enqueue/follow/restore jobs and review proposals;
      no classic readiness probe. Every applicable AI button has a native action.
- [ ] 5. Evidence-backed interpretation and reports through existing analysis
      admission gates; suppressed/non-evidence material never becomes client claims.
      Fieldwork/aggregation/Sociomap stay integrated with their existing provenance.
- [ ] 6. Deep Research integration with PR #54: scoped knowledge retrieval,
      owned search/fetch tools, frozen sources and grounding/quarantine. An unapproved
      search route remains unavailable; do not call model recollection web research.
- [ ] 7. Meaningful tests: isolation, duplicate submissions, frozen memory, stale
      proposals, unknown fields, unsupported claims, cancel/reload, real worker with
      a recorded adapter, budgets and uncertain delivery. Layer/types/lint and UI flow.
- [ ] 8. Documentation, owned PR, deployment and authorized fictional acceptance.
      PR creation is not deployment; no new live calls without an authorized budget.

## Methodology that remains code

Canonical questionnaires and population field policies are not rewritten by a
model. Audience feasibility, facts, deterministic draws, readiness, numeric claim
admission and Sociomap exposure remain code decisions. Novel dimensions remain
proposals until evidence and a person approve them. Attachments/knowledge are data,
not system instructions. URLs alone are not retrieved sources.

## Completion evidence

Record each completed chunk with measured checks. No claim of full completion
while a screen/action, web route or report acceptance is still unavailable.

### Local evidence, 2026-09-27

Chunks 0–4 implemented locally; no deployment or activation. Native jobs have
closed request/output contracts, immutable context/provenance, guarded acceptance
and eight Research actions. Refreshed develop base: core 2,575 pass / 100 skip;
API 202 pass; worker 43 pass / 6 skip; executors 64 pass (including recorded Bedrock
and local TLS delivery tests); web 758 pass. PostgreSQL design/Research/native-agent/
concurrency: 65 pass, including simultaneous approvals. Types clean across 163
Python source files and the web; layer 62; exposure 7; formatting/lint clean;
tokens/skin current and 170 contrast checks pass. The initial verify stopped at
an outdated registry inventory; after correcting that closed inventory and one
old UI-copy expectation, the remaining gates passed. Browser journey, CI,
publication and live acceptance remain separate; no skipped check is a pass.
Search preparation: Tavily Search/Extract, free evaluation proposed, paid overage
off. Public terms/region/retention/storage findings are prepared for user review;
no account/key/approved route or call. Chunks 5–6 remain required for the full goal.

## Claude continuation handoff — 2026-09-27

User requested immediate publication so Claude can continue. Branch
`feature/research-agents`, base develop `043b0dd`. Backend `c88ec50`, browser
proposal flow `45a2651`; a final listing regression follows them. A new design job
must not hide fieldwork results: filter workflow type before pagination. The test
failed with an empty list before the fix; PostgreSQL Research/native-job follow-up
is 30/30. No new live model call, runtime activation, Terraform or deployment.

Next work in order:

1. Read this plan, `docs/architecture/research-agents.md`, the triad and PROGRESS.
   Read the new PR's latest CI and review findings. This draft is incomplete for
   the full goal; do not equate eight design actions with the full Research flow.
2. Run a real browser journey through enqueue, reload, review, accept and stale
   refusal. Recorded model exchanges and component tests passed; a real browser
   journey has not yet run. Keep local model calls recorded/offline.
3. Complete chunk 5 using `application/analysis.py`, closed analysis drafts and
   existing evidence admission. Do not turn fictional synthetic fieldwork into
   client evidence. PR #58's report model/styles are merged, but its plan says
   no complete DOCX renderer exists yet. Continue the report plan and wire
   interpretation/composition/execution/export through scoped durable jobs.
4. Complete chunk 6 against PR #54's Deep Research plan: scoped knowledge,
   owned search/fetch, separate non-model cost accounting, frozen sources,
   citation grounding and quarantine. Confidential-derived queries retain
   their class regardless of missing keywords. The search service is not selected.
5. The user asked about free search options. Tavily offers 1,000 credits/month
   without a card; Exa offers $10/month plus an onboarding bonus. Proposed
   Tavily free evaluation: six basic searches and two five-URL extraction batches,
   reserve eight credits/job; no paid overage. Bedrock inference remains paid.
   No account, key, terms acceptance or route approval exists. The prepared local
   review/config files are included as `docs/architecture/web-search-service-proposal.md`
   and `docs/architecture/web-search-config-draft.json`; neither is deployed.
   Recheck current official pricing/terms before configuring anything.
6. Preserve approval boundaries: existing ADR 0010 covers fictional Class C
   allowlist only. Design capability has its own off-by-default switch and
   worst-case primary/repair reservation. No confidential Class A/B approval.
   The earlier $2 live fieldwork acceptance budget is already consumed; obtain
   a new explicit run budget before another live model acceptance.
7. Required gates, documentation and final review precede merge/deployment.
   Study working-copy recoveries and legacy backup export remain operational
   approval questions; publishing this PR does not resolve them.

Full-process acceptance still requires chunks 5–8 above. Continue on this branch;
reference source remains frozen. No Claude session trailer was fabricated.
