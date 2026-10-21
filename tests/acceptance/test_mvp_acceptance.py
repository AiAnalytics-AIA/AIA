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
#: A study id and a client id of the right shape that nothing has.
ABSENT_STUDY = "STU-0000000000000000000000000000dead"
ABSENT_CLIENT = "CLI-0000000000000000000000000000dead"
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


def _answer(reply: Any) -> tuple[int, Any]:
    """A reply's status and its error body without the request id (None when not JSON)."""
    try:
        return reply.status, _error(reply)
    except (ValueError, TypeError, AttributeError):
        return reply.status, None


def _document_paths(http: Any, people: Any) -> dict[str, dict[str, Any]]:
    spec = http.get("/openapi.json", as_user=people.researcher)
    assert spec.status == 200, spec.text
    paths: dict[str, dict[str, Any]] = spec.json()["paths"]
    assert all(p.startswith(PREFIX + "/") for p in paths), "every route is under the API prefix"
    return paths


def _routes_naming(http: Any, people: Any, key: str, *, without: str = "") -> list[tuple[str, str]]:
    """Every (method, path) of the API whose path names ``key``, from the API's own document."""
    return sorted(
        (method.upper(), path.removeprefix(PREFIX))
        for path, operations in _document_paths(http, people).items()
        if key in path and not (without and without in path)
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )


def _probe_as_stranger(
    http: Any, people: Any, routes: list[tuple[str, str]], key: str, real_id: str, absent_id: str
) -> tuple[list[tuple[str, str, int, str]], list[tuple[str, str, int, str]]]:
    """Each route called by another organization's user on the real id and on an absent one,
    then by the owner on the real id. Returns the leaks (anything but the absent id's 404)
    and the unproven (the owner answered as the stranger was answered, so the 404 may be a
    missing child's, not scope's)."""
    leaks: list[tuple[str, str, int, str]] = []
    unproven: list[tuple[str, str, int, str]] = []
    for method, template in routes:
        body = {} if method in {"POST", "PUT", "PATCH"} else None
        real = _PARAM.sub("X-0", template.replace(key, real_id))
        absent = _PARAM.sub("X-0", template.replace(key, absent_id))
        got = http.call(method, real, as_user=people.other_organization, body=body)
        none = http.call(method, absent, as_user=people.other_organization, body=body)
        if got.status != 404 or _error(got) != _error(none):
            leaks.append((method, template, got.status, got.text[:120]))
            continue
        # After the foreign calls, so nothing the owner's call changes can mask them.
        own = http.call(method, real, as_user=people.researcher, body=body)
        if _answer(own) == _answer(got):
            unproven.append((method, template, own.status, own.text[:120]))
    return leaks, unproven


def _assert_scoped(
    routes: list[tuple[str, str]],
    leaks: list[tuple[str, str, int, str]],
    unproven: list[tuple[str, str, int, str]],
) -> None:
    assert not leaks, (
        f"{len(leaks)} of {len(routes)} routes answer another organization:\n"
        + "\n".join(map(str, leaks))
    )
    assert not unproven, (
        f"{len(unproven)} routes answer the owner as they answer a stranger, so their 404 "
        "may be a missing child, not scope:\n" + "\n".join(map(str, unproven))
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
    organization learns nothing, not even that the study exists.

    The path's other ids are placeholders, so a route could answer 404 for a missing child
    before it ever looked at scope. The study's own researcher calls each route too, the same
    way: their answer must differ from the foreign one (a 2xx, a 422, or the child's own
    "no such run"), which shows the foreign 404 is scope's, decided first."""
    signed_in(people.researcher)
    signed_in(people.other_organization)
    _, study_id = _provision(http, people, unique)
    assert http.get(f"/studies/{study_id}", as_user=people.researcher).status == 200

    routes = _routes_naming(http, people, "{study_id}")
    assert len(routes) >= 50, f"only {len(routes)} study routes: the document is not the API's"
    _assert_scoped(
        routes, *_probe_as_stranger(http, people, routes, "{study_id}", study_id, ABSENT_STUDY)
    )

    # And the other way: the other organization's seeded study is not the researcher's.
    theirs = str(stack.seeded["study_id"])
    assert http.get(f"/studies/{theirs}", as_user=people.researcher).status == 404
    assert http.get(f"/studies/{theirs}", as_user=people.other_organization).status == 200


def test_ac01_a_user_of_another_organization_cannot_tell_a_client_from_an_absent_one(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """The client half of the same boundary, beyond AC-01's study routes. Every route that
    names a client, and no study, answers another organization's user exactly as it answers
    an absent client, never 403, and where that answer is a 404 the owner is answered
    otherwise. Not every such answer is a 404: most client routes validate the body and
    path before they resolve scope, so a stranger sends ``{}`` and gets the same 422 an
    absent client gets (finding F-6 in the harness plan). That discloses nothing; it is not
    the 404 AC-01 asks of study routes."""
    signed_in(people.researcher)
    signed_in(people.other_organization)
    client_id, _ = _provision(http, people, unique)
    routes = _routes_naming(http, people, "{client_id}", without="{study_id}")
    assert len(routes) >= 10, f"only {len(routes)} client routes: the document is not the API's"
    told: list[tuple[str, str, int, str]] = []
    unproven: list[tuple[str, str, int, str]] = []
    for method, template in routes:
        body = {} if method in {"POST", "PUT", "PATCH"} else None
        real = _PARAM.sub("X-0", template.replace("{client_id}", client_id))
        absent = _PARAM.sub("X-0", template.replace("{client_id}", ABSENT_CLIENT))
        got = http.call(method, real, as_user=people.other_organization, body=body)
        none = http.call(method, absent, as_user=people.other_organization, body=body)
        if got.status in (200, 201, 204, 403) or _answer(got) != _answer(none):
            told.append((method, template, got.status, got.text[:120]))
            continue
        if got.status == 404:
            own = http.call(method, real, as_user=people.researcher, body=body)
            if _answer(own) == _answer(got):
                unproven.append((method, template, own.status, own.text[:120]))
    assert not told, (
        f"{len(told)} of {len(routes)} client routes tell another organization the client "
        "exists:\n" + "\n".join(map(str, told))
    )
    assert not unproven, "\n".join(map(str, unproven))
