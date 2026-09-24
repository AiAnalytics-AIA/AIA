// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetBootCache } from "@/unit/boot";
import { PROPOSE_UNCOVERED, UPLOAD_DONE, resetAudienceCatalog } from "@/unit/research/audience";
import { ResearchScreen, ResearchSession } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/audience", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT = {
  empty_project: EMPTY,
  ai_provider: "claude_code_subscription",
  panel: { version: "v17.1.2" },
  edition: { version: "18.6.6", claude_code_enabled: true },
  audiences: [{ audience_id: "A1", name: "Lékaři ČR", rows: 120, type: "customer", population_definition: "Lékaři v praxi" }],
  population_subpanels: [{ key: "medical_doctors", name: "Lékaři", filter: { profese: ["lékař"] }, status: "ready", support_tier: "LOW" }],
  special_panels: [],
};
const CATALOG = {
  filterable_count: 3,
  categories: [{ id: "demography", label: "Demografie", filterable_count: 3, count: 3 }, { id: "research_only", label: "Research-only", filterable_count: 0, count: 2 }],
  factors: [
    { id: "vek", label: "Věk", category: "demography", category_label: "Demografie", kind: "numeric", status: "PANEL_EXISTING", source: "Panel v17", filterable: true, min: 18, max: 77 },
    { id: "kraj", label: "Kraj", category: "demography", category_label: "Demografie", kind: "category", status: "PANEL_EXISTING", filterable: true, values: [{ value: "A", count: 20 }, { value: "B", count: 40 }] },
  ],
};
const ANALYTICS = { audience_entry: "analytics", analytics_choice: "cz18" };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
function unitStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        "/api/bootstrap": () => BOOT,
        "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 3, project_type: "research", project, analysis: null }),
        "/api/projects/save": () => ({ project_id: "PRJ-1", revision: 4 }),
        "/api/providers/claude-code/status": () => ({ ok: true }),
        "/api/audience/dimensions": () => CATALOG,
        "/api/audience": () => ({ support: 20 }),
        "/api/audience/propose": () => ({ job_id: "JOB-P" }),
        "/api/job": () => ({ state: "done", result: { filtry: { kraj: ["B"] }, feasibility: { ok: true }, nepokryto: "sport" } }),
        "/api/audiences": () => [...BOOT.audiences, { audience_id: "A9", name: "Moje", rows: 90, type: "customer" }],
        "/api/audiences/upload": () => ({ audience: { audience_id: "A9", name: "Moje", description: "Nahraná" }, preflight: { ok: true } }),
        ...over,
      };
      const answer = answers[u.split("?")[0]]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path);
const lastSave = () => posted("/api/projects/save").at(-1)?.body as { project: { audience: Record<string, unknown>; ui_state: Record<string, unknown> }; reason: string };
const saved = () => waitFor(() => expect(posted("/api/projects/save").length).toBeGreaterThan(0), { timeout: 4000 });

beforeEach(() => {
  resetBootCache();
  resetAudienceCatalog();
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Audience", () => {
  it("starts at the two sources, and waits for one before going on", async () => {
    unitStub({});
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Odkud mají respondenti pocházet?" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nejdřív vyberte zdroj audience.")).toBeTruthy();
    expect(screen.getByText(/Zatím není nastaven žádný filtr/)).toBeTruthy();
  });

  it("own audience: the saved ones are offered, and choosing one makes the step ready", async () => {
    unitStub({});
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Vlastní audience/ }));
    const select = await screen.findByLabelText("Uložená audience");
    expect((screen.getByRole("button", { name: "Audience mám → Persony" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(select, { target: { value: "A1" } });
    expect(await screen.findByText("Audience je načtená. Další kroky budou používat tento dataset.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(false);
    await saved();
    expect(lastSave().project.audience).toMatchObject({ source_mode: "customer", dataset_id: "A1", dataset_name: "Lékaři ČR" });
  });

  it("own audience: an upload is sent, the list refreshed, and the new one chosen", async () => {
    unitStub({}, {});
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Vlastní audience/ }));
    const file = (await screen.findByLabelText("Soubor")) as HTMLInputElement;
    if (!Blob.prototype.arrayBuffer) Blob.prototype.arrayBuffer = async function () { return new Uint8Array([65]).buffer; };
    Object.defineProperty(file, "files", { value: [new File(["A"], "moje.csv")] });
    fireEvent.click(screen.getByRole("button", { name: "Nahrát a zkontrolovat" }));
    expect(await screen.findByText(UPLOAD_DONE)).toBeTruthy();
    expect(posted("/api/audiences/upload")[0].body).toMatchObject({ filename: "moje.csv", audience_name: "moje", audience_type: "customer" });
    expect(posted("/api/audiences").length).toBe(1);
    expect(await screen.findByText("Populace je připravená.")).toBeTruthy();
  });

  it("AI Analytics: ČR 18+ is ready at once; a special preset says what was chosen", async () => {
    unitStub({ ui_state: { audience_entry: "analytics" } });
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByText(/= výsledky reprezentují celou dospělou populaci/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /Special Audience/ }));
    fireEvent.click(await screen.findByRole("button", { name: /^Lékaři/ }));
    expect(await screen.findByText("Vybráno:")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Audience AI Analytics" }));
    fireEvent.click(await screen.findByRole("button", { name: /Česká populace \(\+18\)/ }));
    expect(await screen.findByRole("heading", { name: "Česká populace (+18)" })).toBeTruthy();
    await saved();
    expect(lastSave()).toMatchObject({ reason: "audience_strategy", project: { audience: { strategy: "population", filters: {}, description: "ČR 18+" } } });
  });

  it("narrows by a factor: the value, a preview, the chip and the readable summary", async () => {
    unitStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: {} } });
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    const kraj = (await screen.findByLabelText("Kraj")) as HTMLSelectElement;
    within(kraj).getByRole("option", { name: "B (40)" }).setAttribute("selected", "");
    (within(kraj).getByRole("option", { name: "B (40)" }) as HTMLOptionElement).selected = true;
    fireEvent.change(kraj);
    await waitFor(() => expect(posted("/api/audience").at(-1)?.body).toEqual({ filtry: { kraj: ["B"] }, n: 300 }));
    expect(await screen.findByText("Populace je připravená.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Odebrat filtr Kraj" })).toBeTruthy();
    expect(screen.getAllByText(/Research-only|2 research-only signálů/).length).toBeGreaterThan(0);
  });

  it("an empty upper bound is stored as 0, as the classic reads it (OI-50)", async () => {
    unitStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: {} } });
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("od 18"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Použít interval" }));
    await waitFor(() => expect(posted("/api/audience").at(-1)?.body).toEqual({ filtry: { vek: { min: 25, max: 0 } }, n: 300 }));
    // The summary prints the range as the chips do; the classic summary prints "[object Object]".
    expect(await screen.findAllByText("25–0")).toBeTruthy();
  });

  it("proposes filters with AI: the model's filters replace the project's, with the classic note", async () => {
    unitStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: { kraj: ["A"] }, description: "Zúžená cílová populace" } });
    render(<ResearchScreen projectId="PRJ-1" step="audience" frame={TEST_FRAME} />);
    const input = await screen.findByPlaceholderText(/např. 25–44/);
    fireEvent.change(input, { target: { value: "Mladí sportovci" } });
    fireEvent.click(screen.getByRole("button", { name: "AI: převést na dostupné filtry" }));
    expect(await screen.findByText(PROPOSE_UNCOVERED, {}, { timeout: 4000 })).toBeTruthy();
    expect(posted("/api/audience/propose")[0].body).toMatchObject({ popis: "Mladí sportovci", model: "sonnet", project_id: "PRJ-1" });
    await saved();
    expect(lastSave().project.audience).toMatchObject({ filters: { kraj: ["B"] }, description: "Mladí sportovci", strategy: "filters" });
  });

  it("keeps the preview while the person moves between steps, as the classic page does", async () => {
    unitStub({ ui_state: ANALYTICS });
    const page = (step: "audience" | "run") => (
      <ResearchSession projectId="PRJ-1">
        <ResearchScreen key={step} projectId="PRJ-1" step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(page("audience"));
    const card = (await screen.findByRole("button", { name: "Audience mám → Persony" })).closest("section") as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Zkontrolovat audience" }));
    expect(await screen.findByText("Populace je připravená.")).toBeTruthy();
    rerender(page("run"));
    await screen.findByRole("heading", { name: "6. Finální kontrola & spuštění" });
    rerender(page("audience"));
    expect(await screen.findByText("Populace je připravená.")).toBeTruthy();
    expect(posted("/api/audience").length).toBe(1);
  });
});
