"""The journal of the client's own work: answered model requests, kept once (K2d).

A step resumed after a budget lift or a worker's release replays what was answered
from here and pays only for what was not. Entries are the client's alone.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.scope import ClientWorkContext, ScopeDenied
from aia_core.infrastructure.client_work_journal import ClientWorkJournal


def work_scope(scoped: Any, client: str = "primary") -> ClientWorkContext:
    return scoped.resolver.client_work_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients[client].client_id
    )


def test_an_answer_is_kept_once_and_found_only_by_its_client(scoped: Any, session: Session) -> None:
    mine = ClientWorkJournal(session, work_scope(scoped))
    assert mine.get("k1") is None
    kept = mine.put("k1", run_id="RUN-1", payload={"output": {"proposals": []}, "n": 1})
    assert kept == {"output": {"proposals": []}, "n": 1}
    # A second write of the same request keeps the first answer.
    assert mine.put("k1", run_id="RUN-2", payload={"n": 2}) == kept
    assert mine.get("k1") == kept
    # Another client's journal has no such entry, and may write its own under the key.
    theirs = ClientWorkJournal(session, work_scope(scoped, "other"))
    assert theirs.get("k1") is None
    assert theirs.put("k1", run_id="RUN-3", payload={"n": 3}) == {"n": 3}
    assert mine.get("k1") == kept


def test_only_the_client_work_scope_reaches_the_journal(scoped: Any, session: Session) -> None:
    study = scoped.scope(user="lead", study="primary")
    with pytest.raises(ScopeDenied):
        ClientWorkJournal(session, study)  # type: ignore[arg-type]
