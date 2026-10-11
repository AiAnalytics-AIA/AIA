// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapFrame, mapLinks, mapObjects, readObjectMap } from "@/lib/object-map-view";
import { INITIAL_CAMERA, terraceLayers } from "@/lib/object-map-3d";
import { ObjectMapTerrain } from "./ObjectMapTerrain";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");
const map = read.map;

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.documentElement.removeAttribute("data-theme"); });

function canvas() {
  const context = {
    setTransform: vi.fn(), clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(),
    lineTo: vi.fn(), closePath: vi.fn(), fill: vi.fn(), stroke: vi.fn(), save: vi.fn(), restore: vi.fn(),
    globalAlpha: 1, fillStyle: "", strokeStyle: "", lineWidth: 1, shadowColor: "", shadowBlur: 0, shadowOffsetY: 0,
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  return context;
}

it("draws the stored mesh as terraces, redraws on camera/theme changes and exposes selectable objects", async () => {
  const context = canvas();
  const objects = mapObjects(battery, map);
  const marks = { selected: objects[0].id, partner: objects[1].id, hovered: null, dimmed: new Set<string>(), labelsOnly: false };
  const links = mapLinks(map).filter((l) => l.a === objects[0].id || l.b === objects[0].id);
  const props = { map, objects, frame: mapFrame(map, objects), camera: INITIAL_CAMERA, view: { width: 900, height: 560 }, links, marks, onSelect: vi.fn() };
  const { rerender } = render(<ObjectMapTerrain {...props} />);
  // One fill per terrace top for every band that has pieces, plus the plinth and its risers.
  const perDraw = context.fill.mock.calls.length;
  const tops = terraceLayers(map).filter((l) => l.pieces.length).length;
  expect(perDraw).toBeGreaterThan(tops + 6);
  expect(screen.getByTestId("object-map-3d").getAttribute("data-triangles")).toBe(String(terraceLayers(map).reduce((n, l) => n + l.pieces.length, 0)));
  expect(context.setTransform).toHaveBeenCalled();
  expect(screen.getAllByRole("button")).toHaveLength(objects.length);
  expect([...screen.getByTestId("object-map-3d-links").children].map((c) => c.getAttribute("data-pair"))).toEqual(links.map((l) => `${l.a}|${l.b}`));
  rerender(<ObjectMapTerrain {...props} camera={{ ...INITIAL_CAMERA, yaw: 1 }} />);
  // A new camera redraws (another yaw shows another set of risers facing the viewer).
  const afterCamera = context.fill.mock.calls.length;
  expect(afterCamera).toBeGreaterThan(perDraw + tops);
  document.documentElement.setAttribute("data-theme", "dark");
  await waitFor(() => expect(context.fill.mock.calls.length).toBeGreaterThan(afterCamera + tops));
  expect(context.globalAlpha).toBe(1);
});

it("hides labels while the opening plays, and never changes the map", () => {
  canvas();
  const before = JSON.stringify(map);
  const objects = mapObjects(battery, map);
  const marks = { selected: null, partner: null, hovered: null, dimmed: new Set<string>(), labelsOnly: false };
  render(<ObjectMapTerrain map={map} objects={objects} frame={mapFrame(map, objects)} camera={INITIAL_CAMERA} view={{ width: 900, height: 560 }} rise={0.2} labels={0} links={[]} marks={marks} onSelect={vi.fn()} />);
  const label = screen.getByTestId(`object-map-point-${objects[0].id}`).querySelector("g[opacity]");
  expect(label?.getAttribute("opacity")).toBe("0");
  expect(JSON.stringify(map)).toBe(before);
});
