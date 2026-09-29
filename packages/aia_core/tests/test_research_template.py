"""The research template is the 18.6.6 unit's empty project, served by AIA (ADR 0018).

The web client's stages complete every document with the template's defaults
(``defaultsMerge``), so a template that drifted from the unit's would change what a
new Study starts with and what an old one is read as. The capture is the unit's own
``GET /api/bootstrap`` answer, the fixture the web client's parity tests read.
"""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.research_template import research_template

REPO = Path(__file__).resolve().parents[3]
CAPTURE = REPO / "apps" / "web" / "src" / "research" / "fixtures" / "empty-project.json"


def test_the_template_is_the_units_empty_project() -> None:
    assert research_template() == json.loads(CAPTURE.read_text("utf-8"))


def test_each_template_is_a_fresh_copy() -> None:
    first = research_template()
    first["briefing"]["situation"] = "changed"
    first["sections"].append({"id": "s1"})
    again = research_template()
    assert again["briefing"]["situation"] == ""
    assert again["sections"] == []
