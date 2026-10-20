---
status: planned
chunks:
  - "[ ] 1. The USD 25 allocation: a ceiling per category, summed and checked before any recorded run, covering fieldwork, analysis and its repairs, the Lead's turns, Deep Research search and tool spend and the second (Interpretation) run, a retry round; the evaluation allowance stated apart"
  - "[ ] 2. The study's fixed inputs, fictional and committed: brief, client document, dataset with one personal column, a web page, a past study"
  - "[ ] 3. The harness: tests/acceptance driven over HTTP, reusing the scripted-provider fixture of test_product_acceptance.py, and its CI step (collected, writing JUnit)"
  - "[ ] 4. Recorded doubles behind the gateway and the retrieval gate for the Lead, every worker, respondents, analysis and Deep Research"
  - "[ ] 5. Criteria wired one by one as each becomes runnable, the built ones first (AC-01, 06, 07, 12, 14)"
  - "[ ] 6. The acceptance record: one PASS/FAIL line per criterion, stored as an artifact, with the parity report beside it"
  - "[ ] 7. Tier B: the live run on develop, its runbook and its record"
  - "[ ] 8. Parity reports, never blocks (owner, 2026-10-19): the 18.6.6 comparison jobs stop gating merges and deploys and report in the step summary and the record"
  - "[ ] 9. The `acceptance` marker registered (`pyproject.toml` runs `--strict-markers`) and the tree collected by CI"
  - "[ ] 10. Browser evidence kept distinct from HTTP evidence: real browser journeys (hand edits, pointing, proposals, keyboard and focus, stale states, all eleven stages, map view-only operations) are their own line in the record and never counted as HTTP"
  - "[ ] 11. The Deep Research evaluations 25, 26 and 39 before the final live chunk 27, and the second live Interpretation run, are in the tier B record and its allocation"
  - "[ ] 12. Production release is a blocker: the record states I-5 as not passed until the production release checklist is done, whatever tier B showed on develop"
  - "[ ] 13. Every prototype scenario (A to M, X1 to X7) is an acceptance journey on recorded doubles; X2 (missing evidence) and X6 (a methodology change refused) stay as negative cases"
  - "[ ] 15. The assumptions and open-answer coding journey (W5, MVPQ-02) with its refusals, over recorded doubles: `assumptions-and-open-answer-coding#AOC9`"
  - "[ ] 14. The acceptance wording reconciled in the acceptance document and `parity-matrix.json` together, in a PR that runs the tests: AC-02 (approval card and plan), AC-11 (OPEN posture), AC-13 (F17), AC-15 (separate model, tool, reservation, uncertain and billing-lag lines; the USD 0.01 tolerance kept unless the owner changes it)"
  - "[ ] 16. The per-number provenance walk for AC-15: every ledger ref of both reports resolves to its model binding, prompt pin, population version and weight role (G65)"
  - "[ ] 17. The acceptance verdict computed from its own JUnit, path parity beside it and never in it; parity-matrix project.memory corrected (G75)"
  - "[ ] 18. Performance budgets as a release gate: page and API latency budgets per journey (D-48; the numbers are open)"
---
# The MVP acceptance harness

Track A of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`docs/migration/mvp-acceptance.md` (`MVP-ACCEPT-2`, #495) and `mvp-cohesion.md` F7 and F10 (#496).
**Owner: a chat session, named when chunk 1 starts.** This plan builds the test the document
defines; the document stays the definition.

**Depends on [#495](https://github.com/AiAnalytics-AIA/AIA/pull/495) merging first.** The
criterion ids below are `MVP-ACCEPT-2`'s. The checked-in `MVP-ACCEPT-1` numbers them differently
(its AC-07 is the worker kill and its AC-12 is configuration; its AC-14 is the parity gate that
MVP-21 removes), so this plan is wrong against `develop` until #495 lands.

## What the document defines (not repeated here)

Fifteen criteria; two tiers, both required for release: **A** in CI over HTTP on recorded doubles
behind the gateway and the retrieval gate, blocking once runnable; **B** a live run on develop
within USD 25 by a person. Every fixed input is committed with the test. No back door: no
repository, domain function or table is touched directly.

## What exists

- A walk of product scenarios over HTTP with the real worker, the stored report and a scripted
  Bedrock (`scripted_bedrock`): `apps/executors/tests/test_product_acceptance.py` (PC11), plus
  `apps/executors/tests/test_sociomap_acceptance.py`. **Extend their fixtures; do not build a
  second scripted provider.**
- Recorded retrieval doubles exist only in `aia_executors/deep_research_recorded.py`, local and
  test (`ARCHITECTURE.md` §3); `test_deep_research_journey.py` drives them.
- `parity_status.py` reports `MVP-ACCEPT-2` as `NOT_RUNNABLE` until the file exists
  (`mvp-acceptance.md` §5, #495).

## Chunks

1. **Budget.** A table, in this plan, of each category's ceiling against the USD 25 of MVP-20:
   fieldwork (`domain/run_cost.py`, an upper bound, n = 300), analysis with repairs, the Lead's
   turns and each worker, live Deep Research (its own pinned allowance, ADR 0022), the report
   writer and map interpreter. **`run_cost.py` covers fieldwork and analysis only** (hypothesis from
   the CLAUDE.md map; confirm in the chunk), so the other lines need their own bound. If the sum
   exceeds 25, the owner chooses a smaller n or a larger budget now, not after tier B.
2. **Inputs.** The brief and the five fictitious concepts from `mvp-acceptance.md` §1; a fictional
   annual summary, a fictional visits dataset with one personal column the contract must drop, one
   public page, one past fictional study; all pinned by SHA-256 like the golden fixtures. No client
   data, no client names (`tools/exposure_check.sh` must pass).
3. **Harness and its CI step.** `tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`,
   never runtime-skipped as a placeholder. Decide here whether it shares `conftest` fixtures with
   the executors' tests or has its own; either way one provider double. **No CI command collects
   `tests/acceptance` today**: the collect-only pass and every pytest step name only
   `packages/aia_core`, `apps/api`, `apps/worker` and `apps/executors`
   (`.github/workflows/ci.yml:200, 208-251 @ 085abe0`), so a green CI would say nothing about it.
   This chunk adds the tree to the collect-only pass and gives it a step of its own that writes
   `--junit-xml … -o junit_family=xunit1`, which `parity_status.py` reads and
   `test_parity_matrix.py` requires of every pytest step (`AGENTS.md:248-251 @ 085abe0`). Test: a deliberately
   failing acceptance test turns CI red, and a skipped one reports `NOT_EXECUTED`, not green.
4. **Doubles.** One recorded exchange per model call kind and one per retrieval, deterministic,
   each stating that it is a recording, behind `GovernedModelGateway` and `RetrievalGate`, never
   around them.
5. **Wiring.** A criterion lands when its work does. The first batch exercises existing paths for AC-01 (scope, 404), AC-12 (project memory) and AC-14 (typed config). AC-06 requires RQC0's fieldwork checkpoint/kill proof and AC-07 requires WCE7's working-revision impact path; collecting older tests for them does not prove the stronger MVP obligations. Each later criterion arrives with the integration gate that makes it runnable
   (`mvp-cohesion.md` §4: I-1 to I-4).
6. **Record.** One line per criterion, `PASS` / `FAIL` with the observation that decided it, stored
   as an artifact of the study with the reports, approved map snapshots and their approval records,
   and the `parity_status.py` report from the same commit as information (MVP-21).
7. **Tier B.** The runbook for a person on develop: the live providers, the Class B route, the
   AWS-tagged spend check (`develop-spend-attribution`), the record. Run before every MVP release.

## Depends on / feeds

Chunks 1-3 can start now. Chunk 5 follows each track's gate (I-1 Lead drives a study, I-2 results
seen, I-3 evidence complete, I-4 Deep Research live). Chunk 7 needs `class-b-search-route` and
`develop-spend-attribution`. This plan ticks, from its single record, the "deploy and verify live"
chunks the consolidation lists (`mvp-consolidation.md` §4.3, #493).

## Doc follow-up

`CLAUDE.md` §3 (the command for the acceptance suite, once it exists), `docs/migration/mvp-acceptance.md`
§5 (the location, once chosen).

## Chunk 8: parity reports and never blocks

**Decision.** The owner decided on 2026-10-19 that parity runs and reports but never blocks
(`mvp-cohesion.md` F9, Q28). Written against `develop` @ `de6ded8`.

**What changes.** Every job that compares AIA with 18.6.6 (`parity`, `oracle-parity`, and the
reference-repository steps of `golden-fixtures`, `.github/workflows/ci.yml`) is non-gating: its failure
is written to the step summary and to the JUnit artifact, `tools/parity_status.py` still prints
`FAIL`, and it exits 0 in CI (a `--report-only` flag, not a changed default, so a person running it
locally still sees a failing exit). `dispatch-develop`'s condition drops those jobs. A parity `FAIL`
also appears as one line in the acceptance record (chunk 6).

**What does not change.** `test_parity_matrix.py` (the matrix describes itself correctly), the vendored
Sociomap golden fixtures F1-F9 and every non-parity test stay blocking. Nothing is skipped or loosened:
the tests still run and still fail loudly in their own job.

**Cost, stated.** A regression against 18.6.6 can now merge and deploy; the protection is that the
report is read. The record's parity line and the PR summary are the only places it shows.

**Test.** A CI-script test feeds `parity_status.py --report-only` a JUnit file with a failing parity test
and asserts exit 0 and a `FAIL` line, and a matrix-consistency failure still exits 1.

## Added by the master plan (2026-10-19)

- **9.** The `acceptance` marker is unregistered under `--strict-markers` (`pyproject.toml:276-282`), so the
  tree would not collect. Gap G10.
- **10.** Tier A is "over HTTP". The workbench, Lead and artifact journeys run in a browser
  (`tools/ui_workbench/*_journey.mjs`); the record keeps them as a separate line so a browser pass is never
  read as an HTTP pass and the reverse.
- **11.** Chunk 7 (tier B) depends on the Deep Research route: the first release's route is Brave for an
  OPEN client (`deep-research-web-search` 53). Evaluations 25, 26 and 39 run before chunk 27
  (`deep-research-web-search`, "Evaluations before the final live run"); the second live run that "cited
  context in the report" needs (`contextual_report.py:985`) is added to AC-11's allocation. Gap G38.
- **12.** `mvp-development-plan.md` §8 said a production release "can follow the acceptance without moving
  the gate"; gate I-5 says "production released". I-5 stands: production is a blocker.
- **13.** The twenty scenarios of `prototypes/research-lead-v2` are the behaviour spec. X2 and X6 are
  central invariants (evidence that is missing says so; a methodology change is refused in place and
  routed to Metodika) and cheap to test on doubles, so they are not deferred. The scenario order is a
  build order, not a release scope.
- **Wording to reconcile, in a PR that runs the tests** (`docs/migration/` and `parity-matrix.json` are
  outside the docs-only path list and `test_parity_matrix.py` reads the matrix): AC-02 "a paid worker job
  starts only on an approval card" against the wallet and the plan card; AC-11 "approved for Class B"
  against the OPEN posture; AC-13 "a reviewer other than the producer" against F17 (withdrawn).

- **14.** The wording that disagrees with settled decisions is changed in the acceptance document and the
  machine criteria in one pull request that runs `test_parity_matrix.py` (those files are outside the
  docs-only path list). **AC-15's reconciliation is stated as separate lines**: model usage in the ledger,
  tool and search spend, reservations, uncertain calls, cloud-billing lag and non-provider infrastructure
  charges; a number never reads as zero because it is unknown. The edit is on `chore/acceptance-reconcile`.


## Incremental gates and full acceptance (2026-10-20)

W0 builds 1-4, 8-9 and 14. W1-W4 extend 5, 10 and 13. W5 finishes 6-7 and 11-12.
RQC10's population double lands before the W1 HTTP path. Do not give an unimplemented criterion
a passing placeholder: record PASS / FAIL / NOT_EXECUTED / BLOCKED with reason and evidence.

I-1 covers the available design workers, not all eleven workers; I-3/W3 adds LO9b and the eight
analysis prompt pins. Only final tier A can report AC-03 PASS for all of them. Browser proof grows
per artifact, and all eleven artifacts must pass before the release record. W0 tree collection,
partial I-1 coverage, live I-R probes, final tier B and production are distinct evidence classes.

The record pins the tested application SHA, plan/acceptance versions, fixture hashes, model and
prompt identities, deployment/composition and effective policy. It includes criterion/negative-case
id, expected/actual behavior, evidence artifact ref and cost/reservation/uncertainty lines. For a
changed input, method, contract, prompt or deployment, identify which evidence must be repeated;
do not carry a green release decision from an older SHA. Paid reruns still require their allowance.

**15. (2026-10-20)** The journey and refusals of `assumptions-and-open-answer-coding#AOC9` join the acceptance tree: an assumption created, evidence attached, status set by a person, shown in the report; open answers coded, counts admitted, shown in Results and the report; a status without support refused, counts never produced from prose, a codebook change that leaves fieldwork untouched. It runs on recorded doubles in tier A; the model coder, if any, is a recorded double.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** 16 (W3), 17 (W0, E01), 18 (W4; D-48 in, its budget values open in the baseline).

**Existing chunks, changed.**

- **3 (G76).** A declared operator bootstrap (`aia_executors.seed`, or production's
  `production-environment#PE10`), named in the record; everything after it over HTTP, the worker as a
  subprocess; an import-linter contract that `tests/acceptance` imports no application or
  infrastructure module.
- **5.** Its front matter's "the built ones first (AC-01, 06, 07, 12, 14)": only AC-12 is an existing
  path. Its wave: W5 (E24) governs.
- **6 (G77).** The record is per criterion per tier; each criterion carries its tier-A and tier-B
  projection, AC-15's AWS clause included.
- **10 (D-48).** Axe in every browser journey: a serious or critical violation fails it.
- **11 (D-11).** The acceptance study cites one known dead URL.
- **14.** AC-01 reads "a user of another organization gets 404, not 403, on every study route"
  (ADR 0019; G73). AC-14 reads "typed settings refuse a malformed value by name; each run records its
  composition digest" (D-09, `lead-orchestration#LO12c`). The three 18.6.6 ledgers are refreshed and
  the L-04 / L-29 contradiction removed.
