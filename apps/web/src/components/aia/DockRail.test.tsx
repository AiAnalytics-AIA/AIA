// @vitest-environment jsdom
// The Dock rail (prototype-build PBA1, PBA2): every page's one rail, Můj Vedoucí on it.
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { forgetHatched, leadPresence, railLeadItem } from "@/lib/rail-lead";

import { AppShell } from "./AppShell";

let path = "/app/clients";
vi.mock("next/navigation", () => ({ usePathname: () => path }));
vi.mock("@/lib/auth", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/auth")>()), useSession: () => ({ email: "jana.novakova@example.test" }) }));

const CSS = readFileSync(join(process.cwd(), "src/components/aia/dock-rail.css"), "utf8");

function answerLead(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    if (String(url).endsWith("/api/v1/lead")) return new Response(JSON.stringify(body), { status });
    return new Response("{}", { status: 200 });
  }));
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "jana.novakova@example.test", subject: "s" }));
});
afterEach(async () => {
  cleanup();
  // A test's GET /lead may still be answering: let it land before the tab's memory is forgotten,
  // or its "hatched" would reach the next test's rail.
  await new Promise((r) => setTimeout(r, 50));
  vi.unstubAllGlobals();
  forgetHatched();
});

describe("Můj Vedoucí's words on the rail", () => {
  it("reads GET /lead's hatched state, anything else unknown", () => {
    expect(leadPresence({ hatched: true, lead: {} })).toBe("hatched");
    expect(leadPresence({ hatched: false, lead: null })).toBe("none");
    expect(leadPresence({})).toBe("unknown");
    expect(leadPresence(null)).toBe("unknown");
    expect(leadPresence({ hatched: "yes" })).toBe("unknown");
  });

  it("offers growing only when there is no Lead; unknown opens Můj Vedoucí, never the grow step", () => {
    expect(railLeadItem("none")).toEqual({ label: "Vypěstovat Vedoucího", href: "/app/lead", grow: true });
    expect(railLeadItem("hatched")).toEqual({ label: "Můj Vedoucí", href: "/app/lead", grow: false });
    expect(railLeadItem("unknown")).toEqual({ label: "Můj Vedoucí", href: "/app/lead", grow: false });
  });
});

describe("the Dock rail", () => {
  it("carries the brand, the four places, Můj Vedoucí, the account and sign-out, each with its words in the DOM", async () => {
    answerLead({ hatched: true, lead: { lead_id: "L" } });
    render(<AppShell title="Klienti"><p>obsah</p></AppShell>);
    const nav = screen.getByRole("navigation", { name: "Hlavní navigace" });
    const names = within(nav).getAllByRole("link").map((a) => a.textContent?.trim());
    expect(names).toEqual(["AI AnalyticsResearch Studio", "Klienti", "Společenská inteligence", "Projektová paměť", "Nastavení", "Můj Vedoucí"]);
    expect(within(nav).getByRole("link", { name: "Klienti" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: /Účet a nastavení · jana.novakova@example.test/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Odhlásit se" })).toBeTruthy();
    // No label is hidden from assistive technology or the keyboard: the rail clips them, the
    // words stay the links' names, and every item is reachable by Tab.
    for (const a of within(nav).getAllByRole("link")) expect(a.getAttribute("tabindex")).not.toBe("-1");
  });

  it("is the same rail in a study: the stage keeps the page, the rail keeps the places", () => {
    answerLead({ hatched: true, lead: {} });
    path = "/app/clients/CLI-a/research/STU-1/brief";
    render(<AppShell track={<nav aria-label="Kroky">stages</nav>} title="Zadání" client={{ id: "CLI-a", name: "Klient A" }}><p>obsah</p></AppShell>);
    expect(document.querySelectorAll("[data-rail]")).toHaveLength(1);
    const nav = screen.getByRole("navigation", { name: "Hlavní navigace" });
    expect(within(nav).getByRole("link", { name: "Klienti" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getByText("Klient A")).toBeTruthy();
    path = "/app/clients";
  });

  it("says Vypěstovat Vedoucího when the researcher has no Lead", async () => {
    answerLead({ hatched: false, lead: null });
    render(<AppShell title="Klienti"><p>obsah</p></AppShell>);
    await waitFor(() => expect(document.querySelector("[data-rail-lead]")?.getAttribute("data-rail-lead")).toBe("grow"));
    expect(screen.getByRole("link", { name: "Vypěstovat Vedoucího" }).getAttribute("href")).toBe("/app/lead");
  });

  it("says Můj Vedoucí while GET /lead is unread or refused", async () => {
    answerLead({ code: "forbidden" }, 403);
    render(<AppShell title="Klienti"><p>obsah</p></AppShell>);
    expect(screen.getByRole("link", { name: "Můj Vedoucí" })).toBeTruthy();
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled());
    expect(document.querySelector("[data-rail-lead]")?.getAttribute("data-rail-lead")).toBe("mine");
  });

  it("opens to 240 px on hover or keyboard focus from 64 px at rest, and moves nothing under reduced motion", () => {
    expect(CSS).toMatch(/\.dock-slot \{\s*width: 64px;/);
    expect(CSS).toMatch(/\.dock \{[^}]*width: 240px;[^}]*clip-path: inset\(0 176px 0 0\);/);
    expect(CSS).toMatch(/\.dock:hover,\s*\.dock:focus-within \{\s*clip-path: inset\(0 0 0 0/);
    expect(CSS).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.dock,\s*\.dock \* \{\s*transition: none !important;/);
  });
});
