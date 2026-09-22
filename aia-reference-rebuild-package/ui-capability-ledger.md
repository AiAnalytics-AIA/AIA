# UI capability ledger

> **STATUS: NOT BUILT — blocked on the reference tree.**
>
> This file is a scope and method record, not a deliverable. It is present so the
> package layout is complete and so the work is specified rather than remembered.
> It contains **no findings**, because findings here would have to be invented.
>
> Blocked by decision **D-0** in `open-decisions.md`.

## What this document must contain

Every user-facing capability: screens, navigation, workflows, forms, analysis
interactions, assistant behaviour, Sociomapping controls, scenario controls,
reporting, approvals, settings, provider controls, costs, population exploration,
data library, export/download.

## Required input

The reference tree or the original ZIP. See `README.md` → *To complete the audit*.

Identity is already established: the 1324 canonical files, their SHA256 hashes and
their type classification are in `reference-file-inventory.json`. What is missing is
the contents.

## Method once the input is available

Derive from the 76 HTML documents. Note the finding in `coverage-summary.md`: the
reference has ZERO standalone `.js` and `.css` files, so behaviour is inline in
the HTML and must be read there. Only 2 of the 76 sit outside `demo_library/`.

Preserve USER CAPABILITY, not CSS or DOM trivia. Per capability record UI location,
backend/API dependency, business function, state, output, current production
replacement if known, target future state.

## Rule

Nothing is to be written into this document that is inferred from a filename. Where
a name is suggestive, it is recorded as a question to answer, never as a finding.
