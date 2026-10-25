#!/usr/bin/env node
/** Zpráva in the report editor, in a real browser (artifact-report RPT8d), against the stand-in
 * Document Server (report_editor_standin.py): no ONLYOFFICE runs, its api.js is a stand-in this
 * journey serves for the fictional origin, and a save is made as a Document Server makes one -- the
 * DOCX written where the API's fetcher reads it, the callback posted, signed. Start the workbench
 * with the editor on, write the fixtures and finish one research run, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true AIA_WORKBENCH_REPORT_EDITOR=true python3 tools/ui_workbench/workbench.py up
 *   make ui-fixtures && make ui-research
 *   node tools/ui_workbench/report_editor_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR] [--fixture persona]
 * Local fictional identity only. It checks, at 1440, 1100 and 768 px the editor in edit mode and at
 * 390 px in view mode, with the doc bar naming the version on screen and no page overflow; then, at
 * 1440 px: an edit started holds the approval off whatever the editor says it saved, until AIA stores
 * the next koncept; that koncept's "Upraveno ručně" names the number changed; a save landing while
 * the question is open approves nothing; the newest koncept is approved as itself (newest_of_line),
 * and the report card downloads it; api.js loads only through a one-time ticket and under the
 * integrity the API names, and a swapped one runs nothing (RPT8e). Nothing paid starts.
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
const out = arg("out", join(repo, "tmp/ui-workbench/report-editor-journey"));
const fixture = arg("fixture", "persona"); // the study make ui-research ran
// The repository's Python, as workbench.py's _api_python() picks it: AIA_API_PYTHON, else the
// project venv, else python3 from PATH -- never a path assumed (AGENTS.md: tooling resolves its interpreter).
const venvPython = join(repo, ".venv/bin/python");
const python = process.env.AIA_API_PYTHON || (existsSync(venvPython) ? venvPython : "python3");
mkdirSync(out, { recursive: true });
const EDITOR_ORIGIN = "https://docs.workbench.invalid"; // report_editor_standin.ORIGIN
const IDENTITY = "workbench@example.invalid";

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
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
await context.addInitScript((identity) => {
  try {
    sessionStorage.setItem(
      "aia.session",
      JSON.stringify({ idToken: identity, refreshToken: "", expiresAt: 4102444800000, email: identity, subject: identity }),
    );
  } catch {
    /* about:blank between widths has no storage */
  }
}, IDENTITY);
// The stand-in Document Server, answering as docs.<hostname> does (the Caddyfile's @editor_script,
// RPT8e): the ticket's URL and api.js, each with CORS for AIA's origin with credentials, and nothing
// else. The real ticket redirects to api.js (test_docs_session_api.py); here it answers 204, because
// Playwright does not intercept the target of a redirect it fulfilled, and the page only spends it.
// `down`: unreachable. `swapped`: an api.js other than the pinned one, which its integrity refuses.
const API_JS = "/web-apps/apps/api/documents/api.js";
const standin = readFileSync(join(repo, "tools/ui_workbench/fixtures/report_editor/api.js"), "utf8");
const cors = { "Access-Control-Allow-Origin": new URL(base).origin, "Access-Control-Allow-Credentials": "true", Vary: "Origin" };
let down = false;
let swapped = false;
const spent = [];
await context.route(`${EDITOR_ORIGIN}/**`, (route) => {
  const url = new URL(route.request().url());
  if (down) return route.abort();
  if (url.pathname === "/__aia/session" && url.searchParams.get("ticket") && url.searchParams.get("next") === API_JS) {
    spent.push(url.href);
    return route.fulfill({ status: 204, headers: cors });
  }
  if (url.pathname === API_JS && !url.search) {
    return route.fulfill({ status: 200, contentType: "application/javascript", headers: cors, body: swapped ? `${standin}\n// swapped\n` : standin });
  }
  return route.abort();
});
const page = await context.newPage();
const errors = [], writes = [], checks = [], approvals = [], editReports = [];
page.on("pageerror", (e) => errors.push(String(e)));
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
  if (path.endsWith("/report/approve")) approvals.push(JSON.parse(r.postData() ?? "{}"));
});
// Each edit start the page reports (RPT8f), with what the server answered.
page.on("response", (r) => {
  if (new URL(r.url()).pathname.endsWith("/edits")) editReports.push({ body: JSON.parse(r.request().postData() ?? "{}"), status: r.status() });
});
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures[fixture] ?? {};
assert(client && study, `no workbench fixture "${fixture}" (run make ui-fixtures)`);
const api = async (path) => {
  const r = await fetch(`${base}/api/v1${path}`, { headers: { Authorization: `Bearer ${IDENTITY}` } });
  assert(r.ok, `GET ${path}: ${r.status}`);
  return r.json();
};
const listed = await api(`/studies/${study}/research/runs`);
const runs = Array.isArray(listed) ? listed : listed.runs ?? listed.items ?? [];
const run = runs.find((r) => (r.steps ?? []).some((s) => s.kind === "research_report" && s.status === "SUCCEEDED"));
assert(run, "no finished research run with its report (run make ui-research)");
const opened = await fetch(`${base}/api/v1/studies/${study}/research/runs/${run.run_id}/report/editor`, {
  method: "POST", headers: { Authorization: `Bearer ${IDENTITY}`, "Content-Type": "application/json" }, body: JSON.stringify({ mode: "view" }),
});
assert.notEqual(opened.status, 404, "the editor is off: start the workbench with AIA_WORKBENCH_REPORT_EDITOR=true");

const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};
const docbar = () => page.locator("[data-editor-docbar]");
const koncept = async () => Number((await docbar().locator("[data-editor-version]").innerText()).match(/Koncept (\d+)/)[1]);
/** One save, as the Document Server makes it, of the config the page was handed. */
const save = (text) => {
  const configFile = join(out, "editor-config.json");
  return page.evaluate(() => JSON.stringify(window.__standinEditor.config)).then((config) => {
    writeFileSync(configFile, config);
    const answer = execFileSync(python, [join(repo, "tools/ui_workbench/report_editor_standin.py"), "save",
      "--facade", base, "--study", study, "--run", run.run_id, "--config", configFile, "--text", text], { encoding: "utf8" });
    assert.deepEqual(JSON.parse(answer), { error: 0 }, `the save of "${text}" was stored`);
  });
};
const open = async (width) => {
  await page.setViewportSize({ width, height: 900 });
  await page.goto("about:blank"); // a fresh load per width: the same URL again is only a hash change
  await page.goto(`${base}/app/clients/${client}/research/${study}/results#report`);
  await page.locator('[data-report-editor="ready"]').waitFor({ timeout: 60000 });
  await docbar().locator("[data-editor-version]").waitFor({ timeout: 30000 });
};

try {
  for (const width of [1440, 1100, 768, 390]) {
    await open(width);
    const mode = width >= 768 ? "edit" : "view";
    assert.equal(await page.locator("[data-report-editor]").getAttribute("data-mode"), mode, `@${width}: the editor opens in ${mode} mode`);
    assert.equal(await page.evaluate(() => window.__standinEditor.config.editorConfig.mode), mode, `@${width}: the signed config says ${mode}`);
    assert.equal(await page.evaluate(() => typeof window.__standinEditor.config.token), "string", `@${width}: the config is handed over signed`);
    assert.equal(await page.evaluate(() => window.__standinEditor.basePath), `${EDITOR_ORIGIN}/web-apps/apps/`, `@${width}: api.js finds its base on the editor's origin (ONLYOFFICE's getBasePath)`);
    if (mode === "view") assert(await page.getByText("Jen ke čtení (úzká obrazovka)").isVisible(), "@390: read only, said");
    assert.equal(await page.getByRole("article", { name: "Koncept zprávy" }).count(), 0, `@${width}: the read-only draft gives way to the editor`);
    assert.match(await docbar().innerText(), /Koncept \d+/, `@${width}: the doc bar names the version on screen`);
    assert.equal(await page.locator("[data-report-docbar]").getByRole("button", { name: "Schválit pro interní použití" }).count(), 0, `@${width}: no approval of the composed draft while the editor shows the document`);
    await noOverflow(`editor @${width}`);
    await page.screenshot({ path: join(out, `${width}-editor.png`) });
  }
  check("the editor in edit mode at 1440, 1100 and 768 and in view mode at 390, from the config the API signed; the doc bar names the version on screen; no draft approval beside it; no overflow");

  await open(1440);
  const k = await koncept();
  // A person starts an edit; the editor then says the edit reached it. AIA has stored nothing.
  await page.evaluate(() => { window.__standinEditor.events.onDocumentStateChange({ data: true }); window.__standinEditor.events.onDocumentStateChange({ data: false }); });
  // (Koncept k may be approved already, by an earlier run of this journey: then no Schválit is shown.)
  await page.locator("[data-editor-unsaved]").waitFor({ timeout: 10000 });
  for (const button of await docbar().getByRole("button", { name: /^Schválit koncept/ }).all()) {
    assert(await button.isDisabled(), "an edit not stored holds the approval off, whatever the editor says it saved");
  }
  await page.screenshot({ path: join(out, "1440-edit-waiting.png") });
  check("an edit started holds the approval off after the editor's own \"saved\", until AIA stores a version");

  await save(`9${k},5 %`);
  const next = docbar().getByRole("button", { name: `Schválit koncept ${k + 1}` });
  await next.waitFor({ timeout: 30000 }); // the bar reads the line again every 10 s while it waits
  assert(await next.isEnabled(), "the stored koncept is approvable");
  assert.equal(await page.locator("[data-editor-unsaved]").count(), 0, "nothing waits once it is stored");
  await docbar().getByRole("button", { name: /^Upraveno ručně: 1 číslo/ }).click();
  assert.match(await docbar().locator("[data-editor-changes]").innerText(), new RegExp(`→ 9${k},5 %`), "Upraveno ručně names the number changed");
  await noOverflow("edited koncept @1440");
  await page.screenshot({ path: join(out, "1440-edited.png") });
  check("the save stored as the next koncept, named in the doc bar, its Upraveno ručně naming the number changed");

  // A save while the question is open approves nothing.
  await next.click();
  let dialog = page.getByRole("dialog");
  await dialog.waitFor({ timeout: 10000 });
  assert.match(await dialog.innerText(), new RegExp(`Schválit interní zprávu, koncept ${k + 1} \\(ART-[0-9a-f]{16}\\)\\?`), "the question names the version");
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Zrušit", "the safe choice holds the focus");
  await page.screenshot({ path: join(out, "1440-approval-dialog.png") });
  await save(`9${k + 1},5 %`);
  await dialog.getByRole("button", { name: `Schválit koncept ${k + 1}` }).click();
  await docbar().getByText(`Editor mezitím uložil koncept ${k + 2}; zkontrolujte jeho změny a schvalte znovu.`).waitFor({ timeout: 10000 });
  assert.equal(approvals.length, 0, "the older koncept was not approved");
  check("a save landing while the question is open approves nothing, said in words");

  // An edit started while the question is open approves nothing; its save, once stored, is the one approvable.
  await docbar().getByRole("button", { name: `Schválit koncept ${k + 2}` }).click();
  dialog = page.getByRole("dialog");
  await dialog.waitFor({ timeout: 10000 });
  // A person's edit comes after the last save: kept apart from it on AIA's clock, as typing would be.
  await page.waitForTimeout(200);
  await page.evaluate(() => window.__standinEditor.events.onDocumentStateChange({ data: true }));
  await dialog.getByRole("button", { name: `Schválit koncept ${k + 2}` }).click();
  await docbar().getByText("V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.").first().waitFor({ timeout: 10000 });
  assert.equal(approvals.length, 0, "the koncept without the new edit was not approved");
  await page.evaluate(() => window.__standinEditor.events.onDocumentStateChange({ data: false }));
  await save(`9${k + 2},5 %`); // the Document Server's save of that edit, its lastsave after it
  check("an edit started while the question is open approves nothing, until its save is stored");

  // The newest is approved as itself, the server checking it is still the newest.
  await docbar().getByRole("button", { name: `Schválit koncept ${k + 3}` }).click({ timeout: 30000 });
  dialog = page.getByRole("dialog");
  await dialog.waitFor({ timeout: 10000 });
  await dialog.getByRole("button", { name: `Schválit koncept ${k + 3}` }).click();
  await docbar().getByText(/interně schváleno/).waitFor({ timeout: 30000 });
  assert.equal(approvals.length, 1, "one approval");
  assert.equal(approvals[0].newest_of_line, true, "approved as its line's newest");
  // RPT8f: every edit start reached AIA, and the approval named the last one the page made.
  assert(editReports.length > 0 && editReports.every((e) => e.status === 204), `edit reports: ${JSON.stringify(editReports)}`);
  const lastSeq = Math.max(...editReports.map((e) => e.body.seq));
  assert.equal(approvals[0].seen_edit?.seq, lastSeq, "the approval names the page's last edit start");
  assert.equal(approvals[0].seen_edit?.page, editReports.at(-1).body.page, "by the page that made it");
  await page.screenshot({ path: join(out, "1440-approved.png") });
  const card = page.locator("[data-approved-edits]");
  await card.waitFor({ timeout: 30000 });
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    card.getByRole("button", { name: `Stáhnout schválenou úpravu, koncept ${k + 3} (DOCX)` }).click(),
  ]);
  assert.match(download.suggestedFilename(), /schvaleno/, "the file downloaded is the approved version");
  check("the newest koncept approved as itself (newest_of_line), naming the page's last edit start the server received (RPT8f), and the report card downloads it");

  // The Document Server down: the read-only draft stays, and it is no longer what stands -- the
  // approved koncept is named over it and the draft is offered for no approval (the PM's audit walk).
  down = true;
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("about:blank");
    await page.goto(`${base}/app/clients/${client}/research/${study}/results#report`);
    await page.locator('[data-report-editor="unavailable"]').waitFor({ timeout: 60000 });
    await page.getByRole("article", { name: "Koncept zprávy" }).waitFor({ timeout: 30000 });
    const over = await page.locator("[data-report-edited-line]").innerText();
    assert.match(over, new RegExp(`koncept ${k + 3} \\(interně schválen\\)`), `@${width}: the approved koncept is named over the draft`);
    assert.equal(await page.getByRole("button", { name: "Schválit pro interní použití" }).count(), 0, `@${width}: no approval of the draft beside it`);
    await noOverflow(`editor down @${width}`);
    await page.screenshot({ path: join(out, `${width}-editor-down.png`) });
  }
  down = false;
  assert.equal(approvals.length, 1, "nothing more was approved");
  check("the Document Server down at 1440, 1100, 768 and 390: the read-only draft names the approved koncept over it and offers no approval of itself");

  // An api.js that is not the pinned one runs nothing in AIA's page: its integrity refuses it (RPT8e).
  swapped = true;
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("about:blank");
  await page.goto(`${base}/app/clients/${client}/research/${study}/results#report`);
  await page.locator('[data-report-editor="unavailable"]').waitFor({ timeout: 60000 });
  assert.equal(await page.evaluate(() => typeof window.__standinEditor), "undefined", "the swapped script did not run");
  await page.getByRole("article", { name: "Koncept zprávy" }).waitFor({ timeout: 30000 });
  await page.screenshot({ path: join(out, "1440-script-swapped.png") });
  swapped = false;
  check("a one-time ticket is spent before api.js loads, at its canonical path under the integrity the API names; a swapped script runs nothing and leaves the read-only draft");
  assert(spent.length > 0, "a ticket was spent before the script loaded");

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} catch (failure) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true }).catch(() => undefined);
  throw failure;
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, consoleErrors, writes, approvals }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
