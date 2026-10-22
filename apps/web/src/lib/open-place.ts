/**
 * The place a link opens on a stage (a gap's fix from the Run stage, lib/answerability.ts
 * gapFixes; read from the URL's hash): scrolled into view and given keyboard focus, so Tab goes on
 * from there and a screen reader reads it, not the start of the page (review web#7). Next moves
 * focus only to an element it finds by the hash, a no-op on a card that cannot take focus, and
 * finds none where the web's id is not the server's.
 */

/** Whether the person asked for less motion: a scroll then jumps. No media query: none asked. */
function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** How a jump scrolls: smoothly, unless the person asked for reduced motion. */
export function scrollBehavior(): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : "smooth";
}

/** Scroll the element with ``id`` into view, as ``scrollBehavior`` says; false when there is none. */
export function scrollToPlace(id: string, block: ScrollLogicalPosition): boolean {
  const el = document.getElementById(id);
  el?.scrollIntoView?.({ behavior: scrollBehavior(), block });
  return !!el;
}

/**
 * Scroll to the element with ``id`` and focus it without a second scroll. One that cannot take
 * focus (a card, a section, a heading) is made focusable from script only (tabindex -1), never
 * added to the Tab order; one that can (a field, a button) keeps its own. False when there is none.
 */
export function openPlace(id: string, block: ScrollLogicalPosition): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView?.({ behavior: scrollBehavior(), block });
  if (el.tabIndex < 0 && !el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
  return true;
}
