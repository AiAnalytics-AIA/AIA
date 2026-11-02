"""A questionnaire table given to the Lead, read and filed as a proposal (lead-orchestration LO18b).

The file is a client's source a message carries (LO18a). When it is a CSV or XLSX in AIA's
questionnaire template, the template import reads it with no model (``questionnaire_file``):
a table without the template's columns is not a questionnaire and stays LO18a's file alone;
one that breaks a template rule is refused in the import's words and files nothing. The
proposal is an ordinary questionnaire job (``ResearchAgentJobs.start_import``), keyed by the
message and the file, so asking twice files once.
"""

from __future__ import annotations

from typing import Final

from ..domain.ai_contracts import canonical_json
from ..domain.lead_files import LeadFileRef, QuestionnaireOutcome
from ..domain.questionnaire_from_file import IMPORT_MAX_BYTES
from ..domain.questionnaire_import import ImportedQuestionnaire, QuestionnaireImportRejected
from ..domain.scope import StudyContext
from ..infrastructure.client_source_repository import ClientSourceRepository
from ..infrastructure.questionnaire_file import import_questionnaire

__all__ = [
    "EMPTY_QUESTIONNAIRE",
    "ONE_QUESTIONNAIRE",
    "TABLE_SUFFIXES",
    "questionnaire_key",
    "read_table",
]

#: The files the template import reads.
TABLE_SUFFIXES: Final = (".csv", ".xlsx")
#: The import's refusals that do not say the template was meant (no template columns, no sheet,
#: nothing readable as the template's text): the table stays LO18a's file alone. Any other
#: refusal (a row breaking a template rule) is the template meant and broken: said, not filed.
_NOT_THE_TEMPLATE: Final = frozenset(
    {"missing_columns", "unsupported_format", "no_sheet", "unreadable", "empty", "no_file"}
)
#: A template with no question or tracked set: nothing to propose, and a replace with it would empty
#: the questionnaire.
EMPTY_QUESTIONNAIRE: Final = "questionnaire_empty"
#: A message's second questionnaire table: one proposal a message.
ONE_QUESTIONNAIRE: Final = "one_questionnaire_per_message"
#: The most of the import's own words a refusal keeps.
_MESSAGE_MAX: Final = 500


def questionnaire_key(turn_id: str, source_id: str) -> str:
    """The proposal job's idempotency key: one per message and file."""
    return f"questionnaire_import:{turn_id}:{source_id}"


def read_table(
    sources: ClientSourceRepository, scope: StudyContext, ref: LeadFileRef
) -> ImportedQuestionnaire | QuestionnaireOutcome | None:
    """The file read by the template import: its questionnaire, a ``refused`` outcome with the
    import's reason, or ``None`` when it is not a questionnaire table at all."""
    if not ref.filename.lower().endswith(TABLE_SUFFIXES):
        return None
    try:
        imported = import_questionnaire(sources.lead_original(scope, ref), ref.filename)
    except QuestionnaireImportRejected as exc:
        if exc.reason in _NOT_THE_TEMPLATE:
            return None
        return QuestionnaireOutcome(
            status="refused", reason=exc.reason, message=str(exc)[:_MESSAGE_MAX]
        )
    if not imported.sections:
        return QuestionnaireOutcome(status="refused", reason=EMPTY_QUESTIONNAIRE)
    if len(canonical_json(imported.sections).encode("utf-8")) > IMPORT_MAX_BYTES:
        return QuestionnaireOutcome(status="refused", reason="questionnaire_too_large")
    return imported
