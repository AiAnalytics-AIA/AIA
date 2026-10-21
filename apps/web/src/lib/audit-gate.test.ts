import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// scripts/audit-gate.mjs, run as CI runs it, over stored reports: no network, no npm.
const script = join(__dirname, "../../scripts/audit-gate.mjs");
const dir = mkdtempSync(join(tmpdir(), "audit-gate-"));
const BRACES = "GHSA-vfj7-8cjw-p6xm";

type Advisory = { id: string; name: string; severity: string };

function report(advisories: Advisory[], counts?: { high: number; critical: number }) {
  const vulnerabilities: Record<string, unknown> = {};
  for (const a of advisories) {
    vulnerabilities[a.name] = {
      name: a.name,
      severity: a.severity,
      via: [{ source: 1, name: a.name, title: `${a.name} advisory`, url: `https://github.com/advisories/${a.id}`, severity: a.severity }],
    };
  }
  const high = counts?.high ?? advisories.filter((a) => a.severity === "high").length;
  const critical = counts?.critical ?? advisories.filter((a) => a.severity === "critical").length;
  return { auditReportVersion: 2, vulnerabilities, metadata: { vulnerabilities: { high, critical } } };
}

const entry = {
  id: BRACES,
  package: "braces",
  path: "eslint-config-next > @next/eslint-plugin-next > fast-glob > micromatch > braces",
  added: "2026-10-20",
  recheck: "2026-11-20",
  reason: "dev-only lint tooling; no fixed version",
  approved_by: "test",
};

let n = 0;
function gate(body: unknown, opts: { today?: string; allowlist?: unknown } = {}) {
  const reportFile = join(dir, `report-${++n}.json`);
  writeFileSync(reportFile, JSON.stringify(body));
  const args = [script, "--report", reportFile, "--today", opts.today ?? "2026-10-20"];
  if (opts.allowlist !== undefined) {
    const allowFile = join(dir, `allow-${n}.json`);
    writeFileSync(allowFile, JSON.stringify(opts.allowlist));
    args.push("--allowlist", allowFile);
  }
  const run = spawnSync(process.execPath, args, { encoding: "utf8" });
  return { code: run.status, out: run.stdout + run.stderr };
}

const allow = { entries: [entry] };
const braces = { id: BRACES, name: "braces", severity: "high" };

describe("npm audit gate", () => {
  it("reads the committed allowlist", () => {
    expect(gate(report([])).code).toBe(0);
  });

  it("passes an allowlisted advisory before its recheck date", () => {
    const run = gate(report([braces]), { allowlist: allow });
    expect(run.code).toBe(0);
    expect(run.out).toContain(`allowed  high ${BRACES} in braces until 2026-11-20`);
  });

  it("passes on the recheck date and fails the day after", () => {
    expect(gate(report([braces]), { today: "2026-11-20", allowlist: allow }).code).toBe(0);
    const late = gate(report([braces]), { today: "2026-11-21", allowlist: allow });
    expect(late.code).toBe(1);
    expect(late.out).toContain("expired on 2026-11-20");
  });

  it("fails a new advisory in an allowlisted package: matched by id, not by name", () => {
    const run = gate(report([{ id: "GHSA-aaaa-bbbb-cccc", name: "braces", severity: "high" }]), { allowlist: allow });
    expect(run.code).toBe(1);
    expect(run.out).toContain("GHSA-aaaa-bbbb-cccc in braces");
  });

  it("fails an allowlisted id reported in another package", () => {
    expect(gate(report([{ id: BRACES, name: "micromatch", severity: "high" }]), { allowlist: allow }).code).toBe(1);
  });

  it("fails high and critical advisories, and passes moderate and low ones", () => {
    expect(gate(report([{ id: "GHSA-1111-2222-3333", name: "next", severity: "critical" }]), { allowlist: allow }).code).toBe(1);
    expect(gate(report([{ id: "GHSA-1111-2222-3333", name: "next", severity: "high" }]), { allowlist: allow }).code).toBe(1);
    expect(gate(report([{ id: "GHSA-1111-2222-3333", name: "next", severity: "moderate" }]), { allowlist: allow }).code).toBe(0);
  });

  it("fails the blocking advisory beside an allowed one", () => {
    const run = gate(report([braces, { id: "GHSA-1111-2222-3333", name: "next", severity: "high" }]), { allowlist: allow });
    expect(run.code).toBe(1);
    expect(run.out).toContain("1 blocking");
  });

  it("names an allowlist entry no longer reported", () => {
    const run = gate(report([]), { allowlist: allow });
    expect(run.code).toBe(0);
    expect(run.out).toContain(`unused   ${BRACES} in braces`);
  });

  it("refuses a report it cannot read rather than passing it", () => {
    expect(gate({ error: { code: "ENOAUDIT", summary: "no registry" } }, { allowlist: allow }).code).toBe(2);
    expect(gate({ auditReportVersion: 1, advisories: {} }, { allowlist: allow }).code).toBe(2);
    // Counts that say high with no advisory read: the shape moved, not a clean audit.
    expect(gate({ auditReportVersion: 2, vulnerabilities: {}, metadata: { vulnerabilities: { high: 2, critical: 0 } } }, { allowlist: allow }).code).toBe(2);
  });

  it("refuses an allowlist entry without its id, dates or reason", () => {
    const noReason = Object.fromEntries(Object.entries(entry).filter(([k]) => k !== "reason"));
    expect(gate(report([braces]), { allowlist: { entries: [noReason] } }).code).toBe(2);
    expect(gate(report([braces]), { allowlist: { entries: [{ ...entry, recheck: "next month" }] } }).code).toBe(2);
    expect(gate(report([braces]), { allowlist: { entries: [{ ...entry, id: "braces" }] } }).code).toBe(2);
  });
});
