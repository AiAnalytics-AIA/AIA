"""Store an AIA-branded internal draft after all native analysis modules finish."""

from __future__ import annotations

from aia_core.application.analysis_results import ReconstructionRefused, reconstruct_run
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    ReportCompositionRefused,
    compose_internal_report,
)
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import Classification, ReportKind, ReportMeta
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import REPORT_STEP_KIND
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

REPORT_ARTIFACT_TYPE = INTERNAL_REPORT_ARTIFACT_TYPE
REPORT_CONTRACT_VERSION = "aia-internal-report-1"


class ReportExecutor:
    """A deterministic REPORT step. It never drafts claims or approves delivery."""

    def __init__(self, *, store: ArtifactStore, build: BuildIdentity) -> None:
        self._store = store
        self._build = build

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
                    subtitle="Syntetický výzkum"
                    if first.record.labels.simulated_respondents
                    else "Výzkum",
                    client_name=client.name,
                    study_name=study.name,
                    study_id=context.scope.study_id,
                    issued_on=run["created_at"].date(),
                    revision=step.project_revision,
                    method_status=first.result.method_status,
                    classification=Classification.INTERNAL,
                    identifiers=(("Běh", step.run_id),),
                )
                document = compose_internal_report(analysis, meta)
            except (ReconstructionRefused, ReportCompositionRefused, ReportInvalid) as exc:
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
                },
                depends_on=[m.artifact_id for m in sources],
            )
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "artifact_type": REPORT_ARTIFACT_TYPE,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "reused": not created,
                "review_state": "DRAFT_UNAPPROVED",
            }
        )


def report_registry(*, store: ArtifactStore, build: BuildIdentity) -> dict[str, ReportExecutor]:
    return {REPORT_STEP_KIND: ReportExecutor(store=store, build=build)}
