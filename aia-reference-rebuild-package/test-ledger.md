# Test ledger

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Every meaningful test in the reference: path, test function, behaviour protected,
subsystem, determinism, target parity requirement, whether a production equivalent
exists.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

65 Python test files are already identified and classified `TEST_CHARACTERIZATION`
in the inventory — this is the one disposition establishable without contents.

Tests are to be read as BEHAVIOURAL CONTRACTS, not as prototype clutter: they often
document behaviour better than the implementation does. The production repository
already carries 94 parity and characterization tests derived from this reference
(`test_legacy_job_store_characterization.py` alone is 1103 lines describing
`job_store.py`); those are the worked example of the output format.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
