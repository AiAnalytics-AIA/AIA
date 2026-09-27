import { describe, expect, it, vi } from "vitest";

import { TIMEOUT_MESSAGE, UnitError, unit } from "./client";

const answer = (status: number, body: string) =>
  vi.fn<typeof fetch>(async () => new Response(body, { status, headers: { "Content-Type": "application/json" } }));

describe("unit()", () => {
  it("GETs the ledger path and returns the parsed body", async () => {
    const f = answer(200, '{"counts":{"demo":30}}');
    await expect(unit("projectsDashboard", { fetchImpl: f })).resolves.toEqual({ counts: { demo: 30 } });
    expect(f).toHaveBeenCalledWith("/api/projects/dashboard", expect.objectContaining({ method: "GET", credentials: "same-origin" }));
  });

  it("POSTs JSON", async () => {
    const f = answer(200, '{"project_id":"PRJ-X"}');
    await unit("demoCopy", { body: { project_id: "PRJ-DEMO" }, fetchImpl: f });
    const init = f.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"project_id":"PRJ-DEMO"}');
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("addresses an id route and adds the query", async () => {
    const f = answer(200, "{}");
    await unit("jobCancel", { id: "J 1", body: {}, fetchImpl: f });
    await unit("job", { query: { id: "J1" }, fetchImpl: f });
    expect(f.mock.calls.map((c) => c[0])).toEqual(["/api/jobs/J%201/cancel", "/api/job?id=J1"]);
  });

  it("raises the unit's own error message with the status", async () => {
    const f = answer(403, '{"error":"Cross-origin request blocked."}');
    const err = await unit("projects", { fetchImpl: f }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(UnitError);
    expect(err).toMatchObject({ message: "Cross-origin request blocked.", status: 403 });
  });

  it("keeps a non-JSON error body as the message", async () => {
    const f = answer(502, "Bad Gateway");
    await expect(unit("projects", { fetchImpl: f })).rejects.toMatchObject({ message: "Bad Gateway", status: 502 });
  });

  it("says the classic interface's timeout sentence when the unit does not answer", async () => {
    const never = vi.fn(
      (_: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_, reject) =>
          init?.signal?.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" }))),
        ),
    );
    await expect(unit("projects", { fetchImpl: never, timeoutMs: 5 })).rejects.toMatchObject({
      message: TIMEOUT_MESSAGE,
      status: null,
    });
  });
});
