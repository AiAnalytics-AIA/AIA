"""Every ruff per-file-ignore names something that exists.

The root pyproject.toml lifts rules per file -- the egress ban's exits, the test
trees. Ruff says nothing about an entry that matches no file, so a renamed module
keeps an exemption that no longer covers it, and the next file to take the old
path inherits it unread. A glob is checked by the directory before its first
wildcard; a plain path by the file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WILDCARDS = set("*?[")


def _per_file_ignores() -> dict[str, list[str]]:
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    ignores: dict[str, list[str]] = config["tool"]["ruff"]["lint"]["per-file-ignores"]
    return ignores


def _anchor(pattern: str) -> Path:
    """The literal part of a pattern: the path itself, or the directory above its wildcard."""
    parts: list[str] = []
    for part in pattern.split("/"):
        if WILDCARDS & set(part):
            break
        parts.append(part)
    return REPO.joinpath(*parts)


def test_there_are_per_file_ignores_to_check() -> None:
    assert _per_file_ignores()


def test_every_per_file_ignore_names_an_existing_path() -> None:
    missing = [
        pattern
        for pattern in _per_file_ignores()
        if not pattern.startswith("**") and not _anchor(pattern).exists()
    ]
    assert missing == []


def test_no_per_file_ignore_starts_with_a_wildcard() -> None:
    """A leading ** reaches every tree, a source package named tests included."""
    assert [p for p in _per_file_ignores() if p.startswith("**")] == []
