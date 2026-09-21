"""Characterization tests for project revision and stage carry-forward rules.

These encode the prototype's durability contract as executable specification:

* an autosave with unchanged content creates no revision;
* a material edit creates a new immutable revision;
* completed stages upstream of the change carry forward with their artifacts;
* the changed stage reopens and everything downstream restarts;
* a provider switch preserves the entire pipeline.

The rules are tested against the pure planner so they hold regardless of the
storage backend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.pipeline import ProjectType, StageStatus, impact_preview
from aia_core.domain.project import (
    Project,
    ProjectRevision,
    ProjectStatus,
    StageState,
    carry_forward_stages,
    initial_stages,
    new_project_id,
    new_revision_id,
    plan_save,
    resolve_provider_defaults,
)
from aia_core.domain.providers import Provider, ProviderPolicy


def _completed_through(project_type: Any, last_stage: str) -> list[StageState]:
    """Build a stage list where every stage up to and including ``last_stage`` is DONE."""
    stages = initial_stages(project_type)
    ids = [s.stage_type for s in stages]
    cutoff = ids.index(last_stage)
    out: list[StageState] = []
    for stage in stages:
        if stage.ordinal <= cutoff:
            out.append(
                stage.model_copy(
                    update={
                        "status": StageStatus.DONE,
                        "input_fingerprint": f"fp-{stage.stage_type}",
                        "provider": Provider.CLAUDE_CODE,
                        "model": "sonnet",
                        "artifact_ids": [f"ART-{stage.stage_type}"],
                        "started_at": datetime(2026, 1, 1, tzinfo=UTC),
                        "finished_at": datetime(2026, 1, 2, tzinfo=UTC),
                    }
                )
            )
        else:
            out.append(stage)
    return out


@pytest.fixture
def saved_project() -> Project:
    """A research project that already has one revision."""
    return Project(
        project_id="PRJ-test",
        title="Test výzkum",
        project_type=ProjectType.RESEARCH,
        current_revision=3,
        current_stage="ANALYSIS",
        status=ProjectStatus.READY_TO_CONTINUE,
    )


# --------------------------------------------------------------------------- #
# Identity and validation
# --------------------------------------------------------------------------- #


def test_generated_ids_match_legacy_format() -> None:
    """Ids keep the prototype's recognisable prefixes and lengths."""
    pid = new_project_id()
    assert pid.startswith("PRJ-")
    assert len(pid) == len("PRJ-") + 14

    rid = new_revision_id()
    assert rid.startswith("REV-")
    assert len(rid) == len("REV-") + 16

    assert new_project_id() != new_project_id()


def test_project_rejects_blank_title() -> None:
    """A project must be identifiable in a portfolio list."""
    with pytest.raises(ValidationError):
        Project(title="   ")


def test_project_rejects_negative_budget() -> None:
    """A negative cost ceiling would disable budget enforcement entirely."""
    with pytest.raises(ValidationError):
        Project(title="x", max_api_cost_usd=-1.0)


def test_project_rejects_unknown_fields() -> None:
    """Strict models stop silent data loss when a caller misspells a field."""
    with pytest.raises(ValidationError):
        Project(title="x", currentRevision=2)  # type: ignore[call-arg]


def test_revision_numbering_starts_at_one() -> None:
    """Revision 0 means 'no content yet' and must never be persisted as a revision."""
    with pytest.raises(ValidationError):
        ProjectRevision(revision=0, content_sha256="x", content={})


def test_simulation_project_uses_simulation_pipeline() -> None:
    """Project type selects the stage list."""
    sim = Project(title="s", project_type=ProjectType.SIMULATION)
    assert "SCENARIO_CONTRACT" in sim.stage_ids
    assert "QUESTIONNAIRE" not in sim.stage_ids
    assert sim.default_title() == "Nová simulace"

    res = Project(title="r")
    assert "QUESTIONNAIRE" in res.stage_ids
    assert res.default_title() == "Nový výzkum"


# --------------------------------------------------------------------------- #
# Provider defaults
# --------------------------------------------------------------------------- #


def test_non_default_provider_widens_default_policy() -> None:
    """Choosing Claude API must not leave the project pinned to Claude Code."""
    provider, policy = resolve_provider_defaults(
        preferred_provider="anthropic", provider_policy=None
    )
    assert provider is Provider.ANTHROPIC
    assert policy is ProviderPolicy.CLAUDE_API_ONLY


def test_explicit_policy_is_respected() -> None:
    """An explicitly chosen policy is never widened."""
    provider, policy = resolve_provider_defaults(
        preferred_provider="claude_code", provider_policy="CLAUDE_CODE_THEN_API"
    )
    assert provider is Provider.CLAUDE_CODE
    assert policy is ProviderPolicy.CLAUDE_CODE_THEN_API


# --------------------------------------------------------------------------- #
# First save
# --------------------------------------------------------------------------- #


def test_first_save_creates_revision_one_with_fresh_stages() -> None:
    """A new project's first save starts at revision 1 with nothing completed."""
    project = Project(title="Nový výzkum")
    outcome = plan_save(
        project=project,
        content={"title": "Nový výzkum", "goal": "g"},
        previous_content=None,
        previous_stages=None,
        reason="project_created",
    )

    assert outcome.revision == 1
    assert not outcome.deduplicated
    assert outcome.root_stage is None
    assert outcome.current_stage == "BRIEF"
    assert outcome.project_status is ProjectStatus.DRAFT
    assert all(s.status is StageStatus.NOT_STARTED for s in outcome.stages)
    assert len(outcome.stages) == 13


# --------------------------------------------------------------------------- #
# Deduplication
# --------------------------------------------------------------------------- #


def test_unchanged_autosave_deduplicates(saved_project: Project) -> None:
    """Re-saving identical content must not burn a revision.

    The UI autosaves aggressively; without this rule a project would accumulate
    hundreds of identical revisions.
    """
    content = {"title": "Test výzkum", "goal": "g", "n": 300}
    outcome = plan_save(
        project=saved_project,
        content=dict(content),
        previous_content=dict(content),
        previous_stages=_completed_through("research", "ANALYSIS"),
    )

    assert outcome.deduplicated
    assert outcome.revision == 3, "revision pointer must not advance"
    assert outcome.stages == []
    assert outcome.current_stage == saved_project.current_stage


def test_key_order_does_not_defeat_deduplication(saved_project: Project) -> None:
    """Content equality is by value, so dict ordering cannot force a revision."""
    outcome = plan_save(
        project=saved_project,
        content={"goal": "g", "title": "t", "n": 300},
        previous_content={"n": 300, "title": "t", "goal": "g"},
        previous_stages=[],
    )
    assert outcome.deduplicated


def test_force_new_revision_overrides_deduplication(saved_project: Project) -> None:
    """An explicit branch/restore must create a revision even with equal content."""
    content = {"title": "t", "goal": "g"}
    outcome = plan_save(
        project=saved_project,
        content=dict(content),
        previous_content=dict(content),
        previous_stages=_completed_through("research", "ANALYSIS"),
        reason="branch",
        force_new_revision=True,
    )

    assert not outcome.deduplicated
    assert outcome.revision == 4
    assert outcome.changed_fields == []


# --------------------------------------------------------------------------- #
# The core reuse rule
# --------------------------------------------------------------------------- #


def test_material_edit_reopens_only_affected_stages(saved_project: Project) -> None:
    """Editing the audience preserves upstream work and reopens from AUDIENCE.

    This is the rule that saves the most money: questionnaire design and deep
    research already cost AI calls, and an audience change must not repeat them.
    """
    previous = {"title": "t", "audience": {"mode": "population"}, "n": 300}
    current = {"title": "t", "audience": {"mode": "customer"}, "n": 300}

    outcome = plan_save(
        project=saved_project,
        content=current,
        previous_content=previous,
        previous_stages=_completed_through("research", "ANALYSIS"),
    )

    assert outcome.revision == 4
    assert outcome.changed_fields == ["audience"]
    assert outcome.root_stage == "AUDIENCE"
    assert outcome.project_status is ProjectStatus.READY_TO_CONTINUE
    assert outcome.current_stage == "AUDIENCE"

    by_id = {s.stage_type: s for s in outcome.stages}

    # Upstream work survives with its artifacts and fingerprints intact.
    for sid in ("BRIEF", "DEEP_RESEARCH", "RESEARCH_DESIGN", "QUESTIONNAIRE"):
        assert by_id[sid].status is StageStatus.DONE, sid
        assert by_id[sid].artifact_ids == [f"ART-{sid}"], sid
        assert by_id[sid].input_fingerprint == f"fp-{sid}", sid

    # The changed stage reopens.
    assert by_id["AUDIENCE"].status is StageStatus.READY
    assert by_id["AUDIENCE"].artifact_ids == []

    # Everything downstream restarts, even though it had completed.
    for sid in ("DIMENSIONS", "SAMPLE_PLAN", "FIELDWORK", "AGGREGATION", "ANALYSIS"):
        assert by_id[sid].status is StageStatus.NOT_STARTED, sid
        assert by_id[sid].artifact_ids == [], sid


def test_provider_switch_preserves_all_completed_work(saved_project: Project) -> None:
    """Switching provider mid-project must not discard a single artifact.

    A user who exhausts their Claude Code quota continues on the Claude API. If this
    invalidated work, the switch would re-run and re-charge the whole pipeline.
    """
    previous = {"title": "t", "provider": "claude_code_subscription", "n": 300}
    current = {"title": "t", "provider": "anthropic", "n": 300}
    completed = _completed_through("research", "ANALYSIS")

    outcome = plan_save(
        project=saved_project,
        content=current,
        previous_content=previous,
        previous_stages=completed,
    )

    assert outcome.changed_fields == ["provider"]
    assert outcome.root_stage is None, "a provider switch must invalidate nothing"
    assert outcome.current_stage == "ANALYSIS"
    assert outcome.last_completed_stage == "ANALYSIS"

    by_id = {s.stage_type: s for s in outcome.stages}
    for stage in completed:
        if stage.status is StageStatus.DONE:
            assert by_id[stage.stage_type].status is StageStatus.DONE
            assert by_id[stage.stage_type].artifact_ids == stage.artifact_ids


def test_presentation_edit_preserves_fieldwork_and_analysis(saved_project: Project) -> None:
    """A report styling change reopens REPORT onward only."""
    outcome = plan_save(
        project=saved_project,
        content={"title": "t", "report_style": "internal"},
        previous_content={"title": "t", "report_style": "client"},
        previous_stages=_completed_through("research", "REPORT"),
    )

    assert outcome.root_stage == "REPORT"
    assert outcome.impact["presentation_only"] is True

    by_id = {s.stage_type: s for s in outcome.stages}
    assert by_id["FIELDWORK"].status is StageStatus.DONE
    assert by_id["ANALYSIS"].status is StageStatus.DONE
    assert by_id["REPORT"].status is StageStatus.READY


def test_incomplete_upstream_stage_is_not_carried_forward(saved_project: Project) -> None:
    """Only genuinely completed stages carry forward.

    A stage that was RUNNING or FAILED has no trustworthy artifact, so it must
    restart rather than appear finished in the new revision.
    """
    stages = _completed_through("research", "QUESTIONNAIRE")
    by_id = {s.stage_type: s for s in stages}
    stages = [
        s.model_copy(update={"status": StageStatus.FAILED, "artifact_ids": []})
        if s.stage_type == "DEEP_RESEARCH"
        else s
        for s in stages
    ]

    outcome = plan_save(
        project=saved_project,
        content={"title": "t", "audience": {"mode": "customer"}},
        previous_content={"title": "t", "audience": {"mode": "population"}},
        previous_stages=stages,
    )

    result = {s.stage_type: s for s in outcome.stages}
    assert result["BRIEF"].status is StageStatus.DONE
    assert result["DEEP_RESEARCH"].status is StageStatus.NOT_STARTED
    assert by_id["QUESTIONNAIRE"].status is StageStatus.DONE
    assert result["QUESTIONNAIRE"].status is StageStatus.DONE


def test_done_with_warnings_carries_forward(saved_project: Project) -> None:
    """DONE_WITH_WARNINGS is a completed state and its artifacts are reusable."""
    stages = _completed_through("research", "QUESTIONNAIRE")
    stages = [
        s.model_copy(update={"status": StageStatus.DONE_WITH_WARNINGS})
        if s.stage_type == "RESEARCH_DESIGN"
        else s
        for s in stages
    ]

    outcome = plan_save(
        project=saved_project,
        content={"title": "t", "audience": {"mode": "customer"}},
        previous_content={"title": "t", "audience": {"mode": "population"}},
        previous_stages=stages,
    )

    result = {s.stage_type: s for s in outcome.stages}
    assert result["RESEARCH_DESIGN"].status is StageStatus.DONE_WITH_WARNINGS
    assert result["RESEARCH_DESIGN"].artifact_ids == ["ART-RESEARCH_DESIGN"]


def test_carry_forward_drops_live_execution_pointers() -> None:
    """A carried stage must not inherit the old revision's job or waiting state.

    Otherwise a new revision would look parked on a quota that no longer applies,
    or point at a job belonging to a previous revision.
    """
    stages = _completed_through("research", "BRIEF")
    stages = [
        s.model_copy(
            update={
                "current_job_id": "JOB-old",
                "waiting_reason": "claude_code_quota",
                "quota_reset_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        )
        if s.stage_type == "BRIEF"
        else s
        for s in stages
    ]

    carried = carry_forward_stages(
        previous=stages,
        project_type="research",
        impact=impact_preview("research", ["audience"]),
    )

    brief = next(s for s in carried if s.stage_type == "BRIEF")
    assert brief.status is StageStatus.DONE
    assert brief.current_job_id is None
    assert brief.waiting_reason is None
    assert brief.quota_reset_at is None


def test_explicit_stage_forces_rerun_without_content_change(saved_project: Project) -> None:
    """A user asking to rerun from a stage gets a revision even with equal content."""
    content = {"title": "t", "goal": "g"}
    outcome = plan_save(
        project=saved_project,
        content=dict(content),
        previous_content=dict(content),
        previous_stages=_completed_through("research", "ANALYSIS"),
        explicit_stage="FIELDWORK",
    )

    assert not outcome.deduplicated
    assert outcome.root_stage == "FIELDWORK"

    by_id = {s.stage_type: s for s in outcome.stages}
    assert by_id["SAMPLE_PLAN"].status is StageStatus.DONE
    assert by_id["FIELDWORK"].status is StageStatus.READY
    assert by_id["ANALYSIS"].status is StageStatus.NOT_STARTED


def test_stage_ordinals_follow_current_pipeline_definition(saved_project: Project) -> None:
    """Carried stages are renumbered so a pipeline change cannot corrupt a revision."""
    stale = _completed_through("research", "QUESTIONNAIRE")
    stale = [s.model_copy(update={"ordinal": 99, "label": "stale"}) for s in stale]

    outcome = plan_save(
        project=saved_project,
        content={"title": "t", "audience": {"mode": "customer"}},
        previous_content={"title": "t", "audience": {"mode": "population"}},
        previous_stages=stale,
    )

    assert [s.ordinal for s in outcome.stages] == list(range(13))
    brief = next(s for s in outcome.stages if s.stage_type == "BRIEF")
    assert brief.label == "Zadání"


def test_simulation_project_carry_forward() -> None:
    """The same rules apply to the simulation pipeline with its own stages."""
    project = Project(
        project_id="PRJ-sim",
        title="Sim",
        project_type=ProjectType.SIMULATION,
        current_revision=2,
    )

    outcome = plan_save(
        project=project,
        content={"title": "Sim", "variants": [{"id": "v2"}]},
        previous_content={"title": "Sim", "variants": [{"id": "v1"}]},
        previous_stages=_completed_through("simulation", "WORLDS"),
    )

    assert outcome.root_stage == "VARIANTS"
    by_id = {s.stage_type: s for s in outcome.stages}
    assert by_id["BASELINE"].status is StageStatus.DONE
    assert by_id["SCENARIO_CONTRACT"].status is StageStatus.DONE
    assert by_id["VARIANTS"].status is StageStatus.READY
    assert by_id["WORLDS"].status is StageStatus.NOT_STARTED


def test_content_hash_recorded_for_every_revision(saved_project: Project) -> None:
    """Every outcome carries the content hash used for deduplication and provenance."""
    outcome = plan_save(
        project=saved_project,
        content={"title": "t", "n": 400},
        previous_content={"title": "t", "n": 300},
        previous_stages=[],
    )
    assert len(outcome.content_sha256) == 64
    assert outcome.content_sha256 != ""
