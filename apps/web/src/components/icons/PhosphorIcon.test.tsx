// @vitest-environment jsdom
// Phosphor icons (prototype-build PBA5): hidden beside their words, named when alone.
import { cleanup, render, screen } from "@testing-library/react";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { RailIcon } from "../aia/rail-icons";
import { Icon as RehomeIcon, Sparkle } from "../rehome/icons";
import { Icon } from "../workbench/Icons";
import { PHOSPHOR } from "./phosphor";
import { PhosphorIcon } from "./PhosphorIcon";

afterEach(cleanup);

describe("PhosphorIcon", () => {
  it("is hidden from assistive technology beside its words", () => {
    render(<button type="button"><PhosphorIcon name="x" />Zavřít</button>);
    const svg = document.querySelector("svg[data-icon='x']")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("viewBox")).toBe("0 0 256 256");
    expect(svg.querySelector("path")?.getAttribute("d")).toBe(PHOSPHOR.x);
    expect(screen.getByRole("button", { name: "Zavřít" })).toBeTruthy();
  });

  it("takes its label as its name when it stands alone", () => {
    render(<PhosphorIcon name="info" label="Kvalita mapy" />);
    expect(screen.getByRole("img", { name: "Kvalita mapy" }).getAttribute("aria-hidden")).toBeNull();
  });

  it("draws the workbench's icons from the one set", () => {
    render(<Icon name="worker" size={13} />);
    const svg = document.querySelector("svg.icon")!;
    expect(svg.getAttribute("data-icon")).toBe("cpu");
    expect(svg.getAttribute("width")).toBe("13");
  });

  it("draws the inspector's panel on the right, where the drawer opens", () => {
    render(<Icon name="inspector" />);
    expect(document.querySelector("svg[data-icon='sidebar-simple'] path")?.getAttribute("transform")).toBe("matrix(-1 0 0 1 256 0)");
    cleanup();
    render(<Icon name="close" />);
    expect(document.querySelector("svg[data-icon='x'] path")?.hasAttribute("transform")).toBe(false);
  });

  it("carries Phosphor's MIT licence beside the paths, and names it in the generated header", () => {
    const dir = join(process.cwd(), "src/components/icons");
    expect(readFileSync(join(dir, "PHOSPHOR-LICENSE"), "utf8")).toMatch(/^MIT License\n\nCopyright \(c\) 2023 Phosphor Icons\n/);
    expect(readFileSync(join(dir, "phosphor.ts"), "utf8")).toContain("Copyright (c) 2023 Phosphor Icons,\n// under the MIT licence in PHOSPHOR-LICENSE");
  });

  it("draws the screens' icons and the AI glyph from the one set; the rail keeps its own four drawings", () => {
    render(<><RehomeIcon name="research" /><RehomeIcon name="inspector" /><RehomeIcon name="close" /><RehomeIcon name="fault" /><Sparkle /><RailIcon name="client" /></>);
    // A close button's x and the fault status's are not the same shape.
    expect(Array.from(document.querySelectorAll("svg[data-icon]")).map((s) => s.getAttribute("data-icon"))).toEqual(["magnifying-glass", "sidebar-simple", "x", "x-circle", "sparkle"]);
    expect(document.querySelector("svg[data-icon='sidebar-simple'] path")?.getAttribute("transform")).toBe("matrix(-1 0 0 1 256 0)");
    const rail = document.querySelectorAll("svg:not([data-icon])");
    expect(rail).toHaveLength(1);
    expect(rail[0].getAttribute("viewBox")).toBe("0 0 16 16");
    expect(rail[0].getAttribute("aria-hidden")).toBe("true");
  });

  it("leaves no hand-drawn icon outside the rail, the identity, the status glyphs and the maps", () => {
    const SRC = join(process.cwd(), "src");
    const walk = (dir: string): string[] => readdirSync(dir).flatMap((n) => {
      const p = join(dir, n);
      return statSync(p).isDirectory() ? walk(p) : /\.tsx$/.test(n) && !/\.test\.tsx$/.test(n) ? [p] : [];
    });
    // Drawings that are not icons: the AIA wordmark, the status glyphs, the object maps and
    // the Metodika illustrations; and the rail's four places, which UI-2 keeps as drawn.
    const KEPT = new Set([
      "components/icons/PhosphorIcon.tsx", "components/aia/rail-icons.tsx", "components/workbench/Icons.tsx", "components/workbench/Glyph.tsx",
      "components/brand/Wordmark.tsx", "components/aia/settings/MethodologyArt.tsx",
      "components/rehome/research/ObjectMapPanel.tsx", "components/rehome/research/ObjectMapTerrain.tsx",
      "components/rehome/research/ObjectMapView.tsx", "components/rehome/research/SociomappingView.tsx",
    ]);
    const drawing = walk(SRC).filter((f) => readFileSync(f, "utf8").includes("<svg")).map((f) => relative(SRC, f)).filter((f) => !KEPT.has(f));
    expect(drawing).toEqual([]);
  });

  it("names in icons.json exactly the icons the generated module carries", () => {
    const listed = JSON.parse(readFileSync(join(process.cwd(), "src/design/icons.json"), "utf8"));
    expect(Object.keys(PHOSPHOR)).toEqual(listed);
  });
});
