# Handoff prompt: building the Research Lead workbench into AIA

Paste everything below the line into the other model. Give it the repository at
`develop` **plus** the branch `prototype/research-lead-v2` (or at least the folder
`prototypes/research-lead-v2/`). Without the prototype it has no target to work toward.

---

You are working on AIA, a production research platform (FastAPI + SQLAlchemy +
PostgreSQL backend, Next.js 16 / React 19 / Tailwind 4 web client, a worker that
executes research steps, Czech-language UI). You will help turn a **validated
interaction prototype** into a plan and code for the real product. Another engineer
(Claude) will review, integrate and test what you produce; you will not commit or
push anything. Your output is either **analysis documents** or **complete code
files**, exactly as specified per work package below.

## 1. Read these first, in this order, and obey them

1. `CLAUDE.md`, the standing rules. They are not advisory. Pay special attention
   to §1 (shared documents no feature work edits), §4 (plans and the anchor rule),
   §5 (commit-message and PR style, if you draft them), §7 (tests), §8 (never stamp a
   guess, never score unknown as good), §9 (a finding needs six parts).
2. `ARCHITECTURE.md`: layering, boundaries, anti-patterns A1–A10, CI tiers.
3. `AGENTS.md`: framework gotchas.
4. The ADRs in `docs/architecture/adr/`, at least 0004, 0005, 0007, 0015, 0016,
   0017, 0018, 0019, 0020, 0021, 0022, 0023, 0024, 0025.
5. `docs/architecture/research-journey.md`, `research-agents.md`, `ai-runtime.md`,
   `deep-research.md`, `analysis.md`, `sociomapa-deterministic-engine.md`.
6. **The target state:** `prototypes/research-lead-v2/`. Start with its `README.md`,
   then `docs/` (information hierarchy, capability inventory, interaction inventory,
   boundary matrix, decision log), then `src/model/` (types, fixture, terms),
   `src/app/commands.ts` (the command layer) and `src/app/scenarios.ts` (scenarios
   A–M and the exceptions). The prototype is fictional and simulated. Treat it as
   the **specification of behaviour and layout**, never as code to copy wholesale.

Some documents under `docs/` are dated. Where a document and the code disagree, the
code at the commit you were given wins. Record the disagreement; don't resolve it.

## 2. What the target state is

One Study has **one persistent Research Lead conversation** (left, 40 %) beside the
**current stage artifact** (right, 60 %). The Lead coordinates; bounded specialist
workers do bounded tasks; AIA's deterministic code stays authoritative for every
number, gate, revision and budget. There are eleven stages in six phases (Brief, Design,
Questionnaire / Audience, Dimensions, Sample / Fieldwork / Results, Sociomapping /
Analysis / Report). Deep Research is a governed capability outside the sequence.
Proposals appear inline in the artifact and change nothing until a person accepts
them. A stale proposal is refused and offers an explicit rebuild. Manual edits form
an autosaved working copy the Lead notices.

The prototype's `docs/capability-inventory.md` labels every capability as
**implemented / simulated / proposed / unavailable**. Respect those labels: a
*proposed* capability (open-answer coding, audience-assumption evidence, semantic
report edits, respondent replacement, the persistent Lead itself) does not exist in
AIA and needs design, not just code.

## 3. Non-negotiable boundaries

Violating any of these makes the output unusable:

- **Model calls** go only through `GovernedModelGateway.invoke`. Name a
  `ModelCapability` and a `DataClass`, never a model or provider. No provider SDK
  anywhere outside the existing adapters (`make layer_check` fails it).
- **Scope:** every study route is study-scoped (`/api/v1/studies/{study_id}/…`);
  scope contexts come only from `ScopeResolver`; Client Knowledge only through
  `ClientKnowledgeRepository` inside a resolved scope.
- **Evidence:** a number reaches a result only as an `AdmittedClaim`. The Lead may
  read and explain admitted claims. It never writes numbers, admits claims, or
  approves its own assertions.
- **Human gates (ADR 0019):** accepting proposals, starting runs, confirming spend,
  lifting budgets and approving reports are a person's actions. The rule belongs in
  the server-side command, not in the prompt or the UI.
- **Revisions (ADR 0016/0018):** Design Revisions are immutable; a run executes a
  frozen revision; a stale save is refused, never merged silently.
- **Deep Research (ADR 0017/0021/0022):** purpose and target are frozen at enqueue;
  data class is inherited and never lowered; scope, class, route and budget are never
  taken from model arguments.
- **Sociomap:** distance is co-movement of relative preferences, height is the mean,
  and the method register decides status. Display filters never touch the frozen
  artifact; methodology changes are versioned data (ADR 0023).
- No arbitrary SQL or Python execution, no unrestricted tool access, no silent
  proposal acceptance, no new runtime dependency without flagging it as a decision.
- New hot-path behaviour ships behind a kill switch, off by default, with its cost
  (calls, tokens, money, latency) estimated.
- Do not edit: `CLAUDE.md`, `ARCHITECTURE.md`, `AGENTS.md`, `.planning/overview.md`,
  `.planning/open-items.md`, the indexes, or anything under `legacy/`.
- Do not resolve open methodology questions. List them.

## 4. How to report

- **Anchor every claim about existing code** as `path:line @ <commit>` or a test
  name. An unanchored claim must be labelled **hypothesis**. Never invent a file,
  function, table, route or env var. If you need one that does not exist, say
  "**new:**" and give its proposed name.
- State uncertainty plainly. "Not verified" beats a confident guess.
- Use Czech for any user-facing string, and put strings where the web client keeps
  them (find where; anchor it).
- For code: give **complete files**, each preceded by its full repository path. No
  fragments, no "…rest unchanged". Include tests beside them (pytest for Python,
  Vitest for pure TypeScript functions) that a reviewer can run. Match the
  surrounding code's style, comment density and naming. Code must pass
  `mypy --strict`, ruff, `tsc --noEmit` and the layering rules as you understand
  them; say which you could not check.
- For each work package, end with: **what you verified**, **what you assumed**,
  **open questions for the product owner**, **risks**.

## 5. Work packages

Do them in order. Packages A–C are analysis and come first, because the code
packages depend on their answers. If you run out of room, stop at a package
boundary and say where you stopped.

### A. Gap map: prototype → current code (analysis)

For every row of `prototypes/research-lead-v2/docs/capability-inventory.md` and every
interaction in `interaction-inventory.md`, find what exists today:

- **Columns:** prototype capability · existing code (anchored) · status (exists / partial
  / missing / conflicts) · what is missing · estimated size (S/M/L) · dependencies.
- Map the prototype's 11 stages to the web client's current stage track
  (`apps/web/src/components/rehome/research/`, `apps/web/src/lib/app-routes.ts`),
  including where Sample's content lives today (Dimenze, Kontrola).
- List every place where the prototype's behaviour contradicts an ADR or the code.
  Say which should win and why, but mark it a decision for the product owner.

**Deliverable:** `analysis/A-gap-map.md`.

### B. Architecture for the persistent Research Lead (analysis, ADR draft)

Design the Lead as a product feature consistent with the ADRs:

- **Data model:** the conversation, messages, activity records and their link to
  agent jobs and runs, decision records, proposal records (base revision, ops,
  status), working copies. Reuse existing tables where they fit; anchor them.
- **API:** study-scoped routes, request/response schemas, and the error contract
  (anchor the existing one).
- **Execution:** which turns run in the API and which in the worker; how a turn's
  context is assembled (AIA instructions → client → study → revision/run → artifact),
  bounded and inspectable; the `ModelCapability` and `DataClass` it uses; how tool
  use is limited to a closed set of typed AIA commands.
- **Command registry:** a server-side mirror of `src/app/commands.ts`. Give each
  command's name, inputs, permission, human-only flag, idempotency, audit record,
  and the existing service it calls. The UI and the Lead must call the same commands.
- **The "AI Interaction Contract"** per artifact (readable state, visual actions,
  domain actions, required revision, refusals) and stable `data-aia` identifiers.
  Say whether it belongs in the API, the web client or both.
- **Cost:** calls per turn, tokens, money per study-day, latency, kill switch,
  budget line. Also retention and summarisation of long conversations.
- **Alternatives considered** and why they were rejected.

**Deliverable:** `analysis/B-research-lead-adr-draft.md`, written in the shape of
the existing ADRs.

### C. Implementation plan (analysis)

A plan file in the repository's format (see `.planning/plans/README.md` and an
existing plan): front-matter with `status: planned` and a `chunks:` list, then
design decisions. Chunks must be small enough to build, test and merge one at a
time, ordered so every merged chunk leaves `develop` green and deployable (behind
flags where needed). Separate the web-shell chunks, which can ship without the
Lead, from the Lead chunks.

**Deliverable:** `analysis/C-plan-research-lead-workbench.md`.

### D. Web shell, no AI (code)

Port the prototype's layout primitives into `apps/web` as product components that
use the existing tokens (`apps/web/src/design/tokens.json` → generated CSS) and the
existing primitives. Do not duplicate them:

1. The resizable conversation/artifact split: drag, keyboard (arrows ±2 %,
   Home resets 40 %), double-click reset, width persisted per browser, focus modes
   that never overwrite the saved width. Pure logic goes in a `lib/` file with
   Vitest tests.
2. The phase-grouped stage navigator with status glyphs, `aria-current`,
   arrow-key navigation, and the lifecycle overview. Status is derived from existing
   API data; put the derivation in a pure function with tests.
3. The contextual inspector: a back stack, Esc to close, focus returned to the
   opener.

These must work with today's stages and data, without the Lead.

**Deliverable:** complete files plus tests, and a short integration note listing
where they mount (anchored).

### E. Proposal review and stale refusal (code + analysis)

The prototype's inline proposal review (`ChangeBlock`, the proposal bar, coverage
gained/lost/kept, stale refusal with explicit rebuild) mapped onto the existing
`ProposalReview` / agent-job acceptance path
(`apps/web/src/components/rehome/research/`, `ResearchAgentJobs.accept`). First
anchor how base revisions and stale saves work today. Then produce the web
components and any pure diff/coverage functions, with tests. If the server lacks
something, specify it; don't build it.

**Deliverable:** analysis section plus complete files and tests.

### F. Fixture-grade test data (code)

Port the prototype fixture's §18 corrections into the web client's test fixtures
and journeys where equivalent ones exist:

- rank consistency;
- 1–10 values never shown as percentages;
- run revision vs study revision;
- the fictional-data disclosure.

Write Vitest tests over the existing pure functions
(`lib/result-reading.ts`, `lib/run-state.ts`, `lib/report-status.ts`, …) that would
fail if those regressions came back.

**Deliverable:** test files only, plus the failures any of them expose in current
code. Each finding must have the six parts of CLAUDE.md §9.

## 6. What not to do

- Don't build the Research Lead's model turns (package B is design only) until the
  ADR is accepted.
- Don't change methodology, thresholds, approval policy, budgets, routes or
  infrastructure.
- Don't copy Open WebUI code. The prototype re-implemented patterns only; see
  `docs/donor-inventory.md`.
- Don't reformat or "tidy" files you were not asked to touch.
- Don't present simulated prototype behaviour as if AIA already does it.

Begin with a short reading summary: what you read, at which commit, and any
document you could not access. Then deliver package A.
