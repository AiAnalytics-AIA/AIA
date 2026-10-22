#!/usr/bin/env node
/** A study from an empty brief to its internal DOCX draft, through the Lead, in a real browser, with
 * nothing paid (research-lead-workbench: the MVP's journey on the workbench, MVP master plan § goal).
 * The workbench answers the Lead by a script, its design jobs and analysis from recordings at zero
 * price, and fieldwork with fictional respondents (aia_executors.workbench):
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up --fresh
 *   make ui-fixtures
 *   node tools/ui_workbench/acceptance_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR] [--db FILE]
 * On the `empty` fixture at 1440 px, as a person would:
 *   1. Zadání: the title, the goal and what the decision is for, typed and saved;
 *   2. "Analyzuj zadání" typed to the Lead: the person's own card, approved, the job's card, its
 *      proposal reviewed on the stage and accepted ("Použít návrh");
 *   3. "Navrhni dotazník": the same for the questionnaire;
 *   4. "Spusť výzkum": the run started from the person's card, followed to its end;
 *   5. Výsledky: the internal draft downloaded as DOCX from the report card, a real Word file that
 *      carries the accepted design's research questions and says it is internal;
 *   6. nothing paid: every job ended at $0, the usage ledger holds no row with a cost, the study
 *      spent nothing; no page error, no Deep Research start.
 * Run once per fresh workbench (a second pass finds the jobs already done for the design).
 */
import assert from "node:assert/strict";
import { execFileSync, execSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/acceptance-journey"));
const db = arg("db", join(repo, "tmp/ui-workbench/aia.sqlite"));
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

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

/** What the workbench's own SQLite file says was paid: rows with a cost, and the study's spend. */
function ledger(study) {
  const script = [
    "import json, sqlite3, sys",
    "c = sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True)",
    "s = sys.argv[2]",
    "paid = c.execute('select count(*), coalesce(sum(cost_usd), 0) from ai_usage_events where study_id = ? and cost_usd > 0', (s,)).fetchone()",
    "rows = c.execute('select count(*) from ai_usage_events where study_id = ?', (s,)).fetchone()[0]",
    "unknown = c.execute('select count(*) from ai_usage_events where study_id = ? and cost_usd is null', (s,)).fetchone()[0]",
    "spent = c.execute('select spent_usd from studies where study_id = ?', (s,)).fetchone()[0]",
    "print(json.dumps({'paid_rows': paid[0], 'paid_usd': paid[1], 'rows': rows, 'unknown_cost_rows': unknown, 'spent_usd': spent}))",
  ].join("\n");
  return JSON.parse(execFileSync("python3", ["-I", "-c", script, db, study], { encoding: "utf8" }));
}

const module = await loadPlaywright();
const chromium = module.chromium ?? module.default.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], writes = [], checks = [], notes = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => {
  checks.push(name);
  console.log(`ok  ${name}`);
};

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures[arg("fixture", "empty")];
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const TITLE = "Akceptace · ranní nápoj pro dojíždějící (fiktivní)";

/** A call with the page's own token, as the person's browser makes it. */
const call = (method, path, body) =>
  page.evaluate(async ({ method, path, body }) => {
    const token = JSON.parse(sessionStorage.getItem("aia.session")).idToken;
    const r = await fetch(`/api/v1${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let json = null;
    try {
      json = await r.json();
    } catch {
      /* no body */
    }
    return { status: r.status, json };
  }, { method, path, body });
const jobs = async () => (await call("GET", `/studies/${study}/research/agent-jobs`)).json ?? [];

async function openStage(slug) {
  await page.goto(base + stagePath(slug));
  await page.locator("[data-workbench]").waitFor({ timeout: 60000 });
  await page.locator("#artbody").waitFor();
}
async function composerReady() {
  const hatch = page.getByRole("button", { name: "Vylíhnout mého Vedoucího" });
  const composer = page.getByLabel("Napište Vedoucímu výzkumu");
  await Promise.race([hatch.waitFor({ timeout: 20000 }), composer.and(page.locator(":enabled")).waitFor({ timeout: 20000 })]).catch(() => {});
  if (await hatch.isVisible()) await hatch.click();
  await composer.and(page.locator(":enabled")).waitFor({ state: "attached", timeout: 60000 });
  return composer;
}
/** Types a start command; returns the person's own card it adds. */
async function typed(phrase) {
  const composer = await composerReady();
  const before = await page.locator(".conv [data-typed]").count();
  await composer.fill(phrase);
  await composer.press("Enter");
  await page.waitForFunction((n) => document.querySelectorAll(".conv [data-typed]").length > n, before, { timeout: 30000 });
  return page.locator(".conv [data-typed]").last();
}
/** A design job from its typed card to its proposal accepted into the working copy. */
async function designJob(phrase, action) {
  const card = await typed(phrase);
  assert.match(await card.innerText(), /Váš příkaz/, `${phrase}: the card says it is the person's own command`);
  const [started] = await Promise.all([
    page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/request$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
    card.getByRole("button", { name: "Spustit úlohu" }).click(),
  ]);
  assert.ok(started.ok(), `${phrase}: the start answered ${started.status()}`);
  const worker = page.locator('.conv [data-card="worker"]').last();
  await worker.waitFor({ timeout: 30000 });
  await page.waitForFunction(() => {
    const cards = document.querySelectorAll('.conv [data-card="worker"]');
    return cards[cards.length - 1]?.getAttribute("data-card-state") === "completed";
  }, null, { timeout: 120000 }).catch(async () => {
    await shot(`${action}-not-completed`);
    throw new Error(`${phrase}: the job did not complete: ${(await worker.innerText()).replace(/\s+/g, " ")}`);
  });
  await worker.locator("[data-card-review]").click();
  const apply = page.getByRole("button", { name: "Použít návrh" });
  await apply.waitFor({ timeout: 30000 });
  await shot(`${action}-review`);
  const [accepted] = await Promise.all([
    page.waitForResponse((r) => /\/agent-jobs\/[^/]+\/accept$/.test(new URL(r.url()).pathname), { timeout: 30000 }),
    apply.click(),
  ]);
  assert.ok(accepted.ok(), `${phrase}: the accept answered ${accepted.status()} ${await accepted.text()}`);
  const job = (await jobs()).find((j) => j.action === action);
  assert.equal(job?.proposal_state, "accepted", `${phrase}: the proposal is accepted (${job?.proposal_state})`);
  check(`"${phrase}": the person's card, approved; the job's card completed; its proposal reviewed and accepted`);
}

try {
  // 1. Zadání, typed and saved.
  await openStage("brief");
  await page.locator("#brief-title input, input#brief-title").first().fill(TITLE);
  await page.locator("#brief-goal textarea").first().fill("Zjistit, zda dojíždějící koupí ranní nápoj do 60 Kč a kterou ze čtyř variant.");
  // Co rozhodnutí ovlivní is edited in place (InlineText): opened by Enter, saved when it closes.
  const decision = page.locator("#brief-decision_use");
  await decision.locator('[role="button"], button').first().focus();
  await page.keyboard.press("Enter");
  await decision.locator("textarea").first().fill("Rozhodnutí o uvedení nápoje a o jedné variantě.");
  await page.keyboard.press("Tab");
  await page.waitForFunction(() => /Uloženo/.test(document.querySelector(".arthead")?.textContent ?? document.body.innerText), null, { timeout: 30000 });
  const saved = (await call("GET", `/studies/${study}/workspace/content`)).json;
  assert.equal(saved?.content?.title, TITLE, "the title is saved in the working copy");
  await shot("1-brief");
  check("Zadání: the title, goal and decision use typed and saved");

  // 2-3. The design through the Lead's typed starts.
  await designJob("Analyzuj zadání", "analyze_brief");
  await designJob("Navrhni dotazník", "build_questionnaire");
  await shot("3-questionnaire");

  // 4. The run, from the person's own card.
  await openStage("run");
  const runCard = await typed("Spusť výzkum");
  await shot("4-run-card");
  const start = runCard.getByRole("button", { name: /Spustit/ }).first();
  await start.waitFor({ timeout: 60000 }).catch(async () => {
    await shot("4-run-card-not-startable");
    throw new Error(`the run cannot start from its card: ${(await runCard.innerText()).replace(/\s+/g, " ")}`);
  });
  const [startedRun] = await Promise.all([
    page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/request$|\/research\/runs$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 60000 }),
    start.click(),
  ]);
  assert.ok(startedRun.ok(), `the run's start answered ${startedRun.status()} ${await startedRun.text()}`);
  check("\"Spusť výzkum\": the run starts from the person's card");
  const run = page.locator('.conv [data-card="run"]').last();
  await run.waitFor({ timeout: 60000 });
  const runs = async () => (await call("GET", `/studies/${study}/research/runs`)).json?.items ?? [];
  const deadline = Date.now() + 600000;
  let latest = (await runs())[0];
  while (latest && !latest.is_terminal && Date.now() < deadline) {
    await page.waitForTimeout(2000);
    latest = (await runs())[0];
  }
  notes.push(`run ${latest?.run_id}: ${latest?.status}; steps ${(latest?.steps ?? []).map((s) => `${s.node_key}=${s.status}`).join(", ")}`);
  assert.equal(latest?.status, "COMPLETED", `the run completed (${latest?.status})`);
  check("the run completed every step: fieldwork, aggregate, sociomap, analysis, report");

  // 5. The internal draft, downloaded as DOCX from Výsledky.
  await openStage(`results?run=${latest.run_id}`);
  // The report card (CompleteReport): the internal variant in DOCX, the one place a run's report is downloaded.
  const card = page.locator("[data-complete-report]");
  await card.waitFor({ timeout: 60000 });
  const docx = card.getByRole("radio", { name: "DOCX" });
  if (await docx.count()) await docx.check();
  const download = card.getByRole("button", { name: "Stáhnout zprávu", exact: true });
  await download.waitFor({ timeout: 60000 });
  await shot("5-results");
  const [file] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), download.click()]);
  const path = join(out, file.suggestedFilename() || "report.docx");
  await file.saveAs(path);
  const bytes = readFileSync(path);
  assert.equal(bytes.subarray(0, 2).toString(), "PK", "the download is a ZIP (a Word file)");
  const text = execFileSync("python3", ["-I", "-c", [
    "import sys, zipfile, re",
    "z = zipfile.ZipFile(sys.argv[1])",
    "x = z.read('word/document.xml').decode('utf-8')",
    "print(re.sub(r'<[^>]+>', '', x.replace('</w:p>', '\\n')))",
  ].join("\n"), path], { encoding: "utf8" });
  // The draft is this run's: it carries the design's research questions as the run froze them
  // (Návrh studie) and says it is internal. The brief's title, goal and decision use are not in it
  // (the plan's finding F19): held to what the draft prints today, not to what it should.
  const words = (s) => s.replace(/\s+/g, " ").trim();
  const frozen = (await call("GET", `/studies/${study}/workspace/content`)).json?.content?.research_plan?.research_questions ?? [];
  assert.ok(frozen.length > 0, "the accepted design has research questions");
  for (const q of frozen) assert.ok(words(text).includes(words(q)), `the draft carries the research question "${q}"`);
  assert.ok(text.includes("Interní — nepředávat klientovi"), "the draft says it is internal");
  notes.push(`DOCX ${file.suggestedFilename()}: ${bytes.length} bytes`);
  check(`Výsledky: the internal draft downloads as a Word file carrying the design's research questions, marked internal (${bytes.length} bytes)`);

  // 6. Nothing paid.
  let listed = await jobs();
  const until = Date.now() + 120000;
  while (listed.some((j) => !j.is_terminal) && Date.now() < until) {
    await page.waitForTimeout(1000);
    listed = await jobs();
  }
  const unpaid = listed.filter((j) => typeof j.actual_cost_usd !== "number" || j.actual_cost_usd !== 0);
  assert.deepEqual(unpaid.map((j) => `${j.run_id} ${j.action}: ${j.actual_cost_usd}`), [], "every job's cost is a number and zero (null is unknown, never $0)");
  const spend = ledger(study);
  notes.push(`ledger: ${JSON.stringify(spend)}`);
  assert.equal(spend.paid_rows, 0, `no usage row with a cost (${spend.paid_usd} USD)`);
  assert.equal(spend.unknown_cost_rows, 0, "no usage row with an unknown cost");
  assert.equal(Number(spend.spent_usd ?? 0), 0, "the study spent nothing");
  assert.deepEqual(writes.filter((w) => /\/deep-research\/runs/.test(w.path)), [], "no Deep Research started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
  check(`nothing paid: ${listed.length} jobs at $0, ${spend.rows} usage rows with no cost, the study spent $0; no page error`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, notes, errors, writes }, null, 2));
  await browser.close();
}
for (const n of notes) console.log(`note ${n}`);
console.log(`evidence: ${out}`);
