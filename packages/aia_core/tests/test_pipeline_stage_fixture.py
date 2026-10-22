"""The research pipeline's stage ids as the web reads them (working-copy-edit-ops WCE7d).

apps/web/src/lib/working-impact.ts maps every one of these to a workbench stage; its test reads the
same file, so a stage added or renamed here fails one side or the other, never neither.
"""

import json
from pathlib import Path

from aia_core.domain.pipeline import stage_ids

FIXTURE = Path(__file__).parent / "fixtures" / "pipeline_stages" / "stages.json"


def test_the_fixture_holds_the_research_pipelines_stage_ids_in_order() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["research"] == stage_ids("research")
