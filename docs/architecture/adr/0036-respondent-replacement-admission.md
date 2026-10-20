# ADR 0036 — Replacing respondents is a new linked run: the original stays as it is, an exclusion is pinned, kept answers are reused by hash; the weighting awaits the methodology owner

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so; **the replacement
method (decision 5) is awaiting the methodology owner** (MVPQ-10) and is not chosen here. The
admission rule [ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 4 requires
before any command reaches *respondent replacement*. **Builds on** [ADR 0016](0016-research-execution-and-model-transmission.md)
(a run executes an immutable Design Revision; respondents are drawn once per run),
[ADR 0019](0019-two-roles-and-human-ai-gates.md) gates 1 and 2, and
[ADR 0028](0028-orchestration-scope-wallet-and-plan-card.md) (the typed start). **Leaves unchanged**
the original run, its dataset, its results and its report.
**Date:** 2026-10-20
**Plan:** [run-qc-and-checkpoint](../../../.planning/plans/run-qc-and-checkpoint.md) RQC4, RQC4a, RQC5

## Context

The owner decided (F18, Q22; `mvp-cohesion.md`): no pause after fieldwork; run QC warns, the
straight-liner worker proposes keep or flag, and **replace is a new linked run**. Today a run's
respondents are drawn once from the specification's seed (`domain/ai_respondent.py:263 @ 854c209`,
`domain/population/sampling.py:496 @ 854c209`), and the only restart over a finished run's data is
`retry_analysis`, which re-asks analysis over the original's frozen dataset by artifact id and
SHA-256 (`FrozenDataset`, `application/research.py:324, 865 @ 854c209`) and never recollects
fieldwork. Nothing excludes a respondent or draws a substitute. How the substitutes are weighted,
what the effective n becomes and when a replacement must be refused are method (MVPQ-10).

## Decision

### 1. A new run, linked, from a COMPLETED run only

`run.replace` is a typed, human-only command (ADR 0026 decision 4) that starts a new run of the
same study, on the **same Design Revision and every pin of the original** (methods, persona source,
population binding, prompts), with `replaces_run_id` in its metadata. The original is never
changed, re-labelled or hidden; both are readable and the newer one names the older.

### 2. The exclusion is pinned, and comes only from accepted flags

The new run pins an exclusion: the respondent ids, each with the accepted QC flag id that justified
it (RQC4's accept destination). An exclusion with no accepted flag is refused
(`replacement_unflagged`); a model's proposal alone excludes no one.

### 3. Kept answers are reused by hash, never paid again

Respondents not excluded keep their answers: the new run's fieldwork step is given the original's
dataset by artifact id and SHA-256, verified before use, as `FrozenDataset` is. Only substitutes
are asked, through the same paid path, journaled per respondent (RQC0). The new run's cost ceiling
counts only the substitutes and its downstream steps, and is charged and confirmed like any start.

### 4. Substitutes are drawn by code, reproducibly

The substitutes are drawn through the run's population and sampler with a seed derived from the
original's seed and the exclusion's fingerprint, never with the original's draw repeated, and never
chosen by a model. The draw is recorded as the original's is.

### 5. The method, awaiting the methodology owner

A versioned, pinned replacement rule (ADR 0023's store): redraw versus exclusion only; the cell a
substitute is drawn from; weight recalibration; the effective n and support after replacement;
quota checks; the conditions that refuse replacement. **Until a version is approved, `run.replace`
refuses (`replacement_method_unapproved`)**: lineage, storage, the exclusion pin and the refusal
tests proceed.

### 6. Reported side by side

The replacement run's report and Results name the original, the exclusion (count, reasons, flag
ids), the method version and the support before and after. Weights are never silently
renormalised; the two runs can be compared because both are kept whole.

## Alternatives considered

- **Edit the original dataset.** Breaks ADR 0016's immutability and every fingerprint that read it.
- **Re-run fieldwork whole.** Pays again for every unchanged respondent, and answers would differ
  for reasons other than the replacement.
- **Drop flagged respondents without substitutes.** It changes n and support without a method;
  it is one of the method's options, not a default.

## Consequences

- A command, a start path from a finished run, an exclusion record and a lineage field; no new
  table.
- Two runs per replacement in every list; the newer is the one a report and the Lead read by
  default, and both are named.

## What enforces it

- Tests: a replacement leaves every artifact of the original byte-identical; kept respondents' answers
  are reused by hash and cost no call; an exclusion without an accepted flag is refused; the
  substitutes' draw is reproducible from the pinned seed and exclusion; a replacement from a run
  that is not COMPLETED is refused; with no approved method version, `run.replace` refuses by name;
  the Lead can only prepare a card for it.

## Unblocks

RQC4a (W1, the flag contract), RQC4 (W3, the accept destination), RQC5's storage and refusals now,
and its executable behaviour once MVPQ-10 is answered.

## Open for Nigel

1. **MVPQ-10, the method**, is the methodology owner's (A. Bahbouh).
2. **Which run a report reads by default** after a replacement: this ADR reads the newer and names
   both; the alternative is that a person chooses each time.
