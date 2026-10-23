import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { apiScriptUrl, editorMode, openFailure, problemWords } from "./report-editor";

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
