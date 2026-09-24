import { readFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { join } from "node:path";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

// A local stub of the unit's `/` (CLAUDE.md §7: stand up a local stub, never the
// real service). It serves the real vendored document unless told otherwise.
const realDocument = readFileSync(join(process.cwd(), "../../legacy/npc-panel-18.6.6/app/ui_app.html"));
let respond: (res: import("node:http").ServerResponse) => void;
let server: Server;

beforeAll(async () => {
  server = createServer((req, res) => (req.url === "/" ? respond(res) : (res.statusCode = 404, res.end())));
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  vi.stubEnv("AIA_LEGACY_PANEL_URL", `http://127.0.0.1:${(server.address() as AddressInfo).port}/`);
  vi.stubEnv("AIA_BUILD_SHA", "abc1234");
});
afterAll(async () => {
  vi.unstubAllEnvs();
  await new Promise<void>((resolve) => server.close(() => resolve()));
});
afterEach(() => {
  vi.stubEnv("AIA_INTERFACE_SKIN_ENABLED", "");
  vi.stubEnv("AIA_INTERFACE_REHOME_ENABLED", "");
  vi.restoreAllMocks();
});

const serve = (status: number, body: Buffer) => {
  respond = (res) => {
    res.writeHead(status, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
    res.end(body);
  };
};

describe("GET /interface-document", () => {
  it("adds the skin to the pinned document when the switch is on", async () => {
    serve(200, realDocument);
    vi.stubEnv("AIA_INTERFACE_SKIN_ENABLED", "true");
    const res = await GET();
    const html = await res.text();
    expect(res.status).toBe(200);
    expect(res.headers.get("x-aia-skin")).toBe("applied");
    expect(res.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(res.headers.get("cache-control")).toContain("no-store");
    expect(html).toContain('<link rel="stylesheet" href="/skin/skin.css?v=abc1234" data-aia-skin="ADR-0013">');
  });

  it("serves the document byte-for-byte when the switch is off (the default)", async () => {
    serve(200, realDocument);
    const res = await GET();
    expect(res.headers.get("x-aia-skin")).toBe("bypassed-disabled");
    expect(res.headers.get("x-aia-handoff")).toBe("bypassed-disabled");
    expect(Buffer.from(await res.arrayBuffer()).equals(realDocument)).toBe(true);
  });

  it("serves an unpinned document byte-for-byte and says so in the log", async () => {
    const other = Buffer.concat([realDocument, Buffer.from("\n")]);
    serve(200, other);
    vi.stubEnv("AIA_INTERFACE_SKIN_ENABLED", "true");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const res = await GET();
    expect(res.headers.get("x-aia-skin")).toBe("bypassed-hash-mismatch");
    expect(Buffer.from(await res.arrayBuffer()).equals(other)).toBe(true);
    expect(JSON.parse(warn.mock.calls[0][0] as string)).toMatchObject({
      event: "interface_skin_bypassed",
      outcome: "bypassed-hash-mismatch",
    });
  });

  it("passes the unit's error status and body through unchanged", async () => {
    serve(503, Buffer.from("starting"));
    vi.stubEnv("AIA_INTERFACE_SKIN_ENABLED", "true");
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const res = await GET();
    expect(res.status).toBe(503);
    expect(res.headers.get("x-aia-skin")).toBe("bypassed-upstream-status");
    expect(await res.text()).toBe("starting");
  });

  it("adds the hand-off script to the pinned document while the rebuilt interface is on", async () => {
    serve(200, realDocument);
    vi.stubEnv("AIA_INTERFACE_SKIN_ENABLED", "true");
    vi.stubEnv("AIA_INTERFACE_REHOME_ENABLED", "true");
    const res = await GET();
    const html = await res.text();
    expect(res.headers.get("x-aia-handoff")).toBe("added");
    expect(html).toContain('<script src="/skin/handoff.js?v=abc1234" data-aia-handoff="ADR-0014"></script></body>');
    expect(html).toContain('data-aia-skin="ADR-0013">');
  });

  it("adds the hand-off without the skin, and neither to an unpinned document", async () => {
    serve(200, realDocument);
    vi.stubEnv("AIA_INTERFACE_REHOME_ENABLED", "true");
    let res = await GET();
    expect(res.headers.get("x-aia-skin")).toBe("bypassed-disabled");
    expect(res.headers.get("x-aia-handoff")).toBe("added");
    expect(await res.text()).not.toContain("data-aia-skin");

    serve(200, Buffer.concat([realDocument, Buffer.from("\n")]));
    vi.spyOn(console, "warn").mockImplementation(() => {});
    res = await GET();
    expect(res.headers.get("x-aia-handoff")).toBe("bypassed-hash-mismatch");
  });

  it("answers 502 when the unit is unreachable", async () => {
    vi.stubEnv("AIA_LEGACY_PANEL_URL", "http://127.0.0.1:1");
    const res = await GET();
    expect(res.status).toBe(502);
    expect(res.headers.get("x-aia-skin")).toBe("bypassed-unreachable");
    vi.stubEnv("AIA_LEGACY_PANEL_URL", `http://127.0.0.1:${(server.address() as AddressInfo).port}/`);
  });
});
