"""What a deleted client's kept rows may still say (settings-backends SB5), pure."""

from __future__ import annotations

import ast
from pathlib import Path

from aia_core.domain.content_free import AUDIT_ACTIONS, ERASED, content_free, rename


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


def test_a_code_is_kept_by_its_vocabulary_never_by_its_shape() -> None:
    # Client text in upper snake case is still client text.
    assert content_free(["ACME_SECRET", "CLIENT_DELETED", "CLASS_B_DERIVED_CLIENT"]) == [
        ERASED,
        "CLIENT_DELETED",
        "CLASS_B_DERIVED_CLIENT",
    ]


def test_every_audit_action_the_code_writes_is_a_kept_code() -> None:
    root = Path(__file__).resolve().parents[3]
    written: set[str] = set()
    for tree in ("packages/aia_core/src", "apps/api/src", "apps/worker/src", "apps/executors/src"):
        for path in (root / tree).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                values = [kw.value for kw in node.keywords if kw.arg == "action"]
                if name.endswith("_audit"):
                    kinds = (ast.Constant, ast.JoinedStr, ast.IfExp)
                    values += [a for a in node.args if isinstance(a, kinds)]
                for v in values:
                    # A code built at run time cannot be checked here: write each one out.
                    assert not isinstance(v, ast.JoinedStr), (
                        f"{path}:{v.lineno}: an f-string action"
                    )
                    if (
                        isinstance(v, ast.Constant)
                        and isinstance(v.value, str)
                        and v.value.isupper()
                    ):
                        written.add(v.value)
                    elif isinstance(v, ast.IfExp):
                        written.update(
                            b.value
                            for b in (v.body, v.orelse)
                            if isinstance(b, ast.Constant) and isinstance(b.value, str)
                        )
    assert written, "the scan found no audit action"
    assert written <= AUDIT_ACTIONS, sorted(written - AUDIT_ACTIONS)
