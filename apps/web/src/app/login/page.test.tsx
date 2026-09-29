// @vitest-environment jsdom
// The front door (ADR 0018 decision 3): any active member gets AIA's session and is
// sent back where they were going. Nothing of 18.6.6 is asked for.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import LoginPage from "./page";

let search = "";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search) }));

type Call = { method: string; url: string };
let calls: Call[] = [];
let replace = vi.fn();

function api(session: () => Response) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      calls.push({ method, url: u });
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
      if (u === "/api/v1/session" && method === "POST") return session();
      return new Response(null, { status: 204 });
    }),
  );
}
const answer = (status: number, body?: unknown) => () => new Response(body === undefined ? null : JSON.stringify(body), { status });

beforeEach(() => {
  search = "";
  replace = vi.fn();
  vi.stubGlobal("location", { ...window.location, replace });
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000 }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("/login", () => {
  it("opens AIA's session and goes back where the person was going", async () => {
    search = "next=%2Fapp%2Fclients%2FCLI-1%2Fresearch";
    api(answer(204));
    render(<LoginPage />);
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/app/clients/CLI-1/research"));
    // AIA's session and nothing else: no 18.6.6 panel to open any more.
    expect(calls.filter((c) => c.method === "POST").map((c) => c.url)).toEqual(["/api/v1/session"]);
  });

  it("goes to the client directory when nowhere is named, and never off this origin", async () => {
    api(answer(204));
    render(<LoginPage />);
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/app/clients"));
    cleanup();
    sessionStorage.removeItem("aia.session.openedAt");
    replace.mockReset();
    search = "next=%2F%2Fevil.example%2F";
    render(<LoginPage />);
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("tells someone who is no member that they are not", async () => {
    api(answer(403, { code: "not_provisioned", message: "This account is not a member of any organization." }));
    render(<LoginPage />);
    expect(await screen.findByText(t("session.notMember"))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("live.signOut") })).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });

  it("offers the sign-in when signed out and never starts it by itself", async () => {
    sessionStorage.clear();
    api(answer(204));
    render(<LoginPage />);
    expect(await screen.findByRole("button", { name: t("home.signInGoogle") })).toBeTruthy();
    expect(calls.some((c) => c.url.startsWith("/api/v1/"))).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });

  it("stops rather than bounce when the gate sends the browser straight back", async () => {
    sessionStorage.setItem("aia.session.openedAt", String(Date.now()));
    api(answer(204));
    render(<LoginPage />);
    expect(await screen.findByText(t("session.loop"))).toBeTruthy();
    expect(calls.some((c) => c.url === "/api/v1/session")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: t("session.retry") }));
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/app/clients"));
  });
});
