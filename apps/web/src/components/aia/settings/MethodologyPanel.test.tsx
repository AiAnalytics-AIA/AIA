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
    // A step is a row (fidelity F5): its heading's button opens it on its formula and values.
    const heading = screen.getByRole("heading", { name: title, hidden: true });
    const button = heading.querySelector("button[aria-expanded]");
    if (button?.getAttribute("aria-expanded") === "false") fireEvent.click(button);
    const article = heading.closest("article") as HTMLElement;
    if (!article.querySelector("[data-step-body]")) throw new Error(`${title} did not open`);
    return article;
  });

/** The tab opens on the module catalogue (fidelity F4): back to it if a module is open, then a card. */
async function openModule(name: string) {
  const back = document.querySelector<HTMLElement>("[data-methodology-back]");
  if (back) fireEvent.click(back);
  fireEvent.click(await within(await screen.findByRole("navigation", { name: "Oblasti metodiky" })).findByRole("button", { name }));
}
/** Opens the object map from the catalogue, as a person's first click on the tab does. */
const openMap = () => openModule("Sociomapa: objektová mapa");

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
    const base = vi.mocked(fetch).getMockImplementation()!;
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => String(url).split("?")[0] === "/api/v1/methodology/sociomap/versions"
      ? new Response(JSON.stringify({ in_force: { origin: "code", preset: "aia-sociomap-5", version_number: null, name: "aia-sociomap-5", register_status: "CLIENT_FACING" }, may_administer: false, may_edit: false, presets: {}, versions: [], history: [] }), { status: 200 })
      : base(url, init)));
    render(<MethodologyPanel />);
    // The tab opens on the catalogue (prototype v51, fidelity F4), under the MVP's note.
    const nav = await screen.findByRole("navigation", { name: "Oblasti metodiky" });
    expect(document.querySelector("[data-mvp-note]")?.textContent).toMatch(/^MVP počítá Sociomapu jedinou metodou: aia-sociomap-5\./);
    expect(screen.getByRole("heading", { level: 2, name: "Moduly" })).toBeTruthy();
    expect(screen.getByText(/^7 modulů · klikněte na modul/)).toBeTruthy();
    // One card per module, the map first; no categories (the product owner, 2026-10-21), and
    // neither the 18.6.6 reference map nor the experimental H-Model (D-13).
    expect(within(nav).getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual([
      "Sociomapa: objektová mapa",
      "Připravenost studie: kdy lze běh spustit",
      "Podpora a potlačení: kdy se číslo smí ukázat", "Agregace: z odpovědí odhad s intervalem",
      "Odpověď respondenta: od pravděpodobností modelu k odpovědi", "Vážení: která váha patří respondentovi a co s neplatnou",
      // Read-only and not a method module: the population's field policy (V1c).
      "Původ polí: k čemu smí sloužit",
    ]);
    expect(within(nav).queryByRole("group")).toBeNull();
    // Each card: its drawing, its accent, and its facts.
    const map = nav.querySelector('[data-module-card="sociomap"]') as HTMLElement;
    expect(map.querySelector("svg")).toBeTruthy();
    // The runtime property, which tokens.css always defines (never Tailwind's --color-*, gap 2).
    expect(map.getAttribute("style")).toContain("var(--hue-blue)");
    expect(within(map.querySelector("[data-module-facts]") as HTMLElement).getByText("V platnosti")).toBeTruthy();
    expect(map.textContent).toMatch(/\d+ kroků · \d+ etap/);
    // One line under each title (the prototype's), never the module's long note.
    expect(map.querySelector("[data-module-line]")?.textContent).toMatch(/^Z hodnocení respondentů spočítá vztahy mezi objekty/);
    // Pro klienty: the register's word on the method in force, for the map alone.
    await waitFor(() => expect(map.querySelector("[data-register]")?.getAttribute("data-register")).toBe("CLIENT_FACING"));
    expect(within(map).getByText("Schváleno v registru")).toBeTruthy();
    expect(nav.querySelector('[data-module-card="support"] [data-register]')).toBeNull();
    // No card takes a status colour or the in-force green.
    expect(nav.innerHTML).not.toMatch(/status-you|status-fault|in-force|hue-green/);
    fireEvent.click(map);
    // The module's page: back to the catalogue, its title, its one line and its facts as chips.
    expect(await screen.findByRole("heading", { level: 2, name: "Sociomapa: objektová mapa" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Oblasti metodiky" })).toBeNull();
    const chips = document.querySelector("[data-module-chips]") as HTMLElement;
    await waitFor(() => expect(within(chips).getByText("V platnosti: aia-sociomap-5")).toBeTruthy());
    expect(within(chips).getByText("Schváleno pro klienty")).toBeTruthy();
    expect(within(chips).getByText(/^\d+ kroků v \d+ etapách$/)).toBeTruthy();
    await screen.findByRole("heading", { name: "Vstupní hodnocení" });
    const groups = [...document.querySelectorAll("h3[id^=mg-]")].map((h) => h.textContent);
    expect(groups.slice(0, 8)).toEqual(["Metoda", "Vstupní hodnocení", "Vztahy mezi objekty", "Rozložení na mapě", "Věrohodnost mapy", "Skóre a výška objektů", "Terén", "Respondenti a podpora mapy"]);
    // D-13: one method offered, aia-sociomap-5, said rather than chosen.
    expect(document.querySelector("[data-preset]")?.textContent).toMatch(/^Kroky popisují metodu aia-sociomap-5 tak, jak je v kódu/);
  });

  it("says where each step sits: what it is for, what it reads, what reads it, and its audit point", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const distance = await card("Cílová vzdálenost z korelace");
    expect(within(distance).getByText("Původ: audit F6")).toBeTruthy();
    const context = distance.querySelector("[data-step-context]") as HTMLElement;
    const linked = (row: string) => [...context.querySelectorAll(`[data-context="${row}"] [data-context-link]`)].map((a) => a.getAttribute("data-context-link"));
    expect(linked("from")).toEqual(["f3_correlation", "f3_status"]);
    expect(linked("to")).toEqual(["f6_smacof", "f7_stress"]);
    // The first step reads the answers themselves; the last ones hand their result to the reader.
    const declared = await card("Hodnocení na společné škále 0-1");
    expect(within(declared.querySelector("[data-context=from]") as HTMLElement).getByText(/odpovědi respondentů/)).toBeTruthy();
    // A link opens the step it names, closed until then, and moves to it.
    const smacofHeading = document.getElementById("ms-f6_smacof")!;
    expect(smacofHeading.closest("article")?.querySelector("[data-step-body]")).toBeNull();
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    fireEvent.click(context.querySelector('[data-context-link="f6_smacof"]')!);
    await waitFor(() => expect(scrolled).toHaveBeenCalled());
    expect(document.getElementById("ms-f6_smacof")?.closest("article")?.querySelector("[data-step-body]")).toBeTruthy();
  });

  it("shows each value with where it comes from, and draws the formula as MathML", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const status = await card("Stav páru: neznámý, slabý, spolehlivý");
    const n = within(status).getByRole("rowheader", { name: /Nejmenší n páru/ }).closest("tr") as HTMLElement;
    expect(within(n).getByText("10 respondenti")).toBeTruthy(); // aia-sociomap-5, in force
    expect(within(n).getByText("metodika")).toBeTruthy();
    const floor = within(status).getByRole("rowheader", { name: /Nejnižší přípustné n_min/ }).closest("tr") as HTMLElement;
    expect(within(floor).getByText("kód")).toBeTruthy();
    expect(status.querySelector("math")).not.toBeNull();
    const smacof = await card("Rozložení objektů (SMACOF na pevném pravítku)");
    expect(within(smacof.querySelector("[data-step-body]") as HTMLElement).getByText("10⁻¹²")).toBeTruthy();
    // A closed row says its values too, as chips beside its title.
    expect(within(smacof.querySelector("h4") as HTMLElement).getAllByText("10⁻¹²").length).toBe(1);
  });

  it("shows a step's formula as the expression the engine evaluates, and an algorithm without one", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const terrain = await card("Terén jako obálka kopců");
    const slot = terrain.querySelector('[data-slot="f12.kernel"]') as HTMLElement;
    expect(within(slot).getByText("h * exp(-d2 / (2 * sigma * sigma))")).toBeTruthy();
    expect(slot.querySelector("math")).not.toBeNull();
    fireEvent.click(slot.querySelector("summary")!);
    expect(within(slot).getByText("kopec má ve svém středu přesně svou výšku")).toBeTruthy();
    const smacof = await card("Rozložení objektů (SMACOF na pevném pravítku)");
    expect(smacof.querySelector("[data-slot]")).toBeNull();
  });

  it("says on its card the version the organization has in force, read from its versions, never the code's preset as if it were", async () => {
    fakeApi();
    const base = vi.mocked(fetch).getMockImplementation()!;
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      if (u === "/api/v1/methodology/sociomap/versions") {
        return new Response(JSON.stringify({ in_force: { origin: "stored", preset: "aia-sociomap-5", version_number: 1, name: "aia-sociomap-5+e1" }, may_administer: true, presets: {}, versions: [], history: [] }), { status: 200 });
      }
      return base(url, init);
    }));
    render(<MethodologyPanel />);
    const nav = await screen.findByRole("navigation", { name: "Oblasti metodiky" });
    const map = nav.querySelector('[data-module-card="sociomap"]') as HTMLElement;
    await waitFor(() => expect(map.querySelector("[data-current-name]")?.textContent).toBe("aia-sociomap-5+e1"));
    // A module whose versions could not be read says so, never its preset as the one in force.
    const support = nav.querySelector('[data-module-card="support"]') as HTMLElement;
    await waitFor(() => expect(support.querySelector("[data-current-unknown]")?.textContent).toBe("nezjištěno"));
    // A read-only module: its code preset, said as the code's.
    expect(nav.querySelector('[data-module-card="weighting"] [data-module-facts]')?.textContent).toMatch(/výchozí v kódu|z kódu/);
  });

  it("offers aia-sociomap-5 only, never the earlier methods (D-13)", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await waitFor(() => expect(document.querySelector("[data-preset]")?.textContent).toMatch(/metodu aia-sociomap-5 /));
    expect(screen.queryByRole("radiogroup", { name: /metodik|předvolb/i })).toBeNull();
    // Nothing offers or names an earlier method as one to use: the preset line, the module's chips.
    // (A step's own note may cite an earlier method as its history -- "as in aia-sociomap-4" -- which
    // the whole-page match this replaces caught only once the steps had loaded.)
    for (const el of document.querySelectorAll("[data-preset], [data-module-chips], [data-module-header]")) expect(el.textContent).not.toMatch(/aia-sociomap-[1-4]\b/);
  });

  it("says where AIA does not compute a point yet", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const f14 = (await screen.findByRole("heading", { name: /^Zatím v AIA není: testy při porovnání oblastí \(F14\)/ })).closest("section") as HTMLElement;
    expect(within(f14).getByText(/V AIA zatím není/)).toBeTruthy();
    expect(within(f14).getByText("Žádný krok: v AIA se zatím nepočítá.")).toBeTruthy();
  });

  it("does not list the 18.6.6 reference map or the experimental H-Model (D-13)", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const nav = await screen.findByRole("navigation", { name: "Oblasti metodiky" });
    expect(within(nav).queryByRole("button", { name: /referenční mapa|H-Model/ })).toBeNull();
    expect(calls.some((c) => c.includes("sociomap_reference") || c.includes("/sociomapping"))).toBe(false);
  });

  it("opens support and suppression with both rule sets side by side, editable by an administrator", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Podpora a potlačení: kdy se číslo smí ukázat");
    await screen.findByRole("heading", { name: "Pravidlo jednotky 18.6.6 (Výsledky)" });
    expect(screen.getByRole("heading", { name: "Brána důkazů AIA (analýza)" })).toBeTruthy();
    expect(calls.some((c) => c.startsWith("/api/v1/methodology/support"))).toBe(true);
    await waitFor(() => expect(calls).toContain("/api/v1/methodology/support/versions")); // its versions, so its editor
  });

  it("opens study readiness with its limits, from 18.6.6's policy, editable as a version", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Připravenost studie: kdy lze běh spustit");
    await screen.findByRole("heading", { name: "Vzorek" });
    expect(screen.getByRole("heading", { name: "Sledovaná sada" })).toBeTruthy();
    expect(screen.getAllByText(/aia-readiness-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Velikost vzorku/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Počet položek v sadě/).length).toBeGreaterThan(0);
    // Where a limit shows is the module's own, not the map reader's.
    expect(screen.queryByText("výsledek běhu, který čte čtenář mapy")).toBeNull();
    // What every version keeps is part of the step's explanation (the editor lists only parameters).
    const sample = await card("Velikost vzorku");
    expect(within(sample.querySelector("[data-step-keeps]") as HTMLElement).getByText("chybějící n blokuje vždy")).toBeTruthy();
    await waitFor(() => expect(calls).toContain("/api/v1/methodology/readiness/versions")); // its versions, so its editor
  });

  it("opens aggregation with its declared bootstrap and the findings on their steps", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Agregace: z odpovědí odhad s intervalem");
    fireEvent.click(await screen.findByRole("button", { name: "Rozbalit všechny kroky" }));
    await screen.findByRole("heading", { name: "Interval: bootstrap dárců" });
    expect(screen.getByRole("heading", { name: "Věrohodnost otázky" })).toBeTruthy();
    expect(screen.getAllByText(/aia-aggregate-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/nález D5/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/nález D7/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Novou verzi parametrů a vzorců vytváří Metodik/)).toBeTruthy();
    // Its estimators are shown as expressions, replaceable in the version editor (G3b).
    const mean = document.querySelector('[data-slot="agg.mean"]') as HTMLElement;
    expect(within(mean).getByText("sum(w * x) / sum(w)")).toBeTruthy();
    expect(within(mean).getByText(/V editoru verzí ho lze nahradit/)).toBeTruthy();
    expect(within(mean).queryByText(/až bude tato oblast upravitelná/)).toBeNull();
  });

  it("opens weighting read-only: the schemes, the sample's raking, the dataset's refusal and D1", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    fireEvent.click(await screen.findByRole("button", { name: "Rozbalit všechny kroky" }));
    await screen.findByRole("heading", { name: "Kishovo efektivní n na čtyřech místech" });
    expect(screen.getAllByText(/aia-weighting-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("vaha_strukturalni_2025").length).toBeGreaterThan(0); // its chip and, open, its row
    // What a run's respondent weighs: the sampler's raking, its values the code's constants.
    expect(screen.getByRole("heading", { name: "Váha respondenta běhu: vzorek z panelu" })).toBeTruthy();
    expect(screen.getByText("Raking vzorku na cíle")).toBeTruthy();
    expect(screen.getByText("Nejvýš iterací")).toBeTruthy();
    // The inert median/refuse switch is gone (W1b); the dataset refuses instead.
    expect(screen.queryByText("median")).toBeNull();
    expect(screen.getByText("Váha v datové sadě běhu")).toBeTruthy();
    // A total the contract does not declare is said, never shown as 0.
    // Four values, each said once in its row's chip and once in its open table.
    expect([...document.querySelectorAll("[data-step-body]")].flatMap((b) => within(b as HTMLElement).queryAllByText("žádná (null)")).length).toBe(4);
    expect([...document.querySelectorAll("[data-step-value]")].filter((c) => c.textContent?.includes("žádná (null)")).length).toBe(4);
    expect(screen.getAllByText(/nález D1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/GREG ani jiná kalibrace v AIA nejsou/).length).toBeGreaterThan(0);
    // Read-only until W1c, and the page says so.
    expect(screen.getByText(/Tento postup je dostupný ke čtení/)).toBeTruthy();
    expect(screen.queryByText(/Novou verzi parametrů a vzorců vytváří Metodik/)).toBeNull();
  });

  it("opens the response process: the unit's coefficients, the draw by code, D6, and editable", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Odpověď respondenta: od pravděpodobností modelu k odpovědi");
    fireEvent.click(await screen.findByRole("button", { name: "Rozbalit všechny kroky" }));
    await screen.findByRole("heading", { name: "Mechanismy odpovědi" });
    expect(screen.getAllByText(/aia-response-1/).length).toBeGreaterThan(0);
    expect(screen.getByText("Losování odpovědi kódem")).toBeTruthy();
    expect(screen.getByText("Strop podílu (λ max)")).toBeTruthy();
    expect(screen.getAllByText(/Nález D6/).length).toBeGreaterThan(0);
    // Editable from R1c: the page offers a new version, as for support and aggregation.
    expect(screen.getByText(/Novou verzi parametrů a vzorců vytváří Metodik/)).toBeTruthy();
    expect(screen.queryByText(/Tento postup je dostupný ke čtení/)).toBeNull();
  });

  it("refuses a body that is not a list rather than drawing an empty methodology", async () => {
    fakeApi({ modules: [] });
    render(<MethodologyPanel />);
    await screen.findByText(/nemá podobu metodiky/);
  });
});

  it("lays the calculation out as the prototype does: stage tiles, a parameter filter, and rows that open on their formula", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    const tiles = await screen.findByRole("group", { name: "Etapy" });
    const all = within(tiles).getByRole("button", { name: /^Všechny etapy/ });
    expect(all.getAttribute("aria-pressed")).toBe("true");
    // Rows are closed: a title, what it is for, its values as chips -- the formula on opening.
    await waitFor(() => expect(document.querySelectorAll("article[data-step]").length).toBeGreaterThan(10));
    expect(document.querySelector("[data-step-body]")).toBeNull();
    // One stage by its tile; the other stages' steps leave the page.
    fireEvent.click(within(tiles).getByRole("button", { name: /^M6\s·\sTerén/ }));
    const sections = [...document.querySelectorAll("section[aria-labelledby^='mg-']:not([data-not-computed] section)")].map((x) => x.querySelector("h3")?.textContent);
    expect(sections).toEqual(["Terén"]);
    fireEvent.click(all);
    // Only the steps that read a parameter, each showing it as a chip.
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Jen kroky" })).getByRole("radio", { name: "S parametry" }));
    const rows = [...document.querySelectorAll("article[data-step]")];
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((r) => r.querySelector("[data-step-value]"))).toBe(true);
    // Every row opens at once, and closes.
    fireEvent.click(screen.getByRole("button", { name: "Rozbalit všechny kroky" }));
    expect(document.querySelectorAll("[data-step-body]").length).toBe(rows.length);
    fireEvent.click(screen.getByRole("button", { name: "Sbalit všechny kroky" }));
    expect(document.querySelector("[data-step-body]")).toBeNull();
  });

  it("counts steps in Czech on the tiles and the stage heads: 1 krok, 3 kroky, 17 kroků", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    const tiles = await screen.findByRole("group", { name: "Etapy" });
    const count = (tile: RegExp) => within(tiles).getByRole("button", { name: tile }).querySelector(".text-xs")?.textContent;
    expect(count(/^Všechny etapy/)).toBe("17 kroků");
    expect(count(/^M1\s·\sSchéma vah/)).toBe("3 kroky");
    expect(count(/^M2\s·\sSoučty populace/)).toBe("1 krok");
    const head = screen.getByRole("heading", { name: "Součty populace" }).closest("section") as HTMLElement;
    expect(within(head).getByText("1 krok")).toBeTruthy();
    // The catalogue's cards count the same way.
    fireEvent.click(document.querySelector<HTMLElement>("[data-methodology-back]")!);
    const readiness = await waitFor(() => document.querySelector('[data-module-card="readiness"]') as HTMLElement);
    expect(readiness.textContent).toContain("3 kroky · 3 etapy");
  });

  it("says a stage has no step with a parameter rather than showing nothing", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    const tiles = await screen.findByRole("group", { name: "Etapy" });
    fireEvent.click(within(tiles).getByRole("button", { name: /^M4\s·\sNeplatná váha/ }));
    expect(document.querySelectorAll("article[data-step]").length).toBe(2);
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Jen kroky" })).getByRole("radio", { name: "S parametry" }));
    expect(document.querySelector("article[data-step]")).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("Žádný krok této etapy nečte parametr.");
  });

  it("counts as a parameter only what a version can change, never a code constant or the method's name", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    await screen.findByRole("group", { name: "Etapy" });
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Jen kroky" })).getByRole("radio", { name: "S parametry" }));
    // The method's own step (its name) and the run's raking (code constants) are not among them.
    const shown = [...document.querySelectorAll("article[data-step] [id^='mst-']")].map((n) => n.textContent);
    expect(shown).not.toContain("Váha respondenta běhu: vzorek z panelu");
    expect(screen.queryByRole("heading", { name: "Vážení" })).toBeNull();
    expect(shown.length).toBe(2);
  });

  it("follows a context link out of a single stage: all stages again, the step open and focused", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    const tiles = await screen.findByRole("group", { name: "Etapy" });
    fireEvent.click(within(tiles).getByRole("button", { name: /^M3\s·\sRozložení na mapě/ }));
    expect(document.getElementById("ms-f3_correlation")).toBeNull();
    const distance = await card("Cílová vzdálenost z korelace");
    Element.prototype.scrollIntoView = vi.fn();
    fireEvent.click(distance.querySelector('[data-context="from"] [data-context-link="f3_correlation"]')!);
    await waitFor(() => expect(document.getElementById("ms-f3_correlation")?.closest("article")?.querySelector("[data-step-body]")).toBeTruthy());
    expect(within(tiles).getByRole("button", { name: /^Všechny etapy/ }).getAttribute("aria-pressed")).toBe("true");
    expect(document.activeElement).toBe(document.querySelector("#ms-f3_correlation button[aria-expanded]"));
  });

