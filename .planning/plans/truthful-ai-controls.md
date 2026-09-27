# Truthful AI controls on Settings

**Status:** in progress · **Owner:** native AI controls (job 1) · **Started:** 2026-09-27 ·
**Branch:** `fix/truthful-ai-controls` from `develop` @ `ceee2dc`

## Problem

`/app/settings` tells a researcher two different stories about what powers AIA.

- The top card says Amazon Bedrock (`apps/web/src/components/aia/GlobalPages.tsx:110-124 @ ceee2dc`),
  from `/config` (`apps/web/src/app/config/route.ts:41-49 @ ceee2dc`).
- The control panel below it, from `GET /api/v1/settings`, says the AI default is
  `claude_code_subscription` under `CLAUDE_CODE_ONLY`
  (`apps/api/src/aia_api/routers/settings.py:204-214 @ ceee2dc`), lists the three prototype
  providers and four prototype policies as if they were choices, one of them
  "předplatné (bez marginální ceny)" (`ControlPanel.tsx:489-517`, `cs.ts:393-402 @ ceee2dc`),
  and offers a project provider policy and a project API ceiling "on the project screen"
  (`routers/settings.py:172-184, 216-220`, `ControlPanel.tsx:135-147 @ ceee2dc`).

None of the second story is true of native execution:

- The worker builds exactly one provider, Bedrock (`apps/executors/src/aia_executors/ai_runtime.py:259-298 @ ceee2dc`,
  `model_document`); models come from that policy, never from a project.
- Native spend is checked against the Study's budget through reservations
  (`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1020-1049 @ ceee2dc`) and
  the gateway's per-call ceiling (`application/model_gateway.py:416-435 @ ceee2dc`); no
  execution path reads a project's `max_api_cost_usd`, `preferred_provider` or
  `provider_policy` (`grep -rn "max_api_cost\|provider_policy\|preferred_provider"` over
  `apps/*/src` and `application/` finds only the generic project repository and schema).
- No screen patches a project (`grep -rn PATCH apps/web/src` is empty), so "mění se na
  obrazovce projektu" points at nothing.

The top card also over-claims. "Připojení spravuje AIA" asserts a connection whatever the
switch says; "povolené pouze pro schválené fiktivní studie" is a fixed sentence, not the
configured approval (`/config` sends `approvedFor` and the card never shows it); and it
cannot say *why* design agents are off, because `/config` folds "the runtime is off" and
"the design switch is off" into one `false`.

## Inventory (every provider, subscription and default-policy control on `/app/settings`)

| Control, as shown on `ceee2dc` | Where | Class | After this change |
| --- | --- | --- | --- |
| "Amazon Bedrock" card: switch, region, model, design switch | `/config` → `GlobalPages.tsx:110-124` | **Active native configuration** | The AI section: each switch by its variable name, region, model, approved data classes; states *configured*, *on*, *off (why)*, *invalid*, *unknown*; never *connected* or *verified* |
| "Připojení spravuje AIA. Přihlášení k poskytovateli ani API klíč se zde nezadávají." | `cs.ts:197` | Stale (subscription era) | Replaced: the worker signs with the server's role; there is no login and no key anywhere; AIA needs no Claude or Claude Code subscription |
| `default_provider = claude_code_subscription` (CODE) | `routers/settings.py:204` | **Historical provenance** (the generic project model's prototype default) | `ai_history.project_default_provider`, explained as the default an older project row reads as |
| `default_provider_policy = CLAUDE_CODE_ONLY` (CODE) | `routers/settings.py:210` | Historical provenance | `ai_history.project_default_provider_policy` |
| `project_provider_policy` (API: `PATCH …/projects/{id}`) | `routers/settings.py:216` | Historical provenance: still writable on generic projects, read by no native run | `ai_history`, said so; no false "on the project screen" |
| `default_project_max_api_cost = 10 USD` (CODE), `project_max_api_cost` (API) | `routers/settings.py:172-184` (group *studies*) | Historical provenance: native spend is the Study budget | Moved to `ai_history`; *studies* keeps the Study budget, the control that is checked |
| Providers vocabulary: Claude Code "předplatné (bez marginální ceny)", Claude API, OpenAI API, Amazon Bedrock | `routers/settings.py:386`, `ControlPanel.tsx:500-508` | Bedrock: native. The rest: historical identifiers in persisted rows, artifacts and the ledger | Each entry carries `use: NATIVE | HISTORICAL`; historical ones listed only under the history heading, with how an old record reads |
| Provider policies `CLAUDE_CODE_ONLY` … `CLAUDE_CODE_THEN_API` | `routers/settings.py:387`, `cs.ts:398-403` | Historical provenance | Listed under history: the prototype's per-project rule; native runs are not steered by it |
| Model capabilities list | `routers/settings.py:388` | Active native (vocabulary) | Kept; each capability shown with the native step that uses it, or "no native step uses it yet" |
| Invariants: one call path, no silent fallback | `routers/settings.py:221-227` | Active native | Kept, plus *configuration is not verification* |
| Workflow `quota_fallback_seconds`, capacity backoff | `routers/settings.py:252-265` | Active native (worker parks) | Unchanged |
| Classic card, "Diagnostika", classic projects link | `GlobalPages.tsx:125-135` | Development/reference (18.6.6 hand-off) | **Not touched**: the phase-out agent's |

## Approach

Three sources, each named on the page, and nothing on the page claims more than its
source knows:

1. **Code** -- `GET /api/v1/settings`, any organization member. What AIA's own runtime
   *is*: the one native provider, how the worker authenticates, each native AI activity
   (the step kind that runs it, the capabilities it asks the gateway for, its harness or
   agent and prompt versions, the switches that turn it on, the actions it offers), the
   capabilities no native step uses yet, and the invariants. All from domain constants;
   tests pin each fact to the domain definitions and to the worker's composition.
2. **Deployment** -- `/config` (the web server's environment, which Compose fills from
   the same values as the worker's). Each switch read with the worker's vocabulary and
   reported by variable name, the source region, the model's inference profile, the
   approved data classes. Nonsecret by construction: no route id, price, fictional
   client list or credential.
3. **Evidence** -- none on this page. It never calls a model, never probes a route, and
   says so. Real calls, their model and cost are recorded on each Study's runs, inside
   the Study's scope.

History is separated, not deleted: every `Provider` and `ProviderPolicy` value stays in
the enums, the database, artifact provenance, the ledger and the parity fixtures. The
settings document marks each provider `NATIVE` or `HISTORICAL` (`NATIVE_PROVIDERS` in
`aia_core.domain.providers`, one definition), and the generic project model's provider
fields and their prototype defaults move to an `ai_history` group that says how an older
record reads.

**The display/configuration contract** -- the exact shapes are in the PR body and in
`apps/api/src/aia_api/schemas/settings.py` (`NativeRuntime`, `NativeActivity`,
`ProviderEntry.use`) and `apps/web/src/app/config/route.ts` (`PublicConfig.aiRuntime`).

### Rejected

- **A "last successful call" read of the usage ledger as verification.** It would be the
  only truthful *verified* signal, but it is an organization-wide query over every
  client's studies: a new cross-study read path next to the work queue, which
  `ARCHITECTURE.md` §3 allows nowhere else. Evidence stays per Study. Raised as a
  question in the PR, not built.
- **The API reading `AIA_AI_*` itself.** The api container receives none of them
  (`deploy/develop/docker-compose.yml:119-145 @ ceee2dc`), and Compose is not this job's
  file. The web container receives the five display keys; `/config` is the place
  ARCHITECTURE §2 already names for that display.
- **Importing the worker's `AIRuntimeSettings` into the API.** `layer_check` forbids
  `aia_executors.ai_` in the API ("the API never builds or invokes the model gateway or
  an adapter"), and it would still validate the API's (empty) environment, not the
  worker's.
- **Renaming `Provider` / `ProviderPolicy` or the `DEFAULT_*` constants.** Persisted rows,
  artifact provenance, the ledger and parity tests carry the values; the job forbids it.
- **A health probe or test call.** Forbidden, and it would spend money to prove a moment.

## Trade-off accepted

Settings can say that the deployment switches a capability on, never that the worker
accepted the rest of its configuration or that Bedrock answered; that evidence lives on
each Study's runs.

## Chunks

- [ ] 1. Domain: `NATIVE_PROVIDERS`; the project model's `DEFAULT_*` documented as
      prototype defaults no native run reads -- `packages/aia_core/src/aia_core/domain/providers.py`,
      a test in `test_providers*.py`
- [ ] 2. `/config`: `aiRuntime.switches` by variable name and `aiRuntime.approvedFor` as
      a list, both additive to the fields already there -- `route.ts`, `route.test.ts`
- [ ] 3. The settings document: `ai_runtime`, `ProviderEntry.use`, the *ai* group
      (invariants only), the *ai_history* group, the project cost items out of *studies*;
      API tests (permissions, no native default spelled as the subscription, facts pinned
      to the domain) and an executors-side cross-check against the worker's composition
      and Compose -- `routers/settings.py`, `schemas/settings.py`, `apps/api/tests/test_settings_api.py`,
      `apps/executors/tests/test_settings_presentation.py`
- [ ] 4. The Settings UI: one AI section (runtime, activities with state and reason,
      invariants), a history section, the top card removed from `GlobalPages.tsx`
      (`set-ai` and its `/config` loader only), state wording as a pure, tested function
      (`lib/ai-runtime.ts`), narrow `cs.ts` patches -- `components/aia/settings/*`
- [ ] 5. Documents and tracker: ARCHITECTURE §2, CLAUDE.md map, `ai-runtime.md`,
      `research-agents.md` § Configuration, PROGRESS, open items for the handoffs;
      screenshots of the representative states

## Ownership and handoffs

Owned here: `routers/settings.py`, `schemas/settings.py`, their tests; `components/aia/settings/*`;
the `aiRuntime` part of `/config`; the `aia.settings` AI keys and `aia.settings.panel` keys
in `cs.ts`; `lib/ai-runtime.ts`.

Shared, edited narrowly: `GlobalPages.tsx` (only the `set-ai` section and the loader that
fed it; the account and classic cards are untouched -- the exact lines are in the PR for
the phase-out agent to agree), `domain/providers.py` (one constant, docstrings),
`lib/api.ts` (the settings types only), ARCHITECTURE/CLAUDE/docs sections named above.

Handoffs (not edited here):
- Research editing still speaks the subscription runtime: `apps/web/src/unit/research/jobs.ts:86-87`
  ("subscription · API $0 · tokeny po dokončení"), `:137` ("Čekám na dostupnost Claude
  Pro."), `unit/research/model.ts:61` (`PROVIDER_FORCED = "claude_code_subscription"`),
  `unit/research/brief.ts:141,176`, `unit/research/store.ts:49` (the run policy written into
  the unit's project), `components/rehome/research/useAiStep.tsx:27`. Classic projects:
  `unit/projects.ts:239,247` ("Claude Code kreditů"), `components/rehome/projects/ProjectCard.tsx:46`.
  Unused rail labels `rehome.navSettingsClaude`, `rehome.statusClaude` (`cs.ts:468,471`).
  Owner: the phase-out agent (research draft serialization, classic screens, legacy
  navigation).
- The generic project API still accepts and stores `preferred_provider`,
  `provider_policy` and `max_api_cost_usd` (`apps/api/src/aia_api/schemas/projects.py:31-35 @ ceee2dc`)
  that no native run reads. Freezing or retiring them is a projects-API decision.

## Review outcome

Filled in when the plan is archived.
