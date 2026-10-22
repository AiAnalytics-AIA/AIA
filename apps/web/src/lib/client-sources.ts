// How a client's source (a file kept for the client, lifecycle K2) reads on the client's
// knowledge (client-workspace C7a): which kinds take a file, the reference an item keeps,
// and what the reading produced, in words. A source is not knowledge: an item names it by
// `content.source_id`, and the file and its reading stay the source's.

import { t, tv } from "@/i18n/t";
import type { ClientSource, SourceLocator } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Tone } from "@/lib/tone";

/** The kinds that carry a file: the material itself (domain SOURCE_BACKED_KINDS). */
const FILE_KINDS = ["DOCUMENT", "SOURCE", "DATASET"] as const;

export const takesFile = (kind: string): boolean => (FILE_KINDS as readonly string[]).includes(kind);

/** What the file picker offers: the owner's formats (domain client_sources._FAMILIES). */
export const FILE_ACCEPT = [
  ".pdf", ".docx", ".doc", ".odt", ".txt", ".md", ".pptx",
  ".csv", ".xlsx", ".xls", ".ods",
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov",
].join(",");

/** The largest file the API keeps (SOURCE_MAX_BYTES, 25 MiB); a larger one is said before it is sent. */
export const FILE_MAX_BYTES = 25 * 1024 * 1024;

const SOURCE_ID = /^SRC-[0-9a-f]{16}$/;

/** The source an item's content names, or null: anything not a source's id names none. */
export function sourceIdOf(content: Record<string, unknown> | null | undefined): string | null {
  const ref = content?.source_id;
  return typeof ref === "string" && SOURCE_ID.test(ref) ? ref : null;
}

/** The content with its file named (or its file removed, with null); the rest kept as it was. */
export function withSource(content: Record<string, unknown> | null | undefined, sourceId: string | null): Record<string, unknown> {
  const rest = { ...(content ?? {}) };
  delete rest.source_id;
  return sourceId ? { ...rest, source_id: sourceId } : rest;
}

/** A title from a file's name: without its extension, as written. */
export function titleFromFilename(name: string): string {
  const base = name.replace(/\\/g, "/").split("/").pop() ?? "";
  const dot = base.lastIndexOf(".");
  return (dot > 0 ? base.slice(0, dot) : base).trim();
}

/** A size as a person reads it, with a Czech decimal comma. */
export function sizeWords(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} kB`;
  return `${(kb / 1024).toFixed(1).replace(".", ",")} MB`;
}

/** Whether AIA has words for a reason code. */
export const reasonKnown = (code: string): boolean => t(`aia.sources.reasons.${code}`) !== `aia.sources.reasons.${code}`;

/** A reason code in words; a code AIA has no words for is shown as the code. */
export function reasonWords(code: string | null | undefined): string {
  if (!code) return "";
  return reasonKnown(code) ? t(`aia.sources.reasons.${code}`) : tv("aia.sources.reasonCode", { code });
}

/** What reading produced, in one line, and its tone. Only READ says all of it was read. */
export function readingLine(s: Pick<ClientSource, "outcome" | "reason" | "family" | "segments" | "characters">): { tone: Tone; text: string } {
  switch (s.outcome) {
    case "READ":
      return {
        tone: "done",
        text:
          s.family === "DATASET"
            ? tv("aia.sources.readRows", { rows: plural(s.segments, "řádek", "řádky", "řádků") })
            : tv("aia.sources.readText", { parts: plural(s.segments, "část", "části", "částí"), chars: s.characters.toLocaleString("cs-CZ") }),
      };
    case "PARTIAL":
      return { tone: "you", text: tv("aia.sources.partial", { parts: plural(s.segments, "část", "části", "částí"), reason: reasonWords(s.reason) }) };
    case "UNREADABLE":
      return { tone: "neutral", text: tv("aia.sources.unreadable", { reason: reasonWords(s.reason) }) };
    case "UNSUPPORTED":
      return { tone: "neutral", text: tv("aia.sources.unsupported", { reason: reasonWords(s.reason) }) };
    case "REFUSED":
      return { tone: "fault", text: tv("aia.sources.refused", { reason: reasonWords(s.reason) }) };
  }
}

/** Where a segment stands in the original, as a reader counts it. */
export function locatorWords(l: SourceLocator): string {
  const parts: string[] = [];
  if (l.sheet != null) parts.push(tv("aia.sources.at.sheet", { v: l.sheet }));
  if (l.page != null) parts.push(tv("aia.sources.at.page", { v: l.page }));
  if (l.slide != null) parts.push(tv("aia.sources.at.slide", { v: l.slide }));
  if (l.table != null) parts.push(tv("aia.sources.at.table", { v: l.table }));
  if (l.paragraph != null) parts.push(tv("aia.sources.at.paragraph", { v: l.paragraph }));
  if (l.row != null) parts.push(tv("aia.sources.at.row", { v: l.row }));
  if (l.line != null) parts.push(tv("aia.sources.at.line", { v: l.line }));
  return parts.join(", ");
}
