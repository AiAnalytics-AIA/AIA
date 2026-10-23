"""What a deleted client's kept rows may still say (settings-backends SB5), pure."""

from __future__ import annotations

from aia_core.domain.content_free import ERASED, content_free, rename


def test_only_aia_ids_codes_digests_and_times_stay() -> None:
    kept = ["CLI-0123abcd", "RUN-deadbeef01", "MEMBER_ADDED", "ab" * 32, "2026-10-23T02:00:00Z"]
    assert content_free(kept) == kept
    # Upper case alone, or a hyphenated word, is text: a brand is not an id.
    for text in ("SKODA", "Coca-Cola", "Acme Corp", "poznamky.txt", "XYZ-12345678"):
        assert content_free(text) == ERASED
    assert content_free({"n": 3, "ok": True, "none": None}) == {"n": 3, "ok": True, "none": None}


def test_a_name_is_replaced_inside_longer_text_and_a_short_one_only_whole() -> None:
    names = {"Acme Corp": "CLI-0123abcd", "S": "STU-0001aaaa"}
    assert rename("Lift for Acme Corp, see S", names) == "Lift for CLI-0123abcd, see S"
    assert rename({"study": "S", "n": ["Acme Corp"]}, names) == {
        "study": "STU-0001aaaa",
        "n": ["CLI-0123abcd"],
    }


def test_a_name_is_never_part_of_another_word_nor_rewrites_an_id_or_a_time() -> None:
    names = {"Pilot": "CLI-aaaa1111", "2026": "CLI-bbbb2222", "deadbeef": "STU-cccc3333"}
    # Another client's word that begins with this client's name stays.
    assert rename("Pilotní studie", names) == "Pilotní studie"
    assert rename("Studie Pilot, druhá", names) == "Studie CLI-aaaa1111, druhá"
    # A digit or hex name never rewrites a time or a digest.
    assert rename("2026-10-23T02:00:00Z", names) == "2026-10-23T02:00:00Z"
    assert rename("deadbeef" * 4, names) == "deadbeef" * 4
    assert rename("2026", names) == "CLI-bbbb2222"


def test_the_codes_own_single_words_stay_and_a_brand_does_not() -> None:
    assert content_free(["ARCHIVED", "ADMIN", "READ", "SKODA"]) == [
        "ARCHIVED",
        "ADMIN",
        "READ",
        ERASED,
    ]
