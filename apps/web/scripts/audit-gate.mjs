#!/usr/bin/env node
/**
 * The security job's npm gate: fails on every high or critical advisory in apps/web's
 * dependencies, production and dev, unless audit-allowlist.json names that advisory's
 * GHSA id for that package and its recheck date has not passed.
 *
 * Matched by id, never by package name: an allowlisted package that gains a new advisory
 * still fails. An entry past its recheck date no longer counts, so CI fails until someone
 * looks again. An audit that cannot be read (npm's error, a report shape this script does
 * not know) fails too: an unread audit is never a clean one.
 *
 *   node scripts/audit-gate.mjs                     runs `npm audit --json` here
 *   node scripts/audit-gate.mjs --report <file>     judges a stored report
 *   --allowlist <file>  --today YYYY-MM-DD           for tests
 *   --npm <executable>  --timeout-ms <n>             for tests: what runs the audit, and its limit
 *
 * The audit is asked at most ATTEMPTS times, each stopped after TIMEOUT_MS: npm's audit endpoint
 * has hung for ~420 s and answered with an empty error (three runs on 2026-10-22). Each attempt's
 * time and exit is logged, and to the job's step summary in CI. A second unread report fails.
 *
 * Exits 0 when nothing blocks, 1 when something does, 2 when the input cannot be read.
 */
import { spawnSync } from "node:child_process";
import { appendFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const BLOCKING = new Set(["high", "critical"]);
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const FIELDS = ["id", "package", "path", "added", "recheck", "reason", "approved_by"];
const ATTEMPTS = 2;
const TIMEOUT_MS = 150_000;

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!["--report", "--allowlist", "--today", "--npm", "--timeout-ms"].includes(key) || argv[i + 1] === undefined) {
      throw new Error(`unknown or incomplete argument: ${key}`);
    }
    out[key.slice(2)] = argv[i + 1];
  }
  return out;
}

function readAllowlist(file) {
  const entries = JSON.parse(readFileSync(file, "utf8")).entries;
  if (!Array.isArray(entries)) throw new Error(`${file}: no entries list`);
  for (const e of entries) {
    const missing = FIELDS.filter((f) => typeof e[f] !== "string" || !e[f].trim());
    if (missing.length) throw new Error(`${file}: ${e.id ?? "an entry"} lacks ${missing.join(", ")}`);
    if (!/^GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$/.test(e.id)) throw new Error(`${file}: ${e.id} is not a GHSA id`);
    for (const f of ["added", "recheck"]) if (!DATE.test(e[f])) throw new Error(`${file}: ${e.id} ${f} is not YYYY-MM-DD`);
  }
  return entries;
}

function readReport(text) {
  const report = JSON.parse(text);
  if (report.error) throw new Error(`npm audit failed: ${report.error.summary || report.error.code || JSON.stringify(report.error)}`);
  if (report.auditReportVersion !== 2 || typeof report.vulnerabilities !== "object") {
    throw new Error(`unknown npm audit report shape (auditReportVersion ${report.auditReportVersion})`);
  }
  return report;
}

// Every advisory in the report, once per (id, package): npm lists an advisory under the
// package it is in, as an object in `via`; a bare string in `via` is a dependency path.
function advisories(report) {
  const found = new Map();
  for (const vuln of Object.values(report.vulnerabilities)) {
    for (const via of vuln.via ?? []) {
      if (typeof via !== "object" || via === null) continue;
      const id = /GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}/.exec(via.url ?? "")?.[0] ?? null;
      const key = `${id ?? via.source}|${via.name}`;
      if (!found.has(key)) found.set(key, { id, package: via.name, severity: via.severity, title: via.title, url: via.url });
    }
  }
  return [...found.values()];
}

function judge(report, entries, today) {
  const blocking = advisories(report).filter((a) => BLOCKING.has(a.severity));
  const counted = report.metadata?.vulnerabilities ?? {};
  // A count of blocking packages with no advisory found means the report says more than
  // this script read: fail rather than pass on what it did not see.
  if (blocking.length === 0 && (counted.high > 0 || counted.critical > 0)) {
    throw new Error(`the report counts ${counted.high} high / ${counted.critical} critical but no advisory was read`);
  }
  const live = entries.filter((e) => today <= e.recheck);
  const failures = [];
  const waived = [];
  for (const a of blocking) {
    const entry = a.id && live.find((e) => e.id === a.id && e.package === a.package);
    if (entry) waived.push({ ...a, entry });
    else failures.push({ ...a, expired: entries.find((e) => e.id === a.id && e.package === a.package) ?? null });
  }
  const unused = entries.filter((e) => !blocking.some((a) => a.id === e.id && a.package === e.package));
  return { failures, waived, unused };
}

// `npm audit --json`, asked again once when an attempt gives no readable report (a timeout, npm's
// error, no JSON): the report read, or the last attempt's reason thrown. Never a report not read.
function audit(npm, timeoutMs) {
  let problem = "";
  for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
    const started = Date.now();
    // npm audit exits non-zero whenever it finds anything; the report is judged, not the exit.
    const run = spawnSync(npm, ["audit", "--json"], { cwd: root, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, timeout: timeoutMs, killSignal: "SIGKILL" });
    const seconds = ((Date.now() - started) / 1000).toFixed(1);
    // What npm wrote is read even when it was stopped: a whole report before a hang still counts.
    let report = null;
    try {
      report = readReport(run.stdout ?? "");
    } catch (e) {
      if (run.error?.code === "ETIMEDOUT") problem = `timed out after ${timeoutMs / 1000} s`;
      else if (run.error) problem = run.error.message;
      else problem = e instanceof Error ? e.message : String(e);
    }
    const line = `npm audit attempt ${attempt}/${ATTEMPTS}: ${seconds} s, exit ${run.status ?? run.signal ?? run.error?.code}, ${report ? "report read" : problem}`;
    console.log(line);
    try {
      if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, `- ${line}\n`);
    } catch {
      // The summary is a log; it never decides the verdict.
    }
    if (report) return report;
  }
  throw new Error(`no report after ${ATTEMPTS} attempts: ${problem}`);
}

function main() {
  const opts = args(process.argv.slice(2));
  const today = opts.today ?? new Date().toISOString().slice(0, 10);
  if (!DATE.test(today)) throw new Error(`--today ${today} is not YYYY-MM-DD`);
  const entries = readAllowlist(opts.allowlist ?? join(root, "audit-allowlist.json"));
  const timeoutMs = Number(opts["timeout-ms"] ?? TIMEOUT_MS);
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1) throw new Error(`--timeout-ms ${opts["timeout-ms"]} is not a whole number of ms`);
  const report = opts.report ? readReport(readFileSync(opts.report, "utf8")) : audit(opts.npm ?? "npm", timeoutMs);
  const { failures, waived, unused } = judge(report, entries, today);
  for (const w of waived) {
    console.log(`allowed  ${w.severity} ${w.id} in ${w.package} until ${w.entry.recheck}: ${w.entry.reason}`);
  }
  for (const u of unused) console.log(`unused   ${u.id} in ${u.package}: no longer reported; remove it from audit-allowlist.json`);
  for (const f of failures) {
    const why = f.expired ? ` (its allowlist entry expired on ${f.expired.recheck}; re-check it)` : "";
    console.log(`::error::${f.severity} ${f.id ?? "advisory without a GHSA id"} in ${f.package}: ${f.title} ${f.url ?? ""}${why}`);
  }
  console.log(failures.length ? `npm audit gate: ${failures.length} blocking advisory(ies)` : `npm audit gate: nothing blocks (${waived.length} allowed)`);
  return failures.length ? 1 : 0;
}

try {
  process.exitCode = main();
} catch (e) {
  console.log(`::error::npm audit gate: ${e instanceof Error ? e.message : String(e)}`);
  process.exitCode = 2;
}
