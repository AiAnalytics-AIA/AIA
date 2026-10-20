# MVP methodology packet: what must be true for `aia-sociomap-5` to ship, and every other open decision that is the methodology owner's

2026-10-20. For **A. Bahbouh, methodology owner** (his AIA Sociomapa methodology is canonical, the
product owner's words), sent by the coordinator and the product owner. Code claims are anchored
`file:line @ 854c209` (`develop` at the time of writing) unless another SHA is given.

**How to answer.** Quote the packet id (`MQ-01` … `MQ-24`) and the option letter, or write your
own rule. Answers are recorded in `mvp-cohesion.md` under the MVPQ id in each heading, and a docs PR
then carries them into the affected plans. A recommendation below is the plans' own proposal, never
an approval; where the plans have none, the packet says so.

**Already settled, not asked.** MVPQ-13 below; the product owner's parts of MVPQ-03, 05 and 09
(2026-10-20, `mvp-owner-decisions.md`); the scope of open-answer coding and of respondent
replacement (MVPQ-02, F18); segments both defined and clustered (MVP-17); object, respondent and
segment maps in the MVP (MVP-16, AC-09); your own 2026-10-19 decisions in
`signed-off-sociomap-method.md` ("Decisions taken"); and every point `-5` decides (MQ-05's record).

**One canonical source.** Your `aia-sociomap-5` is canonical. The formula audit
(`sociomap-formula-corrections`, "NPC Sociomapa: faulty formulas in the code") was written for `-3`:
where `-5` decides a point, `-5`'s answer is the MVP's, and the audit's answers (§ 4 there) stand only
where `-5` is silent. Nothing in this packet asks you to re-confirm your own method.

| Tier | Ids | What the answers unblock |
|---|---|---|
| Recorded | MVPQ-13 | -- |
| 1. What must be true for `-5` to ship | MQ-01 – MQ-06 | The register entry and `require_client_facing`; which segments the MVP shows and their evidence; the stored map's status; what `-5` leaves open of the audit; runtime |
| 2. The `-5` map's remaining meaning (MVPQ-12) | MQ-07 – MQ-10 | Weighted relations, the relative-height legend, context objects, F16 |
| 3. Segments (MVPQ-03) | MQ-11 – MQ-13 | `segment-maps-and-drilldown` 1, 4, 9, 10 (W2) |
| 4. Open answers (MVPQ-02b) | MQ-14 | `assumptions-and-open-answer-coding` AOC4 → AOC5-AOC8, `report-delivery#RD10` |
| 5. Replacement (MVPQ-10) | MQ-15 | `run-qc-and-checkpoint#RQC5` and its ADR |
| 6. Client data (MVPQ-05) | MQ-16 – MQ-18 | `client-data-in-analysis` 0, 4, 5, 6; ADR 0027's amendment |
| 7. Report checks (MVPQ-09, D-18) | MQ-19, MQ-20 | `report-delivery#RD0`, `#RD7`; the analysis prose rule |
| 8. Housekeeping (D-18) | MQ-21 – MQ-24 | Small rules split between web and server |
| Request | R-1 | The audit's evidence script, for the earlier presets (not a decision) |
| Not his | E-1 – E-9 | Engineering gaps the `-5` decision creates |

Total for the methodology owner: **24 decisions (MQ-01 – MQ-24) and one evidence request (R-1)**.

---

## Recorded: MVPQ-13. The MVP ships `aia-sociomap-5` (DECIDED, the product owner, 2026-10-20)

**Decision.** The MVP's Sociomap is the methodology owner's signed-off `aia-sociomap-5`
(`domain/sociomap/specification.py:1553-1630`, #504), not `aia-sociomap-3`. Decided by Nigel Blount,
product owner, 2026-10-20, relayed by the coordinator. Not asked again. `-5` is canonical: where it
decides a point, its answer is the MVP's; the formula audit written for `-3` stands only where `-5` is
silent.

**What it replaces.** The plans and the register assumed `-3`: `mvp-master-plan.md:126` ("the MVP uses
`aia-sociomap-3`"), the register's only entry (`domain/sociomap_register.py:52-69`, CLIENT_FACING,
2026-10-13), the default pins (`domain/research_sociomap.py:323-330`, `-1` and `-3`) and Metodika's
method in force (`domain/methodology/sociomap.py:2014`). Runs that pinned `-3` keep it and its approval;
a pin is never rewritten.

**What the choice changes** (the analysis prepared before the decision, kept as its record):

| | `-3` (not chosen) | `-5` (chosen) |
|---|---|---|
| Register | Approved since 2026-10-13 | A new entry, the methodology owner's (MQ-01) |
| Pair evidence | Kish effective n, `n_min` 30, Fisher 95 %, floor |r| ≥ 0.10, weighted Pearson (`specification.py:1516-1526`) | Respondent count, `n_min` 10, Benjamini-Hochberg q 0.05 with the noise rule, no floor, unweighted (`:1559-1567`) |
| Layout | SMACOF, pure Python, bit-identical, Stress-1 | Soft-rank Spearman with Coulomb repulsion (BB1) to 163 objects, Interval MDS above; no Stress-1; split-half credibility and an uncertainty radius |
| Height | Mean rating on absolute 0-1 terraces | Survey-weighted mean rating as relative heights on [0.15, 1] over a framed grid |
| Respondent map (MVP-4) | None; `sociomap-formula-corrections` 3 would have to be built and waits on the F10 threshold | Built: vector-model placement, PLACED / FADED by the chance test at p ≤ 0.10, density σ 0.35 |
| Clustered segments (MVP-17) | None; `segment-maps-and-drilldown` 0 and 3 wait on an algorithm | Built: taste segments, a mixture on slopes with the shuffle guard, step-down and consensus (`:1602-1620`) |
| Web drawing | Drawn (`apps/web/src/lib/object-map-view.ts:20`) | Not drawn yet (E-3) |
| Report chapters | Exist (`application/report_maps.py:112, 215-220`) | Need the credibility in place of Stress-1 and new figures (E-4) |
| Platform | Deterministic everywhere | BB1 maps can differ between platforms from 12 objects on (MQ-04) |

Worked example, kept: 400 AI respondents rate 8 mineral-water brands on 1-10; *Horská* and *Pramen*
are rated by 36 respondents, half weighted 0.5 and half 2.0. Under `-3` the pair's Kish n is
45² / 76.5 = 26.5 < 30, so UNKNOWN and no link. Under `-5` the pair is known (36 ≥ 10) and tested
by Benjamini-Hochberg among the 28 pairs; the map also carries up to 400 respondent dots and,
if they beat the shuffle guard, taste segments.

**Why the hybrid (`-3` object maps, `-5` respondent and segment maps) was rejected.** Under `-5`,
respondents are placed and segments found against **`-5`'s own object positions** (the respondent map
sits on the object map's frame, the slopes come from the vector model against those positions;
`signed-off-sociomap-method.md`, Doc follow-up). Drawing `-5` respondents on a `-3` map would put
people on a map they were not placed on; the alternative, a rule placing `-5` respondents on `-3`
positions, is a method neither plan contains. It would also have doubled the computation per battery
and needed a map kind in the register.

---

## Tier 1. What must be true for `-5` to ship

### MQ-01. The register entry: what exactly do you approve? (MVPQ-13; D6's precedent)

**(1) The decision.** Do you approve `aia-sociomap-5` at spec fingerprint
`8b0b486443024475a64c06dd0124a24a0a39d3b6bf3937813715cd98032969e0` for client-facing use, and does the
approval cover the object map only, or also the respondent map and the taste segments, with which
reader note?

**(2) Why it matters.** A map reaches a client only if the register approves its exact method id
and spec fingerprint (`sociomap_register.py:72-94`); `require_client_facing` refuses anything else.
Today `-5` is absent, so `INTERNAL_ONLY`. The precedent is D6: `-3` approved on 2026-10-13 at
`e16dc0d0…`, with the reader note printed beside every map (`:52-69`). The fingerprint above was
computed for this packet with `SociomapMethod.of(AIA_SOCIOMAP_V5).spec_fingerprint` on this commit;
the same call returns `-3`'s registered `e16dc0d0…` exactly. An edited version
(`aia-sociomap-5+e1`) is a different method and needs its own entry (`:8-11`).

**(3) Worked example.** A client report on the mineral-water study carries one object map, one
respondent map and three taste segments for the battery "Značky vody". With an entry for the object
map only, the report prints the object map and refuses the other two by name; with an entry
covering all three, all print, each with the reader note, e.g. "Mapa je počítána metodikou AIA
aia-sociomap-5, kterou metodik schválil … Mapa zobrazuje vztahy mezi hodnocenými objekty, nikoli
jejich příčinu."

**(4) Options.** (a) One entry for `-5`, covering every map it computes; (b) the object map now,
the respondent map and segments after the web and report draw them (E-3, E-4); (c) per map kind
(needs a kind field in the register: `MethodApproval` has none today, `:36-49`). Also: the reader
note's text, in Czech.

**(5) Recommendation.** None in the plans. `segment-maps-and-drilldown` 4 says new methods stay
`INTERNAL_ONLY` until you approve them by an entry.

**(6) Blocks / proceeds.** Blocks every client-facing `-5` map, AC-09's client snapshots and AC-13.
Proceeds: everything internal; researchers see `INTERNAL_ONLY` maps.

### MQ-02. Which segments does the MVP show: the sampler's descriptors, `-5`'s taste segments, or both? (MVPQ-03, MVP-17)

**(1) The decision.** The product owner said segments "start from the sampler's stored descriptors";
`-5` finds taste segments by clustering. Which does the MVP show, and if both, which is the default and
how are the two told apart?

**(2) Why it matters.** They are different things. A defined segment is a cell of stored descriptors
(sex, age group, region, education from n 700; CLAUDE.md §2 `population/sampling.py`), and partitions
everyone. A taste segment is found from how people rate the objects, needs at least 30 respondents with
a slope (`specification.py:1606`), may be NONE or BORDERLINE, and colours only clearly placed members at
membership ≥ 0.8 (`:1611`). MVP-17 already says both, defined by default and clustered as an option; the
question is whether `-5`'s mixture *is* that clustering option, and what each may claim.

**(3) Worked example.** 400 respondents. Defined: "ženy 18-29" (41), "muži 65+" (22) and so on. Taste:
the mixture finds 3 segments (41 %, 35 %, 24 %) and colours 230 respondents; 170 stay grey. A client
asks "who are the 24 %?": the profile names the objects they rate above the rest, not their age or sex.

**(4) Options.** (a) Both: defined by default, taste segments as the clustering option, each labelled
("podle znaků vzorku" / "nalezeno shlukováním" — wording to confirm); (b) taste segments only, defined
segments as map filters; (c) defined only, taste segments internal. Changes
`segment-maps-and-drilldown` 0 (answered by `-5` under (a) or (b)), 1, 3 (becomes "show `-5`'s
segments"), 9 and 10.

**(5) Recommendation.** The plans have none beyond MVP-17 (both).

**(6) Blocks / proceeds.** Blocks segment 0, 1, 3, 9 and 10's definition. Proceeds: segment 0a
(storing descriptors per respondent), 5 (filters), 6 (drill-down).

### MQ-03. Segment evidence: the support and suppression rule (X1, `segment-maps-and-drilldown#10`; MVPQ-03)

**(1) The decision.** What floor, on which n, must a segment (defined or taste) meet to have its map
drawn and its numbers admitted as SEGMENT-level claims, and what is said below it?

**(2) Why it matters.** X1 (product owner, 2026-10-20) requires segment evidence so the Segments module
can state a finding, and MVPQ-04 blocks the report while any module has none. `ClaimLevel.SEGMENT` has
no producer (`domain/evidence/claims.py:81`), and the module is told to say segmentation cannot be
assessed without it (`domain/analysis/modules.py:89-96`). Taste segments add a twist: membership is
probabilistic, so a segment's n can be the members coloured, the membership-weighted count, or
everyone assigned by label.

**(3) Worked example.** "ženy 18-29": 41 respondents, Kish n 33. Taste segment 3: 96 respondents by
label, 61 coloured (membership ≥ 0.8), membership-weighted n 74.3. "Muži 65+": 22 (Kish 17). Which are
mapped, which have claims admitted, which are suppressed and named?

**(4) Options.** (a) 30 on Kish n for both map and claims, taste segments counted by coloured members;
(b) separate floors for maps and claims; (c) your rule. In every case a segment below the floor is
suppressed and said so, never ordered (the plan's invariant); `RELIGION` stays refused client-facing.

**(5) Recommendation.** "Do not invent support thresholds" (MVPQ-03's recommendation).

**(6) Blocks / proceeds.** Blocks segment 10, the Segments module's finding and so the report gate
for any study with segments. Proceeds: the admission plumbing with a declared floor.

### MQ-04. BB1's platform dependence: is the map computed in the production worker image the record? (MVPQ-12)

**(1) The decision.** Given `-5` as signed off, is the map the run computed and stored in the production
worker image the record, and how is a map of the same data computed on another platform treated?

**(2) Why it matters.** Your plan leaves it open: from 12 objects on, macOS and Linux can give
different BB1 maps under the same library versions (`signed-off-sociomap-method.md`, Not in this plan;
`domain/sociomap/layout.py:155-162`; pins `packages/aia_core/pyproject.toml:16-19`). The register
approves a specification, not a picture, so MQ-01 is unaffected; what moves is whether AIA may
re-derive a map (a retry on another worker, the report's re-derivation of the run's map, Metodika's
comparison on the API host, `sociomap-formula-corrections` I5's "frozen replay", a developer's laptop)
and call a difference a defect.

**(3) Worked example.** 14 brands computed on the develop worker put *Horská* left of *Pramen*;
recomputed on a macOS laptop, *Horská* sits right of *Pramen*, the map rotated, both fitting equally
well. The client report printed the first; a reviewer re-running locally sees the second.

**(4) Options.** (a) The stored map is the record; every re-derivation compares statuses and decisions,
not coordinates (what your parity tests do); (b) the production worker image is the reference
platform, and a map computed elsewhere is labelled as such and never shown to a client; (c) your rule.
If you want BB1 itself changed, say so; the packet does not propose it.

**(5) Recommendation.** None in the plans.

**(6) Blocks / proceeds.** Blocks E-7 (how the report verifies a `-5` map) and I5's replay test.
Proceeds: everything else.

### MQ-05. What `-5` leaves open of the audit: the F8/F9 scores and connectedness, and the misfit (MVPQ-12)

**Recorded: settled by `-5` (canonical), not asked.** The formula audit's open questions and its
provisional 2026-10-09 answers (the product owner's, for `-3`, `sociomap-formula-corrections.md:1008-1020`)
are superseded where `-5` decides:

| Audit item | `-5`'s answer, the MVP's | Superseded |
|---|---|---|
| Q5, proximity (A1) | Co-movement: each person's ratings mean-centred, then the baseline-corrected relation; level shown as height (`specification.py:1556-1567`) | The 2026-10-09 provisional (c), the same meaning, and the per-person min-max (F2) it rested on |
| Q6, pair evidence (A2) | `n_min` 10 on the respondent count, Benjamini-Hochberg q 0.05 with the noise rule (100 permutations), no practical floor (`:1559-1567`) | Kish n, `n_min` 30, Fisher 95 %, the 0.10 floor (`-3`, `:1516-1526`); weighting stays your own "to revisit", MQ-07 |
| Q7, height (A3) | The survey-weighted mean rating as relative heights on [0.15, 1] (`:1621-1628`) | Mean rating on absolute terraces |
| A5, kernel widths | Object σ 0.25 on the framed grid (`SIGNED_OFF_METHODOLOGY`), respondent density σ 0.35 (`:1599-1601, 1621-1628`) | `-3`'s provisional σ 0.25 (`AIA_PROVISIONAL_R08_5PCT`); F12's `PENDING_PARAMETER` |
| A4 and chunk 3, respondent placement | The vector model, PLACED / FADED by the chance test at p ≤ 0.10 (`:1599-1601`) | F10's ideal points and its misfit threshold; `sociomap-formula-corrections` 3 for the MVP |

Not superseded by `-5`, and not asked here: F16 (MQ-10), the SECONDARY boundary (MQ-09), the input
contracts I0-I5 (engineering, method-independent).

**(1) The decision.** Two points `-5` leaves open: (i) do the F8/F9 object scores (alignment,
connectedness, B8's denominator) and K100 apply to a `-5` map at all; (ii) is the misfit 1 − R² that `-5`
records for each respondent shown anywhere?

**(2) Why it matters.** `-5`'s spec is a copy of `-4` with new values (`specification.py:1553`), so it
still carries `-4`'s `scores` and `connectedness` sections; nothing in your plan says whether they are
part of your method or inherited by construction. If they are not, they must not print beside a `-5`
map. The misfit is stored on every placed respondent but nothing reads it.

**(3) Worked example.** A `-5` map of 8 brands: is "Horská: konektivita 62 (54-70)" printed beside it,
computed by the audit's F9 over `-5`'s relations? A respondent with R² 0.35 is FADED by the chance test;
is "nesoulad 0,65" shown in the drill-down?

**(4) Options.** (i) (a) not part of `-5`: not computed or shown for a `-5` map; (b) part of `-5`, with
B8's denominator (known PRIMARY pairs, the count shown). (ii) (a) not shown; (b) shown in the internal
drill-down only; (c) shown on the respondent map.

**(5) Recommendation.** None.

**(6) Blocks / proceeds.** (i) blocks MQ-22 and what the report prints beside a `-5` map; (ii) blocks
only the display. Closing `sociomap-formula-corrections` 0b and 3 for the MVP needs no further answer.

### MQ-06. Runtime: is 70-90 s per set at 20,000 respondents acceptable, and can the shuffle guard be bounded?

**(1) The decision.** Is a `-5` map's computing time at large n acceptable for the MVP, and may the
shuffle guard (and the consensus maps) be bounded, e.g. by fewer shuffles or a cap on the respondents the
mixture is fitted on?

**(2) Why it matters.** The figure is yours, from #504's description: "a set with 1,000 respondents
takes 2–18 s; with 20,000 respondents and real segments about 70–90 s, almost all of it the
methodology's shuffle guard on 5 maps". It was measured on your machine (macOS, where #504's other
local checks ran), **not in this repository** (no commit, plan or test records it) and not in the
develop worker's image, so E-9 asks for it to be measured there. The cost drivers are declared spec values: up to 20 shuffles, each a full
mixture fit (`specification.py:1605`; fitted 4 at a time, stopping after the first batch where a shuffle
matches the real gain, `signed_off_segments.py:15-18, 106-109`), and the decision taken on 5 maps, the
shown one and 4 jittered ones each laid out again (`:1615-1616`). So the worst case is a set *with* real
segments, where no shuffle stops the guard early. `shuffles` 0 switches the guard off (`:732`); a lower value weakens it.

**(3) Worked example.** A study of 20,000 respondents with 4 batteries: at 80 s each, 5 min 20 s of
worker time per run, on top of fieldwork; a retry that recomputes pays it again.

**(4) Options.** (a) Acceptable as signed off; (b) bound the guard (e.g. 8 shuffles) and record the bound
on every map; (c) fit the mixture on a seeded subsample above some n, recorded; (d) your rule. Any
change is a new spec value, so a new fingerprint and register entry (MQ-01).

**(5) Recommendation.** None.

**(6) Blocks / proceeds.** Blocks nothing until measured (E-9); a bound changes the fingerprint MQ-01
approves, so it is best answered before MQ-01.

---

## Tier 2. The `-5` map's remaining meaning (MVPQ-12)

### MQ-07. Should `-5`'s relations be survey-weighted? (MVPQ-12 Q6; audit B7, B9; your "to revisit")

**(1)** `-5` computes the relations unweighted and the height weighted (your 2026-10-19 decision,
"Survey weights for the relations: … to revisit"). Does the MVP keep that?

**(2)** Panel runs are raked to quotas, so weights differ; an unweighted relation describes the sample,
a weighted one the population.

**(3)** 400 respondents, 60 young men weighted 2.1 each: their co-movements count once each unweighted,
2.1 times weighted; *Horská*–*Pramen* could read, say, r = 0.21 unweighted and 0.29 weighted (illustrative numbers).

**(4)** (a) Unweighted, labelled "vzorek" in the method note; (b) weighted, with an n basis for the
test (Kish). (b) is a new spec value and fingerprint.

**(5)** None. **(6)** Blocks the method note; best answered before MQ-01.

### MQ-08. The relative-height legend (MVPQ-12 Q7)

**(1)** Since `-5`'s heights are relative (the lowest object at 0.15, the highest at 1), what does the
legend say, and is the absolute mean rating shown beside it?

**(2)** A relative hill makes a 0.8-point difference look like the whole range.

**(3)** Means 6.1-6.9 on 1-10: `-5` draws 0.15 for 6.1 and 1.0 for 6.9, so a 0.8-point difference
spans the whole height range.

**(4)** (a) "Relativní výška: průměrné hodnocení, nejnižší a nejvyšší objekt sady" plus each object's
mean on hover and in the report table; (b) your wording.

**(5)** None. **(6)** Blocks the web's and report's legend (E-3, E-4).

### MQ-09. Context (SECONDARY) objects under `-5` (audit B11; your open question of 2026-10-19)

**(1)** `-5` maps PRIMARY objects only. Do context objects join (placed afterwards with the PRIMARY map
fixed, NPC's F17 rule) or stay off, and may they ever affect the PRIMARY map?

**(2)** A competitor declared as context disappears from the client's map today.

**(3)** 6 own brands plus 2 competitors as context: the `-5` map shows 6.

**(4)** (a) Off for the MVP, said under the map; (b) placed afterwards, PRIMARY fixed; (c) another rule.

**(5)** None. **(6)** Blocks the context-object display only.

### MQ-10. F16, the audit's preference map: does the MVP need it beside `-5`'s respondent map? (MVPQ-12; audit A6, B10)

**(1)** `-5` has no preference map of the audit's F16 kind (row-conditional unfolding, R `smacof` as
reference); its respondent map places people. Does the MVP need F16 at all, or is
`sociomap-formula-corrections` 4c closed with that reason?

**(2)** `sociomap-formula-corrections` 4c waits on it (`:1636-1645`); AC-09 does not.

**(3)** On 300 planted ideal points, a Python fit recovering object order with Kendall τ 0.94 against
R's 0.95: the same method (B10's three layers)?

**(4)** (a) Closed for the MVP: `-5`'s respondent map is the canonical way people are placed; (b) a
separate research-module product you still want, with A6's recovery properties and B10's tolerance.

**(5)** None. **(6)** Blocks 4c only.

---

## Tier 3. Segments (MVPQ-03)

What a stored respondent holds today: id, donor, weight and answers (`domain/fieldwork.py:172-181 @
085abe0`, per `segment-maps-and-drilldown` 0a); the drill-down shows stored attributes and answers only
(product owner, 2026-10-20).

### MQ-11. Which descriptor combinations define a segment

**(1)** Which stored descriptors, alone and in which combinations, may define a segment?
**(2)** Every combination multiplies cells and thins them.
**(3)** n = 400: sex gives 2 cells of about 200; sex × 5 age groups, 10 of about 40; sex × age × 14
regions, 140 of about 3.
**(4)** (a) Single descriptors; (b) pairs at most; (c) any combination whose cells meet MQ-03's floor;
(d) your list.
**(5)** The quota-cell fields as the default (0a); no combinations chosen.
**(6)** Blocks segment 1 and 10. Proceeds: 0a.

### MQ-12. How an accepted own dimension takes part

**(1)** May a client's materialized dimension (modelled, never measured, `population/materialized.py`)
define a segment, filter a map, or neither?
**(2)** It is the only client-specific variable a respondent carries, and its values are a model's.
**(3)** "Loajalita ke značce" (target 34 %): 400 respondents split 136 / 264. May "loajální" have its
own map?
**(4)** (a) No; (b) a filter only, labelled modelled; (c) a segment, labelled modelled, under MQ-03.
**(5)** "Make an own-dimension consumer explicit" (G28), no rule.
**(6)** Blocks the own-dimension consumer only.

### MQ-13. The register's granularity for segment maps, and whether a client sees respondent points

**(1)** Under MQ-01, does a segment map need one entry per method, or one per segment definition; and
does a client snapshot print respondent dots, or only the density?
**(2)** Dots are individual modelled people; `segment-maps-and-drilldown` 9 must state it.
**(3)** "Ženy 18-29": 41 dots, or one density surface?
**(4)** (a) One per method; (b) one per definition; dots (i) shown or (ii) density only.
**(5)** None (both "Open" in the plan).
**(6)** Blocks segment 4, 9 and `report-delivery#RD4`'s client figures.

---

## Tier 4. Open answers (MVPQ-02b)

### MQ-14. The open-answer coding method (AOC4)

**(1)** How is an open answer coded and counted: the codebook and who writes it, labels and multi-label
semantics, the denominator and missing answers, review and acceptance, agreement measures, small-code
suppression, and what a model may do?

**(2)** Coding is first-release scope (MVPQ-02); without a method no count is produced (AOC4 blocks
AOC5-AOC8). If a model may propose codes, a twelfth worker is added (AOC7); if not, AOC7 closes.

**(3)** 300 respondents, "Proč byste značku nedoporučili?": 212 answered, 88 blank; 6 codes; 260
assignments. "Cena" on 74 answers is 24.7 % of 300, 34.9 % of 212 or 28.5 % of 260. "Obal" has 4:
shown or suppressed? A model proposes codes for all 212 and a researcher changes 19: agreement
reported (e.g. Cohen's κ), and which assignment counts?

**(4)** Per part: denominator (asked / answered / codes); multi-label (each code once per answer); a
small-code floor; the model (none / proposes for review / never final); review (every answer, or a
sample with agreement ≥ a threshold).

**(5)** The plan's constraints only: counts through `admit_numeric_claims`, a model never final, modelled
answers internal until a validation lifts them.

**(6)** Blocks AOC5 runtime, AOC6-AOC8, RD10. Proceeds: storage contract, refusal tests, assumptions.

---

## Tier 5. Replacement (MVPQ-10)

### MQ-15. What a replaced respondent does to weights, effective n and support (RQC5)

**(1)** When straight-liners are replaced by a new linked run, how are replacements drawn, how are weights
recalibrated, what effective n is reported, and when is replacement refused?
**(2)** The feature is settled (F18); without a rule the two runs cannot be compared honestly.
**(3)** Run 1: n 300 raked to sex × age × region, Kish n 252; 12 straight-liners, 8 from "muži 18-29".
(a) Redraw from the same quota cells and re-rake all 300; (b) keep the 288 weights, give each
replacement the weight of the one it replaces; (c) "muži 18-29" has no unused donors: refuse.
**(4)** (a), (b) or your rule, with the refusal conditions (cell exhausted, replacement share above x %)
and what the report states.
**(5)** "Preserve the original run and paid answers; do not silently renormalize" (MVPQ-10).
**(6)** Blocks RQC5's behaviour and ADR. Proceeds: lineage, storage, refusals.

---

## Tier 6. Client data (MVPQ-05)

### MQ-16. The benchmark interval when supports differ

**(1)** Which interval or comparison is valid between a client number and a modelled one?
**(2)** Client data stands beside modelled results or as a benchmark, never mixed (`client-data-in-analysis` 5).
**(3)** Modelled 31 %, Kish n 180, [24.2, 37.8]; client survey 27 %, n 1,850, [25.0, 29.0]; the
difference 4 pp, about [−3.1, 11.1].
**(4)** (a) Both intervals, no difference claimed; (b) a difference interval; (c) no comparison claim.
**(5)** "No guessed statistical rule." **(6)** Blocks client-data 4 and 5.

### MQ-17. May a client survey ever ground AI respondents?

**(1)** May a client's survey answers condition the personas, or only stay a separate comparison?
**(2)** Grounding makes modelled numbers partly client-reported; ADR 0027 decision 7 keeps them apart.
**(3)** The client's 27 % would pull the modelled 31 % toward it.
**(4)** (a) Never; (b) only as a separate, labelled, validated method (a new plan).
**(5)** No permission without your rule. **(6)** Nothing in the MVP under (a).

### MQ-18. The support, metric and interval of a client number (client-data 0, amended G51)

**(1)** What support does a client count or aggregate carry (row count as n, or "not a sample"), which
metrics it may take beyond mean, pct and n, and when is an interval required?
**(2)** `assess_support` suppresses a number with no n, so AC-10's dataset would be refused
(`client-data-in-analysis.md:129`). The plan names no owner; it is statistical, so it is asked here.
**(3)** "Brno, březen: 4,812 návštěv" from records: a census; an interval or none?
**(4)** (a) Records "not a sample", no interval; (b) row count as n; plus the kinds count, amount, rate.
**(5)** "Never an invented effective n." **(6)** Blocks client-data 0, 5 and AC-10.

---

## Tier 7. Report checks (MVPQ-09, D-18)

### MQ-19. Any scientific check beyond admitted support before a client deliverable

**(1)** Beyond the product owner's three checks (no "Interní dokument" source, no drill-down content, no
unadmitted number), must a client deliverable pass any scientific check?
**(2)** `report-delivery#RD0` leaves it to you; RD7 already blocks an unsupported claim.
**(3)** "Horská je hodnocena lépe než Pramen" with [6.8, 7.4] and [6.6, 7.2]; every number admitted.
**(4)** (a) None; (b) the interval-order rule (MQ-20); (c) multiple-comparison control on segment
differences; (d) your list.
**(5)** "Deterministic where possible." **(6)** Blocks RD0's final policy, not the renderer.

### MQ-20. Must analysis prose follow "an order only where 95 % intervals part"? (F061)

**(1)** Should the web's sentence rule (`apps/web/src/lib/result-reading.ts:5-9`) bind analysis prose and
the report, with intervals given to the model?
**(2)** The analysis model is never given intervals, so it can order what Data says it cannot.
**(3)** MQ-19's example: Data says "nelze potvrdit", the analysis says "lépe".
**(4)** (a) Yes, server-side and in the prompt; (b) web only.
**(6)** Blocks the analysis harness change.

---

## Tier 8. Housekeeping (D-18, `productization-coherence.md:615`)

### MQ-21. The tracked-set size rule (F058)

**(1)** `-5` declares its own minimum (`specification.py:1572`) and runs BB1 to 163 objects, Interval
MDS above. Does it set a maximum or a recommended size for a tracked set, or do the readiness limits
stand (3-40 hard, 4-15 recommended, `domain/research_design.py:84-86`)? Today the web enforces 18.6.6's
4-15 and silently cuts to 15. **(3)** A 22-brand set is cut to 15 in the browser and accepted at 22 by
the server. **(4)** (a) `-5`'s limits, stated by you; (b) the readiness limits, 4-15 a warning.
**(6)** Blocks the web fix only.

### MQ-22. Connectedness (K100) and its interval under `-5` (F084)

**(1)** Only if MQ-05 (i) says connectedness is part of `-5`: is K100's bootstrap interval part of it
too (pinned on the run, reachable on develop)? **(3)** Today it is behind a
switch the develop worker cannot reach and its values are editable in Metodika. **(4)** (a) Part of the
method; (b) not shown under `-5`. **(6)** Blocks F9's display.

### MQ-23. Which presets Metodika offers as a base (F135)

**(1)** With `-5` in force, should an edit start from `-5` (today `-4` is offered first,
`domain/methodology/sociomap.py:2007-2013`), and should `-2`, `-3`, `-4` still be offered at all?
**(4)** (a) `-5` only; (b) `-5` first, the earlier presets kept only to read old runs. **(6)** A
one-line change.

### MQ-24. Analysis modules that never receive their inputs (F062)

**(1)** Hypotheses, Segments and Audience are paid modules that never get their inputs but must
complete for the report (MVPQ-04): which inputs must each receive, or may one be declared not
applicable? **(3)** A study with no hypotheses still pays for, and is blocked by, Hypotheses.
**(4)** (a) Define inputs (Segments: MQ-03's evidence); (b) "not applicable" as a declared state that is
not a missing finding. **(6)** Blocks those modules' contracts; MVPQ-04 stands.

---

## R-1. Evidence request (not a decision): the audit's check script, for the earlier presets only

`NPC/analysis/code_formula_checks.py`, its printed `[C*]`/`[P*]` output and its inputs or seeds
(`sociomap-formula-corrections` 0a, C12-C15; `methodology-tab` S4d). It checks the audit's formulas,
which the earlier presets (`-2` to `-4`) compute; `-5` is checked against your own code and self-test.
If the MVP no longer needs the earlier presets checked, say so and the request is withdrawn. Likewise
F5's transform from a declared 1-10 strength matrix (`SPECIFICATION_REQUIRED`, refused today).

---

## Engineering gaps the `-5` decision creates (not the methodology owner's to answer)

Recorded here so the decision is not mistaken for done. Each needs a chunk; proposals are in the PR
description.

- **E-1. No run can pin `aia-sociomap-5` exactly.** New runs pin `-1` and `-3`
  (`domain/research_sociomap.py:323-330`). The only way to `-5` is a Metodika version, which pins the
  edited spec under its own name `aia-sociomap-5+e<n>` (`domain/methodology/pins.py:84-95`;
  `domain/methodology/versions.py:71-75`), and the register matches the exact method id and refuses
  any replaced formula (`domain/sociomap_register.py:72-86`). So MQ-01's entry for `aia-sociomap-5`
  would approve no run AIA can start.
- **E-2. Metodika's method in force and its base.** `in_force="aia-sociomap-3"`
  (`domain/methodology/sociomap.py:2014`); the presets list `-4` first so an edit starts from it
  (`:2007-2013`); the module note says every run pins `-3`.
- **E-3. The web does not draw `-5`.** `OBJECT_MAP_METHODS` names `-4`, `-3`, `-2`
  (`apps/web/src/lib/object-map-view.ts:20`), so `-5` is read as an unnamed method; its relative
  heights are drawn on absolute terraces; no credibility banner, split-half share, uncertainty
  circles, respondent map, taste segments, "Neumístěno" list or 26x height exaggeration. The standing
  rule: the panel follows `ui_app.html`'s drawing (`signed-off-sociomap-method.md`, Doc follow-up).
- **E-4. The report's figures and chapters.** The map chapter prints Stress-1 (`application/report_maps.py:215-220`),
  which `-5` has none of (`:70`); `object_map_snapshots` and `compose_map_sections` read only object maps
  (`infrastructure/report_docx/object_map_figure.py:110`, `domain/sociomap/models_v3.py:801`);
  respondent and segment figures are `segment-maps-and-drilldown` 9.
- **E-5. Metodika's comparison cannot show `-5`'s changes.** `sociomap_check.MapSummary` (`domain/methodology/sociomap_check.py:136`) carries no
  credibility, respondent map or segments, so an edit of those values shows no difference there.
- **E-6. The worker image.** numba needs `NUMBA_CACHE_DIR=/tmp/numba` in the read-only containers
  (`signed-off-sociomap-method.md`, Doc follow-up); the image's numpy, scipy and numba are part of the
  map's identity under MQ-04.
- **E-7. Re-derivation.** The report re-derives the run's map from its dataset and specification
  (`application/report_chapters.py:66, 121`, `verified_map`); for `-5` that must follow MQ-04's answer.
- **E-8. Plans that name `-3` as the MVP method.** `mvp-master-plan.md:126`, `:337`;
  `segment-maps-and-drilldown` 0, 1, 3, 9; `sociomap-formula-corrections` 3, 5b; AC-09's wording is
  method-neutral and stays.
- **E-9. Runtime unmeasured on the worker.** The only figure is the methodology owner's own (#504:
  2-18 s at 1,000 respondents, about 70-90 s at 20,000 with real segments), measured on his machine;
  nothing in the repository or on the develop worker's image records it. Measure there at 1,500, 5,000
  and 20,000 respondents before MQ-06 is answered.

## Not asked, and why

- **SOMECS / H-Model questions** (`sociomapping-engine.md`): post-MVP (`mvp-master-plan.md:126`).
- **Client-facing analysis prose (ANL-1):** waits on the holdout validation; the MVP client report has
  no analysis prose (`report-delivery.md:28`).
- **Groups without direction on the respondent map:** deferred in your methodology.
- **Evaluation tasks and thresholds (MVPQ-06):** the product owner's.
