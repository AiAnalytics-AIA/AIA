// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, DESIGN_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { LINK_INVALID } from "@/research/brief";
import { PROBLEM_TYPES, briefFingerprint, defaultsMerge } from "@/research/model";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/brief", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE = { empty_project: EMPTY };

type Call = { url: string; body: unknown };
let calls: Call[] = [];

const ATTACH_PATH = "/api/v1/studies/STU-1/workspace/attachments";
let ws: ReturnType<typeof workspaceFixture>;

/** AIA, answering by path; `over` replaces any answer. `project` null is a study never saved. */
function unitStub(project: Record<string, unknown> | null, over: Record<string, (body: unknown) => unknown> = {}, analysis: unknown = null) {
  calls = [];
  ws = workspaceFixture(project, { analysis });
  const native = nativeAgentFixture((_action, baseline) => ({ project: { ...baseline, research_plan: { status: "analyzed", objectives: ["Změřit zájem"] } }, proposal: { objectives: ["Změřit zájem"] }, analysis: { objectives: ["Změřit zájem"] } }), over);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const path = u.split("?")[0];
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answer = native(path, init?.method ?? "GET", body) ?? ws.answer(path, init?.method ?? "GET", body) ?? over[path]?.(body);
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));

/** Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018). */
const unitCalls = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url);

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
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  expect(unitCalls()).toEqual([]);
});

describe("Zadání", () => {
  it("draws the classic blocks, and the next step waits for a goal", async () => {
    unitStub({ title: "Nový výzkum" });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
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
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const tile = await screen.findByRole("button", { name: /Nový produkt \/ koncept/ });
    fireEvent.click(tile);
    // The tile can be on screen before the store's subscription effect has run;
    // a click then renders when it subscribes, not synchronously (AGENTS.md § Next.js / TypeScript).
    await screen.findByRole("button", { name: /Nový produkt \/ koncept/, pressed: true }, { timeout: 5_000 });
    const goal = screen.getByPlaceholderText(/Co chcete zjistit/) as HTMLTextAreaElement;
    expect(goal.value).toBe(PROBLEM_TYPES[1][3]);
    expect((screen.getByRole("button", { name: /Další · vytvořit návrh/ }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(tile);
    expect(tile.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("Změny se uloží za chvíli")).toBeTruthy();
  });

  it("keeps a link only when it is http(s), and removes it again", async () => {
    unitStub({});
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
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

  const record = (b: unknown, n = 1) => ({
    kind: "file",
    attachment_id: `ART-${n}a`,
    filename: (b as { filename: string }).filename,
    extension: ".txt",
    content_type: "text/plain",
    size_bytes: 2048,
    text_extracted: true,
    sha256: `s${n}`,
    context_excerpt: "ahoj",
  });

  it("keeps picked files in AIA, one request each, as base64, and the brief saves their records", async () => {
    unitStub({}, { [ATTACH_PATH]: (b) => record(b) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const input = await screen.findByLabelText("Soubory k zadání");
    fireEvent.change(input, { target: { files: [new File(["ahoj"], "zadani.txt", { type: "text/plain" })] } });
    expect(await screen.findByText("zadani.txt")).toBeTruthy();
    expect(screen.getByText("2 KB · text načten")).toBeTruthy();
    expect(posted(ATTACH_PATH).map((c) => c.body)).toEqual([{ filename: "zadani.txt", data_b64: btoa("ahoj") }]);
    // Nothing reaches 18.6.6.
    expect(calls.filter((c) => c.url.startsWith("/api/project"))).toEqual([]);
    await waitFor(() => expect(ws.saves.at(-1)?.reason).toBe("brief_attachments"), { timeout: 4000 });
    expect((ws.saves.at(-1)?.content.briefing as { attachments: unknown[] }).attachments).toEqual([record({ filename: "zadani.txt" })]);
  });

  it("saves a study that was never saved before its first file, so the file has somewhere to be", async () => {
    unitStub(null, { [ATTACH_PATH]: (b) => record(b) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Soubory k zadání"), { target: { files: [new File(["ahoj"], "zadani.txt")] } });
    expect(await screen.findByText("zadani.txt")).toBeTruthy();
    const order = calls.filter((c) => c.body !== null && (c.url === ATTACH_PATH || c.url.endsWith("/workspace/content"))).map((c) => c.url.split("/").at(-1));
    expect(order[0]).toBe("content");
    expect(order[1]).toBe("attachments");
    expect(ws.saves[0]).toMatchObject({ base_revision: null, reason: "brief_attachments" });
  });

  it("downloads a kept file through the study, and says when a file is not in AIA", async () => {
    // jsdom has no object URLs and does not navigate: both are stood in for, and put back.
    const created: Blob[] = [];
    const clicked = vi.fn();
    const real = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
    URL.createObjectURL = (b: Blob) => (created.push(b), "blob:1");
    URL.revokeObjectURL = () => {};
    HTMLAnchorElement.prototype.click = clicked;
    onTestFinished(() => {
      URL.createObjectURL = real.create;
      URL.revokeObjectURL = real.revoke;
      HTMLAnchorElement.prototype.click = real.click;
    });
    unitStub(
      { briefing: { attachments: [record({ filename: "zadani.txt" }), { kind: "file", filename: "stare.pdf", size_bytes: 1024, attachment_id: "ATT-legacy" }] } },
      { [`${ATTACH_PATH}/ART-1a`]: () => new Response("ahoj", { status: 200, headers: { "Content-Type": "application/octet-stream" } }) },
    );
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Stáhnout přílohu zadani.txt" }));
    await waitFor(() => expect(clicked).toHaveBeenCalledTimes(1));
    expect(await created[0].text()).toBe("ahoj");
    expect(calls.map((c) => c.url)).toContain(`${ATTACH_PATH}/ART-1a`);
    // A record whose file never came into AIA offers no download, and says why.
    expect(screen.queryByRole("button", { name: "Stáhnout přílohu stare.pdf" })).toBeNull();
    expect(screen.getByText("1 KB · reference · soubor není uložen v AIA")).toBeTruthy();
  });

  it("runs the analysis as a job, keeps the person's brief, and goes on to the plan", async () => {
    unitStub({ goal: "Zjistit zájem o nový nápoj" });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")), { timeout: 4000 });
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "analyze_brief", design_revision_id: "REV-A" });
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
    expect(posted(DESIGN_PATH)[0].body).toMatchObject({ content: { briefing: { goal: "Zjistit zájem o nový nápoj" } } });
    // The merged project is saved with the classic reason once the debounce runs.
    expect((screen.getByPlaceholderText(/Co chcete zjistit/) as HTMLTextAreaElement).value).toBe("Zjistit zájem o nový nápoj");
  });

  it("requests a frozen native context even when legacy brief signatures match", async () => {
    const project = { goal: "Zjistit zájem" };
    const sig = briefFingerprint(defaultsMerge(project, TEMPLATE));
    unitStub(project, {}, { objectives: ["A"], _brief_signature: sig });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")));
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted(AGENTS_PATH)).toHaveLength(1);
  });

  it("explains the unavailable design capability without obsolete connection settings", async () => {
    unitStub({ goal: "Cíl" }, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · vytvořit návrh/ }));
    expect(await screen.findByText(PARK_MESSAGE, {}, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Otevřít Nastavení/ })).toBeNull();
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(push).not.toHaveBeenCalled();
  });

  it("shows the native failure and keeps the saved brief", async () => {
    unitStub({ goal: "Cíl" }, { "native/job": () => ({ status: "RECOVERY_REQUIRED", is_terminal: false, needs_attention: true, steps: [{ error_message: "MODEL_TIMEOUT: nic se nevrátilo" }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doplní a navrhne výzkum" }));
    expect(await screen.findByText("AI analýza se nedokončila", {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByText("Zadání zůstalo uložené.")).toBeTruthy();
    expect(screen.getByText("MODEL_TIMEOUT: nic se nevrátilo")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Diagnostika" })).toBeNull();
    expect(push).not.toHaveBeenCalled();
  });

  it("refuses an empty brief with the classic message", async () => {
    unitStub({});
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doplní a navrhne výzkum" }));
    expect(await screen.findByText("Nejdřív popište zadání výzkumu.")).toBeTruthy();
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
  });
});
