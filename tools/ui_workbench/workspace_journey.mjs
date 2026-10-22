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
 *     there, read back from AIA -- adds an objective, reloads -- it is one Lead target --
 *     rewords it in place, reloads -- it is still one, in its new words -- and downloads the
 *     file through the study;
 *   * Dotazník: downloads AIA's template, imports that same file, reloads -- the
 *     imported questionnaire is still there; puts its first question on the 1–10 preset
 *     with a label on every point, reloads -- the range and the ten labels are still there,
 *     and the editor fits at 390 px (input-interactions 3b2);
 *   * Cílová skupina: own audiences and Speciální skupiny say they are not in AIA;
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
// The paths the 18.6.6 unit served on the product hostname (its @unit matcher until ADR
// 0018 decision 5, /classic and its document): now the web client's, never the unit's.
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
const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
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
// A save of the working copy; with `holding`, only one whose body carries that text, so a save
// already in flight for something else does not stand in for it.
const saved = (holding) => page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/workspace/content`) && r.request().method() === "PUT" && r.ok() && (!holding || (r.request().postData() ?? "").includes(holding)), { timeout: 30000 });
const text = async (t, what) => page.getByText(t).first().waitFor({ timeout: 60000 }).catch(async () => { await shot(`missing-${what}`); fail(`${what}: "${t}" not shown`); });

// 1. Zadání: a goal, a file, a reload, a download.
await page.goto(stage("brief"), { waitUntil: "load", timeout: 180000 });
const goal = page.getByRole("textbox", { name: "Cíl výzkumu", exact: true });
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
if ((await page.getByRole("textbox", { name: "Cíl výzkumu", exact: true }).inputValue()) !== GOAL) fail("the goal did not survive a reload");
ok("Zadání: goal and attachment read back from AIA after a reload");
await text("B · odvozené od klienta", "the attachment's data class");
ok("Zadání: the attachment shows the class the server's rule gives it (BRF3)");

// Cíle (artifact-brief BRF2/BRF6): an objective added in the list, read back after a reload as a
// Lead target, then reworded in place.
const OBJECTIVE = "Zjistit, kdo kampaň zaznamenal (fiktivní).";
const objectiveSave = saved(OBJECTIVE);
await page.getByRole("button", { name: "Přidat cíl" }).click();
// An empty new objective is said as a goal to write, not a name (audit, F-BRF-3).
await page.getByRole("textbox", { name: "Přidat cíl" }).press("Enter");
await text("Napište cíl.", "the empty objective's words");
await page.getByRole("textbox", { name: "Přidat cíl" }).fill(OBJECTIVE);
await page.getByRole("textbox", { name: "Přidat cíl" }).press("Enter");
await objectiveSave;
await page.reload({ waitUntil: "load" });
await text(OBJECTIVE, "the objective after a reload");
if ((await page.locator("[data-aia^='objective:']").count()) !== 1) fail("the objective is not one Lead target after a reload");
const rewordSave = saved(`${OBJECTIVE} Upřesněno.`);
await page.getByRole("button", { name: /^Upravit: Cíl 1/ }).click();
await page.getByRole("textbox", { name: "Cíl 1" }).fill(`${OBJECTIVE} Upřesněno.`);
await page.getByRole("textbox", { name: "Cíl 1" }).press("Control+Enter");
await rewordSave;
await page.reload({ waitUntil: "load" });
await text(`${OBJECTIVE} Upřesněno.`, "the reworded objective after a reload");
// In place: still one objective, and the old wording is gone rather than kept beside the new.
const rows = await page.locator("[data-aia^='objective:']").allInnerTexts();
if (rows.length !== 1 || !rows[0].includes("Upřesněno.")) fail(`the reword was not in place: ${JSON.stringify(rows)}`);
ok("Zadání: an objective added in the list, read back as one Lead target, reworded in place (BRF6)");
// Rozhodnutí, edited where it is shown (artifact-brief BRF2): open, type, Ctrl+Enter, saved, read back.
const DECISION = "Rozhodneme, zda změnit kampaň (fiktivní).";
await page.getByRole("button", { name: /^Upravit: Jaké rozhodnutí uděláte/ }).click();
const decisionSave = saved(DECISION);
await page.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }).fill(DECISION);
await page.getByRole("textbox", { name: "Jaké rozhodnutí uděláte" }).press("Control+Enter");
await decisionSave;
await page.reload({ waitUntil: "load" });
await text(DECISION, "the decision after a reload");
ok("Zadání: Rozhodnutí edited in place and read back from AIA after a reload (BRF2)");
const [download] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.getByRole("button", { name: `Stáhnout přílohu ${FILE.name}` }).click()]);
const fileBack = readFileSync(await download.path(), "utf8");
if (fileBack !== FILE.body) fail(`the downloaded file differs: ${JSON.stringify(fileBack)}`);
ok("Zadání: the file downloads through the study, byte for byte");

// An empty file is refused before it is sent, in Czech, never the API's English (audit).
const attachesBefore = requests.filter((r) => r.url.endsWith("/workspace/attachments") && r.method === "POST").length;
await page.locator('input[type="file"][aria-label="Soubory k zadání"]').setInputFiles({ name: "prazdny.txt", mimeType: "text/plain", buffer: Buffer.alloc(0) });
await text("Nepodařilo se uložit · soubor je prázdný", "the empty file's refusal in Czech");
if (requests.filter((r) => r.url.endsWith("/workspace/attachments") && r.method === "POST").length !== attachesBefore) fail("an empty file was sent");
ok("Zadání: an empty file refused before it is sent, said in Czech");
// Removing a material happens at once, with Vrátit (input-interactions I6, audit A28).
// The removal saves first (Vrátit stays offered for 8 s, past the 1.8 s save), then the restore.
const removedSave = saved();
await page.getByRole("button", { name: `Odebrat ${FILE.name}` }).click();
await removedSave;
const restored = saved();
await page.getByRole("button", { name: "Vrátit" }).click();
await restored;
await page.reload({ waitUntil: "load" });
await text(FILE.name, "the attachment after Vrátit and a reload");
ok("Zadání: a removed attachment comes back with Vrátit, saved (A28)");
// A link that is not http(s) is said at its field and checked again as it is typed (I9, audit A26).
const linkField = page.getByRole("textbox", { name: "Odkaz" });
await linkField.fill("example.test");
await linkField.press("Enter");
if ((await linkField.getAttribute("aria-invalid")) !== "true") fail("a link that is not http(s) is not marked at its field");
await shot("brief-link-problem");
await linkField.fill("https://example.test/fiktivni");
if ((await linkField.getAttribute("aria-invalid")) !== null) fail("the link's problem stays after a valid address is typed");
const linkSave = saved();
await linkField.press("Enter");
await linkSave;
await text("https://example.test/fiktivni", "the added link");
ok("Zadání: a link's problem said at its field, cleared as it is typed, the link added (A26)");
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
await text("Načteno: 2 otázky · 1 sledovaná sada", "the import's summary");
await imported;
await page.reload({ waitUntil: "load" });
await text("2 otázky · 1 sledovaná sada", "the imported questionnaire after a reload");
ok("Dotazník: the template imports in AIA and the questionnaire is read back after a reload");
await shot("2-questionnaire");

// 2b. Dotazník: a scale on the 1–10 preset with a label on every point (input-interactions 3b2),
// saved through the working copy and read back after a reload.
const POINTS = ["vůbec", "téměř vůbec", "velmi málo", "málo", "spíše málo", "spíše hodně", "hodně", "velmi hodně", "téměř zcela", "zcela"];
const card = () => page.locator('[id^="qedit_"]').first();
const scaleGroup = (what) => card().getByRole("radiogroup", { name: new RegExp(`^${what} Q1$`) });
const pointButton = (n) => card().getByRole("button", { name: new RegExp(`^Upravit: Popisek bodu ${n}(\\s|$)`) });
await card().getByRole("radiogroup", { name: "Typ" }).getByRole("radio", { name: "Škála" }).click({ timeout: 60000 });
await scaleGroup("Rozsah škály").getByRole("radio", { name: "1–10" }).click();
await scaleGroup("Popisky škály").getByRole("radio", { name: "Každý bod" }).click();
for (const [i, label] of POINTS.entries()) {
  await pointButton(i + 1).click();
  const field = card().getByRole("textbox", { name: `Popisek bodu ${i + 1}`, exact: true });
  await field.fill(label);
  await field.press("Enter");
}
await saved();
if (await card().locator("[data-scale-labels-left-out]").count()) fail("a fully labelled 1–10 scale says its labels are left out");
await page.reload({ waitUntil: "load" });
await scaleGroup("Rozsah škály").getByRole("radio", { name: "1–10", checked: true }).waitFor({ timeout: 60000 }).catch(() => fail("the 1–10 preset did not survive a reload"));
for (const [i, label] of POINTS.entries()) {
  const shown = (await pointButton(i + 1).textContent())?.trim() ?? "";
  if (!shown.startsWith(label) || shown.slice(label.length).trim() !== "") fail(`point ${i + 1} reads ${JSON.stringify(shown)} after a reload, not ${JSON.stringify(label)}`);
}
ok("Dotazník: a 1–10 scale with a label on every point is saved and read back after a reload");
await card().scrollIntoViewIfNeeded();
await card().screenshot({ path: join(OUT, "2b-scale-1440.png") });
await page.setViewportSize({ width: 390, height: 2000 });
await card().scrollIntoViewIfNeeded();
await card().screenshot({ path: join(OUT, "2b-scale-390.png") });
const wide = await card().evaluate((el) => el.scrollWidth > el.clientWidth + 1 || el.getBoundingClientRect().right > window.innerWidth + 1);
if (wide) fail("the scale editor overflows its card at 390 px");
ok("Dotazník: the scale editor fits at 390 px");
await page.setViewportSize({ width: 1440, height: 1100 });

// 3. Cílová skupina: what 18.6.6 computed from its panel says so.
await page.goto(stage("audience"), { waitUntil: "load", timeout: 120000 });
await page.getByRole("radio", { name: /Vlastní audience/ }).click({ timeout: 60000 });
await text("Nahrání a kontrolu vlastního datasetu dělala 18.6.6", "own audiences not in AIA");
ok("Cílová skupina: own audiences say they are not in AIA");
await shot("3-audience");

// 4. Dimenze: no panel factors; a request is a proposal to the client's knowledge.
await page.goto(stage("dimensions"), { waitUntil: "load", timeout: 120000 });
await text("Faktory společnosti v AIA zatím nejsou", "the society factors not in AIA");
await page.getByText("Potřebuji dimenzi, která v systému není").first().click();
await page.getByLabel("Název dimenze").fill("Vztah k ranním nápojům");
const proposed = page.waitForResponse((r) => r.url().endsWith(`/studies/${study.study_id}/knowledge-proposals`) && r.ok(), { timeout: 60000 });
await page.getByRole("button", { name: "Přidat jako požadavek" }).click();
await proposed;
await text("Návrh dimenze je ve Znalostech klienta", "the proposal toast");
await text("Vztah k ranním nápojům · čeká na schválení", "the request waiting beside the selection");
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
