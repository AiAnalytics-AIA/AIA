---
status: planned
chunks:
  - "[ ] 0. Decide the evidence policy for a client's dataset columns (deferred by the owner, 2026-10-19), and settle ADR 0027's three open questions"
  - "[ ] 1. The origin CLIENT_REPORTED and its fourth reading in origin_kind, every label reading it"
  - "[ ] 2. The data contract as a type, and the route a person accepts it through (approval ledger)"
  - "[ ] 3. The analysis copy holds only the columns the accepted contract names, each classified by a person; nothing personal stored for analysis or sent to a model"
  - "[ ] 4. Deterministic computations per shape: descriptive tables and benchmark gaps"
  - "[ ] 5. Admission and the client-reported grade in domain/evidence, and the report's marks"
  - "[ ] 6. A client's own survey: its own Sociomap through the existing engine, never merged"
  - "[ ] 7. The Lead and the analysis modules see only admitted client-reported results, never rows"
  - "[ ] 8. Brief materials pick a client dataset; `brief_signature` and `design_material` carry the source id and the contract version, with one fixture for Python and TypeScript"
  - "[ ] 9. The client-data steps placed in the run: a graph node, a contract-version pin on the run, an impact root, and which run's report prints them; class and lineage for client-reported numbers sent to a model"
  - "[ ] 8a. W0 proposed Brief-material/signature interface and shared fixture; uploaded datasets remain ineligible until an accepted data contract exists"
---
# A client's own data in a study's analysis

Track D of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
ADR 0027 (#494, Proposed) and `mvp-cohesion.md` F3 and F7 (#496). **Owner: a chat session, named
when chunk 0 starts. Runtime use and admission wait for accepted ADR 0027; chunk 8a may propose the cross-plan interface before that decision.**

## Decisions this plan carries

MVP-19: a client's dataset may feed a study's analysis, as a new evidence origin, measured client
data beside modelled respondents; personal columns are dropped, never stored for analysis, never
sent to a model. ADR 0027 records the nine answers behind it. The ADR's own build order is the
chunk order below (its §Consequences).

## What exists

- Origins are an allowlist: `CLIENT_ADMISSIBLE_ORIGINS` holds only `MODELLED_AI_PANEL`
  (`domain/fieldwork.py:88 @ 085abe0`), `origin_kind` has three readings and the comment at `:152`
  says there is no fourth, and `test_every_origin_is_decided_once` fails an origin not decided.
- A study's instrument items become evidence fields only under the policy their answers' origin
  selects, `-1` simulated or `-2` modelled panel; any other origin is refused
  (`domain/evidence/instrument.py:112-121 @ 085abe0`, `ARCHITECTURE.md` §4).
- A dataset's preview names a column personal from its header or its values and masks its samples
  (`domain/client_datasets.py:70, 144 @ 085abe0`). **Masking is the preview's rule; dropping is the
  analysis copy's.** Say it once in chunk 3's test so the two never drift.

## Chunks

0. **The policy decision.** Product owner's part **decided 2026-10-20 (MVPQ-05)**: the accepted
   data contract **alone** compiles into the dataset's evidence policy (one authority *per evidence
   source*, MVP-29), with no AIA field list in between: a column the contract names used and not
   personal is admissible as client-reported. ADR 0027's Q3, the label: "z dat klienta" beside each
   client number, the source and the period disclosed once (a footnote or the methods chapter, set
   with `domain/report/copy.py`), not on every line. **Still open (methodology owner):** Q1, the
   benchmark interval when supports differ greatly, and Q2, whether client survey answers may ever
   ground AI respondents. Output: an amendment to ADR 0027 and this plan's chunks 4 and 5 made exact.
1. **Origin.** Add `CLIENT_REPORTED`, decide it admissible client-facing, add its `origin_kind`
   reading, update `test_every_origin_is_decided_once`; every label, report and readiness check that
   reads an origin reads this one.
2. **Contract.** A frozen type and an accept route under `APPROVE_GATE` writing an approval-ledger
   row in the same transaction (the Lead's routes are the pattern, `ARCHITECTURE.md` §4). A dataset
   is not usable on upload alone (ADR 0027, accepted trade-off). Test: analysis refuses a dataset
   with no accepted contract, by name.
3. **Analysis copy: an allowlist, not a blocklist.** The copy holds **only** the columns the
   accepted contract names as used, and acceptance requires the person to classify each one
   (personal or not); a column classified personal is refused. The preview's personal hints
   (`domain/client_datasets.py:9-14 @ 085abe0`) only warn: they recognise a few header names and
   e-mail, phone and Czech birth-number values, "err towards flagging" and are hints, so an
   identifier under an unrecognised header (`customer_id`, an account number, an IP address, a name)
   would pass a rule that drops only what they flag. Fail closed: a column the contract does not
   name is never copied. The original stays as the client's source, scoped to the client
   (`ClientSourceRepository`). Tests: a dataset whose `customer_id` column no hint flags is absent
   from the copy unless the contract names it, and naming it as not personal is the person's recorded
   act; no unnamed column appears in the stored copy, in an artifact or in a model request.
4. **Computation.** Code computes (descriptive tables, benchmark gaps); no model reads a row.
5. **Admission and grade.** The new grade through `admit_numeric_claims`; each number labelled
   *z dat klienta*, its period and source dataset disclosed once per report (MVPQ-05), not per line; shown **beside** the modelled results or as a
   benchmark, never mixed into one number (ADR 0027 decision 7).
6. **Client survey map.** The existing engine over the client's own survey, labelled as the
   client's survey and never merged with the AI respondents' map. Method registration follows
   `segment-maps-and-drilldown` chunk 4.
7. **Lead and modules.** Only admitted client-reported results enter the Lead's results context
   (`mvp-cohesion.md` F4) and the eight analysis modules' evidence.

## Depends on / feeds

Needs ADR 0027 accepted, `client-knowledge-lifecycle` K2c (dataset preview) and K5 (an owned child),
and `evidence-integrity` chunk 5 (one authority). Feeds AC-10, AC-08 and the report's marks (AC-13).
Chunk 1 edits `domain/fieldwork.py` and `domain/evidence/`: hand-off, not a second editor
(`mvp-cohesion.md` F8).

## Doc follow-up

`ARCHITECTURE.md` §4 (the origin set and the fourth reading), ADR 0027 (chunk 0's amendment),
`overview.md` track D ("ADR first" becomes ADR 0027).

## Added by the master plan (2026-10-19)

- **8.** The Brief's materials are where a person picks a dataset (F19). `briefing.attachments`, the Python
  and TypeScript `brief_signature` and `design_material` are written once. Interfaces I10, gap G25.
- **9.** Nothing places the client-data steps in a run today (T3 A11-A12): no node, no pin, no impact root.
  Client-reported numbers going to a model need a class and a lineage (`MaterialRule` has none), shared
  with `lead-orchestration#LO8`. Gap G35.
- **Permission.** Chunk 2 says the contract is accepted under `APPROVE_GATE`; `mvp-target-architecture.md`
  §5 says `PROPOSE_CLIENT_KNOWLEDGE`. One is chosen in chunk 2 and the other document is corrected. ADR 0027
  decision 3 (a blocklist of flagged personal columns) and chunk 3 (an allowlist the contract names) are
  reconciled in chunk 0.


## Early Brief contract, runtime later (2026-10-20)

**8a. W0 proposed Brief-material interface.** Specify source id, reading hash, optional contract id
and version, use/eligibility state and Python/TypeScript signature fixture before the W1 Brief UI.
An uploaded dataset with no accepted contract is visible as a source but unavailable to analysis;
the signature cannot label it admitted. Review with S1 before workbench 18. This is contract/design
preparation; ADR 0027 remains Proposed until its owner decisions are answered.

Chunk 8 implements the accepted contract/pins in W3 with chunks 0-9; it is not claimed built by 8a.
Evidence-integrity 8 precedes chunks 4-5; frozen contract versions reach node 9 and the report.

## Migration (lane M8, W3)

Chunk 2 stores the accepted contract (`client_data_contracts`) and chunk 3 the analysis copy
(`client_dataset_copies`): one migration, lane **M8**, S3, with each repository, a round-trip test, an isolation
predicate test, a concurrent-access test and its `layer_check` rule in the same PR. Neither table exists before
its chunk needs it; the W0 contract of 8a stores nothing. Gap G43.
