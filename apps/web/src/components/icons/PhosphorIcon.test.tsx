// @vitest-environment jsdom
// Phosphor icons (prototype-build PBA5): hidden beside their words, named when alone.
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

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

  it("names in icons.json exactly the icons the generated module carries", () => {
    const listed = JSON.parse(readFileSync(join(process.cwd(), "src/design/icons.json"), "utf8"));
    expect(Object.keys(PHOSPHOR)).toEqual(listed);
  });
});
