"""Recorded model answers: a Bedrock Converse double the suites and the acceptance harness share.

:class:`RecordedModels` is an ``HttpTransport`` standing in for Bedrock Converse **behind** the
gateway: everything around it is real -- ``GovernedModelGateway``, its Bedrock adapter, the
reservations, the journal and the ledger. It never opens a socket and nothing it answers is
paid. It answers by the output contract a request names (the tool, ``aia_<agent id>``):

* ``aia_research_respondent`` -- one respondent block: fixed probabilities over each item's
  options, built from the block's own schema;
* ``aia_analysis_module`` -- an analysis module's draft citing one number exactly as the
  evidence the turn sends gives it (or, when a test asks, a draft citing a number no evidence
  row holds, an off-contract draft, or a recorded provider failure);
* ``aia_research_lead`` -- one Research Lead turn: a reply with no number in it and no edit;
* ``aia_research_<action>`` -- each of the eight design workers (``research_agents``
  ``ResearchAction``): one fixed answer that keeps its closed contract, with no number in its
  text, so a Lead card or a stage's job runs end to end at no cost (plan
  ``artifact-chain-to-draft-report`` CHN7).

Every response states that it is a recording: its provider request id is ``recorded-<kind>-<n>``
(the id the ledger and the dataset's provenance keep for each call) and it carries
``x-aia-recording: aia-recorded-models-1``. A request for any other contract is answered with
the provider's validation refusal naming it -- an answered, unbilled 400, so the call fails by
name and nothing is invented for a contract this double has no recording of.

Not yet recorded here (``mvp-acceptance-harness`` chunk 4, listed in the plan): the
client-source extraction contract (``aia_knowledge_source_proposals``) and the five Deep
Research agents; the suites that drive
those keep their own doubles until they move here.

Only test compositions use this module: the acceptance harness's worker composition
(:mod:`aia_executors.acceptance_recorded`, local and test only) and the executor suites. No
production composition imports it and no deployment names it (``make layer_check``).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)

__all__ = [
    "ANALYSIS_TOOL",
    "DESIGN_ANSWERS",
    "LEAD_REPLY",
    "LEAD_TOOL",
    "PROFILE",
    "RECORDING",
    "RESPONDENT_TOOL",
    "RecordedModels",
    "RecordedSigner",
    "grounded_draft",
    "invented_draft",
    "runtime_env",
]

#: What every recorded answer says it is.
RECORDING: Final = "aia-recorded-models-1"
PROFILE: Final = "eu.example.analysis-model-v1:0"  # a test id; the real one is configuration
ANALYSIS_TOOL: Final = "aia_analysis_module"
RESPONDENT_TOOL: Final = "aia_research_respondent"
LEAD_TOOL: Final = "aia_research_lead"
#: The Lead's recorded reply: no number, so the number guard has nothing to refuse.
LEAD_REPLY: Final = "Zaznamenaná odpověď vedoucího výzkumu: návrh si přečtu a navrhnu další krok."

_FICTIONAL: Final = "Fiktivní záznam: "
_ADVICE: Final[Mapping[str, Any]] = {
    "answer": _FICTIONAL + "návrh je srozumitelný; doporučuji projít výzkumné otázky.",
    "source_ids": [],
    "followup_questions": ["Která výzkumná otázka je nejdůležitější?"],
    "limitations": ["Zaznamenaná odpověď, ne model."],
}
_SCALE_QUESTION: Final[Mapping[str, Any]] = {
    "text": "Jak často pijete kávu?",
    "typ": "skala",
    "kategorie": [],
    "skala": [1, 5],
    "popisky_skaly": ["Nikdy", "Denně"],
    "povolit_nevim": True,
    "max_slov": 50,
    "topics": [],
    "research_questions": [],
}
_QUESTIONNAIRE: Final[Mapping[str, Any]] = {
    "message": _FICTIONAL + "jeden oddíl s jednou škálovou otázkou.",
    "sections": [
        {
            "type": "questions",
            "title": "Návyky",
            "purpose": "Fiktivní oddíl ze záznamu.",
            "questions": [_SCALE_QUESTION],
        }
    ],
    "warnings": [],
    "comparisons": [],
}
#: Each design worker's recorded answer, by its output tool (``aia_research_<action>``).
DESIGN_ANSWERS: Final[Mapping[str, Mapping[str, Any]]] = {
    "aia_research_analyze_brief": {
        "title": "Fiktivní ranní nápoj",
        "problem_summary": _FICTIONAL + "zjistit, co lidé ráno pijí.",
        "decision_use": "Volba sortimentu ranních nápojů.",
        "objectives": ["Popsat ranní nápojové návyky."],
        "research_questions": ["Jak často lidé ráno pijí kávu?"],
        "hypotheses": [],
        "recommended_topics": [],
        "tracked_sets": [],
        "non_object_measures": [],
        "questions_for_user": [],
        "complexity": "short",
        "method_reason": "Krátký kvantitativní dotazník.",
        "ready_for_questionnaire": True,
    },
    "aia_research_build_questionnaire": _QUESTIONNAIRE,
    "aia_research_optimize_questionnaire": _QUESTIONNAIRE,
    "aia_research_propose_audience": {
        "description": _FICTIONAL + "dospělí, kteří ráno pijí teplý nápoj.",
        "inclusion_criteria": ["Dospělí"],
        "exclusion_criteria": [],
        "questions_for_user": [],
        "limitations": ["Zaznamenaná odpověď, ne model."],
    },
    "aia_research_suggest_dimensions": {
        "new_dimension_suggestions": [
            {
                "label": "Ranní rutina",
                "why": _FICTIONAL + "odlišuje skupiny pijáků.",
                "evidence_needed": ["Otázka na ranní rutinu"],
                "suggested_predictors": [],
                "source_strategy": "Odvodit z dotazníku.",
            }
        ],
        "limitations": [],
    },
    "aia_research_critique_design": _ADVICE,
    "aia_research_design_copilot": _ADVICE,
    "aia_research_answer_memory": _ADVICE,
}

#: The usage each kind of call reports, as Converse reports it.
_USAGE: Final[Mapping[str, Mapping[str, int]]] = {
    ANALYSIS_TOOL: {"inputTokens": 2400, "outputTokens": 380, "totalTokens": 2780},
    RESPONDENT_TOOL: {"inputTokens": 900, "outputTokens": 120, "totalTokens": 1020},
    LEAD_TOOL: {"inputTokens": 1800, "outputTokens": 90, "totalTokens": 1890},
    **{
        tool: {"inputTokens": 3000, "outputTokens": 600, "totalTokens": 3600}
        for tool in DESIGN_ANSWERS
    },
}
_KIND: Final[Mapping[str, str]] = {
    ANALYSIS_TOOL: "analysis",
    RESPONDENT_TOOL: "respondent",
    LEAD_TOOL: "lead",
    **{tool: tool.removeprefix("aia_research_") for tool in DESIGN_ANSWERS},
}


def runtime_env(
    fictional_client_id: str, contents: Iterable[Mapping[str, Any]], **overrides: str
) -> dict[str, str]:
    """The worker's AI runtime as configuration, for one fictional client: the switches the
    analysis and AI fieldwork need, test prices (not Bedrock's: the real entry is dated
    configuration, ADR 0010), and each design in ``contents`` classified as Class C material
    the test generated wholly; a design is Class B by the owner's rule (2026-10-19) all the
    same, so the route carries B. ``overrides`` replace any key."""
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
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL,CLASS_B_DERIVED_CLIENT",
        # Class B, like A, needs the provider's retention stated.
        "AIA_AI_ROUTE_RETENTION_DAYS": "0",
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


class RecordedSigner:
    """Signs nothing: a recorded exchange needs no credential, and none is read."""

    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 recorded"}


# --------------------------------------------------------------------------- #
# the recorded answers
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


def _no_recording(tool: str, number: int) -> HttpResponse:
    """The provider's own refusal of a request it cannot serve: answered, never billed."""
    return HttpResponse(
        status=400,
        headers={
            "x-amzn-requestid": f"recorded-none-{number:05d}",
            "x-amzn-errortype": "ValidationException",
            "x-aia-recording": RECORDING,
        },
        body={"message": f"{RECORDING} holds no recording for the output contract {tool!r}"},
    )


@dataclass
class RecordedModels:
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
    #: modules answered with a grounded draft that states no key finding (MVPQ-04)
    no_findings: set[str] = field(default_factory=set)
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
        name = str(tool["name"])
        with self.lock:
            self.requests.append(request)
            number = len(self.requests)
            payload: dict[str, Any] = {}
            if name == ANALYSIS_TOOL:
                payload = json.loads(request.body["messages"][0]["content"][0]["text"])
                key = (payload["module"], len(self.calls(payload["module"])) + 1)
                self.asked.append(key)
                self._index[key] = number - 1
        if name == ANALYSIS_TOOL:
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
            elif payload["module"] in self.no_findings:
                answer = {**grounded_draft(payload), "key_findings": []}
            else:
                answer = grounded_draft(payload)
        elif name == RESPONDENT_TOOL:
            answer = _respondent(tool["inputSchema"]["json"])
        elif name == LEAD_TOOL:
            answer = {"reply": LEAD_REPLY}
        elif name in DESIGN_ANSWERS:
            answer = json.loads(json.dumps(DESIGN_ANSWERS[name]))
        else:
            return _no_recording(name, number)
        return HttpResponse(
            status=200,
            headers={
                "x-amzn-requestid": f"recorded-{_KIND[name]}-{number:05d}",
                "x-aia-recording": RECORDING,
            },
            body={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"t{number}",
                                    "name": name,
                                    "input": answer,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": dict(_USAGE[name]),
                "metrics": {"latencyMs": 900},
            },
        )
