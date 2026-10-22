#!/usr/bin/env node
/**
 * Dimenze in a browser (artifact-dimensions DIM3, the start of DIM6): the sample size is one
 * stepper inside data-aia="sample:n", bounded by the server's limits; a press saves n plus the
 * step, a value outside the limits is refused at the field and nothing is saved.
 * At 1440, 1100, 768 and 390 px, no page overflow. Zero paid starts: the only writes are saves of
 * the working copy and of the stage the person is on. The fixture's n is put back at the end.
 *
 * After `make ui-workbench` (AIA_WEB_RESEARCH_WORKBENCH=true) and `make ui-fixtures`.
 * `--facade` and `--out` as for the other journeys; `AIA_CHROMIUM` selects the browser.
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
const out = arg("out", join(repo, "tmp/ui-workbench/dimensions-journey"));
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
const { client, study } = fixtures.persona;
const url = `${base}/app/clients/${client}/research/${study}/dimensions`;
const n = () => page.locator('[data-aia="sample:n"] [role="spinbutton"]');
const saved = () => page.waitForResponse((r) => r.url().endsWith(`/studies/${study}/workspace/content`) && r.request().method() === "PUT" && r.ok());

let restore = null;
try {
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(url);
    await n().waitFor({ timeout: 30000 });
    assert.equal(await page.locator('[data-aia="sample:n"] input[type="range"]').count(), 0, "no slider beside the stepper");
    const { w, d } = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
    assert(d <= w + 2, `${width}: page overflow ${d} > ${w}`);
    await page.screenshot({ path: join(out, `dimensions-${width}.png`), fullPage: true });
    check(`${width}: one stepper for n, no overflow`);
  }

  const before = Number((await n().getAttribute("aria-valuenow")) ?? NaN);
  const max = Number(await n().getAttribute("aria-valuemax"));
  assert(Number.isFinite(before) && before + 50 <= max, `n ${before} can step up within ${max}`);
  restore = before;
  const put = saved();
  await page.getByRole("button", { name: /^Zvýšit/ }).click();
  await put;
  assert.equal(await n().getAttribute("aria-valuenow"), String(before + 50));
  check("a press saves n + 50");

  const puts = writes.length;
  await n().fill(String(max + 1));
  await n().press("Enter");
  await page.getByRole("alert").filter({ hasText: "neuloženo" }).waitFor();
  assert.equal(await n().getAttribute("aria-invalid"), "true");
  await page.waitForTimeout(2500); // past the store's 1.8 s save
  assert.equal(writes.length, puts, "a refused n saves nothing");
  check("a value above the limits is refused at the field, nothing saved");

  const paid = writes.filter((x) => !/\/workspace\/(content|stage)$/.test(x.path));
  assert.deepEqual(paid, [], "only the working copy is written: no run, job or request");
  check("zero paid starts");
  assert.deepEqual(errors, []);
} finally {
  if (restore !== null) {
    await n().fill(String(restore));
    const put = saved();
    await n().press("Enter");
    await put;
  }
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, writes, errors }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
