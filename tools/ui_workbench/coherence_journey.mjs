#!/usr/bin/env node
/**
 * The product walked end to end as one researcher, on the workbench, recording what each screen
 * says (productization-coherence PC8):
 *
 *   node tools/ui_workbench/coherence_journey.mjs [--fixture persona] [--out DIR] [--facade URL]
 *
 * Needs `make ui-workbench` (the real API, worker and web on SQLite, fictional fieldwork, no model)
 * and `make ui-fixtures`. Everything is fictional and nothing costs money. It walks:
 *
 *   1. the global pages and the fixture client's six areas;
 *   2. a new study started from the client page: its Dimenze start with none chosen (PC10);
 *   3. the fixture study's Run stage, a run started or found, followed on Průběh to its results,
 *      with the stage track checked against the page (PC5), and Výsledky's three tabs;
 *   4. the design changed after that run: the Run stage shows the new revision, Výsledky keeps
 *      naming the run's own;
 *   5. the study delivered: every stage says it is closed, the design is read-only, nothing is
 *      saved, the report still downloads, nothing starts (PC1); then reopened as it was.
 *
 * For every page it keeps a full-page screenshot and the page's text, so a person (or an agent)
 * can read exactly what was on screen; `report.json` lists every check, every API response of
 * 400 or more, and every page error. Like the other journeys it fails on a request to a path the
 * 18.6.6 unit served (ADR 0018) and on a 502 from the facade. Exits non-zero when a check fails.
 * Output: --out (default tmp/ui-workbench/coherence-journey/<time>/).
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
const OUT = arg("out", join(REPO, "tmp/ui-workbench/coherence-journey", stamp));
const OPERATOR = "workbench@example.invalid";
// A finished run reads by its state (lib/run-state.ts): results ready, or its report too.
const DONE = /^(Výsledky jsou hotové|Zpráva je hotová)$/;

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

const studies = JSON.parse(readFileSync(join(REPO, "tmp/ui-workbench/studies.json"), "utf8"));
const binding = studies[FIXTURE];
if (!binding) {
  console.error(`coherence journey: no workbench fixture "${FIXTURE}" (run make ui-fixtures)`);
  process.exit(1);
}
const clientPath = `/app/clients/${encodeURIComponent(binding.client)}`;
const stage = (study, name) => `${clientPath}/research/${encodeURIComponent(study)}/${name}`;

/** The workbench API as the operator (the development identity takes the e-mail as its token). */
async function api(method, path, body) {
  const r = await fetch(`${FACADE}/api/v1${path}`, {
    method,
    headers: { Authorization: `Bearer ${OPERATOR}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

mkdirSync(OUT, { recursive: true });
const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();

const report = { started: new Date().toISOString(), facade: FACADE, fixture: FIXTURE, checks: [], pages: [], apiErrors: [], pageErrors: [], unitRequests: [], badGateway: [] };
const UNIT_PATH = /^\/(api\/(?!v1\/)|files\/|artifacts\/|project-attachments\/|brand\/|fullsim-arena|status$|health$|classic|interface-document)/;
page.on("pageerror", (e) => report.pageErrors.push(String(e)));
page.on("request", (r) => { try { if (UNIT_PATH.test(new URL(r.url()).pathname)) report.unitRequests.push(`${r.method()} ${r.url()}`); } catch { /* not a URL */ } });
page.on("response", (r) => {
  if (r.status() === 502) report.badGateway.push(r.url());
  // A study without a reused design answers its design source with 404: "nothing here" (useResource).
  if (r.status() >= 400 && r.url().includes("/api/v1/") && !(r.status() === 404 && r.url().endsWith("/design/source"))) {
    report.apiErrors.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  }
});

let failed = false;
const check = (name, ok, detail = "") => {
  report.checks.push({ name, ok: Boolean(ok), detail });
  console.log(`coherence journey: ${ok ? "ok  " : "FAIL"} ${name}${detail ? ` (${detail})` : ""}`);
  if (!ok) failed = true;
};
let shots = 0;
/** Keep what the page says: a full-page screenshot and its text, named in order. */
async function keep(name) {
  const file = `${String(++shots).padStart(2, "0")}-${name}`;
  await page.screenshot({ path: join(OUT, `${file}.png`), fullPage: true });
  writeFileSync(join(OUT, `${file}.txt`), await page.evaluate(() => document.body.innerText));
  report.pages.push({ name, file, url: page.url() });
}
async function visit(path, name, settle = 3000) {
  await page.goto(`${FACADE}${path}`, { waitUntil: "load", timeout: 180000 });
  await page.waitForTimeout(settle);
  await keep(name);
}
/** The stage track's line under one stage (StageTrack): what the header says about it. */
async function trackLine(stageName) {
  const link = page.getByRole("navigation", { name: "Fáze výzkumu" }).getByRole("link", { name: new RegExp(`^${stageName}`) });
  return (await link.first().innerText()).replace(/\s+/g, " ").trim();
}

try {
  // 1. The global pages and the client's areas: what each says, kept for reading.
  for (const [path, name] of [["/app/clients", "clients"], ["/app/intelligence", "intelligence"], ["/app/memory", "memory"], ["/app/settings", "settings"]]) await visit(path, name);
  for (const area of ["", "/research", "/simulations", "/knowledge", "/data", "/profile"]) await visit(`${clientPath}${area}`, `client${area.replace("/", "-") || "-overview"}`);
  check("every global page and client area opened", report.pageErrors.length === 0, report.pageErrors.join(" | "));

  // 2. A new study starts with no dimension chosen (PC10; the owner's report of 2026-10-18).
  await page.goto(`${FACADE}${clientPath}/research`, { waitUntil: "load" });
  await page.getByRole("button", { name: "Nový výzkum" }).first().click();
  await page.getByRole("dialog").getByRole("textbox").fill(`Coherence ${stamp}`);
  await page.getByRole("dialog").getByRole("button", { name: "Založit výzkum" }).click();
  await page.waitForURL(/\/research\/STU-[^/]+\/brief/, { timeout: 60000 });
  const fresh = page.url().match(/\/research\/(STU-[^/]+)\//)[1];
  await page.waitForTimeout(3000);
  await keep("new-study-brief");
  check("a new study's track says it chose no dimension", (await trackLine("Dimenze")).includes("Bez dimenzí"), await trackLine("Dimenze"));
  await visit(stage(fresh, "dimensions"), "new-study-dimensions"); // the persona stage's slug (lib/app-routes.ts)
  check("a new study's Dimenze shows none chosen", await page.getByText("Zatím není vybraná žádná volitelná dimenze.").isVisible());
  await api("PUT", `/studies/${fresh}/status`, { status: "CANCELLED" }); // leave the workbench as it was

  // 3. A run of the fixture study, from the Run stage to its results.
  await visit(stage(binding.study, "run"), "run-before-start", 6000);
  const startButton = page.getByRole("button", { name: "Spustit výzkum" });
  const startable = await startButton.isEnabled().catch(() => false);
  check("the Run stage offers a start or says why not", startable || (await page.getByText(/Návrh neprošel kontrolou|nespustí/).count()) > 0);
  if (startable) {
    await startButton.click();
    await page.waitForURL(/\/progress/, { timeout: 60000 });
  } else {
    await page.goto(`${FACADE}${stage(binding.study, "progress")}`, { waitUntil: "load" });
  }
  await page.getByText(DONE).first().waitFor({ timeout: 240000 })
    .catch(async () => { await keep("progress-timeout"); throw new Error("the run did not reach its results within 240 s (tmp/ui-workbench/logs/worker.log)"); });
  await page.waitForTimeout(3000); // one more read of the track's own poll
  await keep("progress-done");
  const progressLine = await trackLine("Průběh");
  check("the stage track follows the run it shows (PC5)", !/běží/.test(progressLine) && /hotov/.test(progressLine), progressLine);
  check("the stage track points at the run's results", !(await trackLine("Výsledky")).includes("Zatím nic"), await trackLine("Výsledky"));
  await visit(stage(binding.study, "results"), "results", 5000);
  for (const tab of ["Data", "Sociomapy", "Rešerše a zpráva"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.waitForTimeout(2500);
    await keep(`results-${tab.replace(/\W+/g, "-").toLowerCase()}`);
  }
  check("Výsledky say the data are fictional", (await page.getByText(/Fiktivní data/).count()) > 0);

  // 4. The design changes after the run: the Run stage shows the new revision.
  await page.goto(`${FACADE}${stage(binding.study, "brief")}`, { waitUntil: "load" });
  const goal = page.locator("textarea").first();
  await goal.waitFor({ timeout: 60000 });
  const before = await goal.inputValue();
  await goal.fill(`${before} (upraveno ${stamp})`);
  await page.waitForTimeout(3500); // the 1.8 s autosave
  await visit(stage(binding.study, "run"), "run-after-design-change", 6000);
  const revisions = [...(await page.evaluate(() => document.body.innerText)).matchAll(/Revize návrhu (\d+)/g)].map((m) => Number(m[1]));
  check("the Run stage names a newer revision than the run's", revisions.length >= 2 && Math.max(...revisions) > Math.min(...revisions), `revisions on screen: ${revisions.join(", ")}`);
  await goal.page().goto(`${FACADE}${stage(binding.study, "brief")}`, { waitUntil: "load" });
  await page.locator("textarea").first().fill(before); // the goal as it was
  await page.waitForTimeout(3500);

  // 5. The study delivered: closed on every stage, its report still within reach (PC1).
  await api("PUT", `/studies/${binding.study}/status`, { status: "DELIVERED" });
  try {
    await visit(stage(binding.study, "brief"), "delivered-brief", 4000);
    check("a delivered study says it is delivered", (await page.getByText(/Studie je předaná klientovi/).count()) > 0);
    const field = page.locator("textarea").first();
    check("a delivered study's design is read-only", await field.isDisabled());
    check("a delivered study saves nothing", (await page.getByText("Jen ke čtení").count()) > 0 && (await page.getByText("Neuloženo").count()) === 0);
    await visit(stage(binding.study, "run"), "delivered-run", 6000);
    check("a delivered study starts nothing", !(await page.getByRole("button", { name: "Spustit výzkum" }).isEnabled().catch(() => false)));
    await visit(stage(binding.study, "results"), "delivered-results", 6000);
    const download = page.getByRole("button", { name: /Stáhnout zprávu/ });
    const reportMade = (await page.getByText("Tento běh zprávu nevytváří").count()) === 0;
    check("a delivered study keeps its report downloadable", !reportMade || (await download.isEnabled()), reportMade ? "" : "this run makes no report (analysis off)");
  } finally {
    await api("PUT", `/studies/${binding.study}/status`, { status: "ACTIVE" });
  }
} catch (e) {
  check("the journey ran to its end", false, String(e?.message ?? e));
  await keep("stopped").catch(() => {});
}

await browser.close();
check("no request reached a path of the 18.6.6 unit", report.unitRequests.length === 0, report.unitRequests.join(" | "));
check("no 502 from the facade", report.badGateway.length === 0, report.badGateway.join(" | "));
check("no page error", report.pageErrors.length === 0, report.pageErrors.join(" | "));
report.finished = new Date().toISOString();
writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2));
console.log(`coherence journey: ${failed ? "FAIL" : "PASS"} (${report.checks.length} checks, ${report.pages.length} pages; ${OUT})`);
process.exit(failed ? 1 : 0);
