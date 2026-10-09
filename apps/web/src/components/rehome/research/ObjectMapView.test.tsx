// @vitest-environment jsdom
// The audit's object map on the Results page: it says it is internal and provisional first,
// draws the stored terrain, links and points, labels the fit by Stress-1, counts who is not
// placed, and shows one object's stored relations. Fixture from the real builder.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import fixture from "@/lib/fixtures/object-map.json";
import { type BatteryWithMaps, mapLinks, readObjectMap, terrainCells } from "@/lib/object-map-view";
import { ObjectMapView } from "./ObjectMapView";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");

afterEach(cleanup);

describe("ObjectMapView", () => {
  it("says it is provisional and fictional before the map", () => {
    render(<ObjectMapView battery={battery} dataOrigin="SYNTHETIC_FIXTURE" />);
    expect(screen.getByText("Mapa objektů (aia-sociomap-3)")).toBeTruthy();
    expect(screen.getByText(/σ = 0,25/)).toBeTruthy();
    expect(screen.getByText(/Fiktivní data/)).toBeTruthy();
  });

  it("draws every stored cell, every link that passes both gates and every object", () => {
    render(<ObjectMapView battery={battery} dataOrigin={null} />);
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
