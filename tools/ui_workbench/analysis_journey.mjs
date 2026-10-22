#!/usr/bin/env node
/**
 * Analýza in a browser (artifact-analysis ANL8): the analysis of the fixture study's newest finished run, on
 * the workbench's recorded analysis (#565, CHN7), at 1440, 1100, 768 and 390 px.
 *
 * Needs `make ui-workbench` with AIA_WEB_RESEARCH_WORKBENCH=true, `make ui-fixtures` and `make ui-research`
 * (a finished run on the `persona` fixture). Checks, at every width:
 *   - the coverage table, the milestones and Hlavní zjištění are shown, with no page overflow;
 *   - every Analýza target (module:, finding:, claim:) names exactly one element (focus takes the first);
 *   - a cited number opens its measure on Výsledky (#measure-<id>);
 *   - the stage opens on its analysis, not ~1,800 px down the pane, and nothing in the coverage table is
 *     clipped (at 390 px each row is a card);
 *   - a finished run's milestones read "Sběr dokončen" done;
 *   - a coverage finding chip keeps the analysis view (no hash that sends the workspace to Přehled);
 *   - a module stored BLOCKED reads "Potřebuje opravu", never "Hotovo".
 * Zero paid jobs: no research run, agent job, Deep Research run, analysis retry or Lead request is started.
 * `--facade`, `--out` and `--fixture` override the local URL, the evidence directory and the study.
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
const out = arg("out", join(repo, "tmp/ui-workbench/analysis-journey"));
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
const pw = await loadPlaywright();
const chromium = pw.chromium ?? pw.default.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], writes = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures[arg("fixture", "persona")];
const analysisUrl = `${base}/app/clients/${client}/research/${study}/results#analysis`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};
/** Every Analýza target on the page and how many elements carry it. */
const targetCounts = () => page.evaluate(() => {
  const counts = {};
  for (const el of document.querySelectorAll("[data-aia]")) {
    const id = el.getAttribute("data-aia");
    if (/^(module|finding|claim):/.test(id)) counts[id] = (counts[id] ?? 0) + 1;
  }
  return counts;
});

try {
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(analysisUrl, { waitUntil: "load", timeout: 180000 });
    const coverage = page.locator("[data-analysis-coverage]");
    await coverage.waitFor({ timeout: 120000 });
    await page.locator("[data-analysis-milestones]").waitFor({ timeout: 30000 });
    await page.locator("[data-key-findings]").waitFor({ timeout: 30000 });
    // The rows come after the design's research questions are read: measure only once they are there.
    await coverage.locator("tr[data-rq]").first().waitFor({ timeout: 30000 });
    await noOverflow(`analysis @${width}`);
    // Opened as Analýza, the pane starts at the analysis, once it is read (F2).
    await page.waitForFunction(() => {
      const el = document.querySelector("[data-analysis-card]");
      const r = el?.getBoundingClientRect();
      return !!r && r.top >= 0 && r.top < innerHeight / 2;
    }, null, { timeout: 30000 }).catch(() => assert.fail(`@${width}: the analysis is not in view when the stage opens`));
    // Nothing in the coverage table is cut off (F3).
    const clipped = await coverage.evaluate((el) => { const t = el.querySelector("table"); return !!t && t.getBoundingClientRect().width > el.getBoundingClientRect().width + 1; });
    assert.equal(clipped, false, `@${width}: the coverage table is clipped`);
    // Below md each cell shows its column's name; on the full table the header row says it.
    const names = await coverage.evaluate((el) => [...el.querySelectorAll("td span[aria-hidden]")].filter((n) => n.getBoundingClientRect().height > 0).length);
    if (width < 768) assert(names >= 3, `@${width}: the stacked cells show their column names`);
    else assert.equal(names, 0, `@${width}: the column names repeat beside the header row`);
    // A finished run's fieldwork reads done (F1).
    const fieldworkDone = await page.locator("[data-analysis-milestones] li").first().getAttribute("data-done");
    assert.equal(fieldworkDone, "true", `@${width}: Sběr dokončen reads čeká on a finished run`);
    await shot(`analysis-${width}`);

    const counts = await targetCounts();
    const repeated = Object.entries(counts).filter(([, n]) => n !== 1);
    assert.deepEqual(repeated, [], `@${width}: targets on more than one element`);
    assert(Object.keys(counts).some((id) => id.startsWith("module:")), `@${width}: no module target`);

    // A module reads done only when it is stored COMPLETED, and a BLOCKED one reads "Potřebuje opravu".
    const entries = await page.evaluate(() => [...document.querySelectorAll("nav[aria-label=\"Části AI analýzy\"] button")]
      .map((b) => ({ outcome: b.getAttribute("data-outcome"), text: b.textContent ?? "" })));
    assert.equal(entries.length, 8, `@${width}: the eight modules are listed`);
    for (const e of entries) {
      assert.equal(/Dokončeno/.test(e.text), e.outcome === "COMPLETED", `@${width}: "${e.text}" reads against its stored ${e.outcome}`);
      if (e.outcome === "BLOCKED") assert.match(e.text, /Potřebuje opravu/, `@${width}: a blocked module says it needs repair`);
    }
  }
  check("Analýza at 1440, 1100, 768 and 390: opens on its analysis; coverage unclipped, milestones done, Hlavní zjištění; no overflow");
  check("every module:, finding: and claim: target names exactly one element at every width");

  // Moving to Analýza within the page (Výsledky, then its stage) also opens on the analysis (F2).
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(analysisUrl.replace("#analysis", "#data"), { waitUntil: "load", timeout: 180000 });
  await page.locator("[data-key-findings]").waitFor({ state: "attached", timeout: 120000 });
  await page.evaluate(() => { location.hash = "#analysis"; });
  await page.waitForFunction(() => {
    const r = document.querySelector("[data-analysis-card]")?.getBoundingClientRect();
    return !!r && r.top >= 0 && r.top < innerHeight / 2;
  }, null, { timeout: 15000 }).catch(() => assert.fail("moving to Analýza within the page leaves the analysis out of view"));
  check("moving from Výsledky to Analýza within the page opens on the analysis");

  // A coverage finding chip keeps the analysis view and brings the finding into view (F4).
  const chip = page.locator("[data-analysis-coverage] [data-finding-chip]").first();
  await chip.waitFor({ timeout: 30000 });
  {
    await chip.click();
    const after = await page.evaluate(() => ({ hash: location.hash, tab: document.querySelector('[role=tab][aria-selected=true]')?.textContent?.trim(), focused: document.activeElement?.id ?? "" }));
    assert.equal(after.hash, "#analysis", "a finding chip leaves the hash as it was");
    assert.equal(after.tab, "AI analýza", "a finding chip keeps the analysis view");
    assert.match(after.focused, /^analysis-finding-/, "the finding is focused");
    check("a coverage finding chip keeps AI analýza and focuses the finding");
  }

  // A cited number opens its measure on Výsledky.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(analysisUrl, { waitUntil: "load", timeout: 180000 });
  await page.locator("[data-key-findings]").waitFor({ timeout: 120000 });
  const cited = page.locator("[data-key-findings] [data-cited-number] a").first();
  if (await cited.count()) {
    const href = await cited.getAttribute("href");
    assert.match(href ?? "", /^#measure-/, "a cited number links to its measure");
    await cited.click();
    await page.waitForFunction((h) => location.hash === h, href, { timeout: 15000 });
    await page.locator(`[id="${href.slice(1)}"]`).waitFor({ timeout: 30000 });
    check("a cited number opens its measure on Výsledky");
  } else {
    check("no cited number on this run's findings (nothing to open)");
  }

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/analysis\/retry$|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
