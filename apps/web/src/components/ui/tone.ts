import type { Tone } from "@/design/status";

/**
 * Tone → classes. Styling only: what a tone *means* lives in design/status.ts.
 * Amber (status-you) is the waiting-on-a-person family; the solid fill is
 * reserved for "you" — the API said this viewer can resolve it.
 */
export const TONE_CHIP = {
  running: "bg-status-running-wash text-status-running border-transparent",
  you: "bg-status-you text-on-status-you border-transparent font-semibold",
  person: "bg-status-you-wash text-status-you-ink border-status-you",
  world: "bg-status-world-wash text-status-world border-status-world border-dashed",
  fault: "bg-status-fault-wash text-status-fault border-status-fault",
  recovery: "bg-status-recovery text-on-status-recovery border-transparent font-semibold",
  done: "bg-transparent text-status-done border-border",
  "done-warn": "bg-transparent text-status-done border-border",
  ready: "bg-transparent text-ink-muted border-border-strong",
  inert: "bg-transparent text-status-inert border-border border-dashed",
  blocked: "bg-transparent text-status-inert border-border border-dashed",
  invalid: "bg-transparent text-status-inert border-border border-dashed line-through",
  cancelled: "bg-transparent text-status-inert border-border border-dashed",
  skipped: "bg-transparent text-status-inert border-border border-dashed",
} as const satisfies Record<Tone, string>;
