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
const waitFor = async (check, what, ms = 15000) => { const end = Date.now() + ms; while (Date.now() < end) { if (await check()) return; await page.waitForTimeout(250); } throw new Error(`timed out: ${what}`); };
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
    if (id === "ai") {
      for (const g of ["study", "run", "out", "dr", "client"]) assert.equal(await page.locator(`[data-ai-group="${g}"]`).count(), 1, `ai: group ${g}`);
      assert.equal(await page.locator('[data-activity="run_qc"][data-state="not_built"]').count(), 1, "ai: a not-built activity says so");
      await page.locator("#panel-ai [data-config]").waitFor();
    }
    if (id === "prompts") {
      await page.getByLabel("Instrukce", { exact: true }).waitFor();
      assert.equal(await page.locator("[data-change-steps] li").count(), 3, "prompts: three steps of a change");
      assert(await page.locator('[data-group="editable"] [data-prompt]').count() > 0 && await page.locator('[data-group="readOnly"] [data-prompt]').count() > 0, "prompts: editable and read-only groups");
      assert.equal(await page.locator("#panel-prompts").getByRole("button", { name: /Vyzkoušet/ }).count(), 0, "prompts: no test button (X10)");
      await page.locator("[data-prompt-in-force]").waitFor();
    }
    if (id === "deep_research") await page.locator("[data-dr-setting]").first().waitFor({ state: "attached" });
    if (id === "methodology") await page.locator("[data-methodology-editor]").waitFor(); // an administrator opens on the editor
    // Until #839 and #850 are deployed, both boards say so where they are met, never a fabricated state.
    // Before #839 / #850 are deployed each board says it is not in AIA yet; after, it reads its route.
    // Either way it settles on one of the states it can say, never stays loading or invents one.
    if (id === "system") {
      await page.locator("[data-system-readiness] :is([data-not-yet], [data-smoke-check], [data-smoke-none], [role=alert])").first().waitFor();
      await page.locator("[data-system-errors] :is([data-not-yet], [data-glitchtip-unconfigured], h4, [role=alert])").first().waitFor();
    }
    if (id === "data") {
      await page.locator("[data-kept-records] :is([data-not-yet], table, [role=alert])").first().waitFor();
      assert(await page.locator("[data-client-delete] select option").count() > 1, "data: the clients to choose from");
    }
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
  const techPanel = await tab("reference");
  assert(await techPanel.locator("[data-reference-category]").count() > 2, "reference: categories");
  await techPanel.getByRole("radiogroup", { name: "Kdo mění" }).getByRole("radio", { name: "Pevné pravidlo", exact: true }).click();
  assert.equal(await techPanel.locator('[data-owner="deployment"]').count(), 0, "reference: the owner filter");
  await techPanel.getByRole("radiogroup", { name: "Kdo mění" }).getByRole("radio", { name: "Vše", exact: true }).click(); const techSwitch = techPanel.getByRole("switch", { name: "Technické údaje", exact: true });
  const t0 = Date.now(); await techSwitch.click(); await techPanel.locator("[data-technical]").first().waitFor(); const techMs = Date.now() - t0; console.log(`technical details: ${techMs} ms`);
  assert(techMs < 400, `technical details: ${techMs} ms`); await widths("reference with technical details"); await screenshot("reference-technical");
  await techSwitch.click(); assert.equal(await techPanel.locator("[data-technical]").count(), 0);
  checks.push(`Settings tabs carry no disclosures; one switch shows every technical detail in ${techMs} ms (< 400 ms)`);
  await tab("reference"); await page.getByRole("searchbox", { name: "Hledat technickou hodnotu" }).fill("databáze");
  assert.equal(await page.locator('[data-setting="database_backend"]').count(), 1);
  assert(await page.getByText("Typ databáze, ve které AIA ukládá pracovní obsah a historii.").isVisible());
  checks.push("Reference search finds purpose as well as identifiers; technical settings explain their ownership");
  await tab("access");
  // A client's posture and wallet ceiling are read here (#853) and set on its profile (D-17): before
  // the route is deployed each row says so; after, each row its posture. Never a ceiling of 0.
  await page.locator("[data-client] :is([data-not-yet], [data-client-rules=read], [data-client-rules=unknown])").first().waitFor();
  const clientRows = await page.locator("[data-client]").count();
  const settled = await page.locator("[data-client] :is([data-not-yet], [data-client-rules=read], [data-client-rules=unknown])").count();
  assert.equal(settled, clientRows, "access: every client's rules settled (not in AIA yet, read or unknown)");
  for (const row of await page.locator('[data-client-rules="read"]').all()) assert.match(await row.innerText(), /OPEN|CLASSIFIED/, "access: a read row names its posture");
  assert(!/0,00\s*USD/.test(await page.locator("#set-clients").innerText()), "access: no ceiling reads 0");
  const email = `ux.settings.${Date.now()}@example.invalid`;
  // The redesign (settings-redesign 3): add in an inline row, name and role changed where they are shown.
  await page.getByRole("button", { name: "+ Přidat člena", exact: true }).click();
  const newRole = page.getByRole("radiogroup", { name: "Role nového člena", exact: true });
  assert.equal(await newRole.getByRole("radio", { name: "výzkumník", exact: true }).getAttribute("aria-checked"), "true");
  await page.getByLabel("E-mail nového člena", { exact: true }).fill(email); await page.getByLabel("E-mail nového člena", { exact: true }).press("Enter");
  const member = page.locator("[data-member]").filter({ has: page.getByText(email, { exact: true }) }); await member.waitFor();
  await member.getByRole("button", { name: new RegExp(`^Upravit: Jméno: ${email.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`) }).click();
  const nameField = member.getByLabel(`Jméno: ${email}`, { exact: true }); await nameField.fill("Fictional UX administrator"); await nameField.press("Enter");
  await page.getByRole("radiogroup", { name: `Role: ${email}`, exact: true }).getByRole("radio", { name: "správce", exact: true }).click();
  await page.getByText(/je správce · zapsáno do auditu/).waitFor();
  await member.getByText("Fictional UX administrator", { exact: false }).waitFor();
  const savedMember = (await get("/api/v1/members")).find((m) => m.email === email);
  assert.equal(savedMember.organization_role, "ADMIN"); assert.equal(savedMember.display_name, "Fictional UX administrator");
  await widths("access member editing"); checks.push("New member is added in an inline row as a researcher; name and role change in place and persist through the audited API, with Vrátit");
  // The Metodik mark (#823): the OWNER grants it in the row, Vrátit takes it back; the API agrees.
  const markSwitch = page.getByRole("switch", { name: `Štítek Metodik: ${email}`, exact: true });
  await markSwitch.click(); await page.getByText(/ho má · zapsáno do auditu/).waitFor();
  await waitFor(async () => (await get("/api/v1/members")).find((m) => m.email === email)?.methodologist === true, "the mark reached the member");
  await page.getByRole("button", { name: "Vrátit", exact: true }).click();
  await waitFor(async () => (await get("/api/v1/members")).find((m) => m.email === email)?.methodologist === false, "Vrátit took the mark back");
  // Deactivation (#830): at once, the Lead sealed with its erasure dated; Obnovit restores the member.
  await page.getByRole("button", { name: `Deaktivovat ${email}`, exact: true }).click();
  await waitFor(async () => !!(await get("/api/v1/members")).find((m) => m.email === email)?.deactivated_at, "the member deactivated");
  const sealedRow = page.locator(`[data-member="${savedMember.user_id}"][data-deactivated="true"]`); await sealedRow.waitFor();
  // Sealed only when the API reports a seal; this fictional member never hatched a Lead, so none is claimed.
  const deactivatedMember = (await get("/api/v1/members")).find((m) => m.email === email);
  await page.locator(deactivatedMember.lead_sealed_at ? `[data-lead-sealed="${savedMember.user_id}"]` : `[data-lead-none="${savedMember.user_id}"]`).waitFor();
  await widths("access deactivated member");
  await page.getByRole("button", { name: `Obnovit ${email}`, exact: true }).click();
  await waitFor(async () => !(await get("/api/v1/members")).find((m) => m.email === email)?.deactivated_at, "the member restored");
  checks.push("The OWNER grants the Metodik mark in the row and Vrátit takes it back; a member is deactivated with their Lead sealed and dated, and Obnovit restores them; the API agrees each time");
  await tab("studies");
  const studies = await get("/api/v1/studies"); const study = studies[0]; const original = await get(`/api/v1/studies/${study.study_id}`);
  const studyRow = page.locator(`[data-study="${study.study_id}"]`);
  const budget = studyRow.getByRole("spinbutton", { name: `Rozpočet studie ${study.name}`, exact: true });
  await budget.waitFor();
  const target = Math.max(20, Math.ceil(original.spent_usd ?? 0) + 10);
  await budget.fill(String(target));
  await page.getByRole("searchbox", { name: "Hledat studii nebo klienta" }).fill("no-such-study"); assert(!await studyRow.isVisible());
  await page.getByRole("searchbox", { name: "Hledat studii nebo klienta" }).fill(""); { const typed = await budget.inputValue(); assert.equal(Number(typed.replace(/\s/g, "").replace(",", ".")), target, `typed budget reads ${JSON.stringify(typed)}`); }
  await budget.press("Enter");
  await waitFor(async () => (await get(`/api/v1/studies/${study.study_id}`)).budget_usd === target, "the stepped budget reached the study");
  await widths("studies table");
  if (original.budget_usd !== null) { await budget.fill(String(original.budget_usd)); await budget.press("Enter"); await waitFor(async () => (await get(`/api/v1/studies/${study.study_id}`)).budget_usd === original.budget_usd, "the original budget restored"); }
  checks.push("Study filtering retains a typed budget; the budget stepper persists to exactly the selected study and the table holds at every width");
  await tab("audit");
  assert(await page.locator('[data-audit-category="access"]').count() === 1, "audit: categories with counts");
  await page.getByRole("radiogroup", { name: "Období" }).getByRole("radio", { name: "Vše", exact: true }).click();
  await page.getByRole("searchbox", { name: "Hledat v historii" }).fill(email);
  assert(await page.locator("#panel-audit [data-audit-entry]").count(), "audit: the member added is in the history");
  await widths("audit table");
  await page.getByRole("searchbox", { name: "Hledat v historii" }).fill("no-such-event"); await page.getByText("Žádný záznam neodpovídá hledání.", { exact: true }).waitFor();
  checks.push("Readable audit entries filter by person, event and reason");
  await tab("deep_research"); const policyKey = "retention.snapshots";
  assert.equal(await page.locator("[data-dr-reach] [data-not-yet]").count(), 1, "deep research: Dosah says it is not in AIA yet");
  assert.equal(await page.locator("[data-dr-protections] li").count(), 5, "deep research: the code's five protections");
  await page.locator("[data-dr-posture]").getByRole("link", { name: "Přístup a schvalování", exact: true }).waitFor();
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
  await ruleDetail.locator("[data-dr-approve]").getByRole("button", { name: "Schválit", exact: true }).click();
  await row.locator('[data-origin="approved"]').waitFor(); policy = await get(`/api/v1/deep-research/settings/${policyKey}`); assert.equal(policy.value, 365);
  await ruleDetail.getByRole("button", { name: "Vrátit na výchozí", exact: true }).click(); await ruleDetail.locator("[data-dr-approve]").getByRole("button", { name: "Vrátit na výchozí", exact: true }).click();
  // A proposal made in the rule's Návrh cell waits, highlighted, until approved through the modal.
  await page.locator("[data-dr-approve]").waitFor({ state: "detached" });
  await row.getByRole("button", { name: "Zavřít", exact: true }).click();
  const inPlace = row.getByRole("spinbutton", { name: /^Návrh:/ }); await inPlace.fill("200"); await inPlace.press("Enter");
  await page.locator(`[data-dr-setting="${policyKey}"][data-pending]`).waitFor();
  await widths("research policy waiting proposal");
  await row.getByRole("button", { name: "Schválit", exact: true }).click();
  const modal = page.locator("dialog [data-dr-approve]"); await modal.getByText("200 dní", { exact: false }).waitFor();
  await modal.getByRole("button", { name: "Schválit", exact: true }).click();
  await page.locator(`[data-dr-setting="${policyKey}"]:not([data-pending])`).waitFor();
  assert.equal((await get(`/api/v1/deep-research/settings/${policyKey}`)).value, 200);
  await row.getByRole("button", { name: "Upravit", exact: true }).click();
  await ruleDetail.getByRole("button", { name: "Vrátit na výchozí", exact: true }).click(); await ruleDetail.locator("[data-dr-approve]").getByRole("button", { name: "Vrátit na výchozí", exact: true }).click();
  await page.locator("[data-dr-approve]").waitFor({ state: "detached" });
  checks.push("A rule's proposal made in its Návrh cell waits highlighted and is approved through the I7 modal; Dosah says it is not in AIA yet");
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
  // The cards: a drawing each, no category, neither the reference map nor the H-Model (D-13).
  assert(await page.locator("[data-module-card] svg").count() >= 6, "methodology: each card its drawing");
  assert.equal(await page.locator('[data-module-card="sociomap_reference"], [data-module-card="sociomapping"]').count(), 0, "methodology: D-13");
  await widths("methodology cards");
  await page.getByRole("button", { name: "Vážení: která váha patří respondentovi a co s neplatnou", exact: true }).click(); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
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
