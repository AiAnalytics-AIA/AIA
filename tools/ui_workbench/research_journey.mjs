#!/usr/bin/env node
/**
 * One research run, end to end, in a browser, on the workbench (ADR 0016):
 *
 *   node tools/ui_workbench/research_journey.mjs [--fixture persona] [--out DIR]
 *
 * Needs the workbench running (`make ui-workbench`, whose worker has the
 * fictional fieldwork source) and its fixtures (`make ui-fixtures`). Signed in
 * as the workbench operator, it opens the fixture study's Run stage, where the
 * design is submitted as a Design Revision and AIA's readiness is shown; starts
 * one run; follows it on Progress until the worker has finished every step;
 * then reads Results. It asserts what a person must see:
 *
 *   * the fictional-data notice on every stage that shows the run;
 *   * a completed run: compile, preflight, fieldwork, aggregate, sociomap;
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
await startButton.click();
await page.waitForURL(/\/progress/, { timeout: 60000 });
ok("Run: started, now on Progress");

// 2. Progress: labelled fictional; polls until the worker has finished the chain.
await page.getByText(TEXT.fictional).first().waitFor({ timeout: 60000 }).catch(() => fail("Progress does not say the data are fictional"));
ok("Progress: the fictional-data notice is shown");
// The steps themselves, never only the words: with the research workbench on, the Lead pane's
// card for an earlier run of the study says "Zpráva je hotová" while this run is still going.
const CHAIN = ["compile", "preflight", "run", "aggregate", "sociomap"];
await page.waitForFunction(
  (steps) => steps.every((step) => document.querySelector(`[data-step="${step}"]`)?.getAttribute("data-status") === "SUCCEEDED"),
  CHAIN, { timeout: 180000 },
).catch(() => {});
await page.getByText(TEXT.completed).first().waitFor({ timeout: 180000 })
  .catch(async () => { await shot("2-progress-timeout"); fail("the run did not complete within 180 s (see tmp/ui-workbench/logs/worker.log)"); });
for (const step of CHAIN) {
  const status = await page.locator(`[data-step="${step}"]`).first().getAttribute("data-status", { timeout: 5000 }).catch(() => null);
  if (status !== "SUCCEEDED") fail(`step ${step} is ${status ?? "missing"}, not SUCCEEDED`);
}
ok("Progress: the run completed");
// Each step says whether a model or code did it (artifact-fieldwork FLD2) and is pointable by the
// Lead as step:<node_key>. The workbench's fieldwork is fictional code, never AI.
for (const step of ["compile", "preflight", "run", "aggregate", "sociomap"]) {
  const work = await page.locator(`[data-aia="step:${step}"] [data-step-work]`).first().getAttribute("data-step-work", { timeout: 5000 }).catch(() => null);
  if (work !== "running") fail(`step ${step} is tagged ${work ?? "nothing"}, not deterministic`);
}
ok("Progress: every step tagged deterministic and pointable");
// Kdo odpovídal (artifact-fieldwork FLD7): the data's origin code as fieldwork stored it.
const originCode = await page.locator('[data-origin-code]').first().textContent({ timeout: 5000 }).catch(() => null);
if (!originCode?.startsWith("SYNTHETIC_")) fail(`Kdo odpovídal shows origin ${originCode ?? "nothing"}, not a fictional code`);
ok(`Progress: Kdo odpovídal names the data's origin (${originCode})`);
await shot("2-progress");

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
if (toUnit.length) fail(`requests to the unit's paths: ${toUnit.join(" | ")}`);
if (bad.length) fail(`502 responses: ${bad.join(" | ")}`);
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
ok("no request reached a path of the unit");
console.log(`research journey: PASS (screenshots in ${OUT})`);
