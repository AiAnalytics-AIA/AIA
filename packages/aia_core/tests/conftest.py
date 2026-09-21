"""Test fixtures, including access to the legacy prototype for parity testing.

The legacy NPC Panel prototype is deliberately *not* vendored into this
repository. Parity tests import it from the path in ``AIA_LEGACY_REFERENCE`` and
skip cleanly when it is absent, so a normal clone and CI run stay green while a
migration engineer with the reference checkout gets the extra verification.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_DEFAULT_REFERENCE_PATHS = (
    Path(__file__).resolve().parents[4] / "npc-panel-reference",
    Path.home() / "Downloads" / "AIA" / "npc-panel-reference",
)


def _legacy_root() -> Path | None:
    """Return the legacy prototype root, or None when it is unavailable."""
    configured = os.environ.get("AIA_LEGACY_REFERENCE")
    candidates = [Path(configured)] if configured else list(_DEFAULT_REFERENCE_PATHS)
    for candidate in candidates:
        if (candidate / "project_pipeline.py").is_file():
            return candidate
    return None


@pytest.fixture(scope="session")
def legacy_pipeline() -> Iterator[Any]:
    """Import the legacy ``project_pipeline`` module for parity comparison."""
    root = _legacy_root()
    if root is None:
        pytest.skip(
            "legacy prototype not available; set AIA_LEGACY_REFERENCE to the "
            "npc-panel-reference checkout to enable parity tests"
        )
    sys.path.insert(0, str(root))
    try:
        import project_pipeline

        yield project_pipeline
    finally:
        sys.path.remove(str(root))


@pytest.fixture(scope="session")
def legacy_provider_runtime() -> Iterator[Any]:
    """Import the legacy ``provider_runtime`` module for parity comparison."""
    root = _legacy_root()
    if root is None:
        pytest.skip("legacy prototype not available; set AIA_LEGACY_REFERENCE")
    sys.path.insert(0, str(root))
    try:
        import provider_runtime

        yield provider_runtime
    finally:
        sys.path.remove(str(root))


@pytest.fixture
def research_project() -> dict[str, Any]:
    """A representative research project payload touching every stage's inputs."""
    return {
        "schema_version": 2,
        "title": "Test výzkum",
        "goal": "Zjistit postoj k nové nabídce",
        "decision_use": "Rozhodnutí o spuštění produktu",
        "briefing": "Klient zvažuje vstup na trh.",
        "study_type": "brand_positioning",
        "research_plan": {"research_questions": ["Jaký je zájem?", "Kdo je cílová skupina?"]},
        "tracked_objects": ["Značka A", "Značka B", "Značka C"],
        "sections": [{"id": "s1", "questions": [{"id": "q1", "text": "Znáte značku A?"}]}],
        "instrument_library": {"version": "17.1.2-instruments-v1.1"},
        "questionnaire_policy": {"max_questions": 25},
        "audience": {"mode": "population", "filters": {"vek": {"min": 18, "max": 65}}},
        "persona_mode": "calibrated",
        "persona_dimensions": ["hodnoty", "media", "nakupni_chovani"],
        "n": 300,
        "panel_mode": "STATIC",
        "model": "sonnet",
        "population_snapshot": {"panel_version": "v17_4_0"},
        "aggregation_policy": {"weighting": "vaha_strukturalni_2025"},
        "weighting": "vaha_strukturalni_2025",
        "validation_policy": {"require_benchmarks": True},
        "benchmarks": {"source": "CENSUS_2021"},
        "analysis_instructions": "Zaměřit se na segmenty.",
        "analysis_style": "consulting",
        "report_style": "client",
        "report_branding": {"logo": "brand/logo.png"},
        "report_language": "cs",
        "delivery": {"format": "docx"},
        "attachment_refs": ["ATT-1"],
        "data_context": {"has_client_data": False},
        "provider": "claude_code_subscription",
        "preferred_provider": "claude_code_subscription",
        "provider_policy": "CLAUDE_CODE_ONLY",
    }


@pytest.fixture
def simulation_project() -> dict[str, Any]:
    """A representative simulation project payload."""
    return {
        "schema_version": "simulation-project-v1",
        "title": "Test simulace",
        "goal": "Odhadnout dopad cenové změny",
        "scenario_contract": {"change": "cena -10 %", "horizon": "12m"},
        "analysis_instructions": "Porovnat varianty.",
        "report_style": "client",
        "report_branding": {"logo": "brand/logo.png"},
        "delivery": {"format": "docx"},
        "attachment_refs": [],
        "data_context": {},
        "simulation": {
            "context": "Trh reaguje na cenové změny se zpožděním.",
            "brief": "Cenová elasticita",
            "baseline": {"share": 0.21},
            "audience": {"mode": "population"},
            "dimensions": ["cenova_citlivost"],
            "change": "cena -10 %",
            "variants": [{"id": "v1", "change": "-5 %"}, {"id": "v2", "change": "-10 %"}],
            "worlds": [{"id": "w1", "seed": 1}, {"id": "w2", "seed": 2}],
            "n": 500,
            "model": "sonnet",
            "comparison_policy": {"primary_output": "delta"},
            "population_snapshot": {"panel_version": "v17_4_0"},
        },
    }
