// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetBootCache } from "@/unit/boot";
import { briefFingerprint, defaultsMerge } from "@/unit/research/model";
import { CONFIRM_REMOVE_SECTION, GUIDED_PROMPT, OPTIMIZE_DONE, PROMPT_SET_ITEMS, PROMPT_SET_TYPE, SET_SIZE, SET_TOO_SMALL } from "@/unit/research/questionnaire";
import { ResearchScreen } from "./ResearchScreen";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/research/PRJ-1/questionnaire", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT = { empty_project: EMPTY, ai_provider: "claude_code_subscription", panel: { version: "v17.1.2" }, edition: { version: "18.6.6", claude_code_enabled: true } };
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
function unitStub(project: Record<string, unknown>, analysis: unknown = null, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        "/api/bootstrap": () => BOOT,
        "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 3, project_type: "research", project, analysis }),
        "/api/projects/save": () => ({ project_id: "PRJ-1", revision: 4 }),
        "/api/providers/claude-code/status": () => ({ ok: true }),
        "/api/research/build_questionnaire": () => ({ job_id: "JOB-B" }),
        "/api/questionnaire/optimize": () => ({ job_id: "JOB-O" }),
        "/api/job": () => ({ state: "done", result: { project: { ...EMPTY, ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "ai" } } } }),
        ...over,
      };
      const answer = answers[u.split("?")[0]]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path);
const lastSave = () => posted("/api/projects/save").at(-1)?.body as { project: { sections: { questions?: { typ: string; kategorie?: string[] }[]; objects?: string[] }[]; ui_state: Record<string, unknown> }; reason: string };

async function answerDialog(question: string, value: string | null) {
  const form = (await screen.findByText(question)).closest("form") as HTMLFormElement;
  if (value === null) return fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
  const input = within(form).queryByRole("textbox");
  if (input) fireEvent.change(input, { target: { value } });
  fireEvent.submit(form);
}
async function saved() {
  // The store saves 1.8 s after the last change; the test waits for that body.
  await waitFor(() => expect(posted("/api/projects/save").length).toBeGreaterThan(0), { timeout: 4000 });
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
  resetBootCache();
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
});

describe("Dotazník", () => {
  it("offers the three paths with the provider and model, and waits for questions before going on", async () => {
    unitStub(BRIEF);
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    expect(await screen.findByRole("heading", { name: "Jak chcete dotazník vytvořit?" })).toBeTruthy();
    expect(screen.getByText("AI partner · sonnet")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nejdřív vytvořte nebo nahrajte dotazník.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Sestavit ručně/ }));
    expect(await screen.findByText("Dotazník je prázdný")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "změnit způsob vytvoření" }));
    expect(await screen.findByRole("heading", { name: "Jak chcete dotazník vytvořit?" })).toBeTruthy();
  });

  it("draws the preview and the editor, and has no dead 'AI: zlepšit blok' (OI-49)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
    expect(screen.getByText("Otázka 1")).toBeTruthy();
    expect(screen.getByText("Sledovaná sada 3 · Sledovaná sada — média")).toBeTruthy();
    expect(screen.getAllByText("Jak často používáte TV?").length).toBe(1);
    expect(screen.queryByText(/zlepšit blok/)).toBeNull();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("edits a question as the classic editor does: type, options and a scale", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    const card = (await screen.findByText("Q1")).closest("[id^=qedit_]") as HTMLElement;
    const options = within(card).getByLabelText("Možnosti — jedna na řádek");
    fireEvent.blur(options, { target: { value: " Denně \n\nTýdně\nNikdy " } });
    fireEvent.change(within(card).getByLabelText("Typ"), { target: { value: "skala" } });
    expect(await within(card).findByLabelText("Minimum")).toBeTruthy();
    await saved();
    const q1 = lastSave().project.sections[0].questions![0];
    expect(q1).toMatchObject({ typ: "skala", kategorie: ["Denně", "Týdně", "Nikdy"] });
  });

  it("adds a guided question through the classic prompt, and refuses a set of three", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
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
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    const objects = await screen.findByLabelText("Objekty — jeden na řádek (povinně 4–15)");
    fireEvent.blur(objects, { target: { value: "TV\nRádio" } });
    expect(await screen.findByText(SET_TOO_SMALL)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Smazat" })[1]);
    await answerDialog(CONFIRM_REMOVE_SECTION, "");
    await waitFor(() => expect(screen.getByRole("heading", { name: "2 otázek · 0 sledovaných sad" })).toBeTruthy());
  });

  it("imports a file through the unit and opens its questionnaire in the editor", async () => {
    unitStub(
      { ...BRIEF, ui_state: { questionnaire_path: "upload" } },
      null,
      { "/api/questionnaire/upload": () => ({ project: { ...EMPTY, ...BRIEF, sections: SECTIONS }, summary: { question_count: 2, tracked_sets: 1 } }) },
    );
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    expect(await screen.findByRole("link", { name: "Stáhnout XLSX šablonu" })).toHaveProperty("href", "http://localhost:3000/api/questionnaire/template");
    fireEvent.change(screen.getByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    expect(await screen.findByText("Načteno: 2 otázek · 1 sledovaných sad")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
    const [upload] = posted("/api/questionnaire/upload");
    expect(upload.body).toMatchObject({ filename: "dotaznik.xlsx", data_b64: btoa("x") });
  });

  it("builds with AI: the brief's analysis reused, then the job, then the editor", async () => {
    const sig = briefFingerprint(defaultsMerge(BRIEF, BOOT));
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, { objectives: ["O"], _brief_signature: sig });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" }, { timeout: 4000 })).toBeTruthy();
    expect(posted("/api/research/analyze")).toEqual([]);
    const [built] = posted("/api/research/build_questionnaire");
    expect(built.body).toMatchObject({ analysis: { objectives: ["O"] }, model: "sonnet", provider: "claude_code_subscription", project_id: "PRJ-1" });
  });

  it("stops the build at the provider notice when Claude Code is not ready", async () => {
    const sig = briefFingerprint(defaultsMerge(BRIEF, BOOT));
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, { objectives: ["O"], _brief_signature: sig }, { "/api/providers/claude-code/status": () => ({ ok: false }) });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    expect(await screen.findByText("Claude Code není připravený. Projekt zůstává uložený.")).toBeTruthy();
    expect(posted("/api/research/build_questionnaire")).toEqual([]);
  });

  it("optimises without a provider check, as the classic does (OI-55)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, { "/api/providers/claude-code/status": () => ({ ok: false }) });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    fireEvent.click((await screen.findAllByRole("button", { name: "OPTIMALIZOVAT DOTAZNÍK S AI" }))[0]);
    expect(await screen.findByText(OPTIMIZE_DONE, {}, { timeout: 4000 })).toBeTruthy();
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
    expect(posted("/api/questionnaire/optimize")[0].body).toMatchObject({ research: {}, provider: "claude_code_subscription" });
  });

  it("goes on to the audience at its first choice", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    fireEvent.click(await screen.findByRole("button", { name: "Dotazník mám → Koho se ptát" }));
    expect(push).toHaveBeenCalledWith("/app/research/PRJ-1/audience");
    await saved();
    expect(lastSave()).toMatchObject({ reason: "questionnaire_done", project: { ui_state: { audience_entry: "choose" } } });
  });
});
