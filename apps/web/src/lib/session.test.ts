// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { localPath, openSession, signOut } from "./session";

type Call = { method: string; url: string; auth: string | null };
let calls: Call[] = [];

function api(answers: Record<string, () => Response>) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const headers = new Headers(init?.headers);
      calls.push({ method, url: u, auth: headers.get("Authorization") });
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
      const answer = answers[`${method} ${u}`];
      return answer ? answer() : new Response(null, { status: 204 });
    }),
  );
}
const status = (code: number, body?: unknown) => () =>
  new Response(body === undefined ? null : JSON.stringify(body), { status: code });

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000 }));
});
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("openSession", () => {
  it("turns the tab's id token into AIA's session", async () => {
    api({ "POST /api/v1/session": status(204) });
    expect(await openSession()).toEqual({ kind: "opened" });
    expect(calls.filter((c) => c.url === "/api/v1/session")).toEqual([{ method: "POST", url: "/api/v1/session", auth: "Bearer tok" }]);
  });

  it("says who is signed out, who is refused and why, and throws on anything else", async () => {
    api({ "POST /api/v1/session": status(401, { code: "expired_token", message: "x" }) });
    expect(await openSession()).toEqual({ kind: "signed-out" });
    api({ "POST /api/v1/session": status(403, { code: "not_provisioned", message: "Not a member." }) });
    expect(await openSession()).toEqual({ kind: "denied", code: "not_provisioned", message: "Not a member." });
    api({ "POST /api/v1/session": status(503, { code: "identity_unavailable", message: "Down." }) });
    await expect(openSession()).rejects.toThrow("503 identity_unavailable Down.");
  });

  it("asks nothing without a sign-in", async () => {
    sessionStorage.clear();
    api({});
    expect(await openSession()).toEqual({ kind: "signed-out" });
    expect(calls).toEqual([]);
  });
});

describe("signOut", () => {
  it("clears AIA's session, then the sign-in", async () => {
    const assign = vi.fn();
    api({});
    vi.stubGlobal("location", { ...window.location, assign });
    await signOut();
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual(["/api/v1/session"]);
    expect(sessionStorage.getItem("aia.session")).toBeNull();
    expect(assign).toHaveBeenCalledWith("/");
  });

  it("signs out even when clearing a cookie fails", async () => {
    const assign = vi.fn();
    api({});
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      if (String(url) === "/config") return new Response(JSON.stringify({ apiBase: "" }));
      throw new TypeError("offline");
    }));
    vi.stubGlobal("location", { ...window.location, assign });
    await signOut();
    expect(assign).toHaveBeenCalledWith("/");
  });
});

describe("where the person may be sent", () => {
  it("is a path on this origin, never elsewhere", () => {
    expect(localPath("/app/clients/CLI-1?tab=x")).toBe("/app/clients/CLI-1?tab=x");
    for (const bad of [null, "", "//evil.example/", "https://evil.example/", "/\\evil"]) expect(localPath(bad)).toBe("/");
  });
});
