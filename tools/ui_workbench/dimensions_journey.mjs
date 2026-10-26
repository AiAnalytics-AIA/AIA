#!/usr/bin/env node
/**
 * Dimenze in a browser (artifact-dimensions DIM3, the start of DIM6): the sample size is one
 * stepper inside data-aia="sample:n", bounded by the server's limits; a press saves n plus the
 * step, a value outside the limits is refused at the field and nothing is saved.
 * A chosen dimension is removed from the selection itself by keyboard (each remove at least 24 px,
 * focus kept in the selection) and put back by Vrátit (DIM-F5, DIM-F7, DIM-F10). The client's own dimensions (DIM4) are read and lead to "Populace běhu". Inside the workbench
 * "Další" goes on to Vzorek, the navigator's next stage (DIM-F4). The search finds a name typed without
 * diacritics (DIM-F13), and a request the catalogue already names is refused at the field (DIM-F14).
 * At 1440, 1100, 768 and 390 px, no page overflow. Zero paid starts: the only writes are saves of
 * the working copy and of the stage the person is on. The fixture's n is put back at the end; "Další"
 * leaves its Dimenze marked done (persona_mode calibrated): `make ui-fixtures` writes it afresh.
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
// A catalogue card is named by its label and source ("<label> Systém · …"), never by a prefix of another's.
const cardOf = (label) => page.getByRole("button", { name: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")} (Systém|Znalosti klienta)`) }).first();
const saved = () => page.waitForResponse((r) => r.url().endsWith(`/studies/${study}/workspace/content`) && r.request().method() === "PUT" && r.ok());

let restore = null;
let removed = null; // a chosen dimension removed and not yet put back
try {
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(url);
    await n().waitFor({ timeout: 30000 });
    assert.equal(await page.locator('[data-aia="sample:n"] input[type="range"]').count(), 0, "no slider beside the stepper");
    const { w, d } = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
    assert(d <= w + 2, `${width}: page overflow ${d} > ${w}`);
    // DIM-F5: a chosen dimension is removed from the selection itself, its target at least 24 px.
    const removes = page.getByRole("list", { name: "Vybrané dimenze" }).getByRole("button", { name: /^Odebrat dimenzi/ });
    assert((await removes.count()) > 0, `${width}: the fixture's chosen dimensions can be removed where they are listed`);
    for (const box of await removes.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON()))) {
      assert(box.width >= 24 && box.height >= 24, `${width}: a remove target is ${box.width}x${box.height}`);
    }
    await page.screenshot({ path: join(out, `dimensions-${width}.png`), fullPage: true });
    check(`${width}: one stepper for n, the selection's remove targets 24 px or more, no overflow`);
  }

  const own = page.locator("section", { has: page.getByRole("heading", { name: "Vlastní dimenze klienta" }) });
  await own.getByRole("link", { name: /Populace běhu/ }).waitFor();
  assert.equal(await own.getByRole("link", { name: /Populace běhu/ }).getAttribute("href"), `/app/clients/${client}/research/${study}/run`);
  // Still at 390 px from the loop above: the stand-alone link is a touch target (TOUCH_LINK, 44 px).
  const linkBox = await own.getByRole("link", { name: /Populace běhu/ }).boundingBox();
  assert(linkBox && linkBox.height >= 44, `the Populace běhu link is ${linkBox?.height} px tall at 390`);
  check("Vlastní dimenze klienta: read, with the way to Populace běhu, a 44 px target at 390");

  // The last chosen one, so even the fallback in `finally` (the catalogue, which appends) keeps the order.
  const chosen = page.getByRole("list", { name: "Vybrané dimenze" });
  const remove = (name) => chosen.getByRole("button", { name: `Odebrat dimenzi ${name}`, exact: true });
  const last = chosen.getByRole("button", { name: /^Odebrat dimenzi / }).last();
  const label = (await last.getAttribute("aria-label")).slice("Odebrat dimenzi ".length);
  let put = saved();
  await last.focus();
  await page.keyboard.press("Enter");
  removed = label;
  await put;
  assert.equal(await remove(label).count(), 0);
  // DIM-F7: focus stays in the selection (the row before's remove), never back at the page's top.
  assert(await chosen.evaluate((ul) => ul.contains(document.activeElement)), "focus stays in the selection after a remove");
  // DIM-F10: the remove offers Vrátit, which puts the dimension back where it was.
  put = saved();
  await page.getByRole("button", { name: "Vrátit" }).click();
  await put;
  await remove(label).waitFor();
  removed = null;
  await page.waitForFunction((name) => document.activeElement?.getAttribute("aria-label") === name, `Odebrat dimenzi ${label}`);
  check("a chosen dimension is removed by keyboard, focus kept in the selection, and put back by Vrátit with focus on it");

  // DIM-F8: the search's live region is rendered (not display:none) before it has anything to say.
  const catalogue = page.locator("section", { has: page.getByLabel("Hledat dimenzi") });
  const live = catalogue.getByRole("status");
  assert.notEqual(await live.evaluate((e) => getComputedStyle(e).display), "none", "the no-match status is rendered while empty");
  await page.getByLabel("Hledat dimenzi").fill("zzz");
  await live.getByText("Hledání nic nenašlo").waitFor();
  // DIM-F13: typed without diacritics, with spaces around it, the dimension is found.
  await page.getByLabel("Hledat dimenzi").fill(" duvera ");
  await catalogue.getByRole("button", { name: /^Důvěra/ }).waitFor();
  assert.equal(await live.textContent(), "");
  await page.getByLabel("Hledat dimenzi").fill("");
  check("a search that matches nothing is said in a status that was rendered before it; one without diacritics finds");

  // DIM-F14: a name the catalogue has already is refused at the field, and nothing is sent.
  const requests = writes.length;
  const name = page.getByLabel("Název dimenze");
  await name.fill("DUVERA");
  await page.getByRole("button", { name: "Přidat jako požadavek" }).click();
  await page.getByRole("alert").filter({ hasText: "už v katalogu je" }).waitFor();
  assert.equal(await name.getAttribute("aria-invalid"), "true");
  assert.equal(writes.length, requests, "a refused request sends nothing");
  await name.fill("");
  check("a request the catalogue already names is refused at the field, nothing sent");

  const before = Number((await n().getAttribute("aria-valuenow")) ?? NaN);
  const max = Number(await n().getAttribute("aria-valuemax"));
  assert(Number.isFinite(before) && before + 50 <= max, `n ${before} can step up within ${max}`);
  restore = before;
  put = saved();
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

  // Put n back while Dimenze is on screen; "Další" then leaves it for Vzorek.
  await n().fill(String(restore));
  const back = saved();
  await n().press("Enter");
  await back;
  restore = null;
  const done = saved();
  await page.getByRole("button", { name: "Další · Vzorek" }).click();
  await page.waitForFunction(() => location.hash === "#sample");
  await page.locator("[data-sample-view]").waitFor();
  await page.waitForFunction(() => document.activeElement?.matches("h1.arthead__title") && /Vzorek/.test(document.activeElement.textContent ?? ""));
  assert.equal(new URL(page.url()).pathname, `/app/clients/${client}/research/${study}/dimensions`);
  await done; // the persona_done save the click started, before the writes are judged
  check("inside the workbench, Další goes on to Vzorek, its heading focused");

  const paid = writes.filter((x) => !/\/workspace\/(content|stage)$/.test(x.path));
  assert.deepEqual(paid, [], "only the working copy is written: no run, job or request");
  check("zero paid starts");
  assert.deepEqual(errors, []);
} finally {
  if (removed !== null) {
    const put = saved();
    await cardOf(removed).click();
    await put;
  }
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
