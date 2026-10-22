"""A report's document model stored beside the DOCX it was rendered from (report-delivery RD5a).

One path for the internal draft (the worker's REPORT step) and the client report (its download):
the document is stored under the DOCX's input fingerprint and names that DOCX by id and SHA-256.
"""

from __future__ import annotations

from typing import Any

from aia_core.domain.report.document_model import (
    DOCUMENT_MODEL_CONTRACT,
    DOCUMENT_MODEL_MEDIA_TYPE,
    document_bytes,
)
from aia_core.domain.report.model import ReportDocument
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository


def beside(model: Artifact, docx: Artifact) -> bool:
    """Is ``model`` the document of exactly ``docx``?"""
    return (
        model.metadata.get("docx_artifact_id") == docx.artifact_id
        and model.metadata.get("docx_sha256") == docx.sha256
    )


def store_document_beside(
    repo: ArtifactRepository,
    docx: Artifact,
    document: ReportDocument,
    *,
    artifact_type: str,
    metadata: dict[str, Any],
    runtime_version: str = "",
    produced_by_job_id: str | None = None,
) -> Artifact:
    """``document`` stored beside ``docx`` under its fingerprint, or the one already there.

    Reused by fingerprint only when it names this DOCX: a DOCX stored again under the same
    fingerprint (the first one turned CORRUPT, so the step stored another) gets a document of
    its own, never the first DOCX's, which its route would refuse on every read (review of
    #584). The newest is found first next time, so it is stored once."""
    put: dict[str, Any] = {
        "project_id": docx.project_id,
        "revision": docx.revision,
        "stage_type": docx.stage_type,
        "artifact_type": artifact_type,
        "data": document_bytes(document),
        "content_type": DOCUMENT_MODEL_MEDIA_TYPE,
        "input_fingerprint": docx.input_fingerprint,
        "runtime_version": runtime_version,
        "produced_by_job_id": produced_by_job_id,
        "metadata": {
            **metadata,
            "docx_artifact_id": docx.artifact_id,
            "docx_sha256": docx.sha256,
            "document_contract": DOCUMENT_MODEL_CONTRACT,
        },
        "depends_on": [docx.artifact_id],
    }
    model, _created = repo.put(**put)
    if (
        not beside(model, docx)
        or model.metadata.get("document_contract") != DOCUMENT_MODEL_CONTRACT
    ):
        # Another DOCX's, or one of an older contract a reader of today's cannot judge in full.
        model, _created = repo.put(**put, reuse=False)
    return model
