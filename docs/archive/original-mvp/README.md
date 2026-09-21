# Archived: original AIA MVP (superseded)

> [!WARNING]
> **Nothing in this directory is a current requirement.**

These documents describe the AIA product as scoped **before** the production
rebuild brief. That earlier MVP was a single-case workspace whose deliverable was
a copy/paste-ready correlation matrix that a researcher then fed into Sociomapping
**by hand**.

The current product is an internal research operating system: roughly five
internal researchers producing paid client studies, with Client and Study as
first-class isolation boundaries, a durable 13-stage research and simulation
lifecycle, an AI runtime with cost accounting, and a native Sociomapa workspace.

The two are different products. Reading these as requirements would produce the
wrong system.

## Contents

| Document | Described |
| --- | --- |
| [ROADMAP.md](ROADMAP.md) | v0.1 single-case workspace: login → intake → variables → upload → stats → exports |
| [mvp-scope.md](mvp-scope.md) | "Core workflow #1" happy path, auth foundation, staging deploy |
| [BACKLOG.md](BACKLOG.md) | Milestone v0.1 task list for the correlation paste pack |
| [AGENTS.md](AGENTS.md) | A 9-agent / 4-gate workflow (Orchestrator, Study Designer, RAG, Data Sourcing, Data Prep, Statistics, Study Writer, QA, Manual Sociomapping SOP) |

## What carried forward anyway

A few ideas in these documents were sound and survive in the current
architecture, though not in this form:

- **Human-in-the-loop gates are first-class.** Now expressed as the
  `WAITING_USER` workflow state and the approval model.
- **Traceability by design.** Now artifact provenance and the append-only event
  log.
- **Reproducibility.** Now immutable revisions plus stage input fingerprints.
- **Deterministic statistics.** Now an explicit rule: statistics, parsing,
  transformations, scoring, aggregation, validation and cost calculation are
  tested deterministic software, never model output.
- **Confidentiality.** Now tenant, client and study isolation enforced in the
  repository layer.

The 9-agent registry in `AGENTS.md` is **not** the current agent model. See
[`docs/architecture/ai-runtime.md`](../../architecture/ai-runtime.md) for the
capability-based design (`AgentDefinition`, `ModelPolicy`, `LLMGateway`,
logical capabilities rather than hardcoded model names).

## Why these are kept

Deleting them would lose the record of what the team originally committed to and
why the scope changed. Keeping them unarchived would risk a new engineer or coding
agent implementing the wrong product — which is why every file here carries a
superseded notice.
