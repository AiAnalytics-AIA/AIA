// @vitest-environment jsdom
// Zpráva's document in the pane (artifact-report RPT2): the stored draft as the serializer wrote it
// (the shared fixture), every chip resolving in its ledger, a suppressed number never shown, the
// claim opened in the inspector, and each state the route answers said in words.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { t } from "@/i18n/t";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, research, type ResearchRun } from "@/lib/api";
import { type ReportDocumentModel, type StoredReportDocument, valueWords } from "@/lib/artifacts/report";
import { parseAiaId } from "@/lib/workbench-artifacts";

import { ItemInspectorContext } from "@/components/workbench/item-inspector-context";
import type { ReactNode } from "react";
import { StudyFrameProvider } from "./frame";
import { ReportDocumentView } from "./ReportDocumentView";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportDocument: vi.fn() },
}));

const DOC = JSON.parse(
  readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/report_document/internal.json"), "utf8"),
) as ReportDocumentModel;

const STORED: StoredReportDocument = {
  run_id: "RUN-1", artifact_id: "ART-doc", sha256: "a".repeat(64), report_artifact_id: "ART-docx",
  report_sha256: "b".repeat(64), review_state: "DRAFT_UNAPPROVED", approved_on: null, stamped: false, document: DOC,
};

const run = (status: string) => ({ run_id: "RUN-1", steps: [{ node_key: "report", kind: "research_report", status, artifact_id: "ART-docx" }] }) as unknown as ResearchRun;

const show = (r: ResearchRun = run("SUCCEEDED")) =>
  render(<StudyFrameProvider frame={TEST_FRAME}><ReportDocumentView run={r} /></StudyFrameProvider>);

afterEach(() => { cleanup(); vi.mocked(research.reportDocument).mockReset(); });

describe("the stored draft in the pane", () => {
  it("renders every section and block with the Lead's ids, in print order", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const sections = [...container.querySelectorAll("section[data-aia]")].map((s) => s.getAttribute("data-aia"));
    expect(sections).toEqual(DOC.sections.map((s) => `report:${s.id}`));
    const blocks = DOC.sections.flatMap((s) => s.blocks.map((b) => `report:${b.id}`));
    for (const id of blocks) expect(container.querySelector(`[data-aia="${id}"]`)).not.toBeNull();
    expect(container.querySelector("[data-unrendered]")).toBeNull(); // every kind in the fixture has a renderer
  });

  it("gives no two elements one id, and points every chip at Zpráva, never Analýza's claim:", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const ids = [...container.querySelectorAll("[data-aia]")].map((e) => e.getAttribute("data-aia")!);
    expect(new Set(ids).size).toBe(ids.length);
    const chips = [...container.querySelectorAll("[data-claim][data-aia]")].map((e) => e.getAttribute("data-aia")!);
    expect(chips.length).toBeGreaterThan(0);
    for (const id of chips) expect(parseAiaId(id)?.stage).toBe("report");
    expect(ids.some((id) => id.startsWith("claim:"))).toBe(false);
  });

  it("prints each number as the DOCX's text, and no suppressed one", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const chips = [...container.querySelectorAll<HTMLElement>("[data-claim]")];
    expect(chips.length).toBeGreaterThan(0);
    for (const chip of chips) {
      const entry = DOC.ledger.refs[chip.dataset.claim!];
      expect(entry).toBeDefined(); // every chip resolves in the ledger
      if (!entry.suppressed) expect([valueWords(entry, false), valueWords(entry, true)]).toContain(chip.textContent);
    }
    // The shared table's suppressed row is gone and counted.
    const shared = DOC.sections.at(-1)!.blocks.find((b) => b.type === "table")!;
    const table = container.querySelector(`[data-aia="report:${shared.id}"]`)!;
    expect(table.textContent).toContain("odstraněno řádků pro nedostatečnou podporu: 1");
    expect(table.textContent).toContain("Kept");
    expect(table.textContent).not.toContain("Malá skupina");
  });

  it("opens a claim in the inspector and closes it", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const chip = container.querySelector<HTMLElement>("[data-claim]")!;
    fireEvent.click(chip);
    const drawer = await screen.findByRole("complementary");
    expect(within(drawer).getByText(/^Hodnota: /)).toBeTruthy();
    fireEvent.click(within(drawer).getByRole("button", { name: /zavřít/i }));
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("inside the workbench opens a claim in the workbench's one item drawer, with its evidence, and draws none of its own", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const opened: { id: string; body?: () => ReactNode }[] = [];
    const inspector = { open: (entry: { id: string }, body?: () => ReactNode) => { opened.push({ id: entry.id, body }); return true; } };
    const { container } = render(
      <StudyFrameProvider frame={TEST_FRAME}><ItemInspectorContext.Provider value={inspector}><ReportDocumentView run={run("SUCCEEDED")} /></ItemInspectorContext.Provider></StudyFrameProvider>,
    );
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const chip = container.querySelector<HTMLElement>("[data-claim]")!;
    fireEvent.click(chip);
    expect(opened.map((o) => o.id)).toEqual([`report:ref:${chip.dataset.claim}`]);
    expect(parseAiaId(opened[0]!.id)?.stage).toBe("report");
    // The body it gives is the claim's evidence, as its own drawer drew it.
    const body = render(<>{opened[0]!.body!()}</>);
    expect(body.getByText(/^Hodnota: /)).toBeTruthy();
    // Its own drawer stays shut: one drawer, under the frame's Escape order.
    expect(within(container).queryByRole("complementary")).toBeNull();
  });

  it("names the DOCX it is beside and that draft's review", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const bar = container.querySelector("[data-report-docbar]")!;
    expect(bar.textContent).toContain("neschváleno");
    expect(bar.textContent).toContain("ART-docx");
  });
});

describe("Záznam pokrytí, outside the text (RPT4)", () => {
  it("lists beside the article what the draft does not hold: the run's gaps and the outputs no section read", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const r = { ...run("SUCCEEDED"), answerability: { rules: "r", capable: false, digest: "d", pending: [],
      gaps: [{ kind: "not_answerable", research_question: "Liší se segmenty?", verdict: "UNANSWERABLE", reasons: ["segments_unavailable"], measures: ["q1"] }] } } as ResearchRun;
    const { container } = show(r);
    const record = await screen.findByRole("region", { name: /Záznam pokrytí/ });
    // Outside the article: never part of the document's text.
    expect(container.querySelector("article")!.contains(record)).toBe(false);
    expect(record.textContent).toContain("Segmenty: neprovedeno");
    // The shared fixture's manifest: its unread outputs, by words.
    expect(DOC.unread?.length).toBe(2);
    expect(record.textContent).toContain(`${t("research.exec.steps.aggregate")}: uloženo, žádná kapitola z něj nečte`);
    expect(record.textContent).toContain("Zpráva Sociomappingu (interní koncept): uloženo, žádná kapitola z něj nečte");
  });
});

describe("who approved it (RD2)", () => {
  it("names the approver on the doc bar, and nothing for a draft", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue({
      ...STORED, review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22",
      approval: { approved_at: "2026-10-21T23:30:00+00:00", approver_name: "Fiktivní Recenzentka", by_you: false, self_approved: false, self_approval_allowed: true, self_approval_source: "default", note: "" },
    });
    const approved = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(approved.container.querySelector("[data-approval]")?.textContent).toBe("· schválil(a) Fiktivní Recenzentka 22. 10. 2026");
    cleanup();
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const draft = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(draft.container.querySelector("[data-approval]")).toBeNull();
  });
});

describe("what the route answers, in words", () => {
  it("shows nothing until the report step succeeded, and never asks", () => {
    const { container } = show(run("RUNNING"));
    expect(container.textContent).toBe("");
    expect(research.reportDocument).not.toHaveBeenCalled();
  });

  it("says a report composed before its document was stored", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    const { container } = show();
    await waitFor(() => expect(container.querySelector('[data-report-document="not_stored"]')).not.toBeNull());
  });

  it("refuses a document not beside its DOCX, or of another contract", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(409, "report_artifact_invalid", "", null));
    const first = show();
    await waitFor(() => expect(first.container.querySelector('[data-report-document="refused"]')).not.toBeNull());
    cleanup();
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, document: { ...DOC, contract: "aia-report-document-0" } as unknown as ReportDocumentModel });
    const second = show();
    await waitFor(() => expect(second.container.querySelector('[data-report-document="refused"]')).not.toBeNull());
  });

  it("shows nothing to a reader the internal draft is not for", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(403, "forbidden", "", null));
    const { container } = show();
    await waitFor(() => expect(container.textContent).toBe(""));
  });
});
