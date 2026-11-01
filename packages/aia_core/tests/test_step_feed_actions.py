"""The engine's recovery actions, held to the case file the web words each of (FLD11)."""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.workflow import RecoveryAction

CASES = Path(__file__).parent / "fixtures" / "step_feed" / "actions.json"


def test_every_recovery_action_is_in_the_case_file_the_web_words() -> None:
    actions = json.loads(CASES.read_text(encoding="utf-8"))["actions"]
    assert sorted(actions) == sorted(a.value for a in RecoveryAction)
