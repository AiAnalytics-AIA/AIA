#!/usr/bin/env node
// Settings UX through the real fictional local API, with no paid model calls.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { INTERACTION_BUDGET_MS as budget, requireProductionBuild } from "./production.mjs";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const args = process.argv.slice(2);
const arg = (key, fallback) => args.includes(`--${key}`) ? args[args.indexOf(`--${key}`) + 1] : fallback;
const base = arg("facade", "http://127.0.0.1:8780");
assert(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Fictional local identity only");
requireProductionBuild(repo, base);
const out = arg("out", join(repo, "tmp/ui-workbench/contextual-settings-timing"));
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }));
  window.uxCold = null;
  const watch = new MutationObserver(() => {
    if (!document.querySelector("#panel-ai [data-activity]")) return;
    watch.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => { window.uxCold = performance.now(); }));
  });
  watch.observe(document, { subtree: true, childList: true });
});
const page = await context.newPage();
const errors = [], writes = [], latencies = [], layouts = [], checks = [];
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (request) => { if (!["GET", "HEAD", "OPTIONS"].includes(request.method()) && new URL(request.url()).pathname.startsWith("/api/")) writes.push({ method: request.method(), path: new URL(request.url()).pathname }); });
async function timed(name, control, selector, text = null) {
  await control.evaluate((node, spec) => {
    window.uxInteraction = null;
    node.addEventListener("pointerdown", () => {
      const started = performance.now();
      const ready = () => [...document.querySelectorAll(spec.selector)].some((target) => target.getBoundingClientRect().width > 0 && (!spec.text || target.textContent.includes(spec.text)));
      const finish = () => { if (!ready()) return; observer.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => { window.uxInteraction = performance.now() - started; })); };
      const observer = new MutationObserver(finish); observer.observe(document.body, { subtree: true, childList: true, attributes: true }); finish();
    }, { once: true });
  }, { selector, text });
  await control.click();
  await page.waitForFunction(() => window.uxInteraction !== null);
  const milliseconds = await page.evaluate(() => window.uxInteraction);
  latencies.push({ name, milliseconds }); assert(milliseconds < budget, `${name}: ${milliseconds.toFixed(1)}ms >= ${budget}ms`);
}
async function layout(name) {
  const size = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth }));
  assert(size.documentWidth <= size.width + 2, `${name}: horizontal overflow ${JSON.stringify(size)}`);
  const controls = await page.locator('[data-settings-workspace] button, [data-settings-workspace] select, [data-settings-workspace] input:not([type=checkbox]):not([type=radio])').evaluateAll((items) => items.filter((node) => node.getBoundingClientRect().width && !node.disabled).map((node) => ({ label: node.getAttribute("aria-label") ?? node.textContent?.trim().slice(0, 50) ?? "", dense: node.matches("[data-methodology-outline] [data-dense]"), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })));
  // 44 px everywhere but the editor's dense outline rows, which keep WCAG 2.5.8's 24 px minimum by
  // design (MethodologyVersions.tsx, data-dense).
  for (const item of controls) {
    const least = item.dense ? 24 : 44;
    assert(item.width >= least && item.height >= least, `${name}: control below ${least}px ${JSON.stringify(item)}`);
  }
  layouts.push({ name, ...size, controls: controls.length });
}
const targets = {
  // Metodika opens on the area in force (its versions); the list of areas is behind "Změnit oblast".
  methodology: '#panel-methodology [data-methodology-versions]',
  prompts: '#panel-prompts textarea[aria-label="Instrukce"]',
  deep_research: '#panel-deep_research [data-dr-setting]',
  ai: '#panel-ai [data-activity]',
  access: '#panel-access [data-member]',
  studies: '#panel-studies [data-study]',
  audit: '#panel-audit input[type="search"]',
  reference: '#panel-reference input[type="search"]',
};
try {
  await page.goto(`${base}/app/settings`);
  await page.waitForFunction(() => window.uxCold !== null);
  latencies.push({ name: "Cold browser document to AI settings content (no cache)", milliseconds: await page.evaluate(() => window.uxCold) });
  const expected = ["methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "reference"];
  assert.deepEqual(await page.getByRole("tab").evaluateAll((items) => items.map((item) => item.id.replace("tab-", ""))), expected);
  for (const mode of ["first", "warm"]) for (const id of expected) {
    if (id === "ai" && mode === "first") continue;
    await timed(`${mode} ${id} tab`, page.locator(`#tab-${id}`), targets[id]);
    assert.equal(await page.locator(`#tab-${id}`).getAttribute("aria-selected"), "true");
    assert(await page.locator(`#panel-${id} [data-tab-facts]`).isVisible(), `${id} lacks scope/ownership facts`);
  }
  checks.push("All eight purpose-grouped tabs retain their hashes and show scope/ownership facts");
  await page.locator("#tab-methodology").click();
  const choose = page.locator("#panel-methodology").getByRole("button", { name: "Změnit oblast", exact: true });
  await choose.click();
  const nav = page.getByRole("navigation", { name: "Oblasti metodiky" });
  for (const name of ["Před spuštěním", "Mapy objektů", "Čísla ve výsledcích", "Respondenti a váhy", "Populace a tvrzení"]) assert(await nav.getByRole("group", { name }).isVisible());
  // Every method module from the real API, and the read-only field-origin area (methodology-tab V1c).
  const modules = await (await page.request.get(`${base}/api/v1/methodology`, { headers: { Authorization: "Bearer workbench@example.invalid" } })).json();
  assert.equal(await nav.getByRole("button").count(), modules.length + 1);
  await timed("Open editable support module", nav.getByRole("button", { name: "Podpora a potlačení: kdy se číslo smí ukázat" }), '[data-methodology-versions="support"]');
  await choose.click();
  await timed("Return to object map", nav.getByRole("button", { name: "Sociomapa: objektová mapa" }), '[data-methodology-versions="sociomap"]');
  // An administrator opens straight on the editor, and the page stays where it was (no focus move);
  // an edit the person asks for moves focus to the editor's heading (MethodologyVersions, byPerson).
  const versions = page.locator('#panel-methodology [data-methodology-versions="sociomap"]');
  let editor = page.locator("[data-methodology-editor]"); await editor.waitFor();
  assert(!(await editor.locator("h4").evaluate((node) => node === document.activeElement)), "Opening Metodika moves focus into the editor unasked");
  // The editor's own Zrušit, in its header row before any step's content.
  await editor.getByRole("button", { name: "Zrušit", exact: true }).first().click();
  await versions.getByRole("tab", { name: "Upravit" }).click();
  editor = page.locator("[data-methodology-editor]"); await editor.waitFor();
  assert(await editor.locator("h4").evaluate((node) => node === document.activeElement), "Asking for an edit does not focus the editor's heading");
  assert.equal(await nav.count(), 0, "Expanded chooser obscures the active editor");
  // The calculation's blocks in their stages: an outline grouped by stage (was a select with optgroups).
  const outline = editor.locator("[data-methodology-outline]");
  assert(await outline.locator("[data-outline-stage]").count() >= 3, "Calculation blocks lack parent groups");
  await outline.locator('[data-edit-step-link="f3_status"]').click();
  assert(await editor.locator('[data-edit-step="f3_status"]').isVisible());
  // The block says where it sits and shows its calculation: a reading, or the formula itself.
  const block = editor.locator('[data-edit-step="f3_status"]');
  assert(await block.locator("[data-step-stage]").isVisible(), "The block does not say its stage");
  assert(await block.locator("[data-step-reading], math, .katex, [data-edit-slot]").first().isVisible(), "The block shows no calculation");
  await timed("Move to next calculation block", outline.locator('[data-edit-step-link="f3_effect_floor"]'), '[data-edit-step="f3_effect_floor"]:not([hidden])');
  checks.push("Methodology groups real API modules, closes the chooser in edit mode, and moves among calculation blocks");
  await page.screenshot({ path: join(out, "methodology-desktop.png"), animations: "disabled" });
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await layout(`methodology editor ${width} light`);
    if (width === 390) { await editor.scrollIntoViewIfNeeded(); await page.screenshot({ path: join(out, "methodology-phone.png"), animations: "disabled" }); }
  }
  await page.emulateMedia({ reducedMotion: "reduce" }); await page.evaluate(() => document.documentElement.dataset.theme = "dark");
  await layout("methodology editor 390 dark reduced motion");
  await page.screenshot({ path: join(out, "methodology-phone-dark.png"), animations: "disabled" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator("[data-methodology-editor]").waitFor();
  await page.route("**/api/v1/methodology/sociomap/check", async (route) => { const response = await route.fetch(); await new Promise((resolve) => setTimeout(resolve, 1000)); await route.fulfill({ response }); });
  await timed("Server check acknowledges pending work", editor.getByRole("button", { name: "Zkontrolovat", exact: true }), '[data-methodology-editor] [role="status"]', "Kontroluji na serveru");
  await editor.getByText("Kontrola prošla.").waitFor();
  await page.unroute("**/api/v1/methodology/sociomap/check");
  checks.push("Real server validation shows pending feedback before a delayed API response");
  assert.deepEqual(errors, []);
  assert.equal(writes.filter((request) => /agent-jobs|research\/runs|deep-research\/runs/.test(request.path)).length, 0);
  const report = { status: "PASS", checks, latencies, layouts, writes, errors, scope: "Fictional local API; validation read/check only; no paid jobs" };
  writeFileSync(join(out, "checks.json"), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ status: report.status, checks, latencies, layouts: layouts.length }, null, 2));
} catch (error) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true });
  writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(error), checks, latencies, layouts, writes, errors }, null, 2)); throw error;
} finally { await browser.close(); }
