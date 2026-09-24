// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetBootCache } from "@/unit/boot";
import { ANALYSIS_REUSED, LINK_INVALID } from "@/unit/research/brief";
import { PROBLEM_TYPES, briefFingerprint, defaultsMerge } from "@/unit/research/model";
import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME, stagePath } from "./test-frame";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/brief", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT = {
  empty_project: EMPTY,
  ai_provider: "claude_code_subscription",
  panel: { version: "v17.1.2" },
  edition: { version: "18.6.6", claude_code_enabled: true },
};

type Call = { url: string; body: unknown };
let calls: Call[] = [];

/** The unit, answering by path; `over` replaces any answer. */
function unitStub(project: Record<string, unknown>, over: Record<string, (body: unknown) => unknown> = {}, analysis: unknown = null) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const path = u.split("?")[0];
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        "/api/bootstrap": () => BOOT,
        "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 3, project_type: "research", project, analysis }),
        "/api/projects/save": () => ({ project_id: "PRJ-1", revision: 4 }),
        "/api/providers/claude-code/status": () => ({ ok: true }),
        "/api/research/analyze": () => ({ job_id: "JOB-1" }),
        "/api/job": () => ({
          state: "done",
          result: { analysis: { objectives: ["Změřit zájem"] }, project: { research_plan: { status: "proposed" } } },
        }),
        ...over,
      };
      const answer = answers[path]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path);

// jsdom's Blob has no arrayBuffer() (every current browser has); read it through FileReader. AGENTS.md § jsdom.
if (!Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function (this: Blob) {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as ArrayBuffer);
      r.onerror = () => reject(r.error);
      r.readAsArrayBuffer(this);
    });
  };
}

beforeEach(() => {
  resetBootCache();
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Zadání", () => {
  it("draws the classic blocks, and the next step waits for a goal", async () => {
    unitStub({ title: "Nový výzkum" });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Co řešíte?" })).toBeTruthy();
    for (const [, label] of PROBLEM_TYPES) expect(screen.getByRole("button", { name: new RegExp(label.replace(/[/()]/g, ".")) })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Přílohy a odkazy" })).toBeTruthy();
    expect(screen.getByText("Další kontext")).toBeTruthy();
    expect(screen.getByText("Zatím bez příloh.")).toBeTruthy();
    // The empty project's title shows as an empty field, as in the classic screen.
    expect((screen.getByPlaceholderText("Např. Nové balení produktu") as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("button", { name: /Další · vytvořit návrh/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("a problem type is a toggle that fills an empty goal with its default", async () => {
    unitStub({});
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    const tile = await screen.findByRole("button", { name: /Nový produkt \/ koncept/ });
    fireEvent.click(tile);
    expect(tile.getAttribute("aria-pressed")).toBe("true");
    const goal = screen.getByPlaceholderText(/Co chcete zjistit/) as HTMLTextAreaElement;
    expect(goal.value).toBe(PROBLEM_TYPES[1][3]);
    expect((screen.getByRole("button", { name: /Další · vytvořit návrh/ }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(tile);
    expect(tile.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("Změny se uloží za chvíli")).toBeTruthy();
  });

  it("keeps a link only when it is http(s), and removes it again", async () => {
    unitStub({});
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    const url = await screen.findByLabelText("Odkaz");
    fireEvent.change(url, { target: { value: "example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Přidat webový odkaz" }));
    expect(screen.getByRole("alert").textContent).toBe(LINK_INVALID);
    fireEvent.change(url, { target: { value: "https://example.test/a" } });
    fireEvent.click(screen.getByRole("button", { name: "Přidat webový odkaz" }));
    expect(screen.getAllByText("https://example.test/a").length).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat" }));
    expect(screen.getByText("Zatím bez příloh.")).toBeTruthy();
  });

  it("uploads picked files one request each, as base64, and lists what the unit read", async () => {
    unitStub({}, { "/api/project/attachment": (b) => ({ kind: "file", filename: (b as { filename: string }).filename, size_bytes: 2048, text_extracted: true, sha256: "s" }) });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    const input = await screen.findByLabelText("Soubory k zadání");
    fireEvent.change(input, { target: { files: [new File(["ahoj"], "zadani.txt", { type: "text/plain" })] } });
    expect(await screen.findByText("zadani.txt")).toBeTruthy();
    expect(screen.getByText("2 KB · text načten")).toBeTruthy();
    expect(posted("/api/project/attachment").map((c) => c.body)).toEqual([{ filename: "zadani.txt", data_b64: btoa("ahoj") }]);
  });

  it("runs the analysis as a job, keeps the person's brief, and goes on to the plan", async () => {
    unitStub({ goal: "Zjistit zájem o nový nápoj" });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")), { timeout: 4000 });
    const [analyze] = posted("/api/research/analyze");
    expect(analyze.body).toMatchObject({
      briefing: { goal: "Zjistit zájem o nový nápoj", study_config: {}, attachments_context: "" },
      model: "sonnet",
      provider: "claude_code_subscription",
      project_id: "PRJ-1",
      project_revision: 3,
    });
    // The merged project is saved with the classic reason once the debounce runs.
    expect((screen.getByPlaceholderText(/Co chcete zjistit/) as HTMLTextAreaElement).value).toBe("Zjistit zájem o nový nápoj");
  });

  it("reuses the analysis of the same brief without asking the model", async () => {
    const project = { goal: "Zjistit zájem" };
    const sig = briefFingerprint(defaultsMerge(project, BOOT));
    unitStub(project, {}, { objectives: ["A"], _brief_signature: sig });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")));
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(screen.getByText(ANALYSIS_REUSED)).toBeTruthy();
  });

  it("says when the provider is not ready, where the person is, with the way to the settings", async () => {
    unitStub({ goal: "Cíl" }, { "/api/providers/claude-code/status": () => ({ ok: false }) });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    expect(await screen.findByText("Claude Code není připravený. Projekt zůstává uložený.")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Otevřít Nastavení/ }).getAttribute("href")).toBe("/classic#aia:go=settings");
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(push).not.toHaveBeenCalled();
  });

  it("shows the classic error card with what failed when the job fails", async () => {
    unitStub({ goal: "Cíl" }, { "/api/job": () => ({ state: "error", result: { error: "MODEL_TIMEOUT: nic se nevrátilo" } }) });
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doplní a navrhne výzkum" }));
    expect(await screen.findByText("AI analýza se nedokončila", {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByText("Zadání zůstalo uložené.")).toBeTruthy();
    expect(screen.getByText("MODEL_TIMEOUT: nic se nevrátilo")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Diagnostika" })).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });

  it("refuses an empty brief with the classic message", async () => {
    unitStub({});
    render(<ResearchScreen projectId="PRJ-1" step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doplní a navrhne výzkum" }));
    expect(await screen.findByText("Nejdřív popište zadání výzkumu.")).toBeTruthy();
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
  });
});
