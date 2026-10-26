#!/usr/bin/env node
/** Dotazník in a real browser (plan artifact-questionnaire, QST8 and QST9's journey).
 * Start the workbench with the switch on, write the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true AIA_ROUTING_ENABLED=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/questionnaire_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * Local fictional identity only. At 1440, 1100, 768 and 390 px (the workbench at every width):
 * Dotazník's Závislosti lists the tracked set's readers with Sociomapa, keeps the
 * open question out of Analýza, jumps to the set's card, and the page does not overflow; a question
 * removed is put back in its place by Vrátit (input-interactions chunk 3); a display condition is set
 * on an earlier choice question's answer and removed at every width (WCE13 (c)); nothing
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
const out = arg("out", join(repo, "tmp/ui-workbench/questionnaire-journey"));
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
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
const noOverflow = async (label) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${label}: page overflow ${r.d} > ${r.w}`);
};

try {
  // The workbench serves every width since research-lead-workbench 26b: a split from 1100 px, the
  // Lead in a drawer or a sheet below it.
  for (const [width, workbench] of [[1440, true], [1100, true], [768, true], [390, true]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    const deps = page.getByRole("region", { name: "Závislosti" });
    await deps.waitFor({ timeout: 30000 });
    assert.equal(await page.locator("[data-workbench]").count(), workbench ? 1 : 0, `workbench at ${width}: ${workbench}`);

    const set = deps.locator("li", { has: page.getByRole("link", { name: /^Sada 1 / }) });
    assert.deepEqual(await set.getByRole("link").allInnerTexts(), ["Sada 1 Sledovaná sada — varianty", "Sběr dat", "Výsledky", "Sociomapa", "Analýza", "Zpráva"]);
    assert.match(await set.getByRole("link", { name: "Sociomapa" }).getAttribute("href"), /\/results#maps$/);
    const open = deps.locator("li", { has: page.getByRole("link", { name: /^Q4 / }) });
    assert.equal(await open.getByRole("link", { name: "Analýza" }).count(), 0, "an open question feeds no analysis");
    await open.getByText(/data, ne připuštěná evidence/).waitFor();
    await deps.getByText("3 uzavřené otázky (Q1, Q2, Q3)").waitFor();
    await deps.scrollIntoViewIfNeeded();
    await noOverflow(`questionnaire @${width}`);
    await shot(`${width}-dependencies`);
    await deps.screenshot({ path: join(out, `${width}-dependencies-section.png`) });

    await set.getByRole("link", { name: /^Sada 1 / }).click();
    await page.waitForFunction(() => location.hash === "#qset_sec_wb_set");
    // An option's × is a 24 px target (WCAG 2.5.8; the browser audit measured 20 x 20).
    const remove = await page.getByRole("button", { name: "Odebrat možnost 1" }).first().boundingBox();
    assert(remove && remove.width >= 24 && remove.height >= 24, `an option's × at ${width}: ${remove?.width} x ${remove?.height}`);
    // The set's name stays readable beside its badge, count and Smazat (the browser audit, QF-3).
    const name = page.locator("#qset_sec_wb_set").getByRole("button", { name: /^Upravit: Název sady/ });
    const room = await name.evaluate((el) => ({ column: el.closest("div")?.getBoundingClientRect().width ?? 0, clipped: el.scrollWidth > el.clientWidth + 1 }));
    assert(room.column >= 160 && !room.clipped, `the set's name at ${width}: ${Math.round(room.column)} px, clipped ${room.clipped}`);
    check(`${width}: Závislosti lists the set's readers, the open question apart, no overflow`);

    // No familiarity switch a run would refuse; the set says why (spec navrh/Q4, R9).
    const setCard = page.locator("#qset_sec_wb_set");
    assert.equal(await setCard.getByRole("switch", { name: /znalost/ }).count(), 0, `a familiarity switch at ${width}`);
    await setCard.getByText(/proto tu přepínač chybí/).waitFor();
    check(`${width}: a set offers no familiarity switch and says why`);

    // A question's × stays beside its number at every width, never on a row of its own (the
    // browser audit's QF-9: at 390 px the type chips wrapped and pushed it 130 px down).
    const card = page.locator("#qedit_Q_wb1");
    await card.scrollIntoViewIfNeeded();
    const [num, x] = await card.evaluate((el) => {
      const box = (n) => { const r = n.getBoundingClientRect(); return { y: r.top, height: r.height }; };
      const badge = [...el.querySelectorAll("span")].find((n) => n.textContent === "Q1");
      const remove = el.querySelector('button[aria-label^="Odebrat otázku Q1"]');
      return badge && remove ? [box(badge), box(remove)] : [null, null];
    });
    assert(num && x, `Q1's number and its × are on the card at ${width}`);
    // Measured together, so a scroll between the two reads cannot part them.
    assert(x.y < num.y + num.height && x.y + x.height > num.y, `the question's × at ${width}: ${Math.round(x.y - num.y)} px from its number`);
    check(`${width}: a question's × beside its number`);

    // "Měří" as short VO chips (spec navrh/Q3): each reads "VO n", the question's text its name.
    const linkChips = card.getByRole("group", { name: "Odpovídá na výzkumné otázky" }).getByRole("button");
    const chipNames = await linkChips.evaluateAll((els) => els.map((el) => el.textContent ?? ""));
    assert(chipNames.length > 0 && chipNames.every((x) => /^VO\d+: \S/.test(x.trim())), `Q1's link chips at ${width}: ${JSON.stringify(chipNames)}`);
    const shortest = await linkChips.first().boundingBox();
    assert(shortest && shortest.width < 120, `a VO chip at ${width} is short: ${shortest?.width} px`);
    await noOverflow(`link chips @${width}`);
    check(`${width}: a question's research-question links as VO chips, no overflow`);
  }

  // A scale's two ends sit under the ends they name at 390 px (the browser audit, QF-11): the right
  // label had wrapped to a row of its own, below the low label, away from the 10 it names.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(base + stagePath("questionnaire") + "#qedit_Q_wb2");
  const scaleCard = page.locator("#qedit_Q_wb2");
  const low = scaleCard.getByRole("button", { name: /^Upravit: Levý popisek/ });
  const high = scaleCard.getByRole("button", { name: /^Upravit: Pravý popisek/ });
  await high.waitFor({ timeout: 30000 });
  await high.scrollIntoViewIfNeeded();
  const [lowBox, highBox] = [await low.boundingBox(), await high.boundingBox()];
  assert(lowBox && highBox && Math.abs(lowBox.y - highBox.y) < 4, `the scale's labels share a row at 390: ${lowBox?.y} vs ${highBox?.y}`);
  assert(highBox.x > lowBox.x + lowBox.width, "the right label sits right of the left one");
  // The boxes above them, and each label under the end it names.
  const boxes = await scaleCard.locator('span[aria-hidden="true"]', { has: page.locator("i") }).boundingBox();
  assert(boxes && boxes.y + boxes.height <= lowBox.y, "the boxes above the labels");
  assert(lowBox.x - boxes.x < 8 && boxes.x + boxes.width - (highBox.x + highBox.width) < 8, "each label at its end");
  await shot("390-scale-labels");
  check("390: a scale's two labels share a row, each under the end it names");

  // A block renamed in place (input-interactions chunk 3e, I1): Enter saves, the name reads back after a reload.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + stagePath("questionnaire"));
  const blockName = page.getByRole("button", { name: /^Upravit: Název bloku / }).first();
  await blockName.waitFor({ timeout: 30000 });
  const was = (await blockName.innerText()).trim();
  await blockName.click();
  const nameField = page.getByRole("textbox", { name: "Název bloku" });
  await nameField.fill(`${was} (přejmenováno)`);
  await nameField.press("Enter");
  // The copy saved: the artifact header says "Uloženo" once the working copy holds the change.
  const saved = () => page.getByText("Uloženo", { exact: true }).first().waitFor({ timeout: 15000 });
  await page.getByRole("button", { name: `Upravit: Název bloku ${was} (přejmenováno)`, exact: true }).waitFor();
  await saved();
  await page.reload();
  const renamed = page.getByRole("button", { name: `Upravit: Název bloku ${was} (přejmenováno)`, exact: true });
  await renamed.waitFor({ timeout: 30000 });
  await renamed.click();
  await page.getByRole("textbox", { name: "Název bloku" }).fill(was);
  await page.getByRole("textbox", { name: "Název bloku" }).press("Enter");
  await page.getByRole("button", { name: `Upravit: Název bloku ${was}`, exact: true }).waitFor();
  await saved();
  check("1440: a block renamed in place, saved and read back after a reload, then restored");

  // A display condition set at the question (working-copy-edit-ops WCE13 (c)) at every width: Q4 asked
  // only of those who answered Q1 "Méně často", read back after a reload at 1440, then removed. Set
  // only behind the routing switch, which this workbench must run with.
  const config = await (await page.request.get(base + "/config")).json();
  assert.equal(config.routing, true, "start the workbench with AIA_ROUTING_ENABLED=true");
  for (const width of [1440, 1100, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire") + "#qedit_Q_wb4");
    const q = page.locator("#qedit_Q_wb4");
    await q.waitFor({ timeout: 30000 });
    await q.getByRole("button", { name: "Podmínka zobrazení" }).click();
    const sources = q.getByRole("radiogroup", { name: "Zobrazit podle odpovědi na otázku" });
    // Q2 is a scale: only the choice questions before Q4 are offered.
    assert.deepEqual((await sources.getByRole("radio").allInnerTexts()).map((x) => x.split(" · ")[0]), ["Q1", "Q3"]);
    await sources.getByRole("radio", { name: /^Q1 · / }).click();
    await q.getByRole("group", { name: "Zobrazit těm, kdo odpověděli" }).getByRole("button", { name: "Méně často" }).click();
    await noOverflow(`the condition form @${width}`);
    await shot(`${width}-condition-form`);
    await q.getByRole("button", { name: "Uložit podmínku" }).click();
    const sentence = q.getByText(/^Zobrazí se jen těm, kdo u Q1 \(„Jak často během pracovního týdne dojíždíte\?“\) odpověděli „Méně často“\./);
    await sentence.waitFor();
    await saved();
    if (width === 1440) {
      await page.reload();
      await sentence.waitFor({ timeout: 30000 });
    }
    // The sentence keeps a reading width beside or above its buttons (390 px squeezed it to 50 px).
    const words = await sentence.boundingBox();
    assert(words && words.width >= Math.min(256, width - 140), `the condition's words at ${width}: ${words?.width} px wide`);
    await noOverflow(`a question's condition @${width}`);
    await shot(`${width}-condition`);
    await q.getByRole("button", { name: "Odebrat podmínku" }).click();
    await q.getByRole("button", { name: "Podmínka zobrazení" }).waitFor();
    await saved();
    check(`${width}: a condition set on an earlier choice question's answer, said in words, ${width === 1440 ? "read back after a reload, " : ""}then removed`);
  }

  // A question deleted at once and put back with Vrátit (input-interactions chunk 3, I6), at 1440.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + stagePath("questionnaire"));
  const q4 = page.locator("#qedit_Q_wb4");
  await q4.waitFor({ timeout: 30000 });
  const order = () => page.locator('[id^="qedit_"]').evaluateAll((els) => els.map((el) => el.id));
  const before = await order();
  await q4.getByRole("button", { name: /^Odebrat otázku/ }).click();
  // The toast's own Vrátit: the Lead's pane can show another for an automatic text edit.
  const toast = page.getByRole("status").filter({ hasText: "Otázka „Co by vás přesvědčilo nápoj koupit znovu?“ odebrána" });
  await toast.waitFor();
  assert.equal(await q4.count(), 0, "the question is gone at once");
  await toast.getByRole("button", { name: "Vrátit" }).click();
  await q4.waitFor();
  assert.deepEqual(await order(), before, "Vrátit puts the question back in its place");
  await shot("1440-undo-restored");
  check("1440: a question removed at once, Vrátit puts it back in its place");

  // Above the recommended fifteen a set is allowed and warned (Q75 (a)), at 390 px: the count beside
  // the list and the warning stay in view while objects are added, then the added ones are removed.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(base + stagePath("questionnaire") + "#qset_sec_wb_set");
  const card = page.locator("#qset_sec_wb_set");
  const addObject = card.getByRole("textbox", { name: "Přidat objekt a Enter" });
  await addObject.waitFor({ timeout: 30000 });
  const countBadge = card.getByText(/^\d+ \/ doporučeno 4–15$/);
  const objectCount = async () => Number((await countBadge.innerText()).split(" ")[0]);
  const start = await objectCount();
  const added = [];
  for (let i = start; i < 16; i++) {
    const name = `Navíc ${i + 1}`;
    await addObject.fill(name);
    await addObject.press("Enter");
    added.push(name);
    await page.waitForFunction(([n]) => document.querySelector("#qset_sec_wb_set")?.textContent?.includes(`${n} / doporučeno 4–15`), [i + 1]);
  }
  const warning = card.getByText("Víc než doporučených 15 objektů. Sada jich může mít až 40; Kontrola na to upozorní.");
  await warning.waitFor();
  for (const el of [countBadge, warning, addObject]) assert(await el.isVisible() && (await el.evaluate((n) => { const r = n.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })), "the count, the warning and the field in view at 390");
  await noOverflow("a set above fifteen @390");
  await shot("390-set-above-recommended");
  for (const name of added) await card.getByRole("button", { name: new RegExp(`${name}$`) }).click();
  await page.waitForFunction(([n]) => document.querySelector("#qset_sec_wb_set")?.textContent?.includes(`${n} / doporučeno 4–15`), [start]);
  check("390: a sixteenth object taken, counted beside the list and warned in words; the added ones removed");

  const paid = writes.filter((w) => /\/research\/runs$|\/agent-jobs$|\/deep-research\/runs|\/lead\/turns\/[^/]+\/request$/.test(w.path));
  assert.deepEqual(paid, [], "nothing paid started");
  check("nothing paid started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
