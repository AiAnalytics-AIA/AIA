"""The class a study's material takes by rule: the product owner's decision of 2026-10-19.

ADR 0008's amendment of that date. Before it, a study's design, its name and a researcher's
message to the Research Lead had a class only when an operator classified their exact bytes
(:mod:`aia_core.domain.ai_material`), and a chat message is new bytes every time: the Lead and
the AI design jobs never ran on an edited design (OI-126). The owner decided which material
takes which class *by rule*:

* :attr:`MaterialRule.DESIGN`, **B**: a study's design (brief, research questions,
  questionnaire, audience, the attachment excerpts the design carries).
* :attr:`MaterialRule.STUDY_NAME`, **B**: the study's and its client's names.
* :attr:`MaterialRule.LEAD_MESSAGE`, **B**: a researcher's message and focus label to the Lead.
* :attr:`MaterialRule.JOB_INSTRUCTION`, **B**: a researcher's instruction to an AI design job.
* :attr:`MaterialRule.LEAD_FILES`, **C**: the Lead's name, SOUL, USER and personal notes (they
  change only on the researcher's explicit "Pamatovat si").
* :attr:`MaterialRule.CLIENT_NOTE`, **A**: the Lead's client-scoped notes.
* :attr:`MaterialRule.KNOWLEDGE`, **A**: approved Client Knowledge.
* :attr:`MaterialRule.CLIENT_SOURCE`, **A**: a client's uploaded source or dataset.
* :attr:`MaterialRule.INTERNAL_DOCUMENT`, **C**: a client source a person marked
  "Interní dokument" (an internal AIA document holding nothing of the client's).

A researcher's message "takes the study's class" (:data:`STUDY_CLASS`), and so does their
instruction to a design job: the same kind of text, typed to an AI in the same study.

A rule is a decision of the code and the owner, never a default: material no rule names is
still unknown and refuses dispatch (``egress_unclassified_material``). An operator's exact-bytes
classification still applies beside a rule and can only make it stricter, never looser
(:func:`classify_by_rule`), as :func:`~aia_core.domain.research_agents.prompt_data_class` takes
the more restrictive of a declaration and an operator's classification.

No I/O: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from .ai_material import MaterialApproval, classify_material, most_restrictive_material
from .residency import DataClass

__all__ = [
    "DESIGN_CLASS",
    "OPERATOR_SOURCE",
    "RULE_CLASSES",
    "STUDY_CLASS",
    "MaterialRule",
    "RuledMaterial",
    "classify_by_rule",
    "rule_class",
    "source_rule",
]


class MaterialRule(StrEnum):
    """A rule by name; its value is the source a provenance records (``rule:<name>``)."""

    DESIGN = "rule:design"
    STUDY_NAME = "rule:study_name"
    LEAD_MESSAGE = "rule:lead_message"
    JOB_INSTRUCTION = "rule:job_instruction"
    LEAD_FILES = "rule:lead_files"
    CLIENT_NOTE = "rule:client_note"
    KNOWLEDGE = "rule:knowledge"
    CLIENT_SOURCE = "rule:client_source"
    INTERNAL_DOCUMENT = "rule:internal_document"


#: A study's class: its design is derived client information (the owner, 2026-10-19).
STUDY_CLASS: Final = DataClass.CLASS_B_DERIVED_CLIENT
#: A study's design, its attachment excerpts included.
DESIGN_CLASS: Final = STUDY_CLASS

#: Every rule's class. One definition: every model caller of study material reads it here.
RULE_CLASSES: Final[Mapping[MaterialRule, DataClass]] = MappingProxyType(
    {
        MaterialRule.DESIGN: DESIGN_CLASS,
        MaterialRule.STUDY_NAME: STUDY_CLASS,
        MaterialRule.LEAD_MESSAGE: STUDY_CLASS,
        MaterialRule.JOB_INSTRUCTION: STUDY_CLASS,
        MaterialRule.LEAD_FILES: DataClass.CLASS_C_INTERNAL,
        MaterialRule.CLIENT_NOTE: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        MaterialRule.KNOWLEDGE: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        MaterialRule.CLIENT_SOURCE: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        MaterialRule.INTERNAL_DOCUMENT: DataClass.CLASS_C_INTERNAL,
    }
)

#: The source a provenance records when an operator's classification was stricter than the rule.
OPERATOR_SOURCE: Final = "operator"


def rule_class(rule: MaterialRule) -> DataClass:
    """The class ``rule`` gives its material, before any operator's classification."""
    return RULE_CLASSES[rule]


def source_rule(*, internal: bool) -> MaterialRule:
    """The rule for a client's source: an internal AIA document a person marked
    "Interní dokument" (Class C), else the client's own material (Class A)."""
    return MaterialRule.INTERNAL_DOCUMENT if internal else MaterialRule.CLIENT_SOURCE


class RuledMaterial(BaseModel):
    """One piece of material's class, and who answered for it: the rule, or an operator whose
    classification of these exact bytes is stricter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: MaterialRule
    #: ``material_sha256`` of the value, the digest an operator's classification names.
    sha256: str
    data_class: DataClass
    #: ``rule:<name>``, or :data:`OPERATOR_SOURCE` when the operator raised it.
    source: str
    operator_class: DataClass | None
    operator_provenance: str | None


def classify_by_rule(
    value: Any, rule: MaterialRule, approvals: Sequence[MaterialApproval]
) -> RuledMaterial:
    """``value``'s class under ``rule``, raised (never lowered) by an operator's classification
    of its exact bytes."""
    operator = classify_material(value, approvals)
    by_rule = rule_class(rule)
    known = [by_rule] if operator.data_class is None else [by_rule, operator.data_class]
    data_class = most_restrictive_material(known)
    assert data_class is not None  # every class in ``known`` is a class
    return RuledMaterial(
        rule=rule,
        sha256=operator.sha256,
        data_class=data_class,
        source=rule.value if data_class is by_rule else OPERATOR_SOURCE,
        operator_class=operator.data_class,
        operator_provenance=operator.provenance,
    )
