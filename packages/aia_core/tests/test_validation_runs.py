"""Starting a respondent system's confirmation run (panel-grounded-respondents 7e3).

Over the fictional population in ``conftest.py`` and the hand-built preregistration
(``holdout_records``): what the run is made from, everything a start refuses before it writes,
the cost gates, and the rule that a system is confirmed once in an organization.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.population import PopulationRuntime
from aia_core.application.research import CostConfirmationRequired
from aia_core.application.validation import ValidationRuns
from aia_core.domain.holdout.preregistration import HoldoutRefused
from aia_core.domain.holdout.run import VALIDATION_WORKFLOW, arm_node_key
from aia_core.domain.panel_source import pinned_components
from aia_core.domain.population import PopulationKind
from aia_core.infrastructure.holdout_repository import HoldoutRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow, StepRunRow, WorkflowRunRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

LIVE = "SYN_LIVE"
BINDING = "bedrock/claude/bedrock-eu-primary"


@pytest.fixture
def live(session: Any, synthetic_population: Any) -> str:
    """STATIC and LIVE established over the fictional versions; LIVE's version id."""
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    ids = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional test bundle",
            imported_by="importer",
        ).version_id
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    operator = PopulationAuthority(
        PopulationOperatorConfig.from_names({"operator": ("POPULATION_ESTABLISH",)})
    ).operator_context(AuthenticatedPrincipal(user_id="operator", organization_id="platform"))
    for population_id, kind, label in (
        ("SYN_STATIC", PopulationKind.STATIC, "v1_1"),
        (LIVE, PopulationKind.LIVE, "v1_4"),
    ):
        runtime.establish(
            operator=operator,
            population_id=population_id,
            kind=kind,
            version_id=ids[label],
            reason="established for the test",
        )
    return ids["v1_4"]


@pytest.fixture
def prereg(holdout_records: Any, live: str) -> Any:
    """``prereg(**overrides)``: the hand-built record, over today's system and LIVE."""

    def build(**overrides: Any) -> Any:
        system = {**pinned_components(live), "model_binding": BINDING}
        return holdout_records.preregistration(
            system={**system, **overrides.pop("system", {})}, **overrides
        )

    return build


@pytest.fixture
def validation(session: Any, scoped: Any, synthetic_population: Any) -> Any:
    """``validation(user=…, study=…)``: the service over the fictional contract and LIVE."""

    def build(**kw: Any) -> ValidationRuns:
        return ValidationRuns(
            session,
            scoped.scope(**kw),
            population_contract=synthetic_population.contract,
            population_id=LIVE,
        )

    return build


def _fix(session: Any, scoped: Any, prereg: Any, **kw: Any) -> Any:
    return HoldoutRepository(session, scoped.scope(**kw)).record_preregistration(prereg)


def test_a_confirmation_run_is_made_from_the_stored_preregistration_alone(
    session: Any, scoped: Any, prereg: Any, holdout_records: Any, validation: Any, live: str
) -> None:
    stored = _fix(session, scoped, prereg())
    started = validation().start(bank=holdout_records.bank(), reservation_usd=0.01)
    assert started.created and started.workflow_type == VALIDATION_WORKFLOW
    run = started.run
    assert run["metadata"]["preregistration_sha256"] == stored.sha256
    assert run["metadata"]["respondent_system_fingerprint"] == stored.respondent_system_fingerprint
    assert run["metadata"]["population"]["version_id"] == live
    assert run["metadata"]["requests"] == 600 * 2 * 5 * 3
    assert run["metadata"]["cost_ceiling_usd"] == pytest.approx(180.0)
    workflows = WorkflowRepository(session, scoped.scope())
    assert workflows.population_binding(started.run_id).version_id == live
    inputs = {
        row.node_key: row.input_json
        for row in session.scalars(select(StepRunRow).where(StepRunRow.run_id == started.run_id))
    }
    assert len(inputs) == len(run["steps"]) == 1 + 15 + 1
    arm = inputs[arm_node_key("S", 2)]
    assert (arm["arm"], arm["replicate"], arm["seed"], arm["shuffle_seed"]) == ("S", 2, 12, 12)
    assert arm["blocks"] == [["c1", "c2"], ["c3"]] and arm["model_binding"] == BINDING
    # A block's respondents lose every field the block's preregistration leaves out.
    assert arm["exclusions"]["c2"] == ["c1", "c2", "persona_income", "signal_family"]
    assert arm["exclusions"]["c3"] == ["c3"]
    assert [q["id"] for q in arm["specification"]["questions"]] == ["c1", "c2", "c3"]
    assert "shuffle_seed" not in inputs[arm_node_key("D", 1)]
    assert inputs["score"]["preregistration"] == dict(stored.preregistration.document)
    # The run is the Study's confirmation, found through the Study.
    assert validation().run()["run_id"] == started.run_id
    assert HoldoutRepository(session, scoped.scope()).confirmation().run_id == started.run_id
    # Asking again finds it and spends nothing.
    again = validation(user="researcher").start(bank=holdout_records.bank(), reservation_usd=0.01)
    assert not again.created and again.run_id == started.run_id


def test_nothing_is_confirmed_without_a_preregistration(
    holdout_records: Any, validation: Any, live: str
) -> None:
    with pytest.raises(HoldoutRefused) as refused:
        validation().start(bank=holdout_records.bank(), reservation_usd=0.01)
    assert refused.value.reason == "holdout_preregistration_missing"
    assert validation().run() is None


@pytest.mark.parametrize(
    ("overrides", "bank_wording", "reason"),
    [
        ({"system": {"persona_mode": "another mode"}}, None, "holdout_system_stale"),
        ({"system": {"population_version": "pv_other"}}, None, "holdout_system_stale"),
        ({"bank_sha256": "e" * 64}, None, "holdout_bank_mismatch"),
        ({}, {"c3": "Kolik je vám let?"}, "holdout_item_is_a_fact"),
        ({"cost_ceiling_usd": 100.0}, None, "holdout_cost_above_preregistration"),
    ],
)
def test_a_start_that_would_not_confirm_the_preregistered_system_is_refused_before_any_write(
    session: Any,
    scoped: Any,
    prereg: Any,
    holdout_records: Any,
    validation: Any,
    overrides: dict[str, Any],
    bank_wording: dict[str, str] | None,
    reason: str,
) -> None:
    _fix(session, scoped, prereg(**overrides))
    with pytest.raises(HoldoutRefused) as refused:
        validation().start(bank=holdout_records.bank(wording=bank_wording), reservation_usd=0.01)
    assert refused.value.reason == reason
    assert validation().run() is None
    assert session.scalars(select(WorkflowRunRow)).all() == []


def test_an_unknown_reservation_is_never_a_zero_cost(
    session: Any, scoped: Any, prereg: Any, holdout_records: Any, validation: Any
) -> None:
    _fix(session, scoped, prereg())
    with pytest.raises(HoldoutRefused) as refused:
        validation().start(bank=holdout_records.bank(), reservation_usd=None)
    assert refused.value.reason == "holdout_cost_unknown"


def test_a_ceiling_at_the_studys_spend_limit_needs_the_persons_yes_and_records_it(
    session: Any, scoped: Any, prereg: Any, holdout_records: Any, validation: Any
) -> None:
    _fix(session, scoped, prereg())
    scoped.scope_repo.set_study_spend_confirm(scoped.scope(), limit_usd=150.0)
    with pytest.raises(CostConfirmationRequired) as asked:
        validation().start(bank=holdout_records.bank(), reservation_usd=0.01)
    assert asked.value.ceiling_usd == pytest.approx(180.0) and asked.value.limit_usd == 150.0
    started = validation().start(
        bank=holdout_records.bank(), reservation_usd=0.01, confirm_cost_usd=180.0
    )
    rows = session.scalars(
        select(ApprovalDecisionRow).where(ApprovalDecisionRow.run_id == started.run_id)
    ).all()
    assert [(r.gate_type, r.decision) for r in rows] == [("spend", "confirm")]


def test_a_respondent_system_is_confirmed_once_in_an_organization(
    session: Any, scoped: Any, prereg: Any, holdout_records: Any, validation: Any
) -> None:
    _fix(session, scoped, prereg())
    # Another Study preregisters the same system under another seed: a second draw of it.
    _fix(session, scoped, prereg(sample_seed=2), study="sibling")
    validation().start(bank=holdout_records.bank(), reservation_usd=0.01)
    with pytest.raises(HoldoutRefused) as refused:
        validation(study="sibling").start(bank=holdout_records.bank(), reservation_usd=0.01)
    assert refused.value.reason == "holdout_system_confirmation_started"
    assert validation(study="sibling").run() is None


def test_the_database_holds_the_rule_when_two_starts_race(
    session: Any, scoped: Any, prereg: Any
) -> None:
    first = _fix(session, scoped, prereg())
    second = _fix(session, scoped, prereg(sample_seed=2), study="sibling")
    HoldoutRepository(session, scoped.scope()).record_confirmation(
        run_id="RUN-a", preregistration_sha256=first.sha256
    )
    # The sibling's check ran before the first record existed; its own record is refused.
    with pytest.raises(HoldoutRefused) as refused:
        HoldoutRepository(session, scoped.scope(study="sibling")).record_confirmation(
            run_id="RUN-b", preregistration_sha256=second.sha256
        )
    assert refused.value.reason == "holdout_system_confirmation_started"
    # The first record stands, and the transaction is usable.
    assert HoldoutRepository(session, scoped.scope()).confirmation().run_id == "RUN-a"
