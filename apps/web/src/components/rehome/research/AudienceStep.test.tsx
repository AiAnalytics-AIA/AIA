// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AGENTS_PATH, NATIVE_TEST_TIMEOUT_MS, approveProposal, findProposalDialog, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/audience", useRouter: () => ({ push, replace }) }));

const ANALYTICS = { audience_entry: "analytics", analytics_choice: "cz18" };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
let saves: SavedBody[] = [];
/** AIA, answering by path: the study's working content and the native agent jobs; nothing else. */
function aiaStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: null });
  saves = ws.saves;
  const native = nativeAgentFixture((_action, baseline, instruction) => ({ project: { ...baseline, audience: { ...(baseline.audience as object), description: instruction } }, proposal: { description: instruction, inclusion_criteria: ["Sportují"], limitations: ["Ověřte filtry"] } }), over);
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
const lastSave = () => saves.at(-1) as unknown as { content: { audience: Record<string, unknown>; ui_state: Record<string, unknown> }; reason: string };
const saved = () => waitFor(() => expect(saves.length).toBeGreaterThan(0), { timeout: 4000 });
/** Nothing the audience step does reaches the 18.6.6 unit (ADR 0018). */
const noUnitCalls = () => expect(calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url)).toEqual([]);

beforeEach(() => {
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Audience", () => {
  it("starts at the two sources, and waits for one before going on", async () => {
    aiaStub({});
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Odkud mají respondenti pocházet?" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nejdřív vyberte zdroj audience.")).toBeTruthy();
    expect(screen.getByText(/Zatím není nastaven žádný filtr/)).toBeTruthy();
    noUnitCalls();
  });

  it("own audience says it is not in AIA, and the step waits for another source", async () => {
    aiaStub({});
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Vlastní audience/ }));
    expect(await screen.findByText(/Nahrání, kontrolu a preflight vlastního datasetu dělala 18.6.6/)).toBeTruthy();
    expect(screen.getAllByText("V AIA zatím není").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("Soubor")).toBeNull();
    expect(screen.queryByText("Stáhnout XLSX šablonu")).toBeNull();
    expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(true);
    noUnitCalls();
  });

  it("a dataset a study already chose stays visible, and says the run will not use it", async () => {
    aiaStub({ ui_state: { audience_entry: "own" }, audience: { source_mode: "customer", dataset_id: "A1", dataset_name: "Lékaři ČR" } });
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    expect((await screen.findByText("Uložený dataset:")).parentElement?.textContent).toBe("Uložený dataset: Lékaři ČR");
    expect(screen.getAllByText("Zůstává v návrhu studie, ale běh v AIA ho nepoužije.").length).toBe(1);
    noUnitCalls();
  });

  it("AI Analytics: ČR 18+ is ready at once; Special Audience says it is not in AIA", async () => {
    aiaStub({ ui_state: { audience_entry: "analytics" } });
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByText(/= výsledky reprezentují celou dospělou populaci/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /Special Audience/ }));
    expect(await screen.findByText(/Profesní a speciální subpanely počítala 18.6.6/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Lékaři/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Audience AI Analytics" }));
    fireEvent.click(await screen.findByRole("button", { name: /Česká populace \(\+18\)/ }));
    expect(await screen.findByRole("heading", { name: "Česká populace (+18)" })).toBeTruthy();
    await saved();
    expect(lastSave()).toMatchObject({ reason: "audience_strategy", content: { audience: { strategy: "population", filters: {}, description: "ČR 18+" } } });
    // No preview: 18.6.6 counted the audience in its panel; the screen says so.
    expect(screen.queryByRole("button", { name: "Zkontrolovat audience" })).toBeNull();
    expect(screen.getAllByText(/Kontrolu proveditelnosti počítala 18.6.6/).length).toBeGreaterThan(0);
    noUnitCalls();
  });

  it("filters: not in AIA; the ones a study stores stay visible and removable", async () => {
    aiaStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: { kraj: ["B"], vek: { min: 25, max: 0 } } } });
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Katalog faktorů společnosti, jejich hodnoty a počty byly z licencovaného panelu 18.6.6/)).toBeTruthy();
    expect(screen.getByText("Filtry uložené ve studii (běh v AIA je nepoužije):")).toBeTruthy();
    // The summary prints the stored range as the chips do (OI-50's 0 kept as stored).
    expect(screen.getAllByText("25–0").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat filtr kraj" }));
    await saved();
    expect(lastSave().content.audience.filters).toEqual({ vek: { min: 25, max: 0 } });
    noUnitCalls();
  });

  it("reviews an audience proposal while preserving researcher-controlled filters", async () => {
    aiaStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: { kraj: ["A"] }, description: "Zúžená cílová populace" } });
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    const input = await screen.findByPlaceholderText(/např. 25–44/);
    fireEvent.change(input, { target: { value: "Mladí sportovci" } });
    fireEvent.click(screen.getByRole("button", { name: "AI: navrhnout cílovou skupinu" }));
    await findProposalDialog();
    expect(lastSave().content.audience.filters).toEqual({ kraj: ["A"] });
    await approveProposal();
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "propose_audience", instruction: "Mladí sportovci" });
    await saved();
    expect(lastSave().content.audience).toMatchObject({ filters: { kraj: ["A"] }, description: "Mladí sportovci", strategy: "filters" });
    noUnitCalls();
  });
});
