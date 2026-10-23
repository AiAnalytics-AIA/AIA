#!/usr/bin/env node
/**
 * The Metodika tab, every module, in a browser on the workbench (plan methodology-tab Z1b):
 *
 *   node tools/ui_workbench/methodology_journey.mjs [--run] [--facade URL] [--out DIR]
 *
 * Needs the workbench running (`make ui-workbench`); `--run` also needs its fixtures
 * (`make ui-fixtures`). Signed in as the workbench operator (fictional identity), it walks
 * Nastavení -> Metodika module by module, as Z1a walked it by hand:
 *
 *   * every module opens: an editable one on its editor, a read-only one on its catalogue,
 *     every stage either with its steps or saying none is computed;
 *   * in each editor, every step of the outline shows exactly that step, and every link of
 *     a step's place in the computation moves to a step the editor shows (never an empty
 *     pane: the defect found in review on #400);
 *   * each editable module takes one edit, compares it with what is in force, stores it as a
 *     version and puts it in force; the API agrees;
 *   * with --run, one research run (research_journey.mjs) pins every stored version, and the
 *     run says so by name (`methodology` on the run);
 *   * every module it touched is put back to what was in force before it, pass or fail.
 *
 * No page error, no paid job. Screenshots and checks.json go to --out
 * (default tmp/ui-workbench/methodology-journey). Exits non-zero on the first thing that is not so.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (key, fallback) => (args.includes(`--${key}`) ? args[args.indexOf(`--${key}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
assert(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Fictional local identity only");
const RUN = args.includes("--run");
const out = arg("out", join(repo, "tmp/ui-workbench/methodology-journey"));
mkdirSync(out, { recursive: true });

// One edit per editable module, each a value the module's check accepts (Z1a's, where it had one).
const EDITS = {
  sociomap: { reference: "relation.n_min", typed: "20", read: (spec) => spec.relation.n_min, value: 20 },
  support: { reference: "results.min_layer_donors", typed: "20", read: (spec) => spec.results.min_layer_donors, value: 20 },
  aggregation: { reference: "top_box", typed: "1", read: (spec) => spec.top_box, value: 1 },
  response: { reference: "dont_know", typed: "0,2", read: (spec) => spec.dont_know, value: 0.2 },
  readiness: { reference: "sample_size.min", typed: "40", read: (spec) => spec.sample_size.min, value: 40 },
};

const require = createRequire(import.meta.url);
const playwright = await import(pathToFileURL(require.resolve("playwright", { paths: [repo, join(repo, "apps/web")] })).href);
const browser = await (playwright.chromium ?? playwright.default.chromium).launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() => sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" })));
const page = await context.newPage();
const checks = [], errors = [], writes = [], stored = {}, previous = {};
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (request) => { if (!["GET", "HEAD", "OPTIONS"].includes(request.method()) && new URL(request.url()).pathname.startsWith("/api/")) writes.push({ method: request.method(), path: new URL(request.url()).pathname }); });
const headers = { Authorization: "Bearer workbench@example.invalid" };
const get = async (path) => { const r = await page.request.get(base + path, { headers }); assert(r.ok(), `${path}: ${r.status()}`); return r.json(); };
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`), fullPage: true, animations: "disabled" });
const ok = (what) => { checks.push(what); console.log(`methodology journey: ok   ${what}`); };

const openTab = async () => {
  await page.goto(base + "/app/settings"); await page.getByRole("tablist", { name: "Oddíly nastavení" }).waitFor();
  await page.locator("#tab-methodology").click();
  await page.locator("#panel-methodology :is([data-module-card], [data-module-header])").first().waitFor();
};
/** The tab opens on the catalogue (fidelity F4); a module is a card away, back through ← Metodika. */
const openModule = async (title) => {
  const heading = page.getByRole("heading", { level: 2, name: title, exact: true });
  if (await heading.count()) return;
  if (await page.locator("[data-methodology-back]").count()) {
    await page.locator("[data-methodology-back]").click();
    const leave = page.getByRole("button", { name: "Zahodit úpravy a přepnout", exact: true });
    if (await leave.count()) await leave.click();
  }
  await page.getByRole("navigation", { name: "Oblasti metodiky" }).getByRole("button", { name: title, exact: true }).click();
  await heading.waitFor();
};
const visibleSteps = () => page.locator("[data-methodology-editor] fieldset[data-edit-step]:not([hidden])");

/** Every outline step shows itself alone; every context link lands on a step the editor shows. */
const walkEditor = async (moduleId) => {
  const links = await page.locator("[data-edit-step-link]").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-edit-step-link")));
  assert(links.length > 0, `${moduleId}: the editor outline is empty`);
  let moves = 0;
  for (const id of links) {
    await page.locator(`[data-edit-step-link="${id}"]`).click();
    assert.equal(await visibleSteps().count(), 1, `${moduleId}/${id}: not exactly one step shown`);
    assert.equal(await visibleSteps().getAttribute("data-edit-step"), id, `${moduleId}/${id}: another step shown`);
    const targets = await visibleSteps().locator("[data-context-link]").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-context-link")));
    for (const target of targets) {
      await visibleSteps().locator(`[data-context-link="${target}"]`).first().click();
      assert.equal(await visibleSteps().count(), 1, `${moduleId}: the link ${id} -> ${target} left ${await visibleSteps().count()} steps shown`);
      assert.equal(await visibleSteps().getAttribute("data-edit-step"), target, `${moduleId}: the link ${id} -> ${target} landed elsewhere`);
      moves += 1;
      await page.locator(`[data-edit-step-link="${id}"]`).click();
    }
  }
  return { steps: links.length, moves };
};

/** Every stage of a read-only catalogue holds its steps, or says none is computed. */
const walkCatalogue = async (moduleId) => {
  await page.locator("#panel-methodology article").first().waitFor({ state: "attached", timeout: 60000 })
    .catch(() => { throw new Error(`${moduleId}: no step at all`); });
  const stages = page.locator("#panel-methodology section[aria-labelledby^='mg-']");
  const count = await stages.count();
  for (let i = 0; i < count; i += 1) {
    const stage = stages.nth(i);
    const cards = await stage.locator("article").count();
    const none = await stage.getByText("Žádný krok: v AIA se zatím nepočítá.").count();
    assert(cards > 0 || none > 0, `${moduleId}: stage ${i} is empty and does not say so`);
  }
  return count;
};

const chooseField = async (reference) => {
  const field = page.locator(`[data-methodology-editor] [data-field="${reference}"]`).first(); await field.waitFor({ state: "attached" });
  const step = await field.locator("xpath=ancestor::fieldset").getAttribute("data-edit-step");
  await page.locator(`[data-edit-step-link="${step}"]`).click(); await field.waitFor(); return field;
};

/** One edit, compared, stored and put in force through the page; the API agrees. */
const storeAndActivate = async (moduleId) => {
  const edit = EDITS[moduleId];
  const before = await get(`/api/v1/methodology/${moduleId}/versions`);
  previous[moduleId] = before.in_force.origin === "code" ? null : before.in_force.version_number;
  const form = page.locator("[data-methodology-editor]");
  await (await chooseField(edit.reference)).fill(edit.typed);
  await form.getByRole("button", { name: "Porovnat s metodikou v platnosti", exact: true }).click();
  await page.locator("[data-methodology-compare]").waitFor({ timeout: 60000 });
  // The comparison shows on the module's Porovnání (settings-redesign 10b); storing is on Upravit.
  await page.getByRole("tab", { name: "Upravit", exact: true }).click();
  await form.getByRole("button", { name: "Zkontrolovat a uložit", exact: true }).click();
  await form.waitFor({ state: "detached", timeout: 60000 });
  const after = await get(`/api/v1/methodology/${moduleId}/versions`);
  const created = after.versions.find((v) => !before.versions.some((old) => old.version_number === v.version_number));
  assert(created, `${moduleId}: no new version stored`);
  assert.equal(edit.read(created.spec), edit.value, `${moduleId}: stored ${JSON.stringify(edit.read(created.spec))}, typed ${edit.typed}`);
  await page.getByRole("button", { name: `Uvést ${created.name} v platnost`, exact: true }).click();
  const dialog = page.locator("[data-methodology-activate]");
  await dialog.getByRole("radio", { name: "Ověření na pilotní studii", exact: true }).click();
  await dialog.getByRole("button", { name: /^Aktivovat( jako interní)?$/ }).click();
  await page.locator("[data-in-force]").filter({ hasText: created.name }).waitFor();
  assert.equal((await get(`/api/v1/methodology/${moduleId}/versions`)).in_force.version_number, created.version_number);
  stored[moduleId] = created.name;
  return created.name;
};

/** Every module the journey touched back on what was in force before it, through the API the page uses. */
const restore = async () => {
  for (const [moduleId, version] of Object.entries(previous)) {
    const r = await page.request.put(`${base}/api/v1/methodology/${moduleId}/activation`, { headers, data: { version_number: version, reason: "methodology journey: back to what was in force before it" } });
    if (!r.ok()) console.error(`methodology journey: could not restore ${moduleId}: ${r.status()}`);
  }
};

try {
  await openTab();
  // D-13: the 18.6.6 reference map and the experimental H-Model are not listed on the tab.
  const HIDDEN = new Set(["sociomap_reference", "sociomapping"]);
  const modules = (await get("/api/v1/methodology")).filter((m) => !HIDDEN.has(m.id));
  assert(modules.length >= 5, `only ${modules.length} modules`);
  for (const module of modules) {
    await openModule(module.title_cs);
    const editor = page.locator("[data-methodology-editor]");
    if (module.editable) {
      await editor.waitFor({ timeout: 60000 }).catch(() => { throw new Error(`${module.id}: an administrator does not open on the editor`); });
      const walked = await walkEditor(module.id);
      assert(EDITS[module.id], `${module.id}: editable, but the journey has no edit for it`);
      const name = await storeAndActivate(module.id);
      await shot(`${module.id}-in-force`);
      ok(`${module.id}: ${walked.steps} steps each shown alone, ${walked.moves} context links each landing on a shown step; stored and in force as ${name}`);
    } else {
      assert.equal(await editor.count(), 0, `${module.id}: read-only, yet an editor opened`);
      const stages = await walkCatalogue(module.id);
      await shot(`${module.id}`);
      ok(`${module.id}: read-only catalogue, ${stages} stages, each with steps or saying none is computed`);
    }
  }

  if (RUN) {
    execFileSync("node", [join(repo, "tools/ui_workbench/research_journey.mjs"), "--facade", base, "--out", join(out, "research")], { stdio: "inherit" });
    const studies = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
    const runs = (await get(`/api/v1/studies/${studies.persona.study}/research/runs`)).items;
    const latest = runs.reduce((a, b) => (new Date(a.created_at) > new Date(b.created_at) ? a : b));
    for (const [moduleId, name] of Object.entries(stored)) {
      const method = latest.methodology[moduleId];
      assert(method?.stored && method.name === name, `the run pinned ${moduleId} as ${JSON.stringify(method)}, not ${name}`);
    }
    ok(`one research run pinned every stored version by name: ${Object.values(stored).join(", ")}`);
  }

  assert.equal(writes.filter((r) => /agent-jobs|deep-research\/runs/.test(r.path)).length, 0, "a paid job was started");
  assert.deepEqual(errors, []);
  const report = { status: "PASS", checks, pageErrors: errors, paidJobs: 0, stored };
  writeFileSync(join(out, "checks.json"), JSON.stringify(report, null, 2));
  console.log(`methodology journey: PASS (${checks.length} checks; evidence in ${out})`);
} catch (error) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true }).catch(() => {});
  writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(error), checks, pageErrors: errors, stored }, null, 2));
  console.error(`methodology journey: FAIL ${error.message ?? error}`);
  process.exitCode = 1;
} finally {
  await restore();
  await browser.close();
}
