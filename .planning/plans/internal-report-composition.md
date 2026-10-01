---
status: in-progress
chunks:
  - "[x] Compose an internal draft from a complete reconstructed analysis run"
  - "[ ] Store the DOCX as a Study artifact with source provenance and review state"
  - "[ ] Add Study-scoped listing and download after a reviewer can inspect the draft"
  - "[ ] Wire the report into the research results stage and verify a full live run"
---
# Internal report from admitted analysis

Owner: Codex. The user asked for a working AIA research journey and AIA-branded
research output. This feature turns the already implemented report renderer into
a faithful internal draft over the native analysis results. It does not infer
client approval or convert internal synthetic evidence to client-facing claims.

## Slice 1 contract

`compose_internal_report` accepts the Study-scoped `reconstruct_run` result,
which has re-read the run's sources and re-admitted every claim. It requires all
eight modules, the internal claim surface, one common evidence table and source
set, consistent method status and labels, and an unapproved internal ReportMeta.
The eight chapters preserve each module's exact admitted summary, answers and
findings. Each numerical claim is cited through the report ledger; suppressed
rows stay suppressed. The audit appendix records the run and each stored module
fingerprint. A synthetic-respondent limitation is printed explicitly.

The output is a `ReportDocument` and the existing AIA DOCX renderer can render
it. This slice deliberately does not create a durable artifact or expose a
download action; those require the Study report workflow and review state.

## Verification

The existing native-run integration fixture executes and stores all eight
analysis modules, reconstructs them through the evidence gate, composes the
report and renders a lint-clean DOCX. It checks that an incomplete run and a
module with a client-facing input surface are refused. The analysis-result and
report-template suites pass together (47 tests). Strict mypy, Ruff and format
checks pass for this slice.

## Doc follow-up

After the artifact/download work is verified, update the shared research
journey and architecture status in a separate docs-only PR, including the
internal-draft boundary, review state and client-facing report prerequisites.
