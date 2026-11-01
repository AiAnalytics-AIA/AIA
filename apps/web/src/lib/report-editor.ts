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
  /** The Subresource Integrity api.js must match (RPT8e); absent from an API before it, so nothing loads. */
  api_integrity?: string;
};

/** What `POST /session/docs-ticket` answers: where the one-time ticket is spent, on the editor's origin. */
export type DocsTicket = { session_url: string; expires_at: string };

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

const API_JS = "/web-apps/apps/api/documents/api.js";
const DOCS_SESSION = "/__aia/session";

const httpsOrigin = (value: string): URL | null => {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url : null;
  } catch {
    return null;
  }
};

/** The Document Server's api.js on the origin the API named, or null for anything but an https origin:
 *  the page never loads a script from elsewhere, nor from a path an answer chose. The canonical path,
 *  because ONLYOFFICE's api.js finds its own base (and so its iframes' origin) by matching its script
 *  element's src against `api/documents/api.js` (getBasePath; Codex on #895). */
export function apiScriptUrl(documentServer: string): string | null {
  const origin = httpsOrigin(documentServer);
  return origin ? `${origin.origin}${API_JS}` : null;
}

/** Where the page spends the one-time ticket that opens the editor's origin to this person
 *  (report-editor-hosting: the docs gate needs its cookie, which spending the ticket sets), before
 *  api.js is loaded: the ticket's URL, `next` the script's path. Null unless the ticket is spent on the
 *  origin the API named, at its session path, over https, and names no `next` of its own. */
export function ticketUrl(documentServer: string, sessionUrl: string): string | null {
  const origin = httpsOrigin(documentServer);
  const ticket = httpsOrigin(sessionUrl);
  if (!origin || !ticket || ticket.origin !== origin.origin || ticket.pathname !== DOCS_SESSION) return null;
  if (!ticket.searchParams.get("ticket") || ticket.searchParams.has("next")) return null;
  ticket.searchParams.set("next", API_JS);
  return ticket.href;
}

/** The api.js integrity as the API answered it, when it is one SHA-384 digest (RPT8e), else null:
 *  without one the page loads no script into AIA's origin. */
export function scriptIntegrity(value: string | undefined): string | null {
  return value && /^sha384-[A-Za-z0-9+/]{64}$/.test(value) ? value : null;
}

/** The editor's script was not loaded because nothing proves it is the pinned one (RPT8e). */
export const UNVERIFIED = "Skript editoru zprávy nelze ověřit; zobrazuje se koncept jen ke čtení.";

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
/** The edit start a page last made in an editing session (RPT8f): its session's key, the page's own
 *  id and its count from 1. The page reports each start to AIA; an approval names the last one, and
 *  the server refuses it (409 `report_edits_unsaved`) until a stored version holds it. */
export type SeenEdit = { document_key: string; page: string; seq: number };

/** This page's id for its edit reports: random, within the server's `[0-9A-Za-z_-]{8,64}`. */
export function newPageId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return `p${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

/** The document key a signed config opens, or null when it names none. */
export function documentKeyOf(config: Record<string, unknown>): string | null {
  const document = config.document;
  const key = document && typeof document === "object" ? (document as Record<string, unknown>).key : null;
  return typeof key === "string" ? key : null;
}

/** An edit is in no stored version yet: approval waits for the save that holds it. */
export const UNSTORED = "V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.";

/** Why the server held an edited version's approval (RPT8f), in words; null for another refusal. */
export function unsavedWords(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.code !== "report_edits_unsaved") return null;
  return error.details.reason === "edit_not_received"
    ? "Poslední úprava z editoru ještě nedorazila do AIA; schvalte znovu za chvíli."
    : `${UNSTORED} Neuloží-li editor koncept sám, uložte ho v editoru (Ctrl+S).`;
}

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
  /** The last change the file holds, as the Document Server said it (`lastsave`); null when it did
   *  not, and for koncept 1. */
  content_at?: string | null;
  /** The server's time when it answered: the clock `content_at` and `saved_at` are on. */
  server_now?: string;
  /** The server's verdict (RPT8f): whether this version holds every edit its line's open session
   *  reported and the asking page's (`seen_*` on the read), by the rule an approval is refused
   *  under, and why not; absent from an API before it, which holds the approval. */
  edits?: { saved: boolean; reason: string | null };
};

/** What an approval records and hands over (RPT3d, spec Z4), said in every approval question. */
export const EXACT = "Schválení se zapíše pod vaším jménem a stáhnete přesně tuto verzi.";

const stamp = new Intl.DateTimeFormat("cs-CZ", {
  day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Prague",
});

/** A stored time in Prague's words ("23. 10. 2026 22:10"); one that does not parse is said as
 *  stored, never guessed. */
export const timeWords = (iso: string): string => (Number.isNaN(Date.parse(iso)) ? iso : stamp.format(new Date(iso)));

/** "Koncept 3, uložen 23. 10. 2026 22:10 · Jana Nováková": the version and who saved it; an author
 *  the server does not name (no display name, or no longer a member) is "neznámý autor", never
 *  presumed a member; a time that does not parse is said as stored, never guessed. */
export function savedWords(v: Pick<EditorVersionRead, "koncept" | "saved_at" | "author_names">): string {
  const at = timeWords(v.saved_at);
  const who = v.author_names.map((n) => n ?? "neznámý autor").join(", ");
  return v.koncept === 1
    ? `Koncept 1 (složená zpráva), uložen ${at}`
    : `Koncept ${v.koncept}, uložen ${at}${who ? ` · ${who}` : ""}`;
}

/** A control's text as a change line shows it: a locked span (a design, run or map span) can be a
 *  whole paragraph, so past `max` characters it ends in "…"; unknown is "?". */
const clip = (text: string | null, max = 80): string =>
  text === null ? "?" : text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;

/** Both sides of a change as a line shows them: where either is long, each is cut to the stretch
 *  where the two differ, with `context` characters around it, so the difference is never what "…"
 *  hides. */
function clipPair(was: string | null, now: string | null, max = 80, context = 24): [string, string] {
  if (was === null || now === null || (was.length <= max && now.length <= max)) return [clip(was), clip(now)];
  let head = 0;
  while (head < was.length && head < now.length && was[head] === now[head]) head++;
  let tail = 0;
  while (tail < was.length - head && tail < now.length - head && was[was.length - 1 - tail] === now[now.length - 1 - tail]) tail++;
  const around = (text: string) => {
    const from = Math.max(0, head - context);
    const to = Math.min(text.length, text.length - tail + context);
    return `${from > 0 ? "…" : ""}${clip(text.slice(from, to), max)}${to < text.length ? "…" : ""}`;
  };
  return [around(was), around(now)];
}

/** One change in words: what code wrote and what the person left there. */
export function changeWords(c: SavedChange): string {
  const of = c.tag ? `Číslo ${c.tag}` : "Číslo";
  switch (c.kind) {
    case "changed": {
      const [was, now] = clipPair(c.was, c.now);
      return `${of}: ${was} → ${now}`;
    }
    case "removed": return `${of} odstraněno (bylo ${clip(c.was)})`;
    case "added": return `${of} přidáno: ${clip(c.now)}`;
    case "typed": return `Číslo napsané ručně: ${clip(c.now)}${c.paragraph ? ` (v odstavci „${clip(c.paragraph)}“)` : ""}`;
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
  // By name and saved time, never its id (RPT3d, spec Z4).
  const head = `Schvalujete tuto verzi: ${document}, koncept ${v.koncept}, uloženou ${timeWords(v.saved_at)}. ${EXACT}`;
  const edited = editedWords(v);
  if (!edited) return `${head} Je to složená zpráva bez ručních úprav.`;
  const list = v.changes?.changes.length ? ` ${changesListed(v.changes.changes)}.` : "";
  return `${head} ${edited}.${list} Neuložené úpravy v editoru schválení nezahrnuje.`;
}
