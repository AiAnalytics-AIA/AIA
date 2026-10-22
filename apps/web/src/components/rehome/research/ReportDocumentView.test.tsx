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

import { StudyFrameProvider } from "./frame";
import { ReportDocumentView } from "./ReportDocumentView";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportDocument: vi.fn(), clientReportDocument: vi.fn(), prepareClientReport: vi.fn() },
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

afterEach(() => {
  cleanup();
  for (const f of [research.reportDocument, research.clientReportDocument, research.prepareClientReport]) vi.mocked(f).mockReset();
});

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

describe("the client report, read here before it is approved (RD3)", () => {
  const modelled = () => ({
    run_id: "RUN-1",
    steps: [
      { node_key: "run", kind: "research_fieldwork", status: "SUCCEEDED", data_origin: "MODELLED_AI_PANEL", data_origin_kind: "MODELLED" },
      { node_key: "report", kind: "research_report", status: "SUCCEEDED", artifact_id: "ART-docx" },
    ],
  }) as unknown as ResearchRun;
  const CLIENT: StoredReportDocument = { ...STORED, report_artifact_id: "ART-client", document: { ...DOC, meta: { ...DOC.meta, kind: "client" } } };

  it("is offered only for a modelled run, one document at a time, and prepared without a download", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(404, "not_found", "Nenalezeno.", null));
    vi.mocked(research.prepareClientReport).mockResolvedValue(CLIENT);
    const { container } = show(modelled());
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    // Not prepared yet: said so, with the one way to read it; nothing leaves.
    const note = await screen.findByText(/ještě není připravená/);
    expect(note).toBeTruthy();
    expect(container.querySelector("article")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Připravit klientskou zprávu" }));
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(research.prepareClientReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1");
    const bar = container.querySelector("[data-report-docbar]")!;
    expect(bar.textContent).toContain("Klientská zpráva");
    expect(bar.textContent).toContain("ART-client");
    // One article on the page: the Lead's report: ids name one document.
    expect(container.querySelectorAll("article")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    await waitFor(() => expect(container.querySelector("[data-report-docbar]")!.textContent).toContain("ART-docx"));
  });

  it("drops a preparation that answers after the person switched back, and closes an open claim on a switch", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(404, "not_found", "Nenalezeno.", null));
    let answer: (v: StoredReportDocument) => void = () => undefined;
    vi.mocked(research.prepareClientReport).mockReturnValue(new Promise((ok) => { answer = ok; }));
    const { container } = show(modelled());
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(container.querySelector("[data-claim]")!);
    expect(container.querySelector("[data-item-inspector]")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    expect(container.querySelector("[data-item-inspector]")).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Připravit klientskou zprávu" }));
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    await waitFor(() => expect(container.querySelector("[data-report-docbar]")?.textContent).toContain("ART-docx"));
    answer(CLIENT);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector("[data-report-docbar]")!.textContent).toContain("ART-docx");
    expect(container.querySelector("[data-report-document]")!.getAttribute("data-report-document")).toBe("ready");
  });

  it("keeps the switch when the client report may not be read", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(403, "forbidden", "Zakázáno.", null));
    show(modelled());
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Klientskou zprávu číst nemůžete.");
    expect(screen.getByRole("button", { name: "Interní zpráva" })).toBeTruthy();
  });

  it("offers no client report for a run that has none", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(screen.queryByRole("button", { name: "Klientská zpráva" })).toBeNull();
    expect(research.clientReportDocument).not.toHaveBeenCalled();
  });

  it("says a refused preparation in its own words", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(404, "not_found", "Nenalezeno.", null));
    vi.mocked(research.prepareClientReport).mockRejectedValue(new ApiError(409, "client_report_refused", "Klientskou zprávu nelze sestavit.", null));
    show(modelled());
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    fireEvent.click(await screen.findByRole("button", { name: "Připravit klientskou zprávu" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Klientskou zprávu nelze sestavit.");
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
