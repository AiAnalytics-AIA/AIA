import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  PINNED_INTERFACE_SHA256,
  applySkin,
  sha256Hex,
  skinEnabledFrom,
  stylesheetHref,
} from "./interface-skin";

const UNIT = join(process.cwd(), "../../legacy/npc-panel-18.6.6");
const realDocument = readFileSync(join(UNIT, "app/ui_app.html"));

describe("the pin", () => {
  it("is the hash app-manifest.json records for ui_app.html", () => {
    const manifest = JSON.parse(readFileSync(join(UNIT, "app-manifest.json"), "utf8"));
    const entries: Array<{ path: string; sha256: string }> = Array.isArray(manifest)
      ? manifest
      : (manifest.files ?? manifest.entries ?? []);
    const entry = entries.find((e) => e.path === "ui_app.html");
    expect(entry, "ui_app.html in app-manifest.json").toBeDefined();
    expect(PINNED_INTERFACE_SHA256).toBe(entry!.sha256);
  });

  it("is the hash of the vendored document itself", () => {
    expect(sha256Hex(realDocument)).toBe(PINNED_INTERFACE_SHA256);
  });
});

describe("applySkin on the real 18.6.6 document", () => {
  const decision = applySkin(realDocument, { enabled: true, version: "abc1234" });
  const html = decision.body.toString("utf8");

  it("applies", () => {
    expect(decision.outcome).toBe("applied");
    expect(decision.receivedSha256).toBe(PINNED_INTERFACE_SHA256);
  });

  it("adds exactly the two tags and changes nothing else", () => {
    const preload = '<link rel="preload" as="style" href="/skin/skin.css?v=abc1234" data-aia-skin="preload">';
    const stylesheet = '<link rel="stylesheet" href="/skin/skin.css?v=abc1234" data-aia-skin="ADR-0013">';
    expect(html.split(preload)).toHaveLength(2);
    expect(html.split(stylesheet)).toHaveLength(2);
    expect(html.replace(preload, "").replace(stylesheet, "")).toBe(realDocument.toString("utf8"));
  });

  it("preloads in <head> and links after every <style> block in the document", () => {
    const headEnd = html.indexOf("</head>");
    expect(html.indexOf('data-aia-skin="preload"')).toBeLessThan(headEnd);
    const link = html.indexOf('data-aia-skin="ADR-0013"');
    expect(link).toBeGreaterThan(html.lastIndexOf("<style"));
    expect(link).toBeLessThan(html.lastIndexOf("</body>"));
  });
});

describe("applySkin leaves the document untouched when it should", () => {
  it("when the kill switch is off", () => {
    const d = applySkin(realDocument, { enabled: false, version: null });
    expect(d.outcome).toBe("bypassed-disabled");
    expect(d.body.equals(realDocument)).toBe(true);
  });

  it("when one byte differs from the pinned document", () => {
    const altered = Buffer.from(realDocument);
    altered[altered.length - 1] ^= 0x01;
    const d = applySkin(altered, { enabled: true, version: null });
    expect(d.outcome).toBe("bypassed-hash-mismatch");
    expect(d.body.equals(altered)).toBe(true);
    expect(d.receivedSha256).not.toBe(PINNED_INTERFACE_SHA256);
  });

  it("when the document has no </head>, even with a matching pin", () => {
    const doc = Buffer.from("<html><body>no head</body></html>");
    const d = applySkin(doc, { enabled: true, version: null, pinnedSha256: sha256Hex(doc) });
    expect(d.outcome).toBe("bypassed-no-head");
    expect(d.body.equals(doc)).toBe(true);
  });

  it("when the document has no </body> after </head>", () => {
    const doc = Buffer.from("<html><head></head>no body close");
    const d = applySkin(doc, { enabled: true, version: null, pinnedSha256: sha256Hex(doc) });
    expect(d.outcome).toBe("bypassed-no-body");
    expect(d.body.equals(doc)).toBe(true);
  });
});

describe("configuration", () => {
  it("turns on only for an explicit true or 1", () => {
    for (const v of ["true", "TRUE", " 1 ", "1"]) expect(skinEnabledFrom(v), v).toBe(true);
    for (const v of [undefined, "", "0", "false", "yes", "on"]) expect(skinEnabledFrom(v), String(v)).toBe(false);
  });

  it("versions the stylesheet URL when a build SHA is known", () => {
    expect(stylesheetHref(null)).toBe("/skin/skin.css");
    expect(stylesheetHref("a b")).toBe("/skin/skin.css?v=a%20b");
  });
});
