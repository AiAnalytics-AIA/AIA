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

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Final

from ..evidence.validation import RESPONDENT_SYSTEM_COMPONENTS
from ..population.sampling import PanelSample
from ..research_design import COMPILER_VERSION, ResearchSpecification, SpecQuestion
from ..respondent_facts import FactStatus, classify_question
from ..workflow import StepDefinition
from .bank import ItemBank, canonical_json
from .preregistration import HoldoutRefused, Preregistration
from .scoring import ArmRun

__all__ = [
    "ARM_ARTIFACT",
    "ARM_KIND",
    "SAMPLE_ARTIFACT",
    "SAMPLE_KIND",
    "SCORE_KIND",
    "VALIDATION_PROJECT_OWNER",
    "VALIDATION_WORKFLOW",
    "arm_node_key",
    "arm_record",
    "preregistered_blocks",
    "read_arm_record",
    "sample_sha256",
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
#: The artifacts the sample and arm steps write.
SAMPLE_ARTIFACT: Final = "holdout_sample"
ARM_ARTIFACT: Final = "holdout_arm_answers"
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
            labels = [o.label for o in item.options]
            if len(set(labels)) != len(labels):
                raise HoldoutRefused(
                    f"{field}'s option labels repeat; an answer could not name its code",
                    reason="holdout_option_labels_repeat",
                )
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


def sample_sha256(sample: PanelSample) -> str:
    """The sample's identity: who was drawn, in order, with their weights, from which version.

    Every arm and the score re-draw the sample under the preregistered seed and compare this
    with the sample step's record, so all of them ask and score exactly the same people.
    """
    return hashlib.sha256(
        canonical_json(
            {
                "version_id": sample.version_id,
                "content_sha256": sample.content_sha256,
                "seed": sample.seed,
                "respondents": [
                    [r.row, r.donor, repr(r.base_weight), repr(r.analysis_weight)]
                    for r in sample.respondents
                ],
            }
        )
    ).hexdigest()


def _answer_missing(message: str) -> HoldoutRefused:
    return HoldoutRefused(message, reason="holdout_answer_missing")


def arm_record(
    spec: ResearchSpecification,
    codes: Mapping[str, Sequence[str]],
    rows: Sequence[tuple[str, Mapping[str, Any]]],
    details: Sequence[Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """One arm replicate's answers as codes, and the probabilities they were drawn from.

    ``rows`` are each respondent's id and drawn answers (an option label), ``details`` what the
    draw recorded per item, in the same order. A label is mapped back to its code by its position
    in the fielded order. Every item has an answer and a probability over every option for every
    respondent, or the record is refused (``holdout_answer_missing``): a missing answer is never
    scored as any answer.
    """
    if len(rows) != len(details):
        raise _answer_missing("every respondent's answers need their draw's record")
    answers: dict[str, dict[str, str]] = {}
    probabilities: dict[str, dict[str, list[float]]] = {}
    for question in spec.questions:
        item_codes = list(codes.get(question.id, ()))
        if len(item_codes) != len(question.options):
            raise _answer_missing(f"{question.id}: its codes are not its options")
        by_label = dict(zip(question.options, item_codes, strict=True))
        answers[question.id] = {}
        probabilities[question.id] = {}
        for (respondent, drawn), detail in zip(rows, details, strict=True):
            label = drawn.get(question.id)
            meta = detail.get(question.id) or {}
            probs = meta.get("probabilities")
            if label not in by_label or not isinstance(probs, list):
                raise _answer_missing(f"{respondent} has no answer to {question.id}")
            if len(probs) != len(item_codes):
                raise _answer_missing(f"{respondent}'s {question.id} draw is not over its options")
            answers[question.id][respondent] = by_label[label]
            probabilities[question.id][respondent] = [float(p) for p in probs]
    return {"answers": answers, "probabilities": probabilities}


def read_arm_record(arm: str, replicate: int, record: Mapping[str, Any]) -> ArmRun:
    """An arm replicate's stored record as the scoring reads it."""
    answers = {
        (str(item), str(respondent)): str(code)
        for item, by in record["answers"].items()
        for respondent, code in by.items()
    }
    probabilities = {
        (str(item), str(respondent)): tuple(float(p) for p in probs)
        for item, by in record["probabilities"].items()
        for respondent, probs in by.items()
    }
    return ArmRun(arm=arm, replicate=replicate, answers=answers, probabilities=probabilities)
