#!/usr/bin/env node
// The client intake sheet in a browser (client-workspace C7b), on the UI workbench:
// Přidat podklady opens the sheet within 400 ms; fictional files (the readers' own fixtures,
// a PNG and a format AIA does not take) are kept and read, each row in words; a table names
// its personal-data column and is kept as a dataset; files dropped on the client's page open
// the sheet; Přidat makes one item per file and Znalosti lists them. Fictional local identity
// only; no paid job is started (the sheet's AI extraction is disabled and says so).
//
//   make ui-workbench && make ui-fixtures
//   node tools/ui_workbench/intake_journey.mjs [--facade URL] [--out DIR]
//
// Evidence (screenshots, report.json) -> tmp/ui-workbench/intake-journey/.

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
const out = arg("out", join(repo, "tmp/ui-workbench/intake-journey"));
mkdirSync(out, { recursive: true });
const OPEN_BUDGET_MS = 400;

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
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], checks = [], writes = [], httpErrors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("response", (r) => {
  if (r.status() >= 400) httpErrors.push({ status: r.status(), path: new URL(r.url()).pathname });
});
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name, ok, detail = "") => {
  checks.push({ name, ok, detail });
  assert(ok, `${name} ${detail}`);
};

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const client = fixtures.persona.client;
const clientPath = `/app/clients/${client}`;
const stamp = Date.now().toString(36);
const SOURCES = join(repo, "packages/aia_core/tests/fixtures/client_sources");
// A 1x1 PNG and a file AIA does not take; the documents are the readers' pinned fixtures.
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
const files = [
  { name: `zadani-${stamp}.docx`, mimeType: "application/octet-stream", buffer: readFileSync(join(SOURCES, "zadani.docx")) },
  { name: `odpovedi-${stamp}.xlsx`, mimeType: "application/octet-stream", buffer: readFileSync(join(SOURCES, "odpovedi.xlsx")) },
  { name: `vizual-${stamp}.png`, mimeType: "image/png", buffer: PNG },
  { name: `prezentace-${stamp}.key`, mimeType: "application/octet-stream", buffer: Buffer.from("not a key file") },
];

await page.goto(base + clientPath);
await page.locator("header h1").waitFor();
await page.waitForLoadState("networkidle");

// 1. Přidat podklady opens the sheet, within the budget.
const opened = await page.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Přidat podklady");
  const t0 = performance.now();
  button.click();
  return new Promise((resolve) => {
    const tick = () => (document.querySelector("dialog[open]") ? resolve(performance.now() - t0) : requestAnimationFrame(tick));
    tick();
  });
});
check("the sheet opens within the budget", opened < OPEN_BUDGET_MS, `${Math.round(opened)} ms`);
const sheet = page.getByRole("dialog", { name: /Přidat podklady/ });
check("links and AI extraction are not offered", await sheet.getByRole("button", { name: "Vložit odkaz" }).isDisabled() && (await sheet.getByRole("checkbox").isDisabled()));
await page.screenshot({ path: join(out, "1-open.png") });

// 2. Four files: each kept and read, said in words.
await sheet.locator('input[type="file"]').setInputFiles(files);
await sheet.getByText(/Přečteno: \d+ část/).waitFor({ timeout: 30000 });
await sheet.getByText(/Přečteno: 2 listy|Přečteno: 1 list/).waitFor({ timeout: 30000 });
check("the image says AI does not read it", (await sheet.getByText("Uloží se bez textu · AI obrázek ani video nečte").count()) === 1);
check("a format AIA does not take is refused by name", (await sheet.getByText("Soubor nelze přečíst: tento formát AIA nepřijímá").count()) === 1);
check("the table names its personal column", (await sheet.getByText(/Sloupec E-mail vypadá jako osobní údaj/).count()) === 1);
check("the table is offered as a dataset or a document", (await sheet.getByRole("group", { name: /Uložit odpovedi-.* jako/ }).count()) === 1);
check("nothing still reads", (await sheet.getByText("Ukládám a čtu…").count()) === 0);
check("the footer counts what will be added", (await sheet.getByText("Přidá se 1 dokument, 1 datová sada, 1 zdroj bez textu. 1 soubor nelze přidat.").count()) === 1);
await sheet.getByRole("textbox", { name: `Název znalosti pro zadani-${stamp}.docx` }).fill(`Zadání ${stamp}`);
for (const width of [1440, 1024]) {
  await page.setViewportSize({ width, height: 1000 });
  const overflow = await sheet.evaluate((d) => d.scrollWidth > d.clientWidth + 1);
  check(`no sideways scroll in the sheet at ${width}`, !overflow);
  await page.screenshot({ path: join(out, `2-files-${width}.png`) });
}
await page.setViewportSize({ width: 1440, height: 1000 });

// 3. Přidat: one item per file, listed on Znalosti.
await sheet.getByRole("button", { name: "Přidat 3 podklady" }).click();
await sheet.waitFor({ state: "detached", timeout: 30000 });
await page.waitForURL(/\/knowledge/);
await page.getByRole("table", { name: "Znalosti klienta" }).getByText(`Zadání ${stamp}`).waitFor({ timeout: 30000 });
check("the document is listed under its edited title", true);
await page.screenshot({ path: join(out, "3-listed.png"), fullPage: true });
const items = writes.filter((w) => w.path.endsWith("/knowledge/proposals")).length;
check("one item per added file", items === 3, `${items}`);

// 4. A file dropped anywhere on the client's page opens the sheet with it.
await page.evaluate((name) => {
  const dt = new DataTransfer();
  dt.items.add(new File(["Poznámka z porady."], name, { type: "text/plain" }));
  const target = document.querySelector("main") ?? document.body;
  target.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
  target.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
}, `poznamka-${stamp}.txt`);
await sheet.getByText(`poznamka-${stamp}.txt`, { exact: false }).waitFor();
await sheet.getByText(/Přečteno: 1 část/).waitFor({ timeout: 30000 });
check("a drop on the page opens the sheet with the file", true);
await sheet.getByRole("button", { name: "Zrušit" }).last().click();

// Nothing paid, nothing unexpected.
const paid = writes.filter((w) => /agent-jobs|research\/runs|deep-research/.test(w.path));
check("no paid job was started", paid.length === 0, JSON.stringify(paid));
const unexpected = httpErrors.filter((h) => !(h.status === 422 && h.path.endsWith("/sources")));
check("no request failed but the refused format", unexpected.length === 0, JSON.stringify(unexpected));
check("no page error", errors.length === 0, errors.join("\n"));

writeFileSync(join(out, "report.json"), JSON.stringify({ openMs: Math.round(opened), checks, writes, httpErrors }, null, 2));
console.log(`intake journey: ${checks.length} checks passed; the sheet opened in ${Math.round(opened)} ms; evidence in ${out}`);
await browser.close();
