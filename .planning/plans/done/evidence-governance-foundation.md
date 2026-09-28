---
status: done
chunks:
  - "[x] 1. Gate primitives + field policy"
  - "[x] 2. CORE_JOINT_STATUS certificate"
  - "[x] 3. Allowed analysis metrics + effective-n support"
  - "[x] 4. Validation status bound to a system fingerprint + tier gate"
  - "[x] 5. Permissible claim policy"
  - "[x] 6. AdmittedClaim capability + layer_check rule"
  - "[x] 7. Gate-decision parity suite"
  - "[x] 8. The eight analysis modules"
  - "[x] 9. Application runner"
  - "[x] 10. Documents in sync"
---
# Evidence and governance foundation, then the eight analysis modules

**Status:** done · **Owner:** analysis-governance · **Started:** 2026-09-22 · **Finished:** 2026-09-22

## Problem

The product's defining property is epistemic discipline, and the reference
enforces most of it as prose. Four facts from the private reference repository
(`AiAnalytics-AIA/AIA-reference` @ `678e298`) decide the shape of this work:

- **The field dictionary is enforced nowhere.** 400 fields carry an evidence
  status and a claim rule; 51 say *never measured fact*, and nothing stops one
  backing a client claim (`methodology-ledger.md` M02, `high-risk-behaviors.md` R5).
- **The allowed-metric set exists only inside a prompt string.** Rewriting the
  prompt silently widens what a model may claim (M17).
- **`CORE_JOINT_STATUS.json` is the one gate that fails closed** — cross-block
  relationships are not same-person truth, client joint outputs are forbidden,
  and the certificate degrades when the panel hash moves (M03, R6).
- **Suppression is fail-closed by default**: `support_status` defaults to
  `SUPPRESS`, cells under the Kish effective-n threshold are removed, not greyed
  (M16).

Reporting may not be built before any of this is enforceable, because reporting
is where an unsupported claim becomes a deliverable.

## Approach

A new pure bounded context, `aia_core.domain.evidence` (the *Validation &
Evidence* context in `docs/architecture/domain-map.md`), holding every gate as a
typed, deterministic function that returns a `GateDecision`. Then
`aia_core.domain.analysis` ports the eight modules against it, and
`aia_core.application.analysis` runs one module through a generator protocol
with the gate between the model and the result.

Four design decisions, and why the obvious alternative was rejected:

1. **Admission is a capability, like scope.** A claim reaches a result only as an
   `AdmittedClaim`, which only the evidence gate can mint (module-private
   sentinel, enforced by `layer_check`). The alternative — a boolean
   `passed_gate` on a claim — is a field somebody sets. This is what makes
   "prompt text must not be the sole enforcement mechanism" structural.
2. **Field policy is derived, then checked.** The policy book is built by
   re-deriving eligibility from the verbatim dictionary text with the reference
   derivation (`tools/build_field_policy.py` in the reference repo), and a stored
   policy document whose flags disagree with the re-derivation is refused. The
   alternative — trust the stored flags — lets a hand-edited JSON widen a claim.
3. **Unknown is never good.** An undeclared field, an unknown evidence status, an
   unknown metric, a missing interval, an unverifiable panel hash, an unknown
   tier: each blocks. Each is an INTENTIONAL_DIFFERENCE from the reference where
   the reference would degrade, and each has a test proving the new behaviour.
4. **The policy document is supplied, not vendored.** The 400-row policy is
   reference material bound to one population version; committing it here would
   put detailed reference content in this repository (`exposure_check`, D5). The
   domain parses the document format; the population version supplies the
   document at runtime; the parity suite reads the real one from the reference
   repository through `AIA_REFERENCE_REPO` and skips cleanly without it.

What the reference cannot tell us, and is therefore **not** invented: the
legacy source is withheld (`REF-WITHHELD-REFERENCE-ARCHIVE`), so `tier_gate.py`,
`validation_gate.py`, `core_joint._fallback()` and `factual_layer`'s keyword
detection are known only from docstrings, constants and thresholds. Where a
decision is documented, it is ported EXACT. Where only a name is documented, the
production contract takes the fail-closed reading, says so in the docstring, and
an open item records what the legacy-source parity run must confirm.

## Trade-off accepted

Stricter than the reference wherever the reference is silent or leaky — the
evidence gate requires 100% numeric coverage where `evidence_validator.py`
passes at 95% — so a draft the prototype would publish can be blocked here.

## Chunks

- [x] 1. Gate primitives + field policy: `GateDecision`, `Violation`,
      `EvidenceStatus`, `ProvenanceClass`, `ClaimRule`, eligibility derivation,
      `FieldPolicyBook` with fail-closed document parsing. EXACT parity against
      the reference `field-policy.json` for all 400 fields.
- [x] 2. `CORE_JOINT_STATUS` certificate: hash-bound loading with explicit
      degradation, joint-unit classification of fields.
- [x] 3. Allowed analysis metrics + effective-n support: `AnalysisMetric`,
      Kish effective n, `SupportStatus` defaulting to `SUPPRESS`, suppression by
      removal, reportable estimates that cannot exist without an interval.
- [x] 4. Validation status bound to a system fingerprint + tier gate.
- [x] 5. Permissible claim policy (measured vs modelled basis, joint
      restrictions) + factual layer contract.
- [x] 6. `AdmittedClaim` capability + `layer_check` rule.
- [x] 7. Gate-decision parity suite: EXACT and SEMANTIC case tables.
- [x] 8. The eight analysis modules: specs, evidence table, draft schema,
      evidence gate, prompt rendered from the enums.
- [x] 9. Application runner: one durable module, bounded repair loop, fail closed.
- [x] 10. Documents in sync: ARCHITECTURE, CLAUDE, domain map, parity matrix,
      open items, PROGRESS.

## Review outcome

Self-review only; no human review yet. What changed during the work:

- **The analysis evidence gate moved into `evidence/`.** Planned as part of the
  analysis package, it had to live beside the `AdmittedClaim` sentinel for the
  capability to mean anything, so `evidence.admission` owns row checks and
  minting, and `analysis.draft` owns only the prose rules.
- **Numbers in a cited name are not claims.** A strict "every number" rule
  blocked `vek 18-29` as two uncited numbers. The fix is narrow: numbers in the
  cell label of a row the item cites, or in the question it answers, are names.
  A year written in passing still blocks; that is the accepted cost.
- **`AnalysisModuleResult` re-checks prose on construction.** Added after
  noticing that a result built by hand bypassed the draft check.
- **Pre-flight before spend** in the runner: a degraded certificate blocks a
  client-facing module before any model call.
- **Commits.** Chunks 1–2 were committed; the permission layer then refused
  further commits (CLAUDE.md §5 requires explicit permission). Chunks 3–10 are
  prepared, one message per chunk, awaiting that permission.

### Layer-by-layer review map

| Layer | File | Tests |
| --- | --- | --- |
| Domain · evidence | `domain/evidence/gate.py` | `test_evidence_field_policy.py` (gate primitives) |
| | `domain/evidence/field_policy.py` | `test_evidence_field_policy.py`, parity §1 |
| | `domain/evidence/joint_status.py` | `test_evidence_joint_status.py`, parity §2 |
| | `domain/evidence/metrics.py` | `test_evidence_metrics.py`, parity §3 |
| | `domain/evidence/support.py` | `test_evidence_support.py`, parity §3 |
| | `domain/evidence/validation.py` | `test_evidence_validation.py` |
| | `domain/evidence/claims.py` | `test_evidence_claims.py`, parity §4–5 |
| | `domain/evidence/factual.py` | `test_evidence_claims.py` (factual layer) |
| | `domain/evidence/admission.py` | `test_evidence_admission.py` |
| Domain · analysis | `domain/analysis/modules.py`, `prompt.py` | `test_analysis_modules.py` |
| | `domain/analysis/draft.py`, `result.py` | `test_analysis_draft.py` |
| Application | `application/analysis.py` | `test_analysis_runner.py` |
| Enforcement | `tools/layer_check.sh` (+3 rules) | probe-verified to fail, then green |
| Tests · shared | `tests/conftest.py` (synthetic dictionary, certificate, rows, `reference_repo`) | — |
| Documents | `ARCHITECTURE.md` §2 §3 §4 §8, `CLAUDE.md` §2, `AGENTS.md`, `domain-map.md`, `parity-matrix.md`, `reference-source.md`, `status.md`, `open-items.md` OI-1/6/7/8, `PROGRESS.md` | — |
