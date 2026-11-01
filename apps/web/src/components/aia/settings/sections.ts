// The settings page's sections: their ids (each its address, #deep_research), their order and the
// three groups the section menu draws them in (prototype v54). Pure: no React, no request.

export const SECTIONS = ["methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "system", "data"] as const;
export type SectionId = (typeof SECTIONS)[number];

export const SECTION_GROUPS: { key: "research" | "team" | "operations"; sections: readonly SectionId[] }[] = [
  { key: "research", sections: ["methodology", "prompts", "deep_research", "ai"] },
  { key: "team", sections: ["access", "studies"] },
  { key: "operations", sections: ["audit", "system", "data"] },
];

/** A section that is no longer one, and where its content went: Reference is part of Stav systému
 *  (settings-redesign F17, Nigel 25 Oct 2026), so an old #reference link opens Stav systému. */
const MOVED: Readonly<Record<string, SectionId>> = { reference: "system" };

/** The section the page's address names, or null when it names none (or one that does not exist). */
export function sectionFromHash(hash: string = typeof window === "undefined" ? "" : window.location.hash): SectionId | null {
  const id = hash.replace(/^#/, "");
  if (Object.hasOwn(MOVED, id)) return MOVED[id];
  return (SECTIONS as readonly string[]).includes(id) ? (id as SectionId) : null;
}

/**
 * Open a section from the page itself: a new history entry carrying the current entry's state, then
 * the hashchange the page follows. The state is the framework's (Next's __NA and its tree): a bare
 * <a href="#…"> wrote an entry with none, and Next's router ignores a popstate without it, so Back
 * from another page to that entry changed the address and left the other page on screen (review of
 * #900). Next's patched pushState passes a state that carries __NA through untouched.
 */
export function goToSection(id: SectionId): void {
  if (window.location.hash === `#${id}`) return;
  window.history.pushState(window.history.state, "", `#${id}`);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

/** A plain click on a link to a section: opened through goToSection, then `opened` (the menu closes
 *  itself). A click with a modifier (a new tab, a new window) or another button is left to the
 *  browser, which the link's href serves, and the page stays where it is. */
export function sectionLinkClick(id: SectionId, opened?: () => void) {
  return (e: { metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean; button: number; preventDefault: () => void }) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    goToSection(id);
    opened?.();
  };
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
