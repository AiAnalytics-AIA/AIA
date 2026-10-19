// @vitest-environment jsdom
// Můj Vedoucí: the one choice made on the page (plan inline-decisions chunk 2), the researcher's own.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ResearcherLead } from "@/lib/lead";
import { AUTO_ACCEPT_LABEL, AutoAcceptToggle } from "./LeadProfile";

let puts: { url: string; body: unknown }[];
const answered = (on: boolean): ResearcherLead => ({
  hatched: true,
  lead: {
    lead_id: "LEAD-1", name: "Bára", hatched_at: "2026-10-19T08:00:00Z", updated_at: "2026-10-19T08:00:00Z",
    files: { soul: "", user: "" }, memories: [], preferences: { auto_accept_text_edits: on },
  },
});

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  puts = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "" }));
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body)) as { auto_accept_text_edits: boolean };
      puts.push({ url: u, body });
      return new Response(JSON.stringify(answered(body.auto_accept_text_edits)));
    }
    return new Response("{}", { status: 404 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("AutoAcceptToggle", () => {
  it("is off as the server says, and turning it on sets the researcher's own preference", async () => {
    const changed = vi.fn();
    render(<AutoAcceptToggle on={false} onChanged={changed} />);
    const box = screen.getByRole("checkbox", { name: AUTO_ACCEPT_LABEL }) as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    await waitFor(() => expect(changed).toHaveBeenCalledWith(answered(true)));
    expect(puts).toEqual([{ url: "/api/v1/lead/preferences", body: { auto_accept_text_edits: true } }]);
  });

  it("shows the click at once, and puts the box back when the server refuses", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) =>
      String(url) === "/config"
        ? new Response(JSON.stringify({ apiBase: "" }))
        : new Response(JSON.stringify({ code: "lead_not_hatched", message: "Hatch your Research Lead first." }), { status: 409 })));
    const changed = vi.fn();
    render(<AutoAcceptToggle on={false} onChanged={changed} />);
    const box = screen.getByRole("checkbox", { name: AUTO_ACCEPT_LABEL }) as HTMLInputElement;
    fireEvent.click(box);
    expect(box.checked).toBe(true);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Hatch"));
    expect(box.checked).toBe(false);
    expect(changed).not.toHaveBeenCalled();
  });
});
