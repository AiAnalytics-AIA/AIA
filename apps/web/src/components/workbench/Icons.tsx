"use client";

// The workbench's icons: Phosphor Regular (prototype-build PBA5, UI-2), by the names the workbench
// has always called them, each mapped once here. They inherit currentColor and never stand for a
// status: that is Glyph. The AIA mark below is the identity, not an icon.
import { PhosphorIcon } from "../icons/PhosphorIcon";
import type { PhosphorName } from "../icons/phosphor";

const NAMES = {
  at: "at",
  budget: "wallet",
  clock: "clock",
  close: "x",
  down: "caret-down",
  focusArtifact: "corners-out",
  focusChat: "chat-circle",
  inspector: "sidebar-simple",
  memory: "notebook",
  menu: "list",
  next: "caret-right",
  normal: "square-split-horizontal",
  open: "arrow-square-out",
  pencil: "pencil-simple",
  send: "paper-plane-right",
  user: "user",
  worker: "cpu",
} as const satisfies Record<string, PhosphorName>;

export type WorkbenchIconName = keyof typeof NAMES;

// The item inspector opens at the right: its panel glyph is drawn on that side.
const MIRRORED: ReadonlySet<WorkbenchIconName> = new Set(["inspector"]);

export function Icon({ name, size = 16, label }: { name: WorkbenchIconName; size?: number; label?: string }) {
  return <PhosphorIcon name={NAMES[name]} size={size} label={label} className="icon" mirror={MIRRORED.has(name)} />;
}

// The AIA mark: a 5 x 5 lattice where ten points form an A, the apex in signal.
export function Mark({ size = 20, onDark = false }: { size?: number; onDark?: boolean }) {
  const A = new Set(['2,0', '1,1', '3,1', '1,2', '2,2', '3,2', '0,3', '4,3', '0,4', '4,4']);
  const pts = [];
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) pts.push({ x, y, on: A.has(x + ',' + y), apex: x === 2 && y === 0 });
  const ink = onDark ? 'var(--shell-ink)' : 'var(--ink)';
  return (
    <svg width={size} height={size} viewBox="0 0 50 50" aria-hidden className="mark">
      {pts.map((p) => (
        <circle key={p.x + '-' + p.y} cx={5 + p.x * 10} cy={5 + p.y * 10} r={p.on ? 3.6 : 1.4}
          fill={p.apex ? 'var(--brand-apex)' : ink} opacity={p.on ? 1 : 0.28} />
      ))}
    </svg>
  );
}
