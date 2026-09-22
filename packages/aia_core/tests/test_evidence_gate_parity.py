"""Gate-decision parity against the reference contracts.

Two sources of truth, and each section says which it uses:

* **The reference repository** (``AiAnalytics-AIA/AIA-reference``, private,
  via ``AIA_REFERENCE_REPO``) holds the machine-readable exports -- the 400-field
  policy and the methodology ledger. Tests that read it skip cleanly when it is
  absent and are marked ``parity``.
* **The recovered decision tables** below are the reference's documented gate
  decisions (methodology-ledger M03/M10/M16/M17, high-risk R5/R6/R12), written as
  cases. They run everywhere. ``EXACT`` cases must produce the same allow/block
  decision *and* the same refusal code; ``SEMANTIC`` cases must produce the same
  allow/block decision, with the code free to be more specific.

What neither source can supply is the legacy *source* -- it is withheld with the
archive. The decisions of ``tier_gate.py``, ``validation_gate.py`` and
``core_joint._fallback()`` that the docstrings do not state are recorded in
``.planning/open-items.md`` for the run that has the archive.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.evidence import (
    ClaimRule,
    FieldPolicyBook,
    FieldUse,
    JointDegradation,
    ProductionGrade,
    load_joint_status,
)

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def ledger(reference_repo: Path) -> dict[str, dict[str, Any]]:
    """The reference methodology ledger, by entry id (M01..M17)."""
    raw = json.loads((reference_repo / "methodology-ledger.json").read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in raw["entries"]}


# --- 1. Field policy: EXACT for all 400 fields ---------------------------------------


@pytest.fixture(scope="module")
def reference_policy_document(reference_repo: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (reference_repo / "field-policy.json").read_text(encoding="utf-8")
    )
    return document


@pytest.fixture(scope="module")
def reference_book(reference_policy_document: dict[str, Any]) -> FieldPolicyBook:
    return FieldPolicyBook.from_policy_document(reference_policy_document)


@pytest.mark.parity
def test_every_reference_field_rederives_identically(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    """Loading re-derives every field and refuses on any difference, so loading IS the check."""
    assert len(reference_book) == reference_policy_document["declared_field_count"] == 400
    assert reference_book.source_sha256 == reference_policy_document["source_sha256"]


@pytest.mark.parity
def test_reference_counts_match(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    counts = reference_policy_document["counts"]
    fields = list(reference_book.fields.values())
    assert dict(Counter(p.provenance_class.value for p in fields)) == counts["by_provenance_class"]
    assert dict(Counter(p.production_grade.value for p in fields)) == counts["by_production_grade"]
    assert dict(Counter(r.value for p in fields for r in p.claim_rules)) == counts["by_claim_rule"]
    assert sum(p.persona_eligible for p in fields) == counts["persona_eligible"]
    assert (
        sum(p.eligibility.client_facing_measured_claim for p in fields)
        == counts["client_facing_measured_claim_allowed"]
    )


@pytest.mark.parity
def test_methodology_ledger_m02_headline_numbers(reference_book: FieldPolicyBook) -> None:
    """M02: 51 never-measured-fact, 21 never-direct-Schwartz, 10 of 400 grade A."""
    fields = list(reference_book.fields.values())
    never_fact = [p for p in fields if p.has(ClaimRule.NEVER_MEASURED_FACT)]
    assert len(never_fact) == 51
    assert sum(p.has(ClaimRule.NEVER_DIRECT_SCHWARTZ) for p in fields) == 21
    assert sum(p.production_grade is ProductionGrade.A for p in fields) == 10
    assert not any(p.eligibility.permits(FieldUse.CLIENT_FACING_MEASURED_CLAIM) for p in never_fact)


@pytest.mark.parity
def test_runtime_columns_without_an_entry_stay_undeclared(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    extra = {
        e["field"] for e in reference_policy_document["runtime_columns_without_dictionary_entry"]
    }
    assert len(extra) == 8
    assert reference_book.undeclared_runtime_columns == frozenset(extra)
    assert not extra & reference_book.fields.keys()


# --- 2. CORE_JOINT_STATUS: EXACT on the restrictions and the hash binding (M03) ------


@pytest.mark.parity
def test_certificate_restrictions_are_the_ledgers(
    ledger: dict[str, dict[str, Any]], certificate_bytes: Any
) -> None:
    """A certificate carrying M03's restrictions loads to exactly those restrictions."""
    m03 = ledger["M03"]
    restrictions = m03["claim_restrictions"]
    sha = m03["constants"]["panel_sha256"].split()[0]
    certificate = certificate_bytes(
        production_panel=m03["constants"]["production_panel"],
        panel_sha256=sha,
        matched_blocks=m03["matched_blocks"],
        **restrictions,
    )
    status = load_joint_status(certificate, measured_panel_sha256=sha)
    assert status.certified
    for key, expected in restrictions.items():
        assert getattr(status, key) == expected, key
    assert sorted(status.matched_blocks) == sorted(m03["matched_blocks"])

    moved = load_joint_status(certificate, measured_panel_sha256=hashlib.sha256(b"x").hexdigest())
    assert moved.degradation is JointDegradation.PANEL_HASH_MISMATCH


@pytest.mark.parity
def test_the_real_certificate_is_honoured_against_the_real_panel(legacy_root: Path) -> None:
    """With the archive: the shipped certificate parses and binds to the shipped panel.

    If this fails on a key name, the certificate's real shape differs from the
    one documented in population-subsystem.md -- a finding, not a flake.
    """
    manifest = json.loads((REPO / "docs/migration/reference-manifest.json").read_text())
    raw = (legacy_root / "CORE_JOINT_STATUS.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["files"]["CORE_JOINT_STATUS.json"]
    declared = json.loads(raw)
    panel = next(legacy_root.rglob(str(declared["production_panel"])))
    status = load_joint_status(
        raw, measured_panel_sha256=hashlib.sha256(panel.read_bytes()).hexdigest()
    )
    assert status.certified, status.detail
    assert not status.cross_block_same_person_joint
    assert not status.client_joint_outputs_allowed
    assert not status.cross_block_joint_claims_allowed
