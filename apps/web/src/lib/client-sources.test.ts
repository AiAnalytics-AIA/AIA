import { describe, expect, it } from "vitest";

import { cs } from "@/i18n/cs";
import {
  FILE_ACCEPT,
  locatorWords,
  readingLine,
  reasonWords,
  sizeWords,
  sourceIdOf,
  takesFile,
  titleFromFilename,
  withSource,
} from "./client-sources";

const ID = "SRC-0123456789abcdef";

describe("a file on a knowledge item (client-workspace C7a)", () => {
  it("is taken only by the material kinds, as the API allows", () => {
    expect(["DOCUMENT", "SOURCE", "DATASET"].every(takesFile)).toBe(true);
    expect(["FACT", "FINDING", "TERM", "ENTITY", "DIMENSION", "AUDIENCE", "ARTIFACT"].some(takesFile)).toBe(false);
  });

  it("is named by a source's id and nothing else", () => {
    expect(sourceIdOf({ source_id: ID })).toBe(ID);
    for (const bad of [undefined, null, 7, "SRC-XYZ", ` ${ID}`, "../etc"]) expect(sourceIdOf({ source_id: bad })).toBeNull();
    expect(sourceIdOf(null)).toBeNull();
  });

  it("keeps the rest of the content when a file is named, replaced or removed", () => {
    const content = { note: "z brífu", source_id: "SRC-ffffffffffffffff" };
    expect(withSource(content, ID)).toEqual({ note: "z brífu", source_id: ID });
    expect(withSource(content, null)).toEqual({ note: "z brífu" });
    expect(withSource(undefined, ID)).toEqual({ source_id: ID });
  });

  it("titles an item by its file's name as written, without the extension", () => {
    expect(titleFromFilename("Zadání výzkumu 2026.docx")).toBe("Zadání výzkumu 2026");
    expect(titleFromFilename("C:\\data\\odpovědi.final.xlsx")).toBe("odpovědi.final");
    expect(titleFromFilename(".env")).toBe(".env");
  });

  it("offers the owner's formats in the picker", () => {
    for (const s of [".pdf", ".docx", ".doc", ".odt", ".txt", ".md", ".pptx", ".csv", ".xlsx", ".xls", ".ods"]) {
      expect(FILE_ACCEPT.split(",")).toContain(s);
    }
  });

  it("says sizes with a Czech decimal comma", () => {
    expect(sizeWords(512)).toBe("512 B");
    expect(sizeWords(12_800)).toBe("13 kB");
    expect(sizeWords(3_565_158)).toBe("3,4 MB");
  });
});

describe("what reading produced, in words", () => {
  const base = { family: "DOCUMENT" as const, segments: 3, characters: 12_400, reason: null };

  it("says READ only for a complete reading, and counts what was read", () => {
    expect(readingLine({ ...base, outcome: "READ" })).toEqual({ tone: "done", text: "Přečteno: 3 části, 12\u00a0400 znaků" });
    expect(readingLine({ ...base, family: "DATASET", segments: 5, outcome: "READ" }).text).toBe("Přečteno: 5 řádků");
  });

  it("names every other outcome by its reason, never as read", () => {
    expect(readingLine({ ...base, outcome: "PARTIAL", reason: "page_without_text" })).toEqual({
      tone: "you",
      text: "Přečteno jen zčásti (3 části): některé stránky nemají text",
    });
    expect(readingLine({ ...base, outcome: "UNREADABLE", reason: "not_text_media" }).text).toBe("AI tento soubor nepřečte: obrázek nebo video");
    expect(readingLine({ ...base, outcome: "REFUSED", reason: "document_encrypted" }).tone).toBe("fault");
  });

  it("has words for every reason the readers and the upload give", () => {
    const codes = [
      "empty", "too_large", "unsupported_format", "not_base64", "not_text_media", "reader_pending", "no_text",
      "page_without_text", "text_bound", "rows_bound", "sheets_bound", "tables_bound", "document_encrypted",
      "document_malformed", "document_too_many_pages", "document_too_old", "document_zip_bounds",
    ];
    expect(Object.keys(cs.aia.sources.reasons).sort()).toEqual([...codes].sort());
    // A code with no words is shown as the code, never as nothing.
    expect(reasonWords("something_new")).toBe("kód something_new");
  });

  it("places a segment as a reader counts it", () => {
    expect(locatorWords({ page: 2 })).toBe("str. 2");
    expect(locatorWords({ page: 3, table: 1, row: 4 })).toBe("str. 3, tabulka 1, řádek 4");
    expect(locatorWords({ sheet: "Odpovědi", row: 7 })).toBe("list Odpovědi, řádek 7");
    expect(locatorWords({ slide: 5 })).toBe("snímek 5");
  });
});
