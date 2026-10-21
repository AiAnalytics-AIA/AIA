"""The section-source manifest (artifact-chain CHN1).

Every section of a stored report names what it was composed from, the evidence refs it prints are
added from its blocks, ``fixed`` text is the methodology's guidance alone, the run's outputs no
section read are named, the manifest is stored with the document model and printed in the audit,
and the internal sample's manifest is pinned in a committed fixture.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from report_samples import AGGREGATE, KINDS, OUTPUTS, SOCIOMAPPING, build

from aia_core.application.report import beside_outputs
from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.analysis.steps import analysis_node_key
from aia_core.domain.report.document_model import (
    DocumentModelInvalid,
    document_bytes,
    document_payload,
    read_document_payload,
)
from aia_core.domain.report.model import (
    ArtifactSource,
    AuditBlock,
    BesideOutput,
    FixedSource,
    LedgerSource,
)
from aia_core.domain.report.sources import (
    AUDIT_SECTION_ID,
    report_sources,
    source_payload,
    with_source_audit,
)
from aia_core.domain.report.validation import cited_refs, section_refs

FIXTURE = Path(__file__).parent / "fixtures" / "report_sources" / "internal.json"


@pytest.mark.parametrize("kind", KINDS)
def test_every_section_of_the_four_sample_reports_names_a_source(
    kind: str, report_ledger: Any
) -> None:
    manifest = report_sources(build(kind, report_ledger))

    for entry in manifest.sections:
        assert entry.sources, f"{kind}: {entry.section_id} names no source"


@pytest.mark.parametrize("kind", KINDS)
def test_fixed_text_is_only_the_methodology_guidance(kind: str, report_ledger: Any) -> None:
    for entry in report_sources(build(kind, report_ledger)).sections:
        fixed = [s for s in entry.sources if isinstance(s, FixedSource)]
        assert not fixed or entry.section_id == "methodology", entry.section_id


@pytest.mark.parametrize("kind", KINDS)
def test_a_sections_evidence_is_what_its_blocks_print(kind: str, report_ledger: Any) -> None:
    document = build(kind, report_ledger)
    manifest = report_sources(document)

    for section, entry in zip(document.sections, manifest.sections, strict=True):
        ledger = [s for s in entry.sources if isinstance(s, LedgerSource)]
        if entry.section_id == "app-evidence":
            # The evidence appendix lists every ref the document prints.
            assert ledger == [LedgerSource(cited_refs(document))]
        elif section_refs(section, document.ledger):
            assert ledger == [LedgerSource(section_refs(section, document.ledger))]
        else:
            assert ledger == []


def test_the_run_outputs_no_section_read_are_named(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    manifest = report_sources(document)

    # The internal sample's chapters never read the aggregate: the audit names it, but listing is
    # not reading (review of #621), so it is unread beside the Sociomapping no section reads.
    assert manifest.unread == (AGGREGATE, SOCIOMAPPING)
    # One a section reads is not unread; one made beside the report always is.
    beside = BesideOutput("sociomapping_report", "research_sociomapping_report")
    reread = report_sources(replace(document, outputs=(*OUTPUTS, beside)))
    assert reread.unread == (AGGREGATE, SOCIOMAPPING, beside)


def test_the_manifest_is_stored_with_the_document_model(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    payload = read_document_payload(document_bytes(document))
    manifest = report_sources(document)

    for stored, entry in zip(payload["sections"], manifest.sections, strict=True):
        assert stored["sources"] == [source_payload(s) for s in entry.sources]
    assert payload["unread"] == [
        {
            "kind": "artifact",
            "artifact_type": a.artifact_type,
            "artifact_id": a.artifact_id,
            "sha256": a.sha256,
        }
        for a in (AGGREGATE, SOCIOMAPPING)
    ]


def test_a_client_deliverable_stores_an_artifacts_type_without_its_id(report_ledger: Any) -> None:
    """Its document drops the run's identifiers (RD5a); so does its manifest."""
    payload = document_payload(build("client", report_ledger))

    stored = [s for section in payload["sections"] for s in section["sources"]]
    artifacts = [s for s in stored if s["kind"] == "artifact"]
    assert artifacts
    assert all(set(s) == {"kind", "artifact_type"} for s in artifacts)
    assert all(set(s) == {"kind", "artifact_type"} for s in payload["unread"])


def test_a_document_stored_before_the_manifest_is_still_read(report_ledger: Any) -> None:
    payload = document_payload(build("internal", report_ledger))
    older = {
        **payload,
        "contract": "aia-report-document-1",
        "sections": [{k: v for k, v in s.items() if k != "sources"} for s in payload["sections"]],
    }
    older.pop("unread")

    read = read_document_payload(json.dumps(older).encode())

    assert read["contract"] == "aia-report-document-1"
    assert "unread" not in read
    with pytest.raises(DocumentModelInvalid):
        read_document_payload(json.dumps({**older, "contract": "aia-report-document-0"}).encode())


@pytest.mark.parametrize("kind", ["internal", "documentation"])
def test_the_audit_prints_every_sections_sources_and_the_unread(
    kind: str, report_ledger: Any
) -> None:
    document = build(kind, report_ledger)
    audit = next(s for s in document.sections if s.id == AUDIT_SECTION_ID)
    (block,) = [b for b in audit.blocks if isinstance(b, AuditBlock)]
    rows = dict(block.entries)

    for section in document.sections:
        if section.id != AUDIT_SECTION_ID:
            assert f"Zdroje · {section.title}" in rows
    assert SOCIOMAPPING.artifact_id in rows["Nepřečtené výstupy běhu"]
    # A document without an audit appendix is left as it is; its model stores the manifest.
    client = build("client", report_ledger)
    assert with_source_audit(client) == client


def test_the_internal_samples_manifest_matches_its_fixture(report_ledger: Any) -> None:
    """The manifest of ``make report-preview``'s internal sample. Regenerate on purpose only:
    ``AIA_REGENERATE_REPORT_SOURCES=1 pytest packages/aia_core/tests/test_report_sources.py``."""
    payload = document_payload(build("internal", report_ledger))
    manifest = {
        "sections": [{"id": s["id"], "sources": s["sources"]} for s in payload["sections"]],
        "unread": payload["unread"],
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if os.environ.get("AIA_REGENERATE_REPORT_SOURCES") == "1":
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(text, encoding="utf-8")
    assert FIXTURE.read_text(encoding="utf-8") == text


def test_the_steps_beside_the_report_are_named_by_the_graph_not_by_their_state() -> None:
    steps = [
        {"node_key": key, "kind": key, "status": "QUEUED"}
        for key in (
            "compile",
            "preflight",
            "run",
            "aggregate",
            "sociomap",
            *(analysis_node_key(m.module_id) for m in ANALYSIS_MODULES),
            "report",
        )
    ]
    assert beside_outputs(steps) == ()

    experimental = [
        {"node_key": "sociomapping", "kind": "research_sociomapping", "status": "SUCCEEDED"},
        {"node_key": "sociomapping_report", "kind": "research_sociomapping_report"},
    ]
    assert beside_outputs([*steps, *experimental]) == (
        BesideOutput("sociomapping", "research_sociomapping"),
        BesideOutput("sociomapping_report", "research_sociomapping_report"),
    )


def test_an_artifact_source_is_named_by_id_and_content() -> None:
    source = ArtifactSource("research_aggregate", "art-1", "a" * 64)
    assert source_payload(source) == {
        "kind": "artifact",
        "artifact_type": "research_aggregate",
        "artifact_id": "art-1",
        "sha256": "a" * 64,
    }
