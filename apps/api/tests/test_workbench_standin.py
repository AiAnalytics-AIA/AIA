"""The workbench's API stand-in (tools/ui_workbench/api_standin.py) runs research as asked.

The workbench's worker and API share one SQLite file and one artifact directory;
the fieldwork source recorded on a run is the stand-in's ``--fieldwork``. The
production answer, ``ai_runtime``, is its default -- the develop routing proof
relies on it to show a run parking -- and the fictional source is set only by
the workbench, in the ``local`` environment it always runs in (ADR 0016).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from aia_core.domain.fieldwork import FieldworkSource

REPO = Path(__file__).resolve().parents[3]


def _standin() -> ModuleType:
    path = REPO / "tools" / "ui_workbench" / "api_standin.py"
    spec = importlib.util.spec_from_file_location("ui_workbench_api_standin", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_by_default_a_run_is_recorded_for_the_ai_runtime(tmp_path: Path) -> None:
    app, *_ = _standin().build(tmp_path / "aia.sqlite")
    settings = app.state.settings
    assert settings.research_fieldwork_source is FieldworkSource.AI_RUNTIME
    assert settings.env.value == "local"
    assert settings.storage_backend == "filesystem"
    assert settings.storage_root == str(tmp_path / "artifacts")


def test_the_workbench_records_the_fictional_source_in_the_shared_store(tmp_path: Path) -> None:
    app, *_ = _standin().build(
        tmp_path / "aia.sqlite", artifacts=tmp_path / "shared", fieldwork="synthetic_fixture"
    )
    settings = app.state.settings
    assert settings.research_fieldwork_source is FieldworkSource.SYNTHETIC_FIXTURE
    assert settings.storage_root == str(tmp_path / "shared")


def test_the_population_double_mode_offers_the_panel_and_refuses_the_fixture(
    tmp_path: Path,
) -> None:
    """``--population-double`` (run-qc-and-checkpoint RQC6d): the double composed and the panel
    offered, so readiness draws a panel run's sample; the fixture fieldwork, which the panel is
    never offered under, refused by name."""
    standin = _standin()
    app, *_ = standin.build(tmp_path / "aia.sqlite", population_double=True)
    settings = app.state.settings
    assert settings.population_double and settings.ai_population_personas_enabled
    assert settings.research_fieldwork_source is FieldworkSource.AI_RUNTIME
    with pytest.raises(SystemExit):
        standin.main(["--population-double", "--fieldwork", "synthetic_fixture"])


def test_the_report_editor_runs_against_the_stand_in_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``AIA_WORKBENCH_REPORT_EDITOR=true`` (artifact-report RPT8d): the editor on, at the stand-in
    Document Server's fictional origins, its saves read from the local folder; off otherwise."""
    standin = _standin()
    off, *_ = standin.build(tmp_path / "off.sqlite")
    assert not off.state.settings.report_editor_on
    assert getattr(off.state, "editor_fetcher", None) is None

    monkeypatch.setenv("AIA_WORKBENCH_REPORT_EDITOR", "true")
    on, *_ = standin.build(tmp_path / "on.sqlite")
    assert on.state.settings.report_editor_on
    assert on.state.settings.onlyoffice_url == "https://docs.workbench.invalid"
    assert type(on.state.editor_fetcher).__name__ == "WorkbenchSaves"
