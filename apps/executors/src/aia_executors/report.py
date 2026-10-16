"""Store an AIA-branded internal draft after all native analysis modules finish."""

from __future__ import annotations

import hashlib
import time

from aia_core.application.analysis_results import ReconstructionRefused, reconstruct_run
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
    RESEARCH_SUBTITLE,
    ReportCompositionRefused,
    compose_internal_report,
)
from aia_core.application.report_chapters import report_chapters
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.fieldwork import origin_kind
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import Classification, ReportKind, ReportMeta
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import REPORT_STEP_KIND
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.report_pdf import PDF_MEDIA_TYPE, PdfConversionFailed, PdfConverter
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from .research import upstream_artifact

REPORT_ARTIFACT_TYPE = INTERNAL_REPORT_ARTIFACT_TYPE
REPORT_CONTRACT_VERSION = "aia-internal-report-8"
REPORT_PDF_ARTIFACT_TYPE = INTERNAL_REPORT_PDF_ARTIFACT_TYPE


class ReportExecutor:
    """A deterministic REPORT step. It never drafts claims or approves delivery."""

    def __init__(
        self, *, store: ArtifactStore, build: BuildIdentity, pdf: PdfConverter | None = None
    ) -> None:
        self._store = store
        self._build = build
        self._pdf = pdf

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            try:
                run = workflow.get_run(step.run_id)
                analysis = reconstruct_run(session, context.scope, self._store, run_id=step.run_id)
                first = analysis.modules.get(ANALYSIS_MODULES[0].module_id)
                if first is None or first.result is None:
                    raise ReportCompositionRefused("executive analysis is incomplete")
                names = ScopeRepository(session)
                study = names.get_study(context.scope)
                client = names.client_of_study(context.scope)
                meta = ReportMeta(
                    kind=ReportKind.INTERNAL,
                    title="Interní analytická zpráva",
                    subtitle=RESEARCH_SUBTITLE[origin_kind(first.record.labels.data_origin)],
                    client_name=client.name,
                    study_name=study.name,
                    study_id=context.scope.study_id,
                    issued_on=run["created_at"].date(),
                    revision=step.project_revision,
                    method_status=first.result.method_status,
                    classification=Classification.INTERNAL,
                    identifiers=(("Běh", step.run_id),),
                )
                # Maps, every question's numbers, the design and who answered: the same
                # chapters as the report with literature, from the run's verified sources.
                chapters = report_chapters(
                    research_artifacts(session, context.scope, self._store),
                    run,
                    analysis,
                    map_artifact_id=upstream_artifact(workflow, step, "sociomap"),
                    run_id=step.run_id,
                )
                document = compose_internal_report(
                    analysis,
                    meta,
                    map_sections=chapters.maps,
                    question_tables=chapters.questions,
                    design=chapters.design,
                    method=chapters.method,
                )
            except (
                ReconstructionRefused,
                ReportCompositionRefused,
                ReportInvalid,
                ValueError,
            ) as exc:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={"reason": "report_inputs_refused", "message": str(exc)},
                )

        context.checkpoint()
        data = DocxRenderer().render(document)
        sources = [analysis.modules[m.module_id] for m in ANALYSIS_MODULES]
        input_fingerprint = fingerprint(
            {
                "contract": REPORT_CONTRACT_VERSION,
                "run_id": step.run_id,
                "sources": [m.artifact_sha256 for m in sources],
                "sociomap": chapters.map_sha256,
                "title": meta.title,
                "subtitle": meta.subtitle,
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
                artifact_type=REPORT_ARTIFACT_TYPE,
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
                    "synthetic": bool(first.record.labels.simulated_respondents),
                    "data_origin": first.record.labels.data_origin.value,
                    "map_source_sha256": chapters.map_sha256,
                    "report_contract": REPORT_CONTRACT_VERSION,
                },
                depends_on=[*[m.artifact_id for m in sources], chapters.map_artifact_id],
            )
        output: dict[str, object] = {
            "artifact_id": artifact.artifact_id,
            "artifact_type": REPORT_ARTIFACT_TYPE,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "reused": not created,
            "review_state": "DRAFT_UNAPPROVED",
        }
        if self._pdf is not None:
            output["pdf"] = self._store_pdf(
                step, context, artifact.artifact_id, data, run=step.run_id
            )
        return Succeeded(output=output)

    def _store_pdf(
        self, step: StepInput, context: StepContext, docx_id: str, docx: bytes, *, run: str
    ) -> dict[str, object]:
        """The stored DOCX rendered as PDF, beside it. The DOCX is the report: a PDF that
        cannot be made is said so in the step's output and fails nothing."""
        assert self._pdf is not None
        key = fingerprint(
            {"docx": hashlib.sha256(docx).hexdigest(), "converter": self._pdf.version}
        )
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            found = research_artifacts(session, context.scope, self._store).find_reusable(
                project_id=step.project_id,
                stage_type=step.stage_type,
                artifact_type=REPORT_PDF_ARTIFACT_TYPE,
                input_fingerprint=key,
            )
        if found is None:
            started = time.perf_counter()
            try:
                pdf = self._pdf.convert(docx)
            except PdfConversionFailed as exc:
                return {"state": "FAILED", "reason": "pdf_conversion_failed", "message": str(exc)}
            seconds = round(time.perf_counter() - started, 2)
            context.checkpoint()
            with context.transaction() as (session, _workflow):
                found, _created = research_artifacts(session, context.scope, self._store).put(
                    project_id=step.project_id,
                    revision=step.project_revision,
                    stage_type=step.stage_type,
                    artifact_type=REPORT_PDF_ARTIFACT_TYPE,
                    data=pdf,
                    content_type=PDF_MEDIA_TYPE,
                    input_fingerprint=key,
                    runtime_version=self._build.sha or "",
                    produced_by_job_id=step.attempt_id,
                    metadata={
                        "run_id": run,
                        "step_id": step.step_id,
                        "report_kind": ReportKind.INTERNAL.value,
                        "rendering_of": docx_id,
                        "converter": self._pdf.version,
                        "conversion_seconds": seconds,
                    },
                    depends_on=[docx_id],
                )
        return {
            "state": "READY",
            "artifact_id": found.artifact_id,
            "sha256": found.sha256,
            "size_bytes": found.size_bytes,
        }


def report_registry(
    *, store: ArtifactStore, build: BuildIdentity, pdf: PdfConverter | None = None
) -> dict[str, ReportExecutor]:
    return {REPORT_STEP_KIND: ReportExecutor(store=store, build=build, pdf=pdf)}
