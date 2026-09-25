# Architecture decision records

One file per decision that would be expensive to reverse or surprising to
inherit. Each records the decision, the alternatives, and what would make us
revisit it.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-fastapi-backend.md) | Keep the validated Python domain engine; FastAPI for the API | Accepted |
| [0002](0002-postgresql-authoritative-store.md) | PostgreSQL is authoritative and is the v0.1 queue; workers claim with `FOR UPDATE SKIP LOCKED` | Accepted |
| [0002](0002-postgresql-authoritative-store.md) | SQS as a non-authoritative wake-up, after a measured trigger and its own ADR | **Deferred** |
| [0003](0003-cognito-identity-boundary.md) | Cognito federated to Google Workspace for authentication; authorization stays in AIA | Accepted |
| [0004](0004-client-study-isolation.md) | Client and Study as hard isolation boundaries with injected scope | Accepted |
| [0005](0005-llm-gateway.md) | **A** — AIA owns the provider-neutral `ModelGateway` contract and its semantics | Accepted |
| [0005](0005-llm-gateway.md) | **B** — LiteLLM as the transport underneath it | **Proposed** |
| [0006](0006-langgraph-agent-execution.md) | LangGraph for agent-internal reasoning; AIA owns the workflow | **Accepted — constrained use** |
| [0007](0007-deterministic-tools.md) | No LLM for deterministic analytical computation | Accepted |
| [0008](0008-eu-data-residency.md) | EU data residency as a frozen invariant; the egress boundary fails closed | Accepted |
| [0009](0009-single-host-develop-environment.md) | One EC2 host under Docker Compose runs the `develop` environment; production compute stays open | **Accepted — develop only; live 2026-09-23** |
| [0010](0010-bedrock-eu-inference-route.md) | Amazon Bedrock, EU geography, as the first governed inference route (`bedrock-eu-primary`, Class C) | **Proposed** |
| [0011](0011-vendor-legacy-product-unit.md) | Vendor the NPC Panel 18.6.6 product as a frozen, regenerated unit at `legacy/npc-panel-18.6.6/`; run it as the baseline and parity oracle on its own gated hostname | **Accepted — develop; unit frozen** |
| [0012](0012-legacy-interface-as-product-facade.md) | Serve the 18.6.6 interface on the product hostname behind AIA sign-in (org owners/admins), and rebuild each feature behind it; supersedes ADR 0011's "never user-facing" | **Accepted — develop only; `/` superseded by 0015** |
| [0013](0013-interface-skin-at-the-facade.md) | Restyle the 18.6.6 interface with an AIA skin: the web client adds one token-generated stylesheet to the document at `/`, only when its SHA256 is the pinned one; the unit stays byte-identical and the oracle hostname unskinned | **Accepted — develop only; now at `/classic` (0015)** |
| [0014](0014-rebuild-the-interface-in-react.md) | Rebuild the interface in React under `/app`, area by area, behind the same gate, over the unit's API through one ledger-checked client; the classic interface stays at `/` until the rebuild covers it, reached by a fragment hand-off that calls its own functions; D-L1 extends to rebuilt screens | **Proposed — develop only; `/` and the spec rule superseded by 0015** |
| [0015](0015-client-first-product-interface.md) | The React AIA client-first shell is the product on develop: `/` → `/app/clients`, Clients → workspace → study → stages; the classic interface is an explicit hand-off at `/classic` and the legacy hostname stays the oracle; `ClientContext` and Client Knowledge (proposals → approval → revision) | **Accepted — develop; supersedes the facade parts of 0012–0014** |
| [0016](0016-research-execution-and-model-transmission.md) | A research run is a workflow run pinned to an immutable, Study-scoped Design Revision; one `research` workflow type with the reference's node keys; steps are deterministic tools shared with agents; fieldwork is a boundary (`ai_runtime` parks until the Agent Runtime, `synthetic_fixture` only in tests/workbench); model transmission fails closed on dataset licence, the determination kept apart from the rule | **Accepted — develop** |

ADR 0005 is deliberately two rows. The gateway contract and the library that might
implement it are independent decisions, and collapsing them into one status blocked
the architecture on a vendor question.

## Status meanings

- **Accepted** — implemented, or committed to and being implemented.
- **Accepted — constrained use** — adopted, but only within a stated boundary. The
  boundary is part of the decision.
- **Proposed** — the direction is agreed but the choice is not yet locked by
  code. Revisit before the phase that depends on it starts.
- **Deferred** — considered and explicitly not adopted now. The ADR records what
  would have to be true to revisit it.
- **Superseded** — replaced; the replacing ADR is named.

## Not decided anywhere, and deliberately so

These come up often enough to be worth naming as open. Nothing in this repository
should read as though any of them were settled:

- **Production compute service.** ECS Fargate and App Runner both remain options. See
  [ADR 0002](0002-postgresql-authoritative-store.md) § Compute. The `develop`
  environment's single host ([ADR 0009](0009-single-host-develop-environment.md))
  is not that decision and must not be read as one.
- **Model provider and hosting.** No provider is *accepted*. [ADR 0008](0008-eu-data-residency.md)
  sets the constraints any candidate must meet; [ADR 0010](0010-bedrock-eu-inference-route.md)
  proposes Amazon Bedrock in the EU geography as the first route and lists the
  checks a human performs before it is accepted.
- **Observability backend.** OpenTelemetry is the instrumentation standard; the
  backend it exports to is replaceable and unchosen.
