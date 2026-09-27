import { afterEach, describe, expect, it, vi } from "vitest";

import { loadBoot, parseBoot, resetBootCache } from "./boot";

afterEach(() => resetBootCache());

describe("the bootstrap", () => {
  it("reads the template, provider and panel version it needs", () => {
    expect(parseBoot({ empty_project: { title: "Nový výzkum" }, ai_provider: "claude_code_subscription", panel: { version: "v17.1.2" } })).toMatchObject({
      empty_project: { title: "Nový výzkum" },
      ai_provider: "claude_code_subscription",
      panelVersion: "v17.1.2",
    });
    expect(parseBoot({ empty_project: {} }).panelVersion).toBe("");
    expect(() => parseBoot({ edition: {} })).toThrow(/empty_project/);
  });

  it("is read once per page, and read again after a failure", async () => {
    let n = 0;
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      ++n === 1 ? new Response("{}", { status: 503 }) : new Response('{"empty_project":{}}', { status: 200 }),
    );
    await expect(loadBoot(fetchImpl)).rejects.toThrow();
    await loadBoot(fetchImpl);
    await loadBoot(fetchImpl);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
