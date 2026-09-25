"""The recorded licence determinations: policy data, not code (ADR 0016 decision 5).

Each entry is what legal and the data owner have decided about sending material
derived from one dataset to a model provider. **This file changes when a
determination changes, and only then** -- never to unblock a feature. A change
that approves a dataset names who approved it, when, on what basis, and exactly
which routes; the reviewer checks it against the decision record (OI-61).

Today no panel-derived source is approved for any route. The panel is built from
PIAAC and ISSP microdata (AIA-reference ``population-subsystem.md``); whether
their licences allow transmission to a provider -- Bedrock included -- is
unresolved (AIA-reference ``open-decisions.md`` D3). Anything computed from the
panel's rows, such as a synthetic respondent's grounded profile, derives from
those datasets and carries their lineage.
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

__all__ = ["PANEL_DERIVED_DATASETS", "RECORDED", "SYNTHETIC_FIXTURE_DATASET", "recorded_policy"]

_UNRESOLVED: Final = "Unresolved: OI-61 (AIA-reference open-decisions.md D3). No transmission."

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
        status=LicenceStatus.UNDETERMINED,
        basis=_UNRESOLVED,
        decided_by="",
        decided_on=None,
    ),
    LicenceDetermination(
        dataset="issp",
        description="ISSP microdata, a source of the population panel",
        status=LicenceStatus.UNDETERMINED,
        basis=_UNRESOLVED,
        decided_by="",
        decided_on=None,
    ),
    LicenceDetermination(
        dataset="czech_population_panel",
        description="The Czech population panel and anything computed from its rows",
        status=LicenceStatus.UNDETERMINED,
        basis=_UNRESOLVED,
        decided_by="",
        decided_on=None,
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
