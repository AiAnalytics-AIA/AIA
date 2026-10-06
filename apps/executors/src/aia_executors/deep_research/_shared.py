"""What every Deep Research step shares: the store, the build, the composition, the asking."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final, TypeVar

from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import ModelCallFailed, ModelRequest, ModelResult, canonical_json
from aia_core.domain.deep_research.agents import PROMPT_VERSION, AgentRole, model_request
from aia_core.domain.deep_research.contracts import (
    DeepResearchRequest,
    KnowledgeSource,
    ResearchSubject,
    ResearchTrack,
)
from aia_core.domain.deep_research.steps import CallRecord, Gate, PlanRecord
from aia_core.domain.deep_research.workflow import ARTIFACT_TYPES
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, Succeeded
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ai_step import StepModelCaller
from ..research import upstream_artifact
from .runtime import DeepResearchConfig, DeepResearchRuntime

_UNCONFIGURED_MESSAGE: Final = (
    "Deep Research není v tomto prostředí zapnutý. Běh čeká na plánování; nic nebylo "
    "odesláno, vyhledáno ani vymyšleno."
)

_M = TypeVar("_M", bound=BaseModel)


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Answer:
    """A model's answer, or the gate that refused to send the request."""

    output: BaseModel | None
    call: CallRecord | None
    gate: Gate | None = None
    reason: str = ""
    detail: str = ""

    @property
    def refused(self) -> str:
        return f"{self.gate.value}:{self.reason}" if self.gate is not None else ""


def _unconfigured() -> Failed:
    return Failed(
        FailureClass.RUNTIME_UNAVAILABLE,
        error={"reason": "deep_research_unconfigured", "message": _UNCONFIGURED_MESSAGE},
    )


def _invalid(reason: str, message: str) -> Failed:
    return Failed(FailureClass.SCHEMA_VIOLATION, error={"reason": reason, "message": message})


def _missing_upstream(node_key: str) -> Failed:
    return Failed(
        FailureClass.MISSING_CONFIGURATION,
        error={"message": f"the run's {node_key!r} step recorded no artifact"},
    )


def _composition_changed(what: str) -> Failed:
    return _invalid(
        "composition_changed", f"{what} is not what this run was planned with; start a new run"
    )


def _too_large(request: ModelRequest, config: DeepResearchConfig) -> int | None:
    """The request's conservative size in bytes when it cannot fit the window, else None.

    UTF-8 bytes of the prompt, the message and the contract bound the input from
    above; with the output and one repair's worth, it must fit. Never trimmed.
    """
    size = len(
        (
            request.system
            + "".join(m.content for m in request.messages)
            + canonical_json(request.agent.schema)
        ).encode()
    )
    if size + 5 * config.max_output_tokens + 2048 > config.context_window_tokens:
        return size
    return None


def _lineage(sources: Iterable[KnowledgeSource]) -> DataLineage:
    datasets = sorted({d for s in sources for d in s.lineage})
    return DataLineage.of(*datasets) if datasets else DataLineage.none()


def _detail(gate: Gate, reason: str, message: str = "") -> str:
    text = f"{gate.value}: {reason}" + (f" -- {message}" if message else "")
    return text[:2000]


def _produced(artifact: Artifact, *, reused: bool, **extra: Any) -> Succeeded:
    return Succeeded(
        output={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "reused": reused,
            **extra,
        }
    )


class _Step:
    """What every Deep Research step shares: the store, the build, the composition."""

    def __init__(
        self, *, store: ArtifactStore, build: BuildIdentity, runtime: DeepResearchRuntime | None
    ) -> None:
        self._store = store
        self._build = build
        self._runtime = runtime

    def _repo(self, session: Session, context: StepContext) -> ArtifactRepository:
        return research_artifacts(session, context.scope, self._store)

    def _find(
        self, repo: ArtifactRepository, step: StepInput, kind: str, key: str
    ) -> Artifact | None:
        return repo.find_reusable(
            project_id=step.project_id,
            stage_type=step.stage_type,
            artifact_type=ARTIFACT_TYPES[kind],
            input_fingerprint=key,
        )

    def _put(
        self,
        repo: ArtifactRepository,
        step: StepInput,
        *,
        payload: BaseModel | dict[str, Any],
        kind: str,
        key: str,
        depends_on: Sequence[str] = (),
    ) -> tuple[Artifact, bool]:
        body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        return repo.put_json(
            payload=body,
            project_id=step.project_id,
            revision=step.project_revision,
            stage_type=step.stage_type,
            artifact_type=ARTIFACT_TYPES[kind],
            input_fingerprint=key,
            prompt_version=PROMPT_VERSION,
            runtime_version=self._build.sha or "",
            produced_by_job_id=step.attempt_id,
            metadata={"run_id": step.run_id, "step_id": step.step_id, "kind": step.kind},
            depends_on=list(dict.fromkeys(depends_on)),
        )

    @staticmethod
    def _read(repo: ArtifactRepository, artifact_id: str, model: type[_M]) -> _M:
        return model.model_validate(repo.read_json(artifact_id))

    @staticmethod
    def _reused(artifact: Artifact, step: StepInput) -> bool:
        """Stored by an earlier run (a later pass), not by this run's own earlier attempt."""
        return artifact.metadata.get("run_id") != step.run_id

    def _caller(self, context: StepContext, runtime: DeepResearchRuntime) -> StepModelCaller:
        return StepModelCaller(
            gateway=runtime.gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=runtime.config.provider,
            reservation_usd=runtime.config.reservation_usd,
        )

    def _ask(
        self,
        caller: StepModelCaller,
        runtime: DeepResearchRuntime,
        role: AgentRole,
        *,
        payload: dict[str, Any],
        data_class: DataClass,
        lineage: DataLineage,
    ) -> _Answer:
        """One request for one agent, or the gate that refused it. Refusals spend nothing.

        ``StepFailed`` (a failed or uncertain call), ``BudgetExceeded`` and every
        ``StopExecution`` propagate: the worker decides what the attempt becomes.
        """
        cfg = runtime.config
        request = model_request(
            role,
            payload=payload,
            data_class=data_class,
            lineage=lineage,
            policy_version=cfg.policy_version,
            max_output_tokens=cfg.max_output_tokens,
            thinking_budget_tokens=cfg.thinking_budget_tokens,
        )
        size = _too_large(request, cfg)
        if size is not None:
            return _Answer(
                None,
                None,
                Gate.CONTEXT_WINDOW,
                "context_too_large",
                f"{size} bytes of request and {cfg.max_output_tokens} tokens of output "
                f"do not fit {cfg.context_window_tokens} tokens",
            )
        try:
            caller.preflight(request)
        except ModelCallFailed as exc:
            return _Answer(None, None, Gate.MODEL_ROUTE, exc.reason, str(exc))
        result = caller.invoke(request)
        assert result.output is not None
        return _Answer(result.output, _call_record(role, request, result, data_class))

    def _plan(self, context: StepContext, step: StepInput) -> tuple[str, PlanRecord] | Failed:
        with context.transaction() as (session, workflow):
            plan_id = upstream_artifact(workflow, step, "plan")
            if plan_id is None:
                return _missing_upstream("plan")
            return plan_id, self._read(self._repo(session, context), plan_id, PlanRecord)


def _call_record(
    role: AgentRole, request: ModelRequest, result: ModelResult, data_class: DataClass
) -> CallRecord:
    return CallRecord(
        role=role,
        agent_id=request.agent.agent_id,
        prompt_version=request.agent.prompt_version,
        call_id=result.call_id,
        provider_request_id=result.provider_request_id,
        model=result.resolved_model,
        route_id=result.provenance.route_id,
        policy_version=result.provenance.policy_version,
        data_class=data_class,
        cost_usd=result.total_cost_usd,
    )


def _subjects(
    request: DeepResearchRequest, tracks: Sequence[ResearchTrack]
) -> tuple[ResearchSubject, ...]:
    """The request's subjects, then every cross a track opened, once each."""
    seen = {s.key for s in request.subjects}
    crosses = []
    for track in tracks:
        if track.subject.key not in seen:
            seen.add(track.subject.key)
            crosses.append(track.subject)
    return (*request.subjects, *crosses)


def _class_a_texts(request: DeepResearchRequest) -> tuple[str, ...]:
    return tuple(
        k.text
        for k in request.knowledge.items
        if k.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    )
