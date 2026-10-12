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
    "CLIENT_ADMISSIBLE_ORIGINS",
    "DATASET_VERSION",
    "MODELLED_DISCLOSURE",
    "NON_EVIDENCE_ORIGINS",
    "RESPONDENT_SYSTEM_METADATA",
    "Answer",
    "DataOrigin",
    "FieldworkDataset",
    "FieldworkRespondent",
    "FieldworkSource",
    "InvalidDataset",
    "OriginKind",
    "origin_kind",
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

    Two members are synthetic and never evidence (:data:`NON_EVIDENCE_ORIGINS`); one is
    modelled evidence (ADR 0024). A client-facing claim is admitted only from an origin in
    :data:`CLIENT_ADMISSIBLE_ORIGINS`, an allowlist, so a member added later is refused until
    it is decided. Every member is in exactly one of the two sets
    (``test_every_origin_is_decided_once``).
    """

    #: Invented respondents from ``random.Random(seed)``: no panel, no person, no model.
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    #: A model answering *as* invented personas (the AI respondent engine on its
    #: fictional roster). Model-simulated answers of people who do not exist: never
    #: observed fieldwork, never a finding.
    SYNTHETIC_AI_FICTIONAL = "SYNTHETIC_AI_FICTIONAL"
    #: A model answering as respondents built from rows sampled from the run's own recorded
    #: population (ADR 0024): modelled evidence, never measured and never fictional. Every
    #: respondent's donor is its row's ``core_donor_id``.
    MODELLED_AI_PANEL = "MODELLED_AI_PANEL"


#: Synthetic origins: never evidence, labelled "simulated respondents" everywhere.
NON_EVIDENCE_ORIGINS: Final[frozenset[DataOrigin]] = frozenset(
    {DataOrigin.SYNTHETIC_FIXTURE, DataOrigin.SYNTHETIC_AI_FICTIONAL}
)

#: The only origins a client-facing claim may come from (ADR 0024 §2). An allowlist: ``None``
#: and any origin not named here are refused client-facing.
CLIENT_ADMISSIBLE_ORIGINS: Final[frozenset[DataOrigin]] = frozenset({DataOrigin.MODELLED_AI_PANEL})

#: What every modelled number carries beside it (ADR 0024 §7). Never "respondents said",
#: "measured" or "the survey found".
MODELLED_DISCLOSURE: Final = "modelováno: AI respondenti z populace"


#: The fieldwork dataset artifact's metadata key holding the components of the respondent system
#: its answers came from (``evidence.validation.RESPONDENT_SYSTEM_COMPONENTS``), written by the
#: source that produced a modelled dataset. A modelled run's evidence is judged on it.
RESPONDENT_SYSTEM_METADATA: Final = "respondent_system"


class OriginKind(StrEnum):
    """How a label reads an origin: the one three-way reading every surface uses."""

    #: Fictional respondents (:data:`NON_EVIDENCE_ORIGINS`): never evidence.
    SIMULATED = "SIMULATED"
    #: AI respondents built from the run's population (ADR 0024): modelled, never measured.
    MODELLED = "MODELLED"
    #: No origin, or one this code does not know: labelled unknown, never read as real.
    UNKNOWN = "UNKNOWN"


_MODELLED_ORIGINS: Final[frozenset[DataOrigin]] = frozenset({DataOrigin.MODELLED_AI_PANEL})


def origin_kind(origin: DataOrigin | str | None) -> OriginKind:
    """The kind of ``origin``; ``None`` and an unrecognised value are :attr:`OriginKind.UNKNOWN`.

    No member reads as measured: AIA has no measured origin, so there is no fourth kind.
    """
    if origin is None:
        return OriginKind.UNKNOWN
    try:
        member = DataOrigin(origin)
    except ValueError:
        return OriginKind.UNKNOWN
    if member in NON_EVIDENCE_ORIGINS:
        return OriginKind.SIMULATED
    if member in _MODELLED_ORIGINS:
        return OriginKind.MODELLED
    return OriginKind.UNKNOWN


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
