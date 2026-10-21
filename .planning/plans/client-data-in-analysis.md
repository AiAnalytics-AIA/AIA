---
status: in-progress
chunks:
  - "[ ] 0. Decide the evidence policy for a client's dataset columns (deferred by the owner, 2026-10-19), and settle ADR 0027's three open questions"
  - "[ ] 1. The origin CLIENT_REPORTED and its fourth reading in origin_kind, every label reading it"
  - "[ ] 2. The data contract as a type, and the route a person accepts it through (approval ledger)"
  - "[ ] 2a. The data quality report the person accepts (W3, after 3a): missing, duplicate and out-of-range counts per used column over every row, versioned and hashed, shown before accept; a truncated reading cannot be accepted"
  - "[ ] 3. The analysis copy holds only the columns the accepted contract names, each classified by a person; nothing personal stored for analysis or sent to a model"
  - "[ ] 3a. A full-grid reader over the kept original bytes under stated analysis bounds, refusing by name above them, never a partial copy (W3, before 2a)"
  - "[ ] 3b. The hash-verified accessor and the scope the client-data step runs under (W3)"
  - "[ ] 4. Deterministic computations per shape: descriptive tables and benchmark gaps"
  - "[ ] 5. Admission and the client-reported grade in domain/evidence, and the report's marks"
  - "[ ] 6. A client's own survey: its own Sociomap through the existing engine, never merged"
  - "[ ] 7. The Lead and the analysis modules see only admitted client-reported results, never rows"
  - "[ ] 8. Brief materials pick a client dataset; `brief_signature` and `design_material` carry the source id and the contract version, with one fixture for Python and TypeScript"
  - "[ ] 9. The client-data steps placed in the run: a graph node, a contract-version pin on the run, an impact root, and which run's report prints them; class and lineage for client-reported numbers sent to a model"
  - "[x] 8a. W0 proposed Brief-material/signature interface and shared fixture; uploaded datasets remain ineligible until an accepted data contract exists"
  - "[ ] 10. The data contract accepted in the study's Brief drawer with its quality report; the Data tab shows the accepted contract read-only (D-37)"
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
  (`_declared`, `domain/evidence/instrument.py:184-196 @ 085abe0`, `ARCHITECTURE.md` §4).
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

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**Chunk 0, amended (G51, X5).** A client number has no respondent n or effective n, so `assess_support` suppresses it ("support unknown: n or effective n missing"), and `MetricKind`/`MetricUnit` have no count, amount or rate kind: the AC-10 dataset (visits by branch and month) would be suppressed or refused whatever policy source chunk 0 picks. Chunk 0 (and the ADR 0027 amendment it produces) also decides (a) the support a client aggregate or record count carries (exact counts or row count as n, or an explicit "not a sample" status, never an invented effective n), (b) the metric and unit set a client number may take beyond mean, pct and n, (c) when an interval is required; chunk 5 and `evidence-integrity#8b` name it. Test: the AC-10 dataset is admitted client-reported, and a row with no declared support is refused by name.

**2a. The data quality report (G52, X6).** ADR 0027 decision 4 makes code's quality report part of what the person accepts, and the architecture has a `quality_report` column, but no chunk computes it. A pure `client_data.quality_report(contract, rows)` (missing, duplicate and out-of-range counts per used column, `QUALITY_VERSION`, canonical SHA-256), stored on the contract and shown before accept. It reads every row, so 3a comes first. A source whose reading carries `rows_bound` or `sheets_bound` is refused by name, never reported as complete. Test: duplicates, blanks and an out-of-range value are counted over a dataset larger than the preview, and a truncated reading cannot be accepted.

**3a and 3b. Where the analysis copy's rows come from (G52, X7).** The only stored dataset rows sit in a reading cut at 250,000 characters (PARTIAL, `text_bound`), the grid reader is itself bounded, and `ClientSourceRepository` reads only through a `ClientContext` (a `StudyContext` is a separate class), so a copy built from the reading would silently total a truncated dataset and `client_data_prepare` has no accessor. 3a: a full-grid reader over the kept original bytes, not the stored reading, under stated analysis bounds, refusing by name above them and never keeping a partial copy. 3b: the hash-verified accessor and the scope `client_data_prepare` runs under (the client-work context pattern, or a StudyContext read of the client's copy). Test: a CSV over 250,000 characters is copied whole or refused with a named reason, never totalled partial.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** 10 (W3, with 2 and 2a), D-37; it replaces `client-workspace` C8's "V AIA zatím není".

**Existing chunks, changed.** 0 (G51): the methodology owner decides a client number's support,
metric and interval (packet MQ-18).

## Findings (the coordinator's card review, 2026-10-20)

Found on the UI workbench at develop `237fd0a` (screenshots by the coordinator), anchored at
`242523e`. For the docs PR to number in `open-items.md`. Reproduction: `make ui-workbench` with
in-process scripted model answers and `AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`,
unless stated.

- **CR-4. A client with DATASET or FINDING knowledge cannot run any AI design job.**
  Anchor: `domain/research_agents.py:688-690` (the placeholder lineage
  `unclassified-client-knowledge`), `domain/licence.py:158-164`, no such entry in
  `domain/licence_determinations.py @ 242523e`; `knowledge_entries` (`research_agents.py:545-562`)
  carries no lineage. Reproduce: `make seed-develop`, then any design job for Horizont Mobility:
  refused `licence_dataset_unknown`. Consequence: the seeded client, and any real client with a
  dataset or finding, gets no AI help, though only titles and summaries reach the model. Smallest
  fix: the lineage is the union of the items' recorded datasets (`provenance.datasets`), the
  placeholder only when one is unrecorded; the seed records `aia_synthetic_fixture`. Test: a design
  job over a seeded client with DATASET knowledge passes the licence gate; one over an item with no
  recorded dataset is still refused by name.

## 8a, delivered as a proposal (2026-10-21, branch `feature/w0-n-authority-population-double`)

**What is built** (the proposed interface; ADR 0027 stays Proposed, nothing stores a contract):

- `packages/aia_core/src/aia_core/domain/brief_materials.py` (`BRIEF_MATERIALS_VERSION =
  "aia-brief-materials-0-proposed"`). A Brief names a client dataset in `briefing.materials`, beside
  the legacy `briefing.attachments`, as a closed `BriefMaterial`: `kind: "client_dataset"`,
  `source_id` (`SRC-` + 16 hex, the client's source), `reading_sha256` (the reading the person
  picked, as `client_sources.reading_sha256` stores it: a newer reading is another material) and an
  optional `contract_id` + `contract_version` (both or neither: an intent, not an acceptance). The
  Brief holds no row, column or file.
- **Eligibility is computed, never stored.** `eligibility_of(material, accepted)` over the
  `AcceptedContract`s the server holds (chunk 2 will produce them; nothing does today):
  `no_contract` (visible as a source, unavailable to analysis), `contract_not_accepted`,
  `contract_stale` (another version, source or reading) or `eligible` only for an acceptance of
  exactly that source, reading and version. `read_materials` refuses an entry carrying any other
  field (`unknown_field`: an `eligibility` or `admitted` the browser wrote is never read past).
- **The signature.** `design_items.brief_signature` and the web's `briefFingerprint` sign
  `materials` (`material_signature` / `materialSignature` in `apps/web/src/research/
  brief-materials.ts`): per entry the source, reading and named contract, in the person's order,
  null for a non-object, **never an eligibility**. Only a non-empty list is signed, so every brief
  signed before materials keeps its signature byte for byte (the existing four shared cases are
  unchanged). Six cases added to the one shared fixture,
  `packages/aia_core/tests/fixtures/design_items/cases.json` `brief_signatures`, read by
  `test_design_items.py` and `proposal-diff.items.test.ts`; among them an entry claiming
  eligibility signs exactly as one that does not.
- `design_material` shows a model the material's ids and hashes as the Brief stores them, never
  rows (`test_brief_materials.py::test_the_design_a_model_is_shown_names_the_dataset_never_its_rows`).

**Tests.** `packages/aia_core/tests/test_brief_materials.py` (no dataset eligible without an accepted
contract; exact-match acceptance; a self-declared eligibility refused by name; the signature carries
none and old briefs keep theirs), `test_design_items.py::test_the_brief_signature_is_the_browsers`
and `proposal-diff.items.test.ts` "briefFingerprint signs a brief as brief_signature does" over the
new cases.

**Still to do, not claimed by 8a.** The review with S1 before `research-lead-workbench` 18 builds
the Brief picker on it; chunk 2's contract type, its accept route and the `client_data_contracts`
table (migration lane M8) that would hold `AcceptedContract`s; chunk 8, which adopts the reviewed
interface and pins the contract version on the run; chunk 9, the run node. Until then the Brief UI
may list a dataset as the client's source and must say it is not available to analysis.

## Doc follow-up (8a)

- `CLAUDE.md` §2, `domain/`: `brief_materials.py` -- the Brief's materials (proposed, chunk 8a): a
  client dataset named by source, reading and intended contract; eligibility computed from accepted
  contracts, never stored; none eligible before chunk 2. `design_items.py` `brief_signature` and
  `src/research/brief-materials.ts`: `materials` signed only when present, never an eligibility.
