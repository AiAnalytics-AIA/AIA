"""Every chapter a run's report is built from, from the run's verified sources (B1d).

The internal report the worker stores and the report with literature a person downloads
are the same study's report: they must carry the same chapters. Each used to verify the
run's map on its own and only one gained the design, method and question chapters. This
is the one place both get them from:

* the map: the run's frozen sociomap, checked to be derived from this run's dataset and
  specification, drawn as chapters (``compose_map_sections``);
* the specification: the one the map was derived from, whose fingerprint the analysis
  recorded -- the design chapter and the questionnaire come from it, and the question
  tables take its order and words;
* who answered and how: the run's own metadata and its dataset's origin.

A source that does not belong to the run's analysis refuses the report; nothing is
substituted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from aia_core.application.analysis_results import RunAnalysis
from aia_core.application.report import (
    SOCIOMAP_ARTIFACT,
    ReportCompositionRefused,
    sourced,
    upstream_artifacts,
)
from aia_core.application.report_design import DesignSections, compose_design_sections
from aia_core.application.report_maps import compose_map_sections
from aia_core.application.report_method import (
    METHOD_SOURCES,
    compose_method_section,
    compose_methodology_rules,
    research_question_gaps,
)
from aia_core.application.report_tables import (
    QuestionTables,
    compose_question_tables,
    scale_notes,
)
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.native import native_items
from aia_core.domain.report.model import ArtifactSource, Block, RunSource, Section, SpecSource
from aia_core.domain.research_design import ResearchSpecification
from aia_core.infrastructure.artifact_repository import ArtifactRepository, ArtifactStatus

SPECIFICATION_ARTIFACT = "research_specification"


@dataclass(frozen=True, slots=True)
class ReportChapters:
    """The run-derived chapters of one report, and the map they were drawn from."""

    maps: tuple[Section, ...]
    questions: QuestionTables
    design: DesignSections
    method: Section
    #: The rules the run was computed under, for the methodology chapter (CHN9).
    methodology: tuple[Block, ...]
    map_artifact_id: str
    map_sha256: str
    #: Each research question the run recorded as a gap at start, in words, by its text: the
    #: chapter that answers the research questions marks those answers (research_question_gaps).
    gaps: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class VerifiedMap:
    """A run's frozen Sociomap, verified as derived from its dataset and specification."""

    body: Mapping[str, Any]
    artifact_id: str
    sha256: str
    specification: ResearchSpecification


def verified_map(
    repo: ArtifactRepository,
    map_artifact_id: str | None,
    *,
    dataset_sha256: str,
    specification_fingerprint: str,
) -> VerifiedMap:
    """The run's Sociomap and the specification it was derived from, each checked to belong to
    the run's dataset and specification. Raises :class:`ReportCompositionRefused` otherwise."""
    if not map_artifact_id:
        raise ReportCompositionRefused("the run recorded no sociomap artifact")
    map_source = repo.get(map_artifact_id)
    if (
        map_source.artifact_type != SOCIOMAP_ARTIFACT
        or map_source.status is not ArtifactStatus.VALID
    ):
        raise ReportCompositionRefused("the map source is not a valid sociomap artifact")
    dependencies = repo.dependencies(map_artifact_id)
    if not any(d.sha256 == dataset_sha256 for d in dependencies):
        raise ReportCompositionRefused("the map is not derived from this run's dataset")
    specification = next(
        (
            payload
            for d in dependencies
            if d.artifact_type == SPECIFICATION_ARTIFACT
            and (payload := repo.read_json(d.artifact_id)).get("specification_fingerprint")
            == specification_fingerprint
        ),
        None,
    )
    if specification is None:
        raise ReportCompositionRefused("the map is not derived from this specification")
    return VerifiedMap(
        body=repo.read_json(map_artifact_id)["sociomap"],
        artifact_id=map_artifact_id,
        sha256=map_source.sha256,
        specification=ResearchSpecification.model_validate(specification["specification"]),
    )


def report_chapters(
    repo: ArtifactRepository,
    run: Mapping[str, Any],
    analysis: RunAnalysis,
    *,
    map_artifact_id: str | None,
    run_id: str,
) -> ReportChapters:
    """The map, question, design and method chapters of ``run``'s report, each from a source
    verified to belong to ``analysis``. Raises :class:`ReportCompositionRefused` otherwise."""
    from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots

    first = analysis.modules.get(AnalysisModuleId.EXECUTIVE)
    if first is None or first.result is None:
        raise ReportCompositionRefused("executive analysis is incomplete")
    mapped = verified_map(
        repo,
        map_artifact_id,
        dataset_sha256=first.record.sources.dataset.sha256,
        specification_fingerprint=first.record.sources.specification_fingerprint,
    )
    spec, body = mapped.specification, mapped.body
    if analysis.sources is None:
        raise ReportCompositionRefused("the run's own sources were not read")
    # What each chapter is composed from (artifact-chain CHN1).
    specification, dataset, aggregate = upstream_artifacts(analysis.sources)
    the_map = ArtifactSource(SOCIOMAP_ARTIFACT, mapped.artifact_id, mapped.sha256)
    questions = compose_question_tables(
        analysis,
        native_items(spec),
        source=f"Zmrazený výsledek běhu {run_id}; evidence {first.inputs.table.fingerprint()[:12]}",
        scales=scale_notes(spec),
    )
    design = compose_design_sections(
        spec,
        first.inputs.research_questions,
        goal=analysis.brief.goal,
        decision_use=analysis.brief.decision_use,
    )
    # The goal and decision use are read from the Design Revision the run names, not from the
    # specification (CHN1): named only when the chapter prints them.
    brief_source = (
        (RunSource("metadata.design_revision_id"),)
        if analysis.brief.goal or analysis.brief.decision_use
        else ()
    )
    meta = run.get("metadata") or {}
    return ReportChapters(
        maps=tuple(
            sourced(section, the_map)
            for section in compose_map_sections(
                body,
                object_map_snapshots(body),
                source=f"Zmrazený výsledek běhu {run_id}; SHA-256 {mapped.sha256}",
            )
        ),
        questions=replace(
            questions,
            sections=tuple(
                sourced(section, aggregate, specification, SpecSource("questions"))
                for section in questions.sections
            ),
        ),
        design=DesignSections(
            chapter=sourced(
                design.chapter,
                specification,
                SpecSource("questions"),
                SpecSource("batteries"),
                SpecSource("n"),
                SpecSource("audience"),
                *brief_source,
            ),
            appendix=sourced(
                design.appendix, specification, SpecSource("questions"), SpecSource("batteries")
            ),
        ),
        method=sourced(
            compose_method_section(meta, first.record.labels.data_origin),
            dataset,
            *METHOD_SOURCES,
        ),
        methodology=compose_methodology_rules(meta),
        map_artifact_id=mapped.artifact_id,
        map_sha256=mapped.sha256,
        gaps=research_question_gaps(meta),
    )
