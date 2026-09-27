#!/usr/bin/env node
/**
 * A research study's working content, end to end, in a browser, on AIA alone (ADR 0018):
 *
 *   node tools/ui_workbench/workspace_journey.mjs [--out DIR]
 *
 * Needs the workbench (`make ui-workbench`: AIA alone, routed like the develop
 * Caddyfile, so nothing of the 18.6.6 unit answers) and its fixtures (`make
 * ui-fixtures`, for the client). Signed in as the workbench operator, it starts a new
 * research study through the API and then, in the browser:
 *
 *   * Zadání: types a goal, attaches a file, reloads -- the goal and the file are still
 *     there, read back from AIA -- and downloads the file through the study;
 *   * Dotazník: downloads AIA's template, imports that same file, reloads -- the
 *     imported questionnaire is still there;
 *   * Cílová skupina: own audiences and Special Audience say they are not in AIA;
 *   * Dimenze: the panel's factors say they are not in AIA; a dimension request
 *     becomes a proposal to the client's knowledge.
 *
 * Every request the page makes is recorded. The journey fails on any request to a
 * path the unit served, on any 502 from the facade, and on any page error.
 * Screenshots go to --out (default tmp/ui-workbench/shots/workspace-<time>).
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
const OUT = arg("out", join(REPO, "tmp/ui-workbench/shots", `workspace-${stamp}`));
const OPERATOR = "workbench@example.invalid";
const GOAL = "Zjistit, zda by lidé kupovali fiktivní ranní nápoj.";
const FILE = { name: "zadani.txt", body: "Fiktivní zadání: ranní nápoj pro dospělé, test konceptu." };
// The paths the 18.6.6 unit serves (the Caddyfile's @unit, /classic and its document).
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
  console.error(`workspace journey: FAIL ${message}`);
  process.exit(1);
}
const ok = (what) => console.log(`workspace journey: ok   ${what}`);

async function api(method, path, body) {
  const r = await fetch(`${FACADE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${OPERATOR}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) fail(`${method} ${path} answered ${r.status}: ${await r.text()}`);
  return r.json();
}

const studies = JSON.parse(readFileSync(join(REPO, "tmp/ui-workbench/studies.json"), "utf8"));
const client = Object.values(studies)[0]?.client;
if (!client) fail("no workbench fixtures (run make ui-fixtures)");
const study = await api("POST", `/api/v1/clients/${encodeURIComponent(client)}/studies`, { name: `Bez 18.6.6 ${stamp}`, kind: "RESEARCH" });
const empty = await api("GET", `/api/v1/studies/${study.study_id}/workspace/content`);
if (empty.state !== "EMPTY") fail(`a new study's content is ${empty.state}, not EMPTY`);
ok(`started ${study.study_id}: its working content is EMPTY in AIA`);
const stage = (name) => `${FACADE}/app/clients/${encodeURIComponent(client)}/research/${encodeURIComponent(study.study_id)}/${name}`;

mkdirSync(OUT, { recursive: true });
const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
const page = await ctx.newPage();
const errors = [];
const requests = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => requests.push({ method: r.method(), url: r.url() }));
const bad = [];
page.on("response", (r) => { if (r.status() === 502) bad.push(r.url()); });
const shot = (name) => page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
const saved = () => page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/workspace/content`) && r.request().method() === "PUT" && r.ok(), { timeout: 30000 });
const text = async (t, what) => page.getByText(t).first().waitFor({ timeout: 60000 }).catch(async () => { await shot(`missing-${what}`); fail(`${what}: "${t}" not shown`); });

// 1. Zadání: a goal, a file, a reload, a download.
await page.goto(stage("brief"), { waitUntil: "load", timeout: 180000 });
const goal = page.getByPlaceholder(/Co chcete zjistit/);
await goal.waitFor({ timeout: 120000 });
const firstSave = saved();
await goal.fill(GOAL);
await firstSave;
ok("Zadání: the goal is saved in AIA");
const upload = page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/workspace/attachments`) && r.status() === 201, { timeout: 60000 });
await page.locator('input[type="file"][aria-label="Soubory k zadání"]').setInputFiles({ name: FILE.name, mimeType: "text/plain", buffer: Buffer.from(FILE.body) });
await upload;
await text("text načten", "the attachment's text");
await saved();
ok("Zadání: the file is kept in AIA storage and its record saved");
await page.reload({ waitUntil: "load" });
await text(FILE.name, "the attachment after a reload");
if ((await page.getByPlaceholder(/Co chcete zjistit/).inputValue()) !== GOAL) fail("the goal did not survive a reload");
ok("Zadání: goal and attachment read back from AIA after a reload");
const [download] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.getByRole("button", { name: `Stáhnout přílohu ${FILE.name}` }).click()]);
const fileBack = readFileSync(await download.path(), "utf8");
if (fileBack !== FILE.body) fail(`the downloaded file differs: ${JSON.stringify(fileBack)}`);
ok("Zadání: the file downloads through the study, byte for byte");
await shot("1-brief");

// 2. Dotazník: AIA's template, imported back.
await page.goto(stage("questionnaire"), { waitUntil: "load", timeout: 120000 });
await page.getByRole("button", { name: /Nahrát Excel/ }).click({ timeout: 60000 });
const [templateDownload] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.getByRole("button", { name: "Stáhnout XLSX šablonu" }).click()]);
const templatePath = join(OUT, "sablona.xlsx");
writeFileSync(templatePath, readFileSync(await templateDownload.path()));
if (!readFileSync(templatePath).subarray(0, 2).equals(Buffer.from("PK"))) fail("the template is not a workbook");
ok("Dotazník: AIA's template downloads");
const imported = saved();
await page.locator('input[type="file"][aria-label="Vyplněný XLSX / CSV"]').setInputFiles(templatePath);
await text("Načteno: 2 otázek · 1 sledovaných sad", "the import's summary");
await imported;
await page.reload({ waitUntil: "load" });
await text("2 otázek · 1 sledovaných sad", "the imported questionnaire after a reload");
ok("Dotazník: the template imports in AIA and the questionnaire is read back after a reload");
await shot("2-questionnaire");

// 3. Cílová skupina: what 18.6.6 computed from its panel says so.
await page.goto(stage("audience"), { waitUntil: "load", timeout: 120000 });
await page.getByRole("button", { name: /Vlastní audience/ }).click({ timeout: 60000 });
await text("Nahrání, kontrolu a preflight vlastního datasetu dělala 18.6.6", "own audiences not in AIA");
ok("Cílová skupina: own audiences say they are not in AIA");
await shot("3-audience");

// 4. Dimenze: no panel factors; a request is a proposal to the client's knowledge.
await page.goto(stage("dimensions"), { waitUntil: "load", timeout: 120000 });
await text("Faktory panelu v AIA zatím nejsou", "the panel factors not in AIA");
await page.getByText("Potřebuji dimenzi, která v systému není").first().click();
await page.getByLabel("Název dimenze").fill("Vztah k ranním nápojům");
const proposed = page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/knowledge-proposals`) && r.ok(), { timeout: 60000 });
await page.getByRole("button", { name: "Přidat jako požadavek" }).click();
await proposed;
await text("Návrh dimenze je ve Znalostech klienta", "the proposal toast");
ok("Dimenze: a dimension request became a proposal to the client's knowledge");
await shot("4-dimensions");

await browser.close();
const toUnit = requests.filter((r) => { try { return UNIT_PATH.test(new URL(r.url).pathname); } catch { return false; } });
writeFileSync(join(OUT, "requests.json"), JSON.stringify(requests, null, 1));
if (toUnit.length) fail(`requests to the unit's paths: ${toUnit.map((r) => `${r.method} ${r.url}`).join(" | ")}`);
if (bad.length) fail(`502 responses: ${bad.join(" | ")}`);
if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
ok(`${requests.length} requests, none to a path of the unit, no 502`);
console.log(`workspace journey: PASS (screenshots and requests.json in ${OUT})`);
