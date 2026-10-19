---
status: done
chunks:
  - "[x] 1. A model's request profile, declared in its catalog entry and read by the Bedrock adapter"
  - "[x] 2. The Lead's own capability (STUDY_LEAD) and its own pinned model, from configuration"
  - "[x] 3. Compose and env.example pass the Lead model's keys to the worker"
  - "[x] 4. The instance role may invoke the Lead model's profile when one is set"
  - "[x] 5. ADR 0026 amendment: the Lead's own model"
  - "[x] 6. Runbook: the Research Lead's own model"
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

For the docs PR (CLAUDE.md § 2, the map). No shared file is edited on this branch.

- `apps/executors/src/aia_executors/ai_runtime.py`: add to its entry: "`STUDY_LEAD`, the study
  Research Lead's turn (ADR 0026), is bound to the Lead's own model when
  `AIA_AI_RESEARCH_LEAD_MODEL_ID` is set (`LeadModelSettings`: a pinned EU profile, its prices,
  limits and request profile from `AIA_AI_RESEARCH_LEAD_*`, no defaults, a wrong key stops the
  worker by name), a second policy entry on the same route pinned through `PinnedModels`; else
  to the route's model. The Lead's reservation is checked at that model's prices and window."
- `packages/aia_core/src/aia_core/infrastructure/model_adapters/`: add: "Each model's request
  shape is declared in its catalog entry (`domain/ai_models.py` `RequestProfile`:
  `structured_output` forced_tool | auto_tool, `thinking` budget | adaptive, sampling, effort),
  threaded into `AdapterRequest`. The Bedrock adapter sends an `auto_tool` model
  `toolChoice: auto` with the gateway's answer-through-the-tool instruction, never a thinking
  budget or temperature to a model that refuses them, and only a configured effort as
  `additionalModelRequestFields.output_config`; what a profile cannot carry is refused unsent.
  The other adapters refuse any non-default profile."
- `domain/ai_models.py` in the map (`ai_models.py ModelCapability, catalog, ...`): add
  "`RequestProfile`; `STUDY_LEAD` (the study Lead), apart from `RESEARCH_LEAD` (Deep Research)".
- CLAUDE.md's "Native Research agents" paragraph lists the worker keys; add the Lead model's
  keys by reference to `deploy/develop/README.md` § The Research Lead's own model.
- `ARCHITECTURE.md` § 2's AI-settings paragraph: unchanged until F1 is fixed (the settings page
  does not yet list the study Lead).
- `AGENTS.md` § The AI runtime: a gotcha worth recording: **a newer Bedrock model refuses the
  request shapes an older one needed.**

  ```python
  # WRONG -- swap AIA_BEDROCK_MODEL_ID and send what the old model took: a 400 on every call
  {"toolChoice": {"tool": {"name": tool}}}                                   # forced tool
  {"additionalModelRequestFields": {"thinking": {"type": "enabled", "budget_tokens": n}}}
  {"inferenceConfig": {"maxTokens": m, "temperature": 0.0}}                  # sampling
  # RIGHT -- declare the model's request profile in its catalog entry; the adapter reads it
  {"structured_output": "auto_tool", "thinking": "adaptive", "accepts_sampling": False}
  # -> toolChoice auto + the gateway's instruction; nothing about thinking but an effort
  ```

## Findings

- **F1. The settings page does not list the study Research Lead as an AI activity.**
  1. `_native_runtime` lists fieldwork, design agents, analysis, Deep Research and Deep
     Research's lead, and nothing for the study Lead; with `STUDY_LEAD` it now names that
     capability under `unused_capabilities` while develop binds it
     (`apps/api/src/aia_api/routers/settings.py:448-526 @ 6c5cd620`). Before this plan the Lead
     bound `RESEARCH_REASONING`, which the page attributes to the design agents and analysis,
     so it was already misdescribed.
  2. Anchor above; the worker's binding is `AIRuntimeSettings.model_document`
     (`apps/executors/src/aia_executors/ai_runtime.py`, `STUDY_LEAD`).
  3. Reproduction: `test_every_capability_the_worker_binds_belongs_to_an_activity_the_page_lists`
     in `apps/executors/tests/test_settings_presentation.py` parametrised with
     `AIA_AI_RESEARCH_LEAD_ENABLED=true` and its two keys fails.
  4. Consequence: Settings says an AI capability is unused while every Lead turn calls it.
  5. Smallest fix: a `study_lead` `NativeActivity` (capability `STUDY_LEAD`, switches runtime +
     `AIA_AI_RESEARCH_LEAD_ENABLED`); the switch test then needs `AIA_AI_RESEARCH_LEAD_ENABLED`
     in the web's `AI_SWITCHES` and the web service's Compose environment, so it is a web change
     and is left out of this plan (no web change here).
  6. Test: the parametrisation in 3.
