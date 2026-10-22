// Analýza's external-context register (artifact-analysis ANL5): the Design Research findings the run's
// modules were shown as context, never as evidence. Pure.

/** A finding's source as a chip: a link only for an http(s) address, named by its host; anything else
 *  (a knowledge reference, a malformed address) as its text, never a link. */
export function sourceChip(source: string): { href: string | null; label: string } {
  try {
    const url = new URL(source);
    if (url.protocol === "https:" || url.protocol === "http:") return { href: url.href, label: url.hostname.replace(/^www\./, "") };
  } catch {
    /* not an address */
  }
  return { href: null, label: source };
}
