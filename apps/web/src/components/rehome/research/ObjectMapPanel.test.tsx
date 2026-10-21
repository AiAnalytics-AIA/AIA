// @vitest-environment jsdom
// A signed-off map on the Results page, drawn as the AIA panel draws it (plan sociomap-5-web,
// chunk 2): the map is routed to the panel's renderer by its stored estimator, an earlier method
// keeps its terraces, and the panel's controls change only what is shown. Stored fixtures only;
// the canvas is a recording stub (jsdom has none), its frames checked through what it was given.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import signedOff from "@/lib/fixtures/object-map-signed-off.json";
import legacy from "@/lib/fixtures/object-map.json";
import golden from "@/lib/fixtures/object-map-draw-golden.json";
import { type BatteryWithMaps, mapLinks } from "@/lib/object-map-view";
import { readTarget } from "@/lib/artifacts/sociomap";
import { focusSelector } from "@/lib/lead";
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
    // The page around the map stays the web's: the chips and the facts, without the terraces' texts.
    expect(screen.getByTestId("object-map-origin").getAttribute("data-origin-kind")).toBe("SIMULATED");
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
    expect(screen.getByTestId("object-map-support").textContent).toContain("Šířku kopců");
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
    expect(screen.getByRole("button", { name: "Relativní" }).getAttribute("aria-pressed")).toBe("true");
    const strongest = mapLinks(map).sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).slice(0, 5).map((l) => `${l.a}|${l.b}`);
    expect(drawn().sort()).toEqual(strongest.sort());
    expect(canvas().getAttribute("data-selected")).toBe("");
  });

  it("switches Absolutni / Relativni and the relation display, redrawing each time", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    const legend = () => screen.getByTestId("object-map-legend-scale").textContent;
    expect(legend()).toContain("rozsah");
    const before = frames;
    fireEvent.click(screen.getByRole("button", { name: "Absolutní" }));
    expect(canvas().getAttribute("data-norm")).toBe("absolute");
    await nextFrame(before);
    // Absolutni reads the declared 1-10 scale's ends.
    expect(legend()).toBe("1,00absolutní10,0");
    fireEvent.click(screen.getByRole("button", { name: "Vše" }));
    expect(drawn()).toHaveLength(mapLinks(map).length);
    fireEvent.click(screen.getByRole("button", { name: "Vybraný" }));
    expect(drawn()).toEqual([]); // nothing selected: no object's relations to show
  });

  it("offers Absolutni only for a map that stores its absolute terrain", () => {
    const old = structuredClone(hudba);
    delete (old.maps!["aia-sociomap-5"].artifact.terrain as { absolute_height?: unknown }).absolute_height;
    render(<ObjectMapView battery={old} dataOrigin={null} />);
    expect((screen.getByRole("button", { name: "Absolutní" }) as HTMLButtonElement).disabled).toBe(true);
    cleanup();
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect((screen.getByRole("button", { name: "Absolutní" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("selects an object from the list: its relations, highlighted; again clears it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const list = within(screen.getByTestId("object-map-panel-list"));
    const rock = list.getByRole("button", { name: "Vybrat objekt Rock" });
    fireEvent.click(rock);
    expect(rock.getAttribute("aria-pressed")).toBe("true");
    const id = canvas().getAttribute("data-selected")!;
    expect(map.object_ids).toContain(id);
    expect(drawn().length).toBeGreaterThan(0);
    expect(drawn().length).toBeLessThanOrEqual(5);
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
    fireEvent.click(screen.getByRole("button", { name: "Vybraný" }));
    expect(drawn()).toEqual(mapLinks(map).filter((l) => l.a === id || l.b === id).map((l) => `${l.a}|${l.b}`));
    fireEvent.click(rock);
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
    fireEvent.click(within(screen.getByTestId("object-map-panel-list")).getAllByRole("button")[0]);
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

  it("draws the map's five strongest relations under Top vztahy in full screen, a selection or not", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(within(screen.getByTestId("object-map-panel-list")).getAllByRole("button")[0]);
    const id = canvas().getAttribute("data-selected")!;
    // On the page the selection's own five, with its detail card beside the map (the panel's rule).
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
    enterFull();
    expect(canvas().getAttribute("data-selected")).toBe(id);
    expect(drawn().sort()).toEqual(strongest());
    // Vybraný still means the selected object's relations, in full screen too.
    fireEvent.click(screen.getByRole("button", { name: "Vybraný" }));
    for (const pair of drawn()) expect(pair.split("|")).toContain(id);
  });
});

describe("accessibility", () => {
  it("names the canvas, describes its lines, and lists every object as a button", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const img = screen.getByRole("img", { name: "Mapa objektů Hudební žánry: 12 objektů na terénu průměrného hodnocení" });
    expect(document.getElementById(img.getAttribute("aria-describedby")!)!.textContent).toBe("Čar vztahů na mapě: 5");
    const list = within(screen.getByTestId("object-map-panel-list"));
    expect(list.getAllByRole("button")).toHaveLength(map.object_ids.length);
    // The list prints each stored mean on the declared scale, as the panel's object list.
    expect(list.getByRole("button", { name: "Vybrat objekt Pop" }).textContent).toContain("6,32");
    // The object nobody rated is not on the map (its listing is the next chunk's).
    expect(list.queryByRole("button", { name: "Vybrat objekt Reggae" })).toBeNull();
    for (const name of ["Přiblížit", "Oddálit", "Pohled shora", "3D prostor", "Vycentrovat"]) expect(screen.getByRole("button", { name })).toBeTruthy();
  });

  it("folds the legend's key out and back, as the panel's legend", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
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

  it("sizes the nodes by the whole set, objects nobody rated included", async () => {
    const big = structuredClone(hudba);
    const stored = big.maps!["aia-sociomap-5"].artifact;
    // 12 mapped + 38 nobody rated = 50 objects: nodes at sqrt(30 / 50) of their size.
    stored.objects_not_placed = Array.from({ length: 38 }, (_, k) => `extra-${k}`);
    stored.credibility = undefined; // no uncertainty circle among the measured discs
    render(<ObjectMapView battery={big} dataOrigin={null} />);
    await nextFrame(0);
    const scale = Math.sqrt(30 / 50);
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
    expect(screen.getByTestId("object-map-unplaced-objects").textContent).toBe("Neumístěno (nikdo je nehodnotil, proto bez polohy na mapě): Reggae.");
    cleanup();
    render(<ObjectMapView battery={sum} dataOrigin={null} />);
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
    expect(screen.getByTestId("object-map-legend-scale").textContent).toBe("0,00hustota1,00");
    expect(screen.getByTestId("object-map-legend-info").textContent).toContain("hustota jasně umístěných respondentů");
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
      expect(screen.getByTestId("object-map-segments").textContent).toBe(scene.legend);
      const row = screen.getByTestId("object-map-segments-row");
      expect(row.textContent).toBe(`Segmenty: ${scene.row!.value}`);
      expect(row.firstElementChild!.getAttribute("title")).toBe(scene.row!.help);
    });
  }

  it("colours a segment's swatch in the legend as its dots", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    const swatches = [...screen.getByTestId("object-map-segments").querySelectorAll("span[aria-hidden]")].map((s) => (s as HTMLElement).style.background);
    expect(swatches).toEqual(["rgb(127, 211, 255)", "rgb(255, 196, 107)", "rgb(255, 143, 177)", "rgb(154, 163, 173)"]);
  });

  it("quotes the declared thresholds, not fixed ones", () => {
    const b = variant("tooFew");
    b.maps!["aia-sociomap-5"].artifact.spec.segments = { min_respondents: 40, min_ratings: 6, colour_membership: 0.9 };
    render(<ObjectMapView battery={b} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(screen.getByTestId("object-map-segments-row").firstElementChild!.getAttribute("title")).toBe("Segmenty potřebují alespoň 40 lidí s alespoň 6 hodnocenými objekty.");
  });

  it("quotes the declared membership for the colours, not a fixed 80 %", () => {
    const b = structuredClone(hudba);
    b.maps!["aia-sociomap-5"].artifact.spec.segments = { min_respondents: 30, min_ratings: 5, colour_membership: 0.9 };
    render(<ObjectMapView battery={b} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    expect(screen.getByTestId("object-map-segments-row").firstElementChild!.getAttribute("title")).toContain("(≥ 90 %)");
  });

  it("prints a share as the panel does: rounded to 4 decimals first", () => {
    // The panel's payload rounds shares to 4 decimals; on these edges a direct rounding differs by a point.
    expect(sharePercent(23 / 107)).toBe("22 %");
    expect(sharePercent(0.285047)).toBe("28 %");
    expect(sharePercent(0.46598639455782315)).toBe("47 %");
  });
});


describe("what a click shows beside the map", () => {
  const card = () => screen.getByTestId("object-map-detail");
  const label = (id: string) => hudba.objects.find((o) => o.id === id)!.label;

  it("asks for a click, then shows a chosen object's stored numbers and strongest relations", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    expect(card().textContent).toContain("Detail objektu / vztahu");
    expect(card().textContent).toContain("Klikněte na objekt nebo vztah.");
    fireEvent.click(within(screen.getByTestId("object-map-panel-list")).getByRole("button", { name: "Vybrat objekt Rock" }));
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
    fireEvent.click(within(screen.getByTestId("object-map-panel-list")).getByRole("button", { name: `Vybrat objekt ${label(map.object_ids[j])}` }));
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

  it("words a relation under |r| 0,3 as slabý, at or over it as zřetelný", async () => {
    // A drawn pair's midpoint on the opening frame (it does not depend on r), clear of every object.
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const index = (id: string) => map.object_ids.indexOf(id);
    const [i, j, x, y] = mapLinks(map).map((l) => {
      const [a, b] = [index(l.a), index(l.b)];
      const mid = relationGeometry(nodes[a], nodes[b], a < b ? 1 : -1, 0, 0)!.mid;
      return [a, b, mid.x, mid.y];
    }).find(([, , mx, my]) => nodes.every((q) => Math.hypot(q.x - mx, q.y - my) > 14))!;
    // Set the pair to 0,25 and 0,30 and click it on "Vše".
    const verdict = async (v: number) => {
      const r = map.relations.r.map((row, a) => row.map((x0, b) => ((a === i && b === j) || (a === j && b === i) ? v : x0)));
      const stored = hudba.maps!["aia-sociomap-5"];
      render(<ObjectMapView battery={{ ...hudba, maps: { "aia-sociomap-5": { ...stored, artifact: { ...map, relations: { ...map.relations, r } } } } }} dataOrigin={null} />);
      fireEvent.click(screen.getByRole("button", { name: "Vše" }));
      await nextFrame(0);
      fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 });
      fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 });
      const text = screen.getByTestId("object-map-detail-verdict").textContent;
      cleanup();
      frames = 0;
      return text;
    };
    expect(await verdict(0.25)).toBe("Spolehlivý slabý kladný vztah: silnější, než jaký vytvoří náhoda.");
    expect(await verdict(0.3)).toBe("Spolehlivý zřetelný kladný vztah: silnější, než jaký vytvoří náhoda.");
  });

  it("shows a clicked respondent's profile on the respondent map, and asks for a click without one", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    expect(card().textContent).toContain("Profil respondenta");
    expect(card().textContent).toContain("Klikněte na člověka v mapě.");
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
    const button = screen.getByRole("button", { name: "Export PNG" });
    expect(button.getAttribute("title")).toBe("Uloží aktuální pohled na mapu jako obrázek PNG.");
    texts = [];
    fireEvent.click(button);
    expect(saved).toEqual([{ name: "Sociomapa_objekty.png", href: "data:image/png;base64,AAAA" }]);
    // The legend card's words, as the page's legend shows them.
    const marks = screen.getByTestId("object-map-legend-scale").children;
    expect(texts).toEqual(["VÝŠKA · PRŮMĚRNÉ HODNOCENÍ", ...Array.from(marks).map((m) => m.textContent)]);
  });

  it("saves the respondent map with its density legend and segments, as Sociomapa_respondenti.png", async () => {
    const saved = save();
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Respondenti" }));
    await nextFrame(0);
    texts = [];
    fireEvent.click(screen.getByRole("button", { name: "Export PNG" }));
    expect(saved.map((x) => x.name)).toEqual(["Sociomapa_respondenti.png"]);
    expect(texts.slice(0, 4)).toEqual(["VÝŠKA · SHLUKY RESPONDENTŮ", "0,00", "hustota", "1,00"]);
    expect(texts).toContain("CHUŤOVÉ SEGMENTY · PŘEKRÝVAJÍ SE");
    expect(texts.at(-1)).toBe("není jasně v jednom segmentu");
  });
});

// What the Lead can name on the map (artifact-sociomap SOC1/SOC2): each object in the list and the
// selected object and relation in the detail card carry their `object:` / `pair:` id, as the registry
// reads them and as the Lead's focus finds them.
describe("the Lead's names on the map", () => {
  it("names every listed object by its battery, and the Lead's focus finds it", () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    const buttons = within(screen.getByTestId("object-map-panel-list")).getAllByRole("button");
    expect(buttons.map((b) => b.getAttribute("data-aia"))).toEqual(map.object_ids.map((id) => `object:hudba/${id}`));
    const target = `object:hudba/${map.object_ids[2]}`;
    expect(parseAiaId(target)?.stage).toBe("sociomap");
    expect(document.querySelector(focusSelector(target))).toBe(buttons[2]);
  });

  it("names the selected object and the selected relation in the detail card, one pair id either way", async () => {
    render(<ObjectMapView battery={hudba} dataOrigin={null} />);
    await nextFrame(0);
    const nodes = map.object_ids.map((_, k) => nodeAt(k));
    const [, i, j, x, y] = (golden.scenes.relativeInitial.hits as [string, number, number, number, number, number][])
      .find((h) => h[0] === "relation" && nodes.every((q) => Math.hypot(q.x - h[3], q.y - h[4]) > 14))!;
    fireEvent.pointerDown(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    fireEvent.pointerUp(canvas(), { clientX: x, clientY: y, pointerId: 1 });
    const [a, b] = [map.object_ids[i], map.object_ids[j]].sort();
    const pair = screen.getByTestId("object-map-detail-relation").closest("[data-aia]")!;
    expect(pair.getAttribute("data-aia")).toBe(`pair:hudba/${a}~${b}`);
    expect(readTarget(pair.getAttribute("data-aia")!)).toEqual({ kind: "pair", battery: "hudba", a, b });
    expect(screen.getByTestId("object-map-detail-label").getAttribute("data-aia")).toBe(`object:hudba/${map.object_ids[i]}`);
  });
});
