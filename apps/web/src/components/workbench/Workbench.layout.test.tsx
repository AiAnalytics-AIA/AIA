// @vitest-environment jsdom
// The Lead at every width (research-lead-workbench 26b-26c, D20, D21): one element tree, so
// crossing 1100 px remounts nothing and keeps the composer's draft; below 1100 px the
// conversation stays mounted, hidden until the launcher opens it as a modal dialog over the
// artifact, and Zavřít or Escape closes it with focus back on the launcher.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useContext, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ResearchProject } from "@/research/model";
import { ResearchStore } from "@/research/store";
import type { ResearchAgentJob } from "@/lib/api";
import { TEST_FRAME } from "../rehome/research/test-frame";
import { EMPTY_PROJECT } from "../rehome/research/test-workspace";
import { FrameNavigation } from "@/components/rehome/step";
import { useItemInspector } from "./item-inspector-context";
import { Workbench } from "./Workbench";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }), usePathname: () => "/app" }));

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
// What GET /studies/{id}/lead answers, read by read: the last entry repeats.
let leadReads: object[] = [];
// What GET …/research/runs and GET …/research/impact answer (WCE7d); impact null is a 404.
let runsAnswer: object[] = [];
let impactAnswer: object | null = null;
const impactUrls: string[] = [];
const leadState = (over: object = {}) => ({ available: true, unavailable_reason: null, busy: false, turns: [], ...over });
const leadTurn = (id: string, seq: number, view: object[] = []) => ({
  turn_id: id, sequence_no: seq, actor: "lead", kind: "message", stage: "questionnaire", text: null, focus: null, status: "COMPLETED", reason: null,
  output: { reply: "Podívejte se sem.", view }, run_id: null, workspace_revision: 3, created_at: "2026-10-21T08:00:00Z", created_by: null,
});
function Stage() {
  useEffect(() => {
    mounts += 1;
  }, []);
  return <div><div data-aia="question:q1" id="qedit_q1">Jak často pijete čaj?</div></div>;
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  width = 1440;
  mounts = 0;
  lists.length = 0;
  leadReads = [leadState()];
  runsAnswer = [];
  impactAnswer = null;
  impactUrls.length = 0;
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
    if (u.endsWith("/lead")) return new Response(JSON.stringify(leadReads.length > 1 ? leadReads.shift() : leadReads[0]));
    if (u.endsWith("/research/runs")) return new Response(JSON.stringify({ items: runsAnswer }));
    if (u.endsWith("/research/impact")) {
      impactUrls.push(String(url));
      return impactAnswer ? new Response(JSON.stringify(impactAnswer)) : new Response(JSON.stringify({ code: "design_revision" }), { status: 404 });
    }
    if (u === "/api/v1/studies/STU-1") return new Response(JSON.stringify({ study_id: "STU-1", budget_usd: null, spent_usd: null }));
    return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

let opened: boolean[] = [];
function Opener() {
  const inspector = useItemInspector();
  return (
    <div>
      <div data-aia="question:q1" id="qedit_q1">Jak často pijete čaj?</div>
      <button type="button" onClick={() => opened.push(inspector?.open({ id: "question:q1", title: "Otázka q1", sub: "Dotazník" }) ?? false)}>open q1</button>
      <button type="button" onClick={() => opened.push(inspector?.open({ id: "measure:q1", title: "Měření q1" }) ?? false)}>open m1</button>
      <button type="button" onClick={() => opened.push(inspector?.open({ id: "question:Q 2", title: "Bad" }) ?? false)}>open bad</button>
      <button type="button" onClick={() => opened.push(inspector?.open({ id: "report:ref:r1", title: "Tvrzení r1" }, () => <p>Hodnota: 42 %</p>) ?? false)}>open claim</button>
      <button type="button" onClick={() => inspector?.closeWhere("report:ref:")}>close claims</button>
    </div>
  );
}

function bench(child = <Stage />, step: "questionnaire" | "plan" = "questionnaire") {
  const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
  return render(
    <Workbench frame={TEST_FRAME} step={step} store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
      onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
      {child}
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

describe("the launcher and the drawer (26c)", () => {
  it("keeps Tab and Shift+Tab inside the open drawer", async () => {
    bench();
    setWidth(900);
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    const dialog = screen.getByRole("dialog", { name: "Vedoucí výzkumu" });
    await waitFor(() => expect((screen.getByRole("textbox", { name: /vedoucí/i }) as HTMLTextAreaElement).disabled).toBe(false));
    const items = [...dialog.querySelectorAll<HTMLElement>("button:not([disabled]), textarea:not([disabled]), a[href]")];
    const first = items[0]!;
    const last = items[items.length - 1]!;
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    // A Tab from nowhere (the focused control removed, focus on the body) comes back inside.
    last.blur();
    fireEvent.keyDown(document.body, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    // What is behind it is inert: the artifact, the launcher, the header and the navigator.
    for (const sel of [".split__right", ".split__rail", "header.shead", "nav.nav"]) expect(document.querySelector(sel)!.hasAttribute("inert")).toBe(true);
    fireEvent.keyDown(window, { key: "Escape" });
    for (const sel of [".split__right", ".split__rail", "header.shead", "nav.nav"]) expect(document.querySelector(sel)!.hasAttribute("inert")).toBe(false);
  });

  it("'@' in the drawer steps the conversation aside; a tap on the artifact sets the chip and reopens it at the composer", async () => {
    bench();
    setWidth(390);
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    const pick = screen.getByRole("button", { name: "Ukázat na prvek artefaktu (@)" });
    await waitFor(() => expect((pick as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(pick);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText(/Klikněte na otázku/)).toBeTruthy();
    fireEvent.click(screen.getByText("Jak často pijete čaj?"));
    expect(screen.getByRole("dialog", { name: "Vedoucí výzkumu" })).toBeTruthy();
    expect(document.querySelector(".refchip")?.textContent).toMatch(/Otázka q1: Jak často pijete čaj\?/);
    await waitFor(() => expect(document.activeElement?.id).toBe("composer"));
  });

  it("Escape while pointing in the drawer disarms it and reopens the conversation at the composer", async () => {
    bench();
    setWidth(800);
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    const pick = screen.getByRole("button", { name: "Ukázat na prvek artefaktu (@)" });
    await waitFor(() => expect((pick as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(pick);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.queryByText(/Klikněte na otázku/)).toBeNull();
    await waitFor(() => expect(document.activeElement?.id).toBe("composer"));
  });

  it("a finished turn's focus closes the drawer, focuses the target and offers the way back", async () => {
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "focus", target: "question:q1" }])] })];
    bench();
    setWidth(900);
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    Element.prototype.scrollIntoView = vi.fn();
    const target = document.getElementById("qedit_q1")!;
    await waitFor(() => expect(document.activeElement).toBe(target));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(target.getAttribute("tabindex")).toBe("-1");
    fireEvent.click(screen.getByRole("button", { name: "Zpět k Vedoucímu" }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    await waitFor(() => expect(document.activeElement?.id).toBe("composer"));
  });

  it("the launcher says whether the Lead answers: unknown until the worker reports ready, never on", async () => {
    bench();
    setWidth(900);
    await waitFor(() => expect(screen.getByRole("button", { name: /Otevřít konverzaci/ }).getAttribute("aria-label")).toMatch(/Nelze zjistit, zda Vedoucí výzkumu odpovídá/));
    expect(document.querySelector("[data-lead-launcher]")!.getAttribute("data-availability")).toBe("UNKNOWN");
  });

  it("the launcher says ON when the worker is ready, and the pending count in its name", async () => {
    leadReads = [leadState({ worker_ready: true })];
    bench();
    setWidth(390);
    await waitFor(() => expect(document.querySelector("[data-lead-launcher]")!.getAttribute("data-availability")).toBe("ON"));
    expect(screen.getByRole("button", { name: /Otevřít konverzaci/ }).getAttribute("aria-label")).toMatch(/Vedoucí výzkumu odpovídá\./);
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

  it("in the sheet the navigator is no query container, so the stage list's scrim covers the viewport", () => {
    // A container is the containing block of its fixed descendants (Codex on #593).
    const css = readFileSync(join(process.cwd(), "src/components/workbench/workbench.css"), "utf8");
    expect(css).toMatch(/\.nav--sheet \{[^}]*container-type: normal;/);
    expect(css).toMatch(/\.scrim \{ position: fixed; inset: 0;/);
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

describe("the item inspector", () => {
  beforeEach(() => {
    opened = [];
  });

  it("opens what a screen clicks over the artifact, its back stack the stage's, and closes on Escape", async () => {
    bench(<Opener />);
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    const drawer = document.querySelector("[data-item-inspector]")!;
    expect(drawer.getAttribute("data-item-inspector")).toBe("question:q1");
    expect(drawer.closest(".artstage")).toBeTruthy();
    expect(drawer.closest("#artbody")).toBeNull();
    expect(drawer.textContent).toMatch(/Otázka q1/);
    // A kind with no body of its own shows what was opened and a way to it on the page.
    Element.prototype.scrollIntoView = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Ukázat na stránce" }));
    expect(document.activeElement?.id).toBe("qedit_q1");
    fireEvent.click(screen.getByRole("button", { name: "open m1" }));
    expect(document.querySelector("[data-item-inspector]")!.getAttribute("data-item-inspector")).toBe("measure:q1");
    fireEvent.click(screen.getByRole("button", { name: "Zpět" }));
    expect(document.querySelector("[data-item-inspector]")!.getAttribute("data-item-inspector")).toBe("question:q1");
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")).toBeNull());
    expect(opened).toEqual([true, true]);
  });

  it("draws the body the opening screen gave (a report claim's evidence), not the kind's fallback", () => {
    bench(<Opener />);
    fireEvent.click(screen.getByRole("button", { name: "open claim" }));
    const drawer = document.querySelector("[data-item-inspector]")!;
    expect(drawer.getAttribute("data-item-inspector")).toBe("report:ref:r1");
    expect(drawer.textContent).toContain("Hodnota: 42 %");
    expect(drawer.querySelector("[data-inspect-fallback]")).toBeNull();
  });

  it("drops the entries a screen says stopped being true, and shuts when none is left", async () => {
    bench(<Opener />);
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    fireEvent.click(screen.getByRole("button", { name: "open claim" }));
    fireEvent.click(screen.getByRole("button", { name: "close claims" }));
    expect(document.querySelector("[data-item-inspector]")!.getAttribute("data-item-inspector")).toBe("question:q1");
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "open claim" }));
    fireEvent.click(screen.getByRole("button", { name: "close claims" }));
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
  });

  it("opens what the Lead's inspect names on this stage, as a click would (research-lead-workbench 14)", async () => {
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "inspect", target: "question:q1" }])] })];
    bench();
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")?.getAttribute("data-item-inspector")).toBe("question:q1"));
    expect(push).not.toHaveBeenCalled();
    // Named by its words on the page, not by its id.
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")!.textContent).toContain("Jak často pijete čaj?"));
    // The turn names it in words, and its chip opens it again.
    expect(screen.getByRole("button", { name: /^Detail: / })).toBeTruthy();
  });

  it("opens the Lead's inspect on another stage once that stage is shown, through the stage's leave guard", async () => {
    push.mockClear();
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "inspect", target: "rq:rq_1" }])] })];
    bench();
    await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    expect(push.mock.calls[0][0]).toMatch(/\/plan$/);
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
    // A route change remounts the workbench on Návrh: the drawer opens there.
    cleanup();
    leadReads = [leadState()];
    bench(<div><div data-aia="rq:rq_1">Kdo pije čaj ráno?</div></div>, "plan");
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")?.getAttribute("data-item-inspector")).toBe("rq:rq_1"));
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")!.textContent).toContain("Kdo pije čaj ráno?"));
    // Nowhere by its opaque id: neither the heading nor the body of a kind without a detail.
    expect(document.querySelector("[data-item-inspector]")!.textContent).not.toContain("rq_1");
  });

  it("leaves nothing pending when a leave guard stops the Lead's move to the inspected stage", async () => {
    push.mockClear();
    // Held to the guard having stopped the move: without it, a move never tried would pass as stopped.
    let stopped = 0;
    const guard = (e: MouseEvent) => {
      e.preventDefault();
      if (e.target instanceof HTMLAnchorElement) stopped += 1;
    };
    document.addEventListener("click", guard, true);
    try {
      leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "inspect", target: "rq:rq_1" }])] })];
      bench();
      await screen.findByRole("button", { name: /^Detail: / });
      await waitFor(() => expect(stopped).toBe(1));
    } finally {
      document.removeEventListener("click", guard, true);
    }
    expect(push).not.toHaveBeenCalled();
    cleanup();
    leadReads = [leadState()];
    bench(<Stage />, "plan");
    await new Promise((r) => setTimeout(r, 50));
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
  });

  it("gives the focus back to what opened it when it closes (Codex on #623)", async () => {
    bench(<Opener />);
    const opener = screen.getByRole("button", { name: "open q1" });
    opener.focus();
    fireEvent.click(opener);
    await waitFor(() => expect(document.activeElement?.getAttribute("data-item-inspector")).toBe("question:q1"));
    const drawer = document.querySelector("[data-item-inspector]")!;
    fireEvent.click([...drawer.querySelectorAll("header button")].at(-1)!);
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("starts empty on another stage and stays empty when the first stage is reached again", () => {
    const view = bench(<Opener />);
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    expect(document.querySelector("[data-item-inspector]")).toBeTruthy();
    const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
    const at = (step: "questionnaire" | "audience") => (
      <Workbench frame={TEST_FRAME} step={step} store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
        onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
        <Opener />
      </Workbench>
    );
    view.rerender(at("audience"));
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
    view.rerender(at("questionnaire"));
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
  });

  it("behind the Lead's modal drawer, Escape closes the drawer the person is in, not the item behind it (review of #623)", async () => {
    bench(<Opener />);
    setWidth(900);
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    expect(document.querySelector("[data-item-inspector]")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.querySelector("[data-item-inspector]")).toBeTruthy();
    // Back in the item, Escape is its own again.
    (document.querySelector("[data-item-inspector]") as HTMLElement).focus();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("[data-item-inspector]")).toBeNull());
  });

  it("while '@' is armed, Escape disarms it first and leaves the item open (D21's order)", async () => {
    bench(<Opener />);
    setWidth(800);
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    const pick = screen.getByRole("button", { name: "Ukázat na prvek artefaktu (@)" });
    await waitFor(() => expect((pick as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(pick);
    expect(screen.queryByRole("dialog")).toBeNull();
    (document.querySelector("[data-item-inspector]") as HTMLElement).focus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(document.querySelector("[data-item-inspector]")).toBeTruthy();
  });

  it("refuses an id outside the contract's grammar and opens nothing", () => {
    bench(<Opener />);
    fireEvent.click(screen.getByRole("button", { name: "open bad" }));
    expect(opened).toEqual([false]);
    expect(document.querySelector("[data-item-inspector]")).toBeNull();
  });

  it("answers null outside the workbench, so a screen keeps its own behaviour", () => {
    render(<Opener />);
    fireEvent.click(screen.getByRole("button", { name: "open q1" }));
    expect(opened).toEqual([false]);
  });
});

describe("Připravenost a pomoc", () => {
  it("takes the focus when it opens, closes on Escape before the drawer, and gives the focus back (audit)", async () => {
    bench();
    const toggle = screen.getByRole("button", { name: /Připravenost a pomoc/ });
    toggle.focus();
    fireEvent.click(toggle);
    const panel = document.querySelector("aside.insp") as HTMLElement;
    expect(panel.hidden).toBe(false);
    await waitFor(() => expect(document.activeElement).toBe(panel));
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(panel.hidden).toBe(true));
    expect(document.activeElement).toBe(toggle);
  });

  it("leaves the panel open when Escape is pressed in the composer: Escape is the layer in use's", async () => {
    bench();
    fireEvent.click(screen.getByRole("button", { name: /Připravenost a pomoc/ }));
    const panel = document.querySelector("aside.insp") as HTMLElement;
    const composer = document.getElementById("composer") as HTMLTextAreaElement;
    composer.disabled = false;
    composer.focus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(panel.hidden).toBe(false);
  });

  it("behind an open drawer, Escape closes the drawer the person is in, not the hidden panel", async () => {
    bench();
    setWidth(900);
    fireEvent.click(screen.getByRole("button", { name: /Připravenost a pomoc/ }));
    fireEvent.click(screen.getByRole("button", { name: /Otevřít konverzaci/ }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect((document.querySelector("aside.insp") as HTMLElement).hidden).toBe(false);
  });
});

describe("the stage track reads the working copy's impact (working-copy-edit-ops WCE7d)", () => {
  const PIPELINE: string[] = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/pipeline_stages/stages.json"), "utf8")).research;
  const answer = (designId: string, over: Record<string, string>) => ({
    working_revision: 3, design_revision_id: designId, design_revision: 2, changed: ["sections"],
    stages: PIPELINE.map((stage) => ({ stage, impact: over[stage] ?? "CURRENT" })),
  });
  const stageButton = (label: string) => screen.getAllByRole("button").find((b) => b.classList.contains("nav__stage") && b.title.startsWith(label))!;

  it("marks a stage the copy changed and the stages to re-check since the newest run, measured against that run's design", async () => {
    runsAnswer = [{ run_id: "RUN-1", design_revision_id: "REV-2", design_revision: 2, status: "SUCCEEDED", steps: [] }];
    impactAnswer = answer("REV-2", { QUESTIONNAIRE: "CHANGED", ANALYSIS: "RECHECK" });
    bench();
    await waitFor(() => expect(stageButton("Dotazník").getAttribute("data-impact")).toBe("CHANGED"));
    expect(impactUrls[0]).toContain("working_revision=3");
    expect(impactUrls[0]).toContain("design_revision_id=REV-2");
    expect(stageButton("Dotazník").textContent).toContain("změněno od běhu (revize 2)");
    expect(stageButton("Analýza").getAttribute("data-impact")).toBe("RECHECK");
    expect(stageButton("Analýza").title).toContain("ověřit znovu: návrh se od běhu změnil");
    expect(stageButton("Zadání").getAttribute("data-impact")).toBeNull();
  });

  it("says nothing for a study without a Design Revision (404), and reads against the newest one before any run", async () => {
    bench();
    await waitFor(() => expect(impactUrls.length).toBe(1));
    expect(impactUrls[0]).not.toContain("design_revision_id");
    expect(document.querySelectorAll("[data-impact]").length).toBe(0);
  });
});

describe("a stage's forward action through the frame (FrameNavigation's next)", () => {
  function Forward() {
    const frame = useContext(FrameNavigation);
    return frame?.next ? <button type="button" onClick={frame.next.go}>Další → {frame.next.label}</button> : <span>poslední</span>;
  }
  const benchOn = (step: "results" | "questionnaire") => {
    const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
    return render(
      <Workbench frame={TEST_FRAME} step={step} store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
        onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
        <Forward />
      </Workbench>,
    );
  };
  afterEach(() => {
    window.location.hash = "";
  });

  it("names the stage after this one in the workbench's order, and opens it with the focus on its heading", async () => {
    // Výsledky -> Sociomapa: one route, the stage its hash, as Dimenze -> Vzorek (whose screen
    // needs the study's research context, which this frame-only test does not mount).
    window.location.hash = "";
    benchOn("results");
    const forward = screen.getByRole("button", { name: "Další → Sociomapa" });
    forward.focus();
    act(() => forward.click());
    await waitFor(() => expect(window.location.hash).toBe("#maps"));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1, name: "Sociomapa" })));
  });

  it("asks nothing of a forward move a stage's leave guard stopped: a later visit keeps its own focus (review of #686)", async () => {
    const guard = (e: MouseEvent) => {
      if ((e.target as Element).closest("a[href]")) e.preventDefault();
    };
    document.addEventListener("click", guard, true);
    try {
      const view = benchOn("questionnaire");
      act(() => screen.getByRole("button", { name: "Další → Cílová skupina" }).click());
      // The person reaches Cílová skupina some other way later (the navigator): its heading does
      // not take the focus from where that navigation put it.
      const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
      view.rerender(
        <Workbench frame={TEST_FRAME} step="audience" store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
          onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
          <Forward />
        </Workbench>,
      );
      await screen.findByRole("heading", { level: 1, name: "Cílová skupina" });
      await new Promise((r) => setTimeout(r, 30));
      expect(document.activeElement).not.toBe(screen.getByRole("heading", { level: 1, name: "Cílová skupina" }));
    } finally {
      document.removeEventListener("click", guard, true);
    }
  });

  it("names Cílová skupina after Dotazník", () => {
    benchOn("questionnaire");
    expect(screen.getByRole("button", { name: "Další → Cílová skupina" })).toBeTruthy();
  });
});

describe("the Lead's show_diff (research-lead-workbench 14)", () => {
  it("marks the Lead's edits waiting on this stage", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const edit = { op: "question_edit", question_id: "q1", text: "Jak často pijete čaj ráno?", why: "přesnější" };
    const t2 = leadTurn("T2", 2, [{ op: "show_diff", stage: "questionnaire" }]);
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), { ...t2, output: { ...t2.output, edits: [edit] } }] })];
    bench();
    const bar = await screen.findByRole("region", { name: "Návrhy Vedoucího" });
    await waitFor(() => expect(bar.classList.contains("just")).toBe(true));
  });

  it("opens the stage's newest proposal still waiting for review when no edit waits there", async () => {
    const pending = { run_id: "RUN-p", action: "optimize_questionnaire", proposal_state: "pending", created_at: "2026-10-22T09:00:00Z", status: "COMPLETED", is_terminal: true, steps: [] } as unknown as ResearchAgentJob;
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "show_diff", stage: "questionnaire" }])] })];
    const onOpenJob = vi.fn();
    const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
    render(
      <Workbench frame={TEST_FRAME} step="questionnaire" store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={vi.fn(async () => true)}
        onAgentStarted={vi.fn()} jobs={[pending]} onOpenJob={onOpenJob} onRefreshJobs={vi.fn(async () => [])}>
        <Stage />
      </Workbench>,
    );
    await waitFor(() => expect(onOpenJob).toHaveBeenCalledWith(pending));
  });

  it("opens the stage itself, through its leave guard, when nothing waits there", async () => {
    push.mockClear();
    leadReads = [leadState({ busy: true, turns: [leadTurn("T1", 1)] }), leadState({ turns: [leadTurn("T1", 1), leadTurn("T2", 2, [{ op: "show_diff", stage: "dimensions" }])] })];
    bench();
    await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    expect(push.mock.calls[0][0]).toMatch(/\/dimensions$/);
  });
});

describe("the study header's Nabídka menu (the UX audit, #753)", () => {
  it("opens from the keyboard on its first item, moves with the arrows, and Escape closes it back to its button", async () => {
    bench();
    const toggle = screen.getByRole("button", { name: "Nabídka" });
    expect(toggle.getAttribute("aria-haspopup")).toBe("menu");
    toggle.focus();
    fireEvent.keyDown(toggle, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu", { name: "Nabídka" });
    const items = Array.from(menu.querySelectorAll<HTMLElement>('[role="menuitem"]'));
    await waitFor(() => expect(document.activeElement).toBe(items[0]));
    fireEvent.keyDown(items[0]!, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1]!, { key: "End" });
    expect(document.activeElement).toBe(items[items.length - 1]);
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("menu", { name: "Nabídka" })).toBeNull();
    expect(document.activeElement).toBe(toggle);
  });

  it("closes on a press outside without a scrim swallowing it", async () => {
    bench();
    fireEvent.click(screen.getByRole("button", { name: "Nabídka" }));
    await screen.findByRole("menu", { name: "Nabídka" });
    expect(document.querySelector(".shead .scrim")).toBeNull();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu", { name: "Nabídka" })).toBeNull();
  });
});

describe("a typed analysis retry (the PM on #744)", () => {
  it("is approved on the run its card named, and on a newer one only after the person's yes", async () => {
    const typed = { ...leadTurn("T1", 1), actor: "person", kind: "message", text: "Zopakuj analýzu", command: "analysis_retry", output: null };
    leadReads = [leadState({ turns: [typed], analysis_retry_run: { run_id: "RUN-a1", created_at: null, phase: "succeeded" } })];
    const base = vi.mocked(fetch);
    const sent: Record<string, unknown>[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/lead/turns/T1/request")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        sent.push(body);
        return body.retry_run_id === "RUN-b2"
          ? new Response(JSON.stringify({ run_id: "RUN-r3", design_revision_id: "REV-1", status: "QUEUED" }))
          : new Response(JSON.stringify({ code: "analysis_retry_target_moved", message: "moved", details: { current_run_id: "RUN-b2" } }), { status: 409 });
      }
      return base(url, init);
    }));
    const confirm = vi.fn(async () => true);
    const store = new ResearchStore({ revision: 3, project: EMPTY_PROJECT as unknown as ResearchProject, analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
    render(
      <Workbench frame={TEST_FRAME} step="questionnaire" store={store} memory={new Map()} save={null} inspector={null} reload={vi.fn()} confirm={confirm}
        onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
        <Stage />
      </Workbench>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Zopakovat analýzu" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent.map((b) => b.retry_run_id)).toEqual(["RUN-a1", "RUN-b2"]);
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/novější běh s AI analýzou/));
  });
});
