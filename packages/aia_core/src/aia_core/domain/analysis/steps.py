"""Where the analysis modules sit in a research run: the graph specification, as data.

The research template (``workflow_templates``) is owned by the workflow integration
and is not changed here. This module states what that integration adds, so the
template can take it as data and the executor and its tests agree on one shape:

* eight nodes, ``analysis_<module>``, each of kind :data:`ANALYSIS_STEP_KIND`, filed
  under the ``ANALYSIS`` stage;
* each depends on ``aggregate`` **only** -- not on the module before it, as the unit
  chained them (``workflow_engine.STANDARD``): a blocked or failed module strands no
  other, so every module always has its own recorded outcome;
* step input ``{"analysis_module": <id>, "analysis_surface": <surface>}``, chosen by
  the composition, never by a request;
* ``max_attempts`` 3: a retried attempt replays every turn it checkpointed, so a retry
  pays only for turns that never answered.

Pure: no I/O.
"""

from __future__ import annotations

from typing import Any, Final

from ..evidence import ClaimSurface
from ..workflow import StepDefinition
from .modules import ANALYSIS_MODULES, AnalysisModuleId

__all__ = [
    "ANALYSIS_DEPENDS_ON",
    "ANALYSIS_MAX_ATTEMPTS",
    "ANALYSIS_NODE_PREFIX",
    "ANALYSIS_STAGE",
    "ANALYSIS_STEP_KIND",
    "analysis_node_key",
    "analysis_step_definitions",
    "analysis_step_inputs",
    "module_of_node",
]

ANALYSIS_STEP_KIND: Final = "research_analysis"
ANALYSIS_NODE_PREFIX: Final = "analysis_"
ANALYSIS_STAGE: Final = "ANALYSIS"
ANALYSIS_DEPENDS_ON: Final = ("aggregate",)
ANALYSIS_MAX_ATTEMPTS: Final = 3


def analysis_node_key(module_id: AnalysisModuleId) -> str:
    """``analysis_<module>``: the reference's node keys (``analysis_executive`` ...)."""
    return f"{ANALYSIS_NODE_PREFIX}{module_id.value}"


def module_of_node(node_key: str) -> AnalysisModuleId | None:
    """The module a node key names, or ``None`` for any other node."""
    if not node_key.startswith(ANALYSIS_NODE_PREFIX):
        return None
    try:
        return AnalysisModuleId(node_key.removeprefix(ANALYSIS_NODE_PREFIX))
    except ValueError:
        return None


def analysis_step_definitions() -> tuple[StepDefinition, ...]:
    """The eight analysis nodes, in module order, to append to the research graph."""
    return tuple(
        StepDefinition(
            node_key=analysis_node_key(spec.module_id),
            kind=ANALYSIS_STEP_KIND,
            depends_on=ANALYSIS_DEPENDS_ON,
            stage_type=ANALYSIS_STAGE,
            artifact_target=f"research_{analysis_node_key(spec.module_id)}",
            max_attempts=ANALYSIS_MAX_ATTEMPTS,
        )
        for spec in ANALYSIS_MODULES
    )


def analysis_step_inputs(surface: ClaimSurface) -> dict[str, dict[str, Any]]:
    """What each analysis step is told: its module and the surface it writes for."""
    return {
        analysis_node_key(spec.module_id): {
            "analysis_module": spec.module_id.value,
            "analysis_surface": surface.value,
        }
        for spec in ANALYSIS_MODULES
    }
