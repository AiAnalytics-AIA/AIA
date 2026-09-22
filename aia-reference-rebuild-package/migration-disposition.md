# Migration disposition ledger

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Per capability: reference source, target system, status, verification, phase,
notes — tying reference behaviour to the production system.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Requires the capability map first. Production state must be read from the current
repository READ-ONLY and never guessed; where it cannot be confirmed, the target
mapping is recorded as `TO_RECONCILE_WITH_CURRENT_MAIN` rather than invented.

A machine-readable `migration-disposition.json` accompanies it.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
