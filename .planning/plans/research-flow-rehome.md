# Research flow, rebuilt — area A4 of the React re-home

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-24
**Decision:** [ADR 0014](../../docs/architecture/adr/0014-rebuild-the-interface-in-react.md) ·
**Parent plan:** [interface-rehome.md](interface-rehome.md) (area A4) ·
**Tools:** [ui-workbench.md](ui-workbench.md)

> **Re-homed under the client (2026-09-24, [client-first-ia.md](done/client-first-ia.md),
> [ADR 0015](../../docs/architecture/adr/0015-client-first-product-interface.md)).**
> A research is an AIA `Study` of kind `RESEARCH` under its client. Its stages are
> at `/app/clients/<client>/research/<study>/<stage>` (the `persona` step's slug is
> `dimensions`); `/app/research/*` is retired and redirects to `/app/clients`. The
> stage components, their parity-tested logic and their tests are unchanged; the
> frame around them (`StudyFrame`) now comes from the study's AIA workspace, and
> the unit project holding the working content is found only through the study's
> binding (OI-58), bound on the first save. The **classic seven steps are the
> current stage list, not the target specification**: the product lifecycle is
> the 13 stages of `docs/product/README.md`, and a stage is added, merged or
> renamed on that basis, not because the classic flow drew it. Hand-offs go to
> `/classic#aia:open=<unit>@<step>`, with the classic page's bar leading back. The
> URL and rail notes in *Approach* below are historical.

## Problem

The data owner asked, 2026-09-24, for the research flow rebuilt: *brief → plan →
questionnaire → audience → persona → run → progress → results → verify → next*.
It is the product's core path and the largest area of the classic interface:
ten renderers reassigned or wrapped 29 times, one shared project model kept in
browser memory and `localStorage`, and six AI steps run as polled jobs.

## What the classic flow actually is

Surveyed from `legacy/npc-panel-18.6.6/app/ui_app.html` @ `0932c5d` (character
offsets; `tools/ui_functions.py show <name>` prints a declaration, the last
assignment is the one that runs). The rebuild follows the **effective** chain,
not the declarations — several declarations are dead.

**Shared model.** `PROJECT` (the research project), `ANALYSIS` (the AI's reading
of the brief), `LAST_CHECK`, `FINAL_AI_REVIEW`, `LAST_RESULT`, `WORKFLOW_*`.
- Loaded by `openProject1785` @450866: `POST /api/projects/load {project_id}`;
  `PROJECT = defaultsMerge(r.project)` (@101469, from `BOOT.empty_project`).
- Saved by `scheduleServerSave` @440078: 1.8 s debounce, `POST /api/projects/save
  {project_id, parent_project_id, project_type:'research', project, analysis,
  panel_version, reason}`; a failure only `console.warn`s.
- AI steps run through `job` @439417 → @109829: `POST <endpoint>` → `{job_id}`,
  then `GET /api/job?id=` every 700 ms until `done` / `waiting_user` / `error` /
  `cancelled` (`paused` keeps polling); one job at a time; cancel is
  `POST /api/jobs/{id}/cancel`.
- The rail (`RESEARCH_STEPS` @417490) lists **seven** steps: Zadání, Návrh,
  Dotazník, Audience / Cílová skupina, Dimenze, Kontrola & Spuštění, Výsledky.
  It marks only the current step; every step is clickable.

**The ten screens** (effective definition → what it calls):

| Step | Effective | AI job / routes | Browser logic to port |
|---|---|---|---|
| brief | `renderBrief` @403351 + 2 wrappers | `/api/research/analyze` (via `ensureAnalysis1776` @388330, cached by `briefFingerprint1780` @419471); `POST /api/project/attachment` | problem-type toggle, fingerprint, attachment context (22 000 chars) |
| plan | `renderPlan` @313280 + 4 wrappers (variants, comments) | re-runs analyze; comment workflow (`npcProcessComments26`) | `applyProjectVariant1793`, object sets 4–15 |
| questionnaire | `renderQuestionnaire` @135858 + 1 | `/api/research/build_questionnaire`, `/api/questionnaire/upload`, `/api/questionnaire/optimize`, `/api/research/deep`, template download | `questionnaireHasQuestions1789`, counts, ids, 4–15 validation, `changeQType` |
| audience | `renderAudience` @157785 + 3 | `GET /api/audience/dimensions`, `POST /api/audience`, `/api/audiences*`, `/api/audience/propose` | `audienceReady1789`, `humanizeAudienceFilters1795`, factor search |
| persona | `renderPersona` @428625 + wrapper @470534 | `/api/persona/suggest`, `POST /api/library/dimension/request` | `recommendedSample1789`, `suggestedPersonaDims`, `canonicalPersonaDim`, `dimensionCatalogEntries1789` |
| run | `renderRun` @291980 + 2 wrappers | `POST /api/project/check`, `/api/project/final-review`, `/api/questionnaire/repair`, `POST /api/projects/save` + `POST /api/project/run` | issue filtering and labels, `nextRun1789` |
| progress | `renderResearchProgress1770` @414265 | `GET /api/workflows/{id}` every 1.6 s, `POST /api/jobs/{id}/retry` | `workflowActiveJob1784`, `workflowStepLabel`, `workflowPhase1785`, pct |
| results | with a result: `renderReport26` @788651 (the rest of the chain is never reached) | `GET /api/workflows/{id}` (`openWorkflowResult`) | `reportData26` @787055 |
| verify | `renderVerify` @210641 | *(see OI-47)* `/api/results/verify`, `/api/results/contextual_scenario` | `verificationHtml` |
| next | `renderNext` @217160 | `/api/discovery/strategy`, `/api/discovery/from_run`; creates a child project | `smartDiscoveryHtml`, prevalence |

**Found while surveying** (recorded in `open-items.md`):
- **OI-47.** `verify` never renders: it calls `loadVerifyTargets`, which is
  defined nowhere in the file (and `post(...)`, also undefined). No button,
  rail entry or `go('verify')` / `go('next')` reaches either screen.
- **OI-48.** The route ledger misses four paths the unit serves as
  `path in {…}` sets: `POST /api/audience/navrh` + `/api/audience/propose`
  (`ui_server.py:2120`) and `POST /api/results/contextual_calibration` +
  `/api/results/contextual_scenario` (`ui_server.py:2108`). The ledger is pinned
  to the reference's API ledger, which missed them.
- Classic defects the rebuild does not copy: audience range filters render as
  `[object Object]` (`humanizeAudienceFilters1795`); a special-audience preset
  scrolls to `#audFile`, which is not on that screen; the plan card's
  "changed" flag is never cleared.

## Approach

The same shape as Správa projektů (ADR 0014): React screens under `/app`,
the unit's API through `src/unit/`, each piece of browser logic ported from the
original and **parity-tested against it under Node**, a capture pair per screen
in the workbench.

- **URLs a person can share:** `/app/research/<project id>/<step>`, and
  `/app/research/new`. The classic flow has no deep links.
- **One project store** (`useResearchProject`): load, 1.8 s debounced save with
  the classic body, revision tracking — and a visible save state
  (*Ukládám… / Uloženo / Neuloženo — zkusit znovu*) where the classic interface
  only logged to the console.
- **One job runner** (`runJob` + a job panel): the classic polling and states,
  shown the way the design brief asks (§4.3): the phase, real elapsed time, the
  heartbeat, what it is waiting on, and cancel. No invented percentage.
- **The rail** shows the classic seven steps; progress is the run step's live
  state, not a rail entry, as in the classic interface.
- **Until a step is rebuilt**, the rail and buttons hand off to the classic
  interface on that project and step (`#aia:open=<id>@<step>`, an extension of
  the ADR 0014 hand-off).

**No AI in the workbench.** It never calls a model. Steps that need an AI
answer are seen with a **fixture project**: a fictional project filled from a
showcase DEMO's own design files (`RESEARCH_DESIGN_DEMO.json`,
`QUESTIONNAIRE_DEMO.json`, `AUDIENCE_DESIGN_DEMO.json`), saved through
`/api/projects/save`. Job answers in component tests are recorded shapes.

**Trade-off accepted:** results and progress can be seen in the workbench only
from fixtures, because a real run needs the model and the licensed panel; they
are verified against develop after deploy.

## Chunks

Each chunk: the effective classic chain read first, copy verbatim into `cs.ts`,
ported logic with parity tests, component tests, a capture pair (0 classic texts
missing, or each difference listed below), ledger row `REBUILT`, `make verify`.

| # | Chunk | PR | Status |
|---|---|---|---|
| 0 | This plan; OI-47, OI-48 | A | done @ `3c5bd21`, `b3fd59f` |
| 1 | Foundation: research routes (+ the ledger addendum for OI-48), the model and `defaultsMerge` / `briefFingerprint1780` ports, the project store with visible save state, the job runner and panel, the research rail and `/app/research/<id>/<step>`, the `open@step` hand-off, the workbench fixture project | A | done — see below |
| 2 | brief: problem types, title, goal, attachments and links, further context, AI analysis | A | done — see below |
| 3 | plan: variants, understanding, objectives, hypotheses, comparable sets, questions for the user, text-selection comments | A | done — see below |
| 4 | questionnaire: the three paths, Excel upload and template, AI build, the guided editor, respondent preview, optimisation | B | done — see below |
| 5 | audience: own / AI Analytics / special / ČR 18+, the factor filter editor, discovery, the readable summary, preflight | B | done — see below |
| 6 | persona: fixed base, catalog, AI suggestions, custom dimension request, sample size, society factors | B | done — see below (PR #50) |
| 7 | run: technical check and issues, final AI review, overrides, AI repair, start | C | **superseded** by [research-execution.md](research-execution.md) (ADR 0016): an AIA-run workflow, not a rebuild of the classic screen |
| 8 | progress: workflow status, active job, failure and resume, reconnect | C | **superseded** by [research-execution.md](research-execution.md) (ADR 0016): an AIA-run workflow, not a rebuild of the classic screen |
| 9 | results: the analytical report, analyst / client views, attachments | C | **superseded** by [research-execution.md](research-execution.md) (ADR 0016): an AIA-run workflow, not a rebuild of the classic screen |
| 10 | next: ideal group from results, manual propensity, child project | D | pending |
| 11 | verify: its intended screen against `/api/results/verify` and `contextual_scenario`, which the classic interface never draws (OI-47) — **new behaviour**, shown to the data owner before it merges | D | pending |
| — | Re-home under the client: `/app/clients/<client>/research/<study>/<stage>`, the study frame from its AIA binding, breadcrumbs, the rail only inside a study ([client-first-ia.md](done/client-first-ia.md) chunk 6) | IA | done |
| 12 | Switch-over: every A4 ledger row `REBUILT`, the capture of all ten; research projects of the classic store reachable only from their study (Projects is now `/app/settings/classic-projects`) | D | pending |

### Chunk 1 — what landed

- **Routes.** `src/unit/routes.ts`: the research, job and workflow routes, each a
  ledger row; id-addressed routes (`POST /api/jobs/{id}/cancel`) as
  `{route, path(id)}`, the id escaped (`routes.test.ts`). The ledger's
  `addenda` hold OI-48's four set arms
  (`test_the_addenda_are_exactly_the_set_arms_the_reference_missed`).
- **The effective binding.** `tools/ui_functions.py effective <name>` prints the
  binding that runs, not the dead declaration; the parity harness
  (`src/unit/testing/legacy.ts`) evaluates it under Node.
- **Model.** `src/unit/research/model.ts`: `defaultsMerge`, `PROBLEM_TYPES`
  (final splice @495760), `selectedProblemTypes`, `briefFingerprint`
  (`model.parity.test.ts`, 16 checks).
- **Store.** `src/unit/research/store.ts`: load (demo and simulation kept out),
  the classic save body at 1.8 s, a change made during a save stays pending,
  a failed save is a visible state (`store.test.ts`).
- **Jobs.** `src/unit/research/jobs.ts`: payload, meta line, outcome wording,
  one job at a time, cancel with the classic body (`jobs.test.ts`, parity on
  `fmtTime`, `usualRange`, the payload and the meta line).
- **Frame.** `/app/research/new` and `/app/research/<id>/<step>`; the rail of
  seven steps, the eyebrow and done marks (`steps.parity.test.ts` against
  `RESEARCH_STEPS` and `updateTopbarProgress1782`), the save indicator, the job
  panel (cancel armed after 5 s). A step not yet rebuilt says so and hands off
  with `#aia:open=<id>@<route>` (`ResearchScreen.test.tsx`).
- **Workbench.** `make ui-fixtures` writes two fictional projects (`empty`,
  `planned`) through `POST /api/projects/save`.

100 tests across the seven files; seen in the workbench at
`/app/research/<id>/questionnaire` (eyebrow *VÝZKUM · KROK 3 / 7*, *Uloženo*).

### Chunk 2 — what landed

- **Logic.** `src/unit/research/brief.ts`, ported from `setProblemType1785`,
  `updateTop` / `updateBrief` (the analysis is dropped by every briefing edit and
  by the goal and decision, not by the title), `addBriefLink1785`,
  `removeBriefAttachment1785`, `briefAttachmentContext1785` (22 000 characters),
  `fileToB64`, and `ensureAnalysis1776` with its wrapper @412858: the fingerprint
  reuse, the empty-brief refusal, the payload, and the merge that keeps the
  person's title, goal, decision, briefing and screen state
  (`brief.parity.test.ts`, 46 checks, each against the original under Node;
  four deliberate mutations of the port each caught).
- **Provider readiness.** `src/unit/research/provider.ts`: `ensureClaudeReady1776`
  (the edition switch, `GET /api/providers/claude-code/status`,
  `POST /api/settings/ai_check`), `activeProvider1790`, the effective
  `providerLabel1790` (`provider.test.ts`). `settingsAiCheck` added to the routes.
- **Diagnostika.** `src/unit/support.ts`: `createSupportBundle` with the failed
  job's id (`support.test.ts`).
- **Screen.** `BriefStep.tsx` at `/app/research/<id>/brief` and
  `/app/research/new` (`BriefStep.test.tsx`, 9 tests: the classic blocks, the
  toggle and its default goal, links, a file upload as base64, the analysis job
  to the plan, reuse without a job, the provider notice, the error card, the
  empty-brief refusal).
- **Frame fixes.** The project loads once per id, not once per router object
  ("loads a project once, however often the screen re-renders"); a new project
  says *Nový projekt · uloží se po první změně* instead of *Uloženo*.
- **Workbench, found here.** The workbench unit reported Claude Code *READY*: it
  found this session's signed-in CLI. An analysis job was created and cancelled
  while still queued (the workbench runs no job worker; no model was called).
  `unit_standin.py` now switches every provider off three ways
  (`test_the_workbench_unit_can_reach_no_ai_provider`; AGENTS.md § The 18.6.6
  unit).
- **Capture pair.** `route-brief` at `/app/research/new`: 0 classic texts
  missing at 1440 and 1024.

### Chunk 3 — what landed

- **What runs.** The plan is `renderPlan` @313280 under four wrappers: the
  review note (1785), the wizard's *Další · dotazník* (1789), the design
  variants (1793) and the comment workflow (26), which removes both the review
  note and the *Další krok: dotazník* card. Neither is drawn here.
- **Logic.** `src/unit/research/plan.ts`: `comparableFamily`, the question
  preview of `renderObjectSet` (six rows, the first `{object}` filled), the set
  editors (`addPlanSet` with its two prompts and the 15-item cut,
  `addPlanObject`, `renamePlanSet`, `removePlanSet`, `removePlanObject`),
  `projectVariants1793` / `applyProjectVariant1793`, `reanalyze`, the comment
  workflow (`comments26`, the float button's add, `npcRemoveComment26`,
  `npcProcessComments26`) and `setQuestionnairePath('choose')`
  (`plan.parity.test.ts`, 39 checks; five deliberate mutations each caught).
- **Shared analysis.** `useAnalysis.tsx`: the brief's analysis flow and its
  error card, now used by Zadání and by Návrh (follow-up answers; comments,
  forced).
- **Dialogs.** The research context has `confirm` / `prompt` with the classic
  words, through the rebuilt dialog; its form is keyed per question, so two
  prompts in a row never share a value.
- **Screen.** `PlanStep.tsx` (`PlanStep.test.tsx`, 7 tests: the empty state,
  the analysis and its sets, a variant applied, the set editors through the
  prompts and the confirm, follow-up answers to a new analysis, a comment on
  selected text worked in with a forced analysis, the way on). The comment
  flow was also driven in Chromium on the fixture.
- **Capture.** Fixture pairs (`fixture` in the screen ledger): the classic step
  opened on the same project through the hand-off. `route-plan@planned`:
  0 classic texts missing at 1440 and 1024.
- **Found here.** The `open@step` hand-off landed on the overview: the classic
  overview draws itself asynchronously over the step (fixed @ `7d74069`).

### PR B survey — Dotazník, Audience, Dimenze (before any code)

Read from `ui_app.html` @ `8444bda` (unchanged since 18.6.6: same SHA256),
following each renderer's **effective** chain. `tools/ui_functions.py effective`
picks the later of a name's last declaration and last assignment; a declaration
is hoisted to the start of its `<script>` block, so that is exact only if no
assignment follows a declaration inside the same block. None of the 13 blocks
does (pinned by `test_legacy_ui_functions.py::test_no_declaration_is_overridden_within_its_script_block`).
Line numbers are `ui_app.html:<line>`; `N.` marks what a step writes to the
project (`save(reason, invalidateCheck)`).

#### Dotazník (`renderQuestionnaire`)

**Chain.** Declaration `:341` → wizard wrapper `:960` (*Další · cílová
skupina*, disabled unless `questionnaireHasQuestions1789` `:955`, hint *Nejdřív
vytvořte nebo nahrajte dotazník.*). Two bindings only.

**Screens.** `ui_state.questionnaire_path`: `choose` (three paths; the AI tile
shows `aiProviderLabel() · PROJECT.model`) → `upload` (template, methodology
link, file, then the editor below if sections exist) · `manual` (editor) · `ai`
(an AI card while there are no sections, else the editor). Every non-choose
view has *← změnit způsob vytvoření*.

**Editor** (`questionnaireEditorHtml`): a respondent preview (first 14 items:
questions with up to 8 options or the scale's end labels, batteries with up to
8 object rows), the guided editor (`N otázek · M sledovaných sad`; quick add:
one answer / scale 1–10 / open / tracked set), one card per section (question
blocks: title, purpose, question cards; batteries: title, purpose, object
family, the `{object}` question, 4–15 objects one per line, scale ends,
familiarity check, price bands only for `output_type==='test_konceptu'`),
*+ nový blok*, *+ sledovaná sada*, and *Finální optimalizace* with the research
state (`pre_research.accepted`) and *Dotazník mám → Koho se ptát*.

**State transformations (deterministic).** `addGuidedQuestion` (2 prompts for a
choice question; creates *Hlavní otázky* if no question block), `addQuestion`,
`removeQuestion` (no confirm), `changeQType` (defaults: `Ano/Ne`; scale `[1,10]`,
`vůbec/zcela`), options / scale min–max (`+value`, the other bound `||`
defaulted) / scale labels, `addQuestionSection`, `addTrackedSet` (2 prompts;
4–15 or an alert), `removeSection` (confirm), `updateObjects` (lines, trimmed,
15 max, a toast under 4), `setObjLabel`, `setPriceBands`, inline title /
purpose / family / question / familiarity edits. Ids: `secId()` / `qId()`
(time + random). All save `save()` or `save('guided_question')`.

**Deterministic server calls.** `POST /api/questionnaire/upload`
(`{filename,data_b64,project}`, 180 s): the unit parses the XLSX / CSV and
returns the project with its sections; the client takes it whole
(`defaultsMerge`), sets the path to `manual`, `save('questionnaire_import')`,
toast *Načteno: N otázek · M sledovaných sad*. `GET /api/questionnaire/template`
(a download). Verified in the workbench: the template uploads back as 3
sections, 2 questions, 1 set.

**AI jobs.** `buildQuestionnaire` (`/api/research/build_questionnaire`, *AI
tvoří dotazník*, warn 50 s): first `ensureAnalysis1776()` (may run its own
analysis job), then the provider check; the result's project replaces the
project, provider forced to `claude_code_subscription`, path `manual`,
`save('questionnaire_ai_1776')`. `optimizeQuestionnaireAI`
(`/api/questionnaire/optimize`, *Hloubkový research + optimalizace dotazníku*):
**no provider check**; project replaced, `pre_research` and the analysis taken
if returned, `save('questionnaire_optimized')`. `runProjectDeepResearch`
(`/api/research/deep`, only offered once research exists): **no provider
check**; `pre_research` replaced, `save('deep_research')`, toast with the
accepted / quarantined counts.

**Transition.** `continueQuestionnaireToAudience` `:588`: clears the run
check and the final review, `audience_entry ||= 'choose'`,
`save('questionnaire_done', false)`, to audience. The editor's own button calls
it with no condition; the wizard's is disabled without a regular question
(OI-52).

**Dead.** *AI: zlepšit blok* (`quickClaude` `:579`) needs `#chatInput`, which
no code creates (OI-49).

#### Audience (`renderAudience`)

**Chain.** Declaration `:374` → 1785 `:899` (title *4. Audience / Cílová
skupina*; a banner for `audience_entry==='analytics'`) → 1789 `:961` (*Další ·
dimenze*, disabled unless `audienceReady1789`, hint *Nejdřív vyberte zdroj
audience.*) → 1795 `:1173` (appends *Čitelný souhrn cílové skupiny* after the
wizard button, on every audience screen).

**Screens.** `ui_state.audience_entry`: `choose` (own / AI Analytics) → `own`
(template, instructions, saved customer audiences, upload, check, *Audience mám
→ Persony* disabled until a dataset) · `analytics` with `analytics_choice`: none
(three branches) → `cz_coming` (a warning) · `special` (six presets,
`SPECIAL_AUDIENCE_PRESETS` `:362`; *Vybráno*, check, continue) · `cz18` (whole
ČR 18+ / narrow by factors / find the ideal group from results).

**State transformations.** `setAudienceEntry` (own → `source_mode customer`,
dataset cleared), `setAnalyticsChoice` (cz18 → `chooseAudience('population')`;
special → dataset, subpanel and keys cleared, **filters kept**),
`chooseAudience(population|filters|discover)`, `chooseSpecialPreset`
(population kind → `usePopulationSubpanel`, whose filters come from the
bootstrap's subpanel; special kind → `builtin_special:<key>`; coming-soon →
name only; **neither of the last two clears `builtin_subpanel` or the filters**,
OI-51), `selectAudienceDataset`, the factor editor's categorical multi-select
(`setAudienceCategory1793`, then an automatic preview) and numeric range
(`setAudienceRange1793` `:1053`: **an empty bound is stored as 0**, OI-50),
`removeAudienceFactor1793`, the ideal-group texts. `audienceReady1789`: own →
a dataset; analytics → `cz18`, or special with a dataset / subpanel / panel key.

**Deterministic server calls.** `GET /api/audience/dimensions` (the factor
catalogue, cached per page; default category `demography`, search by id, label
and category), `POST /api/audience` (population preview, `{filtry,n}`),
`POST /api/audiences/preflight` (a dataset), `GET /api/audiences`,
`POST /api/audiences/upload`, `GET /api/audiences/template`. The preview is
page memory (`AUDIENCE_PREVIEW`), never saved, cleared by most changes.

**AI job.** `proposeAudience` (`/api/audience/propose`, *AI převádí cílovku na
dostupné filtry*, warn 40 s; `maxMs: 240000` is passed and ignored, OI-55):
provider check first; filters replaced by the model's, strategy `filters`,
description = the text, the preview = its feasibility,
`save('audience_ai_1776', false)`, a toast when part of the text is not
covered.

**Transition.** `go('persona')` from the wizard or the in-card buttons; no
state change.

#### Dimenze (`renderPersona`)

**Chain.** The declaration `:410`, the reassignment `:683` and its 1785 wrapper
`:904` are all replaced by the full reassignment `:979`, then wrapped by 1793
`:1071` (society-factor catalogue card; the model's proposed new dimensions,
page memory only).

**State transformations.** `personaApproved` `:407` **writes the recommended
set into an empty approval during render** (OI-54); add / remove a catalogue
dimension (`dimension_catalog_add` / `_remove`), `autofillPersonaDims`,
`suggestedPersonaDims` (research-plan topics, question topics, study-type rules,
else four defaults; `canonicalPersonaDim`; 8 at most), the sample size
(`recommendedSample1789`: 300, 400 for > 30 questions or a > 1 200-character
goal, ≥ 500 for the ideal-group strategy; the input clamps 50–5 000, empty →
the recommendation), `useRecommendedSample1789`. The catalogue is
`PERSONA_DIM_LABELS` `:404` plus the Data Library's active dimensions, sorted
by Czech label; the search only hides rows.

**Server calls.** `POST /api/library/dimension/request` (a custom or AI-proposed
dimension, then four Data Library reads to refresh), `GET /api/audience/dimensions`.

**AI job.** `suggestPersonaAI` `:1070` (`/api/persona/suggest`, warn 45 s,
`maxMs` 300 s ignored): provider check; **the approval becomes the model's
list, canonicalised, not checked against the catalogue** (OI-53; an earlier,
dead binding `:402` filtered and warned).

**Transition.** *Další · kontrola*: `persona_mode='calibrated'`,
`save('persona_done_1789')`, to the run step (not rebuilt in PR B: it hands off).

#### What PR B keeps from the classic behaviour, and what needs a decision

Ported as the classic does, each with a characterization test: OI-50, OI-51,
OI-52, OI-53, OI-54, OI-55. OI-57 (found in chunk 6) is characterised and not
reproduced: the rebuild asks for the catalogue once. None is silently fixed; each is a decision for the
data owner, listed in the PR. Display-only differences are in the table below.

### Chunk 4 — what landed

- **Logic.** `src/unit/research/questionnaire.ts`: the counts and the four
  views, the respondent preview, every editor action with its prompts and save
  reasons, the import, and what the three AI steps send and keep
  (`questionnaire.parity.test.ts`, 62 checks against the original under Node,
  with time and randomness fixed so the generated ids agree; the editor's
  inline `oninput` / `onchange` handlers are extracted from the classic
  templates and run against a stand-in element; six deliberate mutations each
  caught).
- **Shared AI step.** `useAiStep.tsx`: the provider check (where the classic
  step makes one), the save a job is addressed to, and one failure card; the
  brief's analysis card is now drawn by it.
- **Screen.** `QuestionnaireStep.tsx` (`QuestionnaireStep.test.tsx`, 10 tests:
  the three paths, the editor with no dead button, question edits, the guided
  prompt and the 4–15 refusal, the small-set note and the confirmed delete, the
  import, the AI build reusing the brief's analysis, the provider notice,
  optimisation with no provider check (OI-55), the way on).
- **Workbench.** A `questionnaire` fixture; the capture's comparison treats the
  preview's radio circle "○" as a drawn element, as it already did arrows.
- **Capture.** `route-questionnaire@questionnaire`: 1 classic text missing at
  1440 and 1024, *AI: zlepšit blok* (OI-49).
- **Found here.** `develop` had moved the web client to Next.js 16.3.6
  (`36bcfa4`); this checkout's modules were 16.1.6, which `make verify` does
  not notice (it runs no ESLint). Reinstalled with `npm ci`. Next 16.3's
  `next dev` writes `apps/web/AGENTS.md` and `apps/web/CLAUDE.md`; not
  committed here, a decision for the PR.

### Chunk 5 — what landed

- **Found first: a lost change (OI-56, fixed).** Every step was its own page and
  store, and leaving one dropped a pending save; the project now has one session
  for all its steps (the `[projectId]` layout), handed over from
  `/app/research/new` once it has an id, and `dispose()` saves a pending change.
  The session also holds the page memory the classic keeps in globals.
- **Logic.** `src/unit/research/audience.ts` (`audience.parity.test.ts`, 72
  checks: the six screens and the readiness rule, every chooser and preset, the
  factor list, current values and handlers, chips, summary, preview and
  preflight, saved audiences, upload, proposal; seven mutations caught, two of
  them "fixes" of OI-50 / OI-51 that the characterization tests reject).
- **Screen.** `AudienceStep.tsx` (`AudienceStep.test.tsx`, 8 tests: the two
  sources, own audiences and an upload, AI Analytics with a special preset and
  ČR 18+, a factor with its preview and chip, the empty bound stored as 0
  (OI-50), the AI proposal, the preview kept across steps).
- **Capture.** `route-audience@audience`: 1 classic text missing at 1440 and
  1024, `[object Object]` (the summary's range, drawn `25–54`).

### Chunk 6 — what landed

- **Logic.** `src/unit/research/persona.ts` (`persona.parity.test.ts`, 45
  checks: the catalogue and its search text, `canonicalPersonaDim`, the
  recommended and approved dimensions, add / remove / autofill, the sample and
  the input's own `onchange` handler, the wizard's action cut from the drawn
  page, the AI suggestion's body and what it keeps, both dimension requests,
  Deep Research's topic; thirteen mutations caught). The classic screen writes
  the approval's refill into the project as it draws, so every change the port
  makes (and the suggestion's body) carries the refill, as the classic save
  does; the parity cases draw first and then act.
- **Harness.** `legacyContext({ now })` now fixes a no-argument `new Date()` as
  well as `Date.now()`: the dimension request stamps `created_at` with it.
- **Hand-off.** `#aia:dimension=research` calls the classic
  `openDimensionResearch1793(label)`; the label, free text, goes through
  same-origin `sessionStorage` and is read once (ADR 0014, point 7).
- **Screen.** `PersonaStep.tsx` (`PersonaStep.test.tsx`, 9 tests: the base, the
  refill and the catalogue with the library's; add / remove / autofill and the
  refill after the last (OI-54); the AI suggestion with its new dimensions and
  a request from one (OI-53); the provider notice; a custom request refused
  empty, recorded, the library refreshed; the sample clamped on commit and the
  recommendation; the way on and back to the audience; a failed catalogue asked
  once (OI-57); Deep Research's hand-off).
- **Workbench.** A `persona` fixture: three catalogue dimensions, one request,
  N=450.
- **Capture.** `route-persona@persona`: 0 classic texts missing at 1440 and 1024.
- **Found here.** OI-57: a failed audience catalogue is requested again on every
  draw, without limit (the probe without a bound never ends).

## Deliberate differences (added to as chunks land)

| Step | Classic | Rebuilt | Why |
|---|---|---|---|
| all | no URL per project or step | `/app/research/<id>/<step>` | a step can be linked and reloaded |
| all | save failure only in the console | visible save state with retry | never let a person believe unsaved work is saved |
| all | job overlay text | phase, elapsed, heartbeat, waiting-on, cancel | design brief §4.3: no fake progress |
| brief | provider not ready: jump to Nastavení and `alert()` | a notice where the person is, with *Zkusit znovu* and a link to Nastavení | the brief they were writing stays in view |
| brief | the error card says only *AI analýza se nedokončila* | the same card, plus what failed, in the unit's words | a person can tell a timeout from a refusal |
| brief | a file input and a separate *Přidat soubory* button | one *Přidat soubory* button that opens the picker and uploads | one step, not two; the classic 📎 / 🔗 are icons |
| brief | *Přidávám přílohy* as a full-screen overlay | the same words inline in the attachments card | the rest of the brief stays usable |
| brief | a job starts against whatever was last saved | a new or edited brief is saved before the analysis job starts | the job is addressed to the saved revision |
| plan | a failed follow-up analysis jumps to the brief with its error card; a failed comment analysis is an `alert()` | the error card on the plan | the person stays where the answers are |
| plan | "changed by your comments" is marked on the understanding card and never cleared | the mark stays until another analysis replaces that one | it says something true, or nothing |
| plan | with no analysis, the comment box is drawn | the empty state only | there is no text to comment on |
| plan | the comment box after the *Další* button | before it | the way on is last |
| plan | a missing `what_is_known` would become the word `undefined` | an empty field | defect (defaultsMerge normally prevents it) |
| plan | a comment is offered after a mouse selection | also after a keyboard selection | accessibility |
| questionnaire | *AI: zlepšit blok* on every block | not drawn | it does nothing (OI-49); a decision |
| questionnaire | failures of the AI build, optimisation and deep research in an `alert()` | the same text on the page, with *Zkusit znovu* and *Diagnostika* | the editor stays in view |
| questionnaire | a file input and a *Načíst dotazník* button | one *Načíst dotazník* button that picks and imports | as the brief's attachments |
| questionnaire | *Načítám dotazník* as a full-screen overlay | inline in the import card | the rest of the step stays usable |
| audience | the readable summary prints a range filter as `[object Object]` | `od–do`, as the filter chips print it | display only; the stored filter is the classic one |
| audience | preview and upload failures, the AI proposal's failure in an `alert()` | the same text on the page | the editor stays in view |
| audience | *Nahrávám audience* as a full-screen overlay | inline in the upload card | as the questionnaire's import |
| audience | the readable summary after the *Další* button | before it | the way on is last |
| persona | the society-factor and new-dimension cards below the *Další* button | above it | the way on is last |
| persona | a failed audience catalogue is asked for again on every draw, without limit | asked once per visit; on failure both cards are left out, as the classic draws them | OI-57; the visible result is the classic's |
| persona | the AI suggestion's and the dimension request's failures in an `alert()` | the same text on the page | the catalogue stays in view |
| persona | the search box is emptied by every add or remove (the page is redrawn) | the search is kept | a redraw artefact, not a rule |
| persona | the model's proposed dimensions (`PERSONA_AI_SUGGESTION`) are one global, shown in any project opened next | kept per project session | a suggestion belongs to the project it was made for |
| persona | the labels sent to the model are every Data Library label seen since the page loaded | the system's labels and the current library's | the global only grows; nothing is removed from it |
| persona | the sample saves on the input's `change` | on blur or Enter; a spinner click saves on blur | React's `onChange` is every keystroke |
| persona | the refill of an empty approval is written into the project when the screen draws, and saved by the next save anywhere | saved with the next change made on this step | the rebuild does not change a project by drawing it |
