---
status: in-progress
chunks:
  - "[x] 0. ADR 0023 and this plan"
  - "[ ] A1. Framework: methodology package -- module, step, slot, parameter, specification; completeness and source-hash tests"
  - "[ ] A2. Expression language: parser, whitelist, compiler, LaTeX generator, slot properties on a grid; no eval"
  - "[ ] A3. Version store: methodology_versions + methodology_activations (migration), repository, audit"
  - "[ ] A4. Run pins: every module's in-force version pinned at start, retry keeps it, fingerprints carry it"
  - "[ ] A5. API: GET /api/v1/methodology (modules, steps, values with origin, evidence, open questions); version routes"
  - "[ ] A6. Web: the Metodika tab shell -- module list, step cards, MathML (Temml), parameter tables; read-only"
  - "[ ] S1. Sociomap documented: F1-F16 in the audit's order, aia-sociomap-1, the H-Model; register gaps filled"
  - "[ ] S2. Sociomap declared: contract 4 -- side-table n_min/confidence, K100 quantiles, Stress bands, minimums into the spec; consumers read the pin"
  - "[ ] S3. Sociomap slots: built-in expressions for every F-formula, bit-identical on every fixture"
  - "[ ] S4. Sociomap editable: draft, check (Stress, statuses, aligned positions, heights, K100, audit checks C1-C16/P4-P14), activate"
  - "[ ] G1. Support and suppression documented and declared: one rule set, the combined n_eff named, thresholds in the spec (floor kept, ADR 0023)"
  - "[ ] G2. Aggregation documented and declared: estimators, Kish, donors, bootstrap reps/seeds/level, top-2-box; slots; 18.6.6 deviation label"
  - "[ ] G3. Support + aggregation editable, with the draft check (status changes, estimates, intervals)"
  - "[ ] W1. Weighting documented and declared: schemes, default role, expected totals and tolerances; weight cleaning as a choice"
  - "[ ] R1. Response process documented, declared and editable: betas, satisficing, style links, noise floor, temperature"
  - "[ ] V1. Validation tiers, admission tolerances, readiness bounds, presentation rounding: documented, declared, editable"
  - "[ ] X1. Simulation documented read-only; declared and editable when it is wired into runs"
  - "[ ] Z1. Workbench journeys per module (edit, check, activate, run, see the pin on Results); Doc follow-up"
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

- **A1. Framework.**
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
- **A3. Version store.**
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
- **A5. API.**
  - Read: `GET /api/v1/methodology` and `/{module}` (`OrganizationDep`).
  - Write (`require_administer`): `POST /{module}/versions`, `POST /{module}/check` and
    `PUT /{module}/activation`.
  - The API never names a preset (`layer_check`). It asks the domain.
- **A6. Web.**
  - `TABS` gains `methodology`, labelled "Metodika", and `OWN_TABS` gains it. The UI is Czech.
  - Inside the tab: a module list; per step, the formula (MathML via Temml, pinned), symbols, a
    parameter table (value, unit, origin, allowed range), evidence (rule, label, source page),
    tests, uncertainty and open question.
  - Number inputs accept scientific notation and negatives. Deep Research's `parseInput` refuses
    both, so it is not reused.
  - Vitest renders every formula in a captured API document.
- **S1.** Rules for every step the register lacks, and the null and wrong pointers fixed
  (AUDIT-F1, SOMECS-H7, AUDIT-F7). **The register is also edited by
  `sociomap-formula-corrections.md`:** land S1's register change as its own small PR, after that
  plan's open PR.
- **S2.** Contract 4 moves every listed constant into the specification. The side tables, K100
  and the readiness warning read the run's pin. A layer check forbids importing those constants
  on a run path. This is one fingerprint move for new runs; it is tested.
- **S3 / G2 / R1 / V1.** Each built-in expression is checked against the code on every fixture
  of its module, bit for bit: F1–F9, the AIA golden, the research aggregate cases and the
  response-process captures. Where floating-point order makes bit-identity impossible, the
  built-in keeps running the code path and the expression is shown with the measured maximum
  difference. Such cases are named, not hidden.
- **G1.** One rule set, not two (finding D2). The decision of what the single rule is goes to the
  methodologist and is made in the tab, as the first activated support version. The thresholds
  keep today's values as a floor until the disclosure question in ADR 0023 is answered.

## Findings (hypotheses until reproduced; each names the chunk that tests it)

- **H1.** `_rating` (`research_sociomap.py:267 @ 27062ec`) accepts only ints, so a float rating
  becomes missing. Tested in S1.
- **H2.** AUDIT-F1 and SOMECS-H7 have `implementation: null` although the code exists, and
  AUDIT-F7 points at a function only tests call. Tested in S1.
- **H3.** The `aia-sociomap-1` artifact's spec differs from the pinned spec, because the
  battery's scale overwrites `rating_scale_min/max` (`research_sociomap.py:469-476`). Tested in
  S1.
- **D1.** There are three weight-cleaning rules:
  - median imputation (`research_aggregate.py:158-165`);
  - refusal (`evidence/support.py:244-257`);
  - refusal (`population/weights.py:85-118`).

  Kish n is computed twice. Tested in W1.
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
