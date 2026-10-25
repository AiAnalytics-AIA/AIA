// The settings page's sections: their ids (each its address, #deep_research), their order and the
// three groups the section menu draws them in (prototype v54). Pure: no React, no request.

export const SECTIONS = ["methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "system", "reference", "data"] as const;
export type SectionId = (typeof SECTIONS)[number];

export const SECTION_GROUPS: { key: "research" | "team" | "operations"; sections: readonly SectionId[] }[] = [
  { key: "research", sections: ["methodology", "prompts", "deep_research", "ai"] },
  { key: "team", sections: ["access", "studies"] },
  { key: "operations", sections: ["audit", "system", "reference", "data"] },
];

/** The section the page's address names, or null when it names none (or one that does not exist). */
export function sectionFromHash(hash: string = typeof window === "undefined" ? "" : window.location.hash): SectionId | null {
  const id = hash.replace(/^#/, "");
  return (SECTIONS as readonly string[]).includes(id) ? (id as SectionId) : null;
}

/** The event a section sends when it has changed what waits on the person (an approval, a prompt
 *  switched on): the section menu reads its counts again, so its coral total is never left stale. */
export const WAITING_CHANGED = "aia:settings-waiting-changed";
export function waitingChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(WAITING_CHANGED));
}

/** Whether the shortcut chord is ⌘ (Apple platforms) rather than Ctrl. */
export function appleKeys(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
}
