# The H-Model: what is reported, what is fitted, what is significant

**Status (2026-10-05):** the reported accuracy is implemented
(`aia_core.domain.sociomap.hmodel.hmodel_accuracy`, evaluator `aia_hmodel_accuracy_v1`), and so
is the **experimental AIA candidate** optimiser (`hmodel_candidate.fit_hmodel_candidate`,
method `aia_hmodel_candidate_v1`, register AIA-H9). SOMECS's fitting objective is **unknown**;
the candidate is not presented as SOMECS's method. The significance procedure (§ 5) is proposed,
not built. Rule ids refer to the evidence
register `docs/migration/sociomapping-evidence-register.json`; questions M* to
`.planning/plans/sociomapping-engine.md`. Each statement says whether it is documented,
reproduced, inferred or proposed.

## 1. What the sources fix

| Rule | Statement | Source | Label |
| --- | --- | --- | --- |
| SOMECS-H1 | Place the elements so that plane distances correspond to the fuzzy matrix, keeping its asymmetry | SOMECS help p. 53; p. 10 (C nearest to B, B nearest to A) | documented |
| QED-H2 | From each point, distances to the others follow the order of that point's ratings; not always fully possible | certification material p. 12; step by step p. 19 ("the order of distances is key, not the distance") | documented |
| SOMECS-H3 | Accuracy = Spearman's rank correlation between the Euclidean distance matrix and the fuzzy matrix, shown as a percentage | SOMECS help p. 53 | documented; details inferred (§ 2) |
| SOMECS-H6 | Of the possible layouts, the one most corresponding to the data is chosen; iterating can give another good one | certification p. 11; SOMECS help p. 54 | documented |
| SOMECS-H7 | Positions shown on a 0-1 frame with a per-point weight 0-1 | SOMECS help p. 57 | documented |
| SOMECS-H5 | An estimation module projects random symmetric matrices of n elements into 2-D and gives the distribution of their Spearman accuracy | SOMECS Input pp. 20-21, fig. 22 | documented (screen); details inferred |

Nothing in the sources states the fitting objective, the optimiser, or how per-point fit is
computed.

## 2. The reported accuracy (implemented)

Let `M` be the fuzzy matrix (relations `M_rs` in `[0, 1]`, higher = closer; diagonal undefined)
and `x_1..x_n` a layout, `d_rs = |x_r - x_s|`.

- **Similarity versus distance.** No transformation is needed: Spearman's coefficient depends
  only on ranks, so the accuracy uses `M_rs` and `-d_rs` directly. Any strictly increasing map of
  `M` (a similarity-to-distance conversion included) leaves it unchanged
  (`test_accuracy_ignores_monotone_transforms_of_relations`).
- **Direction.** `acc = rho_S(M_rs, -d_rs)`: +1 when the order of distances is exactly the
  reverse order of relations. SOMECS shows a positive percentage, so this sign (or an absolute
  value) is implied; a good layout cannot have a negative value in either reading.
- **Which cells -- directed relations in a symmetric geometry.** Every ordered pair `r != s`
  is one observation: `(M_rs, -d_rs)`. The distance is symmetric, so an asymmetric pair
  contributes two observations sharing one distance: `(M_rs, -d)` and `(M_sr, -d)`. The layout
  cannot make both "right" when they differ; the rank correlation scores how well the one
  distance serves both. This is how "keeping the asymmetry" (SOMECS-H1) can be scored without
  symmetrising the matrix first, and it differs from scoring the symmetrised matrix
  (`test_asymmetric_relations_enter_as_separate_observations`). For a symmetric matrix it
  equals the correlation over unordered pairs (`test_symmetric_matrix_ordered_equals_unordered_pairs`).
- **Ties.** Average ranks (the standard tie correction); Spearman's rho is Pearson's r of the
  ranks. Inferred, not documented.
- **Exclusions.** The diagonal. A side with no variation (every relation equal, or every
  distance equal -- a collapsed layout) has no rank correlation: the accuracy is `None` with
  the reason, never 0 (`test_degenerate_layouts_are_undefined_not_zero`).
- **Per-point fit (AIA-H4, proposed).** `fit_r = rho_S over s != r of (M_rs, -d_rs)`: QED-H2's
  criterion, scored for one point. SOMECS shows a per-point fit as a colour bar (help p. 56)
  without a formula. A constant row has no per-point fit.
- **Overall versus per-point.** The overall accuracy is one correlation over all `n(n-1)`
  observations; it is not the mean of the per-point values. Both are reported, and the mean
  of the defined per-point values is labelled `mean_per_point`.

**Why "one correlation over all cells" (inferred).** SOMECS's estimation screen (fig. 22)
shows a generated matrix with the coordinates SOMECS fitted to it. On those coordinates the
overall definition gives **0.786** (0.783-0.793 across the transcription's rounding), and
SOMECS's list of accuracies contains **0.785**; the mean of per-row values gives **0.723**,
below every listed value (0.732-0.850). The list is scrolled to its top while the run is at
0.074 %, so which entry belongs to the displayed matrix is not shown: the result is consistent
with the definition, not proof of it (`test_somecs_fig22_layout_scores_as_somecs_lists_it`).

## 3. Invariances the accuracy satisfies (tested)

Rotation, translation, reflection and uniform scaling of the layout; relabelling of the
elements (matrix and layout permuted together); strictly increasing transforms of the
relations. These are properties of the definition; the tests show the implementation keeps
them. They are not evidence about SOMECS.

## 4. The fitting objective: unknown in SOMECS; an experimental AIA candidate (AIA-H8, M2)

**What is known, and what is not.** SOMECS *reports* fit as a Spearman correlation (SOMECS-H3)
and the method *reads* maps ordinally -- the order of distances, not their size (QED-H2). That
is evidence about how fit is reported and interpreted. It is not evidence about how SOMECS
*searches* for a layout: its fitting objective and optimiser are undocumented.

**A comparison, not an identification.** On the fig. 22 matrix, under AIA's evaluator (§ 2):

| Layout | Accuracy | Status |
| --- | --- | --- |
| SOMECS's displayed layout | 0.786 (0.783-0.793 across the transcription's rounding) | provisional comparison score |
| Classical MDS on `1 - M` | 0.661 | baseline, the configuration tested |
| scikit-learn nonmetric MDS, best of 20 seeds (settings in `tools/somecs_estimation_experiment.py`) | 0.743 | baseline, the configurations tested |

SOMECS's layout scores higher than these baselines. That is consistent with an objective closer
to rank agreement than to stress, but equally with other explanations: more or better starts, a
different optimiser of a stress-like objective, manual adjustment before the screenshot, or an
evaluator that differs from ours. Other MDS variants or transforms could score differently. One
layout of one matrix cannot identify an algorithm.

**The experimental AIA candidate, `aia_hmodel_candidate_v1` (built).** AIA's own method,
labelled `EXPERIMENTAL_AIA` on every result; it makes no claim of equivalence with SOMECS. Its
input is a *declared relationship matrix* (`declared.py`, AIA-D1): values as measured, undefined
pairs named, on `fuzzy_0_1` or `signed_correlation`. Because both the evaluator and every phase
use relations only through their order, a signed correlation is laid out without conversion,
and any strictly increasing conversion gives the identical map (tested).

*Objective.* Maximise the reported accuracy (§ 2) over the defined ordered pairs; all points
weigh the same. *Search*, from each start, over elements in a canonical order (sorted ids):

1. *Smooth*: gradient ascent on `r(L, -D)`, the Pearson correlation of the relations' fixed
   average ranks and the negated distances.
2. Two branches, the better kept: *direct* (straight to 3) and *ordinal* (Kruskal-style ordinal
   stress with isotonic targets made strictly increasing by a small gap, then 3). The classical
   MDS start also refines its raw start, so the result never ends below that baseline.
3. *Exact*: one-point-at-a-time local search on the accuracy itself, 16 directions, halving
   step to 1e-6; between rounds a *repair* step on the pairs still out of order.

Why both branches, measured while building: on planted symmetric data (n = 10 and 20, three
seeds each) the direct branch alone stalled one or two pairs short of 1 (0.99987-0.99999); the
ordinal branch with plain isotonic targets let a violating pair settle into a tie; with strictly
increasing targets every planted case reached exactly 1. On fig. 22 the direct branch from the
classical MDS start reaches the higher accuracy (0.859 vs 0.841).

*Starts and selection* (after SOMECS-H6): classical MDS on a rank dissimilarity plus 4 seeded
random starts (`random.Random(seed + k)`, seed 20261005); highest accuracy wins, ties to the
earliest; every start's accuracies are stored. *Frame*: centre, principal axes, third moment
>= 0 per axis, scaled into 0.05-0.95 (SOMECS-H7); the accuracy is unchanged. *Cost*, measured
in this container: n = 10 about 1.5 s, n = 20 about 15-20 s (pure Python; a worker step).

*Unplaced elements.* An element with no defined relation (a constant answer column) is not
placed and is listed with its reason; its pairs are not observations of the rest.

**Acceptance for the candidate** -- criteria on AIA's own terms, none of them a test of
equivalence with SOMECS, and where each stands (`test_sociomapping_hmodel_candidate.py`):

- **Provisional comparison on fig. 22.** The candidate reaches **0.859** beside SOMECS's 0.786
  (rounding band 0.783-0.793). It is *above* the band. That is a finding to explain, not a pass:
  the candidate optimises this evaluator directly and SOMECS's objective is unknown; SOMECS may
  optimise something else, stop earlier, or start differently.
- **Baselines.** Classical MDS on a rank dissimilarity is the candidate's first start and is
  reported on every result (fig. 22: 0.627); the candidate never ends below it (structural,
  tested on six random matrices). Nonmetric MDS (scikit-learn) is measured only by
  `tools/somecs_estimation_experiment.py`; it is not a repository dependency.
- **Perfect fit only where it is guaranteed.** Met: accuracy exactly 1.0 on planted symmetric
  data, one strictly decreasing function of planted distances, no tied distances (n = 5-10 in
  the suite; n = 20 measured while building).
- **Asymmetric planted data -- the criterion first written here was wrong.** With each row a
  different decreasing function, the planted layout has every per-point fit 1 (QED-H2) but a
  *lower pooled accuracy* than other layouts (n = 6-10: planted 0.60-0.87, candidate 0.78-0.92).
  A layout maximising the pooled accuracy (SOMECS-H3) therefore need not keep each point's own
  order, and the candidate does not (tested). Which criterion governs an asymmetric H-Model is
  the method owner's question (plan M2). The research integration lays out object correlations,
  which are symmetric, so it is not affected.
- **Many independent matrices.** Planted symmetric (6 cases), asymmetric planted, random
  symmetric and asymmetric (6), tied 1-5 people ratings (certification Tab. 1), signed object
  correlations with negative pairs and a constant column, and fig. 22 as one member.
- **Repeatability versus reproducibility.** Identical input and parameters give an identical
  result in this container (tested); identical output on other hosts is expected (pure Python,
  fixed order) but claimed only where run.

**Still open after the build.** SOMECS's objective and optimiser; how it weights points; the "HM
correction" that trades accuracy for keeping coherent groups close (help p. 36; plan chunk 6b).

## 5. Significance (proposed -- SOMECS-H5, M15)

**What SOMECS shows.** Fig. 22: random symmetric matrices of `n` elements (diagonal 1, values
spread over 0-1), each projected into 2-D, with the distribution of their Spearman accuracies
and a CSV export. Each generated matrix gets its own fit.

**Proposal for AIA.**

- **Null hypothesis.** The observed matrix is no more representable in two dimensions than a
  matrix whose relations carry no structure, at the same size.
- **What is drawn.** Two nulls, both reported, because the sources settle neither:
  (i) SOMECS's: fresh random matrices, symmetric when the observed matrix is symmetric, values
  i.i.d. uniform on (0, 1) -- the generator SOMECS appears to use; (ii) a matched null: the
  observed matrix with the off-diagonal values of each row permuted independently, which keeps
  every row's value distribution, ties included, and destroys the structure between rows.
- **Refitting.** Every drawn matrix is fitted with the same objective, starts and seeds policy
  as the observed one. Without refitting, the comparison would score random relations against
  a layout chosen for the observed ones, which tests nothing.
- **Result.** `p = (1 + #{k : acc_k >= acc_obs}) / (K + 1)` with `K` and the seeds recorded;
  the null distribution's quantiles stored beside the observed accuracy.

**Cost.** `K` refits per map. At `n <= 30` and `K = 200` this is bounded and runs as a worker
step, never in a request.

## 6. Exports that would narrow what is open

One export can rule candidate rules in or out; it need not identify an algorithm uniquely.
The two below bear on the H-Model; E2-E4 and E6-E9 are in the plan's evidence table.

| Export | Could distinguish | Might remain unresolved |
| --- | --- | --- |
| E1: SOMECS Matrix Model Estimation, n = 10, run to completion, CSV saved | Overall-pairs vs mean-per-row vs Pearson accuracy, sign or absolute value, over hundreds of matrix / coordinate / accuracy triples; the random generator's distribution | Tie handling (continuous random values rarely tie); the asymmetric case (the run ticks "symmetrical"); the optimiser, since coordinates are outputs, not the process; whether the module fits the way the main H-Model does |
| E5: SOMECS H-Model of the help's drinks example -- positions, accuracy, per-point bars | A second accuracy check on a real matrix; per-point candidates, to the colour bar's resolution; SOMECS's layout to compare the candidate's with | The optimiser (one layout from one search); per-point candidates the bar's resolution cannot separate |
