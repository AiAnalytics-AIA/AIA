// @vitest-environment jsdom
// The settings section menu (prototype v54): a button in the top bar names where you are; ⌘K or
// Ctrl+K opens it from anywhere; a search finds a section by name, line or keyword, accents
// ignored; Enter opens the first match and Esc closes it, focus back on the button. A section is
// its address. The coral counts are an administrator's, read from the API, and never guessed.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { SectionMenu, sectionMatches } from "./SectionMenu";

let asked: string[] = [];
function api(answers: { dr?: unknown; prompts?: unknown; fail?: boolean } = {}) {
  asked = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url).split("?")[0]!;
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } }));
    asked.push(u);
    if (answers.fail) return new Response(JSON.stringify({ code: "internal", message: "Boom" }), { status: 500 });
    if (u === "/api/v1/deep-research/settings") return new Response(JSON.stringify(answers.dr ?? { catalogue_version: "c", may_administer: true, missing_for_live: [], settings: [] }));
    if (u === "/api/v1/system-prompts") return new Response(JSON.stringify(answers.prompts ?? []));
    return new Response("{}", { status: 404 });
  }));
}
const prompt = (id: string, waiting: boolean) => ({
  prompt_id: id, family: "f", wired: true, unwired_reason: null, baseline_version: "b", baseline_chars: 1,
  active: { origin: "baseline", version_number: null, activated_at: null, activated_by: null }, version_count: waiting ? 1 : 0, latest_number: waiting ? 1 : null,
});

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
  window.history.replaceState({ __NA: true }, "", "/app/settings#deep_research");
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetConfigCache(); sessionStorage.clear(); });

const trigger = () => screen.getByRole("button", { name: /^Nastavení › / });
const dialog = () => screen.getByRole("dialog", { name: "Nastavení – přejít na" });

describe("the settings section menu", () => {
  it("names the section the address names, and opens on three columns, each section with its line", async () => {
    api();
    render(<SectionMenu mayAdminister={false} />);
    expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research");
    expect(trigger().getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(trigger());
    expect(trigger().getAttribute("aria-expanded")).toBe("true");
    const menu = dialog();
    expect(within(menu).getAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual(["Nastavení výzkumu", "Tým a peníze", "Provoz"]);
    expect(within(menu).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "#methodology", "#prompts", "#deep_research", "#ai", "#access", "#studies", "#audit", "#system", "#reference", "#data",
    ]);
    const here = within(menu).getByRole("link", { name: /Deep Research/ });
    expect(here.getAttribute("aria-current")).toBe("true");
    expect(here.textContent).toContain("Dosah, pravidla, schválení");
    // The search takes the focus as the menu opens.
    await waitFor(() => expect(document.activeElement).toBe(within(menu).getByRole("searchbox", { name: "Hledat v nastavení" })));
  });

  it("opens on ⌘K or Ctrl+K from anywhere, and Esc closes it with the focus back on its button", async () => {
    api();
    render(<><input aria-label="jinde" /><SectionMenu mayAdminister={false} /></>);
    screen.getByLabelText("jinde").focus();
    fireEvent.keyDown(document.body, { key: "k", metaKey: true });
    expect(dialog()).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger());
    fireEvent.keyDown(document.body, { key: "K", ctrlKey: true });
    expect(dialog()).toBeTruthy();
    // K alone is a letter typed, not the menu.
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.keyDown(document.body, { key: "k" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("finds a section by its keywords, accents ignored, and Enter opens the first match", async () => {
    api();
    render(<SectionMenu mayAdminister={false} />);
    fireEvent.click(trigger());
    const search = within(dialog()).getByRole("searchbox");
    const shown = () => within(dialog()).queryAllByRole("link").map((a) => a.getAttribute("data-section-link"));
    fireEvent.change(search, { target: { value: "Brave" } });
    expect(shown()).toEqual(["deep_research"]);
    fireEvent.change(search, { target: { value: "rozpocet" } });
    expect(shown()).toEqual(["studies"]);
    fireEvent.change(search, { target: { value: "práh" } });
    expect(shown()).toEqual(["methodology", "studies"]);
    const events: string[] = [];
    window.addEventListener("hashchange", () => events.push(window.location.hash), { once: true });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(window.location.hash).toBe("#methodology");
    expect(events).toEqual(["#methodology"]);
    // The address is replaced, the framework's history state kept.
    expect(window.history.state).toMatchObject({ __NA: true });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Metodika");
    fireEvent.click(trigger());
    fireEvent.change(within(dialog()).getByRole("searchbox"), { target: { value: "nic takového" } });
    expect(within(dialog()).getByRole("status").textContent).toBe("Nic nenalezeno pro „nic takového“.");
    expect(sectionMatches("audit", "KDO")).toBe(true);
  });

  it("opens a section from its link, and follows the address when it changes elsewhere", async () => {
    api();
    render(<SectionMenu mayAdminister={false} />);
    fireEvent.click(trigger());
    fireEvent.click(within(dialog()).getByRole("link", { name: /Audit/ }));
    expect(window.location.hash).toBe("#audit");
    expect(screen.queryByRole("dialog")).toBeNull();
    act(() => {
      window.history.replaceState(null, "", "/app/settings#reference");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Reference");
  });

  it("counts for an administrator what waits on them, from the API: rules live needs, prompts not switched on", async () => {
    api({ dr: { catalogue_version: "c", may_administer: true, missing_for_live: ["a", "b"], settings: [] }, prompts: [prompt("p1", true), prompt("p2", false)] });
    render(<SectionMenu mayAdminister />);
    await waitFor(() => expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research, čeká na vás: 3"));
    fireEvent.click(trigger());
    const count = (id: string) => dialog().querySelector(`[data-section-link="${id}"] [data-section-count]`)?.textContent;
    await waitFor(() => expect(count("deep_research")).toBe("2"));
    expect(count("prompts")).toBe("1");
    expect(count("studies")).toBeUndefined();
  });

  it("counts nothing for a member, asks nothing, and draws no count it could not read", async () => {
    api();
    render(<SectionMenu mayAdminister={false} />);
    fireEvent.click(trigger());
    await new Promise((r) => setTimeout(r, 30));
    expect(asked).toEqual([]);
    expect(dialog().querySelector("[data-section-count]")).toBeNull();
    cleanup();
    api({ fail: true });
    render(<SectionMenu mayAdminister />);
    await waitFor(() => expect(asked.length).toBeGreaterThan(0));
    fireEvent.click(trigger());
    await new Promise((r) => setTimeout(r, 30));
    expect(dialog().querySelector("[data-section-count]")).toBeNull();
    expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research");
  });
});
