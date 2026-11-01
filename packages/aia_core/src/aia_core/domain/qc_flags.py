"""A run's deterministic QC flags and where a decision on one lands (``run-qc-and-checkpoint``
RQC4a, W1).

A flag is a respondent the run QC's own rule names, by code: a straight-liner is a respondent
whose scale answers ``answer_spread`` reads as ``ONE`` or ``NO_SPREAD`` (RQC1), over the scale
questions alone and only where there are at least ``straight_lining_min_scales`` of them, exactly
the respondents ``run_qc`` counts in its ``straightlining`` share. Nothing pauses on a flag (F18):
it is stored with the run's QC, and a decision on it is a later act.

The accept target is a field of the run's QC record (RQC4): a decision names the flag, the QC
artifact it was read from and the dataset's SHA-256, and is checked against the stored flags
before anything takes it. A decision is ``keep`` or ``flag``; replacing a respondent is a new
linked run (RQC5), which has no command until its ADR and admission rule exist (ADR 0026
decision 4), so ``replace`` is refused by name. The worker that proposes a decision is W3's
(RQC4, LO9b); this module is the contract it and the screens read, and computes nothing new.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .fieldwork import Answer, FieldworkDataset
from .research_design import ResearchSpecification
from .run_qc import (
    UNIT_THRESHOLDS,
    QcNotReadable,
    QcThresholds,
    routed_questions_refusal,
    straight_liners,
)
from .straight_lining import AnswerSpread

__all__ = [
    "ACCEPT_FIELD",
    "QC_FLAGS_VERSION",
    "DecisionRefused",
    "FlagDecision",
    "FlagDecisionRecord",
    "FlagKind",
    "QcFlag",
    "check_decision",
    "dataset_flags",
    "flag_id",
    "flags_payload",
    "read_flags",
    "record_flags",
    "straight_liner_flags",
]

QC_FLAGS_VERSION: Final = "aia-qc-flags-1"
#: The field of the run's QC record (the ``research_qc`` artifact) a decision is written to.
ACCEPT_FIELD: Final = "flag_decisions"


class FlagKind(StrEnum):
    STRAIGHT_LINER = "straight_liner"


class FlagDecision(StrEnum):
    """What a person may decide about a flag. Replacement is a new linked run (RQC5), not one."""

    KEEP = "keep"
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class QcFlag:
    """One respondent a rule named: the rule's reading (``spread``) and the items it read, in
    questionnaire order."""

    kind: FlagKind
    respondent_id: str
    spread: AnswerSpread
    items: tuple[str, ...]

    @property
    def flag_id(self) -> str:
        return flag_id(self.kind, self.respondent_id)


def flag_id(kind: FlagKind, respondent_id: str) -> str:
    """A flag's id within its run's QC record: ``<kind>:<respondent id>``. The record pins the
    dataset, so the id needs no run in it."""
    if not respondent_id:
        raise ValueError("a flag names a respondent")
    return f"{kind.value}:{respondent_id}"


def straight_liner_flags(
    scale_items: Sequence[str],
    respondents: Sequence[tuple[str, Mapping[str, Answer]]],
    *,
    thresholds: QcThresholds = UNIT_THRESHOLDS,
) -> tuple[QcFlag, ...]:
    """The straight-liners among ``respondents`` (``(respondent id, answers)``), in their order:
    the run QC's own count (``run_qc.straight_liners``). Too few scale items and the rule reads
    nothing, as ``run_qc`` reads no share: no flag, never a respondent passed for it."""
    items = tuple(scale_items)
    liners = straight_liners(items, [a for _, a in respondents], thresholds=thresholds)
    return tuple(
        QcFlag(FlagKind.STRAIGHT_LINER, respondents[k][0], spread, items)
        for k, spread in liners or ()
    )


def dataset_flags(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    thresholds: QcThresholds = UNIT_THRESHOLDS,
) -> tuple[QcFlag, ...]:
    """:func:`straight_liner_flags` over a run's stored dataset, read as ``dataset_qc`` reads it
    (the caller has validated it; a conditional question is refused, ``QcNotReadable``)."""
    refusal = routed_questions_refusal(spec)
    if refusal is not None:
        raise QcNotReadable(refusal)
    return straight_liner_flags(
        [q.id for q in spec.questions if q.typ == "skala"],
        [(r.respondent_id, r.answers) for r in dataset.respondents],
        thresholds=thresholds,
    )


def flags_payload(flags: Sequence[QcFlag]) -> dict[str, Any]:
    """The flags as the run's QC record stores them, beside the record's ``inputs`` (lineage)."""
    return {
        "version": QC_FLAGS_VERSION,
        "flags": [
            {
                "id": f.flag_id,
                "kind": f.kind.value,
                "respondent_id": f.respondent_id,
                "spread": f.spread.value,
                "items": list(f.items),
            }
            for f in flags
        ],
    }


def read_flags(payload: Mapping[str, Any]) -> tuple[QcFlag, ...]:
    """Stored flags read back. Anything but this version's shape, or an id that is not its kind
    and respondent, is refused (``ValueError``), never read as no flags."""
    if payload.get("version") != QC_FLAGS_VERSION:
        raise ValueError(f"QC flags of version {payload.get('version')!r} are not readable here")
    flags = []
    try:
        for entry in payload["flags"]:
            items = entry["items"]
            if not isinstance(items, list):
                raise TypeError("items")
            flag = QcFlag(
                FlagKind(entry["kind"]),
                str(entry["respondent_id"]),
                AnswerSpread(entry["spread"]),
                tuple(str(i) for i in items),
            )
            if entry["id"] != flag.flag_id:
                raise ValueError(f"QC flag {entry['id']!r} does not name its kind and respondent")
            flags.append(flag)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"QC flags not in their stored shape ({exc})") from None
    return tuple(flags)


def record_flags(qc: Mapping[str, Any]) -> tuple[QcFlag, ...] | None:
    """The flags a run's stored QC record holds, or ``None`` where it recorded none: a QC that
    could not be read (``not_computed``) or one stored before the flags. Never read as none."""
    stored = qc.get("flags")
    return None if stored is None else read_flags(stored)


@dataclass(frozen=True, slots=True)
class FlagDecisionRecord:
    """A decision as the accept target takes it: written to ``ACCEPT_FIELD`` of the QC record
    ``qc_artifact_id`` names, read over the dataset ``dataset_sha256`` names. ``proposal`` is the
    worker's proposal it answers (W3), ``None`` for a person's own decision."""

    flag_id: str
    decision: str
    qc_artifact_id: str
    dataset_sha256: str
    decided_by: str
    proposal: str | None = None


class DecisionRefused(ValueError):
    """A decision the QC record does not take, with its code: ``replace_not_available``,
    ``decision_unknown``, ``no_author``, ``other_record``, ``stale_dataset``,
    ``flags_unrecorded`` or ``unknown_flag``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def check_decision(
    record: FlagDecisionRecord, *, qc_artifact_id: str, qc: Mapping[str, Any]
) -> FlagDecision:
    """The decision, once it holds against the stored QC record ``qc`` (the ``research_qc``
    artifact ``qc_artifact_id``, its ``inputs`` and ``flags``); else :class:`DecisionRefused`."""
    if record.decision == "replace":
        raise DecisionRefused(
            "replace_not_available",
            "replacing a respondent is a new linked run, which has no command yet (RQC5)",
        )
    try:
        decision = FlagDecision(record.decision)
    except ValueError:
        raise DecisionRefused(
            "decision_unknown", f"{record.decision!r} is not a decision on a QC flag"
        ) from None
    if not record.decided_by:
        raise DecisionRefused("no_author", "a decision names the person who made it")
    if record.qc_artifact_id != qc_artifact_id:
        raise DecisionRefused("other_record", "the decision names another run's QC record")
    if record.dataset_sha256 != qc.get("inputs", {}).get("dataset_sha256"):
        raise DecisionRefused("stale_dataset", "the decision was read over another dataset")
    flags = record_flags(qc)
    if flags is None:
        raise DecisionRefused("flags_unrecorded", "this QC record holds no flags")
    if record.flag_id not in {f.flag_id for f in flags}:
        raise DecisionRefused("unknown_flag", f"no QC flag {record.flag_id!r} in this record")
    return decision
