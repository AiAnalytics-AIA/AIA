"""The experimental Sociomapping's internal draft (plan sociomapping-engine I2), composed.

The DOCX itself is rendered and opened under the real worker in
``apps/executors/tests/test_sociomapping_executors.py``; here, what the composer refuses and
what the document says.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from aia_core.application.sociomapping_report import (
    SociomappingReportRefused,
    compose_sociomapping_report,
    limitation_text,
)
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.project import ProjectType
from aia_core.domain.report.model import (
    Approval,
    Callout,
    CalloutKind,
    Classification,
    ReportKind,
    ReportMeta,
    SociomapFigure,
    Table,
)
from aia_core.domain.workflow_templates import RESEARCH, steps_for_workflow

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[3] / "apps/web/src/lib/fixtures/sociomapping.json").read_text(
        "utf-8"
    )
)["sociomapping"]
META = ReportMeta(
    kind=ReportKind.INTERNAL,
    title="Sociomapping — experimentální metoda AIA",
    subtitle="Interní pracovní koncept",
    client_name="Fiktivní klient",
    study_name="Fiktivní studie",
    study_id="STU-1",
    issued_on=date(2026, 10, 5),
    revision=1,
    method_status=METHOD_STATUS_PENDING,
    classification=Classification.INTERNAL,
)
PNG = b"\x89PNG\r\n\x1a\n"


def _compose(result: dict[str, Any] = FIXTURE, meta: ReportMeta = META) -> Any:
    images = {b["battery_id"]: PNG for b in result["batteries"]}
    return compose_sociomapping_report(result, meta, images, (("Běh", "RUN-1"),))


def test_the_draft_says_what_it_is_and_carries_fit_relations_and_provenance() -> None:
    document = _compose()
    blocks = [b for s in document.sections for b in s.blocks]
    provisional = next(
        b for b in blocks if isinstance(b, Callout) and b.kind is CalloutKind.PROVISIONAL
    )
    assert "nikoli ověřené rekonstrukce SOMECS" in provisional.content[0].text  # type: ignore[union-attr]
    [figure] = [b for b in blocks if isinstance(b, SociomapFigure)]
    assert figure.methodology_status == "EXPERIMENTAL_AIA" and figure.stress_1 is None
    assert figure.fit_caption and "aia_hmodel_accuracy_v1" in figure.fit_caption
    tables = {b.id: b for b in blocks if isinstance(b, Table)}
    assert {t.split("-")[2] for t in tables if t.startswith("tab-sociomapping-")} >= {
        "objects",
        "relations",
        "fit",
        "provenance",
    }
    relations = tables["tab-sociomapping-relations-1"]
    printed = [c.text for row in relations.rows for c in row.cells]  # type: ignore[union-attr]
    assert any(p.startswith("\u22120,") for p in printed)  # negative r printed signed (U+2212)
    assert "nedefinováno" in printed  # the constant object's relations stay undefined
    assert tables["tab-sociomapping-objects-1"].notes  # the unplaced object is named
    assert document.ledger.rows == {}  # nothing here is admitted evidence
    assert [s.id for s in document.sections][-1] == "app-audit"


@pytest.mark.parametrize(
    ("result", "meta", "why"),
    [
        (FIXTURE, replace(META, kind=ReportKind.CLIENT), "internally only"),
        (
            FIXTURE,
            replace(META, approvals=(Approval("X", date(2026, 10, 5)),)),
            "never approved",
        ),
        ({**FIXTURE, "client_facing": True}, META, "does not say it is experimental"),
        ({**FIXTURE, "method_status": "CLIENT_FACING"}, META, "does not say it is experimental"),
    ],
)
def test_the_composer_refuses_anything_but_an_internal_unapproved_experimental_draft(
    result: dict[str, Any], meta: ReportMeta, why: str
) -> None:
    with pytest.raises(SociomappingReportRefused, match=why):
        _compose(result, meta)


def test_every_limitation_in_the_fixture_has_wording_and_its_question() -> None:
    for item in FIXTURE["batteries"][0]["limitations"]:
        text = limitation_text(item)
        assert text and not text.startswith(item["code"])
        if item["question"]:
            assert f"Otevřená otázka {item['question']}." in text


def test_the_research_graph_gains_the_two_steps_only_with_the_switch() -> None:
    plain = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH)
    assert [s.node_key for s in plain][-1] == "sociomap"
    on = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH, sociomapping_enabled=True)
    added = {s.node_key: s for s in on[len(plain) :]}
    assert list(added) == ["sociomapping", "sociomapping_report"]
    assert added["sociomapping"].depends_on == ("run",)
    assert added["sociomapping"].stage_type == "ANALYSIS"
    assert added["sociomapping_report"].depends_on == ("sociomapping",)
    assert added["sociomapping_report"].stage_type == "REPORT"
