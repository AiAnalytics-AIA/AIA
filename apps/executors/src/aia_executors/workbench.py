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
developer's environment holds can point it at a provider.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses): a deployed worker
pointed at it fails at start, before claiming anything. That is the worker's half
of the refusal; the API refuses the setting on staging and production, and the
production registry never provides the source.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, Final

from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.prompts import PromptPin
from aia_core.domain.research_lead import LeadOutput, layer
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_worker.executor import Failed, StepContext, StepExecutor, StepInput

from .ai_runtime import AIRuntimeSettings, build_gateway
from .analysis import AnalysisConfig, analysis_registry
from .recorded_models import RecordedModels, RecordedSigner
from .registry import registry_for
from .research import research_registry
from .research_lead import KIND as RESEARCH_LEAD_KIND
from .research_lead import LeadAnswer, ResearchLeadExecutor

__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "RECORDED_RUNTIME",
    "SCRIPTED_PREFIX",
    "SYNTHETIC_SEED",
    "ScriptedLeadExecutor",
    "build_registry",
    "recorded_analysis",
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
    optimisation as a decision card; a message with "pamatuj" also asks the Lead to remember
    it as a personal note. Every reply starts with :data:`SCRIPTED_PREFIX`.
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


def workbench_registry_for(
    *, store: ArtifactStore, build: BuildIdentity, analysis: StepExecutor | None = None
) -> dict[str, StepExecutor]:
    """Production's registry with the fictional fieldwork source added, and the Research
    Lead's turns answered by a script (no model); ``analysis`` replaces the analysis step
    (:func:`recorded_analysis`; without it the step parks, as production's does). Tests use
    this."""
    return {
        **registry_for(store=store, build=build, analysis=analysis),
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
    analysis = (
        recorded_analysis(store=store, build=build)
        if os.environ.get("AIA_AI_ANALYSIS_ENABLED", "").strip().lower()
        in {"1", "true", "yes", "on"}
        else None
    )
    return workbench_registry_for(store=store, build=build, analysis=analysis)
