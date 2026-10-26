// The rebuilt interface's icons: Phosphor Regular (prototype-build PBA5, UI-2), by the names the
// screens have always called them, each mapped once here. No emoji anywhere (design brief §5);
// 18.6.6's "🗑", "★" and "↗" became these. The rail keeps its own navigation drawings
// (aia/rail-icons.tsx).

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
  fault: "x-circle",
  dot: "dot",
};

// The item inspector opens at the right: its panel glyph is drawn on that side.
const MIRRORED: ReadonlySet<IconName> = new Set(["inspector"]);

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return <PhosphorIcon name={NAMES[name]} size={size} className={`shrink-0 ${className}`} mirror={MIRRORED.has(name)} />;
}

/**
 * The AI glyph: Phosphor's sparkle, as both prototypes draw it. It marks every control that starts
 * an AI worker job, and nothing else.
 */
export function Sparkle({ size = 16, className = "" }: { size?: number; className?: string }) {
  return <PhosphorIcon name="sparkle" size={size} className={`shrink-0 ${className}`} />;
}
