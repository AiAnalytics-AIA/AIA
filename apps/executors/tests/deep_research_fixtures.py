"""Shared fictional recorded exchanges for Deep Research executor proofs."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)
from aia_executors.ai_runtime import AIRuntimeSettings, build_gateway
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research_recorded import recorded_runtime

FIXTURES = Path(__file__).parent / "fixtures" / "deep_research"
WEB = FIXTURES / "web.json"
ANSWERS: dict[str, Any] = json.loads((FIXTURES / "agents.json").read_text(encoding="utf-8"))

Q1 = "Jak roste trh rostlinných nápojů v Česku?"
Q2 = "Proč lidé přecházejí na rostlinné nápoje?"
OATS, ALMOND, SOY = "Ovesný nápoj", "Mandlový nápoj", "Sójový nápoj"

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje v Česku",
    "goal": "Porozumět trhu rostlinných nápojů před uvedením nového nápoje.",
    "decision_use": "Rozhodnutí o uvedení produktu.",
    "briefing": "Klient zvažuje nový nápoj pro dojíždějící.",
    "research_plan": {"research_questions": [Q1, Q2]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jaký podíl domácností kupuje rostlinné nápoje?",
                    "kategorie": ["Ano", "Ne"],
                }
            ],
        },
        {
            "type": "object_battery",
            "objects": [OATS, ALMOND],
            "object_question": "Jak hodnotíte {object}?",
        },
    ],
}
#: The second pass: one tracked object more, nothing else changed.
DESIGN_2: dict[str, Any] = {
    **DESIGN,
    "sections": [
        DESIGN["sections"][0],
        {**DESIGN["sections"][1], "objects": [OATS, ALMOND, SOY]},
    ],
}

FACT = "Ovesný nápoj tvořil v roce 2025 polovinu prodejů rostlinných nápojů v síti klienta."
PLAN_A = "Interní plán: uvedení ovesného nápoje v květnu 2027 za 39 Kč."


#: What a thinking agent reasoned: it must never be stored anywhere.
REASONING = "Úvaha agenta, která se nikam neukládá."


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


@dataclass
class RecordedAgents:
    """One recorded answer per agent, chosen by what the agent was shown.

    ``lose`` names roles whose next request gets no answer (the delivery unknown).
    ``in_text`` names roles whose next answer comes as text, not through the tool.
    ``thinking`` puts a reasoning block before every answer, as Claude does with
    extended thinking on.
    """

    answers: dict[str, Any]
    requests: list[HttpRequest] = field(default_factory=list)
    lose: set[str] = field(default_factory=set)
    in_text: set[str] = field(default_factory=set)
    thinking: bool = False

    def roles(self) -> Counter[str]:
        return Counter(self._role(r) for r in self.requests)

    @staticmethod
    def _role(request: HttpRequest) -> str:
        name = str(request.body["toolConfig"]["tools"][0]["toolSpec"]["name"])
        return name.removeprefix("aia_deep_research_")

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        role = self._role(request)
        if role in self.lose:
            self.lose.discard(role)
            raise TransportFailure("lost response", delivery=Delivery.UNKNOWN)
        payload = json.loads(request.body["messages"][0]["content"][0]["text"])
        answer = getattr(self, f"_{role}")(payload)
        name = request.body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        content: list[dict[str, Any]] = []
        if self.thinking:
            content.append(
                {"reasoningContent": {"reasoningText": {"text": REASONING, "signature": "c2ln"}}}
            )
        if role in self.in_text:
            self.in_text.discard(role)
            content.append({"text": json.dumps(answer, ensure_ascii=False)})
        else:
            content.append({"toolUse": {"toolUseId": "t", "name": name, "input": answer}})
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"rec-{role}-{len(self.requests)}"},
            body={
                "output": {"message": {"role": "assistant", "content": content}},
                "stopReason": "tool_use" if "toolUse" in content[-1] else "end_turn",
                "usage": {"inputTokens": 1000, "outputTokens": 200, "totalTokens": 1200},
            },
        )

    def _planner(self, payload: dict[str, Any]) -> dict[str, Any]:
        plans = self.answers["planner"]
        return {
            "tracks": [
                {
                    "track_id": t["track_id"],
                    "sub_questions": plans.get(t["subject"], {}).get("sub_questions", []),
                    "queries": plans.get(t["subject"], {}).get("queries", [t["subject"]]),
                }
                for t in payload["tracks"]
            ],
            "notes": "",
        }

    def _web_investigator(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = [
            {"source_id": s["source_id"], **e}
            for s in payload["sources"]
            for e in self.answers["web"].get(s["url"], [])
        ]
        return {"evidence": evidence, "gaps": []}

    def _internal_investigator(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = [
            {"source_id": s["source_id"], **e}
            for s in payload["sources"]
            for e in self.answers["internal"].get(s["title"], [])
        ]
        return {"evidence": evidence, "gaps": []}

    def _verifier(self, payload: dict[str, Any]) -> dict[str, Any]:
        overrides = self.answers["verifier"]
        return {
            "verdicts": [
                {
                    "evidence_id": i["evidence_id"],
                    "verdict": overrides.get(i["claim"], "supported"),
                    "reason": "posouzeno podle citace",
                }
                for i in payload["items"]
            ]
        }

    def _synthesizer(self, payload: dict[str, Any]) -> dict[str, Any]:
        by_subject: dict[str, list[dict[str, Any]]] = {}
        for e in payload["evidence"]:
            by_subject.setdefault(e["subject_key"], []).append(e)
        first = payload["evidence"][0]
        findings = [
            {"subject_key": k, "text": v[0]["claim"], "evidence_ids": [v[0]["evidence_id"]]}
            for k, v in by_subject.items()
        ]
        findings += [
            # A number no cited quote carries, and a citation of nothing accepted.
            {
                "subject_key": first["subject_key"],
                "text": "Trh do roku 2030 vzroste o 99 %.",
                "evidence_ids": [first["evidence_id"]],
            },
            {
                "subject_key": first["subject_key"],
                "text": "Tvrzení bez přijatého důkazu.",
                "evidence_ids": ["EV-0000000000000000"],
            },
        ]
        return {
            "summary": first["claim"],
            "findings": findings,
            "gaps": [s["text"] for s in payload["subjects"] if s["subject_key"] not in by_subject],
            "limitations": ["Externí kontext, nikoli výsledky panelu."],
        }


def ai_settings(
    fictional: str, *, approved_for: str, contents: tuple[dict[str, Any], ...] = ()
) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env(
        {
            "AIA_ENV": "test",
            "AIA_AI_RUNTIME_ENABLED": "true",
            "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
            "AIA_BEDROCK_REGION": "eu-central-1",
            "AIA_BEDROCK_MODEL_ID": "eu.test-research-v1:0",
            "AIA_AI_POLICY_VERSION": "test-deep-research-v1",
            "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
            "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
            "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
            "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
            "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
            "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
            "AIA_AI_ROUTE_APPROVED_FOR": approved_for,
            "AIA_AI_ROUTE_RETENTION_DAYS": "0",
            "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
            "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
            "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
            "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
            "AIA_AI_RESEARCH_RESERVATION_USD": "2",
            "AIA_AI_FICTIONAL_CLIENT_IDS": fictional,
            "AIA_AI_MATERIAL_CLASSIFICATIONS": "["
            + ",".join(
                MaterialApproval(
                    sha256=material_sha256(content),
                    data_class=DataClass.CLASS_C_INTERNAL
                    if fictional
                    else DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
                    provenance="generated wholly by this test; class explicitly set",
                    synthetic=bool(fictional),
                ).model_dump_json()
                for content in (DESIGN, DESIGN_2, *contents)
            )
            + "]",
        }
    )
    assert settings is not None
    return settings


#: The test route: Class C, and Class B so the internal channel runs on recorded exchanges.
TEST_ROUTE = "CLASS_C_INTERNAL,CLASS_B_DERIVED_CLIENT"
#: What develop's route is approved for.
DEVELOP_ROUTE = "CLASS_C_INTERNAL"


def recorded(
    world: Any,
    agents: RecordedAgents,
    *,
    fictional: bool = True,
    approved_for: str = TEST_ROUTE,
    policy: str | None = None,
    fixture: Path = WEB,
    thinking: int | None = None,
    contents: tuple[dict[str, Any], ...] = (),
) -> DeepResearchRuntime:
    settings = ai_settings(
        world.client_id if fictional else "", approved_for=approved_for, contents=contents
    )
    return recorded_runtime(
        gateway=build_gateway(settings, transport=agents, signer=Signer()),
        config=DeepResearchConfig(
            policy_version=policy or settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
            thinking_budget_tokens=thinking,
        ),
        fixture=fixture,
        env={"AIA_ENV": "test"},
    )
