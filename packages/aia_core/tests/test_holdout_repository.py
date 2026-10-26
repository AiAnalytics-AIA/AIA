"""A validation Study's preregistration and confirmation, kept once (7e2, 7e3)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import update

from aia_core.domain.holdout.bank import canonical_json
from aia_core.domain.holdout.preregistration import HoldoutRefused
from aia_core.domain.scope import ScopeDenied, StudyKind, StudyStatus
from aia_core.infrastructure.holdout_repository import HoldoutRepository
from aia_core.infrastructure.tables import HoldoutPreregistrationRow


@pytest.fixture
def prereg(holdout_records: Any) -> Any:
    """``prereg(**overrides)``: the hand-built preregistration (conftest)."""
    return holdout_records.preregistration


@pytest.fixture
def holdout(session: Any, scoped: Any) -> Any:
    """A repository for a user's scope on a study: ``holdout(user=…, study=…)``."""
    return lambda **kw: HoldoutRepository(session, scoped.scope(**kw))


def test_a_preregistration_is_fixed_once_and_reads_back_as_fixed(
    prereg: Any, scoped: Any, holdout: Any
) -> None:
    repo = holdout()
    assert repo.preregistration() is None
    prereg = prereg()
    stored = repo.record_preregistration(prereg)
    assert stored.sha256 == prereg.sha256
    assert stored.respondent_system_fingerprint == prereg.respondent_system_fingerprint
    assert stored.population_version == "pv_live"
    assert stored.created_by == scoped.users["lead"]
    assert stored.study_id == scoped.studies["primary"].study_id
    assert holdout(user="researcher").preregistration() == stored
    assert stored.preregistration.document == prereg.document


def test_the_same_record_again_is_the_stored_one_and_another_is_refused(
    prereg: Any, holdout: Any
) -> None:
    repo = holdout()
    first = repo.record_preregistration(prereg())
    assert holdout(user="researcher").record_preregistration(prereg()) == first
    with pytest.raises(HoldoutRefused) as refused:
        repo.record_preregistration(prereg(sample_seed=2))
    assert refused.value.reason == "holdout_preregistration_recorded"
    assert repo.preregistration() == first


def test_a_preregistration_is_found_only_through_its_own_study(prereg: Any, holdout: Any) -> None:
    holdout().record_preregistration(prereg())
    assert holdout(study="sibling").preregistration() is None
    assert holdout(user="other_lead", study="other_client").preregistration() is None
    # A sibling fixes one of its own; neither sees the other's.
    sibling = holdout(study="sibling").record_preregistration(prereg(sample_seed=2))
    assert holdout().preregistration() != sibling


def test_a_record_for_another_scoring_version_or_one_that_does_not_read_is_refused(
    prereg: Any,
    holdout: Any,
) -> None:
    repo = holdout()
    with pytest.raises(HoldoutRefused) as stale:
        repo.record_preregistration(prereg(scoring_version="aia-holdout-scoring-0"))
    assert stale.value.reason == "holdout_scoring_stale"
    with pytest.raises(HoldoutRefused) as malformed:
        repo.record_preregistration(prereg(population_version="pv_other"))
    assert malformed.value.reason == "holdout_preregistration_malformed"
    assert repo.preregistration() is None


@pytest.mark.parametrize(
    "change",
    [
        lambda p: {"content": canonical_json({**p.document, "n": 601})},
        lambda p: {"sha256": "0" * 64},
        lambda p: {"respondent_system_fingerprint": "f" * 64},
        lambda p: {"population_version": "pv_other"},
    ],
)
def test_a_row_changed_behind_aias_back_is_refused_never_read(
    prereg: Any, session: Any, holdout: Any, change: Any
) -> None:
    holdout().record_preregistration(prereg())
    session.execute(update(HoldoutPreregistrationRow).values(**change(prereg())))
    session.expire_all()
    with pytest.raises(HoldoutRefused) as refused:
        holdout().preregistration()
    assert refused.value.reason == "holdout_preregistration_altered"


def test_a_closed_study_or_a_simulation_fixes_no_preregistration(
    prereg: Any, scoped: Any, holdout: Any
) -> None:
    scoped.studies["simulation"] = scoped.scope_repo.create_study(
        scoped.admin_context,
        client_id=scoped.clients["primary"].client_id,
        slug="scenarios",
        name="Acme scenarios",
        kind=StudyKind.SIMULATION,
    )
    with pytest.raises(HoldoutRefused) as refused:
        holdout(study="simulation").record_preregistration(prereg())
    assert refused.value.reason == "holdout_not_research"
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        holdout().record_preregistration(prereg())
    assert closed.value.reason == "study_closed"


def test_the_repository_needs_an_issued_study_context(session: Any) -> None:
    with pytest.raises(TypeError):
        HoldoutRepository(session, object())  # type: ignore[arg-type]


def test_a_deleted_clients_confirmation_still_holds_its_system(
    session: Any, prereg: Any, holdout: Any, scoped: Any
) -> None:
    # OI-232: a confirmation is a respondent system's once per organization. Deleting its
    # client keeps the record (content-free), so a second Study cannot start confirming
    # the same system and keep the run that passes.
    from aia_core.infrastructure.holdout_repository import erase_client_holdouts
    from aia_core.infrastructure.tables import HoldoutConfirmationRow

    record = prereg()
    first = holdout().record_preregistration(record)
    holdout().record_confirmation(run_id="RUN-first0001", preregistration_sha256=first.sha256)
    erase_client_holdouts(session, client_id=scoped.clients["primary"].client_id)

    kept = session.get(HoldoutConfirmationRow, scoped.studies["primary"].study_id)
    assert kept is not None and kept.run_id == "RUN-first0001"
    gone = session.get(HoldoutPreregistrationRow, scoped.studies["primary"].study_id)
    assert gone is not None and gone.content == b""  # the preregistration's content erased

    other = holdout(study="other_client")
    second = other.record_preregistration(record)
    with pytest.raises(HoldoutRefused) as refused:
        other.record_confirmation(run_id="RUN-second001", preregistration_sha256=second.sha256)
    assert refused.value.reason == "holdout_system_confirmation_started"
