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

## Chunk 4 research: schema-enforced output (read-only, 2026-10-28)

### What the provider offers

Sources: Anthropic's own pages, read today (docs.aws.amazon.com is not reachable from this session):
[Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) and
[Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use).
AWS's page, <https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html>, is
known only through a search summary. It still needs to be read: see "Open, for the product owner's
read" below.

- **Two mechanisms, one grammar.** `strict: true` on a tool definition constrains the tool's
  `input` to its schema by grammar-constrained sampling. Structured outputs puts a JSON schema on
  the answer text. On Converse these are, per the search summary of AWS's page, `strict: true` on
  the tool and `outputConfig.textFormat`. Both share one compile pipeline. The strict tool is the
  one that fits AIA: the adapter already sends one output tool (`bedrock.py:240-247 @ b7a0231e`).
- **Models.** Anthropic's page lists `claude-sonnet-4-5-20250929` and `claude-sonnet-5-5` among the
  supported models, with Amazon Bedrock "ga". Whether the **EU inference profiles** carry it, and in
  eu-central-1, is not stated there. That is the one fact to read from AWS.
- **What it would fix.** Constrained sampling cannot emit a string where the schema says array, so
  the 2026-10-28 shape could not occur. Anthropic: "With `strict: true`, the response always
  contains `passengers: 2`", not `"2"`.
- **What it does not guarantee.** A truncated answer (`max_tokens`) or a refusal "might not match
  your schema", and an enum can differ in case. AIA's strict validator stays after the call either
  way, as the plan requires.
- **Limits per request.**
  - 20 strict tools; AIA sends 1.
  - 24 optional parameters and 16 union-typed parameters, across all strict schemas.
  - An internal grammar-size limit, answered with a 400 "Schema is too complex for compilation".
  - A 180 s compile timeout. A new schema's first request compiles, and the compiled grammar is
    cached for 24 h.
- **The schema is cached apart from the messages.** Anthropic says PHI must not be put in property
  names, `enum` or `const` values or `pattern`s, because cached schemas "do not receive the same
  PHI protections". AIA's schemas are built by code from contracts. The respondent block contract
  keys items by their id (`ai_respondent.py:563-580 @ b7a0231e`), never by question text. Before any
  build, a test should hold that no client text can reach a sent schema.
- **Thinking and tool_choice.** Anthropic's pages show strict tools with no `tool_choice`, which is
  `auto`, so they work beside the `auto_tool` profile Sonnet 5.5 needs. Neither page says whether
  strict sampling holds with extended or adaptive thinking on. This goes to the AWS read.

### What AIA's contracts use that the grammar refuses

Measured by walking `output_schema()` of every agent contract (22 contracts, script in the session
scratchpad; to be committed as a test with the build):

- **Every contract** carries `minLength` / `maxLength` and `maxItems`. The supported subset has
  no string-length constraints, no `maxItems`, and `minItems` only 0 or 1.
- **BriefAnalysis:** 11 `maxLength`, 5 `minLength`, 9 `maxItems`, one `minItems` > 1, and one
  `prefixItems` (`scale_labels: tuple[str, str]`). Tuples are not in the supported list.
- **QuestionnaireProposal:** 4 tuples, `minimum` / `maximum`, one `anyOf`.
- **The Lead's LeadOutput:** 14 KB, 18 optional fields (the limit is 24), 9 `anyOf`, 3 `oneOf` (not
  in the supported list), 8 `pattern`s.
- **AnalysisDraft:** 5 optional fields. AIA's own `schema_supports_strict` (an every-field-required
  rule from the OpenAI strict tier) refuses it and the Lead's contract. Anthropic's grammar allows
  optional fields up to 24, so that predicate is the wrong judge for this provider.

So no contract can be sent strict as it stands. The provider's SDK helpers handle this by sending a
**reduced schema**: the unsupported constraints are removed (and named in the field's description),
and the full contract is validated afterwards. For AIA that would be:

- The grammar enforces types, shapes, required fields and `additionalProperties: false`, which is
  the 2026-10-28 class of failure.
- AIA's validator still enforces lengths, counts, bounds and model validators, and their violations
  keep the one repair.

### Design proposal (not built; for the coordinator and the product owner)

1. **The profile.** The grammar is independent of forced versus auto: Sonnet 4.5 is forced, Sonnet
   5.5 is auto, and both are listed. So the proposal is a declared `RequestProfile.constrained: bool`
   beside `structured_output`, rather than two new `StructuredOutput` values (`FORCED_TOOL_STRICT`,
   `AUTO_TOOL_STRICT`) that would duplicate the axis. This differs from the brief's "a new
   `structured_output` value", so it is put up for the decision.
2. **The switch.** `AIA_BEDROCK_CONSTRAINED_OUTPUT`, off by default and off in test. On, it sends
   `strict: true` only where the resolved model's profile declares `constrained` and the reduced
   schema passes a local check of the documented subset. Anything else is sent as today, never
   rewritten into a request nobody priced.
3. **The reduced schema** (`domain/ai_contracts.py`, pure). This is the contract's schema minus the
   unsupported keywords:
   - a tuple sent as an array of its item type, if `prefixItems` turns out to be unsupported;
   - `oneOf` makes a contract ineligible rather than being rewritten.

   It records its own fingerprint beside the contract's, so the ledger says which schema the model
   was held to. The validator is unchanged.
4. **Tests first.** Recorded Converse fixtures for a strict tool request and its answer: forced on
   4.5, auto on 5.5. A golden test over every contract's reduced schema (eligible or not, and why).
   A test that no sent schema carries client text.
5. **The probe** (Nigel's ok, through the coordinator). A few cents: one strict brief analysis on
   the route model in force, read for the 400s a schema would draw and the first-request compile
   latency. It runs outside the infra session's Sonnet 5.5 probe window.

### The AWS read (the product owner, 2026-10-28 ~15:15 UTC, relayed by the PM coordinator)

His summary of AWS's structured-output page, its Claude page, and the Sonnet 4.5 and 5.5 model cards.

**Request fields:**
- Strict tools: `toolConfig.tools[].toolSpec.strict: true`, beside `inputSchema.json`.
- Structured output: `outputConfig.textFormat = {type: "json_schema", structure: {jsonSchema:
  {schema: "<schema as a JSON string>", name, description}}}`.

**Models:**
- Sonnet 4.5 (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`) supports it, with eu-central-1 a
  Geo source. It is in the Legacy stage, end of life 2027-04-08.
- Sonnet 5.5 (`eu.anthropic.claude-sonnet-5-5`) supports it. Its EU Geo profile routes to
  Frankfurt, Stockholm, Milan, Spain, Ireland and Paris.

**Schema subset (Draft 2020-12):**
- Supported: basic types, `enum`, `const`, `anyOf`, `allOf` (limited), internal `$ref`, formats, and
  `pattern` without lookaround or backreferences.
- `minItems` only 0 or 1.
- Unsupported: `minimum`/`maximum`/`multipleOf`, `minLength`/`maxLength`, recursion, external
  `$ref`, and `additionalProperties` other than `false`, which every object must set or the request
  is a 400.
- Not mentioned, and treated here as unsupported: `prefixItems`, `oneOf`, `maxItems`.

**Limits:**
- At most **12 optional properties** per schema, nested objects counted. Anthropic's own page says
  24; Bedrock's is lower.
- At most **16 union-typed properties**.
- The first compile takes up to about 90 s, and AWS recommends a read timeout of at least 120 s
  (AIA's is 300 s).
- Compiled schemas are cached for 24 h from first access, encrypted with AWS-managed keys, and
  shared for identical schemas within the account.
- A too-low `maxTokens` gives incomplete JSON.

**Thinking and tool choice:**
- The structured-output pages say nothing on thinking.
- The Sonnet 5.5 card: adaptive thinking is on by default, and tool choice is "auto and none only".
- Structured output with citations is a 400.

### Revised eligibility (measured 2026-10-28 on `b7a0231e`)

The rules applied: the unsupported keywords are stripped; tuples are sent as plain arrays;
`oneOf`, recursion or an open object makes a contract ineligible; and a contract is ineligible over
12 optional properties or 16 union-typed properties.

**20 of the 22 agent contracts are eligible:**
- the 8 research actions (brief analysis, questionnaire build and optimize, audience, dimensions,
  and the 3 advice actions);
- analysis (5 optional properties);
- client-source proposals;
- Deep Research triage, planner, both extractors, verifier, synthesizer, independent verifier,
  brief synthesizer, lead and replan.

The respondent's block contracts are eligible too: probabilities, selection and open answer,
stripped of their bounds and lengths.

**Ineligible, and sent as today:**
- the Lead's `LeadOutput`: `oneOf`, and 18 optional properties against the limit of 12;
- the Deep Research investigator turn: 17 union-typed properties against 16, a margin of one.
  This count is per object property, and AWS's own counting may differ.

**What the grammar would no longer hold, AIA's validator still does:**
- string lengths;
- list lengths (the 9 tuples, `BriefAnalysis.scale_labels` among them, lose their fixed length 2;
  a probability vector loses its fixed width);
- numeric bounds;
- model validators.

Every pattern in the eligible contracts (`^Q[1-9]$`, `^T[1-9][0-9]{0,2}$`) is within the
supported regex subset.

### Which mechanism, per profile

**Strict tools (`toolSpec.strict`) for both profiles; not `outputConfig.textFormat`.**

- Sonnet 4.5 (`forced_tool`) keeps its forced tool, now strict.
- Sonnet 5.5 (`auto_tool`, tool choice "auto and none only") keeps its offered tool, now strict.
- The answer still arrives as `toolUse.input` through the adapter's one path (`bedrock.py:356-363 @
  b7a0231e`).

Why not `textFormat`: it would move the answer into text, add a second response path, and make the
auto-tool instruction contradict the request.

What strict tools do not cover: under `auto` the model may still answer in text instead of calling
the tool. That stays the gateway's `TEXT_INSTEAD_OF_TOOL` violation and its one repair.

**Open, for the probe.** Whether strict sampling holds while Sonnet 5.5 thinks adaptively. No page
says. The probe's one strict call on the route model in force answers it.

**Two risks the build must carry:**
- **Compile latency.** Every new schema compiles once, for up to about 90 s. Fieldwork builds a
  schema per questionnaire block, keyed by item ids, so the first respondent of each block in a new
  design waits. Propose fieldwork stays out of the first switch-on (a per-capability allowlist),
  with the design and analysis agents first.
- **Schema retention.** The 24 h schema cache is outside the message's protections. The test
  holding that no client text reaches a sent schema comes before the build.

## Chunk 5 draft: keeping the refused answer (for the product owner's approval; not built)

### The class: the request's, not a fixed B

The follow-up as chosen says "classed B like the design it came from". The code says a design job's
request is sent as the **most restrictive** of its parts
(`packages/aia_core/src/aia_core/domain/research_agents.py:791-799 @ b7a0231e`):

- the design, B by rule;
- a nonempty instruction, B by rule;
- the prompt (C for the code's own wording, otherwise what its author declared or an operator
  classified);
- **Class A for every approved knowledge item the snapshot carries**
  (`rule_class(MaterialRule.KNOWLEDGE)`).

So any job whose context carries approved knowledge is sent as Class A. Its answer is written from
that context and can repeat it. A fixed B would store a Class A answer as B, which is lower than what
it came from. The draft therefore gives the answer **the class its request was sent as**.

### The rule (draft wording for `domain/material_rules.py`)

```python
class MaterialRule(StrEnum):
    ...
    #: A model's answer that its output contract refused, kept for diagnosis. It takes the
    #: class its request was sent as (the product owner, <date>): an answer is written from
    #: its context and may repeat any of it, so it is never lower than that context.
    REFUSED_ANSWER = "rule:refused_answer"


def refused_answer_class(sent_as: DataClass) -> DataClass:
    """A refused answer's class: exactly the class its request was sent as."""
    return sent_as
```

`REFUSED_ANSWER` stays out of `RULE_CLASSES`. That map holds fixed classes, and this one is
inherited. Like every rule, an operator's exact-bytes classification can only raise it
(`classify_by_rule`).

### Where it is stored

- **An artifact, never `error_json`.** A new artifact type, `research_agent_refused_answer`, goes on
  the job's own design project, beside its `research_agent_proposal`
  (`apps/executors/src/aia_executors/research_agents.py:56 @ b7a0231e`). It is written only when
  the gateway fails the job with `structured_output_invalid`, and before the step fails.
  `error_json` stays as it is: reason, violations (now with the received type), call ids.
- **Payload.**
  - agent id and version, prompt version, call ids and the violations;
  - `rejected_output`: the last refused answer as `ModelCallFailed` carries it, at most
    65,536 characters (`MAX_REJECTED_OUTPUT_CHARS`, `ai_contracts.py:907 @ b7a0231e`);
  - `data_class`, and `class_source` `rule:refused_answer` (or `operator`).
- **Read by nobody but an operator at first.** No API route serves it, and it is not in any run
  read. If a person should see it later (for example under the run's Technical details), that is
  its own decision.
- **Precedent.** Analysis already keeps its refused answers inside its turn artifacts
  (`packages/aia_core/src/aia_core/domain/analysis/artifact.py:300-303 @ b7a0231e`), stored the
  same way and served by no route. The draft keeps the design jobs' the same way, with the class
  stated.

### Retention and deletion

- **Client deletion erases it.** It lives in the client's design project, and
  `delete_client` erases every artifact of the client's projects
  (`packages/aia_core/src/aia_core/application/client_deletion.py:209 @ b7a0231e`,
  `erase_client_projects`), then their stored objects.
- **Retention otherwise.** It lives as long as the design project's other artifacts. There is no
  separate expiry; a shorter one (for example 90 days) would be a new mechanism, offered only if
  wanted.

### Size

At most 65,536 characters per failed job, and only failed jobs write one. The develop failure's
answers were about 1,900 output tokens, roughly 8 KB.

### Questions for the product owner

1. **Class.** The request's class (A when the job carried approved knowledge, otherwise B), as
   drafted? Or a fixed B, as the follow-up was worded? Recommended: the request's class, which is
   never lower than the material it came from.
2. **Which answer.** The gateway hands back only the **last** refused answer, the repair's. The
   primary's answer is sent back to the model inside the repair turn, but it is not kept. Keeping
   both needs the gateway to carry the first too, a small change in `model_gateway.py`.
   Recommended: the last only for now, since it is the answer that ended the job.
3. **Who reads it.** Operator only at first, as drafted?
4. **Scope.** Design jobs only (chunk 5 as chosen)? Or every structured agent that fails the same
   way: the Lead, client-source proposals, Deep Research? Recommended: design jobs first, and the
   rest when one of them meets the same failure.

### Tests the build starts with (red first)

- A design job failing `structured_output_invalid` stores one `research_agent_refused_answer`
  with the last refused answer, bounded, and its class.
- A job that carried approved knowledge stores the answer as Class A; one without stores it as B.
- `error_json` carries no answer text.
- No API route serves the artifact.
- Deleting the client erases it, with its stored object.

## Doc follow-up

- `AGENTS.md` (Pydantic): strict JSON mode reports a string, null or object for a list field with the
  same `msg`. Read `error["input"]` to say what arrived.
- `docs/architecture/ai-runtime.md:257 @ 848f015b` (the repair call, `schema-repair-v1`): add that a
  repair answering a list or object sent as a string carries one more line, recorded on its note as
  `repair_hint=container-as-string-v1`, and that a wrong-type violation names the JSON type received.
- `.planning/open-items.md`: F2, the research-agent path keeping no refused answer.
