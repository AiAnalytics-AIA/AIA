// The rebuilt interface's icons: Phosphor Regular (prototype-build PBA5, UI-2), by the names the
// screens have always called them, each mapped once here. No emoji anywhere (design brief §5);
// 18.6.6's "🗑", "★" and "↗" became these. The rail keeps its own navigation drawings (RailIcon).

import { PhosphorIcon } from "../icons/PhosphorIcon";
import type { PhosphorName } from "../icons/phosphor";

export type IconName =
  | "home" | "research" | "simulation" | "assistant" | "comment" | "library" | "settings" | "command" | "projects"
  | "external" | "plus" | "search" | "pin" | "tag" | "copy" | "archive" | "trash" | "restore" | "back"
  | "attach" | "link" | "next" | "download" | "client" | "knowledge" | "data" | "memory" | "intelligence"
  | "pencil" | "minus" | "chevron" | "more" | "inspector" | "close"
  | "done" | "running" | "you" | "world" | "fault" | "dot";

const NAMES: Record<IconName, PhosphorName> = {
  home: "house-simple",
  research: "magnifying-glass",
  simulation: "wave-sine",
  assistant: "chat-circle",
  comment: "chat-text",
  library: "books",
  settings: "gear-six",
  command: "terminal-window",
  projects: "folder-simple",
  external: "arrow-square-out",
  plus: "plus",
  search: "magnifying-glass",
  pin: "push-pin",
  tag: "tag",
  copy: "copy",
  archive: "archive",
  trash: "trash",
  restore: "arrow-counter-clockwise",
  back: "caret-left",
  attach: "paperclip",
  link: "link",
  next: "arrow-right",
  download: "download-simple",
  client: "buildings",
  knowledge: "book-open",
  data: "table",
  memory: "clock-counter-clockwise",
  intelligence: "globe",
  pencil: "pencil-simple",
  minus: "minus",
  chevron: "caret-down",
  more: "dots-three",
  inspector: "sidebar-simple",
  close: "x",
  done: "check",
  running: "circle-notch",
  you: "warning",
  world: "globe-simple",
  fault: "x",
  dot: "dot",
};

// The item inspector opens at the right: its panel glyph is drawn on that side.
const MIRRORED: ReadonlySet<IconName> = new Set(["inspector"]);

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return <PhosphorIcon name={NAMES[name]} size={size} className={`shrink-0 ${className}`} mirror={MIRRORED.has(name)} />;
}

/** The Dock rail's four places, drawn as AppShell always drew them (UI-2 keeps them): 1.5 stroke on a 16 grid. */
export type RailIconName = "client" | "intelligence" | "memory" | "settings";

const RAIL_PATHS: Record<RailIconName, string> = {
  client: "M2.5 13.5h11M4 13.5v-10h5v10M9 6.5h3v7M6 5.5h1M6 8h1M6 10.5h1",
  intelligence: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM2 8h12M8 2c1.8 1.8 2.5 3.8 2.5 6S9.8 12.2 8 14M8 2C6.2 3.8 5.5 5.8 5.5 8s.7 4.2 2.5 6",
  memory: "M8 14a6 6 0 1 0-6-6M2 8l-1.5-1.5M2 8l1.5-1.5M8 4.5V8l2.5 1.5",
  settings: "M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
};

export function RailIcon({ name, size = 16 }: { name: RailIconName; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d={RAIL_PATHS[name]} />
    </svg>
  );
}

/**
 * The AI glyph: Phosphor's sparkle, as both prototypes draw it. It marks every control that starts
 * an AI worker job, and nothing else.
 */
export function Sparkle({ size = 16, className = "" }: { size?: number; className?: string }) {
  return <PhosphorIcon name="sparkle" size={size} className={`shrink-0 ${className}`} />;
}
