"""Runnable is not answerable, over HTTP (plan research-integrity-report chunk 1).

Readiness answers ``ready`` (the design can run) beside ``answerability`` (it can answer what
it asks). With the deployment's gate on, a start over a design that cannot needs the person's
acknowledgement of exactly the gaps readiness named; the run then says so. Fictional designs.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from aia_api.config import Settings

API = "/api/v1"
RQS = [
    "Jak klienti důvěřují digitálnímu běžnému účtu?",
    "Co klienty odrazuje od založení účtu online?",
    "Jak se liší důvěra mezi věkovými skupinami?",
    "Které značky klienti považují za nejbezpečnější?",
]
UNLINKED = {
    "title": "Důvěra v digitální účet (fiktivní)",
    "goal": "Pochopit důvěru v digitální běžný účet.",
    "n": 200,
    "research_plan": {"research_questions": RQS},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Nakolik důvěřujete mobilní bance?",
                    "typ": "skala",
                    "skala": [1, 5],
                },
            ],
        }
    ],
}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"research_answerability_gate": True})


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _revision(c: TestClient, world: Any, content: dict[str, Any] = UNLINKED) -> str:
    made = c.post(
        f"{_study(world)}/design/revisions", json={"content": content, "source_stage": "run"}
    )
    assert made.status_code in (200, 201), made.text
    return str(made.json()["revision_id"])


def _readiness(c: TestClient, world: Any, revision: str) -> dict[str, Any]:
    got = c.get(f"{_study(world)}/research/readiness?design_revision_id={revision}")
    assert got.status_code == 200, got.text
    return dict(got.json())


def test_readiness_separates_runnable_from_answerable(researcher: TestClient, world: Any) -> None:
    body = _readiness(researcher, world, _revision(researcher, world))
    assert body["ready"] is True
    answer = body["answerability"]
    assert answer["capable"] is False and len(answer["digest"]) == 64
    assert answer["acknowledgement_required"] is True  # the gate is on in this module
    assert [g["research_question"] for g in answer["gaps"]] == RQS
    assert {tuple(g["reasons"]) for g in answer["gaps"]} == {("unlinked_design",)}


def test_a_start_without_an_acknowledgement_is_refused_with_the_gaps(
    researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    refused = researcher.post(
        f"{_study(world)}/research/runs", json={"design_revision_id": revision}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "research_questions_unanswerable"
    assert refused.json()["details"]["acknowledgement_required"] is True
    assert len(refused.json()["details"]["gaps"]) == 4
    assert researcher.get(f"{_study(world)}/research/runs").json()["items"] == []


def test_an_acknowledged_start_carries_the_decision_on_the_run(
    researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    digest = _readiness(researcher, world, revision)["answerability"]["digest"]
    started = researcher.post(
        f"{_study(world)}/research/runs",
        json={
            "design_revision_id": revision,
            "acknowledge_research_questions": {
                "digest": digest,
                "reason": "Fiktivní test postupu, závěry nečteme.",
            },
        },
    )
    assert started.status_code == 201, started.text
    recorded = started.json()["answerability"]
    assert recorded["capable"] is False and recorded["digest"] == digest
    assert recorded["acknowledgement"]["reason"] == "Fiktivní test postupu, závěry nečteme."


def test_an_acknowledgement_of_a_different_digest_or_without_a_reason_is_not_one(
    researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    url = f"{_study(world)}/research/runs"
    wrong = researcher.post(
        url,
        json={
            "design_revision_id": revision,
            "acknowledge_research_questions": {"digest": "0" * 64, "reason": "Jiné mezery."},
        },
    )
    assert wrong.status_code == 409 and wrong.json()["code"] == "research_questions_unanswerable"
    digest = _readiness(researcher, world, revision)["answerability"]["digest"]
    short = researcher.post(
        url,
        json={
            "design_revision_id": revision,
            "acknowledge_research_questions": {"digest": digest, "reason": "ok"},
        },
    )
    assert short.status_code == 422


def test_readiness_carries_the_decided_verdict_and_a_digest_of_its_own_revision(
    researcher: TestClient, world: Any
) -> None:
    """Review 3: the readiness route's wiring (the decided trace, the coverage check beside a
    gap, the revision in the digest) had no test; reverting any of it left every test green."""
    linked = {
        **UNLINKED,
        "research_plan": {"research_questions": RQS[:2]},
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Nakolik důvěřujete mobilní bance?",
                        "typ": "skala",
                        "skala": [1, 5],
                        "research_questions": [RQS[0]],
                    },
                    {
                        "id": "q2",
                        "text": "Co vás odrazuje?",
                        "typ": "otevrena",
                        "research_questions": [RQS[1]],
                    },
                ],
            }
        ],
    }
    first = _revision(researcher, world, linked)
    body = _readiness(researcher, world, first)
    coverage = next(c for c in body["checks"] if c["id"] == "research_question_coverage")
    assert coverage["status"] == "WARN" and RQS[1] in coverage["message"]
    traced = {q["text"]: q["verdict"] for q in body["research_trace"]["questions"]}
    assert traced[RQS[1]] == "UNANSWERABLE"  # the trace alone says AT_RISK (an open question)
    (gap,) = body["answerability"]["gaps"]
    assert gap["research_question"] == RQS[1] and gap["verdict"] == "UNANSWERABLE"

    second = _revision(researcher, world, {**linked, "title": "Jiná revize (fiktivní)"})
    other = _readiness(researcher, world, second)["answerability"]
    assert other["gaps"] == body["answerability"]["gaps"]
    assert other["digest"] != body["answerability"]["digest"]
    refused = researcher.post(
        f"{_study(world)}/research/runs",
        json={
            "design_revision_id": second,
            "acknowledge_research_questions": {
                "digest": body["answerability"]["digest"],
                "reason": "Potvrzeno pro jinou revizi návrhu.",
            },
        },
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "research_questions_unanswerable"
