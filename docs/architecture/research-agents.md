# Native Research agent jobs

Merged in PR #63 (`85fa951`, 2026-09-27) and in every develop build since *Deploy develop*
run 31. Off by default (`AIA_AI_RESEARCH_AGENTS_ENABLED`, `deploy/develop/docker-compose.yml:176`);
no live design call is recorded, so nothing here has been verified against Bedrock. The
complete-workflow tracker is
[research-agent-workflows](../../.planning/plans/research-agent-workflows.md); what the other
stages need from these jobs is in [research-journey.md](research-journey.md).

## Actions and boundaries

`research_agent` is a one-step durable workflow over a Study's immutable Design
Revision. The eight closed actions are brief analysis, questionnaire generation,
questionnaire optimization, audience proposal, dimension suggestions, design
critique, design copilot and approved-client-memory answers.

`ResearchAgentJobs` owns creation, scoped listing, cancellation, results and
proposal acceptance. The API exposes these beneath
`/api/v1/studies/{study_id}/research/agent-jobs`; it never invokes a model.
Creation requires editing and running work in an open Study. Cancellation
requires the existing cancellation permission. Cost is returned only with
`VIEW_COSTS`. Browser inputs cannot choose providers, models, routes or authority.
Fieldwork runs and design jobs filter their workflow type before pagination;
new proposal jobs cannot hide a Study's older fieldwork results.

The executor uses the existing `StepModelCaller`, governed gateway, Bedrock
adapter and usage ledger. One logical request permits one bounded schema repair.
The workflow permits one attempt; losing a settled response before persisting
the artifact must not cause automatic paid retries. Unknown delivery enters
recovery. Runtime/route/licence refusals park without a call or reservation.
Artifacts record the design revision, harness, prompt/schema fingerprints,
frozen knowledge revisions, context hash, model/route, request ID and call cost.
Reuse is bound to the input revision as well as context and policy.

## Context and memory

Harness `aia-research-harness-1` has explicit context, tool, generation,
orchestration, memory and output-validation seams. NPC Panel 18.6.6 is the frozen
behavior reference; the supplied MemoHarness preprint informs those seams,
not automatic production prompt changes or a proven AIA performance benefit.

Enqueue freezes the design plus approved Study-visible client-knowledge summaries.
The context is limited to 64 KB, with 20 KB for knowledge and a retrieval window
of 200 items. Omitted IDs are explicit. Oversized design inputs are rejected
before calls; knowledge changes after enqueue do not change that job. Provider,
model, key and run-policy fields are not model context. Knowledge is data, not
instructions. No global client-trajectory bank or online policy adaptation exists.

Only explicitly allowlisted fictional clients without transmitted client knowledge
use Class C. Approved client knowledge makes the request Class A; finding/data/
artifact knowledge with unresolved lineage is refused by the licence policy.
The currently approved Class C Bedrock route therefore does not authorize these
confidential requests. A browser cannot downgrade them.

## Human review and revisions

A completed job stores a proposal. It does not mutate the design. A person reviews
the output before acceptance creates a new revision. `submit_if_current` locks the
Study and refuses a baseline superseded by another submission; every design
submission takes that lock, including first creation. The browser also checks for
local unsaved edits before acceptance.

Canonical library instrument sections are preserved. Custom IDs are assigned by
code and avoid collisions. Audience proposals do not fabricate counts or replace
filters. New dimensions remain evidence proposals and never become approved
dimensions automatically. Advice citations must name approved sources in that
job's frozen context. Advice is not admitted numerical evidence or a client report.

The screens follow server jobs, restore unfinished jobs after reload without
enqueueing again, and offer completed proposals for review. Leaving a page stops
local following, not the server job. Pending local review promises are settled on
unmount. Explicit cancellation uses the native job endpoint and confirmation.

## Configuration

Existing `AIA_AI_*` route, model and price approval remains mandatory. Additional
worker keys, all off/unset by default:

- `AIA_AI_RESEARCH_AGENTS_ENABLED`
- `AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS`
- `AIA_AI_RESEARCH_RESERVATION_USD`

Output allowance must fit the verified model ceiling. The reservation covers two
calls at the model input/context and output ceilings, using verified token prices.
An undersized reservation fails worker startup. `RESEARCH_REASONING` and `CRITIC`
capabilities are bound only when enabled. Settings lists design agents as their
own activity, which needs `AIA_AI_RUNTIME_ENABLED` and this switch, and names the
one that is off; the display is not a health check or invocation grant
([ai-runtime.md § What Settings shows](ai-runtime.md#what-settings-shows)).

## Remaining full-process work

Evidence-backed interpretation/report execution must use the existing analysis
admission pipeline. Free-form advice cannot substitute for it. Synthetic fieldwork
remains non-evidence for client claims; Sociomap remains internal-only.

Deep Research still needs owned search/fetch tools, bounded tool-cost accounting,
frozen retrieved evidence, grounding and quarantine. Tavily Search/Extract on its
free tier is proposed for evaluation; service approval, account/key and applicable
terms are outstanding. Confidential-context queries retain their classification;
absence of listed keywords cannot downgrade them. No search route or live calls
were enabled by this implementation.

## Verification anchors

- `test_research_agents.py`: closed contracts, context freezing/classification,
  source isolation, idempotency, library preservation and approval boundaries.
- `test_research_agent_executor.py`: real worker/gateway/adapter over a recorded
  transport; proposal provenance, review, refusals, uncertain delivery and budget.
- `test_research_agent_jobs_api.py`: scope, permissions, closed inputs and cancellation.
- `test_two_reviewed_design_proposals_cannot_overwrite_each_other`: concurrent
  PostgreSQL approvals; one succeeds and one refuses the stale baseline.
- `useResearchAgents.test.tsx`: review, local stale edits, reload, unmount and errors.
  Native Research screen tests exercise accepted outputs through HTTP fixtures.
