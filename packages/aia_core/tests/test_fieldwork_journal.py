"""The fieldwork journal: answered respondent blocks, kept once per run lineage (RQC0).

An interrupted fieldwork attempt, or a retry of its run, replays what was answered from here
and pays only for what was not. Entries are the study's and the lineage's alone.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.fieldwork_journal import FieldworkJournal


def journal(
    scoped: Any, session: Session, *, study: str = "primary", lineage: str = "RUN-1"
) -> FieldworkJournal:
    return FieldworkJournal(session, scoped.scope(user="lead", study=study), lineage_run_id=lineage)


def test_an_answer_is_kept_once_within_its_lineage(scoped: Any, session: Session) -> None:
    mine = journal(scoped, session)
    assert mine.get("k1") is None
    kept = mine.put("k1", run_id="RUN-1", payload={"output": {"p": [0.2, 0.8]}})
    # A second write of the same request -- a raced or a replayed attempt -- keeps the first.
    assert mine.put("k1", run_id="RUN-2", payload={"output": {"p": [1.0, 0.0]}}) == kept
    assert mine.get("k1") == kept
    # A retry of the run shares its lineage, so it finds the answer.
    assert journal(scoped, session).get("k1") == kept
    assert journal(scoped, session).kept() == {"k1": kept}


def test_another_lineage_or_study_never_finds_it(scoped: Any, session: Session) -> None:
    journal(scoped, session).put("k1", run_id="RUN-1", payload={"n": 1})
    # A new run of the same study asks afresh: same request, different lineage.
    assert journal(scoped, session, lineage="RUN-9").get("k1") is None
    for study in ("sibling", "other_client"):
        other = journal(scoped, session, study=study)
        assert other.get("k1") is None
        assert other.put("k1", run_id="RUN-1", payload={"n": 2}) == {"n": 2}
    assert journal(scoped, session).get("k1") == {"n": 1}
    assert journal(scoped, session, lineage="RUN-9").kept() == {}


def test_only_a_study_scope_reaches_the_journal(scoped: Any, session: Session) -> None:
    client = scoped.resolver.client_work_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients["primary"].client_id
    )
    with pytest.raises(ScopeDenied):
        FieldworkJournal(session, client, lineage_run_id="RUN-1")  # type: ignore[arg-type]  # the refusal under test
