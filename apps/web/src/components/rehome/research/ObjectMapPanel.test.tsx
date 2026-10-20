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
import { type BatteryWithMaps, mapLinks } from "@/lib/object-map-view";
import { INITIAL_CAMERA, panelNodes, projection, storedGrid, terrainAt } from "@/lib/object-map-panel";
import { storedFrame } from "@/lib/object-map-signed-off";
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
      : key === "arc" ? (_x: number, _y: number, r: number) => { radii.push(r); } : () => {}),
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
