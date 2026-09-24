import { createHash } from "node:crypto";

/**
 * The AIA skin over the 18.6.6 interface (ADR 0013).
 *
 * The unit serves one document at `/`. This module decides, from that document's
 * bytes alone, whether the skin applies, and if so adds exactly two tags and
 * changes nothing else. It is pure so the decision is testable without a server.
 */

/**
 * SHA256 of `legacy/npc-panel-18.6.6/app/ui_app.html`, as pinned in
 * `legacy/npc-panel-18.6.6/app-manifest.json`. The skin's selectors were written
 * against exactly this document. `interface-skin.test.ts` fails when the
 * manifest's hash moves, so a regenerated unit is a failing test, not a skin
 * silently applied to markup it was not written for.
 */
export const PINNED_INTERFACE_SHA256 =
  "d844dd6fc7bc738bf1bedaed1b668eb44d79c1ad7d281f093eee15ed1c81eaee";

export const SKIN_STYLESHEET_PATH = "/skin/skin.css";

/** Every outcome, named, so the response header and the log say which one happened. */
export type SkinOutcome =
  | "applied"
  | "bypassed-disabled"
  | "bypassed-hash-mismatch"
  | "bypassed-no-head"
  | "bypassed-no-body";

export type SkinDecision = {
  outcome: SkinOutcome;
  /** The document to send: the original bytes unless `outcome === "applied"`. */
  body: Buffer;
  /** SHA256 of the document as received from the unit. */
  receivedSha256: string;
};

export type SkinOptions = {
  enabled: boolean;
  /** Appended as `?v=` so a new build is never served a cached old skin. */
  version: string | null;
  pinnedSha256?: string;
};

export function sha256Hex(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/** `AIA_INTERFACE_SKIN_ENABLED`: only an explicit "true" or "1" turns the skin on. */
export function skinEnabledFrom(value: string | undefined): boolean {
  const v = value?.trim().toLowerCase();
  return v === "true" || v === "1";
}

export function stylesheetHref(version: string | null): string {
  return version ? `${SKIN_STYLESHEET_PATH}?v=${encodeURIComponent(version)}` : SKIN_STYLESHEET_PATH;
}

/**
 * Decide and, when the skin applies, return the document with:
 *   - `<link rel="preload" as="style">` immediately before the first `</head>`,
 *     so the skin is fetched as early as the page's own styles; and
 *   - `<link rel="stylesheet">` immediately before the last `</body>`, because
 *     the interface puts `<style>` blocks inside `<body>` and appends more to
 *     `<head>` at runtime — a stylesheet in `<head>` would lose the cascade to
 *     them at equal specificity (ADR 0013, decision 1).
 *
 * Any other outcome returns the received bytes unchanged.
 */
export function applySkin(document: Buffer, options: SkinOptions): SkinDecision {
  const receivedSha256 = sha256Hex(document);
  const unchanged = (outcome: SkinOutcome): SkinDecision => ({ outcome, body: document, receivedSha256 });

  if (!options.enabled) return unchanged("bypassed-disabled");
  if (receivedSha256 !== (options.pinnedSha256 ?? PINNED_INTERFACE_SHA256)) {
    return unchanged("bypassed-hash-mismatch");
  }

  const html = document.toString("utf8");
  const headEnd = html.search(/<\/head>/i);
  if (headEnd < 0) return unchanged("bypassed-no-head");
  const bodyEnd = html.toLowerCase().lastIndexOf("</body>");
  if (bodyEnd < 0 || bodyEnd < headEnd) return unchanged("bypassed-no-body");

  const href = stylesheetHref(options.version);
  const preload = `<link rel="preload" as="style" href="${href}" data-aia-skin="preload">`;
  const stylesheet = `<link rel="stylesheet" href="${href}" data-aia-skin="ADR-0013">`;
  const skinned =
    html.slice(0, headEnd) + preload + html.slice(headEnd, bodyEnd) + stylesheet + html.slice(bodyEnd);
  return { outcome: "applied", body: Buffer.from(skinned, "utf8"), receivedSha256 };
}
