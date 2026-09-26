"""The respondent factual layer: facts a respondent already has are answered by code.

Ported from 18.6.6 ``legacy/npc-panel-18.6.6/app/factual_layer.py`` (version 1.0), and
compared with the unit's own module in ``test_respondent_facts.py``: *facts already
present in the panel must never be re-invented by a model.* A question that asks for
one of the respondent's recorded attributes (sex, age, education, region, ...) is
**DIRECT**: answered from the persona's attribute, never shown to the model. A
question that asks for an individual fact the persona does not carry (a diagnosis,
a mortgage, a brand owned) is **UNSUPPORTED**: the unit fails closed in LIVE mode,
and so does AIA -- the fieldwork step refuses before any call rather than let a
model invent it.

Differences from the unit, each deliberate:

* AIA questions carry no ``metadata`` (``fact_kind``, ``fact_source_field``) yet, so
  classification is by the unit's text patterns alone.
* "The panel's columns" are the persona's own attribute names: a DIRECT field the
  persona does not have is UNSUPPORTED, exactly as a missing panel column is.
* Choice mapping is AIA's option tuple (DK included last); the unit's 1-based index
  is returned 0-based by :func:`choice_index`.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .research_design import SpecQuestion

__all__ = [
    "FACT_LAYER_VERSION",
    "FactSpec",
    "FactStatus",
    "UnansweredFact",
    "choice_index",
    "classify_question",
    "deterministic_answer",
]

FACT_LAYER_VERSION: Final = "aia-fact-layer-1 (18.6.6 factual_layer 1.0)"


class FactStatus(StrEnum):
    DIRECT = "DIRECT"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_FACT = "NOT_FACT"


@dataclass(frozen=True, slots=True)
class FactSpec:
    status: FactStatus
    field: str = ""
    reason: str = ""


class UnansweredFact(ValueError):
    """A DIRECT fact cannot be mapped onto the question's options. The step refuses."""


def _norm(x: Any) -> str:
    s = str(x or "").strip().lower()
    s = s.replace("\u2013", "-").replace("\u2014", "-")  # en and em dash
    return re.sub(r"\s+", " ", s)


# The unit's patterns, verbatim (factual_layer.py:34-55). Deliberately conservative:
# a false positive here is worse than a model question.
_DIRECT_PATTERNS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("pohlavi", (r"\b(pohlaví|jste muž|jste žena|gender)\b",)),
    ("vek", (r"\b(kolik (je vám|vám je) let|váš věk|věk respondenta)\b",)),
    ("vzdelani", (r"\b(nejvyšší .*vzdělání|jaké máte vzdělání|dosažené vzdělání)\b",)),
    ("kraj", (r"\b(v jakém kraji|který kraj|kraj bydliště|ve kterém kraji)\b",)),
    ("trida_spolecenska", (r"\b(společenská třída|sociální třída)\b",)),
    ("zamestnan", (r"\b(jste zaměstnan|pracujete v současnosti|máte zaměstnání)\b",)),
    ("F_auto", (r"\b(vlastníte .*auto|máte .*automobil|má vaše domácnost .*auto)\b",)),
    ("F_bydleni", (r"\b(jak bydlíte|forma bydlení|typ bydlení|bydlíte v)\b",)),
    ("F_deti", (r"\b(máte děti|máte .*dítě|rodičem)\b",)),
    ("F_rodinny_stav", (r"\b(rodinný stav|jste ženat|jste vdaná|jste svobodn)\b",)),
    ("F_sam", (r"\b(žijete sám|žijete sama|jednočlenná domácnost)\b",)),
    ("F_strana", (r"\b(kterou stranu|koho byste volil|koho byste volila|volební preference)\b",)),
)

_UNSUPPORTED_PATTERNS: Final = (
    r"\b(diabet\w*|cukrovk\w*|celiak\w*|astma\w*|rakovin\w*|onkolog\w*|diagn[oó]z\w*|onemocn\w*|nemoc\w*)\b",
    r"\b(vlastníte|máte)\s+(hypot[eé]ku|úvěr|investic|akcie|krypt|psa|kočku)\b",
    r"\b(používáte|vlastníte|kupujete)\s+(značku|produkt|iphone|android)\b",
)


def classify_question(question: SpecQuestion, fields: set[str]) -> FactSpec:
    """``factual_layer.classify_question`` over the question text; ``fields`` = persona's."""
    text = _norm(question.text)
    for field, patterns in _DIRECT_PATTERNS:
        if any(re.search(p, text, flags=re.I) for p in patterns):
            if not fields or field in fields:
                return FactSpec(FactStatus.DIRECT, field, "detected authoritative fact")
            return FactSpec(
                FactStatus.UNSUPPORTED,
                field,
                f"Respondent neobsahuje očekávaný faktický údaj '{field}'.",
            )
    if any(re.search(p, text, flags=re.I) for p in _UNSUPPORTED_PATTERNS):
        return FactSpec(
            FactStatus.UNSUPPORTED,
            "",
            "Individuální fakt není u respondenta a není pro něj zaveden kalibrační prior.",
        )
    return FactSpec(FactStatus.NOT_FACT)


def _boolish(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, bool):
        return v
    s = _norm(v)
    if s in {"1", "1.0", "ano", "yes", "true"}:
        return True
    if s in {"0", "0.0", "ne", "no", "false"}:
        return False
    return None


_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "zenaty_vdana": ("ženatý/vdaná", "ženatý / vdaná", "ženat/vdaná", "v manželství"),
    "svobodny": ("svobodný/svobodná", "svobodný", "svobodná"),
    "rozvedeny": ("rozvedený/rozvedená", "rozvedený", "rozvedená"),
    "vdovec_vdova": ("vdovec/vdova", "vdovec", "vdova"),
}


def choice_index(categories: Sequence[str], value: Any) -> int | None:
    """``factual_layer._choice_index``, 0-based: the option a recorded value maps to."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    cats = [_norm(x) for x in categories]
    raw = _norm(value)
    if raw in cats:
        return cats.index(raw)
    b = _boolish(value)
    if b is not None:
        yes = {"ano", "ano, mám", "ano, vlastním", "ano, pracuji", "yes", "1"}
        no = {"ne", "ne, nemám", "ne, nevlastním", "nepracuji", "no", "0"}
        pool = yes if b else no
        for i, c in enumerate(cats):
            if c in pool or (b and c.startswith("ano")) or ((not b) and c.startswith("ne")):
                return i
    for alias in _ALIASES.get(raw, ()):
        an = _norm(alias)
        if an in cats:
            return cats.index(an)
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = None
    if num is not None:
        for i, c in enumerate(cats):
            m = re.search(r"(\d{1,3})\s*-\s*(\d{1,3})", c)
            if m and float(m.group(1)) <= num <= float(m.group(2)):
                return i
            m = re.search(r"(\d{1,3})\s*\+", c)
            if m and num >= float(m.group(1)):
                return i
            m = re.search(r"(\d{1,3})\s*(?:let\s*)?(?:a|nebo)\s*(?:více|výše)", c)
            if m and num >= float(m.group(1)):
                return i
            m = re.search(r"(?:více než|nad)\s*(\d{1,3})", c)
            if m and num > float(m.group(1)):
                return i
            m = re.search(r"(?:do|méně než)\s*(\d{1,3})", c)
            if m and num < float(m.group(1)):
                return i
    hits = [i for i, c in enumerate(cats) if raw and (raw in c or c in raw)]
    return hits[0] if len(hits) == 1 else None


def deterministic_answer(question: SpecQuestion, facts: Mapping[str, Any], spec: FactSpec) -> Any:
    """``factual_layer.deterministic_answer``: the answer from the respondent's own fact."""
    if spec.status is not FactStatus.DIRECT:
        raise ValueError("deterministic_answer requires a DIRECT FactSpec")
    value = facts.get(spec.field)
    if question.typ == "skala" and spec.field == "vek":
        if value is None or question.scale is None:
            raise UnansweredFact(f"{question.id}: no age to answer with")
        answer = round(float(value))
        low, high = question.scale
        if not low <= answer <= high:
            raise UnansweredFact(f"Faktická hodnota věku {answer} neleží ve škále {low}-{high}.")
        return answer
    if question.typ == "vyber":
        idx = choice_index(question.options, value)
        if idx is None:
            raise UnansweredFact(
                f"Faktický údaj '{spec.field}' s hodnotou {value!r} nelze jednoznačně "
                "mapovat na možnosti otázky."
            )
        return question.options[idx]
    if question.typ == "otevrena":
        return str(value)
    raise UnansweredFact(
        f"{question.id}: faktická otázka typu {question.typ!r} vyžaduje explicitní "
        "transformaci; odpověď modelem je zakázána."
    )
