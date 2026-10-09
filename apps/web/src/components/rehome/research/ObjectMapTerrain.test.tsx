// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapObjects, readObjectMap } from "@/lib/object-map-view";
import { INITIAL_CAMERA, terrainMesh } from "@/lib/object-map-3d";
import { ObjectMapTerrain } from "./ObjectMapTerrain";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");
const map = read.map;

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.documentElement.removeAttribute("data-theme"); });

it("draws the stored mesh, redraws on camera/theme changes and exposes selectable objects", async () => {
  const context = {
    setTransform: vi.fn(), clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(),
    lineTo: vi.fn(), closePath: vi.fn(), fill: vi.fn(), stroke: vi.fn(),
    globalAlpha: 1, fillStyle: "", strokeStyle: "", lineWidth: 1,
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  const objects = mapObjects(battery, map);
  const props = { map, objects, camera: INITIAL_CAMERA, selected: objects[0].id, partner: objects[1].id, showLinks: true, onSelect: vi.fn() };
  const { rerender } = render(<ObjectMapTerrain {...props} />);
  const faces = terrainMesh(map).length;
  expect(context.fill).toHaveBeenCalledTimes(1 + faces * 2);
  expect(context.setTransform).toHaveBeenCalled();
  expect(screen.getAllByRole("button")).toHaveLength(objects.length);
  rerender(<ObjectMapTerrain {...props} camera={{ ...INITIAL_CAMERA, yaw: 1 }} />);
  expect(context.fill).toHaveBeenCalledTimes(2 * (1 + faces * 2));
  document.documentElement.setAttribute("data-theme", "dark");
  await waitFor(() => expect(context.fill).toHaveBeenCalledTimes(3 * (1 + faces * 2)));
  expect(context.globalAlpha).toBe(1);
});
