"""The ``merge`` and ``verify`` steps: scores, dedupe, the leakage screen; then the verifier."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from aia_core.domain.deep_research.agents import (
    PROMPT_VERSION,
    AgentRole,
    Verdict,
    VerificationProposal,
)
from aia_core.domain.deep_research.classification import most_restrictive
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    QuarantinedEvidence,
    QuarantineReason,
    SnapshotLink,
    TrackStatus,
    digest,
)
from aia_core.domain.deep_research.merge import (
    MERGE_RULES_VERSION,
    Candidate,
    SourceFacts,
    TrackEvidence,
    apply_verdicts,
    excerpt_window,
    merge_evidence,
    verification_batches,
)
from aia_core.domain.deep_research.steps import (
    BatchEntry,
    InvestigationRecord,
    MergeRecord,
    PlanRecord,
    SnapshotArtifact,
    TrackResult,
    VerificationBatch,
    VerifyRecord,
    WorkStandingRecord,
    run_scoped,
)
from aia_core.domain.deep_research.tracing import TraceSource, trace_findings
from aia_core.domain.deep_research.triangulation import (
    IndependenceSource,
    independence_groups,
    publisher_identity,
)
from aia_core.domain.deep_research.verification import (
    RELATED_LIMIT,
    VERIFICATION_RULES_VERSION,
    VerificationReview,
    review_candidates,
    verifier_item,
)
from aia_core.domain.deep_research.verifier import (
    VERIFIER_CONTRACT_VERSION,
    VERIFIER_PROMPT_VERSION,
    ClaimJudgement,
    Verification,
)
from aia_core.domain.deep_research.works import WorkStatusRecord
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome

from ..research import upstream_artifact
from ._shared import (
    _agent_directed,
    _composition_changed,
    _invalid,
    _lineage,
    _missing_upstream,
    _produced,
    _Step,
    _unconfigured,
)
from .runtime import DeepResearchRuntime
from .standing import work_standings

__all__ = ["MergeExecutor", "VerifyExecutor"]

# --------------------------------------------------------------------------- #
# merge
# --------------------------------------------------------------------------- #


class MergeExecutor(_Step):
    """Declared source scores, dedupe, confirmation, the leakage screen. No model."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        runtime = self._runtime
        if runtime is None:
            return _unconfigured()
        loaded = self._plan(context, step)
        if isinstance(loaded, Failed):
            return loaded
        _plan_id, plan = loaded
        if runtime.source_table.version != plan.versions.get("source_table"):
            return _composition_changed("the source table")
        with context.transaction() as (session, workflow):
            repo = self._repo(session, context)
            investigation_id = upstream_artifact(workflow, step, "investigate")
            if investigation_id is None:
                return _missing_upstream("investigate")
            key = run_scoped(
                step.run_id, digest({"kind": "merge", "investigation": investigation_id})
            )
            existing = self._find(repo, step, "merge", key)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)
            investigation = self._read(repo, investigation_id, InvestigationRecord)
            results = [self._read(repo, e.artifact_id, TrackResult) for e in investigation.tracks]
        kept = [r for r in results if r.status is not TrackStatus.BLOCKED]
        # The cited works' standing, asked outside any transaction (chunk 46).
        standings = work_standings(
            context=context,
            step=step,
            runtime=runtime,
            plan=plan,
            dois=[s.doi for r in kept for s in r.sources if s.doi is not None],
            repo=lambda session: self._repo(session, context),
            put=lambda repo, record, k: self._store_standing(repo, step, record, k),
            find=lambda repo, k: self._found_standing(repo, step, k),
            clock=runtime.clock,
        )
        with context.transaction() as (session, workflow):
            repo = self._repo(session, context)
            merged = merge_evidence(
                [
                    TrackEvidence(
                        track_id=r.track.track_id,
                        evidence=r.evidence,
                        sources={
                            s.ref: _with_standing(s.facts(), s.doi, standings) for s in r.sources
                        },
                    )
                    for r in kept
                ],
                questionnaire=plan.request.questionnaire,
                table=runtime.source_table,
            )
            record = MergeRecord(
                kind="deep_research_merge",
                investigation_artifact_id=investigation_id,
                source_table_version=runtime.source_table.version,
                merge_rules_version=MERGE_RULES_VERSION,
                candidates=merged.candidates,
                quarantined=(*(q for r in results for q in r.quarantined), *merged.quarantined),
            )
            artifact, created = self._put(
                repo, step, payload=record, kind="merge", key=key, depends_on=[investigation_id]
            )
        context.progress(
            "deep_research_merged",
            candidates=len(record.candidates),
            quarantined=len(record.quarantined),
        )
        return _produced(artifact, reused=not created)

    def _store_standing(
        self, repo: ArtifactRepository, step: StepInput, record: WorkStandingRecord, key: str
    ) -> None:
        self._put(repo, step, payload=record, kind="work_standing", key=key)

    def _found_standing(
        self, repo: ArtifactRepository, step: StepInput, key: str
    ) -> WorkStandingRecord | None:
        found = self._find(repo, step, "work_standing", key)
        return None if found is None else self._read(repo, found.artifact_id, WorkStandingRecord)


def _with_standing(
    facts: SourceFacts, doi: str | None, standings: Mapping[str, WorkStatusRecord]
) -> SourceFacts:
    """A source's facts with its work's standing, when its DOI was asked about."""
    if doi is None or doi not in standings:
        return facts
    return dataclasses.replace(facts, work_status=standings[doi])


def _refused_detail(
    quarantined: Sequence[QuarantinedEvidence], entries: Sequence[BatchEntry]
) -> tuple[QuarantinedEvidence, ...]:
    """An unverified candidate of a refused batch says which gate refused it."""
    refused = {i: e.refused for e in entries if e.refused for i in e.evidence_ids}
    return tuple(
        q.model_copy(update={"detail": f"verification refused: {refused[q.evidence_id]}"})
        if q.reason is QuarantineReason.UNVERIFIED and q.evidence_id in refused
        else q
        for q in quarantined
    )


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #


class VerifyExecutor(_Step):
    """The verifier, batch by batch, each against its candidates' own excerpts.

    A batch whose request is unchanged -- the same findings, excerpts, policy and
    prompt -- is taken as stored. A batch the gateway refuses leaves its
    candidates unverified, which is quarantine, never acceptance.
    """

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        runtime = self._runtime
        if runtime is None:
            return _unconfigured()
        loaded = self._plan(context, step)
        if isinstance(loaded, Failed):
            return loaded
        _plan_id, plan = loaded
        if runtime.versions() != plan.versions:
            return _composition_changed("the composition's rules or policy")
        with context.transaction() as (session, workflow):
            repo = self._repo(session, context)
            merge_id = upstream_artifact(workflow, step, "merge")
            if merge_id is None:
                return _missing_upstream("merge")
            key = run_scoped(step.run_id, digest({"kind": "verify", "merge": merge_id}))
            existing = self._find(repo, step, "verify", key)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)
            merge = self._read(repo, merge_id, MergeRecord)
            investigation = self._read(repo, merge.investigation_artifact_id, InvestigationRecord)
            snapshot_artifacts = {
                s.snapshot_id: s.artifact_id
                for e in investigation.tracks
                for s in self._read(repo, e.artifact_id, TrackResult).snapshots
            }
            texts: dict[str, str] = {k.ref: k.text for k in plan.request.knowledge.items}
            for c in merge.candidates:
                ref = c.evidence.source_ref
                if ref not in texts and ref in snapshot_artifacts:
                    texts[ref] = self._read(
                        repo, snapshot_artifacts[ref], SnapshotArtifact
                    ).snapshot.text
        missing = sorted({c.evidence.source_ref for c in merge.candidates} - set(texts))
        if missing:
            # A candidate whose source the run cannot show is not verified on its quote alone.
            return _invalid(
                "source_missing",
                "candidates cite sources the run does not hold: " + ", ".join(missing),
            )
        if _agent_directed(plan):
            return self._directed(step, context, runtime, plan, merge_id, key, merge, texts)

        caller = self._caller(context, runtime)
        entries: list[BatchEntry] = []
        verdicts: dict[str, tuple[Verdict, str]] = {}
        for batch in verification_batches(merge.candidates, size=plan.depth.verify_batch):
            context.checkpoint()
            items = [
                {
                    "evidence_id": c.evidence.evidence_id,
                    "claim": c.evidence.claim,
                    "quote": c.evidence.quote,
                    "excerpt": excerpt_window(texts[c.evidence.source_ref], c.evidence.quote_span),
                }
                for c in batch
            ]
            ids = tuple(str(i["evidence_id"]) for i in items)
            fingerprint = digest(
                {
                    "kind": "verification",
                    "items": items,
                    "policy": runtime.config.policy_version,
                    "prompt": PROMPT_VERSION,
                    "harness": HARNESS_VERSION,
                }
            )
            with context.transaction() as (session, _workflow):
                repo = self._repo(session, context)
                found = self._find(repo, step, "verification", fingerprint)
                stored = self._read(repo, found.artifact_id, VerificationBatch) if found else None
            if found is not None and stored is not None:
                entries.append(
                    BatchEntry(
                        fingerprint=fingerprint,
                        evidence_ids=ids,
                        artifact_id=found.artifact_id,
                        reused=self._reused(found, step),
                        refused=None,
                    )
                )
            else:
                knowledge = [
                    k
                    for c in batch
                    if (k := plan.request.knowledge.source(c.evidence.source_ref)) is not None
                ]
                answer = self._ask(
                    caller,
                    runtime,
                    AgentRole.VERIFIER,
                    payload={"items": items},
                    data_class=most_restrictive([c.evidence.data_class for c in batch]),
                    lineage=_lineage(knowledge),
                )
                if answer.gate is not None:
                    entries.append(
                        BatchEntry(
                            fingerprint=fingerprint,
                            evidence_ids=ids,
                            artifact_id=None,
                            reused=False,
                            refused=answer.refused,
                        )
                    )
                    continue
                assert isinstance(answer.output, VerificationProposal) and answer.call is not None
                answered: dict[str, tuple[str, str]] = {}
                for v in answer.output.verdicts:
                    if v.evidence_id in ids and v.evidence_id not in answered:
                        answered[v.evidence_id] = (v.verdict.value, v.reason)
                stored = VerificationBatch(
                    kind="deep_research_verification",
                    evidence_ids=ids,
                    verdicts=answered,
                    call=answer.call,
                )
                with context.transaction() as (session, _workflow):
                    artifact, _created = self._put(
                        self._repo(session, context),
                        step,
                        payload=stored,
                        kind="verification",
                        key=fingerprint,
                    )
                entries.append(
                    BatchEntry(
                        fingerprint=fingerprint,
                        evidence_ids=ids,
                        artifact_id=artifact.artifact_id,
                        reused=False,
                        refused=None,
                    )
                )
            verdicts.update({k: (Verdict(v), r) for k, (v, r) in stored.verdicts.items()})

        accepted, refused_by_verifier = apply_verdicts(merge.candidates, verdicts)
        refused_batches = {i: e.refused for e in entries if e.refused for i in e.evidence_ids}
        quarantined = tuple(
            q.model_copy(
                update={"detail": f"verification refused: {refused_batches[q.evidence_id]}"}
            )
            if q.reason is QuarantineReason.UNVERIFIED and q.evidence_id in refused_batches
            else q
            for q in refused_by_verifier
        )
        record = VerifyRecord(
            kind="deep_research_verify",
            merge_artifact_id=merge_id,
            batches=tuple(entries),
            accepted=accepted,
            quarantined=(*merge.quarantined, *quarantined),
        )
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                self._repo(session, context),
                step,
                payload=record,
                kind="verify",
                key=key,
                depends_on=[merge_id, *(e.artifact_id for e in entries if e.artifact_id)],
            )
        context.progress(
            "deep_research_verified",
            batches=len(entries),
            reused=sum(1 for e in entries if e.reused),
            refused=sum(1 for e in entries if e.refused),
            accepted=len(accepted),
        )
        return _produced(artifact, reused=not created)

    # ----------------------------------------------------------------------- #
    # The agent-directed mode (plan deep-research-web-search.md § 8.3-8.5)
    # ----------------------------------------------------------------------- #

    def _directed(
        self,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        merge_id: str,
        key: str,
        merge: MergeRecord,
        texts: dict[str, str],
    ) -> StepOutcome:
        """Independence, tracing, the independent verifier, supersession and conflicts.

        The same batches as the planned mode, each shown to the independent verifier
        with its measures, its source's trace and the publisher's other figures;
        everything it decided beside acceptance is the record's ``review``.
        """
        register = runtime.register
        candidates = merge.candidates
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            investigation = self._read(repo, merge.investigation_artifact_id, InvestigationRecord)
            results = [self._read(repo, e.artifact_id, TrackResult) for e in investigation.tracks]
            snapshot_ids = {s.snapshot_id: s.artifact_id for r in results for s in r.snapshots}
            refs = sorted({c.evidence.source_ref for c in candidates} & set(snapshot_ids))
            links: dict[str, tuple[SnapshotLink, ...]] = {
                ref: self._read(repo, snapshot_ids[ref], SnapshotArtifact).snapshot.links
                for ref in refs
            }
        published_by_ref = {s.ref: s.published for r in results for s in r.sources}
        published = {
            c.evidence.evidence_id: published_by_ref.get(c.evidence.source_ref) for c in candidates
        }
        sources: dict[str, IndependenceSource] = {}
        for c in candidates:
            ref = c.evidence.source_ref
            sources.setdefault(
                ref,
                IndependenceSource(
                    ref=ref,
                    publisher=publisher_identity(
                        url=c.evidence.source_url, source_ref=ref, register=register
                    ),
                    text=texts[ref],
                ),
            )
        groups = independence_groups(list(sources.values()))
        trace_records, primary_leads = trace_findings(
            [c.evidence for c in candidates],
            {
                c.evidence.source_ref: TraceSource(
                    ref=c.evidence.source_ref,
                    url=c.evidence.source_url,
                    text=texts[c.evidence.source_ref],
                    links=links.get(c.evidence.source_ref, ()),
                )
                for c in candidates
            },
            register=register,
        )
        traces = {t.evidence_id: t for t in trace_records}

        caller = self._caller(context, runtime)
        entries: list[BatchEntry] = []
        judgements: dict[str, ClaimJudgement] = {}
        for batch in verification_batches(candidates, size=plan.depth.verify_batch):
            context.checkpoint()
            shown: list[Candidate] = list(batch)
            items = []
            for c in batch:
                related = [
                    o
                    for o in candidates
                    if o.evidence.evidence_id != c.evidence.evidence_id
                    and traces[o.evidence.evidence_id].publisher
                    == traces[c.evidence.evidence_id].publisher
                ][:RELATED_LIMIT]
                shown += related
                items.append(
                    verifier_item(
                        c,
                        excerpt=excerpt_window(texts[c.evidence.source_ref], c.evidence.quote_span),
                        trace=traces[c.evidence.evidence_id],
                        related=related,
                    )
                )
            ids = tuple(str(i["evidence_id"]) for i in items)
            fingerprint = digest(
                {
                    "kind": "independent_verification",
                    "items": items,
                    "policy": runtime.config.policy_version,
                    "prompt": VERIFIER_PROMPT_VERSION,
                    "contract": VERIFIER_CONTRACT_VERSION,
                    "harness": HARNESS_VERSION,
                }
            )
            with context.transaction() as (session, _workflow):
                repo = self._repo(session, context)
                found = self._find(repo, step, "verification", fingerprint)
                stored = self._read(repo, found.artifact_id, VerificationBatch) if found else None
            if found is not None and stored is not None:
                entries.append(
                    BatchEntry(
                        fingerprint=fingerprint,
                        evidence_ids=ids,
                        artifact_id=found.artifact_id,
                        reused=self._reused(found, step),
                        refused=None,
                    )
                )
            else:
                knowledge = [
                    k
                    for ref in dict.fromkeys(o.evidence.source_ref for o in shown)
                    if (k := plan.request.knowledge.source(ref)) is not None
                ]
                answer = self._ask(
                    caller,
                    runtime,
                    AgentRole.INDEPENDENT_VERIFIER,
                    payload={"items": items},
                    data_class=most_restrictive([o.evidence.data_class for o in shown]),
                    lineage=_lineage(knowledge),
                )
                if answer.gate is not None:
                    entries.append(
                        BatchEntry(
                            fingerprint=fingerprint,
                            evidence_ids=ids,
                            artifact_id=None,
                            reused=False,
                            refused=answer.refused,
                        )
                    )
                    continue
                assert isinstance(answer.output, Verification) and answer.call is not None
                answered: dict[str, ClaimJudgement] = {}
                for j in answer.output.judgements:
                    if j.evidence_id in ids and j.evidence_id not in answered:
                        answered[j.evidence_id] = j
                stored = VerificationBatch(
                    kind="deep_research_verification",
                    evidence_ids=ids,
                    verdicts={k: (j.verdict.value, j.reason) for k, j in answered.items()},
                    call=answer.call,
                    judgements=tuple(answered.values()),
                )
                with context.transaction() as (session, _workflow):
                    artifact, _created = self._put(
                        self._repo(session, context),
                        step,
                        payload=stored,
                        kind="verification",
                        key=fingerprint,
                    )
                entries.append(
                    BatchEntry(
                        fingerprint=fingerprint,
                        evidence_ids=ids,
                        artifact_id=artifact.artifact_id,
                        reused=False,
                        refused=None,
                    )
                )
            judgements.update({j.evidence_id: j for j in stored.judgements})

        outcome = review_candidates(
            candidates,
            judgements,
            groups=groups,
            traces=traces,
            published=published,
            register=register,
        )
        distinct = {g.group_id: g for g in groups.values()}
        review = VerificationReview(
            kind="deep_research_verification_review",
            rules_version=VERIFICATION_RULES_VERSION,
            register_version=register.version if register is not None else None,
            independence=tuple(distinct[k] for k in sorted(distinct)),
            traces=trace_records,
            primary_leads=primary_leads,
            verifier_leads=outcome.verifier_leads,
            supersessions=outcome.supersessions,
            conflicts=outcome.conflicts,
            resolve_requests=outcome.resolve_requests,
        )
        record = VerifyRecord(
            kind="deep_research_verify",
            merge_artifact_id=merge_id,
            batches=tuple(entries),
            accepted=outcome.accepted,
            quarantined=(*merge.quarantined, *_refused_detail(outcome.quarantined, entries)),
            review=review,
        )
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                self._repo(session, context),
                step,
                payload=record,
                kind="verify",
                key=key,
                depends_on=[merge_id, *(e.artifact_id for e in entries if e.artifact_id)],
            )
        context.progress(
            "deep_research_verified",
            batches=len(entries),
            reused=sum(1 for e in entries if e.reused),
            refused=sum(1 for e in entries if e.refused),
            accepted=len(outcome.accepted),
            superseded=len(outcome.supersessions),
            conflicts=len(outcome.conflicts),
            resolve_requests=len(outcome.resolve_requests),
            primary_leads=len(primary_leads),
        )
        return _produced(artifact, reused=not created)
