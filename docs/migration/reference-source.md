# Reference source

The legacy NPC Panel reference is **not in this repository** and must never be
copied into it. It lives in a dedicated private repository.

## Authoritative reference repository

| | |
| --- | --- |
| Repository | **`AiAnalytics-AIA/AIA-reference`** (private) |
| Immutable tag | `reference-18.6.6-gemo-2026-09-11-v1` |
| Entry point | `HANDOFF.md` at the repository root |

**That repository is authoritative for all reference interpretation.** Questions
about what the old system did, what methodology it encoded, which dataset
version it used or what parity is required are answered there, not here and not
from anyone's local machine.

## Reference snapshot identity

| | |
| --- | --- |
| Version | `18.6.6 + GEMO patch 2026-09-11` — the patch as delivered |
| Archive | `NPC_PANEL_18.6.6_CURRENT_DEMOS_UPDATED_GEMO_REPUTACNI_SCENARE_2026-09-11_FULL (1).zip` |
| **SHA256** | **`86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216`** |
| Size | 52,606,090 bytes |
| Files | 1,565 (70,981,764 bytes uncompressed) |

**The ZIP is the snapshot authority.** Two things are *not*:

- **The extracted tree**, because it is mutable — running the reference rewrites
  its `data/*.sqlite` state files. An earlier audit pass hashed the tree and had
  to be corrected.
- **The prototype's own manifests**, because it ships five disagreeing
  `FINAL_FILE_MANIFEST_18_6_*` generations (1,767 down to 1,455 entries) and
  **34 shipped files that none of them can verify**, including `ui_server.py`
  and all 162 of its routes.

## Obtaining the archive

The archive is **withheld from the reference repository** pending a licence
decision: the population derives from PIAAC 2023 CZ and ISSP 2022 CZ licensed
research microdata, and the stated architecture requires EU-resident object
storage, which GitHub Releases do not provide. See
`publication-safety-report.md` in the reference repository.

```bash
git clone https://github.com/AiAnalytics-AIA/AIA-reference.git
cd AIA-reference

# Validates the whole specification with no archive and no network:
python3 tools/verify_reference_inventory.py          # 40 checks

# With the archive, once its location is resolved:
export AIA_REFERENCE_ARCHIVE_URI=s3://<eu-bucket>/<key>   # preferred
# or
export AIA_REFERENCE_LOCAL_ZIP=/path/to/reference.zip
./tools/bootstrap_reference.sh                       # fetch, verify, 42 checks
```

## `AIA_LEGACY_REFERENCE` contract

The parity suites in this repository read the reference from this variable:

```bash
export AIA_LEGACY_REFERENCE=/path/to/extracted/reference/tree
make test-parity
```

Rules:

1. **Absent is valid.** Every parity test skips cleanly when the variable is
   unset, so a normal clone and CI stay green. `make test` never requires it.
2. **Treat the tree as read-only.** Run anything that executes the reference
   against a disposable copy — execution rewrites its SQLite state.
3. **Never commit the tree or the archive.** `.gitignore` excludes it; the
   reference is a sibling checkout or a bootstrap-managed directory.
4. `bootstrap_reference.sh` prints the correct value to export.

## `AIA_REFERENCE_REPO` contract

The population parity suite (`packages/aia_core/tests/test_population_reference_parity.py`)
reads the **repository**, not the archive: `field-policy.json`,
`dataset-ledger.json` and `golden-fixtures/F10_*` / `F11_*`.

```bash
git clone https://github.com/AiAnalytics-AIA/AIA-reference.git ../aia-reference
export AIA_REFERENCE_REPO=../aia-reference     # optional; ../aia-reference is the default
make test-parity
```

Same rules as above: absent is valid and every test skips; nothing from it is ever
copied here. The production contract (`aia_core.domain.population.czech`) pins the
field dictionary by SHA256 and the ordered field names by fingerprint instead of
carrying the 400 names, and this suite is what proves the pins still match.

The evidence-governance parity suite
(`packages/aia_core/tests/test_evidence_gate_parity.py`) reads the machine-readable
exports of the private reference *repository* — `field-policy.json` and
`methodology-ledger.json` — from this variable:

```bash
git clone https://github.com/AiAnalytics-AIA/AIA-reference.git ../aia-reference
export AIA_REFERENCE_REPO=../aia-reference     # the default when unset
pytest packages/aia_core/tests/test_evidence_gate_parity.py
```

Same rules again: absent is valid and skips cleanly, the
checkout is read-only, and nothing from it is committed here. The field policy in
particular is **supplied at runtime** with the population version it describes; it
is never vendored.

The simulation parity scaffold (`packages/aia_core/tests/test_simulation_parity.py`)
reads `golden-fixtures/F13_simulation_world_inoculation.json` from the same
checkout. F13 is not captured yet (`REF-GAP-SIMULATION-WORLD-MODEL`), so it skips
and says so.

## Do not duplicate raw assets into this repository

This repository is the clean production rebuild. It must not absorb:

- the 52.6 MB reference archive
- the three population panels (~22 MB compressed)
- `demo_library/` (32 MB) or `audit_reference/` (7.3 MB)
- any legacy source tree

`docs/migration/reference-manifest.json` is the only integrity artifact kept
here, and it is deliberately small: hashes plus the migration module list,
derived from the authoritative ZIP so CI can verify module coverage without the
reference present.

## Reconciliation note

`docs/migration/reference-manifest.json` previously recorded **1,324 files
derived from the mutable extracted tree**, with no archive hash, and described
itself as "the only integrity record" for the reference. It has been regenerated
from the authoritative ZIP: **1,324 canonical files of the archive's 1,565**, and
**191 migration modules**, carrying the archive SHA256 and a pointer to the
reference repository.

Regeneration is archive-only. `tools/reference_manifest.py write` refuses to run
without `--archive`, because a tree-derived write cannot supply the archive hash,
the repository identity or the module list and would therefore downgrade the
manifest schema — the defect that produced the stale manifest. The refusal, the
schema gate and the committed artifact are all asserted by
`packages/aia_core/tests/test_reference_manifest_schema.py`.

## What the reference repository contains

| Concern | Document |
| --- | --- |
| Start here | `HANDOFF.md` |
| The product, by capability | `rebuild-contract.md` |
| Parity for all 78 capabilities | `parity-plan.md` |
| Methodology and where it is enforced | `methodology-ledger.md` |
| The core runtime dataset | `population-subsystem.md`, `data-import-contracts/czech-population.md` |
| Sociomapping mathematics | `sociomapping-reference-contract.md` |
| Simulation mathematics | `simulation-reference-contract.md` |
| Frontend research logic | `ui-capability-ledger.md` |
| What could corrupt research truth | `high-risk-behaviors.md` |
| Executable fixtures | `golden-fixtures/manifest.json` |
| Environment assumptions | `runtime-environment.md` |
| Open product decisions | `open-decisions.md` |
| Outstanding fixture gaps | `reference-gaps.md` |

## Golden fixtures in CI — no archive needed

The eleven golden fixtures are committed JSON in the reference repository and
**do not need the archive**. Two routes carry them into CI:

- **F1–F9 are vendored** (next section) and run in every backend job.
- **F10–F11 are read from a reference checkout.** CI's `golden-fixtures` job
  checks the reference repository out at the commit pinned in
  [`parity-matrix.json`](parity-matrix.json) (`reference.commit`) with a
  read-only deploy key held as the `AIA_REFERENCE_DEPLOY_KEY` secret. The same
  job checks that the reference's fixture manifest and parity plan hash to their
  pins, and that every vendored copy is byte-identical to the fixture it copies.

Locally, a sibling clone at `../aia-reference` or `AIA_REFERENCE_REPO` does the
same: `make test-golden`.

The pin is a **commit**, not the tag: the tag points at `90d4c5b`, two commits
behind `678e298`, and differs from it only in two tool scripts.

## Known open items owned elsewhere

| Item | Owner |
| --- | --- |
| `REF-GAP-SOCIO-R-SMACOF` — needs R + `smacof` **and** the reference's withheld R wrapper; open as OI-15, no R parity claimed | parity-quality + A8 sociomapa-deterministic |
| `REF-GAP-SIMULATION-WORLD-MODEL` — needs a provider credential, an ADR 0008 egress route **and** the withheld `full_simulation.py`; open as OI-27; status in [simulation-deterministic-engine.md](../architecture/simulation-deterministic-engine.md) §7 | parity-quality + A7 simulation-engine |
| `REF-WITHHELD-REFERENCE-ARCHIVE` — needs a licence decision | data owner |

Neither fixture gap is unknown behaviour: code paths, constants and seeds are
recovered. The simulation gap needs a different environment and, like the Sociomapping gap, the archive: its recipe runs the reference's `build_world_model` and `inoculate_population` (OI-27). The Sociomapping
gap turned out to need more than that: the R *recipe* runs the reference's own
`fit_unfolding` wrapper, which is in the withheld archive
(`.planning/open-items.md` OI-15).

## Golden fixtures vendored here

`golden-fixtures/F1`–`F9` (Sociomapping) are vendored under
`packages/aia_core/tests/fixtures/sociomap/`, byte for byte, each pinned to its
SHA256 in `index.json` against the reference commit it came from. They are
synthetic inputs with the reference's recorded outputs — not reference source,
not client data — which is what makes them the one kind of reference material
this repository may hold. One is renamed to satisfy `exposure_check` (see
`AGENTS.md`).
