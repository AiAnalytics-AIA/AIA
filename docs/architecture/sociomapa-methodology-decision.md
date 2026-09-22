# Sociomap methodology decision — `AIA_SOCIOMAP_V1` (D6 / OI-16)

**For:** the methodology owner who approves client-facing Sociomaps.
**Decides:** whether the four AIA declarations in `AIA_SOCIOMAP_V1` may be used
for client deliverables. Until this document carries an approval, **no Sociomap
is client-deliverable** (§6).

| | |
| --- | --- |
| Spec | `AIA_SOCIOMAP_V1`, `methodology_version = "aia-sociomap-1"` |
| Spec fingerprint | `9d4dffeac5531f3fc0e18c2db6a2a9c8d823d5fd299fbec30870c9aa2f31c211` |
| Engine | `aia_core.domain.sociomap`, `ENGINE_IMPLEMENTATION_VERSION = "1.1.0"` @ `17eac55` |
| Reference | `AiAnalytics-AIA/AIA-reference` @ `678e298`: `sociomapping-reference-contract.md`, fixtures F1–F9 |
| Engineering detail | [sociomapa-deterministic-engine.md](sociomapa-deterministic-engine.md) |

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
| **ACCEPT** (all four) | `aia-sociomap-1` enters the approved-methodology policy (§6) bound to the fingerprint above; its maps may become deliverables under the stated conditions |
| **REPLACE** (any) | Engineering implements the named replacement as a new declared method with a new `methodology_version`; this preset stays unapproved |
| **DEFER** (any) | Nothing is client-deliverable. Computation for internal and exploratory use continues unchanged |

A partial ACCEPT does not approve the preset: approval is of a whole spec,
because the four choices interact.

## 6. The integration rule

Recorded normatively in
[sociomapa-deterministic-engine.md §13](sociomapa-deterministic-engine.md#13-computable-is-not-deliverable).
In short:

1. **Computable.** The engine may compute any explicitly requested SociomapSpec that `require_supported` accepts.
2. **Deliverable.** A Sociomap becomes client-facing only if its spec's `methodology_version` and fingerprint are approved in the product/methodology policy.
3. **Never substituted.** No API, worker or UI may fill in `AIA_SOCIOMAP_V1`, or any other spec, when one was not explicitly given.
