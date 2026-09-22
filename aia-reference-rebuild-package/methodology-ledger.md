# Methodology ledger

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Every file and function encoding RESEARCH METHODOLOGY rather than software
plumbing: formulas, weights, scoring, normalisation, sampling, imputation, donor
logic, calibration, thresholds, validity and significance criteria, evidence
rules, simulation and scenario assumptions, Sociomapping mathematics, report claim
rules, confidence rules, and prompts that encode methodology.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

1. Start from the 82 files already classified `methodology_or_policy` by name, and
   the machine-readable policy files (`PRODUCT_POLICY.json`, `DATA_CONTRACT_v17.json`
   and equivalents) — the brief is explicit that these may matter more than many
   source modules.
2. Then sweep the source for numeric constants, thresholds and statistical
   operations. A 50-line threshold module is in scope; size is not a proxy for
   importance.
3. Per item record source path, exact function/config, description, inputs, outputs,
   assumptions, constants, thresholds, deterministic-or-AI, tests, downstream
   consumers, target production representation, parity requirement.
4. Separate rules enforced by CODE from rules enforced only by PROMPT and rules
   enforced only by HUMAN CONVENTION. Flag conflicting and deprecated rules.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
