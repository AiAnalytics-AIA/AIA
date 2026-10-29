// A file given to the Lead from its composer (lead-orchestration LO18a), the pure part: what a
// chip says about it, which files a message may carry, and what holds a message back. The file
// is kept as the client's source (listed under the client's Data); the message carries its id.
import type { LeadFileKept } from "./api";
import { FILE_MAX_BYTES, readingLine, reasonWords } from "./client-sources";

/** The most files one message carries; the server refuses more (FILES_PER_MESSAGE). */
const LEAD_FILES_MAX = 3;
export type Attached = {
  key: string;
  name: string;
  state: "uploading" | "kept" | "refused";
  /** The client's source, once kept. */
  sourceId: string | null;
  words: string;
};

/** A chip for a file being kept. */
export function uploading(key: string, name: string): Attached {
  return { key, name, state: "uploading", sourceId: null, words: "Ukládá se k podkladům klienta…" };
}

/** A chip for a file kept: what reading produced, and for a dataset that the Lead sees its columns only. */
export function kept(key: string, file: LeadFileKept): Attached {
  const line = readingLine(file);
  const words = file.family === "DATASET" && file.outcome !== "UNREADABLE" ? `${line.text} · Vedoucí uvidí jen přehled sloupců` : line.text;
  return { key, name: file.filename, state: "kept", sourceId: file.source_id, words };
}

/** A chip for a file refused, in words by the refusal's code. */
export function refused(key: string, name: string, code: string): Attached {
  return { key, name, state: "refused", sourceId: null, words: `Nepřiloženo: ${reasonWords(code)}` };
}

/** A file refused before it is sent: too large for the client's sources, or empty. */
export function refusedBeforeUpload(file: { size: number }): string | null {
  if (file.size === 0) return "empty";
  if (file.size > FILE_MAX_BYTES) return "too_large";
  return null;
}

/** How many more files the message can take. */
export function room(attached: Attached[]): number {
  return Math.max(0, LEAD_FILES_MAX - attached.filter((a) => a.state !== "refused").length);
}

/** The sources a message carries: the files kept, in the order chosen. */
export function carried(attached: Attached[]): string[] {
  return attached.flatMap((a) => (a.state === "kept" && a.sourceId ? [a.sourceId] : []));
}

/** A file still being kept holds the message back: it would otherwise go without it. */
export function holdsMessage(attached: Attached[]): boolean {
  return attached.some((a) => a.state === "uploading");
}
