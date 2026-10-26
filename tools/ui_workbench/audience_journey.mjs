#!/usr/bin/env node
/**
 * The audience step from AIA's population, in a browser (panel-grounded-respondents 6f).
 *
 *   node tools/ui_workbench/audience_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 *
 * Needs `make ui-workbench` (whose API holds the fictional LIVE population of
 * fictional_population.py) and `make ui-fixtures`. It starts a new research study through
 * the API and then, in the browser, on Cílová skupina:
 *
 *   * ČR 18+ → Zúžit cílovou skupinu: no "V AIA zatím není" on the filters; the factor
 *     editor lists the population's factors; choosing a region and an age range saves
 *     exactly those filters (an empty upper bound is left out, OI-50), read back after a
 *     reload;
 *   * Proveditelnost: asked again after every change, no button; the API counts the fictional
 *     population and the step says how many people the filters select and that N=300 can be drawn;
 *   * Speciální skupiny: the built-in subpanels; one is chosen and saved as its filter, one
 *     the population's policy refuses cannot be; special panels still say they are not in AIA.
 *
 * Every request is recorded. The journey fails on any request to a path the unit served,
 * on a 502 from the facade and on any page error. Nothing is sent to a model.
 * Screenshots go to --out (default tmp/ui-workbench/shots/audience-<time>).
 */
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "../..");
const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : fallback;
};
const FACADE = arg("facade", "http://127.0.0.1:8780");
const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const OUT = arg("out", join(REPO, "tmp/ui-workbench/shots", `audience-${stamp}`));
const OPERATOR = "workbench@example.invalid";
const UNIT_PATH = /^\/(api\/(?!v1\/)|files\/|artifacts\/|project-attachments\/|brand\/|fullsim-arena|status$|health$|classic|interface-document)/;

async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  for (const from of [REPO, join(REPO, "apps/web")]) {
    try {
      return await import(pathToFileURL(require.resolve("playwright", { paths: [from] })).href);
    } catch { /* next */ }
  }
  const root = execSync("npm root -g", { encoding: "utf8" }).trim();
  return await import(pathToFileURL(join(root, "playwright/index.mjs")).href);
}

function fail(message) {
  console.error(`audience journey: FAIL ${message}`);
  process.exit(1);
}
const ok = (what) => console.log(`audience journey: ok   ${what}`);

async function api(method, path, body) {
  const r = await fetch(`${FACADE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${OPERATOR}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) fail(`${method} ${path} answered ${r.status}: ${await r.text()}`);
  return r.json();
}

const catalogue = await api("GET", "/api/v1/population/audience-catalogue");
ok(`the API serves ${catalogue.version_label}'s catalogue: ${catalogue.factors.length} factors, ${catalogue.subpanels.length} subpanels`);
const studies = JSON.parse(readFileSync(join(REPO, "tmp/ui-workbench/studies.json"), "utf8"));
const client = Object.values(studies)[0]?.client;
if (!client) fail("no workbench fixtures (run make ui-fixtures)");
const study = await api("POST", `/api/v1/clients/${encodeURIComponent(client)}/studies`, { name: `Cílová skupina ${stamp}`, kind: "RESEARCH" });
const stage = (name) => `${FACADE}/app/clients/${encodeURIComponent(client)}/research/${encodeURIComponent(study.study_id)}/${name}`;
const content = () => api("GET", `/api/v1/studies/${study.study_id}/workspace/content`);

mkdirSync(OUT, { recursive: true });
const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();
const errors = [];
const requests = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => requests.push({ method: r.method(), url: r.url() }));
const bad = [];
page.on("response", (r) => { if (r.status() === 502) bad.push(r.url()); });
// Each preview's time to its answer (AUD9 asks one per change): measured here, on develop before merge.
const previewMs = [];
page.on("requestfinished", (r) => { if (r.url().endsWith("/population/audience-preview")) previewMs.push(r.timing().responseEnd); });
const shot = (name) => page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
const saved = () => page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/workspace/content`) && r.request().method() === "PUT" && r.ok(), { timeout: 30000 });
const text = async (t, what) => page.getByText(t).first().waitFor({ timeout: 60000 }).catch(async () => { await shot(`missing-${what}`); fail(`${what}: "${t}" not shown`); });

// 1. ČR 18+, narrowed: the factor editor from the population, filters saved as chosen.
await page.goto(stage("audience"), { waitUntil: "load", timeout: 180000 });
await page.getByRole("radio", { name: /Audience AI Analytics/ }).click({ timeout: 120000 });
await page.getByRole("radio", { name: /Česká populace \(\+18\)/ }).click({ timeout: 60000 });
await page.getByRole("radio", { name: /Zúžit cílovou skupinu/ }).click({ timeout: 60000 });
await text(`z populace ${catalogue.version_label}`, "the catalogue's version");
if (await page.getByRole("radio", { name: /Zúžit cílovou skupinu/ }).getByText("V AIA zatím není").count()) fail("the filters still say they are not in AIA");
ok("Cílová skupina: the filters come from AIA's population, not 'V AIA zatím není'");
const region = catalogue.factors.find((f) => f.id === "kraj")?.values?.[0]?.value;
if (!region) fail("the catalogue has no region values");
const regionSave = saved();
const regionName = new RegExp(region.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
await page.getByRole("button", { name: regionName }).first().click();
await regionSave;
const ageFrom = page.getByRole("spinbutton", { name: "Věk od" });
await ageFrom.fill("30");
const ageSave = saved();
await ageFrom.blur();
await ageSave;
const stored = (await content()).content.audience.filters;
if (JSON.stringify(stored) !== JSON.stringify({ kraj: [region], vek: { min: 30 } })) fail(`the saved filters are ${JSON.stringify(stored)}`);
ok(`Cílová skupina: region and age saved as chosen, the empty bound left out: ${JSON.stringify(stored)}`);
await page.reload({ waitUntil: "load" });
await text("Vybrané filtry:", "the chips after a reload");
ok("Cílová skupina: the filters read back after a reload");
await shot("1-filters");

// 1b. The age range as two bounded steppers (input-interactions I2, audit B6), at four widths.
const ageTo = page.getByRole("spinbutton", { name: "Věk do" });
for (const width of [1440, 1100, 768, 390]) {
  await page.setViewportSize({ width, height: 1000 });
  await ageFrom.waitFor({ timeout: 30000 });
  if (!(await ageTo.isVisible())) fail(`${width} px: the range's upper stepper is not shown`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) fail(`${width} px: the page overflows by ${overflow} px`);
  const clear = await page.getByRole("button", { name: "Bez omezení: zrušit mez Věk od" }).boundingBox();
  if (!clear || clear.width < 24 || clear.height < 24) fail(`${width} px: "Bez omezení" is a ${clear?.width}x${clear?.height} target`);
}
const putsBefore = requests.filter((r) => r.method === "PUT" && r.url.endsWith("/workspace/content")).length;
await ageTo.fill("999");
await ageTo.blur();
if ((await ageTo.getAttribute("aria-invalid")) !== "true") fail("an age above the population's range was not refused at the field");
await page.waitForTimeout(2500); // the study store saves 1.8 s after a change
if (requests.filter((r) => r.method === "PUT" && r.url.endsWith("/workspace/content")).length !== putsBefore) fail("a refused age was saved");
if (JSON.stringify((await content()).content.audience.filters.vek) !== JSON.stringify({ min: 30 })) fail("the stored age range moved");
await ageTo.press("Escape");
ok("Cílová skupina: the age range is two steppers at 1440/1100/768/390 without overflow; 999 is refused at the field and not saved");
await shot("1b-range-390");
await page.setViewportSize({ width: 1440, height: 1100 });

// 2. Proveditelnost: counted by the API, through the run's own sampler, without a click (AUD9).
const previews = requests.filter((r) => r.method === "POST" && r.url.endsWith("/population/audience-preview")).length;
if (!previews) fail("Proveditelnost was not asked as the filters changed");
const figures = page.locator('[data-aia="audience:preview"] [aria-live="polite"]');
await figures.and(page.locator('[aria-busy="false"]')).waitFor({ timeout: 120000 });
await text("lidí z", "the preview's count");
const drawable = (await figures.innerText()).match(/Lze vytáhnout\s+(Ano|Těsně)/);
if (!drawable) fail(`the sampler should draw N=300 from the audience: ${await figures.innerText()}`);
if (await page.getByRole("button", { name: "Ověřit proveditelnost" }).count()) fail("Proveditelnost still waits for a button");
ok(`Proveditelnost: ${previews} previews asked as the filters changed, no button; the sampler's verdict for N=300 is ${drawable[1]}`);
await shot("2-preview");

// 2b. The factor groups and values chosen, never typed (input-interactions I3, audit B7, B8), at four widths.
const regionChip = page.getByRole("button", { name: regionName }).first();
if ((await regionChip.getAttribute("aria-pressed")) !== "true") fail(`${region} is not shown as chosen`);
for (const width of [1440, 1100, 768, 390]) {
  await page.setViewportSize({ width, height: 1000 });
  await page.getByRole("radiogroup", { name: "Skupina faktorů" }).waitFor({ timeout: 30000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) fail(`${width} px: the page overflows by ${overflow} px`);
  const box = await regionChip.boundingBox();
  const least = width < 640 ? 44 : 24;
  if (!box || box.height < least) fail(`${width} px: the value chip is ${box?.height} px tall, under ${least}`);
}
await page.setViewportSize({ width: 1440, height: 1100 });
ok("Cílová skupina: factor groups and values are chips at 1440/1100/768/390, 44 px tall on a phone, without overflow");

// 3. Speciální skupiny: the built-in subpanels.
const presetSave = saved();
await page.getByRole("radio", { name: /Speciální skupiny/ }).click();
await presetSave;
// OI-51 (a): a preset change starts afresh; the region and age chosen above are not carried over.
const afterPreset = (await content()).content.audience;
if (JSON.stringify(afterPreset.filters) !== "{}" || afterPreset.builtin_subpanel) fail(`Speciální skupiny kept the previous audience: ${JSON.stringify({ filters: afterPreset.filters, builtin_subpanel: afterPreset.builtin_subpanel })}`);
ok("Speciální skupiny: the region and age chosen before are cleared, not carried into the new preset (OI-51 (a))");
const usable = catalogue.subpanels.find((s) => s.usable === true);
const refused = catalogue.subpanels.find((s) => s.usable === false);
if (!usable || !refused) fail("the fictional population should make one subpanel usable and one not");
const nameOf = (name) => new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s|$)`);
if (!(await page.getByRole("radio", { name: nameOf(refused.name) }).isDisabled())) fail(`${refused.name} is offered though the policy refuses it`);
const subpanelSave = saved();
await page.getByRole("radio", { name: nameOf(usable.name) }).click();
await subpanelSave;
const audience = (await content()).content.audience;
if (audience.builtin_subpanel !== usable.key || JSON.stringify(audience.filters) !== JSON.stringify(usable.filters)) fail(`the subpanel saved ${JSON.stringify(audience)}`);
await text("speciální panely a vlastní publikum", "special panels not in AIA");
ok(`Speciální skupiny: ${usable.name} saved as its filter ${JSON.stringify(usable.filters)}; ${refused.name} refused by policy`);
await shot("3-subpanels");

// 3b. The subpanels under a search (input-interactions I3, audit B9), at four widths.
const subpanels = page.getByRole("radiogroup", { name: "Vestavěné subpanely" });
const search = page.getByLabel("Hledat subpanel");
for (const width of [1440, 1100, 768, 390]) {
  await page.setViewportSize({ width, height: 1000 });
  await search.waitFor({ timeout: 30000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) fail(`${width} px: the page overflows by ${overflow} px`);
}
await page.setViewportSize({ width: 1440, height: 1100 });
await search.fill("žádný takový subpanel");
const left = await subpanels.getByRole("radio").count();
const chosenLeft = await subpanels.getByRole("radio", { checked: true }).count();
if (left !== 1 || chosenLeft !== 1) fail(`a search that matches nothing should leave only the chosen ${usable.name}: ${left} shown`);
await text("Hledání odpovídá 0 z", "the search's count");
await search.fill("");
ok(`Speciální skupiny: ${catalogue.subpanels.length} subpanels under a search at 1440/1100/768/390 without overflow; a search that matches nothing keeps the chosen one and says 0`);

// 4. Najít ideální skupinu: Discover's two values edited in place (input-interactions I1, audit B11), at four widths.
await page.getByRole("radio", { name: /Česká populace \(\+18\)/ }).click();
const strategySave = saved(); // the strategy's own save lands before the field's is awaited
await page.getByRole("radio", { name: /Najít ideální skupinu z výsledků/ }).click();
await strategySave;
const SUCCESS = "Co má ideální člověk udělat / jak poznáme úspěch?";
const successValue = page.getByRole("button", { name: /^Upravit: Co má ideální člověk/ });
for (const width of [1440, 1100, 768, 390]) {
  await page.setViewportSize({ width, height: 1000 });
  await successValue.waitFor({ timeout: 30000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) fail(`${width} px: the page overflows by ${overflow} px`);
}
await page.setViewportSize({ width: 1440, height: 1100 });
await successValue.click();
const successField = page.getByRole("textbox", { name: SUCCESS });
await successField.fill("Zahodí to");
await successField.press("Escape");
if (await successField.count()) fail("Esc did not close the success criterion's field");
if ((await successValue.innerText()).includes("Zahodí to")) fail("Esc kept the typed value");
await successValue.click();
await successField.fill("Koupí a doporučí známým");
const discoverSave = saved();
await successField.press("Control+Enter");
await discoverSave;
if ((await content()).content.audience.success_definition !== "Koupí a doporučí známým") fail("the success criterion was not saved as typed");
ok("Najít ideální skupinu: the success criterion edited in place at 1440/1100/768/390 without overflow; Esc restores, Ctrl+Enter saves");
await shot("4-discover");

await browser.close();
const toUnit = requests.filter((r) => { try { return UNIT_PATH.test(new URL(r.url).pathname); } catch { return false; } });
writeFileSync(join(OUT, "requests.json"), JSON.stringify(requests, null, 1));
if (toUnit.length) fail(`requests to the unit's paths: ${toUnit.map((r) => `${r.method} ${r.url}`).join(" | ")}`);
if (bad.length) fail(`502 responses: ${bad.join(" | ")}`);
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
ok(`${requests.length} requests, none to a path of the unit, no 502`);
if (previewMs.length) {
  const sorted = [...previewMs].sort((a, b) => a - b);
  const p95 = sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1)];
  ok(`${previewMs.length} previews; median ${Math.round(sorted[Math.floor(sorted.length / 2)])} ms, p95 ${Math.round(p95)} ms on this machine`);
}
console.log(`audience journey: PASS (screenshots and requests.json in ${OUT})`);
