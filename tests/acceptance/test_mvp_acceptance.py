"""``MVP-ACCEPT-2``, tier A: the criteria of ``docs/migration/mvp-acceptance.md``, over HTTP.

Each test is named for the criterion it proves (``test_ac01_…``) and is listed under that
criterion's ``tests`` in ``docs/migration/parity-matrix.json`` (``mvp_acceptance``);
``tools/parity_status.py`` reads this module's JUnit and gives each criterion its verdict: PASS
only when every test it lists passed, FAIL when one failed, NOT_EXECUTED when one did not run,
NOT_RUNNABLE while it lists none. A criterion lands here when the work that makes it runnable
lands (plan ``mvp-acceptance-harness`` chunk 5), never as a placeholder.

Wired so far: AC-01, its tier-A projection (the identity seam is the ``development`` provider;
Cognito in the deployed stack is tier B's).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.acceptance

#: The prefix of every path in the API's own document; ``http`` already carries it.
PREFIX = "/api/v1"
#: A study id of the right shape that no study has.
ABSENT_STUDY = "STU-0000000000000000000000000000dead"
#: Any other path parameter: its shape does not matter, scope is decided first.
_PARAM = re.compile(r"\{[^}]+\}")


def _provision(http: Any, people: Any, unique: Callable[[str], str]) -> tuple[str, str]:
    """Organization -> Client -> Study, as the web client does it: the client, then its study."""
    client = http.post(
        "/clients",
        {"slug": unique("acceptance-client"), "name": "Acceptance client (fiktivní)"},
        as_user=people.researcher,
    )
    assert client.status == 201, client.text
    study = http.post(
        "/studies",
        {
            "client_id": client.json()["client_id"],
            "slug": unique("mvp-acceptance"),
            "name": "MVP acceptance (fiktivní)",
            "budget_usd": 25,
        },
        as_user=people.researcher,
    )
    assert study.status == 201, study.text
    return str(client.json()["client_id"]), str(study.json()["study_id"])


def _error(reply: Any) -> dict[str, Any]:
    """An error body without its request id: the part that could tell two answers apart."""
    body = dict(reply.json())
    body.pop("request_id", None)
    return body


def _document_paths(http: Any, people: Any) -> dict[str, dict[str, Any]]:
    spec = http.get("/openapi.json", as_user=people.researcher)
    assert spec.status == 200, spec.text
    paths: dict[str, dict[str, Any]] = spec.json()["paths"]
    assert all(p.startswith(PREFIX + "/") for p in paths), "every route is under the API prefix"
    return paths


def _study_routes(http: Any, people: Any) -> list[tuple[str, str]]:
    """Every (method, path) of the API that names a study, from the API's own document."""
    return sorted(
        (method.upper(), path.removeprefix(PREFIX))
        for path, operations in _document_paths(http, people).items()
        if "{study_id}" in path
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )


def test_ac01_people_authenticate_through_the_identity_seam_and_provision_the_study(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """The researcher and a reviewer authenticate through the IdentityProvider seam; the study
    is provisioned Organization -> Client -> Study over HTTP; membership is the access."""
    assert http.get("/clients", as_user=None).status == 401
    signed_in(people.researcher)
    client_id, study_id = _provision(http, people, unique)

    study = http.get(f"/studies/{study_id}", as_user=people.researcher)
    assert study.status == 200, study.text
    assert study.json()["client_id"] == client_id
    assert float(study.json()["budget_usd"]) == 25.0

    reviewer = f"{unique('reviewer')}@acceptance.invalid"
    added = http.post(
        "/members",
        {"email": reviewer, "role": "MEMBER", "display_name": "Reviewer (fiktivní)"},
        as_user=people.researcher,
    )
    assert added.status == 201, added.text
    signed_in(reviewer)
    # ADR 0019: membership of the organization is the access; no grant is read.
    seen = http.get(f"/studies/{study_id}", as_user=reviewer)
    assert seen.status == 200, seen.text


def test_ac01_every_project_route_is_study_scoped(http: Any, people: Any) -> None:
    """Scope is carried in the path: a project route outside a study prefix is a defect."""
    project_routes = [p for p in _document_paths(http, people) if "{project_id}" in p]
    assert project_routes, "the API serves project routes; none were found"
    unscoped = [p for p in project_routes if not p.startswith(f"{PREFIX}/studies/{{study_id}}/")]
    assert not unscoped, unscoped


def test_ac01_a_user_of_another_organization_gets_404_on_every_study_route(
    stack: Any,
    http: Any,
    people: Any,
    signed_in: Callable[[str], None],
    unique: Callable[[str], str],
) -> None:
    """404, never 403, and the same 404 a study that does not exist gets (ADR 0019): another
    organization learns nothing, not even that the study exists."""
    signed_in(people.researcher)
    signed_in(people.other_organization)
    _, study_id = _provision(http, people, unique)
    assert http.get(f"/studies/{study_id}", as_user=people.researcher).status == 200

    routes = _study_routes(http, people)
    assert len(routes) >= 50, f"only {len(routes)} study routes: the document is not the API's"
    leaks: list[tuple[str, str, int, str]] = []
    for method, template in routes:
        body = {} if method in {"POST", "PUT", "PATCH"} else None
        real = _PARAM.sub("X-0", template.replace("{study_id}", study_id))
        absent = _PARAM.sub("X-0", template.replace("{study_id}", ABSENT_STUDY))
        got = http.call(method, real, as_user=people.other_organization, body=body)
        none = http.call(method, absent, as_user=people.other_organization, body=body)
        if got.status != 404 or _error(got) != _error(none):
            leaks.append((method, template, got.status, got.text[:120]))
    assert not leaks, (
        f"{len(leaks)} of {len(routes)} study routes answer another organization:\n"
        + "\n".join(map(str, leaks))
    )

    # And the other way: the other organization's seeded study is not the researcher's.
    theirs = str(stack.seeded["study_id"])
    assert http.get(f"/studies/{theirs}", as_user=people.researcher).status == 404
    assert http.get(f"/studies/{theirs}", as_user=people.other_organization).status == 200
