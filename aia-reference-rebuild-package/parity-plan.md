# Parity plan

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Per subsystem: reference entry point, production target, fixture, expected output,
parity type (EXACT / NUMERICAL / SEMANTIC / INTENTIONAL_DIFFERENCE), tolerance,
existing reference test, production test status.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Follows the methodology ledger and high-risk list. Prioritise deterministic
methodology, fingerprints, state transitions, sample selection, aggregation,
scoring, provider policy, simulation numerics, Sociomapping numerics, report data
assembly and validation outcomes.

The production repository's `docs/migration/parity-matrix.md` is the existing
starting point and should be reconciled, not replaced.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
