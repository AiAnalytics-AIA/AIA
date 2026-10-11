"""The methodology store: who may change it, what a change leaves behind, what is in force.

ADR 0023 decision 3; plan ``methodology-tab.md`` A3. Against a real database through the same
scope path production uses.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.scope import ScopeDenied
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V3
from aia_core.infrastructure.methodology_repository import (
    MethodologyReader,
    MethodologyRefused,
    MethodologyRepository,
)
from aia_core.infrastructure.tables import AccessAuditRow, MethodologyVersionRow

SOCIOMAP = "sociomap"


def _spec(**changes: Any) -> dict[str, Any]:
    spec = AIA_SOCIOMAP_V3.model_dump(mode="json")
    for path, value in changes.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return spec


def _member(scoped: Any) -> Any:
    return scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))


def _repo(scoped: Any, session: Any) -> MethodologyRepository:
    return MethodologyRepository(session, scoped.admin_context)


def _reader(scoped: Any, session: Any) -> MethodologyReader:
    return MethodologyReader(session, _member(scoped))


def _propose(repo: MethodologyRepository, **changes: Any) -> Any:
    formulas = changes.pop("formulas", {})
    return repo.propose(
        SOCIOMAP, base_preset="aia-sociomap-3", spec=_spec(**changes), formulas=formulas
    )


def _audit(session: Any) -> list[AccessAuditRow]:
    return list(
        session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.action.like("METHODOLOGY_%"))
            .order_by(AccessAuditRow.event_id)
        )
    )


def test_a_member_reads_but_only_an_administrator_changes(scoped: Any, session: Any) -> None:
    member = _member(scoped)
    assert MethodologyReader(session, member).in_force(SOCIOMAP).origin == "code"
    with pytest.raises(ScopeDenied) as denied:
        MethodologyRepository(session, member)
    assert denied.value.reason == "insufficient_role"


def test_with_nothing_stored_the_codes_preset_is_in_force(scoped: Any, session: Any) -> None:
    in_force = _reader(scoped, session).in_force(SOCIOMAP)
    assert (in_force.origin, in_force.preset, in_force.version) == ("code", "aia-sociomap-3", None)
    assert _reader(scoped, session).versions(SOCIOMAP) == []


def test_a_proposal_is_a_named_version_and_not_yet_in_force(scoped: Any, session: Any) -> None:
    version = _propose(_repo(scoped, session), relation__n_min=40, terrain__sigma=0.3)
    assert (version.version_number, version.name) == (1, "aia-sociomap-3+e1")
    assert version.payload["spec"]["methodology_version"] == "aia-sociomap-3+e1"
    assert version.payload["spec"]["relation"]["n_min"] == 40
    assert len(version.payload_sha256) == 64
    assert _reader(scoped, session).in_force(SOCIOMAP).origin == "code"
    assert [a.action for a in _audit(session)] == ["METHODOLOGY_PROPOSED"]


def test_activation_puts_a_version_in_force_and_reset_returns_to_the_preset(
    scoped: Any, session: Any
) -> None:
    repo = _repo(scoped, session)
    _propose(repo, relation__n_min=40)
    second = _propose(repo, terrain__sigma=0.3)
    in_force = repo.activate(SOCIOMAP, 2, reason="širší kopec ověřen")
    assert in_force.origin == "stored" and in_force.version is not None
    assert in_force.version.payload == second.payload
    assert _reader(scoped, session).in_force(SOCIOMAP).version == second
    back = repo.activate(SOCIOMAP, None, reason="zpět")
    assert (back.origin, back.preset) == ("code", "aia-sociomap-3")
    history = _reader(scoped, session).history(SOCIOMAP)
    assert [(a.version_number, a.reason) for a in history] == [
        (None, "zpět"),
        (2, "širší kopec ověřen"),
    ]
    assert [a.action for a in _audit(session)] == [
        "METHODOLOGY_PROPOSED",
        "METHODOLOGY_PROPOSED",
        "METHODOLOGY_ACTIVATED",
        "METHODOLOGY_RESET",
    ]


def test_putting_in_force_what_is_in_force_changes_nothing(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    _propose(repo)
    repo.activate(SOCIOMAP, 1)
    repo.activate(SOCIOMAP, 1)
    assert len(_reader(scoped, session).history(SOCIOMAP)) == 1


def test_an_invalid_version_is_refused_with_every_problem_and_nothing_stored(
    scoped: Any, session: Any
) -> None:
    with pytest.raises(MethodologyRefused) as refused:
        _propose(_repo(scoped, session), relation__n_min=2, formulas={"f6.distance": "open('x')"})
    assert refused.value.reason == "methodology_invalid"
    assert {"spec.relation.n_min", "formula.f6.distance"} <= set(refused.value.problems)
    assert session.scalar(select(MethodologyVersionRow)) is None
    assert _audit(session) == []


def test_the_reference_map_and_an_unknown_module_are_refused(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    with pytest.raises(MethodologyRefused) as reference:
        repo.propose("sociomap_reference", base_preset="aia-sociomap-1", spec={}, formulas={})
    assert reference.value.reason == "methodology_invalid"
    assert "module" in reference.value.problems
    with pytest.raises(MethodologyRefused) as unknown:
        repo.activate("nothing", None)
    assert unknown.value.reason == "unknown_module"


def test_an_unknown_version_cannot_be_put_in_force(scoped: Any, session: Any) -> None:
    with pytest.raises(MethodologyRefused) as refused:
        _repo(scoped, session).activate(SOCIOMAP, 7)
    assert refused.value.reason == "unknown_version"


def test_versions_are_immutable_and_numbered_per_organization(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    _propose(repo)
    _propose(repo, relation__n_min=50)
    numbers = [v.version_number for v in _reader(scoped, session).versions(SOCIOMAP)]
    assert numbers == [2, 1]
    other_org, other_owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    principal = replace(
        scoped.principal(other_owner.user_id), organization_id=other_org.organization_id
    )
    owner = scoped.resolver.organization_context(principal)
    theirs = MethodologyRepository(session, owner)
    first = theirs.propose(SOCIOMAP, base_preset="aia-sociomap-3", spec=_spec(), formulas={})
    assert first.version_number == 1
    assert MethodologyReader(session, owner).in_force(SOCIOMAP).origin == "code"
    theirs.activate(SOCIOMAP, 1)
    assert _reader(scoped, session).in_force(SOCIOMAP).origin == "code"  # not this org's


def test_a_long_note_or_reason_is_refused_not_cut(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    with pytest.raises(MethodologyRefused) as note:
        repo.propose(
            SOCIOMAP, base_preset="aia-sociomap-3", spec=_spec(), formulas={}, note="x" * 501
        )
    assert note.value.reason == "note_too_long"
    with pytest.raises(MethodologyRefused) as reason:
        repo.activate(SOCIOMAP, None, reason="x" * 501)
    assert reason.value.reason == "reason_too_long"


def test_a_version_replacing_a_formula_is_put_in_force(scoped: Any, session: Any) -> None:
    """The engine computes every slot from its expression (plan S4c)."""
    repo = _repo(scoped, session)
    version = _propose(repo, formulas={"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"})
    in_force = repo.activate(SOCIOMAP, version.version_number)
    assert in_force.version is not None
    assert in_force.version.payload["formulas"] == {"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"}


def test_a_formula_the_engine_does_not_compute_is_never_put_in_force(
    scoped: Any, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stored and shown, never in force: a run must not compute the built-in formula while
    its methodology says another (plan A4). Every built-in slot is computed today, so the
    engine's set is narrowed here to reach the refusal."""
    from aia_core.domain.methodology import pins

    monkeypatch.setattr(pins, "COMPUTED_SLOTS", frozenset())
    repo = _repo(scoped, session)
    version = _propose(repo, formulas={"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"})
    with pytest.raises(MethodologyRefused) as refused:
        repo.activate(SOCIOMAP, version.version_number)
    assert refused.value.reason == "formula_not_computed"
    assert set(refused.value.problems) == {"formula.f12.kernel"}
    assert _reader(scoped, session).in_force(SOCIOMAP).origin == "code"
