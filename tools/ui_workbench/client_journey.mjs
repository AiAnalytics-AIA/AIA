#!/usr/bin/env node
/** The client workspace in a real browser over the fictional workbench (client-workspace C10).
 * Run `make ui-workbench` and `make ui-fixtures` first, then:
 *   node tools/ui_workbench/client_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. It adds, files, edits and removes fictional knowledge of the
 * workbench's own client, and asserts that nothing paid ran: no research run, agent job or
 * Deep Research run is started, and no budget changes.
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
const out = arg("out", join(repo, "tmp/ui-workbench/client-journey"));
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
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], checks = [], writes = [], httpErrors = [], records = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("response", (r) => {
  if (r.status() >= 400) httpErrors.push({ status: r.status(), path: new URL(r.url()).pathname });
});
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const client = fixtures.persona.client;
const clientPath = `/app/clients/${client}`;
const stamp = Date.now().toString(36);
const names = { item: `Cesta ${stamp}: pobočky`, folder: `Cesta ${stamp}`, label: `cesta-${stamp}` };

const visit = async (path) => {
  await page.goto(base + path);
  await page.locator("header h1").waitFor();
  await page.waitForLoadState("networkidle");
};
const measure = async (label) => {
  const row = await page.evaluate(() => ({
    width: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    mainWidth: document.querySelector("main")?.getBoundingClientRect().width ?? 0,
  }));
  records.push({ label, ...row });
  assert(row.documentWidth <= row.width + 2, `${label} @${row.width}: page overflow ${row.documentWidth}`);
};
const main = page.locator("main");

try {
  // Every area of the client at four widths: nothing overflows the page.
  for (const area of ["", "/research", "/simulations", "/knowledge", "/data", "/profile"]) {
    await visit(clientPath + area);
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await measure(clientPath + area);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  checks.push("Six client areas × four widths: no page overflow");

  // Přehled: what waits on a person comes first.
  await visit(clientPath);
  await page.getByRole("heading", { name: "Čeká na vás" }).waitFor();
  await page.getByRole("heading", { name: "Kontext klienta" }).waitFor();
  checks.push("Přehled opens on Čeká na vás, with Kontext klienta beside it");

  // Výzkumy: a table, filtered.
  await visit(`${clientPath}/research`);
  const table = page.getByRole("table", { name: "Výzkumy" });
  await table.waitFor();
  await page.getByRole("group", { name: "Stav studií" }).getByRole("button", { name: /^Archiv/ }).click();
  await page.getByRole("group", { name: "Stav studií" }).getByRole("button", { name: /^Aktuální/ }).click();
  await table.waitFor();
  checks.push("Výzkumy is a table with status filters");

  // Znalosti: write, file, label, edit, then remove what this journey made. A file comes in
  // through Přidat podklady (the intake journey); text is written on Znalosti ("Napsat znalost").
  await visit(`${clientPath}/knowledge`);
  await page.getByRole("button", { name: "Napsat znalost" }).click();
  await page.getByRole("heading", { name: "Napsat znalost klienta" }).waitFor();
  const form = page.getByRole("heading", { name: "Napsat znalost klienta" }).locator("xpath=ancestor::section[1]");
  await form.getByRole("combobox").selectOption("FACT");
  await form.getByRole("textbox").first().fill(names.item);
  await form.getByRole("button", { name: "Uložit znalost" }).click();
  const row = main.getByRole("row").filter({ hasText: names.item });
  await row.waitFor();
  checks.push("Napsat znalost on Znalosti opens the form; the item is listed at once");

  const nav = page.getByRole("navigation", { name: "Pohledy, složky a štítky" });
  // "Nová složka" is a row in the folder list (input-interactions I5): Enter creates, Esc leaves.
  await nav.getByRole("button", { name: "Nová složka" }).click();
  await nav.getByRole("textbox", { name: "Nová složka" }).fill(names.folder);
  await nav.getByRole("textbox", { name: "Nová složka" }).press("Enter");
  await nav.getByRole("button", { name: new RegExp(`^${names.folder}`) }).waitFor();
  await nav.getByRole("textbox", { name: "Nová složka" }).press("Escape");
  await nav.getByRole("button", { name: "Nový štítek" }).click();
  await nav.getByRole("textbox", { name: "Název štítku" }).fill(names.label);
  await nav.getByRole("combobox", { name: "Barva štítku" }).selectOption("TEAL");
  await nav.getByRole("button", { name: "Vytvořit" }).click();
  await nav.getByRole("button", { name: new RegExp(`^${names.label}`) }).waitFor();
  checks.push("A folder and a label are created from the side panel");

  await row.getByRole("checkbox").check();
  const bar = page.getByRole("region", { name: "Hromadné úpravy vybraných znalostí" });
  await bar.getByRole("combobox", { name: "Přesunout do složky…" }).selectOption({ label: names.folder });
  await row.getByText(names.folder).waitFor();
  await bar.getByRole("combobox", { name: "Přidat štítek…" }).selectOption({ label: names.label });
  await row.getByText(names.label).waitFor();
  checks.push("Bulk: the ticked item is moved into the folder and labelled");

  await nav.getByRole("button", { name: new RegExp(`^${names.folder}`) }).click();
  await main.getByRole("heading", { level: 2, name: names.folder }).waitFor();
  await row.waitFor();
  checks.push("The folder view lists what was filed in it");

  await row.getByRole("button", { name: new RegExp(names.item) }).click();
  const panel = page.getByRole("complementary", { name: "Otevřená znalost" });
  await panel.getByRole("textbox", { name: "Shrnutí" }).fill("Upraveno cestou v prohlížeči.");
  await panel.getByRole("button", { name: "Uložit jako revizi 2" }).click();
  await panel.getByText("r2").waitFor();
  checks.push("The open item is edited into revision 2 and its history shows it");

  await main.getByRole("button", { name: "Smazat složku" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "OK" }).click();
  await nav.getByRole("button", { name: new RegExp(`^${names.folder}`) }).waitFor({ state: "detached" });
  await nav.getByRole("button", { name: new RegExp(`^${names.label}`) }).click();
  await main.getByRole("button", { name: "Smazat štítek" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "OK" }).click();
  await nav.getByRole("button", { name: new RegExp(`^${names.label}`) }).waitFor({ state: "detached" });
  await main.getByRole("row").filter({ hasText: names.item }).waitFor();
  checks.push("Deleting the folder and the label keeps the item");

  // Profil: the details saved on the client and read back; a contact added and removed.
  await visit(`${clientPath}/profile`);
  const details = main.locator("form").filter({ has: page.getByRole("heading", { name: "Základní údaje" }) });
  await details.waitFor();
  const market = `Česko ${stamp}`;
  await details.getByRole("textbox", { name: "Trh" }).fill(market);
  await details.getByRole("button", { name: "Uložit profil" }).click();
  await main.getByText(/^Změněno: Trh/).first().waitFor();
  await page.reload();
  await main.getByRole("textbox", { name: "Trh" }).waitFor();
  assert.equal(await main.getByRole("textbox", { name: "Trh" }).inputValue(), market);
  checks.push("Profil saves the client's details and reads them back after a reload");
  const contacts = main.locator("section").filter({ has: page.getByRole("heading", { name: "Kontakty" }) });
  const person = `Kontakt ${stamp}`;
  await contacts.getByRole("button", { name: "Přidat kontakt" }).click();
  await contacts.getByRole("textbox", { name: "Jméno" }).fill(person);
  await contacts.getByRole("textbox", { name: "E-mail" }).fill(`${stamp}@klient.test`);
  await contacts.getByRole("button", { name: "Uložit kontakt" }).click();
  await contacts.getByRole("cell", { name: person, exact: true }).waitFor();
  await contacts.getByRole("button", { name: `Odebrat kontakt ${person}` }).click();
  await contacts.getByRole("cell", { name: person, exact: true }).waitFor({ state: "detached" });
  await main.getByText(`Odebrán kontakt ${person}`).waitFor();
  const history = main.locator("section").filter({ has: page.getByRole("heading", { name: "Historie profilu" }) });
  assert(!(await history.innerText()).includes(`${stamp}@klient.test`), "the history names an e-mail");
  checks.push("A contact is added and removed, and the history names it without its e-mail");
  await measure("profile");

  const paid = writes.filter((w) => /\/(research\/runs|research\/agent-jobs|deep-research|budget|spend-confirm)/.test(w.path));
  assert.deepEqual(paid, [], `paid or budget writes: ${JSON.stringify(paid)}`);
  checks.push(`Zero paid jobs; ${writes.length} writes, all to the client's knowledge and profile`);
  assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
  assert.deepEqual(httpErrors, [], `HTTP errors: ${JSON.stringify(httpErrors)}`);
} catch (e) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true }).catch(() => {});
  writeFileSync(join(out, "report.json"), JSON.stringify({ ok: false, error: String(e), checks, writes, httpErrors, errors, records }, null, 2));
  await browser.close();
  console.error(`FAILED: ${e}`);
  process.exit(1);
}
writeFileSync(join(out, "report.json"), JSON.stringify({ ok: true, checks, writes, records }, null, 2));
await browser.close();
for (const c of checks) console.log(`ok  ${c}`);
console.log(`evidence: ${out}/report.json`);
