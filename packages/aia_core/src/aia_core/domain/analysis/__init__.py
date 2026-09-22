"""Analysis & Reporting: the eight durable analysis modules, gated by the evidence layer.

A model drafts; :func:`check_analysis_draft` decides; only an
:class:`AnalysisModuleResult` built from admitted claims leaves this package.
Reporting is deliberately absent: it is built on top of results, after the
evidence layer is enforceable (``.planning/plans/evidence-governance-foundation.md``).
"""

from .draft import (
    AnalysisDraft,
    DraftCheck,
    FindingDraft,
    NumericClaimDraft,
    ResearchQuestionAnswerDraft,
    check_analysis_draft,
    numbers_in,
    uncovered_numbers,
)
from .modules import (
    ANALYSIS_MODULES,
    AnalysisModuleId,
    AnalysisModuleSpec,
    module_input_fingerprint,
    module_spec,
    modules_to_run,
)
from .prompt import (
    PROMPT_TEMPLATE_VERSION,
    module_payload,
    prompt_template_sha256,
    repair_prompt,
    system_prompt,
)
from .result import (
    AnalysisModuleResult,
    Finding,
    ResearchQuestionAnswer,
    UnbackedResult,
    result_from_check,
)

__all__ = [
    "ANALYSIS_MODULES",
    "PROMPT_TEMPLATE_VERSION",
    "AnalysisDraft",
    "AnalysisModuleId",
    "AnalysisModuleResult",
    "AnalysisModuleSpec",
    "DraftCheck",
    "Finding",
    "FindingDraft",
    "NumericClaimDraft",
    "ResearchQuestionAnswer",
    "ResearchQuestionAnswerDraft",
    "UnbackedResult",
    "check_analysis_draft",
    "module_input_fingerprint",
    "module_payload",
    "module_spec",
    "modules_to_run",
    "numbers_in",
    "prompt_template_sha256",
    "repair_prompt",
    "result_from_check",
    "system_prompt",
    "uncovered_numbers",
]
