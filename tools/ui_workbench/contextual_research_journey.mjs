#!/usr/bin/env node
// Contextual assistance against AIA's real local API; fictional fixtures, disabled model runtime.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const args = process.argv.slice(2);
const arg = (key, fallback) => args.includes(`--${key}`) ? args[args.indexOf(`--${key}`) + 1] : fallback;
const base = arg("facade", "http://127.0.0.1:8780");
assert(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Fictional local identity only");
// The 400 ms budgets are measured on a production build: `next dev` compiles on demand and runs
// dev-only checks, so on it a timed interaction measures the dev server (contextual journeys, 2026-10-22).
if (!existsSync(join(repo, "tmp/ui-workbench/production"))) {
  console.error("This journey times interactions; run it on a production build: python3 tools/ui_workbench/workbench.py down && python3 tools/ui_workbench/workbench.py up --production");
  process.exit(2);
}
const out = arg("out", join(repo, "tmp/ui-workbench/contextual-research")); mkdirSync(out, { recursive: true });
const fixture = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8")).planned;
const stage = (name) => `${base}/app/clients/${fixture.client}/research/${fixture.study}/${name}`;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }));
  window.uxFirstContent = null;
  const watch = new MutationObserver(() => {
    if (!document.querySelector("[data-contextual-assistance]") || !document.querySelector("#plan-understanding [role=button], #plan-understanding button:not([disabled])")) return;
    watch.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => { window.uxFirstContent = performance.now(); }));
  });
  watch.observe(document, { subtree: true, childList: true });
});
const page = await context.newPage();
const errors = [], starts = [], latencies = [], layouts = [], checks = [], network = [];
page.on("pageerror", (error) => errors.push(String(error)));
page.on("requestfinished", (request) => network.push({ path: new URL(request.url()).pathname, type: request.resourceType(), timing: request.timing() }));
page.on("request", (request) => { if (request.method() === "POST" && /\/research\/agent-jobs$/.test(new URL(request.url()).pathname)) starts.push(request.postDataJSON()); });
const budget = 400;
async function interaction(name, control, target, expected = {}) {
  await control.evaluate((node, spec) => {
    window.uxInteraction = null;
    node.addEventListener("pointerdown", () => {
      const start = performance.now();
      const ready = () => {
        const element = document.querySelector(spec.target);
        if (spec.absent) return !element || !element.getBoundingClientRect().width;
        if (!element || !element.getBoundingClientRect().width) return false;
        if (spec.text && !element.textContent.includes(spec.text)) return false;
        if (spec.value && element.value !== spec.value) return false;
        return true;
      };
      const finish = () => {
        if (!ready()) return;
        watch.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => { window.uxInteraction = performance.now() - start; }));
      };
      const watch = new MutationObserver(finish); watch.observe(document.body, { subtree: true, childList: true, attributes: true }); finish();
    }, { once: true });
  }, { target, ...expected });
  await control.click(); await page.waitForFunction(() => window.uxInteraction !== null);
  const milliseconds = await page.evaluate(() => window.uxInteraction);
  latencies.push({ name, milliseconds }); assert(milliseconds < budget, `${name}: ${milliseconds.toFixed(1)}ms >= ${budget}ms`);
}
async function layout(name) {
  const box = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth }));
  assert(box.content <= box.width + 2, `${name}: page overflow ${JSON.stringify(box)}`);
  const targets = await page.locator("[data-contextual-assistance] button, [data-assistance-panel] button, dialog[open] button").evaluateAll((nodes) => nodes.filter((node) => node.getBoundingClientRect().width).map((node) => ({ text: node.textContent.trim(), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })));
  for (const target of targets) assert(target.height >= 44 && target.width >= 44, `${name}: target smaller than 44px ${JSON.stringify(target)}`);
  layouts.push({ name, ...box, targets });
}
try {
  await page.goto(stage("plan")); await page.locator("[data-contextual-assistance]").waitFor();
  await page.waitForFunction(() => window.uxFirstContent !== null);
  const cold = await page.evaluate(() => window.uxFirstContent);
  latencies.push({ name: "Fresh browser document to proposal editor and contextual help (no browser cache)", milliseconds: cold });
  assert(cold < budget, `Cold workspace: ${cold.toFixed(1)}ms >= ${budget}ms`);
  assert(await page.locator("header [data-contextual-assistance]").isVisible());
  assert.equal(await page.locator("[data-contextual-assistance] [data-ai-action]").count(), 3);
  await interaction("Open and prefill contextual question", page.getByRole("button", { name: /Které výzkumné otázky/ }), '[data-assistance-panel] textarea');
  // Field's accessible name comes from its label; select it semantically when reading.
  const question = page.getByRole("textbox", { name: "Co chcete zjistit?" });
  await question.fill("Unfinished contextual question");
  assert.equal(starts.length, 0, "Suggestion or typing started a paid job");
  await page.keyboard.press("Escape");
  assert(await page.getByRole("button", { name: /Které výzkumné otázky/ }).evaluate((node) => node === document.activeElement));
  await interaction("Reopen typed draft", page.getByRole("button", { name: "Zeptat se na návrh", exact: true }), "[data-assistance-panel]");
  assert.equal(await question.inputValue(), "Unfinished contextual question");
  await layout("desktop light panel"); await page.screenshot({ path: join(out, "desktop-panel.png"), animations: "disabled" });
  await page.keyboard.press("Escape");
  await interaction("First navigation to usable questionnaire controls", page.locator(`a[href="${new URL(stage("questionnaire")).pathname}"]`).first(), '[aria-labelledby="q-choose"] button, [aria-labelledby="q-upload"] button, [aria-labelledby="q-ai"] button');
  await interaction("Open draft on another stage", page.getByRole("button", { name: "Zeptat se na návrh", exact: true }), "[data-assistance-panel]");
  assert.equal(await question.inputValue(), "Unfinished contextual question");
  checks.push("Contextual prefill never submits; closing and stage navigation preserve drafts and return focus");
  for (const width of [768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const modal = page.getByRole("dialog", { name: "Pomoc s návrhem" }); await modal.waitFor();
    assert(await modal.evaluate((node) => node.matches(":modal")), "Mobile panel is not a native modal");
    for (let i = 0; i < 12; i++) { await page.keyboard.press(i % 2 ? "Shift+Tab" : "Tab"); assert(await modal.evaluate((node) => node.contains(document.activeElement)), "Focus escaped modal"); }
    await layout(`mobile ${width} light`); await page.screenshot({ path: join(out, `panel-${width}.png`), animations: "disabled" });
    await page.keyboard.press("Escape"); assert.equal(await page.getByRole("dialog").count(), 0);
    await interaction(`Open mobile panel ${width}`, page.getByRole("button", { name: "Zeptat se na návrh", exact: true }), "dialog[open]");
    assert.equal(await question.inputValue(), "Unfinished contextual question");
  }
  await page.emulateMedia({ reducedMotion: "reduce" }); await page.evaluate(() => document.documentElement.dataset.theme = "dark");
  await layout("phone dark reduced motion"); await page.screenshot({ path: join(out, "phone-dark.png"), animations: "disabled" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  // matchMedia replaces the native mobile dialog with the desktop aside. Arm
  // the timing listener only after that replacement, on the actual invoker.
  await page.locator('[data-assistance-panel]').waitFor();
  // Delay the actual API response to verify prompt pending feedback, without inventing a response.
  await page.route("**/research/agent-jobs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch(); await new Promise((resolve) => setTimeout(resolve, 1200)); await route.fulfill({ response });
  });
  await interaction("Explicit question submission acknowledges pending API work", page.getByRole("button", { name: "Odeslat otázku" }), '[data-assistance-panel] [role="status"]');
  await page.locator('[data-assistance-panel] [role="alert"]').first().waitFor({ timeout: 30000 });
  assert.equal(starts.length, 1); assert.equal(starts[0].action, "design_copilot"); assert.equal(starts[0].instruction, "Unfinished contextual question");
  assert.equal(await question.inputValue(), "Unfinished contextual question");
  await page.getByRole("button", { name: "Obnovit stav", exact: true }).click();
  assert.equal(starts.length, 1, "Refreshing created another job");
  checks.push("Real local API receives one explicit request; disabled runtime/refusal remains visible; refresh does not resubmit");
  assert.equal(errors.length, 0, errors.join("\n"));
  const report = { status: "PASS", checks, latencies, layouts, starts, errors, scope: "Fictional local identity and disabled provider runtime; real API, no live model calls" };
  writeFileSync(join(out, "checks.json"), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ status: "PASS", checks, latencies, layouts: layouts.length }, null, 2));
} catch (error) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true });
  writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(error), checks, latencies, layouts, starts, errors, network }, null, 2)); throw error;
} finally { await browser.close(); }
