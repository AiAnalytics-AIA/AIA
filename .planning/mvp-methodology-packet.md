# MVP methodology packet: every open decision that is the methodology owner's

2026-10-20. For **A. Bahbouh, methodology owner** (his AIA Sociomapa methodology is canonical, the
product owner's words), sent by the coordinator and the product owner. Nothing here is an answer.
Each question is one decision, stated so it can be answered in a line. Code claims are anchored
`file:line @ 854c209` (`develop` at the time of writing) unless another SHA is given.

**How to answer.** Quote the packet id (`MQ-01` … `MQ-25`) and the option letter, or write your
own rule. Answers are recorded in `mvp-cohesion.md` under their MVPQ id (the column "MVPQ" below)
and then carried into the affected plans by a docs PR. MQ-01 has no MVPQ id yet: the docs PR that
records its answer gives it one (`.planning/mvp-owner-decisions.md` allocates them). A
recommendation below is the plans' own proposal, never an approval; where the plans have none,
the packet says so.

**What is already settled and not asked.** The product owner's parts of MVPQ-03, 05 and 09 (2026-10-20,
`mvp-owner-decisions.md`); the scope of open-answer coding and of respondent replacement (MVPQ-02, F18);
segments both defined and clustered (MVP-17); object, respondent and segment maps in the MVP (MVP-16,
AC-09); the canonical audit's settled answers (`sociomap-formula-corrections.md` § 4: F2 wins, two stages
F6 then F10, SECONDARY objects never in PRIMARY scores); your own 2026-10-19 decisions in
`signed-off-sociomap-method.md` ("Decisions taken"). The product owner's provisional 2026-10-09 answers to
Q5-Q7 are **provisional for AIA**, not yours; MQ-03 to MQ-05 ask you to confirm or replace them.

## The order, and why

MQ-01 decides what most of the others mean: under `aia-sociomap-5` several MVPQ-12 questions are
already answered by your method, differently from what `aia-sociomap-3` computes. So it comes first,
and every later question says how its answer depends on MQ-01.

| Tier | Ids | What the answers unblock |
|---|---|---|
| 1. The method | MQ-01, MQ-02 | The register entry, which map the web and the report draw, the respondent map (AC-09), the reconciliation of `segment-maps-and-drilldown` 0/1/3/9/10 and `sociomap-formula-corrections` 3 |
| 2. The map's meaning | MQ-03 – MQ-09 (MVPQ-12) | The pair evidence policy, height and terrain, respondent fit, context objects, the F16 product; `sociomap-formula-corrections` 0b, 1d, 3, 4c, I0 |
| 3. Segments | MQ-10 – MQ-14 (MVPQ-03) | `segment-maps-and-drilldown` 0, 1, 3, 4, 9, 10 (W2) and the Segments module's finding the report gate needs (MVPQ-04, X1) |
| 4. Open answers | MQ-15 (MVPQ-02b) | `assumptions-and-open-answer-coding` AOC4, then AOC5-AOC8 and `report-delivery#RD10` (W2-W3) |
| 5. Replacement | MQ-16 (MVPQ-10) | `run-qc-and-checkpoint#RQC5` and its ADR (W3) |
| 6. Client data | MQ-17 – MQ-19 (MVPQ-05) | `client-data-in-analysis` 0, 4, 5, 6 and ADR 0027's amendment (W3) |
| 7. Report checks | MQ-20, MQ-21 (MVPQ-09, D-18) | `report-delivery#RD0`, `#RD7`; the analysis prose rule |
| 8. Housekeeping | MQ-22 – MQ-25 (D-18) | Small rules the cross-check found split between web and server |
| Request | R-1 | The audit's evidence script (not a decision) |

Total: **25 decisions** (MQ-01 – MQ-25) and **one evidence request** (R-1).

---

## Tier 1. The method

### MQ-01. Which Sociomap method does the MVP ship? (new; give it an MVPQ id when answered)

**(1) The decision.** Is the MVP's client-facing Sociomap `aia-sociomap-3` (approved 2026-10-13),
your signed-off `aia-sociomap-5`, or `-3` for object maps with `-5` for the respondent and segment maps?

**(2) Why it matters.** The plans and the register say the MVP uses `aia-sociomap-3`
(`mvp-master-plan.md:126`; `domain/sociomap_register.py:52-69`, the only entry, CLIENT_FACING,
decided by the product owner on 2026-10-13). Your `aia-sociomap-5` is now in `develop`
(`domain/sociomap/specification.py:1553-1630`, #504) and computes a different map at every stage,
plus the respondent map (MVP-4) and taste segments (MVP-17) that `-3` does not have. It is
`INTERNAL_ONLY` (absent from the register), not pinned by any new run
(`domain/research_sociomap.py:323-330` pins `-1` and `-3`), and a run reaches it today only through
a Metodika version, whose name is `aia-sociomap-5+e<n>` (`domain/methodology/pins.py:84-95`,
`domain/methodology/versions.py:71-75`), which no register entry for `aia-sociomap-5` would match
(`sociomap_register.py:72-86` matches the exact id). AC-09 promises object, respondent and segment
maps "each under the method pinned at run start with the Sociomap register's status"
(`docs/migration/mvp-acceptance.md:90`). Whatever ships is what every client map says.

**(3) Worked example.** A fictional study: 400 AI respondents rate 8 brands of mineral water on
1-10. Brands *Horská* and *Pramen* are rated by 36 respondents each, with weights half 0.5 and half
2.0.

- Under `-3`: the pair's Kish effective n is 45² / 76.5 = 26.5, below `n_min` 30
  (`specification.py:1516-1526`, Kish basis), so the pair is UNKNOWN, weight 0 in SMACOF, no link.
  The map shows 8 objects with a Stress-1 label and the envelope terrain at σ 0.25. No respondents,
  no segments.
- Under `-5`: relations are unweighted with `n_min` 10 on the respondent count
  (`specification.py:1559-1567`), so the pair is known (36 ≥ 10) and tested by Benjamini-Hochberg at
  q 0.05 with the noise rule. Objects are placed by soft-rank Spearman with Coulomb repulsion (8 ≤ 163
  objects). No Stress-1; the split-half check says whether the map is weakly determined. Up to 400
  respondent dots, PLACED or FADED by the chance test at p ≤ 0.10; taste segments if the mixture on
  slopes beats 20 shuffles.

The same data, two different link sets, two different pictures, and only one has respondents.

**(4) Options and what each changes.**

| | A. Keep `-3` | B. Register `-5` as the MVP method | C. `-3` object maps, `-5` respondent and segment maps |
|---|---|---|---|
| Register | Unchanged | A new entry for `aia-sociomap-5` at its spec fingerprint, decided by you; the `-3` entry stays for every run that pinned it | Two entries, and the register gains a map kind (today it is keyed by method id alone, `sociomap_register.py:36-49`) |
| What a run pins | Unchanged (`research_sociomap.py:323-330`) | `default_methods` pins `-5`; Metodika's `in_force` moves from `-3` (`methodology/sociomap.py:2014`); an edit starts from `-5`, not `-4` (`:2007-2013`) | Both pinned; each battery computed twice |
| `segment-maps-and-drilldown` 0, 1, 3 | 0 and 3 still need a clustering algorithm from you (MQ-13) | 3 becomes "show `-5`'s taste segments"; 0's clustering is answered by `-5`; 1 (defined segments) still needs MQ-10, MQ-11 | As B for segments |
| `segment-maps-and-drilldown` 9 (figures, chapters) | Respondent and segment figures from chunk 3 of formula-corrections and from a new clustering | Figures drawn from `-5`'s `respondents` and `segments` | As B, and a client snapshot carries two different object configurations per battery (see the note below) |
| `segment-maps-and-drilldown` 10 (segment evidence) | Defined segments only, unless clustering is added | Defined segments, and taste segments if you allow them as a segment definition for SEGMENT claims (MQ-13) | As B |
| `sociomap-formula-corrections` 3 (respondent placement, F10) | Must be built: ideal points against the `-3` map, and it waits on the F10 threshold (MQ-07) | Superseded for the MVP by `-5`'s vector-model placement with the chance test; MQ-07 asks only whether the misfit `-5` records is shown | As B |
| `sociomap-formula-corrections` 0b, 1d (Q5-Q7) | MQ-03 – MQ-05 confirm or replace AIA's provisional `-3` answers | Your `-5` already answers Q6 differently (MQ-03); the questions are asked of `-5` | Asked of both |
| Web drawing | Drawn today (chunk 5a; `apps/web/src/lib/object-map-view.ts:20` reads `-4`, `-3`, `-2`) | Not drawn: `-5` is read as an unnamed method; its relative heights drawn as absolute 0-1 terraces; no credibility banner, respondent map, segments, "Neumístěno" list or 26x exaggeration (`signed-off-sociomap-method.md`, Doc follow-up, web items). Your standing rule: the panel follows `ui_app.html`'s drawing | As B for respondent and segment views |
| Report chapters | Exist for `-3` object maps (`application/report_maps.py:112`, Stress-1 at `:215-220`; `infrastructure/report_docx/object_map_figure.py:110`) | `-5` has no Stress-1 (`report_maps.py:70`): the chapter prints the split-half share and the radius instead; respondent and segment chapters are `segment-maps-and-drilldown` 9 | Both |
| BB1 platform dependence | None: SMACOF is pure Python, bit-identical (`layout.py:150-153`) | Applies (MQ-02) | Applies to the respondent and segment maps |

**Note on C.** Under `-5`, respondents are placed and segments found **against `-5`'s own object
positions** (`respondents` on the object map's frame, slopes from the vector model). Pairing a `-3`
object map with `-5` respondent dots would put people on a map they were not placed on. C is
coherent only if the respondent and segment views show `-5`'s own object positions beside the `-3`
map, or if you sign off a new rule placing `-5` respondents on `-3` positions (a method neither
plan contains).

**(5) Recommendation.** The plans have none. `signed-off-sociomap-method.md` ("Not in this plan")
leaves "making `-5` the default" as a separate step with its own register approval; the master plan
assumes `-3`. For your judgment: A keeps what is drawn and approved and leaves AC-09's respondent and
segment maps to unbuilt work that waits on MQ-07 and MQ-13; B is one method end to end and answers
MQ-07 and MQ-13 by construction, at the cost of the web drawing and MQ-02; C costs the most and has
the consistency problem above.

**(6) Blocks / proceeds.** Blocks: the register entry, `segment-maps-and-drilldown` 0, 1, 3, 4, 9, 10's
method parts, `sociomap-formula-corrections` 3 and 4c's scope, the web's respondent and segment
views, `report-delivery#RD4`'s figure set, AC-09. Proceeds without it: `segment-maps-and-drilldown` 0a
(storing descriptors per respondent), 5 (filters, aggregates only), 6 (drill-down), the `-5` web
drawing as an internal view (researchers see `INTERNAL_ONLY` maps either way), `formula-corrections`
2d, I0-I4.

### MQ-02. Under `-5`, is the stored map the record, and is a different platform's map acceptable? (MVPQ-12, F16 neighbour)

**(1) The decision.** Since BB1 can give a different (equally good) map on another platform from 12
objects on, which map counts: the one stored at run time, never recomputed; or must AIA guarantee
one map across platforms?

**(2) Why it matters.** Your plan records it as open for you ("A platform-independent BB1 map", 
`signed-off-sociomap-method.md`, Not in this plan; `domain/sociomap/layout.py:155-162`). AIA
re-derives maps in several places: a retry under the same pins on another worker, the report's
`verified_map` re-derivation from the dataset and specification (`application/report_chapters.py`,
CLAUDE.md §2), Metodika's comparison on the API host, I5's "frozen replay", and a developer's macOS
machine. The register approves a specification, not a picture, so the approval is unaffected; what
is affected is whether a re-derived map can disagree with the stored one and whether that is a defect.

**(3) Worked example.** A battery of 14 objects computed on the develop worker (Linux x86_64, numba
0.68, `packages/aia_core/pyproject.toml:16-19`) puts *Horská* left of *Pramen*; recomputed on a
macOS laptop it puts *Horská* right of *Pramen*, rotated, with both maps fitting equally well. The
client report printed the first. A reviewer re-running the study locally sees the second.

**(4) Options.**
- (a) The stored map is the record: no client-facing path recomputes a `-5` map; every re-derivation
  compares statuses and decisions, not coordinates (what your parity tests already do). Changes the
  report's map verification to read the stored map for `-5`, and I5's replay to compare statistically.
- (b) One platform is canonical (the worker's image); any other platform's map is labelled
  non-canonical. Changes: the pinned image becomes part of the method's identity.
- (c) Make BB1 platform-independent (a method change, yours).

**(5) Recommendation.** None in the plans. Under MQ-01 A this question does not arise.

**(6) Blocks / proceeds.** Blocks the `-5` report verification and I5's replay test under MQ-01 B or C.
Proceeds: everything under MQ-01 A.

---

## Tier 2. The canonical Sociomap's meaning (MVPQ-12)

These use the decision sheets of `sociomap-formula-corrections.md` § 4a (lines 168-270) and the
request list A1-A6, B8-B11 (lines 755-801). They are not new formulas.

### MQ-03. The pair evidence policy, including weights (MVPQ-12 Q6; audit A2, B7, B9)

**(1) The decision.** What minimum support, which n (respondent count or Kish's effective n), which
reliability criterion (Fisher interval excluding 0, or Benjamini-Hochberg with the noise rule), and
whether a separate practical floor on |r| decides whether a relationship is drawn, and are the
relations survey-weighted?

**(2) Why it matters.** It decides which links appear, which pairs shape the layout and which pairs
enter the scores. `-3` and `-5` answer it differently today:

| | `-3` (the product owner's provisional answer, 2026-10-09) | `-5` (your method) |
|---|---|---|
| n basis | Kish effective n (`specification.py:1521`) | Respondent count (`:1562`) |
| `n_min` | 30 | 10 |
| Criterion | Fisher 95 % interval excludes 0 | Benjamini-Hochberg, q 0.05, plus the noise rule (100 permutations) |
| Practical floor | |r| ≥ 0.10, recorded beside the state | None |
| Weights in the relation | Weighted Pearson | Unweighted (height is weighted); "to revisit", your plan |

**(3) Worked example.** n = 1,000 equal weights, a pair with r = 0.08. Fisher: se = 1/√997 = 0.0317,
interval [0.018, 0.141], excludes 0, so RELIABLE under `-3`, yet below the 0.10 floor, so not drawn
as a strong link. Under `-5` the same pair passes or fails BH depending on the other 27 pairs' p-values,
and no floor applies. Separately, the 36-rater weighted pair of MQ-01 is UNKNOWN under `-3` (Kish 26.5)
and known under `-5` (36 ≥ 10).

**(4) Options.** (a) `-5`'s policy as signed off, everywhere the MVP draws; (b) `-3`'s two gates on
Kish; (c) your own rule, stating the n basis, the floor, the criterion, the floor on |r|, and whether
relations are weighted. Changes: `formula-corrections` 1d (built for `-3`), the preset of whichever
method MQ-01 ships, readiness's `pair_n_min` (`domain/research_design.py:828-907`), the side tables,
and the Metodika steps.

**(5) Recommendation.** The plans ask for one explicit state model (§ 4a, "The ask, as one evidence
policy") and propose none as final.

**(6) Blocks / proceeds.** Blocks `formula-corrections` 0b and the client approval of any new map
method. Proceeds: every policy is a declared parameter, so engineering does not move when you answer.

### MQ-04. What proximity claims (MVPQ-12 Q5; audit A1)

**(1)** Do close objects mean co-moving relative preferences, similar absolute ratings, or two concepts
shown apart (position = co-movement, height = level)?

**(2)** Every distance, link and score inherits it (F2 → F4 → F6 → F7 → F8/F9). `-3` uses per-person
min-max (F2); `-5` uses per-person mean-centring (`specification.py:1556-1558`); both are co-movement.

**(3)** 300 respondents rate *Horská* about 9 and *Pramen* about 3, but whoever rates *Horská* above
their own average also rates *Pramen* above theirs. Under (a)/(c) they sit together, *Horská*'s hill
far taller; under (b), with d = mean |x_i − x_j| / 9 ≈ 0.67, they sit far apart.

**(4)** (a) co-movement only; (b) a level-sensitive distance, a new declared method; (c) both, apart
(AIA's provisional reading). (b) would be a new preset and a new register entry; (a)/(c) change only
the legend.

**(5)** § 4a proposes (c), provisionally.

**(6)** Blocks the meaning sentence printed beside every map (`sociomap_register.py:63-67`'s reader
note) and the report's reading guide. Code does not move under (a) or (c).

### MQ-05. What terrain height claims (MVPQ-12 Q7; audit A3)

**(1)** Is the default height the mean rating, connectedness, alignment, or selectable with a default?

**(2)** The hills are the most visible encoding; "high" must mean one thing. `-3` and `-5` both use
the survey-weighted mean rating; `-5` shows it as relative heights min-max onto [0.15, 1]
(`specification.py:1621-1628`), so the tallest hill is always 1 whatever the ratings.

**(3)** 8 brands with means 6.1-6.9 on 1-10: under `-3` the hills differ by under 0.1 on the absolute
0-1 terraces and look flat; under `-5` the 6.1 brand stands at 0.15 and the 6.9 brand at 1.0, so a
0.8-point difference looks like the whole range.

**(4)** (a) mean rating, absolute; (a') mean rating, relative (`-5`); (b) connectedness; (c)
alignment; (d) selectable, default (a) or (a'). Under (a') the web and report must say "relative"
in the legend (today the web draws `-5`'s relative cells on absolute terraces, a known gap).

**(5)** § 4a proposes (d) with (a), provisionally; `-5` chose (a').

**(6)** Blocks the legend text and the report's reading guide. Proceeds: height metric is a spec field.

### MQ-06. Kernel widths on the fixed ruler (MVPQ-12; audit A5)

**(1)** What is the object-terrain kernel width, and the respondent-density kernel width, each defined
relative to the ruler?

**(2)** They set how far one object's hill reaches toward another, and how much people's density is
smoothed. `-3` runs σ 0.25, `AIA_PROVISIONAL_R08_5PCT` (`sociomap-formula-corrections.md:1064-1074`);
`-5` declares σ 0.25 on a framed grid as `SIGNED_OFF_METHODOLOGY` and density σ 0.35
(`specification.py:1599-1601, 1621-1628`). AUDIT-F12 stays `PENDING_PARAMETER`.

**(3)** At σ 0.25, two objects at r = 0.8 (δ = √0.4 = 0.632) raise each other to exp(−3.2) = 4 % of a
hill; at r = 0.9 (δ = 0.447) to exp(−1.6) = 20 %, so a strongly related pair shares a ridge.

**(4)** (a) confirm `-5`'s values as the canonical widths, and the provisional `-3` value as equal;
(b) other values with their definition.

**(5)** None final; the plan calibrated `-3` itself, labelled PROVISIONAL.

**(6)** Blocks closing F12 and the respondent density's client use. Proceeds: values are declared.

### MQ-07. Respondent fit: the F10 misfit threshold, or `-5`'s chance test (MVPQ-12; audit A4)

**(1)** How is a poorly represented respondent identified: a calibrated threshold on misfit e_k (F10),
or `-5`'s chance test (PLACED at p ≤ 0.10, FADED otherwise, `specification.py:1599-1601`); and is the
misfit `-5` records (1 − R²) shown?

**(2)** It decides which dots are drawn solid, faint or not at all, and which people a segment profile
rests on.

**(3)** A respondent rates 8 objects; the vector model fits R² = 0.35 (misfit 0.65) with p = 0.18. Under
`-5`: FADED (alpha 0.3). Under F10 with a misfit threshold of 0.5: flagged poorly represented; at 0.7:
fine.

**(4)** (a) `-5`'s chance test is the rule (formula-corrections 3's threshold moot for the MVP);
(b) F10 with your threshold and the evidence behind it (A4 asks for both); (c) both, the misfit shown
as a diagnostic.

**(5)** None.

**(6)** Under MQ-01 A it blocks `formula-corrections` 3's classification (a diagnostic-only result must
say it has none). Under B it blocks only whether misfit is displayed.

### MQ-08. Context (SECONDARY) objects: the boundary and how they join `-5` (audit B11; your open question of 2026-10-19)

**(1)** May a context object affect anything in the PRIMARY map (layout, respondent placement,
alignment, quality), and under `-5` how does it join the map (placed afterwards with the PRIMARY map
fixed, NPC's F17 rule, or left off)?

**(2)** `-5` maps PRIMARY objects only, so a declared context object (a competitor shown for reference)
disappears from the client's map today.

**(3)** A study declares 6 own brands and 2 competitor brands as context; the `-5` map shows 6.

**(4)** (a) left off (today); (b) placed afterwards, PRIMARY fixed (F17); (c) another rule.

**(5)** None.

**(6)** Blocks the context-object display under `-5`. Proceeds: PRIMARY maps.

### MQ-09. The research module's preference map, F16: build or retire for the MVP (MVPQ-12 F16; audit A6, B10)

**(1)** Is F16 (row-conditional unfolding, R `smacof` reference) built for the MVP, with which recovery
properties and which tolerance against R, or retired with its reason recorded?

**(2)** `formula-corrections` 4c is gated on it (`:1636-1645`); AC-09 does not wait on it. The product
owner decided on 2026-10-09 that F16 stays pure Python with no R on develop, provisionally.

**(3)** On 300 planted ideal points, a pure-Python fit recovers object order with Kendall τ 0.94 against
R's 0.95: is that "the same method" (B10's three layers: fixture parity, property tests, recovery)?

**(4)** (a) retire for the MVP (`-5`'s respondent map covers people on the map); (b) build, with your
A6 properties and B10 tolerance; (c) build with R on the host.

**(5)** None.

**(6)** Blocks 4c only.

---

## Tier 3. Segments (MVPQ-03, methodology part)

The product owner decided (2026-10-20) that defined segments start from the sampler's stored descriptors
and the drill-down shows stored attributes and answers only. What a stored respondent holds today: id,
donor, weight and answers (`domain/fieldwork.py:172-181 @ 085abe0`, per `segment-maps-and-drilldown` 0a);
the sampler's quota cells are sex × age group × region, plus education from n 700 (CLAUDE.md §2,
`population/sampling.py`).

### MQ-10. Which descriptor combinations define a segment (MVPQ-03)

**(1)** Which stored descriptors, alone and in which combinations, may define a segment?

**(2)** Every combination multiplies cells and thins them.

**(3)** n = 400: sex alone gives 2 cells of about 200; sex × 5 age groups gives 10 of about 40; sex ×
age × 14 regions gives 140 of about 3.

**(4)** (a) single descriptors only; (b) pairs at most; (c) any combination whose every cell meets
MQ-11's floor; (d) your list. Changes `segment-maps-and-drilldown` 1's pure rule and 0a's stored set.

**(5)** The plans: the quota-cell fields as the proposed default (0a), no combinations chosen.

**(6)** Blocks segment 1 and 10. Proceeds: 0a stores the descriptors.

### MQ-11. The minimum support and suppression for a segment, its map and its claims (MVPQ-03)

**(1)** What floor (on which n) must a segment meet to be mapped, and to have SEGMENT-level claims
admitted, and what is said when it does not?

**(2)** X1 (product owner, 2026-10-20) requires segment evidence so the Segments module can state a
finding; `ClaimLevel.SEGMENT` has no producer (`domain/evidence/claims.py:81`) and the module is told to
say segmentation cannot be assessed without it (`domain/analysis/modules.py:89-96`). Today's only
number is the Sociomap's `n_min` 30 WARN (`research_design` `sociomap_support`); `-5` looks for taste
segments from 30 respondents with a slope and keeps none under 5 % (`specification.py:1606-1609`).

**(3)** Segment "ženy 18-29" has 41 respondents with Kish n 33: above 30, mapped and claimed? Segment
"muži 65+" has 22 (Kish 17): suppressed and named, or mapped with a warning?

**(4)** (a) 30 on Kish n for both map and claims; (b) separate floors (map vs claims); (c) your rule;
in every case below the floor the segment is suppressed and said so, never ordered (the plan's
invariant).

**(5)** "Do not invent support thresholds" (MVPQ-03 recommendation).

**(6)** Blocks segment 1, 10 and the Segments module's finding, hence the report gate (MVPQ-04) for any
study with segments.

### MQ-12. How an accepted own dimension takes part (MVPQ-03)

**(1)** May a client's materialized dimension (a modelled variable, never measured,
`population/materialized.py`) define a segment, filter a map, or neither?

**(2)** It is the only client-specific variable a respondent can carry; its values are modelled from
the panel, so a segment built on it is a model's partition.

**(3)** The client materializes "loajalita ke značce" (target 34 % loyal); 400 respondents split
136 / 264: may "loajální" be a segment with its own map?

**(4)** (a) no; (b) as a filter only, labelled modelled; (c) as a segment, labelled modelled, under
MQ-11's floor.

**(5)** The plans: "make an own-dimension consumer explicit" (G28), no rule.

**(6)** Blocks the own-dimension consumer in segment 0a/1. Proceeds: descriptor segments.

### MQ-13. The clustering method, its parameters, and whether taste segments are a segment definition (MVPQ-03, MVP-17)

**(1)** Is `-5`'s taste-segment mixture (on vector-model slopes, BIC × 0.5, 20-shuffle guard, step-down,
consensus over 5 maps, `specification.py:1602-1620`) the MVP's clustering option, and may its segments
carry SEGMENT-level claims like a defined segment?

**(2)** `segment-maps-and-drilldown` 0 and 3 wait for "the algorithm and its parameters"; your method
already has one.

**(3)** 400 respondents, 8 objects: the mixture finds 3 segments (41 %, 35 %, 24 %), BORDERLINE between
2 and 3. Are the 24 % "found by clustering" claims admissible, or only a picture?

**(4)** (a) `-5`'s taste segments, picture only; (b) taste segments, claims too (under MQ-11); (c)
another algorithm under MQ-01 A.

**(5)** None; the master plan says reconcile with #504 first.

**(6)** Blocks segment 0, 3 and its labelling.

### MQ-14. The register's granularity for respondent and segment maps, and what a client snapshot shows (MVPQ-03; segment 4, 9)

**(1)** Does a segment map need one register entry per method, or one per segment definition; and does
a client snapshot print respondent points, or only the aggregate terrain?

**(2)** Without an entry AC-13's approved snapshots cannot include respondent or segment maps
(`segment-maps-and-drilldown` 4); points are individual modelled people.

**(3)** "Ženy 18-29" and "Praha" maps under `-5`: two entries, or one for `-5` segment maps; and does
the client see 41 dots or one density?

**(4)** (a) one per method and kind; (b) one per definition; points (i) shown or (ii) terrain only.

**(5)** None (both listed as "Open" in the plan).

**(6)** Blocks segment 4, 9 and `report-delivery#RD4`'s client figures.

---

## Tier 4. Open answers (MVPQ-02b)

### MQ-15. The open-answer coding method (MVPQ-02b; AOC4)

**(1)** How is an open answer coded and counted: the codebook and who writes it, labels and multi-label
semantics, the denominator and missing answers, review and acceptance, agreement measures, small-code
suppression, and what a model may do?

**(2)** Coding is first-release scope (MVPQ-02); without a method no count can be produced (AOC4 blocks
AOC5-AOC8). If a model may propose codes, a twelfth worker is added (AOC7); if not, AOC7 closes.

**(3)** 300 respondents, "Proč byste značku nedoporučili?": 212 answered, 88 blank; a 6-code codebook;
212 answers carry 260 codes. "Cena" on 74 answers is 24.7 % of 300, 34.9 % of 212, or 28.5 % of 260
codes. "Obal" has 4 answers: shown or suppressed? A model proposes codes for all 212 and a researcher
changes 19: is agreement reported (e.g. Cohen's κ), and which assignment counts?

**(4)** For each part: (a) denominators: respondents asked / answered / codes; (b) multi-label: yes, each
code counted once per answer; (c) small codes: suppress below a floor on n; (d) model: none / proposes
for human review / never final; (e) review: every answer, or a sample with agreement ≥ a threshold.

**(5)** The plan's constraints, not a method: counts only through `admit_numeric_claims`, a model never
final, modelled answers internal until a validation lifts them.

**(6)** Blocks AOC5 runtime, AOC6-AOC8, RD10. Proceeds: storage contract, refusal tests, assumptions.

---

## Tier 5. Replacement (MVPQ-10)

### MQ-16. What a replaced respondent does to weights, effective n and support (MVPQ-10; RQC5)

**(1)** When straight-liners are replaced by a new linked run, how are replacements drawn, how are
weights recalibrated, what effective n is reported, and when is replacement refused?

**(2)** Replacement is settled (F18); without a rule the new run's numbers cannot be compared honestly
with the original.

**(3)** Run 1: n 300 raked to sex × age × region, Kish n 252; 12 straight-liners (8 from "muži 18-29").
Replacement redraws 12. Options give: (a) redraw from the same quota cells, re-rake all 300; (b) keep
the 288 weights, give each replacement the weight of the one it replaces; (c) if "muži 18-29" has no
unused donors left, refuse.

**(4)** (a), (b), or your rule, plus the refusal conditions (cell exhausted; replacement share above
x %) and what the report states (both runs, the rule pinned on the new run).

**(5)** "Preserve the original run and paid answers; do not silently renormalize" (MVPQ-10).

**(6)** Blocks RQC5's executable behaviour and ADR. Proceeds: lineage, storage, refusals.

---

## Tier 6. Client data (MVPQ-05, methodology part)

### MQ-17. The benchmark interval when supports differ (MVPQ-05)

**(1)** Which interval or comparison is valid between a client number and a modelled number with very
different supports?

**(2)** The client report shows client data "beside" modelled results or "as a benchmark", never mixed
(`client-data-in-analysis` 5).

**(3)** Modelled: 31 % prefer *Horská*, Kish n 180, 95 % interval [24.2, 37.8]. Client survey: 27 %,
n 1,850, [25.0, 29.0]. Difference 4 pp, interval about [−3.1, 11.1]: "no confirmed difference"?

**(4)** (a) both intervals side by side, no difference claimed; (b) a difference interval
(independent samples); (c) no comparison claim at all.

**(5)** "No guessed statistical rule."

**(6)** Blocks client-data 4 (benchmark gaps) and 5.

### MQ-18. May a client survey ever ground AI respondents? (MVPQ-05)

**(1)** May a client's own survey answers condition the personas (as the panel does), or must they stay a
separate comparison source?

**(2)** Grounding would make modelled numbers partly client-reported; ADR 0027 decision 7 keeps them
apart.

**(3)** The client's 1,850-customer survey says 27 % prefer *Horská*; grounding would pull the modelled
31 % toward it.

**(4)** (a) never; (b) only as a separate, labelled method with its own validation.

**(5)** "No grounding permission" without your explicit rule.

**(6)** Blocks nothing in the MVP under (a); (b) would be a new plan.

### MQ-19. The support, metric and interval of a client number (client-data 0, amended G51)

**(1)** What support does a client count or aggregate carry (row count as n, or "not a sample"), which
metrics and units it may take beyond mean, pct and n, and when is an interval required?

**(2)** A client number has no respondent n, so `assess_support` suppresses it; AC-10's dataset (visits
by branch and month) would be refused whatever the policy (`client-data-in-analysis.md:129`). The plan
does not name an owner; it is statistical, so it is asked here.

**(3)** "Brno, březen: 4,812 návštěv" from the client's records: a census, no sampling error; an
interval or none?

**(4)** (a) exact records "not a sample", no interval; (b) row count as n; plus the new kinds
(count, amount, rate).

**(5)** "Never an invented effective n."

**(6)** Blocks client-data 0, 5 and AC-10.

---

## Tier 7. Report checks (MVPQ-09, D-18)

### MQ-20. Any scientific check beyond admitted support before a client deliverable (MVPQ-09)

**(1)** Beyond the product owner's three checks (no "Interní dokument" source, no drill-down content, no
number without an admitted claim), must a client deliverable pass any scientific check?

**(2)** `report-delivery#RD0` leaves this to you; RD7 already blocks an unsupported claim.

**(3)** The report says "Horská je hodnocena lépe než Pramen" with intervals [6.8, 7.4] and [6.6, 7.2];
every number is admitted. Refuse the sentence?

**(4)** (a) none; (b) the interval-order rule (MQ-21); (c) multiple-comparison control on segment
differences; (d) a modelled label on every modelled number (already the evidence ledger's).

**(5)** "Deterministic where possible."

**(6)** Blocks RD0's final policy, not the renderer.

### MQ-21. Must analysis prose follow "an order only where 95 % intervals part"? (D-18, F061)

**(1)** Should the rule the web applies to sentences (`apps/web/src/lib/result-reading.ts:5-9`) also bind
analysis prose and the report, with intervals given to the model?

**(2)** Today the analysis model is never given intervals, so its prose can order what the Data view
says it cannot.

**(3)** As MQ-20's example: Data says "cannot be confirmed", the analysis says "lépe".

**(4)** (a) yes, server-side and in the prompt; (b) web only.

**(5)** `productization-coherence` D-18: decide with you.

**(6)** Blocks the analysis harness change.

---

## Tier 8. Housekeeping (D-18, `productization-coherence.md:615`)

### MQ-22. The tracked-set size rule (F058)

**(1)** Is a tracked set 4-15 objects (18.6.6, which the web enforces and silently truncates to 15) or
3-40 hard with 4-15 recommended (the server, `domain/research_design.py:84-86`)?
**(3)** A 22-brand set is cut to 15 in the browser and accepted at 22 by the server. **(4)** (a) 4-15;
(b) 3-40 hard, 4-15 a warning. **(5)** None. **(6)** Blocks the web fix only. (Under `-5`, BB1 runs to 163
objects and Interval MDS above.)

### MQ-23. The connectedness (K100) interval (F084)

**(1)** Is K100's bootstrap interval part of the method (pinned on the run, on develop), or an optional
analytical layer? **(3)** Today it is behind a switch the develop worker cannot reach and its F9 values are
editable in Metodika. **(4)** (a) part of the method; (b) optional, off. **(6)** Blocks F9's display.

### MQ-24. May a superseded preset be a base for a new version? (F135)

**(1)** Should `aia-sociomap-2` still be offered as a Metodika base (`methodology/sociomap.py:2007-2013`)?
**(4)** (a) no, only the method in force and `-5`; (b) yes. **(6)** Blocks nothing; a one-line fix.

### MQ-25. Modules that never receive their inputs (F062)

**(1)** The Hypotheses, Segments and Audience modules are paid calls that never get their inputs but must
complete for the report (MVPQ-04): which inputs must each receive, or may one be declared not applicable
for a study? **(3)** A study with no hypotheses still pays for, and is blocked by, the Hypotheses module.
**(4)** (a) define inputs (segments: MQ-11's evidence); (b) "not applicable" as a declared state that is
not a missing finding. **(6)** Blocks those modules' contracts; MVPQ-04's rule stands.

---

## R-1. Evidence request (not a decision): the audit's check script (C12-C15, `sociomap-formula-corrections` 0a)

`NPC/analysis/code_formula_checks.py`, its printed `[C*]`/`[P*]` output and the simulated inputs (or seeds).
It completes the audit's fixtures and Metodika's draft check (`methodology-tab` S4d). Two readings to confirm
with it, if convenient: B8 (an object's score divided by its known PRIMARY pairs, with the count shown) and F5
(the transform from a declared 1-10 strength matrix, `SPECIFICATION_REQUIRED`, refused today).

## Not asked, and why

- **SOMECS / H-Model questions** (`sociomapping-engine.md`, M-questions): post-MVP by the master plan
  (`mvp-master-plan.md:126`).
- **Client-facing analysis prose (ANL-1):** waits on the holdout validation; the MVP client report carries
  no analysis prose (`report-delivery.md:28`).
- **Groups without direction on the respondent map:** deferred in your methodology.
- **Evaluation tasks and thresholds (MVPQ-06):** the product owner's.
