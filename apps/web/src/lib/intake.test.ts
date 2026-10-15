import { describe, expect, it } from "vitest";

import type { SourceAdded, SourceDetail } from "@/lib/api";
import {
  type Entry,
  action,
  addable,
  alreadyKept,
  badge,
  changed,
  detailFailed,
  failed,
  folderOf,
  itemsFor,
  kindOfName,
  newEntry,
  pastedFile,
  personalColumns,
  placementsFor,
  removed,
  retryable,
  retrying,
  rowLine,
  stored,
  summary,
  withDetail,
} from "./intake";

const src = (id: string, extra: Partial<SourceAdded> = {}): SourceAdded => ({
  source_id: id,
  sha256: "a".repeat(64),
  size_bytes: 1000,
  media_type: "application/pdf",
  family: "DOCUMENT",
  filename: "x.pdf",
  outcome: "READ",
  reason: null,
  reader: "pdf/1",
  characters: 38_200,
  segments: 14,
  occurrences: [{ occurrence_id: "SOC-1", filename: "x.pdf", origin: "upload", added_by: "USR-1", added_at: "2026-10-14T08:00:00Z" }],
  created_at: "2026-10-14T08:00:00Z",
  created: true,
  ...extra,
});
const A = "SRC-aaaaaaaaaaaaaaaa";
const B = "SRC-bbbbbbbbbbbbbbbb";

const batch = (...names: string[]): Entry[] => names.map((n, i) => newEntry({ name: n, size: 1000 }, `k${i}`));

describe("a batch of files on the intake sheet (client-workspace C7b)", () => {
  it("guesses from the name what each file will be, and titles it by its name as written", () => {
    expect(["brief.pdf", "data.xlsx", "x.CSV", "foto.png", "spot.mov", "notes.md"].map(kindOfName)).toEqual([
      "DOCUMENT", "DATASET", "DATASET", "SOURCE", "SOURCE", "DOCUMENT",
    ]);
    expect(newEntry({ name: "Zadání výzkumu.docx", size: 1 }, "k").title).toBe("Zadání výzkumu");
    expect(badge("a.pdf")).toEqual({ label: "PDF", tone: "pdf" });
    expect(badge("README")).toEqual({ label: "?", tone: "plain" });
  });

  it("waits while a file reads and says so in words, never a percentage", () => {
    const e = batch("brief.pdf");
    expect(rowLine(e, e[0]).text).toBe("Ukládám a čtu…");
    expect(action(e)).toEqual({ label: "Čeká se na čtení…", disabled: true });
    expect(summary(e)).toBe("Zatím není co přidat. Ještě se čte 1 soubor; tlačítko počká.");
  });

  it("says what reading produced for each kept file", () => {
    let e = batch("brief.pdf", "foto.png", "smlouva.pdf", "bad.key");
    e = stored(e, "k0", src(A));
    e = stored(e, "k1", src(B, { family: "IMAGE", outcome: "UNREADABLE", reason: "not_text_media", segments: 0, characters: 0 }));
    e = stored(e, "k2", src("SRC-cccccccccccccccc", { outcome: "REFUSED", reason: "document_encrypted", segments: 0, characters: 0 }));
    e = failed(e, "k3", "Soubor nelze přečíst: tento formát AIA nepřijímá");
    expect(e.map((x) => rowLine(e, x).text)).toEqual([
      "Přečteno: 14 částí, 38 200 znaků",
      "Uloží se bez textu · AI obrázek ani video nečte",
      "soubor je chráněn heslem · uloží se, ale AI ho nepřečte",
      "Soubor nelze přečíst: tento formát AIA nepřijímá",
    ]);
    expect(e.map((x) => x.kind)).toEqual(["DOCUMENT", "SOURCE", "DOCUMENT", "DOCUMENT"]);
    expect(summary(e)).toBe("Přidá se 2 dokumenty, 1 zdroj bez textu. 1 soubor nelze přidat.");
    expect(action(e)).toEqual({ label: "Přidat 3 podklady", disabled: false });
  });

  it("adds the same bytes once, and names a file the client already had", () => {
    let e = batch("a.pdf", "kopie-a.pdf");
    e = stored(e, "k0", src(A));
    e = stored(e, "k1", src(A, { created: false }));
    expect(e[1].duplicateOf).toBe("k0");
    expect(rowLine(e, e[1]).text).toBe("Stejný soubor jako a.pdf výše; přidá se jen jednou.");
    expect(addable(e).map((x) => x.key)).toEqual(["k0"]);
    // Removing the first leaves the second standing on its own.
    expect(removed(e, "k0").map((x) => [x.key, x.duplicateOf])).toEqual([["k1", null]]);

    const old = stored(batch("brief.pdf"), "k0", src(A, {
      created: false,
      occurrences: [
        { occurrence_id: "SOC-2", filename: "brief.pdf", origin: "upload", added_by: null, added_at: "2026-10-14T08:00:00Z" },
        { occurrence_id: "SOC-1", filename: "brief_final.pdf", origin: "upload", added_by: null, added_at: null },
      ],
    }));
    expect(alreadyKept(old[0])).toContain("jako brief_final.pdf");
    expect(alreadyKept(stored(batch("n.pdf"), "k0", src(A))[0])).toBeNull();
  });

  it("asks a table to be a dataset or a document, and names its personal columns", () => {
    let e = stored(batch("odpovedi.xlsx"), "k0", src(A, { family: "DATASET", segments: 5 }));
    expect(e[0].kind).toBe("DATASET");
    // Kept, but it reads until its columns are in: never saved before its warning can show.
    expect(rowLine(e, e[0]).text).toBe("Ukládám a čtu…");
    expect(action(e).disabled).toBe(true);
    const detail = {
      ...src(A, { family: "DATASET" }),
      reading: {
        outcome: "READ", reader: "xlsx/1", reason: null, segments: [], notes: [],
        dataset: {
          more_sheets: false,
          sheets: [{ name: "Odpovědi", header_row: 1, rows: 4, truncated: false, columns: [
            { index: 0, letter: "A", header: "Věk", kind: "NUMBER", filled: 4, distinct: 4, distinct_capped: false, personal: null, sample: ["34"] },
            { index: 1, letter: "B", header: "E-mail", kind: "TEXT", filled: 4, distinct: 4, distinct_capped: false, personal: "email_header", sample: [] },
          ] }],
        },
      },
    } as SourceDetail;
    e = withDetail(e, "k0", detail);
    expect(rowLine(e, e[0]).text).toBe("Přečteno: 1 list, 2 sloupce, 4 řádky");
    expect(personalColumns(detail)).toEqual(["E-mail"]);
    e = changed(e, "k0", { kind: "DOCUMENT" });
    expect(summary(e)).toBe("Přidá se 1 dokument.");
  });

  it("holds a table whose columns did not come back, until a retry reads them", () => {
    let e = stored(batch("odpovedi.xlsx"), "k0", src(A, { family: "DATASET" }));
    e = detailFailed(e, "k0", "Sloupce se nenačetly.");
    expect(retryable(e[0])).toBe(true);
    expect(rowLine(e, e[0])).toEqual({ tone: "fault", text: "Sloupce se nenačetly." });
    expect(addable(e)).toEqual([]);
    expect(summary(e)).toBe("Zatím není co přidat. 1 soubor nelze přidat.");
    e = retrying(e, "k0");
    expect(action(e)).toEqual({ label: "Čeká se na čtení…", disabled: true });
    // A file AIA refused has nothing to retry.
    expect(retryable(failed(batch("x.key"), "k0", "ne")[0])).toBe(false);
  });

  it("finishes the filing of items already made, and makes none of them twice", () => {
    expect(action([], true)).toEqual({ label: "Dokončit zařazení", disabled: false });
    expect(action([], false)).toEqual({ label: "Přidat 0 podkladů", disabled: true });
  });

  it("makes one item per file naming its source, with the title as edited", () => {
    let e = batch("a.pdf", "b.xlsx");
    e = stored(e, "k0", src(A));
    e = stored(e, "k1", src(B, { family: "DATASET" }));
    e = withDetail(e, "k1", { ...src(B, { family: "DATASET" }), reading: { outcome: "READ", reader: "xlsx/1", reason: null, segments: [], notes: [], dataset: null } } as SourceDetail);
    e = changed(e, "k0", { title: "  Brand tracking 2025 " });
    e = changed(e, "k1", { title: "" });
    expect(itemsFor(e)).toEqual([
      { key: "k0", kind: "DOCUMENT", title: "Brand tracking 2025", content: { source_id: A } },
      { key: "k1", kind: "DATASET", title: "b", content: { source_id: B } },
    ]);
  });

  it("files the new items: one placement per folder, the batch's labels once", () => {
    let e = batch("a.pdf", "b.pdf", "c.pdf");
    e = changed(e, "k1", { folder: "KNF-2" });
    e = changed(e, "k2", { folder: null });
    expect(e.map((x) => folderOf(x, "KNF-1"))).toEqual(["KNF-1", "KNF-2", null]);
    const created = e.map((x, i) => ({ itemId: `KNW-${i}`, folder: folderOf(x, "KNF-1") }));
    expect(placementsFor(created, ["KNL-1"])).toEqual([
      { item_ids: ["KNW-0"], folder_id: "KNF-1" },
      { item_ids: ["KNW-1"], folder_id: "KNF-2" },
      { item_ids: ["KNW-0", "KNW-1", "KNW-2"], add_labels: ["KNL-1"] },
    ]);
    // No folder and no labels: nothing to file.
    expect(placementsFor(batch("a", "b", "c").map((x, i) => ({ itemId: `KNW-${i}`, folder: folderOf(x, null) })), [])).toEqual([]);
  });

  it("keeps pasted text as a text file under the name given", () => {
    expect(pastedFile("Poznámky z briefingu", "Text.").name).toBe("Poznámky z briefingu.txt");
    expect(pastedFile("zapis.md", "x").name).toBe("zapis.md");
    expect(pastedFile("  ", "x").name).toBe("Vložený text.txt");
  });
});
