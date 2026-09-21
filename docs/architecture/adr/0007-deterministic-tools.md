# ADR 0007 — No LLM for deterministic analytical computation

**Status:** Accepted.
**Date:** 2026-09-21

## Context

AIA produces paid client research. Its outputs include correlation matrices,
weighted aggregates, segment profiles, significance figures and cost totals.

A language model can produce numbers that look right. It cannot be relied on to
produce the same number twice, and it cannot be audited.

## Decision

**Statistics, parsing, transformations, scoring, aggregation, validation and cost
calculation are tested deterministic software. Never model output.**

Agents may:

- decide **which** tool to run, and with which parameters;
- **interpret** a tool's output in prose;
- propose a hypothesis for a tool to test.

Agents may not:

- compute a statistic, a weight, an aggregate or a total;
- parse a dataset into a structured form;
- decide whether a validation gate passes;
- calculate a cost.

Every such operation is a registered tool in the `ToolRegistry`: ordinary Python
with unit tests and fixed-seed reproducibility.

## Why this is non-negotiable here

Three reasons specific to this product:

1. **Reproducibility is a deliverable.** A client can ask why a figure changed
   between two versions of a study. With deterministic tools the answer is a diff
   of inputs. With model-computed numbers there is no answer.
2. **The methodology contract is machine-checkable or it is decorative.**
   `PRODUCT_POLICY.json` sets rules like `linear_interpolation_allowed: false` and
   `invent_missing_truth: false`. A gate that "checks" these by asking a model is
   not a gate.
3. **Cost accounting must be exact.** The budget enforcement that stops a study
   overspending cannot itself be an estimate produced by the thing being metered.

## Consequences

- The tool layer is substantial, and much of it ports directly from the
  prototype's validated numerical code — which is an argument for porting rather
  than rewriting it.
- Agent prompts get longer: the model must be told what tools exist and what they
  return, rather than doing the work inline.
- Some tasks that a model could do in one step take a tool call plus an
  interpretation. Accepted: the cost is latency, and the gain is an auditable
  number.
- A model asked to "just estimate" a figure is a bug, and a review should treat
  it as one.

## Revisit when

Never for the categories above. If a new category of computation appears, the
default is deterministic and the burden is on the exception.
