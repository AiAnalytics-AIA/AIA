#!/usr/bin/env node
/**
 * The experimental Sociomapping, end to end, in a browser, on the workbench
 * (plan sociomapping-engine I5):
 *
 *   node tools/ui_workbench/sociomapping_journey.mjs [--fixture persona] [--out DIR]
 *
 * Needs `make ui-workbench` (whose API starts runs with the experimental Sociomapping and
 * whose worker has fictional fieldwork) and `make ui-fixtures`. Signed in as the workbench
 * operator, it starts one run, follows it until every step has finished, then on Results:
 *
 *   * the experimental card says what the method is before anything else, and that the data
 *     are fictional;
 *   * the map is drawn from the stored artifact: one point per placed object, a top view and
 *     a 3D view, rotation and zoom that move the points, an object's stored details;
 *   * the fit diagnostics and the limitations are shown;
 *   * the internal draft downloads as a DOCX, saved beside the screenshots.
 *
 * It fails on a page error, a console error, a failed request, any 4xx/5xx response other
 * than the 404s the study screens expect for absent optional content, or a request to a
 * path the 18.6.6 unit served. Screenshots go to --out (default
 * tmp/ui-workbench/shots/sociomapping-<time>).
 */
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
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
const OUT = arg("out", join(REPO, "tmp/ui-workbench/shots", `sociomapping-${stamp}`));
const OPERATOR = "workbench@example.invalid";
const STEPS = ["compile", "preflight", "run", "aggregate", "sociomap", "sociomapping", "sociomapping_report"];

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

const log = [];
function fail(message) {
  console.error(`sociomapping journey: FAIL ${message}`);
  writeFileSync(join(OUT, "journey.json"), JSON.stringify({ result: "FAIL", message, log }, null, 1));
  process.exit(1);
}
const ok = (what) => {
  log.push(what);
  console.log(`sociomapping journey: ok   ${what}`);
};

const studies = JSON.parse(readFileSync(join(REPO, "tmp/ui-workbench/studies.json"), "utf8"));
const binding = studies[FIXTURE];
mkdirSync(OUT, { recursive: true });
if (!binding) fail(`no workbench fixture "${FIXTURE}" (run make ui-fixtures)`);
const stage = (name) => `${FACADE}/app/clients/${encodeURIComponent(binding.client)}/research/${encodeURIComponent(binding.study)}/${name}`;

const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();
const errors = [];
const consoleErrors = [];
const failed = [];
const bad = [];
const toUnit = [];
const UNIT_PATH = /^\/(api\/(?!v1\/)|files\/|artifacts\/|project-attachments\/|brand\/|fullsim-arena|status$|health$|classic|interface-document)/;
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
// The study frame records the stage a person is on with a fire-and-forget PUT whose errors it
// ignores (components/aia/ResearchStudy.tsx); a navigation aborts it in the browser after the
// API has answered (the facade log shows 204). Listed, not failed; any other failure fails.
const stageMarkers = [];
page.on("requestfailed", (r) => {
  const line = `${r.method()} ${r.url()} ${r.failure()?.errorText ?? ""}`;
  if (r.method() === "PUT" && /\/workspace\/stage$/.test(new URL(r.url()).pathname) && /ERR_ABORTED/.test(line)) stageMarkers.push(line);
  else failed.push(line);
});
page.on("request", (r) => { try { if (UNIT_PATH.test(new URL(r.url()).pathname)) toUnit.push(`${r.method()} ${r.url()}`); } catch { /* not a URL */ } });
page.on("response", (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
const shot = (name) => page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });

// 1. Start one run over the study's design.
await page.goto(stage("run"), { waitUntil: "load", timeout: 180000 });
const start = page.getByRole("button", { name: "Spustit výzkum" });
await start.waitFor({ timeout: 120000 });
await page.waitForFunction(() => [...document.querySelectorAll("button")].some((b) => b.textContent?.includes("Spustit výzkum") && !b.disabled), null, { timeout: 60000 })
  .catch(() => fail("the start button stayed disabled"));
await start.click();
await page.waitForURL(/\/progress/, { timeout: 60000 });
ok("Run: started");

// 2. Progress until every step, the two experimental ones included, has succeeded.
await page.getByText("Dokončeno", { exact: true }).first().waitFor({ timeout: 300000 })
  .catch(async () => { await shot("2-progress-timeout"); fail("the run did not complete within 300 s (tmp/ui-workbench/logs/worker.log)"); });
for (const step of STEPS) {
  const status = await page.locator(`[data-step="${step}"]`).first().getAttribute("data-status", { timeout: 5000 }).catch(() => null);
  if (status !== "SUCCEEDED") fail(`step ${step} is ${status ?? "missing"}, not SUCCEEDED`);
}
ok(`Progress: all ${STEPS.length} steps succeeded, including sociomapping and sociomapping_report`);
await shot("1-progress");

// 3. Results: the experimental card, its map, interactions, details, fit, limitations.
await page.goto(stage("results"), { waitUntil: "load", timeout: 120000 });
const card = page.getByText("Sociomapping · experimentální metoda AIA");
await card.first().waitFor({ timeout: 60000 }).catch(() => fail("no experimental Sociomapping card on Results"));
await page.getByText("nejde o ověřenou rekonstrukci SOMECS").first().waitFor({ timeout: 30000 }).catch(() => fail("the card does not say the method is experimental"));
await page.getByText(/Fiktivní data \(SYNTHETIC_FIXTURE\)/).first().waitFor({ timeout: 30000 }).catch(() => fail("the card does not say the data are fictional"));
ok("Results: the card says experimental and fictional before the map");
const map = page.getByTestId("sociomapping-map");
await map.waitFor({ timeout: 30000 }).catch(() => fail("no map drawn"));
const points = page.locator('[data-testid^="sociomapping-point-"]');
const count = await points.count();
if (count < 3) fail(`the map draws ${count} points`);
ok(`Results: the map draws ${count} stored points`);
await map.scrollIntoViewIfNeeded();
await shot("2-results-3d");
await page.locator("section", { has: map }).last().screenshot({ path: join(OUT, "3-map-3d.png") });

const where = async () => points.first().locator("circle").getAttribute("cx");
const before = await where();
await page.getByRole("button", { name: "Otočit vpravo" }).click();
await page.getByRole("button", { name: "Otočit vpravo" }).click();
if ((await where()) === before) fail("rotation did not move the points");
const box = await map.boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
await page.mouse.down();
await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 - 40, { steps: 6 });
await page.mouse.up();
await page.getByRole("button", { name: "Přiblížit" }).click();
ok("Results: rotation by button and by drag, zoom");
await page.locator("section", { has: map }).last().screenshot({ path: join(OUT, "4-map-rotated-zoomed.png") });
await page.getByRole("button", { name: "Pohled shora" }).click();
if ((await points.first().locator("line").count()) !== 0) fail("the top view still draws height stems");
ok("Results: top view");
await page.locator("section", { has: map }).last().screenshot({ path: join(OUT, "5-map-top.png") });

await points.nth(1).click();
const details = page.getByTestId("sociomapping-details");
await details.waitFor({ timeout: 10000 }).catch(() => fail("no object details"));
const detailText = await details.textContent();
if (!/Shoda bodu/.test(detailText ?? "") || !/Vztahy k ostatním/.test(detailText ?? "")) fail("details lack fit or relations");
ok("Results: an object's stored height, fit, position and relations");
await page.getByTestId("sociomapping-accuracy").waitFor({ timeout: 10000 }).catch(() => fail("no fit diagnostics"));
const accuracy = await page.getByTestId("sociomapping-accuracy").textContent();
ok(`Results: fit diagnostics shown (overall accuracy ${accuracy})`);
await page.getByText("Otevřená otázka M3").first().waitFor({ timeout: 10000 }).catch(() => fail("limitations do not name M3"));
ok("Results: limitations with their open questions");
await page.getByText("Metoda a původ").first().click();
await shot("6-results-details-method");

// 4. The internal draft, downloaded and saved.
const download = page.getByRole("button", { name: "Stáhnout zprávu (DOCX)" });
await download.waitFor({ timeout: 30000 }).catch(() => fail("no report download button"));
const [file] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), download.click()]);
const saved = join(OUT, file.suggestedFilename());
await file.saveAs(saved);
if (!saved.endsWith("sociomapping-experimental-draft.docx")) fail(`unexpected file name ${saved}`);
ok(`Report: downloaded ${file.suggestedFilename()}`);

await browser.close();
// The study screens ask for optional content that may not exist (a 404 is "nothing here").
const unexpected = bad.filter((b) => !/^404 GET .*\/(workspace\/content|knowledge|agent-jobs|analysis|report)\b/.test(b));
writeFileSync(join(OUT, "journey.json"), JSON.stringify({ result: unexpected.length || errors.length || consoleErrors.length || failed.length || toUnit.length ? "FAIL" : "PASS", log, http_errors: bad, console_errors: consoleErrors, failed_requests: failed, aborted_stage_markers: stageMarkers, page_errors: errors, unit_requests: toUnit, report: saved }, null, 1));
if (toUnit.length) fail(`requests to the unit's paths: ${toUnit.join(" | ")}`);
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
if (failed.length) fail(`failed requests: ${failed.join(" | ")}`);
if (unexpected.length) fail(`unexpected HTTP errors: ${unexpected.join(" | ")}`);
if (consoleErrors.length) fail(`console errors: ${consoleErrors.join(" | ")}`);
ok(`no page error, console error, failed request or unexpected HTTP error (${bad.length} expected 404s; ${stageMarkers.length} stage markers aborted by navigation)`);
console.log(`sociomapping journey: PASS (screenshots, report and journey.json in ${OUT})`);
