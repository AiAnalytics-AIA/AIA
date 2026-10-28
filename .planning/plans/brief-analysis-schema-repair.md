---
status: in-progress
chunks:
  - "[x] 1. A wrong JSON type is named in the violation (received string / null / object / …), so the repair turn and error_json say what arrived"
  - "[x] 2. (a) The repair turn says to send a list or object itself, never a string holding JSON, when one arrived as a string (repair_hint=container-as-string-v1 on that repair's ledger note)"
  - "[ ] 3. Deferred: (b) narrow typed decoding, only if an observed failure shows `received string`"
  - "[ ] 4. Schema-enforced output: what Bedrock Converse supports for the route models in the EU, the contracts' keywords it refuses, thinking and auto_tool; a new RequestProfile.structured_output value behind a switch off by default, recorded adapter fixtures first; any paid probe on the product owner's ok"
  - "[ ] 5. Keep refused answers: a material_rules entry (Class B, as the design it answers), bounded, stored on the failed attempt's run, erased with the client; the draft rule put to the product owner before building"
---
# A brief analysis refused for `tracked_sets: Input should be a valid array`

On develop, 2026-10-28 12:13:54-12:14:40Z, an "Analyzuj zadání" job (the brief-analysis research
agent, contract `BriefAnalysis`) failed twice on the same violation, primary and repair:
run RUN-4486b029e2c74102, step STP-7e7cbdbe4a2b4bb3, attempt ATT-53bca5687f3d4a62, on a fictional
client. Both calls finished COMPLETED (6,723/1,951 and 8,530/1,891 tokens in/out; maxTokens 4096),
so neither was truncated. The 12:08Z switch to application inference profiles is ruled out: it
changes only the URL path (`test_without_the_keys_the_route_model_is_sent_the_same_bytes_as_before`).

## Findings

### F1. A refused design-agent answer is not kept, and its violation cannot tell the shapes apart

1. **Claim.** When a research agent's structured answer is refused, nothing records what the model
   sent. The violation is the same whether the field held a string, null or an object, so the
   failure cannot be diagnosed after the fact.
2. **Anchor.** `ModelCallFailed.rejected_output` carries the answer
   (`packages/aia_core/src/aia_core/domain/ai_contracts.py:933-950 @ 848f015b`). `recovery_inputs`
   drops it from error_json (`packages/aia_core/src/aia_core/domain/ai_execution.py:165-176 @ 848f015b`).
   `ai_usage_events` has no text column (`infrastructure/tables.py:2176 @ 848f015b`).
   `validate_structured_output` prints only Pydantic's `msg`
   (`packages/aia_core/src/aia_core/domain/ai_contracts.py:383-386 @ 848f015b`).
3. **Reproduction.** `pytest packages/aia_core/tests/test_research_agents.py -k wrong_json_type`:
   a string holding a JSON array, null and a lone object each give
   `tracked_sets: Input should be a valid array`.
4. **Consequence.** The researcher's "Analyzuj zadání" fails and its cost is spent (two paid calls).
   The repair turn tells the model the expected type but not what it sent, and here the repair
   repeated the fault. Nobody can say which fault it was.
5. **Smallest fix.** Name the received JSON type in a type violation (chunk 1). The real cure
   depends on the shape (chunk 2).
6. **Test.** `test_a_wrong_json_type_is_named_in_the_violation` (string / null / object).
   The string case is a **hypothesis** for the develop failure: a JSON array sent as a string
   holding JSON, a known tool-use failure in long answers. The real shape was not stored and is
   not recoverable without a paid re-run.

## Decision

The product owner, 2026-10-28 ~12:45 UTC, relayed by the PM coordinator: "Ship the 'received …'
wording plus a repair hint (\"send the list itself, not text holding JSON\"). No relaxation of AIA's
strict check. If a real failure later shows \"received text\", decide on accepting it then." So
chunks 1 and 2 are built, (b) is deferred as chunk 3, (c) is not built. Strict validation is
unchanged: every shape that was refused before is still refused.

Built:

- `validate_structured_output` appends `, received <JSON type>` to a Pydantic wrong-type error (the
  type of `error["input"]`, never its value; nothing appended when no input was recorded), and its
  verdict carries `container_as_string` when a field declared a list, tuple, set, object or map
  arrived as a string (`domain/ai_contracts.py`, `_received`, `_CONTAINER_TYPE_ERRORS`). Tests:
  `test_a_wrong_json_type_is_named_in_the_violation[string|null|object]`,
  `test_a_container_sent_as_a_string_is_still_refused_and_flagged[as_list|as_tuple|as_set|as_map|as_model]`,
  `test_a_scalar_sent_as_a_string_is_not_flagged`.
- The gateway's repair turn adds one line under the violations when `container_as_string`, and that
  repair's ledger note records `repair_hint=container-as-string-v1` beside the unchanged
  `repair_prompt=schema-repair-v1` / `schema-repair-tool-v1`. The note names exactly the
  instruction sent; a repair without the hint sends the same instruction as before
  (`application/model_gateway.py`, `CONTAINER_HINT_VERSION`, `_repair_message`, `_note`). Tests:
  `test_a_list_sent_as_a_string_is_named_and_the_repair_asks_for_the_list`,
  `test_no_container_hint_for_any_other_violation`.

Measured cost: no new call, no new latency. A hinted repair sends one more line (~25 tokens) on a
call that was already being made, so no kill switch: the burst size is zero.

### Review outcomes (`/code-review`, 2026-10-28)

- Fixed: the hint's prompt identity (a v2 bump would not say which repairs carried it; now the hint
  has its own version on the note), set and frozenset fields, and a missing `input` read as null.
- Left: the analysis harness builds its own repair turn (`domain/analysis/harness.py`), so analysis
  modules get the `received …` wording but not the hint. The fix chosen was for the design-job
  path; widening it to analysis is a follow-up for the product owner.
- Left: an analysis outcome stores the violation's detail, so a module refused after this deploy
  reads `…, received string` where one refused before reads without it. The Blokované nároky
  grouping keys on the violation code, not the detail.

Follow-ups 4 and 5: the product owner, 2026-10-28 ~12:50 UTC, relayed by the PM coordinator, chose
all three follow-ups. The third (the route model to Sonnet 5.5) is the infra session's; chunk 4 must
work on whichever route model is in force.

## Proposal (put to the coordinator before building)

- **(a) Repair hint.** The violation names what arrived, and when a list or object field
  received a string, the repair turn adds one line: send the array or object itself, not a string
  holding JSON. It costs one more paid call per failure and may still fail: here the repair
  already saw `tracked_sets` named, and failed again.
- **(b) Narrow typed decoding.** Only for a provider-native tool answer. A string is decoded only
  where the contract's schema declares an array or object at that exact location, and only if
  `json.loads` yields exactly that container. The decoded value then goes through the same strict
  validation. A scalar is never coerced (`"12"` stays not an integer), and every other mismatch is
  still refused. The decoding is recorded on the call's ledger note, so it is visible. It saves the
  repair call, but it accepts an answer the model did not send in its declared form.
- **(c) Keep the refused answer** (bounded) on the attempt, as analysis already does. Rejected for
  now: it is Class B material in a column no rule classifies, and chunk 1 answers the diagnostic
  question without storing text.

### F2. The research-agent path drops the refused answer that analysis keeps

1. **Claim.** A design job's refused answer is carried on `ModelCallFailed.rejected_output` and then
   lost, so no schema failure of a design job can be diagnosed after the fact. Analysis keeps it.
2. **Anchor.** `packages/aia_core/src/aia_core/domain/ai_execution.py:165-176 @ 848f015b`
   (`recovery_inputs`, no `rejected_output`), against
   `apps/executors/src/aia_executors/analysis.py:450 @ 848f015b`, which keeps it. Bedrock
   invocation logging is off in eu-central-1 (the product owner's console read, 2026-10-28, ADR 0010
   activation evidence, "Retention, 2026-10-28"), so no copy exists outside AIA either.
3. **Reproduction.** Any test that makes a research agent fail with `structured_output_invalid` and
   reads the attempt's error: it has no answer text. For example, a scripted adapter answering
   twice off-contract under `ResearchAgentExecutor`.
4. **Consequence.** The develop failure of 2026-10-28 (RUN-4486b029e2c74102) cannot be told apart
   between a string-encoded list, null and an object. Chunk 1 now records the type for new failures.
5. **Smallest fix.** Not built. Keeping the bounded answer in error_json, as analysis does, would
   put the model's answer about a Class B design (up to 65,536 characters, `MAX_REJECTED_OUTPUT_CHARS`)
   in a column that no material rule classifies and that the run reads expose. Chunk 1's received
   type answers the diagnostic question without storing text. If the text is wanted, it belongs in a
   classified artifact of the run, not error_json. That is a decision for the product owner.
6. **Test.** One that asserts what a failed design job's attempt keeps.

## Doc follow-up

- `AGENTS.md` (Pydantic): strict JSON mode reports a string, null or object for a list field with the
  same `msg`. Read `error["input"]` to say what arrived.
- `docs/architecture/ai-runtime.md:257 @ 848f015b` (the repair call, `schema-repair-v1`): add that a
  repair answering a list or object sent as a string carries one more line, recorded on its note as
  `repair_hint=container-as-string-v1`, and that a wrong-type violation names the JSON type received.
- `.planning/open-items.md`: F2, the research-agent path keeping no refused answer.
