#!/usr/bin/env node
/** Deep Research in a real browser, with nothing paid (plan research-lead-workbench 12a, DRL-1).
 * The workbench's worker runs the six Deep Research steps on a fictional recorded web
 * (tools/ui_workbench/fixtures/deep_research/web.json) and answers every agent from a script
 * (aia_executors.workbench ScriptedDeepResearchModel), so no model or search is paid and no
 * request leaves the machine. Start the workbench, write the fixtures, then run:
 *   python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/deep_research_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * It opens the deep_research fixture's Dotazník, starts a Design Research run from the panel
 * ("Spustit veřejný výzkum"), follows it to completion, reads its sealed bundle (every source a
 * RECORDED_FIXTURE snapshot) and, where the review exists (#554), opens "Zkontrolovat návrh" and
 * accepts one EVIDENCE item. It asserts that the usage ledger gained no priced row, that no
 * study spent anything, and that the browser asked nothing of any host but the workbench.
 */
import assert from "node:assert/strict";
import { execFileSync, execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
const LOCAL = ["127.0.0.1", "localhost"];
assert(LOCAL.includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/deep-research-journey"));
const db = arg("db", join(repo, "tmp/ui-workbench/aia.sqlite"));
mkdirSync(out, { recursive: true });
const TOKEN = "workbench@example.invalid";

async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  for (const from of [repo, join(repo, "apps/web")]) {
    try {
      return await import(pathToFileURL(require.resolve("playwright", { paths: [from] })).href);
    } catch {
      /* next */
    }
  }
  const root = execSync("npm root -g", { encoding: "utf8" }).trim();
  return await import(pathToFileURL(join(root, "playwright/index.mjs")).href);
}

/** The usage ledger and the studies' spend, read from the workbench's own SQLite file. */
function ledger() {
  const script = [
    "import json, sqlite3, sys",
    "c = sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True)",
    "rows = c.execute('select count(*), coalesce(sum(cost_usd), 0) from ai_usage_events where cost_usd > 0').fetchone()",
    "routes = sorted(r[0] for r in c.execute('select distinct route_id from ai_usage_events'))",
    "spent = c.execute('select coalesce(sum(spent_usd), 0) from studies').fetchone()[0]",
    "total = c.execute('select count(*) from ai_usage_events').fetchone()[0]",
    "accepts = c.execute(\"select count(*) from approval_decisions where subject_type = 'design_research'\").fetchone()[0]",
    "print(json.dumps({'paid_rows': rows[0], 'paid_usd': rows[1], 'routes': routes, 'spent_usd': spent, 'rows': total, 'design_research_accepts': accepts}))",
  ].join("\n");
  return JSON.parse(execFileSync("python3", ["-I", "-c", script, db], { encoding: "utf8" }));
}

const module = await loadPlaywright();
const chromium = module.chromium ?? module.default.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], writes = [], external = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const url = new URL(r.url());
  if (!["http:", "https:", "ws:", "wss:"].includes(url.protocol)) return;
  if (!LOCAL.includes(url.hostname)) external.push(r.url());
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !url.pathname.startsWith("/_next/")) writes.push({ method: r.method(), path: url.pathname });
});
const check = (name) => checks.push(name);
const api = async (method, path, body) => {
  const response = await page.request.fetch(`${base}/api/v1${path}`, {
    method,
    headers: { authorization: `Bearer ${TOKEN}`, "content-type": "application/json" },
    data: body === undefined ? undefined : JSON.stringify(body),
  });
  assert(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`);
  return response.json();
};

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
assert(fixtures.deep_research, "No deep_research fixture: run tools/ui_workbench/fixture_project.py");
const { client, study } = fixtures.deep_research;
const runsPath = `/studies/${study}/deep-research/runs`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`), fullPage: false });
let before = ledger();
let reviewed = "not offered: the review of #554 is not in this build";

try {
  // The fixture's own run completes on the worker (the fixture script only starts it).
  if (fixtures.deep_research.deep_research_run) {
    let fixtureRun = await api("GET", `${runsPath}/${fixtures.deep_research.deep_research_run}`);
    for (let i = 0; i < 120 && !fixtureRun.is_terminal; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      fixtureRun = await api("GET", `${runsPath}/${fixtures.deep_research.deep_research_run}`);
    }
    assert.equal(fixtureRun.status, "COMPLETED", `the fixture's run is ${fixtureRun.status}`);
    check("the fixture study's Design Research run completed on the workbench's worker");
    before = ledger(); // what the browser's own start adds is measured from here
  }

  await page.goto(`${base}/app/clients/${client}/research/${study}/questionnaire`);
  const panel = page.locator("section[aria-labelledby='deep-research-title']");
  await panel.waitFor({ timeout: 60000 });
  await panel.scrollIntoViewIfNeeded();
  await shot("1440-panel-before");

  // Start from the panel, as a person does: the working copy is submitted, then the run starts.
  const startButton = panel.getByRole("button", { name: "Spustit veřejný výzkum" });
  const [started] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === `/api/v1${runsPath}` && r.request().method() === "POST", { timeout: 60000 }),
    startButton.click(),
  ]);
  assert([200, 201].includes(started.status()), `start answered ${started.status()}: ${await started.text()}`);
  const run = await started.json();
  check(`a Design Research run started from the panel (${started.status() === 201 ? "a new run" : "the run this design already had"})`);

  // Follow it: the worker claims each step; the panel polls until the run ends.
  let current = run;
  for (let i = 0; i < 120 && !current.is_terminal; i++) {
    await page.waitForTimeout(1000);
    current = await api("GET", `${runsPath}/${run.run_id}`);
    if (i === 1) await shot("1440-running");
  }
  assert.equal(current.status, "COMPLETED", `the run ended ${current.status}: ${JSON.stringify(current.steps)}`);
  assert.deepEqual(current.steps.map((s) => s.status), Array(current.steps.length).fill("SUCCEEDED"));
  check(`the run completed: ${current.steps.map((s) => s.node_key).join(" → ")}`);

  // The bundle the panel reads: sealed, every source a recorded fixture.
  await panel.getByText("Výsledek:", { exact: false }).waitFor({ timeout: 60000 });
  const bundle = await api("GET", `${runsPath}/${run.run_id}/bundle`);
  assert.deepEqual(bundle.origins, ["RECORDED_FIXTURE"], "every finding is from the recorded fixture");
  assert(bundle.accepted.length > 0, "the bundle accepted nothing");
  assert(bundle.snapshots.length > 0 && bundle.snapshots.every((s) => s.retrieval_mode === "RECORDED"), "a snapshot was not recorded");
  assert(bundle.snapshots.every((s) => new URL(s.url).hostname.endsWith(".example")), "a snapshot is not a fictional host");
  const shown = await panel.locator("article").count();
  assert.equal(shown, bundle.accepted.length, "the panel shows every accepted finding");
  check(`the panel shows the sealed bundle: ${bundle.accepted.length} accepted findings, ${bundle.snapshots.length} recorded snapshots, ${bundle.quarantined.length} set aside`);
  await panel.scrollIntoViewIfNeeded();
  await shot("1440-completed");

  // The proposal review (#554), where this build has it: one EVIDENCE item accepted.
  const review = page.getByRole("button", { name: "Zkontrolovat návrh" });
  if (await review.count()) {
    await review.first().click();
    const box = page.getByRole("checkbox").first();
    await box.waitFor({ timeout: 30000 });
    await box.check();
    await shot("1440-review");
    const [accepted] = await Promise.all([
      page.waitForResponse((r) => /\/design-proposal\/accept$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 60000 }),
      page.getByRole("button", { name: "Přijmout vybrané" }).click(),
    ]);
    assert(accepted.ok(), `the accept answered ${accepted.status()}: ${await accepted.text()}`);
    await page.waitForTimeout(1500);
    await shot("1440-accepted");
    assert.equal(ledger().design_research_accepts, before.design_research_accepts + 1, "the accept left no design_research ledger row");
    reviewed = "one EVIDENCE item accepted through POST …/design-proposal/accept";
    check("the proposal was reviewed and one item accepted into the design, with its design_research ledger row");
  } else {
    const proposal = await api("GET", `${runsPath}/${run.run_id}/design-proposal`);
    assert(proposal.items.some((item) => item.kind === "EVIDENCE"), "the proposal has no EVIDENCE item");
    check(`no "Zkontrolovat návrh" in this build (#554 not merged); the proposal it would review has ${proposal.items.filter((i) => i.kind === "EVIDENCE").length} EVIDENCE items`);
  }

  // Nothing paid, nothing outside.
  const after = ledger();
  assert.equal(after.paid_rows, before.paid_rows, `the usage ledger gained priced rows: ${JSON.stringify(after)}`);
  assert.equal(after.spent_usd, before.spent_usd, "a study spent money");
  assert(after.rows >= before.rows, "the ledger lost rows");
  assert.deepEqual(after.routes.filter((r) => r !== "workbench-scripted"), before.routes.filter((r) => r !== "workbench-scripted"), "a model route other than the script was used");
  // The fixture's run made the model requests; a run over the same design reuses its work by
  // fingerprint (ADR 0017), so the ledger as a whole is what shows nothing was ever priced.
  assert(after.routes.includes("workbench-scripted"), "no scripted request reached the ledger");
  check(`zero paid calls: ${after.rows} ledger rows, all on workbench-scripted, ${after.paid_rows} priced (this run added ${after.rows - before.rows}; the rest reused); spend unchanged`);
  const paidStarts = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paidStarts, [], "a paid job was started");
  assert.deepEqual(external, [], "the browser asked a host outside the workbench");
  check("no research run or agent job started, and the browser reached no host but the workbench");
  assert.deepEqual(errors, [], "page errors");
  check("no page errors");
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, reviewed, errors, writes, external, ledger: { before, after: ledger() } }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
