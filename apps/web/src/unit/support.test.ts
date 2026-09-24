import { describe, expect, it, vi } from "vitest";

import { createSupportBundle } from "./support";

const answer = (body: unknown) =>
  vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }));

describe("createSupportBundle", () => {
  it("sends the failed job's id, as the classic one does, and returns the download URL", async () => {
    const f = answer({ download_url: "/api/support/download?id=S1" });
    await expect(createSupportBundle("JOB-1", f)).resolves.toBe("/api/support/download?id=S1");
    expect(f.mock.calls[0][0]).toBe("/api/support/bundle");
    expect((f.mock.calls[0][1] as RequestInit).body).toBe('{"job_id":"JOB-1"}');
  });

  it("sends an empty id when no job failed", async () => {
    const f = answer({ download_url: "/x" });
    await createSupportBundle(null, f);
    expect((f.mock.calls[0][1] as RequestInit).body).toBe('{"job_id":""}');
  });

  it("refuses an answer without a file", async () => {
    await expect(createSupportBundle("J", answer({}))).rejects.toThrow("Backend nevytvořil diagnostický soubor.");
  });
});
