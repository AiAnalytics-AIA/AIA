// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapLinks, mapObjects, readObjectMap } from "@/lib/object-map-view";
import { INITIAL_CAMERA, plinthSides, terrainMesh } from "@/lib/object-map-3d";
import { ObjectMapTerrain } from "./ObjectMapTerrain";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");
const map = read.map;

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.documentElement.removeAttribute("data-theme"); });

function canvas() {
  const context = {
    setTransform: vi.fn(), clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(),
    lineTo: vi.fn(), closePath: vi.fn(), fill: vi.fn(), stroke: vi.fn(),
    globalAlpha: 1, fillStyle: "", strokeStyle: "", lineWidth: 1,
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  return context;
}

it("draws the stored mesh as terraces, redraws on camera/theme changes and exposes selectable objects", async () => {
  const context = canvas();
  const objects = mapObjects(battery, map);
  const marks = { selected: objects[0].id, partner: objects[1].id, hovered: null, dimmed: new Set<string>(), labelsOnly: false };
  const links = mapLinks(map).filter((l) => l.a === objects[0].id || l.b === objects[0].id);
  const props = { map, objects, camera: INITIAL_CAMERA, view: { width: 900, height: 560 }, links, marks, onSelect: vi.fn() };
  const { rerender } = render(<ObjectMapTerrain {...props} />);
  const faces = terrainMesh(map);
  // The plinth's walls, the "bez dat" ground, each face and its shading, a light edge per riser.
  const perDraw = plinthSides(2).length + 1 + faces.length * 2 + faces.filter((f) => f.riser).length;
  expect(context.fill).toHaveBeenCalledTimes(perDraw);
  expect(context.setTransform).toHaveBeenCalled();
  expect(screen.getAllByRole("button")).toHaveLength(objects.length);
  expect([...screen.getByTestId("object-map-3d-links").children].map((c) => c.getAttribute("data-pair"))).toEqual(links.map((l) => `${l.a}|${l.b}`));
  rerender(<ObjectMapTerrain {...props} camera={{ ...INITIAL_CAMERA, yaw: 1 }} />);
  expect(context.fill).toHaveBeenCalledTimes(2 * perDraw);
  document.documentElement.setAttribute("data-theme", "dark");
  await waitFor(() => expect(context.fill).toHaveBeenCalledTimes(3 * perDraw));
  expect(context.globalAlpha).toBe(1);
});

it("hides labels until the opening rise is nearly done, and never changes the map", () => {
  canvas();
  const before = JSON.stringify(map);
  const objects = mapObjects(battery, map);
  const marks = { selected: null, partner: null, hovered: null, dimmed: new Set<string>(), labelsOnly: false };
  render(<ObjectMapTerrain map={map} objects={objects} camera={INITIAL_CAMERA} view={{ width: 900, height: 560 }} rise={0.2} links={[]} marks={marks} onSelect={vi.fn()} />);
  const label = screen.getByTestId(`object-map-point-${objects[0].id}`).querySelector("g[opacity]");
  expect(label?.getAttribute("opacity")).toBe("0");
  expect(JSON.stringify(map)).toBe(before);
});
