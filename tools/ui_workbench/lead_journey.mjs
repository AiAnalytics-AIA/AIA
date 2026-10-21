#!/usr/bin/env node
/** The Research Lead in a real browser (plan research-lead-workbench chunk 12, ADR 0026).
 * The workbench answers the Lead by a script, never a model (aia_executors.workbench
 * ScriptedLeadExecutor), so this costs nothing. Start the workbench with the switch on, write
 * the fixtures, then run:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/lead_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * It hatches the researcher's own Lead (or finds it hatched), reads its greeting, sends a message
 * that asks it to remember something, accepts its edit through the server's gate and reads the
 * change back after a reload, sees the prepared job as a card it does not approve, and finds the
 * remembered note on Můj Vedoucí only after the researcher's "Pamatovat si", read only. It then
 * turns automatic text edits on, sees the next turn's text edit accepted as automatic, reverts it
 * with Vrátit, and turns the choice off again. At 1099, 768 and 390 px it opens the conversation from
 * the launcher as a dialog, sends a message, keeps Tab inside and closes it with Escape back to the
 * launcher, and at 390 points at a question with "@". Nothing paid starts.
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
const out = arg("out", join(repo, "tmp/ui-workbench/lead-journey"));
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
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const SCRIPTED = "[Workbench · bez modelu]";
const note = `Pamatuj si, že preferuji krátké otázky (${Date.now()}).`;

try {
  await page.goto(base + stagePath("questionnaire"));
  await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
  const conv = page.locator(".conv");
  await conv.waitFor();

  // One Lead per researcher: hatched on their click, or already theirs from an earlier run.
  const hatch = page.getByRole("button", { name: "Vylíhnout mého Vedoucího" });
  const composer = page.getByLabel("Napište Vedoucímu výzkumu");
  await Promise.race([hatch.waitFor({ timeout: 20000 }), composer.and(page.locator(":enabled")).waitFor({ timeout: 20000 })]).catch(() => {});
  if (await hatch.isVisible()) {
    await hatch.click();
    check("the researcher hatched their own Lead");
  } else {
    check("the researcher's Lead was already hatched");
  }
  await page.waitForFunction(() => !document.querySelector("textarea[aria-label='Napište Vedoucímu výzkumu']")?.disabled, null, { timeout: 30000 });

  // The scripted Lead's answers say they are scripted, every time.
  await conv.getByText(SCRIPTED, { exact: false }).first().waitFor({ timeout: 60000 });
  check("the Lead's answers say they come from the workbench script, not a model");
  await shot("1440-greeting");

  const before = await page.locator(`text=${SCRIPTED}`).count();
  await composer.fill(note);
  await composer.press("Enter");
  await conv.getByText(note).waitFor();
  await page.waitForFunction((n) => document.querySelectorAll(".conv").length && document.body.innerText.split("[Workbench · bez modelu]").length - 1 > n, before, { timeout: 60000 });
  await conv.getByText("Připravil jsem ukázkovou úpravu", { exact: false }).last().waitFor();
  check("a message is answered in the conversation, with the stage it was written on");

  // The edit is a change block: nothing changed until the person accepts it.
  const bar = page.getByRole("region", { name: "Návrhy Vedoucího" });
  await bar.waitFor({ timeout: 30000 });
  await shot("1440-change-block");
  const card = conv.locator(".dec").last();
  await card.getByRole("button", { name: "Spustit úlohu" }).waitFor();
  check("the prepared job is a decision card, and nothing starts until it is approved");
  const acceptOne = bar.getByRole("button", { name: "Přijmout", exact: true }).first();
  await acceptOne.click();
  await page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/edits$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.reload();
  await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
  await page.waitForFunction(() => [...document.querySelectorAll("textarea, input")].some((e) => (e.value ?? "").includes("(upřesněno)")) || document.body.innerText.includes("(upřesněno)"), null, { timeout: 30000 });
  check("an accepted edit passes the server's gate and is in the working copy after a reload");
  await shot("1440-accepted");

  // The note is personal: it would reach every client's studies, so it waits for the
  // researcher's yes (Codex on #484), and is not on Můj Vedoucí before it.
  await page.goto(base + "/app/lead");
  await page.getByRole("heading", { name: "Paměť" }).waitFor({ timeout: 30000 });
  assert.equal(await page.getByText(note.slice(0, 40), { exact: false }).count(), 0, "a personal note waits for the researcher");
  check("a personal note the Lead proposed is not on Můj Vedoucí before the researcher says yes");
  await page.goto(base + stagePath("questionnaire"));
  await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
  const keep = page.locator(".conv").getByRole("button", { name: "Pamatovat si" }).last();
  await keep.waitFor({ timeout: 30000 });
  await shot("1440-self-update-waiting");
  await Promise.all([
    page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/self-update$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
    keep.click(),
  ]);
  await page.locator(".conv").getByText("Zapamatováno pro všechnu vaši práci").last().waitFor({ timeout: 30000 });
  check("the researcher keeps it with Pamatovat si, and the decision is shown");

  // Můj Vedoucí: the note the Lead was asked to remember, read only.
  await page.goto(base + "/app/lead");
  await page.getByRole("heading", { name: "Paměť" }).waitFor({ timeout: 30000 });
  await page.getByText(note.slice(0, 40), { exact: false }).first().waitFor({ timeout: 30000 });
  assert.equal(await page.locator("main textarea, main input[type=text]").count(), 0, "Můj Vedoucí is read only");
  check("Můj Vedoucí shows what the Lead remembered, and nothing on it is editable");
  await shot("1440-my-lead");

  // Automatic text edits (plan inline-decisions chunk 2): off until the researcher turns it on on
  // Můj Vedoucí; then the scripted Lead's edit -- a question's text alone -- is accepted through the
  // same gate when its turn finishes, shown as such with Vrátit. Turned off again afterwards.
  const toggle = page.getByRole("checkbox", { name: /Automaticky přijímat textové úpravy Vedoucího/ });
  assert.equal(await toggle.isChecked(), false, "automatic text edits are off by default");
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/lead/preferences" && r.request().method() === "PUT", { timeout: 30000 }),
    toggle.check(),
  ]);
  check("the researcher turns automatic text edits on, on Můj Vedoucí");
  try {
    await page.goto(base + stagePath("questionnaire"));
    await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
    const again = page.getByLabel("Napište Vedoucímu výzkumu");
    await page.waitForFunction(() => !document.querySelector("textarea[aria-label='Napište Vedoucímu výzkumu']")?.disabled, null, { timeout: 30000 });
    const autoAccepted = page.waitForResponse(
      (r) => /\/lead\/turns\/[^/]+\/edits$/.test(new URL(r.url()).pathname) && r.request().method() === "POST" && r.request().postDataJSON()?.auto === true,
      { timeout: 60000 },
    );
    await again.fill("Uprav prosím znění otázky.");
    await again.press("Enter");
    await autoAccepted;
    const applied = page.getByRole("region", { name: "Přijato automaticky" });
    await applied.waitFor({ timeout: 30000 });
    await applied.getByText("Přijato automaticky (vaše nastavení)", { exact: false }).first().waitFor();
    await shot("1440-auto-accepted");
    check("the Lead's text edit is accepted through the gate when its turn finishes, marked automatic");
    await applied.getByRole("button", { name: "Vrátit" }).first().click();
    await applied.waitFor({ state: "detached", timeout: 30000 });
    check("Vrátit puts the wording back as the researcher's own edit");
  } finally {
    await page.goto(base + "/app/lead");
    const off = page.getByRole("checkbox", { name: /Automaticky přijímat textové úpravy Vedoucího/ });
    await off.waitFor({ timeout: 30000 });
    if (await off.isChecked()) await off.uncheck();
  }

  // The Lead at every width (chunk 26c, D21): below 1100 px the launcher opens the same
  // conversation as a modal drawer (768-1099) or a full-screen sheet (under 768); Tab stays inside,
  // Escape closes it back to the launcher; "@" steps it aside and a tap on a question reopens it
  // at the composer with the chip set.
  for (const width of [1099, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
    const launcher = page.locator("[data-lead-launcher]");
    await launcher.waitFor();
    assert.equal(await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).count(), 0, `${width}: the conversation starts closed`);
    await launcher.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Vedoucí výzkumu" });
    await dialog.waitFor();
    await page.waitForFunction(() => document.activeElement?.id === "composer", null, { timeout: 10000 });
    const reply = page.locator(`text=${SCRIPTED}`);
    const answered = await reply.count();
    const box = page.getByLabel("Napište Vedoucímu výzkumu");
    await page.waitForFunction(() => !document.querySelector("textarea[aria-label='Napište Vedoucímu výzkumu']")?.disabled, null, { timeout: 30000 });
    await box.fill(`Jak to vypadá při šířce ${width} px?`);
    await box.press("Enter");
    // The scripted answer points at a question: the conversation steps aside to it, focus follows,
    // and "Zpět k Vedoucímu" brings it back at the composer.
    await page.locator("[data-peek]").waitFor({ timeout: 60000 });
    await dialog.waitFor({ state: "hidden" });
    await page.waitForFunction(() => !!document.activeElement?.closest("#artbody"), null, { timeout: 10000 });
    await shot(`${width}-peek`);
    await page.getByRole("button", { name: "Zpět k Vedoucímu" }).click();
    await dialog.waitFor();
    await page.waitForFunction(() => document.activeElement?.id === "composer", null, { timeout: 10000 });
    await page.waitForFunction((n) => document.body.innerText.split("[Workbench · bez modelu]").length - 1 > n, answered, { timeout: 60000 });
    for (let i = 0; i < 40; i++) {
      await page.keyboard.press("Tab");
      const at = await page.evaluate(() => document.activeElement?.closest("[role=dialog]") ? "" : `${document.activeElement?.tagName}.${document.activeElement?.className} ${document.activeElement?.textContent?.slice(0, 40)}`);
      assert.equal(at, "", `${width}: Tab stays inside the open conversation (tab ${i})`);
    }
    await shot(`${width}-drawer`);
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
    assert(await page.evaluate(() => document.activeElement?.hasAttribute("data-lead-launcher")), `${width}: Escape returns focus to the launcher`);
    const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
    assert(r.d <= r.w + 2, `${width}: page overflow ${r.d} > ${r.w}`);
    check(`${width} px: the launcher opens the conversation as a dialog; the answer's focus steps it aside to the question and Zpět k Vedoucímu brings it back; Tab stays inside; Escape returns to the launcher`);
  }
  // "@" in the sheet: the conversation steps aside, a tap on a question sets the chip and reopens it.
  await page.locator("[data-lead-launcher]").click();
  await page.getByRole("button", { name: "Ukázat na prvek artefaktu (@)" }).click();
  await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor({ state: "hidden" });
  await page.locator("[id^=qedit_]").first().click();
  await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor();
  await page.locator(".refchip").waitFor();
  await shot("390-picked");
  await page.getByRole("button", { name: "Zrušit odkaz" }).click();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1440, height: 900 });
  check("390 px: '@' steps the sheet aside, a tap on a question sets the chip and reopens it at the composer");

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
