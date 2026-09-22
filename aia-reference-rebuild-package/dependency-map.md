# Dependency map

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

The real call and dependency graph: imports, function calls, route registration,
job dispatch, configuration references, template references, asset loading — and
the actual execution flows for the research, simulation and Sociomapping
pipelines.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Build mechanically from imports first, then correct by reading call sites. The
brief supplies expected flows for research, simulation and Sociomapping; they are
HYPOTHESES to be corrected against the code, not templates to confirm.

Also drives §13: for every module with no inbound edge, decide explicitly whether
it is an older generation, a feature flag, a manual tool, a migration helper, a
debugging aid, offline analysis, an alternative workflow, a hidden route, a test
harness, a future experiment, an abandoned implementation, or an accidentally
disconnected capability. "Not called" never means "useless" by default.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
