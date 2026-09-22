import type { Tone } from "@/design/status";

/**
 * Shape carries the state; colour only reinforces it.
 *   circle family  — machine states: running (ring + core), ready (ring), fault (disc with ×), done (check)
 *   square + bars  — parked: solid = waiting on a person, hollow = waiting on the world
 *   diamond        — recovery required
 *   dashed circle  — inert family: not started, blocked, skipped, cancelled, invalidated
 */
export const TONE_SHAPE = {
  running: "ring-core", you: "square-solid", person: "square-solid", world: "square-hollow",
  fault: "disc-x", recovery: "diamond", done: "check", "done-warn": "check-warn", ready: "ring",
  inert: "dashed-ring", blocked: "dashed-ring-bar", invalid: "dashed-return", cancelled: "ring-slash", skipped: "dashed-arrow",
} as const satisfies Record<Tone, string>;

export function StatusGlyph({ tone, size = 14 }: { tone: Tone; size?: number }) {
  const sw = 1.6;
  let body: React.ReactNode;
  switch (tone) {
    case "running":
      body = <><circle cx={8} cy={8} r={6.2} fill="none" stroke="currentColor" strokeWidth={sw} /><circle cx={8} cy={8} r={3.2} fill="currentColor" /></>;
      break;
    case "you":
    case "person":
      // The bars are holes, so the glyph reads on an amber fill and on a plain surface alike.
      body = <path d="M1.5 1.5h13v13h-13z M5 4.5h2v7h-2z M9 4.5h2v7h-2z" fill="currentColor" fillRule="evenodd" />;
      break;
    case "world":
      body = <><rect x={2} y={2} width={12} height={12} rx={1} fill="none" stroke="currentColor" strokeWidth={sw} /><path d="M6.3 5.5v5M9.7 5.5v5" stroke="currentColor" strokeWidth={sw} /></>;
      break;
    case "fault":
      body = <path d="M8 1.2a6.8 6.8 0 1 0 0 13.6A6.8 6.8 0 0 0 8 1.2z M5.9 4.8 8 6.9l2.1-2.1 1.1 1.1L9.1 8l2.1 2.1-1.1 1.1L8 9.1l-2.1 2.1-1.1-1.1L6.9 8 4.8 5.9z" fill="currentColor" fillRule="evenodd" />;
      break;
    case "recovery":
      body = <path d="M8 .8 15.2 8 8 15.2.8 8z M7.1 4.2h1.8v4.6H7.1z M7.1 10.4h1.8v1.8H7.1z" fill="currentColor" fillRule="evenodd" />;
      break;
    case "done":
      body = <path d="M2.5 8.5l3.7 3.7 7.3-8" fill="none" stroke="currentColor" strokeWidth={2} />;
      break;
    case "done-warn":
      body = <><path d="M1.5 8.5l3.5 3.5 5.5-6.2" fill="none" stroke="currentColor" strokeWidth={2} /><path d="M12.5 9.5l3 5.3h-6z" fill="currentColor" /></>;
      break;
    case "ready":
      body = <circle cx={8} cy={8} r={6} fill="none" stroke="currentColor" strokeWidth={sw} />;
      break;
    case "blocked":
      body = <><circle cx={8} cy={8} r={6} fill="none" stroke="currentColor" strokeWidth={sw} strokeDasharray="2.2 2" /><path d="M5 8h6" stroke="currentColor" strokeWidth={sw} /></>;
      break;
    case "cancelled":
      body = <><circle cx={8} cy={8} r={6} fill="none" stroke="currentColor" strokeWidth={sw} /><path d="M3.8 12.2 12.2 3.8" stroke="currentColor" strokeWidth={sw} /></>;
      break;
    case "skipped":
      body = <><circle cx={8} cy={8} r={6} fill="none" stroke="currentColor" strokeWidth={sw} strokeDasharray="2.2 2" /><path d="M5.5 8h5M8.5 6l2 2-2 2" fill="none" stroke="currentColor" strokeWidth={sw} /></>;
      break;
    case "invalid":
      body = <><path d="M12.6 5.2A5.6 5.6 0 1 0 13.6 9" fill="none" stroke="currentColor" strokeWidth={sw} strokeDasharray="2.2 1.6" /><path d="M10.5 5.3h2.6V2.6" fill="none" stroke="currentColor" strokeWidth={sw} /></>;
      break;
    case "inert":
      body = <circle cx={8} cy={8} r={6} fill="none" stroke="currentColor" strokeWidth={sw} strokeDasharray="2.2 2" />;
      break;
  }
  return (
    <svg className="inline-block shrink-0" width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" data-shape={TONE_SHAPE[tone]}>
      {body}
    </svg>
  );
}
