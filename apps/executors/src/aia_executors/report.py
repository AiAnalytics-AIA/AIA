"""Store an AIA-branded internal draft after all native analysis modules finish."""

from __future__ import annotations

import hashlib
import time

from aia_core.application.analysis_results import ReconstructionRefused, reconstruct_run
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE,
    INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
    RESEARCH_SUBTITLE,
    ReportCompositionRefused,
    beside_outputs,
    compose_internal_report,
)
from aia_core.application.report_chapters import report_chapters
from aia_core.application.report_document import store_document_beside
from aia_core.application.report_export import (
    Export,
    ReviewUnrecorded,
    export_docx,
    exports_stamped,
    review_stamp_record,
)
from aia_core.application.report_variants import PDF_DISABLED, RENDERABLE_REPORTS
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.fieldwork import origin_kind
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import Classification, ReportKind, ReportMeta
from aia_core.domain.report.review import REVIEW_STAMP_CONTRACT, ReviewState
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import REPORT_PDF_STEP_KIND, REPORT_STEP_KIND
from aia_core.infrastructure.artifact_repository import ArtifactNotFound
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.report_pdf import (
    PDF_MEDIA_TYPE,
    REPORT_PDF_KEY,
    PdfConversionFailed,
    PdfConverter,
)
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from .research import upstream_artifact

REPORT_ARTIFACT_TYPE = INTERNAL_REPORT_ARTIFACT_TYPE
# -14: a ledger number in prose, a table or a caption is a locked, tagged content control
# (artifact-report RPT8a, part 1), so a draft rendered before is never reused for an editor.
# -16: KPI tiles, figures, the evidence appendix and suppressed counts locked too (RPT8a, part 2;
# -15 is the brief's goal, F19).
# -17: the map's numbers locked under their stored map (map:<battery>/<method>; RPT8a, part 3).
# -18: the design and method chapters' numbers locked under their sources (design:, run:).
REPORT_CONTRACT_VERSION = "aia-internal-report-18"
REPORT_PDF_ARTIFACT_TYPE = INTERNAL_REPORT_PDF_ARTIFACT_TYPE
REPORT_DOCUMENT_ARTIFACT_TYPE = INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE


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
                    identifiers=(
                        ("Běh", step.run_id),
                        ("Varianta", "základní zpráva bez literární rešerše"),
                    ),
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
                    research_question_gaps=chapters.gaps,
                    map_source=(chapters.map_artifact_id, chapters.map_sha256),
                    methodology_rules=chapters.methodology,
                    outputs=beside_outputs(run["steps"]),
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
            repo = research_artifacts(session, context.scope, self._store)
            artifact, created = repo.put(
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
                    **review_stamp_record(data),
                },
                depends_on=[*[m.artifact_id for m in sources], chapters.map_artifact_id],
            )
            if not created:
                # The DOCX this step stored before (an attempt released after it was stored) is
                # the report; rendering again may have given other bytes under the same
                # fingerprint, which holds the inputs, never the renderer. Its PDF renders it.
                data = repo.read(artifact.artifact_id)
            # The document the DOCX was rendered from, beside it under the same fingerprint
            # (report-delivery RD5a). The fingerprint holds the inputs and the contract, so a
            # DOCX found again finds its document again; one stored before RD5a gets its own now.
            model = store_document_beside(
                repo,
                artifact,
                document,
                artifact_type=REPORT_DOCUMENT_ARTIFACT_TYPE,
                metadata={
                    "run_id": step.run_id,
                    "step_id": step.step_id,
                    "report_kind": ReportKind.INTERNAL.value,
                    "report_contract": REPORT_CONTRACT_VERSION,
                },
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
            )
        output: dict[str, object] = {
            "artifact_id": artifact.artifact_id,
            "artifact_type": REPORT_ARTIFACT_TYPE,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "reused": not created,
            "review_state": "DRAFT_UNAPPROVED",
            "document": {"artifact_id": model.artifact_id, "sha256": model.sha256},
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
        try:
            return store_pdf_rendering(
                step,
                context,
                store=self._store,
                build=self._build,
                pdf=self._pdf,
                docx_id=docx_id,
                docx=docx,
                metadata={"run_id": run},
            )
        except PdfConversionFailed as exc:
            return {"state": "FAILED", "reason": "pdf_conversion_failed", "message": str(exc)}


def store_pdf_rendering(
    step: StepInput,
    context: StepContext,
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    pdf: PdfConverter,
    docx_id: str,
    docx: bytes,
    metadata: dict[str, object],
    approved: Export | None = None,
) -> dict[str, object]:
    """``docx`` (the stored artifact ``docx_id``) rendered as PDF and stored beside it, or the
    PDF already stored for the same bytes and converter. Raises :class:`PdfConversionFailed`.

    One path for every report variant (plan ``research-integrity-report`` chunk 3): the PDF is
    a rendering of a stored DOCX, never a second composition, so both formats carry the same
    content for the same run and selected review.

    ``approved``: the approved version's export (D2), whose bytes are ``docx``. Its mark and
    the stamp contract enter the key and the metadata, so a stamped export's PDF is never the
    draft's. A version stored before the stamp layout exports its stored bytes: the rendering
    of those bytes made while it was a draft is its approved PDF as well
    (``report_variants.variant_pdf``), and one made since records the approval beside it."""
    # The artifact id is part of the key: a PDF is served only as the rendering of the DOCX it
    # names (rendering_of), so two drafts with the same bytes each get their own. A draft's key
    # is as it always was, so every stored draft PDF is found again.
    review: dict[str, object] = {}
    if approved is not None:
        mark = approved.mark
        assert mark.state is ReviewState.APPROVED and mark.approved_on is not None
        review = {
            "review_state": mark.state.value,
            "approved_on": mark.approved_on.isoformat(),
            "review_stamp": REVIEW_STAMP_CONTRACT,
            "stamped": approved.stamped,
            "docx_sha256": mark.sha256,
        }
    key = fingerprint(
        {
            "docx": hashlib.sha256(docx).hexdigest(),
            "docx_artifact_id": docx_id,
            "converter": pdf.version,
            **({"review": review} if review else {}),
        }
    )
    context.checkpoint()
    with context.transaction() as (session, _workflow):
        found = research_artifacts(session, context.scope, store).find_reusable(
            project_id=step.project_id,
            stage_type=step.stage_type,
            artifact_type=REPORT_PDF_ARTIFACT_TYPE,
            input_fingerprint=key,
        )
    if found is None:
        started = time.perf_counter()
        rendered = pdf.convert(docx)
        seconds = round(time.perf_counter() - started, 2)
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            found, _created = research_artifacts(session, context.scope, store).put(
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=REPORT_PDF_ARTIFACT_TYPE,
                data=rendered,
                content_type=PDF_MEDIA_TYPE,
                input_fingerprint=key,
                runtime_version=build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={
                    **metadata,
                    "step_id": step.step_id,
                    "report_kind": ReportKind.INTERNAL.value,
                    "rendering_of": docx_id,
                    "converter": pdf.version,
                    "conversion_seconds": seconds,
                    **review,
                },
                depends_on=[docx_id],
            )
    return {
        "state": "READY",
        "artifact_id": found.artifact_id,
        "artifact_type": REPORT_PDF_ARTIFACT_TYPE,
        "sha256": found.sha256,
        "size_bytes": found.size_bytes,
    }


class ReportPdfExecutor:
    """The ``report_pdf`` step: an already stored report DOCX rendered as PDF.

    Its payload names the DOCX by artifact id and SHA-256 and the run (and review) it reports;
    a DOCX that is not one of those, or whose bytes changed, is refused, never rendered. With
    no converter composed it fails by name (``pdf_disabled``) instead of staying queued.

    The payload also names the version's review as the person asking read it (D2; a job asked
    before that reads as a draft's). The step reads the mark again itself: a draft's job renders
    the stored bytes, an approved version's renders its export -- the stamped DOCX a download of
    it is. A draft's job whose version was approved since ends superseded, rendering nothing,
    when its export is stamped (that is rendered under a key of its own); one whose export is
    its stored bytes (stored before the stamp layout) renders them, its approved PDF. A mark
    that moved any other way is refused (``report_review_changed``).
    """

    def __init__(
        self, *, store: ArtifactStore, build: BuildIdentity, pdf: PdfConverter | None = None
    ) -> None:
        self._store = store
        self._build = build
        self._pdf = pdf

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        payload = step.payload
        docx_id = str(payload.get("docx_artifact_id") or "")
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            repo = research_artifacts(session, context.scope, self._store)
            try:
                artifact = repo.get(docx_id)
                exported = export_docx(repo, artifact)
            except (ArtifactNotFound, IntegrityError, ObjectNotFound) as exc:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={"reason": "report_docx_missing", "message": str(exc)},
                )
            except ReviewUnrecorded as exc:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={
                        "code": "report_review_unrecorded",
                        "reason": "report_review_unrecorded",
                        "message": str(exc),
                    },
                )
        if (
            artifact.artifact_type not in RENDERABLE_REPORTS
            or artifact.sha256 != payload.get("docx_sha256")
            or artifact.metadata.get("run_id") != payload.get("run_id")
            or artifact.metadata.get("deep_research_run_id") != payload.get("deep_research_run_id")
        ):
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "report_docx_mismatch", "message": "not the report this names"},
            )
        # A job asked before payloads named the review was asked for a draft.
        mark = exported.mark
        asked = (payload.get("review_state") or ReviewState.DRAFT.value, payload.get("approved_on"))
        now = (mark.state.value, mark.approved_on.isoformat() if mark.approved_on else None)
        approved_since = asked[0] == ReviewState.DRAFT.value and mark.state is ReviewState.APPROVED
        if approved_since and exports_stamped(artifact, mark):
            # Approved while its draft's PDF waited: a person's routine path, not a broken run.
            # The draft has no PDF to make any more and its stamped export is rendered under a
            # key of its own, so the job ends having converted and stored nothing.
            return Succeeded(output={"state": "SUPERSEDED", "reason": "report_review_changed"})
        # A version stored before the stamp layout exports its stored bytes once approved: the
        # rendering this job was asked for is its approved PDF, made here as it would have been.
        if asked != now and not approved_since:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "code": "report_review_changed",
                    "reason": "report_review_changed",
                    "message": f"asked as {asked}, now {now}",
                },
            )
        if self._pdf is None:
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={"reason": PDF_DISABLED, "message": f"{REPORT_PDF_KEY} is off"},
            )
        try:
            output = store_pdf_rendering(
                step,
                context,
                store=self._store,
                build=self._build,
                pdf=self._pdf,
                docx_id=docx_id,
                docx=exported.data,
                approved=exported if mark.state is ReviewState.APPROVED else None,
                metadata={
                    "run_id": payload.get("run_id"),
                    **(
                        {"deep_research_run_id": payload["deep_research_run_id"]}
                        if payload.get("deep_research_run_id")
                        else {}
                    ),
                },
            )
        except PdfConversionFailed as exc:
            return Failed(
                FailureClass.TRANSIENT,
                error={"reason": "pdf_conversion_failed", "message": str(exc)},
            )
        return Succeeded(output=output)


def report_registry(
    *, store: ArtifactStore, build: BuildIdentity, pdf: PdfConverter | None = None
) -> dict[str, ReportExecutor | ReportPdfExecutor]:
    return {
        REPORT_STEP_KIND: ReportExecutor(store=store, build=build, pdf=pdf),
        REPORT_PDF_STEP_KIND: ReportPdfExecutor(store=store, build=build, pdf=pdf),
    }
