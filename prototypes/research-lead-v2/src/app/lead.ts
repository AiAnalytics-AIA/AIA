// The conversation's writers. The Lead's text streams in place; an activity is
// ONE card updated as work progresses (§11), never a stream of new messages.
import { update, sleep, nextId, isFast, getState } from './store';
import type { Activity, ActivityType, Block, LinkRef, Message, Tone, StageId } from '../model/types';
import { clockLabel } from './commands';

function base(kind: Message['kind']): Message {
  const s = getState();
  return { id: nextId('m'), kind, at: clockLabel(s), day: s.day, rev: s.revision };
}

export function tick(sec = 20) { update((d) => { d.clock += sec; }); }

export function userSays(text: string, ref?: Message['ref']) {
  const m = { ...base('user'), text, ref: ref ?? undefined };
  update((d) => { d.messages.push(m); });
  return m.id;
}

const textOf = (b: Block[]) => b.map((x) => (x.x ?? '') + (x.items ?? []).join(' ') + (x.rows ?? []).map((r) => r.join(' ')).join(' ')).join(' ');

export async function say(blocks: Block[], opts: { links?: LinkRef[]; sources?: string[]; runRev?: number } = {}) {
  const m: Message = { ...base('lead'), blocks, links: opts.links, sources: opts.sources, runRev: opts.runRev, streaming: !isFast(), shown: isFast() ? undefined : 0 };
  update((d) => { d.messages.push(m); });
  if (isFast()) return m.id;
  const total = textOf(blocks).length;
  const steps = Math.min(14, Math.max(4, Math.round(total / 40)));
  for (let i = 1; i <= steps; i++) {
    await sleep(55);
    update((d) => { const x = d.messages.find((y) => y.id === m.id); if (x) x.shown = Math.round((total * i) / steps); });
  }
  update((d) => { const x = d.messages.find((y) => y.id === m.id); if (x) { x.streaming = false; x.shown = undefined; } });
  return m.id;
}

export const p = (x: string): Block => ({ t: 'p', x });
export const ul = (...items: string[]): Block => ({ t: 'ul', items });
export const kv = (...rows: [string, string][]): Block => ({ t: 'kv', rows });
export const h = (x: string): Block => ({ t: 'h', x });

export function notice(text: string, tone: Tone = 'inert') {
  update((d) => { d.messages.push({ ...base('notice'), text, tone }); });
}
export function divider(text: string) {
  update((d) => { d.messages.push({ ...base('divider'), text }); });
}

export function startActivity(type: ActivityType, title: string, summary: string, details: [string, string][] = [], link?: { stage: StageId; focus?: string; label: string }): string {
  const id = nextId('act');
  update((d) => {
    d.activities.push({ id, type, title, summary, status: 'running', startedAt: d.clock, steps: [], details, link } as Activity);
    d.messages.push({ ...base('activity'), activityId: id });
  });
  return id;
}
export function actStep(id: string, text: string, tone: Tone = 'done') {
  update((d) => { const a = d.activities.find((x) => x.id === id); if (a) a.steps.push({ text, tone }); });
}
export function actUpdate(id: string, patch: Partial<Activity>) {
  update((d) => { const a = d.activities.find((x) => x.id === id); if (a) Object.assign(a, patch); });
}
export function actDone(id: string, summary: string, patch: Partial<Activity> = {}) {
  update((d) => { const a = d.activities.find((x) => x.id === id); if (a) Object.assign(a, { status: 'done', endedAt: d.clock, summary }, patch); });
}
export function decisionMsg(decisionId: string) {
  update((d) => { d.messages.push({ ...base('decision'), decisionId }); });
}

export async function pause(ms = 400) { await sleep(ms); }
