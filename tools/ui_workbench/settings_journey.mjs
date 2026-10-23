#!/usr/bin/env node
// Full settings acceptance through real local APIs. Fictional identity only; never paid AI jobs.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (key, fallback) => args.includes(`--${key}`) ? args[args.indexOf(`--${key}`) + 1] : fallback;
const base = arg("facade", "http://127.0.0.1:8780");
assert(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Fictional local identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/settings-journey")); mkdirSync(out, { recursive: true });
const require = createRequire(import.meta.url);
const module = await import(pathToFileURL(require.resolve("playwright", { paths: [repo, join(repo, "apps/web")] })).href);
const browser = await (module.chromium ?? module.default.chromium).launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(() => sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" })));
const page = await context.newPage();
const checks = [], layouts = [], errors = [], writes = [];
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (request) => { if (!["GET", "HEAD", "OPTIONS"].includes(request.method()) && new URL(request.url()).pathname.startsWith("/api/")) writes.push({ method: request.method(), path: new URL(request.url()).pathname }); });
const headers = { Authorization: "Bearer workbench@example.invalid" };
const get = async (path) => { const r = await page.request.get(base + path, { headers }); assert(r.ok(), `${path}: ${r.status()}`); return r.json(); };
const tab = async (id) => { await page.locator(`#tab-${id}`).click(); assert.equal(await page.locator(`#tab-${id}`).getAttribute("aria-selected"), "true"); return page.locator(`#panel-${id}`); };
const measure = async (name) => {
  const size = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth }));
  if (size.documentWidth > size.width + 2) console.log(JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("body *")].map(e => ({ tag: e.tagName, text: e.textContent?.slice(0,75), classes: e.className?.toString(), right: e.getBoundingClientRect().right, width: e.getBoundingClientRect().width })).filter(e => e.width && e.right > innerWidth + 2).slice(-20)), null, 2));
  assert(size.documentWidth <= size.width + 2, `${name}: horizontal page overflow ${JSON.stringify(size)}`); layouts.push({ name, ...size });
};
const widths = async (name) => { for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure(name); } await page.setViewportSize({ width: 1440, height: 1000 }); };
const screenshot = async (name) => { await page.evaluate(() => scrollTo({ top: 0, left: 0, behavior: "instant" })); await page.screenshot({ path: join(out, `${name}.png`), fullPage: true, animations: "disabled" }); await page.screenshot({ path: join(out, `${name}-viewport.png`), animations: "disabled" }); };
const chooseField = async (reference) => {
  const field = page.locator(`[data-field="${reference}"]`).first(); await field.waitFor({ state: "attached" });
  const step = await field.locator("xpath=ancestor::fieldset").getAttribute("data-edit-step");
  await page.locator(`[data-edit-step-link="${step}"]`).click();
  await field.waitFor(); return field;
};
try {
  await page.goto(base + "/app/settings"); await page.getByRole("tablist", { name: "Oddíly nastavení" }).waitFor();
  assert.equal(await page.getByRole("tab").count(), 10);
  // At 1440 every tab shows its line under its name (settings-redesign 1).
  assert.equal(await page.locator("[data-tab-subtitle]:visible").count(), 10);
  for (const id of ["ai", "prompts", "deep_research", "methodology", "access", "studies", "audit", "system", "reference", "data"]) {
    const panel = await tab(id); await panel.locator("h2").first().waitFor();
    if (id === "prompts") await page.getByLabel("Instrukce", { exact: true }).waitFor();
    if (id === "deep_research") await page.locator("[data-dr-setting]").first().waitFor({ state: "attached" });
    if (id === "methodology") await page.locator("[data-methodology-editor]").waitFor(); // an administrator opens on the editor
    await widths(`tab ${id}`); await screenshot(id);
  }
  checks.push("All ten settings tabs load and fit desktop/tablet/phone without page overflow; each names its purpose under its name at 1440");
  // One technical switch per page instead of a disclosure arrow by every value (product owner, 2026-10-13).
  for (const id of ["ai", "access", "studies", "audit", "reference"]) {
    const panel = await tab(id);
    assert.equal(await panel.locator("details, summary").count(), 0, `${id}: a disclosure is back`);
    assert.match(await panel.locator("[data-tab-facts]").innerText(), /^Platí pro: .+ · Mění: .+/);
    for (const [width, height] of [[1710, 1000], [1920, 1080]]) { await page.setViewportSize({ width, height }); await measure(`tab ${id} ${width}`); }
    await page.setViewportSize({ width: 1440, height: 900 }); await measure(`tab ${id} 1440x900`); await page.setViewportSize({ width: 1440, height: 1000 });
  }
  const techPanel = await tab("reference"); const techSwitch = techPanel.getByRole("switch", { name: "Technické údaje", exact: true });
  const t0 = Date.now(); await techSwitch.click(); await techPanel.locator("[data-technical]").first().waitFor(); const techMs = Date.now() - t0;
  assert(techMs < 400, `technical details: ${techMs} ms`); await widths("reference with technical details"); await screenshot("reference-technical");
  await techSwitch.click(); assert.equal(await techPanel.locator("[data-technical]").count(), 0);
  checks.push(`Settings tabs carry no disclosures; one switch shows every technical detail in ${techMs} ms (< 400 ms)`);
  await tab("reference"); await page.getByRole("searchbox", { name: "Hledat technickou hodnotu" }).fill("databáze");
  assert.equal(await page.locator('[data-setting="database_backend"]').count(), 1);
  assert(await page.getByText("Typ databáze, ve které AIA ukládá pracovní obsah a historii.").isVisible());
  checks.push("Reference search finds purpose as well as identifiers; technical settings explain their ownership");
  await tab("access");
  const email = `ux.settings.${Date.now()}@example.invalid`;
  const add = page.getByRole("button", { name: "Přidat člena", exact: true }).locator("xpath=ancestor::form");
  assert.equal(await add.getByRole("combobox", { name: "Role", exact: true }).inputValue(), "MEMBER");
  await add.getByLabel("E-mail", { exact: true }).fill(email); await add.getByLabel("Jméno", { exact: true }).fill("Fictional UX reader"); await add.getByRole("button", { name: "Přidat člena", exact: true }).click();
  const member = page.locator("[data-member]").filter({ has: page.getByText(email, { exact: true }) }); await member.waitFor();
  await member.getByRole("button", { name: "Upravit", exact: true }).click();
  const memberEdit = page.locator(`[data-member-edit="${await member.getAttribute("data-member")}"]`);
  await memberEdit.getByLabel("Jméno", { exact: true }).fill("Fictional UX administrator");
  await memberEdit.getByRole("combobox", { name: `Role: ${email}`, exact: true }).selectOption("ADMIN");
  await memberEdit.getByRole("button", { name: "Uložit", exact: true }).click();
  await member.getByText("Fictional UX administrator", { exact: false }).waitFor();
  const savedMember = (await get("/api/v1/members")).find((m) => m.email === email);
  assert.equal(savedMember.organization_role, "ADMIN"); assert.equal(savedMember.display_name, "Fictional UX administrator");
  await widths("access member editing"); checks.push("New member defaults to researcher; existing name/role edits persist through the audited API");
  await tab("studies");
  const studies = await get("/api/v1/studies"); const study = studies[0]; const original = await get(`/api/v1/studies/${study.study_id}`);
  await page.setViewportSize({ width: 390, height: 1000 });
  const offscreen = await page.locator("[data-study]:not([hidden])").evaluateAll((rows) => rows.filter((row) => { const b = row.querySelector("button")?.getBoundingClientRect(); return !b || b.right > Math.min(innerWidth, row.closest(".overflow-x-auto").getBoundingClientRect().right); }).map((row) => row.dataset.study));
  assert.deepEqual(offscreen, [], "390: a study's Upravit is out of view");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator(`[data-study="${study.study_id}"]`).getByRole("button", { name: "Upravit", exact: true }).click();
  const card = page.locator(`[data-study-edit="${study.study_id}"]`);
  const budget = card.getByLabel("Rozpočet studie", { exact: true }); await budget.fill("20");
  await page.getByRole("searchbox", { name: "Hledat studii nebo klienta" }).fill("no-such-study"); assert(!await card.isVisible());
  await page.getByRole("searchbox", { name: "Hledat studii nebo klienta" }).fill(""); assert.equal(await budget.inputValue(), "20");
  await budget.locator("xpath=ancestor::form").getByRole("button", { name: "Uložit", exact: true }).click();
  await card.getByText("Uloženo.", { exact: true }).waitFor(); assert.equal((await get(`/api/v1/studies/${study.study_id}`)).budget_usd, 20);
  if (original.budget_usd !== null) { await budget.fill(String(original.budget_usd)); await budget.locator("xpath=ancestor::form").getByRole("button", { name: "Uložit", exact: true }).click(); }
  checks.push("Study filtering retains budget drafts; a budget edit persists to exactly the selected study");
  await tab("audit"); await page.getByRole("searchbox", { name: "Hledat v historii" }).fill(email);
  assert(await page.locator("#panel-audit li").count());
  await page.getByRole("searchbox", { name: "Hledat v historii" }).fill("no-such-event"); await page.getByText("Žádný záznam neodpovídá hledání.", { exact: true }).waitFor();
  checks.push("Readable audit entries filter by person, event and reason");
  await tab("deep_research"); const policyKey = "retention.snapshots";
  await page.getByRole("searchbox", { name: "Hledat pravidlo rešerše" }).fill("zachycené");
  const row = page.locator(`[data-dr-setting="${policyKey}"]`); await row.getByRole("button", { name: "Upravit", exact: true }).click();
  const ruleDetail = page.locator(`[data-dr-detail="${policyKey}"]`); const policyForm = ruleDetail.locator("[data-dr-propose]"); await policyForm.getByLabel("Hodnota", { exact: true }).fill("365");
  await row.getByRole("button", { name: "Zavřít", exact: true }).click(); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
  assert.equal(await policyForm.getByLabel("Hodnota", { exact: true }).inputValue(), "365");
  await tab("prompts"); await tab("deep_research"); assert.equal(await policyForm.getByLabel("Hodnota", { exact: true }).inputValue(), "365");
  await widths("research policy editor");
  await policyForm.getByRole("button", { name: "Uložit návrh", exact: true }).click();
  await ruleDetail.locator("[data-dr-version]").last().waitFor();
  let policy = await get(`/api/v1/deep-research/settings/${policyKey}`); const policyVersion = policy.versions.find((v) => v.value === 365);
  assert(policyVersion); assert.equal(policy.origin, "proposed_default");
  await ruleDetail.getByRole("button", { name: `Schválit verzi ${policyVersion.version_number}`, exact: true }).click();
  await ruleDetail.locator("[data-dr-approve]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  await row.locator('[data-origin="approved"]').waitFor(); policy = await get(`/api/v1/deep-research/settings/${policyKey}`); assert.equal(policy.value, 365);
  await ruleDetail.getByRole("button", { name: "Vrátit na výchozí", exact: true }).click(); await ruleDetail.locator("[data-dr-approve]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  checks.push("Policy purpose search, draft protection across close/tab changes and separate propose/approve work through real APIs");
  await tab("methodology");
  // An administrator opens on the editor, its five-step sequence on the first screen (product owner, 2026-10-13).
  const methodEditor = page.locator("[data-methodology-editor]"); await methodEditor.waitFor();
  for (const [width, height] of [[1440, 900], [1710, 1000], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => scrollTo(0, 0));
    const flow = await page.locator("[data-methodology-flow]").boundingBox(); assert(flow && flow.y + flow.height <= height, `${width}: the change sequence is below the fold (${flow?.y})`);
    await measure(`methodology editor ${width}`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Visible feedback inside the Doherty threshold: a step opens, a typed value shows in the draft.
  const doherty = async (name, act, done) => { const t0 = Date.now(); await act(); await done(); const ms = Date.now() - t0; assert(ms < 400, `${name}: ${ms} ms`); return ms; };
  const stepLink = methodEditor.locator("[data-edit-step-link]").nth(3); const stepId = await stepLink.getAttribute("data-edit-step-link");
  const openMs = await doherty("open a step", () => stepLink.click(), () => methodEditor.locator(`[data-edit-step="${stepId}"]`).waitFor({ state: "visible" }));
  const sigmaField = await chooseField("terrain.sigma");
  const typeMs = await doherty("a typed value reaches the draft", () => sigmaField.fill("0,29"), () => methodEditor.getByRole("complementary", { name: "Dopad a rozhodnutí" }).getByText("0,29").waitFor());
  checks.push(`Metodika opens on the editor with its sequence above the fold at 1440/1710/1920; a step opens in ${openMs} ms and a typed value reaches the draft in ${typeMs} ms (< 400 ms)`);
  // The read-only explanation is the editor's other side: close it, and the catalogue is there.
  await methodEditor.getByRole("button", { name: "Zrušit", exact: true }).click();
  if (await page.getByRole("button", { name: "Zahodit neuložené úpravy", exact: true }).count()) await page.getByRole("button", { name: "Zahodit neuložené úpravy", exact: true }).click();
  await methodEditor.waitFor({ state: "detached" });
  await page.getByRole("searchbox", { name: "Hledat výpočet nebo parametr" }).waitFor();

  const defaultHeight = await page.locator("#panel-methodology").evaluate((e) => e.scrollHeight); assert(defaultHeight < 4500, `Methodology default height ${defaultHeight}`);
  await page.getByRole("searchbox", { name: "Hledat výpočet nebo parametr" }).fill("Kish"); assert(await page.locator("#panel-methodology article").count());
  for (const disclosure of await page.locator("#panel-methodology article details").all()) { if (!await disclosure.evaluate((e) => e.open)) await disclosure.locator("summary").first().click(); }
  await widths("methodology technical and formula details");
  await page.getByRole("searchbox", { name: "Hledat výpočet nebo parametr" }).fill("");
  const beforeVersions = await get("/api/v1/methodology/sociomap/versions");
  await page.getByRole("button", { name: "Upravit metodiku", exact: true }).click();
  const methodForm = page.locator("[data-methodology-editor]");
  await (await chooseField("terrain.sigma")).fill("0,3"); await (await chooseField("relation.n_min")).fill("2");
  await methodForm.getByRole("button", { name: "Zkontrolovat", exact: true }).click(); await methodForm.getByText(/Kontrola neprošla/).waitFor();
  assert.equal((await get("/api/v1/methodology/sociomap/versions")).versions.length, beforeVersions.versions.length);
  await (await chooseField("relation.n_min")).fill("34"); assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  await methodForm.getByLabel("Začít od metodiky z kódu", { exact: true }).selectOption("aia-sociomap-2"); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
  assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  await page.getByRole("button", { name: "Změnit oblast", exact: true }).click();
  await page.getByRole("button", { name: "Sociomapa: referenční mapa (18.6.6)", exact: true }).click(); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
  await widths("methodology editor"); await screenshot("methodology-editor");
  await methodForm.getByRole("button", { name: "Porovnat s metodikou v platnosti", exact: true }).click();
  await page.locator("[data-methodology-compare]").waitFor(); await widths("methodology comparison");
  await (await chooseField("terrain.sigma")).fill("0,31"); assert.equal(await page.locator("[data-methodology-compare]").count(), 0);
  await (await chooseField("terrain.sigma")).fill("0,3");
  let refused = false;
  await page.route("**/api/v1/methodology/sociomap/versions", (route) => { if (route.request().method() === "POST" && !refused) { refused = true; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "local_save_refused", message: "Local acceptance refusal" }) }); } return route.continue(); });
  await methodForm.getByRole("button", { name: "Zkontrolovat a uložit", exact: true }).click(); await methodForm.getByRole("alert").filter({ hasText: "Local acceptance refusal" }).waitFor();
  assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  await methodForm.getByRole("button", { name: "Zkontrolovat a uložit", exact: true }).click();
  await methodForm.waitFor({ state: "detached" }); await page.unroute("**/api/v1/methodology/sociomap/versions");
  let versions = await get("/api/v1/methodology/sociomap/versions"); const created = versions.versions.find((v) => v.spec.terrain.sigma === 0.3 && v.spec.relation.n_min === 34 && !beforeVersions.versions.some((old) => old.version_number === v.version_number)); assert(created); assert.equal(versions.in_force.origin, "code");
  // Right after a save its confirmation offers the activation, the one button for that version.
  await page.getByRole("button", { name: `Uvést ${created.name} v platnost`, exact: true }).click();
  await page.locator("[data-methodology-activate]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  await page.locator("[data-in-force]").filter({ hasText: created.name }).waitFor(); await page.reload();
  await page.locator("[data-in-force]").filter({ hasText: created.name }).waitFor();
  versions = await get("/api/v1/methodology/sociomap/versions"); assert.equal(versions.in_force.version_number, created.version_number);
  await screenshot("methodology-activated");
  await page.getByRole("button", { name: /Vrátit na .* z kódu/ }).click(); await page.locator("[data-methodology-activate]").getByRole("button", { name: "Potvrdit", exact: true }).click();
  checks.push("Methodology section edits retain values, invalid fields reject, replacements guard, stale comparisons clear, failed saves retry, saved versions activate separately and survive reload");
  assert.equal(writes.filter((r) => /agent-jobs|research\/runs|deep-research\/runs/.test(r.path)).length, 0); assert.deepEqual(errors, []);
  const report = { status: "PASS", checks, layouts, writes, pageErrors: errors, paidJobs: 0, defaultMethodologyHeight: defaultHeight }; writeFileSync(join(out, "checks.json"), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ ...report, writes: writes.length, layouts: layouts.length, out }, null, 2));
} catch (error) { await page.screenshot({ path: join(out, "failure.png"), fullPage: true }); writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(error), checks, layouts, writes, pageErrors: errors }, null, 2)); throw error; }
finally { await browser.close(); }
