import { describe, expect, it } from "vitest";
import { apiConfig, apiGet, errorKind } from "./client";
import { listOf, pageOf, parseClient, parseProjectDetail, parseStudy } from "./validate";

const config = { baseUrl: "http://api.test/api/v1", subject: "lead@aia.dev", org: null };

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  return async () => new Response(body === undefined ? "" : JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
}

const client = { client_id: "CLI-1", slug: "a", name: "A", status: "ACTIVE", reference: "", study_count: 1, created_at: null };
const study = {
  study_id: "STU-1", client_id: "CLI-1", slug: "s", name: "S", status: "DRAFT", accepts_work: true, your_role: "LEAD",
  budget_usd: 250, spent_usd: 0, remaining_usd: 250, created_at: null, modified_at: null, delivered_at: null,
};

describe("apiConfig", () => {
  it("defaults to the local API and no identity", () => {
    expect(apiConfig({})).toEqual({ baseUrl: "http://localhost:8000/api/v1", subject: null, org: null });
  });
  it("trims a trailing slash and blank values", () => {
    expect(apiConfig({ AIA_API_URL: "http://x/api/v1/", AIA_DEV_SUBJECT: "  ", AIA_DEV_ORG: "ORG-1" })).toEqual({ baseUrl: "http://x/api/v1", subject: null, org: "ORG-1" });
  });
});

describe("apiGet", () => {
  it("sends the development identity and returns parsed data", async () => {
    let seen: RequestInit | undefined;
    const r = await apiGet("/clients", listOf(parseClient), {
      config,
      fetchImpl: async (_url, init) => { seen = init; return new Response(JSON.stringify([client]), { status: 200, headers: { "x-request-id": "rq1" } }); },
    });
    expect(r).toEqual({ ok: true, data: [client], requestId: "rq1" });
    expect((seen?.headers as Record<string, string>)["X-AIA-Subject"]).toBe("lead@aia.dev");
    expect(seen?.cache).toBe("no-store");
  });

  it("reports an unreachable API as unreachable, not as empty", async () => {
    const r = await apiGet("/clients", listOf(parseClient), { config, fetchImpl: async () => { throw new TypeError("fetch failed"); } });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatchObject({ kind: "unreachable", status: null, message: "fetch failed" });
  });

  it("keeps the error contract's code and request id", async () => {
    const r = await apiGet("/studies", listOf(parseStudy), {
      config,
      fetchImpl: respond(403, { code: "not_provisioned", message: "no org", details: {}, request_id: "rq2" }),
    });
    expect(!r.ok && r.error).toMatchObject({ kind: "not_provisioned", status: 403, code: "not_provisioned", requestId: "rq2" });
  });

  it("treats a shape mismatch as an error, never as data", async () => {
    const r = await apiGet("/clients", listOf(parseClient), { config, fetchImpl: respond(200, [{ ...client, study_count: "1" }]) });
    expect(!r.ok && r.error.kind).toBe("invalid_response");
  });

  it("survives a non-JSON error body", async () => {
    const r = await apiGet("/clients", listOf(parseClient), { config, fetchImpl: async () => new Response("<html>", { status: 502, statusText: "Bad Gateway" }) });
    expect(!r.ok && r.error).toMatchObject({ kind: "error", status: 502, code: null });
  });
});

describe("errorKind", () => {
  it.each([
    [401, null, "unauthenticated"],
    [404, "not_found", "not_found"],
    [403, "not_provisioned", "not_provisioned"],
    [400, "organization_required", "organization_required"],
    [500, "internal_error", "error"],
  ] as const)("%i %s → %s", (status, code, kind) => expect(errorKind(status, code)).toBe(kind));

  it("treats a malformed path id as not found, and a malformed query as an error", () => {
    const path = { errors: [{ loc: ["path", "study_id"], msg: "pattern" }] };
    const query = { errors: [{ loc: ["query", "field"], msg: "bad" }] };
    expect(errorKind(422, "validation_error", path)).toBe("not_found");
    expect(errorKind(422, "validation_error", query)).toBe("error");
    expect(errorKind(422, "validation_error", {})).toBe("error");
  });
});

describe("validators", () => {
  it("accepts a study whose cost fields are withheld (null)", () => {
    expect(parseStudy({ ...study, budget_usd: null, spent_usd: null, remaining_usd: null })).not.toBeNull();
  });
  it("rejects a study whose budget is a string", () => {
    expect(parseStudy({ ...study, budget_usd: "250" })).toBeNull();
  });
  it("rejects a list when one item is malformed — a partial list would read as complete", () => {
    expect(listOf(parseClient)([client, { client_id: 1 }])).toBeNull();
  });
  it("reads the paginated envelope", () => {
    expect(pageOf(parseClient)({ items: [client], page: { total: 1, limit: 50, offset: 0, has_more: false } })?.page.total).toBe(1);
    expect(pageOf(parseClient)({ items: [client] })).toBeNull();
  });
  it("rejects a project whose stages are malformed", () => {
    const p = { project_id: "P", title: "T", project_type: "research", status: "DRAFT", current_stage: "BRIEF", current_revision: 1, last_completed_stage: null };
    const stage = { stage_type: "BRIEF", status: "NOT_STARTED", label: "Kontext", ordinal: 0, artifact_count: 0, waiting_reason: null, quota_reset_at: null, started_at: null, finished_at: null, is_complete: false };
    expect(parseProjectDetail({ ...p, stages: [stage] })?.stages).toHaveLength(1);
    expect(parseProjectDetail({ ...p, stages: [{ ...stage, ordinal: "0" }] })).toBeNull();
    expect(parseProjectDetail(p)).toBeNull();
  });
});
