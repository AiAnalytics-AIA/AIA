"""The web reads which acceptance rules a review was merged under as the report does.

The literature screen on Výsledky says a review predates today's acceptance rules from the sealed
bundle's ``versions.merge`` (review web#5), and its report with literature labels the findings
those rules would not accept from the same record (``contextual_report.literature_sections``:
``judged_topic`` and ``document_rules_of``). ``apps/web/src/lib/review-rules.ts`` ports both;
its test reads ``apps/web/src/lib/fixtures/review-rules.json`` as this one does, so the port and
the rules are checked against one file.
"""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.deep_research.document_types import DOCUMENT_RULES_PREFIX, document_rules_of
from aia_core.domain.deep_research.merge import MERGE_RULES_VERSION
from aia_core.domain.deep_research.topicality import TOPICALITY_PREFIX, judged_topic

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "apps/web/src/lib/fixtures/review-rules.json"


def test_the_fixture_names_the_prefixes_and_the_merge_version_of_today() -> None:
    body = json.loads(FIXTURE.read_text("utf-8"))
    assert body["topicality_prefix"] == TOPICALITY_PREFIX
    assert body["document_rules_prefix"] == DOCUMENT_RULES_PREFIX
    assert body["current"] == MERGE_RULES_VERSION


def test_each_case_reads_as_the_report_reads_it() -> None:
    body = json.loads(FIXTURE.read_text("utf-8"))
    assert body["cases"], "the fixture holds cases"
    for case in body["cases"]:
        assert judged_topic(case["merge"]) is case["topic"], case
        assert (document_rules_of(case["merge"]) is not None) is case["documents"], case
