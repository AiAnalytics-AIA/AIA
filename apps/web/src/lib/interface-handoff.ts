import { PINNED_INTERFACE_SHA256 } from "./interface-skin";

/**
 * The hand-off from the rebuilt interface into the classic one (ADR 0014,
 * decision 8): /public/skin/handoff.js, added to the pinned document only, and
 * only while the rebuilt interface is switched on. Pure, like applySkin.
 */

export const HANDOFF_SCRIPT_PATH = "/skin/handoff.js";

export type HandoffOutcome = "added" | "bypassed-disabled" | "bypassed-hash-mismatch" | "bypassed-no-body";

export function applyHandoff(
  document: Buffer,
  receivedSha256: string,
  options: { enabled: boolean; version: string | null; pinnedSha256?: string },
): { outcome: HandoffOutcome; body: Buffer } {
  if (!options.enabled) return { outcome: "bypassed-disabled", body: document };
  if (receivedSha256 !== (options.pinnedSha256 ?? PINNED_INTERFACE_SHA256)) {
    return { outcome: "bypassed-hash-mismatch", body: document };
  }
  const html = document.toString("utf8");
  const bodyEnd = html.toLowerCase().lastIndexOf("</body>");
  if (bodyEnd < 0) return { outcome: "bypassed-no-body", body: document };
  const src = options.version ? `${HANDOFF_SCRIPT_PATH}?v=${encodeURIComponent(options.version)}` : HANDOFF_SCRIPT_PATH;
  const tag = `<script src="${src}" data-aia-handoff="ADR-0014"></script>`;
  return { outcome: "added", body: Buffer.from(html.slice(0, bodyEnd) + tag + html.slice(bodyEnd), "utf8") };
}

export type ClassicTarget = { open: string } | { start: "research" | "simulation" } | { go: string };

/** The link from a rebuilt screen to the classic interface, carrying one hand-off instruction. */
export function classicHref(target?: ClassicTarget): string {
  if (!target) return "/";
  const [verb, arg] = Object.entries(target)[0] as [string, string];
  if (!/^[A-Za-z0-9_-]{1,160}$/.test(arg)) return "/";
  return `/#aia:${verb}=${arg}`;
}
