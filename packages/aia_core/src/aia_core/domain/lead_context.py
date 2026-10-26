"""What one Lead turn could see: the declared layers of its context and the turn's manifest.

ADR 0041 decision 2 and 3, plan ``lead-conversation`` LC1. Pure.

* **The layers are declared, not implied** (:data:`LEAD_LAYERS`): each layer of
  :func:`~aia_core.domain.research_lead.freeze_context`'s context, in its order, with the
  bound it is held to today and what happens when it is over. LC1 declares today's bounds and
  changes none of them; ADR 0041's floors, ceilings and allocation are LC4's.
* **Every turn has a manifest** (:func:`context_manifest`): per layer its bytes, its bound,
  the ids it carried and the ids it left out with the reason, computed from the frozen
  context alone, so two reads of the same context give the same manifest. With the turn's
  ``context_classification`` it also carries each layer's class and who answered for it.
* **Bounded by the number of layers, never by the history** (decision 3): a layer lists at
  most :data:`MANIFEST_IDS_MAX` included and omitted ids and counts the rest.

The manifest is a reading of the context, never an input to it: the context's hash, and so
the turn's identity, does not move.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .ai_contracts import canonical_json
from .ai_material import most_restrictive_material
from .lead_digest import DIGEST_SHARE_MAX_BYTES
from .lead_research_targets import (
    DEEP_RESEARCH_MAX_BYTES,
    DEEP_RESEARCH_RUNS,
    RUNS_FOR_TARGETS,
    TARGETS_MAX,
    TARGETS_MAX_BYTES,
)
from .research_agents import KNOWLEDGE_MAX_BYTES
from .research_lead import (
    CONTEXT_MAX_BYTES,
    EXTERNAL_LAYER,
    HISTORY_TURNS,
    NOTES_IN_CONTEXT,
    NOTES_MAX_BYTES,
    RUNS_IN_CONTEXT,
    context_bytes,
)
from .residency import DataClass

__all__ = [
    "LEAD_LAYERS",
    "MANIFEST_IDS_MAX",
    "MANIFEST_VERSION",
    "PART_LAYERS",
    "LeadLayer",
    "context_manifest",
    "manifest_view",
    "omitted_page",
]

MANIFEST_VERSION: Final = 1

#: The most ids a layer lists as included, and as omitted; the rest are counted.
MANIFEST_IDS_MAX: Final = 50


@dataclass(frozen=True, slots=True)
class LeadLayer:
    """One layer of a Lead turn's context.

    ``ceiling_bytes`` is the layer's own byte bound, ``None`` where only the whole context's
    :data:`~aia_core.domain.research_lead.CONTEXT_MAX_BYTES` holds it. ``bound`` and
    ``over_policy`` say, in words a manifest can show, what the layer keeps and what goes
    first when it is over.
    """

    name: str
    ceiling_bytes: int | None
    bound: str
    over_policy: str


#: The context's layers in :func:`freeze_context`'s order, with today's bounds (LC1).
LEAD_LAYERS: Final[tuple[LeadLayer, ...]] = (
    LeadLayer("prompt", None, "the pinned prompt, whole", "never shortened"),
    LeadLayer(
        "lead",
        NOTES_MAX_BYTES,
        f"name, SOUL and USER whole; the newest {NOTES_IN_CONTEXT} notes within "
        f"{NOTES_MAX_BYTES} bytes",
        "older notes are left out",
    ),
    LeadLayer(
        "knowledge",
        KNOWLEDGE_MAX_BYTES,
        f"approved items' titles and summaries within {KNOWLEDGE_MAX_BYTES} bytes",
        "items past the bound are left out by id",
    ),
    LeadLayer("study", None, "the study's name, client and money", "never shortened"),
    LeadLayer("design", None, "the working copy and its analysis, whole", "never shortened"),
    LeadLayer(
        "runs", None, f"the newest {RUNS_IN_CONTEXT} research runs", "older runs are left out"
    ),
    LeadLayer(
        "deep_research",
        DEEP_RESEARCH_MAX_BYTES,
        f"the newest {DEEP_RESEARCH_RUNS} Deep Research runs within {DEEP_RESEARCH_MAX_BYTES} "
        "bytes",
        "runs past the bound are counted",
    ),
    LeadLayer(
        "targets",
        TARGETS_MAX_BYTES,
        f"at most {TARGETS_MAX} results of the newest {RUNS_FOR_TARGETS} completed runs, "
        f"within {TARGETS_MAX_BYTES} bytes",
        "results past the bound are counted; a run that does not read is named",
    ),
    LeadLayer(
        EXTERNAL_LAYER,
        None,
        "the newest Design Research findings, pinned; context, never evidence",
        "never shortened",
    ),
    LeadLayer("view", None, "the stage, the focus and the message", "never shortened"),
    LeadLayer(
        "memory",
        DIGEST_SHARE_MAX_BYTES,
        "the conversation's decisions, from the approval ledger",
        "decisions past the share are counted with their ledger range",
    ),
    LeadLayer(
        "conversation",
        None,
        f"the newest {HISTORY_TURNS} turns",
        f"the oldest turns go first while the context is over {CONTEXT_MAX_BYTES} bytes",
    ),
)

_BY_NAME: Final = {spec.name: spec for spec in LEAD_LAYERS}

#: The part of a layer its ``ceiling_bytes`` bounds, measured as ``notes_layer`` and
#: ``knowledge_entries`` measure it.
_BOUNDED: Final = {
    "lead": "notes",
    "knowledge": "items",
    "memory": "digest",
    "deep_research": "runs",
    "targets": "candidates",
}


def _bytes(value: Any) -> int:
    return len(canonical_json(value if value is not None else []).encode("utf-8"))


#: Which layer each part of ``context_classification`` belongs to.
PART_LAYERS: Final[Mapping[str, str]] = {
    "prompt": "prompt",
    "lead_name": "lead",
    "lead_soul": "lead",
    "lead_user": "lead",
    "client_note": "lead",
    "personal_note": "lead",
    "note": "lead",
    "knowledge": "knowledge",
    "study_name": "study",
    "design": "design",
    "design_analysis": "design",
    "message": "view",
    "focus_label": "view",
    "external_context": EXTERNAL_LAYER,
    "deep_research": "deep_research",
    "targets": "targets",
    "decision_digest": "memory",
    "earlier_message": "conversation",
    "earlier_reply": "conversation",
}


def _ids(entry: Mapping[str, Any]) -> tuple[list[str], list[dict[str, str]], int | None]:
    """A layer's included ids, its omitted ids with their reason, and the count of what it
    left out that it cannot name: ``None`` where the layer drops without counting (the newest
    runs and notes are kept, the rest never counted; finding F4), never a 0 nobody counted."""
    name = entry["layer"]
    if name == "lead":
        return [str(n["memory_id"]) for n in entry.get("notes") or ()], [], None
    if name == "knowledge":
        included = [str(k["item_id"]) for k in entry.get("items") or ()]
        omitted = [{"id": str(i), "reason": "over_budget"} for i in entry.get("omitted_ids") or ()]
        return included, omitted, 0
    if name == "runs":
        return [str(r["run_id"]) for r in entry.get("runs") or ()], [], None
    if name == "deep_research":
        runs = [str(r["run_id"]) for r in entry.get("runs") or ()]
        return runs, [], int(entry.get("omitted") or 0)
    if name == "targets":
        # A candidate by its turn-local id; a completed run whose specification did not read
        # is named with its reason, the candidates past the bound counted.
        included = [str(c["id"]) for c in entry.get("candidates") or ()]
        unreadable = [
            {"id": str(r), "reason": "unreadable"} for r in entry.get("unreadable_runs") or ()
        ]
        return included, unreadable, int(entry.get("omitted") or 0)
    if name == "view":
        focus = entry.get("focus")
        if isinstance(focus, Mapping) and focus.get("id"):
            return [str(focus["id"])], [], 0
        return [], [], 0
    if name == "memory":
        # The digest's lines by their ledger row, or a waiting proposal by its turn and index;
        # what it left out is the count it froze (lead_digest's left_out).
        digest = entry.get("digest") or {}
        lines = [*digest.get("named", ()), *digest.get("undecided", ()), *digest.get("latest", ())]
        left = digest.get("left_out") or {}
        return (
            [str(x["ledger"]) if "ledger" in x else f"{x['turn']}#{x.get('index')}" for x in lines],
            [],
            int(left.get("decisions") or 0) + int(left.get("proposals") or 0),
        )
    if name == "conversation":
        # Earlier turns reach the context without their ids; their count is what is known.
        return [], [], int(entry.get("omitted_turns") or 0)
    return [], [], 0


def _classes(
    classification: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[DataClass | None, list[str]]]:
    by_layer: dict[str, list[Mapping[str, Any]]] = {}
    for part in classification:
        layer_name = PART_LAYERS.get(str(part.get("part")))
        if layer_name is not None:
            by_layer.setdefault(layer_name, []).append(part)
    out: dict[str, tuple[DataClass | None, list[str]]] = {}
    for layer_name, parts in by_layer.items():
        data_class = most_restrictive_material(
            [None if p.get("data_class") is None else DataClass(p["data_class"]) for p in parts]
        )
        sources = sorted({str(src) for p in parts if (src := p.get("source")) is not None})
        out[layer_name] = (data_class, sources)
    return out


def context_manifest(
    context: Mapping[str, Any],
    classification: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """What a frozen Lead context holds, layer by layer, and what it left out.

    ``classification`` is the turn's ``context_classification``; without it (at enqueue,
    before the worker has the operators' approvals) the layers carry no class. A layer's
    ``data_class`` is the most restrictive of its parts', ``None`` when a part has no class,
    and absent when no part of the turn falls in the layer. Pure and deterministic.
    """
    classes = _classes(classification) if classification is not None else {}
    layers: list[dict[str, Any]] = []
    for entry in context["layers"]:
        name = str(entry["layer"])
        spec = _BY_NAME.get(name)
        included, omitted, unnamed = _ids(entry)
        row: dict[str, Any] = {
            "layer": name,
            "bytes": _bytes(entry),
            "ceiling_bytes": spec.ceiling_bytes if spec else None,
            # What the ceiling bounds: the notes or the items, not the whole layer entry.
            "bounded_bytes": _bytes(entry.get(_BOUNDED[name])) if name in _BOUNDED else None,
            "bound": spec.bound if spec else None,
            "over_policy": spec.over_policy if spec else None,
            "included": included[:MANIFEST_IDS_MAX],
            "included_count": len(included),
            "omitted": omitted[:MANIFEST_IDS_MAX],
            "omitted_count": None if unnamed is None else len(omitted) + unnamed,
        }
        if name in classes:
            data_class, sources = classes[name]
            row["data_class"] = None if data_class is None else data_class.value
            row["class_sources"] = sources
        layers.append(row)
    return {
        "manifest_version": MANIFEST_VERSION,
        "total_bytes": context_bytes(context),
        "ceiling_bytes": CONTEXT_MAX_BYTES,
        "layers": layers,
    }


def manifest_view(context: Mapping[str, Any]) -> dict[str, Any]:
    """The manifest as the researcher reads it (Co Vedoucí vidí, LC2): every declared layer in
    :data:`LEAD_LAYERS`' order, read from the context the turn froze.

    A layer the context does not hold (a turn frozen before the layer existed, or a layer that
    was off for it) is ``recorded: False`` with its declared bound, never an empty layer: an
    empty layer would say the turn saw nothing there, which nobody recorded. Without classes:
    the class a turn was sent as is not the browser's (LC6 shows it).
    """
    manifest = context_manifest(context)
    rows = {row["layer"]: row for row in manifest["layers"]}
    layers = [
        {**rows[spec.name], "recorded": True}
        if spec.name in rows
        else {
            "layer": spec.name,
            "recorded": False,
            "ceiling_bytes": spec.ceiling_bytes,
            "bound": spec.bound,
            "over_policy": spec.over_policy,
        }
        for spec in LEAD_LAYERS
    ]
    return {**manifest, "layers": layers}


def omitted_page(
    context: Mapping[str, Any], layer_name: str, *, after: int = 0, limit: int = MANIFEST_IDS_MAX
) -> tuple[list[dict[str, str]], int]:
    """The ids ``layer_name`` left out, from position ``after``, at most ``limit`` of them, and
    how many it left out by id in all: the rest of what the manifest lists the first
    :data:`MANIFEST_IDS_MAX` of. A layer the context does not hold left nothing out by id."""
    for entry in context["layers"]:
        if entry["layer"] == layer_name:
            _, omitted, _ = _ids(entry)
            return omitted[after : after + limit], len(omitted)
    return [], 0
