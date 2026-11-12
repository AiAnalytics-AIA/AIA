# AIA MVP Map

**Version:** "AIA MVP Map", version 23, version id `1794475505-7777`, 12 Nov 2026.

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

The page opens in Czech; the switch in the header (Česky / English) changes it and is remembered in that browser.

Open [`index.html`](index.html) in a browser. It is one file; the fonts come from Google Fonts. Outside claude.ai
the marks (Keep, Change, Cut, Later, Discuss) and notes are kept in that browser only; in the artifact they are
saved for everyone in the page's database (collections `marks` and `ideas`).

## What changed in this version

- **The Hand-offs diagram is readable** (version 23). The owner, 12 Nov: the arrows were "very chaotic", "duplicated
  or overlap". They were: 35 hand-offs share 25 pairs of steps, and each was drawn as its own arc, so pairs with two
  or three hand-offs showed as stacked near-copies; every arc left and landed on the same dot in the middle of a
  box's top edge; and all of them were drawn above the row. Now there is one arrow per pair of steps, with a number
  on it when it carries more than one hand-off (eight carry 2, one carries 3; the names are in its tooltip and in
  the panels when a step is clicked). Each box spreads its arrows along its edge, incoming on the left and outgoing
  on the right, ordered by distance so that arcs nest instead of crossing at the box. What goes to the report
  outline and on to the client is drawn below the boxes, the rest above. The "2 in · 3 out" line under each box was
  removed: it ran past the boxes into the arrows, and the panels show the same counts. The table under the diagram
  is unchanged.
- **"Zpráva" is now "Report"** (version 22). The owner, 12 Nov: "lets change zprava to Report or Studie". The page
  uses Report, because "studie" already names the whole job on this page (a study, `study_id`). The step Zpráva is
  Report, Osnova zprávy is Osnova reportu, and the Czech text says "report" (masculine) wherever it said "zpráva",
  including the data quality report and the situation reports. Recorded on the page as decision NAME-REPORT; A15,
  which named the stage Osnova zprávy on 2 Nov, now says so.
  Left as they were, on purpose: the 175 plan chunks, which are quoted from the plan files and still match develop
  word for word, and the product's screen labels quoted from the design canvas („Předat do Zprávy“, „Zpráva o
  kvalitě“, „Přidat do osnovy zprávy“ and others). So the plan files, ADR 0046 and the design screens say Zpráva
  and Osnova zprávy while this page says Report and Osnova reportu; Q-PLANWORDS now lists that as well. Step ids
  (`zprava`, `osnova`) and mark ids are unchanged, so earlier marks still attach.
- **A second pass for plain wording** (version 22), asked for by the owner on 12 Nov. Five editors read every Czech
  entry again against one rule sheet (one idea per sentence, everyday words, verbs before noun chains, active
  voice, change nothing for taste). 107 entries changed: 67 only for the rename, 37 for clarity, 3 where a term
  fixed in the first pass had not been applied. The editors also flagged 25 English source sentences as hard to
  follow (dropped verbs, stacked clauses, "accepts the MVP on an independent calculation with known answers before
  the case"); all 25 were rewritten in the source and carry the same numbers. Two readings were chosen by me and
  should be confirmed by the methodologist: "in a world with no relation, draws no more than its declared error
  rate" now names its object ("no more false relations"), and "names are personal data inside the client" now
  reads "personal data of people at the client".
- **An Abbreviations tab** (version 22; "Zkratky"), asked for by the owner on 12 Nov: every abbreviation and code
  family the page uses, 108 rows in seven groups (product and this page, codes on this page, business and finance,
  analysis frameworks, methods and statistics, public sources and registers, files and technology), each with what
  the letters stand for and what it means in plain words, in Czech and English, with a filter box. The rows for
  plan chunk ids (SYS…, CR…, FND…) are drawn from the plan data on the page, so they follow it. The Overview
  glossary links to it. Three things it states rather than hides: W1–W4 are build waves while W2–W28 are answers
  from the 2 Nov walkthrough (the same letter for two things); the page quotes MOD-3.3 and MOD-13.1 without saying
  where the numbered text is kept; and SOMECS, BB1 and WIND are names the page never spells out.
- **A Presentation tab** (version 19; "Prezentace"), asked for by the owner on 11 Nov: thirteen slides that walk an
  executive through the MVP step by step (what we build and why, the nine steps on the Velis example, why the numbers
  can be trusted, what is in and out, how it is built and when it is done, what follows, what we need from the
  owner). Back and Next buttons, dots, and the arrow keys.
- **Czech by default, English one click away** (version 19). The page's source stays English. In Czech mode every
  text the page draws is looked up in a dictionary of 1,448 entries inside the page (`<script id="i18n-cs">`), keyed
  by the English text with each number replaced by `§`, so counts carry across. Left in English on purpose, marked
  `data-notr`: the plan chunks and each step's build detail (quoted from the plan files, which are English) and the
  owner's quoted words. The Session notes export is plain text and stays English. The translation was done in five
  parts against one glossary and then unified; the executive-facing screens were read through, the rest was
  spot-checked. A methodologist's read of the Sociomapa and Methods tabs in Czech is still owed.
  **Proofread in full** (version 21): every entry was read against its English source by five proofreaders, one
  per tab group, plus one pass for terms across the whole page, and the corrected entries were read again. 185 of
  the 1,416 earlier entries changed and one was added. The proofreaders' 133 corrections, by their own labels: 75 for clarity (plainer, more direct Czech), 20 to
  follow the glossary, 18 language errors (agreement, case, typos), 15 where the Czech said something other than
  the English, 3 sentence fragments that did not join, 2 number slips. The rest are terms made the same everywhere.
  The terms now fixed across the page: a named person is „člověk uvedený jménem“ (experts: „jmenovitě uvedení
  experti“), "backs up" is „je zálohou“, the decision rule „dává“ the recommendation and the map „podporuje“ it,
  the PRIM box is „rámeček“, drivers are „faktory“, a baseline forecast is „základní prognóza“, the validation
  suite is „sada validačních zkoušek“, and the lifecycle page keeps its name, Sociomap Lifecycles.
  Found by reading the drawn page rather than the dictionary: a space left before a full stop where a sentence is
  assembled from parts; the kind of a money line glossed twice; the empty plan-chunk message, the "not saved"
  status and the add-item kinds still in English; the two fixed labels of the header; and „z/ze“, „v/ve“ before a
  number, which depend on how the number is read („ve 42 %“, „ze 6“, „z 9“) and are now chosen from the number
  itself, dates left as written.
  Left for the owner or the methodologist to choose, unchanged: „sdílená zastávka“ for a shared stop,
  „myšlenková mapa“ for the mindmap, the group label „Evidence“, and „navrženo“ standing for both "proposed" and
  "designed".
  Numbers are carried across as written, with three rules (version 20): a comma group is read as thousands only
  when the number does not start with 0 (so `20,000` becomes `20 000` and `0,871` stays), a decimal point becomes
  a comma, and a number inside an id (`MOD-13.1`) is left alone. Checked by comparing every number drawn in English
  with the Czech rendering: 3,971 numbers over 40 views, no difference.
- **Machine learning follows the MVP** (version 18). The owner, 11 Nov: "after the mvp we also want to use ML".
  Recorded as decision ML-AFTER. The Methods & ML tab ends with "After the MVP: machine learning": the candidates
  (the mindmap's two first: weights learned from outcomes and from past shocks), and what has to be true before one
  starts. Which comes first is the new open question Q-MLFIRST. This agrees with the mindmap ("the ML branch is out
  of MVP scope"); the MVP's own six methods are fixed statistics and do not learn.
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
