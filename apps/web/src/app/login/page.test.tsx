// @vitest-environment jsdom
// The front door (ADR 0018 decision 3): any active member gets AIA's session and is
// sent back where they were going. Nothing of 18.6.6 is asked for.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import LoginPage from "./page";

let search = "";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search) }));
// The Google round trip itself is lib/auth's; here only that the button starts it.
const login = vi.fn<(returnTo: string) => Promise<void>>(async () => {});
vi.mock("@/lib/auth", async (original) => ({ ...(await original<typeof import("@/lib/auth")>()), login: (to: string) => login(to) }));

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

  it("arms the lift-off film when the person presses sign in", async () => {
    sessionStorage.clear();
    api(answer(204));
    render(<LoginPage />);
    fireEvent.click(await screen.findByRole("button", { name: t("home.signInGoogle") }));
    expect(Number(sessionStorage.getItem("aia.liftoff.armedAt"))).toBeGreaterThan(0);
    expect(login).toHaveBeenCalledWith("/login?next=%2Fapp%2Fclients");
  });

  it("after a sign-in the person started, plays the film where the mark is and goes in when it ends", async () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    sessionStorage.setItem("aia.liftoff.armedAt", String(Date.now()));
    search = "next=%2Fapp%2Fclients%2FCLI-1%2Fresearch";
    api(answer(204));
    const { container } = render(<LoginPage />);
    await vi.waitFor(() => expect(container.querySelector("aside")?.dataset.liftoff).toBe("playing"));
    expect(play).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status").textContent).toBe(t("session.opening"));
    expect(replace).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("aia.session.openedAt")).toBeNull();
    container.querySelector("video")!.dispatchEvent(new Event("ended"));
    expect(replace).toHaveBeenCalledWith("/app/clients/CLI-1/research");
    expect(Number(sessionStorage.getItem("aia.session.openedAt"))).toBeGreaterThan(0);
    // Once: it is disarmed for every later visit.
    expect(sessionStorage.getItem("aia.liftoff.armedAt")).toBeNull();
    play.mockRestore();
  });

  it("puts the mark back when the armed sign-in is refused", async () => {
    sessionStorage.setItem("aia.liftoff.armedAt", String(Date.now()));
    api(answer(403, { code: "not_a_member", message: "no" }));
    const { container } = render(<LoginPage />);
    expect(await screen.findByText(t("session.notMember"))).toBeTruthy();
    expect(container.querySelector("video")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });
});
