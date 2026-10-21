"""The acceptance harness's worker composition and the recorded model wire it shares.

``aia_executors.acceptance_recorded`` is production's composition over recorded answers; it
must refuse to exist anywhere a recording could stand in for a model. ``RecordedModels`` must
say it is a recording in every answer, and refuse -- never invent -- a contract it holds no
recording of. The full path (the API and this worker as processes, a run answered end to end)
is ``tests/acceptance/test_acceptance_harness.py``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aia_core.infrastructure.model_adapters.transport import HttpRequest
from aia_executors import acceptance_recorded
from aia_executors.recorded_models import (
    ANALYSIS_TOOL,
    LEAD_REPLY,
    LEAD_TOOL,
    RECORDING,
    RESPONDENT_TOOL,
    RecordedModels,
    runtime_env,
)


def _request(tool: str, schema: dict[str, Any] | None = None, text: str = "{}") -> HttpRequest:
    return HttpRequest(
        method="POST",
        url="https://bedrock-runtime.eu-central-1.amazonaws.com/model/x/converse",
        headers={},
        body={
            "messages": [{"role": "user", "content": [{"text": text}]}],
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool,
                            "inputSchema": {"json": schema or {"type": "object"}},
                        }
                    }
                ]
            },
        },
    )


@pytest.mark.parametrize("environment", [None, "", "develop", "staging", "production"])
def test_the_composition_refuses_outside_local_and_test(environment: str | None) -> None:
    env = {} if environment is None else {"AIA_ENV": environment}
    with pytest.raises(RuntimeError, match="no deployment composes it"):
        acceptance_recorded.refuse_outside_tests(env)


@pytest.mark.parametrize("environment", ["local", "test"])
def test_the_composition_builds_in_local_and_test(environment: str) -> None:
    acceptance_recorded.refuse_outside_tests({"AIA_ENV": environment})


def test_the_composition_refuses_deep_research_it_has_no_recording_for() -> None:
    """Its search and fetch would be the live routes beside recorded models."""
    with pytest.raises(RuntimeError, match="AIA_DEEP_RESEARCH_ENABLED"):
        acceptance_recorded.refuse_outside_tests(
            {"AIA_ENV": "test", "AIA_DEEP_RESEARCH_ENABLED": "true"}
        )


def test_the_factory_is_production_composition_over_the_recorded_wire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every step kind the production registry has, with the AI runtime configured."""
    for key, value in runtime_env("CLI-fictional", []).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("AIA_AI_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("AIA_AI_ANALYSIS_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("AIA_AI_ANALYSIS_RESERVATION_USD", "1.0")
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    monkeypatch.delenv("AIA_DEEP_RESEARCH_ENABLED", raising=False)
    registry = acceptance_recorded.build_registry()
    assert {"research_fieldwork", "research_analysis", "research_lead_turn"} <= set(registry)
    monkeypatch.setenv("AIA_ENV", "production")
    with pytest.raises(RuntimeError, match="no deployment composes it"):
        acceptance_recorded.build_registry()


def test_every_recorded_answer_says_it_is_a_recording() -> None:
    models = RecordedModels()
    schema = {
        "type": "object",
        "properties": {
            "q1": {
                "type": "object",
                "properties": {"probabilities": {"type": "array", "minItems": 3}},
            }
        },
    }
    respondent = asyncio.run(models.send(_request(RESPONDENT_TOOL, schema), timeout_s=5))
    lead = asyncio.run(models.send(_request(LEAD_TOOL), timeout_s=5))
    for reply, kind in ((respondent, "respondent"), (lead, "lead")):
        assert reply.status == 200
        assert reply.headers["x-aia-recording"] == RECORDING
        assert reply.headers["x-amzn-requestid"].startswith(f"recorded-{kind}-")
    answer = respondent.body["output"]["message"]["content"][0]["toolUse"]["input"]
    assert answer == {"q1": {"probabilities": [0.6, 0.2, 0.2]}}
    said = lead.body["output"]["message"]["content"][0]["toolUse"]["input"]
    assert said == {"reply": LEAD_REPLY}
    assert not any(ch.isdigit() for ch in LEAD_REPLY), "the Lead's number guard has no context"
    assert len(models.requests) == 2 and models.asked == []


def test_a_contract_with_no_recording_is_refused_by_name_never_invented() -> None:
    """An answered 400 (Bedrock's ValidationException: permanent, never retried, not billed):
    the step fails naming the contract, and nothing is made up for it."""
    reply = asyncio.run(
        RecordedModels().send(_request("aia_research_build_questionnaire"), timeout_s=5)
    )
    assert reply.status == 400
    assert reply.headers["x-amzn-errortype"] == "ValidationException"
    assert reply.headers["x-aia-recording"] == RECORDING
    assert "aia_research_build_questionnaire" in reply.body["message"]


def test_the_analysis_answer_cites_the_evidence_the_turn_sent() -> None:
    payload = (
        '{"module": "executive", "research_questions": ["Proč?"], "evidence": '
        '[{"evidence_ref": "q1.mean", "metric": "mean", "value": 3.25, "unit": "points"}]}'
    )
    reply = asyncio.run(RecordedModels().send(_request(ANALYSIS_TOOL, text=payload), timeout_s=5))
    draft = reply.body["output"]["message"]["content"][0]["toolUse"]["input"]
    assert draft["numeric_claims"][0]["evidence_ref"] == "q1.mean"
    assert draft["numeric_claims"][0]["value"] == 3.25
    assert "3,25" in draft["summary"]
    assert reply.headers["x-amzn-requestid"].startswith("recorded-analysis-")
