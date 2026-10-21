// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AGENTS_PATH, NATIVE_TEST_TIMEOUT_MS, approveProposal, findProposalDialog, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";
import { CATALOGUE } from "@/research/audience.live.test";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/audience", useRouter: () => ({ push, replace }) }));

const ANALYTICS = { audience_entry: "analytics", analytics_choice: "cz18" };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
let saves: SavedBody[] = [];
/** The working copy the server wrote on an accept (ADR 0026 decision 6). */
let writes: { content: Record<string, unknown>; analysis: unknown }[] = [];
/** AIA, answering by path: the study's working content and the native agent jobs; nothing else. */
function aiaStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: null });
  saves = ws.saves;
  writes = ws.writes;
  const native = nativeAgentFixture((_action, baseline, instruction) => ({ project: { ...baseline, audience: { ...(baseline.audience as object), description: instruction } }, proposal: { description: instruction, inclusion_criteria: ["Sportují"], limitations: ["Ověřte filtry"] } }), over, ws.write);
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
const saved = () => waitFor(() => expect(saves.length).toBeGreaterThan(0));
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
    fireEvent.click(await screen.findByRole("radio", { name: /Vlastní audience/ }));
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
    // Studio v3: one page; the population is the second question, its three choices side by side.
    fireEvent.click(await screen.findByRole("radio", { name: /Special Audience/ }));
    expect(await screen.findByText(/Profesní a speciální subpanely počítala 18.6.6/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Lékaři/ })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /Česká populace \(\+18\)/ }));
    // The third question appears with the whole population chosen, and the summary says so.
    expect(await screen.findByRole("radio", { name: /Celá ČR 18\+/, checked: true })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Souhrn cílové skupiny" }).textContent).toContain("Česká populace (+18)");
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
    // The server writes the accepted proposal into the working copy; the stage reloads it.
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].content.audience).toMatchObject({ filters: { kraj: ["A"] }, description: "Mladí sportovci", strategy: "filters" });
    expect(saves.some((s) => s.reason === "native_ai_proposal_accepted")).toBe(false);
    noUnitCalls();
  });

  describe("from AIA's population (panel-grounded-respondents 6e)", () => {
    const CAT = "/api/v1/population/audience-catalogue";
    const PREVIEW = "/api/v1/population/audience-preview";
    const live = (extra: Record<string, (b: unknown) => unknown> = {}) => ({ [CAT]: () => CATALOGUE, ...extra });

    it("filters are chosen from the catalogue, an empty bound is no bound, and nothing says 'not in AIA'", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: {} } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      expect(await screen.findByText(/z populace v17_4_0/)).toBeTruthy();
      expect(screen.queryByText("V AIA zatím není")).toBeNull();
      expect(screen.queryByText(/Katalog faktorů společnosti/)).toBeNull();
      fireEvent.click(screen.getByRole("checkbox", { name: /Zlínský kraj/ }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ kraj: ["Zlínský kraj"] });
      const from = screen.getAllByLabelText("Od")[0] as HTMLInputElement;
      fireEvent.change(from, { target: { value: "30" } });
      fireEvent.blur(from);
      await waitFor(() => expect(lastSave().content.audience.filters).toEqual({ kraj: ["Zlínský kraj"], vek: { min: 30 } }));
      // A factor the version's policy refuses is listed, said, and cannot be chosen.
      expect((screen.getByRole("checkbox", { name: /Rodič/ }) as HTMLInputElement).disabled).toBe(true);
      expect(screen.getByText(/unclassified_derived_field/)).toBeTruthy();
      expect(screen.getByText("Vybrané filtry:")).toBeTruthy();
      noUnitCalls();
    });

    it("the preview counts the audience in AIA and says whether n can be drawn", async () => {
      aiaStub(
        { ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { vek: { min: 30, max: 59 } } } },
        live({ [PREVIEW]: () => ({ version_id: "DSV-1", version_label: "v17_4_0", population_rows: 18766, selected_rows: 5120, selected_donors: 1400, filters_applied: { vek: { min: 30, max: 59 } }, audience: { ok: true }, n: 500, sample: { ok: false, reason: "sampling_unrepresentative", message: "x" }, seed: 20261012 }) }),
      );
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.click(await screen.findByRole("button", { name: "Ověřit proveditelnost" }));
      const status = await screen.findByRole("status");
      expect(status.textContent).toContain("Filtry vyberou 5\u00a0120 z 18\u00a0766 lidí populace v17_4_0");
      expect(status.textContent).toMatch(/nebyl reprezentativní/);
      expect(posted(PREVIEW)[0]!.body).toEqual({ filters: { vek: { min: 30, max: 59 } }, n: 500 });
      noUnitCalls();
    });

    it("the preview names what each filter selects alone (AUD3)", async () => {
      const filters = { vek: { min: 30, max: 59 }, kraj: ["Zlínský kraj"] };
      aiaStub(
        { ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters } },
        live({ [PREVIEW]: () => ({ version_id: "DSV-1", version_label: "v17_4_0", population_rows: 18766, selected_rows: 900, selected_donors: 400, filters_applied: { vek: { min: 30, max: 59 }, kraj: { values: ["Zlínský kraj"] } }, per_filter: { vek: 5120, kraj: 1200 }, audience: { ok: true }, n: null, sample: null, seed: 20261012 }) }),
      );
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.click(await screen.findByRole("button", { name: "Ověřit proveditelnost" }));
      const status = await screen.findByRole("status");
      expect(status.textContent).toContain("Filtry vyberou 900 z 18\u00a0766");
      expect(status.textContent).toMatch(/Samotný filtr .+: 5\u00a0120 lidí\./);
      expect(status.textContent).toMatch(/Samotný filtr .+: 1\u00a0200 lidí\./);
      noUnitCalls();
    });

    it("a deployment without the population mounted says the preview is not here", async () => {
      aiaStub(
        { ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: {} } },
        live({ [PREVIEW]: () => new Response(JSON.stringify({ code: "audience_preview_unavailable", message: "no" }), { status: 503 }) }),
      );
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.click(await screen.findByRole("button", { name: "Ověřit proveditelnost" }));
      expect((await screen.findByRole("status")).textContent).toContain("populace k ní není připojená");
    });

    it("a built-in subpanel is chosen as its filter; one the policy refuses cannot be", async () => {
      aiaStub({ ui_state: { audience_entry: "analytics", analytics_choice: "special" } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const young = await screen.findByRole("radio", { name: /Mladí 18–29/ });
      expect((screen.getByRole("radio", { name: /Studenti/ }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.getByText(/Nelze použít: audit_only/)).toBeTruthy();
      expect(screen.getByText(/speciální panely a vlastní publikum stavěla 18.6.6/i)).toBeTruthy();
      fireEvent.click(young);
      await saved();
      expect(lastSave()).toMatchObject({ reason: "population_subpanel", content: { audience: { builtin_subpanel: "young_18_29", source_mode: "population", filters: { vek: [18, 29] } } } });
      await waitFor(() => expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(false));
      noUnitCalls();
    });
  });
});
