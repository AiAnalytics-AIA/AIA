#!/usr/bin/env node
/** Dotazník in a real browser (plan artifact-questionnaire, QST8 and QST9's journey).
 * Start the workbench with the switch on, write the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/questionnaire_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. At 1440 and 1100 px (the workbench) and 768 and 390 px (the
 * classic layout): Dotazník's Závislosti lists the tracked set's readers with Sociomapa, keeps the
 * open question out of Analýza, jumps to the set's card, and the page does not overflow; nothing
 * paid starts: no research run, agent job, Deep Research run or Lead request approval.
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
const out = arg("out", join(repo, "tmp/ui-workbench/questionnaire-journey"));
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
const errors = [], writes = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => checks.push(name);


const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.questionnaire;
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};

try {
  // The workbench serves every width since research-lead-workbench 26b: a split from 1100 px, the
  // Lead in a drawer or a sheet below it.
  for (const [width, workbench] of [[1440, true], [1100, true], [768, true], [390, true]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    const deps = page.getByRole("region", { name: "Závislosti" });
    await deps.waitFor({ timeout: 30000 });
    assert.equal(await page.locator("[data-workbench]").count(), workbench ? 1 : 0, `workbench at ${width}: ${workbench}`);

    const set = deps.locator("li", { has: page.getByRole("link", { name: /^Sada 1 / }) });
    assert.deepEqual(await set.getByRole("link").allInnerTexts(), ["Sada 1 Sledovaná sada — varianty", "Sběr dat", "Výsledky", "Sociomapa", "Analýza", "Zpráva"]);
    assert.match(await set.getByRole("link", { name: "Sociomapa" }).getAttribute("href"), /\/results#maps$/);
    const open = deps.locator("li", { has: page.getByRole("link", { name: /^Q4 / }) });
    assert.equal(await open.getByRole("link", { name: "Analýza" }).count(), 0, "an open question feeds no analysis");
    await open.getByText(/data, ne připuštěná evidence/).waitFor();
    await deps.getByText("3 uzavřené otázky (Q1, Q2, Q3)").waitFor();
    await deps.scrollIntoViewIfNeeded();
    await noOverflow(`questionnaire @${width}`);
    await shot(`${width}-dependencies`);
    await deps.screenshot({ path: join(out, `${width}-dependencies-section.png`) });

    await set.getByRole("link", { name: /^Sada 1 / }).click();
    await page.waitForFunction(() => location.hash === "#qset_sec_wb_set");
    // The set's name stays readable beside its badge, count and Smazat (the browser audit, QF-3).
    const name = await page.locator("#qset_sec_wb_set").getByRole("textbox", { name: "Název sady" }).boundingBox();
    assert(name && name.width >= 160, `the set's name at ${width}: ${Math.round(name?.width ?? 0)} px wide`);
    check(`${width}: Závislosti lists the set's readers, the open question apart, no overflow`);
  }

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
