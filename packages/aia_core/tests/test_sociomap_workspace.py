"""Native workspace parity and deliberate missing-evidence differences."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aia_core.domain.sociomap.models import RatingsMatrix
from aia_core.domain.sociomap.workspace import compute_workspace

FIXTURE = Path(__file__).parent / "fixtures/sociomap_workspace/native_views.json"


def matrix() -> RatingsMatrix:
    data = json.loads(FIXTURE.read_text())
    return RatingsMatrix(
        respondent_ids=data["respondent_ids"], object_ids=data["object_ids"], values=data["rows"]
    )


def test_native_geometry_and_metrics_match_the_archived_workspace() -> None:
    data = json.loads(FIXTURE.read_text())
    source = (
        Path(__file__).resolve().parents[3] / "legacy/npc-panel-18.6.6/app/visualization_lab.py"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == data["source_sha256"]
    result = compute_workspace(matrix(), (1, 10))
    expected = data["expected"]
    for mine, theirs in zip(result.people, expected["points"], strict=True):
        assert (mine.id, mine.status) == (theirs["id"], theirs["position_status"])
        assert (mine.x, mine.y) == pytest.approx((theirs["x"], theirs["y"]), abs=1e-5)
    for mine, theirs in zip(result.objects, expected["object_map"]["positions"], strict=True):
        assert (mine.x, mine.y) == pytest.approx((theirs["x"], theirs["y"]), abs=1e-5)
    for ours, key in [
        ("relation_classic", "scores_classic"),
        ("relation_norm", "scores_normative"),
        ("mean_rating", "mean_rating"),
        ("support_n", "support_n"),
    ]:
        assert result.metrics[ours] == pytest.approx(expected["object_map"][key], abs=1e-4)
    for ours, theirs in zip(result.relations, expected["object_map"]["matrix"], strict=True):
        assert ours == pytest.approx(theirs, abs=1e-4)
    assert result.pair_n == tuple(tuple(r) for r in expected["object_map"]["pair_n"])
    assert result == compute_workspace(matrix(), (1, 10))
    assert result.respondent_terrain is not None
    assert result.respondent_terrain.mode == "respondent_density"
    assert all(t.mode == "object_metric" for t in result.object_terrains.values())
    assert result.weighting == "UNWEIGHTED"


@pytest.mark.parametrize("rows", [[[1, 2]] * 6, [[1, 2], [3, 4]], [[None, 2]] * 6])
def test_undefined_relationships_never_draw_a_neutral_object_landscape(
    rows: list[list[float | None]],
) -> None:
    inputs = RatingsMatrix(
        respondent_ids=tuple(str(i) for i in range(len(rows))),
        object_ids=("a", "b", "c"),
        values=[[*r, 3] for r in rows],
    )
    result = compute_workspace(inputs, (1, 10))
    assert result.relations[0][1] is None
    assert not result.objects and not result.object_terrains
    assert result.object_reason == "INSUFFICIENT_PAIR_SUPPORT_OR_VARIANCE"
    assert len(result.people) == len(rows)


def test_unsupported_scale_and_out_of_range_values() -> None:
    assert compute_workspace(matrix(), (0, 10)).reason == "SCALE_NOT_1_10"
    bad = matrix().model_copy(update={"values": tuple((11.0, *row[1:]) for row in matrix().values)})
    with pytest.raises(ValueError, match="declared"):
        compute_workspace(bad, (1, 10))


def test_size_limit_does_not_silently_sample() -> None:
    inputs = RatingsMatrix(
        respondent_ids=tuple(str(i) for i in range(2001)),
        object_ids=("a", "b", "c"),
        values=((1, 2, 3),) * 2001,
    )
    result = compute_workspace(inputs, (1, 10))
    assert result.reason == "WORKSPACE_SIZE_LIMIT" and not result.people


def test_input_fingerprint_records_ids_and_missingness() -> None:
    source = matrix()
    result = compute_workspace(source, (1, 10))
    changed = source.model_copy(
        update={"values": ((None, *source.values[0][1:]), *source.values[1:])}
    )
    assert compute_workspace(changed, (1, 10)).input_fingerprint != result.input_fingerprint
