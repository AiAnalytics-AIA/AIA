/**
 * Client scope chrome: which of the six accent slots a client wears, and its
 * monogram. Presentation only — the accent is a cue, not an identifier and not a
 * security boundary (plan decision DS-2). Name and monogram stay authoritative
 * and are always shown beside it.
 *
 * FALLBACK. The slot will come from the server as `clients.accent_slot`,
 * assigned by least-used at client creation (OI-12). Until that column exists
 * this hashes the client id, which collides: at five clients two share a slot
 * (`cl_salvia` and `cl_tecka` both land on slot 4). Remove `hashAccentSlot` when the
 * API returns the slot.
 */

export const ACCENT_SLOTS = [1, 2, 3, 4, 5, 6] as const;
export type AccentSlot = (typeof ACCENT_SLOTS)[number];

/** FNV-1a (32-bit) of the id, onto slots 1..6. Deterministic, collision-prone. */
export function hashAccentSlot(clientId: string): AccentSlot {
  let h = 0x811c9dc5;
  for (let i = 0; i < clientId.length; i++) {
    h ^= clientId.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return ACCENT_SLOTS[h % ACCENT_SLOTS.length];
}

/** Server slot when present and valid, else the hash fallback. */
export function accentSlot(clientId: string, serverSlot?: number | null): AccentSlot {
  return ACCENT_SLOTS.find((s) => s === serverSlot) ?? hashAccentSlot(clientId);
}

/** Literal class names, so Tailwind sees them at build time. */
export const ACCENT_BG: Record<AccentSlot, string> = {
  1: "bg-client-1",
  2: "bg-client-2",
  3: "bg-client-3",
  4: "bg-client-4",
  5: "bg-client-5",
  6: "bg-client-6",
};

/**
 * Up to two letters: the initials of the first two words of the name, or the
 * first two letters of a one-word name. Diacritics are kept (Č stays Č).
 */
export function monogram(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters = words.length === 1 ? [...words[0]].slice(0, 2) : [[...words[0]][0], [...words[1]][0]];
  return letters.join("").toLocaleUpperCase("cs-CZ");
}
