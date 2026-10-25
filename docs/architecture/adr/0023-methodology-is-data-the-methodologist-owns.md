# ADR 0023 — AIA's mathematics and statistics are shown from the code, and their parameters and formulas are a methodology version the methodologist edits

**Status:** Proposed — develop (2026-10-11). To be implemented as
[`methodology-tab.md`](../../../.planning/plans/methodology-tab.md).
**Builds on:**
- [ADR 0020](0020-runtime-editable-system-prompts.md): immutable versions, append-only
  activations, a pin at enqueue, audit.
- [ADR 0022](0022-deep-research-settings-are-approved-data.md): a code-owned catalogue, a default
  that changes nothing while nothing is stored, values that shape a result move its reuse
  identity.

**Takes up:** the audit *NPC Sociomapa: faulty formulas in the code* (A. Bahbouh, 2026-10-06), as
carried by the evidence register (AUDIT-F1 … F16) and
[`sociomap-formula-corrections.md`](../../../.planning/plans/sociomap-formula-corrections.md).
**Leaves unchanged:** the D6 / OI-17 client-facing gate, the licence gate, residency and egress.
**Owner decision, 2026-10-25** (ADR-0020-0024 (b), the audit page, relayed by coordinator 3): the owner will review ADRs 0020 to
0024 one by one. His note, verbatim: "i want to review them, Create a document that includes all the
questions, how they're connected in AIA, and the inputs and outputs. Include an example when
explaining complex topics. do it for each individually." The status is unchanged until he does.

**Date:** 2026-10-11

## Context

AIA has a methodologist who keeps its mathematics and statistics correct. The owner's
requirement: **every piece of mathematics or statistics in AIA is visible to them and directly
editable by them**, the formulas included, not only their constants. Today none of it is. The
whole inventory, anchored at `27062ec`, is in the plan:

- **Sociomap.** There are three paths:
  - `aia-sociomap-1`, the reference;
  - `aia-sociomap-3`, the audit's object map;
  - the experimental H-Model.

  Formulas live in `domain/sociomap/` and `research_sociomap*.py`. Method constants sit outside
  the specification: the side tables' `n_min` and confidence, K100's resamples and seed, the
  Stress bands, the mappability minimum.
- **Aggregation and uncertainty** (`research_aggregate.py`, an EXACT port of 18.6.6): weighted
  estimators, Kish n, donor support, a cluster bootstrap with inline replicate counts and seeds,
  and top-2-box.
- **Support and suppression** (`evidence/support.py`): `REFERENCE_THRESHOLDS`, and the combined
  n_eff the gate reads.
- **Weighting** (`population/`): declared schemes and expected totals; no calibration step.
- **The response process** (`respondent_behavior.py`, EXACT): β coefficients, the satisficing
  cap, style links. It shapes every AI respondent's answer distribution.
- **Validation tiers, admission tolerances, readiness bounds, report rounding.**
- **The simulation core:** reference constants and the inoculation design; not wired into runs
  yet.
- **Deep Research scoring:** already ADR 0022's.

All of it is constants and formulas in code. A change is a branch, CI and a deploy, written by
someone other than the methodologist.

## Decision

1. **One tab, "Metodika", generated from the code.**
   - A pure domain package, `aia_core.domain.methodology`, holds a catalogue per **method module**:
     `sociomap`, `aggregation`, `support`, `weighting`, `response_process`, `validation`,
     `readiness`, `presentation`, `simulation`.
   - Each module lists its steps in computation order. Each step carries:
     - its formula, as a slot expression (decision 4) or LaTeX;
     - its symbols, units and parameters, with values read from the in-force method;
     - the register rules or fixtures that evidence it;
     - the tests that pin it;
     - the function it describes, pinned by source hash.
   - Tests enforce completeness:
     - every field of every module's specification belongs to exactly one step;
     - every step's tests exist;
     - a moved source hash fails until the step is re-read.
   - The Sociomap module follows the audit's numbering, F1–F16, plus the reference map and the
     H-Model.

2. **Every module has a declared specification; nothing that shapes a number stays a loose
   constant.**
   - Inline literals and module constants that shape a result become specification fields. Each
     module's code preset is its specification today. A test proves every output bit-identical,
     so declaring a value changes no result.
   - Examples of what moves into a specification:
     - the bootstrap's 400/350 replicates and its seeds;
     - `_SUPPRESS_BELOW` / `_REPORTABLE_FROM`;
     - `REFERENCE_THRESHOLDS`;
     - the side tables' `n_min = 30` and 0.95;
     - the Stress bands;
     - the β coefficients;
     - the readiness bounds;
     - the decimals per metric.
   - Every consumer reads the run's pinned specification, never a module constant. That includes
     the readiness warning, which today reads `AUDIT_PROVISIONAL_N_MIN` directly
     (`research_design.py:625 @ 27062ec`). A layer check forbids importing a method constant on a
     run path.
   - **What stays code, shown read-only:**
     - numerical-method internals that only guard arithmetic: division floors, Jacobi limits,
       step-size schedules;
     - iterative algorithms themselves (decision 5);
     - rails that are not statistics: the licence gate, residency and data class; "a number
       reaches a result only through admission"; fictional data labelled as fictional;
       individual-level claims refused.

     The *values inside* admission (thresholds, tolerances, interval level) are methodology and
     editable.

3. **What is edited is a methodology version, per module, put in force by an activation.**
   - **Drafts and versions.** A person derives a draft from the in-force version and changes
     parameters or formulas. The module's validator checks it, reporting every problem at once.
     It is stored immutable in `methodology_versions` (organization, module, number, base,
     payload, fingerprint, note, author, time).
   - **Activation.** A version is put in force by an append-only `methodology_activations` row:
     the newest wins, and `NULL` means the code preset.
   - **Audit.** Every change writes an `access_audit` row.
   - **Nothing stored means nothing changes.** Each module's resolution then yields the code
     preset byte for byte, and a test pins it.
   - **Reference baselines stay.** A module that ports 18.6.6 EXACT keeps its code preset as the
     tested reference: the aggregation, the response process and `aia-sociomap-1`. An edited
     version is a labelled **deviation from the 18.6.6 reference**, never an edit of it, so the
     parity suites keep testing what they test.

4. **Formulas are editable in declared slots, as expressions the engine evaluates.**
   - **Slots.** Each formula the methodologist may replace is a slot with a declared signature:
     its variables (with units and domains), its parameters, and the index sets it may aggregate
     over. Slots exist wherever a formula exists. Examples:
     - **Sociomap:** each of F1–F16, e.g. the scale transform, the person normalisation, the
       estimator, the effective n, the interval, the status rule, δ(r), Stress and its bands, the
       scores, the K100 interval, the kernel and how hills combine, placement misfit, the effect
       sizes and the multiplicity rule.
     - **Aggregation:** weighted mean, variance (its ddof), the quantile rule, Kish n, the
       combined n_eff, top-2-box, weight cleaning.
     - **Support:** the status rule.
     - **Response process:** each β, the satisficing λ and its cap, the style signal and noise.
     - **Simulation:** the inoculation target.
     - **Presentation:** rounding.
   - **The expression language.**
     - Allowed: arithmetic, comparisons, `if … then … else`, `exp`, `log`, `sqrt`, `abs`, `min`,
       `max`, `floor`, `tanh`, `atanh`, `Φ`, `Φ⁻¹`, and `sum`, `mean`, `max`, `min` over the
       slot's declared index sets.
     - Not allowed: names other than the slot's own, loops, attribute access, imports, I/O and
       randomness. A slot that needs a draw gets it as a declared variable from the code's
       seeded generator.
     - Processing: it is parsed to an AST, every node is checked against the whitelist, and it is
       compiled once to a closure. No text reaches `eval`.
   - **What is shown is what runs.** The LaTeX on the page is generated from the stored
     expression.
   - **Built-in formulas are expressions too.** Each is proved bit-identical to the code it
     mirrors on every fixture. With nothing stored, the code path runs.
   - **Properties a formula must keep.** Each slot declares them, and they are checked on a grid
     before a version is saved. Examples:
     - a kernel is non-negative, 1 at 0 and non-increasing;
     - δ is ≥ 0 and 0 at r = 1;
     - an interval contains its estimate;
     - 0 < n_eff ≤ n;
     - probabilities stay in [0, 1] and sum to 1.

     A formula that yields NaN or ±∞ on its declared domain is refused, never coerced
     (`CLAUDE.md` §8).

5. **Algorithms are a choice among registered implementations, not an expression.**
   - Iterative procedures stay code and are each a selectable choice with its own parameters:
     SMACOF, the unfolding, the bootstrap loop, Higham's nearest correlation, bisection
     calibration, coherence linkage, Procrustes.
   - A new algorithm is a code change: a fixture first, then review.
   - The tab lets the methodologist file that request from the step it would replace, with the
     formula they want written in the slot language as its specification.

6. **A run pins every module in force when it starts.**
   - `ResearchRuns.start` resolves each module's in-force version and pins them all: payload,
     fingerprint, origin. It does so beside the existing Sociomap method pin, which becomes the
     `sociomap` module's pin.
   - A retry keeps the original pins, and an activation changes only runs started afterwards.
   - Each module's fingerprint joins the input fingerprint of every artifact it shapes, so
     nothing made under one method is reused under another.
   - A run made before this ADR reads as "code preset at that commit", as legacy Sociomap pins do
     today.

7. **A draft is checked before activation, on fictional and fixture data only.**
   - The draft and the in-force version run side by side through the real engine, and the
     check shows the differences, per module:
     - Sociomap: Stress-1, pair statuses, aligned positions, heights, K100;
     - aggregation: estimates and intervals;
     - support: rows that change between REPORTABLE, INDICATIVE and SUPPRESS;
     - response process: answer distributions.
   - It also reruns:
     - the audit's printed checks C1–C16 and P4–P14, for the Sociomap;
     - the module's reference fixtures, reporting where the draft departs from 18.6.6.
   - A draft that fails a check can still be activated. The version then carries the failed
     checks, and every result made with it says so. Changing the method is the methodologist's
     call.

8. **Rendering.** Formulas render to MathML with Temml, pinned. A test renders every formula the
   catalogue can produce, so a malformed one fails CI rather than a page.

9. **Access is not designed here.**
   - Reading follows the rest of Settings.
   - Writing uses `OrganizationContext.require_administer` (ADR 0019), the gate every Settings
     write uses. No role is introduced.

10. **The small-cell thresholds are the methodologist's, both ways.** `min_cell`, `n_guard`, the
    donor minimums and `max_donor_share` are editable like any other parameter. They can be raised
    or lowered, with no floor. The owner decided this on 2026-10-11. Like every value, they are
    bounded only by their declared domain (for example a count is ≥ 1).

    A lowered threshold also lowers how far an output is kept from reproducing a few licensed donor
    respondents. So the draft check (decision 7) lists every row a draft would newly report. The
    version records the thresholds it was activated with.

## Not decided here

- **Signing D6 from the tab.** An activated version is not a sign-off, and the map stays
  `INTERNAL_ONLY`.
- **Per-study methods** (I0 of `sociomap-formula-corrections.md`), and a methodologist role.
- **Editing an iterative algorithm from the page.**

## Consequences

- The methodologist sees AIA's mathematics as it runs: every value with its origin, every formula
  as the engine evaluates it. They change parameters and formulas without a deploy, with the
  change pinned per run, checked on fixtures, attributable and reversible.
- **Cost 1: two homes.** Every method now lives in the code preset and the stored version. The
  tab always names which one is in force.
- **Cost 2: formula code outside review.** An edited formula is code that has not been reviewed.
  The expression language bounds what it can do: no I/O, no loops, deterministic. The slot
  properties and the reference checks bound what it can mean. Neither proves it right; the
  version records who took that responsibility.
- **Cost 3: the declaration step costs effort and is one-time.** Every module needs its loose
  constants declared and its consumers switched to the pin before it can be edited. That is the
  bulk of the plan.
- **Cost 4: one fingerprint move.** Every new run's fingerprints move once, when module pins
  enter them. Old runs read as before.

## Revisit when

- methods must differ per study or per client;
- the methodologist must approve separately from an Admin;
- the simulation core is wired into runs;
- a module needs an algorithm the expression language cannot express.
