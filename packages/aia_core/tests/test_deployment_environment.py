"""The deployment environment and the one fictional-material rule.

The API and the worker both ask ``fictional_material_problem``; these tests are the
rule's single statement. The refusals matter most: an environment nobody named, or a
production-like one, must never accept fictional clients.
"""

from __future__ import annotations

import pytest

from aia_core.domain.deployment import (
    DeploymentEnvironment,
    fictional_material_problem,
    parse_environment,
)

E = DeploymentEnvironment


def test_develop_staging_and_production_are_deployed() -> None:
    assert {e for e in E if e.is_deployed} == {E.DEVELOP, E.STAGING, E.PRODUCTION}


def test_fictional_material_is_allowed_only_in_local_test_and_develop() -> None:
    assert {e for e in E if e.allows_fictional_material} == {E.LOCAL, E.TEST, E.DEVELOP}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("develop", E.DEVELOP),
        (" Production ", E.PRODUCTION),
        ("staging", E.STAGING),
        ("", None),
        (None, None),
        ("prod", None),
        ("dev", None),
    ],
)
def test_parse_environment_names_only_the_five_values(
    raw: str | None, expected: DeploymentEnvironment | None
) -> None:
    assert parse_environment(raw) is expected


@pytest.mark.parametrize("environment", [E.LOCAL, E.TEST, E.DEVELOP])
def test_fictional_clients_are_accepted_where_fictional_material_belongs(
    environment: DeploymentEnvironment,
) -> None:
    assert fictional_material_problem(environment, ["C1", "C2"]) is None


@pytest.mark.parametrize("environment", [E.STAGING, E.PRODUCTION])
def test_fictional_clients_are_refused_in_staging_and_production(
    environment: DeploymentEnvironment,
) -> None:
    problem = fictional_material_problem(environment, ["C1"])
    assert problem is not None
    assert f"refused in {environment.value}" in problem


def test_an_unknown_environment_refuses_fictional_clients() -> None:
    problem = fictional_material_problem(None, ["C1"])
    assert problem is not None
    assert "unknown environment" in problem


@pytest.mark.parametrize("environment", [*E, None])
def test_no_fictional_clients_is_never_a_problem(
    environment: DeploymentEnvironment | None,
) -> None:
    assert fictional_material_problem(environment, []) is None
    assert fictional_material_problem(environment, ["", "  "]) is None
