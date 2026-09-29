---
status: in-progress
chunks:
  - "[x] 1. Classify model inputs by material and verified provenance (OI-79)"
  - "[ ] 2. Register analysis in the research workflow and expose its outcomes"
  - "[ ] 3. Connect Deep Research workers, API and live retrieval"
  - "[ ] 4. Validate, deploy and complete the authorized fictional acceptance"
---
# Make the native AI research workflow operational

User direction 2026-09-29: both brief → questionnaire → AI respondents → analysis
and Deep Research are essential. The first live acceptance uses entirely fictional
inputs and a **$2 total** AI cap. No unbounded paid calls or client-data route
approval follows from this acceptance authorization.

Base: develop `32ed9a459e5fbe87a7973a3af54924d93e3a5b5c`, deployed and healthy.

## Decisions

- A client or Study marked fictional cannot classify material. Classification
  comes from an operator record bound to the exact content hash and its source.
  Missing classification refuses a model dispatch. Approved knowledge keeps its
  own restrictive class; it cannot inherit Class C from the surrounding design.
- Reuse the existing proposal, respondent, analysis and Deep Research executors.
  Keep their evidence admission, scope, reservation and retry contracts intact.
- Activation is separate from composition. All paid stages retain explicit
  switches and validated limits. The existing archived client stays archived.
- Live retrieval needs a configured source/provider and approval for the actual
  query class. No model recollection is presented as live research.

## Findings

1. `domain/research_agents.py::agent_request @ 32ed9a4` classifies a copied
   design as Class C solely from `fictional_client=True` when no knowledge is
   selected. Reproduce with an attachment carrying an arbitrary context excerpt.
   This can disclose unclassified uploaded or pasted input. Fix: bind an explicit
   material classification to exact input bytes before gateway preflight. Tests
   must prove changed upload/paste/instruction text sends zero calls.
2. `aia_executors/registry.py::build_registry @ 32ed9a4` does not register
   `analysis_registry` or `deep_research_registry`; `workflow_templates.py` has
   neither analysis nodes nor a Deep Research type. Their isolated executor
   tests pass without establishing a deployed end-to-end workflow. Fix the
   composition and exercise the production-shaped registry in recorded tests.

## Validation and acceptance

Record exact commands, outcomes, deployment revision and live costs here as each
chunk finishes. Unknown input, exhausted budget, cancelled work and uncertain
delivery must refuse/park without a second unrecorded paid call. Internal results
from fictional respondents remain visibly synthetic and cannot become client
evidence. The paid acceptance must prove both paths within the shared $2 cap.

### Chunk 1, local verification (2026-09-29)

- PostgreSQL 16: an isolated local database, no host data or model credentials.
- Core: 3,201 passed, 77 reference-dependent skips; API: 259 passed; worker: 56
  passed. Executors: 130 passed after fixing the confidential test fixture's
  synthetic-origin marker. Web: 481 passed on Node 20.20.2.
- Strict mypy: 225 source files; ruff lint and formatting passed. Layering: 70
  rules passed. Exposure guard passed on all staged files, including the new domain module,
  tests, plan and architecture note. Plan front-matter check passed.
- Parity selection: 102 passed, 47 skipped for unavailable reference material.
  This is not proof of the withheld reference-dependent checks.
- Negative tests prove zero network calls for unclassified uploads, pasted text,
  instructions and questionnaires, even with the historical client allowlist.
- No live configuration changed. No paid calls made. Deployment and both complete
  journeys remain open work in chunks 2–4.

## Doc follow-up

Apply finalized registry, workflow, configuration and activation changes to the
shared architecture/map/open-items documents in a separate docs-only PR, including
the verified disposition of OI-79. Do not claim a whole workflow or live search
works before its deployed acceptance succeeds.
