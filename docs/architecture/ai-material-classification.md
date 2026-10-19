# Model-input classification by content

Native design, respondent, analysis and Deep Research calls do not infer a data
class from a client or Study label. `AIA_AI_FICTIONAL_CLIENT_IDS` is retained for
configuration compatibility; it grants no classification in these executors.

## Classes by rule (the product owner, 2026-10-19)

Some material takes its class by a rule of the code and the owner
(`packages/aia_core/src/aia_core/domain/material_rules.py`, ADR 0008's amendment of
2026-10-19). Every model caller of that material reads its class from there:

| Material | Class | Rule (`source` in a provenance) |
|---|---|---|
| A study's design: brief, research questions, questionnaire, audience, the attachment excerpts it carries | B | `rule:design` |
| The study's and its client's names | B | `rule:study_name` |
| A researcher's message and focus label to the Research Lead, earlier messages included | B (the study's class) | `rule:lead_message` |
| A researcher's instruction to an AI design job | B (the study's class) | `rule:job_instruction` |
| The Lead's name, SOUL, USER and personal notes | C | `rule:lead_files` |
| The Lead's client-scoped notes | A | `rule:client_note` |
| Approved Client Knowledge | A | `rule:knowledge` |
| A client's uploaded source or dataset | A | `rule:client_source` |
| A client source a person marked "Interní dokument" | C | `rule:internal_document` |

AIA's own prompts keep their own rule: the code's wording is Class C, a stored edit
travels on its author's declaration (`prompt_data_class`). Material no rule names is
still unknown and refuses dispatch (`egress_unclassified_material`): an undeclared
prompt edit, an earlier Lead reply of unknown class, a Lead note of a scope no rule
names. A rule classifies; it approves no route, grants no licence and changes no
budget: a route not approved for Class B still refuses a design.

## Operator classifications

The worker reads `AIA_AI_MATERIAL_CLASSIFICATIONS`, a JSON array of operator
records. Each record names `sha256`, `data_class`, `provenance` and an optional
`synthetic` boolean (default false). The hash is SHA-256 of the exact value's
canonical JSON (UTF-8, sorted keys, no whitespace between members). Use
`aia_core.domain.ai_material.material_sha256`; do not hash a pretty-printed file.
The record is trusted deployment configuration, never a field inside submitted
design content. Duplicate hashes, malformed classes and missing source descriptions
refuse worker startup.

Beside a rule, an operator's classification of the exact bytes can only make the
class stricter, never looser (`classify_by_rule`): an operator who finds client
material in a design raises it to Class A, and the provenance names `operator` as
the source. An operator's Class C for a design leaves it at B.

The operator must inspect the material's actual sources before recording its
class. A synthetic fixture is Class C only when every part was generated as
synthetic: title, brief, pasted passages, all extracted attachment text and
instructions. Labeling its surrounding client fictional proves none of that.
Mixed material needs its most restrictive class.

## Where each caller classifies

Design assistants classify the sanitized design copied into their frozen context
(`rule:design`) and each nonempty instruction (`rule:job_instruction`). The
Research Lead classifies each part of its frozen context and records every part's
class and source with the turn (`context_classification`). Approved Client
Knowledge keeps Class A regardless of the design's class. Fieldwork and analysis
classify the immutable Design Revision of their run by `rule:design`; the
independently validated dataset/persona provenance can raise, never lower, that
class. Deep Research verifies the design belongs to the held Study before checking
its classification, which is still the operator's exact-bytes record alone: its web
routes carry Class C only, and a query inherits the class of what it was written
from, so a rule raising every design to B would refuse every web track (plan
`usable-classification`, Findings). Its queries still pass the retrieval gate.

A `synthetic: true` record marks generated test provenance for Deep Research's
existing internal-only acceptance rules. Public material can be Class C without
being synthetic. Classification does not approve a route, grant a licence, change
a study budget or activate any AI stage.

Tests: `test_ai_material.py`, `test_material_rules.py`,
`test_an_edited_design_or_instruction_is_sent_as_class_b_by_rule`, and the
real-worker suites for AI respondents, analysis and Deep Research.
