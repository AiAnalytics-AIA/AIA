---
status: planned
chunks:
  - "[ ] 1. Measure first: per call kind, the share of input that is a repeated prefix, from the usage ledger and the request shapes (no code change)"
  - "[ ] 2. Pricing that cannot under-charge: an unknown cache-write price refused once caching can be on (the cost rule, the ceiling, the reservation checks)"
  - "[ ] 3. The adapter: a Bedrock cachePoint after a declared prefix, behind AIA_AI_PROMPT_CACHE (off), declared per catalog entry (min tokens, TTL), never guessed from the id"
  - "[ ] 4. The gateway: a request names its cacheable prefix; fingerprints, provenance and the ledger record cache reads and writes as they are reported"
  - "[ ] 5. The first caller: the Research Lead's frozen context (the largest repeated prefix), on develop, measured"
  - "[ ] 6. Further callers, each on its own measurement: analysis modules over one dataset, design jobs, Deep Research agents; respondents only if chunk 1 shows a prefix above the minimum"
---
# Prompt caching on the Bedrock route

**Drafted:** 2026-10-25 · **Base:** `develop` @ `f7762d72` · **Owner:** the product owner, who asked
on 2026-10-25, during the Sonnet 5.5 switch (`sonnet-5-5-switch.md`), to plan for prompt caching.

## Where it stands (anchored)

- AIA sends no cache point. Nothing in `packages/` or `apps/` writes `cachePoint` (grep @ 26f70903, the Sonnet 5.5 branch; develop @ f7762d72 the same).
- The ledger already reads what Bedrock reports: `cacheReadInputTokens` and `cacheWriteInputTokens`
  (`infrastructure/model_adapters/bedrock.py:373-374 @ f7762d72`), priced by `ModelPricing.cost_usd`.
- **Writes cost more than input.** Sonnet 5.5 on develop: input 2.20, cache read 0.11, cache write
  2.75 USD per Mtok (read by the infra session, 2026-10-25). A prefix repays its write only when it is
  read again within the cache's lifetime.
- **An unset write price under-charges** (`ModelPricing.cost_usd`, `domain/ai_models.py:174-206 @
  f7762d72`): writes are charged at the input rate. Harmless while nothing is cached; chunk 2 closes it
  before chunk 3 can turn caching on.
- The worst-case ceiling already prices every input token at the larger of input and write
  (`ceiling_usd`, `:208-221`), so reservations stay safe with caching on.

## Candidates, by what repeats (hypotheses until chunk 1 measures them)

- **The Research Lead.** A turn's frozen context is up to 96 KB of canonical JSON
  (`domain/research_lead.py:18`), resent on the repair and largely on the next turn. Likely the
  largest win.
- **Analysis.** Eight modules read one run's dataset; a shared prefix only if the payload puts it
  first and the same.
- **Design jobs.** Up to 64 KB of context (`domain/research_agents.py:35`), one call and a repair.
- **Deep Research.** Many agent calls; prefixes depend on the frozen engine's prompts, which this plan
  does not change.
- **Respondents.** The system prompt is 2,286 characters, likely below a cacheable minimum. The
  profile repeats across one respondent's blocks. Measured, not assumed.

## Rules this plan keeps

- Off by default, behind a switch, cost measured before it merges (CLAUDE.md § 8).
- What a model supports (minimum prefix, lifetime) is declared in its catalog entry from the Bedrock
  documentation the infra session reads, never inferred from the id.
- A cached call is the same call: the input fingerprint and every result stay as they are; only the
  ledger's cache columns and its cost differ.
- No caching of anything a data-class or licence gate would refuse; the gates run before the cache
  point is placed, as before.
