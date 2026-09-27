"""The research template: the document a new research Study's stages start from.

AIA's own copy of the empty research project the 18.6.6 unit handed every new
project (``empty_project()``, ``legacy/npc-panel-18.6.6/app/research_project.py:61``,
served in ``GET /api/bootstrap``), so a Study starts, and a stored document is
completed with defaults (the stages' ``defaultsMerge``), without asking the unit.
It is pinned to the unit's answer by
``tests/test_research_template.py``, against the capture the web client's parity
tests already use (``apps/web/src/research/fixtures/empty-project.json``).

Two fields are carried as the unit wrote them and read by nothing in AIA:
``run_policy.provider`` and ``model``. AIA's model route is its AI runtime's
configuration (ADR 0010), never a project's content, and the research agents strip
both before a model sees the document (``research_agents.py``). They stay so that
the stages' ported functions, parity-tested against the unit's JavaScript, see the
document they were written for.

Pure: no I/O.
"""

from __future__ import annotations

import copy
from typing import Any, Final

__all__ = ["RESEARCH_TEMPLATE_VERSION", "research_template"]

#: Bumped whenever the template changes; recorded nowhere else, read by the tests.
RESEARCH_TEMPLATE_VERSION: Final = "18.6.6-empty-project-v1"

_TEMPLATE: Final[dict[str, Any]] = {
    "schema_version": 3,
    "title": "Nový výzkum",
    "study_type": "custom",
    "study_config": {},
    "instrument_library": {"version": "", "missing_slots": [], "skipped_instruments": []},
    "goal": "",
    "decision_use": "",
    "briefing": {
        "product_description": "",
        "situation": "",
        "what_is_known": "",
        "constraints": "",
    },
    "research_plan": {
        "status": "draft",
        "problem_summary": "",
        "objectives": [],
        "research_questions": [],
        "hypotheses": [],
        "recommended_topics": [],
        "non_object_measures": [],
        "questions_for_user": [],
        "complexity": "standard",
        "estimated_minutes": None,
        "method_reason": "",
    },
    "audience": {
        "source_mode": "population",
        "dataset_id": "",
        "dataset_name": "ČR 18+",
        "builtin_subpanel": "",
        "strategy": "population",
        "description": "ČR 18+",
        "filters": {},
        "segment": {"mode": "none"},
        "product_description": "",
        "success_definition": "",
        "discovery_note": "",
        "subpanel_status": "",
        "support_tier": "",
        "support_summary": {},
        "audience_recommendation": {},
    },
    "n": 300,
    "persona_mode": "calibrated",
    "persona_dimensions": {"approved": []},
    "panel_mode": "standard",
    "ai_panel_profile": {},
    "model": "sonnet",
    "ui_state": {
        "questionnaire_path": "choose",
        "audience_entry": "choose",
        "persona_path": "choose",
    },
    "research_context": True,
    "pre_research": {},
    "run_policy": {"provider": "claude_code_subscription", "allow_provider_fallback": False},
    "budget": {"max_usd": None, "warning_pct": 80},
    "sections": [],
    "discovery": {"enabled": False, "question_id": "", "positive_answers": [], "min_positive": 20},
    "notes": [],
}


def research_template() -> dict[str, Any]:
    """A fresh copy of the research template; the caller may change it freely."""
    return copy.deepcopy(_TEMPLATE)
