// The rebuilt interface's icon set: one stroke weight (1.5 on a 16 grid), no
// fill, currentColor. No emoji anywhere (design brief §5); 18.6.6's "🗑", "★"
// and "↗" become these.

export type IconName =
  | "home" | "research" | "simulation" | "assistant" | "library" | "settings" | "command" | "projects"
  | "external" | "plus" | "search" | "pin" | "tag" | "copy" | "archive" | "trash" | "restore" | "back"
  | "attach" | "link" | "next" | "client" | "knowledge" | "data" | "memory" | "intelligence"
  | "done" | "running" | "you" | "world" | "fault" | "dot";

const PATHS: Record<IconName, string> = {
  home: "M2.5 7.5 8 3l5.5 4.5M4 6.5V13h8V6.5",
  research: "M7 11.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9ZM10.5 10.5 14 14",
  simulation: "M2 12.5c2-6 4-6 6 0s4 6 6 0M2 3.5h12",
  assistant: "M3 3.5h10v7H7l-3 2.5v-2.5H3z",
  library: "M3 2.5v11M6.5 2.5v11M10 3l3 10.5",
  settings: "M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
  command: "M3 4.5 6 8l-3 3.5M8 11.5h5",
  projects: "M2 4h4l1.5 1.5H14V13H2z",
  external: "M9.5 2.5h4v4M13.5 2.5 7.5 8.5M11.5 9.5v4h-9v-9h4",
  plus: "M8 3v10M3 8h10",
  search: "M7 11.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9ZM10.5 10.5 14 14",
  pin: "M6 2.5h4l-.5 4 2 2H4.5l2-2zM8 8.5v5",
  tag: "M2.5 2.5h5l6 6-5 5-6-6zM5.5 5.5h.01",
  copy: "M5.5 5.5h8v8h-8zM10.5 5.5v-3h-8v8h3",
  archive: "M2 3h12v3H2zM3 6v7h10V6M6.5 8.5h3",
  trash: "M2.5 4h11M6 4V2.5h4V4M4 4l.7 9.5h6.6L12 4",
  restore: "M3 8a5 5 0 1 0 1.5-3.5L3 6M3 2.5V6h3.5",
  back: "M10 3 5 8l5 5",
  client: "M2.5 13.5h11M4 13.5v-10h5v10M9 6.5h3v7M6 5.5h1M6 8h1M6 10.5h1",
  knowledge: "M2.5 3h4a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 0 6.5 12h-4zM13.5 3h-4A1.5 1.5 0 0 0 8 4.5v9A1.5 1.5 0 0 1 9.5 12h4z",
  data: "M2.5 3h11v10h-11zM2.5 6.5h11M2.5 10h11M6.5 3v10",
  memory: "M8 14a6 6 0 1 0-6-6M2 8l-1.5-1.5M2 8l1.5-1.5M8 4.5V8l2.5 1.5",
  intelligence: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM2 8h12M8 2c1.8 1.8 2.5 3.8 2.5 6S9.8 12.2 8 14M8 2C6.2 3.8 5.5 5.8 5.5 8s.7 4.2 2.5 6",
  attach: "M11 5.5 6.2 10.3a1.5 1.5 0 0 0 2.1 2.1l5-5a3 3 0 0 0-4.2-4.2l-5 5a4.5 4.5 0 0 0 6.4 6.4L14 11",
  link: "M6.5 9.5l3-3M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1",
  next: "M3 8h10M9 4l4 4-4 4",
  // Status glyphs: shape carries the status as well as colour (brief §5).
  done: "M3 8.5 6.5 12 13 4.5",
  running: "M8 2.5a5.5 5.5 0 1 1-5.5 5.5",
  you: "M8 2.5v6M8 11.5v.01M2.5 13.5 8 2.5l5.5 11z",
  world: "M4.5 8h7M8 4.5v7M8 13.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11Z",
  fault: "M4 4l8 8M12 4l-8 8",
  dot: "M8 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
};

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/**
 * The AI glyph (Studio v3): two four-point stars, filled. It marks every control
 * that starts an AI worker job, and nothing else.
 */
export function Sparkle({ size = 16, className = "" }: { size?: number; className?: string }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 16 16" fill="currentColor" className={`shrink-0 ${className}`}>
      <path d="M7 1.5l1.25 3.6L11.8 6.4 8.25 7.7 7 11.3 5.75 7.7 2.2 6.4l3.55-1.3z" />
      <path d="M12.2 9.6l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z" />
    </svg>
  );
}
