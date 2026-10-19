""" "Ověřeno, přidat zdroj": a source a person checked becomes the client's knowledge, once.

Plan inline-decisions chunk 1. The run is found through the Study and its sealed bundle is the
only source of what is written; the bundle served here is aia_core's fictional fixture, read
through the run (``self.get`` first, as :meth:`DeepResearchRuns.bundle` does), so a run of
another Study is not found.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.bundle import EvidenceBundle
from fastapi.testclient import TestClient

API = "/api/v1"
BUNDLE = (
    Path(__file__).resolve().parents[3]
    / "packages/aia_core/tests/fixtures/deep_research_pre_step1/bundle.json"
)
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}
#: Two accepted findings of the fixture cite this snapshot; a third cites another.
SNAPSHOT = "SNP-63021d954c34213046156456"
URL = "https://stat.example/rostlinne-napoje-2025"
FINDING = "EV-496b5f047c6e4329"
SAME_SOURCE = "EV-e4d5edc882ae668d"
OTHER_SOURCE = "EV-2220bdb6eb026c2c"


@pytest.fixture
def sealed(monkeypatch: pytest.MonkeyPatch) -> EvidenceBundle:
    bundle = EvidenceBundle.model_validate_json(BUNDLE.read_bytes())

    def served(self: DeepResearchRuns, run_id: str, *, store: Any) -> EvidenceBundle:
        self.get(run_id)  # the run is found through the Study, or not at all
        return bundle

    monkeypatch.setattr(DeepResearchRuns, "bundle", served)
    return bundle


def _run(client: TestClient, world: Any) -> str:
    design = world.design(client, DESIGN, source_stage="brief")
    assert design.status_code == 201, design.text
    started = client.post(
        f"{API}/studies/{world.study_id()}/deep-research/runs",
        json={
            "design_revision_id": design.json()["revision_id"],
            "preset_name": "QUICK",
            "channels": ["WEB"],
        },
    )
    assert started.status_code == 201, started.text
    return str(started.json()["run_id"])


def _add(client: TestClient, world: Any, run_id: str, snapshot: str, evidence: str) -> Any:
    return client.post(
        f"{API}/studies/{world.study_id()}/deep-research/runs/{run_id}/sources/{snapshot}/knowledge",
        json={"evidence_id": evidence},
    )


def _sources(client: TestClient, world: Any, name: str = "primary") -> list[dict[str, Any]]:
    got = client.get(
        f"{API}/clients/{world.client_id(name)}/knowledge", params={"section": "sources"}
    )
    assert got.status_code == 200, got.text
    return list(got.json())


def test_a_checked_source_is_the_clients_knowledge_at_once_from_the_bundle_alone(
    researcher: TestClient, world: Any, sealed: EvidenceBundle
) -> None:
    run_id = _run(researcher, world)
    added = _add(researcher, world, run_id, SNAPSHOT, FINDING)
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["status"] == "added" and body["item_id"] and body["url"] == URL
    assert body["client_id"] == world.client_id()

    [item] = _sources(researcher, world)
    snapshot = next(s for s in sealed.snapshots if s.snapshot_id == SNAPSHOT)
    finding = next(a.evidence for a in sealed.accepted if a.evidence.evidence_id == FINDING)
    assert item["item_id"] == body["item_id"] and item["kind"] == "SOURCE"
    assert item["content"]["url"] == URL
    assert item["content"]["quote"] == finding.quote
    assert item["content"]["snapshot_id"] == SNAPSHOT
    assert item["content"]["text_sha256"] == snapshot.text_sha256

    history = researcher.get(
        f"{API}/clients/{world.client_id()}/knowledge/items/{item['item_id']}/revisions"
    )
    assert history.status_code == 200, history.text
    provenance = history.json()[0]["provenance"]
    assert provenance["deep_research_run_id"] == run_id
    assert provenance["evidence_id"] == FINDING
    assert provenance["verified_by_person"] is True
    assert provenance["authored"] == "person"
    assert provenance["added_by"] == world.users["researcher"]


def test_a_second_click_or_another_finding_on_the_same_url_writes_nothing(
    researcher: TestClient, world: Any, sealed: EvidenceBundle
) -> None:
    run_id = _run(researcher, world)
    first = _add(researcher, world, run_id, SNAPSHOT, FINDING).json()
    again = _add(researcher, world, run_id, SNAPSHOT, FINDING)
    same_url = _add(researcher, world, run_id, SNAPSHOT, SAME_SOURCE)
    for answer in (again, same_url):
        assert answer.status_code == 200, answer.text
        assert answer.json()["status"] == "exists"
        assert answer.json()["item_id"] == first["item_id"]
    assert len(_sources(researcher, world)) == 1


def test_a_source_not_in_the_runs_bundle_is_refused_and_the_browser_names_no_url(
    researcher: TestClient, world: Any, sealed: EvidenceBundle
) -> None:
    run_id = _run(researcher, world)
    absent = _add(researcher, world, run_id, f"SNP-{'0' * 24}", FINDING)
    assert absent.status_code == 404 and absent.json()["code"] == "source_not_in_run"
    # A finding that cites another source does not carry this one.
    elsewhere = _add(researcher, world, run_id, SNAPSHOT, OTHER_SOURCE)
    assert elsewhere.status_code == 404 and elsewhere.json()["code"] == "source_not_in_run"
    # Nothing the browser says becomes the item: a URL in the body is refused outright.
    forged = researcher.post(
        f"{API}/studies/{world.study_id()}/deep-research/runs/{run_id}/sources/{SNAPSHOT}/knowledge",
        json={"evidence_id": FINDING, "url": "https://elsewhere.example/"},
    )
    assert forged.status_code == 422
    assert _sources(researcher, world) == []


def test_another_studys_run_is_not_found_and_writes_nothing(
    researcher: TestClient, other_client_lead: TestClient, world: Any, sealed: EvidenceBundle
) -> None:
    run_id = _run(researcher, world)
    other = world.study_id("other_client")
    wrong = other_client_lead.post(
        f"{API}/studies/{other}/deep-research/runs/{run_id}/sources/{SNAPSHOT}/knowledge",
        json={"evidence_id": FINDING},
    )
    assert wrong.status_code == 404, wrong.text
    other_client = next(
        name
        for name, c in world.clients.items()
        if c.client_id == world.studies["other_client"].client_id
    )
    assert _sources(other_client_lead, world, other_client) == []
    assert _sources(researcher, world) == []


def test_a_study_with_self_approval_off_files_the_source_as_a_proposal(
    researcher: TestClient, owner: TestClient, world: Any, sealed: EvidenceBundle
) -> None:
    """The client allows self-approval; the Study turned it off. The Study's rule is the more
    specific one, so the click files a proposal another person decides, never knowledge."""
    configured = owner.put(
        f"{API}/self-approval", json={"allowed": False, "study_id": world.study_id()}
    )
    assert configured.status_code == 200, configured.text
    run_id = _run(researcher, world)
    added = _add(researcher, world, run_id, SNAPSHOT, FINDING)
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["status"] == "proposed" and body["item_id"] is None and body["proposal_id"]
    assert _sources(researcher, world) == []
    # The pending proposal holds the URL: a second click writes nothing more.
    again = _add(researcher, world, run_id, SNAPSHOT, FINDING)
    assert again.status_code == 200 and again.json()["status"] == "exists"
    assert again.json()["proposal_id"] == body["proposal_id"]
