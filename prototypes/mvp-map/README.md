# AIA MVP Map

**Version:** "AIA MVP Map", version 17, version id `1794374826-eed2`, 11 Nov 2026.

What the MVP is and how it gets built, on one page: the nine steps of a business-decision study, who does what in
each, the hand-offs, the Sociomapa systémů maps, the statistical methods, the decisions made and open, the build
order and the tests that say it is done. It is written for three readers: the executive, the build team and the
methodologist. It is a planning page, not product code. Velis and the fleet are invented cases.

| | |
|---|---|
| Live artifact (first account, owner) | <https://claude.ai/artifact/5pvnwbXtgP2ev3TyYWhSj6> |
| Plan chunks on the page | the 13 pivot plans' front-matter as on `develop` @ b675b5ed (175 chunks, all identical) |
| Method on the Sociomapa tab | "Sociomap Lifecycles" (`https://claude.ai/artifact/3UkTi8G66E85nx9Ccn36oK`, 10 Nov, computed on develop 12bb21c4e); not in the repo |
| Indicator-profile proposal | "AIA MVP" mindmap (`https://claude.ai/artifact/TvY3JTpJySwNJd9s4s5cwm`, 9–10 Nov); not in the repo |

## How to open it

Open [`index.html`](index.html) in a browser. It is one file; the fonts come from Google Fonts. Outside claude.ai
the marks (Keep, Change, Cut, Later, Discuss) and notes are kept in that browser only; in the artifact they are
saved for everyone in the page's database (collections `marks` and `ideas`).

## What changed in this version

- **A new first tab, Overview:** what the MVP is in plain words, where the plan stands, the nine steps, what is in
  the MVP and what is not, the open questions by who has to answer, where each reader goes next, how the three
  documents fit together, and a glossary.
- **The indicator profile map** from the mindmap has its own section on the Sociomapa tab (its five steps, its open
  decisions, its test dataset and traps), shown as proposed.
- **Eight open questions added** (Q-SPINE, Q-CLOSE, Q-NORM, Q-WACT, Q-PLANWORDS, Q-DATASET, Q-XLSX, Q-FETCH) and
  Q-PROFILE reworded. The Decisions tab can be filtered by who has to answer.
- **Figures and labels corrected** against the lifecycle page's stored runs (below).
- **Wording:** every tab opens with what it is for and how to read it; the stage header shows the step's plain
  explanation; "ML" is now "Methods & ML".
- Mark ids are unchanged, so earlier marks still attach to their items.
- **"+ Note" opens the editor of the item that was clicked.** The same item is drawn more than once (a decision on
  its step and on Decisions, a chunk in its step and in a popover, one of Aram's questions twice on the Sociomapa
  tab), and a hidden tab keeps its markup, so a lookup by id opened another copy. The editor is now found from the
  clicked buttons' own card, and a typed note updates every copy (versions 12 and 15). The candidate model
  templates had mark buttons and no editor; they have one now.
- **A chunk's popover on Build order shows the stance just picked** (version 16). It sits outside the tabs and was
  not redrawn with them, so a second click on the button that still looked unselected cleared the saved mark.
- **An answer to one of Aram's questions can combine options** (version 17). Q4, Q6, Q9 and Q13 recommend two
  options together, and picking the second used to replace the first. The answer is stored as one string joined with
  " + ", so answers saved earlier read the same.
- **A mark someone else cleared now disappears for everyone** (version 13). The page used to keep every local mark
  the database no longer held, to protect writes still in flight, so a cleared mark stayed on other people's screens
  and in their session export. Only marks this browser has not yet saved are kept now, and they are retried on the
  next visit. A mark that an older version failed to save, and that the database never held, is dropped the first
  time the new version syncs.
- **A note on one of Aram's questions reaches the session export** even when no answer or stance was chosen
  (version 13).
- **A change by someone else is no longer lost while you are typing** (version 14). An update that arrived while a
  text field had focus was discarded; it now waits until focus leaves the field. "Copy as text" copies the marks as
  they are at that moment. An item just added is kept while its save is in flight, the same rule as for marks.

## Consistency check, 11 Nov 2026

**The first finding is in the repo, not between the artifacts: two scope records disagree (Q-SPINE, owner).**

- `.planning/plans/mvp-master-plan.md:122 @ b675b5ed` and `docs/architecture/adr/0046-business-decisions-pivot.md:38
  @ b675b5ed` keep A1 of 2 Nov: "Keep all in MVP", no single journey is the spine. The MVP Map is built on this.
- `prototypes/obchodni-model/MVP-SCOPE.md:22-29 @ b675b5ed` (version 3, 9 Nov) says A1 "is superseded by the owner's
  words of 8 Nov": study type 2, the report-2 site decision on the ChemVitro files, is the spine. Its §5
  (`MVP-SCOPE.md:432-448`) parks the analysis frameworks, other model types, accounting and market size, operations
  research, the automatic public-data and legal connectors, Sobol/PRCC and fitted demand forecasting, the six diagram
  stacks, the shared client review, the personal-data register and Deep Research v2 beyond typed inputs. Its §6
  accepts on an independent oracle before the case, and its §7 plans five two-week waves (`MVP-SCOPE.md:529`).
- The MVP Map shows the parked items as in the MVP (decisions A1, A10, A13, W26; plan chunks in W1–W4; twelve
  acceptance statements on the Velis journey). The page now lists them in their own column on the Overview, marks A1
  as contested, and says so on the Build order and Done-when tabs. Nothing was removed: which record stands is the
  owner's word. If the 9 Nov record stands, the steps, build order and acceptance on the page need re-cutting to it.

The three artifacts were then compared. The lifecycle page's figures were recomputed from the engine results stored in
it and compared with every figure the MVP Map quotes.

**They agree** on two map types and five configurations (futures, weight settings, experts, units, months, with
futures × weights as an option of the scenario map), one engine (`aia-sociomap-5`), a test per configuration, the
never-claim lists, and the rule that a map supports the recommendation and the decision rule makes it. Figures that
matched: the fleet options' mean savings and loss counts, the 15 pair relations, the joint-loss example (126, 126,
3), shares of first place (68 %, 91 %, 99,7 %; 635 of 800), planted answers found (6 of 6 futures runs, 8 of 9
crossed, 2 of 2 at 12 experts, 3 of 4 missed at 4 and 7), units (7 of 7 planted pairs, 12 false pairs of 126, up to
5 of 21 in one run, interval width about 0,8 at 15 units), months (1 of 16 at 24 months, 4 of 4 at 60 months and low
inertia, 34,6 effective months of 36) and the terrain stretch (0,47–0,54).

**Corrected on the page:**

| Was | Now | Why |
|---|---|---|
| Weakest agreement of the futures map quoted as 0,871 in two places and 0,846 in two others | Both, each named by its sample | 0,871 is sample 1 and 0,846 sample 2 |
| Expert uncertainty radius 0,28–0,41 | 0,28–0,43 | the six runs give 0,281 to 0,426 |
| Weight-settings result with no client weights named | "under the provoz weights", and that another option leads under the finance weights | the 68 % / 91 % / 99,7 % shares are the provoz runs only |
| Scenario maps graded "odhad (modelováno)", "modelled" | "odhad" | the methodology prints `odhad`; the six grades have no "modelled" |
| Never-claim list without two of the lifecycle page's items | added: a share of first place is not a probability; a pair without a line is not "unrelated" | |
| "Two map types, five configurations" over seven equal cards | grouped by type; the crossed map marked as an option; the profile moved to its own proposed section | |
| Six "ML" methods in the MVP, against the mindmap's "ML is out of MVP scope" | tab renamed, lede says none of the six learns from outcomes; the mindmap's two learning ideas added under Later | different things under one word |
| SYS7's text older than develop | synced | `.planning/plans/sociomapa-systemu.md:12 @ b675b5ed` |

**Still different, and now open questions on the page:**

- **What "the MVP" is (Q-PROFILE, owner).** The mindmap describes the MVP as indicator tables, then maps, then a
  report. The MVP Map's MVP is the nine-step study; the indicator profile is a proposed sixth configuration.
- **Four method choices (Q-CLOSE, Q-NORM, Q-WACT, Q-MINROWS, methodologist).** The mindmap leaves them open; the MVP
  Map had stated "close = the same pattern" and "median and MAD per indicator" as settled and did not mention where
  the weights act.
- **Deliverables (Q-XLSX, owner).** Mindmap: maps with coordinates, the processed data file, the report. MVP Map:
  the report only.
- **Public data connectors (Q-FETCH, owner).** After the MVP in the mindmap; W1–W3 in `public-data-routes`.
- **The test dataset (Q-DATASET, owner).** The mindmap wants one built from real figures with planted traps; no
  plan chunk builds it. TD-1 only seals its answer.
- **Mindmap items the MVP Map still does not place anywhere:** the mindmap's "leave one row out" stability check
  (the MVP Map proposes resampling by indicator family instead), and "through time" as maps compared across years
  (the months configuration answers a different question: which monthly figures move together).

**Repo drift found, not fixed here** (plan files are outside this folder's permission; raised as Q-PLANWORDS):

- `.planning/plans/sociomapa-systemu.md:14-16 @ b675b5ed` (SYS9–SYS11) speaks of four "modes", grade `MODELLED`
  and ">= 800" scenarios. The methodology has two types and five configurations, grade `odhad` and 20 000 futures.
- `.planning/plans/mvp-master-plan.md:146 @ b675b5ed` (M-8) says a scenario map's "edge stands only when it is
  stable". On the lifecycle page a scenario map draws no lines; the whole map is tested. The MVP Map's M-8 is worded
  as a planted-answer test per configuration.
- R2-Q15 and R2-Q16 are recorded in `prototypes/obchodni-model/MVP-SCOPE.md:5-7 @ b675b5ed` (version 3, 9 Nov),
  which already has the two types and five configurations; the plan files above lag behind it. R2-Q20, R2-Q22 and
  the references MOD-3.3, MOD-11.1 and MOD-13 that the page cites resolve to nothing on develop.
- `MVP-SCOPE.md:8 @ b675b5ed` names the ChemVitro case as the MVP's spine and refers to
  `prototypes/case-chemvitro/`, which is not on develop; the MVP Map walks through Velis and M-10 names Velis.

## Known to be wrong or thin

- The Velis figures on the process map and the Methods tab illustrate the journey; nothing computed them.
- The fleet example is 600 futures per sample, two samples; the method starts at 20 000.
- The examples differ between the documents (fleet, Velis, ChemVitro, "which of 8 sites"). Each is labelled, none
  is unified.
- The mindmap and the lifecycle page are not exported into the repo.
