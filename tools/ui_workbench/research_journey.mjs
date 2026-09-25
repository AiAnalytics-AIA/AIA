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
 *   * an aggregate table and the Sociomap labelled INTERNAL_ONLY (PROGRESS D6);
 *   * no page error.
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
  completed: "Dokončeno",
  internal: "Interní: metodika Sociomapy (PROGRESS D6)",
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
const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
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
await page.getByText(TEXT.completed, { exact: true }).first().waitFor({ timeout: 180000 })
  .catch(async () => { await shot("2-progress-timeout"); fail("the run did not complete within 180 s (see tmp/ui-workbench/logs/worker.log)"); });
for (const step of ["compile", "preflight", "run", "aggregate", "sociomap"]) {
  const status = await page.locator(`[data-step="${step}"]`).first().getAttribute("data-status", { timeout: 5000 }).catch(() => null);
  if (status !== "SUCCEEDED") fail(`step ${step} is ${status ?? "missing"}, not SUCCEEDED`);
}
ok("Progress: the run completed");
await shot("2-progress");

// 3. Results: labelled fictional, an aggregate table, the Sociomap internal only.
await page.goto(stage("results"), { waitUntil: "load", timeout: 120000 });
await page.getByText(TEXT.fictional).first().waitFor({ timeout: 60000 }).catch(() => fail("Results do not say the data are fictional"));
await page.locator("table").first().waitFor({ timeout: 60000 }).catch(() => fail("Results show no aggregate table"));
await page.getByText(TEXT.internal).first().waitFor({ timeout: 60000 }).catch(() => fail("the Sociomap is not labelled INTERNAL_ONLY"));
ok("Results: fictional notice, aggregate tables, Sociomap INTERNAL_ONLY");
await shot("3-results");

await browser.close();
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
console.log(`research journey: PASS (screenshots in ${OUT})`);
