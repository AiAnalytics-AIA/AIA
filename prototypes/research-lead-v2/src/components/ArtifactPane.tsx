// The artifact workspace: one header (title, state, version, actions), at most
// one state bar (proposal / stale / working copy / frozen), the artifact, and
// the inspector over it. Inputs, feeds, workers and provenance live in the
// inspector, not in strips above the work.
import { useEffect, useRef, useState, type ReactElement } from 'react';
import { useApp } from '../app/store';
import * as C from '../app/commands';
import { STAGES, T } from '../model/terms';
import { contentRev } from '../model/doc';
import { pendingProposals } from '../model/status';
import { Icon } from './Icons';
import { Glyph } from './Glyph';
import { Inspector } from './Inspector';
import { BriefArt, DesignArt, QuestionnaireArt } from '../artifacts/DesignStages';
import { AudienceArt, DimensionsArt, SampleArt } from '../artifacts/SampleStages';
import { FieldworkArt, ResultsArt, SociomapArt } from '../artifacts/EvidenceStages';
import { AnalysisArt, ReportArt } from '../artifacts/InterpretStages';
import { runScript, rebuild, staleRefusal } from '../app/scenarios';
import type { StageId, ArtifactState } from '../model/types';

const ART: Record<StageId, () => ReactElement> = {
  brief: BriefArt, design: DesignArt, questionnaire: QuestionnaireArt, audience: AudienceArt, dimensions: DimensionsArt, sample: SampleArt,
  fieldwork: FieldworkArt, results: ResultsArt, sociomap: SociomapArt, analysis: AnalysisArt, report: ReportArt,
};
const RUN_STAGES: StageId[] = ['fieldwork', 'results', 'sociomap', 'analysis'];
const scrollMemory: Partial<Record<StageId, number>> = {};

export function ArtifactPane() {
  const s = useApp((x) => x);
  const stage = s.stage;
  const props = pendingProposals(s, stage);
  const prop = props[0];
  const stale = prop ? C.isStale(s, prop) : false;
  const working = s.working[stage] ?? [];
  const isRun = RUN_STAGES.includes(stage);
  const runDone = s.run.status === 'completed';
  const body = useRef<HTMLDivElement>(null);
  const [showImpact, setShowImpact] = useState(false);

  // Restore each artifact's scroll position when coming back to it.
  useEffect(() => {
    const el = body.current;
    if (!el) return;
    el.scrollTop = scrollMemory[stage] ?? 0;
    const on = () => { scrollMemory[stage] = el.scrollTop; };
    el.addEventListener('scroll', on, { passive: true });
    return () => el.removeEventListener('scroll', on);
  }, [stage]);
  useEffect(() => { setShowImpact(false); }, [stage, prop?.id]);

  const state: ArtifactState = working.length ? 'working' : prop ? 'proposed' : isRun ? (runDone ? 'frozen' : s.run.status === 'none' || s.run.status === 'ready' ? 'empty' : 'working') : 'accepted';
  const reportDraft = stage === 'report' && runDone && !s.reportState.reviewed && state === 'accepted';
  const analysisDraft = stage === 'analysis' && runDone && state === 'frozen';
  const stateWord = reportDraft ? 'Koncept · neschváleno' : analysisDraft ? 'Uloženo · nerevidováno' : state === 'working' ? (isRun ? 'Běží' : T.artifact.working) : state === 'proposed' ? T.artifact.proposed : state === 'frozen' ? T.artifact.frozen : state === 'empty' ? (stage === 'fieldwork' && s.run.status === 'ready' ? 'Připraveno' : T.artifact.empty) : T.artifact.accepted;
  const version = stage === 'report'
    ? 'Koncept ' + s.reportState.draft + ' · z běhu ' + s.run.id + ' (revize ' + s.run.revision + ')'
    : isRun
      ? (s.run.status === 'none' || s.run.status === 'ready' ? 'Běh zmrazí revizi ' + s.revision : 'Běh ' + s.run.id + ' · revize ' + s.run.revision + (s.revision !== s.run.revision ? ' · studie je na revizi ' + s.revision : ''))
      : 'Obsah z revize ' + contentRev(s, stage) + (contentRev(s, stage) !== s.revision ? ' · studie je na revizi ' + s.revision : '') + (runDone && ['questionnaire', 'audience', 'dimensions', 'design'].includes(stage) ? ' · běh použil revizi ' + s.run.revision : '');
  const Art = ART[stage];

  return (
    <div className="art" aria-label={'Artefakt ' + STAGES[stage].label}>
      <div className="arthead">
        <div style={{ minWidth: 0 }}>
          <div className="row"><h2 className="arthead__title">{STAGES[stage].label}</h2><span className={'statepill statepill--' + (state === 'empty' || reportDraft || analysisDraft ? 'working' : state)}>{stateWord}</span></div>
          <div className="arthead__sub" title={version}>{version}</div>
        </div>
        <div className="arthead__actions">
          <button className="btn btn--sm btn--quiet" onClick={() => C.visual.inspect({ type: 'history', stage })}><Icon name="history" size={14} />{T.artifact.history}</button>
          <button className="btn btn--sm btn--quiet" onClick={() => C.visual.inspect({ type: 'details', stage })}><Icon name="inspector" size={14} />Podrobnosti</button>
          <button className="btn btn--sm btn--quiet" onClick={() => C.visual.inspect({ type: 'contract', stage })} title="Co z artefaktu čte a co smí Vedoucí"><Icon name="layers" size={14} />Kontrakt AI</button>
          <button className={'iconbtn' + (s.mode === 'artifact' ? ' is-on' : '')} aria-pressed={s.mode === 'artifact'} title={s.mode === 'artifact' ? T.layout.backToNormal : T.layout.artifactFocus} aria-label={s.mode === 'artifact' ? T.layout.backToNormal : T.layout.artifactFocus} onClick={() => C.visual.mode(s.mode === 'artifact' ? 'normal' : 'artifact')}><Icon name={s.mode === 'artifact' ? 'normal' : 'focusArtifact'} size={16} /></button>
        </div>
      </div>

      {prop && stale && (
        <div className="artbar artbar--stale" role="status" data-aia={'proposal.' + prop.id + '.stale'}>
          <Glyph tone="reopened" size={12} />
          <div className="artbar__grow"><b>{prop.title}</b> · {T.proposal.stale(prop.baseRev, C.currentBase(s, stage))}<div className="cap">{T.proposal.rebuildNote}</div></div>
          <button className="btn btn--sm" disabled={s.busy} onClick={() => void runScript((t) => rebuild(t, prop.id))}>{T.proposal.rebuild(C.currentBase(s, stage))}</button>
          <button className="btn btn--sm btn--quiet" onClick={() => C.rejectProposal(prop.id)}>Zahodit</button>
        </div>
      )}
      {prop && !stale && (
        <div className="artbar artbar--you" role="status" data-aia={'proposal.' + prop.id}>
          <Glyph tone="you" size={12} />
          <div className="artbar__grow"><b>{T.proposal.review}:</b> {prop.title} · {prop.changes.filter((c) => c.why && c.kind !== 'keep').length} změn · {prop.baseLabel.toLowerCase().startsWith('běh') ? prop.baseLabel : stage === 'report' ? 'vychází z konceptu ' + prop.baseRev : 'vychází z revize ' + prop.baseRev}<div className="cap">{prop.author} · {T.proposal.nothingChanges}</div></div>
          <button className="btn btn--sm btn--quiet" aria-expanded={showImpact} onClick={() => setShowImpact((v) => !v)}>{showImpact ? 'Skrýt dopad' : 'Dopad a pokrytí'}</button>
          <button className="btn btn--sm btn--quiet" onClick={() => C.rejectProposal(prop.id)}>{T.proposal.keep}</button>
          <button className="btn btn--sm btn--primary" onClick={() => { const r = C.acceptProposal(prop.id, 'ui'); if (!r.ok) void runScript(staleRefusal); }}>{stage === 'report' ? 'Použít jako koncept ' + (s.reportState.draft + 1) : C.DESIGN_STAGES.includes(stage) ? T.proposal.applyAs(s.revision + 1) : T.proposal.apply}</button>
        </div>
      )}
      {prop && showImpact && (
        <div className="impact" data-aia={'proposal.' + prop.id + '.impact'}>
          {prop.coverage && <div><h4>{T.proposal.coverage}</h4><ul className="plain">{prop.coverage.gained.map((x) => <li key={x}><span className="cov cov--gain">získá</span> {x}</li>)}{prop.coverage.lost.map((x) => <li key={x}><span className="cov cov--lose">ztratí</span> {x}</li>)}{prop.coverage.kept.map((x) => <li key={x}><span className="cov">zachová</span> {x}</li>)}</ul></div>}
          <div><h4>{T.proposal.implications}</h4><ul className="plain">{prop.implications.map((x) => <li key={x}>{x}</li>)}</ul></div>
          <div><h4>{T.proposal.downstream}</h4><ul className="plain">{prop.impact.length ? prop.impact.map((x) => <li key={x.stage + x.effect}><button className="linkbtn" onClick={() => C.visual.open(x.stage)}>{STAGES[x.stage].label}</button>: {x.effect}</li>) : <li>nic</li>}</ul>
            <h4>{T.proposal.recompute}</h4><p className="cap" style={{ margin: 0 }}>{prop.recompute}{prop.cost ? ' · ' + prop.cost : ''}</p></div>
        </div>
      )}
      {!prop && working.length > 0 && (
        <div className="artbar artbar--work" role="status" data-aia={'working.' + stage}>
          <Glyph tone="working" size={12} />
          <div className="artbar__grow">{T.artifact.savedWorking(working.length, s.workingSince[stage] ?? contentRev(s, stage))} · uloženo automaticky{(s.leadSeen[stage] ?? 0) >= working.length && <span className="muted"> · {T.artifact.leadNoticed}</span>}</div>
          <button className="btn btn--sm btn--quiet" onClick={() => C.discardWorking(stage)}>{T.artifact.discard}</button>
          <button className="btn btn--sm btn--primary" onClick={() => C.acceptWorking(stage)}>{stage === 'report' ? 'Přijmout jako koncept ' + (s.reportState.draft + 1) : T.artifact.acceptAs(s.revision + 1)}</button>
        </div>
      )}
      {prop && working.length > 0 && <div className="artbar artbar--work"><Glyph tone="working" size={12} /><div className="artbar__grow">Také {T.artifact.savedWorking(working.length, s.workingSince[stage] ?? contentRev(s, stage))}</div><button className="btn btn--sm btn--quiet" onClick={() => C.discardWorking(stage)}>{T.artifact.discard}</button><button className="btn btn--sm" onClick={() => C.acceptWorking(stage)}>{T.artifact.acceptAs(s.revision + 1)}</button></div>}
      {isRun && runDone && stage !== 'fieldwork' && !s.reopened.includes(stage) && (
        <div className="artbar artbar--frozen"><Icon name="lock" size={13} /><div className="artbar__grow">Zmrazeno z běhu {s.run.id} · revize {s.run.revision}. Úpravy návrhu do těchto výsledků nevstoupí; potřebují nový běh.</div><span className="synth">{T.synthetic.short}</span></div>
      )}

      <div className="artstage">
        <div className="artbody" ref={body} id="artbody">
          <Art />
        </div>
        <Inspector />
      </div>
    </div>
  );
}
