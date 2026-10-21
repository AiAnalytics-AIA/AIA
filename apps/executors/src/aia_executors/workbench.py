"""The test and workbench composition: production's executors plus fictional fieldwork.

``AIA_WORKER_EXECUTORS=aia_executors.workbench:build_registry`` gives the research
fieldwork step one dataset producer, the fictional synthetic source (ADR 0016
D1), so the chain after fieldwork -- aggregation, the Sociomap, the results
screens -- can be proven on this machine and in tests. Nothing it produces is
fieldwork; every dataset and every artifact computed from one carries
``data_origin = SYNTHETIC_FIXTURE``. A Research Lead turn here is answered by a script
from its frozen context, without a model, and says so (``scripted: true``, a reply starting
"[Workbench · bez modelu]"), so the conversation, the edit and request gates and the Lead's
memory can be tried on this machine for real.

With ``AIA_AI_ANALYSIS_ENABLED=true`` the eight analysis modules are answered too, by
:class:`~aia_executors.recorded_models.RecordedModels` behind the real gateway, reservations and
ledger, at a price of zero, so a fictional run reaches its internal draft report on this machine
(plan ``artifact-chain-to-draft-report`` CHN7). No other key of the AI runtime is read here: the
route, model and prices are this composition's own (:data:`RECORDED_RUNTIME`), so nothing a
developer's environment holds can point it at a provider. With
``AIA_AI_RESEARCH_AGENTS_ENABLED=true`` the eight design workers answer the same way, one
recorded proposal each, so a job's card, its proposal and its stale refusal can be met here.

Deep Research runs here end to end with nothing paid and nothing leaving the process
(research-lead-workbench 12a, F-DRL-6) when ``AIA_WORKBENCH_DEEP_RESEARCH_FIXTURES`` names a
directory holding ``web.json`` (a recorded web exchange, replayed by
:mod:`aia_executors.deep_research_recorded`) and ``agents.json`` (what the scripted agents
answer). The six steps and the track kind are production's; the model side is the real
gateway and Bedrock adapter over :class:`ScriptedDeepResearchModel`, a wire that answers each
agent from that file, reports no tokens (so every call settles at zero) and says it is
scripted in every request id and response header. A fictional design's class is set here,
Class C and synthetic, by :class:`WorkbenchDesignClassifier`: on this machine the workbench is
its operator. Unset, the six steps are registered over no runtime and a run parks at plan, as
before.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses): a deployed worker
pointed at it fails at start, before claiming anything. That is the worker's half
of the refusal; the API refuses the setting on staging and production, and the
production registry never provides the source.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.deep_research.contracts import DeepResearchRequest
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH_KINDS
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.prompts import PromptPin
from aia_core.domain.research_lead import LeadOutput, layer
from aia_core.domain.residency import DataClass
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_worker.executor import Failed, StepContext, StepExecutor, StepInput, StepOutcome
from pydantic import ValidationError

from .ai_runtime import AIRuntimeSettings, build_gateway
from .analysis import AnalysisConfig, analysis_registry
from .deep_research import (
    DeepResearchConfig,
    DeepResearchRuntime,
    PlanExecutor,
    deep_research_registry,
)
from .deep_research_recorded import recorded_runtime
from .recorded_models import RecordedModels, RecordedSigner
from .registry import registry_for
from .research import research_registry
from .research_agents import ResearchAgentConfig, ResearchAgentExecutor
from .research_lead import KIND as RESEARCH_LEAD_KIND
from .research_lead import LeadAnswer, ResearchLeadExecutor

__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "DEEP_RESEARCH_FIXTURES_KEY",
    "RECORDED_RUNTIME",
    "SCRIPTED_DEEP_RESEARCH",
    "SCRIPTED_PREFIX",
    "SYNTHETIC_SEED",
    "ScriptedDeepResearchModel",
    "ScriptedLeadExecutor",
    "WorkbenchDesignClassifier",
    "build_registry",
    "recorded_analysis",
    "recorded_research_agent",
    "scripted_deep_research_runtime",
    "scripted_lead_output",
    "workbench_registry_for",
]

#: Where the fictional source may exist. Anything else refuses at start.
ALLOWED_ENVIRONMENTS: Final = frozenset({"local", "test"})

#: One fixed seed: the same design gives the same fictional dataset every time.
SYNTHETIC_SEED: Final = 20260816


#: What a scripted reply starts with: never read as a model's answer.
SCRIPTED_PREFIX: Final = "[Workbench · bez modelu]"
#: What makes a scripted answer this one's, for the stored turn's reuse key.
SCRIPT_VERSION: Final = "workbench-lead-1"
_SCRIPTED_WHY: Final = "Ukázková úprava z workbench"
_FOCUS_ID: Final = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _questions(content: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        q
        for section in content.get("sections") or ()
        if isinstance(section, Mapping) and section.get("type") == "questions"
        for q in section.get("questions") or ()
        if isinstance(q, Mapping) and q.get("id")
    ]


def scripted_lead_output(frozen: Mapping[str, Any]) -> LeadOutput:
    """A Lead turn's answer without any model, from the frozen context alone, deterministic.

    A greeting says where the study stands in three lines. A message proposes one edit (the
    first question's text, else the title), focuses it and prepares the questionnaire's
    optimisation as a decision card (a message with "spusť": the research run instead; with
    "aktualizuj návrh": the brief's analysis, which reads Návrh's saved answers and comments); a
    message with "pamatuj" also asks the Lead to remember it as a personal note. Every reply
    starts with :data:`SCRIPTED_PREFIX`.
    """
    view = layer(frozen, "view")
    study = layer(frozen, "study")
    content = layer(frozen, "design").get("content") or {}
    questions = _questions(content)
    if view.get("kind") == "greeting":
        reply = (
            f"{SCRIPTED_PREFIX} Studie: {study.get('name')}.\n"
            f"Otázek v pracovní verzi: {len(questions)}.\n"
            "Doporučený další krok: projděte zadání."
        )
        return LeadOutput(reply=reply, follow=["Co mám udělat jako první?"])
    message = str(view.get("message") or "")
    first = questions[0] if questions else None
    edit: dict[str, Any]
    target = "brief:title"
    if first is not None:
        edit = {
            "op": "question_edit",
            "question_id": str(first["id"]),
            "text": f"{first.get('text') or ''} (upřesněno)".strip(),
            "why": _SCRIPTED_WHY,
        }
        if _FOCUS_ID.match(str(first["id"])):
            target = f"question:{first['id']}"
    else:
        edit = {
            "op": "set_text",
            "field": "title",
            "value": f"{content.get('title') or 'Studie'} (upřesněno)",
            "why": _SCRIPTED_WHY,
        }
    body: dict[str, Any] = {
        "reply": f"{SCRIPTED_PREFIX} Připravil jsem ukázkovou úpravu a jedno rozhodnutí.",
        "view": [{"op": "focus", "target": target}],
        "edits": [edit],
        "request": {
            "kind": "agent_job",
            "action": "optimize_questionnaire",
            "why": "Ukázka rozhodnutí",
        },
    }
    if "spusť" in message.casefold():
        # A prepared research run instead (plan research-lead-workbench chunk 23): its card starts
        # the run through Spuštění's route, on the workbench's fictional fieldwork.
        body["request"] = {"kind": "research_run", "why": "Ukázka spuštění výzkumu"}
    elif "aktualizuj návrh" in message.casefold():
        # Návrh's saved answers or comments, read from the working copy by the brief's analysis.
        body["request"] = {
            "kind": "agent_job",
            "action": "analyze_brief",
            "why": "Aktualizace návrhu podle uložených odpovědí a komentářů",
        }
    if "pamatuj" in message.casefold():
        body["self_update"] = {"remember": [{"scope": "personal", "text": message[:300]}]}
    return LeadOutput.model_validate(body)


class ScriptedLeadExecutor(ResearchLeadExecutor):
    """The Research Lead's turn answered without a model, for this composition only.

    Everything but the answer is the real executor's: the frozen context's checks, grounding,
    the Lead's ``self_update`` applied under the turn's lease, and the stored result, which
    says ``scripted: true``. No gateway, no reservation, no data class.
    """

    def _unconfigured(self) -> Failed | None:
        return None

    def _identity(self) -> dict[str, Any]:
        return {"script": SCRIPT_VERSION}

    def _answer(
        self,
        step: StepInput,
        context: StepContext,
        frozen: Mapping[str, Any],
        pin: PromptPin,
    ) -> LeadAnswer | Failed:
        return LeadAnswer(
            output=scripted_lead_output(frozen),
            data_class=None,
            provenance={"script": SCRIPT_VERSION, "prompt_origin": pin.origin, "cost_usd": 0.0},
            scripted=True,
        )


#: The AI runtime the recorded analysis runs on: a test route and model, priced at zero, never
#: read from the environment. RecordedModels answers every request; nothing leaves the process.
RECORDED_RUNTIME: Final[Mapping[str, str]] = {
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.example.analysis-model-v1:0",
    "AIA_AI_POLICY_VERSION": "aia-workbench-recorded-1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "0",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "0",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL,CLASS_B_DERIVED_CLIENT",
    "AIA_AI_ROUTE_RETENTION_DAYS": "0",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_ANALYSIS_ENABLED": "true",
    "AIA_AI_ANALYSIS_MAX_OUTPUT_TOKENS": "4096",
    "AIA_AI_ANALYSIS_RESERVATION_USD": "0.01",
    "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
    "AIA_AI_RESEARCH_RESERVATION_USD": "0.01",
}


def recorded_analysis(
    *, store: ArtifactStore, build: BuildIdentity, models: RecordedModels | None = None
) -> StepExecutor:
    """The analysis step over recorded answers behind the real gateway, at zero price."""
    settings = AIRuntimeSettings.from_env({"AIA_ENV": "test", **RECORDED_RUNTIME})
    assert settings is not None
    gateway = build_gateway(settings, transport=models or RecordedModels(), signer=RecordedSigner())
    config = AnalysisConfig.from_settings(
        settings,
        max_output_tokens=settings.analysis_max_output_tokens,
        reservation_usd=settings.analysis_reservation_usd,
    )
    return analysis_registry(store=store, build=build, gateway=gateway, config=config)[
        "research_analysis"
    ]


# --------------------------------------------------------------------------- #
# Deep Research: recorded web, scripted agents, nothing paid
# --------------------------------------------------------------------------- #

#: The directory holding ``web.json`` and ``agents.json``; unset, Deep Research parks here.
DEEP_RESEARCH_FIXTURES_KEY: Final = "AIA_WORKBENCH_DEEP_RESEARCH_FIXTURES"
#: What every scripted Deep Research answer says it is.
SCRIPTED_DEEP_RESEARCH: Final = "workbench-deep-research-1"
#: The model the scripted wire stands for: never a Bedrock profile anyone can call.
SCRIPTED_MODEL_ID: Final = "eu.workbench-scripted-deep-research-v1:0"
_TOOL_PREFIX: Final = "aia_deep_research_"
_DESIGN_PROVENANCE: Final = (
    "workbench: a fictional client's design on this machine, classified Class C and synthetic "
    "by aia_executors.workbench (local and test only)"
)


#: A nominal price per million tokens. It only sizes each request's hold (a metered request
#: needs a positive one, ``StepModelCaller``); the script reports no tokens, so every call
#: settles at exactly zero.
_HOLD_USD_PER_MTOK: Final = "0.01"


def _scripted_settings(environment: str) -> AIRuntimeSettings:
    """The AI runtime the scripted wire sits behind: nominal holds, approved for Class C."""
    settings = AIRuntimeSettings.from_env(
        {
            "AIA_ENV": environment,
            "AIA_AI_RUNTIME_ENABLED": "true",
            "AIA_AI_ROUTE_ID": "workbench-scripted",
            "AIA_BEDROCK_REGION": "eu-central-1",
            "AIA_BEDROCK_MODEL_ID": SCRIPTED_MODEL_ID,
            "AIA_AI_POLICY_VERSION": SCRIPTED_DEEP_RESEARCH,
            "AIA_BEDROCK_INPUT_USD_PER_MTOK": _HOLD_USD_PER_MTOK,
            "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": _HOLD_USD_PER_MTOK,
            "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
            "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
            "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
            "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
            "AIA_AI_ROUTE_APPROVED_FOR": DataClass.CLASS_C_INTERNAL.value,
            "AIA_AI_ROUTE_RETENTION_DAYS": "0",
            "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
            "AIA_AI_FIELDWORK_RESERVATION_USD": "0.01",
            "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
            "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
            "AIA_AI_RESEARCH_RESERVATION_USD": "0.01",
        }
    )
    assert settings is not None  # AIA_AI_RUNTIME_ENABLED is set above
    return settings


class _ScriptedSigner:
    """Signs nothing: the scripted wire needs no credential, and none is read."""

    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 workbench-scripted"}


@dataclass
class ScriptedDeepResearchModel:
    """Bedrock Converse's wire for the Deep Research agents, answered by a script.

    Each answer is built from what the agent was shown and ``answers`` (``agents.json``):
    the planner's queries per subject text (else ``default_queries``), each web source's
    evidence by URL (quotes literally on the recorded page, so grounding passes by its own
    rules), every item supported by the verifier, and one finding per subject citing its
    first accepted evidence. An internal track finds nothing. A contract this wire has no
    script for gets the provider's validation refusal, answered and unbilled. Every response
    carries ``x-aia-scripted`` and a ``workbench-scripted-<role>-<n>`` request id.
    """

    answers: Mapping[str, Any]
    requests: list[HttpRequest] = field(default_factory=list)

    def roles(self) -> list[str]:
        """The role of every request this wire answered, in order."""
        return [_role(r) for r in self.requests]

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        role = _role(request)
        headers = {
            "x-amzn-requestid": f"workbench-scripted-{role}-{len(self.requests)}",
            "x-aia-scripted": SCRIPTED_DEEP_RESEARCH,
        }
        answer = getattr(self, f"_answer_{role}", None)
        if answer is None:
            return HttpResponse(
                status=400,
                headers={**headers, "x-amzn-errortype": "ValidationException"},
                body={"message": f"the workbench has no script for {role!r}"},
            )
        name = request.body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        payload = json.loads(request.body["messages"][0]["content"][0]["text"])
        tool = {"toolUse": {"toolUseId": "t", "name": name, "input": answer(payload)}}
        return HttpResponse(
            status=200,
            headers=headers,
            body={
                "output": {"message": {"role": "assistant", "content": [tool]}},
                "stopReason": "tool_use",
                # A script reads and writes no tokens: every call costs exactly nothing.
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
            },
        )

    def _answer_planner(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        plans: Mapping[str, Any] = self.answers.get("planner") or {}
        default = list(self.answers.get("default_queries") or [])
        tracks = []
        for track in payload["tracks"]:
            plan: Mapping[str, Any] = plans.get(track["subject"]) or {}
            tracks.append(
                {
                    "track_id": track["track_id"],
                    "sub_questions": list(plan.get("sub_questions") or []),
                    "queries": list(plan.get("queries") or default),
                }
            )
        return {"tracks": tracks, "notes": ""}

    def _answer_web_investigator(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        web: Mapping[str, Any] = self.answers.get("web") or {}
        evidence = [
            {"source_id": s["source_id"], **e}
            for s in payload["sources"]
            for e in web.get(s["url"], [])
        ]
        return {"evidence": evidence, "gaps": []}

    def _answer_internal_investigator(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {"evidence": [], "gaps": []}

    def _answer_verifier(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "verdicts": [
                {
                    "evidence_id": item["evidence_id"],
                    "verdict": "supported",
                    "reason": "workbench: podloženo citací",
                }
                for item in payload["items"]
            ]
        }

    def _answer_synthesizer(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        by_subject: dict[str, list[Mapping[str, Any]]] = {}
        for evidence in payload["evidence"]:
            by_subject.setdefault(evidence["subject_key"], []).append(evidence)
        first = payload["evidence"][0]["claim"] if payload["evidence"] else ""
        return {
            "summary": first or "Workbench: nic nebylo nalezeno.",
            "findings": [
                {"subject_key": k, "text": v[0]["claim"], "evidence_ids": [v[0]["evidence_id"]]}
                for k, v in by_subject.items()
            ],
            "gaps": [s["text"] for s in payload["subjects"] if s["subject_key"] not in by_subject],
            "limitations": ["Workbench: zaznamenané fiktivní stránky, nikoli živý web."],
        }


def _role(request: HttpRequest) -> str:
    name = str(request.body["toolConfig"]["tools"][0]["toolSpec"]["name"])
    return name.removeprefix(_TOOL_PREFIX) if name.startswith(_TOOL_PREFIX) else name


def scripted_deep_research_runtime(
    fixtures: Path, *, env: Mapping[str, str] | None = None
) -> tuple[DeepResearchRuntime, ScriptedDeepResearchModel]:
    """Recorded web retrieval and the scripted agents over ``fixtures``; local and test only.

    The script reports no tokens, so every reservation settles at nothing. The recorded
    composition refuses any ``AIA_ENV`` but local and test, as :func:`build_registry` does.
    """
    environment = ((os.environ if env is None else env).get("AIA_ENV") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "the workbench's Deep Research answers from a script over recorded web and refuses "
            f"AIA_ENV={environment!r}; no deployment composes it"
        )
    answers = json.loads((fixtures / "agents.json").read_text(encoding="utf-8"))
    model = ScriptedDeepResearchModel(answers=answers)
    settings = _scripted_settings(environment)
    runtime = recorded_runtime(
        gateway=build_gateway(settings, transport=model, signer=_ScriptedSigner()),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
            fictional_client_ids=frozenset(),
        ),
        fixture=fixtures / "web.json",
        env={"AIA_ENV": environment},
    )
    return runtime, model


class WorkbenchDesignClassifier(PlanExecutor):
    """The plan step with the run's design classified first, Class C and synthetic.

    A deployed operator classifies a design by its exact bytes; on this machine every
    client is fictional and the workbench is the operator, so the design the run froze is
    classified here and the real plan step runs over that classification. Nothing else of
    the step changes; a request it cannot read is the real step's to refuse, by name.
    """

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        runtime = self._runtime
        if runtime is None:
            return super().execute(step, context)
        try:
            request = DeepResearchRequest.model_validate(step.payload["request"])
            with context.transaction() as (session, _workflow):
                content = StudyDesignRepository(session, context.scope).content(
                    request.design_revision_id
                )
        except (KeyError, ValidationError, DesignRevisionNotFound):
            return super().execute(step, context)  # the real step names what is wrong
        approval = MaterialApproval(
            sha256=material_sha256(content),
            data_class=DataClass.CLASS_C_INTERNAL,
            provenance=_DESIGN_PROVENANCE,
            synthetic=True,
        )
        known = tuple(a for a in runtime.config.material_approvals if a.sha256 != approval.sha256)
        classified = replace(
            runtime, config=replace(runtime.config, material_approvals=(*known, approval))
        )
        return PlanExecutor(store=self._store, build=self._build, runtime=classified).execute(
            step, context
        )


def _deep_research(
    *, store: ArtifactStore, build: BuildIdentity, fixtures: Path | None
) -> dict[str, StepExecutor]:
    """Nothing without fixtures (production's parked steps stay); else the six steps and
    the track kind over the scripted runtime, the plan step classifying first."""
    if fixtures is None:
        return {}
    runtime, _model = scripted_deep_research_runtime(fixtures)
    return {
        **deep_research_registry(store=store, build=build, runtime=runtime),
        DEEP_RESEARCH_KINDS["plan"]: WorkbenchDesignClassifier(
            store=store, build=build, runtime=runtime
        ),
    }


def recorded_research_agent(
    *, store: ArtifactStore, build: BuildIdentity, models: RecordedModels | None = None
) -> StepExecutor:
    """The eight design workers over recorded answers behind the real gateway, at zero price
    (:data:`~aia_executors.recorded_models.DESIGN_ANSWERS`, one fixed answer per worker): a
    job's proposal, its card in the Lead's conversation and its accept, on this machine."""
    settings = AIRuntimeSettings.from_env({"AIA_ENV": "test", **RECORDED_RUNTIME})
    assert settings is not None
    return ResearchAgentExecutor(
        store=store,
        build=build,
        gateway=build_gateway(
            settings, transport=models or RecordedModels(), signer=RecordedSigner()
        ),
        config=ResearchAgentConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            reservation_usd=settings.research_reservation_usd,
            fictional_client_ids=frozenset(),
        ),
    )


def workbench_registry_for(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    analysis: StepExecutor | None = None,
    research_agent: StepExecutor | None = None,
    deep_research: Path | None = None,
) -> dict[str, StepExecutor]:
    """Production's registry with the fictional fieldwork source added, the Research Lead's
    turns answered by a script (no model); ``analysis`` replaces the analysis step
    (:func:`recorded_analysis`; without it the step parks, as production's does), as
    ``research_agent`` replaces the design workers (:func:`recorded_research_agent`) and, with
    ``deep_research`` (a fixtures directory), Deep Research runs on recorded web and scripted
    agents. Tests use this."""
    return {
        **registry_for(store=store, build=build, analysis=analysis, research_agent=research_agent),
        **_deep_research(store=store, build=build, fixtures=deep_research),
        RESEARCH_LEAD_KIND: ScriptedLeadExecutor(store=store, build=build),
        **research_registry(
            store=store,
            build=build,
            producers={
                FieldworkSource.SYNTHETIC_FIXTURE: lambda spec: synthetic_dataset(
                    spec, seed=SYNTHETIC_SEED
                )
            },
        ),
    }


def build_registry() -> dict[str, StepExecutor]:
    """The factory for ``AIA_WORKER_EXECUTORS``; refuses outside local and test."""
    env = os.environ.get("AIA_ENV", "").strip().lower()
    if env not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            f"aia_executors.workbench provides fictional fieldwork and refuses AIA_ENV={env!r}; "
            "a deployed worker uses aia_executors.registry:build_registry (ADR 0016)"
        )
    store = build_artifact_store(StorageSettings.from_env())
    build = BuildIdentity.from_env()

    def switched(key: str) -> bool:
        return os.environ.get(key, "").strip().lower() in {"1", "true", "yes", "on"}

    analysis = (
        recorded_analysis(store=store, build=build) if switched("AIA_AI_ANALYSIS_ENABLED") else None
    )
    agent = (
        recorded_research_agent(store=store, build=build)
        if switched("AIA_AI_RESEARCH_AGENTS_ENABLED")
        else None
    )
    fixtures = (os.environ.get(DEEP_RESEARCH_FIXTURES_KEY) or "").strip()
    return workbench_registry_for(
        store=store,
        build=build,
        analysis=analysis,
        research_agent=agent,
        deep_research=Path(fixtures) if fixtures else None,
    )
