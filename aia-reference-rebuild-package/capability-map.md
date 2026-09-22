# Capability map

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Organise the prototype by bounded capability, not by filename, covering at
minimum: project/study management, research design, respondent/fieldwork engine,
population, aggregation, analysis, validation/governance, reporting, simulation,
Sociomapping, data library/society intelligence, AI runtime, workflow/jobs,
cost/budget, API, frontend, configuration/policy — plus anything found that this
list does not anticipate.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

1. Read every `python_application_source` file (184 files) and record, per module,
   its responsibilities — a module may carry persistence, rules, UI and model calls
   at once and must be decomposed, never filed under one label.
2. Group responsibilities into capabilities. Multiple modules may collapse into one
   bounded context; one module may split across several.
3. For each capability record purpose, reference implementation, key functions,
   inputs, outputs, state, dependencies, rules, edge cases, assets, tests, target
   bounded context, parity strategy, migration status.
4. Emit `capability-map.json` with a `capabilities` array whose `reference_files`
   entries are inventory ids — check C8 of the verifier enforces that they resolve.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
