import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
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

// A stand-in for npm: each call takes the next step of FAKE_PLAN (`hang`, `error` or `report`),
// counted in FAKE_DIR, so an attempt can time out or come back unreadable without the network.
const fakeNpm = join(dir, "npm.mjs");
writeFileSync(fakeNpm, `#!/usr/bin/env node
import { existsSync, readFileSync, writeFileSync } from "node:fs";
const count = process.env.FAKE_DIR + "/calls";
const n = existsSync(count) ? Number(readFileSync(count, "utf8")) : 0;
writeFileSync(count, String(n + 1));
const step = process.env.FAKE_PLAN.split(",")[n];
if (step === "hang") setTimeout(() => {}, 60000);
else if (step === "answer-then-hang") process.stdout.write(process.env.FAKE_REPORT, () => setTimeout(() => {}, 60000));
else if (step === "error") process.stdout.write(JSON.stringify({ error: { code: "ETIMEDOUT", summary: "" } }));
else process.stdout.write(process.env.FAKE_REPORT);
`);
chmodSync(fakeNpm, 0o755);

function audited(plan: string) {
  const work = mkdtempSync(join(dir, "plan-"));
  const summary = join(work, "summary.md");
  writeFileSync(join(work, "allow.json"), JSON.stringify({ entries: [] }));
  const run = spawnSync(process.execPath, [script, "--npm", fakeNpm, "--timeout-ms", "3000", "--today", "2026-10-20", "--allowlist", join(work, "allow.json")], {
    encoding: "utf8",
    env: { ...process.env, FAKE_DIR: work, FAKE_PLAN: plan, FAKE_REPORT: JSON.stringify(report([])), GITHUB_STEP_SUMMARY: summary },
  });
  const calls = Number(readFileSync(join(work, "calls"), "utf8"));
  return { code: run.status, out: run.stdout + run.stderr, calls, summary: existsSync(summary) ? readFileSync(summary, "utf8") : "" };
}

describe("npm audit gate, asking npm", () => {
  it("asks again after an attempt that timed out, and judges the report it then reads", () => {
    const run = audited("hang,report");
    expect([run.code, run.calls]).toEqual([0, 2]);
    expect(run.out).toMatch(/attempt 1\/2: [\d.]+ s, exit SIGKILL, timed out after 3 s/);
    expect(run.out).toMatch(/attempt 2\/2: [\d.]+ s, exit 0, report read/);
    expect(run.summary.split("\n").filter(Boolean)).toHaveLength(2);
  });

  it("asks again after npm's own error, naming its code when its summary is empty", () => {
    const run = audited("error,report");
    expect([run.code, run.calls]).toEqual([0, 2]);
    expect(run.out).toContain("attempt 1/2");
    expect(run.out).toContain("npm audit failed: ETIMEDOUT");
  });

  it("fails when the second attempt reads no report either, never passing on a missing one", () => {
    const run = audited("hang,hang,report");
    expect([run.code, run.calls]).toEqual([2, 2]);
    expect(run.out).toContain("no report after 2 attempts: timed out after 3 s");
    expect(audited("hang,error").code).toBe(2);
  });

  it("asks once when the first attempt reads", () => {
    expect(audited("report").calls).toBe(1);
  });

  it("judges a whole report npm wrote before it hung", () => {
    const run = audited("answer-then-hang");
    expect([run.code, run.calls]).toEqual([0, 1]);
    expect(run.out).toMatch(/attempt 1\/2: [\d.]+ s, exit SIGKILL, report read/);
  });
});
