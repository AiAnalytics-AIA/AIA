// @vitest-environment jsdom
// A signed-off map on the Results page, drawn as the AIA panel draws it (plan sociomap-5-web,
// chunk 2): the map is routed to the panel's renderer by its stored estimator, an earlier method
// keeps its terraces, and the panel's controls change only what is shown. Stored fixtures only;
// the canvas is a recording stub (jsdom has none), its frames checked through what it was given.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import signedOff from "@/lib/fixtures/object-map-signed-off.json";
import legacy from "@/lib/fixtures/object-map.json";
import golden from "@/lib/fixtures/object-map-draw-golden.json";
import { type BatteryWithMaps, mapLinks } from "@/lib/object-map-view";
import { readTarget } from "@/lib/artifacts/sociomap";
import { LEAD_REVEAL, focusSelector } from "@/lib/lead";
import { parseAiaId } from "@/lib/workbench-artifacts";
import { INITIAL_CAMERA, densityGrid, panelDots, panelNodes, projection, relationGeometry, storedGrid, terrainAt } from "@/lib/object-map-panel";
import { type SignedOffRespondents, storedFrame } from "@/lib/object-map-signed-off";
import { num } from "@/lib/sociomapping-view";
import { sharePercent } from "./ObjectMapPanel";
import { ObjectMapView } from "./ObjectMapView";

const [hudba, sum] = signedOff.batteries as unknown as BatteryWithMaps[];
const legacyBattery = legacy.sociomap.batteries[0] as unknown as BatteryWithMaps;
const map = hudba.maps!["aia-sociomap-5"].artifact;

let frames = 0;
let radii: number[] = [];
let texts: string[] = [];
beforeEach(() => {
  frames = 0;
  radii = [];
  texts = [];
  // Enough of a 2D context for the drawing to run; every frame starts with the background.
  const context = new Proxy({ measureText: (s: string) => ({ width: s.length * 6.2 }) } as Record<string, unknown>, {
    get: (target, key) => (key in target ? target[key as string]
      // A frame starts with the background; the veil of a weakly determined map is a later fill.
      : key === "fillRect" ? () => { if (target.fillStyle === "#07090c") { frames++; radii = []; texts = []; } }
      : key === "fillText" ? (text: string) => { texts.push(text); }
      : key === "arc" ? (_x: number, _y: number, r: number) => { radii.push(r); }
      : key === "createLinearGradient" ? () => ({ addColorStop: () => {} }) : () => {}),
    set: (target, key, value) => { target[key as string] = value; return true; },
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const canvas = () => screen.getByTestId("object-map-canvas");
const drawn = () => (canvas().getAttribute("data-relations") || "").split(" ").filter(Boolean);
const camera = () => JSON.parse(canvas().getAttribute("data-camera")!);
/** The map's overlays, opened as a reader does: Nastavení mapy and Nástroje from the bar (popovers),
 *  the object list from Nastavení mapy (a tab of the side sheet), the legend from its chip. */
const openSettings = () => fireEvent.click(screen.getByRole("button", { name: "Nastavení mapy" }));
const openTools = () => fireEvent.click(screen.getByRole("button", { name: "Nástroje" }));
const openList = () => { openSettings(); fireEvent.click(screen.getByRole("button", { name: "Správa objektů" })); return within(screen.getByTestId("object-map-panel-list")); };
const openLegend = () => fireEvent.click(screen.getByTitle("Legenda (L)"));
const openInfo = () => fireEvent.click(screen.getByRole("button", { name: /^Informace o mapě/ }));
/** Waits for the next drawn frame (draws are coalesced into animation frames). */
const nextFrame = async (after = frames) => waitFor(() => expect(frames).toBeGreaterThan(after));

/** Where the opening frame (900 x 700, the panel's camera) puts object k, from the same projection. */
const nodeAt = (k: number) => {
  const node = panelNodes(hudba, map, storedFrame(map)!)[k];
  const q = projection(INITIAL_CAMERA, 900, 700).project(node.x, node.y, terrainAt(storedGrid(map)!, node.x, node.y) + 0.8);
  return { x: q.x, y: q.y };
};

describe("which drawing a stored map gets", () => {
  it("draws a signed-off map with the panel's renderer, never as terraces", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin="SYNTHETIC_FIXTURE" />);
    await nextFrame(0);
    expect(screen.getByTestId("object-map-panel")).toBeTruthy();
    expect(screen.queryByTestId("object-map-svg")).toBeNull();
    expect(screen.queryByTestId("object-map-terrain")).toBeNull();
    expect(screen.getByText("Mapa objektů (aia-sociomap-5)")).toBeTruthy();
    // The page around the map stays the web's chips; the facts are in the map's ⓘ box, without the terraces' texts.
    expect(screen.getByTestId("object-map-origin").getAttribute("data-origin-kind")).toBe("SIMULATED");
    openInfo();
    const facts = screen.getByTestId("object-map-support").textContent!;
    expect(facts).toContain("Dvojice: 62 spolehlivé · 4 slabé · 0 neznámé vztahy");
    expect(facts).not.toContain("deseti pásem");
  });

  it("knows a signed-off map stored under an edited version's name", () => {
    const edited = { ...hudba, maps: { "aia-sociomap-5+e1": hudba.maps!["aia-sociomap-5"], "aia-sociomap-3": legacyBattery.maps!["aia-sociomap-3"] } };
    render(<ObjectMapView battery={edited} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-panel")).toBeTruthy();
    expect(screen.getByText("Mapa objektů (aia-sociomap-5+e1)")).toBeTruthy();
  });

  it("keeps an earlier method's map exactly as before", () => {
    render(<ObjectMapView battery={legacyBattery} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-svg")).toBeTruthy();
    expect(screen.queryByTestId("object-map-panel")).toBeNull();
    expect(screen.getByTestId("object-map-support").textContent).toContain("Šířka kopců");
  });
});

describe("drawing in the browser", () => {
  it("draws after a remount, as React's development double mount does", async () => {
    render(<StrictMode><ObjectMapView battery={hudba} dataOrigin="SYNTHETIC_FIXTURE" /></StrictMode>);
    await nextFrame(0);
  });
});

describe("the panel's controls", () => {
  it("opens in 3D on Relativni with the 5 strongest reliable pairs, nothing selected", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(camera()).toEqual({ yaw: -0.55, pitch: 0.72, zoom: 1, panX: 0, panY: 0 });
    expect(canvas().getAttribute("data-norm")).toBe("range");
    openSettings();
    expect(screen.getByRole("button", { name: "Relativní" }).getAttribute("aria-pressed")).toBe("true");
    const strongest = mapLinks(map).sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).slice(0, 5).map((l) => `${l.a}|${l.b}`);
    expect(drawn().sort()).toEqual(strongest.sort());
    expect(canvas().getAttribute("data-selected")).toBe("");
  });

  it("switches Absolutni / Relativni and the relation display, redrawing each time", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    openLegend();
    const legend = () => screen.getByTestId("object-map-legend-scale").textContent;
    expect(legend()).toContain("rozsah");
    const before = frames;
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Absolutní" }));
    expect(canvas().getAttribute("data-norm")).toBe("absolute");
    await nextFrame(before);
    // Absolutni reads the declared 1-10 scale's ends (an open popover folds the legend to its chip).
    openSettings();
    openLegend();
    expect(legend()).toBe("1,00absolutní10,0");
    openTools();
    fireEvent.click(screen.getByRole("button", { name: "Vše" }));
    expect(drawn()).toHaveLength(mapLinks(map).length);
    fireEvent.click(screen.getByRole("button", { name: "Vybraný" }));
    expect(drawn()).toEqual([]); // nothing selected: no object's relations to show
  });

  it("offers Absolutni only for a map that stores its absolute terrain", () => {
    const old = structuredClone(hudba);
    delete (old.maps!["aia-sociomap-5"].artifact.terrain as { absolute_height?: unknown }).absolute_height;
    render(<ObjectMapView battery={old} dataOrigin={null} />);
    openSettings();
    expect((screen.getByRole("button", { name: "Absolutní" }) as HTMLButtonElement).disabled).toBe(true);
    cleanup();
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openSettings();
    expect((screen.getByRole("button", { name: "Absolutní" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("selects an object from the list: its relations, highlighted; again clears it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    // The pick opens its detail; the list, back in its tab, marks it.
    expect(openList().getByRole("button", { name: "Vybrat objekt Rock" }).getAttribute("aria-pressed")).toBe("true");
    const id = canvas().getAttribute("data-selected")!;
    expect(map.object_ids).toContain(id);
    expect(drawn().length).toBeGreaterThan(0);
    expect(drawn().length).toBeLessThanOrEqual(5);
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
    openTools();
    fireEvent.click(screen.getByRole("button", { name: "Vybraný" }));
    expect(drawn()).toEqual(mapLinks(map).filter((l) => l.a === id || l.b === id).map((l) => `${l.a}|${l.b}`));
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    expect(canvas().getAttribute("data-selected")).toBe("");
  });

  it("selects by clicking a node, turns on a drag, clears on a click on free ground", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0); // the nodes' places come from the drawn frame
    const at = nodeAt(0);
    fireEvent.pointerMove(canvas(), { clientX: at.x, clientY: at.y });
    expect(canvas().style.cursor).toBe("pointer");
    fireEvent.pointerDown(canvas(), { clientX: at.x + 3, clientY: at.y - 2, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at.x + 3, clientY: at.y - 2, pointerId: 1 });
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[0]);
    await nextFrame();
    // A drag that starts on the node turns the map instead and keeps the selection.
    fireEvent.pointerDown(canvas(), { clientX: at.x, clientY: at.y, pointerId: 1 });
    fireEvent.pointerMove(canvas(), { clientX: at.x + 40, clientY: at.y + 10, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at.x + 40, clientY: at.y + 10, pointerId: 1 });
    expect(camera().yaw).toBeCloseTo(-0.55 + 40 * 0.007, 12);
    expect(camera().pitch).toBeCloseTo(0.72 + 10 * 0.004, 12);
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[0]);
    fireEvent.pointerDown(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    expect(canvas().getAttribute("data-selected")).toBe("");
  });

  it("zooms by the wheel over the map, as the panel, and leaves the page's scroll alone elsewhere", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(fireEvent.wheel(canvas(), { deltaY: 100 })).toBe(false); // prevented: the map zooms
    expect(camera().zoom).toBeCloseTo(0.91, 12);
    expect(fireEvent.wheel(canvas(), { deltaY: -100 })).toBe(false);
    expect(camera().zoom).toBeCloseTo(0.91 * 1.1, 12);
    expect(fireEvent.wheel(screen.getByTestId("object-map-panel"), { deltaY: 100 })).toBe(true); // outside: scrolls
    expect(camera().zoom).toBeCloseTo(0.91 * 1.1, 12);
  });

  it("opens the map stage in full screen and closes it again", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const stage = screen.getByTestId("object-map-stage");
    const request = vi.fn(() => Promise.resolve());
    const exit = vi.fn(() => Promise.resolve());
    Object.assign(stage, { requestFullscreen: request });
    Object.assign(document, { exitFullscreen: exit });
    const button = screen.getByRole("button", { name: "Celá obrazovka" });
    fireEvent.click(button);
    expect(request).toHaveBeenCalledOnce();
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: stage });
    fireEvent(document, new Event("fullscreenchange"));
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    expect(exit).toHaveBeenCalledOnce();
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: null });
    fireEvent(document, new Event("fullscreenchange"));
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("zooms by the tools, goes to 2D and back to 3D, and recentres", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.wheel(canvas(), { deltaY: 100 });
    expect(camera().zoom).toBeCloseTo(0.91, 12);
    fireEvent.click(screen.getByRole("button", { name: "Přiblížit" }));
    expect(camera().zoom).toBeCloseTo(0.91 * 1.13, 12);
    const top = screen.getByRole("button", { name: "Pohled shora" });
    fireEvent.click(top);
    expect(camera().pitch).toBe(0);
    expect(camera().yaw).toBeCloseTo(0, 12);
    expect(top.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "3D prostor" }));
    expect(camera().pitch).toBe(0.72);
    fireEvent.click(screen.getByRole("button", { name: "Vycentrovat" }));
    expect(camera()).toEqual({ yaw: -0.55, pitch: 0.72, zoom: 1, panX: 0, panY: 0 });
  });
});

// Where the web leaves the panel (Sprint 5, the product owner's Q50 (b)): the selection's state,
// each case the screenshot it reproduces, failing on the panel's own behaviour.
describe("the display state, where the web leaves the panel", () => {
  const enterFull = () => {
    const stage = screen.getByTestId("object-map-stage");
    Object.assign(stage, { requestFullscreen: () => Promise.resolve() });
    fireEvent.click(screen.getByRole("button", { name: "Celá obrazovka" }));
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: stage });
    fireEvent(document, new Event("fullscreenchange"));
  };
  afterEach(() => { Object.defineProperty(document, "fullscreenElement", { configurable: true, value: null }); });
  const strongest = () => mapLinks(map).sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).slice(0, 5).map((l) => `${l.a}|${l.b}`).sort();

  it("starts the respondent map with nothing selected, and comes back to the objects with nothing selected", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(openList().getAllByRole("button")[0]);
    expect(canvas().getAttribute("data-selected")).not.toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(canvas().getAttribute("data-selected")).toBe("");
    expect(canvas().getAttribute("data-relation")).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
    expect(canvas().getAttribute("data-selected")).toBe("");
    expect(drawn().sort()).toEqual(strongest());
  });

  it("forgets the ringed respondent when the map changes", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    // A dot no other dot or marker sits within a hit radius of, where the drawn frame put it.
    const dots = panelDots(map, storedFrame(map)!);
    const grid = densityGrid(map)!;
    const P = projection(INITIAL_CAMERA, 900, 700);
    const at = dots.map((d) => P.project(d.x, d.y, terrainAt(grid, d.x, d.y) + 0.65));
    const lone = at.findIndex((q, k) => at.every((o, j) => j === k || Math.hypot(o.x - q.x, o.y - q.y) > 16));
    fireEvent.pointerDown(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    expect(canvas().getAttribute("data-person")).toBe(dots[lone].id);
    fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(canvas().getAttribute("data-person")).toBe("");
  });

  it("draws the strongest relations in full screen as on the page: the selection's five, the map's five without one", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const first = () => openList().getAllByRole("button")[0];
    fireEvent.click(first());
    const id = canvas().getAttribute("data-selected")!;
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
    enterFull();
    expect(canvas().getAttribute("data-selected")).toBe(id);
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
    expect(drawn().sort()).not.toEqual(strongest());
    // Nothing selected: the map's five strongest.
    fireEvent.click(first());
    expect(canvas().getAttribute("data-selected")).toBe("");
    expect(drawn().sort()).toEqual(strongest());
  });
});

describe("accessibility", () => {
  // The page holds the landmarks: the side column is layout, not a complementary region of its own
  // nested inside them (axe landmark-complementary-is-top-level, Sociomapa audit 2026-10-22).
  it("adds no landmark of its own beside the map, on the signed-off map and an older method's", () => {
    const { unmount } = render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(screen.queryAllByRole("complementary")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(screen.queryAllByRole("complementary")).toHaveLength(0);
    unmount();
    render(<ObjectMapView battery={legacyBattery} dataOrigin={null} />);
    expect(screen.queryAllByRole("complementary")).toHaveLength(0);
  });

  it("names the canvas, describes its lines, and lists every object as a button", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const img = screen.getByRole("img", { name: "Mapa objektů Hudební žánry: 12 objektů na terénu průměrného hodnocení" });
    expect(document.getElementById(img.getAttribute("aria-describedby")!)!.textContent).toBe("Čar vztahů na mapě: 5");
    const list = openList();
    expect(list.getAllByRole("button")).toHaveLength(map.object_ids.length);
    // The list prints each stored mean on the declared scale, as the panel's object list.
    expect(list.getByRole("button", { name: "Vybrat objekt Pop" }).textContent).toContain("6,32");
    // The object nobody rated is not on the map (its listing is the next chunk's).
    expect(list.queryByRole("button", { name: "Vybrat objekt Reggae" })).toBeNull();
    for (const name of ["Přiblížit", "Oddálit", "Pohled shora", "3D prostor", "Vycentrovat"]) expect(screen.getByRole("button", { name })).toBeTruthy();
  });

  it("folds the legend's key out and back, as the panel's legend", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openLegend();
    const more = screen.getByRole("button", { name: "Co znamenají čáry a značky ▸" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(more);
    const key = screen.getByTestId("object-map-legend-key").textContent!;
    expect(key).toContain("síla vztahu |r|: 0 → ");
    expect(key).toContain("(nejsilnější vztah mapy)");
    expect(key).toContain("souhlasně · opačně; čára nemá směr");
    fireEvent.click(screen.getByRole("button", { name: "Skrýt vysvětlivky ▴" }));
    expect(screen.queryByTestId("object-map-legend-key")).toBeNull();
    expect(screen.getByTestId("object-map-legend-info").textContent).toContain("relativní · nejnižší objekt = 15 % výšky nejvyššího");
  });

  it("sizes the nodes by the mapped objects, not by those nobody rated", async () => {
    const big = structuredClone(hudba);
    const stored = big.maps!["aia-sociomap-5"].artifact;
    // 12 mapped + 38 nobody rated: the 38 are left out of the map, so the nodes keep their full size
    // (up to 30 objects); with 50 mapped they would shrink to sqrt(30 / 50).
    stored.objects_not_placed = Array.from({ length: 38 }, (_, k) => `extra-${k}`);
    stored.credibility = undefined; // no uncertainty circle among the measured discs
    render(<ObjectMapView battery={big} dataOrigin={null} />);
    await nextFrame(0);
    const scale = 1;
    expect(Math.max(...radii)).toBeCloseTo(5.7 * scale + 2.5, 9); // the white ring is 2.5 px wider, unscaled
    expect(Math.min(...radii)).toBeCloseTo(5.7 * scale, 9);
  });

  it("keeps the objects and the facts when the map has no terrain to draw on", () => {
    const flat = structuredClone(hudba);
    flat.maps!["aia-sociomap-5"].artifact.terrain = { status: "not_computed", reason: "test" };
    render(<ObjectMapView battery={flat} dataOrigin={null} />);
    expect(screen.queryByTestId("object-map-canvas")).toBeNull();
    expect(screen.getByTestId("object-map-no-terrain").textContent).toContain("test");
    expect(within(screen.getByTestId("object-map-panel-list")).getAllByRole("button")).toHaveLength(map.object_ids.length);
    expect(screen.getByTestId("object-map-support")).toBeTruthy();
  });

  it("draws a weakly determined map too (its statement is the next chunk's)", () => {
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-panel")).toBeTruthy();
    expect(drawn()).toEqual([]); // no reliable pair
  });
});

describe("what the map says about itself", () => {
  it("veils a weakly determined map behind the panel's statement, with its split-half score", async () => {
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
    await nextFrame(0);
    expect(texts).toContain("Slabě určená mapa");
    expect(texts.join(" ")).toContain("Dvě poloviny vzorku se shodnou jen v 54 % srovnání „co je blíž“ (50 % = náhoda).");
    expect(texts).toContain("typická nejistota polohy objektu");
  });

  it("says when no relation differs from chance, and notes a sparse design on a map that is not weak", async () => {
    const none = structuredClone(hudba);
    Object.assign(none.maps!["aia-sociomap-5"].artifact.credibility!, { split_half: null, rule: "no_reliable_pair", weakly_determined: true });
    render(<ObjectMapView battery={none} dataOrigin={null} />);
    await nextFrame(0);
    expect(texts).toContain("Žádná spolehlivá struktura");
    expect(texts).not.toContain("Slabě určená mapa");
    cleanup();
    const sparse = structuredClone(hudba);
    sparse.maps!["aia-sociomap-5"].artifact.sparse_design = { flag: true, share_below_layout_floor: 0.4, weakly_connected: [] };
    const before = frames;
    render(<ObjectMapView battery={sparse} dataOrigin={null} />);
    await nextFrame(before);
    expect(texts).toContain("Řídký design: polohy málokdy společně hodnocených objektů jsou určeny slabě");
    expect(texts).not.toContain("Slabě určená mapa");
  });

  it("names the objects nobody rated beside the map, in the panel's words", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openList();
    expect(screen.getByTestId("object-map-unplaced-objects").textContent).toBe("Neumístěno (nikdo je nehodnotil, proto bez polohy na mapě): Reggae.");
    cleanup();
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
    openList();
    expect(screen.queryByTestId("object-map-unplaced-objects")).toBeNull();
  });
});

describe("the respondent map", () => {
  const show = () => fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));

  it("switches to the respondent map: dots, markers, its legend and counts, no relations", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    const before = frames;
    show();
    await nextFrame(before);
    expect(canvas().getAttribute("data-map")).toBe("respondents");
    expect(canvas().getAttribute("data-relations")).toBe("");
    expect(screen.getByRole("button", { name: "Respondenti" }).getAttribute("aria-pressed")).toBe("true");
    // 219 clearly and 75 weakly placed dots, one marker per object (two squares each), no circle.
    expect(radii.filter((r) => r === 2.6)).toHaveLength(219 + 75);
    expect(texts).not.toContain("typická nejistota polohy objektu");
    expect(screen.queryByRole("group", { name: "Vztahy" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Normalizace" })).toBeNull();
    openLegend();
    expect(screen.getByTestId("object-map-legend-scale").textContent).toBe("0,00hustota1,00");
    expect(screen.getByTestId("object-map-legend-info").textContent).toContain("hustota jasně umístěných respondentů");
    openInfo();
    const counts = screen.getByTestId("object-map-respondent-counts").textContent!;
    expect(counts).toContain("Jasný směr: 73 % (219) · tvoří výšku");
    expect(counts).toContain("Slabý směr: 25 % (75) · světlé body");
    expect(counts).toContain("Bez polohy: 6");
    expect(counts).not.toContain("orientační");
    fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
    expect(canvas().getAttribute("data-map")).toBe("objects");
    expect(screen.queryByTestId("object-map-respondent-counts")).toBeNull();
  });

  it("rings a clicked respondent and clears it on free ground", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    show();
    await nextFrame(0);
    const dots = panelDots(map, storedFrame(map)!);
    const grid = densityGrid(map)!;
    const P = projection(INITIAL_CAMERA, 900, 700);
    // A dot no other dot or marker sits within a hit radius of: the click must land on it alone.
    const at = dots.map((d) => P.project(d.x, d.y, terrainAt(grid, d.x, d.y) + 0.65));
    const lone = at.findIndex((q, k) => at.every((o, j) => j === k || Math.hypot(o.x - q.x, o.y - q.y) > 16));
    fireEvent.pointerDown(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    expect(canvas().getAttribute("data-person")).toBe(dots[lone].id);
    await nextFrame();
    fireEvent.pointerDown(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    expect(canvas().getAttribute("data-person")).toBe("");
  });

  it("notes a set under the declared minimum of objects, and one under the minimum ratings", async () => {
    const small = (k: number) => {
      const b = structuredClone(hudba), m = b.maps!["aia-sociomap-5"].artifact;
      m.object_ids = m.object_ids.slice(0, k);
      m.layout = { ...m.layout!, points: m.layout!.points.slice(0, k) };
      const r = m.respondents as SignedOffRespondents;
      r.informative = false;
      return b;
    };
    render(<ObjectMapView battery={small(5)} dataOrigin={null} />);
    show();
    await nextFrame(0);
    expect(texts).toContain("Sada má 5 objektů: mapa respondentů je jen orientační (spolehlivá od 6)");
    openInfo();
    expect(screen.getByTestId("object-map-respondent-counts").textContent).toContain("Mapa respondentů: jen orientační · 5 obj. (spolehlivá od 6)");
    cleanup();
    // An edited version may declare more ratings than the set has objects: the number is the declared one.
    const strict = small(4);
    strict.maps!["aia-sociomap-5"].artifact.spec.respondent_map!.min_ratings = 5;
    const before = frames;
    render(<ObjectMapView battery={strict} dataOrigin={null} />);
    show();
    await nextFrame(before);
    expect(texts).toContain("Sada má 4 objekty: respondenty nelze umístit (potřeba aspoň 5 hodnocení)");
    openInfo();
    expect(screen.getByTestId("object-map-respondent-counts").textContent).not.toContain("orientační");
  });

  it("veils a weakly determined respondent map too, and offers no switch without a stored respondent map", async () => {
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
    show();
    await nextFrame(0);
    expect(canvas().getAttribute("data-map")).toBe("respondents");
    expect(texts).toContain("Slabě určená mapa");
    cleanup();
    const none = structuredClone(hudba);
    none.maps!["aia-sociomap-5"].artifact.respondents = { status: "not_computed", reason: "test" };
    render(<ObjectMapView battery={none} dataOrigin={null} />);
    expect(screen.queryByRole("button", { name: "Respondenti" })).toBeNull();
  });
});

describe("taste segments", () => {
  /** The stored hudba map with its taste segments replaced, as the golden run's variants. */
  const variant = (name: string): BatteryWithMaps => {
    const b = structuredClone(hudba);
    const seg = (b.maps!["aia-sociomap-5"].artifact.respondents as SignedOffRespondents).segments!;
    const patch = structuredClone((golden.segmentPatches as Record<string, object>)[name]) as Partial<NonNullable<SignedOffRespondents["segments"]>>;
    if (name === "borderline") patch.hint = { k: 2, shares: [0.58, 0.42], profiles: seg.profiles.slice(0, 2) };
    Object.assign(seg, patch);
    return b;
  };
  const sources: Record<string, BatteryWithMaps> = { hudba, sum, ...Object.fromEntries(Object.keys(golden.segmentPatches).map((k) => [k, variant(k)])) };

  for (const [name, scene] of Object.entries(golden.segmentScenes)) {
    it(`says what the panel says about the segments of ${name}, under the legend and in the map info`, () => {
      render(<ObjectMapView battery={sources[name]} dataOrigin={null} />);
      fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
      openLegend();
      expect(screen.getByTestId("object-map-segments").textContent).toBe(scene.legend);
      openInfo();
      const row = screen.getByTestId("object-map-segments-row");
      expect(row.textContent).toBe(`Segmenty: ${scene.row!.value}`);
      expect(row.firstElementChild!.getAttribute("title")).toBe(scene.row!.help);
    });
  }

  it("colours a segment's swatch in the legend as its dots", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    openLegend();
    const swatches = [...screen.getByTestId("object-map-segments").querySelectorAll("span[aria-hidden]")].map((s) => (s as HTMLElement).style.background);
    expect(swatches).toEqual(["rgb(127, 211, 255)", "rgb(255, 196, 107)", "rgb(255, 143, 177)", "rgb(154, 163, 173)"]);
  });

  it("quotes the declared thresholds, not fixed ones", () => {
    const b = variant("tooFew");
    b.maps!["aia-sociomap-5"].artifact.spec.segments = { min_respondents: 40, min_ratings: 6, colour_membership: 0.9 };
    render(<ObjectMapView battery={b} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    openInfo();
    expect(screen.getByTestId("object-map-segments-row").firstElementChild!.getAttribute("title")).toBe("Segmenty potřebují alespoň 40 lidí s alespoň 6 hodnocenými objekty.");
  });

  it("quotes the declared membership for the colours, not a fixed 80 %", () => {
    const b = structuredClone(hudba);
    b.maps!["aia-sociomap-5"].artifact.spec.segments = { min_respondents: 30, min_ratings: 5, colour_membership: 0.9 };
    render(<ObjectMapView battery={b} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    openInfo();
    expect(screen.getByTestId("object-map-segments-row").firstElementChild!.getAttribute("title")).toContain("(≥ 90 %)");
  });

  it("prints a share as the panel does: rounded to 4 decimals first", () => {
    // The panel's payload rounds shares to 4 decimals; on these edges a direct rounding differs by a point.
    expect(sharePercent(23 / 107)).toBe("22 %");
    expect(sharePercent(0.285047)).toBe("28 %");
    expect(sharePercent(0.46598639455782315)).toBe("47 %");
  });
});


describe("what a click shows in the detail window", () => {
  const card = () => screen.getByTestId("object-map-detail");
  const label = (id: string) => hudba.objects.find((o) => o.id === id)!.label;

  it("asks for a click, then shows a chosen object's stored numbers and strongest relations", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    // Nothing chosen, no detail window; a chosen object opens it.
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    expect(card().textContent).toContain("Detail objektu / vztahu");
    expect(screen.getByTestId("object-map-detail-label").textContent).toBe("Rock");
    const k = map.object_ids.indexOf(canvas().getAttribute("data-selected")!);
    const text = card().textContent!;
    expect(text).toContain("Průměrné hodnocení");
    expect(text).toContain("Provázanost (0–100)");
    expect(text).toContain(num(100 * map.scores!.objects[k].connectedness!, 1));
    // The alignment says nothing on this map (every object PRIMARY, each respondent's mean removed).
    expect(text).not.toContain("Soulad s rodinou");
    const rows = within(screen.getByTestId("object-map-detail-relations")).getAllByText(/^[+−-]?\d,\d\d$/);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThanOrEqual(5);
    // Nothing the map does not store: no p-value, no noise level, no rating distribution.
    expect(text).not.toMatch(/Úroveň šumu|Rozložení hodnocení|První volba/);
  });

  // The canvas takes no keyboard: the object's listed relations open a pair as a click on its line does
  // (artifact-sociomap audit, 2026-10-22).
  // Enter and Space on a button are the browser's: the workbench check presses them (jsdom has no activation).
  it("opens a relation from the object's card, a focusable button named by what it shows, and closes it again", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    const i = map.object_ids.indexOf(canvas().getAttribute("data-selected")!);
    const rows = within(screen.getByTestId("object-map-detail-relations")).getAllByRole("button");
    expect(rows.length).toBeGreaterThan(0);
    const row = rows[0];
    // Its name starts with the text it shows (WCAG 2.5.3), then says what it does.
    expect(row.textContent).toMatch(/^.+ [+−-]?\d,\d\d, ukázat vztah Rock – .+$/);
    row.focus();
    expect(document.activeElement).toBe(row);
    fireEvent.click(row);
    const j = map.object_ids.findIndex((id) => row.textContent!.endsWith(`– ${label(id)}`));
    expect(canvas().getAttribute("data-relation")).toBe(`${map.object_ids[i]}|${map.object_ids[j]}`);
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[i]);
    expect(screen.getByTestId("object-map-detail-relation").textContent).toContain(`${label(map.object_ids[i])} – ${label(map.object_ids[j])}`);
    const pressed = within(screen.getByTestId("object-map-detail-relations")).getAllByRole("button")[0];
    expect(pressed.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(pressed);
    expect(canvas().getAttribute("data-relation")).toBe("");
    expect(screen.queryByTestId("object-map-detail-relation")).toBeNull();
  });

  it("selects a relation by a click on its line: the pair's r, interval, N and verdict", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    // A drawn line's midpoint (the panel's own hits on the opening frame) with no object within its hit radius.
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const line = (golden.scenes.relativeInitial.hits as [string, number, number, number, number, number][])
      .find((h) => h[0] === "relation" && nodes.every((q) => Math.hypot(q.x - h[3], q.y - h[4]) > 14))!;
    const [, i, j, x, y] = line;
    fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    expect(canvas().getAttribute("data-relation")).toBe(`${map.object_ids[i]}|${map.object_ids[j]}`);
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[i]);
    const block = screen.getByTestId("object-map-detail-relation").textContent!;
    expect(block).toContain("Vybraný vztah");
    expect(block).toContain(`${label(map.object_ids[i])} – ${label(map.object_ids[j])}`);
    const r = map.relations.r[i][j]!;
    expect(block).toContain((r >= 0 ? "+" : "") + num(r, 2));
    // This estimator stores no interval: "95 % —", as the panel prints a missing one.
    expect(map.relations.interval![i][j]).toBeNull();
    expect(block).toContain("95 % —");
    expect(block).toContain(String(map.relations.n[i][j]));
    // "zřetelný" from |r| 0,3, as the panel words it.
    const word = Math.abs(r) >= 0.3 ? "zřetelný" : "slabý", sign = r >= 0 ? "kladný" : "záporný";
    expect(screen.getByTestId("object-map-detail-verdict").textContent).toBe(`Spolehlivý ${word} ${sign} vztah: silnější, než jaký vytvoří náhoda.`);
    // The object's own detail follows under the relation; choosing an object from the list drops the relation.
    expect(screen.getByTestId("object-map-detail-label").textContent).toBe(label(map.object_ids[i]));
    const reselect = () => { fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 }); fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 }); };
    fireEvent.click(openList().getByRole("button", { name: `Vybrat objekt ${label(map.object_ids[j])}` }));
    expect(canvas().getAttribute("data-relation")).toBe("");
    expect(screen.queryByTestId("object-map-detail-relation")).toBeNull();
    // So does a click on an object on the map (the panel's list does; its canvas keeps a stale relation).
    reselect();
    expect(canvas().getAttribute("data-relation")).not.toBe("");
    const other = map.object_ids.findIndex((_, k) => k !== i && k !== j && nodes.every((q, m) => m === k || Math.hypot(q.x - nodes[k].x, q.y - nodes[k].y) > 28));
    fireEvent.pointerDown(canvas(), { clientX: nodes[other].x, clientY: nodes[other].y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: nodes[other].x, clientY: nodes[other].y, pointerId: 1 });
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[other]);
    expect(canvas().getAttribute("data-relation")).toBe("");
    // A click on free ground clears both.
    reselect();
    fireEvent.pointerDown(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    expect(canvas().getAttribute("data-selected")).toBe("");
    expect(canvas().getAttribute("data-relation")).toBe("");
    expect(screen.queryByTestId("object-map-detail-relation")).toBeNull();
  });

  it("prints a stored interval as the panel does: signed, decimal comma", async () => {
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const line = (golden.scenes.relativeInitial.hits as [string, number, number, number, number, number][])
      .find((h) => h[0] === "relation" && nodes.every((q) => Math.hypot(q.x - h[3], q.y - h[4]) > 14))!;
    const [, i, j] = line;
    const interval = map.relations.r.map((row, a) => row.map((_, b) => ((a === i && b === j) || (a === j && b === i) ? [-0.05, 0.41] as [number, number] : null)));
    const stored = hudba.maps!["aia-sociomap-5"];
    const withInterval = { ...hudba, maps: { "aia-sociomap-5": { ...stored, artifact: { ...map, relations: { ...map.relations, interval } } } } };
    render(<ObjectMapView battery={withInterval} dataOrigin={null} />);
    await nextFrame(0);
    fireEvent.pointerDown(canvas(), { clientX: line[3], clientY: line[4], pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: line[3], clientY: line[4], pointerId: 1 });
    expect(screen.getByTestId("object-map-detail-relation").textContent).toContain("95 % -0,05 až +0,41");
  });

  it("words a relation slabý below the declared |r| and zřetelný from it (0,3 on a map stored before it)", async () => {
    // A drawn pair's midpoint on the opening frame (it does not depend on r), clear of every object.
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const index = (id: string) => map.object_ids.indexOf(id);
    const [i, j, x, y] = mapLinks(map).map((l) => {
      const [a, b] = [index(l.a), index(l.b)];
      const mid = relationGeometry(nodes[a], nodes[b], a < b ? 1 : -1, 0, 0)!.mid;
      return [a, b, mid.x, mid.y];
    }).find(([, , mx, my]) => nodes.every((q) => Math.hypot(q.x - mx, q.y - my) > 14))!;
    // Set the pair to 0,25 and 0,30 and click it on "Vše".
    const verdict = async (v: number, clear?: number) => {
      const r = map.relations.r.map((row, a) => row.map((x0, b) => ((a === i && b === j) || (a === j && b === i) ? v : x0)));
      const stored = hudba.maps!["aia-sociomap-5"];
      const spec = clear === undefined ? map.spec : { ...map.spec, relation: { ...map.spec.relation, clear_effect: clear } };
      render(<ObjectMapView battery={{ ...hudba, maps: { "aia-sociomap-5": { ...stored, artifact: { ...map, spec, relations: { ...map.relations, r } } } } }} dataOrigin={null} />);
      openTools();
      fireEvent.click(screen.getByRole("button", { name: "Vše" }));
      await nextFrame(0);
      fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 });
      fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 });
      const text = screen.getByTestId("object-map-detail-verdict").textContent;
      cleanup();
      frames = 0;
      return text;
    };
    expect(map.spec.relation.clear_effect).toBeUndefined();
    expect(await verdict(0.25)).toBe("Spolehlivý slabý kladný vztah: silnější, než jaký vytvoří náhoda.");
    expect(await verdict(0.3)).toBe("Spolehlivý zřetelný kladný vztah: silnější, než jaký vytvoří náhoda.");
    // An edited version's threshold (Metodika) moves the word.
    expect(await verdict(0.25, 0.2)).toBe("Spolehlivý zřetelný kladný vztah: silnější, než jaký vytvoří náhoda.");
    expect(await verdict(0.3, 0.4)).toBe("Spolehlivý slabý kladný vztah: silnější, než jaký vytvoří náhoda.");
  });

  it("shows a clicked respondent's profile on the respondent map, and asks for a click without one", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    const dots = panelDots(map, storedFrame(map)!);
    const grid = densityGrid(map)!;
    const P = projection(INITIAL_CAMERA, 900, 700);
    const at = dots.map((d) => P.project(d.x, d.y, terrainAt(grid, d.x, d.y) + 0.65));
    const lone = at.findIndex((q, k) => at.every((o, j) => j === k || Math.hypot(o.x - q.x, o.y - q.y) > 16));
    fireEvent.pointerDown(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    const id = dots[lone].id, k = map.respondent_ids!.indexOf(id);
    const r = map.respondents as SignedOffRespondents;
    expect(screen.getByTestId("object-map-detail-person").textContent).toBe(id);
    expect(card().textContent).toContain("Profil respondenta");
    const text = card().textContent!;
    expect(text).toContain("Poloha z odpovědí");
    expect(text).toContain(`Mapa vysvětluje ${Math.round(100 * (1 - r.misfit[k]!))} % rozdílů v jeho hodnoceních`);
    expect(text.includes("slabě umístěn")).toBe(r.placement[k] === "FADED");
    const seg = r.segments!;
    expect(text).toContain(seg.coloured![k] ? `Chuťový segment ${seg.label![k] + 1}` : "Není jasně v jednom chuťovém segmentu");
  });
});

describe("Export PNG", () => {
  const save = () => {
    const saved: { name: string; href: string }[] = [];
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/png;base64,AAAA");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { saved.push({ name: this.download, href: this.href }); });
    return saved;
  };

  it("saves the object map with the legend drawn in, as Sociomapa_objekty.png", async () => {
    const saved = save();
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    openSettings();
    const button = screen.getByRole("button", { name: "Export PNG" });
    expect(button.getAttribute("title")).toBe("Uloží aktuální pohled na mapu jako obrázek PNG.");
    texts = [];
    fireEvent.click(button);
    expect(saved).toEqual([{ name: "Sociomapa_objekty.png", href: "data:image/png;base64,AAAA" }]);
    // The legend card's words, as the page's legend shows them.
    openLegend();
    const marks = screen.getByTestId("object-map-legend-scale").children;
    expect(texts).toEqual(["VÝŠKA · PRŮMĚRNÉ HODNOCENÍ", ...Array.from(marks).map((m) => m.textContent)]);
  });

  it("saves the respondent map with its density legend and segments, as Sociomapa_respondenti.png", async () => {
    const saved = save();
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    texts = [];
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Export PNG" }));
    expect(saved.map((x) => x.name)).toEqual(["Sociomapa_respondenti.png"]);
    expect(texts.slice(0, 4)).toEqual(["VÝŠKA · SHLUKY RESPONDENTŮ", "0,00", "hustota", "1,00"]);
    expect(texts).toContain("CHUŤOVÉ SEGMENTY · PŘEKRÝVAJÍ SE");
    expect(texts.at(-1)).toBe("není jasně v jednom segmentu");
  });
});

describe("the map's overlays (artifact-sociomap SOC13)", () => {
  const pop = (name: string) => screen.queryByRole("dialog", { name });
  const sheet = () => screen.queryByTestId("object-map-sheet");
  const tab = (name: string) => within(sheet()!).getByRole("tab", { name });
  const stage = () => screen.getByTestId("object-map-stage");
  const esc = () => fireEvent.keyDown(stage(), { key: "Escape" });
  const key = (k: string) => fireEvent.keyDown(stage(), { key: k });
  const clickNode = (k: number) => {
    const at = nodeAt(k);
    fireEvent.pointerDown(canvas(), { clientX: at.x, clientY: at.y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at.x, clientY: at.y, pointerId: 1 });
  };

  it("holds the map's controls in one bar: the map switch, Nastavení mapy, Nástroje and the ⓘ", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const bar = screen.getByRole("toolbar", { name: "Ovládání mapy" });
    expect(within(bar).getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? b.textContent))
      .toEqual(["Objekty", "Respondenti", "Nastavení mapy", "Nástroje", "Informace o mapě: Kvalita mapy 78 %"]);
    expect(within(bar).getByRole("group", { name: "Mapa" })).toBeTruthy();
    // The view's own controls sit in one rail apart from it.
    const rail = screen.getByRole("group", { name: "Pohled na mapu" });
    for (const name of ["Přiblížit", "Oddálit", "Vycentrovat", "Pohled shora", "3D prostor", "Celá obrazovka"]) expect(within(rail).getByRole("button", { name })).toBeTruthy();
    // The CSS keeps the bar on one row: it never wraps over the map.
    const css = readFileSync(join(process.cwd(), "src/components/rehome/research/object-map-windows.css"), "utf8");
    expect(css).toMatch(/\.omx-bar \{[^}]*white-space: nowrap/);
    expect(css).not.toMatch(/\.omx-bar \{[^}]*flex-wrap: wrap/);
  });

  it("toggles a popover from its bar button, the button pressed while it is open, one popover at a time", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const button = screen.getByRole("button", { name: "Nastavení mapy" });
    expect(button.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(button);
    expect(pop("Nastavení mapy")).toBeTruthy();
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    expect(pop("Nastavení mapy")).toBeNull();
    openSettings();
    openTools();
    expect(pop("Nastavení mapy")).toBeNull();
    expect(pop("Nástroje mapy")).toBeTruthy();
    // Nástroje holds the relation display only on the object map: it closes there.
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(pop("Nástroje mapy")).toBeNull();
    expect(screen.queryByRole("button", { name: "Nástroje" })).toBeNull();
  });

  it("opens Správa objektů and the detail in one side sheet beside the map, never over it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(sheet()).toBeNull();
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Správa objektů" }));
    // Správa objektů closes the popover it was opened from.
    expect(pop("Nastavení mapy")).toBeNull();
    expect(tab("Objekty").getAttribute("aria-selected")).toBe("true");
    expect((tab("Detail") as HTMLButtonElement).disabled).toBe(true);
    // The sheet is the map's sibling, not a layer on it: the canvas's box ends where the sheet begins.
    const box = canvas().parentElement!;
    expect(box.className).toContain("omx-mapbox");
    expect(box.contains(sheet())).toBe(false);
    expect(box.parentElement).toBe(sheet()!.parentElement);
    // A pick shows its detail in the sheet's other tab; the list stays one tab away.
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    expect(tab("Detail").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("object-map-detail-label").textContent).toBe("Rock");
    fireEvent.click(tab("Objekty"));
    fireEvent.click(within(screen.getByTestId("object-map-panel-list")).getByRole("button", { name: "Vybrat objekt Jazz" }));
    expect(screen.getByTestId("object-map-detail-label").textContent).toBe("Jazz");
  });

  it("folds the sheet to its edge and back, and closes it by its ×", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openList();
    fireEvent.click(screen.getByRole("button", { name: "Sbalit panel ke kraji" }));
    expect(sheet()!.className).toContain("is-folded");
    expect(screen.queryByTestId("object-map-panel-list")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Rozbalit panel" }));
    expect(screen.getByTestId("object-map-panel-list")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zavřít: Správa objektů" }));
    expect(sheet()).toBeNull();
  });

  it("closes with Esc in order: a popover, the sheet's open tab, the ⓘ box, the legend", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openLegend();
    expect(screen.getByTestId("object-map-legend")).toBeTruthy();
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    openTools();
    esc();
    expect(pop("Nástroje mapy")).toBeNull();
    expect(screen.getByTestId("object-map-detail")).toBeTruthy();
    esc();
    // The detail closes; Správa objektů, open before it, shows again.
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    expect(screen.getByTestId("object-map-panel-list")).toBeTruthy();
    esc();
    expect(sheet()).toBeNull();
    // The ⓘ box shares the popovers' place, so it is open alone (see the next test).
    openInfo();
    expect(screen.getByTestId("object-map-info")).toBeTruthy();
    esc();
    expect(screen.queryByTestId("object-map-info")).toBeNull();
    // An open sheet or popover folded the legend to its chip; with nothing else open Esc folds it too.
    openLegend();
    esc();
    expect(screen.queryByTestId("object-map-legend")).toBeNull();
    // The selection stays; only the overlays closed.
    expect(canvas().getAttribute("data-selected")).not.toBe("");
  });

  // Codex, #815: the ⓘ box and the two popovers open at one place under the bar, so one at a time.
  it("opens the ⓘ box and the bar's popovers one at a time, by click and by key, and Esc reveals none", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const open = () => stage().querySelectorAll(".omx-pop");
    openSettings();
    openInfo();
    expect(open()).toHaveLength(1);
    expect(screen.getByTestId("object-map-info")).toBeTruthy();
    esc();
    expect(open()).toHaveLength(0);
    openInfo();
    openTools();
    expect(open()).toHaveLength(1);
    expect(pop("Nástroje mapy")).toBeTruthy();
    key("i");
    expect(open()).toHaveLength(1);
    expect(screen.getByTestId("object-map-info")).toBeTruthy();
    esc();
    expect(open()).toHaveLength(0);
  });

  it("opens the detail on a click on the map, and closes it by its × and by a click on free ground", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    clickNode(0);
    expect(within(screen.getByTestId("object-map-detail")).getByTestId("object-map-detail-label").textContent).toBe(hudba.objects.find((o) => o.id === map.object_ids[0])!.label);
    fireEvent.click(screen.getByRole("button", { name: "Zavřít: Detail objektu / vztahu" }));
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    await nextFrame();
    clickNode(0);
    expect(screen.getByTestId("object-map-detail")).toBeTruthy();
    fireEvent.pointerDown(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: 2, clientY: 2, pointerId: 1 });
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    expect(canvas().getAttribute("data-selected")).toBe("");
  });

  it("reaches every object by keyboard: the list is one button per object", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const buttons = openList().getAllByRole("button", { name: /^Vybrat objekt / });
    expect(buttons).toHaveLength(map.object_ids.length);
    for (const b of buttons) expect(b.tagName).toBe("BUTTON");
  });

  it("shows the map's facts and its stored quality behind the ⓘ, the quality on its button", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const info = screen.getByRole("button", { name: "Informace o mapě: Kvalita mapy 78 %" });
    expect(info.textContent).toBe("78 %");
    expect(info.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByTestId("object-map-support")).toBeNull();
    fireEvent.click(info);
    expect(info.getAttribute("aria-expanded")).toBe("true");
    const box = screen.getByTestId("object-map-info").textContent!;
    expect(box).toContain("Hudební žánry");
    expect(box).toContain("Kvalita mapy: 78 % (50 % = náhoda)");
    expect(box).toContain("Dvojice: 62 spolehlivé · 4 slabé · 0 neznámé vztahy");
    cleanup();
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
    expect(screen.getByRole("button", { name: "Informace o mapě: ⚠ Slabě určená mapa" }).className).toContain("is-warn");
  });

  it("keeps the bar, the rail, the legend, the ⓘ box and the sheet inside the stage, so they stay in its full screen", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const s = stage();
    Object.assign(s, { requestFullscreen: () => Promise.resolve() });
    fireEvent.click(screen.getByRole("button", { name: "Celá obrazovka" }));
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: s });
    fireEvent(document, new Event("fullscreenchange"));
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    openInfo();
    openLegend();
    const inside = [screen.getByRole("toolbar", { name: "Ovládání mapy" }), screen.getByRole("group", { name: "Pohled na mapu" }), screen.getByTestId("object-map-info"), screen.getByTestId("object-map-legend"), sheet()!];
    for (const el of inside) expect(s.contains(el)).toBe(true);
    // Esc in full screen closes the sheet, whatever has the focus.
    fireEvent.keyDown(document.body, { key: "Escape" });
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(sheet()).toBeNull();
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: null });
  });

  it("does what the controls do on the map's keys, never on keys typed in a field", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    key("r");
    expect(canvas().getAttribute("data-map")).toBe("respondents");
    key("o");
    expect(canvas().getAttribute("data-map")).toBe("objects");
    key("l");
    expect(screen.getByTestId("object-map-legend")).toBeTruthy();
    key("l");
    expect(screen.queryByTestId("object-map-legend")).toBeNull();
    key("i");
    expect(screen.getByTestId("object-map-info")).toBeTruthy();
    const zoom = camera().zoom;
    key("+");
    expect(camera().zoom).toBeGreaterThan(zoom);
    key("-");
    key("-");
    expect(camera().zoom).toBeLessThan(zoom);
    key("0");
    expect(camera()).toEqual(INITIAL_CAMERA);
    // A key typed in a field is the field's.
    const field = document.createElement("input");
    stage().appendChild(field);
    fireEvent.keyDown(field, { key: "r" });
    expect(canvas().getAttribute("data-map")).toBe("objects");
    field.remove();
    // The shortcut is named in the control's tooltip.
    expect(screen.getByRole("button", { name: "Objekty" }).getAttribute("title")).toBe("Objekty (O)");
    expect(screen.getByRole("button", { name: "Celá obrazovka" }).getAttribute("title")).toBe("Celá obrazovka (F)");
  });

  it("fades the overlays while the map is turned, and brings them back when it is let go", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(stage().hasAttribute("data-moving")).toBe(false);
    fireEvent.pointerDown(canvas(), { clientX: 2, clientY: 2, pointerId: 1, button: 0 });
    fireEvent.pointerMove(canvas(), { clientX: 60, clientY: 40, pointerId: 1 });
    expect(stage().hasAttribute("data-moving")).toBe(true);
    fireEvent.pointerUp(canvas(), { clientX: 60, clientY: 40, pointerId: 1 });
    expect(stage().hasAttribute("data-moving")).toBe(false);
    const css = readFileSync(join(process.cwd(), "src/components/rehome/research/object-map-windows.css"), "utf8");
    expect(css).toMatch(/\.omx\[data-moving\] :is\(\.omx-bar, \.omx-rail, \.omx-legendchip, \.omx-legendwrap\) \{ opacity: var\(--omx-fade\); \}/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\) \{ \.omx-bar, \.omx-rail, \.omx-legendchip, \.omx-legendwrap \{ transition: none; \} \}/);
  });
});

describe("the map's overlays: review follow-ups", () => {
  const pop = (name: string) => screen.queryByRole("dialog", { name });
  const clickNode = (k: number) => {
    const at = nodeAt(k);
    fireEvent.pointerDown(canvas(), { clientX: at.x, clientY: at.y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at.x, clientY: at.y, pointerId: 1 });
  };

  it("isolates the stage, so its overlays stay under the page's header, toasts and dialogs", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-stage").className.split(" ")).toContain("isolate");
  });

  it("keeps the detail open while a popover opens and closes over the bar", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    clickNode(0);
    for (const step of [openSettings, openTools, openSettings]) {
      step();
      expect(screen.getByTestId("object-map-detail")).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Nastavení mapy" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Nástroje" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("closes the detail and Nástroje when the map changes", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    clickNode(0);
    openTools();
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    expect(pop("Nástroje mapy")).toBeNull();
  });

  // Selection is the object map's (artifact-sociomap audit): on Respondenti the list only lists, so a
  // click there neither selects nor marks, and a ringed respondent's profile stays as it is.
  it("on the respondent map, a list click selects nothing and leaves the respondent's profile as it is", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    const dots = panelDots(map, storedFrame(map)!);
    const grid = densityGrid(map)!;
    const P = projection(INITIAL_CAMERA, 900, 700);
    const at = dots.map((d) => P.project(d.x, d.y, terrainAt(grid, d.x, d.y) + 0.65));
    const lone = at.findIndex((q, k) => at.every((o, j) => j === k || Math.hypot(o.x - q.x, o.y - q.y) > 16));
    fireEvent.pointerDown(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: at[lone].x, clientY: at[lone].y, pointerId: 1 });
    expect(screen.getByTestId("object-map-detail-person").textContent).toBe(dots[lone].id);
    const pop = openList().getAllByRole("button").find((b) => b.textContent!.startsWith("Pop"))!;
    fireEvent.click(pop);
    expect(canvas().getAttribute("data-person")).toBe(dots[lone].id);
    expect(canvas().getAttribute("data-selected")).toBe("");
    expect(pop.hasAttribute("aria-pressed")).toBe(false);
    // The profile is still the ringed respondent's, one tab away.
    fireEvent.click(within(screen.getByTestId("object-map-sheet")).getByRole("tab", { name: "Respondent" }));
    expect(screen.getByTestId("object-map-detail-person").textContent).toBe(dots[lone].id);
  });

  it("gives the focus back to what opened the detail when it closes by × or by Esc from inside it", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    clickNode(0);
    fireEvent.click(screen.getByRole("button", { name: "Zavřít: Detail objektu / vztahu" }));
    expect(document.activeElement).toBe(canvas());
    // A pick from the list: closed by Esc from inside the detail, the list's button (back in its tab) is gone
    // with the pick's tab, so the focus falls back to the canvas.
    fireEvent.click(openList().getByRole("button", { name: "Vybrat objekt Rock" }));
    const close = screen.getByRole("button", { name: "Zavřít: Detail objektu / vztahu" });
    close.focus();
    fireEvent.keyDown(close, { key: "Escape" });
    expect(screen.queryByTestId("object-map-detail")).toBeNull();
    expect([canvas(), within(screen.getByTestId("object-map-panel-list")).getByRole("button", { name: "Vybrat objekt Rock" })]).toContain(document.activeElement);
  });

  it("scopes Esc to its own map, and to nothing from a control outside the maps", () => {
    render(<><button type="button">outside</button><ObjectMapView battery={hudba} dataOrigin={null} /><ObjectMapView battery={hudba} dataOrigin={null} /></>);
    const [a, b] = screen.getAllByTestId("object-map-stage");
    for (const button of screen.getAllByRole("button", { name: "Nastavení mapy" })) fireEvent.click(button);
    expect(screen.getAllByRole("dialog", { name: "Nastavení mapy" })).toHaveLength(2);
    fireEvent.keyDown(screen.getByRole("button", { name: "outside" }), { key: "Escape" });
    expect(screen.getAllByRole("dialog", { name: "Nastavení mapy" })).toHaveLength(2);
    fireEvent.keyDown(a, { key: "Escape" });
    expect(within(a).queryByRole("dialog")).toBeNull();
    expect(within(b).getByRole("dialog", { name: "Nastavení mapy" })).toBeTruthy();
  });

  it("ignores an Esc another handler took, and one typed in a field", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openSettings();
    const stage = screen.getByTestId("object-map-stage");
    const taken = (e: Event) => e.preventDefault();
    stage.addEventListener("keydown", taken);
    fireEvent.keyDown(stage, { key: "Escape" });
    expect(pop("Nastavení mapy")).toBeTruthy();
    stage.removeEventListener("keydown", taken);
    const field = document.createElement("input");
    stage.appendChild(field);
    fireEvent.keyDown(field, { key: "Escape" });
    expect(pop("Nastavení mapy")).toBeTruthy();
    field.remove();
    fireEvent.keyDown(stage, { key: "Escape" });
    expect(pop("Nastavení mapy")).toBeNull();
  });
});

// What the Lead can name on the map (artifact-sociomap SOC1/SOC2): each object in the list and the
// selected object and relation in the detail card carry their `object:` / `pair:` id, as the registry
// reads them and as the Lead's focus finds them.
describe("the Lead's names on the map", () => {
  it("names every listed object by its battery, and the Lead's focus finds it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const buttons = openList().getAllByRole("button");
    expect(buttons.map((b) => b.getAttribute("data-aia"))).toEqual(map.object_ids.map((id) => `object:hudba/${id}`));
    const target = `object:hudba/${map.object_ids[2]}`;
    expect(parseAiaId(target)?.stage).toBe("sociomap");
    expect(document.querySelector(focusSelector(target))).toBe(buttons[2]);
  });

  it("opens Správa objektů when the Lead points at one of its objects, and only then", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const reveal = (target: string) => act(() => { window.dispatchEvent(new CustomEvent(LEAD_REVEAL, { detail: target })); });
    const list = () => screen.queryByTestId("object-map-panel-list");
    reveal(`object:${sum.battery_id}/${map.object_ids[2]}`);
    reveal("question:q1");
    expect(list()).toBeNull();
    const target = `object:hudba/${map.object_ids[2]}`;
    reveal(target);
    expect(list()).toBeTruthy();
    expect(document.querySelector(focusSelector(target))?.tagName).toBe("BUTTON");
  });

  it("names the selected relation in the detail card, one pair id either way, and each object once", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    // The objects' one element each is their button in Správa objektů, a tab beside the detail.
    openList();
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const [, i, j, x, y] = (golden.scenes.relativeInitial.hits as [string, number, number, number, number, number][])
      .find((h) => h[0] === "relation" && nodes.every((q) => Math.hypot(q.x - h[3], q.y - h[4]) > 14))!;
    fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    const [a, b] = [map.object_ids[i], map.object_ids[j]].sort();
    const pair = screen.getByTestId("object-map-detail-relation").closest("[data-aia]")!;
    expect(pair.getAttribute("data-aia")).toBe(`pair:hudba/${a}~${b}`);
    expect(readTarget(pair.getAttribute("data-aia")!)).toEqual({ kind: "pair", battery: "hudba", a, b });
    // One element per target, selected or not: the object's list button, never the card's label too.
    expect(document.querySelectorAll(`[data-aia^="object:hudba/"]`)).toHaveLength(0);
    fireEvent.click(within(screen.getByTestId("object-map-sheet")).getByRole("tab", { name: "Objekty" }));
    for (const k of [i, j]) {
      const same = document.querySelectorAll(`[data-aia="object:hudba/${map.object_ids[k]}"]`);
      expect(same).toHaveLength(1);
      expect(same[0].tagName).toBe("BUTTON");
    }
    expect(document.querySelector(focusSelector(`object:hudba/${map.object_ids[i]}`))?.tagName).toBe("BUTTON");
  });
});

// On the map (artifact-sociomap SOC3): the filter chip in the bar names what the popovers changed and that
// the computation did not; the ⓘ box names the four kinds of content.
describe("the filter bar and the four registers", () => {
  const bar = () => screen.queryByTestId("object-map-filter-bar");

  it("shows no bar at the map's opening, and the four registers beside it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(bar()).toBeNull();
    openInfo();
    const registers = screen.getByTestId("object-map-registers");
    expect([...registers.querySelectorAll("[data-register]")].map((r) => r.getAttribute("data-register"))).toEqual(["computed", "display", "interpretation", "external"]);
    expect(registers.textContent).toContain("Spočtený výsledek");
    expect(registers.textContent).not.toContain("Deterministický");
    expect(registers.textContent).toContain("do výpočtu nevstupují");
  });

  it("speaks to a researcher, not in the workshop's jargon (spec copy pass, SOC11b)", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    openSettings();
    expect(screen.getByRole("button", { name: "Absolutní" }).getAttribute("title")).toBe("Na škále, kterou sada uvádí v Dotazníku (např. 1–5 nebo 0–100)");
    openTools();
    expect(screen.getByRole("button", { name: "Nejsilnější vztahy na mapě" })).toBeTruthy();
    openInfo();
    expect(screen.getByTestId("object-map-registers")).toBeTruthy();
    for (const word of ["Top vztahy", "kroku 3", "Stress-1", "PROGRESS", "Deterministický"]) expect(document.body.innerHTML).not.toContain(word);
  });

  it("names a display change and says what did not change, leaving the map's numbers as they were", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const list = () => within(screen.getByTestId("object-map-panel-list")).getAllByRole("button").map((b) => b.textContent);
    openList();
    const before = list();
    openTools();
    fireEvent.click(screen.getByRole("button", { name: "Vše" }));
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Absolutní" }));
    expect(bar()!.textContent).toContain("Filtr absolutní výšky, všechny vztahy");
    expect(bar()!.textContent).toContain("Výpočet, polohy objektů, výšky, vztahy a věrohodnost mapy beze změny.");
    expect(bar()!.getAttribute("title")).toContain("Filtr zobrazení: absolutní výšky, všechny vztahy.");
    expect(bar()!.getAttribute("data-aia-filters")).toBe("norm:absolute relations:all");
    fireEvent.click(screen.getByRole("button", { name: "Správa objektů" }));
    expect(list()).toEqual(before);
  });

  it("goes back to how the map opens on Zrušit filtr", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(bar()!.textContent).toContain("mapa respondentů");
    fireEvent.click(within(bar()!).getByRole("button", { name: "Zrušit filtr" }));
    expect(bar()).toBeNull();
    expect(canvas().getAttribute("data-map")).toBe("objects");
    expect(canvas().getAttribute("data-norm")).toBe("range");
    openTools();
    expect(screen.getByRole("button", { name: "Nejsilnější vztahy na mapě" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("keeps the keyboard in the bar when Zrušit filtr removes its own chip, and announces the bar from a live region already there", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const live = screen.getByTestId("object-map-filter-status");
    expect(live.getAttribute("role")).toBe("status");
    expect(live.textContent).toBe("");
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Absolutní" }));
    expect(screen.getByTestId("object-map-filter-status")).toBe(live);
    expect(live.textContent).toContain("absolutní výšky");
    const reset = within(bar()!).getByRole("button", { name: "Zrušit filtr" });
    reset.focus();
    fireEvent.click(reset);
    expect(bar()).toBeNull();
    await waitFor(() => expect(document.activeElement).not.toBe(document.body));
    expect(screen.getByRole("toolbar", { name: "Ovládání mapy" }).contains(document.activeElement)).toBe(true);
  });
});

// The object list on the respondent map (artifact-sociomap audit, 2026-10-21): a click there marked an
// object pressed and changed nothing a person could see, the respondent card staying where the object's
// detail would be. Selection is the object map's; on the respondent map the list only lists.
describe("the object list on the respondent map", () => {
  it("lists the objects without offering a selection the respondent map cannot show", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    const buttons = openList().getAllByRole("button");
    expect(buttons.length).toBe(map.object_ids.length);
    for (const b of buttons) expect(b.getAttribute("aria-disabled")).toBe("true");
    // Read only, yet still a target the Lead can focus (Codex, #639): a disabled button takes no focus.
    buttons[2].focus();
    expect(document.activeElement).toBe(buttons[2]);
    fireEvent.click(buttons[2]);
    expect(canvas().getAttribute("data-selected")).toBe("");
    // It reads as the object and its value, not as a toggle that selects (no "Vybrat", nothing pressed).
    expect(buttons[2].hasAttribute("aria-pressed")).toBe(false);
    expect(buttons[2].hasAttribute("aria-label")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
    const back = within(screen.getByTestId("object-map-panel-list")).getAllByRole("button");
    expect(back[2].hasAttribute("aria-disabled")).toBe(false);
    fireEvent.click(back[2]);
    expect(canvas().getAttribute("data-selected")).toBe(map.object_ids[2]);
  });
});
