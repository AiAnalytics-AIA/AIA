// @vitest-environment jsdom
// A refusal is never said as nothing (PC18): an empty message from the API reads as its code.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { signedIn } from "@/components/rehome/research/test-workspace";
import { ApiError, research } from "@/lib/api";

let answer: { code?: string; message?: string } = {};

beforeEach(() => {
  signedIn();
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    if (String(url).split("?")[0] === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
    return new Response(JSON.stringify(answer), { status: 409, statusText: "Conflict" });
  }));
});
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("a refusal from the API", () => {
  it("reads an empty message as its code, and keeps a message it was given", async () => {
    answer = { code: "report_artifact_missing", message: "" };
    const empty = await research.run("STU-1", "RUN-1").catch((e: unknown) => e);
    expect(empty).toBeInstanceOf(ApiError);
    expect((empty as ApiError).message).toBe("report_artifact_missing");
    answer = { code: "stale", message: "Upraveno mezitím." };
    expect(((await research.run("STU-1", "RUN-1").catch((e: unknown) => e)) as ApiError).message).toBe("Upraveno mezitím.");
  });
});
