// The stored document model as the pane reads it (artifact-report RPT1). The fixture is the Python
// serializer's own output (packages/aia_core/tests/test_report_document_model.py
// test_the_web_reads_the_document_model_this_writes), so the two read one form.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { parseAiaId } from "@/lib/workbench-artifacts";

import {
  approvalWords, blockTarget, claimLines, claimTarget, gradeWords, readDocument, reviewWords, sectionTarget, warningsWords,
  supportWords, unresolvedRefs, valueWords, type LedgerEntry, type ReportDocumentModel,
} from "./report";

const FIXTURE = JSON.parse(
  readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/report_document/internal.json"), "utf8"),
) as unknown;

const doc = readDocument(FIXTURE) as ReportDocumentModel;

describe("readDocument", () => {
  it("reads the serializer's document", () => {
    expect(doc).not.toBeNull();
    expect(doc.meta.kind).toBe("internal");
    expect(doc.sections.at(-1)?.id).toBe("ch-shared");
  });

  it("reads -2 and -3, which only add sources and unread (CHN1) and each entry's level (RD0)", () => {
    expect(readDocument({ ...(FIXTURE as object), contract: "aia-report-document-2", unread: [] })).not.toBeNull();
    expect(readDocument({ ...(FIXTURE as object), contract: "aia-report-document-3", unread: [] })).not.toBeNull();
  });

  it("refuses another contract, never reading it in part", () => {
    expect(readDocument({ ...(FIXTURE as object), contract: "aia-report-document-0" })).toBeNull();
    expect(readDocument({ ...(FIXTURE as object), contract: "aia-report-document-7" })).toBeNull();
    expect(readDocument({ ...(FIXTURE as object), sections: undefined })).toBeNull();
    expect(readDocument(null)).toBeNull();
    expect(readDocument("text")).toBeNull();
  });
});

describe("pointing", () => {
  it("names every section and block in the Lead's grammar, each on Zpráva", () => {
    for (const section of doc.sections) {
      expect(parseAiaId(sectionTarget(section))).toEqual({ kind: "report", id: section.id, stage: "report" });
      for (const block of section.blocks) {
        expect(block.id.startsWith(`${section.id}.`)).toBe(true);
        expect(parseAiaId(blockTarget(block))?.stage).toBe("report");
      }
    }
  });

  it("names a number in its block, in the report's kind, never Analýza's claim:", () => {
    const block = { id: "ch-1.2" };
    expect(claimTarget(block, "trust_praha")).toBe("report:ch-1.2:trust_praha");
    expect(parseAiaId(claimTarget(block, "trust_praha")!)).toEqual({ kind: "report", id: "ch-1.2:trust_praha", stage: "report" });
    expect(claimTarget(block, "q3.pct.Spíše ano")).toBeNull();
  });
});

describe("reading a ref", () => {
  const entries = doc.ledger.refs;
  const admitted = Object.values(entries).find((e): e is Extract<LedgerEntry, { suppressed: false }> => !e.suppressed && e.interval_text !== null)!;
  const suppressed = Object.values(entries).find((e) => e.suppressed)!;

  it("prints the stored text, with the interval only where it is asked", () => {
    expect(valueWords(admitted, false)).toBe(admitted.value_text);
    expect(valueWords(admitted, true)).toBe(`${admitted.value_text} ${admitted.interval_text}`);
  });

  it("never prints a number for a suppressed or an unknown ref", () => {
    expect(valueWords(suppressed, true)).toBe("potlačeno");
    expect(valueWords(undefined, true)).toBe("?");
    expect(claimLines(undefined)).toEqual(["Zpráva toto číslo nemá; nic se netiskne."]);
    expect(claimLines(suppressed)[0]).toBe("Potlačeno: zpráva ho netiskne.");
  });

  it("reads an unknown grade or support as unknown, never as good", () => {
    expect(gradeWords("measured")).toBe("měřeno");
    expect(gradeWords("something-new")).toBe("neznámý stupeň");
    expect(supportWords("REPORTABLE")).toBe("dostatečná");
    expect(supportWords("")).toBe("neznámá");
  });

  it("labels a modelled ref as the DOCX does", () => {
    const modelled = Object.values(entries).find((e) => !e.suppressed && e.modelled_panel);
    if (modelled) expect(claimLines(modelled)).toContain("modelováno: AI respondenti z populace");
  });
});

describe("the document's refs", () => {
  it("every cited ref resolves in its ledger", () => {
    expect(unresolvedRefs(doc)).toEqual([]);
  });

  it("names a ref the ledger lacks", () => {
    const [first, ...rest] = doc.sections;
    const broken = { ...doc, sections: [{ ...first, refs: [...first.refs, "missing_ref"] }, ...rest] };
    expect(unresolvedRefs(broken)).toEqual(["missing_ref"]);
  });

  it("holds no suppressed row in a table, and counts it as the DOCX does", () => {
    const table = doc.sections.at(-1)!.blocks.find((b) => b.type === "table");
    expect(table?.type === "table" && table.suppressed_rows).toBe(1);
    expect(table?.type === "table" && table.rows.length).toBe(1);
  });
});

it("names the DOCX's review", () => {
  expect(reviewWords({ review_state: "DRAFT_UNAPPROVED" })).toBe("neschváleno");
  expect(reviewWords({ review_state: "APPROVED_INTERNAL" })).toBe("interně schváleno");
  // One stored state, the client's words for the client report (RPT3a).
  expect(reviewWords({ review_state: "APPROVED_INTERNAL" }, "client")).toBe("schváleno k předání klientovi");
  expect(reviewWords({ review_state: "DRAFT_UNAPPROVED" }, "client")).toBe("neschváleno");
});

describe("who approved, in words (RD2)", () => {
  const base = {
    approved_at: "2026-10-21T23:30:00+00:00", approver_name: "Fiktivní Recenzentka", by_you: false,
    self_approved: false, self_approval_allowed: true, self_approval_source: "default", note: "",
  };

  it("names the approver and the server's day, never one the browser works out", () => {
    // 23:30 UTC is 22. 10. in Prague; the server's approved_on says so, and it is the one used.
    expect(approvalWords(base, "2026-10-22")).toBe("schválil(a) Fiktivní Recenzentka 22. 10. 2026");
    expect(approvalWords(base, null)).toBe("schválil(a) Fiktivní Recenzentka neznámého dne");
  });

  it("speaks to the asker, names no one without a name, and says one's own work", () => {
    expect(approvalWords({ ...base, by_you: true }, "2026-10-22")).toBe("schválili jste 22. 10. 2026");
    expect(approvalWords({ ...base, approver_name: null }, "2026-10-22")).toBe("schválil(a) člen bez jména 22. 10. 2026");
    expect(approvalWords({ ...base, self_approved: true }, "2026-10-22")).toBe("schválil(a) Fiktivní Recenzentka 22. 10. 2026 · vlastní práce");
  });

  it("says an approval that went past the client checks' warnings, and none when it went past none", () => {
    const warned = { ...base, warnings: [{ code: "drill_down_content", where: "v.1", message: "doslovná odpověď" }] };
    expect(approvalWords(warned, "2026-10-24")).toBe("schválil(a) Fiktivní Recenzentka 24. 10. 2026 přes 1 upozornění");
    expect(approvalWords({ ...base, warnings: [] }, "2026-10-24")).toBe("schválil(a) Fiktivní Recenzentka 24. 10. 2026");
    expect(approvalWords({ ...base, warnings: null }, "2026-10-24")).toBe("schválil(a) Fiktivní Recenzentka 24. 10. 2026");
  });

  it("names where each warning is in words, and says nothing for none or none read", () => {
    expect(warningsWords([{ code: "gate_unrecorded", where: "report", message: "verze nemá uložený dokument, nelze ji ověřit" }]))
      .toBe("Upozornění (1): verze nemá uložený dokument, nelze ji ověřit (celá zpráva). Schválením je berete na vědomí; zaznamenají se se schválením.");
    const document = { sections: [{ id: "ch-a", title: "Shrnutí", appendix: false, refs: [], blocks: [{ id: "ch-a.1" }] }] } as never;
    expect(warningsWords([
      { code: "unadmitted_number", where: "evidence", message: "čísla nejsou pro klienta" },
      { code: "drill_down_content", where: "ch-a.1", message: "doslovná odpověď" },
      { code: "drill_down_content", where: "ch-z.9", message: "doslovná odpověď" },
    ], document)).toBe(
      "Upozornění (3): čísla nejsou pro klienta (čísla zprávy); doslovná odpověď (oddíl „Shrnutí“); doslovná odpověď (blok ch-z.9). "
      + "Schválením je berete na vědomí; zaznamenají se se schválením.",
    );
    expect(warningsWords([])).toBeNull();
    expect(warningsWords(undefined)).toBeNull();
  });

  it("says nothing for a draft", () => {
    expect(approvalWords(null, null)).toBeNull();
    expect(approvalWords(undefined, "2026-10-22")).toBeNull();
  });
});
