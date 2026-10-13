"""A validation Study's preregistration, kept once (panel-grounded-respondents 7e2)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import update

from aia_core.domain.evidence.validation import respondent_system_fingerprint
from aia_core.domain.holdout.bank import canonical_json
from aia_core.domain.holdout.preregistration import (
    ARMS,
    MODEL_ARMS,
    PREREGISTRATION_VERSION,
    THRESHOLDS,
    HoldoutRefused,
    Preregistration,
)
from aia_core.domain.holdout.scoring import SCORING_VERSION
from aia_core.domain.scope import ScopeDenied, StudyKind, StudyStatus
from aia_core.infrastructure.holdout_repository import HoldoutRepository
from aia_core.infrastructure.tables import HoldoutPreregistrationRow

SYSTEM = {
    "respondent_prompt_sha256": "c" * 64,
    "persona_builder": "panel-persona-1/profile-1",
    "persona_mode": "calibrated->core (no active profile)",
    "sampler_version": "sampler-1",
    "population_version": "pv_live",
    "model_binding": "bedrock/claude/bedrock-eu-primary",
    "response_process_version": "behavior-1/facts-1",
}


def _prereg(**overrides: Any) -> Preregistration:
    """A preregistration as ``preregister`` writes one, built by hand: the repository reads
    the record, and the split behind it is ``test_holdout_preregistration``'s to test."""
    document: dict[str, Any] = {
        "preregistration_version": PREREGISTRATION_VERSION,
        "bank_sha256": "b" * 64,
        "pool_sha256": "p" * 64,
        "split": {
            "seed": 20261013,
            "development_share": 0.4,
            "near_duplicate": 0.7,
            "development": ["d1", "d2"],
            "confirmation": ["c1", "c2", "c3"],
            "duplicates": [],
        },
        "blocks": [
            {
                "items": ["c1", "c2"],
                "excluded": [
                    {"field": "c1", "item": "c1", "reason": "ITEM", "association": None},
                    {"field": "c2", "item": "c2", "reason": "ITEM", "association": None},
                ],
                "signals": [],
            },
            {
                "items": ["c3"],
                "excluded": [{"field": "c3", "item": "c3", "reason": "ITEM", "association": None}],
                "signals": [],
            },
        ],
        "arms": list(ARMS),
        "model_arms": list(MODEL_ARMS),
        "n": 600,
        "sample_seed": 1,
        "replicate_seeds": [11, 12, 13],
        "bootstrap": {"seed": 7, "resamples": 10_000},
        "thresholds": dict(THRESHOLDS),
        "scoring_version": SCORING_VERSION,
        "population_version": SYSTEM["population_version"],
        "respondent_system": {
            "components": dict(SYSTEM),
            "fingerprint": respondent_system_fingerprint(SYSTEM),
        },
        "cost_ceiling_usd": 500.0,
    }
    document.update(overrides)
    return Preregistration(document=document)


@pytest.fixture
def holdout(session: Any, scoped: Any) -> Any:
    """A repository for a user's scope on a study: ``holdout(user=…, study=…)``."""
    return lambda **kw: HoldoutRepository(session, scoped.scope(**kw))


def test_a_preregistration_is_fixed_once_and_reads_back_as_fixed(scoped: Any, holdout: Any) -> None:
    repo = holdout()
    assert repo.preregistration() is None
    prereg = _prereg()
    stored = repo.record_preregistration(prereg)
    assert stored.sha256 == prereg.sha256
    assert stored.respondent_system_fingerprint == prereg.respondent_system_fingerprint
    assert stored.population_version == "pv_live"
    assert stored.created_by == scoped.users["lead"]
    assert stored.study_id == scoped.studies["primary"].study_id
    assert holdout(user="researcher").preregistration() == stored
    assert stored.preregistration.document == prereg.document


def test_the_same_record_again_is_the_stored_one_and_another_is_refused(holdout: Any) -> None:
    repo = holdout()
    first = repo.record_preregistration(_prereg())
    assert holdout(user="researcher").record_preregistration(_prereg()) == first
    with pytest.raises(HoldoutRefused) as refused:
        repo.record_preregistration(_prereg(sample_seed=2))
    assert refused.value.reason == "holdout_preregistration_recorded"
    assert repo.preregistration() == first


def test_a_preregistration_is_found_only_through_its_own_study(holdout: Any) -> None:
    holdout().record_preregistration(_prereg())
    assert holdout(study="sibling").preregistration() is None
    assert holdout(user="other_lead", study="other_client").preregistration() is None
    # A sibling fixes one of its own; neither sees the other's.
    sibling = holdout(study="sibling").record_preregistration(_prereg(sample_seed=2))
    assert holdout().preregistration() != sibling


def test_a_record_for_another_scoring_version_or_one_that_does_not_read_is_refused(
    holdout: Any,
) -> None:
    repo = holdout()
    with pytest.raises(HoldoutRefused) as stale:
        repo.record_preregistration(_prereg(scoring_version="aia-holdout-scoring-0"))
    assert stale.value.reason == "holdout_scoring_stale"
    with pytest.raises(HoldoutRefused) as malformed:
        repo.record_preregistration(_prereg(population_version="pv_other"))
    assert malformed.value.reason == "holdout_preregistration_malformed"
    assert repo.preregistration() is None


@pytest.mark.parametrize(
    "change",
    [
        {"content": canonical_json({**_prereg().document, "n": 601})},
        {"sha256": "0" * 64},
        {"respondent_system_fingerprint": "f" * 64},
        {"population_version": "pv_other"},
    ],
)
def test_a_row_changed_behind_aias_back_is_refused_never_read(
    session: Any, holdout: Any, change: dict[str, Any]
) -> None:
    holdout().record_preregistration(_prereg())
    session.execute(update(HoldoutPreregistrationRow).values(**change))
    session.expire_all()
    with pytest.raises(HoldoutRefused) as refused:
        holdout().preregistration()
    assert refused.value.reason == "holdout_preregistration_altered"


def test_a_closed_study_or_a_simulation_fixes_no_preregistration(scoped: Any, holdout: Any) -> None:
    scoped.studies["simulation"] = scoped.scope_repo.create_study(
        scoped.admin_context,
        client_id=scoped.clients["primary"].client_id,
        slug="scenarios",
        name="Acme scenarios",
        kind=StudyKind.SIMULATION,
    )
    with pytest.raises(HoldoutRefused) as refused:
        holdout(study="simulation").record_preregistration(_prereg())
    assert refused.value.reason == "holdout_not_research"
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        holdout().record_preregistration(_prereg())
    assert closed.value.reason == "study_closed"


def test_the_repository_needs_an_issued_study_context(session: Any) -> None:
    with pytest.raises(TypeError):
        HoldoutRepository(session, object())  # type: ignore[arg-type]
