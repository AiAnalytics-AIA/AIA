"""A respondent system's confirmation run: its graph, questionnaire and cost (7e3).

A confirmation run is made from one stored preregistration (:mod:`.preregistration`) and
nothing else that could move:

- **The graph** (:func:`validation_steps`) has one ``sample`` step: the n respondents, drawn
  once under the preregistered seed. Then one ``arm_<X>_<k>`` step per model arm and replicate,
  each depending on the sample alone. Last, one ``score`` step that depends on every arm and
  computes the code baselines L0 and L1 with the verdict. Every step reads the population
  the run recorded.
- **The questionnaire** (:func:`validation_specification`) is the confirmation items as the
  source survey fielded them: each a single choice, its options in the fielded order, so an
  option's position is its code's. Items come in the preregistered block order. An item whose
  wording code would answer as a persona fact (``respondent_facts``) is refused: code, not the
  model, would answer it, from a field the respondent is given.
- **The cost** (:func:`validation_requests`, :func:`validation_cost_ceiling`) is one request per
  respondent, block, model arm and replicate, each at the fieldwork reservation. The code
  baselines cost nothing.
- **The system** (:func:`system_mismatch`) is checked at start against everything this code
  pins and the population the run records. The model binding is resolved by the gateway at the
  first request, so the arm step checks that one (7e4).

The workflow is not a ``workflow_templates`` type, because its graph is the preregistration's:
the application service creates the run from :func:`validation_steps`, as Deep Research's does.

Pure: stdlib and the domain.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from ..evidence.validation import RESPONDENT_SYSTEM_COMPONENTS
from ..research_design import COMPILER_VERSION, ResearchSpecification, SpecQuestion
from ..respondent_facts import FactStatus, classify_question
from ..workflow import StepDefinition
from .bank import ItemBank
from .preregistration import HoldoutRefused, Preregistration

__all__ = [
    "ARM_KIND",
    "SAMPLE_KIND",
    "SCORE_KIND",
    "VALIDATION_PROJECT_OWNER",
    "VALIDATION_WORKFLOW",
    "arm_node_key",
    "preregistered_blocks",
    "shuffle_seed",
    "system_mismatch",
    "validation_cost_ceiling",
    "validation_requests",
    "validation_specification",
    "validation_steps",
]

#: The workflow type a confirmation run is created with.
VALIDATION_WORKFLOW: Final = "respondent_validation"
#: ``projects.owner`` of a validation Study's own project, which no generic route sees.
VALIDATION_PROJECT_OWNER: Final = "study_validation"
SAMPLE_KIND: Final = "holdout_sample"
ARM_KIND: Final = "holdout_arm"
SCORE_KIND: Final = "holdout_score"
#: What a confirmation run is titled in its questionnaire.
_TITLE: Final = "Validace respondentního systému"


def arm_node_key(arm: str, replicate: int) -> str:
    """The step of ``arm``'s ``replicate`` (1-based)."""
    return f"arm_{arm}_{replicate}"


def _model_arms(preregistration: Preregistration) -> tuple[str, ...]:
    return tuple(str(a) for a in preregistration.document["model_arms"])


def _replicates(preregistration: Preregistration) -> int:
    return len(preregistration.document["replicate_seeds"])


def preregistered_blocks(preregistration: Preregistration) -> tuple[tuple[str, ...], ...]:
    """The request blocks, as preregistered: each a tuple of item fields, in order."""
    return tuple(
        tuple(str(i) for i in block["items"]) for block in preregistration.document["blocks"]
    )


def shuffle_seed(replicate_seed: int) -> int:
    """The shuffled arm's derangement seed for a replicate: the replicate's own seed.

    The derangement draws under its own namespace (``arms.derangement``), so sharing the seed
    with the replicate's answer draw correlates nothing. It is fixed by the preregistration,
    since the replicate seed is.
    """
    return replicate_seed


def validation_steps(preregistration: Preregistration) -> list[StepDefinition]:
    """The confirmation run's graph: sample, then each model arm x replicate, then score."""
    arms = [
        arm_node_key(arm, k)
        for arm in _model_arms(preregistration)
        for k in range(1, _replicates(preregistration) + 1)
    ]
    steps = [
        StepDefinition(
            node_key="sample",
            kind=SAMPLE_KIND,
            stage_type="SAMPLE_PLAN",
            artifact_target="holdout_sample",
            max_attempts=3,
            consumes_population=True,
        )
    ]
    steps.extend(
        StepDefinition(
            node_key=key,
            kind=ARM_KIND,
            depends_on=("sample",),
            stage_type="FIELDWORK",
            artifact_target="holdout_arm_answers",
            # As research fieldwork: every request is journaled, so a retry never pays twice.
            max_attempts=3,
            consumes_population=True,
        )
        for key in arms
    )
    steps.append(
        StepDefinition(
            node_key="score",
            kind=SCORE_KIND,
            depends_on=tuple(arms),
            stage_type="ANALYSIS",
            artifact_target="holdout_verdict",
            max_attempts=3,
            consumes_population=True,
        )
    )
    return steps


def validation_specification(
    bank: ItemBank, preregistration: Preregistration
) -> ResearchSpecification:
    """The confirmation items as a questionnaire, in the preregistered block order.

    Refuses a bank that is not the preregistered one (``holdout_bank_mismatch``) and an item
    that code would answer as a fact (``holdout_item_is_a_fact``).
    """
    if bank.sha256 != preregistration.document["bank_sha256"]:
        raise HoldoutRefused(
            "the item bank is not the one preregistered", reason="holdout_bank_mismatch"
        )
    questions = []
    for block in preregistered_blocks(preregistration):
        for field in block:
            try:
                item = bank.item(field)
            except KeyError:
                raise HoldoutRefused(
                    f"{field} is not in the item bank", reason="holdout_bank_mismatch"
                ) from None
            question = SpecQuestion(
                id=item.field,
                section_id=f"holdout-{item.domain}",
                text=item.wording,
                typ="vyber",
                options=tuple(o.label for o in item.options),
            )
            if classify_question(question, set()).status is not FactStatus.NOT_FACT:
                raise HoldoutRefused(
                    f"{field}'s wording is answered by code as a fact, not by the respondent",
                    reason="holdout_item_is_a_fact",
                )
            questions.append(question)
    return ResearchSpecification(
        compiler_version=COMPILER_VERSION,
        title=_TITLE,
        n=int(preregistration.document["n"]),
        questions=tuple(questions),
        batteries=(),
        audience={},
    )


def validation_requests(preregistration: Preregistration) -> int:
    """The most model requests the run makes: respondents x blocks x model arms x replicates."""
    return (
        int(preregistration.document["n"])
        * len(preregistered_blocks(preregistration))
        * len(_model_arms(preregistration))
        * _replicates(preregistration)
    )


def validation_cost_ceiling(
    preregistration: Preregistration, reservation_usd: float | None
) -> float | None:
    """The most the run can cost, each request at the fieldwork reservation.

    ``None`` when the reservation is unknown: unknown is never zero.
    """
    if reservation_usd is None or not reservation_usd > 0:
        return None
    return validation_requests(preregistration) * reservation_usd


def system_mismatch(
    preregistration: Preregistration, current: Mapping[str, Any]
) -> tuple[str, ...]:
    """The components of the preregistered respondent system that ``current`` contradicts.

    ``current`` names every component but ``model_binding``, which only the gateway resolves;
    a component it names differently, or does not name, is a mismatch.
    """
    pinned = preregistration.document["respondent_system"]["components"]
    return tuple(
        name
        for name in RESPONDENT_SYSTEM_COMPONENTS
        if name != "model_binding" and current.get(name) != pinned.get(name)
    )
