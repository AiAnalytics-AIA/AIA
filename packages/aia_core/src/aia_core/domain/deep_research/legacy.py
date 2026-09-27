"""The 18.6.6 leakage screen and merge rules, ported exactly.

``legacy/npc-panel-18.6.6/app/research_context.py``: ``_canonical_url`` (112-121),
``_tokens`` / ``_similarity`` (124-134), ``_coerce_findings`` (205-233),
``_deterministic_target_overlap`` (313-332) and ``_merge_agents`` (335-387). Each
function here reproduces the unit's output exactly on the captured fixtures
(``tests/fixtures/deep_research/``, captured by ``tools/deep_research_capture.py``
and pinned with the unit source), including its quirks:

* ``_tokens`` keeps only ``a-z``, digits and the code-point range U+00E1..U+017E,
  so ``à`` and ``ß`` separate words while ``ÿ`` and ``ž`` do not;
* ``_canonical_url`` lower-cases the whole ``netloc`` (credentials and port too),
  strips one ``www.`` and one trailing slash, and drops the fragment;
* ``_merge_agents`` may pair a finding with a peer that an earlier finding
  already consumed, so one source can back two accepted items.

What AIA *uses* from here is the rule, not the pipeline: the agent's own leakage
label and :func:`deterministic_target_overlap` are the quarantine screen of
:mod:`.merge`, re-run against the final questionnaire at compile
(:mod:`.quarantine`). The unit's acceptance by self-reported ``source_quality``
and by two agents' lexical agreement is kept here for parity only; AIA accepts
on grounding and its declared source tables instead (ADR 0017 decision 4).

Pure: stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

__all__ = [
    "EXCLUDE_USE",
    "SAFE_USE",
    "LegacyFinding",
    "LegacyMergeConfig",
    "canonical_url",
    "coerce_findings",
    "deterministic_target_overlap",
    "merge_agents",
    "similarity",
    "tokens",
]

SAFE_USE: Final = "context_only"
EXCLUDE_USE: Final = "exclude_target_leakage"

# ``[^a-z0-9á-ž]+`` in the unit: the range is U+00E1..U+017E, precomposed.
_NOT_TOKEN: Final = re.compile("[^a-z0-9\u00e1-\u017e]+")
_STOP: Final = frozenset(
    {"a", "i", "v", "ve", "na", "se", "je", "jsou", "pro", "do", "z", "ze", "\u017ee", "to", "u"}
)
_OUTCOME_SIGNAL: Final = re.compile(
    "%|procent|respondent|dot\u00e1zan|dotazan|would|purchase intent|buy|koup|"
    "souhlas|support|vote|volil|prefer|zva\u017e|zvaz|ochot|intent|mean score|"
    "pr\u016fm\u011br|prumer",
    re.I,
)
_TRAILING_SLASH: Final = re.compile(r"/$")
_PRIMARY_TYPES: Final = frozenset({"primary_source", "peer_reviewed", "official_report"})


@dataclass(frozen=True, slots=True)
class LegacyFinding:
    """``research_context.EvidenceItem``, field for field and in the same order."""

    claim: str
    why_relevant: str
    source_title: str
    source_url: str
    source_date: str | None = None
    evidence_type: str = "other"
    geography: str = ""
    population: str = ""
    topics: tuple[str, ...] = field(default_factory=tuple)
    source_quality: float = 0.5
    outcome_overlap: bool = False
    recommended_use: str = SAFE_USE
    agent: str = ""

    def as_record(self) -> dict[str, Any]:
        """The unit's ``asdict(item)``: the same keys, ``topics`` as a list."""
        record = asdict(self)
        record["topics"] = list(self.topics)
        return record


@dataclass(frozen=True, slots=True)
class LegacyMergeConfig:
    """The three ``ResearchConfig`` fields ``_merge_agents`` reads, with their defaults."""

    strict_consensus: bool = True
    allow_single_agent_primary: bool = True
    max_context_blocks: int = 8


def canonical_url(url: object) -> str:
    """``_canonical_url``: http(s) only, lower-cased netloc without ``www.``, no fragment."""
    try:
        parts = urlsplit(str(url).strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        host = parts.netloc.lower().removeprefix("www.")
        path = _TRAILING_SLASH.sub("", parts.path or "")
        return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))
    except Exception:
        return ""


def tokens(text: object) -> set[str]:
    """``_tokens``: lower-cased words of four or more characters, minus stop words."""
    words = _NOT_TOKEN.sub(" ", str(text).lower())
    return {w for w in words.split() if len(w) >= 4 and w not in _STOP}


def similarity(a: object, b: object) -> float:
    """``_similarity``: the Jaccard index of the two token sets; 0 when either is empty."""
    x, y = tokens(a), tokens(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def deterministic_target_overlap(claim: str, questions: Sequence[Mapping[str, Any]]) -> bool:
    """``_deterministic_target_overlap``: an outcome signal *and* lexical overlap >= 0.24.

    The unit's docstring states the rule: prior outcomes close to the tested wording
    are exactly the evidence that makes a synthetic panel look accurate without
    predicting anything, so a claim with outcome-like language that overlaps any
    target question's text and categories is quarantined, whatever the agent said.
    """
    if not _OUTCOME_SIGNAL.search(claim.lower()):
        return False
    for question in questions:
        target = str(question.get("text", "")) + " " + " ".join(question.get("kategorie") or [])
        if similarity(claim, target) >= 0.24:
            return True
    return False


def coerce_findings(obj: object, agent: str) -> list[LegacyFinding]:
    """``_coerce_findings``: the unit's reading of one agent's raw findings."""
    out: list[LegacyFinding] = []
    raw = obj.get("findings", []) if isinstance(obj, dict) else []
    for x in raw:
        try:
            url = canonical_url(x.get("source_url", ""))
            if not url:
                continue
            use = str(x.get("recommended_use", SAFE_USE))
            overlap = bool(x.get("outcome_overlap", False))
            if overlap:
                use = EXCLUDE_USE
            out.append(
                LegacyFinding(
                    claim=str(x.get("claim", "")).strip()[:1200],
                    why_relevant=str(x.get("why_relevant", "")).strip()[:600],
                    source_title=str(x.get("source_title", "")).strip()[:300],
                    source_url=url,
                    source_date=(str(x.get("source_date"))[:40] if x.get("source_date") else None),
                    evidence_type=str(x.get("evidence_type", "other")).strip().lower(),
                    geography=str(x.get("geography", "")).strip()[:100],
                    population=str(x.get("population", "")).strip()[:160],
                    topics=tuple(
                        [str(t).strip() for t in (x.get("topics") or []) if str(t).strip()][:8]
                    ),
                    source_quality=max(0.0, min(1.0, float(x.get("source_quality", 0.5)))),
                    outcome_overlap=overlap,
                    recommended_use=use,
                    agent=agent,
                )
            )
        except Exception:
            continue
    return [x for x in out if x.claim and x.source_title]


def merge_agents(
    findings: Sequence[LegacyFinding],
    config: LegacyMergeConfig,
    questions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``_merge_agents`` over the agents' findings in agent order: (accepted, quarantined)."""
    quarantined: list[dict[str, Any]] = []
    safe: list[LegacyFinding] = []
    for x in findings:
        overlap = deterministic_target_overlap(x.claim, questions)
        labelled = x.outcome_overlap or x.recommended_use != SAFE_USE
        if labelled or overlap:
            reason = "target_outcome_overlap" if labelled else "deterministic_target_overlap"
            quarantined.append({**x.as_record(), "reason": reason})
        elif x.source_quality < 0.55:
            quarantined.append({**x.as_record(), "reason": "low_source_quality"})
        else:
            safe.append(x)

    accepted: list[dict[str, Any]] = []
    used: set[int] = set()
    for i, x in enumerate(safe):
        if i in used:
            continue
        peers: list[tuple[int, LegacyFinding]] = []
        for j, y in enumerate(safe):
            if j == i or y.agent == x.agent:
                continue
            same_url = canonical_url(y.source_url) == canonical_url(x.source_url)
            similar = similarity(x.claim, y.claim) >= 0.42
            if same_url or similar:
                peers.append((j, y))
        if peers:
            j, y = max(peers, key=lambda z: z[1].source_quality)
            used.update({i, j})
            best = x if x.source_quality >= y.source_quality else y
            accepted.append(
                {
                    **best.as_record(),
                    "consensus": True,
                    "agents": sorted({x.agent, y.agent}),
                    "supporting_urls": sorted(
                        {canonical_url(x.source_url), canonical_url(y.source_url)}
                    ),
                    "merge_confidence": round(
                        min(0.98, 0.55 + 0.22 * (x.source_quality + y.source_quality)), 3
                    ),
                }
            )
        elif not config.strict_consensus or (
            config.allow_single_agent_primary
            and x.evidence_type in _PRIMARY_TYPES
            and x.source_quality >= 0.90
        ):
            used.add(i)
            accepted.append(
                {
                    **x.as_record(),
                    "consensus": False,
                    "agents": [x.agent],
                    "supporting_urls": [canonical_url(x.source_url)],
                    "merge_confidence": round(0.65 * x.source_quality, 3),
                }
            )
        else:
            quarantined.append({**x.as_record(), "reason": "no_independent_confirmation"})

    accepted.sort(
        key=lambda a: (bool(a.get("consensus")), float(a.get("merge_confidence", 0))),
        reverse=True,
    )
    return accepted[: config.max_context_blocks], quarantined
