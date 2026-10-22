---
status: in-progress
chunks:
  - "[x] RQC0. A per-respondent checkpoint (OI-64): each answered respondent and its paid-call identity are stored under the lease; a retry resumes; a possibly-billed uncertain call requires recovery and never triggers an automatic paid replay"
  - "[ ] RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker"
  - "[ ] RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity"
  - "[ ] RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)"
  - "[ ] RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination"
  - "[ ] RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers; its ADR and deterministic admission rule (ADR 0026 decision 4) come first"
  - "[ ] RQC6. Quotas before a run and a support forecast for the panel path (split 2026-10-22 into RQC6a-RQC6d, owner: the Vzorek session)"
  - "[x] RQC6a. Domain: a panel sample's quota cells (the sampler's own largest-remainder allotment) and the support forecast from a drawn panel sample, through the roster path's donor_support and analysis gate"
  - "[x] RQC6b. Application and API: readiness draws the panel sample a start would draw (fieldwork_seed, the design's filters, the population the run would record) and carries its forecast and quota cells; the audience preview carries its quota cells at PREVIEW_SEED; unknown, said why, without the population"
  - "[x] RQC6c. Web (artifact-sample SMP2): Vzorek's composition as quota cells, each sample:quota:<cell>, and the panel run's forecast in words"
  - "[ ] RQC6d. Journey (artifact-sample SMP6): Vzorek's panel composition and forecast at 1440, 1100, 768 and 390 px over the population double, zero paid jobs"
  - "[ ] RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code"
  - "[ ] RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks"
  - "[x] RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead"
  - "[x] RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05"
  - "[ ] RQC11. Routing in fieldwork (W1, after working-copy-edit-ops WCE13): a conditional question is asked only of respondents whose earlier answer meets its condition, and the dataset records who was not asked"
  - "[ ] RQC4a. W1 flag contract: deterministic QC flags, ids, lineage and accept-target schema before the W3 model-worker proposal"
  - "[ ] RQC12. Weight identity over HTTP: weight_role and weight_column in the run's population note and in the report's method section (G78)"
  - "[ ] RQC13. Fieldwork shows a question's stimulus to each respondent before the question, recorded in the answer's provenance (D-45)"
---
# Run QC and a fieldwork checkpoint

Fieldwork that does not repay on retry, and the run QC that the Fieldwork and Results artifacts show. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-2-sample-execution.md`; OI-64 was owned only by `research-agent-workflows` I4.

**Owner: S2.** Takes the gap rows G26, G27, G29 and interfaces I6, I7 of `mvp-master-plan.md` §6.1 and serves AC-05, AC-06, AC-08 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Respondents are population-built by default; invented respondents only for tests (Q17).
- Straight-liners: no pause after fieldwork; a warning, then the worker proposes keep or flag; replace is a new linked run (F18, Q22).
- Fieldwork that is killed loses no work (AC-06); this is an engineering prerequisite, not a product choice (the owner, 2026-10-19).

## Chunks

**RQC0. A per-respondent checkpoint (OI-64): each answered respondent and its paid-call identity are stored under the lease; a retry resumes; a possibly-billed uncertain call requires recovery and never triggers an automatic paid replay**  
Each attempt starts at the first respondent and stores the dataset only at the end (`ai_fieldwork.py:283-326`), `max_attempts=3`, a clean shutdown is a RETRY (`workflow.py:660-686`), and the plain whole-run `retry` of a failed or cancelled run "spends again" (`research.py:835-862`). **Narrowed after the independent review: `retry_analysis` reuses the frozen dataset and never recollects fieldwork (`research.py:865-895`), so the claim covers interrupted fieldwork and the plain retry, not an analysis retry.** Shape: the `client_work_journal` pattern. Test: kill the worker mid-fieldwork; the retry spends nothing for respondents already answered. **First S2 item in W1, before any step that runs after fieldwork.**

**RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker**  
There are three definitions today (`sociomap/engine.py:84-109`, the unit QC `qc.py:200-207`, the workbench D17). Interfaces I6.

**RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity**  
`evidence-integrity` 2 and 3 produce the artifact and its display; this chunk puts it in the graph.

**RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)**  
`material_rules.py:59-70` has none. Interfaces I16.

**RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination**  
Per F18 nothing pauses; a proposal waits. The accept destination is a field of the run's QC record.

**RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers**  
Per F18 replacement is a new linked run. **Prerequisite (ADR 0026 decision 4, Accepted):** respondent replacement gets no command until its own ADR and a deterministic admission rule exist (respondents are drawn once per run); the feature is settled, the ADR is the work. The weighting and support meaning of a replacement is a **methodology dependency** and sits in the master decision register (`mvp-master-plan.md` §11.4); the chunk builds the mechanism the owner decided and labels its limits.

**RQC6. Quotas before a run and a support forecast for the panel path**  
The preview drops the composition and readiness does not call the previewer for the panel; `support_forecast` is unknown for a panel run today.

Split 2026-10-22 (assigned by the PM to the Vzorek session; SMP2 and SMP6 of `artifact-sample` wait on it).
What the code already says, and what the split rests on:

- A panel run's sample is not a guess before the run. Fieldwork draws it with
  `draw_panel_sample(population, spec.selection.audience_filters, spec.n, fieldwork_seed(spec))`
  (`panel_source.panel_plans`; `ai_fieldwork.py`, `seed = fieldwork_seed(spec)`), the seed the
  roster forecast already uses (`support_forecast._statuses`). Drawn over the population the run
  would record, the readiness forecast is that run's sample, not an approximation. The preview's
  `PREVIEW_SEED` stays the preview's; readiness uses the run's seed.
- The quota cells are the sampler's own: `representative_draw`'s largest-remainder allotment
  (`Draw.quotas` over `Draw.quota_fields`, the unit's `_quotas`, held to
  `fixtures/representative_draw`), which `PanelSample` drops today. They say how the n is spread,
  never that a pair of objects will have support: the Sociomap's pair support is read from the
  data (audit F3), and no word says a quota guarantees it.
- Support uses the rules a start would pin (`SupportSpec` in force, the aggregation slots), as
  the roster path does. Unknown is never good: no population, a refused draw, a selected child
  population (P4d) or a version other than the one a start would record reads unknown, with the
  reason.

**RQC6a. Domain.** `PanelSample` carries its quota cells (fields and allotment), outside
`provenance()`, so no recorded run changes. `forecast_support` takes a drawn panel sample: its
donors and analysis weights through `donor_support` and `reassess_support`, as the roster's.
`reportable_n` stays the roster's only (a panel search would draw the population per candidate).
Tests: the cells equal `representative_draw`'s quotas on the captured cases; a panel forecast
over a fictional population equals donor_support on the sample's own donors; no sample, unknown.

**RQC6b. Application and API.** `ResearchRuns.readiness(…, persona_source=panel)` draws the
sample through a process cache of the run population (the audience previewer's loader, keyed by
the population the run records, `RunPopulationDep`), only when the panel is chosen, which the
persona-source switch (`AIA_AI_POPULATION_PERSONAS_ENABLED`) already gates. The readiness body
gains `sample_composition` (quota fields, cells with a Lead-safe id, the seed, the version);
`/population/audience-preview` gains its cells at `PREVIEW_SEED`. The draw's cost on the
population is measured and stated in the PR. Tests: readiness on a panel design over the
population double states the run's donors and cells; without the population root, unknown.

RQC6a delivered in #690: `PanelSample.quota_cells` (`QuotaCell`, out of `provenance()`) and
`forecast_support(…, sample=)`; tests `test_population_sampling.py::test_a_samples_quota_cells_are_the_units_largest_remainder`
and `::test_a_panel_forecast_reads_the_sample_a_start_would_draw`. Metodika's `sample_base` and
`kish_sample` pins moved with `draw_panel_sample`.

RQC6b delivered: a sample drawn at any seed but `fieldwork_seed(spec)` reads unknown (the
domain's one guard, review on #690). `AudiencePreviewer.panel_sample` keeps the last 32 draws per
(version, filters, n, seed); `dependencies.get_panel_sampler` binds it to the request's session
only when the previewer reads the population a new run records, so the workbench's stand-in
audience reads unknown. Readiness (both routes), `POST …/research/runs` and the Lead's typed
start (`RunStartSettings.panel_sampler`) draw the same sample, so the gaps a person acknowledged on
readiness are the start's; a start over a selected child or a retry draws none (unknown, as
before). Readiness answers `sample_composition` (refused, version, seed, quota fields, cells with
a `key`, donors); the audience preview's `sample` gains its `quota_fields` and `cells` at
`PREVIEW_SEED`. Measured: readiness over the double (3,000 rows) 102 ms with the population cold,
45 ms warm with the draw cold, 28-36 ms cached; the draw alone over 18,766 rows (LIVE's size)
41 / 62 / 127 ms at n 300 / 1,000 / 3,000. Test
`test_population_double_api.py::test_readiness_draws_the_panel_sample_a_start_would_draw`,
`::test_a_start_draws_the_sample_readiness_drew` and
`::test_a_population_that_will_not_load_reads_unknown_never_fails_readiness` (a load failure is
`refused: population_unavailable`, never a 500).

Open from RQC6b's review, each a hypothesis until reproduced over HTTP:
- A refused panel draw (`sampling_n_exceeds_support`, `sampling_field_refused`) is named in
  `sample_composition.refused` but is no readiness check, so a start goes ahead and fieldwork fails
  on the same refusal; a FAIL (or WARN) check from the refusal is a readiness rule of its own.
- (Fixed on #694 after review: readiness takes the run's `population_version_id` and draws nothing
  over a selected child, as its start; Spuštění forwards its chosen child.)

**RQC6c. Web (SMP2).** Vzorek's §1 composition from `sample_composition`; `sample:quota:<cell>`
on each cell; the panel forecast's words in §2; unknown said with its reason.

**RQC6d. Journey (SMP6).** The workbench journey reads Vzorek's panel composition over the
population double at four widths; zero paid jobs.

**RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code**  
Written first by S2; consumed by the Fieldwork artifact (`research-lead-workbench` 19). Interfaces I7.

**RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks**  
The panel default needs the route widened and the API reads no egress key. Shares the composition record of `lead-orchestration#LO12b`.

**RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead**  
Four ranges today: web 50-5000, Lead 30-40,000, readiness 20-10,000, the sampler.

**RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05**  
Fictional rows cannot meet the v17 contract, so the existing panel tests inject a loader. Written with the acceptance harness (`mvp-acceptance-harness` 4).

## Open: owner clarifications

- The weighting and support meaning of a replaced respondent (a method question; RQC5 builds the mechanism and labels the limit).


## Execution predecessors (2026-10-20)

RQC9-RQC10 land in W0: the single valid-n contract and population double precede the W1 UI and
HTTP journey. RQC0 is first in W1 before resumed fieldwork; RQC1-RQC3, RQC4a and RQC6-RQC8
then supply the deterministic QC contract/node, readiness/support and Fieldwork events. The
Fieldwork artifact cannot be called integrated before it consumes RQC7's real payload.

RQC4's model-worker proposal/accept implementation and RQC5's linked replacement land in W3,
after the shared contracts: RQC4's accept-result type precedes LO9b's binding; the executable proposal follows that binding. RQC4a separates the earlier typed
flag contract from that paid worker. Replacement also needs its own ADR and approved weighting,
effective-n and support semantics; preparing storage/refusal tests does not approve those semantics.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**RQC11. Routing in fieldwork (G53, X8; the owner, 2026-10-20: build routing end to end).** Fieldwork today asks every respondent every question, and readiness refuses a conditional one. With `working-copy-edit-ops#WCE13` storing valid conditions, this chunk evaluates each condition on the respondent's own earlier answer, in questionnaire order, asks the question only when it holds, and records "not asked" distinctly from a missing answer, so the filtered base is computable. The checkpoint (RQC0) keeps routing state per respondent. Tests: Q7 is asked only of respondents who answered "never" to Q2; the dataset distinguishes not asked from not answered; a resumed run routes the same way.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** RQC12 (W1). RQC13 (W2, after `working-copy-edit-ops#WCE14`); a stimulus changes the
respondent's input, so its prompt part is pinned with the run like the rest of the respondent system.

**Existing chunks, changed.**

- **RQC4 / RQC5 (D-36).** After a replacement the report and the Lead read the newer run and name
  both.
- **RQC9.** The valid-n authority is the organization's readiness methodology in force, not a code
  constant.
- The attention check (D-43) is **out**.

## RQC9, delivered (2026-10-20, branch `feature/w0-n-authority-population-double`)

**The rule.** `sample_size_problem(n, limits)` in `domain/research_design.py` is the one judgement of
a valid n: a whole number within the readiness limits in force, both bounds included; a boolean, a
fraction or text is `sample_size_missing`, a whole number outside the range
`sample_size_out_of_range`. Nothing clamps. Readiness's `sample_size` check calls it.

**The authority.** `application/research.py` `readiness_in_force(session, scope)`: the
organization's readiness methodology in force (a stored version, else the preset
`aia-readiness-1`, 20-10,000), as the scope-freeze note on RQC9 requires. A run start pins it as
before (`ResearchRuns._readiness` now calls it); the three readers below read the same function.

- **The web** reads `GET /api/v1/studies/{study_id}/research/limits` (`ResearchLimitsResponse`:
  `methodology_version`, `version`, `sample_size {min, max}`). Its own 50-5,000 copy is gone
  (`research/persona.ts` `setSampleSize`, `PersonaStep.tsx` `SampleInput`). A value outside the
  range, an empty field or anything but a whole number is **refused and said, never stored and never
  clamped** (finding IA-1 closed): the field keeps what the person typed, `role="alert"` says the
  range, the presets and the recommendation are disabled where the range does not admit them, the
  slider's thumb range sits inside it. Limits not yet read disable the field; limits that cannot be
  read refuse every value and say so (unknown is never presumed to admit a value).
- **The Lead** is frozen with the limits (`design.readiness` in the turn's context,
  `domain/research_lead.py` `readiness_layer`). `ground_edits(…, sample_size=)` drops a `set_n`
  outside them by name at the turn; `apply_edit(…, sample_size=)` refuses it at the accept under the
  limits in force *then* (`decide_edits`), so a version activated while the Lead worked is what is
  enforced. The closed schema keeps only `ge=1`: its old 30-40,000 was the fourth range. The harness
  moved to `aia-research-lead-2`, so a turn queued under 1 (no limits frozen) is refused by the
  executor's existing harness check rather than grounded without limits.
- **The sampler** is not a fourth authority: it draws the n the run was started with, and a start
  is refused below or above the readiness limits before any draw.

**Tests.** `test_research_design.py::test_the_one_rule_for_a_valid_n_refuses_and_never_clamps`,
`::test_a_valid_n_is_judged_by_the_limits_given_not_the_preset`;
`test_research_lead.py::test_a_set_n_is_held_to_the_readiness_limits_at_the_turn_and_at_the_accept`,
`::test_a_set_n_with_no_limits_known_is_dropped_and_refused_never_presumed_valid`;
`test_methodology_api.py::test_the_study_reads_the_valid_n_in_force_and_an_activation_moves_it`;
`test_research_lead_api.py::test_a_sample_size_is_accepted_only_within_the_readiness_limits_in_force`;
`test_research_lead_executor.py::test_a_sample_size_outside_the_frozen_readiness_limits_is_dropped_by_name`;
`PersonaStep.test.tsx` "the sample: a value outside the server's valid n is refused and said, never
clamped (IA-1)", "… a narrower range in force disables …", "… with the range unread nothing is
stored …"; `persona.parity.test.ts` "the input: a value the classic stored as typed is stored the
same; one it clamped is refused".

**A deliberate departure from 18.6.6.** The classic input's clamp (`PROJECT.n=Math.max(50,
Math.min(5000, …))`) is not ported: the parity test now pins what still matches (an in-range value
is stored as the classic stored it) and asserts the refusal where the classic clamped.

**Left for the input-interactions plan (not this chunk).** IA-3, one stepper replacing the field and
the slider, is that plan's B1; the slider here only stays inside the range.

## RQC10, delivered (2026-10-21, branch `feature/w0-n-authority-population-double`)

**The double.** `packages/aia_core/src/aia_core/application/population_double.py`: one fictional
population (the sampler's 3,000 fictional rows on 400 donors, the fictional signal catalog, the
unit's value labels and a joint certificate naming the panel) under a contract of its own
(`aia_population_double/v1`, LIVE `DOUBLE_FICTIONAL_LIVE`), built from deterministic bytes so two
processes build the same contract and source independently, and established through
`PopulationRuntime` as an operator would (`establish`, idempotent; LIVE's audience catalogue kept).
Nothing bypasses the canonical loader, the field policy or the certificate gate.

**Composed in both processes, by configuration.**

- **API**: `AIA_POPULATION_DOUBLE=true` (`Settings.population_double`).
  `dependencies.install_population_double` composes it at start without touching the database (the
  schema may not exist yet); the first request that needs it establishes it in its own transaction
  (`get_run_population`, `get_audience_population`, `get_audience_previewer`). A new research run
  then records the double's LIVE (`RunPopulationDep` on `POST …/research/runs`), and the audience
  catalogue and preview read it. Off, every deployment records the Czech LIVE exactly as before.
- **Worker**: `AIA_WORKER_EXECUTORS=aia_executors.population_double:build_registry` is the production
  registry (`registry.build_registry(population=…)`, a new keyword the factory is never called with
  by name) with the panel path's loader replaced by the double's. Everything else, the AI runtime,
  the gateway's gates and the Class A panel request, is production's.

**Never in a deployment.** The double refuses any `AIA_ENV` but local and test before it reads a
byte (`population_double_problem`; unset and unknown refuse); `Settings.validate_for_production`
refuses the switch in develop, staging and production; `tools/layer_check.sh` allows only
`apps/api/src/aia_api/dependencies.py` and `apps/executors/src/aia_executors/population_double.py`
to import it, forbids it in the worker and the rest of the core, and forbids `deploy/` and `infra/`
naming it -- the rules the workbench composition and recorded web retrieval are kept by.

**One builder.** The executors' panel tests (`apps/executors/tests/grounded_world.py`) and the API's
audience fixture (`apps/api/tests/conftest.py` `fictional_live`) carried two hand-copied builders
of the same population; both are now the double under their own names, so the panel path those
tests prove is the one tier A drives (the files that use them pass unchanged: 54 tests in
`test_ai_fieldwork.py`, `test_validation_executors.py` and `test_deep_research_planned_recovery.py`,
26 in `test_population_api.py`). `tools/ui_workbench/fictional_population.py` (a third
copy, with its own `wb1_*` labels and no persona companions) is left for its own change: its labels
are what the workbench journeys read.

**Tests.** `packages/aia_core/tests/test_population_double.py` (refusals per environment, determinism
across two builds, idempotent establishment, a load from a second build);
`apps/api/tests/test_population_double_api.py` (every deployed environment refuses the switch; a
panel run over HTTP records the double's LIVE; the audience step reads it);
`apps/executors/tests/test_population_double_worker.py::test_a_panel_run_over_http_is_answered_from_the_double_the_worker_composed`
(an API with the double, a worker with a double of its own, a scripted Bedrock: the run's fieldwork
step is `MODELLED_AI_PANEL` from the recorded LIVE, one request per respondent per block), and the
worker composition's refusals and its equality with the production registry's step kinds.

**What tier A still needs from other plans.** The recorded model doubles behind the gateway
(`mvp-acceptance-harness#4`) and the harness itself (`#3`); this chunk supplies only the
population. A live AC-05 run on develop reads the Czech LIVE, never this.

## Review of #539 (2026-10-21), fixed on the branch

- **P2-2, RQC10: establishing raced on a fresh database.** The audience step reads its catalogue and
  its preview at once (`AudienceStep.tsx:100`, `:425`), so two first requests both found nothing and
  both imported: a unique-constraint 500. `PopulationDouble.establish` now writes in a savepoint and,
  when another transaction got there first (`IntegrityError`, or the registry's `PromotionRefused`),
  reads back what it wrote. The API establishes it inside the asking request's own transaction
  (`dependencies.ensure_population_double`, through `SessionDep`), so it commits with that request.
  Tests:
  `test_population_double.py::test_two_concurrent_first_establishes_both_get_the_one_live` (two
  threads, both read before either writes; PostgreSQL, skipped on SQLite, which admits one writer),
  `::test_an_establish_that_read_before_another_committed_reads_back_what_it_wrote`,
  `test_population_double_api.py::test_concurrent_first_requests_establish_the_double_once` (two
  request transactions at once; PostgreSQL). Both core tests fail with the savepoint's handler
  removed (measured).
- **P3-3, RQC10: an unset `AIA_ENV` composed the API's double.** The settings read an unset
  `AIA_ENV` as local (`config.py:37`); the API now passes the environment to the double only when
  it was named (`Settings.model_fields_set`), so unset refuses as it does in the worker
  (`test_population_double_api.py::test_an_unset_aia_env_refuses_the_double`).
- **P3-4, RQC9: a design variant stored its n unchecked** (`research/plan.ts` `applyVariant`). It now
  takes the server's limits: an n outside them (or unread limits) is not stored, the plan still is,
  and the toast says why; while the limits load nothing is applied. `persona.ts` `sampleRefusal` is
  the one web check both screens use. Tests: `plan.parity.test.ts` "a variant's n is held to the
  server's valid n (RQC9)", `PlanStep.test.tsx` "applies a variant whose n the valid range refuses
  without its n, and says so".
- **P3-5, RQC9: the slider left the valid n** when its maximum is under 250. `PersonaStep.tsx`
  `sliderRange`: 200-2,000 in steps of 50 cut to the range, else the whole range in steps of 1; its
  ends are always inside (`PersonaStep.test.tsx` "the slider's ends sit inside the valid n").
- **P3-6, RQC9: refusals showed as codes.** `lib/lead.ts` `editRefusalWords` / `droppedLines`: a
  refused or dropped edit in Czech, the sample-size reasons included; the Workbench says why a
  clicked edit was refused, and the Lead pane names a dropped sample size on its own line
  (`lead.test.ts` "a refused or dropped edit says why in words (RQC9)").

## Doc follow-up (RQC9, RQC10)

- `CLAUDE.md` §2: under `routers/` research, `GET …/research/limits` (the readiness limits in force,
  the valid n the web refuses outside of); under `application/`, `population_double.py` (LOCAL AND
  TEST ONLY: the fictional population both processes compose for tier A, refused outside local and
  test); under `aia_executors/`, `population_double.py` (the production registry with the panel
  loader replaced by the double's; refuses outside local and test); `dependencies.py`: the population
  a new run records (`RunPopulationDep`: the Czech LIVE; the double only under
  `AIA_POPULATION_DOUBLE`); `research/persona.ts`: the sample input refuses outside the server's
  range, never clamps (IA-1); `domain/research_lead.py`: `set_n` held to the readiness limits frozen
  in `design.readiness` (harness `aia-research-lead-2`).
- `ARCHITECTURE.md` §3, five rows: "nothing in the core / the worker imports the population double;
  in the API only the composition root; among the executors only its composition; no deployment or
  infrastructure definition names it" | prevents "a fictional population reaching a deployed run, or
  a deployed process composed with it".
- `ARCHITECTURE.md` §4 (population): a run records the deployment's LIVE; in local and test, the
  population double's when `AIA_POPULATION_DOUBLE` composes it.
- `.planning/open-items.md`: IA-1 closed by RQC9 (anchor `research/persona.ts` `setSampleSize`, test
  `PersonaStep.test.tsx` "the sample: a value outside the server's valid n is refused and said, never
  clamped (IA-1)").
