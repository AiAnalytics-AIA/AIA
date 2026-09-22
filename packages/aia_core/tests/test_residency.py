"""EU residency and the egress boundary: every refusal path.

The property under test is that the boundary **fails closed**. Most of these
assert a denial, which is the point: the dangerous defect in a residency control
is not a wrong allow, it is an allow for a case nobody configured.

No vendor, region string or hosting product appears here. Which provider satisfies
the constraints is an implementation choice under its own ADR; the constraints are
what is frozen.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.residency import (
    DataClass,
    EgressDenied,
    EgressPolicy,
    ProviderRoute,
    ResidencyZone,
    evaluate_egress,
)

EU_CLIENT_ROUTE = ProviderRoute(
    route_id="eu-managed-inference",
    provider="approved_eu_managed",
    zone=ResidencyZone.EU,
    eu_processing_approved=True,
    excluded_from_training=True,
    retention_days=0,
    approved_for=frozenset(
        {
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            DataClass.CLASS_B_DERIVED_CLIENT,
            DataClass.CLASS_C_INTERNAL,
        }
    ),
)

DERIVED_ONLY_ROUTE = ProviderRoute(
    route_id="eu-aggregates-only",
    provider="approved_eu_managed",
    zone=ResidencyZone.EU,
    eu_processing_approved=True,
    excluded_from_training=True,
    retention_days=30,
    approved_for=frozenset({DataClass.CLASS_B_DERIVED_CLIENT}),
)

INTERNAL_ROUTE = ProviderRoute(
    route_id="direct-provider-api",
    provider="direct_api",
    zone=ResidencyZone.NON_EU,
    approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
)


@pytest.fixture
def scope(session: Session, scoped: Any) -> Any:
    """An authorised study scope, issued by the authorization layer."""
    return scoped.scope(user="lead", study="primary")


# --------------------------------------------------------------------------- #
# Fail-closed: the cases nobody configured
# --------------------------------------------------------------------------- #


def test_unclassified_material_may_not_leave(scope: Any) -> None:
    """**Unclassified client data must not leave AIA.**

    Absence of a classification is refused rather than treated as internal. The
    call site that forgot to classify is exactly the one holding something it did
    not think about.
    """
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(scope=scope, data_class=None, route=EU_CLIENT_ROUTE)
    assert exc.value.reason == "unclassified_material"


def test_no_configured_route_means_no_egress(scope: Any) -> None:
    """An empty policy permits nothing. It does not fall back to a default."""
    empty = EgressPolicy()
    with pytest.raises(EgressDenied) as exc:
        empty.authorise(
            scope=scope,
            data_class=DataClass.CLASS_C_INTERNAL,
            route_id="anything",
        )
    assert exc.value.reason == "no_approved_route"


def test_an_unknown_route_id_is_refused_rather_than_substituted(scope: Any) -> None:
    """No silent substitution: a missing route is a refusal, not a fallback.

    This is the residency face of the product's no-silent-fallback rule. Quietly
    using a configured route because the requested one is absent would move client
    material somewhere nobody authorised.
    """
    policy = EgressPolicy(routes=(EU_CLIENT_ROUTE, INTERNAL_ROUTE))
    with pytest.raises(EgressDenied) as exc:
        policy.authorise(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route_id="route-that-does-not-exist",
        )
    assert exc.value.reason == "no_approved_route"


def test_egress_requires_an_authorised_scope() -> None:
    """A dictionary is not a StudyContext, and cannot be made into one here.

    An outbound call needs trusted information about whose data it carries. A
    model-supplied payload can assert anything, so it is refused by type.
    """
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope={"study_id": "STU-forged"},  # type: ignore[arg-type]
            data_class=DataClass.CLASS_C_INTERNAL,
            route=INTERNAL_ROUTE,
        )
    assert exc.value.reason == "unauthorised_scope"


# --------------------------------------------------------------------------- #
# Class A -- client confidential
# --------------------------------------------------------------------------- #


def test_class_a_may_not_use_an_arbitrary_direct_provider_api(scope: Any) -> None:
    """**Raw client material does not go to a direct provider API.**"""
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=INTERNAL_ROUTE,
        )
    assert exc.value.reason == "route_not_approved_for_class"


def test_class_a_requires_confirmed_eu_processing(scope: Any) -> None:
    """A route in the EU that nobody has confirmed is not a confirmed route."""
    unconfirmed = ProviderRoute(
        route_id="eu-unconfirmed",
        provider="somewhere",
        zone=ResidencyZone.EU,
        eu_processing_approved=False,
        excluded_from_training=True,
        retention_days=0,
        approved_for=frozenset({DataClass.CLASS_A_CLIENT_CONFIDENTIAL}),
    )
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=unconfirmed,
        )
    assert exc.value.reason == "residency_violation"


def test_an_unknown_zone_is_refused_for_client_material(scope: Any) -> None:
    """``UNKNOWN`` exists so that an under-specified route can be refused."""
    vague = ProviderRoute(
        route_id="vague",
        provider="somewhere",
        eu_processing_approved=True,
        excluded_from_training=True,
        retention_days=0,
        approved_for=frozenset({DataClass.CLASS_B_DERIVED_CLIENT}),
    )
    assert vague.zone is ResidencyZone.UNKNOWN
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(scope=scope, data_class=DataClass.CLASS_B_DERIVED_CLIENT, route=vague)
    assert exc.value.reason == "residency_violation"


def test_client_material_requires_exclusion_from_training(scope: Any) -> None:
    """Residency is not only geography.

    Material processed in the EU but fed to a provider's training has left the
    client's control just as surely as material processed elsewhere.
    """
    trains = ProviderRoute(
        route_id="eu-but-trains",
        provider="approved_eu_managed",
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=False,
        retention_days=0,
        approved_for=frozenset({DataClass.CLASS_A_CLIENT_CONFIDENTIAL}),
    )
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=trains,
        )
    assert exc.value.reason == "training_exclusion_missing"


def test_client_material_requires_a_specified_retention_period(scope: Any) -> None:
    """Unspecified retention is not zero retention."""
    unspecified = ProviderRoute(
        route_id="eu-unspecified-retention",
        provider="approved_eu_managed",
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        retention_days=None,
        approved_for=frozenset({DataClass.CLASS_A_CLIENT_CONFIDENTIAL}),
    )
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=unspecified,
        )
    assert exc.value.reason == "retention_unspecified"


def test_class_a_is_allowed_over_a_fully_qualified_eu_route(scope: Any) -> None:
    """The permitted path, and the record it produces."""
    decision = evaluate_egress(
        scope=scope,
        data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        route=EU_CLIENT_ROUTE,
    )
    assert decision.zone is ResidencyZone.EU
    assert decision.study_id == scope.study_id
    assert decision.client_id == scope.client_id
    assert decision.audit_fields()["data_class"] == "CLASS_A_CLIENT_CONFIDENTIAL"
    assert decision.audit_fields()["route_id"] == "eu-managed-inference"


# --------------------------------------------------------------------------- #
# Class B and Class C
# --------------------------------------------------------------------------- #


def test_approval_is_per_class_not_per_provider(scope: Any) -> None:
    """A route cleared for aggregates is not thereby cleared for raw data.

    Same provider, same zone, same terms -- and still refused, because what the
    operator approved was the narrower thing.
    """
    assert (
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_B_DERIVED_CLIENT,
            route=DERIVED_ONLY_ROUTE,
        ).route_id
        == "eu-aggregates-only"
    )
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=DERIVED_ONLY_ROUTE,
        )
    assert exc.value.reason == "route_not_approved_for_class"


def test_class_c_may_use_a_broader_approved_route(scope: Any) -> None:
    """Internal material has more options -- but still needs an approved route."""
    decision = evaluate_egress(
        scope=scope, data_class=DataClass.CLASS_C_INTERNAL, route=INTERNAL_ROUTE
    )
    assert decision.zone is ResidencyZone.NON_EU
    assert decision.provider == "direct_api"
    # Provenance and cost attribution are owed regardless of what was carried.
    assert decision.audit_fields()["study_id"] == scope.study_id


def test_class_c_still_cannot_use_an_unapproved_route(scope: Any) -> None:
    unapproved = ProviderRoute(route_id="ad-hoc", provider="whatever")
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(scope=scope, data_class=DataClass.CLASS_C_INTERNAL, route=unapproved)
    assert exc.value.reason == "route_not_approved_for_class"


def test_a_route_that_declares_nothing_carries_nothing() -> None:
    """The defaults are the restrictive ones."""
    bare = ProviderRoute(route_id="bare", provider="p")
    assert bare.zone is ResidencyZone.UNKNOWN
    assert bare.eu_processing_approved is False
    assert bare.excluded_from_training is False
    assert bare.has_bounded_retention is False
    assert bare.approved_for == frozenset()
    assert bare.is_eu_processing is False


def test_a_policy_can_be_asked_what_may_carry_a_class() -> None:
    """Answerable before work starts, not discovered mid-pipeline."""
    policy = EgressPolicy(routes=(EU_CLIENT_ROUTE, DERIVED_ONLY_ROUTE, INTERNAL_ROUTE))
    assert [r.route_id for r in policy.routes_for(DataClass.CLASS_A_CLIENT_CONFIDENTIAL)] == [
        "eu-managed-inference"
    ]
    assert len(policy.routes_for(DataClass.CLASS_B_DERIVED_CLIENT)) == 2
    assert EgressPolicy().routes_for(DataClass.CLASS_C_INTERNAL) == ()


def test_there_is_no_downgrade_affordance_on_a_denial(scope: Any) -> None:
    """A denial is a hard stop.

    `EgressDenied` deliberately carries no suggested or fallback route: "refused,
    try the other one" is how a residency control becomes a formality. This mirrors
    `BudgetDecision`, which has no `suggested_provider` for the same reason.
    """
    with pytest.raises(EgressDenied) as exc:
        evaluate_egress(
            scope=scope,
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            route=INTERNAL_ROUTE,
        )
    for attribute in ("suggested_route", "fallback_route", "alternative"):
        assert not hasattr(exc.value, attribute)
