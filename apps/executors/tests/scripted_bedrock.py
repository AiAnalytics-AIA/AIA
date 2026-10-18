"""A Bedrock Converse double, for runs whose analysis and AI fieldwork a model answers.

``ScriptedModels`` is an ``HttpTransport`` standing in for Bedrock Converse: it answers each
analysis turn with a draft built from the evidence the turn itself sends (or with the recorded
failure a test asks for), and each AI respondent block with fixed probabilities. Everything around
it is real: the gateway, its Bedrock adapter, the reservations and the ledger. Nothing leaves the
process and nothing is paid. Shared by the analysis executor suite and the product acceptance
suite; tests import this module, never each other.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)

PROFILE = "eu.example.analysis-model-v1:0"  # a test id; the real one is configuration
ANALYSIS_TOOL = "aia_analysis_module"


def runtime_env(
    fictional_client_id: str, contents: Iterable[Mapping[str, Any]], **overrides: str
) -> dict[str, str]:
    """The worker's AI runtime as configuration, for one fictional client: the switches the
    analysis and AI fieldwork need, test prices (not Bedrock's: the real entry is dated
    configuration, ADR 0010), and each design in ``contents`` classified as Class C material
    the test generated wholly. ``overrides`` replace any key."""
    env = {
        "AIA_ENV": "test",
        "AIA_AI_RUNTIME_ENABLED": "true",
        "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
        "AIA_BEDROCK_REGION": "eu-central-1",
        "AIA_BEDROCK_MODEL_ID": PROFILE,
        "AIA_AI_POLICY_VERSION": "aia-model-policy-test-1",
        # Test prices, not Bedrock's: the real entry is dated configuration (ADR 0010).
        "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
        "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
        "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
        "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
        "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
        "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
        "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
        "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
        # Today RESEARCH_REASONING is bound only with the design agents' switch; the
        # analysis switch and its binding are the activation work's (see the plan).
        "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
        "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
        "AIA_AI_RESEARCH_RESERVATION_USD": "2",
        "AIA_AI_FICTIONAL_CLIENT_IDS": fictional_client_id,
        "AIA_AI_MATERIAL_CLASSIFICATIONS": "["
        + ",".join(
            MaterialApproval(
                sha256=material_sha256(content),
                data_class=DataClass.CLASS_C_INTERNAL,
                provenance="generated wholly by this test",
            ).model_dump_json()
            for content in contents
        )
        + "]",
    }
    env.update(overrides)
    return env


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


# --------------------------------------------------------------------------- #
# the recorded model
# --------------------------------------------------------------------------- #


def _shown(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def grounded_draft(payload: Mapping[str, Any]) -> dict[str, Any]:
    """What a careful analyst returns: one cited number, written as the table gives it."""
    rows = payload["evidence"]
    row = next(
        (r for r in rows if ".pct." in r["evidence_ref"] or r["evidence_ref"].endswith(".mean")),
        rows[0],
    )
    shown = _shown(row["value"])
    return {
        "module": payload["module"],
        "summary": f"Podle fiktivních respondentů je odhad {shown}; jde o modelovaný údaj.",
        "research_question_answers": [
            {"question": q, "answer": f"Modelovaný odhad je {shown}.", "claim_ids": ["c1"]}
            for q in payload["research_questions"]
        ],
        "key_findings": [{"text": f"Modelovaný odhad: {shown}.", "claim_ids": ["c1"]}],
        "numeric_claims": [
            {
                "claim_id": "c1",
                "evidence_ref": row["evidence_ref"],
                "metric": row["metric"],
                "value": row["value"],
                "unit": row["unit"],
            }
        ],
    }


def invented_draft(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A draft whose number is in no evidence row: the gate refuses it every time."""
    return {
        "module": payload["module"],
        "summary": "Kávu pije 55 % fiktivních respondentů.",
        "research_question_answers": [
            {"question": q, "answer": "Nelze doložit.", "claim_ids": []}
            for q in payload["research_questions"]
        ],
        "key_findings": [],
        "numeric_claims": [],
    }


def _respondent(schema: Mapping[str, Any]) -> dict[str, Any]:
    def resolve(node: Mapping[str, Any]) -> Mapping[str, Any]:
        ref = node.get("$ref")
        return schema["$defs"][ref.rsplit("/", 1)[-1]] if isinstance(ref, str) else node

    out: dict[str, Any] = {}
    for item_id, node in schema["properties"].items():
        props = resolve(node)["properties"]
        if "probabilities" in props:
            k = int(props["probabilities"]["minItems"])
            out[item_id] = {"probabilities": [0.6] + [0.4 / (k - 1)] * (k - 1)}
        elif "selected" in props:
            out[item_id] = {"selected": [1]}
        else:
            out[item_id] = {"text": "Fiktivní odpověď."}
    return out


@dataclass
class ScriptedModels:
    """An ``HttpTransport`` for Bedrock Converse. Records every request it is sent.

    Analysis requests are counted per module: ``(module, n)`` is that module's n-th call.
    A repair turn sends the evidence, the last draft and the repair, not the history, so
    which *turn* a call answered is the executor's to record (``CallRecord``), not this
    double's to infer.
    """

    #: modules whose every draft cites a number no evidence row holds
    invent: set[str] = field(default_factory=set)
    #: (module, n) whose draft cites a number no evidence row holds
    invent_calls: set[tuple[str, int]] = field(default_factory=set)
    #: (module, n) answered with a draft that breaks the output contract
    off_contract: set[tuple[str, int]] = field(default_factory=set)
    #: (module, n) -> a recorded failure: an HttpResponse or a TransportFailure
    failures: dict[tuple[str, int], HttpResponse | TransportFailure] = field(default_factory=dict)
    #: called with (module, n) before an analysis call is answered
    hook: Callable[[str, int], None] | None = None
    requests: list[HttpRequest] = field(default_factory=list)
    asked: list[tuple[str, int]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def calls(self, module: str) -> list[int]:
        return [n for m, n in self.asked if m == module]

    def messages(self, module: str, n: int) -> list[str]:
        """The texts of the messages a module's n-th call sent."""
        request = self.requests[self._index[(module, n)]]
        return [m["content"][0]["text"] for m in request.body["messages"]]

    def __post_init__(self) -> None:
        self._index: dict[tuple[str, int], int] = {}

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]
        with self.lock:
            self.requests.append(request)
            number = len(self.requests)
            payload: dict[str, Any] = {}
            if tool["name"] == ANALYSIS_TOOL:
                payload = json.loads(request.body["messages"][0]["content"][0]["text"])
                key = (payload["module"], len(self.calls(payload["module"])) + 1)
                self.asked.append(key)
                self._index[key] = number - 1
        if tool["name"] == ANALYSIS_TOOL:
            if self.hook is not None:
                self.hook(*key)
            failure = self.failures.get(key)
            if isinstance(failure, TransportFailure):
                raise failure
            if isinstance(failure, HttpResponse):
                return failure
            if key in self.off_contract:
                answer: dict[str, Any] = {**grounded_draft(payload), "confidence": "high"}
            elif payload["module"] in self.invent or key in self.invent_calls:
                answer = invented_draft(payload)
            else:
                answer = grounded_draft(payload)
            usage = {"inputTokens": 2400, "outputTokens": 380, "totalTokens": 2780}
        else:
            answer = _respondent(tool["inputSchema"]["json"])
            usage = {"inputTokens": 900, "outputTokens": 120, "totalTokens": 1020}
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{number:05d}"},
            body={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"t{number}",
                                    "name": tool["name"],
                                    "input": answer,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": usage,
                "metrics": {"latencyMs": 900},
            },
        )
