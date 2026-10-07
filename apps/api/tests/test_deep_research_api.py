"""The native Deep Research route uses the Study's scope and a durable six-step run."""

from __future__ import annotations

from typing import Any

from aia_core.application.deep_research import DeepResearchRuns, run_spec_metadata
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.deep_research.contracts import Channel
from aia_core.domain.deep_research.integration import (
    RUN_SPEC_CONTRACT,
    ArtifactPin,
    DeepResearchPurpose,
    DeepResearchRunSpec,
    DesignLineage,
    InterpretationLineage,
    PurposeSource,
    SociomapTarget,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import WorkflowRunRow
from fastapi.testclient import TestClient

API = "/api/v1"
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}


def _url(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}/deep-research/runs"


def _revision(client: TestClient, world: Any) -> str:
    response = client.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": DESIGN, "source_stage": "brief"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["revision_id"])


def test_start_is_scoped_idempotent_and_does_not_publish_before_worker(
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """ADR 0019: every member holds the Researcher role, so the "viewer" label reads it all.

    A member who was never granted the study, and another client's lead, read it too. What
    still bounds a run is its own study: under another study's path it does not exist.
    """
    revision = _revision(researcher, world)
    payload = {"design_revision_id": revision, "preset_name": "QUICK", "channels": ["WEB"]}
    started = researcher.post(_url(world), json=payload)
    assert started.status_code == 201, started.text
    job = started.json()
    assert [step["node_key"] for step in job["steps"]] == [
        "plan",
        "investigate",
        "merge",
        "verify",
        "synthesize",
        "publish",
    ]
    assert job["channels"] == ["WEB"] and job["preset"] == "QUICK"
    assert researcher.post(_url(world), json=payload).status_code == 200
    assert len(researcher.get(_url(world)).json()) == 1
    run_url = f"{_url(world)}/{job['run_id']}"
    assert viewer.get(run_url).status_code == 200
    assert researcher.get(f"{run_url}/bundle").status_code == 409
    assert viewer.get(f"{run_url}/bundle").status_code == 409
    assert viewer.get(f"{run_url}/events").status_code == 200
    events = researcher.get(f"{run_url}/events")
    assert events.status_code == 200, events.text
    wrong_study = f"{_url(world, 'other_client')}/{job['run_id']}"
    for path in (run_url, f"{run_url}/events"):
        assert outsider.get(path).status_code == 200, path
        assert other_client_lead.get(path).status_code == 200, path
    for member in (outsider, other_client_lead):
        assert member.get(f"{run_url}/bundle").status_code == 409  # not published yet
        for path in (wrong_study, f"{wrong_study}/bundle", f"{wrong_study}/events"):
            assert member.get(path).status_code == 404, path


def test_an_invalid_job_is_refused_before_enqueue_and_a_viewer_label_may_start(
    researcher: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    """ADR 0019: a start needs membership, not a role; the "viewer" label holds the one role."""
    revision = _revision(researcher, world)
    base = {"design_revision_id": revision, "preset_name": "QUICK"}
    assert outsider.get(_url(world)).status_code == 200  # a member with no grant reads the list
    for channels in ([], ["WEB", "WEB"], ["OTHER"]):
        assert researcher.post(_url(world), json={**base, "channels": channels}).status_code == 422
    assert researcher.post(_url(world), json={**base, "preset_name": "UNKNOWN"}).status_code == 422
    assert (
        researcher.post(_url(world), json={**base, "design_revision_id": "REV-0"}).status_code
        == 404
    )
    assert researcher.get(f"{_url(world)}/RUN-0").status_code == 404
    started = viewer.post(_url(world), json={**base, "channels": ["WEB"]})
    assert started.status_code == 201, started.text
    # A member who was never granted the study starts the same job: idempotent, so 200.
    again = outsider.post(_url(world), json={**base, "channels": ["WEB"]})
    assert again.status_code == 200 and again.json()["run_id"] == started.json()["run_id"]


def test_a_run_says_why_what_and_on_which_design_and_the_old_shape_still_starts(
    researcher: TestClient, world: Any
) -> None:
    """ADR 0021. The deployed client names no purpose: a new start through that shape is
    Design Research, recorded as the compatibility default; naming it is the same run."""
    revision = _revision(researcher, world)
    legacy_shape = {"design_revision_id": revision, "preset_name": "QUICK", "channels": ["WEB"]}
    started = researcher.post(_url(world), json=legacy_shape)
    assert started.status_code == 201, started.text
    job = started.json()
    assert job["integration_contract"] == "aia-deep-research-run-spec-1"
    assert job["purpose"] == "DESIGN_RESEARCH" and job["purpose_source"] == "LEGACY_DEFAULT"
    assert job["target"] == {"kind": "DESIGN_REVISION", "design_revision_id": revision}
    assert job["lineage"]["kind"] == "DESIGN"
    assert job["lineage"]["design_revision_id"] == revision
    assert len(job["lineage"]["design_content_sha256"]) == 64
    assert len(job["run_spec_fingerprint"]) == 64

    named = researcher.post(
        _url(world), json={**legacy_shape, "purpose": "DESIGN_RESEARCH", "title": "Kontext"}
    )
    assert named.status_code == 200 and named.json()["run_id"] == job["run_id"]

    # The result-side start is not this route's yet; nothing else is a purpose.
    for purpose in ("INTERPRETATION_RESEARCH", "ANYTHING"):
        refused = researcher.post(_url(world), json={**legacy_shape, "purpose": purpose})
        assert refused.status_code == 422, purpose

    run_url = f"{_url(world)}/{job['run_id']}"
    provenance = researcher.get(f"{run_url}/provenance")
    assert provenance.status_code == 409
    assert provenance.json()["code"] == "bundle_not_ready"


def test_an_interpretation_row_answers_interpretation_not_ready_and_starts_nothing(
    researcher: TestClient, world: Any, app: Any
) -> None:
    """ADR 0021 Step 1: Interpretation Research is frozen, never enqueued, until chunk 30.

    No route creates an interpretation run, so the row is written at the repository level
    (a historical or future row): its retry is 409 ``interpretation_not_ready`` and no run
    is created."""
    revision = _revision(researcher, world)
    started = researcher.post(
        _url(world),
        json={"design_revision_id": revision, "preset_name": "QUICK", "channels": ["WEB"]},
    ).json()
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(
                user_id=world.users["researcher"], organization_id=world.organization_id
            ),
            study_id=world.study_id(),
        )
        runs = DeepResearchRuns(session, scope)
        request = runs.freeze(
            design_revision_id=revision, preset_name="QUICK", channels=(Channel.WEB,)
        )
        design = DesignLineage(
            kind="DESIGN",
            design_revision_id=revision,
            design_revision=request.design_revision,
            design_content_sha256="a" * 64,
        )
        spec = DeepResearchRunSpec(
            contract_version=RUN_SPEC_CONTRACT,
            purpose=DeepResearchPurpose.INTERPRETATION_RESEARCH,
            target=SociomapTarget(
                kind="SOCIOMAP",
                research_run_id="RUN-00000000000000a1",
                sociomap_artifact_id="ART-00000000000000a4",
                battery_id="napoje",
            ),
            lineage=InterpretationLineage(
                kind="INTERPRETATION",
                research_run_id="RUN-00000000000000a1",
                design=design,
                artifacts=(
                    ArtifactPin(
                        node_key="sociomap",
                        artifact_id="ART-00000000000000a4",
                        artifact_type="research_sociomap",
                        sha256="b" * 64,
                    ),
                ),
            ),
            engine_request=request,
        )
        row = session.get(WorkflowRunRow, started["run_id"])
        assert row is not None
        row.metadata_json = {
            **row.metadata_json,
            **run_spec_metadata(spec, purpose_source=PurposeSource.EXPLICIT),
        }
        session.commit()
    run_url = f"{_url(world)}/{started['run_id']}"
    shown = researcher.get(run_url).json()
    assert shown["purpose"] == "INTERPRETATION_RESEARCH" and shown["target"]["kind"] == "SOCIOMAP"
    assert researcher.post(f"{run_url}/cancel").status_code == 200
    retried = researcher.post(f"{run_url}/retry")
    assert retried.status_code == 409 and retried.json()["code"] == "interpretation_not_ready"
    assert [r["run_id"] for r in researcher.get(_url(world)).json()] == [started["run_id"]]


def test_a_design_proposal_waits_for_the_run_and_its_accept_is_validated(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Chunk 29's routes: nothing to propose before the run completes; the accept's body is
    checked before anything is read; under another study's path the run does not exist."""
    revision = _revision(researcher, world)
    started = researcher.post(
        _url(world), json={"design_revision_id": revision, "preset_name": "QUICK"}
    )
    assert started.status_code == 201, started.text
    run_url = f"{_url(world)}/{started.json()['run_id']}"
    proposal = researcher.get(f"{run_url}/design-proposal")
    assert proposal.status_code == 409 and proposal.json()["code"] == ("proposal_not_ready")
    accept = {"item_ids": ["DRP-" + "0" * 24], "expected_revision_id": revision}
    refused = researcher.post(f"{run_url}/design-proposal/accept", json=accept)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "proposal_not_ready"
    for body in (
        {**accept, "item_ids": []},
        {**accept, "item_ids": ["not-an-item"]},
        {**accept, "expected_revision_id": "latest"},
        {**accept, "extra": True},
    ):
        assert researcher.post(f"{run_url}/design-proposal/accept", json=body).status_code == 422
    wrong_study = f"{_url(world, 'other_client')}/{started.json()['run_id']}"
    assert other_client_lead.get(f"{wrong_study}/design-proposal").status_code == 404
    assert (
        other_client_lead.post(f"{wrong_study}/design-proposal/accept", json=accept).status_code
        == 404
    )
    # Nothing was written: the design is still the one the run was started on.
    revisions = researcher.get(f"{API}/studies/{world.study_id()}/design/revisions")
    assert [r["revision_id"] for r in revisions.json()["items"]] == [revision]
