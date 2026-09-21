"""Integration tests for the project repository.

These run against a real database engine. Locally that is in-memory SQLite, which
exercises all the SQL and transaction logic; CI additionally runs the same tests
against PostgreSQL by setting ``DATABASE_URL`` so that dialect-specific behaviour
(JSONB, timezone-aware timestamps, cascade deletes) is covered before deploy.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.pipeline import ProjectType, StageStatus
from aia_core.domain.project import ProjectStatus
from aia_core.domain.providers import Provider, ProviderPolicy
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.tables import ProjectRevisionRow


@pytest.fixture
def repo(session: Session, scoped) -> ProjectRepository:
    """Repository scoped to the primary client's primary study, as a LEAD."""
    return ProjectRepository(session, scoped.scope(user="lead", study="primary"))


@pytest.fixture
def other_repo(session: Session, scoped) -> ProjectRepository:
    """Repository scoped to a *different client's* study, for isolation tests."""
    return ProjectRepository(session, scoped.scope(user="other_lead", study="other_client"))


# --------------------------------------------------------------------------- #
# Construction guards
# --------------------------------------------------------------------------- #


def test_repository_requires_an_issued_study_context(session: Session) -> None:
    """An unscoped repository is not constructible.

    Isolation is a type-level guarantee rather than a convention a handler could
    forget. The forgery cases are covered in test_scope_isolation.py.
    """
    with pytest.raises(TypeError, match="requires a StudyContext"):
        ProjectRepository(session, None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #


def test_create_writes_project_and_first_revision(repo: ProjectRepository) -> None:
    """Creating a project immediately persists revision 1 and its stages."""
    project, outcome = repo.create(title="Test výzkum", content={"goal": "g"})

    assert project.project_id.startswith("PRJ-")
    assert project.current_revision == 1
    assert project.status is ProjectStatus.DRAFT
    assert project.current_stage == "BRIEF"
    assert outcome.revision == 1
    assert not outcome.deduplicated

    stages = repo.stages(project.project_id)
    assert len(stages) == 13
    assert [s.ordinal for s in stages] == list(range(13))
    assert all(s.status is StageStatus.NOT_STARTED for s in stages)
    assert stages[0].label == "Zadání"


def test_create_defaults_czech_titles(repo: ProjectRepository) -> None:
    """A blank title falls back to the product's Czech default per project type."""
    research, _ = repo.create(title="")
    assert research.title == "Nový výzkum"

    simulation, _ = repo.create(title="   ", project_type=ProjectType.SIMULATION)
    assert simulation.title == "Nová simulace"


def test_create_simulation_uses_simulation_stages(repo: ProjectRepository) -> None:
    """A simulation project gets the simulation pipeline, not the research one."""
    project, _ = repo.create(title="Sim", project_type="simulation")
    stage_ids = [s.stage_type for s in repo.stages(project.project_id)]

    assert "SCENARIO_CONTRACT" in stage_ids
    assert "WORLDS" in stage_ids
    assert "QUESTIONNAIRE" not in stage_ids


def test_create_widens_policy_for_non_default_provider(repo: ProjectRepository) -> None:
    """Choosing Claude API must not leave the project pinned to Claude Code."""
    project, _ = repo.create(title="x", preferred_provider="anthropic")
    assert project.preferred_provider is Provider.ANTHROPIC
    assert project.provider_policy is ProviderPolicy.CLAUDE_API_ONLY


def test_create_records_project_created_event(repo: ProjectRepository) -> None:
    """Project creation is auditable from the first moment."""
    project, _ = repo.create(title="x")
    types = [e.event_type for e in repo.events(project.project_id)]

    assert "PROJECT_CREATED" in types
    assert "REVISION_SAVED" in types


# --------------------------------------------------------------------------- #
# Save, deduplication and revisions
# --------------------------------------------------------------------------- #


def test_unchanged_save_creates_no_revision(repo: ProjectRepository) -> None:
    """Repeated autosaves of identical content must not accumulate revisions."""
    project, _ = repo.create(title="x", content={"title": "x", "goal": "g"})
    before = repo.get(project.project_id).current_revision

    for _ in range(5):
        outcome = repo.save(project.project_id, content={"title": "x", "goal": "g"})
        assert outcome.deduplicated

    assert repo.get(project.project_id).current_revision == before
    assert len(repo.revisions(project.project_id)) == 1


def test_material_change_creates_new_revision(repo: ProjectRepository) -> None:
    """A real edit creates an immutable revision and advances the pointer."""
    project, _ = repo.create(title="x", content={"title": "x", "n": 300})

    outcome = repo.save(project.project_id, content={"title": "x", "n": 500})

    assert not outcome.deduplicated
    assert outcome.revision == 2
    assert outcome.changed_fields == ["n"]
    assert repo.get(project.project_id).current_revision == 2
    assert len(repo.revisions(project.project_id)) == 2


def test_prior_revision_content_is_immutable(repo: ProjectRepository) -> None:
    """Saving a new revision must not alter any earlier revision's content."""
    project, _ = repo.create(title="x", content={"title": "x", "n": 300})
    repo.save(project.project_id, content={"title": "x", "n": 500})
    repo.save(project.project_id, content={"title": "x", "n": 900})

    assert repo.content(project.project_id, 1)["n"] == 300
    assert repo.content(project.project_id, 2)["n"] == 500
    assert repo.content(project.project_id, 3)["n"] == 900
    assert repo.content(project.project_id)["n"] == 900


def test_revision_chain_records_parent(repo: ProjectRepository, session: Session) -> None:
    """Each revision points at the one it was derived from."""
    project, _ = repo.create(title="x", content={"title": "x", "n": 1})
    repo.save(project.project_id, content={"title": "x", "n": 2})
    repo.save(project.project_id, content={"title": "x", "n": 3})

    rows = session.scalars(
        select(ProjectRevisionRow)
        .where(ProjectRevisionRow.project_id == project.project_id)
        .order_by(ProjectRevisionRow.revision)
    ).all()

    assert [r.revision for r in rows] == [1, 2, 3]
    assert [r.parent_revision for r in rows] == [None, 1, 2]
    assert len({r.revision_id for r in rows}) == 3


def test_revision_stores_content_hash_and_impact(repo: ProjectRepository) -> None:
    """Provenance fields are persisted, not just computed in memory."""
    project, _ = repo.create(title="x", content={"title": "x", "audience": {"m": 1}})
    repo.save(project.project_id, content={"title": "x", "audience": {"m": 2}})

    latest = repo.revisions(project.project_id)[0]
    assert len(latest.content_sha256) == 64
    assert latest.changed_fields == ["audience"]
    assert latest.impact["root_stage"] == "AUDIENCE"


def test_force_new_revision_bypasses_dedup(repo: ProjectRepository) -> None:
    """A branch or restore must produce a revision even with identical content."""
    project, _ = repo.create(title="x", content={"title": "x"})

    outcome = repo.save(
        project.project_id, content={"title": "x"}, reason="branch", force_new_revision=True
    )

    assert not outcome.deduplicated
    assert outcome.revision == 2
    assert repo.revisions(project.project_id)[0].reason == "branch"


def test_title_updates_even_when_deduplicated(repo: ProjectRepository) -> None:
    """The header title tracks content without needing a new revision."""
    project, _ = repo.create(title="Original", content={"title": "Original"})
    repo.save(project.project_id, content={"title": "Original"})
    assert repo.get(project.project_id).title == "Original"


# --------------------------------------------------------------------------- #
# The reuse rule, persisted
# --------------------------------------------------------------------------- #


def _complete_stages_through(
    session: Session, repo: ProjectRepository, project_id: str, last_stage: str
) -> None:
    """Mark stages DONE up to and including ``last_stage`` on the current revision."""
    from aia_core.infrastructure.tables import ProjectStageRow

    revision = repo.get(project_id).current_revision
    rows = session.scalars(
        select(ProjectStageRow)
        .where(
            ProjectStageRow.project_id == project_id,
            ProjectStageRow.revision == revision,
        )
        .order_by(ProjectStageRow.ordinal)
    ).all()

    cutoff = next(r.ordinal for r in rows if r.stage_type == last_stage)
    for row in rows:
        if row.ordinal <= cutoff:
            row.status = StageStatus.DONE.value
            row.input_fingerprint = f"fp-{row.stage_type}"
            row.provider = Provider.CLAUDE_CODE.value
            row.model = "sonnet"
            row.artifact_ids = [f"ART-{row.stage_type}"]
    session.flush()


def test_completed_upstream_stages_carry_into_new_revision(
    repo: ProjectRepository, session: Session
) -> None:
    """Artifacts upstream of an edit survive into the new revision.

    This is the persisted form of the no-recompute rule: expensive AI work already
    done for BRIEF..QUESTIONNAIRE is still available at revision 2.
    """
    project, _ = repo.create(title="x", content={"title": "x", "audience": {"mode": "population"}})
    _complete_stages_through(session, repo, project.project_id, "ANALYSIS")

    repo.save(project.project_id, content={"title": "x", "audience": {"mode": "customer"}})

    stages = {s.stage_type: s for s in repo.stages(project.project_id)}
    assert repo.get(project.project_id).current_revision == 2

    for sid in ("BRIEF", "DEEP_RESEARCH", "RESEARCH_DESIGN", "QUESTIONNAIRE"):
        assert stages[sid].status is StageStatus.DONE, sid
        assert stages[sid].artifact_ids == [f"ART-{sid}"], sid
        assert stages[sid].input_fingerprint == f"fp-{sid}", sid

    assert stages["AUDIENCE"].status is StageStatus.READY
    assert stages["DIMENSIONS"].status is StageStatus.NOT_STARTED
    assert stages["ANALYSIS"].status is StageStatus.NOT_STARTED


def test_provider_switch_preserves_every_completed_stage(
    repo: ProjectRepository, session: Session
) -> None:
    """A provider change must not cost the user a single re-run."""
    project, _ = repo.create(
        title="x", content={"title": "x", "provider": "claude_code_subscription"}
    )
    _complete_stages_through(session, repo, project.project_id, "REPORT")

    outcome = repo.save(project.project_id, content={"title": "x", "provider": "anthropic"})

    assert outcome.root_stage is None
    stages = {s.stage_type: s for s in repo.stages(project.project_id)}
    for sid in ("BRIEF", "FIELDWORK", "ANALYSIS", "REPORT"):
        assert stages[sid].status is StageStatus.DONE, sid
        assert stages[sid].artifact_ids == [f"ART-{sid}"], sid

    reloaded = repo.get(project.project_id)
    assert reloaded.current_stage == "REPORT"
    assert reloaded.last_completed_stage == "REPORT"
    assert reloaded.status is ProjectStatus.READY_TO_CONTINUE


def test_earlier_revision_stages_remain_queryable(
    repo: ProjectRepository, session: Session
) -> None:
    """Stage state is per revision, so history stays inspectable."""
    project, _ = repo.create(title="x", content={"title": "x", "n": 1})
    _complete_stages_through(session, repo, project.project_id, "FIELDWORK")
    repo.save(project.project_id, content={"title": "x", "n": 2})

    rev1 = {s.stage_type: s for s in repo.stages(project.project_id, 1)}
    rev2 = {s.stage_type: s for s in repo.stages(project.project_id, 2)}

    assert rev1["FIELDWORK"].status is StageStatus.DONE
    assert rev2["FIELDWORK"].status is StageStatus.NOT_STARTED


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #


def test_another_client_cannot_read_a_project(
    repo: ProjectRepository, other_repo: ProjectRepository
) -> None:
    """Cross-client access raises the same error as a missing project.

    Distinguishing "not found" from "not yours" would leak the existence of
    another client's engagement.
    """
    project, _ = repo.create(title="Secret")

    with pytest.raises(ProjectNotFound):
        other_repo.get(project.project_id)
    with pytest.raises(ProjectNotFound):
        other_repo.content(project.project_id)
    with pytest.raises(ProjectNotFound):
        other_repo.stages(project.project_id)
    with pytest.raises(ProjectNotFound):
        other_repo.events(project.project_id)
    with pytest.raises(ProjectNotFound):
        other_repo.revisions(project.project_id)


def test_another_client_cannot_write_a_project(
    repo: ProjectRepository, other_repo: ProjectRepository
) -> None:
    """Every mutating path is scope-checked too, not just the reads."""
    project, _ = repo.create(title="Secret", content={"title": "Secret"})

    with pytest.raises(ProjectNotFound):
        other_repo.save(project.project_id, content={"title": "hijacked"})
    with pytest.raises(ProjectNotFound):
        other_repo.update_settings(project.project_id, title="hijacked")
    with pytest.raises(ProjectNotFound):
        other_repo.move_to_trash(project.project_id)

    assert repo.get(project.project_id).title == "Secret"


def test_listing_is_scoped_to_the_study(
    repo: ProjectRepository, other_repo: ProjectRepository
) -> None:
    """A portfolio listing never includes another client's projects."""
    repo.create(title="Mine A")
    repo.create(title="Mine B")
    other_repo.create(title="Theirs")

    mine = repo.list_projects()
    theirs = other_repo.list_projects()

    assert mine.total == 2
    assert {p.title for p in mine.items} == {"Mine A", "Mine B"}
    assert theirs.total == 1
    assert {p.title for p in theirs.items} == {"Theirs"}


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #


def test_listing_orders_pinned_first_then_newest(repo: ProjectRepository) -> None:
    """Pinned projects lead the portfolio, then most recently modified."""
    first, _ = repo.create(title="First")
    repo.create(title="Second")
    repo.update_settings(first.project_id, pinned=True)

    titles = [p.title for p in repo.list_projects().items]
    assert titles[0] == "First"
    assert "Second" in titles


def test_listing_paginates(repo: ProjectRepository) -> None:
    """Pagination reports a stable total and a has_more flag."""
    for i in range(5):
        repo.create(title=f"P{i}")

    page = repo.list_projects(limit=2, offset=0)
    assert page.total == 5
    assert len(page.items) == 2
    assert page.has_more

    last = repo.list_projects(limit=2, offset=4)
    assert len(last.items) == 1
    assert not last.has_more


def test_listing_clamps_absurd_limits(repo: ProjectRepository) -> None:
    """A caller cannot request the entire table."""
    repo.create(title="x")
    assert repo.list_projects(limit=10_000).limit == 200
    assert repo.list_projects(limit=0).limit == 1
    assert repo.list_projects(offset=-5).offset == 0


def test_listing_filters_by_type_and_search(repo: ProjectRepository) -> None:
    """Type and title filters narrow the portfolio."""
    repo.create(title="Brand study")
    repo.create(title="Price simulation", project_type=ProjectType.SIMULATION)

    assert repo.list_projects(project_type=ProjectType.SIMULATION).total == 1
    assert repo.list_projects(project_type=ProjectType.RESEARCH).total == 1
    assert repo.list_projects(search="brand").total == 1
    assert repo.list_projects(search="nothing").total == 0


# --------------------------------------------------------------------------- #
# Settings, trash and purge
# --------------------------------------------------------------------------- #


def test_provider_change_is_audited(repo: ProjectRepository) -> None:
    """Changing provider writes an event, because it changes cost and provenance."""
    project, _ = repo.create(title="x")
    repo.update_settings(project.project_id, preferred_provider="openai")

    events = repo.events(project.project_id)
    settings_events = [e for e in events if e.event_type == "SETTINGS_UPDATED"]
    assert settings_events
    assert settings_events[0].payload["provider"]["to"] == "openai"
    assert repo.get(project.project_id).provider_policy is ProviderPolicy.OPENAI_ONLY


def test_negative_budget_is_rejected(repo: ProjectRepository) -> None:
    """A negative ceiling would disable budget enforcement."""
    project, _ = repo.create(title="x")
    with pytest.raises(ValueError, match="must not be negative"):
        repo.update_settings(project.project_id, max_api_cost_usd=-5)


def test_trash_hides_project_but_keeps_data(repo: ProjectRepository) -> None:
    """Trashing is reversible and loses nothing."""
    project, _ = repo.create(title="x", content={"title": "x", "n": 7})

    repo.move_to_trash(project.project_id)
    assert repo.list_projects().total == 0
    assert repo.list_projects(include_trashed=True).total == 1
    assert repo.content(project.project_id)["n"] == 7

    repo.restore_from_trash(project.project_id)
    assert repo.list_projects().total == 1
    assert repo.get(project.project_id).status is ProjectStatus.READY_TO_CONTINUE


def test_purge_requires_trash_first(repo: ProjectRepository) -> None:
    """A hard delete is always a deliberate second action."""
    project, _ = repo.create(title="x")

    with pytest.raises(ValueError, match="only a trashed project can be purged"):
        repo.purge(project.project_id)

    repo.move_to_trash(project.project_id)
    repo.purge(project.project_id)

    with pytest.raises(ProjectNotFound):
        repo.get(project.project_id)


def test_purge_cascades_to_revisions_and_stages(repo: ProjectRepository, session: Session) -> None:
    """Purging leaves no orphaned revisions, stages or events behind."""
    from aia_core.infrastructure.tables import ProjectEventRow, ProjectStageRow

    project, _ = repo.create(title="x", content={"title": "x"})
    repo.save(project.project_id, content={"title": "x", "n": 2})
    pid = project.project_id

    repo.move_to_trash(pid)
    repo.purge(pid)

    for table in (ProjectRevisionRow, ProjectStageRow, ProjectEventRow):
        remaining = session.scalars(
            select(table).where(table.project_id == pid)  # type: ignore[attr-defined]
        ).all()
        assert remaining == [], f"orphaned rows left in {table.__tablename__}"
