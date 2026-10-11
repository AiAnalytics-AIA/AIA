#!/usr/bin/env node
// Real local APIs, fictional workspace only. No AI calls or live organization edits.
import assert from "node:assert/strict";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (k, value) => args.includes(`--${k}`) ? args[args.indexOf(`--${k}`) + 1] : value;
const base = arg("facade", "http://127.0.0.1:8780");
assert(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Fictional local identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/proposal-prompts")); mkdirSync(out, { recursive: true });
const require = createRequire(import.meta.url);
let module;
for (const from of [repo, join(repo, "apps/web")]) {
  try { module = await import(pathToFileURL(require.resolve("playwright", { paths: [from] })).href); break; } catch { /* next */ }
}
module ??= await import(pathToFileURL(join(execSync("npm root -g", { encoding: "utf8" }).trim(), "playwright/index.mjs")).href);
const browser = await (module.chromium ?? module.default.chromium).launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() => sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" })));
const page = await context.newPage();
const checks = [], layouts = [], errors = [], writes = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("request", (r) => { if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && new URL(r.url()).pathname.startsWith("/api/")) writes.push({ method: r.method(), path: new URL(r.url()).pathname }); });
const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.planned;
const path = `/app/clients/${client}/research/${study}`;
const contentPath = `/api/v1/studies/${study}/workspace/content`;
const headers = { Authorization: "Bearer workbench@example.invalid" };
const get = async (url) => { const r = await page.request.get(base + url, { headers }); assert(r.ok(), `${url}: ${r.status()}`); return r.json(); };
const visit = async (url) => { await page.goto(base + url); await page.locator("h1").waitFor(); };
const saved = async () => { await page.getByText("Uloženo", { exact: true }).waitFor(); return get(contentPath); };
const measure = async (label) => {
  const size = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  assert(size.document <= size.viewport + 2, `${label}: horizontal page overflow`);
  layouts.push({ label, ...size });
};
try {
  await visit(path + "/plan"); await page.getByRole("button", { name: "Upravit text návrhu", exact: true }).waitFor();
  const original = await get(contentPath);
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("proposal"); }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Upravit text návrhu", exact: true }).click();
  const narrative = page.getByRole("form", { name: "Upravit text návrhu" });
  await narrative.getByLabel("Shrnutí výzkumného problému").fill("Fiktivní návrh: ověřit preference a dostupnost.");
  await narrative.getByLabel("Výzkumné otázky", { exact: true }).fill("Která nabídka osloví?\nJakou roli má dostupnost?");
  await narrative.getByLabel("Co má výzkum zjistit").fill("Porovnat čtyři nabídky\n\nOvěřit bariéry dostupnosti");
  await narrative.getByLabel("Co stojí za ověření").fill("Dostupnost ovlivní volbu.");
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("narrative editor"); }
  await narrative.getByRole("button", { name: "Použít úpravy návrhu" }).click();
  let current = await saved();
  assert.deepEqual(current.content.research_plan.objectives, ["Porovnat čtyři nabídky", "Ověřit bariéry dostupnosti"]);
  assert.deepEqual(current.analysis.objectives, current.content.research_plan.objectives);
  assert.deepEqual(current.content.sections, original.content.sections);
  await page.reload(); await page.getByText("Fiktivní návrh: ověřit preference a dostupnost.", { exact: true }).waitFor();
  checks.push("Narrative edit persists to project and analysis, survives reload and preserves the questionnaire");
  await page.getByRole("button", { name: "Upravit měření a položky" }).first().click();
  const measurement = page.getByRole("form", { name: "Upravit měření a položky" });
  await measurement.getByLabel("Název sady", { exact: true }).fill("Varianty dostupnosti");
  await measurement.getByLabel("Co tato sada porovnává").fill("Srovnat stejné nabídky v různých časech.");
  await measurement.getByLabel("Položky sady (jedna na řádek)").fill("Ráno\nPoledne\nOdpoledne\nVečer");
  await measurement.getByLabel("Otázka sady · položí se ke každé položce").fill("Chybí zástupný text");
  await measurement.getByRole("button", { name: "Použít změny sady" }).click();
  await measurement.getByRole("alert").waitFor();
  await measurement.getByLabel("Otázka sady · položí se ke každé položce").fill("Jak vám vyhovuje {object}?");
  await measurement.getByLabel("1 na škále", { exact: true }).fill("nevyhovuje");
  await measurement.getByLabel("10 na škále", { exact: true }).fill("zcela vyhovuje");
  await measurement.getByText("Jak vám vyhovuje Ráno?", { exact: true }).waitFor();
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("measurement editor"); }
  await page.screenshot({ path: join(out, "proposal-measurement-phone.png"), fullPage: true });
  await measurement.getByRole("button", { name: "Použít změny sady" }).click();
  current = await saved();
  assert.deepEqual(current.analysis.tracked_sets, current.content.research_plan.tracked_sets);
  assert.deepEqual(current.content.research_plan.tracked_sets[0].scale_labels, ["nevyhovuje", "zcela vyhovuje"]);
  await page.reload(); await page.getByText("Jak vám vyhovuje Ráno?", { exact: true }).waitFor();
  checks.push("Measurement template validation, live preview and edited objects/anchors persist after reload");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: join(out, "proposal-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "Upravit text návrhu", exact: true }).click();
  await page.getByRole("form", { name: "Upravit text návrhu" }).getByLabel("Shrnutí výzkumného problému").fill("Unsaved text must survive");
  await page.locator(`a[href="${path}/questionnaire"]`).first().click();
  await page.getByRole("dialog").waitFor(); await page.getByRole("button", { name: "Zrušit", exact: true }).click();
  assert.equal(await page.getByLabel("Shrnutí výzkumného problému").inputValue(), "Unsaved text must survive");
  await page.getByRole("form", { name: "Upravit text návrhu" }).getByRole("button", { name: "Zrušit úpravy" }).click();
  checks.push("Research rail navigation cannot silently discard an unfinished edit");
  let injected = false;
  await page.route("**" + contentPath, async (route) => {
    if (route.request().method() === "PUT" && !injected) { injected = true; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "temporary_failure", message: "Intentional local save failure" }) }); }
    return route.continue();
  });
  await page.getByRole("button", { name: "Upravit text návrhu", exact: true }).click();
  await page.getByLabel("Shrnutí výzkumného problému").fill("Uložení po obnovení spojení.");
  await page.getByRole("form", { name: "Upravit text návrhu" }).getByRole("button", { name: "Použít úpravy návrhu" }).click();
  await page.getByText("Neuloženo", { exact: true }).waitFor(); await page.getByRole("button", { name: "Zkusit znovu", exact: true }).click();
  current = await saved(); assert.equal(current.content.research_plan.problem_summary, "Uložení po obnovení spojení.");
  await page.unroute("**" + contentPath); checks.push("A refused save keeps the edited content and succeeds on explicit retry");
  const design = await page.request.post(base + `/api/v1/studies/${study}/design/revisions`, { headers, data: { content: current.content, source_stage: "plan" } });
  assert(design.ok(), await design.text());
  const submitted = await design.json();
  const pinned = await get(`/api/v1/studies/${study}/design/revisions/${submitted.revision_id}`);
  assert.deepEqual(pinned.content.research_plan, current.content.research_plan);
  checks.push("The real design-revision API receives exactly the edited proposal");
  // Reproduce the live native-plan/legacy-analysis mismatch without changing live data.
  const nativeStudy = fixtures.empty.study, nativePath = `/api/v1/studies/${nativeStudy}/workspace/content`;
  const empty = await get(nativePath);
  const put = await page.request.put(base + nativePath, { headers, data: { content: { ...empty.content, research_plan: { problem_summary: "Native plan without analysis", objectives: ["Native saved objective"], research_questions: ["Native saved question?"], hypotheses: [] } }, analysis: null, base_revision: empty.revision, reason: "local_native_proposal_regression" } });
  assert(put.ok(), await put.text());
  await visit(`/app/clients/${fixtures.empty.client}/research/${nativeStudy}/plan`);
  await page.getByText("Native saved objective", { exact: true }).waitFor();
  assert.equal(await page.getByText("Zatím není návrh", { exact: true }).count(), 0);
  checks.push("Saved native proposal is visible and editable even without a legacy analysis");
  await visit("/app/settings#prompts"); await page.getByLabel("Instrukce", { exact: true }).waitFor();
  assert(!await page.locator("#panel-prompts").innerText().then((s) => s.includes("aia.settings.prompts.names")));
  const catalog = page.getByRole("navigation", { name: "Seznam promptů" });
  await page.getByRole("searchbox", { name: "Hledat prompt" }).fill("vedoucí"); assert.equal(await catalog.locator("[data-prompt]").count(), 1);
  await page.getByRole("searchbox").fill("");
  await page.getByLabel("Zobrazit prompty").selectOption("readOnly"); assert.equal(await catalog.locator("[data-prompt]").count(), 12);
  await page.getByLabel("Zobrazit prompty").selectOption("all");
  checks.push("All 20 prompt names render correctly; search and code-owned filters work");
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("prompt settings"); }
  const baseline = await page.getByLabel("Instrukce", { exact: true }).inputValue();
  const text = baseline + `\nLocal fictional UX acceptance ${Date.now()}.`;
  await page.getByLabel("Instrukce", { exact: true }).fill(text);
  await catalog.locator('[data-prompt="aia.research.build_questionnaire"]').click();
  await page.getByRole("button", { name: "Zůstat u úprav" }).click();
  assert.equal(await page.getByLabel("Instrukce", { exact: true }).inputValue(), text);
  await page.getByRole("button", { name: "Uložit jako novou verzi", exact: true }).click();
  await page.locator('[data-answer="ok"]').waitFor();
  const activeBefore = await get("/api/v1/system-prompts/aia.research.analyze_brief");
  const created = activeBefore.versions.find((v) => v.text === text);
  assert(created, "The API contains the exact newly saved prompt text");
  const versionKey = `v${created.version_number}`, label = created.label;
  const version = page.locator(`[data-version="${versionKey}"]`); await version.waitFor();
  assert.notEqual(activeBefore.active.label, label);
  await page.getByLabel("Instrukce", { exact: true }).fill(text + " Unsaved important addition.");
  await page.locator('[data-version="baseline"]').getByRole("button", { name: "Do editoru" }).click();
  await page.getByRole("button", { name: "Pokračovat v úpravách" }).click();
  assert.equal(await page.getByLabel("Instrukce", { exact: true }).inputValue(), text + " Unsaved important addition.");
  await page.getByRole("button", { name: "Vrátit neuložené změny" }).click();
  await version.getByRole("button", { name: `Zapnout ${label}`, exact: true }).click();
  await page.locator("[data-activation]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  await page.getByText(`Teď běží: ${label}.`, { exact: true }).waitFor();
  await page.reload(); await page.getByLabel("Instrukce", { exact: true }).waitFor();
  assert.equal(await page.getByLabel("Instrukce", { exact: true }).inputValue(), text);
  assert.equal(await page.locator(`[data-version="${versionKey}"]`).getAttribute("data-running"), "yes");
  checks.push("Prompt save, protected switching/loading, explicit activation and reload work against the real API");
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("prompt version cards"); }
  await page.screenshot({ path: join(out, "prompts-phone.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.screenshot({ path: join(out, "prompts-desktop.png"), fullPage: true });
  // Restore the local code baseline. Never apply this identity or flow to live organizations.
  await page.locator('[data-version="baseline"]').getByRole("button", { name: "Vrátit základ z kódu" }).click();
  await page.locator("[data-activation]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  await page.getByText("Teď běží: Základ z kódu.", { exact: true }).waitFor();
  // Session expiry must return to this settings section after sign-in.
  await page.route("**/api/v1/system-prompts", (route) => route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ code: "unauthenticated", message: "Local session-expiry acceptance" }) }));
  await page.reload(); await page.waitForURL("**/login?next=*");
  assert.equal(new URL(page.url()).searchParams.get("next"), "/app/settings#prompts");
  checks.push("Expired authentication preserves the prompt section in the sign-in return URL");
  assert.equal(writes.filter((r) => /agent-jobs|research\/runs|deep-research\/runs/.test(r.path)).length, 0);
  assert.deepEqual(errors, []);
  writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "PASS", checks, layouts, writes, pageErrors: errors }, null, 2));
  console.log(JSON.stringify({ status: "PASS", checks, layoutAssertions: layouts.length, paidJobs: 0, out }, null, 2));
} catch (e) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true });
  writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(e), checks, layouts, writes, pageErrors: errors }, null, 2));
  throw e;
} finally { await browser.close(); }
