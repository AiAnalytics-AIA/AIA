"""What a saved version changed in what code wrote, compared from two censuses (artifact-report
RPT8b): never refusing, and never "no change" when nothing could be compared."""

from __future__ import annotations

import pytest

from aia_core.domain.report.saved_changes import (
    Census,
    ChangeKind,
    ControlSpan,
    LooseNumber,
    SavedChange,
    Uncomparable,
    changes_payload,
    compare,
    read_changes_payload,
)

BASE = Census(
    (
        ControlSpan("trust_total", "42,5 %"),
        ControlSpan("trust_total", "42,5 %"),
        ControlSpan("trust_praha", "48,2 %"),
        ControlSpan("run:RUN-1", "n = 1204"),
    ),
    (LooseNumber("2026", "Důvěra v banky 2026"), LooseNumber("1", "1 Návrh")),
)


def test_a_save_that_moved_and_reworded_around_the_numbers_changed_nothing() -> None:
    saved = Census(
        (
            ControlSpan("run:RUN-1", "n = 1204"),
            ControlSpan("trust_praha", "48,2 %"),
            ControlSpan("trust_total", "42,5 %"),
            ControlSpan("trust_total", "42,5 %"),
        ),
        (LooseNumber("1", "1 Návrh"), LooseNumber("2026", "Důvěra bankám 2026")),
    )
    assert compare(BASE, saved).changes == ()
    assert compare(BASE, saved).comparable


def test_a_retyped_a_deleted_and_a_copied_control_are_each_said() -> None:
    saved = Census(
        (
            ControlSpan("trust_total", "42,5 %"),
            ControlSpan("trust_total", "50 %"),
            ControlSpan("run:RUN-1", "n = 1204"),
            ControlSpan("run:RUN-1", "n = 1204"),
        ),
        BASE.loose,
    )
    assert compare(BASE, saved).changes == (
        SavedChange(ChangeKind.CHANGED, "trust_total", was="42,5 %", now="50 %"),
        SavedChange(ChangeKind.REMOVED, "trust_praha", was="48,2 %"),
        SavedChange(ChangeKind.ADDED, "run:RUN-1", now="n = 1204"),
    )


def test_a_control_with_a_tag_the_baseline_lacks_is_added() -> None:
    saved = Census((*BASE.controls, ControlSpan("trust_brno", "39,7 %")), BASE.loose)
    assert compare(BASE, saved).changes == (
        SavedChange(ChangeKind.ADDED, "trust_brno", now="39,7 %"),
    )


def test_a_number_typed_outside_a_control_is_said_with_its_paragraph() -> None:
    saved = Census(
        BASE.controls,
        (*BASE.loose, LooseNumber("7", "Sedm z deseti 7."), LooseNumber("2026", "Rok 2026")),
    )
    assert compare(BASE, saved).changes == (
        SavedChange(ChangeKind.TYPED, now="7", paragraph="Sedm z deseti 7."),
        SavedChange(ChangeKind.TYPED, now="2026", paragraph="Rok 2026"),
    )


def test_a_number_moved_between_paragraphs_is_no_change() -> None:
    saved = Census(BASE.controls, (LooseNumber("2026", "Jinde 2026"), LooseNumber("1", "1 Návrh")))
    assert compare(BASE, saved).changes == ()


@pytest.mark.parametrize(
    ("baseline", "reason"),
    [(None, Uncomparable.NO_BASELINE), (Census((), BASE.loose), Uncomparable.NO_CONTROLS)],
)
def test_nothing_to_compare_with_is_never_no_change(
    baseline: Census | None, reason: Uncomparable
) -> None:
    result = compare(baseline, BASE)
    assert not result.comparable and result.uncomparable is reason and result.changes == ()


def test_the_stored_form_reads_back_and_refuses_another_contract() -> None:
    saved = Census(BASE.controls[1:], (*BASE.loose, LooseNumber("7", "Sedm 7.")))
    changes = compare(BASE, saved)
    assert read_changes_payload(changes_payload(changes)) == changes
    uncomparable = compare(None, saved)
    assert read_changes_payload(changes_payload(uncomparable)) == uncomparable
    with pytest.raises(ValueError):
        read_changes_payload({**changes_payload(changes), "contract": "aia-report-changes-0"})
