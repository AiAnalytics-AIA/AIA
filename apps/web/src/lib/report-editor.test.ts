import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import {
  apiScriptUrl, changesListed, changeWords, editedApprovalQuestion, editedWords, editorMode, type EditorVersionRead, holdsEdit,
  openFailure, problemWords, type SavedChange, savedWords,
} from "./report-editor";

describe("where the editor's script is loaded from", () => {
  it("is the named origin's api.js, whatever path the answer carried", () => {
    expect(apiScriptUrl("https://docs.aia.example.test")).toBe("https://docs.aia.example.test/web-apps/apps/api/documents/api.js");
    expect(apiScriptUrl("https://docs.aia.example.test:8443/elsewhere/?x=1")).toBe(
      "https://docs.aia.example.test:8443/web-apps/apps/api/documents/api.js",
    );
  });

  it("is nothing for an origin that is not https, carries credentials or is not a URL", () => {
    for (const bad of ["http://docs.aia.example.test", "https://u:p@docs.aia.example.test", "javascript:alert(1)", "", "docs"]) {
      expect(apiScriptUrl(bad)).toBeNull();
    }
  });
});

describe("the mode a width opens the editor in", () => {
  it("edits from 768 px and reads below", () => {
    expect(editorMode(1440)).toBe("edit");
    expect(editorMode(768)).toBe("edit");
    expect(editorMode(767)).toBe("view");
    expect(editorMode(390)).toBe("view");
  });
});

describe("what opening the editor answered", () => {
  it("reads 404 as the editor off, said nowhere", () => {
    expect(openFailure(new ApiError(404, "not_found", "No such resource.", null))).toEqual({ kind: "off" });
  });

  it("says a refusal by its code, a 403 and anything else in words", () => {
    expect(openFailure(new ApiError(409, "client_report_not_editable", "", null))).toEqual({
      kind: "said", words: "Klientská zpráva se v editoru neupravuje.",
    });
    expect(openFailure(new ApiError(409, "context_report_not_prepared", "", null)).kind).toBe("said");
    expect(openFailure(new ApiError(403, "forbidden", "", null))).toEqual({ kind: "said", words: "Zprávu v editoru upravovat nemůžete." });
    expect(openFailure(new Error("network")).kind).toBe("said");
    expect(openFailure(new ApiError(500, "http_500", "", null)).kind).toBe("said");
  });
});

describe("why the last save was not stored", () => {
  it("is words for each reason the server keeps, the code itself for one it has no words for, and nothing for none", () => {
    expect(problemWords("document_server_restarted")).toMatch(/restartoval/);
    expect(problemWords("session_closed")).toMatch(/zavřené relace/);
    expect(problemWords("something_new")).toBe("Poslední uložení AIA nepřevzala (something_new).");
    expect(problemWords(null)).toBeNull();
    expect(problemWords(undefined)).toBeNull();
  });
});

const change = (over: Partial<SavedChange>): SavedChange => ({ kind: "changed", tag: "t", was: "1", now: "2", paragraph: null, ...over });
const version = (over: Partial<EditorVersionRead> = {}): EditorVersionRead => ({
  version_artifact_id: "ART-2", line_id: "ART-1", koncept: 2, edited_from: "ART-1", author_names: ["Jana"],
  saved_at: "2026-10-23T20:10:00+00:00", review_state: "DRAFT_UNAPPROVED", approved_on: null, approval: null,
  changes: { uncomparable: null, changes: [change({})] }, newest_in_line: null, ...over,
});

describe("a saved version in words", () => {
  it("names the koncept, the time in Prague and who saved it, an unnamed author as unknown", () => {
    expect(savedWords(version())).toBe("Koncept 2, uložen 23. 10. 2026 22:10 · Jana");
    expect(savedWords(version({ author_names: ["Jana", null] }))).toBe("Koncept 2, uložen 23. 10. 2026 22:10 · Jana, neznámý autor");
    expect(savedWords(version({ koncept: 1, author_names: [] }))).toBe("Koncept 1 (složená zpráva), uložen 23. 10. 2026 22:10");
    expect(savedWords(version({ saved_at: "nevím" }))).toBe("Koncept 2, uložen nevím · Jana");
  });

  it("says each change by its kind, never dropping what was there", () => {
    expect(changeWords(change({ tag: "trust", was: "42,5 %", now: "50 %" }))).toBe("Číslo trust: 42,5 % → 50 %");
    expect(changeWords(change({ kind: "removed", was: "12", now: null }))).toBe("Číslo t odstraněno (bylo 12)");
    expect(changeWords(change({ kind: "added", was: null, now: "7" }))).toBe("Číslo t přidáno: 7");
    expect(changeWords(change({ kind: "typed", tag: null, was: null, now: "33 %", paragraph: "Důvěra roste" })))
      .toBe("Číslo napsané ručně: 33 % (v odstavci „Důvěra roste“)");
  });

  it("ends a long span's text in an ellipsis, never dropping that it changed", () => {
    const long = "Sledovaná sada — varianty — 4 položky hodnocené otázkou „Jak vás oslovuje …?“ na škále 1 až 10.";
    const said = changeWords(change({ tag: "design:a1", was: long, now: `91,5 % ${long}` }));
    expect(said).toMatch(/^Číslo design:a1: Sledovaná sada — .{20,}… → 91,5 % Sledovaná sada .{20,}…$/);
    expect(said.length).toBeLessThan(190);
  });

  it("counts Upraveno ručně, says why nothing compared, and nothing for koncept 1", () => {
    expect(editedWords(version())).toBe("Upraveno ručně: 1 číslo");
    expect(editedWords(version({ changes: { uncomparable: null, changes: [change({}), change({}), change({})] } }))).toBe("Upraveno ručně: 3 čísla");
    expect(editedWords(version({ changes: { uncomparable: null, changes: Array.from({ length: 5 }, () => change({})) } }))).toBe("Upraveno ručně: 5 čísel");
    expect(editedWords(version({ changes: { uncomparable: null, changes: [] } }))).toBe("Upraveno ručně: žádné číslo");
    expect(editedWords(version({ changes: { uncomparable: "no_controls", changes: [] } })))
      .toBe("Upraveno ručně: nelze porovnat (zpráva byla složena dřív, než kód zamykal svá čísla)");
    expect(editedWords(version({ changes: { uncomparable: "new_reason", changes: [] } }))).toBe("Upraveno ručně: nelze porovnat (new_reason)");
    expect(editedWords(version({ changes: null }))).toBeNull();
  });

  it("asks an edited version's approval by name with its changes, the rest counted", () => {
    expect(editedApprovalQuestion(version(), "interní zprávu")).toBe(
      "Schválit interní zprávu, koncept 2 (ART-2)? Upraveno ručně: 1 číslo. Číslo t: 1 → 2. Neuložené úpravy v editoru schválení nezahrnuje.",
    );
    const many = Array.from({ length: 10 }, (_, i) => change({ tag: `n${i}` }));
    expect(changesListed(many, 2)).toBe("Číslo n0: 1 → 2; Číslo n1: 1 → 2; a 8 dalších");
  });
});

describe("whether a stored version holds an edit", () => {
  const at = (iso: string) => Date.parse(iso);
  const version = (content_at: string | null, server_now = "2026-10-24T00:30:00.000Z") =>
    ({ content_at, server_now });

  it("holds an edit its last change is no earlier than, on the server's clock", () => {
    // The browser runs 10 s behind the server: an edit at its 00:29:45 is the server's 00:29:55.
    const sent = at("2026-10-24T00:29:50.000Z");
    expect(holdsEdit(version("2026-10-24T00:29:56.000Z"), at("2026-10-24T00:29:45.000Z"), sent)).toBe(true);
    expect(holdsEdit(version("2026-10-24T00:29:50.000Z"), at("2026-10-24T00:29:45.000Z"), sent)).toBe(false);
  });

  it("never takes a slow answer for clock skew: a snapshot from before the edit holds nothing", () => {
    // Clocks agree. Snapshot at 00:00:00; the edit and the request at 00:00:10, the server answering
    // then; the answer arriving at 00:00:25. Placed by its arrival, the edit would read as 00:29:55.
    const snapshot = version("2026-10-24T00:00:00.000Z", "2026-10-24T00:00:10.000Z");
    expect(holdsEdit(snapshot, at("2026-10-24T00:00:10.000Z"), at("2026-10-24T00:00:10.000Z"))).toBe(false);
  });

  it("allows the second the Document Server reads its time to, no more", () => {
    const now = at("2026-10-24T00:30:00.000Z");
    expect(holdsEdit(version("2026-10-24T00:30:00.000Z"), now + 900, now)).toBe(true);
    expect(holdsEdit(version("2026-10-24T00:30:00.000Z"), now + 1_500, now)).toBe(false);
  });

  it("holds nothing without the Document Server's time, a time that does not parse, or no server time", () => {
    const now = at("2026-10-24T00:30:00.000Z");
    // Stored a second after the edit, yet it says nothing of what it holds: a snapshot taken before.
    expect(holdsEdit(version(null), at("2026-10-24T00:29:58.000Z"), now)).toBe(false);
    expect(holdsEdit(version("včera"), now - 60_000, now)).toBe(false);
    expect(holdsEdit({ content_at: "2026-10-24T00:30:00.000Z" }, now - 60_000, now)).toBe(false);
  });
});
