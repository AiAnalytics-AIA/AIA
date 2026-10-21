// @vitest-environment jsdom
// The Lead at every width (research-lead-workbench 26b-26c, D20, D21): one element tree, so
// crossing 1100 px remounts nothing and keeps the composer's draft; below 1100 px the
// conversation stays mounted, hidden until the launcher opens it as a modal dialog over the
// artifact, and Zavřít or Escape closes it with focus back on the launcher.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ResearchProject } from "@/research/model";
import { ResearchStore } from "@/research/store";
import { TEST_FRAME } from "../rehome/research/test-frame";
import { EMPTY_PROJECT } from "../rehome/research/test-workspace";
import { Workbench } from "./Workbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app" }));

let width = 1440;
const lists: { query: string; listeners: Set<() => void> }[] = [];
function setWidth(w: number) {
  width = w;
  act(() => {
    for (const l of lists) for (const on of l.listeners) on();
  });
}
const matches = (query: string) => width >= Number(/min-width: (\d+)px/.exec(query)?.[1] ?? 0);

let mounts = 0;
function Stage() {
  useEffect(() => {
    mounts += 1;
  }, []);
  return <div>Dotazník</div>;
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  width = 1440;
  mounts = 0;
  lists.length = 0;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
  vi.stubGlobal("matchMedia", (query: string) => {
    const entry = { query, listeners: new Set<() => void>() };
    lists.push(entry);
    return {
      get matches() {
        return matches(query);
      },
      media: query,
      addEventListener: (_: string, on: () => void) => entry.listeners.add(on),
      removeEventListener: (_: string, on: () => void) => entry.listeners.delete(on),
    };
  });
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url).split("?")[0]!;
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
    if (u === "/api/v1/lead") return new Response(JSON.stringify({ hatched: true, lead: { lead_id: "LEAD-1", name: "Bára", hatched_at: "2026-10-19T08:00:00Z", updated_at: "2026-10-19T08:00:00Z", files: { soul: "", user: "" }, memories: [] } }));
    if (u.endsWith("/lead")) return new Response(JSON.stringify({ available: true, unavailable_reason: null, busy: false, turns: [] }));
    if (u.endsWith("/research/runs")) return new Response(JSON.stringify([]));
    if (u === "/api/v1/studies/STU-1") return new Response(JSON.stringify({ study_id: "STU-1", budget_usd: null, spent_usd: null }));
    return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function bench() {
  const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
  return render(
    <Workbench frame={TEST_FRAME} step="questionnaire" store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
      onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
      <Stage />
    </Workbench>,
  );
}

const layout = () => document.querySelector("[data-workbench]")!.getAttribute("data-layout");
const conversation = () => document.querySelector(".split__left")!;

describe("the workbench at every width", () => {
  it("takes the split, the drawer and the sheet at 1100 and 768 px", () => {
    bench();
    expect(layout()).toBe("split");
    setWidth(1099);
    expect(layout()).toBe("drawer");
    setWidth(768);
    expect(layout()).toBe("drawer");
    setWidth(767);
    expect(layout()).toBe("sheet");
    setWidth(1100);
    expect(layout()).toBe("split");
  });

  it("remounts nothing across 1100 px and keeps the composer's draft", async () => {
    bench();
    const composer = await screen.findByRole("textbox", { name: /zpráv|vedoucí/i });
    fireEvent.change(composer, { target: { value: "Rozepsaná otázka" } });
    setWidth(1024);
    setWidth(390);
    setWidth(1440);
    expect(mounts).toBe(1);
    expect((screen.getByRole("textbox", { name: /zpráv|vedoucí/i }) as HTMLTextAreaElement).value).toBe("Rozepsaná otázka");
  });

  it("below 1100 px keeps the conversation mounted and hidden until the launcher opens it as a dialog", async () => {
    bench();
    setWidth(1024);
    expect(conversation().hasAttribute("hidden")).toBe(true);
    expect(screen.queryByRole("dialog")).toBeNull();
    const launcher = screen.getByRole("button", { name: /Otevřít konverzaci/ });
    expect(launcher.getAttribute("aria-haspopup")).toBe("dialog");
    fireEvent.click(launcher);
    const dialog = screen.getByRole("dialog", { name: "Vedoucí výzkumu" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(launcher.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Zavřít konverzaci" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(launcher));
  });

  it("closes the open drawer on Escape, back to the launcher; in the split Escape leaves the conversation alone", async () => {
    bench();
    setWidth(800);
    const launcher = screen.getByRole("button", { name: /Otevřít konverzaci/ });
    fireEvent.click(launcher);
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(launcher));

    setWidth(1440);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(conversation().hasAttribute("hidden")).toBe(false);
    expect(screen.queryByRole("button", { name: "Zavřít konverzaci" })).toBeNull();
  });

  it("an open drawer is closed by widening to the split, which has no drawer", () => {
    bench();
    setWidth(900);
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    setWidth(1300);
    expect(screen.queryByRole("dialog")).toBeNull();
    setWidth(900);
    expect(conversation().hasAttribute("hidden")).toBe(true);
  });
});

describe("the compact header and stage navigator (26d)", () => {
  it("under 768 px one button names the stage and opens all eleven, by phase, keyboard included", () => {
    bench();
    setWidth(390);
    const nav = screen.getByRole("navigation", { name: "Kroky studie" });
    const current = screen.getByRole("button", { name: /Krok: Dotazník/ });
    expect(current.getAttribute("aria-expanded")).toBe("false");
    expect(nav.querySelectorAll(".nav__stage")).toHaveLength(0);
    fireEvent.click(current);
    const stages = nav.querySelectorAll<HTMLButtonElement>(".nav__stage");
    expect(stages).toHaveLength(11);
    expect(nav.querySelectorAll('[role="group"]')).toHaveLength(6);
    stages[0]!.focus();
    fireEvent.keyDown(stages[0]!, { key: "ArrowDown" });
    expect(document.activeElement).toBe(stages[1]);
    fireEvent.keyDown(stages[1]!, { key: "End" });
    expect(document.activeElement).toBe(stages[10]);
    fireEvent.keyDown(stages[10]!, { key: "Escape" });
    expect(nav.querySelectorAll(".nav__stage")).toHaveLength(0);
    expect(document.activeElement).toBe(current);
  });

  it("from 768 to 1099 px the navigator scrolls sideways and keeps every stage; the header keeps its meter", () => {
    bench();
    setWidth(900);
    const nav = screen.getByRole("navigation", { name: "Kroky studie" });
    expect(nav.classList.contains("nav--scroll")).toBe(true);
    expect(nav.querySelectorAll(".nav__stage")).toHaveLength(11);
    expect(document.querySelector(".budgetmini")).not.toBeNull();
  });

  it("under 768 px the budget and what waits move into the menu", () => {
    bench();
    setWidth(390);
    expect(document.querySelector(".budgetmini")).toBeNull();
    expect(document.querySelector(".shead__state")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Nabídka" }));
    expect(screen.getByRole("menu").textContent).toMatch(/Rozpočet nenastaven/);
  });
});
