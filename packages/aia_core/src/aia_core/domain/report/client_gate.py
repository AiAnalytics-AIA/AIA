"""The client deliverable's checks (report-delivery RD0; the product owner, MVPQ-09, 2026-10-20).

Read at approval over the stored document model the client DOCX was rendered from (RD5a), so
the version a person approves is the version judged. Since 2026-10-22 each is a warning, never a
refusal (the product owner: "Warnings for all of it"): shown in the approval dialog and recorded
with the approval, so who approved past which warning is on record. Each names its block:

* ``drill_down_content``: nothing that reads one respondent -- a verbatim quote, or a claim at
  the individual level (the drill-down stays the researcher's, never in a client export; F2);
* ``unadmitted_number``: every ref the document prints is one its ledger holds, on the client
  surface (the renderer's validation refused anything else before the DOCX was written; this
  reads the stored version, whatever wrote it);
* ``ledger_not_client_facing``: the document's numbers were admitted for another surface. The
  block checks still run over it, so a warning about the whole never hides one about a block.

``internal_source_cited`` waits for a chapter that cites a client source (RD11): no client
report cites one yet, so there is nothing to read. It is not a legal-rights review either way.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aia_core.domain.evidence.claims import ClaimLevel, ClaimSurface
from aia_core.domain.report.document_model import DOCUMENT_MODEL_CONTRACT


class GateCode(StrEnum):
    DRILL_DOWN = "drill_down_content"
    UNADMITTED_NUMBER = "unadmitted_number"
    LEDGER_NOT_CLIENT_FACING = "ledger_not_client_facing"
    #: The version has no stored document to judge: unknown, never passed.
    UNRECORDED = "gate_unrecorded"


@dataclass(frozen=True, slots=True)
class GateFinding:
    """One thing the deliverable's checks found, and the block it is in: a warning."""

    code: GateCode
    where: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"code": self.code.value, "where": self.where, "message": self.message}


def client_gate(document: Mapping[str, Any]) -> tuple[GateFinding, ...]:
    """Every finding on a stored client document model (``document_model.document_payload``);
    empty when nothing was found."""
    if document.get("contract") != DOCUMENT_MODEL_CONTRACT:
        # An older stored form names no claim's level: not judged, so not passed.
        return (
            GateFinding(
                GateCode.UNRECORDED,
                "report",
                "dokument verze je ve starší podobě, nelze ho ověřit; stáhněte ji znovu",
            ),
        )
    ledger = document["ledger"]
    findings: list[GateFinding] = []
    if ledger["surface"] != ClaimSurface.CLIENT_FACING.value:
        findings.append(
            GateFinding(
                GateCode.LEDGER_NOT_CLIENT_FACING,
                "evidence",
                f"čísla jsou připuštěna pro {ledger['surface']}, ne pro klienta",
            )
        )
    entries: Mapping[str, Any] = ledger["refs"]
    for section in document["sections"]:
        for block in section["blocks"]:
            where = block["id"]
            if block["type"] == "quote":
                findings.append(
                    GateFinding(GateCode.DRILL_DOWN, where, "doslovná odpověď jednoho respondenta")
                )
            for ref in block["refs"]:
                entry = entries.get(ref)
                if entry is None:
                    findings.append(
                        GateFinding(
                            GateCode.UNADMITTED_NUMBER, where, f"tiskne nepřipuštěné číslo {ref}"
                        )
                    )
                elif not entry["suppressed"] and entry["level"] == ClaimLevel.INDIVIDUAL.value:
                    findings.append(
                        GateFinding(
                            GateCode.DRILL_DOWN, where, f"číslo {ref} čte jednoho respondenta"
                        )
                    )
    return tuple(findings)
