---
status: done
chunks:
  - "[x] 1. Domain: NATIVE_PROVIDERS"
  - "[x] 2. /config: aiRuntime.switches and approvedClasses"
  - "[x] 3. The settings document: ai_runtime, ProviderEntry.use"
  - "[x] 4. The Settings UI"
  - "[x] 5. Documents; merged PR #75 at 8017b54"
---
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

- [x] 1. Domain: `NATIVE_PROVIDERS`; the project model's `DEFAULT_*` documented as
      prototype defaults no native run reads -- `df22227`;
      `test_providers_parity.py::test_the_native_runtime_calls_bedrock_and_every_prototype_provider_is_historical`
- [x] 2. `/config`: `aiRuntime.switches` by variable name and `aiRuntime.approvedClasses`,
      both additive to the fields already there -- `7873a57`; `route.test.ts` (6)
- [x] 3. The settings document: `ai_runtime` (with the master `switch`), `ProviderEntry.use`,
      the *ai* group (invariants only), the *ai_history* group, the project cost items out
      of *studies* -- `76bb5a5`; `test_settings_api.py` (19),
      `apps/executors/tests/test_settings_presentation.py` (5: bindings per switch, switches
      read by the worker and handed to both containers, the read-first rule, the signer).
      Mutation check: dropping `CRITIC` from the described design activity fails it with
      the message naming the file to update
- [x] 4. The Settings UI -- `6a6d0dd`, `d941a63` (AI first; the history's sentence seam, both
      seen in the workbench); `lib/ai-runtime.test.ts` (7), `ControlPanel.test.tsx` (17, of
      which 8 new; the three Bedrock-card tests moved there from `ClientFirst.test.tsx` with
      every assertion)
- [x] 5. Documents and tracker: ARCHITECTURE §2, CLAUDE.md map, `ai-runtime.md`
      (§ Providers, § Policies, § Budget control, new § What Settings shows),
      `research-agents.md` § Configuration, the runbook's § AI settings, OI-72 to OI-76
      (OI-76 since fixed by #83, whose entry replaced this branch's copy when `develop` @
      `8c13a11` was merged in), PROGRESS; screenshots of four states at 1440 px and the history at 1024 px

## Evidence

- Screenshots, local only (`make ui-workbench`'s API stand-in and facade, no unit, `next dev`
  restarted per state): develop's state (fieldwork on, design off), runtime off, a design
  switch the worker refuses, both on with the route approved for nothing, the history at
  1024 px. Each capture recorded no page error, no request beyond `/api/v1/*` and `/config`,
  no connected/verified wording, no login or key wording, and no horizontal overflow at
  1024 px.
- Web suite, alternated with `ceee2dc` in the same container: this branch 7 of 8 full runs
  green, `ceee2dc` 4 of 6. Every failure is a native research-agent screen test outrunning its
  15 s budget (OI-76), none in a file this change touches. #83 found the cause, a `/config`
  failure an earlier test left cached, and fixed it.
- No model call, no health probe, no paid inference.

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
