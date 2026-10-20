# ADR 0027 — A client's own data is client-reported evidence: its own origin, computed by code, shown beside modelled results, never mixed into them

**Status:** Proposed — 2026-10-19, from the product owner's answers of the same day (`overview.md`
§ MVP roadmap, MVP-19). **Builds on** [ADR 0015](0015-client-first-product-interface.md) (Client
Knowledge, scoped before it is read), [ADR 0016](0016-research-execution-and-model-transmission.md)
(a run executes a Design Revision), [ADR 0019](0019-two-roles-and-human-ai-gates.md) (a person
decides what the AI produced), [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md)
(an origin of its own, admitted only as what it is) and the evidence gates (`domain/evidence/`).
**Changes** the closed set of data origins (decision 1) and the claims a report may print (decision 6).
**Leaves unchanged** the AI respondents' origins, the Sociomap register, the methodology in force and
every existing run.
**Date:** 2026-10-19. **Amended 2026-10-20** with the product owner's MVPQ-05 answer (decisions 3, 6 and
Q3; `mvp-owner-decisions.md`) and the support question the cross-check found (Q4, master plan G51).

## Context

A client brings data: sales by product and channel, prices and margins, a CRM or order export, a
survey it ran itself. Today AIA keeps such a file as a client source, reads it and previews it
(`domain/client_datasets.py`, lifecycle K2c), and proposes knowledge from documents. A dataset is
"V AIA zatím není" for analysis: nothing computes on it.

The owner decided on 2026-10-19 that in the MVP a client's dataset **feeds a study's analysis**,
with personal columns dropped (MVP-19), and answered the questions this ADR records.

Three facts of the code frame it:

- **Origins are an allowlist.** `DataOrigin` names where the respondent data behind an artifact came
  from; every member is in exactly one of `NON_EVIDENCE_ORIGINS` or `CLIENT_ADMISSIBLE_ORIGINS`, and
  a member added later is refused until it is decided (`domain/fieldwork.py:59-88 @ 0b4e05e`,
  `test_every_origin_is_decided_once`). Today the only admissible origin is `MODELLED_AI_PANEL`
  (`:88`).
- **A number reaches a result only as an `AdmittedClaim`**, minted by `admit_numeric_claims`
  (`domain/evidence/admission.py:188, 298 @ 0b4e05e`) after field policy, support, interval and tier.
- **Personal data is detected on reading.** A column whose header names a person or contact, or where
  a share of filled cells looks like an e-mail, phone or Czech birth number, carries a `PersonalHint`
  (`domain/client_datasets.py:70, 144 @ 0b4e05e`).

## Decisions

1. **A new origin: `CLIENT_REPORTED`.** Data a client measured and gave AIA is its own origin,
   admissible client-facing (decision 6), never a member of the modelled or synthetic sets.
   `origin_kind` gains a fourth reading, *client-reported*, and every label reads it from there.

2. **Three shapes, each with its unit declared.** The MVP accepts aggregates (a table already
   summarised: month × product × channel), row-level records (one customer, order or transaction per
   row) and a client's own survey (one respondent per row). What a row is, is part of the data
   contract (decision 4); nothing is inferred from the file.

3. **Personal columns are dropped, never stored for analysis, never sent to a model.** The analysis
   copy holds **only** the columns the accepted contract names as used and not personal: an
   allowlist, not the preview's `PersonalHint`s, which only warn (amended 2026-10-20, MVPQ-05: the
   accepted contract alone is the dataset's evidence policy, with no AIA field list in between). A
   column the contract does not name is never copied. The kept source file is unchanged and stays a
   client source; the analysis copy is a separate artifact without the other columns.

4. **A person accepts a data contract before any use.** Per dataset: the period and the unit (what a
   row is, currency, units); each used column's meaning (AIA proposes, a person confirms); the use
   rights (the client allows this use, and who confirmed it); and code's quality report (missing
   values, duplicates, out-of-range values), which the person accepts or rejects. The contract is
   versioned; a run pins the version it used.

5. **Code computes; models see only code's admitted results.** Every number from a client dataset is
   computed by deterministic code (product rule "No LLM for deterministic computation") and admitted
   through `admit_numeric_claims` like any other. The Lead, the analysis modules and the map
   interpreter see those admitted results, never rows. Rows never leave AIA's storage.

6. **Graded "client-reported", printed every time.** A client-reported number carries its own grade:
   measured by the client, not verified by AIA. AIA vouches for the computation, not the data. It may
   appear in the client report and the approved exports, each time labelled *z dat klienta* (the owner,
   MVP-19). Its source dataset and period are disclosed once per report, in a footnote or the methods
   chapter, not on every line (amended 2026-10-20, MVPQ-05).

7. **Beside modelled results, never mixed into one number.** A client-reported number and a modelled
   number are never combined into one figure. Two uses are allowed:
   - **Side by side:** its own tables and findings next to the modelled ones, each with its label.
   - **Benchmark:** a modelled result compared with the client's measured value (for example
     modelled against actual channel shares), the gap shown with both labels and both supports.
   Calibrating or weighting the AI respondents from client data is **not** decided here: it changes
   the modelled evidence itself and is the methodology owner's call.

8. **A client's own survey may have its own Sociomap.** Computed by the same engine under the
   study's pinned method, labelled as the client's survey, with the same support rules (n, intervals,
   pair status), and never merged with the AI respondents' map. Its status is the Sociomap register's
   for the method, as for every map.

9. **Scoped like Client Knowledge, kept until a person deletes it.** A dataset belongs to one client
   and is read only inside a resolved `ClientContext` or `StudyContext`, never across clients. It is
   kept for that client's studies until a person deletes it. A run that used it keeps its computed,
   admitted results and a record that the source was removed; it never silently loses provenance.

## Consequences

- **New code, in order:** the origin and its reading (`domain/fieldwork.py`, its test); the data
  contract as a type and its acceptance route; the analysis copy without personal columns; the
  deterministic computations per shape (descriptive tables, benchmark gaps); admission and the
  client-reported grade in `domain/evidence/` and the report's marks; the survey's map path through
  the existing engine. Each lands with its test; nothing is client-facing until decisions 4-6 hold.
- **What it costs:** a fourth origin every label, report and readiness check must read; a contract a
  person fills before a dataset is useful. The owner accepted that a client dataset is not usable on
  upload alone.
- **What it does not do:** no calibration of AI respondents (decision 7), no scenario inputs
  (scenarios are out of the MVP, MVP-1), no promotion of client data into the shared population
  (MVP-7), no joining of a client's rows to AI respondents.

## Open questions

- **Q1.** How a benchmark states its gap when the two supports differ greatly (a modelled n of 300
  against a client's 40,000 rows): one interval rule, or each side's own?
- **Q2.** Whether a client's survey answers may also ground AI respondents later (decision 7's
  calibration), and who decides it: the methodology owner.
- ~~**Q3.** The exact label words beside each number in the report.~~ Answered 2026-10-20 (MVPQ-05):
  *z dat klienta* beside each number; source and period once (decision 6).
- **Q4** (the cross-check, master plan G51). A client number has no respondent n or effective n, so
  the evidence layer's support rule would suppress it, and the metric vocabulary has no count,
  amount or rate. Decide the support a client aggregate or record count carries (exact counts or
  row count as n, or an explicit "not a sample" status, never an invented effective n), the metric
  and unit set a client number may take, and when an interval is required
  (`client-data-in-analysis#0`). Q1, Q2 and Q4 are the methodology owner's.
