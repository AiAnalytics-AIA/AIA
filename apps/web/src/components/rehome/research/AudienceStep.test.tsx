// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AGENTS_PATH, NATIVE_TEST_TIMEOUT_MS, approveProposal, findProposalDialog, nativeAgentFixture } from "./test-native-agents";
import { FrameNavigation } from "../step";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";
import { CATALOGUE } from "@/research/audience.live.test";
import { focusSelector } from "@/lib/lead";
import { audienceTargets } from "@/lib/artifacts/audience";
import type { ResearchProject } from "@/research/model";

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
    expect(await screen.findByText(/Nahrání a kontrolu vlastního datasetu dělala 18.6.6/)).toBeTruthy();
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

  it("inside the workbench goes on to Dimenze through the frame's next stage", async () => {
    aiaStub({ ui_state: { audience_entry: "analytics" } });
    const go = vi.fn();
    render(<FrameNavigation.Provider value={{ next: { label: "Dimenze", go } }}><ResearchScreen step="audience" frame={TEST_FRAME} /></FrameNavigation.Provider>);
    fireEvent.click(await screen.findByRole("radio", { name: /Česká populace \(\+18\)/ }));
    const next = await screen.findByRole("button", { name: /Další · dimenze/ });
    await waitFor(() => expect((next as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(next);
    expect(go).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("AI Analytics: ČR 18+ is ready at once; Speciální skupiny say they are not in AIA", async () => {
    aiaStub({ ui_state: { audience_entry: "analytics" } });
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    expect(await screen.findByText(/= výsledky reprezentují celou dospělou populaci/)).toBeTruthy();
    // Studio v3: one page; the population is the second question, its three choices side by side.
    fireEvent.click(await screen.findByRole("radio", { name: /Speciální skupiny/ }));
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
      fireEvent.click(screen.getByRole("button", { name: /Zlínský kraj/ }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ kraj: ["Zlínský kraj"] });
      const from = screen.getByRole("spinbutton", { name: "Věk od" });
      fireEvent.change(from, { target: { value: "30" } });
      fireEvent.blur(from);
      await waitFor(() => expect(lastSave().content.audience.filters).toEqual({ kraj: ["Zlínský kraj"], vek: { min: 30 } }));
      // A factor the version's policy refuses is listed, said, and cannot be chosen.
      expect((screen.getByRole("button", { name: /Rodič/ }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.getByText(/unclassified_derived_field/)).toBeTruthy();
      expect(screen.getByText("Vybrané filtry:")).toBeTruthy();
      noUnitCalls();
    });

    it("a numeric factor's range is two steppers within the population's range: nothing out of it saved, no end crossed, an end cleared by its own button (audit B6)", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { vek: { min: 30, max: 59 } } } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const from = await screen.findByRole("spinbutton", { name: "Věk od" });
      const to = screen.getByRole("spinbutton", { name: "Věk do" });
      expect([from.getAttribute("aria-valuemin"), from.getAttribute("aria-valuemax")]).toEqual(["18", "59"]);
      expect([to.getAttribute("aria-valuemin"), to.getAttribute("aria-valuemax")]).toEqual(["30", "89"]);
      expect(screen.getByText("Rozsah v populaci 18–89. Od nesmí být víc než Do.")).toBeTruthy();
      // Above the population's range: said at the field, nothing saved, never clamped to 89.
      fireEvent.change(to, { target: { value: "200" } });
      fireEvent.blur(to);
      expect(to.getAttribute("aria-invalid")).toBe("true");
      // Below the other end: refused, never swapped as the server would.
      fireEvent.change(from, { target: { value: "70" } });
      fireEvent.blur(from);
      expect(from.getAttribute("aria-invalid")).toBe("true");
      await new Promise((r) => setTimeout(r, 50));
      expect(saves).toHaveLength(0);
      // An end set back to the population's own: left out of the stored filter.
      fireEvent.click(screen.getByRole("button", { name: "Bez omezení: zrušit mez Věk do" }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ vek: { min: 30 } });
      // The cleared end is empty and says so; the refused 200 is gone with it.
      await waitFor(() => expect((screen.getByRole("spinbutton", { name: "Věk do" }) as HTMLInputElement).value).toBe(""));
      expect(screen.queryByRole("button", { name: "Bez omezení: zrušit mez Věk do" })).toBeNull();
      expect(screen.getByRole("spinbutton", { name: "Věk do" }).getAttribute("aria-invalid")).toBeNull();
      expect(screen.getAllByText("Bez omezení").map((e) => e.tagName)).toEqual(["BUTTON", "SPAN"]);
      // The other end's refused 70 went with the bound it was refused against: Od may now reach 89.
      const fromNow = screen.getByRole("spinbutton", { name: "Věk od" });
      expect(fromNow.getAttribute("aria-invalid")).toBeNull();
      expect((fromNow as HTMLInputElement).value).toBe("30");
      expect(fromNow.getAttribute("aria-valuemax")).toBe("89");
      noUnitCalls();
    });

    it("shows a stored bare number as both ends, as the population reads it, and keeps it when one end moves", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { vek: 40 } } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const from = await screen.findByRole("spinbutton", { name: "Věk od" });
      const to = screen.getByRole("spinbutton", { name: "Věk do" });
      expect([(from as HTMLInputElement).value, (to as HTMLInputElement).value]).toEqual(["40", "40"]);
      fireEvent.change(from, { target: { value: "30" } });
      fireEvent.blur(from);
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ vek: { min: 30, max: 40 } });
      noUnitCalls();
    });

    it("says a stored end the population cannot read, and keeps a stored end beyond the population inside it", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { vek: { min: "abc", max: 99 } } } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const from = await screen.findByRole("spinbutton", { name: "Věk od" });
      expect((from as HTMLInputElement).value).toBe("");
      expect(screen.getByText("Uložená mez není číslo a populace ji nepřečte; nastavte ji znovu.")).toBeTruthy();
      // 99 is stored; Od is still bounded by the population's 89, never by 99.
      expect(from.getAttribute("aria-valuemax")).toBe("89");
      noUnitCalls();
    });

    it("a factor's group is chosen from chips, its values are toggle chips with counts, many of them under a filter (audit B7, B8)", async () => {
      const many = { ...CATALOGUE.factors[1]!, id: "obec", column: "obec", label: "Obec", values: Array.from({ length: 20 }, (_, i) => ({ value: `Obec ${i + 1}`, count: 100 - i })) };
      const catalogue = { ...CATALOGUE, factors: [...CATALOGUE.factors, many] };
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { obec: ["Zaniklá obec"] } } }, { [CAT]: () => catalogue });
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      // B8: the groups are one radio group, the chosen one checked.
      const groups = await screen.findByRole("radiogroup", { name: "Skupina faktorů" });
      expect(within(groups).getByRole("radio", { name: "Demografie a životní fáze" }).getAttribute("aria-checked")).toBe("true");
      // B7: Kraj's few values are toggles with how many people hold each.
      const zlin = screen.getByRole("button", { name: /Zlínský kraj/ });
      expect(zlin.getAttribute("aria-pressed")).toBe("false");
      expect(zlin.textContent).toMatch(/\(\d[\d\s\u00a0]* lidí\)/);
      // Twenty values: the same chips under a filter field; a stored value not on screen is kept.
      const obec = screen.getByRole("group", { name: "Hodnoty: Obec" });
      expect(within(obec).getAllByRole("button")).toHaveLength(20);
      fireEvent.change(screen.getByLabelText("Hledat hodnotu: Obec"), { target: { value: "obec 2" } });
      expect(within(obec).getAllByRole("button").map((b) => b.textContent!.split("(")[0])).toEqual(["Obec 2", "Obec 20"]);
      expect(screen.getByText("Zobrazeno 2 z 20 hodnot.")).toBeTruthy();
      expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
      fireEvent.click(within(obec).getByRole("button", { name: /Obec 20/ }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ obec: ["Zaniklá obec", "Obec 20"] });
      noUnitCalls();
    });

    it("a toggle keeps a stored value that is not text as stored", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { kraj: [true, "Zlínský kraj"] } } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.click(await screen.findByRole("button", { name: /Hlavní město Praha/ }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ kraj: [true, "Zlínský kraj", "Hlavní město Praha"] });
      noUnitCalls();
    });

    it("Discover's product and success criterion are edited in place: leaving saves, Esc restores (audit B11)", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "discover", source_mode: "population", success_definition: "Koupí za 220 Kč" } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const SUCCESS = "Co má ideální člověk udělat / jak poznáme úspěch?";
      fireEvent.click(await screen.findByRole("button", { name: new RegExp(`${SUCCESS.replace(/[?/]/g, "\\$&")}.*Koupí za 220 Kč`) }));
      const field = screen.getByRole("textbox", { name: SUCCESS });
      fireEvent.change(field, { target: { value: "Zahodí to" } });
      fireEvent.keyDown(field, { key: "Escape" });
      // Esc restores: the field closes on the stored value, the typed one gone.
      expect(screen.queryByRole("textbox", { name: SUCCESS })).toBeNull();
      expect(screen.queryByText("Zahodí to")).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: new RegExp("Koupí za 220 Kč") }));
      const again = screen.getByRole("textbox", { name: SUCCESS });
      fireEvent.change(again, { target: { value: "Koupí a doporučí" } });
      fireEvent.blur(again);
      await saved();
      expect(lastSave().content.audience).toMatchObject({ success_definition: "Koupí a doporučí" });
      expect(saves.some((x) => JSON.stringify(x.content).includes("Zahodí to"))).toBe(false);
      // Optional, as it was: emptied, it is saved empty rather than refused.
      fireEvent.click(screen.getByRole("button", { name: new RegExp("Koupí a doporučí") }));
      const third = screen.getByRole("textbox", { name: SUCCESS });
      fireEvent.change(third, { target: { value: "" } });
      fireEvent.blur(third);
      await waitFor(() => expect(lastSave().content.audience).toMatchObject({ success_definition: "" }));
      noUnitCalls();
    });

    it("announces how many values a long factor's filter shows, as the person types", async () => {
      const many = { ...CATALOGUE.factors[1]!, id: "obec", column: "obec", label: "Obec", values: Array.from({ length: 20 }, (_, i) => ({ value: `Obec ${i + 1}`, count: 100 - i })) };
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: {} } }, { [CAT]: () => ({ ...CATALOGUE, factors: [...CATALOGUE.factors, many] }) });
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.change(await screen.findByLabelText("Hledat hodnotu: Obec"), { target: { value: "obec 2" } });
      expect(screen.getByText("Zobrazeno 2 z 20 hodnot.").getAttribute("aria-live")).toBe("polite"); // the count alone
      noUnitCalls();
    });

    it("names the description, the filters, each stored filter and the preview for the Lead to focus", async () => {
      // prijem is outside the category the editor opens on, so its editor is not drawn: its
      // target is the chip every stored filter has.
      const income = { ...CATALOGUE.factors[1]!, id: "prijem", column: "prijem", label: "Příjem domácnosti", category: "economy", category_label: "Ekonomika", values: [{ value: "Nad 60 000 Kč", count: 20 }] };
      const catalogue = { ...CATALOGUE, categories: [...CATALOGUE.categories, { id: "economy", label: "Ekonomika", description: "", count: 1, filterable_count: 1 }], factors: [...CATALOGUE.factors, income] };
      const filters = { kraj: ["Zlínský kraj"], vek: { min: 30, max: 59 }, prijem: ["Nad 60 000 Kč"] };
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters } }, { [CAT]: () => catalogue });
      const { container } = render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      await screen.findByText(/z populace v17_4_0/);
      expect(screen.queryByRole("button", { name: /Nad 60 000 Kč/ })).toBeNull();
      for (const target of ["audience:definition", "audience:filters", "audience:filter:kraj", "audience:filter:vek", "audience:filter:prijem", "audience:preview"]) {
        expect(container.querySelectorAll(focusSelector(target)), target).toHaveLength(1);
      }
      expect(container.querySelector(focusSelector("audience:filter:kraj"))!.textContent).toContain("Zlínský kraj");
      expect(container.querySelector(focusSelector("audience:filter:prijem"))!.textContent).toContain("Příjem domácnosti");
      // The screen marks exactly what the contract names (subpanels are drawn on their own path).
      const marks = [...container.querySelectorAll("[data-aia^='audience:']")].map((e) => e.getAttribute("data-aia"));
      expect(marks.sort()).toEqual(audienceTargets({ audience: { filters } } as unknown as ResearchProject, { preview: true, subpanels: [] }).sort());
      expect(container.querySelector(focusSelector("audience:preview"))!.textContent).toContain("Ověřit proveditelnost");
    });

    it("without a population, the filters target is the note that says why", async () => {
      aiaStub({ ui_state: ANALYTICS, audience: { strategy: "filters", source_mode: "population", filters: {} } }, { [CAT]: () => new Response(JSON.stringify({ code: "population_not_established", message: "no" }), { status: 409 }) });
      const { container } = render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      await waitFor(() => expect(container.querySelector(focusSelector("audience:filters"))?.textContent).toContain("V AIA zatím není"));
      expect(container.querySelector(focusSelector("audience:preview"))).toBeNull();
      const marks = [...container.querySelectorAll("[data-aia^='audience:']")].map((e) => e.getAttribute("data-aia"));
      expect(marks.sort()).toEqual(audienceTargets({ audience: {} } as unknown as ResearchProject, { preview: false, subpanels: [] }).sort());
    });

    it("says at once which stored filter the population cannot honour, and how a run treats it (F3)", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: { kraj: ["Zlínský kraj", "Fiktivní kraj A"], vek: { min: 30 } } } }, live());
      const { container } = render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const note = await screen.findByRole("note");
      expect(note.textContent).toContain("Populace v17_4_0");
      expect(note.textContent).toContain("Kraj – v populaci chybí: Fiktivní kraj A. Výběr je vynechá a použije ostatní uložené hodnoty.");
      const chip = container.querySelector('[data-aia="audience:filter:kraj"]')!;
      expect(chip.hasAttribute("data-filter-problem")).toBe(true);
      expect(chip.textContent).toContain("některé hodnoty chybí"); // said in words; the filter still applies with the rest
      expect(container.querySelector('[data-aia="audience:filter:vek"]')!.hasAttribute("data-filter-problem")).toBe(false);
      // Unticking the value it has leaves only the one it lacks: a run refuses the filter.
      fireEvent.click(screen.getByRole("button", { name: /Zlínský kraj/ }));
      await saved();
      expect(lastSave().content.audience.filters).toEqual({ kraj: ["Fiktivní kraj A"], vek: { min: 30 } });
      expect((await screen.findByRole("note")).textContent).toContain("Žádná uložená hodnota nezbývá, výběr odmítne celou cílovou skupinu.");
      expect(container.querySelector('[data-aia="audience:filter:kraj"]')!.textContent).toContain("nelze použít");
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

    it("announces how many factors the factor search shows, as the person types", async () => {
      aiaStub({ ui_state: ANALYTICS, n: 500, audience: { strategy: "filters", source_mode: "population", filters: {} } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      fireEvent.change(await screen.findByLabelText("Hledat faktor"), { target: { value: "kraj" } });
      expect(screen.getByText(/^Zobrazeno 1 z \d+ faktorů\.$/).getAttribute("aria-live")).toBe("polite");
      noUnitCalls();
    });

    it("the subpanels sit under a search that says what matched and never hides the chosen one (audit B9)", async () => {
      aiaStub({ ui_state: { audience_entry: "analytics", analytics_choice: "special" }, audience: { builtin_subpanel: "students" } }, live());
      render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const group = await screen.findByRole("radiogroup", { name: "Vestavěné subpanely" });
      const names = () => within(group).getAllByRole("radio").map((r) => r.querySelector(".font-semibold")!.textContent);
      expect(names()).toEqual(["Mladí 18–29", "Studenti"]);
      expect(screen.getByText("Hledání odpovídá 2 z 2 subpanelů; zvolený zůstává vidět.")).toBeTruthy();
      fireEvent.change(screen.getByLabelText("Hledat subpanel"), { target: { value: "mladí" } });
      expect(names()).toEqual(["Mladí 18–29", "Studenti"]); // Studenti is the chosen one
      expect(screen.getByText("Hledání odpovídá 1 z 2 subpanelů; zvolený zůstává vidět.")).toBeTruthy();
      fireEvent.change(screen.getByLabelText("Hledat subpanel"), { target: { value: "nikdo" } });
      expect(names()).toEqual(["Studenti"]);
      // Announced as the person types: the search's only feedback.
      expect(screen.getByText("Hledání odpovídá 0 z 2 subpanelů; zvolený zůstává vidět.").getAttribute("aria-live")).toBe("polite");
      noUnitCalls();
    });

    it("a built-in subpanel is chosen as its filter; one the policy refuses cannot be", async () => {
      aiaStub({ ui_state: { audience_entry: "analytics", analytics_choice: "special" } }, live());
      const { container } = render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
      const young = await screen.findByRole("radio", { name: /Mladí 18–29/ });
      expect((screen.getByRole("radio", { name: /Studenti/ }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.getByText(/Nelze použít: audit_only/)).toBeTruthy();
      expect(screen.getByText(/speciální panely a vlastní publikum stavěla 18.6.6/i)).toBeTruthy();
      expect(container.querySelector(focusSelector("audience:subpanel:young_18_29"))!.textContent).toContain("Mladí 18–29");
      // In the Speciální skupiny view the screen marks exactly the contract's targets, subpanels included.
      const marks = [...container.querySelectorAll("[data-aia^='audience:']")].map((e) => e.getAttribute("data-aia"));
      const keys = CATALOGUE.subpanels.map((sp) => sp.key);
      expect(marks.sort()).toEqual(audienceTargets({ audience: {} } as unknown as ResearchProject, { preview: false, subpanels: keys }).filter((x) => x.startsWith("audience:subpanel:")).sort());
      fireEvent.click(young);
      await saved();
      expect(lastSave()).toMatchObject({ reason: "population_subpanel", content: { audience: { builtin_subpanel: "young_18_29", source_mode: "population", filters: { vek: [18, 29] } } } });
      await waitFor(() => expect((screen.getByRole("button", { name: /Další · dimenze/ }) as HTMLButtonElement).disabled).toBe(false));
      noUnitCalls();
    });
  });
});
