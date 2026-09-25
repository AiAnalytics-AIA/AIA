"""The fieldwork boundary (ADR 0016 decision 4): where respondent data comes from.

The research workflow's fieldwork step (node ``run``) has one job: produce a
fieldwork dataset from a declared source. Every later step reads only that
dataset, so a new source -- the AI respondent engine, a client's own data -- is a
new producer of the same thing, not a change to aggregation or Sociomapping.

A run records its source when it is created; the worker executes only a source
its composition provides. Pure: no I/O.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["DataOrigin", "FieldworkSource"]


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
    """Where the respondent data behind an artifact came from, stamped on it."""

    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
