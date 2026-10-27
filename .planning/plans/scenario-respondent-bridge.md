---
status: planned
chunks:
  - "[ ] 0. Scope and sequencing: this plan is blocked on panel-grounded-respondents#7 (chunks 7f-7h) and does not start before it records a verdict"
  - "[ ] 1. ADR: scenario-conditioned respondents are a second, separately-evidenced modelled origin, never blended with panel-grounded-respondents#7's validation"
  - "[ ] 2. The bridge contract (plan before code): how a WorldModel's FS_* values become persona input, what a respondent is and is not told, refusals"
  - "[ ] 3. ScenarioPersonaInput: pure function, FS_* columns -> persona facts, under the same policy gates panel_persona already enforces"
  - "[ ] 4. The per-world respondent run: one ai_respondent/panel_persona call per sampled row per world, answers folded into WorldOutcome"
  - "[ ] 5. Origin and evidence: DataOrigin.SCENARIO_MODELLED_PANEL, instrument policy -3, client-facing gated on a recorded forecast score, never on chunk 7's validation"
  - "[ ] 6. Sociomap compatibility guard: a sociomap run refuses a dataset whose respondents answered more than one world, and refuses cross-world aggregation silently"
  - "[ ] 7. Cost and workflow wiring: SIMULATION workflow step that calls the bridge, budget reservation at n x worlds x variants, parks like any fieldwork step"
  - "[ ] 8. Scoring loop: freeze_prediction already exists; wire the per-world respondent answers into WorldOutcome -> ensemble_worlds -> score_prediction once truth is recorded"
---
# Scenario-conditioned respondents: the simulation studio's missing hop, built on the validated panel-respondent contract

**Owner:** unassigned. **Written:** 2026-10-27, from a product direction discussion: AIA's goal
is current-state estimation (research, Sociomap) **and** future/what-if scenario prediction
(the simulation studio), at business-consulting scale. The MVP correctly scopes simulation out
(D9, `mvp-acceptance.md`), but the product direction needs it accounted for now so the research
engine's one respondent primitive is built to be reused, not rebuilt.

## Problem

Two systems in this repository already do almost all of what a "predict how people will react
to a hypothesized future" product needs, and they do not talk to each other:

- **The panel-grounded respondent mechanism** (`panel-grounded-respondents.md`, chunks 0-7)
  draws real population rows, builds first-person personas from them, and asks a model one
  question block at a time; code never invents a fact. Its evidence is gated through
  `DataOrigin.MODELLED_AI_PANEL` and `aia-instrument-evidence-2`, lifted to client-facing only
  by a pre-registered holdout validation against the *same sampled people's own, already-measured*
  survey answers (chunk 7).
- **The deterministic simulation core** (`simulation-deterministic-engine.md`, Phase 7 first
  slice, `domain/simulation/`) takes a model-authored `WorldModel` (hypothesized factors,
  drivers, correlations, explicitly marked `HYPOTHESIZED_JOINT`) and a population, and produces
  `FS_*` perturbation columns per respondent row through `inoculate_population`. It stops
  exactly where a person would be asked anything: "the respondent run per world (Phase 5)...
  not built" (`simulation-deterministic-engine.md` §8).

Nothing in the codebase lets a scenario's `FS_*` columns become persona input to the mechanism
that already knows how to ask a grounded respondent a question. Without this plan, the day the
simulation studio is picked back up, there is no contract for that hop and no agreed evidence
story for it, so it either gets built in a rush with no validation plan, or the team reinvents
a second respondent mechanism from scratch.

**Why this cannot wait for the simulation studio's own plan.** `simulation-studio.md` (status
`planned`, chunks S0-S7) explicitly defers this: "Later, out of this plan: world-model
generation and the scenario compiler through the gateway, the per-world respondent run". If
the panel-respondent contract (chunk 7) lands without this plan recording how it will later be
reused, a future implementer has two bad options: duplicate the persona/evidence machinery for
scenarios, or retrofit scenario support into chunk 7's validation in a way that quietly mixes
two different evidence claims (see Trade-off below). This plan exists so that choice is made
once, in writing, before either system changes again.

## Approach

**Reuse the respondent primitive; do not reuse its validation.** A scenario-conditioned
respondent call is byte-for-byte the same contract as a production panel-grounded respondent
call (`panel_personas` -> `ai_respondent`/`AgentDefinition`/`ModelRequest` -> code-side answer
drawing), with one addition: the persona's input facts are extended with the sampled row's
`FS_*` values for one world, read through the same `RuntimePopulation.decide` /
`decide_joint(FieldUse.PERSONA_CONSTRUCTION, ...)` gates every other persona field already
passes. No new model-call mechanism, no new prompt format, no new response contract.

**Keep its evidence entirely separate from chunk 7.** Chunk 7 validates: "on a question not in
its persona, this respondent system's answers are close to the *same, already-measured* people's
real answers." A scenario has no corresponding real answer to hold out — the world is
hypothesized, not measured, by construction (`HYPOTHESIZED_JOINT` is stamped on every factor
for exactly this reason). The honest validation available here is the one the simulation core
already stubs: `freeze_prediction` (blind, pre-registered, uncontaminated) ->
`record_truth` (write-once, after the fact) -> `score_prediction`. A scenario-conditioned
respondent run is therefore evidenced by **forecast scoring against eventual outcomes**, never
by chunk 7's holdout, and the two are never allowed to be read as substitutes for each other.
This needs its own `DataOrigin` (chunk 5) so the origin gate — not a comment, not a convention —
is what keeps them apart (`ARCHITECTURE.md` A6: one definition, checked by code).

**Keep Sociomap's independence assumption intact.** Sociomap's confidence gates (Kish effective
n, the 95% Fisher interval, `n_min=30`) assume each respondent's relation judgment is an
independent observation (`sociomapa-methodology-decision.md` v3; `hmodel.md` §2). A
scenario-conditioned respondent answering under one `WorldModel` is still answering alone, with
no visibility into any other respondent's answer or any other world's outcome — independence
within a world is preserved, so a Sociomap run *within one world* is statistically identical in
shape to a production research Sociomap. What must never happen is aggregating respondents who
answered under *different* worlds, or who interacted across worlds, into one Sociomap input: that
would silently break the independence the confidence math assumes (chunk 6 is a hard refusal for
this, not a warning).

**Explicitly not building:** agent-to-agent interaction, shared memory across respondents,
opinion diffusion/contagion, or anything resembling MiroFish's swarm-simulation loop. That is a
materially different epistemic claim (dynamics of currently-unknown future opinion, not calibrated
current-state or single-shot scenario estimation) with no analogous validation path available
today, and mixing it into this pipeline would make Sociomap's and chunk 7's confidence numbers
wrong without anyone having decided they should be. If the business later wants that capability,
it is a new plan, a new `DataOrigin`, and a new report surface — never an extension of this one.

## Trade-off accepted

Scenario-conditioned respondents will be able to answer questions no real person has ever
answered, with a validation story that is real but structurally weaker than chunk 7's (scored
only after the fact, against outcomes nobody can accelerate) — and that is reported to clients
as a distinct, named evidence class, never folded into "modelováno: AI respondenti z populace"
disclosure chunk 7 earns, so a client cannot mistake a forecast for a calibrated estimate.

## Chunks

**0. Scope and sequencing.** This plan does not start until `panel-grounded-respondents.md`
chunks 7f-7h record a verdict (pass or fail) for the production respondent system. Starting
earlier risks building the bridge against a persona contract or evidence gate that chunk 7
still changes. *Done when:* the owner confirms chunk 7's status and this plan's front-matter
moves to `in-progress`.

**1. ADR.** A new ADR (number after 0041) states: scenario-conditioned respondents are a
second modelled-evidence origin, structurally distinct from `MODELLED_AI_PANEL`; what a
scenario respondent's answer may be used for (per-world Sociomap, ensembled forecast ranges,
never a measured or chunk-7-validated claim); the write-once truth/scoring path as the only
route to a lifted disclosure; the explicit non-goal of agent interaction. Covers the interaction
with D6 (Sociomap `INTERNAL_ONLY` while still true) and with ADR 0024 (this ADR does not amend
it; it adds beside it).

**2. The bridge contract.** `domain/simulation/respondent_bridge.py` (pure, stdlib + Pydantic,
same layer as `domain/simulation/*` and `domain/panel_persona.py`):

- Input: one `SampledRespondent` (from `PanelSample`, the same sampler panel-grounded-respondents
  built), one `InoculatedWorld`'s row for that respondent (the `FS_*` columns
  `inoculation.apply_world` already produces), the `WorldModel` the row was inoculated under.
- Output: a `ScenarioPersonaInput` — the same `Persona` shape `ai_respondent.Persona` already
  defines, with its `facts` extended by exactly the `FS_*` fields `WorldModel.FIELD_POLICY`
  (or its simulation-side equivalent) marks as persona-eligible, each stamped
  `EXPERIMENTAL_HYPOTHESIZED_JOINT` in the persona text itself, never silently blended with the
  respondent's real panel facts without that marker.
- A respondent is never told: the world's id, seed, or that it is one of several ensembled
  worlds — only the hypothesized state itself, as "suppose X", matching how 18.6.6's own
  scenario framing worked (`full_simulation.py` `FS_SIMULATION_PROFILE`, noted as absent from
  the ported core in `population.md`).
- Refusals, each named: `scenario_field_not_persona_eligible` (an `FS_*` column with no
  `FIELD_POLICY` persona entry), `scenario_joint_refused` (the combined panel + `FS_*` fields
  fail `decide_joint`), `scenario_world_uncalibrated` (a row the world model was not applied to).

**3. `ScenarioPersonaInput` implementation.** Pure function, parity-tested the same way
`panel_persona.py` is: given a fixed `SampledRespondent`, `InoculatedWorld` row and
`WorldModel`, deterministic output; every policy gate exercised with a refusal fixture.

**4. The per-world respondent run.** `aia_executors` step (new, alongside `ai_fieldwork`):
for one `(world, variant)` pair, one request per sampled respondent per question block, through
the existing `GovernedModelGateway` and `AIA_RESPONSE_V1` response process — no new model-call
path. **`world_outcome()` (`domain/simulation/results.py:111`) keeps its existing meaning
unchanged**: the deterministic numeric read of a world's `FS_*` columns, no model call involved.
The respondent run is a second, parallel consumer of the same `InoculatedWorld`: its answers
assemble into a `FieldworkDataset` exactly as production fieldwork's `assemble_dataset` does
today (one dataset per `(world, variant)` pair, stamped with the new origin from chunk 5 and the
world's id/seed/sha256 recorded in its provenance), never merged into or mistaken for
`WorldOutcome`/`EnsembleOutcome`, which stay the deterministic factor-level read. The two can be
reported side by side (what the deterministic chain says the factors do; what grounded people
say they would do under that world) but are never combined into one statistic. *Done when:* a
fictional world model and a fictional population produce both a `WorldOutcome` (unchanged path)
and a respondent `FieldworkDataset` whose answers trace to specific persona facts, for the same
world.

**5. Origin and evidence.** `DataOrigin.SCENARIO_MODELLED_PANEL` (new member, beside
`MODELLED_AI_PANEL` in `domain/fieldwork.py:59`), never in `NON_EVIDENCE_ORIGINS` and never
automatically in `CLIENT_ADMISSIBLE_ORIGINS` — it is added to the allowlist only once chunk 8's
scoring loop records at least one non-contaminated, eligible `PredictionScore`. A new instrument
policy `aia-instrument-evidence-3`: `MEASURED` claims refused always (as `-1` and `-2`); client-
facing claims require a disclosure naming the scoring record and its forecast horizon, distinct
wording from "modelováno: AI respondenti z populace" (something in the shape "modelováno: scénář
nad AI respondenty, skóre k datu…").

**6. Sociomap compatibility guard.** `research_sociomapping.py`'s dataset reader refuses (not
warns) a `FieldworkDataset` whose respondents carry more than one distinct `InoculatedWorld.sha256`
(`domain/simulation/inoculation.py:442`, content-addressed), and a request to combine two
respondent datasets from different worlds into one Sociomap run. **Not keyed on `FS_WORLD_ID`
or `world_id()` alone**: `world_id()` (`domain/simulation/reference.py:83-87`) is purely a
function of `world_index` — `world_001` for index 0 regardless of seed or world model — so two
different runs' first worlds share a display id while differing in seed, world model and
content. A guard keyed on the display id would pass exactly the mixed-world case it exists to
catch. Test: a dataset built from two worlds with identical `world_id`/`FS_WORLD_ID` but
different `InoculatedWorld.sha256` (different seeds or world models at the same index) still
raises `sociomap_mixed_worlds_refused` before any statistic is computed.

**7. Cost and workflow wiring.** A `SIMULATION` workflow's respondent-run step reserves budget
at `n (respondents) x worlds x variants x blocks` requests, through the same `reserve_budget`
path research fieldwork uses; it parks in `AWAITING_BUDGET` under the same rules
(`CLAUDE.md` §10, `workflow_repository.py:1017-1059`), never a silent partial run across worlds
(mirrors the ablation budget-exhaustion refusal `panel-grounded-respondents.md` §7 already
documents for arms).

**8. Scoring loop.** `freeze_prediction`/`record_truth`/`score_prediction`
(`results.py:380,409,478`) are typed to `VariantResult`/`FrozenPrediction`, i.e. the
deterministic ensemble's factor distributions — they are not reused as-is for respondent
answers, since a respondent dataset's shape (per-question option shares across a sampled,
weighted population) differs from a factor's weighted scale-point distribution. This chunk
ports the same three-step pattern (freeze blind and pre-registered -> write truth once, after
the fact -> score, eligibility carried by the frozen record alone) to the respondent dataset:
a new `FrozenRespondentPrediction` over the dataset's own per-question distributions, scored by
the same `score_distribution` (`results.py:446`) once a person records the real outcome. This is
the only path that can ever move `SCENARIO_MODELLED_PANEL` into `CLIENT_ADMISSIBLE_ORIGINS` for
a given respondent system + world-model fingerprint pair. The deterministic ensemble's own
`FrozenPrediction` path is unaffected and keeps scoring the factor chain exactly as it does today.

## Dependencies

- `panel-grounded-respondents.md` chunks 7f-7h (recorded verdict) — hard blocker, chunk 0.
- `simulation-studio.md` S0-S4 (SIMULATION workflow type, population adapter, executor,
  variant freezing) — this plan's chunk 4 and 7 assume S1-S4 exist; if the studio's own plan
  is picked up first, coordinate chunk ownership rather than duplicating the executor.
- `population-operations.md` P3 (a run records its population binding) — already done,
  consumed by both this plan and the studio plan.

## Findings

None yet; this is a design plan, not a landed chunk.

## Doc follow-up

- `docs/architecture/simulation-deterministic-engine.md` §8 ("Not built"): once chunk 4 lands,
  move "the respondent run per world" from Not built to a dated, anchored entry.
- `docs/architecture/population.md`: note that `FS_*` columns may become persona input under
  `FieldUse.PERSONA_CONSTRUCTION`, gated exactly as every other field.
- `ARCHITECTURE.md` §6 A6 (enum drift): add `SCENARIO_MODELLED_PANEL` to the audited enum list.
- `.planning/overview.md`: record this plan against D9/D10/D11's simulation scope questions,
  without re-opening them.

## Review outcome

Not yet reviewed.
