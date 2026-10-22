#!/usr/bin/env node
/** Výsledky in a real browser (plan artifact-results RES7).
 * Start the workbench with the switch on, write the fixtures, finish one run, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/research_journey.mjs        # one completed run on the persona fixture
 *   node tools/ui_workbench/results_journey.mjs [--facade http://127.0.0.1:8780] [--fixture persona] [--out DIR]
 * Local fictional identity only. At 1440, 1100, 768 and 390 px, on the completed run's Data view:
 *   - the view opened by hash is what the screen shows: the study's report card stays on Přehled and
 *     Rešerše a zpráva (hidden, never unmounted), so the data is not two screens down;
 *   - no page overflow, and nothing of the data view wider than the screen (a rated set's table
 *     fits a phone: its interval band column is left out under 640 px);
 *   - each measure card's reading runs the card's width, never squeezed beside its support chip;
 *   - the Lead's ids: every data-aia on the data view is a measure: id in the published grammar,
 *     each on exactly one element;
 *   - a measure opened by hash (#measure-<id>) is shown, focused and its detail open;
 *   - Data and Sociomapa (#maps) open scrolled to their view, not under the run's notices;
 *   - nothing but the study's open stage is written, so nothing paid starts (the journey only reads).
 */
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const fixture = arg("fixture", "persona");
const out = arg("out", join(repo, "tmp/ui-workbench/results-journey"));
mkdirSync(out, { recursive: true });
// lib/workbench-artifacts.ts ID_SOURCE, the server's ID_PATTERN.
const ID = /^[A-Za-z0-9_.\-~/:]{1,80}$/;

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
const module = await loadPlaywright();
const chromium = module.chromium ?? module.default.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const binding = fixtures[fixture];
assert(binding, `no workbench fixture "${fixture}" (run make ui-fixtures)`);
const results = `${base}/app/clients/${binding.client}/research/${binding.study}/results`;

const errors = [], writes = [], checks = [];
const check = (name) => checks.push(name);

async function open(width, hash) {
  const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 1000 } });
  await context.addInitScript(() =>
    sessionStorage.setItem(
      "aia.session",
      JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
    ),
  );
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(`${width}: ${e}`));
  page.on("request", (r) => {
    const path = new URL(r.url()).pathname;
    if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
  });
  await page.goto(`${results}#${hash}`);
  await page.locator("[data-aggregate-explorer]").first().waitFor({ state: "attached", timeout: 60000 });
  return { page, context };
}

try {
  for (const width of [1440, 1100, 768, 390]) {
    const { page, context } = await open(width, "data");
    const explorer = page.locator("[data-aggregate-explorer]");
    await explorer.waitFor({ state: "visible", timeout: 30000 });
    assert.equal(await page.getByRole("tab", { name: "Data" }).getAttribute("aria-selected"), "true", `${width}: Data is the view the hash opened`);
    // The card is there and hidden, not merely not drawn yet.
    await page.locator("[data-complete-report]").waitFor({ state: "attached", timeout: 30000 });
    assert.equal(await page.locator("[data-results-lead]").count(), 1, `${width}: the study's report card is kept apart from the views`);
    assert(await page.locator("[data-results-lead]").evaluate((el) => el.hidden), `${width}: the study's report card is hidden on Data`);
    await page.waitForFunction(() => { const t = document.querySelector("[role=tablist]")?.getBoundingClientRect(); return t && t.top >= 0 && t.top < innerHeight / 3; }, null, { timeout: 10000 })
      .catch(() => assert.fail(`${width}: Data opens scrolled to its view`));
    check(`${width}: Data opens on the data, the report card kept for Přehled and Rešerše a zpráva`);

    const layout = await page.evaluate(() => {
      const view = document.querySelector("[data-aggregate-explorer]");
      // Every measure's detail open, so its per-question table is measured too.
      for (const d of view.querySelectorAll("details")) d.open = true;
      const wide = [...view.querySelectorAll("*")]
        .filter((el) => el.getClientRects().length && el.getBoundingClientRect().right > innerWidth + 1)
        .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]}`);
      const squeezed = [...view.querySelectorAll("[data-measure-reading]")]
        .map((p) => {
          const card = p.closest("section");
          const box = card.getBoundingClientRect();
          const pad = parseFloat(getComputedStyle(card).paddingLeft) + parseFloat(getComputedStyle(card).paddingRight);
          return { id: card.id, ratio: p.getBoundingClientRect().width / (box.width - pad) };
        })
        .filter((r) => r.ratio < 0.9);
      return {
        page: document.documentElement.scrollWidth - innerWidth, wide: [...new Set(wide)].slice(0, 5), squeezed,
        sets: view.querySelectorAll("[data-object-comparison] table").length, readings: view.querySelectorAll("[data-measure-reading]").length,
      };
    });
    assert(layout.sets > 0 && layout.readings > 0, `${width}: the run has a rated set's table and readings to measure`);
    assert(layout.page <= 2, `${width}: page overflow by ${layout.page}px`);
    assert.deepEqual(layout.wide, [], `${width}: nothing of the data view is wider than the screen`);
    check(`${width}: no overflow, a rated set's table fits`);
    assert.deepEqual(layout.squeezed, [], `${width}: every reading runs its card's width`);
    check(`${width}: each reading runs its card's width`);

    const ids = await page.evaluate(() => [...document.querySelectorAll("[data-aggregate-explorer] [data-aia]")].map((el) => el.getAttribute("data-aia")));
    assert(ids.length > 0, `${width}: the data view names its measures`);
    for (const id of ids) {
      assert(id.startsWith("measure:") && ID.test(id.slice("measure:".length)), `${width}: ${id} is a measure: id in the grammar`);
      assert.equal(await page.locator(`[data-aia="${id}"]`).count(), 1, `${width}: ${id} names exactly one element`);
    }
    check(`${width}: ${ids.length} measure ids, each on one element`);
    await page.screenshot({ path: join(out, `data-${width}.png`) });

    // A measure opened by its hash, as the analysis and the comparisons link to it.
    const anchor = await page.locator("[data-aggregate-explorer] section[id^='measure-']").last().getAttribute("id");
    await page.evaluate((a) => { window.location.hash = a; }, anchor);
    const card = page.locator(`[id="${anchor}"]`);
    await page.waitForFunction((a) => document.getElementById(a)?.getAttribute("data-focused") === "true", anchor, { timeout: 10000 });
    assert(await card.locator("details").evaluate((d) => d.open), `${width}: the opened measure shows its detail`);
    assert(await card.isVisible(), `${width}: the opened measure is visible`);
    check(`${width}: #${anchor} opens its card`);
    await context.close();

    // Sociomapa is the same workspace on #maps: it opens scrolled to the map (artifact-sociomap's audit).
    const maps = await open(width, "maps");
    await maps.page.waitForFunction(() => { const t = document.querySelector("[role=tablist]")?.getBoundingClientRect(); return t && t.top >= 0 && t.top < innerHeight / 3; }, null, { timeout: 10000 })
      .catch(() => assert.fail(`${width}: Sociomapa opens scrolled to the map`));
    assert.equal(await maps.page.getByRole("tab", { name: "Sociomapy" }).getAttribute("aria-selected"), "true", `${width}: #maps opens Sociomapy`);
    check(`${width}: Sociomapa opens scrolled to the map`);
    await maps.context.close();
  }

  // The journey only reads: the one write is the study's open stage, kept as a stage opens. Any other
  // (a run, a retry, a Lead turn, a budget lift) is a defect.
  assert.deepEqual(writes.filter((w) => !(w.method === "PUT" && w.path.endsWith("/workspace/stage"))), [], "nothing but the open stage written, so nothing paid started");
  check("nothing but the open stage written, so nothing paid started");
  assert.deepEqual(errors, [], "no page error");
  check("no page error");
  for (const c of checks) console.log(`results journey: ok   ${c}`);
  writeFileSync(join(out, "report.json"), JSON.stringify({ ok: true, checks, writes }, null, 2));
  console.log(`results journey: PASS (${checks.length} checks; evidence in ${out})`);
} catch (error) {
  for (const c of checks) console.log(`results journey: ok   ${c}`);
  console.error(`results journey: FAIL ${error.message}`);
  writeFileSync(join(out, "report.json"), JSON.stringify({ ok: false, error: error.message, checks, writes, errors }, null, 2));
  process.exitCode = 1;
} finally {
  await browser.close();
}
