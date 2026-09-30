"""The Deep Research steps: plan, investigate, merge, verify, synthesize, publish.

ADR 0017 as amended; ``docs/architecture/deep-research.md``. Each executor is a
shell around the pure rules of ``aia_core.domain.deep_research``: it reads its
inputs under the lease-issued scope, asks a model only through
:class:`~aia_executors.ai_step.StepModelCaller`, reaches the web only through
:class:`~aia_core.application.web_retrieval.RetrievalGate`, and stores what it found
as artifacts of the Study's research (``research_artifacts``). Upstream results are
found through the run itself (``upstream_artifact``), never through an id a payload
names; the request a run was frozen to is checked against the step's fingerprint.

What runs is the composition's, :class:`DeepResearchRuntime`:

* **none** -- the plan step parks the run (``RUNTIME_UNAVAILABLE``,
  ``deep_research_unconfigured``) before anything is read or sent;
* **a gateway, no retrieval** -- the default: every web track is blocked
  (``web_retrieval_unavailable``)
  without a planner call, and every internal track meets the gateway's gates,
  which refuse Client Knowledge on a Class C route before anything is sent;
* **a gateway and recorded retrieval** -- the recorded composition, local and test
  only (a module nothing else here may import): the whole path, on captured
  exchanges.
* **a gateway and live public retrieval** -- a separately enabled, fee-free Czech
  Wikipedia search/fetch route for classified Class C material and internal review.

Models propose and code decides (plan decision I-1): a query leaves only if the
gate lets it, a finding exists only if its quote is in a source the track
captured, acceptance is the declared source tables and the verifier, and a
number reaches the brief only from a quote it cites. Every unit of work is an
artifact with a fingerprint (I-4), so a retried step and a later pass buy nothing
twice. The production registry includes the six kinds, including the parked state.
"""

from __future__ import annotations

from aia_core.domain.deep_research.workflow import DEEP_RESEARCH_KINDS
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import StepExecutor

from .investigate import InvestigateExecutor
from .plan import PlanExecutor
from .publish import PublishExecutor, SynthesizeExecutor
from .review import MergeExecutor, VerifyExecutor
from .runtime import DeepResearchConfig, DeepResearchRuntime, StepToolMeter

__all__ = [
    "DeepResearchConfig",
    "DeepResearchRuntime",
    "InvestigateExecutor",
    "MergeExecutor",
    "PlanExecutor",
    "PublishExecutor",
    "StepToolMeter",
    "SynthesizeExecutor",
    "VerifyExecutor",
    "deep_research_registry",
]


def deep_research_registry(
    *, store: ArtifactStore, build: BuildIdentity, runtime: DeepResearchRuntime | None
) -> dict[str, StepExecutor]:
    """The six Deep Research kinds -> executors over one composition.

    ``runtime=None`` is the honest unconfigured state: the plan step parks the run.
    """
    return {
        DEEP_RESEARCH_KINDS["plan"]: PlanExecutor(store=store, build=build, runtime=runtime),
        DEEP_RESEARCH_KINDS["investigate"]: InvestigateExecutor(
            store=store, build=build, runtime=runtime
        ),
        DEEP_RESEARCH_KINDS["merge"]: MergeExecutor(store=store, build=build, runtime=runtime),
        DEEP_RESEARCH_KINDS["verify"]: VerifyExecutor(store=store, build=build, runtime=runtime),
        DEEP_RESEARCH_KINDS["synthesize"]: SynthesizeExecutor(
            store=store, build=build, runtime=runtime
        ),
        DEEP_RESEARCH_KINDS["publish"]: PublishExecutor(store=store, build=build, runtime=runtime),
    }
