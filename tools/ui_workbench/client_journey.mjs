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
  // A client's rules (#853) answer 404 until their route is deployed; the page says "V AIA zatím není".
  const notYetRules = r.status() === 404 && /^\/api\/v1\/clients\/[^/]+\/rules$/.test(new URL(r.url()).pathname);
  if (r.status() >= 400 && !notYetRules) httpErrors.push({ status: r.status(), path: new URL(r.url()).pathname });
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
      if (["/research", "/simulations", "/knowledge"].includes(area)) {
        // The area's table fits its own frame: no column is cut off behind a sideways scroll.
        const table = await page.evaluate(() => {
          const t = document.querySelector("main table");
          return t ? { table: t.scrollWidth, frame: t.parentElement.clientWidth } : null;
        });
        // An area showing its empty state has no table to fit.
        if (table) assert(table.table <= table.frame + 1, `${area} @${width}: the table is ${table.table} px in a ${table.frame} px frame`);
      }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  checks.push("Six client areas × four widths: no page overflow; the studies' and the knowledge's tables fit their frames");

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
  // No modal anywhere in the library (input-interactions I7): never a <dialog> open, never a
  // role=dialog, at every step below.
  const noModal = async (step) => {
    const open = await page.locator("dialog[open], [role=dialog]").count();
    assert.equal(open, 0, `${step}: a modal is open`);
  };
  const folderRow = (name) => nav.getByRole("button", { name: new RegExp(`^${name}`) });
  // "Nová složka" is a row in the folder list (input-interactions I5): Enter creates, Esc leaves.
  await nav.getByRole("button", { name: "Nová složka" }).click();
  await nav.getByRole("textbox", { name: "Nová složka" }).fill(`${names.folder} (návrh)`);
  await noModal("new folder");
  await nav.getByRole("textbox", { name: "Nová složka" }).press("Enter");
  await folderRow(`${names.folder} \\(návrh\\)`).waitFor();
  await nav.getByRole("textbox", { name: "Nová složka" }).press("Escape");
  // "+ Nový štítek" is a row too, its swatch beside the name; Enter creates it in that colour.
  await nav.getByRole("button", { name: "Nový štítek" }).click();
  await nav.getByRole("textbox", { name: "Nový štítek" }).fill(names.label);
  await nav.getByRole("button", { name: /^Barva nového štítku/ }).click();
  await nav.getByRole("option", { name: "Tyrkysová" }).click();
  await nav.getByRole("textbox", { name: "Nový štítek" }).press("Enter");
  await folderRow(names.label).waitFor();
  await nav.getByRole("textbox", { name: "Nový štítek" }).press("Escape");
  await nav.getByRole("button", { name: `Barva štítku ${names.label}: Tyrkysová` }).waitFor();
  await noModal("new label");
  checks.push("A folder and a label are created in their lists, by typing and Enter; the label in the swatch chosen");

  // Renamed where the name is shown (I1): F2 on the folder's row, Enter saves; focus comes back to it.
  await folderRow(`${names.folder} \\(návrh\\)`).focus();
  await page.keyboard.press("F2");
  const folderName = nav.getByRole("textbox", { name: "Název složky" });
  await folderName.fill(names.folder);
  await noModal("rename folder");
  await folderName.press("Enter");
  await folderRow(names.folder).waitFor();
  await nav.getByRole("button", { name: new RegExp(`\\(návrh\\)`) }).waitFor({ state: "detached" });
  // Esc on a rename restores the name and sends nothing.
  await folderRow(names.folder).focus();
  await page.keyboard.press("F2");
  await folderName.fill("nic z toho");
  await folderName.press("Escape");
  await folderRow(names.folder).waitFor();
  assert.equal(await nav.getByRole("textbox", { name: "Název složky" }).count(), 0);
  // Recoloured by its swatch (I3): the arrows move, a click chooses and saves.
  await nav.getByRole("button", { name: `Barva štítku ${names.label}: Tyrkysová` }).click();
  await page.keyboard.press("ArrowRight");
  await nav.getByRole("option", { name: "Fialová" }).click();
  await nav.getByRole("button", { name: `Barva štítku ${names.label}: Fialová` }).waitFor();
  checks.push("The folder is renamed in place (F2, Enter; Esc restores) and the label recoloured by its swatch");

  await row.getByRole("checkbox").check();
  const bar = page.getByRole("region", { name: "Hromadné úpravy vybraných znalostí" });
  // Filing is a menu (I3): the arrows move through it, Enter files the one reached.
  await bar.getByRole("button", { name: "Přesunout do složky" }).click();
  await bar.getByRole("menu", { name: "Přesunout do složky" }).getByRole("menuitem", { name: names.folder }).click();
  await row.getByText(names.folder, { exact: true }).waitFor();
  await bar.getByRole("button", { name: "Přidat štítek" }).focus();
  await page.keyboard.press("ArrowDown");
  const labelItem = bar.getByRole("menu", { name: "Přidat štítek" }).getByRole("menuitem", { name: names.label });
  for (let i = 0; i < 50 && !(await labelItem.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await row.getByText(names.label, { exact: true }).waitFor();
  await noModal("bulk filing");
  checks.push("Bulk: the ticked item is moved into the folder and labelled, by menus (keyboard for the label)");

  // At phone width a row's menu opens inside the page.
  await page.setViewportSize({ width: 390, height: 900 });
  await nav.getByRole("button", { name: `Akce složky ${names.folder}` }).click();
  await nav.getByRole("menu", { name: `Akce složky ${names.folder}` }).waitFor();
  await measure(`${clientPath}/knowledge, a folder's menu open`);
  await page.screenshot({ path: join(out, "knowledge-390-folder-menu.png"), fullPage: false });
  await page.keyboard.press("Escape");
  await bar.getByRole("button", { name: "Odebrat štítek" }).click();
  await measure(`${clientPath}/knowledge, the bulk menu open`);
  await page.screenshot({ path: join(out, "knowledge-390-bulk-menu.png"), fullPage: false });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1440, height: 1000 });
  checks.push("At 390 px a row's menu and the bulk bar's menu open without page overflow");

  await nav.getByRole("button", { name: new RegExp(`^${names.folder}`) }).click();
  await main.getByRole("heading", { level: 2, name: names.folder }).waitFor();
  await row.waitFor();
  checks.push("The folder view lists what was filed in it");

  await row.getByRole("button", { name: new RegExp(names.item) }).click();
  const panel = page.getByRole("complementary", { name: "Otevřená znalost" });
  await panel.getByRole("textbox", { name: "Shrnutí" }).fill("Upraveno cestou v prohlížeči.");
  await panel.getByRole("button", { name: "Uložit jako revizi 2" }).click();
  // The history's own row, exactly: the run's stamp names the item, folder and label, and a stamp
  // holding "r2" made a substring match find four elements.
  await panel.getByRole("listitem").getByText("r2", { exact: true }).waitFor();
  checks.push("The open item is edited into revision 2 and its history shows it");

  // A delete happens at once with Vrátit (I6): the folder goes, Vrátit makes it again with the item
  // filed back; then it goes for good with the label, and the item stays.
  const deleteFrom = async (menu, action) => {
    await nav.getByRole("button", { name: menu }).click();
    await nav.getByRole("menu", { name: menu }).getByRole("menuitem", { name: action }).click();
  };
  await deleteFrom(`Akce složky ${names.folder}`, "Smazat složku");
  await folderRow(names.folder).waitFor({ state: "detached" });
  await noModal("delete folder");
  const toast = page.getByRole("status").filter({ hasText: `Složka „${names.folder}“ smazána` });
  await toast.waitFor();
  await page.screenshot({ path: join(out, "knowledge-1440-undo.png"), fullPage: false });
  await toast.getByRole("button", { name: "Vrátit" }).click();
  await folderRow(names.folder).waitFor();
  await main.getByRole("row").filter({ hasText: names.item }).getByText(names.folder, { exact: true }).waitFor();
  checks.push("Deleting the folder is at once, and Vrátit makes it again with the item filed back");

  await deleteFrom(`Akce složky ${names.folder}`, "Smazat složku");
  await folderRow(names.folder).waitFor({ state: "detached" });
  await deleteFrom(`Akce štítku ${names.label}`, "Smazat štítek");
  await folderRow(names.label).waitFor({ state: "detached" });
  await page.getByRole("status").filter({ hasText: `Štítek „${names.label}“ smazán` }).waitFor();
  await main.getByRole("row").filter({ hasText: names.item }).waitFor();
  await noModal("delete label");
  checks.push("Deleting the folder and the label keeps the item; no modal opened in the library");

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
  // Pravidla (D-17, #853): the data posture and the wallet ceiling, set here. Before the route is
  // deployed the card says so; after, an unset posture reads CLASSIFIED and no ceiling "bez stropu".
  const rules = main.locator("section").filter({ has: page.getByRole("heading", { name: "Pravidla" }) });
  await rules.locator(":is([data-not-yet], [data-client-rules-editor], [role=alert])").first().waitFor();
  if (await rules.locator("[data-client-rules-editor]").count()) {
    assert(await rules.getByRole("radiogroup", { name: "Postoj dat" }).getByRole("radio", { checked: true }).count() === 1, "rules: one posture in force");
    // The ceiling says what it is: none ("bez stropu", an empty field, no amount) or an amount (0 is a real cap).
    const noCeiling = (await rules.locator("[data-no-ceiling]").count()) > 0;
    const field = rules.getByLabel("Strop peněženky", { exact: true });
    if (await field.count()) assert.equal((await field.inputValue()) === "", noCeiling, "rules: the ceiling field is empty exactly when there is no ceiling");
    else assert.equal(/\d,\d{2}\s*USD/.test(await rules.innerText()), !noCeiling, "rules: a member sees an amount exactly when there is a ceiling");
  }
  checks.push("Pravidla shows the client's posture and wallet ceiling, or says they are not in AIA yet");
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
