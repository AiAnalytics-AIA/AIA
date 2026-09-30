# Model-input classification by content

Native design, respondent, analysis and Deep Research calls do not infer a data
class from a client or Study label. `AIA_AI_FICTIONAL_CLIENT_IDS` is retained for
configuration compatibility; it grants no classification in these executors.

The worker reads `AIA_AI_MATERIAL_CLASSIFICATIONS`, a JSON array of operator
records. Each record names `sha256`, `data_class`, `provenance` and an optional
`synthetic` boolean (default false). The hash is SHA-256 of the exact value's
canonical JSON (UTF-8, sorted keys, no whitespace between members). Use
`aia_core.domain.ai_material.material_sha256`; do not hash a pretty-printed file.
The record is trusted deployment configuration, never a field inside submitted
design content. Duplicate hashes, malformed classes and missing source descriptions
refuse worker startup.

The operator must inspect the material's actual sources before recording its
class. A synthetic fixture is Class C only when every part was generated as
synthetic: title, brief, pasted passages, all extracted attachment text and
instructions. Labeling its surrounding client fictional proves none of that.
Mixed material needs its most restrictive class. New unknown text requires a new
classification and cannot inherit an earlier classification by editing the design.

Design assistants check the sanitized design actually copied into their frozen
context, and separately check each nonempty instruction. Approved Client Knowledge
keeps Class A regardless of the design's class. Missing design/instruction
classification refuses the entire request at gateway preflight. Fieldwork and
analysis check the immutable Design Revision of their run; the independently
validated dataset/persona provenance can raise, never lower, that class. Deep
Research verifies the design belongs to the held Study before checking its
classification. Its queries inherit that class and still pass the retrieval gate.

A `synthetic: true` record marks generated test provenance for Deep Research's
existing internal-only acceptance rules. Public material can be Class C without
being synthetic. Classification does not approve a route, grant a licence, change
a study budget or activate any AI stage.

Tests: `test_ai_material.py`, `test_allowlisted_client_cannot_send_unclassified_text`,
and the real-worker suites for AI respondents, analysis and Deep Research.
