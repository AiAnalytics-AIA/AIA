#!/usr/bin/env node
/**
 * The Dock rail in a browser (prototype-build PBA1, PBA2): on the local workbench, after
 * `make ui-workbench` + `make ui-fixtures`.
 *   node tools/ui_workbench/rail_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 *
 * At 1440 and 1024 px, on a top-level page and in a study: the rail is 64 px at rest and the page
 * starts after it; a pointer on it opens it to 240 px over the page; keyboard focus opens it, with
 * every item's words visible; focus leaving closes it; under reduced motion it opens with no
 * transition. Můj Vedoucí is an item of its own on every page. At 768 and 390 px the rail is the top
 * bar with its menu. No page overflows. Local fictional identity only; nothing but a stage's own
 * last-stage record is written.
 */
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
};
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/rail-journey"));
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
const session = () =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  );

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const client = fixtures.persona.client;
const pages = [
  ["clients", "/app/clients"],
  ["client", `/app/clients/${client}`],
  ["lead", "/app/lead"],
  ["stage", `/app/clients/${client}/research/${fixtures.persona.study}/brief`],
];
const checks = [];
const ok = (line) => {
  checks.push(line);
  console.log(`ok  ${line}`);
};

/** How wide the rail shows: the right edge of its unclipped part, read from the hit test. */
const shown = (page) =>
  page.evaluate(() => {
    const rail = document.querySelector("[data-rail]");
    if (!rail) return null;
    const box = rail.getBoundingClientRect();
    let edge = 0;
    for (let x = 1; x < box.width; x += 4) if (rail.contains(document.elementFromPoint(x, Math.round(innerHeight / 2)))) edge = x;
    return edge;
  });
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - innerWidth);

async function journey(reduced) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: reduced ? "reduce" : "no-preference" });
  await context.addInitScript(session);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const writes = [];
  page.on("request", (r) => {
    // Opening a stage records it as the study's last stage (PUT …/workspace/stage): the page's own
    // write, not the rail's.
    const p = new URL(r.url()).pathname;
    if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !p.startsWith("/_next/") && !p.endsWith("/workspace/stage")) writes.push(r.url());
  });
  for (const width of reduced ? [1440] : [1440, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [name, path] of pages) {
      await page.goto(base + path);
      await page.locator("h1").first().waitFor();
      await page.waitForLoadState("networkidle");
      await page.mouse.move(width - 10, 450);
      await page.waitForTimeout(reduced ? 50 : 900);
      const rest = await shown(page);
      assert(rest !== null && rest >= 56 && rest <= 64, `${name} @${width}: the rail at rest shows ${rest} px, not 64`);
      const main = await page.locator("#aia-main-content").boundingBox();
      assert(main && main.x >= 63, `${name} @${width}: the page starts under the rail (${main?.x})`);
      assert((await overflow(page)) <= 2, `${name} @${width}: page overflow`);
      const lead = page.getByRole("navigation", { name: "Hlavní navigace" }).locator("[data-rail-lead]");
      assert.equal(await lead.count(), 1, `${name}: Můj Vedoucí is not on the rail`);
      // A pointer on the rail opens it over the page.
      await page.mouse.move(32, 300);
      await page.waitForTimeout(reduced ? 50 : 900);
      const hover = await shown(page);
      assert(hover >= 230, `${name} @${width}: hovered, the rail shows ${hover} px, not 240`);
      const after = await page.locator("#aia-main-content").boundingBox();
      assert.equal(Math.round(after.x), Math.round(main.x), `${name} @${width}: opening the rail moved the page`);
      if (name === "clients") await page.screenshot({ path: join(out, `${reduced ? "reduced-" : ""}open-${width}.png`) });
      await page.mouse.move(width - 10, 450);
      await page.waitForTimeout(reduced ? 50 : 1200);
      assert((await shown(page)) <= 64, `${name} @${width}: the pointer left and the rail stayed open`);
      // Keyboard: focus opens it, every item's words are visible, and focus leaving closes it.
      await page.getByRole("link", { name: "Klienti", exact: true }).first().focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Shift+Tab");
      await page.waitForTimeout(reduced ? 50 : 900);
      assert((await shown(page)) >= 230, `${name} @${width}: focused, the rail did not open`);
      const labels = await page.locator("[data-rail] .dock__label").evaluateAll((els) => els.map((e) => [e.textContent, getComputedStyle(e).opacity]));
      assert(labels.length >= 5 && labels.every(([, o]) => Number(o) > 0.9), `${name} @${width}: a label is not visible while focused ${JSON.stringify(labels)}`);
      await page.locator("#aia-main-content").focus();
      await page.waitForTimeout(reduced ? 50 : 1200);
      assert((await shown(page)) <= 64, `${name} @${width}: focus left and the rail stayed open`);
      if (reduced) {
        const transition = await page.locator("[data-rail]").evaluate((e) => getComputedStyle(e).transitionDuration);
        assert(transition.split(",").every((d) => Number.parseFloat(d) === 0), `reduced motion still animates the rail (${transition})`);
      }
      if (!reduced) await page.screenshot({ path: join(out, `${name}-${width}.png`), fullPage: width === 1440 && name !== "stage" });
    }
    ok(`${reduced ? "reduced motion, " : ""}${width} px: 64 px at rest, 240 px on hover and on focus, over the page; Můj Vedoucí on every page; no overflow`);
  }
  if (!reduced) {
    for (const width of [768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const [name, path] of pages) {
        await page.goto(base + path);
        await page.locator("h1").first().waitFor();
        await page.waitForLoadState("networkidle");
        assert((await overflow(page)) <= 2, `${name} @${width}: page overflow`);
        const toggle = page.locator("[data-rail] .dock__bar button");
        await toggle.click();
        await page.getByRole("navigation", { name: "Hlavní navigace" }).getByRole("link", { name: "Projektová paměť" }).waitFor();
        assert.equal(await page.getByRole("navigation", { name: "Hlavní navigace" }).locator("[data-rail-lead]").isVisible(), true, `${name} @${width}: Můj Vedoucí not in the menu`);
        await page.screenshot({ path: join(out, `${name}-${width}-menu.png`) });
        await toggle.click();
      }
      ok(`${width} px: the top bar's menu holds the places and Můj Vedoucí; no overflow`);
    }
  }
  assert.deepEqual(errors, [], "page errors");
  assert.deepEqual(writes, [], "the journey wrote");
  await context.close();
}

await journey(false);
await journey(true);
ok("nothing written, no page error");
writeFileSync(join(out, "report.json"), JSON.stringify({ checks }, null, 2));
await browser.close();
console.log(`rail journey: PASS (evidence in ${out})`);
