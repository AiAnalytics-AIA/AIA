# High-risk behaviours

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Everything whose loss or subtle change could alter RESEARCH TRUTH or product
integrity: statistical formulas, normalisation, weighting, imputation, population
selection, sampling, scenario mathematics, Sociomapping, validation thresholds,
legal restrictions, evidence rules, cost controls, provider fallback,
deterministic state transitions, hidden assumptions.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Derived from the methodology ledger. These become the priority parity contracts.

One item can already be named from the production repository's own history, without
the tree: the prototype's `recover_expired` refuses to retry a possibly-billed paid
call, moving the job to `RECOVERY_REQUIRED` and settling the reservation as
`SETTLED_UNCERTAIN`. Losing that turns a worker crash into a silent double-spend.
It is documented in `docs/migration/status.md` and already carried into production
— the worked example of what this document is for.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
