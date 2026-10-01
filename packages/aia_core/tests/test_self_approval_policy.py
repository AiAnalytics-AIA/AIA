"""Configurable self-approval: the policy, its hierarchy, and its audit trail.

Self-approval is **allowed by default** since ADR 0019: the person who produced
something may accept it, and the audit record says so. An organization, a client
or a study may turn it off, and an explicit ``False`` is honoured, resolved from
persisted AIA state as ``study > client > organization > true``.

Two properties are being defended here, and they are easy to confuse:

* **Policy decides independence, permission decides authority.** Allowing
  self-approval does not let someone approve who could not approve anyway. The
  worker's execution context still cannot sign off, because it holds no sign-off
  permission at all (ADR 0019 decision 6), whatever the policy says.
* **Policy is server state, never an argument.** It reaches the approval on a
  :class:`StudyContext`, which only the authorization layer can issue. A model, an
  agent, a tool argument or a request body has no way to assert it.

The permanent regressions -- that a scope which has turned self-approval off
refuses it, and that a deployment which has configured nothing allows and records
it -- live next to the features they guard, in ``test_workflow_engine.py`` and
``test_artifacts.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.scope import (
    DEFAULT_SELF_APPROVAL_ALLOWED,
    Permission,
    ScopeDenied,
    SelfApprovalPolicy,
    SelfApprovalSource,
    SeparationOfDutiesViolation,
    StudyContext,
    resolve_self_approval_policy,
)
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import AccessAuditRow, ApprovalDecisionRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository, WorkQueue

# Declared here rather than imported: both test directories in this repository
# are called `tests`, so they are not packages and cannot import each other.
PIPELINE = [
    StepDefinition(node_key="compile", kind="project_compile", stage_type="BRIEF"),
    StepDefinition(
        node_key="report", kind="final_report", depends_on=("compile",), stage_type="REPORT"
    ),
]


# --------------------------------------------------------------------------- #
# Resolution: the hierarchy, in isolation from any database
# --------------------------------------------------------------------------- #


def test_self_approval_is_allowed_by_default() -> None:
    """ADR 0019: configure nothing, and a person may accept what they produced."""
    policy = resolve_self_approval_policy()
    assert policy.allowed is True
    assert policy.source is SelfApprovalSource.DEFAULT
    assert SelfApprovalPolicy().allowed is True
    assert DEFAULT_SELF_APPROVAL_ALLOWED is True


def test_an_explicit_false_is_honoured_at_every_level() -> None:
    """Turning independent review back on is still possible, per scope."""
    for levels in ({"organization": False}, {"client": False}, {"study": False}):
        policy = resolve_self_approval_policy(**levels)
        assert policy.allowed is False
        assert policy.source is not SelfApprovalSource.DEFAULT


def test_organization_enables_self_approval_for_everything_beneath_it() -> None:
    policy = resolve_self_approval_policy(organization=True)
    assert policy.allowed is True
    assert policy.source is SelfApprovalSource.ORGANIZATION


def test_client_overrides_the_organization_in_both_directions() -> None:
    """A client override wins whichever way it points.

    Turning it *off* for one client under a permissive organization is the case
    that matters: a client contract may require independent review regardless of
    how the organization is configured.
    """
    assert resolve_self_approval_policy(organization=False, client=True) == SelfApprovalPolicy(
        allowed=True, source=SelfApprovalSource.CLIENT
    )
    assert resolve_self_approval_policy(organization=True, client=False) == SelfApprovalPolicy(
        allowed=False, source=SelfApprovalSource.CLIENT
    )


def test_study_overrides_the_client_in_both_directions() -> None:
    assert resolve_self_approval_policy(
        organization=False, client=False, study=True
    ) == SelfApprovalPolicy(allowed=True, source=SelfApprovalSource.STUDY)
    assert resolve_self_approval_policy(
        organization=True, client=True, study=False
    ) == SelfApprovalPolicy(allowed=False, source=SelfApprovalSource.STUDY)


def test_none_inherits_rather_than_meaning_false() -> None:
    """``None`` is "ask my parent", which is not the same as "no".

    If ``None`` meant ``False`` the hierarchy would not be a hierarchy: every
    unconfigured client would silently override its organization.
    """
    assert resolve_self_approval_policy(organization=True, client=None, study=None).allowed is True
    assert resolve_self_approval_policy(organization=True, client=True, study=None).source is (
        SelfApprovalSource.CLIENT
    )


@pytest.mark.parametrize(
    ("organization", "client", "study", "expected_source"),
    [
        (None, None, None, SelfApprovalSource.DEFAULT),
        (True, None, None, SelfApprovalSource.ORGANIZATION),
        (True, True, None, SelfApprovalSource.CLIENT),
        (None, False, None, SelfApprovalSource.CLIENT),
        (True, True, True, SelfApprovalSource.STUDY),
        (None, None, False, SelfApprovalSource.STUDY),
    ],
)
def test_specificity_precedence(
    organization: bool | None,
    client: bool | None,
    study: bool | None,
    expected_source: SelfApprovalSource,
) -> None:
    """The most specific configured level always decides, and says so."""
    policy = resolve_self_approval_policy(organization=organization, client=client, study=study)
    assert policy.source is expected_source


# --------------------------------------------------------------------------- #
# Resolution against persisted state
# --------------------------------------------------------------------------- #


def _enable(scoped: Any, **where: Any) -> None:
    """Enable self-approval at one level through the trusted admin path."""
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=True, **where)


def _disable(scoped: Any, **where: Any) -> None:
    """Turn self-approval off at one level: the way independent review comes back."""
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False, **where)


def test_the_policy_reaches_the_study_context_from_persisted_state(
    session: Session, scoped: Any
) -> None:
    """The resolver reads configuration; nothing else supplies it."""
    default = scoped.scope(user="lead").self_approval
    assert (default.allowed, default.source) == (True, SelfApprovalSource.DEFAULT)

    _disable(scoped)
    session.flush()
    policy = scoped.scope(user="lead").self_approval
    assert policy.allowed is False
    assert policy.source is SelfApprovalSource.ORGANIZATION


def test_a_client_setting_does_not_leak_to_another_client(session: Session, scoped: Any) -> None:
    """The override is scoped to the client it was set on."""
    _disable(scoped, client_id=scoped.clients["primary"].client_id)
    session.flush()

    assert scoped.scope(user="lead", study="primary").self_approval.allowed is False
    other = scoped.scope(user="other_lead", study="other_client").self_approval
    assert (other.allowed, other.source) == (True, SelfApprovalSource.DEFAULT)


def test_a_study_setting_does_not_leak_to_a_sibling_study(session: Session, scoped: Any) -> None:
    _disable(scoped, study_id=scoped.studies["primary"].study_id)
    session.flush()

    primary = scoped.scope(user="lead", study="primary").self_approval
    sibling = scoped.scope(user="lead", study="sibling").self_approval
    assert (primary.allowed, primary.source) == (False, SelfApprovalSource.STUDY)
    assert (sibling.allowed, sibling.source) == (True, SelfApprovalSource.DEFAULT)


def test_clearing_a_level_restores_inheritance(session: Session, scoped: Any) -> None:
    """``allowed=None`` is not ``False``: it hands the decision back upwards."""
    study_id = scoped.studies["primary"].study_id
    _enable(scoped)
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False, study_id=study_id)
    session.flush()
    assert scoped.scope(user="lead", study="primary").self_approval.allowed is False

    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=None, study_id=study_id)
    session.flush()
    resolved = scoped.scope(user="lead", study="primary").self_approval
    assert resolved.allowed is True
    assert resolved.source is SelfApprovalSource.ORGANIZATION


def test_configuring_self_approval_requires_organization_administration(
    session: Session, scoped: Any
) -> None:
    """An ordinary member cannot arrange self-approval for their own study.

    Changing the control, in either direction, is an administrative act (ADR 0019
    keeps the setting, and who may change it). If a Researcher could set it, the
    control would be self-service and therefore no control.
    """
    from aia_core.application.scope import ScopeResolver
    from aia_core.domain.scope import OrganizationContext, ScopeGrant

    member_context = ScopeResolver(session).organization_context(
        scoped.principal(scoped.users["lead"])
    )
    assert isinstance(member_context, OrganizationContext)
    assert isinstance(member_context.grant, ScopeGrant)

    with pytest.raises(ScopeDenied):
        scoped.scope_repo.set_self_approval(member_context, allowed=True)


def test_levels_read_back_as_stored_not_as_resolved(session: Session, scoped: Any) -> None:
    """The read shows which level decided, which a resolved value cannot."""
    assert scoped.scope_repo.self_approval_levels(scoped.admin_context) == {
        "organization": None,
        "clients": [],
        "studies": [],
    }

    client_id = scoped.clients["primary"].client_id
    study_id = scoped.studies["sibling"].study_id
    _enable(scoped)
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False, client_id=client_id)
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=True, study_id=study_id)
    session.flush()

    levels = scoped.scope_repo.self_approval_levels(scoped.admin_context)
    assert levels["organization"] is True
    assert levels["clients"] == [{"client_id": client_id, "allowed": False}]
    assert levels["studies"] == [{"study_id": study_id, "client_id": client_id, "allowed": True}]

    # Clearing a level removes it from the list: absent means inherit.
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=None, client_id=client_id)
    session.flush()
    assert scoped.scope_repo.self_approval_levels(scoped.admin_context)["clients"] == []


def test_reading_self_approval_levels_requires_organization_administration(
    session: Session, scoped: Any
) -> None:
    from aia_core.application.scope import ScopeResolver

    member_context = ScopeResolver(session).organization_context(
        scoped.principal(scoped.users["lead"])
    )
    with pytest.raises(ScopeDenied):
        scoped.scope_repo.self_approval_levels(member_context)


def test_configuring_self_approval_is_audited(session: Session, scoped: Any) -> None:
    """Turning the control off is itself a security event."""
    _enable(scoped, client_id=scoped.clients["primary"].client_id)
    session.flush()

    row = session.scalars(
        select(AccessAuditRow).where(AccessAuditRow.action == "SELF_APPROVAL_CONFIGURED")
    ).one()
    assert row.client_id == scoped.clients["primary"].client_id
    assert row.payload == {"level": "client", "allow_self_approval": True}


def test_policy_cannot_be_supplied_by_a_caller(session: Session, scoped: Any) -> None:
    """A StudyContext carrying a permissive policy cannot be fabricated.

    This is the security rule: a model, an agent, a tool argument or a request
    body must not be able to decide that self-approval is permitted. The policy
    travels on a context that only the authorization layer can issue, and
    constructing one without an issued grant fails.
    """
    with pytest.raises(ScopeDenied):
        StudyContext(
            organization_id=scoped.organization_id,
            client_id=scoped.clients["primary"].client_id,
            study_id=scoped.studies["primary"].study_id,
            actor_id=scoped.users["lead"],
            role=scoped.scope(user="lead").role,
            permissions=frozenset({Permission.APPROVE_GATE}),
            organization_role=scoped.admin_context.organization_role,
            grant={"forged": True},  # type: ignore[arg-type]
            self_approval=SelfApprovalPolicy(allowed=True, source=SelfApprovalSource.STUDY),
        )


# --------------------------------------------------------------------------- #
# Artifact sign-off under policy
# --------------------------------------------------------------------------- #


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture
def project(session: Session, scoped: Any) -> Any:
    created, _ = ProjectRepository(session, scoped.scope(user="lead")).create(
        title="Approval host", content={"goal": "g"}
    )
    return created


def _authored_artifact(session: Session, scoped: Any, store: Any, project: Any) -> str:
    """A report artifact authored by the lead, who also holds sign-off."""
    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    artifact, _ = repo.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"draft": True},
    )
    return artifact.artifact_id


def test_the_default_lets_a_person_sign_off_what_they_produced(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    """ADR 0019: nothing configured, and the author may accept their own work.

    The audit record still says so: ``self_approved`` is True and the policy came
    from the default.
    """
    artifact_id = _authored_artifact(session, scoped, store, project)

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    assert repo.approve(artifact_id).is_approved is True

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.producer_user_id == record.approver_user_id == scoped.users["lead"]
    assert record.self_approved is True
    assert record.self_approval_allowed is True
    assert record.self_approval_source == SelfApprovalSource.DEFAULT.value


@pytest.mark.parametrize("level", ["organization", "client", "study"])
def test_turning_self_approval_off_at_any_level_refuses_self_sign_off(
    session: Session, scoped: Any, store: Any, project: Any, level: str
) -> None:
    """The setting survives ADR 0019: a scope can demand independent review."""
    artifact_id = _authored_artifact(session, scoped, store, project)
    wheres: dict[str, dict[str, str]] = {
        "organization": {},
        "client": {"client_id": scoped.clients["primary"].client_id},
        "study": {"study_id": scoped.studies["primary"].study_id},
    }
    where = wheres[level]
    _disable(scoped, **where)
    session.flush()

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    with pytest.raises(SeparationOfDutiesViolation):
        repo.approve(artifact_id)

    # Someone else may still accept it: independence is what the setting asks for.
    other = ArtifactRepository(session, scoped.scope(user="reviewer"), store)
    assert other.approve(artifact_id).is_approved is True


def test_organization_level_enable_permits_self_sign_off(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    artifact_id = _authored_artifact(session, scoped, store, project)
    _enable(scoped)
    session.flush()

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    assert repo.approve(artifact_id).is_approved is True


def test_client_level_override_permits_self_sign_off(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    artifact_id = _authored_artifact(session, scoped, store, project)
    _enable(scoped, client_id=scoped.clients["primary"].client_id)
    session.flush()

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    assert repo.approve(artifact_id).is_approved is True


def test_study_level_override_permits_self_sign_off(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    artifact_id = _authored_artifact(session, scoped, store, project)
    _enable(scoped, study_id=scoped.studies["primary"].study_id)
    session.flush()

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    assert repo.approve(artifact_id).is_approved is True


def test_a_study_override_of_false_beats_a_permissive_organization(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    """Specificity wins even when the specific answer is the stricter one."""
    artifact_id = _authored_artifact(session, scoped, store, project)
    _enable(scoped)
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, study_id=scoped.studies["primary"].study_id
    )
    session.flush()

    repo = ArtifactRepository(session, scoped.scope(user="lead"), store)
    with pytest.raises(SeparationOfDutiesViolation):
        repo.approve(artifact_id)


def test_policy_does_not_confer_approval_authority(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    """The worker still cannot sign off, however permissive the policy.

    Self-approval removes the independence objection. It is not a permission, and
    treating it as one would turn a convenience setting into privilege escalation.
    Since ADR 0019 every person holds the sign-off permission, so the context that
    exercises this boundary is the worker's: it can write the artifact and cannot
    accept it (decision 6).
    """
    _enable(scoped)
    scope = scoped.scope(user="lead")
    run_id = WorkflowRepository(session, scope).create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key="policy-no-authority",
    )
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None and work.run_id == run_id
    worker = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    assert worker.self_approval.allowed is True
    assert not worker.has(Permission.SIGN_OFF_DELIVERABLE)

    repo = ArtifactRepository(session, worker, store)
    artifact, _ = repo.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"draft": True},
    )
    with pytest.raises(ScopeDenied) as exc:
        repo.approve(artifact.artifact_id)
    assert exc.value.reason == "insufficient_role"


def test_independent_sign_off_still_works_normally(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    """A second person accepting the work is still recorded as independent.

    ADR 0019 removed the requirement, not the record: ``self_approved`` is False
    when the approver is not the producer, whatever the policy allowed.
    """
    artifact_id = _authored_artifact(session, scoped, store, project)
    reviewer = ArtifactRepository(session, scoped.scope(user="reviewer"), store)
    assert reviewer.approve(artifact_id).is_approved is True

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.self_approved is False
    assert record.self_approval_allowed is True
    assert record.self_approval_source == SelfApprovalSource.DEFAULT.value


def test_a_self_approved_sign_off_is_fully_reconstructible(
    session: Session, scoped: Any, store: Any, project: Any
) -> None:
    """The audit requirement, stated as an assertion.

    Producer, approver, whether it was self-approved, the effective policy, where
    that policy came from, the exact artifact and revision, the timestamp, the
    decision and the basis -- all of it, from one row, years later, without
    re-resolving a configuration that has since changed.
    """
    artifact_id = _authored_artifact(session, scoped, store, project)
    _enable(scoped, study_id=scoped.studies["primary"].study_id)
    session.flush()

    scope = scoped.scope(user="lead")
    ArtifactRepository(session, scope, store).approve(artifact_id, note="sole author on call")

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.producer_user_id == scoped.users["lead"]
    assert record.approver_user_id == scoped.users["lead"]
    assert record.self_approved is True
    assert record.self_approval_allowed is True
    assert record.self_approval_source == SelfApprovalSource.STUDY.value
    assert (record.subject_type, record.subject_id) == ("artifact", artifact_id)
    assert (record.project_id, record.project_revision) == (project.project_id, 1)
    assert record.artifact_type == "CLIENT_REPORT"
    assert record.decision == "APPROVED"
    assert record.comment == "sole author on call"
    assert record.created_at is not None
    assert record.study_id == scope.study_id
    assert record.client_id == scope.client_id


# --------------------------------------------------------------------------- #
# Gate decisions under policy
# --------------------------------------------------------------------------- #


@pytest.fixture
def gate(session: Session, scoped: Any, project: Any) -> tuple[WorkflowRepository, str]:
    """A pending approval gate opened by the lead who produced the work."""
    repo = WorkflowRepository(session, scoped.scope(user="lead"))
    run_id = repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=PIPELINE,
        idempotency_key=f"{project.project_id}:rev1:approval",
    )
    claimed = repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = repo.open_gate(
        step_id=claimed.step_id, question="Approve this report?", options=["proceed"]
    )
    assert run_id
    return repo, gate_id


def test_gate_self_decision_is_allowed_by_default(
    session: Session, gate: tuple[WorkflowRepository, str]
) -> None:
    """ADR 0019: the person who opened the work may decide it, and it is recorded."""
    repo, gate_id = gate
    assert repo.decide_gate(gate_id, option="proceed").value == "RUNNABLE"

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.self_approved is True
    assert record.self_approval_allowed is True
    assert record.self_approval_source == SelfApprovalSource.DEFAULT.value


def test_gate_self_decision_is_refused_where_the_policy_is_off(
    session: Session, scoped: Any, gate: tuple[WorkflowRepository, str]
) -> None:
    """An explicit False (here on the study) still demands another person."""
    _, gate_id = gate
    _disable(scoped, study_id=scoped.studies["primary"].study_id)
    session.flush()

    # A fresh repository, because the policy is resolved when scope is issued.
    repo = WorkflowRepository(session, scoped.scope(user="lead"))
    with pytest.raises(SeparationOfDutiesViolation):
        repo.decide_gate(gate_id, option="proceed")


def test_gate_self_decision_is_allowed_once_policy_enables_it(
    session: Session, scoped: Any, gate: tuple[WorkflowRepository, str]
) -> None:
    _, gate_id = gate
    _enable(scoped, study_id=scoped.studies["primary"].study_id)
    session.flush()

    # A fresh repository, because the policy is resolved when scope is issued.
    repo = WorkflowRepository(session, scoped.scope(user="lead"))
    assert repo.decide_gate(gate_id, option="proceed", note="urgent delivery").value == "RUNNABLE"

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert (record.subject_type, record.subject_id) == ("gate", gate_id)
    assert record.gate_type == "approval"
    assert record.self_approved is True
    assert record.self_approval_allowed is True
    assert record.self_approval_source == SelfApprovalSource.STUDY.value
    assert record.decision == "proceed"
    assert record.comment == "urgent delivery"
    assert record.producer_user_id == record.approver_user_id == scoped.users["lead"]
    assert record.run_id and record.step_id


def test_an_independent_gate_decision_is_recorded_as_such(
    session: Session, scoped: Any, gate: tuple[WorkflowRepository, str]
) -> None:
    _, gate_id = gate
    reviewer = WorkflowRepository(session, scoped.scope(user="reviewer"))
    reviewer.decide_gate(gate_id, option="proceed")

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.self_approved is False
    assert record.approver_user_id == scoped.users["reviewer"]
    assert record.producer_user_id == scoped.users["lead"]
