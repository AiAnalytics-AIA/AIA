# Duplicate implementation generations

**Evidence mode: MANIFEST.** Everything here is derived from filenames and paths
in the committed manifest. Filenames are strong evidence that *a family of
generations exists*; they are no evidence at all about *which one is live*, *what
changed between them*, or *which the tests target*. Those three questions need
the tree and are listed as open questions per family.

Purpose of this document: prevent **false inflation of requirements**. If three
generations of a report generator exist and only one is live, the rebuild owes
one capability, not three.

## Version lineage of the prototype as a whole

The manifest shows a release history spanning **v17.x to 18.6.6**, with
`docs/history/` retaining superseded releases:

- 43 `FINAL_RELEASE_*.md` — 18_6_0 … 18_6_6 plus historical 17_x
- 28 `FINAL_ACCEPTANCE_*.json` — acceptance records per release
- 6 `FINAL_FILE_MANIFEST_*.csv` — the prototype's own per-release file manifests
- 6 `HANDOFF_VERIFICATION_17_8_*.json`
- 3 `SHA256SUMS_*.txt` — prior integrity records
- `audit_reference/release_history/` — `PACKAGE_MANIFEST_v17_1_2 … v17_3_1`

**This is materially useful and should not be discarded.** The prototype kept its
own acceptance and manifest records per release. `FINAL_FILE_MANIFEST_18_6_6.csv`
is very likely the prototype's own authoritative inventory of its final release,
and `FINAL_ACCEPTANCE_18_6_6.json` its own statement of what it considered
verified. Both should be read first when the tree arrives — they may answer
questions this package would otherwise have to reconstruct.

> **Open question G0.** Does `FINAL_FILE_MANIFEST_18_6_6.csv` agree with the
> committed `reference-manifest.json` (1324 canonical files)? A disagreement
> would mean the two snapshots are not the same delivery. This is the first
> reconciliation to run when the tree is available.

## Confirmed asset generation families

### G1 · Full synthetic population panel — 3 generations

| Generation | Path | Zone |
|---|---|---|
| v17_0 BASE | `audit_reference/FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz` | audit_reference |
| v17_1_2 | `FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz` | root |
| v17_4_0 | `FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz` | root |

All three are canonical, hashed entries — see `data-asset-ledger.md` for hashes.

**Open questions.** Which generation does the running system load? Is v17_0_BASE
retained as a calibration baseline, a holdout, or simply history? Do the three
share a schema? Is v17_4_0 derived from v17_1_2 by a script in the tree, or
independently generated? Until answered, **all three must be preserved** — a
baseline used for validation is not redundant with the panel used at runtime.

### G2 · Coherence audit — 2 generations
`COHERENCE_AUDIT_v17.csv`, `COHERENCE_AUDIT_v17_1.csv`

### G3 · Dimension evidence registry — 2+ generations
`DIMENSION_EVIDENCE_REGISTRY_v3.csv` and at least one sibling. A *registry* of
evidence per dimension is methodology, not data — it is a priority read.

### G4 · Calibration reproduction
`CALIBRATION_REPRODUCTION_CHECK_v17_1.csv` alongside `CALIBRATION_REGISTRY.csv`.
The existence of a *reproduction check* implies the prototype had a notion of
reproducible calibration — a strong candidate for a numerical parity contract.

## Families that the task brief expects but which cannot be confirmed here

The brief anticipates multiple generations of report generators, provider
routers, simulation engines, Sociomapping implementations, UI generations and
persistence layers. **None of these can be confirmed or denied from the
manifest**, because Python module names in this prototype are not version-suffixed:
the manifest shows single names such as `project_pipeline.py`, `job_store.py`,
`ai_router.py`, and generation-vs-generation duplication inside or beside them is
invisible without reading the code.

Detecting those families is a tree-dependent task. The method is recorded in
`capability-map.md`.
