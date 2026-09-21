# AIA product scope

> **This directory is authoritative.** Documents under
> [`docs/archive/original-mvp/`](../archive/original-mvp/) describe a superseded
> product and are not requirements.

## What AIA is

An **internal research operating system**. Roughly five internal researchers use
it to produce paid client studies: they state a client's business question, and
AIA designs a study, runs it against a calibrated synthetic population of the
Czech Republic, analyses the results, and produces a consulting-grade report.

It is not a self-serve SaaS product and not a general analytics tool. Every
design decision follows from that: a small number of expert users, a small number
of concurrent studies, high per-study value, and a hard requirement that client
work never leaks between clients.

## Users

| Who | Needs |
| --- | --- |
| Internal researcher | Design and run studies, interpret results, write reports |
| Internal reviewer | Approve methodology gates and sign off deliverables before a client sees them |
| Administrator | Manage clients, studies, access and budgets |

Clients are **not** users of this system. They receive delivered reports. There is
no client-facing login.

## Isolation boundaries

Client and Study are **first-class isolation boundaries**, not labels.

```
Organization          the AIA team itself
└── Client            a paying client; a hard confidentiality boundary
    └── Study         one engagement; the unit of budget, delivery and access
        └── Project revisions, stages, artifacts, workflow runs, costs
```

Two rules follow, and they are enforced in code rather than trusted to callers:

1. **Every client-derived object resolves to a client and a study.** There is no
   object that "belongs to the organization" but carries client data.
2. **Scope is injected from authenticated application context, never inferred.**
   In particular, **no AI or model-generated argument may determine client or
   study scope.** A model can decide which tool to call; it cannot decide whose
   data that tool reads.

See [`docs/architecture/scope-and-authorization.md`](../architecture/scope-and-authorization.md).

## The two lifecycles

Both are 13 stages. Both are durable: each stage's material inputs are
fingerprinted, so an edit reopens only the affected stage and its dependants.

**Research** — answer a question by fielding a study.

```
Brief → Deep Research → Research Design → Questionnaire → Audience → Dimensions
      → Sample Plan → Fieldwork → Aggregation → Validation → Analysis
      → Report → Delivery
```

**Simulation** — estimate the effect of a change.

```
Brief → Deep Research → Baseline → Scenario Contract → Audience → Dimensions
      → Variants → Worlds → Frozen Results → Comparison → Interpretation
      → Report → Delivery
```

## Capabilities

| Area | What it does |
| --- | --- |
| **Portfolio** | Studies across clients, with state, pending steps and quick resume |
| **Research Studio** | The research lifecycle, brief-first, with AI-assisted design and questionnaire construction |
| **Simulation Studio** | Scenario contracts, independently modelled variants, multi-world runs, frozen results |
| **Results workspace** | Headline answer, findings, segments, filters, respondent explorer, charts, evidence, exports |
| **Sociomapa** | Respondent and object maps over a shared data contract; matrix, comparison and what-if modes |
| **Data Library / Society Intelligence** | Source ingestion → evidence proposal → human approval → dimension materialisation → LIVE population revision |
| **Project memory** | Retrieval over historical studies and approved high-level artifacts |
| **Cost and budget** | Per-study budgets enforced before expensive calls; an immutable AI usage ledger |

## Product rules the system enforces

These are requirements, not preferences. Each is implemented as a backend rule.

**No silent provider fallback.** When a provider cannot serve a request, work
parks in a waiting state and asks. It never moves to a provider that costs money
or changes provenance without an explicit user action.

**No spending past a study budget.** A paid call is checked before it is made.
Over budget means park and ask.

**No LLM for deterministic computation.** Statistics, parsing, transformations,
scoring, aggregation, validation and cost calculation are tested deterministic
software. Agents choose which tools to run and interpret the outputs; they do not
compute the numbers.

**No invented certainty.** Evidence roles travel with the data
(`MEASURED_JOINT`, `CALIBRATED_CORE`, `MODELED_BEHAVIOR_PRIOR`, …). A modelled
figure is never presented as a measurement. Cross-block relationships are not
same-person truth. External predictive validation is `EXTERNAL_HOLDOUT_PENDING`
and the product says so.

**No fake progress.** Real elapsed time, real stage transitions, real counts. No
synthesised percentage the backend cannot know.

**No visualisation mutating research truth.** Dragging a node on the Sociomapa
saves a view override. What-if is a layer over immutable originals.

**Human sign-off before delivery.** Automated reports pass an evidence and QA
gate and still require a person to approve them before a client sees them.

## Durability requirements

A study represents days of work and real money in provider calls. Work must
survive: browser closure, API restart, worker termination, provider failure and
temporary quota exhaustion. Nothing expensive runs inside an HTTP request.

## Out of scope

- Client-facing accounts or dashboards
- Self-serve signup, billing or a plan tier model
- A marketplace or third-party integration surface
- Real-person respondent panels (the population is synthetic by design)
- Local AIA passwords — authentication is Cognito federated to Google Workspace

## Documents

| Document | Covers |
| --- | --- |
| [scope-model.md](scope-model.md) | Organization / Client / Study / membership in product terms |
| [research-lifecycle.md](research-lifecycle.md) | The 13 research stages and what each produces |
| [methodology-contract.md](methodology-contract.md) | Epistemic rules, evidence roles, what fails closed |
