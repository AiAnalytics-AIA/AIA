#!/usr/bin/env node
/**
 * One research run, end to end, in a browser, on the workbench (ADR 0016):
 *
 *   node tools/ui_workbench/research_journey.mjs [--fixture persona] [--out DIR]
 *
 * Needs the workbench running (`make ui-workbench`, whose worker has the
 * fictional fieldwork source; with AIA_WEB_RESEARCH_WORKBENCH=true for the Lead's card) and its
 * fixtures (`make ui-fixtures`). Safe to re-run on the same fixtures: each pass starts one more
 * fictional run and follows that one. Signed in
 * as the workbench operator, it opens the fixture study's Run stage, where the
 * design is submitted as a Design Revision and AIA's readiness is shown; starts
 * one run; follows it on Progress until the worker has finished every step;
 * then reads Results. It asserts what a person must see:
 *
 *   * the fictional-data notice on every stage that shows the run;
 *   * a completed run: compile, preflight, fieldwork, aggregate, sociomap;
 *   * the run as a card in the Lead's conversation, and on Progress at 1100, 768 and 390 px its steps,
 *     Kdo odpovídal and the card (in the Lead's drawer below 1100 px), with no page overflow;
 *   * an aggregate table and the Sociomap labelled by the Sociomap register (each map says
 *     whether its method is approved for reports; complete-study-report B4);
 *   * no page error, and no request to a path the 18.6.6 unit served (ADR 0018): the
 *     facade routes none of them to the unit, as the develop Caddyfile does not, so
 *     such a request would be a dependency on 18.6.6; and no 502 from the facade.
 *
 * Screenshots of each stage go to --out (default tmp/ui-workbench/shots/research-<time>).
 * Exits non-zero on the first thing that is not so.
 */
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "../..");
const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : fallback;
};
const FACADE = arg("facade", "http://127.0.0.1:8780");
const FIXTURE = arg("fixture", "persona");
const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const OUT = arg("out", join(REPO, "tmp/ui-workbench/shots", `research-${stamp}`));
const OPERATOR = "workbench@example.invalid";
const TEXT = {
  fictional: "Fiktivní data. Tento běh používá smyšlené respondenty",
  start: "Spustit výzkum",
  // A finished run reads by its state (lib/run-state.ts): results ready, or its report too.
  completed: /^(Výsledky jsou hotové|Zpráva je hotová)$/,
  internal: "U každé mapy je uvedeno, zda AIA schválila metodiku",
};

async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  for (const from of [REPO, join(REPO, "apps/web")]) {
    try {
      return await import(pathToFileURL(require.resolve("playwright", { paths: [from] })).href);
    } catch { /* next */ }
  }
  const root = execSync("npm root -g", { encoding: "utf8" }).trim();
  return await import(pathToFileURL(join(root, "playwright/index.mjs")).href);
}

function fail(message) {
  console.error(`research journey: FAIL ${message}`);
  process.exit(1);
}

const studies = JSON.parse(readFileSync(join(REPO, "tmp/ui-workbench/studies.json"), "utf8"));
const binding = studies[FIXTURE];
if (!binding) fail(`no workbench fixture "${FIXTURE}" (run make ui-fixtures)`);
const stage = (name) => `${FACADE}/app/clients/${encodeURIComponent(binding.client)}/research/${encodeURIComponent(binding.study)}/${name}`;

mkdirSync(OUT, { recursive: true });
const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
// The paths the 18.6.6 unit served on the product hostname (its @unit matcher until ADR
// 0018 decision 5, /classic and its document): now the web client's, never the unit's.
const UNIT_PATH = /^\/(api\/(?!v1\/)|files\/|artifacts\/|project-attachments\/|brand\/|fullsim-arena|status$|health$|classic|interface-document)/;
const toUnit = [];
const bad = [];
page.on("request", (r) => { try { if (UNIT_PATH.test(new URL(r.url()).pathname)) toUnit.push(`${r.method()} ${r.url()}`); } catch { /* not a URL */ } });
page.on("response", (r) => { if (r.status() === 502) bad.push(r.url()); });
// Every write the page sends, and the run's own answers: zero paid jobs is checked against them.
const writes = [];
page.on("request", (r) => { if (r.method() !== "GET") try { writes.push(`${r.method()} ${new URL(r.url()).pathname}`); } catch { /* not a URL */ } });
const runReads = new Map();
page.on("response", async (r) => {
  try {
    const m = /\/research\/runs\/([^/]+)$/.exec(new URL(r.url()).pathname);
    if (m && r.request().method() === "GET" && r.ok()) runReads.set(m[1], await r.json());
  } catch { /* a closed page's answer */ }
});
const shot = (name) => page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
const ok = (what) => console.log(`research journey: ok   ${what}`);

// 1. Run: the design becomes a revision; readiness is AIA's; the run starts.
await page.goto(stage("run"), { waitUntil: "load", timeout: 180000 });
const startButton = page.getByRole("button", { name: TEXT.start });
await startButton.waitFor({ timeout: 120000 });
await page.waitForFunction((label) => [...document.querySelectorAll("button")].some((b) => b.textContent?.includes(label) && !b.disabled), TEXT.start, { timeout: 60000 })
  .catch(() => fail("the Run stage's start button stayed disabled (readiness not met?)"));
ok("Run: design submitted, readiness passed");
await shot("1-run");
// The research workbench (AIA_WEB_RESEARCH_WORKBENCH=true) puts the Lead beside the stage; with the switch
// off the classic layout serves, and the Lead's card is not checked.
const workbench = (await page.locator("[data-workbench]").count()) > 0;
if (!workbench) console.log("research journey: note the classic layout serves (AIA_WEB_RESEARCH_WORKBENCH off): the Lead's card is not checked");
// Spuštění's Start is reachable at every layout (FLD8); it is pressed once, at 1440.
for (const width of [1100, 768, 390]) {
  await page.setViewportSize({ width, height: 900 });
  await startButton.scrollIntoViewIfNeeded();
  if (!(await startButton.isEnabled())) fail(`@${width}: Spuštění's start button is not reachable`);
}
await page.setViewportSize({ width: 1440, height: 1100 });
// The run this start made, from the start's own answer.
const started = page.waitForResponse((r) => r.request().method() === "POST" && /\/research\/runs$/.test(new URL(r.url()).pathname), { timeout: 60000 });
await startButton.click();
const runId = (await (await started).json().catch(() => ({}))).run_id;
if (!runId) fail("the start did not answer with its run");
await page.waitForURL(/\/progress/, { timeout: 60000 });
ok("Run: started, now on Progress");
// The run is also a card in the Lead's conversation (artifact-fieldwork FLD8, #550).
const card = page.locator(`.conv [data-card="run"][data-aia="run.${runId}"]`);
if (workbench) {
  await card.waitFor({ timeout: 60000 }).catch(() => fail(`the Lead's conversation shows no card for run ${runId}`));
  ok("Progress: the run is a card in the Lead's conversation");
}

// 2. Progress: labelled fictional; polls until the worker has finished the chain.
await page.getByText(TEXT.fictional).first().waitFor({ timeout: 60000 }).catch(() => fail("Progress does not say the data are fictional"));
ok("Progress: the fictional-data notice is shown");
// The steps themselves, never only the words: with the research workbench on, the Lead pane's
// card for an earlier run of the study says "Zpráva je hotová" while this run is still going.
// The wait ends when every step succeeded or any step ended otherwise, and a timeout is said.
const CHAIN = ["compile", "preflight", "run", "aggregate", "sociomap"];
const settled = await page.waitForFunction(
  (steps) => {
    const status = steps.map((step) => document.querySelector(`[data-step="${step}"]`)?.getAttribute("data-status"));
    return status.every((s) => s === "SUCCEEDED") || status.some((s) => s === "FAILED" || s === "CANCELLED");
  },
  CHAIN, { timeout: 180000 },
).then(() => true, () => false);
if (!settled) { await shot("2-progress-timeout"); fail("the run's steps did not settle within 180 s (see tmp/ui-workbench/logs/worker.log)"); }
for (const step of CHAIN) {
  const status = await page.locator(`[data-step="${step}"]`).first().getAttribute("data-status", { timeout: 5000 }).catch(() => null);
  if (status !== "SUCCEEDED") fail(`step ${step} is ${status ?? "missing"}, not SUCCEEDED`);
}
// This run's own state, never the Lead pane's card for another run (.conv).
const completed = await page.waitForFunction(
  (source) => [...document.querySelectorAll("body *")].some((e) => !e.closest(".conv") && new RegExp(source).test(e.textContent?.trim() ?? "")),
  TEXT.completed.source, { timeout: 180000 },
).then(() => true, () => false);
if (!completed) { await shot("2-progress-timeout"); fail("the run's steps succeeded but its state never read complete within 180 s"); }
ok("Progress: the run completed");
// Each step says whether a model or code did it (artifact-fieldwork FLD2) and is pointable by the
// Lead as step:<node_key>. The workbench's fieldwork is fictional code, never AI.
for (const step of CHAIN) {
  const work = await page.locator(`[data-aia="step:${step}"] [data-step-work]`).first().getAttribute("data-step-work", { timeout: 5000 }).catch(() => null);
  if (work !== "running") fail(`step ${step} is tagged ${work ?? "nothing"}, not deterministic`);
}
ok("Progress: every step tagged deterministic and pointable");
// Kdo odpovídal (artifact-fieldwork FLD7): pointable, with the data's origin code as fieldwork stored it.
const originCode = await page.locator('[data-aia="receipt:respondents"] [data-origin-code]').first().textContent({ timeout: 5000 }).catch(() => null);
if (!originCode?.startsWith("SYNTHETIC_")) fail(`Kdo odpovídal shows origin ${originCode ?? "nothing"}, not a fictional code`);
ok(`Progress: Kdo odpovídal names the data's origin (${originCode})`);
// Náklady (artifact-fieldwork FLD4b): the run's spend read from the API; fictional fieldwork spent nothing.
const spent = (await page.locator('[data-run-spend] [data-spend="spent"] dd').first().textContent({ timeout: 30000 }).catch(() => null))?.trim();
if (spent !== "0,00 USD") fail(`Náklady shows spent ${spent ?? "nothing"}, not 0,00 USD`);
// The ceiling this start recorded (FLD4d): a new run always records one, never "nezaznamenán".
const ceilingRow = (await page.locator('[data-run-spend] [data-spend="ceiling"] dd').first().textContent({ timeout: 30000 }).catch(() => null))?.trim();
if (!ceilingRow || ceilingRow.startsWith("nezaznamenán")) fail(`Náklady shows the run's ceiling as ${ceilingRow ?? "nothing"}`);
ok(`Progress: Náklady reads the run's spend (0,00 USD on fictional fieldwork) and its recorded ceiling (${ceilingRow})`);
await shot("2-progress");

// The same run at every layout (FLD8): split from 1100 px, the Lead a drawer from 768 and a sheet below.
// Its steps and Kdo odpovídal on the artifact, its card in the Lead's conversation, no page overflow
// with the Lead open or closed.
const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
for (const width of [1100, 768, 390]) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(`${stage("progress")}?run=${encodeURIComponent(runId)}`, { waitUntil: "load", timeout: 120000 });
  for (const step of ["compile", "preflight", "run", "aggregate", "sociomap"]) {
    const status = await page.locator(`[data-aia="step:${step}"]`).first().getAttribute("data-status", { timeout: 60000 }).catch(() => null);
    if (status !== "SUCCEEDED") fail(`@${width}: step ${step} is ${status ?? "missing"}, not SUCCEEDED`);
  }
  const origin = await page.locator('[data-aia="receipt:respondents"] [data-origin-code]').first().textContent({ timeout: 30000 }).catch(() => null);
  if (origin !== originCode) fail(`@${width}: Kdo odpovídal shows origin ${origin ?? "nothing"}, not ${originCode}`);
  if (workbench && width < 1100) {
    await page.getByRole("button", { name: /^Otevřít konverzaci s Vedoucím výzkumu/ }).click();
    await card.waitFor({ timeout: 30000 }).catch(() => fail(`@${width}: the run's card is not in the Lead's drawer`));
    const open = await overflow();
    if (open > 0) fail(`@${width}: Progress overflows the page by ${open} px with the Lead open`);
    await page.keyboard.press("Escape");
    await card.waitFor({ state: "hidden", timeout: 10000 }).catch(() => fail(`@${width}: Escape does not close the Lead's drawer`));
  } else if (workbench) {
    await card.waitFor({ timeout: 30000 }).catch(() => fail(`@${width}: the run's card is not beside the artifact`));
  }
  const closed = await overflow();
  if (closed > 0) fail(`@${width}: Progress overflows the page by ${closed} px`);
  if (width === 390) {
    // At a phone's width each value takes the card's width under its label, never a sliver beside it.
    const widths = await page.locator("dl:has([data-origin-code]) dd").evaluateAll((dds) =>
      dds.map((dd) => dd.getBoundingClientRect().width / dd.closest("dl").getBoundingClientRect().width));
    if (!widths.length || widths.some((w) => w < 0.8)) fail(`Kdo odpovídal squeezes its values beside their labels at 390 px: ${widths.map((w) => w.toFixed(2))}`);
    // The way on to Results is the input standard's touch target (F-FLD-5). It is in the run's
    // inspector, which the workbench opens from the artifact's header.
    if (workbench) await page.getByRole("button", { name: "Připravenost a pomoc" }).click();
    const toResults = await page.getByRole("link", { name: "Zobrazit výsledky", exact: true }).first().boundingBox({ timeout: 5000 }).catch(() => null);
    if (!toResults || toResults.height < 44) fail(`Progress's "Zobrazit výsledky" is ${toResults?.height ?? "missing"} px tall at 390 px, not 44`);
  }
  await shot(`2-progress-${width}`);
}
await page.setViewportSize({ width: 1440, height: 1100 });
ok(`Progress at 1100, 768 and 390: the steps, Kdo odpovídal${workbench ? ", the run's card (in the Lead's drawer below 1100)" : ""}, no overflow; at 390 the receipt stacked and Zobrazit výsledky a 44 px target`);

// 3. Results: labelled fictional, an aggregate table, the Sociomap labelled by method.
await page.goto(stage("results"), { waitUntil: "load", timeout: 120000 });
await page.getByText(TEXT.fictional).first().waitFor({ timeout: 60000 }).catch(() => fail("Results do not say the data are fictional"));
await page.getByRole("tab", { name: "Data", exact: true }).click();
await page.locator("table").first().waitFor({ state: "attached", timeout: 60000 }).catch(() => fail("Results show no aggregate table"));
await page.getByRole("tab", { name: "Sociomapy", exact: true }).click();
await page.getByText(TEXT.internal).first().waitFor({ timeout: 60000 }).catch(() => fail("the Sociomap does not say which methods are approved"));
ok("Results: fictional notice, aggregate tables, Sociomap INTERNAL_ONLY");
await shot("3-results");

await browser.close();
// Zero paid jobs, as an allowlist: the only writes are the working copy's save, the stage it is on, the
// design's submit and the one start; anything else fails by its path. The run's own API answer: SYNTHETIC_ data, cost 0.
const KNOWN = [
  /^(PUT|POST) \/api\/v1\/studies\/[^/]+\/workspace\/content$/,
  /^PUT \/api\/v1\/studies\/[^/]+\/workspace\/stage$/, // the stage a person is on, kept per visit
  /^POST \/api\/v1\/studies\/[^/]+\/design\/revisions$/,
  // Zpráva opening its draft in the report editor, on a workbench started with it on
  // (AIA_WORKBENCH_REPORT_EDITOR=true): a session for the draft, nothing paid (artifact-report RPT8d).
  /^POST \/api\/v1\/studies\/[^/]+\/research\/runs\/[^/]+\/report\/editor$/,
];
const starts = writes.filter((w) => /^POST \/api\/v1\/studies\/[^/]+\/research\/runs$/.test(w));
const unknown = writes.filter((w) => !starts.includes(w) && !KNOWN.some((k) => k.test(w)));
if (starts.length !== 1 || unknown.length) fail(`writes beyond one fictional start: ${starts.length} starts; ${unknown.join(" | ")}`);
const answered = runReads.get(runId);
const origin = answered?.steps?.find((st) => st.node_key === "run")?.data_origin;
if (answered?.actual_cost_usd !== 0 || !origin?.startsWith("SYNTHETIC_")) {
  fail(`the run's own answer: cost ${answered?.actual_cost_usd ?? "not read"}, origin ${origin ?? "not read"}`);
}
ok(`zero paid jobs: one fictional run (${origin}) at cost 0 by its own answer, no other write`);
if (toUnit.length) fail(`requests to the unit's paths: ${toUnit.join(" | ")}`);
if (bad.length) fail(`502 responses: ${bad.join(" | ")}`);
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
ok("no request reached a path of the unit");
console.log(`research journey: PASS (screenshots in ${OUT})`);
