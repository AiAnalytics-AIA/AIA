// @vitest-environment jsdom
// The settings section menu (prototype v54): a button in the top bar names where you are; ⌘K on
// Apple platforms, Ctrl+K elsewhere, opens it from anywhere but a field being typed in; a search
// finds a section by name, line or keyword, accents ignored, and says how many it found; Enter
// opens the first match, Esc or the shortcut closes it, focus back on the button, and focus leaving
// it closes it. A section is its address. The coral counts are an administrator's, read from the
// API, again on a section change or when a section says it changed one, and never guessed.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { SectionMenu, sectionMatches } from "./SectionMenu";
import { waitingChanged } from "./sections";

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
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); resetConfigCache(); sessionStorage.clear(); });

/** Records whether the page prevented each click on a link (its verdict), then cancels the browser's
 *  default, which jsdom would carry out in this page a task later. `done` stops listening. */
function leftToTheBrowser() {
  const verdicts: boolean[] = [];
  const listen = (e: MouseEvent) => { verdicts.push(e.defaultPrevented); e.preventDefault(); };
  window.addEventListener("click", listen);
  return { done: () => { window.removeEventListener("click", listen); return verdicts; } };
}

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
    // The button is the trail's current page; the shortcut is the platform's, named after mount.
    expect(trigger().getAttribute("aria-current")).toBe("page");
    expect(trigger().getAttribute("aria-keyshortcuts")).toBe("Control+K");
    expect(document.querySelector("[data-shortcut]")?.textContent).toBe("Ctrl K");
  });

  it("opens on Ctrl+K off Apple platforms; Esc or Ctrl+K again closes it with the focus back on its button", async () => {
    api();
    render(<SectionMenu mayAdminister={false} />);
    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true });
    expect(dialog()).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger());
    fireEvent.keyDown(document.body, { key: "K", ctrlKey: true });
    const search = within(dialog()).getByRole("searchbox");
    await waitFor(() => expect(document.activeElement).toBe(search));
    // The shortcut pressed in the menu's own search closes it, the focus back on the button.
    fireEvent.keyDown(search, { key: "k", ctrlKey: true });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger());
    // K alone is a letter typed, ⌘K is not this platform's chord, a held key repeats nothing.
    fireEvent.keyDown(document.body, { key: "k" });
    fireEvent.keyDown(document.body, { key: "k", metaKey: true });
    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true, repeat: true });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens on ⌘K on Apple platforms, where Ctrl+K is the text field's own", () => {
    vi.spyOn(navigator, "platform", "get").mockReturnValue("MacIntel");
    api();
    render(<SectionMenu mayAdminister={false} />);
    expect(trigger().getAttribute("aria-keyshortcuts")).toBe("Meta+K");
    expect(document.querySelector("[data-shortcut]")?.textContent).toBe("⌘K");
    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true });
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.keyDown(document.body, { key: "k", metaKey: true });
    expect(dialog()).toBeTruthy();
  });

  it("leaves the shortcut to a field being typed in, and to a key another handler took", () => {
    api();
    render(<><input aria-label="jinde" /><textarea aria-label="text" /><div contentEditable aria-label="editor" /><SectionMenu mayAdminister={false} /></>);
    for (const label of ["jinde", "text", "editor"]) {
      const field = screen.getByLabelText(label);
      field.focus();
      const pressed = new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true, cancelable: true });
      field.dispatchEvent(pressed);
      expect(pressed.defaultPrevented).toBe(false);
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(document.activeElement).toBe(field);
    }
    const taken = new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true, cancelable: true });
    taken.preventDefault();
    document.body.dispatchEvent(taken);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("says how many sections the search found, and closes when the focus leaves it", async () => {
    api();
    render(<><SectionMenu mayAdminister={false} /><button type="button">jinde</button></>);
    fireEvent.click(trigger());
    const status = within(dialog()).getByRole("status");
    expect(status.textContent).toBe("10 oddílů");
    fireEvent.change(within(dialog()).getByRole("searchbox"), { target: { value: "Brave" } });
    expect(status.textContent).toBe("1 oddíl");
    fireEvent.change(within(dialog()).getByRole("searchbox"), { target: { value: "práh" } });
    expect(status.textContent).toBe("2 oddíly");
    const last = within(dialog()).getAllByRole("link").at(-1)!;
    fireEvent.blur(last, { relatedTarget: screen.getByRole("button", { name: "jinde" }) });
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
    const entries = window.history.length;
    fireEvent.keyDown(search, { key: "Enter" });
    expect(window.location.hash).toBe("#methodology");
    expect(events).toEqual(["#methodology"]);
    // A new entry, the framework's history state kept on it: Back from another page lands here.
    expect(window.history.length).toBe(entries + 1);
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
    // A click for a new tab or window is the browser's: not prevented, the page stays where it is.
    // jsdom has no new tab: it would follow the href in this page, a task later and into whichever
    // test runs then (#900's CI), so the browser's default is cancelled after the menu has decided.
    const audit = within(dialog()).getByRole("link", { name: /Audit/ });
    const prevented = leftToTheBrowser();
    for (const modifier of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
      fireEvent.click(audit, modifier);
      expect(window.location.hash).toBe("#deep_research");
      expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research");
    }
    expect(prevented.done()).toEqual([false, false, false, false]);
    await new Promise((r) => setTimeout(r, 20));
    expect(window.location.hash).toBe("#deep_research");
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

  it("reads the counts again when the section changes and when a section says what waits changed", async () => {
    let missing = ["a", "b"];
    api();
    const fetcher = vi.mocked(fetch);
    const answer = fetcher.getMockImplementation()!;
    fetcher.mockImplementation(async (url, init) => String(url).startsWith("/api/v1/deep-research/settings")
      ? new Response(JSON.stringify({ catalogue_version: "c", may_administer: true, missing_for_live: missing, settings: [] }))
      : answer(url, init));
    render(<SectionMenu mayAdminister />);
    await waitFor(() => expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research, čeká na vás: 2"));
    missing = ["a"];
    act(() => waitingChanged());
    await waitFor(() => expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Deep Research, čeká na vás: 1"));
    missing = [];
    act(() => {
      window.history.replaceState(null, "", "/app/settings#access");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    await waitFor(() => expect(trigger().getAttribute("aria-label")).toBe("Nastavení › Přístup a schvalování"));
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
