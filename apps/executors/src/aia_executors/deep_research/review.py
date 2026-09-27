"""The ``merge`` and ``verify`` steps: scores, dedupe, the leakage screen; then the verifier."""

from __future__ import annotations

from aia_core.domain.deep_research.agents import (
    PROMPT_VERSION,
    AgentRole,
    Verdict,
    VerificationProposal,
)
from aia_core.domain.deep_research.classification import most_restrictive
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    QuarantineReason,
    TrackStatus,
    digest,
)
from aia_core.domain.deep_research.merge import (
    MERGE_RULES_VERSION,
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
    SnapshotArtifact,
    TrackResult,
    VerificationBatch,
    VerifyRecord,
    run_scoped,
)
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome

from ..research import upstream_artifact
from ._shared import (
    _composition_changed,
    _invalid,
    _lineage,
    _missing_upstream,
    _produced,
    _Step,
    _unconfigured,
)

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
            merged = merge_evidence(
                [
                    TrackEvidence(
                        track_id=r.track.track_id,
                        evidence=r.evidence,
                        sources={s.ref: s.facts() for s in r.sources},
                    )
                    for r in results
                    if r.status is not TrackStatus.BLOCKED
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
