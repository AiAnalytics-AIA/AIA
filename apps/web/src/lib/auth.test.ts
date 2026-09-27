import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadConfig, resetConfigCache } from "./auth";

// The page's one read of /config: shared while it holds, never a failure kept for
// every later request. A kept failure made every native Research job in a test file
// fail once one request had read /config without that test's stub (OI-76).
const CONFIG = { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" };
const answer = (status = 200) => new Response(JSON.stringify(CONFIG), { status });

beforeEach(() => resetConfigCache());
afterEach(() => {
  vi.unstubAllGlobals();
  resetConfigCache();
});

describe("loadConfig", () => {
  it("reads /config once and shares the answer, a read in flight included", async () => {
    const fetch = vi.fn(async () => answer());
    vi.stubGlobal("fetch", fetch);
    expect(await Promise.all([loadConfig(), loadConfig()])).toEqual([CONFIG, CONFIG]);
    expect(await loadConfig()).toEqual(CONFIG);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/config", { cache: "no-store" });
  });

  it("does not keep a failed read: the next call reads /config again", async () => {
    // What the real fetch answers a relative URL under jsdom, as a request left over from an earlier test gets it.
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to parse URL from /config"); }));
    await expect(loadConfig()).rejects.toThrow("Failed to parse URL from /config");
    const fetch = vi.fn(async () => answer());
    vi.stubGlobal("fetch", fetch);
    expect(await loadConfig()).toEqual(CONFIG);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not keep a refused answer either", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => answer(502)));
    await expect(loadConfig()).rejects.toThrow("/config answered 502");
    vi.stubGlobal("fetch", vi.fn(async () => answer()));
    expect(await loadConfig()).toEqual(CONFIG);
  });

  it("reads again after resetConfigCache, which is for tests", async () => {
    const fetch = vi.fn(async () => answer());
    vi.stubGlobal("fetch", fetch);
    await loadConfig();
    resetConfigCache();
    await loadConfig();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
