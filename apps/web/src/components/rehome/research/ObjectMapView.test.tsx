// @vitest-environment jsdom
// The audit's object map on the Results page, redesigned (plan object-map-3d-redesign): it says
// it is internal and fictional first, opens from above, draws the stored terrain as ten display
// terraces, the selected object's drawn relations and every object, labels the fit by Stress-1,
// counts who is not placed, and explains one pair from its stored evidence. Fixture from the
// real builder; nothing here recomputes a methodological number.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapLinks, readObjectMap } from "@/lib/object-map-view";
import { terraceLayers } from "@/lib/object-map-3d";
import { ObjectMapView } from "./ObjectMapView";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");
const map = read.map;
const key = (a: string, b: string) => `${a}|${b}`;
const linksOf = (id: string, m = map) => mapLinks(m).filter((l) => l.a === id || l.b === id).map((l) => key(l.a, l.b));
const drawnPairs = (testId: string) => [...screen.getByTestId(testId).children].map((c) => c.getAttribute("data-pair"));

/** The fixture with its stored artifact changed, as another stored map would be. */
function variant(change: (m: typeof map) => void): BatteryWithMaps {
  const copy = structuredClone(battery);
  change(copy.maps!["aia-sociomap-3"].artifact);
  return copy;
}

beforeEach(() => { vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ObjectMapView", () => {
  it("says it is internal, provisional and fictional before the map", () => {
    render(<ObjectMapView battery={battery} dataOrigin="SYNTHETIC_FIXTURE" />);
    expect(screen.getByText("Mapa objektů (aia-sociomap-3)")).toBeTruthy();
    expect(screen.getByText("Interní · nesmí ke klientovi")).toBeTruthy();
    expect(screen.getByTestId("object-map-origin").textContent).toContain("Fiktivní data");
    expect(screen.getByTestId("object-map-origin").getAttribute("data-origin-kind")).toBe("SIMULATED");
    expect(screen.getByText(/σ = 0,25/)).toBeTruthy();
    expect(screen.getByTestId("object-map-support").textContent).toContain("Fiktivní data (SYNTHETIC_FIXTURE)");
  });

  it("says modelled data is modelled, never fictional and never measured (ADR 0024 §7)", () => {
    render(<ObjectMapView battery={battery} dataOrigin="MODELLED_AI_PANEL" />);
    const chip = screen.getByTestId("object-map-origin");
    expect(chip.getAttribute("data-origin-kind")).toBe("MODELLED");
    expect(chip.textContent).toContain("Modelováno: AI respondenti z populace");
    expect(chip.textContent).not.toContain("Fiktivní");
    expect(screen.getByTestId("object-map-support").textContent).toContain("Modelováno: AI respondenti z populace (MODELLED_AI_PANEL)");
  });

  it("opens from above, the 3D renderer not mounted", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-svg")).toBeTruthy();
    expect(screen.queryByTestId("object-map-3d")).toBeNull();
    expect(document.querySelector("canvas")).toBeNull();
    expect(screen.getByRole("button", { name: "Pohled shora" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "3D terén" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("draws every stored cell, the selected object's drawn links and every object", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    // Ten terraces, each the stored surface cut at its band (filled exactly where it has pieces).
    const bands = [...screen.getByTestId("object-map-terrain").querySelectorAll("g[data-band]")];
    expect(bands).toHaveLength(10);
    terraceLayers(map).forEach((layer, k) => expect(bands[k].querySelector("path")!.getAttribute("d") !== "").toBe(layer.pieces.length > 0));
    expect(drawnPairs("object-map-links")).toEqual(linksOf("altair"));
    const negative = [...screen.getByTestId("object-map-links").children].filter((l) => l.getAttribute("stroke-dasharray"));
    expect(negative).toHaveLength(mapLinks(map).filter((l) => (l.a === "altair" || l.b === "altair") && l.sign === "negative").length);
    for (const id of map.object_ids) expect(screen.getByTestId(`object-map-point-${id}`)).toBeTruthy();
    // No origin recorded: said as unknown, never read as fieldwork.
    expect(screen.getByTestId("object-map-origin").getAttribute("data-origin-kind")).toBe("UNKNOWN");
    fireEvent.click(screen.getByTestId("object-map-point-deneb"));
    expect(drawnPairs("object-map-links")).toEqual(linksOf("deneb"));
  });

  it("says whose relations the lines are, and follows a click to another object", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    const caption = () => screen.getByTestId("object-map-links-caption").textContent;
    expect(caption()).toBe(`Čáry: vztahy objektu Altair (${linksOf("altair").length}) · klikněte na jiný objekt`);
    fireEvent.click(screen.getByTestId("object-map-point-deneb"));
    expect(caption()).toBe(`Čáry: vztahy objektu Deneb (${linksOf("deneb").length}) · klikněte na jiný objekt`);
    expect(screen.getByTestId("object-map-links-caption").getAttribute("aria-live")).toBe("polite");
    fireEvent.click(screen.getByRole("button", { name: "Vztahy" }));
    expect(caption()).toBe("Čáry vztahů jsou skryté");
    const lonely = variant((m) => { for (let j = 0; j < m.object_ids.length; j++) if (j !== 0) { m.relations.status[0][j] = m.relations.status[j][0] = "weak"; } });
    cleanup();
    render(<ObjectMapView battery={lonely} dataOrigin={null} />);
    expect(caption()).toContain("Altair: žádný vztah nesplňuje pravidla pro čáru");
    expect(drawnPairs("object-map-links")).toEqual([]);
  });

  it("never draws a WEAK, UNKNOWN, undefined or below-floor pair, and never more than mapLinks", () => {
    const changed = variant((m) => {
      m.relations.status[0][1] = m.relations.status[1][0] = "unknown"; // r kept
      m.relations.r[0][2] = m.relations.r[2][0] = null; // never computed
      m.relations.status[0][2] = m.relations.status[2][0] = "unknown";
      m.relations.meets_effect_floor![0][3] = m.relations.meets_effect_floor![3][0] = false; // reliable, below floor
    });
    const stored = readObjectMap(changed);
    if (!stored.ok) throw new Error("variant");
    render(<ObjectMapView battery={changed} dataOrigin={null} />);
    const drawn = drawnPairs("object-map-links");
    expect(drawn).toEqual(linksOf("altair", stored.map));
    for (const pair of ["altair|borealis", "altair|cirrus", "altair|deneb", "altair|elara"]) expect(drawn).not.toContain(pair);
    fireEvent.click(screen.getByTestId("object-map-point-deneb"));
    expect(drawnPairs("object-map-links")).not.toContain("deneb|fomalhaut"); // WEAK in the fixture
  });

  it("draws a SECONDARY object as context: no link, and the stored terrain unchanged", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    const terrain = screen.getByTestId("object-map-terrain").innerHTML;
    cleanup();
    const context = variant((m) => (m.roles.altair = "secondary"));
    render(<ObjectMapView battery={context} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-terrain").innerHTML).toBe(terrain);
    expect(drawnPairs("object-map-links")).toEqual([]);
    const pin = screen.getByTestId("object-map-point-altair");
    expect(pin.querySelector("rect[transform]")).toBeTruthy(); // the diamond
    expect(pin.textContent).toContain("Altair · kontext");
    expect(within(screen.getByTestId("object-map-details")).getByText("kontextový objekt")).toBeTruthy();
    fireEvent.click(screen.getByTestId("object-map-point-borealis"));
    expect(drawnPairs("object-map-links")).not.toContain("altair|borealis");
  });

  it("labels the fit by its stored Stress-1 and quality, and counts who is not placed", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    const fit = screen.getByTestId("object-map-fit").textContent!;
    expect(fit).toContain("Stress-1 = 0,158");
    expect(fit).toContain("slabá shoda");
    expect(fit).not.toContain("Spearman");
    expect(screen.getByTestId("object-map-not-placed").textContent).toContain("Nezařazení respondenti: 1");
    const support = screen.getByTestId("object-map-support").textContent!;
    expect(support).toContain("Dvojice: 11 spolehlivé · 4 slabé · 0 neznámé vztahy");
    // The aggregate UNKNOWN count is neutral: it holds UNKNOWN estimates and undefined r alike.
    const counts = within(screen.getByTestId("object-map-support")).getByText(/^Dvojice/).textContent!;
    expect(counts).toContain("neznámé vztahy");
    expect(counts).not.toMatch(/evidenc/);
    expect(screen.getByTestId("object-map-method").textContent).toBe(`Metoda aia-sociomap-3 · otisk ${read.fingerprint.slice(0, 12)}`);
  });

  it("shows a chosen object's stored relations, with which of them are drawn", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByTestId("object-map-point-deneb"));
    const details = screen.getByTestId("object-map-details");
    expect(within(details).getByText("Deneb")).toBeTruthy();
    const fomalhaut = within(details).getByText("Fomalhaut").closest("button")!;
    expect(fomalhaut.textContent).toContain("slabý");
    expect(fomalhaut.textContent).not.toContain("na mapě");
  });

  it("prints stored values, the display band only beside them", () => {
    render(<ObjectMapView battery={{ ...battery, rating_scale: [1, 10] }} dataOrigin={null} />);
    const h = map.heights.values[0]!;
    const cs = (v: number, d: number) => v.toLocaleString("cs-CZ", { minimumFractionDigits: d, maximumFractionDigits: d });
    const details = screen.getByTestId("object-map-details").textContent!;
    expect(details).toContain(cs(h, 2));
    expect(details).toContain(cs(1 + 9 * h, 1));
    expect(details).toContain(`${Math.floor(h * 10) + 1}/10`);
    expect(details).toContain("pásmo (zobrazení)");
    const label = screen.getByTestId("object-map-point-altair").textContent!;
    expect(label).toContain(`${cs(h, 2)} · ${cs(1 + 9 * h, 1)}/10 · zobrazovací pásmo ${Math.floor(h * 10) + 1}/10`);
    // Two heights in one band print two different numbers.
    const nudged = variant((m) => (m.heights.values[0] = Math.floor(h * 10) / 10 + 0.001));
    cleanup();
    render(<ObjectMapView battery={nudged} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-details").textContent).toContain(`${Math.floor(h * 10) + 1}/10`);
    expect(screen.getByTestId("object-map-details").textContent).not.toContain(cs(h, 2));
  });

  it("ranks every object by its stored height", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    const rows = within(screen.getByTestId("object-map-ranked")).getAllByRole("button");
    expect(rows.map((r) => r.textContent!.replace(/^\d+/, "").replace(/[\d,]+$/, ""))).toEqual(["Altair", "Borealis", "Cirrus", "Deneb", "Elara", "Fomalhaut"]);
    fireEvent.click(rows[3]);
    expect(within(screen.getByTestId("object-map-details")).getByText("Deneb")).toBeTruthy();
  });

  it("tells an UNKNOWN estimate apart from an r that could not be computed", () => {
    const changed = variant((m) => {
      m.relations.status[0][1] = m.relations.status[1][0] = "unknown";
      m.relations.r[0][2] = m.relations.r[2][0] = null;
      m.relations.status[0][2] = m.relations.status[2][0] = "unknown";
    });
    render(<ObjectMapView battery={changed} dataOrigin={null} />);
    const row = (name: string) => within(screen.getByTestId("object-map-details")).getByText(name).closest("button")!;
    fireEvent.click(row("Borealis"));
    const estimate = screen.getByTestId("object-map-pair").textContent!;
    expect(estimate).toContain(map.relations.r[0][1]!.toLocaleString("cs-CZ", { minimumFractionDigits: 3, maximumFractionDigits: 3 }));
    expect(estimate).toContain("neznámý");
    expect(estimate).toContain("Nedostatečná evidence pro interpretaci tohoto odhadu.");
    expect(estimate).not.toContain("nebylo možné vypočítat");
    fireEvent.click(row("Cirrus"));
    const none = screen.getByTestId("object-map-pair").textContent!;
    expect(screen.getByTestId("object-map-pair-r").textContent).toBe("—");
    expect(none).toContain("Vztah nebylo možné vypočítat.");
    expect(none).not.toContain("Nedostatečná evidence");
    expect(screen.getByTestId("object-map-pair-why").textContent).toContain("odhad r neexistuje");
  });

  it("explains a pair from its stored evidence: support, interval, floor, drawn or not", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(within(screen.getByTestId("object-map-details")).getByText("Borealis").closest("button")!);
    const card = screen.getByTestId("object-map-pair").textContent!;
    const [low, high] = map.relations.interval![0][1]!;
    expect(card).toContain("n = 79");
    expect(card).toContain(`95 % interval r: ${low.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
    expect(card).toContain(high.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    expect(screen.getByTestId("object-map-pair-evidence").textContent).toContain("|r| ≥ 0,10 splněn · na mapě");
    expect(screen.queryByTestId("object-map-pair-why")).toBeNull(); // drawn: no reason to give
    expect(card).not.toMatch(/p\s*[=<]/);
    fireEvent.click(screen.getByRole("button", { name: "Prohodit pohled" }));
    expect(within(screen.getByTestId("object-map-details")).getByText("Borealis")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zavřít detail dvojice" }));
    expect(screen.queryByTestId("object-map-pair")).toBeNull();
  });

  it("opens the stored terrain in 3D, changes only the camera, and unmounts it from above", () => {
    const before = JSON.stringify(battery);
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    const view = screen.getByTestId("object-map-3d");
    const initial = view.getAttribute("data-camera");
    expect(Number(view.getAttribute("data-triangles"))).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Otočit vpravo" }));
    expect(view.getAttribute("data-camera")).not.toBe(initial);
    fireEvent.click(screen.getByRole("button", { name: "Přiblížit" }));
    expect(JSON.parse(view.getAttribute("data-camera")!).zoom).toBeGreaterThan(1);
    fireEvent.keyDown(screen.getByRole("region", { name: "Interaktivní mapa objektů" }), { key: "Home" });
    expect(view.getAttribute("data-camera")).toBe(initial);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "1.5" } });
    expect(JSON.parse(view.getAttribute("data-camera")!).relief).toBe(1.5);
    fireEvent.click(screen.getByRole("button", { name: "Výchozí pohled" }));
    expect(view.getAttribute("data-camera")).toBe(initial);
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(screen.queryByTestId("object-map-3d")).toBeNull();
    expect(document.querySelector("canvas")).toBeNull();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(JSON.stringify(battery)).toBe(before);
  });

  it("keeps selection across views, selects by keyboard and toggles the drawn links", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    fireEvent.keyDown(screen.getByRole("button", { name: "Vybrat objekt Deneb" }), { key: "Enter" });
    expect(within(screen.getByTestId("object-map-details")).getByText("Deneb")).toBeTruthy();
    expect(drawnPairs("object-map-3d-links")).toEqual(linksOf("deneb"));
    fireEvent.click(screen.getByRole("button", { name: "Vztahy" }));
    expect(screen.getByTestId("object-map-3d-links").children).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(within(screen.getByTestId("object-map-details")).getByText("Deneb")).toBeTruthy();
    expect(screen.getByTestId("object-map-links").children).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    expect(screen.getByRole("button", { name: "Vybrat objekt Deneb" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("shows names only on request, without changing the stored values elsewhere", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    const pin = () => screen.getByTestId("object-map-point-altair");
    expect(pin().textContent).toContain("zobrazovací pásmo");
    const details = screen.getByTestId("object-map-details").textContent;
    fireEvent.click(screen.getByRole("button", { name: "Jen názvy" }));
    expect(screen.getByRole("button", { name: "Jen názvy" }).getAttribute("aria-pressed")).toBe("true");
    expect(pin().textContent).toBe("AltairAltair"); // the <title> and the name
    expect(screen.getByTestId("object-map-details").textContent).toBe(details);
  });

  it("plays the opening animation as presentation only", () => {
    const before = JSON.stringify(battery);
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Přehrát animaci" }));
    expect(screen.getByTestId("object-map-terrain").querySelectorAll("g[data-band]")).toHaveLength(10);
    expect(JSON.stringify(battery)).toBe(before);
    // "Otáčet" from above opens 3D and turns it, as in the approved design.
    fireEvent.click(screen.getByRole("button", { name: "Otáčet" }));
    expect(screen.getByTestId("object-map-3d")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Otáčet" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(screen.getByRole("button", { name: "Otáčet" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("describes the surface, weak fit and actual pair separately from object height", () => {
    render(<ObjectMapView battery={{ ...battery, rating_scale: [1, 10] }} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    expect(screen.getByLabelText("Výška = průměrné hodnocení na škále 1–10")).toBeTruthy();
    const firstPoint = screen.getByTestId(`object-map-point-${map.object_ids[0]}`);
    const expectedRating = 1 + map.heights.values[0]! * 9;
    expect(firstPoint.textContent).toContain(expectedRating.toLocaleString("cs-CZ", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    const reading = screen.getByTestId("object-map-reading");
    expect(reading.textContent).toContain("není dalším měřením");
    expect(reading.textContent).toContain("Shoda této mapy je slabá");
    expect(reading.textContent).toContain("Výška a barva terasy = průměrné hodnocení. Blízkost = podobnost relativních preferencí");
    fireEvent.click(within(screen.getByTestId("object-map-ranked")).getByText("Deneb").closest("button")!);
    fireEvent.click(within(screen.getByTestId("object-map-details")).getByText("Fomalhaut").closest("button")!);
    expect(screen.getByTestId("object-map-pair").textContent).toContain("Podpora vztahu nesplňuje");
    expect(screen.getByTestId("object-map-details").textContent).toContain("škála 1–10");
  });

  it("keeps the top view available without a stored terrain", () => {
    const copy = variant((m) => (m.terrain = { status: "not_computed", reason: "disabled" }));
    render(<ObjectMapView battery={copy} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-svg")).toBeTruthy();
    expect(screen.getByTestId("object-map-terrain").querySelectorAll("path")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "3D terén" }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByTestId("object-map-3d")).toBeNull();
  });

  it("says why a family could not be mapped, and draws nothing", () => {
    const unmapped = variant((m) => Object.assign(m, { outcome: "NOT_MAPPABLE", layout: null, not_mappable: { reason: "no_known_pair", message: "žádná dvojice", objects: [] } }));
    render(<ObjectMapView battery={unmapped} dataOrigin={null} />);
    expect(screen.getByRole("alert").textContent).toContain("Mapu nelze sestavit: žádná dvojice");
    expect(screen.queryByTestId("object-map-svg")).toBeNull();
    expect(screen.getByTestId("object-map-not-placed")).toBeTruthy();
  });

  it("refuses a stored map of another contract by saying so", () => {
    const stored = battery.maps!["aia-sociomap-3"];
    const other = { ...battery, maps: { "aia-sociomap-3": { ...stored, artifact: { ...stored.artifact, contract_version: "4" } } } } as unknown as BatteryWithMaps;
    render(<ObjectMapView battery={other} dataOrigin={null} />);
    expect(screen.getByRole("alert").textContent).toContain("jinou smlouvu");
  });

  it("still reads a run that pinned aia-sociomap-2", () => {
    const older = { ...battery, maps: { "aia-sociomap-2": battery.maps!["aia-sociomap-3"] } } as BatteryWithMaps;
    render(<ObjectMapView battery={older} dataOrigin={null} />);
    expect(screen.getByText("Mapa objektů (aia-sociomap-2)")).toBeTruthy();
    expect(screen.getByTestId("object-map-svg")).toBeTruthy();
  });
});
