#!/usr/bin/env node
/**
 * The Sociomapa stage in a browser, on the workbench (plan artifact-sociomap SOC8):
 *
 *   node tools/ui_workbench/sociomap_journey.mjs --prepare   # once: one fictional run on -5 (what is in force put back)
 *   node tools/ui_workbench/sociomap_journey.mjs [--facade URL] [--out DIR]
 *
 * Needs `make ui-workbench` with AIA_WEB_RESEARCH_WORKBENCH=true and `make ui-fixtures`. The map the
 * stage draws is the newest run of the `sociomapping` fixture (eight fictional brands). --prepare,
 * when the study has no such run, puts a version of the aia-sociomap-5 preset in force in the local
 * workbench, runs research_journey.mjs on that fixture (fictional fieldwork, no model), and puts back
 * what was in force at once: the run keeps the -5 it pinned. Rerun, it starts nothing new. The
 * journey itself starts nothing:
 *
 *   * the -5 panel at 1440 and 1100 (the workbench's split) and 768 and 390 px, no page overflow;
 *   * every object listed in Správa objektů (Nastavení mapy) carries its Lead name
 *     `object:<battery>/<object>` (SOC1/SOC2), once, and the Lead's focus selector finds that button;
 *   * the Lead's map views (the workbench's aia:lead-map-view event; SOC2) at 1440 and 390 px: a pair
 *     selected opens its detail, a view from above, a control the map lacks said and nothing changed;
 *   * on the workbench's Sociomapa stage (1440): no results tabs, the map before what explains it, no
 *     run or method id outside Technické údaje (artifact-sociomap SOC9-SOC11);
 *   * Objekty / Respondenti opens each map with nothing selected (#562); a pick's detail opens in the
 *     side sheet beside the map, the canvas ending where the sheet begins (SOC13);
 *   * full screen draws Nejsilnější vztahy as the page does: the selected object's five, else the map's;
 *   * a display change (Vše in Nástroje, Absolutní in Nastavení mapy) raises the filter chip, which
 *     says the computation is unchanged, and "Zrušit filtr" goes back to the opening (SOC3); the
 *     listed numbers do not move;
 *   * "Co je co" in the ⓘ box names the four registers (SOC3);
 *   * every pressed control on the -5 map reads in a colour apart from its background (#591);
 *   * an older method's run says so, "Mapa ze starší metody; spusťte nový běh", and draws no map, at
 *     1440, 1100, 768 and 390 px (signed-off-sociomap-method#8, #598). No new run can pin an older
 *     method, so on a workbench without one from before, the -5 run is read as one: its Sociomap
 *     artifact answered in the browser with no map in it; on the Sociomapa stage, no map hint above it;
 *   * no page error, and no write but the stage opened (PUT …/workspace/stage); zero paid jobs.
 *
 * Screenshots and journey.json go to --out (default tmp/ui-workbench/sociomap-journey).
 */
import assert from "node:assert/strict";
import { execFileSync, execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
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

/** The study's finished runs, newest first (the route's largest page). */
async function finishedRuns() {
  const { items } = await api("GET", `/studies/${study}/research/runs?limit=100`);
  return items.filter((r) => r.status === "COMPLETED" && r.methodology?.sociomap?.name);
}
const isFive = (name) => name.startsWith("aia-sociomap-5");
/** The newest finished run whose Sociomap is an older method's (not -5 or a version of it). */
async function olderRun() {
  return (await finishedRuns()).find((r) => !isFive(r.methodology.sociomap.name)) ?? null;
}

/** The repository's interpreter, as the Makefile picks it: AIA_API_PYTHON, else .venv, else python3. */
function python() {
  if (process.env.AIA_API_PYTHON) return process.env.AIA_API_PYTHON;
  const venv = join(repo, ".venv/bin/python");
  return existsSync(venv) ? venv : "python3";
}

if (args.includes("--prepare")) {
  // research_journey.mjs starts the run through the Run stage. Its own end check can read the study's
  // earlier run as the new one's (a study with a finished run already), so the run is then followed
  // here, by the runs route, until a finished run of the method wanted is there.
  const journey = async (wanted) => {
    try {
      execFileSync("node", [join(repo, "tools/ui_workbench/research_journey.mjs"), "--fixture", "sociomapping", "--facade", base], { stdio: "inherit" });
    } catch {
      console.log("sociomap journey: the research journey's own check did not pass; following the run by the API");
    }
    for (let i = 0; i < 90 && !(await finishedRuns()).some((r) => wanted(r.methodology.sociomap.name)); i++) await new Promise((r) => setTimeout(r, 2000));
    if (!(await finishedRuns()).some((r) => wanted(r.methodology.sociomap.name))) throw new Error("the run did not finish within 3 minutes (see tmp/ui-workbench/logs/worker.log)");
  };
  const runs = await finishedRuns();
  const versions = await api("GET", "/methodology/sociomap/versions");
  // What is in force now: a stored version's number, or null for the code's preset; put back below.
  const before = versions.in_force?.origin === "stored" ? versions.in_force.version_number : null;
  // -5 already in force: a stored version of it, or the code's own preset (signed-off-sociomap-method#8).
  const fiveInForce = isFive(versions.in_force?.name ?? "");
  // An older method's run first, while one is what a new run pins; once -5 is the code's own preset no
  // new run can be one, and the journey says it made no older-method check.
  if (!fiveInForce && !runs.some((r) => !isFive(r.methodology.sociomap.name))) await journey((name) => !isFive(name));
  if (!runs.some((r) => isFive(r.methodology.sociomap.name))) {
    // A version of the -5 preset, reused when one is stored: its specification read from the domain
    // (no route serves a preset's).
    let five = fiveInForce ? versions.in_force : versions.versions.find((v) => v.base_preset === "aia-sociomap-5") ?? null;
    if (!five) {
      const spec = JSON.parse(execFileSync(python(), ["-c",
        "import json; from aia_core.domain.methodology.sociomap import SOCIOMAP as m; " +
        "p = next(x for x in m.presets if x.name == 'aia-sociomap-5'); print(p.spec.model_dump_json())"], { encoding: "utf8" }));
      five = await api("POST", "/methodology/sociomap/versions", { base_preset: "aia-sociomap-5", spec, formulas: {}, note: "sociomap journey: the -5 map, locally" });
    }
    // With a -5 version already in force (someone's own choice), the run takes it and nothing is changed.
    if (!fiveInForce) await api("PUT", "/methodology/sociomap/activation", { version_number: five.version_number, reason: "sociomap journey: one -5 run, locally" });
    try {
      await journey(isFive);
    } finally {
      // A run keeps the methods it pinned, so what was in force goes back at once (as ui-methodology does).
      if (!fiveInForce) await api("PUT", "/methodology/sociomap/activation", { version_number: before, reason: "sociomap journey: back to what was in force before it" });
    }
    console.log(`sociomap journey: one run on ${five.name}; ${before === null ? "the code's preset" : `version ${before}`} in force again`);
  }
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
// The map's controls: the bar opens Nastavení mapy (Správa objektů from it, a tab of the side sheet) or
// Nástroje as popovers; the sheet's Objekty tab shows the list again after a pick opened its detail.
const openWindow = async (name) => {
  if (name === "Správa objektů") await button("Nastavení mapy").click();
  await button(name).click();
};
const showList = () => panel.getByRole("tab", { name: "Objekty" }).click();
const attr = (name) => canvas.getAttribute(name);
// The newest run on -5, by its id: a later run on another method does not take its place.
const fiveRun = (await finishedRuns()).find((r) => isFive(r.methodology.sociomap.name)) ?? null;
const openMap = async () => {
  if (!fiveRun) throw new Error("no aia-sociomap-5 run on the sociomapping fixture: run this journey with --prepare first");
  await page.goto(`${base}/app/clients/${client}/research/${study}/results?run=${fiveRun.run_id}#maps`);
  await panel.waitFor({ timeout: 120000 }).catch(() => {
    throw new Error(`run ${fiveRun.run_id} shows no aia-sociomap-5 map`);
  });
};

// The map fits where it is read: the whole stage, its dock on the canvas, in one view of the pane (the
// workbench's artifact pane, else the window under the shell's sticky header), and a narrow canvas no
// taller than its width calls for (the map is drawn at the scale of its shorter side).
const fits = async (where) => {
  await panel.evaluate((n) => n.scrollIntoView({ block: "start" }));
  const fit = await page.evaluate(() => {
    const box = (s) => document.querySelector(s)?.getBoundingClientRect();
    const stage = box('[data-testid="object-map-stage"]');
    const sticky = [...document.querySelectorAll("header")].filter((h) => getComputedStyle(h).position === "sticky").map((h) => h.getBoundingClientRect().height);
    const pane = document.querySelector(".artbody")?.getBoundingClientRect() ?? { top: Math.max(0, ...sticky), bottom: innerHeight };
    return { top: stage.top, bottom: stage.bottom, paneTop: pane.top, paneBottom: pane.bottom, w: stage.width, h: stage.height };
  });
  assert(fit.bottom - fit.top <= fit.paneBottom - fit.paneTop + 1, `${where}: the stage (${Math.round(fit.bottom - fit.top)} px) fit the pane (${Math.round(fit.paneBottom - fit.paneTop)} px)`);
  assert(fit.h <= Math.max(360, 1.5 * fit.w) + 1, `${where}: the canvas (${Math.round(fit.w)} x ${Math.round(fit.h)}) is no taller than its width calls for`);
};

let result = "PASS", message = "";
try {
  // The four widths at 900 px, then two short screens (a phone held sideways, a short window): the
  // stage has to fit what the pane leaves, not a floor of its own (Codex, #637).
  for (const [width, height] of [[1440, 900], [1100, 900], [768, 900], [390, 900], [844, 390], [390, 600]]) {
    await page.setViewportSize({ width, height });
    await openMap();
    await canvas.waitFor();
    await noOverflow(`sociomap @${width}x${height}`);
    await fits(`@${width}x${height}`);
    await shot(`${width}x${height}-sociomap`);
  }
  check("the -5 map at 1440, 1100, 768 and 390 px and on two short screens, no page overflow, the stage in one view");

  // The classic layout: project memory reads the same run under the shell, where the window scrolls
  // the panel and the shell's header stays over it from lg up.
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(`${base}/app/clients/${client}/memory/${study}#maps`);
  await panel.waitFor({ timeout: 60000 });
  await canvas.waitFor();
  await noOverflow("sociomap in project memory @1366x768");
  await fits("project memory @1366x768");
  await shot("1366x768-memory-sociomap");
  check("project memory's map at 1366 x 768: the stage in one view under the sticky header");

  await page.setViewportSize({ width: 1440, height: 900 });
  await openMap();
  await canvas.waitFor();
  await openWindow("Správa objektů");
  const list = panel.locator('[data-testid="object-map-panel-list"] button');
  const names = await list.evaluateAll((bs) => bs.map((b) => b.getAttribute("data-aia")));
  assert(names.length > 0 && names.every((n) => /^object:[^/]+\/[^/~]+$/.test(n ?? "")), `every listed object named: ${names}`);
  for (const n of names) {
    const found = await page.evaluate((t) => [...document.querySelectorAll(`[data-aia="${t}"]`)].map((e) => e.tagName), n);
    assert.deepEqual(found, ["BUTTON"], `${n} is one element, its button`);
  }
  check("every listed object carries its Lead name once, on its button");

  // The Lead's map views (SOC2; research-lead-workbench 14): the event the workbench sends, applied to the
  // picture only. Not live from the server yet, so sent here as the workbench sends it.
  assert(names.length >= 2, `a relation needs two listed objects: ${names}`);
  const [battery, first] = names[0].slice("object:".length).split("/");
  const second = names[1].slice("object:".length).split("/")[1];
  const [a, b] = [first, second].sort();
  const sendView = (view) => page.evaluate((v) => window.dispatchEvent(new CustomEvent("aia:lead-map-view", { detail: v })), view);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await openMap();
    await canvas.waitFor();
    await sendView({ op: "select", target: `pair:${battery}/${a}~${b}` });
    assert.deepEqual((await attr("data-relation")).split("|").sort(), [a, b], `@${width}: the Lead's pair selected`);
    assert.equal(await page.locator(`[data-aia="pair:${battery}/${a}~${b}"]`).count(), 1, `@${width}: the pair's detail open`);
    await sendView({ op: "filter", name: "view", value: "top" });
    assert.equal(JSON.parse(await attr("data-camera")).pitch, 0, `@${width}: the Lead's view from above`);
    const before = await attr("data-camera");
    await sendView({ op: "filter", name: "hide_weak", value: "on" });
    assert((await page.getByTestId("object-map-lead-note").textContent()).includes("skrýt slabé vztahy"), `@${width}: a control the map lacks, said in words`);
    assert.equal(await attr("data-camera"), before, `@${width}: nothing changed by the refused view`);
    await noOverflow(`lead views @${width}`);
    await shot(`${width}-lead-pair`);
  }
  // Back to the map as it opens (the same URL: a goto alone would keep the Lead's selection).
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload();
  await panel.waitFor({ timeout: 120000 });
  await canvas.waitFor();
  await openWindow("Správa objektů");
  check("the Lead's map views at 1440 and 390 px: a pair selected with its detail, the view from above, a control the map lacks said");

  // The workbench's Sociomapa stage is the map (SOC9-SOC11): no results tabs, the map first, what explains
  // it under it, no id outside Technické údaje.
  const stageView = page.locator('[data-testid="sociomap-stage"]');
  if (await stageView.count()) {
    assert.equal(await page.getByRole("tablist", { name: "Oddíly výsledků" }).count(), 0, "no results tabs on the Sociomapa stage");
    const order = await stageView.evaluate((s) => {
      const map = s.querySelector('[data-testid="object-map-stage"]'), explained = s.querySelector('[data-testid="map-explained"]');
      return Boolean(map && explained && map.compareDocumentPosition(explained) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    assert(order, "the map comes before what explains it");
    const plain = await stageView.evaluate((s, ids) => {
      const copy = s.cloneNode(true);
      copy.querySelector('[data-testid="map-tech"]')?.remove();
      return ids.filter((id) => copy.textContent.includes(id));
    }, [fiveRun.run_id, fiveRun.methodology.sociomap.name]);
    assert.deepEqual(plain, [], "no run or method id outside Technické údaje");
    await page.locator('[data-testid="map-explained"]').scrollIntoViewIfNeeded();
    await shot("1440-map-explained");
    await panel.scrollIntoViewIfNeeded();
    check("the Sociomapa stage is the map: no results tabs, the map before what explains it, no id outside Technické údaje");
  } else {
    check("the Sociomapa stage at 1440 is Výsledky's Sociomapy tab here (the workbench is off)");
  }

  await list.first().click();
  const chosen = await attr("data-selected");
  assert(chosen, "an object is selected");
  // The detail opens in the sheet beside the map, never over it: the canvas ends where the sheet begins,
  // and the bar's controls stay free.
  const beside = await page.evaluate(() => {
    const c = document.querySelector('[data-testid="object-map-canvas"]').getBoundingClientRect();
    const s = document.querySelector('[data-testid="object-map-sheet"]').getBoundingClientRect();
    return { canvasRight: c.right, sheetLeft: s.left };
  });
  assert(beside.canvasRight <= beside.sheetLeft + 1, `the canvas (to ${beside.canvasRight}) ends where the sheet (from ${beside.sheetLeft}) begins`);
  await button("Nástroje").click();
  await button("Nástroje").click();
  await shot("1440-detail-beside");
  await button("Respondenti").click();
  assert.equal(await attr("data-map"), "respondents");
  assert.equal(await attr("data-selected"), "", "the respondent map opens with nothing selected");
  await button("Objekty").click();
  assert.equal(await attr("data-selected"), "", "the object map comes back with nothing selected");
  check("Objekty / Respondenti opens each map with nothing selected; a pick's detail opens beside the map");

  await showList();
  await list.first().click();
  const onPage = (await attr("data-relations")).split(" ").sort().join(" ");
  await page.evaluate(() => document.querySelector('[data-testid="object-map-stage"]').requestFullscreen());
  await page.waitForFunction(() => document.fullscreenElement !== null);
  assert.equal(await attr("data-selected"), chosen);
  assert.equal((await attr("data-relations")).split(" ").sort().join(" "), onPage, "full screen draws the selected object's five, as the page");
  await shot("1440-fullscreen-top");
  await page.evaluate(() => document.exitFullscreen());
  await page.waitForFunction(() => document.fullscreenElement === null);
  check("full screen: Nejsilnější vztahy follows the selection, as on the page");

  const values = () => list.evaluateAll((bs) => bs.map((b) => b.textContent));
  await showList();
  const before = await values();
  assert(before.length > 0, "the list is read");
  assert.equal(await bar.count(), 0, "no filter bar at the opening");
  await openWindow("Nástroje");
  await button("Vše").click();
  await openWindow("Nastavení mapy");
  await button("Absolutní").click();
  const said = await bar.innerText();
  assert(said.includes("absolutní výšky, všechny vztahy"), said);
  assert(said.includes("beze změny"), said);
  await button("Správa objektů").click();
  assert.deepEqual(await values(), before, "the listed numbers do not move");
  await shot("1440-filter-bar");
  await bar.getByRole("button", { name: "Zrušit filtr" }).click();
  assert.equal(await bar.count(), 0);
  assert.equal(await attr("data-norm"), "range");
  check("the filter bar names a display change, says what did not change, and Zrušit filtr goes back");

  await panel.getByRole("button", { name: /^Informace o mapě/ }).click();
  const registers = await panel.locator('[data-testid="object-map-registers"] [data-register]').evaluateAll((rs) => rs.map((r) => r.getAttribute("data-register")));
  assert.deepEqual(registers, ["computed", "display", "interpretation", "external"]);
  check("Co je co in the ⓘ box: the four registers");

  const pressed = await panel.locator('button[aria-pressed="true"]').evaluateAll((bs) => bs.map((b) => {
    const s = getComputedStyle(b);
    return { text: b.textContent, color: s.color, background: s.backgroundColor };
  }));
  assert(pressed.length > 0, "some control is pressed");
  for (const p of pressed) assert.notEqual(p.color, p.background, `pressed "${p.text}" reads apart from its background`);
  check("every pressed control reads apart from its background");

  // An older method's run says so and draws no map (#598). A run from before -5 when the workbench
  // has one; else the -5 run, its Sociomap artifact answered in the browser with no map of the
  // signed-off method (no new run can pin an older method).
  const older = await olderRun();
  const read = older ?? fiveRun;
  if (!older) {
    await page.route(`**/research/runs/${fiveRun.run_id}/artifacts/*`, async (route) => {
      try {
        const response = await route.fetch();
        const body = await response.json();
        for (const b of body?.payload?.sociomap?.batteries ?? []) b.maps = {};
        // The body is decoded and shorter now: the stored length and encoding no longer describe it.
        const headers = { ...response.headers() };
        delete headers["content-length"];
        delete headers["content-encoding"];
        await route.fulfill({ status: response.status(), headers, json: body });
      } catch {
        // Not rewritten (an answer that is not JSON, or the page moved on): passed on as it is.
        await route.continue().catch(() => {});
      }
    });
  }
  const label = older ? older.methodology.sociomap.name : `${fiveRun.methodology.sociomap.name} read without its maps`;
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    // On the -5 run this is the URL already open, which a goto would not load again.
    const target = `${base}/app/clients/${client}/research/${study}/results?run=${read.run_id}#maps`;
    if (page.url() === target) await page.reload();
    else await page.goto(target);
    const notice = page.locator("[data-older-method]").first();
    await notice.waitFor({ timeout: 120000 });
    assert.equal(await notice.innerText(), "Mapa ze starší metody; spusťte nový běh");
    assert.equal(await page.locator('[data-testid="object-map-stage"]').count(), 0, `@${width}: an older method's run draws no map`);
    // On the workbench's Sociomapa stage nothing tells how to use the map that is not drawn.
    if (await page.locator('[data-testid="sociomap-stage"]').count()) {
      assert.equal(await page.getByText("Mapu můžete prohlížet shora").count(), 0, `@${width}: no map hint above the notice`);
    }
    await noOverflow(`older method @${width}`);
    await notice.scrollIntoViewIfNeeded();
    await shot(`${width}-older-method`);
  }
  await page.unroute(`**/research/runs/${fiveRun.run_id}/artifacts/*`);
  check(`older method's run (${label}): it says so and draws no map, at 1440, 1100, 768 and 390 px`);

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
