> [!WARNING]
> **SUPERSEDED — NOT CURRENT REQUIREMENTS.**
>
> This document describes the *original* AIA MVP: a single-case workspace that
> produced a copy/paste correlation matrix for **manual** Sociomapping. That scope
> was superseded by the production rebuild brief, which replaces the AIA
> application with the full NPC Panel research and simulation product.
>
> It is retained for historical context only. Do not implement from it, cite it as
> a requirement, or treat it as a backlog.
>
> **Current authoritative documentation:**
> - Product scope — [`docs/product/`](../../product/)
> - Architecture — [`docs/architecture/`](../../architecture/)
> - Migration status — [`docs/migration/status.md`](../../migration/status.md)

---

# AIA — Agent Registry (v0.1)

This is the canonical list of agents, their contracts, and where they fit in the workflow.

## Shared principles
- **Human-in-the-loop** gates are first-class. No silent auto-approval.
- **Traceability by design**: outputs must cite evidence/artifacts.
- **Reproducibility**: datasets + transforms + stats params are versioned.
- **Confidentiality**: client docs/data never leave the controlled environment.

## Workflow gates
- **Gate 1**: Variables approved
- **Gate 2**: Data approved
- **Gate 3**: Stats approved
- **Gate 4**: QA approved

## Agents

### 1) Orchestrator / Case Manager
- Purpose: workflow router + case state manager + gate enforcement.
- Inputs: Intake, Case File, gate states, artifacts registry.
- Outputs: updated Case File, run logs, approval packets.
- Model: small/medium (mostly deterministic).
- Gates: 1–4.

### 2) Business Analysis Agent (Study Designer)
- Purpose: translate assignment + Evidence Pack into Study Spec + Variable Spec.
- Inputs: Case File, Evidence Pack, internal standards/templates.
- Outputs: Study Spec, Variable Spec, data requirements, report outline.
- Constraints: grounded in evidence; variables measurable; no final report.
- Model: medium.
- Gate: 1.

### 3) Knowledge / RAG Agent
- Purpose: retrieve internal precedents; build Evidence Pack with citations.
- Inputs: query + KB + metadata filters.
- Outputs: Evidence Pack (citations/excerpts/tags).
- Model: small.
- Feeds: Gate 1 + QA.

### 4) Data Sourcing Agent
- Purpose: obtain datasets; create Source Log; propose proxies.
- Inputs: Variable Spec + rights/access constraints.
- Outputs: Source Log + staging exports + alternatives.
- Model: small (connectors + structured logging).
- Gate: 2.

### 5) Data Preparation Agent
- Purpose: clean/transform to stat-ready dataset; dictionary + quality report.
- Inputs: staging data + Variable Spec.
- Outputs: stat-ready dataset + Data Dictionary + Data Quality Report + params/hash.
- Model: small (code-first).
- Gate: 2.

### 6) Statistics / Correlation Agent
- Purpose: compute Spearman/Pearson; validate; produce paste-ready matrix.
- Inputs: stat-ready dataset + method params.
- Outputs: NxN matrix with headers; validation summary; exports (xlsx/csv).
- Model: small (code-first).
- Gate: 3.

### 7) Study Writer Agent
- Purpose: draft report sections (CZ) from specs + evidence + results.
- Inputs: Study Spec, Variable Spec, Evidence Pack, stats outputs, templates.
- Outputs: draft report sections + Sociomap placeholders.
- Model: medium.
- Gate: 4.

### 8) QA / Compliance Agent
- Purpose: traceability + consistency + GDPR/PII checks; issue list.
- Inputs: draft report + evidence + artifacts.
- Outputs: issues (S1/S2/S3) + approve/reject recommendation.
- Model: small/medium (deterministic checks preferred).
- Gate: 4.

### 9) Manual Sociomapping SOP
- Purpose: explicit manual checklist + artifact uploads.
- Inputs: paste-ready matrix + dictionary + instructions.
- Outputs: sociomap uploads + final report version.
- Model: none/small.

## Output envelope (recommended)
All agents should emit structured JSON alongside artifacts.

```json
{
  "case_id": "CASE-001",
  "agent": "study_designer",
  "version": "1.0",
  "created_at": "ISO-8601",
  "inputs": { "artifact_ids": [] },
  "outputs": { "artifact_ids": [] },
  "decisions": [{ "id": "D1", "text": "...", "rationale": "...", "citations": [] }],
  "warnings": [],
  "next_actions": []
}
```
