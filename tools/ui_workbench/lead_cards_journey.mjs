#!/usr/bin/env node
/** The study's AI work as cards in the Research Lead's conversation, in a real browser (plan
 * research-lead-workbench chunk 23, D15). The workbench answers the Lead by a script, never a
 * model, its design jobs park without the AI runtime, and its research run answers with fictional
 * fieldwork, so this costs nothing. Start the workbench with the switch on, write the fixtures:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/lead_cards_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * It checks that no stage of the workbench offers an AI start of its own (no AI pomoc, no
 * "Navrhnout"), approves the scripted Lead's design job and sees it as a card in the conversation
 * with no dialog, starts a job by a typed command from the person's own card (LO5), then has the
 * Lead prepare a research run, starts it from the card through
 * Spuštění's route, and follows its card: the orb while a step runs, Průběh and Výsledky once done.
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
const out = arg("out", join(repo, "tmp/ui-workbench/lead-cards-journey"));
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
const errors = [], writes = [], checks = [], notes = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const path = new URL(r.url()).pathname;
  if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !path.startsWith("/_next/")) writes.push({ method: r.method(), path });
});
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures[arg("fixture", "persona")];
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
/** A card on its own, scrolled to the middle of the conversation first, so nothing crops it. */
const cardShot = async (card, name) => {
  await card.evaluate((e) => e.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(300);
  await card.screenshot({ path: join(out, `${name}.png`) });
};
const SCRIPTED = "[Workbench · bez modelu]";

async function openStage(slug) {
  await page.goto(base + stagePath(slug));
  await page.locator("[data-workbench]").waitFor({ timeout: 60000 });
  await page.locator("#artbody").waitFor();
}
async function composerReady() {
  const hatch = page.getByRole("button", { name: "Vylíhnout mého Vedoucího" });
  const composer = page.getByLabel("Napište Vedoucímu výzkumu");
  await Promise.race([hatch.waitFor({ timeout: 20000 }), composer.and(page.locator(":enabled")).waitFor({ timeout: 20000 })]).catch(() => {});
  if (await hatch.isVisible()) await hatch.click();
  await page.getByLabel("Napište Vedoucímu výzkumu").and(page.locator(":enabled")).waitFor({ state: "attached", timeout: 60000 });
  return composer;
}
async function say(text) {
  const composer = await composerReady();
  const before = await page.locator(".conv").getByText(SCRIPTED, { exact: false }).count();
  await composer.fill(text);
  await composer.press("Enter");
  await page.waitForFunction((n) => document.body.innerText.split("[Workbench · bez modelu]").length - 1 > n, before, { timeout: 90000 });
}

try {
  // D15: no stage of the workbench offers an AI start of its own.
  for (const slug of ["brief", "questionnaire", "audience", "dimensions"]) {
    await openStage(slug);
    await page.waitForTimeout(1500);
    assert.equal(await page.locator("[data-contextual-assistance]").count(), 0, `${slug}: no AI pomoc`);
    // Deep Research keeps its own start until the Lead's design_research request starts it end to
    // end (it opens the stage today, D7): the one AI start left, and only that one.
    const starts = await page.locator("#artbody [data-ai-action]").evaluateAll((els) =>
      els.filter((e) => !e.closest("section[aria-labelledby='deep-research-title']")).map((e) => e.textContent?.trim()));
    assert.deepEqual(starts, [], `${slug}: no AI start in the artifact`);
  }
  check("no AI pomoc and no stage AI start on Zadání, Dotazník, Cílová skupina and Dimenze (Deep Research's own start kept)");
  await openStage("run");
  await page.getByRole("button", { name: "Spustit výzkum" }).first().waitFor({ timeout: 60000 });
  check("Spuštění keeps its own Start");

  // A design job approved on the Lead's card is a card in the conversation, with no dialog.
  await openStage("questionnaire");
  await say("Projdi dotazník a navrhni úpravy.");
  const decision = page.locator(".conv .dec").filter({ hasText: "Návrhová úloha AI" }).last();
  await Promise.all([
    page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/request$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
    decision.getByRole("button", { name: "Spustit úlohu" }).click(),
  ]);
  const worker = page.locator('.conv [data-card="worker"]').last();
  await worker.waitFor({ timeout: 30000 });
  await page.waitForTimeout(4000);
  assert.equal(await page.locator('[role="dialog"]').count(), 0, "no job dialog");
  const workerState = await worker.getAttribute("data-card-state");
  notes.push(`design job card: ${workerState} (${(await worker.innerText()).replace(/\s+/g, " ").trim()})`);
  check(`the approved design job is a card in the conversation (${workerState}), and no dialog opens`);
  await cardShot(worker, "1440-worker-card");
  await shot("1440-worker-card-page");

  // A typed start (lead-orchestration LO5): the whole message is a command the server matched, so
  // no Lead turn answers it; the person's own card follows their message, and its approval starts
  // the job through …/request (ledger chat_start).
  const typedCards = await page.locator(".conv [data-typed]").count();
  const composer = await composerReady();
  await composer.fill("Zkontroluj návrh");
  await composer.press("Enter");
  await page.waitForFunction((n) => document.querySelectorAll(".conv [data-typed]").length > n, typedCards, { timeout: 30000 });
  const typed = page.locator(".conv [data-typed]").last();
  assert.match(await typed.innerText(), /Váš příkaz/, "the card says it is the person's own command");
  const jobsBefore = await page.locator('.conv [data-card="worker"]').count();
  const [typedStart] = await Promise.all([
    page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/request$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
    typed.getByRole("button", { name: "Spustit úlohu" }).click(),
  ]);
  assert.ok(typedStart.ok(), `the typed start answered ${typedStart.status()}`);
  await page.waitForFunction((n) => document.querySelectorAll('.conv [data-card="worker"]').length > n, jobsBefore, { timeout: 30000 });
  await cardShot(typed, "1440-typed-start");
  check("a typed start shows the person's own card, and its approval starts the job through …/request");

  // The research run: prepared by the Lead, started from its card through Spuštění's route. Not the
  // bare command: "Prosím, spusť výzkum." is a message, so the Lead answers it.
  await say("Prosím, spusť výzkum.");
  const request = page.locator('.conv [data-card="run-request"]').last();
  await request.getByRole("button", { name: "Zkontrolovat spuštění" }).click();
  const start = request.locator("[data-run-request-start]");
  await start.waitFor({ timeout: 60000 }).catch(async () => {
    await shot("1440-run-request-not-startable");
    throw new Error(`the prepared run cannot start from its card: ${(await request.innerText()).replace(/\s+/g, " ")}`);
  });
  await cardShot(request, "1440-run-request");
  const [startedRun] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname.endsWith("/research/runs") && r.request().method() === "POST", { timeout: 60000 }),
    start.click(),
  ]);
  assert.ok(startedRun.ok(), `the start answered ${startedRun.status()}`);
  check("the Lead's prepared run starts from its card, through POST …/research/runs");
  const run = page.locator('.conv [data-card="run"]').last();
  await run.waitFor({ timeout: 60000 });
  const orb = await run.locator("[data-orb]").first().waitFor({ timeout: 60000 }).then(() => true, () => false);
  if (orb) {
    await cardShot(run, "1440-run-card-running");
    await shot("1440-run-card-running-page");
    check("the run's card shows the orb while a step runs");
  } else {
    notes.push("the run's steps finished between two reads: no running step was seen (the orb is held to RUNNING by the Vitest suite)");
  }
  // Výsledky opens once the data exist; later steps (analysis, report) may still run beside it.
  await run.getByRole("link", { name: "Výsledky" }).waitFor({ timeout: 240000 });
  check("the run's card links to Výsledky once its data exist");
  await run.locator("[data-orb]").first().waitFor({ state: "detached", timeout: 240000 });
  const ended = await run.getAttribute("data-card-state");
  notes.push(`run card once nothing runs: ${ended} (${(await run.innerText()).replace(/\s+/g, " ").trim()})`);
  await cardShot(run, "1440-run-card-done");
  await shot("1440-run-card-done-page");
  assert.equal(await run.getByRole("link", { name: "Průběh" }).count(), 1, "Průběh is linked");
  check(`once no step runs the card has no orb, and links to Průběh and Výsledky (${ended})`);
  assert.equal(await page.locator('[role="dialog"]').count(), 0, "no job dialog");

  // The same at 1100 px, the workbench's narrowest width: nothing covers a card's actions.
  await page.setViewportSize({ width: 1100, height: 900 });
  await page.waitForTimeout(800);
  await run.scrollIntoViewIfNeeded();
  await shot("1100-run-card-done-page");
  await page.setViewportSize({ width: 1440, height: 900 });

  // Návrh's follow-up answers (the owner, 2026-10-21): saved for the Lead, which prepares the
  // design's update as its card; nothing paid starts from the stage.
  const planned = fixtures.planned;
  await page.goto(base + `/app/clients/${planned.client}/research/${planned.study}/plan`);
  await page.locator("[data-workbench]").waitFor({ timeout: 60000 });
  await page.getByLabel("Odpověď na otázku 1").fill("Ano, jen veřejnou dopravou.");
  const before = writes.length;
  await page.getByRole("button", { name: "Uložit odpovědi" }).click();
  await page.locator("[data-saved-for-lead]").waitFor({ timeout: 30000 });
  assert.equal(writes.slice(before).filter((w) => /\/agent-jobs$|\/lead\/turns\/[^/]+\/request$/.test(w.path)).length, 0, "saving the answers starts nothing");
  check("Návrh's answers are saved for the Lead, with no AI call from the stage");
  await composerReady();
  const replies = await page.locator(".conv").getByText(SCRIPTED, { exact: false }).count();
  await page.getByRole("button", { name: "Požádat Vedoucího" }).click();
  await page.waitForFunction((n) => document.body.innerText.split("[Workbench · bez modelu]").length - 1 > n, replies, { timeout: 90000 });
  await page.locator(".conv .dec").filter({ hasText: "Analýza zadání" }).last().getByRole("button", { name: "Spustit úlohu" }).waitFor({ timeout: 30000 });
  await shot("1440-plan-answers-to-lead");
  check("Požádat Vedoucího sends the Lead a message, and the Lead prepares the brief's analysis as its card");

  const paid = writes.filter((w) => /\/deep-research\/runs/.test(w.path));
  assert.deepEqual(paid, [], "no Deep Research started");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, notes, errors, writes }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
for (const n of notes) console.log(`note ${n}`);
console.log(`evidence: ${out}`);
