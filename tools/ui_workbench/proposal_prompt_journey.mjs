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
// artifact-design DSN3: a narrative item is edited where it is shown (InlineText) and saved at once.
const editInPlace = async (label, value) => {
  await page.getByRole("button", { name: new RegExp(`^Upravit: ${label}`) }).click();
  const field = page.getByRole("textbox", { name: label, exact: true });
  await field.fill(value);
  await field.press("Control+Enter");
};
const measure = async (label) => {
  const size = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  assert(size.document <= size.viewport + 2, `${label}: horizontal page overflow`);
  layouts.push({ label, ...size });
};
try {
  await visit(path + "/plan"); await page.getByRole("button", { name: /^Upravit: Shrnutí výzkumného problému/ }).waitFor();
  const original = await get(contentPath);
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("proposal"); }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // The stage shows (and writes back to both) the analysis's narrative when one is stored.
  const shown = original.analysis ?? original.content.research_plan;
  const before = shown.objectives?.length ?? 0;
  await editInPlace("Shrnutí výzkumného problému", "Fiktivní návrh: ověřit preference a dostupnost.");
  await editInPlace("Cíl 1", "Porovnat čtyři nabídky");
  await page.getByRole("button", { name: "Přidat cíl", exact: true }).click();
  const row = page.getByRole("textbox", { name: "Přidat cíl", exact: true });
  await row.fill("Ověřit bariéry dostupnosti"); await row.press("Enter");
  // A repeat is refused at the row in the words an edit in place says, never as a taken name.
  await row.fill("ověřit  bariéry dostupnosti"); await row.press("Enter");
  await page.getByText("Tato položka už v seznamu je.", { exact: true }).waitFor();
  assert.equal(await page.getByText(/už existuje/).count(), 0, "a narrative repeat is not said as a taken name");
  await row.press("Escape");
  const questions = shown.research_questions?.length ?? 0;
  await page.getByRole("button", { name: "Přidat výzkumnou otázku", exact: true }).click();
  const rq = page.getByRole("textbox", { name: "Přidat výzkumnou otázku", exact: true });
  await rq.fill("Jakou roli má dostupnost?"); await rq.press("Enter"); await rq.press("Escape");
  const added = `Výzkumná otázka ${questions + 1}`;
  await page.getByRole("button", { name: new RegExp(`^Upravit: ${added}`) }).click();
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("narrative item editor"); }
  await page.getByRole("textbox", { name: added, exact: true }).fill("Která nabídka osloví?");
  await page.getByRole("textbox", { name: added, exact: true }).press("Control+Enter");
  await page.setViewportSize({ width: 1440, height: 1000 });
  let current = await saved();
  assert.equal(current.content.research_plan.objectives[0], "Porovnat čtyři nabídky");
  assert.equal(current.content.research_plan.objectives.length, before + 1);
  assert.equal(current.content.research_plan.objectives.at(-1), "Ověřit bariéry dostupnosti");
  assert.equal(current.content.research_plan.research_questions[questions], "Která nabídka osloví?");
  assert.deepEqual(current.analysis.objectives, current.content.research_plan.objectives);
  assert.deepEqual(current.content.sections, original.content.sections);
  assert.equal(await page.getByRole("button", { name: "Upravit text návrhu" }).count(), 0, "no separate narrative editor");
  await page.reload(); await page.getByText("Fiktivní návrh: ověřit preference a dostupnost.", { exact: true }).waitFor();
  checks.push("Narrative items edited and added in place persist to project and analysis, survive reload and preserve the questionnaire");
  // Q68: part of an item's words is selected in place to comment on it, only the words shown (never
  // the hidden "Upravit: …" label); a double-click selects a word; a plain click still edits.
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const item = page.locator("#plan-understanding li [role=button]").first();
    await item.scrollIntoViewIfNeeded();
    const box = await item.boundingBox();
    await page.mouse.move(box.x + 6, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + Math.min(box.width - 30, 120), box.y + box.height / 2, { steps: 12 });
    await page.mouse.up();
    const selected = (await page.evaluate(() => getSelection().toString())).trim();
    assert(selected && !selected.includes("Upravit"), `${width}: a drag selects an item's own words, got "${selected}"`);
    await page.getByRole("button", { name: "Přidat komentář" }).waitFor();
    await item.dblclick();
    await page.waitForTimeout(500);
    assert.equal(await page.locator("#plan-understanding textarea").count(), 0, `${width}: a drag or a double-click does not open the editor`);
    await page.evaluate(() => getSelection().removeAllRanges());
    await item.click();
    await page.locator("#plan-understanding textarea").first().waitFor();
    await page.keyboard.press("Escape");
  }
  checks.push("Part of a narrative item is selected in place to comment on it, and a plain click still edits it (Q68)");
  await page.setViewportSize({ width: 1440, height: 1000 });
  // audit A33: a set's measurement is edited field by field on its card, each saved at once.
  assert.equal(await page.getByRole("button", { name: "Upravit měření a položky" }).count(), 0, "no separate measurement editor");
  const card = page.locator("#plan-sets article").first();
  await card.getByRole("button", { name: /^Upravit: Název sady/ }).click();
  await card.getByRole("textbox", { name: "Název sady", exact: true }).fill("Varianty dostupnosti");
  await card.getByRole("textbox", { name: "Název sady", exact: true }).press("Enter");
  const setField = async (label, value, multiline = true) => {
    const name = `${label} · Varianty dostupnosti`;
    await card.getByRole("button", { name: new RegExp(`^Upravit: ${name}`) }).click();
    const field = card.getByRole("textbox", { name, exact: true });
    await field.fill(value);
    await field.press(multiline ? "Control+Enter" : "Enter");
    return field;
  };
  await setField("Co tato sada porovnává", "Srovnat stejné nabídky v různých časech.");
  const question = await setField("Otázka sady · položí se ke každé položce", "Chybí zástupný text");
  await card.getByText("Otázka musí obsahovat {object}: tam se vloží název položky.").waitFor();
  assert.equal(await question.inputValue(), "Chybí zástupný text", "a refused question stays typed");
  // Leaving the stage would drop it: every way out asks first, and "Zrušit" stays on Návrh.
  const onWorkbench = (await page.locator("[data-workbench]").count()) > 0;
  await (onWorkbench ? page.locator(".nav__stage", { hasText: "Dotazník" }) : page.locator(`a[href="${path}/questionnaire"]`).first()).click();
  await page.getByText("Některé úpravy návrhu nejdou uložit a zůstaly v poli. Zahodit je a pokračovat?").waitFor();
  await page.getByRole("button", { name: "Zrušit", exact: true }).click();
  assert(page.url().endsWith(`${path}/plan`), "a refused draft keeps the person on Návrh");
  await question.fill("Jak vám vyhovuje {object}?");
  await question.press("Control+Enter");
  await setField("1 na škále", "nevyhovuje", false);
  await setField("10 na škále", "zcela vyhovuje", false);
  // An item is reworded in its place, keeping its order.
  await card.getByRole("button", { name: /^Upravit: Položka · 2 / }).click();
  const second = card.getByRole("textbox", { name: "Položka · 2", exact: true });
  await second.fill("Varianta Druhá"); await second.press("Enter");
  // A repeated item is refused at the chip and stays typed there.
  const stored = await get(contentPath);
  const firstItem = (stored.analysis ?? stored.content.research_plan).tracked_sets[0].objects[0];
  const chip = card.getByRole("textbox", { name: "Přidat položku a Enter" });
  await chip.fill(firstItem.toLocaleUpperCase("cs")); await chip.press("Enter");
  await card.getByText("Tato položka už v sadě je.").waitFor();
  assert.equal(await chip.inputValue(), firstItem.toLocaleUpperCase("cs"));
  await chip.fill("");
  await card.getByText(`Jak vám vyhovuje ${firstItem}?`, { exact: true }).waitFor();
  for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure("set card in place"); }
  await page.screenshot({ path: join(out, "proposal-measurement-phone.png"), fullPage: true });
  current = await saved();
  assert.deepEqual(current.analysis.tracked_sets, current.content.research_plan.tracked_sets);
  assert.equal(current.content.research_plan.tracked_sets[0].title, "Varianty dostupnosti");
  assert.equal(current.content.research_plan.tracked_sets[0].object_question, "Jak vám vyhovuje {object}?");
  assert.deepEqual(current.content.research_plan.tracked_sets[0].scale_labels, ["nevyhovuje", "zcela vyhovuje"]);
  assert.equal(current.content.research_plan.tracked_sets[0].objects[1], "Varianta Druhá");
  assert.equal(current.content.research_plan.tracked_sets[0].objects[0], firstItem);
  await page.reload(); await page.getByText(`Jak vám vyhovuje ${firstItem}?`, { exact: true }).waitFor();
  checks.push("Set fields and items edited in place: a question without {object} and a repeated item refused at the field, leaving asks while one is held, the preview live, every field persisting after reload");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: join(out, "proposal-desktop.png"), fullPage: true });
  // An item open in place is saved when the person leaves it: following a link blurs the field first.
  await page.getByRole("button", { name: /^Upravit: Shrnutí výzkumného problému/ }).click();
  await page.getByRole("textbox", { name: "Shrnutí výzkumného problému", exact: true }).fill("Unsaved text must survive");
  // The stage's own way out: the workbench's navigator, else the classic stage track's link.
  const workbench = (await page.locator("[data-workbench]").count()) > 0;
  await (workbench ? page.locator(".nav__stage", { hasText: "Dotazník" }) : page.locator(`a[href="${path}/questionnaire"]`).first()).click();
  await page.waitForURL(`**${path}/questionnaire`);
  await page.waitForFunction(async ([url, auth]) => (await (await fetch(url, { headers: { Authorization: auth } })).json()).content.research_plan.problem_summary === "Unsaved text must survive", [base + contentPath, headers.Authorization], { timeout: 15000 });
  await visit(path + "/plan");
  checks.push("Research rail navigation never silently discards an item open in place: it is saved on leaving");
  let injected = false;
  await page.route("**" + contentPath, async (route) => {
    if (route.request().method() === "PUT" && !injected) { injected = true; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "temporary_failure", message: "Intentional local save failure" }) }); }
    return route.continue();
  });
  await editInPlace("Shrnutí výzkumného problému", "Uložení po obnovení spojení.");
  await page.getByText("Neuloženo", { exact: true }).waitFor(); await page.getByRole("button", { name: "Zkusit znovu", exact: true }).click();
  current = await saved(); assert.equal(current.content.research_plan.problem_summary, "Uložení po obnovení spojení.");
  await page.unroute("**" + contentPath); checks.push("A refused save keeps the edited content and succeeds on explicit retry");
  const design = await page.request.post(base + `/api/v1/studies/${study}/design/revisions`, { headers, data: { content: current.content, source_stage: "plan", workspace_revision: current.revision } });
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
  // The saved version is switched on from the next step beside the editor: one button for it.
  assert.equal(await version.getByRole("button", { name: `Zapnout verzi ${created.version_number}`, exact: true }).count(), 0);
  await page.locator("[data-next-step]").getByRole("button", { name: `Zapnout verzi ${created.version_number}`, exact: true }).click();
  await page.locator("[data-activation]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  await page.getByText(`Teď běží: verze ${created.version_number}.`, { exact: true }).waitFor();
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
