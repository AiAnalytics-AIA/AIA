#!/usr/bin/env node
/** Zpráva in a real browser (artifact-report RPT2, extended by RPT7): the run's internal draft read in
 * the pane from its stored document model (report-delivery RD5a), at 1440, 1100, 768 and 390 px.
 * Start the workbench with the switch on, write the fixtures and finish one research run, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   make ui-fixtures && make ui-research
 *   node tools/ui_workbench/report_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR] [--fixture persona]
 * Local fictional identity only. It checks: the draft is in the pane with its sections in print order,
 * each with its `report:<section>` id; every number chip names a ref the document's ledger holds and
 * prints that ref's stored text; a chip opens its claim in the inspector and Escape closes it; no page
 * overflow at any width; and nothing paid starts (no research run, agent job, Deep Research run or Lead
 * request approval) -- reading the draft is a GET.
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
const out = arg("out", join(repo, "tmp/ui-workbench/report-journey"));
const fixture = arg("fixture", "persona"); // the study make ui-research ran
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
await context.addInitScript(() => {
  try {
    sessionStorage.setItem(
      "aia.session",
      JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
    );
  } catch {
    /* about:blank between widths has no storage */
  }
});
const page = await context.newPage();
const errors = [], writes = [], checks = [];
let stored = null;
page.on("pageerror", (e) => errors.push(String(e)));
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const notFound = [];
page.on("response", async (r) => {
  if (r.status() === 404) notFound.push(new URL(r.url()).pathname);
  if (/\/research\/runs\/[^/]+\/report\/document$/.test(new URL(r.url()).pathname) && r.ok()) stored = await r.json();
});
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures[fixture] ?? {};
assert(client && study, `no workbench fixture "${fixture}" (run make ui-fixtures)`);
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};

try {
  for (const width of [1440, 1100, 768, 390]) {
    stored = null;
    await page.setViewportSize({ width, height: 900 });
    await page.goto("about:blank"); // a fresh load per width: the same URL again is only a hash change
    await page.goto(`${base}/app/clients/${client}/research/${study}/results#report`);
    const article = page.getByRole("article", { name: "Koncept zprávy" });
    await article.waitFor({ timeout: 60000 });
    // The response handler reads the body asynchronously; give it the moment it needs.
    for (let i = 0; i < 50 && !stored; i++) await page.waitForTimeout(100);
    assert(stored, `@${width}: the pane read the stored document`);
    const doc = stored.document;

    const sections = await article.locator("section[data-aia]").evaluateAll((els) => els.map((e) => e.getAttribute("data-aia")));
    assert.deepEqual(sections, doc.sections.map((s) => `report:${s.id}`), `@${width}: sections in print order with their ids`);

    const chips = await article.locator("[data-claim]").evaluateAll((els) => els.map((e) => [e.getAttribute("data-claim"), e.textContent]));
    assert(chips.length > 0, `@${width}: the draft cites numbers`);
    for (const [ref, text] of chips) {
      const entry = doc.ledger.refs[ref];
      assert(entry, `@${width}: chip ${ref} is in the ledger`);
      assert(!entry.suppressed, `@${width}: no suppressed number is shown (${ref})`);
      assert(text.startsWith(entry.value_text), `@${width}: chip ${ref} prints the stored text`);
    }
    const ids = await article.locator("[data-aia]").evaluateAll((els) => els.map((e) => e.getAttribute("data-aia")));
    assert.equal(new Set(ids).size, ids.length, `@${width}: no two elements share a data-aia`);
    assert(ids.every((id) => id.startsWith("report:")), `@${width}: every target is the report's own kind`);
    // Záznam pokrytí (RPT4): beside the article, never in it; one line per output the stored
    // manifest says no section read, and a line on the research questions (recorded or not).
    // The client report is a modelled run's alone (RD3): the workbench's fictional run offers none.
    assert.equal(await page.locator("[data-report-kind]").count(), 0, `@${width}: no client report for a fictional run`);
    const record = page.getByRole("region", { name: /Záznam pokrytí/ });
    await record.waitFor({ timeout: 10000 });
    assert.equal(await article.locator("[data-report-coverage]").count(), 0, `@${width}: the record is outside the text`);
    const unread = doc.unread ?? [];
    assert.equal(await record.locator('li[data-coverage="output"]').count(), Math.max(1, unread.length), `@${width}: one line per output the manifest says no section read`);
    assert(await record.locator('li[data-coverage="question"]').count() > 0, `@${width}: the research questions have their line`);
    await record.screenshot({ path: join(out, `${width}-report-coverage.png`) });
    await noOverflow(`report @${width}`);
    await page.screenshot({ path: join(out, `${width}-report.png`) });

    await article.locator("[data-claim]").first().click();
    const drawer = page.locator("[data-item-inspector]");
    await drawer.waitFor({ timeout: 10000 });
    assert.match(await drawer.innerText(), /Hodnota: /, `@${width}: the claim opens in the inspector`);
    await noOverflow(`report inspector @${width}`);
    await page.screenshot({ path: join(out, `${width}-report-claim.png`) });
    await page.keyboard.press("Escape");
    await drawer.waitFor({ state: "detached", timeout: 10000 });
  }
  check("the stored draft in the pane at 1440, 1100, 768 and 390: sections in print order with their ids, every chip a held ref with its stored text, none suppressed, every data-aia unique and report:, no overflow");
  check("no client report offered for the fictional run; Záznam pokrytí beside the draft at every width: the research questions, each output no section read, outside the text");
  check("a number chip opens its claim in the inspector and Escape closes it, at every width");

  // Approval is on the document being read, in the pane's doc bar (artifact-report RPT3a), never on
  // the report card. It asks first, naming the stored version (input-interactions B22); "Zrušit" approves
  // nothing. The draft stays a draft, so the journey can run again; a draft approved by someone
  // else on this workbench is said by name, not waited out (run on `workbench.py up --fresh`).
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("about:blank");
    await page.goto(`${base}/app/clients/${client}/research/${study}/results#report`);
    const approve = page.locator("[data-report-docbar]").getByRole("button", { name: "Schválit pro interní použití" });
    const approvedAlready = page.getByText(/^Stav: Schváleno/);
    await approve.or(approvedAlready).first().waitFor({ timeout: 60000 });
    if (await approvedAlready.count()) throw new Error("the fixture run's internal report is already approved: rerun on `python tools/ui_workbench/workbench.py up --fresh`");
    assert.equal(await page.locator("[data-complete-report]").getByRole("button", { name: /^Schválit/ }).count(), 0, `@${width}: the report card approves nothing`);
    const before = writes.filter((w) => w.path.endsWith("/report/approve")).length;
    await approve.click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor({ timeout: 10000 });
    assert.match(await dialog.innerText(), /Schválit interní zprávu, uloženou verzi ART-[0-9a-f]{16} \(DOCX[^)]*\)\?/, `@${width}: the question names the version and its format`);
    assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Zrušit", `@${width}: the safe choice holds the focus`);
    await noOverflow(`approval dialog @${width}`);
    await page.screenshot({ path: join(out, `${width}-approval-dialog.png`) });
    await dialog.getByRole("button", { name: "Zrušit" }).click();
    await dialog.waitFor({ state: "hidden", timeout: 10000 });
    assert.equal(writes.filter((w) => w.path.endsWith("/report/approve")).length, before, `@${width}: Zrušit approves nothing`);
  }
  check("approval in the doc bar, none on the card, asks first, naming the stored version and its format, the focus on Zrušit, which approves nothing, at 1440 and 390");

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, consoleErrors, notFound, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
