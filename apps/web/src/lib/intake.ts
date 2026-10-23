// The client's intake sheet (client-workspace C7b), its pure part: a batch of files, each
// kept as the client's source the moment it lands (lifecycle K2) and said in words; then
// one knowledge item per file, filed in the batch's folder and labels or its own folder.
// Nothing here talks to the API; IntakeSheet.tsx does, one file at a time.

import { t, tv } from "@/i18n/t";
import type { Placement, SourceAdded, SourceDetail } from "@/lib/api";
import { readingLine, reasonWords, titleFromFilename, withSource } from "@/lib/client-sources";
import { plural, relative } from "@/lib/format";
import type { Tone } from "@/lib/tone";

/** What a file becomes in the client's knowledge. */
export type IntakeKind = "DOCUMENT" | "DATASET" | "SOURCE";

export type Entry = {
  key: string;
  name: string;
  size: number;
  phase: "reading" | "stored" | "failed";
  source: SourceAdded | null;
  /** A table's reading, read once it is kept, for its columns; the row reads until it has it. */
  detail: SourceDetail | null;
  error: string | null;
  kind: IntakeKind;
  title: string;
  /** The file's own folder; undefined follows the batch's. */
  folder: string | null | undefined;
  /** The earlier row of this batch holding the same bytes: this one adds nothing. */
  duplicateOf: string | null;
};

const TABLE = new Set([".csv", ".xlsx", ".xls", ".ods"]);
const MEDIA = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov"]);

const extensionOf = (name: string): string => {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot).toLowerCase() : "";
};

/** What the name says a file will be, before AIA has kept it. */
export function kindOfName(name: string): IntakeKind {
  const ext = extensionOf(name);
  return TABLE.has(ext) ? "DATASET" : MEDIA.has(ext) ? "SOURCE" : "DOCUMENT";
}

/** The short type a row's badge shows: the extension, or a question mark. */
export function badge(name: string): { label: string; tone: "pdf" | "word" | "table" | "slides" | "plain" } {
  const ext = extensionOf(name).slice(1);
  const label = ext ? ext.toUpperCase().slice(0, 4) : "?";
  if (ext === "pdf") return { label, tone: "pdf" };
  if (["doc", "docx", "odt"].includes(ext)) return { label, tone: "word" };
  if (TABLE.has(`.${ext}`)) return { label, tone: "table" };
  if (ext === "pptx") return { label, tone: "slides" };
  return { label, tone: "plain" };
}

export function newEntry(file: { name: string; size: number }, key: string): Entry {
  return {
    key,
    name: file.name,
    size: file.size,
    phase: "reading",
    source: null,
    detail: null,
    error: null,
    kind: kindOfName(file.name),
    title: titleFromFilename(file.name),
    folder: undefined,
    duplicateOf: null,
  };
}

/** A file kept: what it is now follows what AIA found, and a repeat in the batch is named.
 *  A table still reads until its columns are in (withDetail), so its personal-data warning is
 *  never missing from a row that can be saved. */
export function stored(entries: Entry[], key: string, source: SourceAdded): Entry[] {
  const earlier = entries.find((e) => e.key !== key && e.source?.source_id === source.source_id && !e.duplicateOf);
  return entries.map((e) => {
    if (e.key !== key) return e;
    const kind: IntakeKind =
      source.family === "DATASET" ? (e.kind === "DOCUMENT" ? "DOCUMENT" : "DATASET") : source.family === "DOCUMENT" ? "DOCUMENT" : "SOURCE";
    const phase = source.family === "DATASET" ? "reading" : "stored";
    return { ...e, phase, source, kind, error: null, duplicateOf: earlier ? earlier.key : null };
  });
}

export const failed = (entries: Entry[], key: string, message: string): Entry[] =>
  entries.map((e) => (e.key === key ? { ...e, phase: "failed", error: message } : e));

export const withDetail = (entries: Entry[], key: string, detail: SourceDetail): Entry[] =>
  entries.map((e) => (e.key === key ? { ...e, phase: "stored", detail, error: null } : e));

/** A kept table whose columns could not be read back: it waits for a retry, never saved blind. */
export const detailFailed = (entries: Entry[], key: string, message: string): Entry[] =>
  entries.map((e) => (e.key === key ? { ...e, phase: "failed", error: message } : e));

/** A row that can be tried again: the file is kept, only its columns are missing. */
export const retryable = (e: Entry): boolean => e.phase === "failed" && e.source !== null;

/** A retried row reads again. */
export const retrying = (entries: Entry[], key: string): Entry[] =>
  entries.map((e) => (e.key === key ? { ...e, phase: "reading", error: null } : e));

export const changed = (entries: Entry[], key: string, change: Partial<Pick<Entry, "kind" | "title" | "folder">>): Entry[] =>
  entries.map((e) => (e.key === key ? { ...e, ...change } : e));

/** A row removed; a row that repeated it now stands on its own. */
export function removed(entries: Entry[], key: string): Entry[] {
  const rest = entries.filter((e) => e.key !== key);
  const heir = rest.find((e) => e.duplicateOf === key);
  return rest.map((e) => (e.duplicateOf !== key ? e : e === heir ? { ...e, duplicateOf: null } : { ...e, duplicateOf: heir!.key }));
}

/** A table: AIA read it as rows, so the person chooses Datová sada or Dokument. */
export const isTable = (e: Entry): boolean => e.phase === "stored" && e.source?.family === "DATASET";

/** The rows that become knowledge: kept, and not a repeat of another row. */
export const addable = (entries: Entry[]): Entry[] => entries.filter((e) => e.phase === "stored" && !e.duplicateOf);

const stillReading = (entries: Entry[]): number => entries.filter((e) => e.phase === "reading").length;

/** The columns a table's reading flagged as personal data, by their header or letter. */
export function personalColumns(detail: SourceDetail | null): string[] {
  const sheets = detail?.reading.dataset?.sheets ?? [];
  return sheets.flatMap((s) => s.columns.filter((c) => c.personal).map((c) => c.header ?? c.letter));
}

/** A table's reading in words: its sheets, the first sheet's columns and rows. */
function tableLine(detail: SourceDetail): string | null {
  const data = detail.reading.dataset;
  if (!data || detail.outcome !== "READ") return null;
  const first = data.sheets[0];
  if (!first) return null;
  return tv("aia.intake.readTable", {
    sheets: plural(data.sheets.length, "list", "listy", "listů") + (data.more_sheets ? "+" : ""),
    columns: plural(first.columns.length, "sloupec", "sloupce", "sloupců"),
    rows: plural(first.rows, "řádek", "řádky", "řádků"),
  });
}

/** What happened to a row, in words, and its tone. Never a number AIA does not have. */
export function rowLine(entries: Entry[], e: Entry): { tone: Tone; text: string } {
  if (e.phase === "reading") return { tone: "running", text: t("aia.intake.reading") };
  if (retryable(e)) return { tone: "fault", text: e.error ?? t("aia.intake.columnsFailed") };
  if (e.phase === "failed" || !e.source) return { tone: "fault", text: e.error ?? t("aia.intake.failed") };
  if (e.duplicateOf) {
    const first = entries.find((x) => x.key === e.duplicateOf);
    return { tone: "neutral", text: tv("aia.intake.sameAsAbove", { name: first?.name ?? "" }) };
  }
  const s = e.source;
  if (s.family === "IMAGE" || s.family === "VIDEO") return { tone: "you", text: t("aia.intake.noText") };
  if (s.outcome === "UNREADABLE" || s.outcome === "UNSUPPORTED" || s.outcome === "REFUSED") {
    return { tone: "you", text: tv("aia.intake.keptUnread", { reason: reasonWords(s.reason) }) };
  }
  const table = e.detail ? tableLine(e.detail) : null;
  return table ? { tone: "done", text: table } : readingLine(s);
}

/** Bytes the client already had: where they first came. Null for a new source. */
export function alreadyKept(e: Entry): string | null {
  const s = e.source;
  if (!s || s.created || e.duplicateOf) return null;
  const first = s.occurrences[s.occurrences.length - 1];
  if (!first) return null;
  return tv("aia.intake.alreadyKept", { name: first.filename, when: relative(first.added_at) ?? "" });
}

/** The footer's line: what will be added, what still reads, what cannot be added. */
export function summary(entries: Entry[]): string {
  const ready = addable(entries);
  const n = (k: IntakeKind) => ready.filter((e) => e.kind === k).length;
  const parts = [
    n("DOCUMENT") ? plural(n("DOCUMENT"), "dokument", "dokumenty", "dokumentů") : null,
    n("DATASET") ? plural(n("DATASET"), "datová sada", "datové sady", "datových sad") : null,
    n("SOURCE") ? plural(n("SOURCE"), "zdroj bez textu", "zdroje bez textu", "zdrojů bez textu") : null,
  ].filter((p): p is string => p !== null);
  const lines = [parts.length ? tv("aia.intake.willAdd", { what: parts.join(", ") }) : t("aia.intake.nothingYet")];
  const reading = stillReading(entries);
  if (reading) lines.push(tv("aia.intake.waitingFor", { n: plural(reading, "soubor", "soubory", "souborů") }));
  const bad = entries.filter((e) => e.phase === "failed").length;
  if (bad) lines.push(tv("aia.intake.cannotAdd", { n: plural(bad, "soubor", "soubory", "souborů") }));
  return lines.join(" ");
}

/** The save button's words; it waits while a file is still being read. Items made but not yet
 *  filed (a placement failed) are finished first, and are never made twice. */
export function action(entries: Entry[], unfiled = false): { label: string; disabled: boolean } {
  if (stillReading(entries)) return { label: t("aia.intake.waiting"), disabled: true };
  if (unfiled && !addable(entries).length) return { label: t("aia.intake.fileAgain"), disabled: false };
  const n = addable(entries).length;
  return { label: tv("aia.intake.add", { n: plural(n, "podklad", "podklady", "podkladů") }), disabled: n === 0 };
}

/** One knowledge item per row: its kind, title and the source it names. */
export function itemsFor(entries: Entry[]): { key: string; kind: IntakeKind; title: string; content: Record<string, unknown> }[] {
  return addable(entries).map((e) => ({
    key: e.key,
    kind: e.kind,
    title: e.title.trim() || titleFromFilename(e.name) || e.name,
    content: withSource({}, e.source!.source_id),
  }));
}

/** The folder a row's item goes to: its own, else the batch's. */
export const folderOf = (e: Entry, batchFolder: string | null): string | null => (e.folder === undefined ? batchFolder : e.folder);

/** An item made, with the folder its row asked for when it was made. */
export type Made = { itemId: string; folder: string | null };

/** Filing after the items exist: one placement per folder, then the batch's labels once. */
export function placementsFor(created: Made[], labels: string[]): Placement[] {
  const byFolder = new Map<string, string[]>();
  for (const c of created) {
    if (!c.folder) continue;
    byFolder.set(c.folder, [...(byFolder.get(c.folder) ?? []), c.itemId]);
  }
  const out: Placement[] = [...byFolder].map(([folder_id, item_ids]) => ({ item_ids, folder_id }));
  if (labels.length && created.length) out.push({ item_ids: created.map((c) => c.itemId), add_labels: labels });
  return out;
}

/** Pasted text as a file the readers take: its name, with .txt when it has none. */
export function pastedFile(name: string, text: string): File {
  const base = name.trim() || t("aia.intake.pastedName");
  const file = extensionOf(base) === ".txt" || extensionOf(base) === ".md" ? base : `${base}.txt`;
  return new File([text], file, { type: "text/plain" });
}
