---
status: in-progress
chunks:
  - "[ ] 1. A model's request profile, declared in its catalog entry and read by the Bedrock adapter"
  - "[ ] 2. The Lead's own capability (STUDY_LEAD) and its own pinned model, from configuration"
  - "[ ] 3. Compose and env.example pass the Lead model's keys to the worker"
  - "[ ] 4. The instance role may invoke the Lead model's profile when one is set"
  - "[ ] 5. ADR 0026 amendment: the Lead's own model"
  - "[ ] 6. Runbook: the Research Lead's own model"
---

# The Research Lead's own model

**Decision** (the product owner, 2026-10-19): the study's Research Lead (ADR 0026) runs on its
own model, a current-generation model on Bedrock, while every other capability stays on the
route's existing model. No model name and no price lives in code, tests or docs: both come
from configuration (environment / SSM), recorded by an operator from the Bedrock console and
pricing page.

## Why the model cannot just be swapped

The Bedrock adapter gets structured output in one of two ways
(`packages/aia_core/src/aia_core/infrastructure/model_adapters/bedrock.py:189-222 @ 6c5cd620`):

- without thinking, a forced tool (`toolChoice: {"tool": {"name": …}}`);
- with thinking, `additionalModelRequestFields.thinking = {type: "enabled", budget_tokens: N}`
  and `toolChoice: auto`.

The newer model family refuses both with a 400: forced tool choice (`any` / `tool`), a thinking
budget, and non-default sampling values. Thinking is adaptive when the field is omitted. The
path that works is the existing "auto + instruction" one: `toolChoice: auto`, the single tool,
and the gateway's instruction to answer through it; an answer in text takes the gateway's one
schema repair (`application/model_gateway.py:598-601 @ 6c5cd620`).

So the request shape becomes a **declared property of the model** in its catalog entry, never
a guess from its id.

## Chunks

1. **Request profile.** `ModelDescriptor` gains `structured_output` (`forced_tool` default |
   `auto_tool`), `thinking` (`budget` default | `adaptive`), `accepts_sampling` (default true)
   and `effort` (optional, adaptive only). The gateway threads the resolved model's profile into
   `AdapterRequest`, and tells an `auto_tool` model to answer through the tool, as it tells a
   thinking call today. The adapter sends `toolChoice: auto` for it, never a thinking budget or
   a temperature, and `additionalModelRequestFields` only for an effort. A request the profile
   cannot carry (a thinking budget on an adaptive model, a temperature on a model that takes
   none) is refused unsent, by name. Defaults keep every existing request byte for byte.
2. **STUDY_LEAD.** A capability of its own for the Lead's turn (`RESEARCH_LEAD` is Deep
   Research's lead researcher). `LeadModelSettings` from `AIA_AI_RESEARCH_LEAD_MODEL_*` keys,
   read only when `AIA_AI_RESEARCH_LEAD_MODEL_ID` is set; no defaults; the worker refuses to
   start on a missing or invalid key and names it. `model_document` binds `STUDY_LEAD` to the
   lead model on the same route, else to the route's model. The Lead's reservation minimum and
   window checks use the lead model's prices and limits.
3. **Compose and env.example.** The keys reach the worker as `${KEY:-}`.
4. **IAM.** `bedrock_lead_model_id` (default empty) adds the profile and its foundation model in
   the destination regions to the instance role's Bedrock grant.
5. **ADR 0026 amendment.**
6. **Runbook.** SSM names, Terraform, `bin/write-env.sh`, the worker's restart and its log.

## Doc follow-up

(Filled in as chunks land.)

## Findings

None yet.
