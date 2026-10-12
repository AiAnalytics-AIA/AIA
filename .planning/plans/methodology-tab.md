---
status: in-progress
chunks:
  - "[x] 0. ADR 0023 and this plan"
  - "[x] A1. Framework: methodology package -- module, step, group, parameter, constant, preset; completeness and source-hash tests (slots land with A2)"
  - "[x] A2. Expression language: parser, whitelist, compiler, LaTeX generator, slot properties on a grid; no eval"
  - "[x] A3. Version store: methodology_versions + methodology_activations (migration), repository, audit"
  - "[x] A4. Run pins: every module's in-force version pinned at start, retry keeps it, fingerprints carry it"
  - "[x] A5a. API: GET /api/v1/methodology and /{module} (steps, values with origin, evidence, tests); read-only"
  - "[x] A5b. API: methodology version routes (after A3)"
  - "[x] A6. Web: the Metodika tab shell -- module list, step cards, MathML (Temml), parameter tables; read-only"
  - "[x] S1a. Sociomap documented: the object map (aia-sociomap-3 / -2) in the audit's order F1-F16"
  - "[x] S1b. Sociomap documented: the reference map aia-sociomap-1 (contract 2, F1-F9 fixtures)"
  - "[x] S1c. Sociomap documented: the experimental H-Model candidate (read-only)"
  - "[x] S1d. Evidence register: rules for the uncovered steps, the wrong pointers fixed (own PR)"
  - "[x] S2a. Sociomap declared: the object map's own constants (K100 quantiles, Stress bands, the three-object minimum) in the spec; preset aia-sociomap-4"
  - "[x] S2b. Sociomap declared: the reference set's side tables and K100 read the run's object-map pin; a layer check keeps the constants off run paths"
  - "[x] S2c. Sociomap declared: the readiness warning reads the organization's methodology in force"
  - "[x] S3. Sociomap slots: built-in expressions for every F-formula, bit-identical on every fixture"
  - "[x] S4a. Sociomap editable: the editor in the tab -- every spec field and formula slot, the domain's check at the field, store, activate with a reason, back to the code, history"
  - "[x] S4b. Sociomap draft check: the edit beside what is in force on fixed fictional panels (maps, Stress, statuses, aligned shifts, heights, K100 point, terrain)"
  - "[ ] S4d. Draft check: the audit's printed checks C1-C16/P4-P14 run on the draft (blocked: their inputs are with the audit's author, sociomap-formula-corrections 0a)"
  - "[x] S4c. The engine computes a stored formula expression (COMPUTED_SLOTS), slot by slot, bit-identical when unchanged"
  - "[x] G1a. Support documented: both rule sets side by side, read-only (the unit's donor rule as Results shows it; AIA's evidence gate as analysis applies it), D1-D4 named on their steps"
  - "[x] G1b. Support declared: a specification with both rule sets as presets, bit-identical; each surface reads its own preset"
  - "[x] G1c. One rule set: Results and analysis read the support version in force (the default is the owner's call, finding D2)"
  - "[x] G1d. Support editable both ways, with the draft check listing every row a change newly reports or suppresses (ADR 0023 decision 10)"
  - "[x] G2a. Aggregation documented and declared: estimators, Kish, bootstrap reps/seeds/quantiles, top-2-box in AggregationSpec (aia-aggregate-1, the unit's literals bit for bit); D1, D5, D7 named on their steps"
  - "[x] G2b. Aggregation slots: the estimators as formula expressions, bit-identical on every aggregate fixture"
  - "[x] G2c. The 18.6.6 deviation label: an aggregate computed under any version but aia-aggregate-1 says it is no longer the unit's port"
  - "[x] G3a. Aggregation pinned: a run pins the aggregation version in force (spec + replaced formulas), a retry keeps it, the aggregate computes under it and its deviation label is reachable"
  - "[x] G3b. Aggregation editable, with the draft check on fictional panels (estimates, intervals, status changes); support is editable since G1d"
  - "[x] G3c. The 18.6.6 deviation carried past Results: analysis and the report say when the aggregate they read is no longer the unit's port"
  - "[x] W1a. Weighting documented and declared: schemes, default role, expected totals and tolerances, the aggregate's weight cleaning (aia-weighting-1, the import contract's declaration exactly); D1 reproduced on its steps"
  - "[ ] W1b. Weight cleaning a choice a run reads: the weighting pinned per run, a retry keeps it; refuse refuses an aggregate with an invalid weight by name; a non-median cleaning is a deviation from 18.6.6"
  - "[ ] W1c. Weighting editable: the cleaning and the default role, with the draft check on fictional panels; the contract's columns, totals and tolerances stay its facts"
  - "[ ] R1. Response process documented, declared and editable: betas, satisficing, style links, noise floor, temperature"
  - "[ ] V1. Validation tiers, admission tolerances, readiness bounds, presentation rounding: documented, declared, editable"
  - "[ ] X1. Simulation documented read-only; declared and editable when it is wired into runs"
  - "[x] Z1a. The path walked on the workbench for the Sociomap, support and aggregation (edit, check, compare, store, activate, run, Results); Results name the methods a run computed under"
  - "[ ] Z1b. The walk as committed workbench journeys per module, run like make ui-research; Doc follow-up"
---
# The Metodika tab — every formula and statistic in AIA, shown from the code and editable by the methodologist

**Written:** 2026-10-11 against `develop` @ `27062ec` · **Branch:** `feature/methodology-tab`
· **Decision:** [ADR 0023](../../docs/architecture/adr/0023-methodology-is-data-the-methodologist-owns.md)

## Problem

The methodologist who keeps AIA's mathematics and statistics correct cannot see them or change
them. The owner's requirement is that **any mathematics or statistics in AIA is directly
accessible to them: visible, and editable down to the formula**, with the audit *NPC Sociomapa:
faulty formulas in the code* (A. Bahbouh, 2026-10-06) first among them. Today every formula and
constant is Python, changed through a branch, CI and a deploy.

## How the work is ordered

- **Phase A: the framework, built once.** Phases S, G, W, R, V and X then each take one module
  through the same four steps:
  1. **documented**: the tab shows it read-only;
  2. **declared**: its loose constants move into a specification, bit-identical;
  3. **slotted**: its formulas become expressions, bit-identical;
  4. **editable**: drafts, the check, activation.
- **The Sociomap goes first** because the audit asks for it. Support and aggregation come next
  because they gate every client number.
- **Each chunk is its own PR.** Chunks that touch files another open plan edits are flagged
  below.

## Inventory (`27062ec`), what each module covers

### Sociomap, in the audit's order

The status in AIA comes from `sociomap-formula-corrections.md`.

| Audit | Formula in AIA | State | Editable as |
| --- | --- | --- | --- |
| F1 | declared scale ends → 0–1, `engine_v2.py:131-147` | built (contract 3); register pointer null | slot (transform) |
| F2 | per-person min–max over every rated item, then Pearson, `relations.py:321-344` | built | slot (normalisation, exclusion rule) |
| F3 | weighted Pearson, Kish n_eff, Fisher interval, `n_min` 30, UNKNOWN / WEAK / RELIABLE, `pairs.py:205-298`, `relations.py:403-526` | built | parameters (`n_min`, confidence, floor); slots (estimator, n_eff, interval, status rule) |
| F4 | signed strength beside \|r\| | built (stage 2a) | slot (display mapping) |
| F5 | declared matrix type, `relations.py:262-294` | built | choice |
| F6 | δ = √(2(1−r)), SMACOF on the fixed ruler, `layout.py:687-894` | built | slot (δ); algorithm choice; parameters (iterations, tolerance) |
| F7 | one layout, Procrustes as a view, Stress-1 and bands, `view.py:406-493` | built; bands are a module constant | slot (Stress); parameters (bands) |
| F8 | A_i, K_i over known PRIMARY pairs, `metrics.py:488-548` | built | slot |
| F9 | K100 with a respondent bootstrap, type-7 quantiles, `metrics.py:608-808` | built behind `AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED`; quantiles a constant | parameters (resamples, seed, quantiles); slot (score) |
| F10 | ideal-point placement and misfit | **not built** (formula-corrections chunk 3) | slot (misfit) and parameter (flag) when built |
| F11 | NOT PLACED straight-liners, `engine.py:86-108` | built | slot (rule) |
| F12 / F13 | envelope max_j h_j·exp(−d²/2σ²), σ 0.25 provisional, `terrain.py:409-443` | built | slot (kernel, combine); parameters (σ, grid, extent, cutoff) |
| F14 | positioning variables excluded, Holm | **not built** (4d) | choice (multiplicity); parameter (α) when built |
| F15 | Cohen's d and h | **not built** (4d) | slot when built |
| F16 | row-conditional unfolding | **open** (4c) | algorithm choice when built |

Beside the audit's map:
- **`aia-sociomap-1`, the reference.** It is documented read-only as the 18.6.6 baseline (F1–F9
  fixtures), and is a base an edited version may start from.
- **The H-Model candidate, read-only.** `CandidateParameters` has defaults; they are declared in
  S2.
- **Constants outside the specification today:**
  - the side tables' `n_min = 30` and 0.95 (`research_sociomap.py:125,397-421`);
  - K100 resamples and seed (`:128-131`) and quantiles (`metrics.py:608`);
  - the Stress bands (`view.py:406`);
  - `_FISHER_MIN_N` (`relations.py:387`);
  - the three-object minimum (`engine_v2.py:264-295`);
  - the readiness warning's n 30 (`research_design.py:625`).

  All of these move into the specification in S2.

A built-but-not-yet formula (F10, F14, F15, F16) appears on the tab with the audit's proposed
formula and "V AIA zatím není". It becomes a slot in the same PR that builds it, under that plan.

### Aggregation (`research_aggregate.py`, EXACT port; a deviation once edited)

- `clean_weights` replaces an invalid weight with the median (`:158-165`).
- `kish_effective_n` (`:168`).
- Weighted mean, distribution, quantile (np.interp) and variance, ddof 0 (`:176-241`).
- `donor_support`: `effective_n_combined = min(kish·n_layer/n, kish, n_layer, n_core)`, status
  from donors at 25/50 (`:244-273, 64-65`).
- The cluster bootstrap (`:282-399`), with inline replicates 400/350, seeds 20260816 / +i /
  20260818, and level 0.95.
- Top-2-box: x ≥ max − 1.
- The fidelity regexes, which REFUSE absolute-value questions (`:72-140`).

### Support and suppression (`evidence/support.py`)

- `REFERENCE_THRESHOLDS`: `min_cell` 50, `n_guard` 25, `indicative` 50, donors 25/50
  (`:66-81`).
- `assess_support`: SUPPRESS by default (`:125-163`).
- `Interval` and `ReportableEstimate` invariants.
- `analysis/native.py:243-259` passes `effective_n_combined`, rounded to 1 dp, as n_eff.

### Weighting (`population/`)

- `parse_weight` and `analysis_weights` refuse rather than clean (`weights.py:70-118`).
- Four schemes, a default role and expected totals with tolerances (`czech.py:210-226`,
  `validation.py:244-250`).
- There is no calibration, raking or GREG step.

### Response process (`respondent_behavior.py`, EXACT; `ai_respondent.py`)

- Social desirability β = 0.18 + 0.10·sds.
- Acquiescence 0.16; extremity 0.22; "don't know" 0.24.
- Satisficing λ = clamp(0.10 + 0.06·s, 0, 1), capped at 0.35.
- Soft reweighting clamps βs to ±8.
- Style links `_LINKS`, noise floor 0.05, temperature 1.0 (`:67-320`).
- `describe_style` threshold 0.7.

### Validation, admission, readiness, presentation

- **Validation:** `TIER_PERMITS` (`evidence/validation.py:174-184`).
- **Admission:** exact match and `_MAX_DECIMALS` 6 (`evidence/admission.py`).
- **Prose coverage:** 0.5·10^(−d) (`analysis/draft.py:163-165`).
- **Decimals per metric:** `analysis/native.py:353-412`.
- **Readiness:** sample size 20–10000, tracked-set limits (3, 40) and (4, 15)
  (`research_design.py:66-70`).
- **Report numbers:** effective n rounded down (`report/numbers.py:77-86`).

### Simulation (`simulation/`, not wired into runs)

- `reference.py` bounds and seeds.
- `numerics.py`: Higham nearest correlation, counter-based Φ⁻¹ draws.
- `inoculation.py`: driver, residual, bisection calibration of a and b.
- `results.py`: bands, ensemble, delta, truth score.

### Deep Research scoring

It is already ADR 0022's settings. The tab links to it and does not duplicate it.

## Chunk notes

- **A1. Framework. Landed.**
  - `domain/methodology/`: `catalogue.py` (MethodModule, MethodStep, StepGroup, ParameterRef,
    ConstantRef, Preset, Evidence, Symbol), `resolution.py` (`leaf_paths`, `read_path`,
    `read_constant`, `describe`, `module_problems`), and `registry.py` (`MODULES`, empty until
    S1).
  - A constant or function is read only from `aia_core.domain.*`. A path through a declared
    `None` reads `ABSENT`, never a zero.
  - Tests: `packages/aia_core/tests/test_methodology.py`. They cover the framework on a small
    specification over real domain functions, and every registered module's completeness, source
    pins and named tests. They loop over `MODULES` rather than parametrise, so an empty registry
    passes rather than skipping.
  - Slots (formulas as expressions) are not in A1. They land with A2, where they are evaluated.
- **A1. Framework, as planned.**
  - `domain/methodology/` (pure) defines `MethodModule`, `MethodStep`, `Slot`, `Parameter` and
    `ModuleSpecification`. The spec is a frozen Pydantic model with no defaults; its code preset
    is a named constant, and it has a validator and a fingerprint.
  - The Sociomap module wraps `SociomapSpecV3` rather than replacing it.
  - Tests:
    - every specification field belongs to one step;
    - every step's tests exist (AST, as `test_sociomapping_evidence_register.py` does);
    - each step's `implements` function is pinned by `inspect.getsource` SHA256.
- **A2. Expression language.**
  - The grammar is listed in ADR 0023, decision 4. `ast.parse(mode="eval")`, a node whitelist,
    and a compiler to a closure over `math` and `statistics.NormalDist`.
  - LaTeX is generated from the same AST.
  - Slot properties are checked on a declared grid. NaN or ±∞ on the domain refuses.
  - Tests:
    - every forbidden construct is refused: attribute, call to an undeclared name, lambda,
      comprehension, subscript outside an index set;
    - LaTeX round-trips;
    - property failures are named;
    - performance: the F12 kernel over a 65² grid × 30 objects within a stated budget, measured.
- **A2. Landed.**
  - **The module.** `domain/methodology/expressions.py`.
    - `Slot` and `Variable` hold scalars, or vectors with elementwise arithmetic and the
      aggregates `sum`, `mean`, `count`, and `min`/`max` of one vector.
    - `Property` kinds: `non_negative`, `within`, `equals_at`, `non_increasing_in`,
      `non_decreasing_in`, `at_most_variable`; finiteness is always checked.
    - `compile_formula`: `ast.parse(mode="eval")`, a node whitelist, then closures over `math`
      and `NormalDist`.
    - `latex` is written from the same tree, with aggregates bracketed under powers and 1e-12
      written as 10^{-12}.
    - `check_properties` reports one counter-example per broken property.
  - **Bit-identity, tested.** Written the way the engine computes, these expressions give the
    engine's exact bits: the envelope kernel against `terrain.envelope_at` (500 random cases),
    the Fisher lower bound against `relations.fisher_interval`, and Kish's n against
    `relations.kish_effective_n` (200 random weight vectors). This is what S3 relies on.
  - **Refusals, tested.** 22 hostile or foreign inputs are refused, among them `__import__`,
    attribute access, `open`, `eval`, a lambda, a comprehension, a subscript, a string, a
    keyword argument, a chained comparison, `//`, `@`, `~`, starred arguments, and a formula
    that is too long or too deep. A domain error (division by zero, log of a negative,
    atanh(1), overflow, an empty mean) raises and is never a number. A test pins that the
    module calls neither `eval` nor `exec`.
  - **Measured.** A 65 x 65 grid with 30 hills means 126,750 kernel evaluations. They take 1.2 s
    through the closure, against 0.03 s for the engine's own `object_envelope`: about 40 times
    slower. That is acceptable for a step run once per map. If it ever matters, the fix is to
    evaluate whole vectors per call (grid-at-once) rather than one cell per call.
  - **Checked by hand.** The generated LaTeX of the seven test formulas renders through Temml
    0.13.5 with no error. S3 puts the built-in expressions into the web fixture, so the web
    test enforces this from then on.
- **A3. Landed.**
  - **Domain.** `domain/methodology/versions.py` turns a draft into a version and fails closed:
    `validate_version` (every problem at once), `named` (`<base>+e<n>`, written into the
    specification by the store, never by its author), `version_payload` (contract
    `aia-methodology-version-1`) and `payload_sha256`.
    - The specification must validate as the base preset's own type, under the module's own
      validator.
    - Each replaced formula must name a slot, compile in it and keep its properties.
    - `MethodModule.editable` decides which modules can be edited: the object map can, the
      reference map cannot.
  - **Storage.**
    - Tables `methodology_versions` (immutable) and `methodology_activations` (append-only;
      newest wins; NULL means the preset). Migration `c4e6a8b0d2f3` follows `b2d4f6a8c0e1`.
    - Verified on PostgreSQL 16: the upgrade compared with the models shows 0 differences
      across all tables, and downgrade then upgrade round-trips.
  - **Repository.** `infrastructure/methodology_repository.py`:
    - `MethodologyReader` (any member) offers `in_force`, `versions` and `history`.
    - `MethodologyRepository` (`require_administer`) offers `propose`, and `activate` (a version
      number, or None to return to the preset). `activate` validates the version again, because
      one stored under an older engine may no longer compute.
    - Every change is audited as `METHODOLOGY_PROPOSED`, `METHODOLOGY_ACTIVATED` or
      `METHODOLOGY_RESET`.
    - There is no independent-review rule here; access is decision 9's.
  - **Layer check.** Four new rules keep the rows inside the repository (105 rules).
  - **Tests.** `test_methodology_versions.py` (9) and `test_methodology_repository.py` (10); the
    repository tests also pass on PostgreSQL.
- **A3. Version store, as planned.**
  - Tables `methodology_versions` and `methodology_activations`, and their migration.
  - A repository with `propose` (the module's validator plus the slot checks), `activate`,
    `reset`, `history` and `in_force(org)`.
  - `access_audit` actions `METHODOLOGY_*`.
  - Tests:
    - immutability;
    - newest activation wins;
    - `NULL` gives the code preset;
    - nothing stored yields the code preset byte for byte.
- **A4. Run pins.**
  - `ResearchRuns.start` pins `{module: (version, fingerprint, payload)}` for every module, and
    `read_methodology_pin` verifies it.
  - The existing `sociomap.methods` pin becomes the `sociomap` module's pin; legacy runs read as
    today.
  - Tests:
    - an activation changes only later runs;
    - a retry keeps the pin;
    - every artifact's input fingerprint carries the pins of the modules that shape it;
    - a tampered pin fails closed.
- **A4. Landed.**
  - **What a run pins.** `ResearchRuns.start` reads `methodology_in_force_for_study`, which uses
    the Study's own scope, so a start needs no administrator context. When a version is in force,
    `domain.methodology.pins.sociomap_methods_for(payload)` makes it the run's second
    `SociomapMethod`, `aia-sociomap-3+e<n>`; the reference `aia-sociomap-1` stays first. The run's
    metadata gains `methodology: {module, version, name, payload_sha256}`.
  - **Its identity.** The idempotency key carries `:methodology:<sha16>`, so the same revision under
    an edited methodology is another run, and that run is idempotent. It goes through the spend
    confirmation like any other start.
  - **What already existed.** The existing `sociomap_methods` pin is the module's pin.
    - A retry keeps it: `test_a_retry_keeps_the_methodology_its_run_pinned`.
    - A tampered pin fails the step by name: `test_a_pin_that_does_not_verify_fails_the_step_by_name`.
    - The sociomap step is reused only under the same pins.
    - With nothing stored, a run pins exactly `default_methods()`, as before:
      `test_with_nothing_stored_a_run_pins_the_codes_methods`.
  - **Formulas are not computed yet.** `COMPUTED_SLOTS` is empty, so `activate` refuses a version
    that replaces a formula (`formula_not_computed`). A run must never compute the built-in formula
    while its methodology says another. Such a version is stored and shown, never put in force,
    until the engine evaluates that slot.
  - **Tests.**
    - `apps/executors/tests/test_methodology_run_pins.py`: four tests through the real worker. An
      edited sigma and n_min are computed in the map; an earlier run keeps 0.25; reset gives the
      code's pins again.
    - `test_methodology_repository.py::test_a_version_replacing_a_formula_the_engine_does_not_compute_is_not_put_in_force`.
- **A5. API.**
  - Read: `GET /api/v1/methodology` and `/{module}` (`OrganizationDep`).
  - Write (`require_administer`): `POST /{module}/versions`, `POST /{module}/check` and
    `PUT /{module}/activation`.
  - The API never names a preset (`layer_check`). It asks the domain.
- **A5b. Landed.** These routes are in `apps/api/src/aia_api/routers/methodology.py`.
  - **`GET /{module}/versions`** returns what is in force (`origin: stored | code`), every stored
    version (its whole spec, its replaced formulas and its digest), the activation log, and
    `may_administer`.
  - **`POST /{module}/check`** asks the domain's own `validate_version` and stores nothing.
    - Any member may check.
    - It returns every problem at once, plus `not_computed`: the replaced formulas a version may
      store but not yet put in force.
  - **`POST /{module}/versions`** (201) and **`PUT /{module}/activation`** write through
    `MethodologyRepository`, which runs `require_administer`; a member gets 403
    `insufficient_role`.
  - **Refusals keep the repository's codes.**
    - 404: `unknown_module`, `unknown_version`.
    - 409: `concurrent_edit`, `formula_not_computed`, `version_missing`.
    - Anything else is 422, with `details.problems` field by field.
  - **The old `test_nothing_here_writes`** became
    `test_the_only_writes_are_a_version_a_check_and_an_activation`.
  - **Tests.** `apps/api/tests/test_methodology_api.py`, eight new tests.
- **A5a + A6. Landed.**
  - **The route.** `apps/api/src/aia_api/routers/methodology.py` serves `GET /api/v1/methodology`
    and `/{module_id}?preset=`.
    - It uses `OrganizationDep`, so any member reads it.
    - Its only job is to serialise `describe()`. A value the preset omits is `absent: true` with
      `value: null`, never a zero.
    - There is no write route; a test pins that.
  - **The fixture.** `tools/methodology_fixture.py` writes `apps/web/src/lib/fixtures/methodology.json`
    from the route's own builder. `test_the_web_fixture_is_what_the_api_serves` fails when it is
    stale.
  - **The web tab.** `MethodologyPanel.tsx` is a new Settings tab, "Metodika". It shows a module
    list, a methodology selector, the steps in their groups, and each step's formula, symbols,
    values with origin, evidence, and function and tests. Supporting pieces:
    - `src/lib/methodology.ts`: value wording (absent and null in words, tiny tolerances as
      powers of ten) and grouping;
    - Temml 0.13.5, pinned, used with `trust: false`.
  - **What the tests caught.** `src/lib/methodology.test.ts` renders all of the API's formulas and
    symbols (130). On its first run it found three formulas where `\quad` had run into the next
    letter; that fix is on the S1 branch. A test pins that markup comes out escaped and that
    `\href` is refused, because the page inserts Temml's output as HTML.
  - **Temml version.** 0.14.0 was three days old when this was written, so 0.13.5 (six weeks
    old) is pinned instead.
- **A6. Web, as planned.**
  - `TABS` gains `methodology`, labelled "Metodika", and `OWN_TABS` gains it. The UI is Czech.
  - Inside the tab: a module list; per step, the formula (MathML via Temml, pinned), symbols, a
    parameter table (value, unit, origin, allowed range), evidence (rule, label, source page),
    tests, uncertainty and open question.
  - Number inputs accept scientific notation and negatives. Deep Research's `parseInput` refuses
    both, so it is not reused.
  - Vitest renders every formula in a captured API document.
- **S1a. Landed.**
  - `domain/methodology/sociomap.py` is module `sociomap`. Its presets are `aia-sociomap-3`
    (in force) and `aia-sociomap-2`. It has 22 steps in 16 groups: M, then F1–F16, with F12–F13
    as one group.
  - Every leaf of both presets is shown exactly once. Each step pins its function, cites its
    AUDIT rule (or the Q6/Q7 decision) and names its tests.
  - F5 is empty here: the object map reads no supplied matrix. F14 and F15 are "V AIA zatím
    není", with the audit's proposal. F16 is open and belongs to the reference map. F10 shows the
    audit's proposed placement against `respondent_placement = null`.
  - The constants outside the specification are shown as code: the Stress bands, the K100
    quantiles and generator, `_FISHER_MIN_N`, `_V3_N_MIN_FLOOR` and `FIXED_RULER_EXTENT`. The
    three-object minimum is a bare literal and is named in its step's note. S2 moves these into
    the specification.
  - Tests: `test_methodology_sociomap.py` covers the audit order, the values in force, absent
    vs `None`, code-vs-specification labels, and that every cited register rule exists.
- **S1b. Landed.**
  - `domain/methodology/sociomap_reference.py` is module `sociomap_reference`, preset
    `aia-sociomap-1`. It has 17 steps in six stage groups:
    1. method;
    2. inputs and scale;
    3. relations;
    4. unfolding and frame;
    5. scores;
    6. terrain.
  - All 29 values are shown once.
  - Each step the audit criticises cites the AUDIT rule with the criticism in one line: F2, F3,
    F4, F5, F6, F8, F9, F12 and F16.
  - Evidence is the F1–F9 fixtures and the 18.6.6 functions it ports. The module says it is not
    edited.
  - Shown as code: the 5-rater threshold and 5.5 inside `derive_relation_matrix` are bare literals
    of a ported function. They stay code, because the reference map is not edited.
- **S1c. Landed.**
  - `domain/methodology/sociomapping.py` is module `sociomapping`, the experimental H-Model
    (`aia_hmodel_candidate_v1`). Its one preset is `CandidateParameters()`, the parameters
    every result records. It is shown and not edited (`editable` False, no slots): the
    candidate is an experiment whose search is an open question (AIA-H8), not a methodology a
    run adopts.
  - 16 steps in four groups: inputs (complete respondents only, unweighted; the set's scale),
    relations (signed correlations; the declared matrix), the layout (accuracy as the
    objective, placeability, starts, the smooth, ordinal, exact and repair phases, the frame,
    the search as a whole) and heights and coherences.
  - All ten parameters are shown once, with the values a result records
    (`test_every_parameter_a_result_records_is_shown_once_with_its_value`).
  - Each step pins its function and cites its register rule: AIA-D1, AIA-D2, RTS-N1, RTS-O1,
    RTS-O2, RTS-W3, SOMECS-H3, SOMECS-H6, SOMECS-H7, QED-H2, AIA-H8, AIA-H9. The module says
    `EXPERIMENTAL_AIA` and that it is not SOMECS's method.
  - Shown as code: the frame `_FRAME` (0.05-0.95), the method and status constants, the
    complete-cases rule and `_FEW_OBJECTS`.
  - The plan said the candidate's defaults would be "declared in S2". They need no
    declaration: `CandidateParameters` already is their declaration and is recorded on every
    result. Making them editable would need the candidate to become a methodology a run pins,
    which nothing has asked for.
- **S3. Landed.**
  - `domain/methodology/sociomap_formulas.py` declares 14 slots, each with the expression the
    engine computes: F1 scale, F2 person min-max, F3 Kish n, the lower and upper Fisher bounds,
    the effect floor, F6 distance, F7 Stress-1, F8 alignment, connectedness and height, F9 K100,
    the F12 kernel, and the map's support n.
  - `test_methodology_sociomap_formulas.py` evaluates each against the engine's own function
    (`_scaled`, `person_minmax`, `kish_effective_n`, `fisher_interval`, `meets_effect_floor`,
    `correlation_distance`, `_object_stress`, `primary_scores`, `_heights`,
    `connectedness_100`, `envelope_at`, `_support`). Inputs are random and boundary cases:
    |r| = 1, an empty weight, all known pairs. The values are equal as floats, not
    approximately.
  - `module_problems` now also requires that each built-in formula compiles and keeps its
    slot's properties.
  - The API sends each step's `formulas` (expression, LaTeX written from it, variables,
    properties). The tab shows them in a "Vzorec jako výraz" block, and the web render test
    covers their LaTeX.
  - Algorithms stay code and have no slot: the status classification, the linear quantile, the
    ranking, SMACOF, mappability, and the envelope's maximum over hills.
- **S4a. Landed.** The editor is `apps/web/src/components/aia/settings/MethodologyVersions.tsx`;
  its pure part is `apps/web/src/lib/methodology-edit.ts`.
  - **What an editable module shows.**
    - What is in force, with its origin.
    - Every stored version and what it changes against its base preset (dotted fields, plus
      `ƒ <slot>` for each replaced formula).
    - Activation with a reason, back to the code's preset, and the history.
    - For an administrator, the editor.
  - **The editor starts from the whole specification** of a preset or a stored version.
    - The presets come from `GET …/versions`, a field this PR adds.
    - It offers every specification field the catalogue lists, and each formula slot as an
      expression.
    - A typed value keeps its type: a number takes a decimal comma; nothing coerces across
      types.
    - A field the base lacks is refused, never created (`withPath`).
    - Only a formula that differs from its built-in expression is sent.
  - **The check is the domain's own** (`POST …/check`). Its problems land at the field or slot
    they name; a problem no field shows is listed above the form. A replaced formula is drawn
    from the LaTeX the check writes (`formulas_latex`, added here), with the "not in force yet"
    note while `COMPUTED_SLOTS` is empty.
  - **The API changes.**
    - `ModuleSummary.editable` (the reference map is shown and never edited).
    - `VersionsOut.presets` and `CheckOut.formulas_latex`.
    - The web fixture now carries `presets`.
  - **`Formula` moved** to `MethodologyFormula.tsx`, so the panel and the editor do not import
    each other.
  - **Tests.**
    - `methodology-edit.test.ts` (9, against the API's own document).
    - `MethodologyVersions.test.tsx` (7, a stateful fake of the four routes).
    - Two new API tests.
  - **Seen in a browser** on the workbench, against the real API. The editor stored
    `terrain.sigma` 0.3, showed the domain's `n_min` refusal at its field, drew a replaced
    kernel and put the version in force, with no console error.
- **S4c. Landed.** The engine computes every slot from a version's expression.
  - **The vocabulary.** `domain/sociomap/slots.py` names the 14 slot ids the engine reads
    (`ENGINE_SLOTS`). It knows nothing of the expression language.
  - **Each function takes `slots`** (default `NO_SLOTS`) and calls a replaced slot by its
    variables exactly where its own formula ran. The functions are `_scaled` (F1),
    `person_minmax` (F2), `derive_pair_relations` (F3: Kish n, either interval bound, and the
    floor test), `correlation_distances` (F6), the reported Stress-1 over `stress_terms`
    (F7), `primary_scores` (F8), `_heights` (F8), `connectedness_100` (F9: K and K100 in the
    full sample and every resample), `envelope_at` / `object_envelope` (F12: the kernel at
    the hill's height, its reach at height 1) and `_support`.
  - **The algorithms stay code:** which rows are excluded, which pairs are read, SMACOF, the
    bootstrap draws, the maximum over hills.
  - **A replaced interval decides the status** through `status_of_interval`, the same rule.
  - **The pin.**
    - `SociomapMethod.formulas` carries what a version replaces. It is left out of the stored
      form when empty, so every code preset's pin and `methods_fingerprint` are byte for byte
      as before.
    - `SociomapMethod.slots()` compiles the formulas again on read. It refuses by name a
      formula that does not compile, names no engine slot, or sits on a contract-2 map.
    - The research body's `methods` entry records the formulas beside the map they shaped.
    - A map computed with a replaced formula never lends its K100 to the body.
  - **`COMPUTED_SLOTS` is now `ENGINE_SLOTS`.** `formula_not_computed` stays as the guard for
    a slot added to the catalogue before the engine reads it; a test narrows the set to
    reach it.
  - **The step pins moved** for the ten steps whose functions gained `slots`, and were re-read.
    With no slot replaced, every golden, parity-capture and engine test passes unchanged.
  - **Tests.**
    - `test_methodology_engine_slots.py` (36). For each slot, its built-in expression gives the
      code's map bit for bit (`model_dump` equality) on a weighted panel with gaps, the
      bootstrap and the terrain. Another expression moves what that slot computes.
    - The pin's tests.
    - `test_a_run_computes_the_formula_its_methodology_replaced`, through the real worker.
- **S4b. Landed.** The draft check lives in `domain/methodology/sociomap_check.py`.
  - **What it computes.** It runs the draft and the methodology in force through the real
    engine (`compute_object_map`, each with its own slots) on `CHECK_PANELS`, three fixed
    fictional panels from seeded generators; no client data is read:
    - balanced: 120 respondents, equal weights;
    - weighted: 90, weights 0.3 to 3, 8 % blank, one SECONDARY object;
    - small: 36, near `n_min`.
  - **What it reports** per panel:
    - the outcome and its reason;
    - Stress-1 and its band;
    - status counts and every pair whose status changes;
    - each object's shift once the draft is turned onto the map in force
      (`align_to_reference`: rotation and reflection only);
    - heights;
    - the K100 point (`f9.k100` of K);
    - support n;
    - the largest terrain-cell change.
  - **K100's interval is not in the check.** It is computed without the bootstrap, which costs
    about 1.6 s per map at B = 500 (measured on 120 x 8). The check says so on every panel; the
    run computes the interval.
  - **The check resolves both sides through the run's own pin** (`sociomap_methods_for`), so it
    computes exactly what a run would. All three panels take 0.13 s for parameter edits.
  - **The route** is `POST /api/v1/methodology/{module}/compare`, for any member, storing
    nothing. An invalid edit returns its problems; a module other than the object map is 422
    `no_comparison`.
  - **The editor** has a "Porovnat s metodikou v platnosti" button and a per-panel comparison
    (`MethodologyComparison.tsx`). It says plainly what did not move.
  - **Seen on the workbench.** `n_min` 34 plus `sigma` 0.3 leaves the balanced and weighted
    maps unchanged except the terrain, which moves by up to 0.07. The small panel becomes
    unmappable (DISCONNECTED: 13 pairs drop to UNKNOWN).
  - **Tests.**
    - `test_methodology_sociomap_check.py` (7): fixed panels; a methodology beside itself moves
      nothing; `n_min` moves statuses only where the panel is small; `sigma` moves only the
      terrain; a replaced δ moves objects; a replaced K100 halves it; a payload is checked
      through the pin.
    - Four API tests and two web tests.
- **Finding H5 (fixed in this PR).** The body's K100 was copied from an object map whose
  evidence basis is not the body's.
  1. **Claim.** `battery_sociomap` copies the K100 of an object map whose bootstrap matches by
     B, seed, n_min, confidence and roles. It did not compare the evidence basis: the body's
     statuses read the respondent count, `aia-sociomap-3`'s read Kish's n.
  2. **Anchor.** `packages/aia_core/src/aia_core/domain/research_sociomap.py:507 @ e9d68b4`
     (the guard, before the fix).
  3. **Reproduce.**
     `pytest packages/aia_core/tests/test_research_sociomap_k100_copy.py`: 45 respondents of
     case A01, one in three weighted 20 times the others.
  4. **Consequence.** With the bootstrap switched on
     (`AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED`) and `aia-sociomap-3` pinned beside the
     reference map, as every new run has it, the stored body recorded no K100 for any object
     (`known_pairs` 0). Its own bootstrap gives kava 36.97, upper bound 61.43, for example.
     No screen reads the body's K100 today; the stored internal artifact is wrong.
  5. **Fix.** The guard also requires the map's basis to be `respondent_count`. Today no
     default map matches, so the body computes its own K100: about 90 s per large set while
     the switch is on.
  6. **Test.** The one above. It also asserts that the map's K100 differs on that panel, so it
     cannot pass vacuously.
- **Finding H4.** The domain's problems are English sentences, shown verbatim on a Czech page:
  `n_min 2 is below 4: the Fisher interval needs four raters`
  (`packages/aia_core/src/aia_core/domain/sociomap/specification.py:535 @ 41dc1be`).
  - Reproduce: `MethodologyVersions.test.tsx`-style check with `relation.n_min` 2, or the
    workbench editor.
  - Consequence: the methodologist reads the reason in English.
  - Smallest fix: a problem code beside each message, and Czech words for the codes in
    `cs.ts`, with the English as the fallback.
  - Test: one per code, in the web suite.
  - It is not fixed here because the messages belong to the specification validators, which S2
    rewrites.
- **S1d.** Rules for every step the register lacks, and the null and wrong pointers fixed
  (AUDIT-F1, SOMECS-H7, AUDIT-F7). **The register is also edited by
  `sociomap-formula-corrections.md`:** land S1's register change as its own small PR, after that
  plan's open PR.
  - **Landed.** No open PR edited the register (checked 2026-10-12), so nothing had to land
    first.
  - **Pointers.**
    - AUDIT-F1 now points at `engine_v2:_scaled` with three tests. It no longer says path A
      reads raw ratings: only the reference map does, by design.
    - AUDIT-F7 now points at `view:stress_quality`, the part every run computes. The alignment
      (`align_to_reference`) is called only by the Metodika draft check, and the text says so.
      It also records that Results and the report show the label
      (`report_maps.py:89 @ 6556f27`), and that no test pins the printed sentence.
    - SOMECS-H7 now points at the H-Model candidate's `_frame`, whose frame is [0.05, 0.95].
  - **Rules for the steps without one.**
    - A new label, `PORTED`, and a document, `NPC_UNIT` (the frozen unit's code). An exact
      port of 18.6.6 had no honest label: DOCUMENTED and INFERRED need a paged document, and
      PROPOSED means "no source speaks".
    - Six rules, `LEGACY-R2` to `LEGACY-R7`: the weight rescale, the mutual relation, the
      object metric, the respondent density terrain, the normaliser, and the mean rating. Each
      cites the unit's line or function. `test_a_ported_rule_names_the_units_code_and_is_built_and_checked`
      holds the label to that.
    - The reference map's `scale` step cites AUDIT-F1 (the declared ends), and the object map's
      `f3_effect_floor` cites AUDIT-F3 (Q6 shapes it, per the register's `aia_decisions`).
    - `test_every_step_that_computes_cites_a_register_rule` now holds every registered module to
      a rule per step. Only `method` is exempt: it names the method and computes nothing.
  - **Finding (fixed here).** `object_rating_summaries` said the mean rating was "an AIA
    declaration rather than a recovered function". The unit computes it the same way, in
    `visualization_lab.py:131`, rounded to four decimals. The docstring now says so (LEGACY-R7).
- **S2.** Every listed constant moves into the specification. The side tables, K100 and the
  readiness warning read the run's pin. A layer check forbids importing those constants on a run
  path. ~~This is one fingerprint move for new runs~~: superseded, see "No fingerprint move" below.
  - **Split** into S2a (the object map's own constants), S2b (the reference set's side tables and
    K100) and S2c (the readiness warning). Each touches different consumers.
  - **Not a new contract class.** Contract 3 already grew a declaration without moving a pin:
    `effect_floor` is left out of the stored form when absent
    (`specification.py:386-410 @ 8265af7`). The new declarations follow the same rule. A pin made
    before them reads, fingerprints and computes exactly as before, with the value its code fixed
    then. The preset `aia-sociomap-4` declares every one, with the same numbers as -3.
  - **No fingerprint move for new runs (decided in S2a).** The owner's pending D6 sign-off names
    `aia-sociomap-3` and its fingerprint `e16dc0d06361…`
    (`docs/architecture/sociomapa-methodology-decision.md`, enforced by
    `test_sociomap_decision_package.py`). Moving new runs to -4 would change the subject of that
    sign-off under the owner. So `default_methods()` still pins -3 and the catalogue keeps -3 in
    force. `aia-sociomap-4` is the editor's starting point: an edit from it
    (`aia-sociomap-4+e<n>`) declares the constants and can move them, and a run pins it only
    once a person puts that version in force. Moving the code default to -4 is the D6 owner's
    call, a one-line change with nothing to compute differently
    (`test_v4_computes_exactly_what_v3_computes`).
  - **`_FISHER_MIN_N` stays code.** Four raters is the domain of the Fisher interval
    (`1/sqrt(n - 3)`), not a methodological choice. The tab shows it as a code constant, and
    `n_min` is refused below it. A methodologist who wants another interval replaces the
    `f3.interval_*` formulas (S4c).
  - **Landed (S2a).** Contract 3 gains `layout.min_objects`, `layout.stress_bands` and
    `connectedness.quantiles`, each optional and out of the stored form when undeclared, each
    refused outside its domain by name (`test_a_constant_outside_its_domain_is_refused_by_name`).
    The engine reads each declaration and falls back to the code's value
    (`LEGACY_MIN_OBJECTS`, `LEGACY_STRESS_BANDS`, `LEGACY_CONNECTEDNESS_QUANTILES`). -3's stored
    form and fingerprint are unchanged (`test_the_d6_subject_keeps_its_stored_form_and_fingerprint`).
    -4 computes byte for byte what -3 does on every check panel, spec aside. K100's `rule_text`
    names the quantiles it used, and reads as before at the defaults. The catalogue's F6, F7 and
    F9 steps name the new parameters; the code constants stay beside them as "before
    aia-sociomap-4". Results reads an object map under -4 too (`OBJECT_MAP_METHODS`).
  - **Landed (S2b).** The reference set's side tables (`relation`, `relation_rescaled`,
    `object_scores`) and its K100 read `n_min`, the confidence and the bootstrap (B, seed,
    quantiles) from the run's last pinned object map (`research_sociomap.side_tables_for`).
    The body records which, under `side_tables`, and `SOCIOMAP_VERSION` is
    `aia-research-sociomap-9`, so a body stored under 8 is not reused as if it had them. A run
    that pinned no object map keeps the code's values (`LEGACY_SIDE_TABLES`). The statuses
    keep reading the respondent count, the body's documented rule. Under the default pin
    (-3) every table is what it was (`test_the_default_pin_computes_the_tables_it_always_did`).
    K100 is copied from a map only when its quantiles also match. Enforcement:
    - `tools/layer_check.sh` forbids the code constants in application, infrastructure, the
      API, the worker and the executors.
    - Inside `research_sociomap.py`, `test_no_run_path_reads_the_codes_constants` checks the
      names that `battery_sociomap` and `research_sociomaps` compile to.
  - **Landed (S2c).** The readiness warning ("n is below the respondents each pair needs")
    reads the pair `n_min` of the methods the run pins, through the same
    `research_sociomap.side_tables_of` as the side tables, so the two never disagree.
    `assess_readiness` and `prepare` take `pair_n_min` and have no default.
    - `ResearchRuns.readiness` reads the methodology in force, and `start` reads the methods it
      is about to pin. Both resolve the methods through one `_methods`, and an uncomputable pin
      is refused before the checks.
    - The worker's preflight step reads the run's own pin from its step input
      (`step_inputs["preflight"]["methods"]`). A run started before S2c has none there and
      reads as `aia-sociomap-1`, whose `n_min` is the same 30.
    - Tests: `test_readiness_warns_with_the_n_min_of_the_methodology_in_force`,
      `test_the_preflight_step_reads_the_runs_pin_not_what_is_in_force_later`.
    - A layer rule keeps the code constants out of `research_design.py`.
  - **Finding (fixed in S2a).** The tab offered a field that a preset leaves out of its stored
    form as editable with the value `null` (`relation.effect_floor` under `aia-sociomap-2`). The
    editor works on the stored form, so saving from -2 would have thrown on that field.
    `describe` now reads such a value as absent (`resolution.py` `_read_or_absent`,
    `test_the_predecessor_shows_the_terrain_it_does_not_have_as_absent`). The editor's default
    base is the first preset in the module's ordered list, not the first key of a JSON object.
- **S3 / G2 / R1 / V1.** Each built-in expression is checked against the code on every fixture
  of its module, bit for bit: F1–F9, the AIA golden, the research aggregate cases and the
  response-process captures. Where floating-point order makes bit-identity impossible, the
  built-in keeps running the code path and the expression is shown with the measured maximum
  difference. Such cases are named, not hidden.
- **G1, split four ways.** G1a documents; G1b declares both rule sets, bit-identical; G1c makes
  one rule govern both Results and analysis; G1d makes it editable with the draft check.
  - **Decided (owner, 2026-10-12): both rules as today until a version is in force.** Before
    any version, Results keeps 18.6.6's donor rule and analysis keeps AIA's gate: that is
    `aia-support-1`. A version the methodologist puts in force replaces both, and can make them
    one rule by giving `results` and `analysis` the same lines.
  - **G1b. Landed.** `evidence/support.py`:
    - `SupportThresholds` is now a frozen model whose `None` means a line the rule does not
      check. It refuses a boolean, a negative or non-finite line, and an indicative line below
      its suppression line.
    - `SupportSpec` holds two rules, `results` and `analysis`. `AIA_SUPPORT_V1`
      (`aia-support-1`) is today: `UNIT_DONOR_THRESHOLDS` (donors 25/50, nothing else) for
      Results, and `REFERENCE_THRESHOLDS` for analysis.
    - One decision function serves both `assess_support` and the new `support_status`.
      `research_aggregate.donor_support` reads its status from the `results` rule, and its
      recorded thresholds from the same rule.
    - Bit-identical: the unit's exact-parity aggregate tests pass unchanged, and
      `test_the_results_rule_is_the_units_donor_lines_whatever_n` checks 81 donor counts at two
      (n, effective n) pairs each.
    - The module `support` now has the preset `aia-support-1` in force, a `method` step, and
      every line as a specification parameter. It was not yet editable (G1d).
  - **G1c. Landed.**
    - **Pin.** `ResearchRuns.start` pins the organization's support version in force
      (`methodology_in_force_for_study(…, "support")`). With nothing stored that is
      `aia-support-1` (`pins.support_spec_for`). The pin goes in the run's metadata and the
      aggregate step's input, with `support_methodology` naming a stored version.
    - **Retry and identity.** A retry keeps the original's pin, and a run stored before the pin
      reads as `aia-support-1` (`pins.read_support_pin`). A stored version, or a set the caller
      chooses over the code's, is part of the run's identity, like the Sociomap's methods.
    - **Aggregate.** `aggregate_dataset(…, support=)` decides every cell by the pinned
      `results` rule. `donor_support` and `aggregate_question` take the rule as a required
      keyword, so no run path has a default.
    - **Analysis.** `native_sources` reads the pin into `NativeSources.support`, and
      `native_evidence(…, support=)` gates by its `analysis` rule. A pin that does not read is
      refused by name (`support_pin`).
    - **Fingerprints.** Only a rule other than today's enters a fingerprint (the aggregate
      artifact's input and the native evidence's system fingerprint), so a run under today's
      rules keeps the keys and validations it always had.
    - Tests: `test_support_pin.py`; `test_methodology_run_pins.py`, the support tests through
      the real worker (a strict pin suppresses every object; a retry keeps its pin);
      `test_analysis_results.py`, `test_a_runs_pinned_support_rules_reach_its_analysis`.
  - **G1d. Landed.**
    - **Editable both ways.** Module `support` is `editable`. Any line of either rule may move
      up or down, become checked or stop being checked, so a version can make the two rules one
      (`test_the_two_rules_may_be_made_one`). The model's own checks still hold: no boolean, a
      finite non-negative number, and an indicative line never below its suppression line.
    - **Refused.** A rule that suppresses nothing is refused by the module
      (`support._validate`, `SupportRuleRefused`, problem key `spec.results` or
      `spec.analysis`). Such a rule has none of `min_cell`, `n_guard`, `min_layer_donors`, so
      it would show every cell however thin.
    - **The draft check.** `domain/methodology/support_check.py` decides 16 fixed fictional
      cells: four panels (60–400 respondents, 24–120 donors, equal to strongly unequal
      weights), each with four answer rates.
      - Each cell is decided under the rules in force and under the draft, through the run's
        own functions: `donor_support` for Results and `analysis.native.reassess_support`
        (renamed from `_support`, now public) for analysis.
      - The check lists every cell and surface the draft newly reports or newly suppresses,
        then every cell with both statuses.
      - Under `aia-support-1` the cells span all three statuses and include D2's disagreement
        (`nevyvazeny.q3`: REPORTABLE in Results, INDICATIVE in analysis).
      - `POST /methodology/support/compare` returns it as `support`, with `panels` empty.
        The tab's comparison lists it (`MethodologyComparison.tsx`, `SupportCheck`).
    - **The editor clears a line.** A number field now also takes `null`
      (`methodology-edit.ts` `fromInput`), so a line can stop being checked from the tab. Before
      this, only a line already `null` could change, in one direction. Whether `null` is allowed
      stays the domain's to say. Proven by `MethodologyVersions.test.tsx`, "the support rules'
      versions".
    - **The note.** Every cell's `uncertainty_note` is now written from the rule that decided
      it (`research_aggregate.uncertainty_note`). Under 18.6.6's rule it is the unit's text,
      verbatim (`UNCERTAINTY_NOTE`, unchanged), so the parity tests hold.
    - Tests: `test_methodology_support.py` (both ways, made one, the refusals),
      `test_methodology_support_check.py`, `test_support_pin.py` (the note follows the pin),
      `test_methodology_api.py` (store and put in force, refusal, the check), and
      `MethodologyComparison.test.tsx`.
  - **Finding (for G1d), resolved by G1d.** The aggregate's `UNCERTAINTY_NOTE`
    (`research_aggregate.py:60`, on the G1b branch) is the unit's text, verbatim: "<25 se nereportuje;
    25–49 je INDIKATIVNÍ". Once the Results rule is editable, the note must be written from the
    rule in force, or it will state lines the rule no longer uses.
  - **G2 splits into G2a-G2c.** The unit wrote the bootstrap's values inline
    (`research_aggregate.py`, `reps=400`, `seed=20260816`, …), so unlike G1a there is no module
    constant for the tab to read. Documenting them means declaring them, so G2a does both.
  - **G2a. Landed.**
    - **Declared.** `research_aggregate.AggregationSpec`: `bootstrap` (`reps` 400, `reps_multi`
      350, `seed` 20260816, `seed_top_box` 20260818, `quantiles` (0.025, 0.975)) and `top_box`
      2. Its preset `AIA_AGGREGATE_V1` (`aia-aggregate-1`) holds the unit's literals.
      - The quantiles are declared, not derived from a level: `(1 - 0.95) / 2` is
        0.025000000000000022, and a derived bound would move every interval in its last bit.
      - A multiple choice's seed stays `seed + i` (the option's index). That is the method, so
        it is not a parameter.
      - Refused: zero replicates, a negative seed, quantiles outside 0 < low < high < 1, an
        empty top box, a boolean, an unknown field.
    - **Read.** `aggregate_question(…, method=)` takes the specification, and
      `bootstrap_weighted_mean` and `bootstrap_weighted_distribution` take `quantiles`; none of
      them holds a literal any more (`test_the_preset_is_the_units_literals_bit_for_bit`).
      `aggregate_dataset` passes `AIA_AGGREGATE_V1`. A run does not pin it yet (G3).
    - **Bit-identical.** The exact-parity aggregate tests, the seed-spread tests and AIA's own
      pinned bounds pass unchanged.
    - **Module.** `domain/methodology/aggregation.py` is module `aggregation`, read-only, in
      force `aia-aggregate-1`, registered after `support`. Its groups:
      - M, the method;
      - V, weights: cleaning (D1) and Kish;
      - O, estimates: share, mean, median, sd, top box, multiple choice;
      - B, the donor bootstrap: resampling and the percentile interval (D5);
      - F, fidelity: the keyword lists (D7, shown as code constants) and the rating.
    - **D7, tested.** `test_the_keyword_lists_decide_what_is_refused`: "Kolik byste zaplatili…"
      is refused, while "Jakou částku … považujete za přiměřenou?" passes as AMBER. The refusal
      is only as good as the lists.
  - **G3 splits into G3a-G3c.** Support has been editable since G1d, so G3 is aggregation's.
    It follows support's order: pin (G1c), then editing with its draft check (G1d). The
    label's reach past Results is its own chunk.
  - **G3c. Landed.** The deviation G2c records on the aggregate now reaches everything that
    reads the aggregate's numbers.
    - **Analysis evidence.** `native_evidence` puts the deviation (method name, changed values,
      replaced formulas) into the system fingerprint, only when there is one, the way a
      non-reference support rule enters it.
      - A validation recorded for 18.6.6's method never vouches for numbers another method
        computed.
      - Every analysis under the port keeps the fingerprint its validations are bound to.
      - A deviation that cannot be read is refused (`NativeEvidenceRefused`), never taken for
        the port.
    - **Reconstruction and API.** `RunAnalysis.aggregation_deviation` is read once from the
      verified sources by `reconstruct_run`. `GET …/analysis` returns it as
      `aggregation_deviation` (`null` for the port).
    - **The web.** The AI analysis card shows G2c's "Odchylka od 18.6.6" banner above the
      modules, naming each change and each replaced formula.
    - **The internal report** (`compose_internal_report`), following the synthetic-respondents
      disclosure it already makes:
      - a LIMITATION callout titled "Odchylka od 18.6.6" in the introduction;
      - a paragraph in "Metodika a způsob interpretace" naming the version, each changed value
        ("top_box (18.6.6: 2, zde 1)") and each replaced formula;
      - a limitation callout in the limitations chapter;
      - "Metodika agregace" in the audit appendix.

      None of it appears for the port. The DOCX still lints clean.
    - Tests:
      - `test_analysis_results.py::test_an_aggregate_that_is_not_the_units_port_says_so_in_analysis_and_the_report`
        (fingerprint moves; garbled refused; reconstruct carries it; every report place),
        with the negative added to the existing composition test;
      - `test_research_api.py` (the key, `null` before any module read an aggregate);
      - `ExecutionSteps.test.tsx` (the banner on the analysis, and none on the port).
  - **G3 complete.** Support has been editable since G1d, and aggregation since G3b. Both are
    pinned by every run, and any departure from 18.6.6 is said wherever the numbers go.
  - **G3b. Landed.**
    - **Editable.** Module `aggregation` is `editable`. A version may change any declared value
      and replace any of the five estimator slots. `validate_version` checks both: the
      specification's own refusals (zero replicates, quantiles out of order) and each slot's
      properties on its grid (a share above 100 % is refused by name).
    - **The draft check.** `domain/methodology/aggregation_check.py` aggregates three fixed
      fictional panels through `aggregate_dataset` itself, under the aggregation in force and
      under the draft:
      - a small unweighted panel (60 respondents, 24 donors), SUPPRESS;
      - a strongly weighted panel (240, 40, weights 0.2-4), INDICATIVE;
      - a large panel (500, 160), REPORTABLE.

      Each panel answers two scales, a single choice and a multiple choice: 11 estimates.
      - It compares every estimate with its 95 % interval, each question's support status
        under the support rules in force, and each question's effective n.
      - It names every estimate that moved and every status that changed.
      - Computed in memory only: nothing is stored or reaches a run. About 1 s per side.
    - **What it shows, measured on the panels.**
      - A one-point top box moves exactly the two top boxes, downward.
      - Fewer replicates move intervals, never estimates.
      - Kish replaced by `count(w)` lifts the weighted panel's effective n from about 31 to
        its 40 donors (the combined n is capped by them). Under a rule suppressing below an
        effective n of 35, that turns all four of its questions from SUPPRESS to REPORTABLE.
    - **API.** `POST /methodology/aggregation/compare` returns `aggregation` (panels, rows,
      `status_changes` as `QuestionStatusOut`, `effective_n`). Statuses are decided by the
      organization's support rules in force, as a run started now would decide them.
    - **Web.** `MethodologyComparison.tsx`, `AggregationPanel`, following the settings
      workspace (#290):
      - one collapsible panel each, the first open;
      - every moved estimate as "value (low-high) → value (low-high)";
      - status and effective-n changes;
      - "Žádný odhad se nemění." where nothing moved.

      The version editor needed no change: the quantiles are a JSON field, and each slot shows
      its built-in expression.
    - **End to end.** An aggregation version stored and put in force as the tab does is pinned
      by the next run (`aggregation_methodology` names it), computed under, and labelled. A
      run started before keeps the unit's port
      (`test_a_run_pins_the_aggregation_version_in_force_and_its_aggregate_says_so`).
  - **G3a. Landed.**
    - **The pin.** `ResearchRuns.start(…, aggregation=)` pins the organization's aggregation
      version in force (`methodology_in_force_for_study(…, "aggregation")`). With nothing
      stored, that is `UNIT_AGGREGATION_PIN`: `aia-aggregate-1`, no formula replaced.
      - The pin is `{"spec", "formulas"}`, in the run's metadata (`aggregation`, with
        `aggregation_methodology` naming a stored version) and the aggregate step's input.
      - A retry keeps the original's pin (`_aggregation_of`). A run stored before the pin
        retries as 18.6.6's port.
      - A stored version, or a pin the caller chooses over the unit's, is part of the run's
        identity, like the support rules.
    - **Refused before any run.** A pin is read at start exactly as the aggregate will read it
      (`pins.read_aggregation_pin`): a formula that does not compile, or a slot the aggregate
      does not read, never reaches a run. `aggregation_pin_for` refuses a stored version
      replacing a formula outside `COMPUTED_SLOTS`. `COMPUTED_SLOTS` is now
      `ENGINE_SLOTS | AGGREGATE_SLOTS`, and the two sets are disjoint.
    - **The step.** The aggregate step computes `aggregate_dataset(…, method=, slots=)` under
      the pin. A pin that does not read fails as `aggregation_pin_invalid`. Only a pin other
      than the unit's enters the artifact's reuse key, so every earlier aggregate is reused as
      it was.
    - **The label is reachable.** A run under an edited pin stores an aggregate whose
      `deviation` names the changed value and the replaced formula
      (`test_a_run_aggregates_under_the_aggregation_it_pinned_and_says_so`, through the real
      worker).
    - Tests: `test_aggregation_pin.py`; `test_methodology_run_pins.py`, four aggregation
      tests; `test_methodology_engine_slots.py` restates the computed set for both modules.
  - **G2c. Landed.**
    - **When an aggregate departs.** `research_aggregate.aggregation_deviation(method, slots)`
      is `None` for 18.6.6's port. Otherwise it names every value of `aia-aggregate-1` the
      method changed (path, the unit's value, the one used) and every replaced formula.
      - A version that only renames changes no number and claims nothing.
      - A replaced formula counts even when its expression equals the built-in: an edit is
        an edit.
    - **The artifact.** `aggregate_dataset(…, method=, slots=)` adds a `deviation` block only
      when there is one. The port's artifact is byte for byte what it was: the parity
      self-fixture, which compares whole artifacts, passes unchanged.
    - **Results.** Above the numbers, "Odchylka od 18.6.6", the version, each changed value
      ("top_box: 2 v 18.6.6, zde 3") and each replaced formula (`ExecutionSteps.tsx`,
      `Deviation`).
      - The top box is named by the width the aggregate used ("Horní body (3)"), no longer
        always "Horní dva body".
      - A deviation the page cannot read is still shown as a deviation, with nothing named;
        it never passes as the port (`research-execution.ts`, `aggregateDeviation`).
    - **Reachable from G3 (now G3a).** No run passed a method or slots yet, so no stored aggregate can
      deviate until a run pins the aggregation version in force. Analysis and the report read
      the aggregate's numbers; carrying the label into them belongs with that pin.
    - Tests: `test_aggregate_deviation.py`; `research-execution.test.ts`
      (`aggregateDeviation`, `topBoxWidth`, the top-box label); `ExecutionSteps.test.tsx`
      (the label above the numbers, and none on the port).
  - **G2b. Landed.**
    - **The obstacle.** A built-in expression must give the code's exact bits, and the
      formula language's `sum` is `math.fsum`. The aggregate summed with plain `sum`, so an
      expression and the code differed in the last bit.
      - The sociomap engine already sums with `fsum`, which is why S3's slots could be
        bit-identical.
      - Plain `sum` was never the unit's bits either: 18.6.6 sums with NumPy.
      - So the aggregate now sums with `fsum` (exactly rounded), not the expressions with
        something looser.
    - **Nothing visible moved.** The exact-parity tests against the unit, the seed-spread tests
      and AIA's pinned bounds pass unchanged. A 1,000-respondent × 18-question fictional
      aggregate hashes identically before and after (`62d3fe29…`).
    - **Cost.** That aggregate takes 2.54 s before and 2.84 s after (+12 %), median of three
      runs. A first cut cost +35 %; most of it was won back by computing each replicate's
      weights once with `map` and grouping a distribution's rows by label outside the
      replicate loop. `_multipliers` (the random draws) still dominates the profile.
    - **The slots** (`domain/methodology/aggregation_formulas.py`, ids in
      `research_aggregate`, `AGGREGATE_SLOTS`):

      | Slot | Built-in | Step |
      |---|---|---|
      | `agg.kish` | `sum(w) ** 2 / sum(w * w)` | kish |
      | `agg.share` | `100 * sum(w * hit) / sum(w)` | share |
      | `agg.mean` | `sum(w * x) / sum(w)` | mean |
      | `agg.variance` | `sum(w * (x - sum(w * x) / sum(w)) ** 2) / sum(w)` | sd |
      | `agg.top_box` | `x >= top - (b - 1)` | top_box |

      - Weight cleaning, the weighted median, the resampling and the linear quantile are
        algorithms, so they stay code without a slot.
    - **The engine.** Every estimator function takes `slots` (default none: the code, bit for
      bit). A replaced slot computes the point and every bootstrap replicate.
      `aggregate_dataset(…, slots=)` passes them through; no run pins any yet (G3).
    - **One estimator, used consistently.** The top box's share and each multiple-choice
      option's share are weighted means of 0/1 indicators, so they follow `agg.mean`. The
      mean step says so: editing the mean edits them too.
    - **Proof** (`test_methodology_aggregation_formulas.py`):
      - every fixture, aggregated with all five slots replaced by their own built-ins, is
        identical to the code's aggregate;
      - unrounded points, bounds, Kish n and variances are equal as floats on random inputs;
      - the top-box rule matches the code's for every width;
      - a replaced estimator moves what the aggregate reports and nothing else.
  - **G1a. Landed.** `domain/methodology/support.py` is module `support`, read-only. It has no
    specification yet, so every value is a code constant read where it is used.
    - Group U, the unit's rule (what Results shows): weight cleaning, Kish n, donors with the
      combined effective n and the largest donor's share, and the status from donors alone
      (25/50).
    - Group A, AIA's evidence gate (what analysis applies): Kish n that refuses bad weights,
      `assess_support` with all five `REFERENCE_THRESHOLDS`, and `analysis.native._support`
      re-assessing the unit's status, the stricter winning.
    - The findings are named on their steps: D1 (median imputation vs refusal), D2 (the two
      rule sets), D3 (the gate's effective n is the combined one), D4 (the largest donor's
      share is stored and never read).
    - Checked before writing: `max_donor_share` is written at `research_aggregate.py:270, 438`
      and read nowhere; `effective_n` is `effective_n_combined` at `:433` (@ ca56fd00).
- **W1, split three ways** like G1-G3: W1a documents and declares, W1b makes the cleaning a
  choice a run reads, W1c makes it editable.
  - **W1a. Landed.** `domain/methodology/weighting.py` is module `weighting`, read-only,
    registered after `aggregation`.
    - **Declared.** `WeightingSpec` (`population/weights.py`): `contract_id`, `default_role`,
      `schemes` keyed by role (column, expected total, tolerance) and `aggregate_cleaning`
      (`median`, the unit's; `refuse`). Its preset `aia-weighting-1` is built by
      `weighting_spec(CZ_SYNTHETIC_V17, ...)`, so it is the contract's declaration exactly,
      never a copy that can drift
      (`test_methodology_weighting.py::test_the_preset_is_the_contracts_declaration_exactly`).
      A default role that is not a scheme, a total without its tolerance, a negative tolerance
      and two schemes on one column are refused.
    - **Nothing reads it yet.** The loader still resolves through the contract and the
      aggregate still cleans with the median; the module says so, and that a run reads it
      from W1b.
    - **Steps, in five groups:** the method; the scheme (role to column, one weight's parse,
      the column refused whole); the import's totals; the aggregate's cleaning; Kish's n in its
      three places. There is no calibration, raking or GREG step, and the module says that too.
    - **Finding D1, reproduced.**
      - Three cleaning rules for one weight: `clean_weights([1, nan, 3, 5])` gives
        `[1, 3, 3, 5]`; `evidence.support.kish_effective_n` raises; `analysis_weights`
        raises `unusable_weight` (`::test_three_cleaning_rules_impute_or_refuse_the_same_weight`).
      - Kish's n is computed in three places, not two: `research_aggregate`, `evidence.support`
        and `sociomap.relations`. All three give the same float on 200 random positive weight
        vectors. On a zero, the Sociomap's pair refuses while the other two agree. On a
        negative, the aggregate drops it (1.8 for `[1, -1, 2]`) while the other two refuse
        (`::test_kish_is_computed_three_times_and_agrees_only_on_valid_weights`).
      - D1 is a fact, not a defect, until W1b makes the cleaning a choice.
- **G1.** One rule set, not two (finding D2). The decision of what the single rule is goes to the
  methodologist and is made in the tab, as the first activated support version. The thresholds
  are editable both ways, with no floor (owner, 2026-10-11; ADR 0023 decision 10). The draft
  check lists every row a lowered threshold would newly report.

- **Z1a. Landed.** Walked on the UI workbench at `develop @ a19af14d`.
  - **Through the API, per module.** Edit, `/check`, `/compare`, store as a version, activate
    with a reason: the Sociomap (`relation.n_min` 30 → 20), support (Results' lower donor line
    25 → 20) and aggregation (`top_box` 2 → 1). Every step 200/201. The draft checks moved what
    the edits should: the top boxes (small panel 52.7 % → 5.5 %, means unchanged) and one small-panel
    cell SUPPRESS → INDICATIVE. The balanced panel's map did not move under n_min 20, as
    expected at 120 raters.
  - **The run.** A research run through the browser (`tools/ui_workbench/research_journey.mjs`)
    pinned all three stored versions by name and hash, with the edited values. Results show the
    map as `aia-sociomap-3+e1`, and the Data tab opens with the 18.6.6 deviation naming
    `aia-aggregate-1+e1` and `top_box: 2 v 18.6.6, zde 1`, the top boxes reading "Horní body (1)".
    The support edit cannot show on that run: every cell has 141 donors.
  - **In the browser, as the methodologist clicks it.** Nastavení → Metodika → Podpora a
    potlačení → Upravit metodiku → one field → Porovnat → Zkontrolovat a uložit → Uvést v
    platnost with a reason: stored `aia-support-1+e2`, in force, no error.
  - **Fixed here.** Results never said which methods a run used: the run API did not return
    them, the run's provenance showed only its ids, and the support version appeared nowhere.
    The run now carries `methodology` (each module's name, stored or the code's preset), read
    from its metadata by `methodology.pins.run_methods` (the domain: layer_check keeps the
    Sociomap preset's name out of the API; no pin reads as the preset, a pin that cannot be read as `null`, never a guess,
    `test_run_methods.py`), and Results show it as "Metodika běhu"
    (`test_research_api.py::test_a_run_names_the_methods_it_computed_under`). Every editable
    module also introduced itself as "Postup výpočtu mapy"; now "Postup výpočtu".
  - **Not fixed (minor).** A line a rule does not check is edited as the text `null`; the
    Metodika tab has no link of its own (`/app/settings?tab=` is not read).
  - **Workbench in a git worktree.** The API and worker ran the main checkout's code through
    the editable install until `PYTHONPATH` named the worktree's sources, and `next dev`
    (Turbopack) refuses a symlinked `node_modules`. Doc follow-up for AGENTS.md.

## Findings (hypotheses until reproduced; each names the chunk that tests it)

- **H1.** `_rating` (`research_sociomap.py:267 @ 27062ec`) accepts only ints, so a float rating
  becomes missing. Tested in S1.
- **H2.** AUDIT-F1 and SOMECS-H7 have `implementation: null` although the code exists, and
  AUDIT-F7 points at a function only tests call. Tested in S1. **Confirmed and fixed in S1d.** By then the Metodika draft check also called
  `align_to_reference`, but no run path did.
- **H3.** The `aia-sociomap-1` artifact's spec differs from the pinned spec, because the
  battery's scale overwrites `rating_scale_min/max` (`research_sociomap.py:469-476`). Tested in
  S1.
- **D1.** There are three weight-cleaning rules:
  - median imputation (`research_aggregate.py:158-165`);
  - refusal (`evidence/support.py:244-257`);
  - refusal (`population/weights.py:85-118`).

  Kish n is computed twice. Tested in W1. **Reproduced in W1a:** three times, not twice
  (`test_methodology_weighting.py`); equal on positive finite weights only.
- **D2.** There are two suppression rule sets: the unit's (donors 25/50) and AIA's (raw n 50,
  n_eff 25/50). Results shows the unit's (`apps/web/src/lib/research-execution.ts:134-177`), so a
  cell can read INDICATIVE on screen while its evidence row is suppressed. Tested in G1, and
  user-visible.
- **D3.** The gate's n_eff is `effective_n_combined`, rounded to 1 dp, not Kish
  (`analysis/native.py:243-259`). Tested in G1.
- **D4.** `max_donor_share` is computed but never gated. Tested in G1.
- **D5.** The bootstrap's replicates and seeds are inline literals, and its fixed-weight
  percentile method is undeclared (`research_aggregate.py:448-487`). Tested in G2.
- **D6.** On fictional rosters, donors = ⌊n/3⌋, so n < 75 suppresses everything
  (`ai_respondent.py:255-291`). Tested in R1.
- **D7.** Plain Czech keyword lists decide REFUSE (`research_aggregate.py:72-90`). Tested in G2.

## Not in this plan

- A methodologist role.
- Signing D6.
- Per-study methods.
- Editing an iterative algorithm from the page.
- Building F10, F14, F15 or F16; that is `sociomap-formula-corrections.md`.

## Doc follow-up

To be written as chunks land:
- the `CLAUDE.md` map: `domain/methodology/`, the tables, the routes, the tab;
- `ARCHITECTURE.md`: the methodology pin, and the layer rule that forbids method constants on run
  paths;
- the ADR index entry for 0023;
- `AGENTS.md` if Temml under Next 16 or the expression compiler needs a note.
