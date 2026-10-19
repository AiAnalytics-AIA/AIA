---
status: planned
chunks:
  - "[ ] 1. The USD 25 allocation: a ceiling per category, summed and checked before any recorded run"
  - "[ ] 2. The study's fixed inputs, fictional and committed: brief, client document, dataset with one personal column, a web page, a past study"
  - "[ ] 3. The harness: tests/acceptance driven over HTTP, reusing the scripted-provider fixture of test_product_acceptance.py"
  - "[ ] 4. Recorded doubles behind the gateway and the retrieval gate for the Lead, every worker, respondents, analysis and Deep Research"
  - "[ ] 5. Criteria wired one by one as each becomes runnable, the built ones first (AC-01, 06, 07, 12, 14)"
  - "[ ] 6. The acceptance record: one PASS/FAIL line per criterion, stored as an artifact, with the parity report beside it"
  - "[ ] 7. Tier B: the live run on develop, its runbook and its record"
---
# The MVP acceptance harness

Track A of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`docs/migration/mvp-acceptance.md` (`MVP-ACCEPT-2`, #495) and `mvp-cohesion.md` F7 and F10 (#496).
**Owner: a chat session, named when chunk 1 starts.** This plan builds the test the document
defines; the document stays the definition.

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
3. **Harness.** `tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`, never
   runtime-skipped as a placeholder. Decide here whether it shares `conftest` fixtures with the
   executors' tests or has its own; either way one provider double.
4. **Doubles.** One recorded exchange per model call kind and one per retrieval, deterministic,
   each stating that it is a recording, behind `GovernedModelGateway` and `RetrievalGate`, never
   around them.
5. **Wiring.** A criterion lands when its work does. The first batch rests on built work: AC-01
   (scope, 404), AC-06 (worker killed), AC-07 (impact preview), AC-12 (project memory), AC-14 (typed
   config). Each later criterion arrives with the integration gate that makes it runnable
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
