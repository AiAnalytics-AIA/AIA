#!/usr/bin/env node
/** A stale card and a direct request, held by the same server gates in every layout
 * (plan research-lead-workbench chunk 26e). The workbench answers the Lead by a script and its
 * design jobs from recordings at zero price (aia_executors.workbench), so nothing is paid:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up --fresh
 *   python3 tools/ui_workbench/fixture_project.py
 *   node tools/ui_workbench/lead_stale_journey.mjs [--facade http://127.0.0.1:8780] [--out DIR]
 * In the split at 1100 px and in the drawer at 768 px: the Lead's prepared job is approved from
 * its card and answers; the person then accepts the Lead's edit to the question the proposal
 * also rewrites, so the proposal goes stale, and its "Použít návrh" is refused by the server and
 * said so in words. Then, with the page's own token: the used turn's request asked again returns
 * the same job; a start and a rebuild meet the study's confirmation threshold (409
 * cost_confirmation_required, then 201 once the ceiling is confirmed); every job cost $0.
 */
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/lead-stale-journey"));
rmSync(out, { recursive: true, force: true });
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
const context = await browser.newContext({ viewport: { width: 1100, height: 900 } });
await context.addInitScript(() =>
  sessionStorage.setItem(
    "aia.session",
    JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" }),
  ),
);
const page = await context.newPage();
const errors = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
const check = (name) => checks.push(name);

const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.questionnaire;
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });

/** A call with the page's own token, as a person's browser would make it outside the screen. */
const call = (method, path, body) =>
  page.evaluate(async ({ method, path, body }) => {
    const token = JSON.parse(sessionStorage.getItem("aia.session")).idToken;
    const r = await fetch(`/api/v1${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let json = null;
    try {
      json = await r.json();
    } catch {
      /* no body */
    }
    return { status: r.status, json };
  }, { method, path, body });

const jobs = async () => (await call("GET", `/studies/${study}/research/agent-jobs`)).json ?? [];

/** The conversation: beside the artifact in the split, opened from the launcher in a compact layout. */
async function openConversation(compact) {
  if (!compact) return;
  if (await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).count()) return;
  await page.locator("[data-lead-launcher]").click();
  await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor();
}
async function closeConversation(compact) {
  if (!compact) return;
  if (!(await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).count())) return;
  await page.keyboard.press("Escape");
  await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor({ state: "hidden" });
}

let lastTurn = null;
try {
  for (const [width, compact] of [[1100, false], [768, true]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(base + stagePath("questionnaire"));
    await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
    await openConversation(compact);

    // One Lead per researcher: hatched on the first pass, already theirs on the second.
    const hatch = page.getByRole("button", { name: "Vylíhnout mého Vedoucího" });
    const composer = page.getByLabel("Napište Vedoucímu výzkumu");
    await Promise.race([hatch.waitFor({ timeout: 20000 }), composer.and(page.locator(":enabled")).waitFor({ timeout: 20000 })]).catch(() => {});
    if (await hatch.isVisible()) await hatch.click();
    await page.waitForFunction(() => !document.querySelector("textarea[aria-label='Napište Vedoucímu výzkumu']")?.disabled, null, { timeout: 30000 });

    // The scripted Lead edits the first question and prepares the questionnaire's optimisation.
    const before = await jobs();
    const cards = await page.locator(".conv .dec").count();
    await composer.fill(`Navrhni úpravy dotazníku (${width} px).`);
    await composer.press("Enter");
    // This turn's own decision card, not an earlier one: the count of cards moves on.
    await page.waitForFunction((n) => document.querySelectorAll(".conv .dec").length > n, cards, { timeout: 60000 });
    // The scripted answer points at the question it edits: in the drawer the conversation steps
    // aside to it (26c), and "Zpět k Vedoucímu" brings it back to the card.
    if (compact) {
      await page.locator("[data-peek]").waitFor({ timeout: 30000 });
      await page.getByRole("button", { name: "Zpět k Vedoucímu" }).click();
      await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).waitFor();
    }
    const card = page.locator(".conv .dec").last();
    const [approval] = await Promise.all([
      page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/request$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
      card.getByRole("button", { name: "Spustit úlohu" }).click(),
    ]);
    assert([200, 201].includes(approval.status()), `${width}: the card's approval starts the job (${approval.status()})`);
    lastTurn = new URL(approval.url()).pathname.split("/").at(-2);
    const started = (await jobs()).filter((j) => !before.some((b) => b.run_id === j.run_id));
    assert.equal(started.length, 1, `${width}: one job from one approval`);
    check(`${width} px: the Lead's prepared job starts from its card, through the server's approval`);

    // The recorded worker answers; the job's card offers its proposal for review.
    await page.locator("[data-card-review]").last().waitFor({ timeout: 90000 });
    await shot(`${width}-job-ready`);

    // The person accepts the Lead's edit to the first question, which the proposal also rewrites.
    await closeConversation(compact);
    const bar = page.getByRole("region", { name: "Návrhy Vedoucího" });
    await bar.waitFor({ timeout: 30000 });
    await Promise.all([
      page.waitForResponse((r) => /\/lead\/turns\/[^/]+\/edits$/.test(new URL(r.url()).pathname) && r.request().method() === "POST", { timeout: 30000 }),
      bar.getByRole("button", { name: "Přijmout", exact: true }).first().click(),
    ]);
    check(`${width} px: the working copy moves under the proposal (the Lead's edit accepted)`);

    // The stale card: its accept is the server's to refuse, and the refusal is said in words.
    await openConversation(compact);
    await page.locator("[data-card-review]").last().click();
    if (compact && (await page.getByRole("dialog", { name: "Vedoucí výzkumu" }).count())) await closeConversation(compact);
    const apply = page.getByRole("button", { name: "Použít návrh" });
    await apply.waitFor({ timeout: 30000 });
    const refused = page.waitForResponse((r) => /\/agent-jobs\/[^/]+\/accept$/.test(new URL(r.url()).pathname), { timeout: 30000 });
    await apply.click();
    assert.equal((await refused).status(), 409, `${width}: a stale proposal's accept is refused by the server`);
    const notice = page.locator("[data-proposal-stale]");
    await notice.waitFor({ timeout: 30000 });
    assert((await notice.innerText()).trim().length > 20, `${width}: the refusal is said in words`);
    await page.getByRole("button", { name: "Navrhnout znovu" }).waitFor();
    await shot(`${width}-stale-refused`);
    check(`${width} px: the stale card's accept is refused by the server, said in words, with "Navrhnout znovu"`);
    await page.getByRole("button", { name: "Ponechat současný návrh" }).click();
  }

  // Direct requests with the page's own token meet the same gates as the screen.
  const count = (await jobs()).length;
  const again = await call("POST", `/studies/${study}/lead/turns/${lastTurn}/request`, {});
  assert.equal(again.status, 200, `a used turn's request asked again answers 200 (${again.status})`);
  assert.equal((await jobs()).length, count, "a used turn's request starts no second job");
  check("a used turn's request asked again directly returns its job and starts no second one");

  const content = (await call("GET", `/studies/${study}/workspace/content`)).json;
  const revision = (await call("POST", `/studies/${study}/design/revisions`, { content: content.content, source_stage: "questionnaire", workspace_revision: content.revision })).json;
  const limit = await call("PUT", `/studies/${study}/spend-confirm`, { limit_usd: 0.001 });
  assert.equal(limit.status, 200, `the study's confirmation threshold is set (${limit.status})`);
  try {
    const asked = await call("POST", `/studies/${study}/research/agent-jobs`, { design_revision_id: revision.revision_id, action: "critique_design" });
    assert.equal(asked.status, 409, `a direct start above the threshold is asked to confirm (${asked.status})`);
    assert.equal(asked.json?.code, "cost_confirmation_required");
    const ceiling = asked.json.details.ceiling_usd;
    const startedJob = await call("POST", `/studies/${study}/research/agent-jobs`, { design_revision_id: revision.revision_id, action: "critique_design", confirm_cost_usd: ceiling });
    assert.equal(startedJob.status, 201, `a confirmed direct start starts (${startedJob.status})`);
    check("a direct start above the study's threshold is asked to confirm (409), and starts once confirmed");

    const stale = (await jobs()).find((j) => j.action === "optimize_questionnaire" && j.status === "COMPLETED");
    const rebuild = await call("POST", `/studies/${study}/research/agent-jobs/${stale.run_id}/rebuild`, { design_revision_id: revision.revision_id });
    assert.equal(rebuild.status, 409, `a direct rebuild above the threshold is asked to confirm (${rebuild.status})`);
    assert.equal(rebuild.json?.code, "cost_confirmation_required");
    const rebuilt = await call("POST", `/studies/${study}/research/agent-jobs/${stale.run_id}/rebuild`, { design_revision_id: revision.revision_id, confirm_cost_usd: rebuild.json.details.ceiling_usd });
    assert([200, 201].includes(rebuilt.status), `a confirmed direct rebuild starts (${rebuilt.status})`);
    check("a direct rebuild above the study's threshold is asked to confirm (409), and starts once confirmed");
  } finally {
    await call("PUT", `/studies/${study}/spend-confirm`, { limit_usd: null });
  }

  // Nothing paid: every job this journey started answered from a recording at zero price.
  await page.waitForTimeout(3000);
  const spent = (await jobs()).map((j) => Number(j.actual_cost_usd ?? 0));
  assert(spent.every((usd) => usd === 0), `every job cost $0: ${spent.join(", ")}`);
  check("every job cost $0 (recorded answers)");
  assert.deepEqual(errors, [], `page errors: ${errors.join("\n")}`);
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify({ checks, errors }, null, 2));
  await browser.close();
}
console.log(checks.map((c) => `ok  ${c}`).join("\n"));
console.log(`evidence: ${out}`);
