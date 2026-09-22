"""`tools/dev_seed.py` provisions through the real authorisation path, and only locally.

The seed is what the web client's vertical slice runs against, so it must write a
world the API accepts -- grants the resolver honours, projects whose stages are
whatever the domain initialises -- and it must refuse any non-local environment.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "dev_seed.py"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dev_seed", TOOL_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("env", ["production", "staging", "development"])
def test_it_refuses_a_non_local_environment(
    tool: ModuleType, env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIA_ENV", env)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    assert tool.main() == 2


def test_it_requires_a_database_url(tool: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_ENV", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert tool.main() == 2


def test_it_seeds_a_world_the_resolver_honours(
    tool: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.pipeline import StageStatus
    from aia_core.domain.scope import ScopeRole
    from aia_core.infrastructure.db import create_app_engine, create_session_factory
    from aia_core.infrastructure.repositories import ProjectRepository
    from aia_core.infrastructure.scope_repository import ScopeRepository
    from aia_core.infrastructure.tables import Base

    url = f"sqlite:///{tmp_path / 'seed.db'}"
    engine = create_app_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("AIA_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", url)

    assert tool.main() == 0
    retail_id, tariff_id = json.loads(capsys.readouterr().out)["studies"]

    with create_session_factory(engine)() as s:
        repo, resolver = ScopeRepository(s), ScopeResolver(s)
        user = repo.upsert_user(email=tool.OWNER)
        (org_id,) = repo.memberships_for_user(user["user_id"])
        principal = AuthenticatedPrincipal(user_id=user["user_id"], organization_id=org_id)
        lead = resolver.study_context(principal, study_id=retail_id)
        viewer = resolver.study_context(principal, study_id=tariff_id)
        assert lead.role is ScopeRole.LEAD
        assert viewer.role is ScopeRole.VIEWER

        projects = ProjectRepository(s, lead)
        page = projects.list_projects()
        assert sorted(p.project_type.value for p in page.items) == ["research", "simulation"]
        for p in page.items:
            # The seed never hand-sets run state.
            assert {st.status for st in projects.stages(p.project_id)} == {StageStatus.NOT_STARTED}
    engine.dispose()
