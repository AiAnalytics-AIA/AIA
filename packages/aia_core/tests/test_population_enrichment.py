"""The ANALYSIS view's seven runtime dimensions against 18.6.6's own ``attach_derived`` (2d).

``tests/fixtures/enrichment/expected.json`` is what the unit's unmodified
``audience_dimensions.enrich_panel`` returned on fictional rows, read as the unit reads its panel
(``tools/enrichment_capture.py``). Every comparison is EXACT, cell by cell.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.population import CZ_SYNTHETIC_V17, ParsedPanel
from aia_core.domain.population.enrichment import (
    DERIVED_FIELDS,
    AudienceDimensionsEnricher,
    EnrichmentInputMissing,
)

FIXTURES = Path(__file__).parent / "fixtures" / "enrichment"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _panel(name: str) -> ParsedPanel:
    """A fixture file as AIA's parser holds a panel: exact text, an empty cell as None."""
    reader = csv.reader(io.StringIO((FIXTURES / name).read_text("utf-8")))
    header, *rows = list(reader)
    columns = tuple(
        tuple(None if row[i] == "" else row[i] for row in rows) for i in range(len(header))
    )
    return ParsedPanel(header=tuple(header), columns=columns, row_count=len(rows))


def test_the_fixture_is_pinned_to_its_inputs_and_the_unit_source() -> None:
    for name, entry in EXPECTED["files"].items():
        assert _sha(FIXTURES / name) == entry["sha256"], name
    for name, sha in EXPECTED["unit_sources"].items():
        assert _sha(UNIT / name) == sha, f"{name} changed; re-run tools/enrichment_capture.py"


@pytest.mark.parametrize("name", sorted(EXPECTED["files"]))
@pytest.mark.parametrize("field", DERIVED_FIELDS)
def test_every_derived_field_is_the_units_cell_for_cell(name: str, field: str) -> None:
    produced = AudienceDimensionsEnricher().derive(_panel(name))
    assert list(produced[field]) == EXPECTED["files"][name]["derived"][field]


def test_the_enricher_produces_exactly_what_the_czech_contract_declares() -> None:
    """``PopulationRuntime._enrich`` refuses any other set, so this is what makes v17 loadable."""
    produced = AudienceDimensionsEnricher().derive(_panel("full.csv"))
    assert set(produced) == set(CZ_SYNTHETIC_V17.enrichment_fields) == set(DERIVED_FIELDS)
    assert all(len(cells) == 122 for cells in produced.values())


def test_a_missing_flag_column_refuses_and_names_it() -> None:
    """The unit fails with an AttributeError here; AIA names what is missing."""
    panel = _panel("full.csv")
    keep = [i for i, h in enumerate(panel.header) if h not in ("is_parent", "has_partner")]
    without = ParsedPanel(
        header=tuple(panel.header[i] for i in keep),
        columns=tuple(panel.columns[i] for i in keep),
        row_count=panel.row_count,
    )
    with pytest.raises(EnrichmentInputMissing) as refused:
        AudienceDimensionsEnricher().derive(without)
    assert refused.value.reason == "enrichment_input_missing"
    assert "is_parent" in str(refused.value) and "has_partner" in str(refused.value)


def test_a_row_with_no_score_falls_back_as_the_unit_does() -> None:
    produced = AudienceDimensionsEnricher().derive(_panel("full.csv"))
    row = _panel("full.csv").column("panel_row_id").index("FIC-ROW-EMPTY")
    assert produced["dominant_media_derived"][row] == "Bez dominantního kanálu"
    assert produced["dominant_leisure_derived"][row] == "Bez dominantní aktivity"
    assert produced["shopping_orientation_derived"][row] == "Vyvážená"
    assert produced["digital_engagement_tier_derived"][row] is None


def test_a_tie_goes_to_the_first_column_in_the_units_order() -> None:
    produced = AudienceDimensionsEnricher().derive(_panel("full.csv"))
    row = _panel("full.csv").column("panel_row_id").index("FIC-ROW-TIE")
    assert produced["dominant_media_derived"][row] == "TV"
    assert produced["dominant_leisure_derived"][row] == "Gaming"
    assert produced["shopping_orientation_derived"][row] == "Value / slevy"
