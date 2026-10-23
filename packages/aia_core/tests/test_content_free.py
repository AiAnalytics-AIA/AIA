"""What a deleted client's kept rows may still say (settings-backends SB5), pure."""

from __future__ import annotations

from aia_core.domain.content_free import ERASED, content_free, rename


def test_only_aia_ids_codes_digests_and_times_stay() -> None:
    kept = ["CLI-0123abcd", "RUN-deadbeef01", "MEMBER_ADDED", "ab" * 32, "2026-10-23T02:00:00Z"]
    assert content_free(kept) == kept
    # Upper case alone, or a hyphenated word, is text: a brand is not an id.
    for text in ("SKODA", "Coca-Cola", "READ", "Acme Corp", "poznamky.txt", "XYZ-12345678"):
        assert content_free(text) == ERASED
    assert content_free({"n": 3, "ok": True, "none": None}) == {"n": 3, "ok": True, "none": None}


def test_a_name_is_replaced_inside_longer_text_and_a_short_one_only_whole() -> None:
    names = {"Acme Corp": "CLI-0123abcd", "S": "STU-0001aaaa"}
    assert rename("Lift for Acme Corp, see S", names) == "Lift for CLI-0123abcd, see S"
    assert rename({"study": "S", "n": ["Acme Corp"]}, names) == {
        "study": "STU-0001aaaa",
        "n": ["CLI-0123abcd"],
    }
