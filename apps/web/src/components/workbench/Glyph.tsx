"use client";

// Ported from the research-lead prototype (prototypes/research-lead-v2 @ 9b50963f).
// Status glyphs after the AIA design system's grammar: shape carries the state,
// colour only reinforces it. Machine states are circles, parked-on-a-person
// states are squares with pause bars (solid = you, hollow = the world), recovery
// is a diamond, inert states are dashed.
export type GlyphTone =
  | 'done' | 'done-warn' | 'running' | 'you' | 'world' | 'fault' | 'recovery'
  | 'reopened' | 'working' | 'ready' | 'blocked' | 'cancelled' | 'inert';

const SIZE = 12;

export function Glyph({ tone, size = SIZE, title }: { tone: GlyphTone; size?: number; title?: string }) {
  const s = size;
  const c = s / 2;
  const r = s / 2 - 1.25;
  const label = title ?? undefined;
  const common = { width: s, height: s, viewBox: `0 0 ${s} ${s}`, role: label ? 'img' : undefined, 'aria-label': label, 'aria-hidden': label ? undefined : true, className: 'glyph' } as const;
  switch (tone) {
    case 'done':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="var(--status-done)" /><path d={`M${s * 0.28} ${c} l${s * 0.15} ${s * 0.15} l${s * 0.28} -${s * 0.3}`} stroke="var(--surface-raised)" strokeWidth={1.5} fill="none" /></svg>
      );
    case 'done-warn':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--status-done)" strokeWidth={1.5} /><path d={`M${s * 0.28} ${c} l${s * 0.15} ${s * 0.15} l${s * 0.28} -${s * 0.3}`} stroke="var(--status-done)" strokeWidth={1.5} fill="none" /></svg>
      );
    case 'running':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--status-running)" strokeWidth={1.5} /><circle cx={c} cy={c} r={r / 2.2} fill="var(--status-running)" /></svg>
      );
    case 'you':
      return (
        <svg {...common}><rect x={1} y={1} width={s - 2} height={s - 2} rx={1} fill="var(--status-you)" /><rect x={s * 0.33} y={s * 0.28} width={1.4} height={s * 0.44} fill="var(--on-status-you)" /><rect x={s * 0.56} y={s * 0.28} width={1.4} height={s * 0.44} fill="var(--on-status-you)" /></svg>
      );
    case 'world':
      return (
        <svg {...common}><rect x={1.25} y={1.25} width={s - 2.5} height={s - 2.5} rx={1} fill="none" stroke="var(--status-world)" strokeWidth={1.5} /><rect x={s * 0.33} y={s * 0.3} width={1.3} height={s * 0.4} fill="var(--status-world)" /><rect x={s * 0.56} y={s * 0.3} width={1.3} height={s * 0.4} fill="var(--status-world)" /></svg>
      );
    case 'fault':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="var(--status-fault)" /><path d={`M${s * 0.33} ${s * 0.33} L${s * 0.67} ${s * 0.67} M${s * 0.67} ${s * 0.33} L${s * 0.33} ${s * 0.67}`} stroke="var(--on-status-fault)" strokeWidth={1.4} /></svg>
      );
    case 'recovery':
      return (
        <svg {...common}><path d={`M${c} 1 L${s - 1} ${c} L${c} ${s - 1} L1 ${c} Z`} fill="var(--status-recovery)" /></svg>
      );
    case 'reopened':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--ink)" strokeWidth={1.4} strokeDasharray="2 1.6" /><path d={`M${c} ${s * 0.3} v${s * 0.25}`} stroke="var(--ink)" strokeWidth={1.4} /><circle cx={c} cy={s * 0.72} r={0.9} fill="var(--ink)" /></svg>
      );
    case 'working':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--ink)" strokeWidth={1.4} /><circle cx={c} cy={c} r={1.4} fill="var(--ink)" /></svg>
      );
    case 'ready':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--ink-muted)" strokeWidth={1.4} /></svg>
      );
    case 'blocked':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--status-inert)" strokeWidth={1.3} strokeDasharray="2 1.8" /><path d={`M${s * 0.3} ${c} h${s * 0.4}`} stroke="var(--status-inert)" strokeWidth={1.3} /></svg>
      );
    case 'cancelled':
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--status-inert)" strokeWidth={1.3} /><path d={`M${s * 0.3} ${s * 0.7} L${s * 0.7} ${s * 0.3}`} stroke="var(--status-inert)" strokeWidth={1.3} /></svg>
      );
    case 'inert':
    default:
      return (
        <svg {...common}><circle cx={c} cy={c} r={r} fill="none" stroke="var(--status-inert)" strokeWidth={1.2} strokeDasharray="1.6 1.8" /></svg>
      );
  }
}
