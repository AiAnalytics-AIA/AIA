# AIA Research Lead workbench · design V3 (artifacts)

The product owner's design for the chat-centric study screen, as of 2026-10-19. One Research Lead
conversation per study on the left (40 %). The right 60 % is the stage's **artifact**, one
purpose-built artifact per research step, which the Lead steers. It follows
[`research-lead-v2`](../research-lead-v2/) and changes one thing there: each step is designed as its
own artifact, where today's workbench mounts the existing stage screens unchanged.

It is **not product code**. The study ("Young Customer Perception 2026" for Fio banka), its numbers,
sources and quotes are fictional; none of it is a fact about Fio banka. The copy is English; AIA's
interface is Czech, so the design gives the structure and the meaning, and the product writes it in
Czech.

The work that builds it is in [`.planning/plans/research-lead-workbench.md`](../../.planning/plans/research-lead-workbench.md)
(chunks 13 onwards).

## Files

The design was exported from the design tool as three self-unpacking HTML bundles. **The bundles
are not kept here**: `tools/exposure_check.sh` refuses their compressed contents, and the product
owner keeps the originals. What is kept is every board's visible text, extracted in a headless
browser on 2026-10-19, so the design can be searched and cited. `FRAME n` is the n-th board in the
bundle's order; `FRAME 0` is the bundle's index.

| File | Bundle | What it is |
|---|---|---|
| `text/artifacts.txt` | AIA Research Lead Workbench | The eleven step artifacts, one board each: Brief, Research design, Questionnaire, Audience, Dimensions, Sample, Fieldwork, Results, Analysis, Sociomap, Report |
| `text/scenario.txt` | AIA Research Lead scenario | Eight full-screen flows on one study: A opening and Brief, B questionnaire proposal, C Audience with Deep Research self-activated, D Fieldwork, E Sociomapping, F Analysis, G Report composition, PM "Where are we? Continue until you need me" |
| `text/boundaries.txt` | Reuse and boundaries | Which mechanism each interaction runs through (browser operator, typed command, worker, deterministic engine, Deep Research, read-only retrieval, a person), what was taken from Open WebUI's interaction grammar, what must not reach production, what production needs |

Two deliberate departures, decided by the product owner on 2026-10-19:

- **The stage navigator stays at the top of the page**, as in today's workbench. The scenario
  boards draw it as a lifecycle rail at the bottom; that placement is not adopted.
- **The interface is Czech.**

## Not to carry into production

As `text/boundaries.txt` says: Open WebUI's code (its licence, and it is Svelte), the Demo control,
the scripted replies, the drawn terrain on the map (the product draws the engine's stored artifact),
the fictional sources and quotes, and the English copy.
