"""Licence eligibility fails closed (ADR 0016 decision 5, D3): a gate beside residency.

The rule is code; the determinations are data. These tests pin both halves: the
rule refuses everything it cannot positively justify, and the recorded data
approves no panel-derived source for any route -- Bedrock included.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import ModelRequest
from aia_core.domain.licence import (
    ANY_APPROVED_ROUTE,
    DataLineage,
    LicenceDenied,
    LicenceDetermination,
    LicencePolicy,
    LicenceStatus,
)
from aia_core.domain.licence_determinations import (
    PANEL_APPROVED_ROUTE,
    PANEL_DERIVED_DATASETS,
    RECORDED,
    SYNTHETIC_FIXTURE_DATASET,
    recorded_policy,
)
from aia_core.domain.residency import DataClass, EgressDenied, ProviderRoute, ResidencyZone

BEDROCK_EU = ProviderRoute(
    route_id=PANEL_APPROVED_ROUTE,
    provider="bedrock",
    zone=ResidencyZone.EU,
    eu_processing_approved=True,
    excluded_from_training=True,
    retention_days=0,
    approved_for=frozenset(DataClass),
)
OTHER = ProviderRoute(route_id="other-route", provider="anthropic")


def _approved(dataset: str, *routes: str) -> LicenceDetermination:
    return LicenceDetermination(
        dataset=dataset,
        description="cleared in a test",
        status=LicenceStatus.APPROVED,
        basis="test",
        decided_by="legal",
        decided_on=date(2026, 9, 25),
        approved_routes=frozenset(routes),
    )


def _denied(policy: LicencePolicy, lineage: DataLineage | None, route: ProviderRoute) -> str:
    with pytest.raises(LicenceDenied) as refused:
        policy.authorise(lineage=lineage, route=route)
    # Its own refusal: a residency handler must not mistake it for one of its own.
    assert not isinstance(refused.value, EgressDenied)
    return refused.value.reason


# --------------------------------------------------------------------------- #
# The recorded determinations
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("dataset", sorted(PANEL_DERIVED_DATASETS))
def test_each_panel_derived_dataset_reaches_the_eu_bedrock_route_and_no_other(
    dataset: str,
) -> None:
    """OI-61, determined 2026-10-12: approved for the one route named, and only that."""
    policy = recorded_policy()
    policy.authorise(lineage=DataLineage.of(dataset), route=BEDROCK_EU)
    assert _denied(policy, DataLineage.of(dataset), OTHER) == "not_approved_for_route"
    found = policy.determination(dataset)
    assert found is not None and found.status is LicenceStatus.APPROVED
    assert found.approved_routes == frozenset({PANEL_APPROVED_ROUTE})
    assert "OI-61" in found.basis and found.decided_by and found.decided_on


def test_a_lineage_mixing_the_panel_and_the_fixture_follows_its_narrowest_dataset() -> None:
    lineage = DataLineage.of(SYNTHETIC_FIXTURE_DATASET, "issp")
    recorded_policy().authorise(lineage=lineage, route=BEDROCK_EU)
    assert _denied(recorded_policy(), lineage, OTHER) == "not_approved_for_route"


def test_the_fictional_fixture_and_no_data_at_all_may_be_sent() -> None:
    policy = recorded_policy()
    policy.authorise(lineage=DataLineage.of(SYNTHETIC_FIXTURE_DATASET), route=BEDROCK_EU)
    policy.authorise(lineage=DataLineage.of(SYNTHETIC_FIXTURE_DATASET), route=OTHER)
    policy.authorise(lineage=DataLineage.none(), route=OTHER)


def test_only_the_fixture_is_approved_for_every_route() -> None:
    every_route = {d.dataset for d in RECORDED if ANY_APPROVED_ROUTE in d.approved_routes}
    assert every_route == {SYNTHETIC_FIXTURE_DATASET}
    assert {d.dataset for d in RECORDED} >= PANEL_DERIVED_DATASETS


# --------------------------------------------------------------------------- #
# The rule
# --------------------------------------------------------------------------- #


def test_an_undeclared_lineage_is_refused_not_read_as_clean() -> None:
    assert _denied(recorded_policy(), None, BEDROCK_EU) == "lineage_undeclared"


def test_a_dataset_nobody_has_decided_about_is_refused() -> None:
    assert _denied(recorded_policy(), DataLineage.of("new_survey"), OTHER) == "dataset_unknown"


def test_approval_is_per_route_and_a_refusal_is_final() -> None:
    policy = LicencePolicy(
        (
            _approved("cleared", BEDROCK_EU.route_id),
            LicenceDetermination(
                dataset="refused",
                description="",
                status=LicenceStatus.REFUSED,
                basis="the licence forbids it",
                decided_by="legal",
                decided_on=date(2026, 9, 25),
            ),
        )
    )
    policy.authorise(lineage=DataLineage.of("cleared"), route=BEDROCK_EU)
    assert _denied(policy, DataLineage.of("cleared"), OTHER) == "not_approved_for_route"
    assert _denied(policy, DataLineage.of("refused"), BEDROCK_EU) == "refused"


def test_approving_a_dataset_changes_data_and_not_the_rule() -> None:
    """An approval is one determination replaced; the rule reading it is untouched."""
    cleared = tuple(
        _approved("issp", OTHER.route_id) if d.dataset == "issp" else d for d in RECORDED
    )
    LicencePolicy(cleared).authorise(lineage=DataLineage.of("issp"), route=OTHER)
    assert _denied(LicencePolicy(cleared), DataLineage.of("piaac"), OTHER) == (
        "not_approved_for_route"
    )


def test_a_determination_says_who_approved_what() -> None:
    with pytest.raises(ValueError, match="only an approved determination names routes"):
        LicenceDetermination(
            dataset="x",
            description="",
            status=LicenceStatus.UNDETERMINED,
            basis="",
            decided_by="",
            decided_on=None,
            approved_routes=frozenset({ANY_APPROVED_ROUTE}),
        )
    with pytest.raises(ValueError, match="who approved it"):
        LicenceDetermination(
            dataset="x",
            description="",
            status=LicenceStatus.APPROVED,
            basis="",
            decided_by="",
            decided_on=None,
        )
    with pytest.raises(ValueError, match="one determination per dataset"):
        LicencePolicy((_approved("x", "r"), _approved("x", "r")))


def test_a_lineage_names_its_datasets_or_says_none() -> None:
    with pytest.raises(ValueError):
        DataLineage.of()
    with pytest.raises(ValueError):
        DataLineage.of(" ")
    assert DataLineage.none().datasets == frozenset()


def test_neither_a_request_nor_a_gateway_can_leave_the_licence_out() -> None:
    """No default anywhere: forgetting the gate is a TypeError, not a pass."""
    lineage = inspect.signature(ModelRequest).parameters["data_lineage"]
    assert lineage.default is inspect.Parameter.empty
    licence = inspect.signature(GovernedModelGateway.__init__).parameters["licence"]
    assert licence.default is inspect.Parameter.empty
