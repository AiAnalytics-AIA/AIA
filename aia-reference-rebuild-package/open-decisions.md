# Open decisions

Genuine product and architecture decisions only. Ordinary migration work does not
belong here.

---

## D-0 · BLOCKING · How does the reference reach this analysis?

**Issue.** The reference tree and the original ZIP are not present in the
environment. Every behavioural deliverable in this package — capability map,
methodology ledger, API ledger, UI ledger, dependency map, rebuild contract,
parity plan — is blocked on it. This is not a migration task; it is an input the
audit cannot proceed without.

**Evidence.** `docs/migration/status.md` states the prototype is deliberately not
vendored. `AIA_LEGACY_REFERENCE` is unset. No ZIP exists on the filesystem. All
94 parity and characterization tests skip for this reason, in this environment
and in CI.

**Choices.**

1. **Supply the tree to the analysis environment only** (a mounted path or an
   upload, never committed). Unblocks this package. Leaves CI parity still
   skipping — so OI-1 in the production repo remains open.
2. **Vendor the reference as a private submodule.** Unblocks this package *and*
   closes OI-1: CI could finally run the 94 parity tests. Costs a private
   dependency in the build, and puts the population panel behind a submodule
   fetch.
3. **Publish a fixture pack** — recorded prototype inputs and outputs rather than
   its source. Unblocks parity testing but **not** this package: a fixture pack
   captures behaviour at the boundary, and a rebuild contract needs the rules
   inside.
4. **Upload the original ZIP.** The only option that also establishes ZIP
   filename and SHA256 — the top-level identity of the delivery — and the only
   one that includes the runtime-generated output the manifest excludes.

**Consequence of not deciding.** The package stays at foundation level, and
1259 files stay `UNKNOWN_NEEDS_DECISION`. The clean-room standard in §31 of the
brief cannot be met: a competent team could not rebuild the product from what
exists today.

**Recommendation.** Option 4 for this audit, then option 2 for CI. They are
complementary, not alternatives: the ZIP is the forensic record, the submodule is
the test dependency.

---

## D-1 · Where do the population assets live in production?

**Issue.** Three generations of the full synthetic panel plus 18 special panels
are canonical reference assets. They are gzipped CSV in a flat prototype tree.
Production is PostgreSQL + S3 on AWS.

**Evidence.** `data-asset-ledger.md`; `reference-snapshot.json` →
`irreplaceable_runtime_assets_identified`.

**Choices.** S3 with versioning and a registry table in PostgreSQL · a dedicated
external data repository · PostgreSQL tables with the panel as rows · keep them
as immutable artifacts in the existing `ArtifactStore`.

**Consequence.** This decides whether a population revision is a database
migration, an object-store version, or an artifact row — which in turn decides
how audience filtering and population revisioning are implemented. It is a
data-architecture decision, not a file-placement one.

**Not to be decided silently.** Sizes are unknown (see the ledger), and size will
materially affect the answer.

---

## D-2 · Which population generation is authoritative?

**Issue.** `v17_0_BASE`, `v17_1_2` and `v17_4_0` all exist. Retaining all three
forever, or retiring two, is a methodology decision — a base panel may be a
validation baseline rather than history.

**Evidence.** `duplicate-generations.md` G1.

**Consequence.** Retiring a baseline that validation depends on would silently
change research truth. **Until answered, all three are preserved.**

---

## D-3 · What is the status of the prototype's own release records?

**Issue.** The reference carries its own manifests and acceptance records —
`FINAL_FILE_MANIFEST_18_6_6.csv`, `FINAL_ACCEPTANCE_18_6_6.json`, 43
`FINAL_RELEASE_*.md`, prior `SHA256SUMS_*.txt`.

**Evidence.** `duplicate-generations.md`, version lineage section.

**Choices.** Treat them as an authoritative second opinion to reconcile against ·
treat them as history to archive · treat them as the primary inventory and demote
the committed manifest.

**Consequence.** If `FINAL_FILE_MANIFEST_18_6_6.csv` disagrees with the committed
`reference-manifest.json`, the two are different snapshots and every parity
anchor in the production repository points at something other than the delivered
ZIP. **This must be reconciled before any parity claim is trusted** (open
question G0).
