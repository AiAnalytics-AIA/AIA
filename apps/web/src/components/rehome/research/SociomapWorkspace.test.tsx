// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SociomapWorkspace } from "./SociomapWorkspace";
import type { MapWorkspace, Terrain } from "@/lib/sociomap-workspace";
afterEach(cleanup);
const field: Terrain = {
  parameters: { grid_resolution: 1, half_extent: 62, z_scale: 26 },
  height_raw: [
    [1, 2],
    [3, 4],
  ],
  height_normalised: [
    [0, 0.3],
    [0.6, 1],
  ],
  normalizer_lo: 1,
  normalizer_hi: 4,
};
const point = (id: string, x: number) => ({
  id,
  x,
  y: 0,
  status: "POSITIONED" as const,
  ratings: [7, 8, 9],
});
const w: MapWorkspace = {
  version: "aia-native-workspace-1",
  input_fingerprint: "test-input",
  status: "AVAILABLE",
  reason: null,
  object_reason: null,
  weighting: "UNWEIGHTED",
  people: [point("R1", 1)],
  anchors: [point("a", -10), point("b", 0), point("c", 10)],
  objects: [point("a", -10), point("b", 0), point("c", 10)],
  relations: [
    [0, 5, 6],
    [5, 0, 7],
    [6, 7, 0],
  ],
  pair_n: [
    [0, 6, 7],
    [6, 0, 8],
    [7, 8, 0],
  ],
  metrics: { relation_classic: [11, 12, 13], mean_rating: [7, 8, 9] },
  respondent_terrain: field,
  object_terrains: {
    relation_classic: field,
    mean_rating: { ...field, normalizer_lo: 7, normalizer_hi: 9 },
  },
};
const labels = [
  { id: "a", label: "Káva" },
  { id: "b", label: "Čaj" },
  { id: "c", label: "Voda" },
];
it("reads both map modes, changes height, and reveals stored responses and pair support", () => {
  const before = JSON.stringify(w);
  render(
    <SociomapWorkspace
      workspace={w}
      labels={labels}
      origin="SYNTHETIC_FIXTURE"
    />,
  );
  expect(screen.getByRole("note").textContent).toContain("Syntetická data");
  fireEvent.change(screen.getByLabelText("Detail respondenta"), {
    target: { value: "R1" },
  });
  expect(screen.getByRole("table").textContent).toContain("Káva7");
  fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
  fireEvent.change(screen.getByLabelText("Výška a barva"), {
    target: { value: "mean_rating" },
  });
  expect(screen.getByRole("img").getAttribute("aria-label")).toContain(
    "Průměrné hodnocení",
  );
  fireEvent.change(screen.getByLabelText("Detail objektu"), {
    target: { value: "a" },
  });
  expect(screen.getByRole("table").textContent).toContain("Čaj56");
  const beforeCamera = screen
    .getByRole("img")
    .querySelector("polygon")
    ?.getAttribute("points");
  fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
  expect(
    screen.getByRole("img").querySelector("polygon")?.getAttribute("points"),
  ).not.toBe(beforeCamera);
  fireEvent.keyDown(screen.getByRole("img"), { key: "ArrowRight" });
  expect(JSON.stringify(w)).toBe(before);
});
it("explains missing old artifacts and unsupported relationships", () => {
  const r = render(<SociomapWorkspace labels={labels} origin={null} />);
  expect(screen.getByText(/Tento běh neobsahuje 3D mapu/)).toBeTruthy();
  r.rerender(
    <SociomapWorkspace
      workspace={{
        ...w,
        objects: [],
        object_terrains: {},
        object_reason: "INSUFFICIENT_PAIR_SUPPORT_OR_VARIANCE",
      }}
      labels={labels}
      origin="SYNTHETIC_FIXTURE"
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Objekty" }));
  expect(screen.getByRole("status").textContent).toContain(
    "pět společných odpovědí",
  );
  expect(screen.queryByRole("img")).toBeNull();
});
it("refuses unknown versions and unsupported scales without drawing", () => {
  const r = render(
    <SociomapWorkspace
      workspace={{ ...w, version: "future" }}
      labels={labels}
      origin={null}
    />,
  );
  expect(screen.getByRole("status").textContent).toContain("verze");
  r.rerender(
    <SociomapWorkspace
      workspace={{ ...w, status: "UNSUPPORTED", reason: "SCALE_NOT_1_10" }}
      labels={labels}
      origin={null}
    />,
  );
  expect(screen.getByRole("status").textContent).toContain("škálu 1–10");
  expect(screen.queryByRole("img")).toBeNull();
});
