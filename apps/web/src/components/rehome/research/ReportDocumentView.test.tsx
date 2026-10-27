// @vitest-environment jsdom
// Zpráva's document in the pane (artifact-report RPT2): the stored draft as the serializer wrote it
// (the shared fixture), every chip resolving in its ledger, a suppressed number never shown, the
// claim opened in the inspector, and each state the route answers said in words.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { t } from "@/i18n/t";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, deepResearch, research, type ResearchRun } from "@/lib/api";
import { type ReportDocumentModel, type StoredReportDocument, valueWords } from "@/lib/artifacts/report";
import { parseAiaId } from "@/lib/workbench-artifacts";
import { saveBlob } from "@/lib/download";

import { ItemInspectorContext } from "@/components/workbench/item-inspector-context";
import type { ReactNode } from "react";
import { StudyFrameProvider } from "./frame";
import { ReportDocumentView } from "./ReportDocumentView";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/download", () => ({ saveBlob: vi.fn() }));
vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportDocument: vi.fn(), clientReportDocument: vi.fn(), prepareClientReport: vi.fn(), approveReport: vi.fn(), report: vi.fn(), openReportEditor: vi.fn(), downloadReport: vi.fn(), downloadClientReport: vi.fn() },
  deepResearch: { runs: vi.fn(), contextReport: vi.fn(), contextReportDocument: vi.fn(), prepareContextReport: vi.fn() },
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

// The run's report as the pane reads it when the internal draft's approval is asked: the version
// it names and its PDF.
beforeEach(() => {
  // No literature review by default: the pane offers the reports a run has.
  vi.mocked(deepResearch.runs).mockResolvedValue([]);
  vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-docx", pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never);
  vi.mocked(deepResearch.contextReport).mockResolvedValue({ state: "READY", artifact_id: "ART-context", pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never);
  // The report editor off (AIA_ONLYOFFICE_URL unset, the default): the read-only draft is the pane.
  vi.mocked(research.openReportEditor).mockRejectedValue(new ApiError(404, "not_found", "No such resource.", null));
});

afterEach(() => {
  cleanup();
  for (const f of [research.reportDocument, research.clientReportDocument, research.prepareClientReport, research.approveReport, research.report, research.openReportEditor,
    research.downloadReport, research.downloadClientReport, saveBlob, deepResearch.runs, deepResearch.contextReport, deepResearch.contextReportDocument, deepResearch.prepareContextReport]) vi.mocked(f).mockReset();
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

  it("inside the workbench opens a claim in the workbench's one item drawer, with its evidence, and draws none of its own", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const opened: { id: string; body?: () => ReactNode }[] = [];
    const inspector = { open: (entry: { id: string }, body?: () => ReactNode) => { opened.push({ id: entry.id, body }); return true; }, closeWhere: vi.fn() };
    const { container } = render(
      <StudyFrameProvider frame={TEST_FRAME}><ItemInspectorContext.Provider value={inspector}><ReportDocumentView run={run("SUCCEEDED")} /></ItemInspectorContext.Provider></StudyFrameProvider>,
    );
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const chip = container.querySelector<HTMLElement>("[data-claim]")!;
    fireEvent.click(chip);
    expect(opened.map((o) => o.id)).toEqual([`report:ref:internal:${chip.dataset.claim}`]);
    expect(parseAiaId(opened[0]!.id)?.stage).toBe("report");
    // The body it gives is the claim's evidence, as its own drawer drew it.
    const body = render(<>{opened[0]!.body!()}</>);
    expect(body.getByText(/^Hodnota: /)).toBeTruthy();
    // Its own drawer stays shut: one drawer, under the frame's Escape order.
    expect(within(container).queryByRole("complementary")).toBeNull();
  });

  it("lets every source line break anywhere, so a SHA-256 never widens a phone's page", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const sources = [...container.querySelectorAll("p")].filter((p) => p.textContent?.startsWith("Zdroj:"));
    expect(sources.length).toBeGreaterThan(0);
    for (const p of sources) expect(p.className).toContain("[overflow-wrap:anywhere]");
  });

  it("names the DOCX it is beside and that draft's review, the review in words", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const bar = container.querySelector("[data-report-docbar]")!;
    expect(bar.textContent).toContain("neschváleno");
    expect(bar.getAttribute("data-report-version")).toBe("ART-docx");
  });

  it("carries the document's exports in its doc bar, beside its review (RPT3c)", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const bar = container.querySelector("[data-report-docbar]") as HTMLElement;
    expect(within(bar).getByRole("button", { name: /Stáhnout DOCX/ })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: /Stáhnout PDF/ })).toBeTruthy();
  });

  it("shows no run id, artifact id or review code anywhere on the stage (RPT12)", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22" });
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    const text = container.textContent ?? "";
    for (const id of ["RUN-", "ART-", "APPROVED_INTERNAL", "DRAFT_UNAPPROVED"]) expect(text).not.toContain(id);
    expect(container.querySelector("[data-report-foot]")!.textContent).toContain("interně schváleno");
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

describe("approved on the document being read, in the doc bar (RPT3a)", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
  });

  const modelled = {
    run_id: "RUN-1",
    steps: [
      { node_key: "run", kind: "research_fieldwork", status: "SUCCEEDED", data_origin: "MODELLED_AI_PANEL", data_origin_kind: "MODELLED" },
      { node_key: "report", kind: "research_report", status: "SUCCEEDED", artifact_id: "ART-docx" },
    ],
  } as unknown as ResearchRun;
  const CLIENT: StoredReportDocument = { ...STORED, report_artifact_id: "ART-client", stored_at: "2026-10-21T13:12:00Z", document: { ...DOC, meta: { ...DOC.meta, kind: "client" } } };
  const APPROVE = "Schválit k předání klientovi";
  const bar = (c: HTMLElement) => c.querySelector("[data-report-docbar]") as HTMLElement;
  const openClient = async (frame = TEST_FRAME) => {
    const view = render(<StudyFrameProvider frame={frame}><ReportDocumentView run={modelled} /></StudyFrameProvider>);
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    await waitFor(() => expect(bar(view.container).getAttribute("data-report-version")).toBe("ART-client"));
    return view.container;
  };

  it("asks by the version's name and what its file carries, approves that version once, tells the card, and keeps the document on screen", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockResolvedValue({ ...CLIENT, stamped: true });
    let answer: (v: unknown) => void = () => undefined;
    vi.mocked(research.approveReport).mockReturnValue(new Promise((ok) => { answer = ok; }) as never);
    const container = await openClient();
    const article = container.querySelector("article");
    fireEvent.click(within(bar(container)).getByRole("button", { name: APPROVE }));
    const dialog = container.querySelector("dialog[open]") as HTMLElement;
    // By name and when it was stored, never its id; the numbers said modelled (RPT3d, spec Z4).
    expect(dialog.textContent).toContain("Schvalujete tuto verzi: Klientská zpráva, vytvořenou 21. 10. 2026 15:12 (DOCX).");
    expect(dialog.textContent).toContain("stáhnete přesně tuto verzi");
    expect(dialog.textContent).toContain("Čísla jsou modelovaná");
    expect(dialog.textContent).not.toContain("ART-");
    expect(dialog.textContent).toContain("„KONCEPT — NESCHVÁLENO“");
    // Zrušit approves nothing.
    fireEvent.click(within(dialog).getByRole("button", { name: "Zrušit" }));
    expect(research.approveReport).not.toHaveBeenCalled();
    fireEvent.click(within(bar(container)).getByRole("button", { name: APPROVE }));
    fireEvent.click(within(container.querySelector("dialog[open]") as HTMLElement).getByRole("button", { name: "Schválit" }));
    // In flight: the same version cannot be asked about and sent twice.
    await waitFor(() => expect((within(bar(container)).getByRole("button", { name: APPROVE }) as HTMLButtonElement).disabled).toBe(true));
    answer({ artifact_id: "ART-client", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22", stamped: true, approval: null });
    await waitFor(() => expect(bar(container).textContent).toContain("schváleno k předání klientovi"));
    expect(research.approveReport).toHaveBeenCalledTimes(1);
    expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-client");
    // The server's answer, in place: the same article, no second read, no second approval offered.
    await waitFor(() => expect(within(bar(container)).queryByRole("button", { name: APPROVE })).toBeNull());
    expect(container.querySelector("article")).toBe(article);
    expect(bar(container).textContent).toContain("schváleno k předání klientovi");
    expect(bar(container).textContent).not.toContain("interně");
    expect(research.clientReportDocument).toHaveBeenCalledTimes(1);
  });

  it("names the client checks' warnings in the question and approves past them (RD0, warnings since 2026-10-22)", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const warnings = [{ code: "drill_down_content", where: "ch-summary.2", message: "doslovná odpověď jednoho respondenta" }];
    vi.mocked(research.clientReportDocument).mockResolvedValue({ ...CLIENT, warnings });
    vi.mocked(research.approveReport).mockResolvedValue({ artifact_id: "ART-client", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-24", stamped: true, approval: null } as never);
    const container = await openClient();
    fireEvent.click(within(bar(container)).getByRole("button", { name: APPROVE }));
    const dialog = container.querySelector("dialog[open]") as HTMLElement;
    expect(dialog.textContent).toContain("Upozornění (1): doslovná odpověď jednoho respondenta (oddíl „Shrnutí pro vedení“). Schválením je berete na vědomí");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-client"));
  });

  it("marks a sentence that compares with no number where it stands, names it in the question and approves past it (RD7)", async () => {
    const sentence = "Nejvíc důvěřují lidé v Praze, nejméně v Ostravě; rozdíl je dost velký na to, aby rozhodl o tom, kde začít.";
    const elsewhere = "Věta, kterou žádný úsek textu neobsahuje celou.";
    const mark = (where: string, text: string, n: number) => ({ code: "unsupported_comparison", where, message: `srovnání bez doloženého čísla: „${text}“`, sentence: n, text });
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, warnings: [mark("ch-summary.1", sentence, 1), mark("ch-confidence.1", elsewhere, 0)] });
    vi.mocked(research.approveReport).mockResolvedValue({ artifact_id: "ART-docx", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-24", stamped: false, approval: null } as never);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    // In place, inside its paragraph, every other word of it kept and unmarked.
    const marked = container.querySelector('[data-aia="report:ch-summary.1"] mark[data-sentence-mark]') as HTMLElement;
    expect(marked.textContent).toBe(`${sentence} (srovnání bez doloženého čísla)`);
    expect(container.querySelector('[data-aia="report:ch-summary.1"] p')?.textContent).toContain("Bankám v Česku důvěřuje");
    // One no inline holds whole is named under its block, never dropped.
    const under = container.querySelector('[data-aia="report:ch-confidence.1"] p[data-sentence-mark]');
    expect(under?.textContent).toBe(`Upozornění: srovnání bez doloženého čísla: „${elsewhere}“`);
    expect(container.querySelectorAll("[data-sentence-mark]")).toHaveLength(2);
    fireEvent.click(within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" }));
    await waitFor(() => expect(container.querySelector("dialog[open]")).not.toBeNull());
    const dialog = container.querySelector("dialog[open]") as HTMLElement;
    expect(dialog.textContent).toContain(`Upozornění (2): srovnání bez doloženého čísla: „${sentence}“ (oddíl „`);
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-docx"));
  });

  it("says a refusal in words over the version refused only, and tells the card nothing", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockResolvedValue(CLIENT);
    vi.mocked(research.approveReport).mockRejectedValue(new ApiError(409, "report_not_approvable", "Zprávu nelze schválit.", null));
    const container = await openClient();
    fireEvent.click(within(bar(container)).getByRole("button", { name: APPROVE }));
    fireEvent.click(within(container.querySelector("dialog[open]") as HTMLElement).getByRole("button", { name: "Schválit" }));
    expect((await screen.findByRole("alert")).textContent).toBeTruthy();
    // The internal draft was not refused: its page says nothing of it.
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    await waitFor(() => expect(bar(container).getAttribute("data-report-version")).toBe("ART-docx"));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("prepares again a client report stored without its document, so it can be approved on one", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    vi.mocked(research.prepareClientReport).mockResolvedValue(CLIENT);
    render(<StudyFrameProvider frame={TEST_FRAME}><ReportDocumentView run={modelled} /></StudyFrameProvider>);
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    fireEvent.click(await screen.findByRole("button", { name: "Připravit klientskou zprávu znovu" }));
    expect(await screen.findByRole("button", { name: APPROVE })).toBeTruthy();
    expect(research.prepareClientReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1");
  });

  it("offers no second preparation when one answered the same, as for an approved version stored before its document", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    vi.mocked(research.prepareClientReport).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    render(<StudyFrameProvider frame={TEST_FRAME}><ReportDocumentView run={modelled} /></StudyFrameProvider>);
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    fireEvent.click(await screen.findByRole("button", { name: "Připravit klientskou zprávu znovu" }));
    await screen.findByText("K této verzi AIA dokument nesloží; lze ji jen stáhnout.");
    expect(screen.queryByRole("button", { name: "Připravit klientskou zprávu znovu" })).toBeNull();
    expect(research.prepareClientReport).toHaveBeenCalledTimes(1);
    // As the notice says, it is downloaded here (stand-in review of #985: the card did, RPT3c), never approved unseen.
    const file = new Blob(["docx"]);
    vi.mocked(research.downloadClientReport).mockResolvedValue({ blob: file, filename: "klient.docx", artifactId: "ART-client-old", reviewState: "APPROVED_INTERNAL" } as never);
    expect(screen.queryByRole("button", { name: /Schválit/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Stáhnout DOCX/ }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(file, "klient.docx"));
    expect(research.downloadClientReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1");
  });

  it("approves the internal draft it shows, naming the PDF the approval renders as the run states it at the ask, and says a producer's refusal in words", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, stamped: true });
    vi.mocked(research.report)
      // The doc bar's own read of its PDF (RPT3c), on mount.
      .mockResolvedValueOnce({ artifact_id: "ART-docx", stored_at: "2026-10-21T13:12:00Z", stamped: true, pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never)
      .mockResolvedValueOnce({ artifact_id: "ART-docx", stored_at: "2026-10-21T13:12:00Z", stamped: true, pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never)
      .mockResolvedValue({ artifact_id: "ART-docx", stored_at: "2026-10-21T13:12:00Z", stamped: true, pdf: { state: "READY" }, approval_renders_pdf: true } as never);
    vi.mocked(research.approveReport)
      .mockRejectedValueOnce(new ApiError(403, "separation_of_duties", "independent review required", null))
      .mockResolvedValue({ artifact_id: "ART-docx", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22", stamped: true, approval: null } as never);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    // Before the person asks, only the doc bar's read of its PDF; the approval reads the status again at the ask.
    await waitFor(() => expect(research.report).toHaveBeenCalledTimes(1));
    const button = () => within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" });
    const ask = async () => {
      fireEvent.click(button());
      await waitFor(() => expect(container.querySelector("dialog[open]")).not.toBeNull());
      return container.querySelector("dialog[open]") as HTMLElement;
    };
    let dialog = await ask();
    expect(dialog.textContent).toContain("Interní zpráva, vytvořenou 21. 10. 2026 15:12 (DOCX).");
    expect(dialog.textContent).not.toContain("modelovaná");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    expect(await screen.findByText(t("research.exec.results.reportApproveIndependent"))).toBeTruthy();
    // The PDF became part of the approval meanwhile: the next question says so, read again.
    dialog = await ask();
    expect(dialog.textContent).toContain("Interní zpráva, vytvořenou 21. 10. 2026 15:12 (DOCX i jeho PDF).");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledTimes(2));
    expect(research.approveReport).toHaveBeenLastCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-docx");
    expect(bar(container).textContent).toContain("interně schváleno");
  });

  it("asks nothing while the run's report names another version, and says why; a failed read is said too", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.report)
      // The doc bar's own read of its PDF (RPT3c), on mount; then the approval's.
      .mockResolvedValueOnce({ artifact_id: "ART-docx", pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never)
      .mockResolvedValueOnce({ artifact_id: "ART-newer", pdf: { state: "READY" }, approval_renders_pdf: true } as never)
      .mockRejectedValueOnce(new ApiError(503, "unavailable", "Služba nedostupná.", null));
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    await waitFor(() => expect(research.report).toHaveBeenCalledTimes(1));
    const button = () => within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" });
    fireEvent.click(button());
    expect((await screen.findByRole("alert")).textContent).toContain("ART-newer");
    expect(container.querySelector("dialog[open]")).toBeNull();
    fireEvent.click(button());
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Služba nedostupná."));
    expect(container.querySelector("dialog[open]")).toBeNull();
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("approves an internal draft it cannot show on the version its run names, as the card did before", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-old", pdf: { state: "READY" }, approval_renders_pdf: true } as never);
    vi.mocked(research.approveReport).mockResolvedValue({ artifact_id: "ART-old", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22", stamped: false, approval: null } as never);
    const { container } = show();
    fireEvent.click(await screen.findByRole("button", { name: "Schválit pro interní použití" }));
    await waitFor(() => expect(container.querySelector("dialog[open]")).not.toBeNull());
    const dialog = container.querySelector("dialog[open]") as HTMLElement;
    // The status gave no time: none is said, never guessed.
    expect(dialog.textContent).toContain("Schvalujete tuto verzi: Interní zpráva (DOCX i jeho PDF).");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-old"));
    expect(await screen.findByText(t("research.exec.results.reportApprovedInternal"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Schválit pro interní použití" })).toBeNull();
  });

  it("says a version approved meanwhile by someone else, updating the document shown and asking nothing", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-docx", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22", stamped: true } as never);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" }));
    await waitFor(() => expect(bar(container).textContent).toContain("interně schváleno"));
    expect(within(bar(container)).queryByRole("button", { name: "Schválit pro interní použití" })).toBeNull();
    expect(container.querySelector("dialog[open]")).toBeNull();
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("offers no approval of a draft a version saved in the editor stands over, when the editor cannot show it", async () => {
    // The PM's walk: the Document Server fails, the draft is shown, koncept 4 is approved.
    vi.mocked(research.openReportEditor).mockRejectedValue(new ApiError(503, "unavailable", "Služba nedostupná.", null));
    const line = { artifact_id: "ART-k4", koncept: 4, review_state: "APPROVED_INTERNAL" as const, approved_on: "2026-10-24", stamped: true };
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, edited_line: line });
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(within(bar(container)).queryByRole("button", { name: "Schválit pro interní použití" })).toBeNull();
    const said = container.querySelector("[data-report-edited-line]") as HTMLElement;
    expect(said.textContent).toBe("Nad tímto konceptem je v editoru uložen koncept 4 (interně schválen); schvaluje se v editoru, tento koncept už ne.");
  });

  it("refuses at the ask a draft it cannot show once the run's status names a version saved over it", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    vi.mocked(research.report).mockResolvedValue({
      artifact_id: "ART-old", pdf: { state: "READY" }, approval_renders_pdf: true,
      edited_line: { artifact_id: "ART-k2", koncept: 2, review_state: "DRAFT_UNAPPROVED" },
    } as never);
    const { container } = show();
    fireEvent.click(await screen.findByRole("button", { name: "Schválit pro interní použití" }));
    expect((await screen.findByRole("alert")).textContent).toContain("koncept 2 (neschválen)");
    expect(container.querySelector("dialog[open]")).toBeNull();
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("still offers the internal draft's approval when its document could not be read", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(503, "unavailable", "Služba nedostupná.", null));
    show();
    await screen.findByText(/Služba nedostupná\./);
    expect(screen.getByRole("button", { name: "Schválit pro interní použití" })).toBeTruthy();
  });

  it("reads, prepares and approves the report with a completed literature review, naming the review and its PDF", async () => {
    const REVIEW = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" }, status: "COMPLETED", title: "Fiktivní rešerše" };
    vi.mocked(deepResearch.runs).mockResolvedValue([REVIEW, { ...REVIEW, run_id: "RUN-running", status: "RUNNING" }] as never);
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    const WITH: StoredReportDocument = { ...STORED, report_artifact_id: "ART-context", stamped: true };
    vi.mocked(deepResearch.contextReportDocument)
      .mockRejectedValueOnce(new ApiError(409, "context_report_not_prepared", "", null))
      .mockResolvedValue(WITH);
    vi.mocked(deepResearch.prepareContextReport).mockResolvedValue({} as never);
    vi.mocked(deepResearch.contextReport).mockResolvedValue({ artifact_id: "ART-context", stored_at: "2026-10-21T13:12:00Z", stamped: true, pdf: { state: "READY" }, approval_renders_pdf: true } as never);
    vi.mocked(research.approveReport).mockResolvedValue({ artifact_id: "ART-context", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22", stamped: true, approval: null } as never);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    // A completed review only: one report with literature offered, named plainly.
    fireEvent.click(await screen.findByRole("button", { name: "Zpráva s rešerší" }));
    fireEvent.click(await screen.findByRole("button", { name: "Připravit zprávu s rešerší" }));
    await waitFor(() => expect(bar(container).getAttribute("data-report-version")).toBe("ART-context"));
    expect(deepResearch.prepareContextReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "RUN-deep");
    expect(bar(container).textContent).toContain("Zpráva s rešerší");
    fireEvent.click(within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" }));
    await waitFor(() => expect(container.querySelector("dialog[open]")).not.toBeNull());
    const dialog = container.querySelector("dialog[open]") as HTMLElement;
    expect(dialog.textContent).toContain("Schvalujete tuto verzi: Zpráva s rešerší · Fiktivní rešerše, vytvořenou 21. 10. 2026 15:12 (DOCX i jeho PDF).");
    expect(dialog.textContent).not.toContain("RUN-deep");
    expect(deepResearch.contextReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "RUN-deep");
    // The safe choice holds the focus (B22); Esc answers the dialog alone, nothing beneath it sees
    // it (I7, D21); Zrušit approves nothing.
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Zrušit" }));
    const beneath = vi.fn();
    window.addEventListener("keydown", beneath);
    fireEvent.keyDown(dialog, { key: "Escape" });
    window.removeEventListener("keydown", beneath);
    expect(beneath).not.toHaveBeenCalled();
    fireEvent.click(within(container.querySelector("dialog[open]") as HTMLElement).getByRole("button", { name: "Zrušit" }));
    expect(research.approveReport).not.toHaveBeenCalled();
    fireEvent.click(within(bar(container)).getByRole("button", { name: "Schválit pro interní použití" }));
    await waitFor(() => expect(container.querySelector("dialog[open]")).not.toBeNull());
    fireEvent.click(within(container.querySelector("dialog[open]") as HTMLElement).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-context"));
  });

  it("follows the review the page holds, and tells the page the review of the document chosen here (RPT3c)", async () => {
    vi.mocked(deepResearch.runs).mockResolvedValue([{ run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" }, status: "COMPLETED", is_terminal: true, title: "Fiktivní rešerše" }] as never);
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(deepResearch.contextReportDocument).mockResolvedValue({ ...STORED, report_artifact_id: "ART-context" });
    const told: (string | null)[] = [];
    const page = (held: string | null) => <StudyFrameProvider frame={TEST_FRAME}><ReportDocumentView run={run("SUCCEEDED")} review={held} onReview={(id) => told.push(id)} /></StudyFrameProvider>;
    const view = render(page(null));
    await screen.findByRole("article", { name: "Koncept zprávy" });
    // "Použít ve zprávě" on the review panel: the pane opens the report with that review.
    view.rerender(page("RUN-deep"));
    await waitFor(() => expect(document.querySelector("[data-report-docbar]")?.getAttribute("data-report-version")).toBe("ART-context"));
    expect(deepResearch.contextReportDocument).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "RUN-deep");
    // The internal draft chosen here: the page hears no review.
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    expect(told).toEqual([null]);
  });

  it("downloads an internal draft it cannot show as the version its run names, read again first (RPT3c)", async () => {
    vi.mocked(research.reportDocument).mockRejectedValue(new ApiError(409, "report_document_not_stored", "", null));
    vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-old", review_state: "DRAFT_UNAPPROVED", pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never);
    vi.mocked(research.downloadReport).mockResolvedValue({ blob: new Blob(["x"]), filename: "x.docx", artifactId: "ART-old", reviewState: "DRAFT_UNAPPROVED" } as never);
    show();
    expect(await screen.findByText(/Koncept DOCX stáhnete zde/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /Stáhnout DOCX/ }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    // Its status read again before the file is asked for (stand-in review of #985).
    const reads = vi.mocked(research.report).mock.invocationCallOrder;
    expect(reads[reads.length - 1]).toBeLessThan(vi.mocked(research.downloadReport).mock.invocationCallOrder[0]);
    // A run that now names another version: that version's file is not handed over.
    vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-newer", review_state: "DRAFT_UNAPPROVED", pdf: { state: "NOT_REQUESTED" }, approval_renders_pdf: false } as never);
    fireEvent.click(screen.getByRole("button", { name: /Stáhnout DOCX/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("není verze");
    expect(saveBlob).toHaveBeenCalledTimes(1);
  });

  it("offers the report with literature although the run's own report failed", async () => {
    vi.mocked(deepResearch.runs).mockResolvedValue([{ run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" }, status: "COMPLETED", is_terminal: true }] as never);
    vi.mocked(deepResearch.contextReportDocument).mockRejectedValue(new ApiError(409, "context_report_not_prepared", "", null));
    vi.mocked(deepResearch.prepareContextReport).mockResolvedValue({ state: "READY" } as never);
    show(run("FAILED"));
    fireEvent.click(await screen.findByRole("button", { name: "Zpráva s rešerší" }));
    fireEvent.click(await screen.findByRole("button", { name: "Připravit zprávu s rešerší" }));
    await waitFor(() => expect(deepResearch.prepareContextReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "RUN-deep"));
  });

  it("says a report with literature not found, keeping the way back to the internal draft", async () => {
    vi.mocked(deepResearch.runs).mockResolvedValue([{ run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" }, status: "COMPLETED", is_terminal: true }] as never);
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(deepResearch.contextReportDocument).mockRejectedValue(new ApiError(404, "not_found", "", null));
    show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(await screen.findByRole("button", { name: "Zpráva s rešerší" }));
    expect(await screen.findByText("Zprávu s touto rešerší AIA nenašla.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Interní zpráva" })).toBeTruthy();
  });

  it("offers no report with literature to a reader who may not review, and asks for no reviews", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    render(<StudyFrameProvider frame={{ ...TEST_FRAME, canReview: false }}><ReportDocumentView run={run("SUCCEEDED")} /></StudyFrameProvider>);
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(deepResearch.runs).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Zpráva s rešerší/ })).toBeNull();
  });

  it("offers no approval to a reader who may not review, nor on an approved version", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockResolvedValue(CLIENT);
    await openClient({ ...TEST_FRAME, canReview: false });
    expect(screen.queryByRole("button", { name: /^Schválit/ })).toBeNull();
    cleanup();
    vi.mocked(research.clientReportDocument).mockResolvedValue({ ...CLIENT, review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22" });
    await openClient();
    expect(screen.queryByRole("button", { name: APPROVE })).toBeNull();
    cleanup();
    vi.mocked(research.reportDocument).mockResolvedValue({ ...STORED, review_state: "APPROVED_INTERNAL", approved_on: "2026-10-22" });
    show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(screen.queryByRole("button", { name: /^Schválit/ })).toBeNull();
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
    expect(bar.getAttribute("data-report-version")).toBe("ART-client");
    // One article on the page: the Lead's report: ids name one document.
    expect(container.querySelectorAll("article")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    await waitFor(() => expect(container.querySelector("[data-report-docbar]")!.getAttribute("data-report-version")).toBe("ART-docx"));
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
    await waitFor(() => expect(container.querySelector("[data-report-docbar]")?.getAttribute("data-report-version")).toBe("ART-docx"));
    answer(CLIENT);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector("[data-report-docbar]")!.getAttribute("data-report-version")).toBe("ART-docx");
    expect(container.querySelector("[data-report-document]")!.getAttribute("data-report-document")).toBe("ready");
  });

  it("inside the workbench closes the old document's claims in the frame's drawer when the person switches (review of #689)", async () => {
    vi.mocked(research.reportDocument).mockResolvedValue(STORED);
    vi.mocked(research.clientReportDocument).mockResolvedValue(CLIENT);
    const inspector = { open: vi.fn(() => true), closeWhere: vi.fn() };
    render(
      <StudyFrameProvider frame={TEST_FRAME}><ItemInspectorContext.Provider value={inspector}><ReportDocumentView run={modelled()} /></ItemInspectorContext.Provider></StudyFrameProvider>,
    );
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    expect(inspector.closeWhere).toHaveBeenCalledWith("report:ref:internal:");
    await waitFor(() => expect(document.querySelector("[data-report-docbar]")?.getAttribute("data-report-version")).toBe("ART-client"));
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    expect(inspector.closeWhere).toHaveBeenLastCalledWith("report:ref:client:");
    // The document already shown closes nothing.
    fireEvent.click(screen.getByRole("button", { name: "Interní zpráva" }));
    expect(inspector.closeWhere).toHaveBeenCalledTimes(2);
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
