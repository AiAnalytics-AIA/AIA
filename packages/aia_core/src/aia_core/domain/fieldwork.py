"""The fieldwork boundary (ADR 0016 decision 4): where respondent data comes from.

The research workflow's fieldwork step (node ``run``) has one job: produce a
:class:`FieldworkDataset` from a declared source. Every later step reads only that
dataset, so a new source -- the AI respondent engine, a client's own data -- is a
new producer of the same thing, not a change to aggregation or Sociomapping.

A run records its source when it is created; the worker executes only a source
its composition provides. The dataset says where it came from
(:class:`DataOrigin`), and everything computed from it inherits that origin.
Pure: no I/O.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .research_design import ResearchSpecification

__all__ = [
    "DATASET_VERSION",
    "NON_EVIDENCE_ORIGINS",
    "Answer",
    "DataOrigin",
    "FieldworkDataset",
    "FieldworkRespondent",
    "FieldworkSource",
    "InvalidDataset",
    "validate_dataset",
]

DATASET_VERSION: Final = "aia-fieldwork-dataset-1"


class FieldworkSource(StrEnum):
    """Who answers the questionnaire for a run."""

    #: The AI respondent engine (the Agent Runtime PR). Until it is deployed the
    #: fieldwork step parks the run waiting for it; nothing is fabricated.
    AI_RUNTIME = "ai_runtime"
    #: A fictional dataset for tests and the workbench. Refused by every deployed
    #: composition: the API's settings, the production executor registry, and the
    #: worker's own composition each refuse it (ADR 0016 decision 4, D1).
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class DataOrigin(StrEnum):
    """Where the respondent data behind an artifact came from, stamped on it.

    Every member so far is synthetic, and none is evidence: the evidence gate refuses
    a client-facing claim from any origin in :data:`NON_EVIDENCE_ORIGINS`.
    """

    #: Invented respondents from ``random.Random(seed)``: no panel, no person, no model.
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    #: A model answering *as* invented personas (the AI respondent engine on its
    #: fictional roster). Model-simulated answers of people who do not exist: never
    #: observed fieldwork, never a finding.
    SYNTHETIC_AI_FICTIONAL = "SYNTHETIC_AI_FICTIONAL"


#: Origins from which no client-facing claim may be made. Today: all of them.
NON_EVIDENCE_ORIGINS: Final[frozenset[DataOrigin]] = frozenset(
    {DataOrigin.SYNTHETIC_FIXTURE, DataOrigin.SYNTHETIC_AI_FICTIONAL}
)


#: One answer: a category (``vyber``), categories (``multi``), a scale point or
#: ``None`` for "don't know" (``skala`` and battery ratings), or text (``otevrena``).
Answer = str | list[str] | int | None


class FieldworkRespondent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    respondent_id: str
    donor_id: str
    weight: float = Field(gt=0)
    answers: dict[str, Answer]


class FieldworkDataset(BaseModel):
    """Every respondent's answers to one specification, with weights and donors.

    ``donor_id`` is the unit's ``core_donor_id``: the real panel person a
    respondent was built from, which is what uncertainty is clustered on
    (``uncertainty.py`` ``donor_support``). A fictional dataset has fictional donors.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str
    source: FieldworkSource
    origin: DataOrigin | None
    spec_fingerprint: str
    seed: int | None
    generator: str
    respondents: tuple[FieldworkRespondent, ...]

    @field_validator("respondents")
    @classmethod
    def _unique_ids(cls, v: tuple[FieldworkRespondent, ...]) -> tuple[FieldworkRespondent, ...]:
        if len({r.respondent_id for r in v}) != len(v):
            raise ValueError("respondent ids must be unique")
        return v

    @property
    def is_synthetic(self) -> bool:
        return self.origin in NON_EVIDENCE_ORIGINS


class InvalidDataset(ValueError):
    """The dataset does not answer the specification it names."""


def validate_dataset(spec: ResearchSpecification, dataset: FieldworkDataset) -> None:
    """Refuse a dataset that answers a different questionnaire, or answers off it.

    Checked, not trusted: a later step computes from these answers, and a value
    outside a question's options would become a number nobody asked for.
    """
    if dataset.spec_fingerprint != spec.fingerprint():
        raise InvalidDataset("the dataset answers a different specification")
    questions = {q.id: q for q in spec.questions}
    ratings = {b.question_id(o): b.scale for b in spec.batteries for o in b.objects}
    for r in dataset.respondents:
        unknown = set(r.answers) - set(questions) - set(ratings)
        if unknown:
            raise InvalidDataset(f"{r.respondent_id} answers unknown items {sorted(unknown)}")
        for qid, value in r.answers.items():
            if value is None:
                continue
            if qid in ratings:
                low, high = ratings[qid]
                if not (
                    isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
                ):
                    raise InvalidDataset(
                        f"{r.respondent_id}.{qid}: {value!r} is off the {low}-{high} scale"
                    )
                continue
            q = questions[qid]
            if q.typ == "vyber" and value not in q.options:
                raise InvalidDataset(f"{r.respondent_id}.{qid}: {value!r} is not an option")
            if q.typ == "multi" and not (isinstance(value, list) and set(value) <= set(q.options)):
                raise InvalidDataset(f"{r.respondent_id}.{qid}: {value!r} are not options")
            if q.typ == "skala" and q.scale is not None:
                low, high = q.scale
                if not (
                    isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
                ):
                    raise InvalidDataset(f"{r.respondent_id}.{qid}: {value!r} is off the scale")
            if q.typ == "otevrena" and not isinstance(value, str):
                raise InvalidDataset(f"{r.respondent_id}.{qid}: an open answer is text")
