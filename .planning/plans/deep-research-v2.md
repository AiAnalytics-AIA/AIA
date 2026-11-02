---
status: planned
chunks:
  - "[ ] DRV0. The gate's three additions before a structured or archive route goes live: per-source rate limits (ARES 500 a minute), a robots.txt and text-and-data-mining reservation check before any fetch for mining, a retention limit on mined copies; each refusal named"
  - "[ ] DRV1. The typed input as a contract: value, unit, period, range, source, licence and as-of date, with the labelled Czech set (300+ sentences from annual reports, ČSÚ releases and price lists, two annotators) pinned as a fixture"
  - "[ ] DRV2. The rule-based extractor in code: the model proposes the concept and the period only; value and unit F1 >= 0.90 on the labelled set before it is used"
  - "[ ] DRV3. The extraction step between verify and synthesize: typed inputs extracted from accepted findings' quotes and from structured routes (public-data-routes), each accepted by a person before it reaches a model input (public_source) or a findings table"
  - "[ ] DRV4. Citation precision and recall in verify: DeepTRACE's citation accuracy and thoroughness, the judge calibrated on 100 human-labelled statement-source pairs (kappa reported), and a link-health check; targets accuracy >= 90 %, unsupported < 10 %, thoroughness >= 50 %"
  - "[ ] DRV5. Source credibility v2: declared (source, claim type) tables, a Code-of-Practice checklist for statistics, a review date and a four-year stale flag; a score proposed by a model refused"
  - "[ ] DRV6. Triangulation: each numeric claim decomposed into sub-questions, agreement or contradiction recorded per typed input, a person resolves a contradiction (macro-F1 measured on a labelled Czech set)"
  - "[ ] DRV7. As-of-date research: Memento TimeGate and Wayback CDX beside the Common Crawl index, a new 'as of' purpose; every archive finding carries its capture's own datetime within a declared tolerance"
  - "[ ] DRV8. Scheduled monitoring: structured series polled by their own update annotations (Eurostat UPDATE_DATA), pages at an estimated change rate, an alert only when an extracted value changes"
  - "[ ] DRV9. Precedents and case outcomes as a purpose: candidates only, each confirmed by a person; no outcome predicted"
---
# Deep Research v2: typed numbers, citation recall, credibility, as-of dates

Written 2026-11-02 under [ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
decision 6. It comes from the research's § Deep Research v2 spec and section B
([`../evidence/pivot-research-2026-11-02.md`](../evidence/pivot-research-2026-11-02.md)).

**What stays as built.** These are not reopened:
- the six steps;
- `RetrievalGate`;
- the snapshots;
- the rule that a finding is a quote in a captured source.

Every capability here is a new gate check, a new step or a new purpose around them. DRV4 extends verify
on an evaluation finding (B1), which is the one ground on which the frozen engine may change.

**The order.** The research ranks structured routes (`public-data-routes`) and typed extraction (DRV1-DRV3)
first, because they turn research into model inputs. DRV0 comes before any route goes live.

**Owner:** S2. Proposed; the session that takes it reviews this plan first.
