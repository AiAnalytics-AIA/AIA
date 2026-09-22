# reference-rebuild-local

**STATUS: COMPLETED / INACTIVE.** Retired. No further AIA assignment, and no
future work may depend on it. This agent ran on a local workstation; that machine
is no longer required and must not be treated as a source.

Specifically, nothing may depend on a path under `/Users/…` or any other local
machine, on the local extracted reference tree, or on manual copy/paste of
reference material from the human. A question about the legacy system is answered
from `AiAnalytics-AIA/AIA-reference`, or it is not answered.

## What was delivered

The legacy reference now has a durable home:
**`AiAnalytics-AIA/AIA-reference`** (private, verified via the API).

| | |
| --- | --- |
| Repository | `AiAnalytics-AIA/AIA-reference` — visibility `PRIVATE` |
| Commit | `678e298ad9ca0263da53cc8920d153fdfb956c93` |
| Tag | `reference-18.6.6-gemo-2026-09-11-v1` |
| Release | `reference-18.6.6-gemo-2026-09-11-v1`, asset `SHA256SUMS.txt` (3,654 bytes) |
| Entry point | `HANDOFF.md` at the repository root |

**That repository is authoritative for reference interpretation.** No cloud
agent should depend on a local filesystem path.

### Reference snapshot identity

| | |
| --- | --- |
| Archive | `NPC_PANEL_18.6.6_CURRENT_DEMOS_UPDATED_GEMO_REPUTACNI_SCENARE_2026-09-11_FULL (1).zip` |
| SHA256 | `86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216` |
| Size | 52,606,090 bytes · 1,565 files |
| Version | 18.6.6 + delivered GEMO patch (2026-09-11) |

The ZIP is the authority. The extracted tree is **mutable** — running the
reference rewrites its `data/*.sqlite` files.

### Observed verifier results

| Run | Result |
| --- | --- |
| Clean clone, no archive | **40 passed, 0 failed** |
| Clean clone, with archive | **42 passed, 0 failed** (full re-hash of 1,565 files) |
| Bootstrap without archive | exit 3 with guidance, as designed |
| Markdown links from clean clone | 150 checked, **0 broken** |
| Local-path dependencies | **0** |

## Production pointer PR — needs review, not merged by me

**`AiAnalytics-AIA/AIA` PR #7** — `migration/reference-repository-link`,
head `f6d6a0598e0906ab7ed4094a38b3002048c1cf70`. Rebased onto `main@69a2874`.

Observed: **MERGEABLE**. CI **all 6 jobs success** on re-run (see defect note
below). Local: 523 passed / 116 skipped without the reference, 623 passed / 16
skipped with it; ruff and `mypy --strict` clean.

Contents: `docs/migration/reference-source.md` (the pointer), a reconciled
`reference-manifest.json`, and the module inventory plus its CI guard.

## Two findings other agents should act on

### 1. `reference-manifest.json` was hashed from the mutable tree

Now reconciled in PR #7: regenerated from the authoritative ZIP, carrying the
archive SHA256, 1,324 canonical files of 1,565 in the archive, and 191
migration modules.

**This affects `aia-reference-rebuild-package/` on `main`.** That package was
built in `evidence_mode: "manifest"` from the previous manifest
(`a3815c2b…`) without the archive present — it says so honestly, and its
content-dependent fields are correctly `null`. Rebuilding it against the
reconciled manifest, or simply deferring to `AIA-reference`, would establish
what it could not: the archive hash, the GEMO-patch layering, the 34 shipped
files no shipped manifest can verify (including `ui_server.py`), and every
finding that required reading a file.

### 2. Client-identifying filenames are in the PUBLIC repository

`AiAnalytics-AIA/AIA` is **public**. `aia-reference-rebuild-package/reference-file-inventory.csv`
on `main` contains **32 rows naming `GEMO` and 37 naming `MMC`**.

Observed scope: **filenames and hashes only** — no briefs, findings,
recommendations or report text. `Motol` appears in **0** rows. The `AURORA` /
`MEDORA` style names are fictional showcase brands and carry no risk.

Why it matters: `GEMO` is a real Czech construction company and the archive's
`GEMO_REPUTATION_DEMO` is *"reputace v kontextu kauzy Motol"* — reputation
research about a named company in the context of a named public controversy.
The public inventory associates that company name with reputation-scenario
filenames.

This is why `AIA-reference` is private. **Not actioned here**: removing it from
a public repository's history is a destructive, outward-facing change and is
the data owner's call. Full analysis in
`publication-safety-report.md` in `AIA-reference`.

## Transferred ownership

| Item | Owner | Blocker |
| --- | --- | --- |
| `REF-GAP-SOCIO-R-SMACOF` | parity-quality + sociomapa-deterministic | needs R + `smacof`; local host has no `Rscript` |
| `REF-GAP-SIMULATION-WORLD-MODEL` | parity-quality + simulation-engine | needs an authorized provider credential |
| `REF-WITHHELD-REFERENCE-ARCHIVE` | data owner | PIAAC/ISSP licence decision + EU-residency requirement |
| Population import | population-data | — |
| Reference interpretation | `AIA-reference` is authoritative | — |

Neither fixture gap is unknown behaviour: code paths, constants and seeds are
recovered, and both have a step-by-step recipe in `reference-gaps.md`.
`REF-GAP-SOCIO-R-SMACOF` notably has an input fixture ready
(`F4_python_unfolding_layout`) to run the R branch against.

## Withheld asset

The 52.6 MB archive is **not** attached to the release. Reason: the population
derives from PIAAC 2023 CZ / ISSP 2022 CZ licensed research microdata with an
unresolved licence question, and the stated architecture requires EU-resident
object storage, which GitHub Releases are not. Path, hash and transfer route are
recorded in `publication-safety-report.md` §4 and `reference-gaps.md`.

Nothing depends on its location: the 40-check validation runs from committed
JSON alone.

## Observed defect, not mine to fix

`test_workflow_concurrency.py::test_concurrent_reconcilers_recover_each_attempt_once`
failed once on PR #7's first CI run (`assert 5.0 == 10.0`, *"uncertain exposure
must be charged once per reservation, not once per reconciler"*) and **passed on
re-run**, all 6 jobs green. My PR touches only documentation plus one new test
file and nothing in the workflow engine.

I attempted local characterization against PostgreSQL and it was
**inconclusive** — my local instance did not give a clean baseline, so I did not
claim a deterministic failure. Flagging it because the assertion guards accounting
for possibly-billed provider calls, which is a money-correctness invariant.

**Resolved by `architecture-reconciliation`.** Root-caused as a lost update on
`studies.spent_usd`: `_charge_study` was an unlocked read-modify-write under READ
COMMITTED. Reproduced deterministically (8 concurrent charges recorded 1), fixed
with an atomic increment, regression test measured at 12/12 detection against the
old code. PR #8. Owner: platform-runtime.
