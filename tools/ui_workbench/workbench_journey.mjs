#!/usr/bin/env node
/** The research workbench in a real browser (plan research-lead-workbench chunk 12, ADR 0026).
 * Start the workbench with the switch on, write the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/workbench_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. It checks the workbench at 1440, 1280, 1100, 1099, 768 and 390 px
 * (the split, the side drawer and the sheet, research-lead-workbench 26b-26c): no page overflow,
 * nothing remounted across 1100 or 768 px, the Lead opened from the launcher and closed by Escape, the eleven stages in six phases, the separator by
 * keyboard, the focus modes, the stage navigation (Výsledky's views by hash), Návrh's research
 * questions with their coverage at 1440, 1100, 768 and 390 px, and that nothing
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
const out = arg("out", join(repo, "tmp/ui-workbench/workbench-journey"));
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
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};

try {
  await page.goto(base + stagePath("brief"));
  const wb = page.locator("[data-workbench]");
  await wb.waitFor({ timeout: 30000 });
  check("the workbench is the study screen at 1440");

  const stages = page.locator("nav[aria-label='Kroky studie'] .nav__stage");
  assert.equal(await stages.count(), 11, "eleven stages");
  assert.equal(await page.locator("nav[aria-label='Kroky studie'] [role=group]").count(), 6, "six phases");
  assert.equal((await page.locator(".nav__stage.is-current").innerText()).split("\n")[0], "Zadání");
  check("eleven stages in six phases, Zadání current");

  await page.locator(".conv").waitFor();
  assert(await page.locator(".art .arthead__title").innerText() === "Zadání");
  await noOverflow("brief @1440");
  await shot("1440-brief");

  // The separator: keyboard moves it 2 % within 28-62 %; Home goes back to 40 %.
  const sep = page.getByRole("separator", { name: "Změnit poměr konverzace a artefaktu" });
  await sep.focus();
  const now = async () => Number(await sep.getAttribute("aria-valuenow"));
  const start = await now();
  await page.keyboard.press("ArrowRight");
  assert.equal(await now(), Math.min(62, start + 2));
  for (let i = 0; i < 30; i++) await page.keyboard.press("ArrowLeft");
  assert.equal(await now(), 28);
  await page.keyboard.press("Home");
  assert.equal(await now(), 40);
  check("separator: arrows by 2 %, bounded at 28 %, Home back to 40 %");

  // Focus modes: the artifact takes the width (the conversation a rail), then the conversation 68 %.
  await page.getByRole("button", { name: "Soustředit se na artefakt" }).click();
  await page.locator(".split__rail").waitFor();
  assert.equal(await page.locator(".split__left").isVisible(), false, "the conversation is hidden in artifact focus");
  await shot("1440-artifact-focus");
  await page.getByRole("button", { name: "Zpět na 40 / 60" }).first().click();
  await page.locator(".split__left").waitFor({ state: "visible" });
  await page.getByRole("button", { name: "Soustředit se na konverzaci" }).click();
  const leftShare = await page.evaluate(() => document.querySelector(".split__left").getBoundingClientRect().width / document.querySelector(".split").getBoundingClientRect().width);
  assert(Math.abs(leftShare - 0.68) < 0.02, `conversation focus is 68 %: ${leftShare}`);
  await page.keyboard.press("Alt+Shift+N");
  await page.locator(".split__handle").waitFor();
  assert.equal(await now(), 40, "focus modes never changed the width chosen");
  check("focus modes: rail, 68 %, back to the width chosen");

  // The navigator opens each design stage on its own route.
  for (const [label, slug] of [["Návrh", "plan"], ["Dotazník", "questionnaire"], ["Cíl. skupina", "audience"], ["Dimenze", "dimensions"]]) {
    await page.locator(".nav__stage", { hasText: label }).click();
    await page.waitForURL(`**${stagePath(slug)}`);
    await page.locator(".nav__stage.is-current", { hasText: label }).waitFor();
    await page.locator("[data-workbench]").waitFor();
    await noOverflow(`${slug} @1440`);
    await shot(`1440-${slug}`);
  }
  check("navigator opens Návrh, Dotazník, Cílová skupina and Dimenze on their routes");

  // Vzorek is a read-only view over Dimenze and Kontrola, on Dimenze's route.
  await page.locator(".nav__stage", { hasText: "Vzorek" }).click();
  await page.waitForFunction(() => location.hash === "#sample");
  await page.locator("[data-sample-view]").waitFor();
  await shot("1440-sample");
  await page.locator(".nav__stage", { hasText: "Dimenze" }).click();
  await page.locator(".nav__stage.is-current", { hasText: "Dimenze" }).waitFor();
  assert.equal(await page.locator("[data-sample-view]").count(), 0, "back on Dimenze, not Vzorek");
  check("Vzorek shows the sample read only, and Dimenze is one click back");

  // Výsledky's views are the hash ResultsWorkspace reads.
  await page.locator(".nav__stage", { hasText: "Sociomapa" }).click();
  await page.waitForURL(`**${stagePath("results")}#maps`);
  await page.locator(".nav__stage.is-current", { hasText: "Sociomapa" }).waitFor();
  await page.locator(".nav__stage", { hasText: "Zpráva" }).click();
  await page.waitForFunction(() => location.hash === "#report");
  await page.locator(".nav__stage.is-current", { hasText: "Zpráva" }).waitFor();
  await shot("1440-report");
  check("Sociomapa and Zpráva open Výsledky's views by hash");

  // Narrower: the split down to 1100 px, the side drawer from 768, the sheet below (26b, D21).
  const layoutIs = async (want) => assert.equal(await page.locator("[data-workbench]").getAttribute("data-layout"), want);
  for (const [width, want] of [[1280, "split"], [1100, "split"], [1099, "drawer"], [768, "drawer"], [390, "sheet"]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    await page.locator("[data-workbench]").waitFor();
    await layoutIs(want);
    await noOverflow(`questionnaire @${width}`);
    await shot(`${width}-questionnaire`);
  }
  check("the workbench at 1280 and 1100 (split), 1099 and 768 (drawer), 390 (sheet), no overflow");

  // A resize across 1100 px remounts nothing: the stage's and the conversation's own DOM nodes,
  // tagged before, are the same nodes after crossing both ways (a remount makes new ones).
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + stagePath("questionnaire"));
  await page.locator(".wb-stage > div").first().waitFor();
  await page.locator(".conv").waitFor({ state: "attached" });
  await page.evaluate(() => {
    document.querySelector(".wb-stage > div:not([hidden])").dataset.kept = "stage";
    document.querySelector(".conv").dataset.kept = "conversation";
  });
  await page.setViewportSize({ width: 1024, height: 900 });
  await layoutIs("drawer");
  await page.setViewportSize({ width: 390, height: 900 });
  await layoutIs("sheet");
  await page.setViewportSize({ width: 1440, height: 900 });
  await layoutIs("split");
  assert.equal(await page.locator('[data-kept="stage"]').count(), 1, "the stage's screen was not remounted");
  assert.equal(await page.locator('[data-kept="conversation"]').count(), 1, "the conversation was not remounted");
  check("crossing 1100 and 768 px both ways remounts neither the stage nor the conversation");

  // Below 1100 px the launcher opens the Lead as a modal dialog; Escape closes it, back to the launcher.
  for (const width of [1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const launcher = page.locator("[data-lead-launcher]");
    await launcher.click();
    const dialog = page.getByRole("dialog", { name: "Vedoucí výzkumu" });
    await dialog.waitFor();
    await noOverflow(`Lead open @${width}`);
    await shot(`${width}-lead-open`);
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await page.evaluate(() => document.activeElement?.hasAttribute("data-lead-launcher")), true, `focus back on the launcher @${width}`);
  }
  check("the launcher opens the Lead at 1024 and 390; Escape closes it to the launcher");

  // Návrh: each research question with its coverage (artifact-design DSN2), at every width, in the
  // workbench at each. Reading it is a GET.
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("plan"));
    const coverage = page.getByRole("region", { name: "Výzkumné otázky a jejich pokrytí" });
    await coverage.waitFor({ timeout: 30000 });
    await coverage.getByText(/Podle revize návrhu|Návrh zatím nemá revizi|nedá sestavit/).first().waitFor({ timeout: 30000 });
    await noOverflow(`plan @${width}`);
    await coverage.screenshot({ path: join(out, `${width}-plan-coverage.png`) });
  }
  check("Návrh shows its research questions' coverage at 1440, 1100, 768 and 390, no overflow");

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
