// @vitest-environment jsdom
// The hero (UI-1, prototype-build PBA4): top-level pages only, a figure not read says so.
import { cleanup, render, screen } from "@testing-library/react";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { Hero } from "./Hero";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients" }));
vi.mock("@/lib/auth", () => ({ useSession: () => null }));

afterEach(cleanup);

describe("Hero", () => {
  it("sets the title in the serif at 40/46, the lede and the eyebrow", () => {
    render(<Hero eyebrow="Pracovní prostor" title="Klienti" lede="Pro kterého klienta dnes pracujete?" />);
    const h1 = screen.getByRole("heading", { level: 1, name: "Klienti" });
    expect(h1.className).toContain("font-serif");
    expect(h1.className).toContain("text-[40px]");
    expect(h1.className).toContain("leading-[46px]");
    expect(screen.getByText("Pro kterého klienta dnes pracujete?")).toBeTruthy();
    expect(document.querySelector("[data-hero-eyebrow]")?.textContent).toBe("Pracovní prostor");
  });

  it("says a figure it was not given is unknown, never 0", () => {
    render(<Hero title="Klienti" figures={[{ label: "Klienti", value: 3 }, { label: "Studie", value: null }, { label: "Aktivní práce", value: undefined }, { label: "Nula", value: 0 }]} />);
    const figures = Array.from(document.querySelectorAll("dd[data-hero-figure]"));
    expect(figures.map((d) => [d.getAttribute("data-hero-figure"), d.textContent])).toEqual([
      ["known", "3"], ["unknown", "neznámé"], ["unknown", "neznámé"], ["known", "0"],
    ]);
  });

  it("shows the edit chip in its tone", () => {
    render(<Hero title="Metodika" edit={{ label: "Jen ke čtení", tone: "read" }} />);
    expect(document.querySelector("[data-hero-edit='read']")?.textContent).toBe("Jen ke čtení");
  });
});

describe("AppShell's hero", () => {
  it("draws the hero on a top-level page that asks for it, and the plain header otherwise", () => {
    render(<AppShell hero title="Klienti" sub="Lede" figures={[{ label: "Klienti", value: null }]}><p>obsah</p></AppShell>);
    expect(document.querySelector("[data-hero]")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "Klienti" }).className).toContain("font-serif");
    cleanup();
    render(<AppShell title="Klienti"><p>obsah</p></AppShell>);
    expect(document.querySelector("[data-hero]")).toBeNull();
  });

  it("lets the hero scroll with its page, and keeps the plain header pinned", () => {
    render(<AppShell hero title="Klienti"><p>obsah</p></AppShell>);
    expect(document.querySelector("[data-shell-header]")?.className).not.toContain("lg:sticky");
    cleanup();
    render(<AppShell title="Klienti"><p>obsah</p></AppShell>);
    expect(document.querySelector("[data-shell-header]")?.className).toContain("lg:sticky");
  });

  it("never draws it in a study: the stage keeps its compact header even when asked", () => {
    render(<AppShell hero track={<nav>stages</nav>} title="Dotazník"><p>obsah</p></AppShell>);
    expect(document.querySelector("[data-hero]")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Dotazník" }).className).not.toContain("font-serif");
  });

  it("is asked for by no study screen", () => {
    // Every screen inside a study: the stage frame, the research and simulation studies, the
    // workbench and a past research read from project memory.
    const SRC = join(process.cwd(), "src");
    const study = [
      "components/aia/ResearchStudy.tsx", "components/aia/SimulationFrame.tsx", "components/aia/MemoryStudy.tsx",
    ].map((f) => join(SRC, f));
    const walk = (dir: string): string[] => readdirSync(dir).flatMap((n) => {
      const p = join(dir, n);
      return statSync(p).isDirectory() ? walk(p) : /\.tsx?$/.test(n) && !/\.test\.tsx?$/.test(n) ? [p] : [];
    });
    const files = [...study, ...walk(join(SRC, "components/rehome")), ...walk(join(SRC, "components/workbench"))];
    const offenders = files.filter((f) => {
      const s = readFileSync(f, "utf8");
      return /from "[^"]*\/Hero"|<Hero\b|<AppShell[^>]*\bhero\b/.test(s);
    }).map((f) => relative(SRC, f));
    expect(offenders).toEqual([]);
  });
});
