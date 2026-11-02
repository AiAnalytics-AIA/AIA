// A file given to the Lead from its composer (lead-orchestration LO18a), the pure part: what a
// chip says about it, which files a message may carry, and what holds a message back. The file
// is kept as the client's source (listed under the client's Data); the message carries its id.
import type { LeadFileKept } from "./api";
import type { FileQuestionnaire } from "./lead";
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

/** The server's own refusals of a questionnaire table (application/lead_questionnaire.py, the design's
 * DesignRejected reasons fall back to their code); the import's refusals come with their own words. */
const REFUSALS: Record<string, string> = {
  questionnaire_empty: "šablona nemá žádnou otázku ani sledovanou sadu.",
  one_questionnaire_per_message: "zpráva nese víc tabulek dotazníku; jako dotazník se čte jen první.",
  questionnaire_too_large: "dotazník je větší, než AIA najednou přijme.",
};

/** A questionnaire table's line under the message (LO18b): what it became, in words. A choice not
 *  made yet is asked by the card's two buttons, never guessed. */
export function questionnaireLine(q: FileQuestionnaire): string {
  const counts = `${q.questions} ${q.questions === 1 ? "otázka" : q.questions >= 2 && q.questions <= 4 ? "otázky" : "otázek"}, ${q.tracked_sets} ${q.tracked_sets === 1 ? "sada" : q.tracked_sets >= 2 && q.tracked_sets <= 4 ? "sady" : "sad"}`;
  if (q.status === "refused") return `Tabulka se jako dotazník nenačetla: ${q.message || (q.reason && REFUSALS[q.reason]) || q.reason || "důvod neznámý"}`;
  if (q.status === "filed" || q.run_id) return `Dotazník ze souboru (${counts}) čeká na kontrolu jako návrh.`;
  return `Tabulka je dotazník (${counts}). Dotazník studie už otázky má: nahradit je, nebo doplnit jen ty, které v něm nejsou?`;
}
