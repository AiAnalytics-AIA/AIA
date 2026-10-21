"""The recorded licence determinations: policy data, not code (ADR 0016 decision 5).

Each entry is what legal and the data owner have decided about sending material
derived from one dataset to a model provider. **This file changes when a
determination changes, and only then** -- never to unblock a feature. A change
that approves a dataset names who approved it, when, on what basis, and exactly
which routes; the reviewer checks it against the decision record (OI-61).

The panel is built from PIAAC and ISSP microdata (AIA-reference
``population-subsystem.md``); anything computed from its rows, such as a synthetic
respondent's grounded profile, derives from those datasets and carries their lineage.
OI-61 asked whether that may reach a model provider. On 2026-10-12 the data owner
determined that it may, over AIA's EU Bedrock route alone (ADR 0010): each
panel-derived dataset names that one route, and another route needs a determination
of its own.

A client's approved DATASET, ARTIFACT or FINDING knowledge item records no datasets it
came from, so a model request carrying one declares the named placeholder lineage
``unclassified-client-knowledge`` (:data:`CLIENT_KNOWLEDGE_DATASET`). On 2026-10-21 the
data owner determined that such material may reach a model provider over the same EU
Bedrock route alone (/pmstatus Q60, answer (a)); another route still needs its own.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from .licence import (
    ANY_APPROVED_ROUTE,
    LicenceDetermination,
    LicencePolicy,
    LicenceStatus,
)

__all__ = [
    "CLIENT_KNOWLEDGE_DATASET",
    "PANEL_APPROVED_ROUTE",
    "PANEL_DERIVED_DATASETS",
    "RECORDED",
    "SYNTHETIC_FIXTURE_DATASET",
    "recorded_policy",
]

#: AIA's EU Bedrock route (ADR 0010; ``AIA_AI_ROUTE_ID``): the only route the
#: panel-derived determinations, and unrecorded client knowledge's, approve.
PANEL_APPROVED_ROUTE: Final = "bedrock-eu-primary"

_PANEL_BASIS: Final = (
    "OI-61, owner determination of 2026-10-12: the dataset's licence permits sending "
    "material derived from it to a model provider. Recorded for AIA's EU Bedrock route "
    "alone (ADR 0010); another route needs its own determination."
)
_PANEL_DECIDED_BY: Final = "Nigel Blount, data owner"

#: The lineage a client's DATASET, ARTIFACT or FINDING knowledge carries when nobody recorded
#: which datasets it came from: the Lead's turns, the design jobs and Deep Research's
#: knowledge (``knowledge_access.UNRESOLVED_LINEAGE``) all declare this one name.
CLIENT_KNOWLEDGE_DATASET: Final = "unclassified-client-knowledge"

_CLIENT_KNOWLEDGE_BASIS: Final = (
    "/pmstatus Q60, answer (a), data owner determination of 2026-10-21: approved for the EU "
    "Bedrock route only. A client's own knowledge, whose source datasets nobody recorded, may "
    "be sent to a model provider over AIA's EU Bedrock route alone (ADR 0010); another route "
    "needs its own determination."
)

#: The lineage of anything computed from AIA's fictional fixture dataset (ADR 0016 D1).
SYNTHETIC_FIXTURE_DATASET: Final = "aia_synthetic_fixture"

#: The datasets the population panel is built from, and the panel itself.
PANEL_DERIVED_DATASETS: Final[frozenset[str]] = frozenset(
    {"piaac", "issp", "czech_population_panel"}
)

RECORDED: Final[tuple[LicenceDetermination, ...]] = (
    LicenceDetermination(
        dataset="piaac",
        description="OECD PIAAC microdata, a source of the population panel",
        status=LicenceStatus.APPROVED,
        basis=_PANEL_BASIS,
        decided_by=_PANEL_DECIDED_BY,
        decided_on=date(2026, 10, 12),
        approved_routes=frozenset({PANEL_APPROVED_ROUTE}),
    ),
    LicenceDetermination(
        dataset="issp",
        description="ISSP microdata, a source of the population panel",
        status=LicenceStatus.APPROVED,
        basis=_PANEL_BASIS,
        decided_by=_PANEL_DECIDED_BY,
        decided_on=date(2026, 10, 12),
        approved_routes=frozenset({PANEL_APPROVED_ROUTE}),
    ),
    LicenceDetermination(
        dataset="czech_population_panel",
        description="The Czech population panel and anything computed from its rows",
        status=LicenceStatus.APPROVED,
        basis=_PANEL_BASIS,
        decided_by=_PANEL_DECIDED_BY,
        decided_on=date(2026, 10, 12),
        approved_routes=frozenset({PANEL_APPROVED_ROUTE}),
    ),
    LicenceDetermination(
        dataset=CLIENT_KNOWLEDGE_DATASET,
        description=(
            "A client's approved DATASET, ARTIFACT or FINDING knowledge, its source datasets "
            "unrecorded"
        ),
        status=LicenceStatus.APPROVED,
        basis=_CLIENT_KNOWLEDGE_BASIS,
        decided_by="Nigel Blount, product owner as data owner",
        decided_on=date(2026, 10, 21),
        approved_routes=frozenset({PANEL_APPROVED_ROUTE}),
    ),
    LicenceDetermination(
        dataset=SYNTHETIC_FIXTURE_DATASET,
        description="AIA's fictional fixture dataset: invented respondents, no source data",
        status=LicenceStatus.APPROVED,
        basis="Authored by AIA from no source dataset; there is no third-party licence.",
        decided_by="AIA engineering (ADR 0016)",
        decided_on=date(2026, 9, 25),
        approved_routes=frozenset({ANY_APPROVED_ROUTE}),
    ),
)


def recorded_policy() -> LicencePolicy:
    """The policy every composition root uses: the determinations above, nothing else."""
    return LicencePolicy(RECORDED)
