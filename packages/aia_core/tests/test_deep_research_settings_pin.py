"""A Deep Research run pins the settings in force at its enqueue (chunk 43, first part).

ADR 0022 decision 4: the run stores every setting's value and where it came from, with its
digests, beside its run spec; the plan step reads the pin, never the store; an approval
changes only runs enqueued after it; a pin that does not hash to itself is never run. With
nothing approved, a run's request and every step's fingerprint are what they were (the
values the engine reads from a pin: ``test_deep_research_settings_values.py``).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from aia_core.application.deep_research import DeepResearchRuns, run_settings
from aia_core.domain.deep_research.settings import (
    CATALOGUE,
    CATALOGUE_VERSION,
    SETTINGS_PIN_CONTRACT,
    Origin,
    SettingsPinCorrupt,
    effective,
    pin,
    read_pin,
)
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsRepository,
    settings_in_force_for_study,
)
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository

RETENTION = "retention.snapshots"

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "research_plan": {"research_questions": ["Jak roste trh rostlinných nápojů v Česku?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Kupujete rostlinné nápoje?", "kategorie": ["Ano", "Ne"]}
            ],
        }
    ],
}


def _stored(settings: Any) -> dict[str, Any]:
    """The pin as the run's JSON column returns it."""
    return json.loads(json.dumps(pin(settings)))  # type: ignore[no-any-return]


# ------------------------------------------------------------------ the pin itself


def test_a_pin_reads_back_as_the_settings_it_was_made_from() -> None:
    settings = effective({})
    stored = _stored(settings)
    assert stored["contract"] == SETTINGS_PIN_CONTRACT
    assert stored["catalogue"] == CATALOGUE_VERSION
    assert [v["key"] for v in stored["values"]] == [d.key for d in CATALOGUE]
    assert {v["origin"] for v in stored["values"]} == {Origin.PROPOSED_DEFAULT.value}
    back = read_pin(stored)
    assert back == settings
    assert (stored["settings_digest"], stored["method_digest"]) == (
        settings.digest(),
        settings.method_digest(),
    )


def _row(stored: dict[str, Any], key: str) -> dict[str, Any]:
    return next(v for v in stored["values"] if v["key"] == key)  # type: ignore[no-any-return]


def _altered(change: Any) -> dict[str, Any]:
    stored = _stored(effective({}))
    change(stored)
    return stored


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda p: _row(p, RETENTION).update(value=91), "pin_altered"),
        (lambda p: p["values"][0].update(origin="approved"), "pin_altered"),
        (lambda p: p.update(method_digest="0" * 64), "pin_altered"),
        (lambda p: p["values"].pop(), "pin_unreadable"),
        (lambda p: p["values"].append(dict(p["values"][0])), "pin_unreadable"),
        (lambda p: p["values"][0].update(origin="guessed"), "pin_unreadable"),
        (lambda p: p.update(contract="aia-dr-settings-pin-0"), "pin_unreadable"),
        (lambda p: p.update(catalogue="aia-dr-settings-catalogue-0"), "catalogue_changed"),
    ],
)
def test_a_pin_that_does_not_prove_itself_is_refused_by_name(change: Any, reason: str) -> None:
    with pytest.raises(SettingsPinCorrupt) as refused:
        read_pin(_altered(change))
    assert refused.value.reason == reason


def test_nothing_that_is_not_a_pin_reads_as_one() -> None:
    for junk in (None, [], "pin", {"contract": SETTINGS_PIN_CONTRACT}):
        with pytest.raises(SettingsPinCorrupt):
            read_pin(junk)


# ------------------------------------------------------------------ on a run


@pytest.fixture
def start(session: Any, scoped: Any) -> Any:
    """``start(preset)``: a Design Research run over a fresh revision of the primary study."""

    def go(preset: str = "QUICK", content: dict[str, Any] = DESIGN) -> Any:
        scope = scoped.scope(user="lead")
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=content, source_stage="brief"
        )
        return DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name=preset
        )

    return go


def _approve(scoped: Any, session: Any, key: str, value: Any) -> None:
    repo = DeepResearchSettingsRepository(session, scoped.admin_context)
    version = repo.propose(key, value)
    repo.approve(key, version.version_number)


def test_a_run_pins_what_its_organization_has_in_force(
    start: Any, scoped: Any, session: Any
) -> None:
    started = start()
    metadata = started.run["metadata"]
    in_force = settings_in_force_for_study(session, scoped.scope(user="lead"))
    assert run_settings(metadata) == in_force
    assert metadata["settings_pin"] == _stored(in_force)
    plan = WorkflowRepository(session, scoped.scope(user="lead")).get_run(started.run_id)
    assert plan["metadata"]["settings_pin"]["pin_digest"] == metadata["settings_pin"]["pin_digest"]


def test_an_approval_reaches_only_runs_enqueued_after_it(
    start: Any, scoped: Any, session: Any
) -> None:
    before = start()
    _approve(scoped, session, RETENTION, 90)
    after = start(content={**DESIGN, "title": "Rostlinné nápoje II"})
    first = run_settings(before.run["metadata"])
    second = run_settings(after.run["metadata"])
    assert first is not None and second is not None
    assert first[RETENTION].origin is Origin.PROPOSED_DEFAULT
    assert (second[RETENTION].origin, second[RETENTION].value) == (Origin.APPROVED, 90)
    # The earlier run's pin did not move, read again after the approval.
    run = DeepResearchRuns(session, scoped.scope(user="lead")).get(before.run_id)
    assert run_settings(run["metadata"]) == first


def test_with_nothing_approved_the_request_carries_no_method_digest(
    start: Any, session: Any
) -> None:
    """Harness 3 with nothing approved: the plan's request holds no method digest, so it and
    every key it shapes are harness 2's but for the harness string; every step's fingerprint
    is the engine request's; the plan step's input carries the pin beside the request."""
    from sqlalchemy import select

    from aia_core.infrastructure.tables import StepRunRow

    started = start()
    metadata = started.run["metadata"]
    assert metadata["harness_version"] == "aia-deep-research-harness-3"
    rows = session.scalars(select(StepRunRow).where(StepRunRow.run_id == started.run_id)).all()
    assert {r.input_fingerprint for r in rows} == {metadata["request_fingerprint"]}
    (plan,) = [r for r in rows if r.node_key == "plan"]
    assert set(plan.input_json) == {"request", "settings"}
    # Nothing approved: the request carries no method digest, so it keys as harness 2's.
    assert "settings_method" not in plan.input_json["request"]
    assert plan.input_json["settings"] == metadata["settings_pin"]


def test_a_run_stored_before_pins_reads_as_none_and_a_tampered_one_is_refused(
    start: Any,
) -> None:
    metadata = start().run["metadata"]
    assert run_settings({k: v for k, v in metadata.items() if k != "settings_pin"}) is None
    tampered = {**metadata, "settings_pin": {**metadata["settings_pin"], "method_digest": "0" * 64}}
    with pytest.raises(SettingsPinCorrupt):
        run_settings(tampered)


def test_another_organizations_approvals_never_reach_this_studys_pin(
    start: Any, scoped: Any, session: Any
) -> None:
    from dataclasses import replace

    other_org, other_owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    owner = scoped.resolver.organization_context(
        replace(scoped.principal(other_owner.user_id), organization_id=other_org.organization_id)
    )
    repo = DeepResearchSettingsRepository(session, owner)
    version = repo.propose(RETENTION, 30)
    repo.approve(RETENTION, version.version_number)
    pinned = run_settings(start().run["metadata"])
    assert pinned is not None and pinned[RETENTION].origin is Origin.PROPOSED_DEFAULT


def test_an_approved_method_setting_is_another_run_and_a_status_setting_is_not(
    start: Any, scoped: Any, session: Any
) -> None:
    """Harness 3: the request carries the approved method digest, so a start repeated after a
    method setting is approved is a new run, and one after a non-method approval is not."""
    first = start()
    _approve(scoped, session, RETENTION, 90)  # retention shapes no result: not a method key
    assert start().run_id == first.run_id
    _approve(scoped, session, "budgets.allowance.exhaustive.crawl_pages", 300)
    second = start()
    assert second.run_id != first.run_id
    pinned = run_settings(second.run["metadata"])
    assert pinned is not None and pinned.approved_method() == pinned.method_digest()
    assert (
        second.run["metadata"]["request_fingerprint"]
        != first.run["metadata"]["request_fingerprint"]
    )
