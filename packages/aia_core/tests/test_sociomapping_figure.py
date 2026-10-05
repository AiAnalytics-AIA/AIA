"""The experimental map as a report image: labels apart, bytes deterministic (plan I2)."""

from __future__ import annotations

import pytest

from aia_core.infrastructure.report_docx.sociomapping_figure import (
    draw_sociomapping_map,
    height_band,
    label_lines,
)


def test_close_points_get_their_labels_on_separate_lines() -> None:
    # Iris and Halo from the workbench's eight-brand map: 0.02 apart, same height.
    assert label_lines([(0.45, 0.73), (0.43, 0.73), (0.2, 0.58), (0.9, 0.6)]) == [1, 0, 0, 0]
    assert label_lines([(0.1, 0.1), (0.9, 0.9)]) == [0, 0]  # far apart: untouched


def test_the_image_is_deterministic_and_refuses_mismatched_input() -> None:
    args = (["A", "B", "C"], [(0.1, 0.2), (0.5, 0.9), (0.95, 0.4)], [2.0, 9.5, 5.5], (1.0, 10.0))
    first = draw_sociomapping_map(*args, ("vůbec", "velmi"))
    assert first.startswith(b"\x89PNG") and first == draw_sociomapping_map(
        *args, ("vůbec", "velmi")
    )
    with pytest.raises(ValueError, match="one label"):
        draw_sociomapping_map(["A"], [(0.1, 0.2), (0.3, 0.4)], [1.0], (1.0, 10.0))
    assert [height_band(v, 1, 10) for v in (1, 5.5, 10)] == [0, 3, 6]
