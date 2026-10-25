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
  // Settings opens on Metodika's catalogue (fidelity F4): the cold load is measured to its cards.
  const watch = new MutationObserver(() => {
    if (!document.querySelector("#panel-methodology [data-module-card]")) return;
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
  const controls = await page.locator('[data-settings-workspace] button, [data-settings-workspace] select, [data-settings-workspace] input:not([type=checkbox]):not([type=radio])').evaluateAll((items) => items.filter((node) => node.getBoundingClientRect().width && !node.disabled).map((node) => ({ label: node.getAttribute("aria-label") ?? node.textContent?.trim().slice(0, 50) ?? "", dense: node.matches("[data-dense]"), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })));
  // 44 px everywhere but a control marked dense, which keeps WCAG 2.5.8's 24 px minimum by design:
  // a pointer's shortcut beside a keyboard path (a parameter's − / +, whose field takes ↑ ↓), a
  // segmented filter, Výpočet's "Rozbalit všechny kroky".
  for (const item of controls) {
    const least = item.dense ? 24 : 44;
    assert(item.width >= least && item.height >= least, `${name}: control below ${least}px ${JSON.stringify(item)}`);
  }
  layouts.push({ name, ...size, controls: controls.length });
}
const targets = {
  // Metodika opens on its catalogue of modules (fidelity F4).
  methodology: '#panel-methodology [data-module-card]',
  prompts: '#panel-prompts textarea[aria-label="Instrukce"]',
  deep_research: '#panel-deep_research [data-dr-setting]',
  ai: '#panel-ai [data-activity]',
  // A member's row is display: contents (no box of its own): its first cell is what shows.
  access: '#panel-access [data-member] [role="cell"]',
  studies: '#panel-studies [data-study]',
  audit: '#panel-audit input[type="search"]',
  system: '#panel-system [data-system-readiness]',
  reference: '#panel-reference input[type="search"]',
  data: '#panel-data [data-kept-records]',
};
try {
  await page.goto(`${base}/app/settings`);
  await page.waitForFunction(() => window.uxCold !== null);
  latencies.push({ name: "Cold browser document to Metodika's catalogue (no cache)", milliseconds: await page.evaluate(() => window.uxCold) });
  // The ten tabs in their three groups (settings-redesign F2), each with its lede.
  const expected = ["methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "system", "reference", "data"];
  assert.deepEqual(await page.getByRole("tablist", { name: "Oddíly nastavení" }).getByRole("tab").evaluateAll((items) => items.map((item) => item.id.replace("tab-", ""))), expected);
  for (const mode of ["first", "warm"]) for (const id of expected) {
    if (id === "methodology" && mode === "first") continue;
    await timed(`${mode} ${id} tab`, page.locator(`#tab-${id}`), targets[id]);
    assert.equal(await page.locator(`#tab-${id}`).getAttribute("aria-selected"), "true");
    assert(await page.locator(`#panel-${id} [data-tab-lede]`).isVisible(), `${id} lacks its lede`);
  }
  checks.push("All ten tabs in their three groups retain their hashes and show their lede");
  await page.locator("#tab-methodology").click();
  // The catalogue: a card for every module the API lists but the two D-13 leaves out, and the
  // read-only field-origin area (methodology-tab V1c).
  const nav = page.getByRole("navigation", { name: "Oblasti metodiky" });
  const modules = await (await page.request.get(`${base}/api/v1/methodology`, { headers: { Authorization: "Bearer workbench@example.invalid" } })).json();
  const listed = modules.filter((m) => !["sociomap_reference", "sociomapping"].includes(m.id));
  assert.equal(await nav.locator("[data-module-card]").count(), listed.length + 1);
  await timed("Open editable support module", nav.locator('[data-module-card="support"]'), '[data-methodology-versions="support"]');
  await page.locator("[data-methodology-back]").click();
  await timed("Return to object map", nav.locator('[data-module-card="sociomap"]'), '[data-methodology-versions="sociomap"]');
  // A Metodik opens straight on the editor, and the page stays where it was (no focus move); an
  // edit the person asks for -- another start -- moves the focus to the list's heading.
  let editor = page.locator("[data-methodology-editor]"); await editor.waitFor();
  const heading = () => editor.getByRole("heading", { name: "Parametry", exact: true });
  assert(!(await heading().evaluate((node) => node === document.activeElement)), "Opening Metodika moves focus into the editor unasked");
  await editor.getByLabel("Začít od metodiky z kódu", { exact: true }).selectOption("aia-sociomap-4");
  editor = page.locator("[data-methodology-editor]"); await editor.waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent === "Parametry");
  // Zahodit úpravu starts over from what is in force, where the person is: no focus move.
  await editor.getByRole("button", { name: "Zahodit úpravu", exact: true }).click();
  await editor.locator("[data-start-note]").getByText("Úprava začíná z verze v platnosti", { exact: false }).waitFor();
  assert.equal(await nav.count(), 0, "The catalogue obscures the open editor");
  // The calculation's parameters in their stages: every row names its stage, three and more of them.
  const stages = new Set(await editor.locator("[data-edit-row] label + span").evaluateAll((nodes) => nodes.map((n) => n.textContent.split(" · ")[0])));
  assert(stages.size >= 3, `Parameters name only ${stages.size} stages`);
  // A parameter steps at once; the formulas for the expert open on their first slot.
  const nMin = editor.locator('[data-field="relation.n_min"]');
  await timed("Step a parameter", editor.locator('[data-edit-row="relation.n_min"]').getByRole("button", { name: "Zvýšit: Nejmenší n páru", exact: true }), "[data-draft-chip]", "Neuloženo");
  assert.equal(await nMin.inputValue(), "11");
  await timed("Open the formulas", editor.locator("[data-edit-formulas] summary"), "[data-edit-slot]");
  await editor.locator("[data-edit-formulas] summary").click();
  // Výpočet: one stage by its tile.
  await page.getByRole("tab", { name: "Výpočet", exact: true }).click();
  await timed("Pick one stage on Výpočet", page.getByRole("group", { name: "Etapy", exact: true }).getByRole("button", { name: /^M6\s·\sTerén/ }), "#panel-methodology section[aria-labelledby^='mg-'] h3", "Terén");
  await page.getByRole("tab", { name: "Upravit", exact: true }).click();
  checks.push("Metodika opens on its catalogue of the API's modules, a module opens and returns in budget, the editor lists every parameter by stage, steps a value and opens the formulas, and Výpočet picks a stage");
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
  await timed("Server check acknowledges pending work", editor.getByRole("button", { name: "Zkontrolovat", exact: true }), '[data-methodology-editor] [data-operation] [role="status"]', "Kontroluji na serveru");
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
