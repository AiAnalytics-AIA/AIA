"""The behavioural block of a panel persona: the catalog's signals a question's topics call for.

A port of ``persona_grounded.grounded_profile_text`` and its helpers
(``legacy/npc-panel-18.6.6/app/persona_grounded.py:45-318``), the block 18.6.6's adaptive
persona showed (``persona_depth.deep_profile_text``, ``persona_depth.py:513-520``). Inputs are two
companions of the population version, read through the loader
(``RuntimePopulation.companion``): ``PERSONA_SIGNAL_CATALOG_v17.csv`` (which column, how to
render it, which topics, its evidence role) and ``PERSONA_VALUE_LABELS_v17.json`` (what a
column's values mean). Parity is EXACT against the unit's own function on fictional rows and a
fictional catalog, with the unit's own value labels (``tools/persona_capture.py``;
``tests/fixtures/persona_profile/``).

What the unit does, kept:

* a signal is a candidate only when its topics meet the question's, never when its role is
  ``MODELED_BEHAVIOR_PRIOR`` (the 17.1 gate), and only when the row holds a value;
* a column with value labels renders by them first; otherwise by its ``kind``;
* the score is the catalog's priority, raised by the value's distance from the scale's middle and
  by each specific (non-generic) topic it matches;
* candidates in score order, ties by column (a NaN score last: the one difference, since the
  unit's order for it depended on the Python version); at most 3 per block and one per
  concept, within the signal budget (``product_policy.persona_signal_budget``,
  ``PRODUCT_POLICY.json``: 4, one more per two extra topics, at most 8; then clamped to 3..9);
* each signal carries its provenance in brackets (``_role_suffix``).

The catalog is read as ``pandas.read_csv`` reads it (:func:`parse_catalog`), its quirks with it: an
empty ``block``, ``kind`` or ``topics`` cell reads ``"nan"``, an empty ``priority`` is NaN.

The unit's other path, the ``P_*`` compatibility block (``persona_depth.py:521-560``), runs only
when the catalog yields nothing for a row that carries ``P_*`` columns; v17 replaced it
(``persona_grounded.py:10``) and it is not ported. :func:`compatibility_columns` names the columns
whose presence would need it, so a caller refuses rather than silently differs.

Pure: stdlib only.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .population.audience import Typed, _typed, column_type

__all__ = [
    "CATALOG_ASSET",
    "COMPATIBILITY_PREFIXES",
    "VALUE_LABELS_ASSET",
    "Signal",
    "compatibility_columns",
    "grounded_text",
    "parse_catalog",
    "parse_value_labels",
    "render",
    "signal_budget",
]

CATALOG_ASSET: Final = "PERSONA_SIGNAL_CATALOG_v17.csv"
VALUE_LABELS_ASSET: Final = "PERSONA_VALUE_LABELS_v17.json"

#: ``PRODUCT_POLICY.json`` ``persona.signal_budget`` (``PRODUCT_POLICY.json:34-38``).
_BUDGET_BASE: Final = 4
_BUDGET_STEP: Final = 1
_BUDGET_MAX: Final = 8
_PER_BLOCK: Final = 3
_GENERIC_TOPICS: Final = frozenset(
    {
        "digital",
        "online",
        "politika",
        "verejne",
        "zdravi",
        "vztahy",
        "finance",
        "spolecnost",
        "prace",
    }
)
_ANCHOR_MAX_WORDS: Final = 12
#: The ``P_*`` columns of ``persona_depth``'s compatibility block (``persona_depth.py:97-125``).
COMPATIBILITY_PREFIXES: Final = (
    "P_media_",
    "P_buy_",
    "P_brand_",
    "P_value_",
    "P_life_",
    "P_digital_",
)

_FREQUENCY: Final = {
    1: "nikdy",
    2: "méně než měsíčně",
    3: "alespoň měsíčně, ne týdně",
    4: "alespoň týdně, ne denně",
    5: "denně",
}
_HEALTH: Final = {1: "výborné", 2: "velmi dobré", 3: "dobré", 4: "uspokojivé", 5: "špatné"}
_TEXT_NONE: Final = frozenset(
    {"nan", "none", "<na>", "neví/odmítl", "nevi/odmitl", "don't know", "dont know", "refused"}
)
_TEXT_CZECH: Final = {
    "None of the time": "nikdy",
    "A little of the time": "malou část času",
    "Some of the time": "část času",
    "Most of the time": "většinu času",
    "All of the time": "stále",
    "Never": "nikdy",
    "Daily": "denně",
    "Every week": "jednou týdně",
    # The unit's literal holds this key twice; the later value wins (persona_grounded.py:251,256).
    "More than once a week": "více než jednou týdně",
    "Every two weeks": "jednou za dva týdny",
    "Once a month": "jednou měsíčně",
    "Every two months or less frequently": "jednou za dva měsíce nebo méně často",
    "On specific holidays only": "jen o vybraných svátcích",
    "Once a week": "jednou týdně",
}

Row = Mapping[str, Typed]


@dataclass(frozen=True, slots=True)
class Signal:
    """One catalog row, as ``persona_grounded._catalog`` holds it."""

    column: str
    label: str
    topics: frozenset[str]
    source: str
    wave: str
    evidence_role: str
    block: str
    kind: str
    priority: float
    min_abs_z: float
    concept: str


def _present(value: Typed) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def _text_or(value: Typed, default: str) -> str:
    """``str(value or default)``: NaN is truthy, so a missing cell reads ``"nan"``."""
    if value is None:
        return "nan"
    return str(value or default)


def _float_or(value: Typed, default: float) -> float:
    """``float(value or default)``: a missing cell is NaN."""
    if value is None:
        return math.nan
    return float(value or default)


def parse_catalog(data: bytes) -> tuple[Signal, ...]:
    """The catalog as ``_catalog`` reads it (``persona_grounded.py:62-84``)."""
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    header, *raw = list(reader)
    cells = {h: [None if r[i] == "" else r[i] for r in raw] for i, h in enumerate(header)}
    typed = {h: [_typed(c, column_type(h, col)) for c in col] for h, col in cells.items()}

    def get(name: str, i: int) -> Typed:
        return typed[name][i] if name in typed else None

    out: list[Signal] = []
    for i in range(len(raw)):
        column = _text_or(get("column", i), "").strip() if "column" in typed else ""
        if not column:
            continue
        topics_text = _text_or(get("topics", i), "")
        concept = get("concept", i)
        out.append(
            Signal(
                column=column,
                label=_text_or(get("label", i), column).strip(),
                topics=frozenset(
                    x.strip().lower()
                    for x in topics_text.split("|")
                    if x.strip() and x.strip().lower() != "nan"
                ),
                source=_text_or(get("source", i), "").strip(),
                wave=_text_or(get("wave", i), "").strip(),
                evidence_role=_text_or(get("evidence_role", i), "").strip(),
                block=_text_or(get("block", i), "").strip(),
                kind=_text_or(get("kind", i), "raw").strip(),
                priority=_float_or(get("priority", i), 1.0),
                min_abs_z=_float_or(get("min_abs_z", i), 0.0),
                concept="" if not _present(concept) else str(concept or "").strip(),
            )
        )
    return tuple(out)


def parse_value_labels(data: bytes) -> dict[str, dict[str, Any]]:
    """``_value_labels`` (``persona_grounded.py:51-59``): the ``variables`` mapping."""
    try:
        return dict(json.loads(data.decode("utf-8")).get("variables") or {})
    except (ValueError, AttributeError):
        return {}


def signal_budget(topics: Iterable[str]) -> int:
    """``persona_signal_budget`` (``product_policy.py:91-95``)."""
    n = len({str(x).strip().lower() for x in topics if str(x).strip()})
    return max(1, min(_BUDGET_MAX, _BUDGET_BASE + max(0, (n - 1) // 2) * _BUDGET_STEP))


def _safe_num(value: Typed) -> float | None:
    try:
        x = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _role_suffix(signal: Signal, row: Row) -> str:
    """``_role_suffix`` (``persona_grounded.py:87-101``)."""
    role = signal.evidence_role
    if role == "MEASURED_DERIVED":
        return f"měřeno v core donorovi; {signal.source} {signal.wave}"
    if role == "MEASURED_JOINT":
        return f"měřeno ve stejném core donorovi; {signal.source} {signal.wave}"
    if role in {"MATCHED_DONOR_BLOCK", "MATCHED_WHOLE_BLOCK_CANONICAL"}:
        block = signal.block or "blok"
        quality = row.get(f"_donor_{block}_quality")
        qs = f", match {quality}" if _present(quality) and str(quality).strip() else ""
        return f"statisticky přiřazený celý donor blok; {signal.source} {signal.wave}{qs}"
    if role == "CALIBRATED_BEHAVIOR_MODEL":
        return "kalibrovaný behaviorální model"
    if role == "MODELED_BEHAVIOR_PRIOR":
        return "modelový behaviorální prior"
    if role == "MODELED_VALUE_PROXY":
        return "modelový hodnotový proxy"
    if role == "CALIBRATED_MODELED_COMPOSITE":
        return "kalibrovaný modelový kompozit"
    if role == "CALIBRATED_MODELED_BINARY":
        return "kalibrovaná modelová položka"
    return role.lower().replace("_", " ")


def _compact_anchor(label: str, low: str, high: str, direction: str) -> str:
    """``_compact_anchor`` (``persona_grounded.py:107-142``)."""
    label_words = {w for w in re.findall(r"\w+", label.lower()) if len(w) > 3}

    def clean(text: str) -> str:
        t = re.sub(r"^\s*\d+\s*=\s*", "", str(text or "").strip())
        out: list[str] = []
        for w in t.split():
            if re.sub(r"\W", "", w).lower() in label_words:
                break
            out.append(w)
        if not out:
            out = t.split()[:3]
        return " ".join(out).strip(" ,;—-")

    lo, hi = clean(low), clean(high)
    if lo and hi and lo.lower() == hi.lower():
        hi = ""
    parts: list[str] = []
    if lo or hi:
        parts.append(f"0={lo or '—'}, 10={hi or '—'}")
    d = str(direction or "").strip()
    if d and not re.match(r"^(vyšší|nižší|více|méně)\b", d, re.I) and len(d.split()) <= 6:
        parts.append(d)
    return " ".join("; ".join(parts).split()[:_ANCHOR_MAX_WORDS])


def _from_labels(
    signal: Signal, value: Typed, spec: Mapping[str, Any]
) -> tuple[bool, tuple[str, float] | None]:
    """The value-label path (``persona_grounded.py:152-178``): whether it decided, and what.

    It decides when the value is not a number (nothing shown), when the value has a label, and
    when the column has anchors; otherwise the signal's ``kind`` renders it.
    """
    x = _safe_num(value)
    if x is None:
        return True, None
    label, score = signal.label, signal.priority
    values = spec.get("values") or {}
    key = str(round(x)) if abs(x - round(x)) < 1e-9 else f"{x:g}"
    if key in values:
        direction = str(spec.get("direction") or "").strip()
        suffix = f"; {direction}" if direction else ""
        return True, (f"{label}: {values[key]}{suffix}", score * (1.15 if direction else 1.05))
    anchors = spec.get("anchors") or {}
    if anchors:
        low = str(anchors.get("low") or "").strip()
        high = str(anchors.get("high") or "").strip()
        direction = str(spec.get("direction") or "").strip()
        generic = (
            "nízká intenzita" in low
            and "vysoká intenzita" in high
            and "více uvedeného" in direction
        )
        if generic:
            return True, (f"{label}: {x:g}/10", score * (1 + abs(x - 5) / 10))
        anchor = _compact_anchor(label, low, high, direction)
        text = f"{label}: {x:g}/10" + (f" ({anchor})" if anchor else "")
        return True, (text, score * (1 + abs(x - 5) / 10))
    return False, None


def render(
    signal: Signal, row: Row, labels: Mapping[str, Mapping[str, Any]]
) -> tuple[str, float] | None:
    """``_render`` (``persona_grounded.py:145-264``): a signal's text and score, or nothing."""
    column = signal.column
    if column not in row or not _present(row.get(column)):
        return None
    value = row[column]
    kind, label, score = signal.kind, signal.label, signal.priority

    spec = labels.get(column)
    if spec:
        decided, labelled = _from_labels(signal, value, spec)
        if decided:
            return labelled

    x = _safe_num(value)
    if kind == "bfi_z":
        if x is None or abs(x) < max(0.35, signal.min_abs_z):
            return None
        strength = "výrazně" if abs(x) >= 1.15 else "spíše"
        direction = "vyšší" if x > 0 else "nižší"
        return f"{strength} {direction} {label} než populační průměr", score * (1.2 + abs(x))
    if kind in {"categorical", "text"}:
        text = str(value).strip()
        if kind == "categorical":
            if not text or text.lower() in {"nan", "none", "<na>", "unknown"}:
                return None
            return f"{label}: {text}", score
        if not text or text.lower() in _TEXT_NONE:
            return None
        return f"{label}: {_TEXT_CZECH.get(text, text)}", score * 1.15
    if x is None:
        return None
    if kind == "scale10":
        return f"{label}: {x:g}/10", score * (1 + abs(x - 5) / 5)
    if kind == "scale5":
        return f"{label}: {x:g}/5", score * (1 + abs(x - 3) / 2)
    if kind == "frequency5":
        return f"{label}: {_FREQUENCY.get(round(x), str(x))}", score * (1 + abs(x - 3) / 2)
    if kind == "health5":
        return f"{label}: {_HEALTH.get(round(x), str(x))}", score * (1 + abs(x - 3) / 2)
    if kind == "scale4":
        return f"{label}: {x:g}/4", score * (1 + abs(x - 2.5) / 1.5)
    if kind == "scale6":
        return f"{label}: {x:g}/6", score * (1 + abs(x - 3.5) / 2.5)
    if kind == "yesno":
        return f"{label}: {'ano' if round(x) == 1 else 'ne'}", score * 1.2
    if kind == "minutes_day":
        return f"{label}: ~{x:g} min/den", score * (1 + min(abs(x), 180) / 360)
    if kind == "hours_week":
        return f"{label}: ~{x:g} h/týden", score
    if kind == "scale01":
        return f"{label}: {x:.2f} (0–1)", score  # noqa: RUF001 - the unit's own text
    if kind == "phq9":
        return f"PHQ-9 symptom score: {x:g}/27 (nikoli diagnóza)", score * (1 + min(x, 20) / 20)
    if kind == "gad7":
        return f"GAD-7 symptom score: {x:g}/21 (nikoli diagnóza)", score * (1 + min(x, 18) / 18)
    return None


def grounded_text(
    row: Row,
    topics: Iterable[str],
    catalog: Sequence[Signal],
    labels: Mapping[str, Mapping[str, Any]],
) -> str:
    """``grounded_profile_text`` (``persona_grounded.py:267-318``): the signals, or ``""``."""
    topic_set = {str(x).strip().lower() for x in topics if str(x).strip()}
    if not topic_set:
        return ""
    candidates: list[tuple[float, Signal, str]] = []
    for signal in catalog:
        if not topic_set & signal.topics:
            continue
        if signal.evidence_role == "MODELED_BEHAVIOR_PRIOR":
            continue
        rendered = render(signal, row, labels)
        if rendered is None:
            continue
        text, score = rendered
        specific = (topic_set & signal.topics) - _GENERIC_TOPICS
        score *= 1.0 + 0.80 * len(specific)
        candidates.append((score, signal, text))
    if not candidates:
        return ""
    # The unit's order (score descending, then column). A NaN score (an empty priority) has no
    # place in it: Python's sort leaves such a key where its internals put it, and 18.6.6's own
    # output then differs between Python versions. AIA ranks it last: unknown is never good.
    candidates.sort(
        key=lambda c: (math.isnan(c[0]), 0.0 if math.isnan(c[0]) else -c[0], c[1].column)
    )
    budget = max(3, min(9, signal_budget(topic_set)))
    selected: list[tuple[Signal, str]] = []
    per_block: dict[str, int] = {}
    concepts: set[str] = set()
    for _, signal, text in candidates:
        block = signal.block or "other"
        if per_block.get(block, 0) >= _PER_BLOCK:
            continue
        if signal.concept and signal.concept in concepts:
            continue
        selected.append((signal, text))
        per_block[block] = per_block.get(block, 0) + 1
        if signal.concept:
            concepts.add(signal.concept)
        if len(selected) >= budget:
            break
    return "Relevantní datové signály: " + "; ".join(
        f"{text} [{_role_suffix(signal, row)}]" for signal, text in selected
    )


def compatibility_columns(columns: Iterable[str]) -> tuple[str, ...]:
    """The ``P_*`` columns whose presence would call for the unported compatibility block."""
    return tuple(c for c in columns if c.startswith(COMPATIBILITY_PREFIXES))
