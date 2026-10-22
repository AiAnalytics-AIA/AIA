// @vitest-environment jsdom
// The Metodika tab against a fake of its route serving the API's own document
// (src/lib/fixtures/methodology.json): the modules, the object map in the audit's order,
// each value with where it comes from, another methodology's omitted part said in words,
// a point AIA does not compute saying so, and a body that is not a list refused.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import fixture from "@/lib/fixtures/methodology.json";
import { MethodologyPanel } from "./MethodologyPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

type Doc = { modules: { id: string }[]; details: Record<string, Record<string, unknown>> };
const doc = fixture as unknown as Doc;
let calls: string[] = [];

function fakeApi(list: unknown = doc.modules) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    const full = String(url);
    calls.push(full);
    const [u, query] = full.split("?");
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (u === "/config") return json({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } });
    if (u === "/api/v1/methodology") return json(list);
    const m = u.match(/^\/api\/v1\/methodology\/([^/]+)$/);
    const byPreset = m ? doc.details[decodeURIComponent(m[1])] : undefined;
    if (!byPreset) return json({ code: "unknown_module", message: "no such module" }, 404);
    const preset = new URLSearchParams(query ?? "").get("preset") ?? Object.keys(byPreset)[0];
    return byPreset[preset] ? json(byPreset[preset]) : json({ code: "unknown_preset", message: "no such preset" }, 404);
  }));
}

const card = (title: string) =>
  waitFor(() => {
    const heading = screen.getByRole("heading", { name: title, hidden: true });
    const group = heading.closest("details") as HTMLDetailsElement;
    if (group && !group.open) fireEvent.click(group.querySelector("summary")!);
    return heading.closest("article") as HTMLElement;
  });

/** The area chooser is closed by default (the editor opens first): open it, then pick an area. */
async function openModule(name: string) {
  if (!screen.queryByRole("navigation", { name: "Oblasti metodiky" })) fireEvent.click(await screen.findByRole("button", { name: "Změnit oblast" }));
  fireEvent.click(await screen.findByRole("button", { name }));
}

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "member@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  resetConfigCache();
  vi.unstubAllGlobals();
});

describe("the Metodika tab", () => {
  it("lists every module and opens the object map in force, grouped by the stages of the computation", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    // The area in force opens at once; choosing another is one click away.
    expect(await screen.findByRole("heading", { level: 3, name: "Sociomapa: objektová mapa" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Oblasti metodiky" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Změnit oblast" }));
    const nav = await screen.findByRole("navigation", { name: "Oblasti metodiky" });
    expect(within(nav).getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual([
      "Připravenost studie: kdy lze běh spustit",
      "Sociomapa: objektová mapa", "Sociomapa: referenční mapa (18.6.6)", "Sociomapping: experimentální H-Model (kandidát AIA)",
      "Agregace: z odpovědí odhad s intervalem", "Podpora a potlačení: kdy se číslo smí ukázat",
      "Odpověď respondenta: od pravděpodobností modelu k odpovědi", "Vážení: která váha patří respondentovi a co s neplatnou",
      // Read-only and not a method module: the population's field policy (V1c).
      "Původ polí: k čemu smí sloužit",
    ]);
    expect(within(nav).getByRole("group", { name: "Před spuštěním" })).toBeTruthy();
    expect(within(nav).getByRole("group", { name: "Mapy objektů" })).toBeTruthy();
    expect(within(nav).getByRole("group", { name: "Čísla ve výsledcích" })).toBeTruthy();
    expect(within(nav).getByRole("group", { name: "Respondenti a váhy" })).toBeTruthy();
    await screen.findByRole("heading", { name: "Vstupní hodnocení" });
    const groups = [...document.querySelectorAll("h3[id^=mg-]")].map((h) => h.textContent);
    expect(groups.slice(0, 8)).toEqual(["Metoda", "Vstupní hodnocení", "Vztahy mezi objekty", "Rozložení na mapě", "Věrohodnost mapy", "Skóre a výška objektů", "Terén", "Respondenti a podpora mapy"]);
    expect(screen.getByRole("radio", { name: /aia-sociomap-5 · výchozí v kódu/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("says where each step sits: what it is for, what it reads, what reads it, and its audit point", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const distance = await card("Cílová vzdálenost z korelace");
    expect(within(distance).getByText("Původ: audit F6")).toBeTruthy();
    const context = distance.querySelector("[data-step-context]") as HTMLElement;
    const linked = (row: string) => [...context.querySelectorAll(`[data-context="${row}"] [data-context-link]`)].map((a) => a.getAttribute("data-context-link"));
    expect(linked("from")).toEqual(["f3_correlation", "f3_status"]);
    expect(linked("to")).toEqual(["f6_smacof", "f7_stress"]);
    // The first step reads the answers themselves; the last ones hand their result to the reader.
    const declared = await card("Hodnocení na společné škále 0-1");
    expect(within(declared.querySelector("[data-context=from]") as HTMLElement).getByText(/odpovědi respondentů/)).toBeTruthy();
    // A link opens the step it names, even in a stage that is closed.
    const smacofHeading = document.getElementById("ms-f6_smacof")!;
    smacofHeading.scrollIntoView = vi.fn();
    fireEvent.click(context.querySelector('[data-context-link="f6_smacof"]')!);
    expect(smacofHeading.scrollIntoView).toHaveBeenCalled();
    expect((smacofHeading.closest("details") as HTMLDetailsElement).open).toBe(true);
  });

  it("shows each value with where it comes from, and draws the formula as MathML", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const status = await card("Stav páru: neznámý, slabý, spolehlivý");
    const n = within(status).getByRole("rowheader", { name: /Nejmenší n páru/ }).closest("tr") as HTMLElement;
    expect(within(n).getByText("10 respondenti")).toBeTruthy(); // aia-sociomap-5, in force
    expect(within(n).getByText("metodika")).toBeTruthy();
    const floor = within(status).getByRole("rowheader", { name: /Nejnižší přípustné n_min/ }).closest("tr") as HTMLElement;
    expect(within(floor).getByText("kód")).toBeTruthy();
    expect(status.querySelector("math")).not.toBeNull();
    const smacof = await card("Rozložení objektů (SMACOF na pevném pravítku)");
    expect(within(smacof).getByText("10⁻¹²")).toBeTruthy();
  });

  it("shows a step's formula as the expression the engine evaluates, and an algorithm without one", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const terrain = await card("Terén jako obálka kopců");
    const slot = terrain.querySelector('[data-slot="f12.kernel"]') as HTMLElement;
    expect(within(slot).getByText("h * exp(-d2 / (2 * sigma * sigma))")).toBeTruthy();
    expect(slot.querySelector("math")).not.toBeNull();
    fireEvent.click(slot.querySelector("summary")!);
    expect(within(slot).getByText("kopec má ve svém středu přesně svou výšku")).toBeTruthy();
    const smacof = await card("Rozložení objektů (SMACOF na pevném pravítku)");
    expect(smacof.querySelector("[data-slot]")).toBeNull();
  });

  it("says what another methodology omits, and never shows it as 0", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("radio", { name: "aia-sociomap-2" }));
    await waitFor(() => expect(calls.some((c) => c.includes("preset=aia-sociomap-2"))).toBe(true));
    const terrain = await card("Terén jako obálka kopců");
    const sigma = within(terrain).getByRole("rowheader", { name: /Šířka kopce/ }).closest("tr") as HTMLElement;
    await waitFor(() => expect(within(sigma).getByText("v této metodice není")).toBeTruthy());
  });

  it("says where AIA does not compute a point yet", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const f14 = (await screen.findByRole("heading", { name: "Zatím v AIA není: testy při porovnání oblastí (F14)" })).closest("section") as HTMLElement;
    expect(within(f14).getByText(/V AIA zatím není/)).toBeTruthy();
    expect(within(f14).getByText("Žádný krok: v AIA se zatím nepočítá.")).toBeTruthy();
  });

  it("opens the reference map with its own steps", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Sociomapa: referenční mapa (18.6.6)");
    await screen.findByRole("heading", { name: "Matice vztahů objektů (stupnice 1-10)" });
    expect(calls).toContain("/api/v1/methodology/sociomap_reference?preset=aia-sociomap-1");
  });

  it("opens the experimental H-Model with its search parameters, shown and not offered for editing", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Sociomapping: experimentální H-Model (kandidát AIA)");
    await screen.findByRole("heading", { name: "Rozložení (H-Model, kandidát AIA)" });
    expect(calls).toContain("/api/v1/methodology/sociomapping?preset=aia_hmodel_candidate_v1");
    expect(screen.getAllByText(/EXPERIMENTAL_AIA/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
  });

  it("opens support and suppression with both rule sets side by side, editable by an administrator", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Podpora a potlačení: kdy se číslo smí ukázat");
    await screen.findByRole("heading", { name: "Pravidlo jednotky 18.6.6 (Výsledky)" });
    expect(screen.getByRole("heading", { name: "Brána důkazů AIA (analýza)" })).toBeTruthy();
    expect(calls.some((c) => c.startsWith("/api/v1/methodology/support"))).toBe(true);
    await waitFor(() => expect(calls).toContain("/api/v1/methodology/support/versions")); // its versions, so its editor
  });

  it("opens study readiness with its limits, from 18.6.6's policy, editable as a version", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Připravenost studie: kdy lze běh spustit");
    await screen.findByRole("heading", { name: "Vzorek" });
    expect(screen.getByRole("heading", { name: "Sledovaná sada" })).toBeTruthy();
    expect(screen.getAllByText(/aia-readiness-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Velikost vzorku/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Počet položek v sadě/).length).toBeGreaterThan(0);
    // Where a limit shows is the module's own, not the map reader's.
    expect(screen.queryByText("výsledek běhu, který čte čtenář mapy")).toBeNull();
    await waitFor(() => expect(calls).toContain("/api/v1/methodology/readiness/versions")); // its versions, so its editor
  });

  it("opens aggregation with its declared bootstrap and the findings on their steps", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Agregace: z odpovědí odhad s intervalem");
    await screen.findByRole("heading", { name: "Interval: bootstrap dárců" });
    expect(screen.getByRole("heading", { name: "Věrohodnost otázky" })).toBeTruthy();
    expect(screen.getAllByText(/aia-aggregate-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/nález D5/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/nález D7/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Vlastník nebo správce může vytvořit novou verzi/)).toBeTruthy();
    // Its estimators are shown as expressions, replaceable in the version editor (G3b).
    const mean = document.querySelector('[data-slot="agg.mean"]') as HTMLElement;
    expect(within(mean).getByText("sum(w * x) / sum(w)")).toBeTruthy();
    expect(within(mean).getByText(/V editoru verzí ho lze nahradit/)).toBeTruthy();
    expect(within(mean).queryByText(/až bude tato oblast upravitelná/)).toBeNull();
  });

  it("opens weighting read-only: the schemes, the sample's raking, the dataset's refusal and D1", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    await screen.findByRole("heading", { name: "Kishovo efektivní n na čtyřech místech" });
    expect(screen.getAllByText(/aia-weighting-1/).length).toBeGreaterThan(0);
    expect(screen.getByText("vaha_strukturalni_2025")).toBeTruthy();
    // What a run's respondent weighs: the sampler's raking, its values the code's constants.
    expect(screen.getByRole("heading", { name: "Váha respondenta běhu: vzorek z panelu" })).toBeTruthy();
    expect(screen.getByText("Raking vzorku na cíle")).toBeTruthy();
    expect(screen.getByText("Nejvýš iterací")).toBeTruthy();
    // The inert median/refuse switch is gone (W1b); the dataset refuses instead.
    expect(screen.queryByText("median")).toBeNull();
    expect(screen.getByText("Váha v datové sadě běhu")).toBeTruthy();
    // A total the contract does not declare is said, never shown as 0.
    expect(screen.getAllByText("žádná (null)").length).toBe(4);
    expect(screen.getAllByText(/nález D1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/GREG ani jiná kalibrace v AIA nejsou/).length).toBeGreaterThan(0);
    // Read-only until W1c, and the page says so.
    expect(screen.getByText(/Tento postup je dostupný ke čtení/)).toBeTruthy();
    expect(screen.queryByText(/Vlastník nebo správce může vytvořit novou verzi/)).toBeNull();
  });

  it("opens the response process: the unit's coefficients, the draw by code, D6, and editable", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await openModule("Odpověď respondenta: od pravděpodobností modelu k odpovědi");
    await screen.findByRole("heading", { name: "Mechanismy odpovědi" });
    expect(screen.getAllByText(/aia-response-1/).length).toBeGreaterThan(0);
    expect(screen.getByText("Losování odpovědi kódem")).toBeTruthy();
    expect(screen.getByText("Strop podílu (λ max)")).toBeTruthy();
    expect(screen.getAllByText(/Nález D6/).length).toBeGreaterThan(0);
    // Editable from R1c: the page offers a new version, as for support and aggregation.
    expect(screen.getByText(/Vlastník nebo správce může vytvořit novou verzi/)).toBeTruthy();
    expect(screen.queryByText(/Tento postup je dostupný ke čtení/)).toBeNull();
  });

  it("refuses a body that is not a list rather than drawing an empty methodology", async () => {
    fakeApi({ modules: [] });
    render(<MethodologyPanel />);
    await screen.findByText(/nemá podobu metodiky/);
  });
});

  it("focuses the calculation with search and keeps provenance available on demand", async () => {
    fakeApi(); render(<MethodologyPanel />);
    const input = await screen.findByRole("searchbox", { name: "Hledat výpočet nebo parametr" });
    fireEvent.change(input, { target: { value: "Kish" } });
    const cards = [...document.querySelectorAll("article")];
    expect(cards.length).toBeGreaterThan(0);
    expect(cards.every((c) => c.textContent?.includes("Kish"))).toBe(true);
    expect([...document.querySelectorAll("section > details")].every((d) => (d as HTMLDetailsElement).open)).toBe(true);
    fireEvent.change(input, { target: { value: "no-such-calculation" } });
    expect(screen.getByRole("status").textContent).toBe("Žádná část neodpovídá hledání.");
  });
