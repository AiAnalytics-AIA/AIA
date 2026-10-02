// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { briefFingerprint, defaultsMerge } from "@/research/model";
import { CONFIRM_REMOVE_SECTION, GUIDED_PROMPT, PROMPT_SET_ITEMS, PROMPT_SET_TYPE, SET_SIZE, SET_TOO_SMALL } from "@/research/questionnaire";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE = { empty_project: EMPTY };
const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", purpose: "", questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] },
    { id: "Q2", text: "Jak moc?", typ: "skala", skala: [1, 10], popisky_skaly: ["vůbec", "zcela"] },
  ] },
  { id: "sec_b", type: "object_battery", title: "Sledovaná sada — média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"], object_question: "Jak často používáte {object}?", scale_labels: ["nikdy", "denně"] },
];
const BRIEF = { goal: "Zjistit zájem o nový nápoj" };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
let saves: SavedBody[] = [];
function unitStub(project: Record<string, unknown>, analysis: unknown = null, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: analysis });
  saves = ws.saves;
  const native = nativeAgentFixture((action, baseline) => action === "analyze_brief" ? { project: baseline, proposal: { objectives: ["O"] }, analysis: { objectives: ["O"] } } : { project: { ...baseline, sections: SECTIONS }, proposal: { sections: SECTIONS } }, over);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answer = native(u.split("?")[0], init?.method ?? "GET", body) ?? ws.answer(u.split("?")[0], init?.method ?? "GET", body) ?? over[u.split("?")[0]]?.(body);
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));

/** Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018). */
const unitCalls = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url);
const lastSave = () => saves.at(-1) as unknown as { content: { sections: { questions?: { typ: string; kategorie?: string[] }[]; objects?: string[] }[]; ui_state: Record<string, unknown> }; reason: string };

async function answerDialog(question: string, value: string | null) {
  const form = (await screen.findByText(question)).closest("form") as HTMLFormElement;
  if (value === null) return fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
  const input = within(form).queryByRole("textbox");
  if (input) fireEvent.change(input, { target: { value } });
  fireEvent.submit(form);
}
async function saved() {
  // The store saves 1.8 s after the last change; the test waits for that body.
  await waitFor(() => expect(saves.length).toBeGreaterThan(0), { timeout: 4000 });
}

if (!Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function (this: Blob) {
    return new Promise<ArrayBuffer>((resolve) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as ArrayBuffer);
      r.readAsArrayBuffer(this);
    });
  };
}
beforeEach(() => {
  push.mockReset();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  Element.prototype.scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  expect(unitCalls()).toEqual([]);
});

describe("Dotazník", () => {
  it("offers the three paths with the design availability, and waits for questions before going on", async () => {
    unitStub(BRIEF);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Jak chcete dotazník vytvořit?" })).toBeTruthy();
    expect(screen.getByText("Návrh AI se uloží jako návrh ke kontrole. Změny použijete až po potvrzení.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nejdřív vytvořte nebo nahrajte dotazník.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Sestavit ručně/ }));
    expect(await screen.findByText("Dotazník je prázdný")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "změnit způsob vytvoření" }));
    expect(await screen.findByRole("heading", { name: "Jak chcete dotazník vytvořit?" })).toBeTruthy();
  });

  it("draws the preview and the editor, and has no dead 'AI: zlepšit blok' (OI-49)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
    expect(screen.getByText("Otázka 1")).toBeTruthy();
    expect(screen.getByText("Sledovaná sada 3 · Sledovaná sada — média")).toBeTruthy();
    expect(screen.getAllByText("Jak často používáte TV?").length).toBe(1);
    expect(screen.queryByText(/zlepšit blok/)).toBeNull();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("edits a question as the classic editor does: type, options and a scale", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const card = (await screen.findByText("Q1")).closest("[id^=qedit_]") as HTMLElement;
    const options = within(card).getByLabelText("Možnosti — jedna na řádek");
    fireEvent.blur(options, { target: { value: " Denně \n\nTýdně\nNikdy " } });
    fireEvent.change(within(card).getByLabelText("Typ"), { target: { value: "skala" } });
    expect(await within(card).findByLabelText("Minimum")).toBeTruthy();
    await saved();
    const q1 = lastSave().content.sections[0].questions![0];
    expect(q1).toMatchObject({ typ: "skala", kategorie: ["Denně", "Týdně", "Nikdy"] });
  });

  it("adds a guided question through the classic prompt, and refuses a set of three", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Škála 1–10" }));
    await answerDialog(GUIDED_PROMPT.scale, "Jak moc vám chutná?");
    expect((await screen.findAllByText("Jak moc vám chutná?")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "3 otázek · 1 sledovaných sad" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sledovaná sada" }));
    await answerDialog(PROMPT_SET_TYPE, "značky");
    await answerDialog(PROMPT_SET_ITEMS, "A, B, C");
    expect(await screen.findByText(SET_SIZE)).toBeTruthy();
  });

  it("notes a set under four objects, and removes a block only when confirmed", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const objects = await screen.findByLabelText("Objekty — jeden na řádek (povinně 4–15)");
    fireEvent.blur(objects, { target: { value: "TV\nRádio" } });
    expect(await screen.findByText(SET_TOO_SMALL)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Smazat" })[1]);
    await answerDialog(CONFIRM_REMOVE_SECTION, "");
    await waitFor(() => expect(screen.getByRole("heading", { name: "2 otázek · 0 sledovaných sad" })).toBeTruthy());
  });

  it("starts durable public Deep Research from the saved design, without the legacy endpoint", async () => {
    const path = "/api/v1/studies/STU-1/deep-research/runs";
    const job = { run_id: "RUN-a1", design_revision_id: "REV-A", preset: "QUICK", channels: ["WEB"], status: "RUNNING", phase: "RUNNING", is_terminal: false, needs_attention: false, retryable: false, created_at: null, steps: [], actual_cost_usd: null };
    let started = false;
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, {
      [path]: (body) => {
        if (body) { started = true; return job; }
        return started ? [job] : [];
      },
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Spustit veřejný výzkum" }));
    await waitFor(() => expect(posted(path)).toHaveLength(1));
    expect(posted(path)[0].body).toEqual({ design_revision_id: "REV-A", preset_name: "QUICK", channels: ["WEB"] });
    expect(posted("/api/v1/studies/STU-1/design/revisions")[0].body).toMatchObject({ source_stage: "questionnaire" });
    expect(calls.some((call) => call.url === "/api/research/deep")).toBe(false);
    expect(await screen.findByText("Stav: RUNNING · RUNNING")).toBeTruthy();
  });

  const IMPORT_PATH = "/api/v1/studies/STU-1/workspace/questionnaire-import";
  const TEMPLATE_PATH = "/api/v1/studies/STU-1/workspace/questionnaire-template";

  it("imports a file in AIA, puts its sections on the questionnaire and saves", async () => {
    unitStub(
      { ...BRIEF, title: "Moje studie", ui_state: { questionnaire_path: "upload" } },
      null,
      { [IMPORT_PATH]: () => ({ sections: SECTIONS, summary: { question_count: 2, tracked_sets: 1, sections: 2 }, filename: "dotaznik.xlsx" }) },
    );
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    expect(await screen.findByText("Načteno: 2 otázek · 1 sledovaných sad")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
    // AIA is sent the file alone, never the project, and nothing reaches the unit.
    expect(posted(IMPORT_PATH).map((c) => c.body)).toEqual([{ filename: "dotaznik.xlsx", data_b64: btoa("x") }]);
    expect(calls.filter((c) => c.url.startsWith("/api/questionnaire"))).toEqual([]);
    await saved();
    const body = saves.at(-1) as unknown as { reason: string; content: Record<string, unknown> & { research_plan: { status: string }; ui_state: Record<string, unknown> } };
    expect(body.reason).toBe("questionnaire_import");
    expect(body.content.sections).toEqual(SECTIONS);
    expect(body.content.research_plan.status).toBe("questionnaire_ready");
    expect(body.content.ui_state.questionnaire_path).toBe("manual");
    // The rest of the project is the person's own.
    expect(body.content.title).toBe("Moje studie");
  });

  it("shows why a file did not import, in the words AIA gave", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [IMPORT_PATH]: () => new Response(JSON.stringify({ code: "missing_columns", message: "Chybí povinné sloupce: typ" }), { status: 422 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.csv")] } });
    expect((await screen.findByRole("alert")).textContent).toBe("Chybí povinné sloupce: typ");
    expect(saves).toEqual([]);
  });

  it("downloads AIA's template through the study, and links to nothing of the unit's", async () => {
    const created: Blob[] = [];
    const clicked = vi.fn();
    const real = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
    URL.createObjectURL = (b: Blob) => (created.push(b), "blob:t");
    URL.revokeObjectURL = () => {};
    HTMLAnchorElement.prototype.click = clicked;
    onTestFinished(() => {
      URL.createObjectURL = real.create;
      URL.revokeObjectURL = real.revoke;
      HTMLAnchorElement.prototype.click = real.click;
    });
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [TEMPLATE_PATH]: () => new Response("PK-template", { status: 200 }),
    });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Stáhnout XLSX šablonu" }));
    await waitFor(() => expect(clicked).toHaveBeenCalledTimes(1));
    expect(await created[0].text()).toBe("PK-template");
    // No link into the unit's paths: the template and the guide are AIA's.
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href") || "");
    expect(hrefs.filter((h) => h.startsWith("/api/questionnaire") || h.startsWith("/files/"))).toEqual([]);
    expect(screen.queryByText("Metodika pro externí AI")).toBeNull();
  });

  it("reviews the native brief analysis and questionnaire before opening the editor", async () => {
    const sig = briefFingerprint(defaultsMerge(BRIEF, TEMPLATE));
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, { objectives: ["O"], _brief_signature: sig });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    await approveProposal();
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" }, { timeout: 4000 })).toBeTruthy();
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted(AGENTS_PATH).map((c) => (c.body as { action: string }).action)).toEqual(["build_questionnaire"]);
    expect(posted("/api/research/build_questionnaire")).toEqual([]);
  });

  it("parks the build at the native runtime boundary", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, null, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    expect(await screen.findByText(PARK_MESSAGE, {}, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(posted("/api/research/build_questionnaire")).toEqual([]);
  });

  it("reviews native optimization without asking for a legacy provider connection", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click((await screen.findAllByRole("button", { name: "OPTIMALIZOVAT DOTAZNÍK S AI" }))[0]);
    await approveProposal();
    await waitFor(() => expect(posted(`${AGENTS_PATH}/RUN-A/accept`)).toHaveLength(1));
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "optimize_questionnaire" });
    expect(posted("/api/questionnaire/optimize")).toEqual([]);
  });

  it("goes on to the audience at its first choice", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Dotazník mám → Koho se ptát" }));
    expect(push).toHaveBeenCalledWith(stagePath("audience"));
    await saved();
    expect(lastSave()).toMatchObject({ reason: "questionnaire_done", content: { ui_state: { audience_entry: "choose" } } });
  });
});
