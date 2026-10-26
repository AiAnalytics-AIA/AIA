#!/usr/bin/env node
/** Vzorek over the population double: a panel run's sample by quota cell, in a real browser
 * (plans run-qc-and-checkpoint RQC6d, artifact-sample SMP6). Start the workbench in that mode,
 * write the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up --fresh --population-double
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/sample_panel_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. At 1440, 1100, 768 and 390 px: "Složení podle kvót" shows the
 * sample readiness drew, each cell its sample:quota:<key> target with the server's n, the largest
 * six first and the rest folded; the support forecast is known; nothing is editable, nothing
 * overflows. Then a readiness check opens the stage that fixes it; nothing is written but the
 * stage visit, so nothing paid starts.
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
const out = arg("out", join(repo, "tmp/ui-workbench/sample-panel-journey"));
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
const samplePath = `/app/clients/${client}/research/${study}/dimensions#sample`;
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};
const SHOWN = 6;

try {
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    // The readiness Vzorek reads on the working copy is the one the table must show.
    const read = page.waitForResponse((r) => /\/research\/readiness\/working\?/.test(r.url()) && r.ok(), { timeout: 60000 });
    // The same URL again would be a same-document navigation, which reads nothing.
    if (page.url() === base + samplePath) await page.reload();
    else await page.goto(base + samplePath);
    const readiness = await (await read).json();
    const composition = readiness.sample_composition;
    assert(composition && composition.refused === null, `readiness drew the panel's sample @${width}: is the workbench up with --population-double?`);
    const cells = [...composition.cells].sort((a, b) => b.n - a.n);
    assert.equal(cells.reduce((s, c) => s + c.n, 0), readiness.n, `the cells add up to n @${width}`);

    const sample = page.locator("[data-sample-view]");
    await sample.waitFor({ timeout: 30000 });
    await sample.getByRole("heading", { name: "Složení podle kvót" }).waitFor({ timeout: 30000 });
    const rows = sample.locator('[data-aia^="sample:quota:"]');
    assert.equal(await rows.count(), cells.length, `a target per cell @${width}`);
    // The largest six in view, in the server's order of size, each with the server's n.
    const visible = await rows.evaluateAll((trs) => trs.filter((tr) => tr.checkVisibility()).map((tr) => ({ aia: tr.dataset.aia, n: Number(tr.lastElementChild.textContent) })));
    assert.equal(visible.length, Math.min(SHOWN, cells.length), `six cells shown @${width}`);
    assert.deepEqual(visible.map((v) => v.n), cells.slice(0, SHOWN).map((c) => c.n), `largest first @${width}`);
    for (const c of cells) assert.equal(await sample.locator(`[data-aia="sample:quota:${c.key}"]`).count(), 1, `sample:quota:${c.key} @${width}`);
    if (cells.length > SHOWN) {
      await sample.locator("details summary", { hasText: "Dalších" }).click();
      const opened = await rows.evaluateAll((trs) => trs.filter((tr) => tr.checkVisibility()).length);
      assert.equal(opened, cells.length, `the fold opens to every cell @${width}`);
    }
    // §2 reads the drawn sample: the support forecast is known, no longer "neznámé".
    const forecast = page.getByRole("region", { name: "Kolik dat bude za čísly" });
    await forecast.getByRole("heading", { name: /^Opora výsledků/ }).waitFor({ timeout: 30000 });
    assert.equal(await forecast.getByRole("heading", { name: "Opora výsledků: neznámé" }).count(), 0, `the panel's forecast is known @${width}`);
    const editable = "input, select, textarea, [contenteditable]:not([contenteditable='false']), [role=slider], [role=spinbutton], [role=textbox], [role=checkbox], [role=radio], [role=switch], [role=combobox]";
    const editableOutsideN = await sample.locator(editable).evaluateAll((els) => els.filter((e) => !e.closest('[data-aia="sample:n"]')).length);
    assert.equal(editableOutsideN, 0, `Vzorek has no editable control but n (SMP7) @${width}`);
    // The input standard's touch target (I11, WCAG 2.5.8): 44 px at a phone's width, 32 px from
    // 640 px, for every control that stands on its own (one inside a sentence is exempt).
    const floor = width < 640 ? 44 : 32;
    const small = await sample.locator("button, summary").evaluateAll((els, min) => els
      .filter((el) => el.checkVisibility())
      .filter((el) => ![...el.parentElement.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()))
      .map((el) => ({ text: el.textContent.trim(), height: Math.round(el.getBoundingClientRect().height) }))
      .filter((c) => c.height < min), floor);
    assert.deepEqual(small, [], `Vzorek's controls are ${floor} px targets @${width}`);
    await noOverflow(`sample @${width}`);
    await sample.screenshot({ path: join(out, `${width}-sample-panel.png`) });
  }
  check("Složení podle kvót: every drawn cell a sample:quota target with the server's n, the largest six shown, the rest folded, at 1440, 1100, 768 and 390, no overflow");
  check("the support forecast reads the drawn sample: known, at every width");
  check("every control that stands on its own is a touch target: 44 px on a phone, 32 px from 640 px");

  // A readiness check opens the stage that fixes it (SMP4, SMP6), at 1440 (the page is there).
  await page.setViewportSize({ width: 1440, height: 900 });
  const link = page.getByRole("region", { name: "Připravenost ke spuštění" }).locator('[data-aia^="sample:ready:"] button').first();
  await link.waitFor({ timeout: 30000 });
  // "Opravit v Dimenzích" names the stage in the locative; the button carries the stage it opens.
  const stage = await link.getAttribute("data-opens");
  await link.click();
  await page.locator("[data-sample-view]").waitFor({ state: "detached", timeout: 30000 });
  assert.equal((await page.locator(".art .arthead__title").innerText()).trim(), stage, "the check opened its stage");
  check(`a readiness check opens its stage (${stage})`);

  // This journey only reads: the one write a stage visit makes is the frame recording the stage
  // (PUT …/workspace/stage). Anything else, paid or not, fails it (an allow-list, as #697's).
  const unexpected = writes.filter((w) => !(w.method === "PUT" && /^\/api\/v1\/studies\/[^/]+\/workspace\/stage$/.test(w.path)));
  assert.deepEqual(unexpected, [], "no write but the stage visit");
  check("nothing written but the stage visit: nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
