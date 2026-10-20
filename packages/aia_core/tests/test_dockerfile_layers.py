"""tools/dockerfile_layers.py: a source-only commit leaves the dependency layer alone.

The real Python Dockerfile keeps the rules; each rule fails a Dockerfile that breaks
it (.planning/plans/image-build-layers.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

DOCKERFILE = Path(__file__).resolve().parents[3] / "deploy/docker/python.Dockerfile"


@pytest.fixture(scope="module")
def layers(tool_loader: Any) -> Any:
    return tool_loader("dockerfile_layers")


@pytest.fixture(scope="module")
def text() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def test_the_python_dockerfile_keeps_every_rule(layers: Any, text: str) -> None:
    assert layers.check(text) == []


def test_sources_copied_into_the_dependency_stage_are_refused(layers: Any, text: str) -> None:
    broken = text.replace(
        "COPY apps/executors/pyproject.toml apps/executors/pyproject.toml\n",
        "COPY apps/executors/pyproject.toml apps/executors/pyproject.toml\n"
        "COPY packages/aia_core/src packages/aia_core/src\n",
        1,
    )
    assert broken != text
    assert layers.check(broken) == ["deps reads 'packages/aia_core/src' from the build context"]


def test_a_build_sha_above_the_venv_copy_is_refused(layers: Any, text: str) -> None:
    marker = "AS runtime\n"
    broken = text.replace(marker, marker + "ARG AIA_BUILD_SHA\n", 1)
    assert broken != text
    assert layers.check(broken) == ["runtime declares a per-commit argument: ARG AIA_BUILD_SHA"]


def test_a_build_sha_before_a_targets_last_layer_is_refused(layers: Any, text: str) -> None:
    marker = "FROM runtime AS worker\n"
    broken = text.replace(marker, marker + "ARG AIA_BUILD_TIME\n", 1)
    assert broken != text
    assert layers.check(broken) == ["worker declares ARG AIA_BUILD_TIME before a layer"]


def test_source_copied_into_the_runtime_stage_is_refused(layers: Any, text: str) -> None:
    marker = "COPY --from=deps /opt/venv /opt/venv\n"
    broken = text.replace(marker, marker + "COPY apps/api/src /src/apps/api/src\n", 1)
    assert broken != text
    assert layers.check(broken) == [
        "runtime copies from the build context: COPY apps/api/src /src/apps/api/src"
    ]
