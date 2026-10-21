// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, DESIGN_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { LINK_INVALID } from "@/research/brief";
import { briefTarget, briefTargets } from "@/lib/artifacts/brief";
import { focusSelector, targetOfElement } from "@/lib/lead";
import { PROBLEM_TYPES, type ResearchProject, briefFingerprint, defaultsMerge } from "@/research/model";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

/** The step's one analysis action, in its dock (Studio v3). */
const NEXT = /Vytvořit návrh s AI/;

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
  const native = nativeAgentFixture((_action, baseline) => ({ project: { ...baseline, research_plan: { status: "analyzed", objectives: ["Změřit zájem"] } }, proposal: { objectives: ["Změřit zájem"] }, analysis: { objectives: ["Změřit zájem"] } }), over, ws.write);
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
    // Studio v3: four numbered sections, the readiness panel beside them.
    expect(await screen.findByRole("heading", { name: "Co potřebujete zjistit a rozhodnout?" })).toBeTruthy();
    const types = screen.getByRole("group", { name: "Typ problému" });
    for (const [, label] of PROBLEM_TYPES) expect(within(types).getByRole("button", { name: new RegExp(label.replace(/[/()]/g, ".")) })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^Podklady/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^Kontext, který zpřesní návrh/ })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Připravenost zadání" }).textContent).toContain("0 %");
    // The empty project's title shows as an empty field, as in the classic screen.
    expect((screen.getByPlaceholderText("Např. Nové balení produktu") as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("button", { name: NEXT }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Napište cíl, nebo co přesně zkoumáme")).toBeTruthy();
  });

  it("a problem type is a toggle that fills an empty goal with its default", async () => {
    unitStub({});
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const tile = await screen.findByRole("button", { name: /Nový produkt \/ koncept/ });
    fireEvent.click(tile);
    // The tile can be on screen before the store's subscription effect has run;
    // a click then renders when it subscribes, not synchronously (AGENTS.md § Next.js / TypeScript).
    await screen.findByRole("button", { name: /Nový produkt \/ koncept/, pressed: true });
    const goal = screen.getByLabelText("Cíl výzkumu") as HTMLTextAreaElement;
    expect(goal.value).toBe(PROBLEM_TYPES[1][3]);
    expect((screen.getByRole("button", { name: NEXT }) as HTMLButtonElement).disabled).toBe(false);
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
    fireEvent.click(screen.getByRole("button", { name: "Odebrat https://example.test/a" }));
    expect(screen.queryByText("https://example.test/a")).toBeNull();
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
    // A file shows while it is on its way, and its stored detail once AIA has it.
    expect(await screen.findByText("zadani.txt")).toBeTruthy();
    expect(await screen.findByText("2 KB · text načten")).toBeTruthy();
    expect(posted(ATTACH_PATH).map((c) => c.body)).toEqual([{ filename: "zadani.txt", data_b64: btoa("ahoj") }]);
    // Nothing reaches 18.6.6.
    expect(calls.filter((c) => c.url.startsWith("/api/project"))).toEqual([]);
    await waitFor(() => expect(ws.saves.at(-1)?.reason).toBe("brief_attachments"));
    expect((ws.saves.at(-1)?.content.briefing as { attachments: unknown[] }).attachments).toEqual([record({ filename: "zadani.txt" })]);
  });

  it("saves a study that was never saved before its first file, so the file has somewhere to be", async () => {
    unitStub(null, { [ATTACH_PATH]: (b) => record(b) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Soubory k zadání"), { target: { files: [new File(["ahoj"], "zadani.txt")] } });
    await waitFor(() => expect(posted(ATTACH_PATH)).toHaveLength(1));
    const order = calls.filter((c) => c.body !== null && (c.url === ATTACH_PATH || c.url.endsWith("/workspace/content"))).map((c) => c.url.split("/").at(-1));
    expect(order[0]).toBe("content");
    expect(order[1]).toBe("attachments");
    expect(ws.saves[0]).toMatchObject({ base_revision: null, reason: "brief_attachments" });
  });

  it("has exactly one element for every target its contract names, and @ reads each back (BRF1)", async () => {
    const project = {
      title: "Studie",
      goal: "Chceme zjistit, jak lidé vnímají značku.",
      decision_use: "Rozhodneme o kampani",
      briefing: {
        situation: "Trh roste",
        attachments: [record({ filename: "a.txt" }), record({ filename: "b.txt" }, 2), { kind: "url", url: "https://example.org/a", title: "A" }, record({ filename: "a.txt" })],
      },
    };
    unitStub(project);
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    await screen.findByText("b.txt");
    const targets = briefTargets(project as unknown as ResearchProject);
    expect(targets).toContain("brief:briefing.situation");
    expect(targets).toContain("brief:briefing.constraints");
    expect(targets.filter((x) => x.startsWith("material:"))).toHaveLength(2);
    for (const target of targets) {
      const found = document.querySelectorAll(focusSelector(target));
      expect(found, target).toHaveLength(1);
      expect(targetOfElement(found[0]!)?.id, target).toBe(target);
    }
    // Each field's row carries the name, with the field edited in place inside it, empty or not.
    expect(within(document.getElementById("brief-briefing.situation")!).getByRole("button", { name: /^Upravit: Situace \/ trh/ })).toBeTruthy();
    expect(within(document.getElementById("brief-briefing.constraints")!).getByRole("button", { name: /^Upravit: Omezení/ })).toBeTruthy();
    // A target the contract does not name finds nothing on the screen.
    expect(briefTarget("brief:situation")).toBeNull();
    expect(document.querySelectorAll(focusSelector("brief:situation"))).toHaveLength(0);
  });

  it("edits the objectives in place: one item's words change, Esc restores, add and remove with Vrátit (BRF2)", async () => {
    const analysis = { problem_summary: "S", objectives: ["Změřit zájem", "Porovnat značky"], research_questions: [], hypotheses: [], tracked_sets: [] };
    unitStub({ title: "Studie", goal: "Chceme zjistit, jak lidé vnímají značku.", research_plan: { objectives: ["Změřit zájem", "Porovnat značky"] } }, {}, analysis);
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const section = within(await screen.findByRole("region", { name: "Cíle" }));
    // Each objective is a Lead target, found once, read back by @.
    const items = document.querySelectorAll("[data-aia^='objective:']");
    expect(items).toHaveLength(2);
    for (const el of items) expect(targetOfElement(el)?.id).toBe(el.getAttribute("data-aia"));

    // Esc restores and sends nothing.
    fireEvent.click(section.getByRole("button", { name: /^Upravit: Cíl 2/ }));
    fireEvent.change(section.getByRole("textbox", { name: "Cíl 2" }), { target: { value: "Něco jiného" } });
    fireEvent.keyDown(section.getByRole("textbox", { name: "Cíl 2" }), { key: "Escape" });
    expect(section.getByText("Porovnat značky")).toBeTruthy();

    // A reword changes that item only, in the plan and the analysis alike.
    fireEvent.click(section.getByRole("button", { name: /^Upravit: Cíl 2/ }));
    fireEvent.change(section.getByRole("textbox", { name: "Cíl 2" }), { target: { value: "Porovnat tři značky" } });
    fireEvent.keyDown(section.getByRole("textbox", { name: "Cíl 2" }), { key: "Enter", ctrlKey: true });
    await waitFor(() => expect(ws.saves.at(-1)?.reason).toBe("brief_objective"), { timeout: 10_000 });
    const saved = ws.saves.at(-1)!;
    expect((saved.content.research_plan as { objectives: string[] }).objectives).toEqual(["Změřit zájem", "Porovnat tři značky"]);
    expect((saved.analysis as { objectives: string[] }).objectives).toEqual(["Změřit zájem", "Porovnat tři značky"]);
    expect(saved.content.goal).toBe("Chceme zjistit, jak lidé vnímají značku.");

    // Added in the list.
    fireEvent.click(section.getByRole("button", { name: "Přidat cíl" }));
    const row = section.getByRole("textbox", { name: "Přidat cíl" });
    fireEvent.change(row, { target: { value: "Najít bariéry" } });
    fireEvent.keyDown(row, { key: "Enter" });
    expect(await section.findByText("Najít bariéry")).toBeTruthy();

    // Removed at once, and put back in place by Vrátit.
    fireEvent.click(section.getByRole("button", { name: "Odebrat cíl 1" }));
    expect(section.queryByText("Změřit zájem")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(await section.findByText("Změřit zájem")).toBeTruthy();
    // Back where it was: first again.
    expect(document.querySelector("[data-aia^='objective:']")?.textContent).toContain("Změřit zájem");
  });

  it("says Zatím prázdné when no objectives are stated, never the goal in their place (BRF2)", async () => {
    unitStub({ title: "Studie", goal: "Chceme zjistit, jak lidé vnímají značku." });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const section = within(await screen.findByRole("region", { name: "Cíle" }));
    expect(section.getByText(/^Zatím prázdné/)).toBeTruthy();
    expect(section.queryByText("Chceme zjistit, jak lidé vnímají značku.")).toBeNull();
    expect(document.querySelectorAll("[data-aia^='objective:']")).toHaveLength(0);
  });

  it("prints each material's class as the server answers it, and unknown when it names none (BRF3)", async () => {
    const B = { data_class: "CLASS_B_DERIVED_CLIENT", class_source: "rule:design" };
    unitStub(
      { briefing: { attachments: [record({ filename: "zadani.txt" }), { kind: "url", url: "https://example.org/a", title: "A" }, { kind: "url", url: "https://example.org/b", title: "B" }] } },
      {
        "/api/v1/studies/STU-1/workspace/materials": () => ({
          revision: 1,
          materials: [
            { index: 0, kind: "file", ref: "ART-1a", ...B },
            { index: 1, kind: "url", ref: "https://example.org/a", ...B },
            { index: 2, kind: "url", ref: "https://example.org/b", data_class: null, class_source: null },
          ],
        }),
      },
    );
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const chips = await screen.findAllByText("B · odvozené od klienta");
    expect(chips).toHaveLength(2);
    expect(chips[0].getAttribute("title")).toBe("Třída podle pravidla rule:design; přísněji ji může zařadit jen operátor.");
    expect(screen.getByText("třída neznámá").getAttribute("data-data-class")).toBe("unknown");
    expect(screen.getByText(/třída dat určuje, kam smí/)).toBeTruthy();
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
    expect(new TextDecoder().decode(await created[0].arrayBuffer())).toBe("ahoj");
    expect(calls.map((c) => c.url)).toContain(`${ATTACH_PATH}/ART-1a`);
    // A record whose file never came into AIA offers no download, and says why.
    expect(screen.queryByRole("button", { name: "Stáhnout přílohu stare.pdf" })).toBeNull();
    expect(screen.getByText("1 KB · reference · soubor není uložen v AIA")).toBeTruthy();
  });

  it("runs the analysis as a job, keeps the person's brief, and goes on to the plan", async () => {
    unitStub({ goal: "Zjistit zájem o nový nápoj" });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }));
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")));
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "analyze_brief", design_revision_id: "REV-A" });
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
    expect(posted(DESIGN_PATH)[0].body).toMatchObject({ content: { briefing: { goal: "Zjistit zájem o nový nápoj" } } });
    // The merged project is saved with the classic reason once the debounce runs.
    expect((screen.getByLabelText("Cíl výzkumu") as HTMLTextAreaElement).value).toBe("Zjistit zájem o nový nápoj");
  });

  it("goes on to the plan once an analysis that waited for budget is lifted and accepted, asking nothing again (CR-2, Codex on #533)", async () => {
    let lifted = false;
    const waiting = { run_id: "RUN-A", design_revision_id: "REV-A", action: "analyze_brief", status: "AWAITING_BUDGET", is_terminal: false, needs_attention: true,
      steps: [{ step_id: "STEP-A", node_key: "agent", status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", error_message: null }],
      created_at: null, context_sha256: "sha", harness_version: "v1", actual_cost_usd: null };
    unitStub({ goal: "Zjistit zájem o nový nápoj" }, {
      "native/job": () => (lifted ? undefined : waiting),
      [`${AGENTS_PATH}/RUN-A/budget`]: () => { lifted = true; return { ...waiting, status: "RUNNING", steps: [{ ...waiting.steps[0], status: "RUNNABLE" }] }; },
      "/api/v1/studies/STU-1": () => ({ study_id: "STU-1", name: "Alfa", budget_usd: 5, spent_usd: 5, remaining_usd: 0 }),
    });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }, NATIVE_JOB_WAIT));
    const form = await screen.findByRole("form", { name: "Zvýšit rozpočet studie" }, NATIVE_JOB_WAIT);
    expect(screen.queryByRole("button", { name: "Zkusit znovu" })).toBeNull();
    await within(form).findByText(/5\.00/);
    fireEvent.change(within(form).getByLabelText("Nový rozpočet studie (USD)"), { target: { value: "7" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zvýšit rozpočet a pokračovat" }));
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")), NATIVE_JOB_WAIT);
    // One analysis, continued: never a second job for the one that waited.
    expect(posted(AGENTS_PATH)).toHaveLength(1);
    expect(posted(`${AGENTS_PATH}/RUN-A/budget`).map((c) => c.body)).toEqual([{ budget_usd: 7, note: "" }]);
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("offers to follow the lifted analysis again when following it breaks off, never a retry that starts a new one (review P3-2)", async () => {
    let lifted = false;
    let broken = 1; // the first read after the lift fails
    const waiting = { run_id: "RUN-A", design_revision_id: "REV-A", action: "analyze_brief", status: "AWAITING_BUDGET", is_terminal: false, needs_attention: true,
      steps: [{ step_id: "STEP-A", node_key: "agent", status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", error_message: null }],
      created_at: null, context_sha256: "sha", harness_version: "v1", actual_cost_usd: null };
    unitStub({ goal: "Zjistit zájem o nový nápoj" }, {
      "native/job": () => {
        if (!lifted) return waiting;
        if (broken-- > 0) return new Response(JSON.stringify({ code: "unavailable", message: "Spojení se přerušilo." }), { status: 503 });
        return undefined; // completed
      },
      [`${AGENTS_PATH}/RUN-A/budget`]: () => { lifted = true; return { ...waiting, status: "RUNNING", steps: [{ ...waiting.steps[0], status: "RUNNABLE" }] }; },
      "/api/v1/studies/STU-1": () => ({ study_id: "STU-1", name: "Alfa", budget_usd: 5, spent_usd: 5, remaining_usd: 0 }),
    });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }, NATIVE_JOB_WAIT));
    const form = await screen.findByRole("form", { name: "Zvýšit rozpočet studie" }, NATIVE_JOB_WAIT);
    await within(form).findByText(/5\.00/);
    fireEvent.change(within(form).getByLabelText("Nový rozpočet studie (USD)"), { target: { value: "7" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zvýšit rozpočet a pokračovat" }));
    const again = await screen.findByRole("button", { name: "Sledovat znovu" }, NATIVE_JOB_WAIT);
    expect(screen.getByText("Spojení se přerušilo.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Zkusit znovu" })).toBeNull();
    fireEvent.click(again);
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")), NATIVE_JOB_WAIT);
    // The same analysis, followed twice: one job, one lift, nothing started anew.
    expect(posted(AGENTS_PATH)).toHaveLength(1);
    expect(posted(`${AGENTS_PATH}/RUN-A/budget`)).toHaveLength(1);
  });

  it("requests a frozen native context even when legacy brief signatures match", async () => {
    const project = { goal: "Zjistit zájem" };
    const sig = briefFingerprint(defaultsMerge(project, TEMPLATE));
    unitStub(project, {}, { objectives: ["A"], _brief_signature: sig });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }));
    await approveProposal();
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("plan")));
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted(AGENTS_PATH)).toHaveLength(1);
  });

  it("explains the unavailable design capability without obsolete connection settings", async () => {
    unitStub({ goal: "Cíl" }, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }));
    expect(await screen.findByText(PARK_MESSAGE, {}, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Otevřít Nastavení/ })).toBeNull();
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(push).not.toHaveBeenCalled();
  });

  it("shows the native failure and keeps the saved brief", async () => {
    unitStub({ goal: "Cíl" }, { "native/job": () => ({ status: "RECOVERY_REQUIRED", is_terminal: false, needs_attention: true, steps: [{ error_message: "MODEL_TIMEOUT: nic se nevrátilo" }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: NEXT }));
    expect(await screen.findByText("AI analýza se nedokončila")).toBeTruthy();
    expect(screen.getByText("Zadání zůstalo uložené.")).toBeTruthy();
    expect(screen.getByText("MODEL_TIMEOUT: nic se nevrátilo")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Diagnostika" })).toBeNull();
    expect(push).not.toHaveBeenCalled();
  });

  it("does not start the analysis of an empty brief, and says what is missing", async () => {
    // Studio v3 keeps one analysis action, in the dock, under the classic button's
    // condition (canAnalyse); the duplicate that let an empty brief be refused is gone.
    unitStub({});
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const next = (await screen.findByRole("button", { name: NEXT })) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    expect(next.getAttribute("data-ai-action")).toBe("true");
    fireEvent.click(next);
    expect(screen.getByText("Napište cíl, nebo co přesně zkoumáme")).toBeTruthy();
    expect(posted(AGENTS_PATH)).toEqual([]);
  });

  it("starts the goal with a sentence, and suggests a title from it", async () => {
    unitStub({});
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Chceme zjistit, jak…" }));
    const goal = (await screen.findByDisplayValue("Chceme zjistit, jak", { exact: false })) as HTMLTextAreaElement;
    fireEvent.change(goal, { target: { value: "Chceme zjistit, jak lidé vnímají novou kampaň banky. Výsledek použijeme." } });
    expect(await screen.findAllByText("72 znaků")).toHaveLength(2); // the counter and the readiness row
    fireEvent.click(screen.getByRole("button", { name: "Navrhnout z cíle" }));
    expect(await screen.findByDisplayValue("Lidé vnímají novou kampaň banky")).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Připravenost zadání" }).textContent).toContain("25 %");
  });

  it("edits Rozhodnutí and each Kontext field in place: Esc restores, a reword saves, clearing saves empty (BRF2)", async () => {
    unitStub({ decision_use: "Kampaň A, nebo B", briefing: { situation: "Konkurence zlevňuje" } });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const decision = within(await screen.findByRole("region", { name: "Rozhodnutí, které má výzkum podpořit" }));
    const context = within(screen.getByRole("region", { name: /^Kontext/ }));
    // Every field is shown, an empty one with its example; nothing waits behind a chip.
    expect(context.getByRole("button", { name: /^Upravit: Situace \/ trh/ }).textContent).toContain("Konkurence zlevňuje");
    expect(context.getByRole("button", { name: /^Upravit: Omezení/ }).textContent).toMatch(/Např\./);

    // Esc restores and saves nothing.
    fireEvent.click(decision.getByRole("button", { name: /^Upravit: Jaké rozhodnutí uděláte/ }));
    fireEvent.change(decision.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }), { target: { value: "Jinak" } });
    fireEvent.keyDown(decision.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }), { key: "Escape" });
    expect(decision.getByText("Kampaň A, nebo B")).toBeTruthy();

    // A reword is saved where the Lead's edits write it.
    fireEvent.click(decision.getByRole("button", { name: /^Upravit: Jaké rozhodnutí uděláte/ }));
    fireEvent.change(decision.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }), { target: { value: "Kampaň B" } });
    fireEvent.keyDown(decision.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }), { key: "Enter", ctrlKey: true });
    await waitFor(() => expect(ws.saves.at(-1)?.content.decision_use).toBe("Kampaň B"));

    // Clearing a context field is an edit like any other: it saves empty.
    fireEvent.click(context.getByRole("button", { name: /^Upravit: Situace \/ trh/ }));
    fireEvent.change(context.getByRole("textbox", { name: "Situace / trh" }), { target: { value: "" } });
    fireEvent.keyDown(context.getByRole("textbox", { name: "Situace / trh" }), { key: "Enter", ctrlKey: true });
    await waitFor(() => expect((ws.saves.at(-1)?.content.briefing as { situation?: string })?.situation).toBe(""));
  });

  it("takes files dropped anywhere on the stage the way it takes picked ones", async () => {
    unitStub({}, { [ATTACH_PATH]: (b) => record(b) });
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    // Dropped on the goal, far from the files section (research-lane-redesign).
    const goal = await screen.findByLabelText("Cíl výzkumu");
    fireEvent.drop(goal, { dataTransfer: { files: [new File(["ahoj"], "zadani.txt", { type: "text/plain" })], types: ["Files"] } });
    expect(await screen.findByText("2 KB · text načten")).toBeTruthy();
    expect(posted(ATTACH_PATH).map((c) => c.body)).toEqual([{ filename: "zadani.txt", data_b64: btoa("ahoj") }]);
  });
});
