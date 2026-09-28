"""The ``synthesize`` and ``publish`` steps: the checked brief, and the sealed bundle."""

from __future__ import annotations

from aia_core.domain.deep_research.agents import PROMPT_VERSION, AgentRole, SynthesisProposal
from aia_core.domain.deep_research.bundle import (
    SnapshotRef,
    SynthesisRecord,
    TrackRecord,
    seal_bundle,
)
from aia_core.domain.deep_research.classification import most_restrictive
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    StopReason,
    TrackStatus,
    digest,
)
from aia_core.domain.deep_research.steps import (
    Gate,
    InvestigationRecord,
    SynthesisArtifact,
    TrackResult,
    VerificationBatch,
    VerifyRecord,
    run_scoped,
    tally,
)
from aia_core.domain.deep_research.synthesis import (
    SynthesisCheck,
    SynthesisStatus,
    validate_synthesis,
)
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from ..research import upstream_artifact
from ._shared import (
    _composition_changed,
    _detail,
    _lineage,
    _missing_upstream,
    _produced,
    _Step,
    _unconfigured,
)

__all__ = ["PublishExecutor", "SynthesizeExecutor"]

# --------------------------------------------------------------------------- #
# synthesize
# --------------------------------------------------------------------------- #


class SynthesizeExecutor(_Step):
    """A brief from accepted evidence only; code keeps what cites it and drops the rest."""

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
            verify_id = upstream_artifact(workflow, step, "verify")
            if verify_id is None:
                return _missing_upstream("verify")
            mine = run_scoped(step.run_id, digest({"kind": "synthesis", "verify": verify_id}))
            existing = self._find(repo, step, "synthesis", mine)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)
            verify = self._read(repo, verify_id, VerifyRecord)

        accepted = {a.evidence.evidence_id: a for a in verify.accepted}
        subjects = {s.key: s for s in plan.subjects}
        if not accepted:
            empty = SynthesisArtifact(
                kind="deep_research_synthesis",
                check=SynthesisCheck(
                    status=SynthesisStatus.EMPTY,
                    summary=None,
                    summary_withheld=None,
                    findings=(),
                    excluded=(),
                    gaps=tuple(s.text for s in plan.subjects),
                    limitations=(),
                ),
                call=None,
                refused=None,
            )
            return self._record(context, step, empty, mine, verify_id)

        payload = {
            "subjects": [
                {"subject_key": s.key, "kind": s.kind.value, "text": s.text} for s in plan.subjects
            ],
            "evidence": [
                {
                    "evidence_id": a.evidence.evidence_id,
                    "subject_key": a.evidence.subject_key,
                    "claim": a.evidence.claim,
                    "quote": a.evidence.quote,
                    "source_title": a.evidence.source_title,
                    "source_url": a.evidence.source_url,
                    "confidence": a.confidence,
                }
                for a in verify.accepted
            ],
        }
        fingerprint = digest(
            {
                "kind": "synthesis",
                "payload": payload,
                "policy": runtime.config.policy_version,
                "prompt": PROMPT_VERSION,
                "harness": HARNESS_VERSION,
            }
        )
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            found = self._find(repo, step, "synthesis", fingerprint)
            if found is not None:
                repo.read(found.artifact_id)
                return _produced(found, reused=self._reused(found, step))
        knowledge = [
            k
            for a in verify.accepted
            if (k := plan.request.knowledge.source(a.evidence.source_ref)) is not None
        ]
        answer = self._ask(
            self._caller(context, runtime),
            runtime,
            AgentRole.SYNTHESIZER,
            payload=payload,
            data_class=most_restrictive([a.evidence.data_class for a in verify.accepted]),
            lineage=_lineage(knowledge),
        )
        if answer.gate is not None:
            refused = SynthesisArtifact(
                kind="deep_research_synthesis",
                check=SynthesisCheck(
                    status=SynthesisStatus.BLOCKED,
                    summary=None,
                    summary_withheld=f"the synthesis was not requested: {answer.refused}",
                    findings=(),
                    excluded=(),
                    gaps=(),
                    limitations=(),
                ),
                call=None,
                refused=answer.refused,
            )
            return self._record(context, step, refused, mine, verify_id)
        assert isinstance(answer.output, SynthesisProposal)
        written = SynthesisArtifact(
            kind="deep_research_synthesis",
            check=validate_synthesis(answer.output, accepted=accepted, subjects=subjects),
            call=answer.call,
            refused=None,
        )
        return self._record(context, step, written, fingerprint, verify_id)

    def _record(
        self,
        context: StepContext,
        step: StepInput,
        record: SynthesisArtifact,
        key: str,
        verify_id: str,
    ) -> Succeeded:
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                self._repo(session, context),
                step,
                payload=record,
                kind="synthesis",
                key=key,
                depends_on=[verify_id],
            )
        context.progress(
            "deep_research_synthesized",
            status=record.check.status.value,
            findings=len(record.check.findings),
            excluded=len(record.check.excluded),
            model_requests=0 if record.call is None else 1,
        )
        return _produced(artifact, reused=not created)


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #


class PublishExecutor(_Step):
    """The sealed evidence bundle: every track, finding, refusal and cost of the run."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        if self._runtime is None:
            return _unconfigured()
        loaded = self._plan(context, step)
        if isinstance(loaded, Failed):
            return loaded
        plan_id, plan = loaded
        with context.transaction() as (session, workflow):
            repo = self._repo(session, context)
            ids = {
                n: upstream_artifact(workflow, step, n)
                for n in ("investigate", "verify", "synthesize")
            }
            for node, artifact_id in ids.items():
                if artifact_id is None:
                    return _missing_upstream(node)
            investigation_id, verify_id, synthesis_id = (
                str(ids["investigate"]),
                str(ids["verify"]),
                str(ids["synthesize"]),
            )
            key = run_scoped(
                step.run_id,
                digest(
                    {
                        "kind": "bundle",
                        "plan": plan_id,
                        "investigation": investigation_id,
                        "verify": verify_id,
                        "synthesis": synthesis_id,
                    }
                ),
            )
            existing = self._find(repo, step, "bundle", key)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)
            investigation = self._read(repo, investigation_id, InvestigationRecord)
            verify = self._read(repo, verify_id, VerifyRecord)
            synthesis_artifact = repo.get(synthesis_id)
            synthesis = self._read(repo, synthesis_id, SynthesisArtifact)
            results = [
                (self._read(repo, e.artifact_id, TrackResult), e.reused, e.artifact_id)
                for e in investigation.tracks
            ]
            batch_calls = {
                e.fingerprint: self._read(repo, e.artifact_id, VerificationBatch).call
                for e in verify.batches
                if e.artifact_id is not None and not e.reused
            }

            quarantined_by_track: dict[str, list[str]] = {}
            for q in verify.quarantined:
                quarantined_by_track.setdefault(q.track_id, []).append(q.evidence_id)
            tracks = [
                TrackRecord(
                    track_id=r.track.track_id,
                    subject_key=r.track.subject.key,
                    channel=r.track.channel,
                    fingerprint=r.track.fingerprint,
                    status=r.status,
                    stop_reason=r.stop_reason,
                    detail=r.detail,
                    reused=reused,
                    artifact_id=artifact_id,
                    retrieval_mode=r.retrieval_mode if r.track.channel is Channel.WEB else None,
                    queries=r.queries,
                    snapshot_ids=tuple(s.snapshot_id for s in r.snapshots),
                    evidence_ids=tuple(e.evidence_id for e in r.evidence),
                    quarantined_ids=tuple(quarantined_by_track.get(r.track.track_id, ())),
                    model_requests=len(r.calls),
                    search_calls=r.search_calls,
                    fetches=r.fetches,
                    credits=r.credits,
                    model_cost_usd=r.model_cost_usd,
                    tool_cost_usd=r.tool_cost_usd,
                )
                for r, reused, artifact_id in results
            ]
            tracks += [
                TrackRecord(
                    track_id=t.track_id,
                    subject_key=t.subject.key,
                    channel=t.channel,
                    fingerprint=t.fingerprint,
                    status=TrackStatus.BLOCKED,
                    stop_reason=StopReason.TRACK_LIMIT,
                    detail=_detail(
                        Gate.TRACK_LIMIT,
                        "track_limit",
                        f"the {plan.depth.name} preset researches at most "
                        f"{plan.depth.max_tracks} tracks",
                    ),
                    reused=False,
                    artifact_id=None,
                    retrieval_mode=None,
                    queries=(),
                    snapshot_ids=(),
                    evidence_ids=(),
                    quarantined_ids=(),
                    model_requests=0,
                    search_calls=0,
                    fetches=0,
                    credits=0,
                    model_cost_usd=0.0,
                    tool_cost_usd=0.0,
                )
                for t in plan.beyond
            ]
            snapshots: dict[str, SnapshotRef] = {}
            for r, _reused, _id in results:
                for s in r.snapshots:
                    snapshots.setdefault(s.snapshot_id, s)
            counts, spend = tally(
                plan=plan,
                results=[(r, reused) for r, reused, _ in results],
                batches=verify.batches,
                batch_calls=batch_calls,
                synthesis=synthesis,
                synthesis_reused=self._reused(synthesis_artifact, step),
                accepted=len(verify.accepted),
                quarantined=len(verify.quarantined),
            )
            bundle = seal_bundle(
                request=plan.request,
                subjects=plan.subjects,
                versions=plan.versions,
                tracks=tracks,
                accepted=verify.accepted,
                quarantined=verify.quarantined,
                snapshots=tuple(snapshots.values()),
                synthesis=SynthesisRecord(artifact_id=synthesis_id, check=synthesis.check),
                fictional_client=plan.fictional_client,
                counts=counts,
                spend_usd=spend,
            )
            artifact, created = self._put(
                repo,
                step,
                payload={"bundle": bundle.model_dump(mode="json")},
                kind="bundle",
                key=key,
                depends_on=[
                    plan_id,
                    investigation_id,
                    verify.merge_artifact_id,
                    verify_id,
                    synthesis_id,
                ],
            )
        context.progress(
            "deep_research_published",
            quality_status=bundle.quality_status.value,
            accepted=len(bundle.accepted),
            quarantined=len(bundle.quarantined),
            **{
                k: v
                for k, v in counts.items()
                if k in ("model_requests", "search_calls", "fetches")
            },
        )
        return _produced(artifact, reused=not created, bundle_sha256=bundle.sha256)
