"""The fieldwork event contract (RQC7), held to the case file the web reads."""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.fieldwork_events import (
    FIELDWORK_EVENTS_VERSION,
    HEARTBEAT_SECONDS,
    PAYLOAD_KEYS,
    FieldworkEvent,
    progress,
    progress_due,
)

CONTRACT = Path(__file__).parent / "fixtures" / "fieldwork_events" / "contract.json"


def test_the_contract_is_the_case_file_the_web_reads() -> None:
    file = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert file["version"] == FIELDWORK_EVENTS_VERSION
    assert file["events"] == {event.value: list(keys) for event, keys in PAYLOAD_KEYS.items()}
    assert set(progress(respondents=1, of=2, sent=3, replayed=4)) == set(
        PAYLOAD_KEYS[FieldworkEvent.PROGRESS]
    )


def test_progress_is_due_every_few_respondents_at_the_last_and_as_a_heartbeat() -> None:
    def due(n: int, idle: float = 0.0) -> bool:
        return progress_due(respondents=n, of=25, idle_seconds=idle, every=10)

    assert [n for n in range(26) if due(n)] == [10, 20, 25]
    assert due(3, idle=HEARTBEAT_SECONDS) and not due(3, idle=HEARTBEAT_SECONDS - 0.1)
    # A step configured to report every respondent, or nonsensically every 0, still reports.
    assert progress_due(respondents=1, of=5, idle_seconds=0, every=0)
