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
  it("lists every module and opens the object map in force, in the audit's order", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const nav = await screen.findByRole("navigation", { name: "Oblasti metodiky" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Sociomapa: objektová mapa", "Sociomapa: referenční mapa (18.6.6)",
      "Sociomapping: experimentální H-Model (kandidát AIA)",
      "Podpora a potlačení: kdy se číslo smí ukázat",
    ]);
    await screen.findByRole("heading", { name: "F1 Které položky jsou hodnocení" });
    const groups = [...document.querySelectorAll("h3[id^=mg-]")].map((h) => h.textContent);
    expect(groups.slice(0, 4)).toEqual(["Metoda", "F1 Které položky jsou hodnocení", "F2 Hodnoticí zvyklosti", "F3 Vztah dvou objektů a jeho spolehlivost"]);
    expect(screen.getByRole("radio", { name: /aia-sociomap-3 · výchozí v kódu/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("shows each value with where it comes from, and draws the formula as MathML", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const status = await card("Stav páru: neznámý, slabý, spolehlivý");
    const n = within(status).getByRole("rowheader", { name: /Nejmenší n páru/ }).closest("tr") as HTMLElement;
    expect(within(n).getByText("30 respondenti")).toBeTruthy();
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
    const f14 = (await screen.findByRole("heading", { name: "F14 Testy při porovnání oblastí" })).closest("section") as HTMLElement;
    expect(within(f14).getByText(/V AIA zatím není/)).toBeTruthy();
    expect(within(f14).getByText("Žádný krok: v AIA se zatím nepočítá.")).toBeTruthy();
  });

  it("opens the reference map with its own steps", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Sociomapa: referenční mapa (18.6.6)" }));
    await screen.findByRole("heading", { name: "Matice vztahů objektů (stupnice 1-10)" });
    expect(calls).toContain("/api/v1/methodology/sociomap_reference?preset=aia-sociomap-1");
  });

  it("opens the experimental H-Model with its search parameters, shown and not offered for editing", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Sociomapping: experimentální H-Model (kandidát AIA)" }));
    await screen.findByRole("heading", { name: "Rozložení (H-Model, kandidát AIA)" });
    expect(calls).toContain("/api/v1/methodology/sociomapping?preset=aia_hmodel_candidate_v1");
    expect(screen.getAllByText(/EXPERIMENTAL_AIA/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
  });

  it("opens support and suppression with both rule sets side by side, documented and not editable", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Podpora a potlačení: kdy se číslo smí ukázat" }));
    await screen.findByRole("heading", { name: "Pravidlo jednotky 18.6.6 (Výsledky)" });
    expect(screen.getByRole("heading", { name: "Brána důkazů AIA (analýza)" })).toBeTruthy();
    expect(calls.some((c) => c.startsWith("/api/v1/methodology/support"))).toBe(true);
    expect(screen.queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
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
