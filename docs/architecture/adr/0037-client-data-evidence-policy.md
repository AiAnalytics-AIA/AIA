# ADR 0037 — A client dataset's evidence policy is compiled from its accepted data contract, and nothing else

**Status:** Proposed — 2026-10-20; **held for the methodology owner's answers** (the product
owner, 2026-10-20: "accept 0028-0033, 0035, 0038-0040; hold 0034, 0036, 0037"). **The support,
metric and benchmark rules (decision 4) are awaiting the methodology owner** (ADR 0027 Q1, Q2, Q4).
**Amends** [ADR 0027](0027-client-data-is-client-reported-evidence.md), as that ADR reads after the
open docs PR #508 (the allowlist copy, *z dat klienta* per number with source and period once,
MVPQ-05, and Q4), without editing it: this ADR is the mechanism behind its decisions 3-6. **Builds
on** [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md) (an origin of its own,
admitted only as what it is) and the evidence gates. **Leaves unchanged** the population contract as
the authority for panel respondents, `aia-instrument-evidence-1` and `-2`, and every existing run.
**Owner decision, 2026-10-25** (ADR-HELD (a), the audit page, relayed by coordinator 3): accept once its methodology answer is
written in; the owner asked for the same review document as for ADRs 0020 to 0024 (its questions,
how it connects in AIA, its inputs and outputs, an example for each complex topic). The status is
unchanged until the methodology answer is written in and he accepts it.

**Decision notes, 2026-10-26** (the product owner, Decision Review, relayed by the PM coordinator;
answered in part, the status unchanged, the rest the methodology owner's):

- **0037-Q4 (a): "A Metodika module ('client data'), versioned, pinned per run".** Decision 4's
  support rule version lives in the ADR 0023 store as a module of its own, written by the methodology
  owner, and a run pins it like every other module; it is not a code constant.
- **0037-Q5 (a): "Close it".** *Open for Nigel* item 2 (sequencing with #508) is closed: #508 has
  merged and ADR 0027 carries its 2026-10-20 amendment.
- **MQ-17 (a): "Never"** (shared with ADR 0027 Q2). A client's survey answers never condition the
  AI respondents' personas; client data stays a separate comparison. Decision 4's "grounding
  forbidden until answered" is now forbidden, full stop.

Still open: MQ-16, MQ-18 and the verdict, left for the methodology owner.

**Date:** 2026-10-20
**Plan:** [client-data-in-analysis](../../../.planning/plans/client-data-in-analysis.md) 0-9

## Context

ADR 0027 makes a client's dataset admissible as `CLIENT_REPORTED` evidence but gave no policy for
its columns (`mvp-cohesion.md` F3). The evidence layer admits a number only under a field policy
(`FieldPolicyBook`, `domain/evidence/field_policy.py:368 @ 854c209`), with support that defaults to
`SUPPRESS` (`domain/evidence/support.py:66-67, 171-177 @ 854c209`). A study's own items get theirs
from the origin of their answers, `-1` simulated or `-2` modelled panel, and any other origin is
refused (`_declared`, `domain/evidence/instrument.py:184 @ 854c209`; versions at `:99, 117`). The
metric vocabulary has means, top-2-box, percentages and respondent counts only
(`domain/evidence/metrics.py:32-53 @ 854c209`); a client's sales, prices and order counts fit none.

The owner answered on 2026-10-20 (MVPQ-05): **the human-accepted data contract alone compiles into
the dataset's evidence policy**: a column the contract names used and not personal is admissible as
client-reported, with no AIA-maintained field list in between. One authority per evidence source
(MVP-29): the population contract for panel respondents, the data contract for a client's data.

## Decision

### 1. A third instrument policy, compiled per contract version

`aia-instrument-evidence-3` is a pure function `client_policy(contract) -> FieldPolicyBook` over an
**accepted** data contract version: one field per column the contract names `used` and
`not_personal`, carrying the column's declared meaning, unit and period, the contract's use rights
and its version and hash. A column the contract does not name has no field and is refused. A
contract not accepted compiles to nothing. Nothing else (no AIA field list, no preview hint, no
model) contributes a field.

### 2. Its evidence status is its own

A new `EvidenceStatus` member, `CLIENT_REPORTED`, with its own provenance class: measured by the
client, not verified by AIA. It is admissible client-facing under ADR 0027 decision 6, never read as
measured by AIA, modelled or synthetic. `CLIENT_REPORTED` joins `CLIENT_ADMISSIBLE_ORIGINS`
(`domain/fieldwork.py:88 @ 854c209`) and `origin_kind` gains its fourth reading (`:149`).

### 3. A run pins the contract version it computed under

The policy's version and hash are in the run's identity beside the dataset copy's SHA-256; a new
contract version is a new policy and a new run, never a silent re-read. A deleted source leaves the
run's admitted results and a record that it was removed (ADR 0027 decision 9).

### 4. Support, metrics and benchmarks: the engineering contract, the method awaiting its owner

A client number is not a sample estimate. The contract it is computed under declares its **support
basis**: `exact` (an aggregate the client supplied, or a total over every row) or `row_count` (a
statistic over rows, with the row count stated). It never carries an invented effective n or
interval. The metric set is extended by named kinds and units for client numbers (count, amount
with currency, rate, share), each declared in the contract's column meaning.

**Awaiting the methodology owner:** when an interval is required and how it is computed (Q4); the
minimum support below which a client number is suppressed; the benchmark gap's rule when the two
supports differ greatly (Q1); whether a client's survey may ever ground AI respondents (Q2, not
allowed until answered). **Until a rule version is approved, admission of a `CLIENT_REPORTED`
number refuses (`client_support_rule_unapproved`)**: the contract, the copy, the computations and
their tests proceed.

### 5. Personal data: one rule, stated once

The preview **masks** values in columns its hints flag (`domain/client_datasets.py:70, 144 @
854c209`); the analysis copy **holds only** the contract's named, not-personal, used columns; no model
sees a row of either. The hints warn; they decide nothing.

## Alternatives considered

- **An AIA-maintained list of admissible client fields.** Rejected by the owner (MVPQ-05).
- **Admit by the preview's personal hints** (drop what they flag). An identifier under an unknown
  header passes; the allowlist fails closed.
- **Treat a client's rows as respondents** (n, effective n). It would print intervals for totals and
  suppress exact figures as small samples.

## Consequences

- A third policy version, a new evidence status and origin, metric kinds and units, and a refusal
  that holds client numbers back until the methodology owner's rule exists.
- A person's contract is the whole policy, so a wrong classification is that person's recorded act;
  the copy cannot contain what they did not name.

## What enforces it

- `test_every_origin_is_decided_once` extended to the new origin; a gate test: a `CLIENT_REPORTED`
  number with no accepted contract is refused by name; a column the contract does not name is absent
  from the copy, its artifact and every model request (the `customer_id` case of chunk 3); the
  compiled policy is a pure function (same contract, same book and hash); with no approved support
  rule, admission refuses by name.
- `make layer_check`: the data-contract tables only through `ClientDataContractRepository`.

## Unblocks

`client-data-in-analysis` 0 (the policy decision's engineering half), 1-3b, 4 and 5 (W3), 9; gate I-3
and AC-10.

## Open for Nigel

1. **Q1, Q4** are the methodology owner's (A. Bahbouh); Q2 is answered, "Never" (MQ-17 (a), the
   product owner, 2026-10-26).
2. ~~**Sequencing with #508.** This ADR reads ADR 0027 as #508 amends it; if #508 changes before it
   merges, this ADR follows it.~~ Closed 2026-10-26 (the product owner, Q5 (a): "Close it"): #508
   has merged.
