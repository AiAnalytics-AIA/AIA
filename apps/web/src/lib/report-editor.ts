// Zpráva in the report editor (artifact-report RPT8d), the pure part: where the Document Server's
// api.js is loaded from, the mode a width opens in, and what the open route's answers mean in words.
// The editor itself (ONLYOFFICE Docs, behind AIA_ONLYOFFICE_URL) is the API's to configure and sign
// (RPT8c): the page only loads the script the API names and hands it the config the API signed.

import { ApiError } from "./api";
import type { Approval } from "./artifacts/report";

/** What `POST …/report/editor` answers: the Document Server's origin, the signed config, and the
 *  line and version opened (RPT8c). */
export type EditorOpened = {
  document_server: string;
  config: Record<string, unknown> & { token: string };
  line_id: string;
  koncept: number;
  version_artifact_id: string;
  lines: EditorLine[];
  /** Why the line's last save was not stored, as the server keeps it; null when none failed. */
  problem?: string | null;
};

export type EditorLine = {
  line_id: string;
  koncept: number;
  version_artifact_id: string;
  saved_at: string;
  current_composition: boolean;
};

export type EditorMode = "edit" | "view";

/** The editor edits from 768 px and is read only below (the owner, 2026-10-22). */
export const EDIT_FROM_PX = 768;

/** How long a Document Server has to answer before the read-only draft stays and says so. */
export const EDITOR_TIMEOUT_MS = 20_000;

export function editorMode(widthPx: number): EditorMode {
  return widthPx >= EDIT_FROM_PX ? "edit" : "view";
}

/** The Document Server's api.js on the origin the API named, or null for anything but an https
 *  origin: the page never loads a script from elsewhere, nor from a path the answer chose. */
export function apiScriptUrl(documentServer: string): string | null {
  let url: URL;
  try {
    url = new URL(documentServer);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || url.username || url.password) return null;
  return `${url.origin}/web-apps/apps/api/documents/api.js`;
}

/** What opening the editor answered, for the pane: `off` (no editor configured: the read-only
 *  draft as before, nothing said), or a refusal or failure, said in words beside the read-only draft. */
export type OpenFailure = { kind: "off" } | { kind: "said"; words: string };

const REFUSED: Record<string, string> = {
  client_report_not_editable: "Klientská zpráva se v editoru neupravuje.",
  report_not_ready: "Zpráva k tomuto běhu ještě není složená.",
  report_not_editable: "Tuto verzi zprávy editor neotevře.",
  context_report_not_prepared: "Zprávu s rešerší nejprve připravte; pak ji lze upravit v editoru.",
};

export function openFailure(error: unknown): OpenFailure {
  if (error instanceof ApiError) {
    // 404 is the editor off (AIA_ONLYOFFICE_URL unset), or a line that is not there: either way
    // the read-only draft, as Zpráva shows it without the editor.
    if (error.status === 404) return { kind: "off" };
    const words = REFUSED[error.code];
    if (words) return { kind: "said", words };
    if (error.status === 403) return { kind: "said", words: "Zprávu v editoru upravovat nemůžete." };
  }
  return { kind: "said", words: "Editor zprávy se nepodařilo otevřít; zobrazuje se koncept jen ke čtení." };
}

/** The editor did not come up: its script did not load, or it did not answer in time. */
export const UNREACHABLE = "Editor zprávy neodpovídá; zobrazuje se koncept jen ke čtení.";

const PROBLEMS: Record<string, string> = {
  document_server_restarted: "Editor se mezitím restartoval a poslední uložení nepřevzal; upravte dokument znovu.",
  document_server_unreachable: "Poslední uložení se z editoru nepodařilo stáhnout.",
  document_server_save_failed: "Editor poslední uložení nedokončil.",
  not_the_editors_file: "Poslední uložení ukazovalo mimo editor; AIA ho nepřevzala.",
  unknown_author: "Poslední uložení podepsal někdo, komu AIA editor neotevřela; nepřevzato.",
  save_unreadable: "Poslední uložený soubor nebylo možné přečíst; nepřevzato.",
  save_too_large: "Poslední uložený soubor byl příliš velký; nepřevzato.",
  session_closed: "Poslední uložení přišlo do již zavřené relace; nepřevzato.",
};

/** Why the line's last save was not stored, in words; null when none failed. A code AIA has no words
 *  for yet is said as it is, never dropped. */
export function problemWords(problem: string | null | undefined): string | null {
  if (!problem) return null;
  return PROBLEMS[problem] ?? `Poslední uložení AIA nepřevzala (${problem}).`;
}

/** A number the save changed, as `GET …/report/editor/versions/{id}` stores it (RPT8b). */
export type SavedChange = {
  kind: "changed" | "removed" | "added" | "typed";
  /** The locked control's tag; null for a number typed outside one. */
  tag: string | null;
  was: string | null;
  now: string | null;
  /** For `typed`: the paragraph the number sits in, as saved. */
  paragraph: string | null;
};

/** A saved version of a report line, as the doc bar and its approval read it (RPT8c). */
export type EditorVersionRead = {
  version_artifact_id: string;
  line_id: string;
  koncept: number;
  edited_from: string | null;
  author_names: (string | null)[];
  saved_at: string;
  review_state: "DRAFT_UNAPPROVED" | "APPROVED_INTERNAL";
  approved_on: string | null;
  approval: Approval | null;
  /** Null for koncept 1, the composer's own, which changed nothing. */
  changes: { uncomparable: string | null; changes: SavedChange[] } | null;
  /** The line's newest version; another than this one means a later save exists. */
  newest_in_line: { version_artifact_id: string; koncept: number } | null;
};

const stamp = new Intl.DateTimeFormat("cs-CZ", {
  day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Prague",
});

/** "Koncept 3, uložen 23. 10. 2026 22:10 · Jana Nováková": the version and who saved it; an author
 *  the server does not name (no display name, or no longer a member) is "neznámý autor", never
 *  presumed a member; a time that does not parse is said as stored, never guessed. */
export function savedWords(v: Pick<EditorVersionRead, "koncept" | "saved_at" | "author_names">): string {
  const at = Number.isNaN(Date.parse(v.saved_at)) ? v.saved_at : stamp.format(new Date(v.saved_at));
  const who = v.author_names.map((n) => n ?? "neznámý autor").join(", ");
  return v.koncept === 1
    ? `Koncept 1 (složená zpráva), uložen ${at}`
    : `Koncept ${v.koncept}, uložen ${at}${who ? ` · ${who}` : ""}`;
}

/** One change in words: what code wrote and what the person left there. */
export function changeWords(c: SavedChange): string {
  const of = c.tag ? `Číslo ${c.tag}` : "Číslo";
  switch (c.kind) {
    case "changed": return `${of}: ${c.was ?? "?"} → ${c.now ?? "?"}`;
    case "removed": return `${of} odstraněno (bylo ${c.was ?? "?"})`;
    case "added": return `${of} přidáno: ${c.now ?? "?"}`;
    case "typed": return `Číslo napsané ručně: ${c.now ?? "?"}${c.paragraph ? ` (v odstavci „${c.paragraph}“)` : ""}`;
  }
}

const UNCOMPARABLE: Record<string, string> = {
  no_baseline: "první verze této řady není uložena",
  no_controls: "zpráva byla složena dřív, než kód zamykal svá čísla",
};

/** What "Upraveno ručně" says of a version, against its line's first version (the composed
 *  draft): null for koncept 1, the reason when nothing could be compared (never "no change"), else
 *  the count. */
export function editedWords(v: Pick<EditorVersionRead, "changes">): string | null {
  if (v.changes === null) return null;
  if (v.changes.uncomparable) {
    return `Upraveno ručně: nelze porovnat (${UNCOMPARABLE[v.changes.uncomparable] ?? v.changes.uncomparable})`;
  }
  const n = v.changes.changes.length;
  return n === 0 ? "Upraveno ručně: žádné číslo" : `Upraveno ručně: ${n} ${n === 1 ? "číslo" : n < 5 ? "čísla" : "čísel"}`;
}

/** The changes a dialog names, at most `max`, the rest counted. */
export function changesListed(changes: SavedChange[], max = 8): string {
  const shown = changes.slice(0, max).map(changeWords).join("; ");
  return changes.length > max ? `${shown}; a ${changes.length - max} dalších` : shown;
}

/** The question an edited version's approval asks: the version by name, and what it changed. */
export function editedApprovalQuestion(v: EditorVersionRead, document: string): string {
  const head = `Schválit ${document}, koncept ${v.koncept} (${v.version_artifact_id})?`;
  const edited = editedWords(v);
  if (!edited) return `${head} Je to složená zpráva bez ručních úprav.`;
  const list = v.changes?.changes.length ? ` ${changesListed(v.changes.changes)}.` : "";
  return `${head} ${edited}.${list} Neuložené úpravy v editoru schválení nezahrnuje.`;
}
