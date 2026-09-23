"""OI-8: only a configured population operator may establish or promote.

Every refusal is asserted by type and by reason: an unconfigured user, an
insufficient permission, a study or organization context, a principal passed where
a context belongs, a forged grant, and a model-shaped argument.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.application.population_authority import (
    PopulationAuthority,
    PopulationOperatorConfig,
)
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.population import (
    PopulationKind,
    PopulationOperatorContext,
    PopulationOperatorGrant,
    PopulationPermission,
    PopulationPermissionDenied,
)
from aia_core.infrastructure.population_repository import PopulationRegistryRepository

P = PopulationPermission
PRINCIPAL = AuthenticatedPrincipal(user_id="ops-1", organization_id="platform", request_id="r1")


def authority(**operators: tuple[str, ...]) -> PopulationAuthority:
    return PopulationAuthority(PopulationOperatorConfig.from_names(operators))


@pytest.fixture
def imported(session: Session, synthetic_population: Any) -> dict[str, Any]:
    pop = synthetic_population
    rt = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    versions = {
        label: rt.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="synthetic",
            imported_by="importer",
        )
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    return {"rt": rt, "versions": versions, "pop": pop}


def establish(rt: PopulationRuntime, operator: Any, version_id: str) -> Any:
    return rt.establish(
        operator=operator,
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=version_id,
        reason="establish",
    )


# --------------------------------------------------------------------------- #
# Issuance
# --------------------------------------------------------------------------- #


def test_a_configured_principal_gets_exactly_its_permissions() -> None:
    context = authority(**{"ops-1": ("POPULATION_PROMOTE",)}).operator_context(PRINCIPAL)
    assert context.actor_id == "ops-1"
    assert context.permissions == {P.POPULATION_PROMOTE}
    assert context.request_id == "r1"


def test_an_unconfigured_principal_is_refused() -> None:
    with pytest.raises(PopulationPermissionDenied) as caught:
        authority(**{"someone-else": ("POPULATION_PROMOTE",)}).operator_context(PRINCIPAL)
    assert caught.value.reason == "not_an_operator"


def test_the_default_configuration_names_nobody() -> None:
    with pytest.raises(PopulationPermissionDenied):
        PopulationAuthority(PopulationOperatorConfig()).operator_context(PRINCIPAL)


def test_a_configured_user_with_no_permissions_is_refused() -> None:
    with pytest.raises(PopulationPermissionDenied) as caught:
        authority(**{"ops-1": ()}).operator_context(PRINCIPAL)
    assert caught.value.reason == "not_an_operator"


def test_an_unknown_permission_name_is_a_configuration_error() -> None:
    with pytest.raises(ValueError):
        PopulationOperatorConfig.from_names({"ops-1": ["POPULATION_ADMIN"]})
    with pytest.raises(ValueError):
        PopulationOperatorConfig.from_names({"": ["POPULATION_PROMOTE"]})


def test_the_authority_refuses_anything_but_a_principal(scoped: Any) -> None:
    for impostor in (scoped.scope(user="lead"), scoped.admin_context, "ops-1"):
        with pytest.raises(PopulationPermissionDenied) as caught:
            authority(**{"ops-1": ("POPULATION_PROMOTE",)}).operator_context(impostor)
        assert caught.value.reason == "not_a_principal"


def test_an_organization_owner_is_not_a_population_operator(scoped: Any) -> None:
    # The owner administers one tenant; population operation is platform-wide.
    owner = scoped.admin_principal
    with pytest.raises(PopulationPermissionDenied) as caught:
        authority(**{"ops-1": ("POPULATION_ESTABLISH",)}).operator_context(owner)
    assert caught.value.reason == "not_an_operator"


def test_an_operator_context_cannot_be_forged() -> None:
    with pytest.raises(PopulationPermissionDenied) as caught:
        PopulationOperatorGrant(_issuer=object())
    assert caught.value.reason == "forged_operator_grant"
    with pytest.raises(PopulationPermissionDenied):
        PopulationOperatorContext(
            actor_id="ops-1",
            permissions=frozenset(P),
            grant=object(),  # type: ignore[arg-type]
        )


# --------------------------------------------------------------------------- #
# Enforcement inside the use case
# --------------------------------------------------------------------------- #


def test_establish_requires_the_establish_permission(imported: dict[str, Any]) -> None:
    rt, v = imported["rt"], imported["versions"]
    promoter = authority(**{"ops-1": ("POPULATION_PROMOTE",)}).operator_context(PRINCIPAL)
    with pytest.raises(PopulationPermissionDenied) as caught:
        establish(rt, promoter, v["v1_1"].version_id)
    assert caught.value.reason == "insufficient_population_permission"


def test_promote_requires_the_promote_permission(imported: dict[str, Any]) -> None:
    rt, v = imported["rt"], imported["versions"]
    establisher = authority(**{"ops-1": ("POPULATION_ESTABLISH",)}).operator_context(PRINCIPAL)
    establish(rt, establisher, v["v1_1"].version_id)
    rt.establish(
        operator=establisher,
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=v["v1_4"].version_id,
        reason="establish",
    )
    with pytest.raises(PopulationPermissionDenied) as caught:
        rt.promote_live(
            operator=establisher,
            population_id="SYN_LIVE",
            target_version_id=v["v1_1"].version_id,
            expected_current_version_id=v["v1_4"].version_id,
            reason="move",
        )
    assert caught.value.reason == "insufficient_population_permission"


@pytest.mark.parametrize("kind", ["study", "organization", "principal", "tool_payload", "none"])
def test_nothing_but_an_operator_context_is_accepted(
    imported: dict[str, Any], scoped: Any, kind: str
) -> None:
    impostor = {
        "study": scoped.scope(user="lead"),
        "organization": scoped.admin_context,
        "principal": PRINCIPAL,
        # What a model or tool call could produce: the right-looking fields.
        "tool_payload": {"actor_id": "ops-1", "permissions": ["POPULATION_ESTABLISH"]},
        "none": None,
    }[kind]
    with pytest.raises(PopulationPermissionDenied) as caught:
        establish(imported["rt"], impostor, imported["versions"]["v1_1"].version_id)
    assert caught.value.reason == "not_an_operator_context"


def test_a_refused_call_writes_nothing(session: Session, imported: dict[str, Any]) -> None:
    with pytest.raises(PopulationPermissionDenied):
        establish(imported["rt"], PRINCIPAL, imported["versions"]["v1_1"].version_id)
    assert (
        PopulationRegistryRepository(session).populations(imported["pop"].contract.dataset_id) == []
    )


def test_the_recorded_actor_is_the_operators_verified_id(
    session: Session, imported: dict[str, Any]
) -> None:
    operator = authority(**{"ops-1": ("POPULATION_ESTABLISH",)}).operator_context(PRINCIPAL)
    population = establish(imported["rt"], operator, imported["versions"]["v1_1"].version_id)
    assert population.established_by == "ops-1"
    history = PopulationRegistryRepository(session).promotions(imported["pop"].contract.dataset_id)
    assert [(r.actor_id, r.reason) for r in history] == [("ops-1", "establish")]
