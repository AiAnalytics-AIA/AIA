"""What a saved version of a report changed in what code wrote ("Upraveno ručně"), pure.

A report opened in the editor prints every number code wrote inside a locked content control
tagged with its source (artifact-report RPT8a, ``control_tags.py``). A lock is a guard, never a
rule: the researcher may unlock, retype or delete anything (ADR 0035, amended), and a save is never
refused for it. What a save changed is said instead (artifact-report RPT8b):

- a control whose text differs from the one code wrote (``changed``), one that is gone
  (``removed``) and one code did not write there, a copy (``added``): the controls are compared
  as a multiset of (tag, text), so a moved paragraph is no change and a ref printed twice is
  matched without an id;
- a number typed outside every control (``typed``), with the paragraph it sits in: the numbers
  outside controls are compared as a multiset too, so furniture code wrote there (a date on the
  cover, a heading's number) is no change, nor is prose edited around it.

The census of a DOCX is the infrastructure's (``report_docx/census.py``); this compares two. With
no baseline, or one that holds no control (a draft rendered before RPT8a), nothing can be compared,
and the result says so (``comparable`` false), never "no change".
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

#: The stored form's contract (beside a saved version, as its own small JSON).
CHANGES_CONTRACT: Final = "aia-report-changes-1"


class ChangeKind(StrEnum):
    CHANGED = "changed"
    REMOVED = "removed"
    ADDED = "added"
    TYPED = "typed"


class Uncomparable(StrEnum):
    #: No baseline: the line's first version is not stored.
    NO_BASELINE = "no_baseline"
    #: The baseline holds no locked control: rendered before code locked its numbers.
    NO_CONTROLS = "no_controls"


@dataclass(frozen=True)
class ControlSpan:
    """One tagged control as a document holds it: its tag and the text inside it."""

    tag: str
    text: str


@dataclass(frozen=True)
class LooseNumber:
    """A number printed outside every control and field, and the paragraph it sits in."""

    token: str
    paragraph: str


@dataclass(frozen=True)
class Census:
    """What a DOCX holds that a save could change, in document order."""

    controls: tuple[ControlSpan, ...]
    loose: tuple[LooseNumber, ...]


@dataclass(frozen=True)
class SavedChange:
    kind: ChangeKind
    #: The control's tag; ``None`` for a number typed outside one.
    tag: str | None = None
    was: str | None = None
    now: str | None = None
    #: For ``typed``: the paragraph the number sits in, as saved.
    paragraph: str | None = None


@dataclass(frozen=True)
class SavedChanges:
    changes: tuple[SavedChange, ...]
    #: Why nothing could be compared; ``None`` when it was.
    uncomparable: Uncomparable | None = None

    @property
    def comparable(self) -> bool:
        return self.uncomparable is None


def _texts(spans: Iterable[ControlSpan]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for span in spans:
        out.setdefault(span.tag, []).append(span.text)
    return out


def _surplus(of: Mapping[str, list[str]], over: Mapping[str, list[str]]) -> dict[str, list[str]]:
    """Per tag, the texts of ``of`` that ``over`` does not match, in ``of``'s order."""
    out: dict[str, list[str]] = {}
    for tag, texts in of.items():
        left = Counter(over.get(tag, ()))
        for text in texts:
            if left[text]:
                left[text] -= 1
            else:
                out.setdefault(tag, []).append(text)
    return out


def _control_changes(baseline: Census, saved: Census) -> list[SavedChange]:
    before, after = _texts(baseline.controls), _texts(saved.controls)
    gone, new = _surplus(before, after), _surplus(after, before)
    out: list[SavedChange] = []
    for tag in dict.fromkeys(s.tag for s in baseline.controls):
        was, now = gone.get(tag, []), new.pop(tag, [])
        out.extend(
            SavedChange(ChangeKind.CHANGED, tag, w, n) for w, n in zip(was, now, strict=False)
        )
        out.extend(SavedChange(ChangeKind.REMOVED, tag, was=w) for w in was[len(now) :])
        out.extend(SavedChange(ChangeKind.ADDED, tag, now=n) for n in now[len(was) :])
    for tag, texts in new.items():
        out.extend(SavedChange(ChangeKind.ADDED, tag, now=n) for n in texts)
    return out


def _typed(baseline: Census, saved: Census) -> list[SavedChange]:
    """A number the save holds more of than the baseline, in a paragraph the baseline did not
    hold it in: a number moved with its paragraph, or left where prose was edited, is no change."""
    tokens = Counter(n.token for n in saved.loose) - Counter(n.token for n in baseline.loose)
    pairs = Counter(saved.loose) - Counter(baseline.loose)
    out: list[SavedChange] = []
    for number in saved.loose:
        if tokens[number.token] and pairs[number]:
            tokens[number.token] -= 1
            pairs[number] -= 1
            out.append(SavedChange(ChangeKind.TYPED, now=number.token, paragraph=number.paragraph))
    return out


def compare(baseline: Census | None, saved: Census) -> SavedChanges:
    """What ``saved`` changed in what code wrote, ``baseline`` being the line's first version."""
    if baseline is None:
        return SavedChanges((), Uncomparable.NO_BASELINE)
    if not baseline.controls:
        return SavedChanges((), Uncomparable.NO_CONTROLS)
    return SavedChanges((*_control_changes(baseline, saved), *_typed(baseline, saved)))


def changes_payload(changes: SavedChanges) -> dict[str, Any]:
    """The stored form, beside the version it describes."""
    return {
        "contract": CHANGES_CONTRACT,
        "uncomparable": changes.uncomparable.value if changes.uncomparable else None,
        "changes": [
            {
                "kind": c.kind.value,
                "tag": c.tag,
                "was": c.was,
                "now": c.now,
                "paragraph": c.paragraph,
            }
            for c in changes.changes
        ],
    }


def read_changes_payload(payload: Mapping[str, Any]) -> SavedChanges:
    """A stored form read back; any other contract refused (``ValueError``), never read in part."""
    if payload.get("contract") != CHANGES_CONTRACT:
        raise ValueError(f"not {CHANGES_CONTRACT}: {payload.get('contract')!r}")
    reason = payload["uncomparable"]
    return SavedChanges(
        tuple(
            SavedChange(
                ChangeKind(c["kind"]),
                tag=c["tag"],
                was=c["was"],
                now=c["now"],
                paragraph=c["paragraph"],
            )
            for c in payload["changes"]
        ),
        Uncomparable(reason) if reason is not None else None,
    )
