---
status: planned
chunks:
  - "[ ] S0. Settle the scope: D9 against the 2026-10-07 direction, and the 13 stages against 18.6.6's five screens"
  - "[ ] S1. A simulation Study gets working content and a SIMULATION workflow type"
  - "[ ] S2. The population adapter: a run's bound RuntimePopulation as the core's SimulationPopulation"
  - "[ ] S3. Store an approved WorldModel and ScenarioContract as hashed artifacts, behind study routes"
  - "[ ] S4. The simulation executor: one frozen VariantResult per variant against one bound baseline"
  - "[ ] S5. The comparison artifact, and proof that a new scenario never changes an old result"
  - "[ ] S6. The simulation report with explicit review state"
  - "[ ] S7. The studio's screens in place of SimulationFrame's notice"
---
# Simulation studio: the deterministic core reaches a person

**Owner:** unassigned. **Written:** 2026-10-09, from `mvp-workflow-assurance.md` A2
(`develop @ c6ee438`). No current plan owns building the studio:
`done/simulation-deterministic-core.md` owns the core only (chunks 1-7, done), and
`legacy-strangler.md` slice 11 and `interface-rehome.md` A5 name it without chunks.

## What exists and where it stops (at `c6ee438`)

The journey stops after "create a SIMULATION study". The core is pure and tested, and
nothing connects it to a person.

| Hop | State | Anchor |
|---|---|---|
| List / create a simulation study | EXISTS | `apps/web/src/app/app/clients/[clientId]/simulations/page.tsx`; `apps/api/src/aia_api/routers/workspace.py:636-660`; `domain/scope.py:454` |
| The study's page | Placeholder | `apps/web/src/components/aia/SimulationFrame.tsx:3-5, 33-38` |
| Working content / design | Refused | `infrastructure/study_workspace_repository.py:135`, `study_design_repository.py:90` (`not_research`) |
| API routes, application service | ABSENT | nothing under `routers/` or `application/` |
| Workflow type | ABSENT | `domain/workflow_templates.py:58`: develop_snapshot, research, research_agent |
| Executor | ABSENT | `apps/executors/src/aia_executors/registry.py` registers none |
| Scenario approval, variants, worlds, run, freeze, comparison | EXISTS (domain only) | `domain/simulation/scenario.py:77, 139, 150, 199-229`; `inoculation.py:348, 575`; `results.py:209, 297-310, 380` |
| Population | Not connected | the core takes `SimulationPopulation` (`inoculation.py:139`); nothing builds one from `PopulationRuntime.load_for_run` (`application/population.py:459`) |
| Immutable storage | Generic only | `infrastructure/artifact_repository.py:573-585` (`freeze`) |
| Report | ABSENT | `application/report.py`, `executors/report.py` are research-only |

The 13 stages are labels (`domain/pipeline.py:117-131`). 18.6.6 had five screens
(`legacy/npc-panel-18.6.6/app/ui_app.html:728-732`), all `NOT_IN_AIA`
(`docs/migration/interface-screens.json`), with a REVIEW_REQUIRED/APPROVED scenario contract
and a resumable budget-capped run. Not built in the core either: world-model generation, the
scenario compiler's model step, the per-world respondent run
(`docs/architecture/simulation-deterministic-engine.md:219-232`).

## Chunks

- **S0. Scope.** D9 (`.planning/overview.md`, "Is the Simulation lifecycle in the MVP?") still
  reads as open, and `docs/migration/mvp-acceptance.md` scopes the MVP to Research; the user's
  2026-10-07 direction requires the studio (`mvp-workflow-assurance.md`). The owner confirms,
  and the docs PR closes D9 (this makes OI-27 release-blocking). Decide how the 13 stages map
  to 18.6.6's five screens, and which stages S1-S7 deliver (BRIEF, DEEP_RESEARCH, AUDIENCE,
  DIMENSIONS, INTERPRETATION and DELIVERY have no core). D10 and D11 stay open; S4 uses the
  core's constants as they are, versioned.
  *Done when:* the decision and the stage map are recorded here with a date.
- **S1. Content and type.** Lift the `not_research` refusals for a SIMULATION study's own
  working content (not the research design), and add a `SIMULATION` workflow type and step
  graph to `workflow_templates.py`. *Done when:* a simulation study saves and reloads its
  content, a run of the new type is created and refused by the worker with a named reason.
- **S2. Population.** One adapter from the run's bound `RuntimePopulation` to
  `SimulationPopulation`, asking `decide` / `decide_joint` for every field, with the weight
  role pinned at binding. Depends on run creation binding a population
  (`population-operations.md` P3). *Done when:* the adapter refuses a field its policy denies,
  and the same binding gives the same population bytes.
- **S3. Contracts as artifacts.** An approved WorldModel and ScenarioContract stored as hashed
  artifacts of the study, approval bound to the contract's sha256 (the core's rule), with
  create / approve / read routes. The first world model is a hand-authored fictional fixture;
  no model call. *Done when:* an edited contract after approval is a new artifact needing a new
  approval.
- **S4. Executor.** Runs `run_variant` per variant against one bound baseline and freezes each
  `VariantResult` (`freeze`). A retry keeps the binding, seed and hashes. *Done when:* the
  real worker runs two variants end to end on fictional data, and a retry reproduces the
  frozen bytes.
- **S5. Comparison.** `compare_variants` as an artifact; it refuses pairs whose world model,
  population, seed or worlds differ. *Done when:* a new scenario creates new artifacts and the
  old ones are byte-identical.
- **S6. Report.** A report over the frozen results and comparison, with explicit review state
  (the research report's `DRAFT_UNAPPROVED` pattern), synthetic data labelled every time.
- **S7. Screens.** The stages S1-S6 deliver, in place of `SimulationFrame`'s notice;
  `interface-screens.json` moves the five screens from `NOT_IN_AIA`.

**Later, out of this plan:** world-model generation and the scenario compiler through the
gateway, the per-world respondent run, F13 parity (OI-27).

## Dependencies

`population-operations.md` P3 (a run records its population binding) for S2; `client-knowledge-lifecycle.md`
§ Simulation (scenarios bound to knowledge versions, units and bounds before free-form
scenarios) before any scenario is written from client material.
