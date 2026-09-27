"""Central product policy for NPC Panel 15.0.

Historically, product heuristics were scattered across research_project.py,
study_contract.py, persona_depth.py and audience code. This module makes the
limits inspectable and configurable. Only mathematical/runtime impossibilities
should be hard blockers; methodological preferences are exposed as warnings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
import json

ROOT = Path(__file__).resolve().parent
POLICY_FILE = ROOT / "PRODUCT_POLICY.json"

_DEFAULTS: dict[str, Any] = {
    "research_design": {
        "sample_size": {"default": 300, "hard_min": 20, "hard_max": 10000},
        "tracked_set": {
            "recommended_min": 4, "recommended_max": 15, "hard_max": 40,
            "min_for_position_map": 3, "min_for_other_outputs": 1,
        },
    },
    "persona": {
        "allowed_evidence_roles": ["MEASURED_JOINT", "AGGREGATE_MARGIN"],
        "include_synthetic_ungrounded": False,
        "signal_budget": {"base": 4, "per_two_extra_topics": 1, "max": 8},
        "minimum_distinctiveness_z": 0.35,
    },
    "audience": {"ess_recommended_min": 150},
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    try:
        obj = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("policy root is not an object")
    except Exception:
        obj = {}
    return _merge(_DEFAULTS, obj)


def policy_value(*path: str, default: Any = None) -> Any:
    cur: Any = load_policy()
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def sample_size_bounds() -> tuple[int, int, int]:
    p = policy_value("research_design", "sample_size", default={}) or {}
    return int(p.get("hard_min", 20)), int(p.get("hard_max", 10000)), int(p.get("default", 300))


def tracked_set_limits(output_type: str) -> tuple[int, int, tuple[int, int]]:
    p = policy_value("research_design", "tracked_set", default={}) or {}
    hard_min = int(p.get("min_for_position_map", 3) if str(output_type) == "pozicni_mapa"
                   else p.get("min_for_other_outputs", 1))
    hard_max = int(p.get("hard_max", 40))
    rec = (int(p.get("recommended_min", 4)), int(p.get("recommended_max", 15)))
    return hard_min, hard_max, rec


def tracked_set_warning(count: int, output_type: str) -> str:
    hard_min, hard_max, (rec_min, rec_max) = tracked_set_limits(output_type)
    if count < hard_min or count > hard_max:
        return ""
    if count < rec_min:
        return f"Sada má jen {count} položek; pro stabilnější srovnání bývá vhodné přibližně {rec_min}–{rec_max}."
    if count > rec_max:
        return f"Sada má {count} položek; nad {rec_max} zvaž kratší baterii, split nebo MaxDiff, ale běh není automaticky blokován."
    return ""


def persona_signal_budget(topics: Iterable[str] | None) -> int:
    p = policy_value("persona", "signal_budget", default={}) or {}
    base = int(p.get("base", 4)); step = int(p.get("per_two_extra_topics", 1)); cap = int(p.get("max", 8))
    n = len({str(x).strip().lower() for x in (topics or []) if str(x).strip()})
    return max(1, min(cap, base + max(0, (n - 1) // 2) * step))
