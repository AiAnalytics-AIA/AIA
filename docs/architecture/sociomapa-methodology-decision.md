# Sociomap methodology decision — `AIA_SOCIOMAP_V3`, earlier `V1` (D6 / OI-16)

**For:** the methodology owner who approves client-facing Sociomaps.
**Decides:** whether **`aia-sociomap-3`** (`AIA_SOCIOMAP_V3`, its fingerprint in the v3
section) may be used for client deliverables. The one approval this document asks for is the
v3 table below. Everything after it -- the v2 section and the `AIA_SOCIOMAP_V1` package in
§1-§4 with their approval lines -- is **history**: an answer recorded there approves
`aia-sociomap-1` at most, never `aia-sociomap-3`. Until the v3 table carries an ACCEPT, **no
Sociomap is client-deliverable** (§6).

The v1 preset, the subject of the history in §1-§4:

| | |
| --- | --- |
| Spec | `AIA_SOCIOMAP_V1`, `methodology_version = "aia-sociomap-1"` |
| Spec fingerprint | `9d4dffeac5531f3fc0e18c2db6a2a9c8d823d5fd299fbec30870c9aa2f31c211` |
| Engine | `aia_core.domain.sociomap`, `ENGINE_IMPLEMENTATION_VERSION = "1.1.0"` @ `17eac55` |
| Reference | `AiAnalytics-AIA/AIA-reference` @ `678e298`: `sociomapping-reference-contract.md`, fixtures F1–F9 |
| Engineering detail | [sociomapa-deterministic-engine.md](sociomapa-deterministic-engine.md) |

## v3 (2026-10-09): the decision's subject is `aia-sociomap-3`

AIA's product owner decided the audit's open questions Q5-Q7 for AIA on 2026-10-09, pending
the audit's author ([plan § 4a](../../.planning/plans/sociomap-formula-corrections.md)). The
decisions are a methodology version of their own, so D6 is now to approve **`aia-sociomap-3`**;
`aia-sociomap-2` is unchanged and stays readable for the runs that pinned it.

| | |
| --- | --- |
| Spec | `AIA_SOCIOMAP_V3`, `methodology_version = "aia-sociomap-3"`, spec contract 3 |
| Spec fingerprint | `e16dc0d0636109322900ab56ed9613e6b2d4f6e65f2dd7e26b9ada059b7cf241` |
| Engine | `domain/sociomap/engine_v2.py`, `compute_object_map`; `terrain.object_envelope` @ `1025539` (#205) |
| Pinned by | every new research run, beside `aia-sociomap-1` (`research_sociomap.default_methods`) |
| What it covers | the object map (F1-F3, F6-F9) and its terrain (F12, F13); respondent placement (F10) is not built |

What `aia-sociomap-3` adds to `aia-sociomap-2`, and what each choice claims:

- **Q5 (c), two concepts kept apart.** Positions show whether people's relative preferences
  for two objects move together (F2's per-person min-max, then Pearson, then F6's distance);
  how highly an object is rated is shown separately, as height. Height is never closeness.
- **Q6 (b) + (c), two gates.** Evidence sufficiency: UNKNOWN below `n_min` 30, WEAK when the
  Fisher 95 % interval includes 0, RELIABLE otherwise, read on each pair's **Kish effective n**
  of its valid respondents' weights. Practical materiality: `|r| >= 0.10`, recorded per pair as
  `meets_effect_floor` beside the state and never folded into it. A link is drawn only for a
  RELIABLE pair that meets the floor.
- **Q7 (d) with (a).** Height is selectable; the default in maps and reports is the mean
  rating on the declared 0-1 scale.
- **The terrain (F12).** The max-envelope of the PRIMARY objects' hills, each exactly its
  height; `sigma = 0.25` on the fixed ruler is **AIA's provisional width**
  (`aia_provisional_r08_5pct`: a hill falls below 5 % of its height at the correlation distance
  of r = 0.8), because the audit leaves the width to its author (A5).

Still open, and not answered by approving this version: the respondent-misfit threshold (A4),
the audit author's own value for the kernel width (A5), F8's denominator reading (B8), the
F16 equivalence tolerance (B10), the SECONDARY boundary (B11), the audit's check scripts and
their output (C12-C15), finding F-4a-1 and finding F-S3-1. An answer from the audit's author
that differs from any choice above becomes a new methodology version, never an edit to this
one. Approving `aia-sociomap-3` approves its fingerprint as a whole (§5); the map stays
`INTERNAL_ONLY` until then.

**Approval of `aia-sociomap-3`**

| Field | Value |
| --- | --- |
| Decision | ACCEPT / REPLACE / DEFER |
| Decided by | |
| Date | |
| Conditions | |

## v2 (2026-10-08), history: the decision's subject was `aia-sociomap-2`

*Superseded by v3 above; kept as the record of why v1 stopped being the subject.*

The formula audit ([`sociomap-formula-corrections.md`](../../.planning/plans/sociomap-formula-corrections.md))
is canonical for AIA's object map, and overrides every earlier Sociomap decision where they
disagree. D6 is therefore to approve **`aia-sociomap-2`**, not `aia-sociomap-1`:

| | |
| --- | --- |
| Spec | `AIA_SOCIOMAP_V2`, `methodology_version = "aia-sociomap-2"`, spec contract 3 |
| Spec fingerprint | `3f1c01221492f883ce715b5763a3815ae2a8f4c1e5456f3c581a9f67838d6b43` |
| Engine | `domain/sociomap/engine_v2.py`, `compute_object_map` @ `71bf294` |
| What it covers | the object map only (F1–F3, F6–F9); respondent placement and terrain are not in contract 3 yet |

Every new research run pins both methods and computes both; both are `INTERNAL_ONLY`, and
Results and the report draw only `aia-sociomap-1` until chunk 5.

The four `aia-sociomap-1` declarations below, re-read against the audit:

- **§1 dissimilarity target.** For the object map the audit's correlation distance
  `sqrt(2 (1 − r~))` (F6) replaces it; AIA's δ stays only as `aia-sociomap-1`'s.
- **§2 layout.** For the object map the audit's SMACOF on a fixed ruler (F6, F7) replaces the
  unfolding; respondent placement (F10) is not built.
- **§3 map frame.** The audit rejects stretching a map to an extent (F7); contract 3 declares
  `fixed_ruler`.
- **§4 missing relation policy.** Agreed in substance: an unknown pair is UNKNOWN and weighs
  nothing (F3), never 5.5.

Still open for the owner, not answered here: the audit's provisional `n_min` 30 and the pair
evidence basis (Q6), the default height and F8's denominator (Q7), finding F-4a-1, and
finding F-S3-1 (a context object moves PRIMARY r~ under F2). The approval line for the v1
declarations below stays as it was; a decision on `aia-sociomap-2` approves its fingerprint as
a whole (§5).

## v1 package, history: `AIA_SOCIOMAP_V1` (the original D6 subject)

*From here to §4 is the original package. Its approval lines decide `aia-sociomap-1` only; they
are not the D6 decision, which is the v3 table above.*

## What is not in question

Everything else in the preset is **recovered reference behaviour, verified
against a fixture**, and needs no methodology decision:

- scale coercion to 1–10 (F1);
- mutual-relation position input (F2);
- ipsatization (F3, ported; see §1);
- the normaliser (F5);
- object metrics and the T-score default (F6);
- respondent density terrain and its constants (F7);
- object weighted-mean terrain semantics and constants (F8, partial);
- drag as a view override (F9).

The four entries below are the only places where AIA chose because the
reference could not be read.

---

## 1. Dissimilarity target — `scale_top_minus_rating`

**Reference evidence.**
- F4's metadata: the reference unfolds `target = "row_relative_dissimilarity"`, with `ipsatized = 1` and `missing_policy = "observed_cells_only"`.
- The pipeline order is `ipsatize → coerce → mutual → fit_unfolding`.
- The rating scale is 1–10 (F1; the F8 `mean_rating` bounds).

**What is not recovered.** The formula behind `row_relative_dissimilarity`, which is in `sociomap.py` inside the withheld archive. F4 pins the result, not the rule. About 200 candidate target and stress definitions were evaluated on F4's own coordinates, and none reproduces its `stress_1 = 0.391394498`. Reconstruction has stopped (OI-13).

**Current AIA choice.** `δ_ij = rating_scale_max − rating_ij` over observed cells, with `rating_scale = [1, 10]` and `ipsatize = false`.

**Why it was chosen.**
- The layout is a ratio model, so it needs non-negative dissimilarities whose zero means "at the object".
- Ipsatized values are centred on each respondent's mean and are negative for half the ratings, so the implemented target cannot take them. `ipsatize: true` is refused rather than silently ignored.
- `row_max − rating` was implemented first and rejected: under a ratio model it places every respondent exactly on their favourite object.

**Behavioural consequence.**
- Absolute rating level shapes position. A respondent who rates everything 8–9 sits nearer every object than one who rates 2–3.
- How widely each respondent uses the scale is absorbed by a per-respondent scale factor. A uniform shift in level is not.
- A respondent who rates every object at 10 has no position. They are excluded from the map with a reason, but still counted in `mean_rating` and `support_n`.
- A rating outside [1, 10] is refused, not clipped.

**Alternatives.** None implemented. The only real alternative is the reference's `row_relative_dissimilarity`, and it becomes available only when the archive does.

**Legacy comparability.** **None.** Legacy maps were built from ipsatized, row-relative targets, so the input to the layout differs before any geometry is computed.

**Recommended decision** *(proposal — requires methodology-owner approval)*. **ACCEPT with conditions:**
- deliverables name `aia-sociomap-1` as their methodology;
- no deliverable compares an AIA map with a legacy map;
- re-review when the archive becomes available.

**Approval:** ☐ ACCEPT ☐ REPLACE ☐ DEFER — by: ______ date: ______ notes: ______

---

## 2. Layout — `aia_rowcond_unfolding_v1`

**Reference evidence.**
- The primary contract is row-conditional multidimensional unfolding.
- Two branches exist: R `smacof::unfolding`, and the Python `fit_python_unfolding`.
- F4 pins the Python branch's output: 24 respondent and 5 object coordinates, `stress_1 = 0.391394498`, `iterations = 350`, `seed = 20260814`, convergence `|Δstress| < 1e-7`.
- The reference chooses between the two branches by probing the host for `Rscript`, falling back silently from R to Python. The reference repository itself classifies this as a defect to remove (INTENTIONAL_DIFFERENCE).

**What is not recovered.**
- `fit_python_unfolding`'s source (OI-13).
- The R wrapper's call arguments, and any R fixture (OI-15, `REF-GAP-SOCIO-R-SMACOF`).

Both are in the withheld archive.

**Current AIA choice.** `aia_rowcond_unfolding_v1`: row-conditional ratio unfolding by alternating exact majorisation. Parameters are `dimensions 2`, `max_iterations 2000` and `convergence_tolerance 1e-7` (the reference's own stopping rule); `seed = null`.

**Why it was chosen.**
- It is declared, never detected.
- It is deterministic without randomness, and pure Python, so it is bit-identical on every host.
- It is row-conditional, as the contract requires.
- It recovers a planted geometry to stress-1 < 1e-4, and is pinned by its own golden fixture.
- Both reference branches refuse to run and give the reason. No fallback exists.

**Behavioural consequence.**
- Coordinates differ from any legacy map.
- It has a single deterministic start, so it can stop in a local minimum. Measured: one fully observed 60 × 8 planted design stops at stress-1 0.017, against < 1e-4 on two others.
- Designs whose rating blocks overlap on only two objects admit a reflected solution at nearly the same stress.
- `stress_1` is reported on every artifact.
- Cost is 0.41 s at 200 × 12 and 3.3 s at 1,000 × 20.

**Alternatives.** None implemented. `python_weighted_unfolding` and `r_smacof_unfolding` are known identifiers that are refused until their source or fixture exists. The iteration cap and tolerance are parameters, not alternative methods.

**Legacy comparability.** **None, geometrically or numerically.** On F4's own ratings, the AIA configuration sits at Procrustes RMSD **1.91** from the legacy one, whose RMS radius is **2.01**. That is unrelated geometry. AIA maps are comparable with each other: the same inputs and spec give an identical artifact.

**Recommended decision** *(proposal — requires methodology-owner approval)*. **ACCEPT with conditions:**
- the same three conditions as §1;
- every deliverable states `stress_1`;
- the methodology owner sets the stress level above which a map may not be delivered. That threshold is methodology, not engineering, and this proposal does not choose it.

**Approval:** ☐ ACCEPT ☐ REPLACE ☐ DEFER — by: ______ date: ______ notes: ______

---

## 3. Map frame — `max_abs_to_extent`, extent `45`

**Reference evidence.**
- The terrain works in map units: a 43 × 43 grid spanning ±62, with kernel σ = 9.5 for respondents and 12 for objects (F7, F8).
- F7's synthetic respondent points lie within ±45.
- The layout's own coordinates are on the order of ±2.5 (F4).

**What is not recovered.** How the reference converts layout units into terrain units. This is frontend code in the withheld archive, and no fixture spans both units.

**Current AIA choice.** Scale every coordinate by `45 / max |coordinate|` over all placed respondents and objects. The factor is recorded as `layout_to_map_scale`.

**Why it was chosen.**
- A kernel of width 9.5 means nothing on coordinates of ±2.5, so some conversion is unavoidable.
- 45 matches the range of the reference's own terrain fixture. It keeps every point inside the grid with a margin of 17 units, which is 1.8 σ for respondents and 1.4 σ for objects.

**Behavioural consequence.**
- Terrain shape depends on the frame. Hills merge or separate as the scale changes, because σ is fixed in map units.
- One outlying point sets the scale for everyone. A single extreme respondent compresses the rest of the map towards the centre, and their hills merge.

**Alternatives.** The method has one implemented option. The extent is a free, supported parameter: any positive value is accepted and fingerprinted. That changes terrain granularity, not positions relative to each other.

**Legacy comparability.** Legacy terrain *values* cannot be compared, because the legacy scale is unknown. The terrain *formula* is verified to 1e-9 against F7, given points in map units.

**Recommended decision** *(proposal — requires methodology-owner approval)*. **ACCEPT** extent 45. Revisit only if an outlier-robust frame is wanted, which would be a new, declared method rather than a change to this one.

**Approval:** ☐ ACCEPT ☐ REPLACE ☐ DEFER — by: ______ date: ______ notes: ______

---

## 4. Missing relation policy — `refuse`

**Reference evidence.** Recovered exactly (F1): the reference substitutes `NaN → 5.5`, `+inf → 10.0` and `−inf → 1.0`. A missing relation becomes the scale midpoint.

**What is not recovered.** Only the order of the sentinel substitution against scale-branch detection, for a matrix that mixes missing cells with a 0–1 or −1–1 scale. The engine refuses that case either way (`AmbiguousCoercion`). The rest is recovered.

**Current AIA choice.** `refuse`: a missing off-diagonal relation cell stops the computation with an error naming the cell.

**Why it was chosen.** The midpoint sentinel scores *unknown* as *neutral*, which `ARCHITECTURE.md` A4 forbids by default. A missing relation feeds `relation_classic` and the T-score, which is the default object height, so it silently shapes the object map.

**Behavioural consequence.** A study with any missing relation cell cannot use relation-derived metrics under this spec. It must either complete the matrix, or run a spec with no relation matrix and use `mean_rating` or `support_n` as the height.

**Alternatives.** One, implemented: `reference_midpoint_sentinel`. It reproduces the reference, lists every substituted cell in the artifact and warns. It is chosen only by explicit declaration in a study's spec, never by default.

**Legacy comparability.** **Full** for complete matrices: relation metrics match the reference to 1e-9 (F6), whatever the policy. For incomplete matrices, only `reference_midpoint_sentinel` reproduces legacy numbers.

**Recommended decision** *(proposal — requires methodology-owner approval)*. **ACCEPT** `refuse` as the default. Permit `reference_midpoint_sentinel` per study only with the owner's explicit sign-off, recorded against that study's spec.

**Approval:** ☐ ACCEPT ☐ REPLACE ☐ DEFER — by: ______ date: ______ notes: ______

---

## 5. What each answer does

| Answer | Effect |
| --- | --- |
For the D6 decision, the v3 approval table:

| Answer | Effect |
| --- | --- |
| **ACCEPT** | `aia-sociomap-3` enters the approved-methodology policy (§6) bound to fingerprint `e16dc0d0636109322900ab56ed9613e6b2d4f6e65f2dd7e26b9ada059b7cf241`; its maps may become deliverables under the conditions recorded in the table. No other version or fingerprint is approved by it |
| **REPLACE** | Engineering implements the named replacement as a new declared method with a new `methodology_version`; `aia-sociomap-3` stays unapproved |
| **DEFER** | Nothing is client-deliverable. Computation for internal and exploratory use continues unchanged |

Approval is of a whole spec, never of one of its choices, because the choices interact.

For the history in §1-§4 only: an ACCEPT on all four v1 lines would admit `aia-sociomap-1`
(fingerprint in the v1 table at the top) and nothing else; a partial ACCEPT approves nothing.

## 6. The integration rule

Recorded normatively in
[sociomapa-deterministic-engine.md §13](sociomapa-deterministic-engine.md#13-computable-is-not-deliverable).
In short:

1. **Computable.** The engine may compute any explicitly requested SociomapSpec that `require_supported` accepts.
2. **Deliverable.** A Sociomap becomes client-facing only if its spec's `methodology_version` and fingerprint are approved in the product/methodology policy.
3. **Never substituted.** No API, worker or UI may fill in `AIA_SOCIOMAP_V1`, or any other spec, when one was not explicitly given.
