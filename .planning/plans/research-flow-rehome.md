# Research flow, rebuilt — area A4 of the React re-home

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-24
**Decision:** [ADR 0014](../../docs/architecture/adr/0014-rebuild-the-interface-in-react.md) ·
**Parent plan:** [interface-rehome.md](interface-rehome.md) (area A4) ·
**Tools:** [ui-workbench.md](ui-workbench.md)

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
| 3 | plan: variants, understanding, objectives, hypotheses, comparable sets, questions for the user, text-selection comments | A | pending |
| 4 | questionnaire: the three paths, Excel upload and template, AI build, the guided editor, respondent preview, optimisation | B | pending |
| 5 | audience: own / AI Analytics / special / ČR 18+, the factor filter editor, discovery, the readable summary, preflight | B | pending |
| 6 | persona: fixed base, catalog, AI suggestions, custom dimension request, sample size, society factors | B | pending |
| 7 | run: technical check and issues, final AI review, overrides, AI repair, start | C | pending |
| 8 | progress: workflow status, active job, failure and resume, reconnect | C | pending |
| 9 | results: the analytical report, analyst / client views, attachments | C | pending |
| 10 | next: ideal group from results, manual propensity, child project | D | pending |
| 11 | verify: its intended screen against `/api/results/verify` and `contextual_scenario`, which the classic interface never draws (OI-47) — **new behaviour**, shown to the data owner before it merges | D | pending |
| 12 | Switch-over: Projects opens research projects in `/app`, every A4 ledger row `REBUILT`, the capture of all ten | D | pending |

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
| audience | range filter shown as `[object Object]` | `od–do` | defect |
