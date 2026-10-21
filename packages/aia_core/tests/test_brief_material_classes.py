"""The class of each material a Brief carries (artifact-brief BRF3)."""

from __future__ import annotations

from aia_core.domain.brief_material_classes import brief_material_classes
from aia_core.domain.material_rules import MaterialRule, rule_class
from aia_core.domain.residency import DataClass


def test_a_file_and_a_link_are_the_design_class_b_by_rule() -> None:
    content = {
        "briefing": {
            "attachments": [
                {"kind": "file", "attachment_id": "ART-01", "filename": "zadani.txt"},
                {"kind": "url", "url": "https://example.org/a", "title": "A"},
            ]
        }
    }
    classes = brief_material_classes(content)
    assert [(m.index, m.kind, m.ref) for m in classes] == [
        (0, "file", "ART-01"),
        (1, "url", "https://example.org/a"),
    ]
    assert {m.data_class for m in classes} == {DataClass.CLASS_B_DERIVED_CLIENT}
    assert {m.class_source for m in classes} == {"rule:design"}
    # One definition: the rule's class, not a copy of it.
    assert classes[0].data_class is rule_class(MaterialRule.DESIGN)


def test_a_record_from_before_kind_reads_as_a_file_whose_artifact_may_be_missing() -> None:
    # 18.6.6's records name no AIA artifact; the file is still the design's.
    [m] = brief_material_classes({"briefing": {"attachments": [{"filename": "stary.pdf"}]}})
    assert (m.kind, m.ref, m.data_class) == ("file", None, DataClass.CLASS_B_DERIVED_CLIENT)


def test_an_entry_no_rule_names_has_no_class_never_a_guess() -> None:
    entries = ["text", {"kind": "client_dataset", "source_id": "SRC-1"}, {"kind": "url"}, None]
    classes = brief_material_classes({"briefing": {"attachments": entries}})
    assert [m.index for m in classes] == [0, 1, 2, 3]
    assert all(m.data_class is None and m.class_source is None for m in classes)
    assert all(m.kind is None and m.ref is None for m in classes)


def test_no_content_briefing_or_list_is_no_materials() -> None:
    assert brief_material_classes(None) == []
    assert brief_material_classes({}) == []
    assert brief_material_classes({"briefing": "x"}) == []
    assert brief_material_classes({"briefing": {"attachments": {"a": 1}}}) == []
