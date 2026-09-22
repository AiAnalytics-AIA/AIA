# API ledger

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Every HTTP route in the prototype: method, path, handler, auth assumptions,
inputs, outputs, state changed, capability, frontend caller, replacement status —
then grouped into capabilities.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Extract route registrations from the source. One legacy route does not imply one
production route: the question the ledger must answer is whether the USER/BUSINESS
CAPABILITY is preserved, not whether the URL is.

Cross-check against the production repository's own contract assertions in
`.github/workflows/ci.yml`, which already enumerate the study-scoped routes that
exist today.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
