import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import {
  documentKeyOf, newPageId, unsavedWords, UNSTORED,
  apiScriptUrl, changesListed, changeWords, editedApprovalQuestion, editedWords, editorMode, type EditorVersionRead,
  openFailure, problemWords, type SavedChange, savedWords, scriptIntegrity,
} from "./report-editor";

describe("where the editor's script is loaded from", () => {
  const DOCS = "https://docs.aia.example.test";
  const ticket = `${DOCS}/__aia/session?ticket=t.k`;

  it("is api.js through the ticket's session path on the named origin, whatever path the answer carried", () => {
    const url = new URL(apiScriptUrl(DOCS, ticket)!);
    expect(url.origin).toBe(DOCS);
    expect(url.pathname).toBe("/__aia/session");
    expect(url.searchParams.get("ticket")).toBe("t.k");
    expect(url.searchParams.get("next")).toBe("/web-apps/apps/api/documents/api.js");
    expect(apiScriptUrl(`${DOCS}/elsewhere/?x=1`, ticket)).toBe(url.href);
  });

  it("is nothing for an origin that is not https, carries credentials or is not a URL", () => {
    for (const bad of ["http://docs.aia.example.test", "https://u:p@docs.aia.example.test", "javascript:alert(1)", "", "docs"]) {
      expect(apiScriptUrl(bad, ticket)).toBeNull();
    }
  });

  it("is nothing for a ticket spent anywhere but the named origin's session path, or naming its own next", () => {
    for (const bad of [
      "https://evil.example.test/__aia/session?ticket=t.k",
      `${DOCS}/web-apps/apps/api/documents/api.js?ticket=t.k`,
      `${DOCS}/__aia/session`,
      `${DOCS}/__aia/session?ticket=t.k&next=/elsewhere.js`,
      "http://docs.aia.example.test/__aia/session?ticket=t.k",
    ]) {
      expect(apiScriptUrl(DOCS, bad)).toBeNull();
    }
  });
});

describe("the integrity api.js must match (RPT8e)", () => {
  it("is one SHA-384 digest or nothing", () => {
    const good = `sha384-${"A".repeat(64)}`; // 48 bytes are 64 base64 characters, no padding
    expect(scriptIntegrity(good)).toBe(good);
    for (const bad of [undefined, "", `sha256-${"A".repeat(43)}=`, `sha384-${"A".repeat(63)}`, `${good}=`, `${good} ${good}`]) {
      expect(scriptIntegrity(bad)).toBeNull();
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
    // The difference is at the start: each side shows it with its context, the rest cut.
    expect(said).toMatch(/^Číslo design:a1: Sledovaná sada — .{5,}… → 91,5 % Sledovaná sada.{5,}…$/);
    expect(said.length).toBeLessThan(190);
  });

  it("keeps the difference in view when it lies past the cut", () => {
    const long = "Sledovaná sada — varianty — 4 položky hodnocené otázkou „Jak vás oslovuje …?“ na škále 1 až 10.";
    const said = changeWords(change({ tag: "design:a1", was: long, now: long.replace("1 až 10.", "1 až 100.") }));
    const [was, now] = said.replace("Číslo design:a1: ", "").split(" → ");
    expect(was).not.toBe(now);
    expect(was).toMatch(/1 až 10\.$/);
    expect(now).toMatch(/1 až 100\.$/);
    expect(was.startsWith("…")).toBe(true);
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

describe("the edit sequence (RPT8f)", () => {
  it("gives a page an id within the server's grammar, a new one each time", () => {
    const a = newPageId();
    expect(a).toMatch(/^[0-9A-Za-z_-]{8,64}$/);
    expect(newPageId()).not.toBe(a);
  });

  it("reads the session's key from the signed config, or none", () => {
    expect(documentKeyOf({ document: { key: "ART-1.aa.1" } })).toBe("ART-1.aa.1");
    expect(documentKeyOf({ document: {} })).toBeNull();
    expect(documentKeyOf({})).toBeNull();
  });

  it("says why the server held an approval, and nothing for another refusal", () => {
    const held = (reason: string) => new ApiError(409, "report_edits_unsaved", "…", null, { reason });
    expect(unsavedWords(held("edit_not_saved"))).toBe(`${UNSTORED} Neuloží-li editor koncept sám, uložte ho v editoru (Ctrl+S).`);
    expect(unsavedWords(held("edit_not_received"))).toMatch(/nedorazila do AIA/);
    expect(unsavedWords(new ApiError(409, "report_version_stale", "…", null, {}))).toBeNull();
    expect(unsavedWords(new Error("x"))).toBeNull();
  });
});
