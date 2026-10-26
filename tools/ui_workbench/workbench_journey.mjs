#!/usr/bin/env node
/** The research workbench in a real browser (plan research-lead-workbench chunk 12, ADR 0026).
 * Start the workbench with the switch on, write the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/workbench_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. It checks the workbench at 1440, 1280, 1100, 1099, 768 and 390 px
 * (the split, the side drawer and the sheet, research-lead-workbench 26b-26c): no page overflow,
 * nothing remounted across 1100 or 768 px, the Lead opened from the launcher and closed by Escape, the eleven stages in six phases, the separator by
 * keyboard, the focus modes, the stage navigation (Výsledky's views by hash), Návrh's research
 * questions with their coverage at 1440, 1100, 768 and 390 px, Vzorek read only with the server's
 * forecast at the same four widths, and that nothing
 * paid starts: no research run, agent job, Deep Research run or Lead request approval.
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
const out = arg("out", join(repo, "tmp/ui-workbench/workbench-journey"));
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
const errors = [], writes = [], checks = [], requests = [], switches = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (r.method() === "GET" && path.startsWith("/api/")) requests.push(path);
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.questionnaire;
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
// A stage by its own name: its button also says its status and what reopened it, which can name
// another stage ("změna dříve v návrhu"), so a text match on the button finds several.
const navStage = (label, current = false) =>
  page.locator(`.nav__stage${current ? ".is-current" : ""}`).filter({ has: page.locator(".nav__label", { hasText: new RegExp(`^${label}$`) }) });
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};

try {
  await page.goto(base + stagePath("brief"));
  const wb = page.locator("[data-workbench]");
  await wb.waitFor({ timeout: 30000 });
  check("the workbench is the study screen at 1440");

  const stages = page.locator("nav[aria-label='Kroky studie'] .nav__stage");
  assert.equal(await stages.count(), 11, "eleven stages");
  assert.equal(await page.locator("nav[aria-label='Kroky studie'] [role=group]").count(), 6, "six phases");
  assert.equal((await page.locator(".nav__stage.is-current").innerText()).split("\n")[0], "Zadání");
  check("eleven stages in six phases, Zadání current");

  // The navigator is one steady bar (research-lead-workbench 35): across the whole width, and every
  // stage's slot where it was whichever stage is current, at 1440, 1280 and 1100 px.
  for (const width of [1440, 1280, 1100]) {
    await page.setViewportSize({ width, height: 900 });
    const slots = [];
    for (const slug of ["brief", "questionnaire", "audience", "results"]) {
      await page.goto(base + stagePath(slug));
      await page.locator(".nav__stage.is-current").waitFor();
      slots.push(await stages.evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return `${Math.round(r.x)}:${Math.round(r.width)}:${Math.round(r.height)}`; })));
    }
    for (const other of slots.slice(1)) assert.deepEqual(other, slots[0], `the navigator shifted with the current stage @${width}`);
    const last = await stages.last().evaluate((e) => e.getBoundingClientRect().right);
    assert(last >= width - 24, `the navigator ends at ${last} of ${width} px`);
    await noOverflow(`navigator @${width}`);
    await page.locator("nav[aria-label='Kroky studie']").screenshot({ path: join(out, `${width}-navigator.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + stagePath("brief"));
  await page.locator(".conv").waitFor();
  check("the navigator spans the width, and no slot moves or grows with the current stage at 1440, 1280 and 1100");

  await page.locator(".conv").waitFor();
  assert(await page.locator(".art .arthead__title").innerText() === "Zadání");
  await noOverflow("brief @1440");
  await shot("1440-brief");

  // The Brief's Lead targets (artifact-brief BRF1): each field the contract names is one element
  // (an empty context field by its chip), and a name it does not hold finds nothing.
  // Counted once the Brief has read its materials: until then it says it is loading.
  await page.locator('[id="brief-goal"]').waitFor({ timeout: 30000 });
  const BRIEF_FIELDS = ["goal", "title", "objectives", "type", "files", "context", "briefing.product_description", "decision_use", "briefing.situation", "briefing.what_is_known", "briefing.constraints"];
  for (const f of BRIEF_FIELDS) assert.equal(await page.locator(`[id="brief-${f}"]`).count(), 1, `brief:${f}`);
  assert.equal(await page.locator('[id="brief-situation"]').count(), 0, "brief:situation is not a target");
  check("every Brief target the contract names is one element");

  // One focus ring per field: a field that sets outline-none inside a wrapper drawing the ring on
  // focus-within keeps it, and the workbench's own controls still get theirs.
  const linkField = page.getByRole("textbox", { name: "Odkaz", exact: true });
  await linkField.focus();
  assert.equal(await linkField.evaluate((e) => getComputedStyle(e).outlineStyle), "none", "a focused outline-none field draws no ring of its own");
  const phase = page.locator(".wb button").first();
  await phase.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle), "solid", "a workbench control focused by keyboard draws the ring");
  check("one focus ring on a field, the ring on the workbench's controls");

  // The separator: keyboard moves it 2 % within 28-62 %; Home goes back to 40 %.
  const sep = page.getByRole("separator", { name: "Změnit poměr konverzace a artefaktu" });
  await sep.focus();
  const now = async () => Number(await sep.getAttribute("aria-valuenow"));
  const start = await now();
  await page.keyboard.press("ArrowRight");
  assert.equal(await now(), Math.min(62, start + 2));
  for (let i = 0; i < 30; i++) await page.keyboard.press("ArrowLeft");
  assert.equal(await now(), 28);
  await page.keyboard.press("Home");
  assert.equal(await now(), 40);
  check("separator: arrows by 2 %, bounded at 28 %, Home back to 40 %");

  // Focus modes: the artifact takes the width (the conversation a rail), then the conversation 68 %.
  await page.getByRole("button", { name: "Soustředit se na artefakt" }).click();
  await page.locator(".split__rail").waitFor();
  assert.equal(await page.locator(".split__left").isVisible(), false, "the conversation is hidden in artifact focus");
  await shot("1440-artifact-focus");
  await page.getByRole("button", { name: "Zpět na 40 / 60" }).first().click();
  await page.locator(".split__left").waitFor({ state: "visible" });
  await page.getByRole("button", { name: "Soustředit se na konverzaci" }).click();
  const leftShare = await page.evaluate(() => document.querySelector(".split__left").getBoundingClientRect().width / document.querySelector(".split").getBoundingClientRect().width);
  assert(Math.abs(leftShare - 0.68) < 0.02, `conversation focus is 68 %: ${leftShare}`);
  await page.keyboard.press("Alt+Shift+N");
  await page.locator(".split__handle").waitFor();
  assert.equal(await now(), 40, "focus modes never changed the width chosen");
  check("focus modes: rail, 68 %, back to the width chosen");

  // The navigator opens each design stage on its own route, and only the stage's body swaps
  // (research-lead-workbench 34): the Lead's composer is the same element, its draft kept, and the
  // study's Lead is never read again. The switch is timed from the click to the new stage's title.
  // A Lead not hatched yet (a fresh workbench; lead_journey hatches it) has no draft to keep: its
  // composer is disabled, and the pane's identity is the check.
  await page.locator("#composer").waitFor();
  const draft = (await page.locator("#composer").isEnabled()) ? "Rozepsaná zpráva, neodeslaná" : null;
  if (draft) await page.locator("#composer").fill(draft);
  await page.evaluate(() => { window.__aiaComposer = document.getElementById("composer"); window.__aiaPane = document.querySelector(".conv"); });
  const leadReads = () => requests.filter((r) => /\/api\/v1\/studies\/[^/]+\/lead$/.test(r)).length;
  const leadBefore = leadReads();
  for (const [label, slug, title] of [["Návrh", "plan", "Návrh"], ["Dotazník", "questionnaire", "Dotazník"], ["Cíl. skupina", "audience", "Cílová skupina"], ["Dimenze", "dimensions", "Dimenze"]]) {
    const started = Date.now();
    await navStage(label).click();
    await page.waitForURL(`**${stagePath(slug)}`);
    await page.waitForFunction((t) => document.querySelector(".art .arthead__title")?.textContent === t, title);
    switches.push({ stage: slug, ms: Date.now() - started });
    await navStage(label, true).waitFor();
    assert.equal(await page.evaluate(() => document.getElementById("composer") === window.__aiaComposer), true, `${slug}: the Lead's pane was drawn again`);
    assert.equal(await page.evaluate(() => document.querySelector(".conv") === window.__aiaPane), true, `${slug}: the conversation was drawn again`);
    if (draft) assert.equal(await page.locator("#composer").inputValue(), draft, `${slug}: the draft was lost`);
    await noOverflow(`${slug} @1440`);
    await shot(`1440-${slug}`);
  }
  assert.equal(leadReads(), leadBefore, "a stage change read the study's Lead again");
  // Generous: a dev server compiles each route once; the measure is in report.json.
  for (const s of switches) assert(s.ms < 5000, `switching to ${s.stage} took ${s.ms} ms`);
  if (draft) await page.locator("#composer").fill("");
  check(`navigator opens Návrh, Dotazník, Cílová skupina and Dimenze on their routes, the Lead's pane${draft ? " and draft" : ""} kept (${switches.map((s) => `${s.stage} ${s.ms} ms`).join(", ")})`);

  // Vzorek is a read-only view over Dimenze and Kontrola, on Dimenze's route.
  await navStage("Vzorek").click();
  await page.waitForFunction(() => location.hash === "#sample");
  await page.locator("[data-sample-view]").waitFor();
  await shot("1440-sample");
  await navStage("Dimenze").click();
  await navStage("Dimenze", true).waitFor();
  assert.equal(await page.locator("[data-sample-view]").count(), 0, "back on Dimenze, not Vzorek");
  check("Vzorek shows the sample read only, and Dimenze is one click back");

  // Výsledky's views are the hash ResultsWorkspace reads.
  await navStage("Sociomapa").click();
  await page.waitForURL(`**${stagePath("results")}#maps`);
  await navStage("Sociomapa", true).waitFor();
  await navStage("Zpráva").click();
  await page.waitForFunction(() => location.hash === "#report");
  await navStage("Zpráva", true).waitFor();
  await shot("1440-report");
  check("Sociomapa and Zpráva open Výsledky's views by hash");

  // Narrower: the split down to 1100 px, the side drawer from 768, the sheet below (26b, D21).
  // The layout follows the width's media query, a render after the resize's event: waited for, then
  // asserted, so a read in between never decides it.
  const layoutIs = async (want) => {
    await page.waitForFunction((w) => document.querySelector("[data-workbench]")?.getAttribute("data-layout") === w, want, { timeout: 5000 }).catch(() => {});
    assert.equal(await page.locator("[data-workbench]").getAttribute("data-layout"), want);
  };
  for (const [width, want] of [[1280, "split"], [1100, "split"], [1099, "drawer"], [768, "drawer"], [390, "sheet"]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    await page.locator("[data-workbench]").waitFor();
    await layoutIs(want);
    await noOverflow(`questionnaire @${width}`);
    // One level-one heading, the artifact's title; and at every width room beside it for the
    // save state ("Změny se uloží za chvíli", 150 px at 12 px) on one line (workbench audit F13).
    assert.deepEqual(await page.locator("h1").allInnerTexts(), ["Dotazník"], `the page's h1 @${width}`);
    const column = await page.locator(".arthead > div").first().evaluate((e) => e.getBoundingClientRect().width);
    assert.ok(column >= 240, `the title column is ${Math.round(column)} px @${width}`);
    assert.equal(await page.getByRole("button", { name: /^Připravenost a pomoc/ }).count(), 1, `the readiness button keeps its name @${width}`);
    // The root's layout rules apply: nested under .wb they once read ".wb .wb--sheet …" and matched nothing.
    if (want === "sheet") assert.equal(await page.locator(".shead__spacer").evaluate((e) => getComputedStyle(e).display), "none", "the sheet's header rules apply");
    await shot(`${width}-questionnaire`);
  }
  check("the workbench at 1280 and 1100 (split), 1099 and 768 (drawer), 390 (sheet), no overflow, one h1, room for the save state");


  // A resize across 1100 px remounts nothing: the stage's and the conversation's own DOM nodes,
  // tagged before, are the same nodes after crossing both ways (a remount makes new ones).
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + stagePath("questionnaire"));
  await page.locator(".wb-stage > div").first().waitFor();
  await page.locator(".conv").waitFor({ state: "attached" });
  await page.evaluate(() => {
    document.querySelector(".wb-stage > div:not([hidden])").dataset.kept = "stage";
    document.querySelector(".conv").dataset.kept = "conversation";
  });
  await page.setViewportSize({ width: 1024, height: 900 });
  await layoutIs("drawer");
  await page.setViewportSize({ width: 390, height: 900 });
  await layoutIs("sheet");
  await page.setViewportSize({ width: 1440, height: 900 });
  await layoutIs("split");
  assert.equal(await page.locator('[data-kept="stage"]').count(), 1, "the stage's screen was not remounted");
  assert.equal(await page.locator('[data-kept="conversation"]').count(), 1, "the conversation was not remounted");
  check("crossing 1100 and 768 px both ways remounts neither the stage nor the conversation");

  // Below 1100 px the launcher opens the Lead as a modal dialog; Escape closes it, back to the launcher.
  for (const width of [1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const launcher = page.locator("[data-lead-launcher]");
    await launcher.click();
    const dialog = page.getByRole("dialog", { name: "Vedoucí výzkumu" });
    await dialog.waitFor();
    await noOverflow(`Lead open @${width}`);
    await shot(`${width}-lead-open`);
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
    // The launcher takes the focus a frame after the drawer hides (moveFocus): waited for, not raced.
    await page.waitForFunction(() => document.activeElement?.hasAttribute("data-lead-launcher"), null, { timeout: 5000 })
      .catch(() => assert.fail(`focus back on the launcher @${width}`));
  }
  check("the launcher opens the Lead at 1024 and 390; Escape closes it to the launcher");

  // The compact navigator (26d): every stage reachable by keyboard at 768 and 390 px, no overflow.
  await page.setViewportSize({ width: 768, height: 900 });
  await page.goto(base + stagePath("questionnaire"));
  await page.locator(".nav--scroll .nav__stage").first().focus();
  await page.keyboard.press("End");
  assert.match(await page.evaluate(() => document.activeElement?.textContent ?? ""), /Zpráva/);
  const inView = await page.evaluate(() => {
    const r = document.activeElement.getBoundingClientRect();
    return r.right <= window.innerWidth + 1 && r.left >= -1;
  });
  assert(inView, "the last stage scrolls into view by keyboard @768");
  await noOverflow("navigator @768");
  await page.setViewportSize({ width: 390, height: 900 });
  await page.locator(".nav__current").click();
  assert.equal(await page.locator(".nav__list .nav__stage").count(), 11, "all eleven stages @390");
  await page.locator(".nav__list .nav__stage").first().focus();
  await page.keyboard.press("End");
  assert.match(await page.evaluate(() => document.activeElement?.textContent ?? ""), /Zpráva/);
  await noOverflow("navigator open @390");
  await shot("390-navigator");
  await page.keyboard.press("Escape");
  await page.locator(".nav__list").waitFor({ state: "detached" });
  await shot("390-header");
  check("every stage reachable by keyboard at 768 (scrolling) and 390 (the stage list), no overflow");

  // At a phone's width every control the frame owns is a 44 px target (input-interactions I11): the
  // header, the navigator and its list, the artifact header, the launcher and the open conversation.
  const frameTargets = (where) => page.evaluate(() => [...document.querySelectorAll("[data-workbench] button, [data-workbench] a[href]")]
    .filter((e) => !e.closest("#artbody") && !e.classList.contains("skip") && e.getClientRects().length && getComputedStyle(e).visibility !== "hidden")
    .map((e) => ({ name: (e.getAttribute("aria-label") || e.textContent || "").trim().slice(0, 40), h: Math.round(e.getBoundingClientRect().height), w: Math.round(e.getBoundingClientRect().width) }))
    .filter((x) => x.h < 44 || x.w < 44)).then((small) => assert.deepEqual(small, [], `frame targets under 44 px @390 (${where})`));
  await frameTargets("closed");
  await page.locator(".nav__current").click();
  await frameTargets("stage list");
  await page.keyboard.press("Escape");
  await page.locator("[data-lead-launcher]").click();
  await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor();
  await frameTargets("conversation");
  await page.keyboard.press("Escape");
  check("every control the frame owns is a 44 px target at 390: header, stage list, artifact header, conversation");

  // Zadání: V2's sections in order -- Cíle, Rozhodnutí, Kontext -- at every width (artifact-brief
  // BRF2). Reading it is a GET; nothing is edited here (the workspace journey edits a fresh study).
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("brief"));
    const sections = page.locator('[id="brief-objectives"], [id="brief-decision_use"], [id="brief-context"]');
    await sections.first().waitFor({ timeout: 30000 });
    assert.equal(await sections.count(), 3, `Cíle, Rozhodnutí, Kontext @${width}`);
    assert.equal(await page.getByRole("button", { name: /^Upravit: Situace \/ trh/ }).count(), 1, `Kontext edited in place @${width}`);
    await noOverflow(`brief @${width}`);
    await page.screenshot({ path: join(out, `${width}-brief.png`), fullPage: true });
  }
  check("Zadání shows Cíle, Rozhodnutí and Kontext, edited in place, at 1440, 1100, 768 and 390, no overflow");

  // Návrh: each research question with its coverage on its row (artifact-design DSN2, DSN2b), at every width, in the
  // workbench at each. Reading it is a GET.
  const planSubmitsBefore = writes.filter((w) => w.path.endsWith("/design/revisions")).length;
  const planSavesBefore = writes.filter((w) => w.path.endsWith("/workspace/content")).length;
  const dr = fixtures.deep_research;
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + `/app/clients/${dr.client}/research/${dr.study}/plan`);
    const coverage = page.getByRole("region", { name: "Výzkumné otázky a co je měří" });
    await coverage.waitFor({ timeout: 30000 });
    // DSN2b: the coverage is read under the research questions. The deep_research fixture states two
    // in research_plan and none in its analysis, the list's source: the server traces them anyway, so
    // they are listed with their coverage under the list, never hidden (each row's own coverage is
    // PlanStep.test's). Every width reads it without writing anything.
    await coverage.getByText(/Podle pracovní kopie, revize \d+\. Po/).waitFor({ timeout: 30000 });
    const elsewhere = coverage.getByRole("group", { name: "Co AIA čte jako výzkumné otázky mimo tento seznam" });
    await elsewhere.waitFor({ timeout: 30000 });
    assert.equal(await elsewhere.locator(":scope > ul > li").count(), 2, `plan @${width}: the traced research questions`);
    await elsewhere.locator(":scope > ul > li").first().getByText(/pokryto|částečně|mezera|neznámé/).first().waitFor({ timeout: 30000 });
    // DSN12: the hypotheses are a section of their own, each a Lead target, with no verdict said.
    const hypotheses = page.getByRole("region", { name: "Hypotézy" });
    assert.equal(await hypotheses.locator('[data-aia^="hypothesis:"]').count(), 2, `plan @${width}: the hypotheses' section`);
    await noOverflow(`plan @${width}`);
    assert.equal(writes.filter((w) => w.path.endsWith("/design/revisions")).length, planSubmitsBefore, `plan @${width}: Návrh's coverage submitted a design`);
    assert.equal(writes.filter((w) => w.path.endsWith("/workspace/content")).length, planSavesBefore, `plan @${width}: reading Návrh's coverage saved the working copy`);
    // WCAG 2.5.8: a remove control on Návrh is at least 24 × 24 px (a set item's × was 12 × 20).
    const small = await page.evaluate(() => [...document.querySelectorAll('button[aria-label^="Odebrat "]')]
      .map((e) => [e.getAttribute("aria-label"), e.getBoundingClientRect()])
      .filter(([, r]) => r.width > 0 && (r.width < 24 || r.height < 24))
      .map(([name, r]) => `${name} ${Math.round(r.width)}×${Math.round(r.height)}`));
    assert.deepEqual(small, [], `plan @${width}: remove targets under 24 px`);
    await coverage.screenshot({ path: join(out, `${width}-plan-coverage.png`) });
    await hypotheses.screenshot({ path: join(out, `${width}-plan-hypotheses.png`) });
  }
  check("Návrh shows the coverage of every research question the server reads and the hypotheses as their own section at 1440, 1100, 768 and 390, nothing saved, no overflow");

  // Cílová skupina names what the Lead can focus (data-aia, the artifact contract's row `audience`):
  // the description, the filters, each factor by its catalogue id and the preview, at every width.
  const aud = fixtures.audience;
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + `/app/clients/${aud.client}/research/${aud.study}/audience`);
    await page.locator('[data-aia="audience:definition"]').waitFor({ timeout: 30000 });
    for (const target of ["audience:definition", "audience:filters", "audience:preview"]) {
      await page.locator(`[data-aia="${target}"]`).waitFor({ timeout: 30000 });
      assert.equal(await page.locator(`[data-aia="${target}"]`).count(), 1, `${target} @${width}`);
    }
    // Every stored filter's chip carries its target, whichever factors the editor shows.
    const chips = await page.getByRole("button", { name: /^Odebrat filtr/ }).count();
    assert(chips > 0, `the audience fixture stores filters (fixture_project.py), so a chip shows @${width}`);
    assert.equal(await page.locator('[data-aia^="audience:filter:"]').count(), chips, `a target per stored filter @${width}`);
    // A chip's remove button is a 24 px target at every width (WCAG 2.5.8; it was 15 x 16).
    for (const box of await page.getByRole("button", { name: /^Odebrat filtr/ }).evaluateAll((els) => els.map((e) => e.getBoundingClientRect()))) {
      assert(box.width >= 24 && box.height >= 24, `remove-filter target ${box.width} x ${box.height} @${width}`);
    }
    await noOverflow(`audience @${width}`);
    await shot(`${width}-audience`);
  }
  check("Cílová skupina names its description, filters, factors and preview at 1440, 1100, 768 and 390; each filter's remove button a 24 px target");

  // Vzorek (artifact-sample SMP6): read only, at every width. Its forecast is the server's, labelled
  // a forecast, on the revision it was read on; nothing on it sets n or starts anything.
  const submitsBefore = writes.filter((w) => /\/design\/revisions$/.test(w.path)).length;
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("dimensions") + "#sample");
    const sample = page.locator("[data-sample-view]");
    await sample.waitFor({ timeout: 30000 });
    const forecast = page.getByRole("region", { name: "Kolik dat bude za čísly" });
    await forecast.getByText("odhad před během, ne výsledek").waitFor();
    // The journey's identity edits, so Vzorek reads readiness on the revision its copy submits to:
    // the empty state ("odhad není") or a failed read is a failure here, never a pass.
    await forecast.getByText(/Podle pracovní kopie|odhad není|nepodařilo načíst/).first().waitFor({ timeout: 30000 });
    assert.equal(await forecast.getByText(/Podle pracovní kopie, revize \d+/).count(), 1, `Vzorek's forecast read on the working revision @${width}`);
    // Read only: no editable surface of any kind, and every button one of its navigation links.
    const editable = "input, select, textarea, [contenteditable]:not([contenteditable='false']), [role=slider], [role=spinbutton], [role=textbox], [role=checkbox], [role=radio], [role=switch], [role=combobox]";
    assert.equal(await sample.locator(editable).count(), 0, `Vzorek has no editable control @${width}`);
    // The section links, the stage each readiness check is fixed on, and the way on to Sběr dat.
    const NAVIGATION = new Set(["Upravit v Dimenzích", "Upravit cílovou skupinu", "Sociomapa", "Změnit ve Spuštění", "Pokračovat na Sběr dat", "Dimenze", "Cílová skupina", "Dotazník"]);
    // A link card reads its title, then what is set there: the title names where it goes.
    const buttons = (await sample.locator("button, [role=button]").allInnerTexts()).map((b) => b.trim().split("\n")[0].trim());
    assert.deepEqual(buttons.filter((b) => !NAVIGATION.has(b)), [], `Vzorek's buttons only navigate @${width}`);
    for (const id of ["sample:size", "sample:n", "sample:forecast", "sample:forecast:support", "sample:forecast:outlook"]) {
      assert.equal(await sample.locator(`[data-aia="${id}"]`).count(), 1, `${id} @${width}`);
    }
    // Připravenost ke spuštění (SMP4): the server's checks on the working copy, each its own target.
    const ready = page.getByRole("region", { name: "Připravenost ke spuštění" });
    await ready.locator('[data-aia^="sample:ready:"]').first().waitFor({ timeout: 30000 });
    assert.equal(await ready.getByText("nepodařilo načíst").count(), 0, `Vzorek's readiness read @${width}`);
    await noOverflow(`sample @${width}`);
    await sample.screenshot({ path: join(out, `${width}-sample.png`) });
  }
  // Reading readiness on the working copy submits no Design Revision (working-copy-edit-ops WCE7b).
  assert.equal(writes.filter((w) => /\/design\/revisions$/.test(w.path)).length, submitsBefore, "a Vzorek visit submits no design");
  // Its links open the stages where things are set.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Pokračovat na Sběr dat" }).click();
  await navStage("Sběr dat", true).waitFor();
  check("Vzorek: size, the server's forecast and readiness on the working copy at 1440, 1100, 768 and 390, nothing submitted, read only, no overflow; Sběr dat one click away");

  // Spuštění (artifact-fieldwork F-FLD-3, F-FLD-4, F-FLD-5): every link of the stage is the input
  // standard's touch target (44 px at a phone's width, 32 px from 640 px; I11), and "Co spustíte"
  // puts each value under its label on a narrow card, never a sliver beside it.
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("run"));
    const edit = page.getByRole("link", { name: "Upravit", exact: true });
    await edit.first().waitFor({ timeout: 60000 });
    assert((await edit.count()) > 0, `Co spustíte names its stages @${width}`);
    const floor = width < 640 ? 44 : 32;
    // Every shown link of the stage's own but one inside a sentence, which WCAG 2.5.8 exempts: a link
    // with text of its parent's beside it.
    const links = await page.locator("#artbody a").evaluateAll((els) => els
      .filter((el) => el.getClientRects().length)
      .filter((el) => ![...el.parentElement.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()))
      .map((el) => ({ text: el.textContent.trim(), height: el.getBoundingClientRect().height })));
    const small = links.filter((l) => l.height < floor);
    assert(links.length && !small.length, `Spuštění's links are ${floor} px targets @${width}: ${small.map((l) => `${l.text} ${l.height}`).join(", ")}`);
    if (width === 390) {
      const share = await page.locator("dl:has(a) dd:not(:has(a))").evaluateAll((dds) =>
        dds.map((dd) => dd.getBoundingClientRect().width / dd.closest("dl").getBoundingClientRect().width));
      // The link keeps its column beside them; the label no longer does.
      assert(share.length && share.every((w) => w >= 0.7), `Co spustíte's values take most of the card @390: ${share}`);
    }
    await noOverflow(`run @${width}`);
    await shot(`${width}-run`);
  }
  check("Spuštění's links are touch targets, Co spustíte stacks on a phone, at 1440, 1100, 768 and 390, no overflow");

  // The stages' docks name no classic step: the navigator names the neighbours (DIM-F4). Last,
  // because a visit to Návrh submits a Design Revision that Vzorek's forecast then reads (WCE7b).
  for (const slug of ["plan", "questionnaire", "audience", "dimensions"]) {
    await page.goto(base + stagePath(slug));
    await page.locator("[data-workbench]").waitFor();
    await page.locator("#artbody").getByRole("button").first().waitFor({ timeout: 60000 });
    const classic = await page.locator("#artbody a").evaluateAll((as) => as.map((a) => a.textContent?.trim() ?? "").filter((t) => /^\d\. /.test(t)));
    assert.deepEqual(classic, [], `${slug}: no classic "N. stage" link in the artifact`);
  }
  check("no stage's dock names a classic step inside the workbench");

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, writes, switches }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
