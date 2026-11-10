# Brief: the MVP that produces report 2

8 Nov 2026. From the product owner, in the PM coordinator's chat (session `session_013NjzbvdQ2LevhrQqa6bUW2`):

> "we showed the executive the reports we made and he loved report number 2 from the chem vitro case study. We need to
> focus on creating an MVP that will allow us to produce these reports … include the scenario maps where we allocate
> different weights to different attributes to different components of the business so whether logistics is a 0.3 and
> operations management is 0.5 … take the different components of what we're measuring, allocate weights to it and run
> the scenarios and display the scenarios on the Sociomaps. … go back to the MVP drawing board prototype and analyze and
> improve and focus the MVP to be able to create the reports like report 2 … let's build from the bottom up, step by step."
>
> "we need to be able to work from all business perspectives: financial, strategic, operational, marketing, logistics
> just everything. Spawn as many fable 5.1 sessions as needed to build this. I want the outcome to be one MVP prototype,
> one methodology PDF, and one MVP scope. When building, keep points straightforward; don't use bloated text or redundant
> labels. Use today's AIA software as the base for the pivot."

## The three outcomes

| Outcome | Where it lives | Owner |
|---|---|---|
| One MVP prototype | this canvas, `prototypes/obchodni-model/` (the Design canvas `HM9rmiwAM9asP8hfyn1XHp`; the coordinator publishes) | sessions A–E below |
| One methodology PDF | `prototypes/obchodni-model/methodology/` (HTML sources, the build script, the PDF) | session F |
| One MVP scope | `prototypes/obchodni-model/MVP-SCOPE.md` and board MV0; the `.planning` plan follows in a docs PR on the owner's word | session A |

## The exemplar

`exemplar/ChemVitro_2_model-lokality_nigel.pdf` (text in `.txt`), 44 pages, 5 Nov 2026. The executive's verdict: this is
the report AIA must produce. Its parts carry ids R2-P01 … R2-P18. What it does, step by step:

1. **Zadání.** The decision, eight options plus the buy baseline, four constraints, the CFO's rule written on 2. 11. 2026
   before any result (median saving, P(beats buying) ≥ 0,75, P(loss > 20) ≤ 0,10, P(start by 1. 7. 2030) ≥ 0,80,
   investment ≤ 175). One condition needed an interpretation (investment judged on the base case); it is stated and
   waits for the CFO. The case pack: branch `chore/case-chemvitro`, `prototypes/case-chemvitro/` (read it with
   `git show origin/chore/case-chemvitro:…`; do not merge the branch).
2. **Data.** Every file and document used; 42 data-check findings (units, kg vs t, currencies, price years, duplicates, a
   USD row, a spot purchase), each with its disposition (P1). The key finding: the brief says 1 470 EUR/t, the purchase
   file shows 1 694 and 1 868. Rešerše's public inputs (ETS price, taxes, contributions, rates) are marked
   *prozatímní* until verified at the source; "Stav podkladů" on page 1 says so.
3. **Předpoklady.** 54 inputs in one table (T9): low / likely / high, distribution, source, grade, who stands behind it,
   state (ověřeno / prozatímní / úsudek). Estimates from client data where possible (EPC overrun 17 % median from 36
   comparable plants; overrun and delay drawn together). Scope check of the EPC estimate against each site's documents;
   the exclusions priced (bridge, rail spur, pre-treatment, compensation, park fee). Correlations declared as judgement
   with a stability test fixed before computing.
4. **Model.** One cost-of-supply model, shared timeline (decision 1. 2. 2027 → permits → build → ramp-up; spot purchases
   while late), base case plus 20 000 seeded futures, seed 20270201, same bytes on rerun.
5. **Výsledky.** *Rozhodnutí*: the rule as written per site at 8, 6 and 10 % (T1–T3), the verdict as a boundary (the
   compensation chance at which the rule's choice flips: 14 / 15 / 16 %), delay tables (0/2/4/6 months, with and without
   compensation), hiring delay as a stress test, tornado, break-even prices, post-2035 terms as a second lever,
   correlation settings leave the verdict unchanged. *Hodnota informace* in two measures: for the rule (what the
   enquiry does to the rule's choice) first, EVPPI second, neither a budget; an enquiry table with output, duration and
   cost. *Finance*: pre- and post-tax NPV at 6/8/10, IRR, payback, incentives as tax reliefs vs cash grants (T4, T5).
   *Provoz*: cost per tonne by category in 2032 (T6). *Harmonogram*: start-date distribution per site against the
   deadline, P(včas), every month of delay.
6. **Sociomapa.** The futures map (8 sites, 20 000 futures as observers, centred per future): heights = mean saving,
   links only where reliable, the relation matrix T7, the shared-failure table T8 ("no site is a backup of another"),
   relative vs absolute reading, a stability test over three correlation settings declared in advance (the map failed
   it, and the report says so). Internal until the methodologist approves.
7. **Zpráva.** Shrnutí (Doporučení · Důvod · Jistota · Další rozhodnutí, the rule table, Stav podkladů), Úvod, Přehled
   literatury, Metodika, Předpoklady, the result chapters, Diskuse, Doporučení a provedení (a dated plan with who and
   what output), Meze studie, Literatura, Zkratky, Přílohy A–D and tables T1–T9. Every number carries one of seven
   grades in small type and a numbered source at the chapter's end.

What the report itself admits (ch. 14) and the MVP must fix: public inputs unverified; the compensation chance is a
judgement with no document; the map is not stable; changes tested one at a time.

## The focus (replaces "Keep all in MVP", A1 of 2 Nov)

The MVP's spine is **study type 2, end to end, on the ChemVitro case**, producing a report with the exemplar's content
and quality. Everything the canvas has that type 2 does not need is parked (planned, not deleted): the worker survey
(type 3), Blue Ocean, governance and architecture frameworks, the six diagram stacks, unit and period maps, the GDPR
register, the analysis catalogue beyond what the perspectives below need.

**Perspectives, not views.** The owner: "all business perspectives: financial, strategic, operational, marketing,
logistics". Each perspective is a set of *components* of the decision, each component a measure per option with a
source (model result, client data, cited finding, named expert score) and a direction. Perspectives: finanční
(saving, investment, IRR, payback, tax), strategická (supplier dependence, reversibility, post-2035 terms, market
position), provozní (cost per tonne, staffing, ramp-up, hiring time), marketingová / obchodní (customer promise,
delivery time, demand growth; thin for ChemVitro, central for Velis), logistická (transport in and out, rail, access,
distance), prostředí a povolování (permits, emissions, wastewater, compensation chance), lidé (wages, labour market).
A perspective with no component for a case stays empty and says so.

**Weighting scenarios (new map).** A scenario is a named weight vector over components or perspectives, composed by the
researcher or the client's people (e.g. "FR: finance 0,5 · provoz 0,3 · logistika 0,2"), plus a fan around each.
*Mapa scénářů vah*: rows are the scenarios, objects are the options, height is the weighted score under the chosen
scenario, options close together win under the same weightings. It sits beside the futures map, never merged.
The review's rules of 5 Nov hold (ADR 0046 § The methodology review, R1–R10): the client's rule decides; gates are never
compensated; a missing component keeps a range, never a score; the map is preference information and goes to "Co by
závěr změnilo", not into the recommendation; shares are shares of tested settings, not probabilities.

## Sessions

Each session owns the boards named; nobody edits another's boards. New boards keep the frame of MV3
(`MV3SystemMap.dc.html`): the nine-step navigator, Ada's collapsible pane (`#leadx`, closed), header, `.zseq` arrows.
Board codes and file names of existing boards stay. `tools/` under this folder shows how boards are generated from
specs and how the real `aia-sociomap-5` engine draws maps (`engine_maps.py`, `build.py`).

| Session | Builds | Boards |
|---|---|---|
| A Scope | `MVP-SCOPE.md`; MV0 rewritten around the spine (steps → what exists in `apps/`, `packages/` today → the chunk that builds the rest, by plan id; acceptance = the ChemVitro answer key); Z0 flow and board list; perspectives defined for the other sessions | MV0, Z0, MVP-SCOPE.md |
| B Inputs | the Zadání for a type-2 case (rule with four conditions, the interpretation record), Data (contracts, the findings table P1 with dispositions, units/currencies/price years), Rešerše (public inputs with state and verification at source), Předpoklady (the T9 table, estimates from comparables, scope check vs EPC, correlations as judgement with the stability test declared) | Z3, Z5, M1, MV1, MV2, M2 |
| C Model and results | Model (timeline, cost-of-supply, base case, futures, stopping rule, one-change-at-a-time propočty), Rozhodnutí (rule table at three rates, decision boundary, delay tables, hiring stress, tornado, break-even, post-2035 lever, correlation check, value of information for the rule vs EVPPI, the enquiry table), Finance, Provoz, **Harmonogram (new board M4g)** | M3, M4, M4b, M4d, new M4g; M4c and M4e marked parked |
| D Maps | the futures map as the exemplar draws it (T7, T8, relative vs absolute, the three-setting stability test, honest failure), the **weighting-scenario map (new board MV9)** on the real engine with the perspectives and named scenarios, SI1–SI4 reduced to what MV9 needs | MV3, new MV9, SI1–SI4 |
| E Report | Osnova zprávy with the exemplar's part structure (R2-P01…P18) and the grade/source conventions, Zpráva as the report AIA renders (reuse `domain/report`, the DOCX renderer, grades from `domain/report/evidence.py`), MV8 validity review on the exemplar's admitted limits, MV5 register entries the exemplar waits on | MV4, M6, MV8, MV5 |
| F Methodology | version 3 of the methodology PDF: one chapter per step of the spine, each with inputs, outputs, checks, what exists in AIA today and what the ChemVitro acceptance expects; the perspectives and the weighting map; the exemplar as the worked example; sources `methodology/*.html`, `build.js`, the PDF | `methodology/` |

Session A finishes its perspectives definition first and messages the coordinator; B–E read it from the branch.
Session F starts from this brief and the exemplar, then folds in the boards as they land.

## Rules

- **Today's AIA is the base.** Every step names what already exists (`CLAUDE.md` § 2 map: the workbench, the Lead,
  working copy and revisions, data contracts, the report document model and DOCX renderer, grades, the `-5` engine,
  Metodika's register) and what is new. No parallel product.
- **Plain text.** Short sentences, no filler, no label that repeats its neighbour, no explanation of how AIA works on a
  screen. Czech on the boards, English in the scope and the methodology, Czech on-screen terms in italics.
- **Fictional numbers consistent with the exemplar.** Where a board shows ChemVitro numbers, take them from the exemplar's
  tables T1–T9; do not invent new ones that contradict it. Velis boards keep their own numbers.
- **Methodology review of 5 Nov holds** (ADR 0046 on `chore/pivot-business-decisions`, § The methodology review).
- **Render before you push.** `tools/prototype_renders/render.js` with the Design runtime saved as `support.js`
  (read `artifact-type/dc-runtime.js` from the canvas with the Artifact tool, or ask the coordinator); every board
  with 0 errors and 0 failed requests; set the board's `$preview` height and its `h` in `canvas.json`.
- **Do not publish the canvas.** Export files only; the coordinator publishes the consolidated canvas.
- **Git.** Branch `chore/mvp-r2-<letter>` from `origin/chore/obchodni-model-method-v2`. Commit and push only files
  under `prototypes/`: that is the owner's standing permission (CLAUDE.md § 5, Artifact exports), and his words above
  ("Spawn … sessions … to build this", 8 Nov) authorise this work. Nothing outside `prototypes/`, no merge; open a
  draft PR into `develop` and message the coordinator (`session_013NjzbvdQ2LevhrQqa6bUW2`) with the PR number and a
  five-line summary. Author `nigelblount <191063588+nigelblount@users.noreply.github.com>`; no model names in
  commits or files.
