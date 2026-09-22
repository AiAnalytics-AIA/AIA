"""The vendored Sociomapping golden fixtures are the reference's, byte for byte.

F1-F9 are the parity evidence for :mod:`aia_core.domain.sociomap`. A fixture
edited here -- to make a failing comparison pass, or by an over-helpful
formatter -- would turn the parity tests into tests of themselves. These checks
pin every vendored file to the SHA256 recorded in ``index.json``, which was taken
from ``AiAnalytics-AIA/AIA-reference`` at the commit the index names.

Re-vendoring is deliberate: copy the files from the reference repository, update
``index.json`` in the same commit, and say why in the commit body.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sociomap"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
REFERENCE_ZIP_SHA256 = "86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216"


def test_index_names_the_authoritative_reference() -> None:
    assert INDEX["reference_repository"] == "AiAnalytics-AIA/AIA-reference"
    assert INDEX["reference_commit"] == "678e298ad9ca0263da53cc8920d153fdfb956c93"
    assert INDEX["reference_zip_sha256"] == REFERENCE_ZIP_SHA256


def test_every_sociomapping_fixture_f1_to_f9_is_vendored() -> None:
    prefixes = sorted(fid.split("_", 1)[0] for fid in INDEX["fixtures"])
    assert prefixes == [f"F{i}" for i in range(1, 10)]


def test_no_unindexed_fixture_file_is_present() -> None:
    indexed = {entry["file"] for entry in INDEX["fixtures"].values()}
    present = {p.name for p in FIXTURES.glob("*.json")} - {"index.json"}
    assert present == indexed


@pytest.mark.parametrize("fixture_id", sorted(INDEX["fixtures"]))
def test_vendored_fixture_matches_its_recorded_hash(fixture_id: str) -> None:
    entry = INDEX["fixtures"][fixture_id]
    actual = hashlib.sha256((FIXTURES / entry["file"]).read_bytes()).hexdigest()
    assert actual == entry["sha256"], f"{entry['file']} has been edited since it was vendored"


@pytest.mark.parametrize("fixture_id", sorted(INDEX["fixtures"]))
def test_fixture_documents_agree_with_the_index(fixture_id: str) -> None:
    entry = INDEX["fixtures"][fixture_id]
    document: dict[str, Any] = json.loads((FIXTURES / entry["file"]).read_text(encoding="utf-8"))
    assert document["fixture_id"] == fixture_id
    assert document["reference_zip_sha256"] == REFERENCE_ZIP_SHA256
    assert document["parity_type"] == entry["parity_type"]
    assert document["tolerance"] == entry["tolerance"]


def test_the_loader_fixture_resolves_by_short_id(sociomap_fixture: Any) -> None:
    assert sociomap_fixture("F7")["fixture_id"] == "F7_terrain66_respondent_density"
