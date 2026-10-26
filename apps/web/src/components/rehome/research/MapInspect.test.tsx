// @vitest-environment jsdom
// Sociomapa's item inspector body (artifact-sociomap SOC4; spec szz S3): an object or a relation of a map on
// the stage, from the stored map only.
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import signedOff from "@/lib/fixtures/object-map-signed-off.json";
import type { BatteryWithMaps, ObjectMapArtifact } from "@/lib/object-map-view";
import { MapInspect, setShownMaps } from "./MapInspect";

const [hudba] = signedOff.batteries as unknown as BatteryWithMaps[];
const map = hudba.maps!["aia-sociomap-5"].artifact as unknown as ObjectMapArtifact;
const [a, b] = map.object_ids;
const pair = `pair:hudba/${[a, b].sort().join("~")}`;
const show = (m: ObjectMapArtifact) => act(() => { setShownMaps([{ battery: hudba, map: m }]); });

afterEach(() => { cleanup(); act(() => { setShownMaps([]); }); });

describe("a relation in the inspector", () => {
  it("shows the stored pair: its r, interval, N and verdict", () => {
    show(map);
    render(<MapInspect target={pair} />);
    const body = screen.getByTestId("map-inspect-pair").textContent!;
    expect(body).toContain("Vztah r̃");
    expect(body).toContain("Ze zmrazené mapy běhu");
  });

  it("reads a pair with an undefined r as unknown, never as 0", () => {
    const stored = structuredClone(map);
    const [i, j] = [0, 1];
    stored.relations.r[i][j] = null;
    stored.relations.r[j][i] = null;
    stored.relations.status[i][j] = "unknown";
    stored.relations.status[j][i] = "unknown";
    stored.relations.n[i][j] = 3;
    stored.relations.n[j][i] = 3;
    show(stored);
    render(<MapInspect target={pair} />);
    const body = screen.getByTestId("map-inspect-pair").textContent!;
    expect(body).toContain("neznámý");
    expect(body).toContain("málo lidí hodnotilo oba objekty");
    expect(body).not.toMatch(/[+−-]?0,00/);
  });

  it("says the item is not on this run's map rather than guess one", () => {
    show(map);
    render(<MapInspect target="pair:jina/x~y" />);
    expect(screen.getByText("Tato položka na mapě tohoto běhu není.")).toBeTruthy();
  });
});

describe("an object in the inspector", () => {
  it("shows the object's rating, connectedness and strongest relations", () => {
    show(map);
    render(<MapInspect target={`object:hudba/${a}`} />);
    const body = screen.getByTestId("map-inspect-object").textContent!;
    expect(body).toContain(hudba.objects.find((o) => o.id === a)!.label);
    expect(body).toContain("Průměrné hodnocení");
    expect(body).toContain("Provázanost (0–100)");
  });
});
