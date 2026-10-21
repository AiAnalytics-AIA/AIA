#!/usr/bin/env node
/**
 * The Sociomapa stage in a browser, on the workbench (plan artifact-sociomap SOC8):
 *
 *   node tools/ui_workbench/sociomap_journey.mjs --prepare   # once: a -5 version in force, one fictional run
 *   node tools/ui_workbench/sociomap_journey.mjs [--facade URL] [--out DIR]
 *
 * Needs `make ui-workbench` with AIA_WEB_RESEARCH_WORKBENCH=true and `make ui-fixtures`. The map the
 * stage draws is the newest run of the `sociomapping` fixture (eight fictional brands). --prepare stores
 * a methodology version from the aia-sociomap-5 preset, puts it in force in the local workbench
 * only, and runs research_journey.mjs on that fixture, so the run pins -5 (fictional fieldwork, no
 * model). The journey itself starts nothing:
 *
 *   * the -5 panel at 1440 and 1100 (the workbench's split) and 768 and 390 px, no page overflow;
 *   * every listed object carries its Lead name `object:<battery>/<object>` (SOC1/SOC2), once, and
 *     the Lead's focus selector finds that button;
 *   * Objekty / Respondenti opens each map with nothing selected (#562);
 *   * full screen draws the map's five strongest relations whatever is selected (#562);
 *   * a display change raises the filter bar, which says the computation is unchanged, and
 *     "Zrušit filtr" goes back to the opening (SOC3); the listed numbers do not move;
 *   * "Co je co" names the four registers (SOC3);
 *   * every pressed control reads in a colour apart from its background, on the -5 map and on an
 *     older method's run (workbench.css base layer, #591); once #598 lands, that run says it is an
 *     older method's and draws no map;
 *   * no page error, and no write but the stage opened (PUT …/workspace/stage); zero paid jobs.
 *
 * Screenshots and journey.json go to --out (default tmp/ui-workbench/sociomap-journey).
 */
import assert from "node:assert/strict";
import { execFileSync, execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/sociomap-journey"));
mkdirSync(out, { recursive: true });
const OPERATOR = "workbench@example.invalid";
const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.sociomapping;

async function api(method, path, body) {
  const r = await fetch(`${base}/api/v1${path}`, {
    method, headers: { Authorization: `Bearer ${OPERATOR}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

/** The newest finished run of the study whose Sociomap is an older method's (not -5 or a version of it). */
async function olderRun() {
  const { items } = await api("GET", `/studies/${study}/research/runs`);
  return items.find((r) => r.status === "COMPLETED" && r.methodology?.sociomap?.name && !r.methodology.sociomap.name.startsWith("aia-sociomap-5")) ?? null;
}

if (args.includes("--prepare")) {
  // The aia-sociomap-5 preset's specification, read from the domain (no route serves a preset's spec).
  const python = join(repo, ".venv/bin/python");
  const spec = JSON.parse(execFileSync(python, ["-c",
    "import json; from aia_core.domain.methodology.sociomap import SOCIOMAP as m; " +
    "p = next(x for x in m.presets if x.name == 'aia-sociomap-5'); print(p.spec.model_dump_json())"], { encoding: "utf8" }));
  const inForce = (await api("GET", "/methodology/sociomap")).in_force;
  const journey = () => execFileSync("node", [join(repo, "tools/ui_workbench/research_journey.mjs"), "--fixture", "sociomapping", "--facade", base], { stdio: "inherit" });
  // An older method's run first, while the code's preset is in force, for the older-method check.
  if (!(await olderRun()) && !String(inForce).startsWith("aia-sociomap-5")) journey();
  if (!String(inForce).startsWith("aia-sociomap-5")) {
    const v = await api("POST", "/methodology/sociomap/versions", { base_preset: "aia-sociomap-5", spec, formulas: {}, note: "sociomap journey: the -5 map, locally" });
    await api("PUT", "/methodology/sociomap/activation", { version_number: v.version_number, reason: "sociomap journey: the -5 map, locally" });
    console.log(`sociomap journey: ${v.name} in force (was ${inForce})`);
  }
  journey();
  console.log("sociomap journey: prepared; run it again without --prepare");
  process.exit(0);
}

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
await context.addInitScript((s) => sessionStorage.setItem("aia.session", s),
  JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR }));
const page = await context.newPage();
const errors = [], writes = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => { checks.push(name); console.log(`sociomap journey: ok   ${name}`); };
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};
const panel = page.locator('[data-testid="object-map-panel"]').first();
const canvas = page.locator('[data-testid="object-map-canvas"]').first();
const bar = page.locator('[data-testid="object-map-filter-bar"]');
const button = (name) => panel.getByRole("button", { name, exact: true }).first();
const attr = (name) => canvas.getAttribute(name);
const openMap = async () => {
  await page.goto(`${base}/app/clients/${client}/research/${study}/results#maps`);
  await panel.waitFor({ timeout: 120000 }).catch(() => {
    throw new Error("no aia-sociomap-5 map on the sociomapping fixture's newest run: run this journey with --prepare first");
  });
};

let result = "PASS", message = "";
try {
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await openMap();
    await canvas.waitFor();
    await noOverflow(`sociomap @${width}`);
    await panel.scrollIntoViewIfNeeded();
    await shot(`${width}-sociomap`);
  }
  check("the -5 map at 1440, 1100, 768 and 390 px, no page overflow");

  await page.setViewportSize({ width: 1440, height: 900 });
  await openMap();
  await canvas.waitFor();
  const list = panel.locator('[data-testid="object-map-panel-list"] button');
  const names = await list.evaluateAll((bs) => bs.map((b) => b.getAttribute("data-aia")));
  assert(names.length > 0 && names.every((n) => /^object:[^/]+\/[^/~]+$/.test(n ?? "")), `every listed object named: ${names}`);
  for (const n of names) {
    const found = await page.evaluate((t) => [...document.querySelectorAll(`[data-aia="${t}"]`)].map((e) => e.tagName), n);
    assert.deepEqual(found, ["BUTTON"], `${n} is one element, its button`);
  }
  check("every listed object carries its Lead name once, on its button");

  const opening = (await attr("data-relations")).split(" ").sort().join(" ");
  await list.first().click();
  const chosen = await attr("data-selected");
  assert(chosen, "an object is selected");
  await button("Respondenti").click();
  assert.equal(await attr("data-map"), "respondents");
  assert.equal(await attr("data-selected"), "", "the respondent map opens with nothing selected");
  await button("Objekty").click();
  assert.equal(await attr("data-selected"), "", "the object map comes back with nothing selected");
  check("Objekty / Respondenti opens each map with nothing selected");

  await list.first().click();
  await page.evaluate(() => document.querySelector('[data-testid="object-map-stage"]').requestFullscreen());
  await page.waitForFunction(() => document.fullscreenElement !== null);
  assert.equal(await attr("data-selected"), chosen);
  assert.equal((await attr("data-relations")).split(" ").sort().join(" "), opening, "full screen draws the map's five strongest");
  await shot("1440-fullscreen-top");
  await page.evaluate(() => document.exitFullscreen());
  await page.waitForFunction(() => document.fullscreenElement === null);
  check("full screen: Top vztahy is the map's five strongest whatever is selected");

  const values = () => list.evaluateAll((bs) => bs.map((b) => b.textContent));
  const before = await values();
  assert.equal(await bar.count(), 0, "no filter bar at the opening");
  await button("Vše").click();
  await button("Absolutní").click();
  const said = await bar.innerText();
  assert(said.includes("absolutní výšky, všechny vztahy"), said);
  assert(said.includes("beze změny"), said);
  assert.deepEqual(await values(), before, "the listed numbers do not move");
  await shot("1440-filter-bar");
  await bar.getByRole("button", { name: "Zrušit filtr" }).click();
  assert.equal(await bar.count(), 0);
  assert.equal(await attr("data-norm"), "range");
  check("the filter bar names a display change, says what did not change, and Zrušit filtr goes back");

  const registers = await panel.locator('[data-testid="object-map-registers"] [data-register]').evaluateAll((rs) => rs.map((r) => r.getAttribute("data-register")));
  assert.deepEqual(registers, ["computed", "display", "interpretation", "external"]);
  check("Co je co: the four registers");

  const pressed = await panel.locator('button[aria-pressed="true"]').evaluateAll((bs) => bs.map((b) => {
    const s = getComputedStyle(b);
    return { text: b.textContent, color: s.color, background: s.backgroundColor };
  }));
  assert(pressed.length > 0, "some control is pressed");
  for (const p of pressed) assert.notEqual(p.color, p.background, `pressed "${p.text}" reads apart from its background`);
  check("every pressed control reads apart from its background");

  // An older method's run: its map is drawn as before (its pressed pills read apart from their
  // background, the workbench base layer, #591) or, once signed-off-sociomap-method#8 (#598) lands, it
  // says so and draws nothing. Without such a run there is nothing to look at, and the journey says so.
  const older = await olderRun();
  if (!older) check("no older method's run on this workbench: the older-method check not made (--prepare makes one)");
  else {
    await page.goto(`${base}/app/clients/${client}/research/${study}/results?run=${older.run_id}#maps`);
    const notice = page.locator("[data-older-method]").first();
    const stage = page.locator('[data-testid="object-map-stage"]').first();
    await Promise.race([notice.waitFor({ timeout: 120000 }), stage.waitFor({ timeout: 120000 })]);
    if (await notice.count()) {
      assert((await notice.innerText()).includes("Mapa ze starší metody"));
      check(`older method's run (${older.methodology.sociomap.name}): it says so and draws no map`);
    } else {
      await stage.scrollIntoViewIfNeeded();
      const pills = await stage.locator('button[aria-pressed="true"]').evaluateAll((bs) => bs.map((b) => {
        const s = getComputedStyle(b);
        return { text: b.textContent, color: s.color, background: s.backgroundColor };
      }));
      assert(pills.length > 0, "the older map has a pressed control");
      for (const p of pills) assert.notEqual(p.color, p.background, `older map: pressed "${p.text}" reads apart from its background`);
      await stage.screenshot({ path: join(out, "1440-older-method.png") });
      check(`older method's run (${older.methodology.sociomap.name}): every pressed pill reads apart from its background`);
    }
  }

  assert.deepEqual(errors, [], "no page error");
  // Opening a stage records it (PUT …/workspace/stage, the study's last stage); nothing else is written.
  const other = writes.filter((w) => !/\/workspace\/stage$/.test(w.path));
  assert.deepEqual(other, [], "nothing written but the stage opened: the map changes only its picture");
  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("no page error; nothing written but the stage opened; zero paid jobs");
} catch (e) {
  result = "FAIL";
  message = String(e?.message ?? e);
  await shot("failure").catch(() => {});
} finally {
  writeFileSync(join(out, "journey.json"), JSON.stringify({ result, message, checks, errors, writes }, null, 1));
  await browser.close();
}
console.log(`sociomap journey: ${result}${message ? ` ${message}` : ""} (evidence in ${out})`);
process.exit(result === "PASS" ? 0 : 1);
