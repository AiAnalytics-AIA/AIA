"""The acceptance harness's worker: ``aia_executors.acceptance_recorded:build_registry``.

Tier A of ``MVP-ACCEPT-2`` (``docs/migration/mvp-acceptance.md`` §2) runs the production stack
over HTTP with recorded, deterministic providers **behind** the gateway and the retrieval gate.
This is that worker's composition: the production one (:func:`registry.compose_registry`, the
same settings, executors, gateway, reservations, ledger and gates), with one change -- the model
wire is :class:`~aia_executors.recorded_models.RecordedModels` and its signer, so every model
request is answered by a recording and nothing leaves the process or is paid.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses), and no
deployment may name it (``make layer_check``): a recorded answer can never stand in for a model.

Deep Research runs here only over recordings (plan ``mvp-acceptance-harness`` chunk 4):
``AIA_ACCEPTANCE_RECORDINGS`` names a directory holding ``web.json`` (the recorded search and
fetch, :mod:`aia_executors.deep_research_recorded`) and ``agents.json`` (the five agents'
recorded script, :func:`~aia_executors.recorded_models.deep_research_answer`). With
``AIA_DEEP_RESEARCH_ENABLED`` and no recordings it refuses: the search and fetch would
otherwise be the live routes. A live route named beside the recordings is refused by the
runtime (``deep_research_runtime(retrieval=)``).

Two knobs shape the recorded wire for a test, and only here:
``AIA_ACCEPTANCE_RECORDED_STALL_AFTER``, the calls answered before every later one is held until
the worker stops (so a worker killed then dies inside a call, AC-06), and
``AIA_ACCEPTANCE_RECORDED_NO_FINDINGS``, the analysis modules answered with no supported finding
(a module a person may then ask again over the run's frozen data, AC-06). A value outside them is
refused by name at start.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_worker.executor import StepExecutor

from .deep_research_recorded import recorded_retrieval
from .deep_research_runtime import ENABLED_KEY as DEEP_RESEARCH_KEY
from .deep_research_runtime import deep_research_enabled
from .recorded_models import RecordedModels, RecordedSigner
from .registry import compose_registry

__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "NO_FINDINGS_KEY",
    "RECORDINGS_KEY",
    "STALL_KEY",
    "build_registry",
    "recorded_wire",
    "refuse_outside_tests",
]

#: Where recorded models may answer. Anything else refuses at start.
ALLOWED_ENVIRONMENTS: Final = frozenset({"local", "test"})
#: The directory holding the recorded web (``web.json``) and agents (``agents.json``).
RECORDINGS_KEY: Final = "AIA_ACCEPTANCE_RECORDINGS"
#: Calls answered before every later one is held until the worker stops; unset, none held.
STALL_KEY: Final = "AIA_ACCEPTANCE_RECORDED_STALL_AFTER"
#: Analysis modules answered with no supported finding, comma-separated; unset, none.
NO_FINDINGS_KEY: Final = "AIA_ACCEPTANCE_RECORDED_NO_FINDINGS"


def refuse_outside_tests(env: Mapping[str, str]) -> None:
    """Raise unless this process is a local or test one, and Deep Research is off."""
    environment = (env.get("AIA_ENV") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "aia_executors.acceptance_recorded answers model requests from recordings and "
            f"refuses AIA_ENV={environment!r}; no deployment composes it"
        )
    if deep_research_enabled(env) and not (env.get(RECORDINGS_KEY) or "").strip():
        raise RuntimeError(
            f"aia_executors.acceptance_recorded runs Deep Research only over recordings: "
            f"{DEEP_RESEARCH_KEY} needs {RECORDINGS_KEY}, else it would compose the live "
            "search routes beside recorded models"
        )


def recorded_wire(
    env: Mapping[str, str], *, deep_research: Mapping[str, Any] | None = None
) -> RecordedModels:
    """The recorded wire, shaped by :data:`STALL_KEY` and :data:`NO_FINDINGS_KEY`."""
    raw_stall = (env.get(STALL_KEY) or "").strip()
    stall_after = int(raw_stall) if raw_stall.isdigit() else None
    if raw_stall and stall_after is None:
        raise RuntimeError(f"{STALL_KEY} must be a whole number of calls")
    modules = {m.strip() for m in (env.get(NO_FINDINGS_KEY) or "").split(",") if m.strip()}
    unknown = sorted(modules - {m.value for m in AnalysisModuleId})
    if unknown:
        raise RuntimeError(f"{NO_FINDINGS_KEY} names no analysis module: {', '.join(unknown)}")
    return RecordedModels(no_findings=modules, stall_after=stall_after, deep_research=deep_research)


def build_registry() -> dict[str, StepExecutor]:
    """The factory ``AIA_WORKER_EXECUTORS`` names; reads the environment like production's."""
    refuse_outside_tests(os.environ)
    if not deep_research_enabled(os.environ):
        return compose_registry(transport=recorded_wire(os.environ), signer=RecordedSigner())
    recordings = Path(os.environ[RECORDINGS_KEY].strip())
    script: dict[str, Any] = json.loads((recordings / "agents.json").read_text("utf-8"))
    return compose_registry(
        transport=recorded_wire(os.environ, deep_research=script),
        signer=RecordedSigner(),
        deep_research_retrieval=recorded_retrieval(recordings / "web.json"),
    )
