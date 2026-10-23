// Zpráva in the report editor (artifact-report RPT8d), the pure part: where the Document Server's
// api.js is loaded from, the mode a width opens in, and what the open route's answers mean in words.
// The editor itself (ONLYOFFICE Docs, behind AIA_ONLYOFFICE_URL) is the API's to configure and sign
// (RPT8c): the page only loads the script the API names and hands it the config the API signed.

import { ApiError } from "./api";

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
