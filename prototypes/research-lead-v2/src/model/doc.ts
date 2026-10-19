// Applying edits to the element model, and reading a stage's content at each
// level: accepted revision, working copy (accepted + your unsaved edits), and a
// proposal's preview. Pure functions; the store holds the op lists.
import type { AppState, Op, StageId, AppliedOp } from './types';
import { AUDIENCE, BRIEF, DESIGN, DIMENSIONS, QUESTIONNAIRE, REPORT, BASE_REV, type Doc, type Item } from './fixture';

export const EDITABLE: StageId[] = ['brief', 'design', 'questionnaire', 'audience', 'dimensions', 'report'];
const BASE: Partial<Record<StageId, Doc>> = { brief: BRIEF, design: DESIGN, questionnaire: QUESTIONNAIRE, audience: AUDIENCE, dimensions: DIMENSIONS, report: REPORT };

export function applyOp(doc: Doc, op: Op): Doc {
  const d: Doc = structuredClone(doc);
  const sec = d.sections.find((s) => s.id === op.sec);
  if (!sec) return d;
  if (op.op === 'set') {
    if (!op.item) { (sec as unknown as Record<string, unknown>)[op.field] = op.value; return d; }
    const it = sec.items.find((i) => i.id === op.item);
    if (it) it[op.field] = op.value;
  } else if (op.op === 'add') {
    const at = op.after == null ? sec.items.length : sec.items.findIndex((i) => i.id === op.after) + 1;
    sec.items.splice(at < 0 ? sec.items.length : at, 0, op.item as Item);
  } else if (op.op === 'remove') {
    sec.items = sec.items.filter((i) => i.id !== op.item);
  } else if (op.op === 'move') {
    const i = sec.items.findIndex((x) => x.id === op.item);
    const j = i + op.dir;
    if (i >= 0 && j >= 0 && j < sec.items.length) { const [x] = sec.items.splice(i, 1); sec.items.splice(j, 0, x); }
  }
  return d;
}

export const applyOps = (doc: Doc, ops: Op[]) => ops.reduce(applyOp, doc);

export function acceptedDoc(s: AppState, stage: StageId): Doc {
  return applyOps(BASE[stage] ?? { sections: [] }, (s.accepted[stage] ?? []).map((a) => a.op));
}
export function workingDoc(s: AppState, stage: StageId): Doc {
  return applyOps(acceptedDoc(s, stage), (s.working[stage] ?? []).map((a) => a.op));
}

// The revision in which this stage's accepted content last changed.
export function contentRev(s: AppState, stage: StageId): number {
  const ops = s.accepted[stage] ?? [];
  const revs = ops.map((o) => Number(o.note?.match(/^r(\d+)/)?.[1] ?? 0));
  return Math.max(BASE_REV[stage], ...revs);
}

export function itemsChangedByWorking(s: AppState, stage: StageId): Set<string> {
  const ids = new Set<string>();
  (s.working[stage] ?? []).forEach((a: AppliedOp) => {
    const o = a.op;
    ids.add(o.op === 'add' ? o.item.id : o.op === 'set' ? (o.item ?? o.sec) : o.item);
  });
  return ids;
}

export function findItem(doc: Doc, id: string): { sec: string; item: Item } | null {
  for (const s of doc.sections) { const it = s.items.find((i) => i.id === id); if (it) return { sec: s.id, item: it }; }
  return null;
}

export function questionnaireMinutes(doc: Doc): number {
  const sec = doc.sections.flatMap((s) => s.items).reduce((t, i) => t + Number(i.d ?? 0), 0);
  return Math.round((sec / 60) * 2) / 2;
}
