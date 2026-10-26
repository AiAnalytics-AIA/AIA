// The Dock rail's four places, drawn as AppShell always drew them: UI-2 moves the product to
// Phosphor and keeps these. The only hand-drawn icons left in the product; only DockRail uses them.

/** The four places: 1.5 stroke on a 16 grid. */
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
