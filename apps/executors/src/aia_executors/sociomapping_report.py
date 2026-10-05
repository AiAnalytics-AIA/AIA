"""Render the experimental Sociomapping's internal draft (plan sociomapping-engine I2).

Reads the run's ``research_sociomapping`` artifact, draws each set's map, composes the
INTERNAL document and stores the DOCX as ``research_sociomapping_docx`` on the Study's
design project. The draft is never approved here, and its metadata says it is experimental.
"""

from __future__ import annotations

from typing import Any

from aia_core.application.research import research_artifacts
from aia_core.application.sociomapping_report import (
    SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
    SOCIOMAPPING_REPORT_CONTRACT,
    SociomappingReportRefused,
    compose_sociomapping_report,
)
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import Classification, ReportKind, ReportMeta
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import SOCIOMAPPING_REPORT_STEP_KIND
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.report_docx.sociomapping_figure import draw_sociomapping_map
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from .research import SOCIOMAPPING, upstream_artifact


def _scale_labels(value: Any) -> tuple[str, str] | None:
    if isinstance(value, list) and len(value) == 2:
        return str(value[0]), str(value[1])
    return None


def _images(result: dict[str, Any]) -> dict[str, bytes]:
    images: dict[str, bytes] = {}
    for battery in result.get("batteries", []):
        layout = battery.get("layout")
        if battery.get("status") != "MAPPED" or layout is None:
            continue
        labels = {o["id"]: o["label"] for o in battery["objects"]}
        heights = dict(
            zip([o["id"] for o in battery["objects"]], battery["heights"]["on_scale"], strict=True)
        )
        low, high = battery["rating_scale"]
        images[battery["battery_id"]] = draw_sociomapping_map(
            [labels[e] for e in layout["element_ids"]],
            layout["positions"],
            [heights[e] for e in layout["element_ids"]],
            (float(low), float(high)),
            _scale_labels(battery.get("scale_labels")),
        )
    return images


class SociomappingReportExecutor:
    """A deterministic REPORT step over the stored experimental result."""

    def __init__(self, *, store: ArtifactStore, build: BuildIdentity) -> None:
        self._store = store
        self._build = build

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            source_id = upstream_artifact(workflow, step, "sociomapping")
            if source_id is None:
                return Failed(
                    FailureClass.MISSING_CONFIGURATION,
                    error={"message": "the run's 'sociomapping' step recorded no artifact"},
                )
            repo = research_artifacts(session, context.scope, self._store)
            source = repo.get(source_id)
            result = repo.read_json(source_id)["sociomapping"]
            run = workflow.get_run(step.run_id)
            names = ScopeRepository(session)
            study = names.get_study(context.scope)
            client = names.client_of_study(context.scope)
        meta = ReportMeta(
            kind=ReportKind.INTERNAL,
            title="Sociomapping — experimentální metoda AIA",
            subtitle="Interní pracovní koncept · fiktivní data"
            if result.get("synthetic_data")
            else "Interní pracovní koncept",
            client_name=client.name,
            study_name=study.name,
            study_id=context.scope.study_id,
            issued_on=run["created_at"].date(),
            revision=step.project_revision,
            method_status=METHOD_STATUS_PENDING,
            classification=Classification.INTERNAL,
            identifiers=(("Běh", step.run_id), ("Výsledek", source_id)),
        )
        audit = (
            ("Běh", step.run_id),
            ("Krok", step.step_id),
            ("Artefakt výsledku", source_id),
            ("SHA-256 výsledku", source.sha256),
            ("Sestavení", self._build.sha or "neuvedeno"),
            ("Smlouva zprávy", SOCIOMAPPING_REPORT_CONTRACT),
        )
        try:
            document = compose_sociomapping_report(result, meta, _images(result), audit)
        except (SociomappingReportRefused, ReportInvalid) as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "report_inputs_refused", "message": str(exc)},
            )
        context.checkpoint()
        data = DocxRenderer().render(document)
        input_fingerprint = fingerprint(
            {
                "contract": SOCIOMAPPING_REPORT_CONTRACT,
                "run_id": step.run_id,
                "source": source.sha256,
                "client": meta.client_name,
                "study": meta.study_name,
                "issued_on": meta.issued_on.isoformat(),
            }
        )
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            artifact, created = research_artifacts(session, context.scope, self._store).put(
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
                data=data,
                content_type=DocxRenderer.media_type,
                input_fingerprint=input_fingerprint,
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={
                    "run_id": step.run_id,
                    "step_id": step.step_id,
                    "report_kind": ReportKind.INTERNAL.value,
                    "review_state": "DRAFT_UNAPPROVED",
                    "method_status": result["method_status"],
                    "client_facing": False,
                    "synthetic": bool(result.get("synthetic_data")),
                    "source_kind": SOCIOMAPPING,
                },
                depends_on=[source_id],
            )
        context.progress("zpráva Sociomappingu uložena (interní koncept)")
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "artifact_type": SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "reused": not created,
                "review_state": "DRAFT_UNAPPROVED",
                "method_status": result["method_status"],
            }
        )


def sociomapping_report_registry(
    *, store: ArtifactStore, build: BuildIdentity
) -> dict[str, SociomappingReportExecutor]:
    return {SOCIOMAPPING_REPORT_STEP_KIND: SociomappingReportExecutor(store=store, build=build)}
