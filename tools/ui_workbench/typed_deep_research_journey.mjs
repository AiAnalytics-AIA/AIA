#!/usr/bin/env node
/** A person's typed Deep Research start and stop in a real browser, nothing paid (lead-orchestration
 * LO5a.3b). The workbench's worker answers Deep Research on its recorded web and scripted agents
 * (12a), so no model or search is paid and no request leaves the machine. Run, in order:
 *   AIA_WEB_RESEARCH_WORKBENCH=true python3 tools/ui_workbench/workbench.py up --fresh
 *   make ui-fixtures && make ui-research
 *   node tools/ui_workbench/typed_deep_research_journey.mjs [--facade URL] [--out DIR] [--db FILE]
 * On the persona fixture (its finished run, with analysis) at 1440 px it types "Spusť rešerši
 * výsledků": the card offers the server's Interpretation targets with the default chosen and the
 * quoted ceiling, and its approval starts one Interpretation Research run. "Zastav rešerši" then
 * names that run and stops it, or, once it has ended, says nothing runs and holds its button. At
 * 390 px, in the Lead's sheet, "Spusť rychlou rešerši výsledků" shows the same card without page
 * overflow and is left with "Teď ne". It asserts no priced row in the usage ledger, no spend, and
 * no request to any host but the workbench.
 */
import assert from "node:assert/strict";
import { execFileSync, execSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback);
const base = arg("facade", "http://127.0.0.1:8780");
const LOCAL = ["127.0.0.1", "localhost"];
assert(LOCAL.includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/typed-deep-research-journey"));
const db = arg("db", join(repo, "tmp/ui-workbench/aia.sqlite"));
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

/** The usage ledger, the studies' spend and this study's Deep Research runs, from the workbench's SQLite. */
function ledger(study) {
  const script = [
    "import json, sqlite3, sys",
    "c = sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True)",
    "paid = c.execute('select count(*) from ai_usage_events where cost_usd > 0').fetchone()[0]",
    "spent = c.execute('select coalesce(sum(spent_usd), 0) from studies').fetchone()[0]",
    "runs = [{'run_id': r[0], 'status': r[1]} for r in c.execute(\"select run_id, status from workflow_runs where workflow_type = 'deep_research' and study_id = ? order by created_at\", (sys.argv[2],))]",
    "starts = c.execute(\"select count(*) from approval_decisions where subject_type = 'chat_start' and study_id = ?\", (sys.argv[2],)).fetchone()[0]",
    "print(json.dumps({'paid_rows': paid, 'spent_usd': spent, 'runs': runs, 'chat_start': starts}))",
  ].join("\n");
  return JSON.parse(execFileSync("python3", ["-I", "-c", script, db, study], { encoding: "utf8" }));
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
const errors = [], external = [], checks = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => {
  const url = new URL(r.url());
  if (["http:", "https:", "ws:", "wss:"].includes(url.protocol) && !LOCAL.includes(url.hostname)) external.push(r.url());
});
const check = (name) => {
  checks.push(name);
  console.log(`typed deep research journey: ok   ${name}`);
};

const { client, study } = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8")).persona;
const stagePath = (slug) => `/app/clients/${client}/research/${study}/${slug}`;
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const noOverflow = async (what) => {
  const r = await page.evaluate(() => ({ w: innerWidth, d: document.documentElement.scrollWidth }));
  assert(r.d <= r.w + 2, `${what}: overflow ${r.d} > ${r.w}`);
};
const composer = page.getByLabel("Napište Vedoucímu výzkumu");
const lastCard = () => page.locator('[data-card="request"][data-typed]').last();
const type = async (text) => {
  await composer.and(page.locator(":enabled")).waitFor({ timeout: 30000 });
  await composer.fill(text);
  await composer.press("Enter");
};
/** The card's own text, once its price was read (never "Zjišťuje se…"). */
const priced = async () => {
  await page.waitForFunction(() => {
    const cards = document.querySelectorAll('[data-card="request"][data-typed]');
    const t = cards[cards.length - 1]?.textContent ?? "";
    return t.includes("Cena nejvýše") && !t.includes("Zjišťuje se");
  }, null, { timeout: 30000 });
  return (await lastCard().textContent()) ?? "";
};

try {
  const before = ledger(study);
  await page.goto(base + stagePath("questionnaire"));
  await page.locator("[data-workbench]").waitFor({ timeout: 30000 });
  const hatch = page.getByRole("button", { name: "Vylíhnout mého Vedoucího" });
  await Promise.race([hatch.waitFor({ timeout: 20000 }), composer.and(page.locator(":enabled")).waitFor({ timeout: 20000 })]).catch(() => {});
  if (await hatch.isVisible()) await hatch.click();

  // 1440: the typed Interpretation start, its target from the server's list, its price, its start.
  await type("Spusť rešerši výsledků");
  const target = page.getByLabel("K čemu rešerše hledá").last();
  await target.waitFor({ timeout: 30000 });
  const options = await target.locator("option").count();
  assert(options >= 1, "the server offered at least one target");
  const text = await priced();
  assert.match(text, /Hloubkový výzkum k výkladu/);
  assert.match(text, /Cena nejvýše(\d|Neznámá)/, "the price is a number or said unknown");
  await noOverflow("1440 typed card");
  await shot("1440-typed-interpretation");
  check(`1440: the typed card offers ${options} targets from the server, the default chosen, and its price`);

  await lastCard().getByRole("button", { name: "Spustit literární rešerši" }).click();
  // A threshold at or below the ceiling asks first; the journey confirms it, as a person would.
  const confirm = page.getByRole("dialog").getByRole("button", { name: /Spustit|Potvrdit/ });
  if (await confirm.isVisible({ timeout: 3000 }).catch(() => false)) await confirm.click();
  await page.waitForFunction(() => {
    const cards = document.querySelectorAll('[data-card="request"][data-typed]');
    return (cards[cards.length - 1]?.textContent ?? "").includes("Rozhodnuto");
  }, null, { timeout: 60000 });
  const started = ledger(study);
  assert.equal(started.chat_start, before.chat_start + 1, "one chat_start row");
  // The same spec on an earlier pass of this journey is that run, found again, never a second one.
  const reused = started.runs.length === before.runs.length;
  if (!reused) assert.equal(started.runs.length, before.runs.length + 1, "one Deep Research run started");
  const run = started.runs.at(-1);
  check(reused
    ? "1440: approved on the run an earlier pass started: found again, nothing new started or charged"
    : `1440: approved, one Interpretation Research run started (${run.status}) under one chat_start row`);

  // The stop names that run while it runs; once it has ended, nothing runs and the card says so.
  await type("Zastav rešerši");
  const stopCard = page.locator('[data-card="request"][data-typed]', { hasText: "Zastavení hloubkového výzkumu" }).last();
  await stopCard.getByRole("button", { name: "Zastavit hloubkový výzkum" }).waitFor({ timeout: 30000 });
  const stop = stopCard.getByRole("button", { name: "Zastavit hloubkový výzkum" });
  const stopText = (await stopCard.textContent()) ?? "";
  if (stopText.includes("Žádný hloubkový výzkum teď neběží")) {
    assert.equal(await stop.isDisabled(), true, "nothing to stop: the button is held");
    check("1440: the run had ended before the stop; the card says nothing runs and holds its button");
  } else {
    assert.match(stopText, /Který běh.*Rešerše z /);
    await stop.click();
    await page.waitForFunction(() => {
      const cards = document.querySelectorAll('[data-card="request"][data-typed]');
      return (cards[cards.length - 1]?.textContent ?? "").includes("Rozhodnuto");
    }, null, { timeout: 60000 });
    // Cooperative: a step in flight sees the request at its next checkpoint, then the run ends.
    let stopped = null;
    for (let i = 0; i < 120 && !["CANCELLED", "COMPLETED", "FAILED"].includes(stopped?.status); i++) {
      stopped = ledger(study).runs.find((r) => r.run_id === run.run_id);
      if (!["CANCELLED", "COMPLETED", "FAILED"].includes(stopped.status)) await page.waitForTimeout(500);
    }
    assert.ok(["CANCELLED", "COMPLETED"].includes(stopped.status), `stopped: ${stopped.status}`);
    check(`1440: "Zastav rešerši" named the running run and the stop ended it (${stopped.status})`);
  }
  await shot("1440-typed-stop");

  // 390: the same card in the Lead's sheet, no overflow; left with Teď ne.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.locator("[data-lead-launcher]").click();
  await type("Spusť rychlou rešerši výsledků");
  await page.getByLabel("K čemu rešerše hledá").last().waitFor({ timeout: 30000 });
  const quick = await priced();
  assert.match(quick, /RozsahRychlý/);
  await noOverflow("390 typed card");
  await shot("390-typed-interpretation");
  await lastCard().getByRole("button", { name: "Teď ne" }).click();
  check("390: the quick card in the sheet shows its target and price without overflow, left with Teď ne");

  const after = ledger(study);
  assert.equal(after.paid_rows, 0, "no priced row in the usage ledger");
  assert.equal(after.spent_usd, 0, "no study spent anything");
  assert.equal(after.runs.length, started.runs.length, "Teď ne started nothing");
  assert.deepEqual(external, [], "no request left the machine");
  assert.deepEqual(errors, [], "no page error");
  check("zero paid: no priced ledger row, no spend, no request off the machine");
  console.log(`typed deep research journey: PASS (screenshots in ${out})`);
} catch (e) {
  await shot("failure").catch(() => {});
  console.error(`typed deep research journey: FAIL ${e instanceof Error ? e.stack : e}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
