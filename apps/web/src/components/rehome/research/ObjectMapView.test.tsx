// @vitest-environment jsdom
// The audit's object map on the Results page: it says it is internal and provisional first,
// draws the stored terrain, links and points, labels the fit by Stress-1, counts who is not
// placed, and shows one object's stored relations. Fixture from the real builder.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapLinks, readObjectMap, terrainCells } from "@/lib/object-map-view";
import { ObjectMapView } from "./ObjectMapView";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");

beforeEach(() => { vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ObjectMapView", () => {
  it("says it is provisional and fictional before the map", () => {
    render(<ObjectMapView battery={battery} dataOrigin="SYNTHETIC_FIXTURE" />);
    expect(screen.getByText("Mapa objektů (aia-sociomap-3)")).toBeTruthy();
    expect(screen.getByText(/σ = 0,25/)).toBeTruthy();
    expect(screen.getByText(/Fiktivní data/)).toBeTruthy();
  });

  it("draws every stored cell, every link that passes both gates and every object", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(screen.getByTestId("object-map-terrain").querySelectorAll("rect")).toHaveLength(terrainCells(read.map).length);
    const links = screen.getByTestId("object-map-links").querySelectorAll("line");
    expect(links).toHaveLength(mapLinks(read.map).length);
    const negative = [...links].filter((l) => l.getAttribute("stroke-dasharray"));
    expect(negative).toHaveLength(mapLinks(read.map).filter((l) => l.sign === "negative").length);
    for (const id of read.map.object_ids) expect(screen.getByTestId(`object-map-point-${id}`)).toBeTruthy();
    expect(screen.queryByText(/Fiktivní data/)).toBeNull();
  });

  it("labels the fit by Stress-1 and counts who is not placed", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-fit").textContent).toMatch(/Stress-1 = 0,158 · slabá/);
    expect(screen.getByTestId("object-map-not-placed").textContent).toContain("Nezařazeno: 1");
    expect(screen.getByTestId("object-map-support").textContent).toContain("dvojice: 11 spolehlivé, 4 slabé, 0 neznámé");
  });

  it("shows a chosen object's stored relations, with which of them are drawn", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByTestId("object-map-point-deneb"));
    const details = screen.getByTestId("object-map-details");
    expect(within(details).getByText("Deneb")).toBeTruthy();
    const fomalhaut = within(details).getByText("Fomalhaut").closest("tr")!;
    expect(fomalhaut.textContent).toContain("slabý");
    expect(fomalhaut.textContent).not.toContain("na mapě");
  });


  it("opens the stored terrain in 3D and changes only the camera with controls", () => {
    const before = JSON.stringify(battery);
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    expect(screen.queryByTestId("object-map-3d")).toBeNull();
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
    expect(JSON.stringify(battery)).toBe(before);
  });

  it("retains selection across views, allows keyboard selection and toggles gated links", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    fireEvent.keyDown(screen.getByRole("button", { name: "Vybrat objekt Deneb" }), { key: "Enter" });
    expect(within(screen.getByTestId("object-map-details")).getByText("Deneb")).toBeTruthy();
    expect(screen.getByTestId("object-map-3d-links").children).toHaveLength(mapLinks(read.map).length);
    fireEvent.click(screen.getByRole("checkbox", { name: "Zobrazit spolehlivé vztahy" }));
    expect(screen.getByTestId("object-map-3d-links").children).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(within(screen.getByTestId("object-map-details")).getByText("Deneb")).toBeTruthy();
    expect(screen.getByTestId("object-map-links").children).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    expect(screen.getByRole("button", { name: "Vybrat objekt Deneb" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("describes the surface, weak fit and actual pair separately from object height", () => {
    render(<ObjectMapView battery={{ ...battery, rating_scale: [1, 10] }} dataOrigin={null} />);
    fireEvent.click(screen.getByRole("button", { name: "3D terén" }));
    expect(screen.getByLabelText("Výška = průměrné hodnocení na škále 1–10")).toBeTruthy();
    const firstPoint = screen.getByTestId(`object-map-point-${read.map.object_ids[0]}`);
    const expectedRating = 1 + read.map.heights.values[0]! * 9;
    expect(firstPoint.textContent).toContain(expectedRating.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    const reading = screen.getByTestId("object-map-reading");
    expect(reading.textContent).toContain("není dalším měřením");
    expect(reading.textContent).toContain("Shoda této mapy je slabá");
    fireEvent.change(screen.getByRole("combobox", { name: "Objekt" }), { target: { value: "deneb" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Porovnat Deneb s objektem" }), { target: { value: "fomalhaut" } });
    expect(screen.getByTestId("object-map-pair").textContent).toContain("Podpora vztahu nesplňuje");
    expect(screen.getByTestId("object-map-details").textContent).toContain("Průměr na škále 1–10");
  });

  it("keeps the top view available without a stored terrain", () => {
    const copy = structuredClone(battery);
    copy.maps!["aia-sociomap-3"].artifact.terrain = { status: "not_computed", reason: "disabled" };
    render(<ObjectMapView battery={copy} dataOrigin={null} />);
    expect(screen.getByTestId("object-map-svg")).toBeTruthy();
    expect(screen.getByRole("button", { name: "3D terén" }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByTestId("object-map-3d")).toBeNull();
  });

  it("says why a family could not be mapped, and draws nothing", () => {
    const stored = battery.maps!["aia-sociomap-3"];
    const unmapped = {
      ...battery,
      maps: {
        "aia-sociomap-3": {
          ...stored,
          artifact: { ...stored.artifact, outcome: "NOT_MAPPABLE", layout: null, not_mappable: { reason: "no_known_pair", message: "žádná dvojice", objects: [] } },
        },
      },
    } as BatteryWithMaps;
    render(<ObjectMapView battery={unmapped} dataOrigin={null} />);
    expect(screen.getByRole("alert").textContent).toContain("Mapu nelze sestavit: žádná dvojice");
    expect(screen.queryByTestId("object-map-svg")).toBeNull();
  });

  it("refuses a stored map of another contract by saying so", () => {
    const stored = battery.maps!["aia-sociomap-3"];
    const other = { ...battery, maps: { "aia-sociomap-3": { ...stored, artifact: { ...stored.artifact, contract_version: "4" } } } } as unknown as BatteryWithMaps;
    render(<ObjectMapView battery={other} dataOrigin={null} />);
    expect(screen.getByRole("alert").textContent).toContain("jinou smlouvu");
  });
});
