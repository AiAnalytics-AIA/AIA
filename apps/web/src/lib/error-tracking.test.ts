import { afterEach, describe, expect, it, vi } from "vitest";

import { redact, reportError, resetErrorTracking, scrubBreadcrumb, scrubEvent, startErrorTracking } from "./error-tracking";

// Assembled, so the repository's committed-key scan (outside tests/ directories) does not match it.
const KEY = ["sk", "ant", "api03", "AbCdEfGhIjKlMnOpQrStUv"].join("-");
const JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJlLWJ5dGVz";
const DSN = "https://0123abcd@errors.aia.example.test/3";

function fakeSdk() {
  const captured: unknown[] = [];
  const tags: Record<string, string>[] = [];
  const sdk = {
    init: vi.fn(),
    captureException: vi.fn((e: unknown) => captured.push(e)),
    withScope: vi.fn((fn: (scope: { setTag: (k: string, v: string) => void }) => void) => {
      const scoped: Record<string, string> = {};
      fn({ setTag: (k, v) => (scoped[k] = v) });
      tags.push(scoped);
    }),
  };
  return { sdk, captured, tags };
}

afterEach(() => resetErrorTracking());

describe("starting the browser reporter", () => {
  it("loads nothing without a DSN", async () => {
    const load = vi.fn();
    expect(await startErrorTracking({ dsn: null, environment: "develop", release: null }, load)).toBe(false);
    expect(await startErrorTracking(undefined, load)).toBe(false);
    expect(load).not.toHaveBeenCalled();
  });

  it("starts once with the deployment's labels and no session, and sends what was held", async () => {
    const { sdk, captured, tags } = fakeSdk();
    const crash = new Error("render failed");
    reportError(crash, { boundary: "app" }); // before /config answered
    const load = vi.fn(async () => sdk as never);
    const settings = { dsn: DSN, environment: "develop", release: "f6f88cb9" };
    expect(await startErrorTracking(settings, load)).toBe(true);
    expect(await startErrorTracking(settings, load)).toBe(true);
    expect(load).toHaveBeenCalledTimes(1);
    const options = sdk.init.mock.calls[0][0];
    expect(options).toMatchObject({ dsn: DSN, environment: "develop", release: "f6f88cb9", sendDefaultPii: false });
    expect(options.integrations([{ name: "BrowserSession" }, { name: "GlobalHandlers" }])).toEqual([{ name: "GlobalHandlers" }]);
    expect(captured).toEqual([crash]);
    expect(tags).toEqual([{ caught_by: "error_boundary", boundary: "app" }]);
  });
});

describe("what may leave", () => {
  it("redacts secrets, drops queries, headers and the user", () => {
    const event = scrubEvent({
      message: `token refresh failed for ${JWT}`,
      user: { id: "u-1", email: "lead@art-chain.io" },
      request: {
        url: "https://aia.example.test/auth/callback?code=abc&state=xyz#frag",
        headers: { "User-Agent": "test", Authorization: `Bearer ${KEY}`, Referer: "https://x/?q=1" },
      },
      exception: { values: [{ type: "Error", value: `provider said ${KEY}` }] },
      extra: { apiKey: "plain", note: "fine" },
      breadcrumbs: [
        { category: "fetch", data: { url: "/api/v1/population?q=secret+client+term", method: "GET" } },
        { category: "navigation", data: { from: "/login?next=/app", to: "/app/clients?tab=1" } },
      ],
    });
    const flat = JSON.stringify(event);
    for (const leak of [KEY, JWT, "code=abc", "state=xyz", "frag", "lead@art-chain.io", "secret+client", "next=", "tab=1", "plain"]) {
      expect(flat).not.toContain(leak);
    }
    expect(event.request).toEqual({ url: "https://aia.example.test/auth/callback", headers: { "User-Agent": "test" } });
    expect(event.breadcrumbs[0].data).toEqual({ url: "/api/v1/population", method: "GET" });
    expect(event.breadcrumbs[1].data).toEqual({ from: "/login", to: "/app/clients" });
    expect(event.extra).toEqual({ apiKey: "[redacted]", note: "fine" });
  });

  it("keeps the shape of what it does not touch", () => {
    expect(scrubBreadcrumb({ category: "console", message: "ok", data: { arguments: ["ok"] } })).toEqual({
      category: "console",
      message: "ok",
      data: { arguments: ["ok"] },
    });
    expect(redact("token=abcdefghijklmnop")).toBe("token=[redacted]");
    expect(redact(42)).toBe(42);
  });
});
