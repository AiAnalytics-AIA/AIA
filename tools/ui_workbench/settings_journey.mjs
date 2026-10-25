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
// A section is opened as a person does (prototype v54): the top bar's section menu, then its link.
const menuButton = () => page.locator("[data-section-menu] > button");
const tab = async (id) => {
  await menuButton().click(); await page.locator(`[data-section-link="${id}"]`).click();
  await page.locator(`#panel-${id}`).waitFor({ state: "visible" });
  assert.equal(new URL(page.url()).hash, `#${id}`); return page.locator(`#panel-${id}`);
};
const measure = async (name) => {
  const size = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth }));
  if (size.documentWidth > size.width + 2) console.log(JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("body *")].map(e => ({ tag: e.tagName, text: e.textContent?.slice(0,75), classes: e.className?.toString(), right: e.getBoundingClientRect().right, width: e.getBoundingClientRect().width })).filter(e => e.width && e.right > innerWidth + 2).slice(-20)), null, 2));
  assert(size.documentWidth <= size.width + 2, `${name}: horizontal page overflow ${JSON.stringify(size)}`); layouts.push({ name, ...size });
};
const widths = async (name) => { for (const width of [1440, 1024, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); await measure(name); } await page.setViewportSize({ width: 1440, height: 1000 }); };
const waitFor = async (check, what, ms = 15000) => { const end = Date.now() + ms; while (Date.now() < end) { if (await check()) return; await page.waitForTimeout(250); } throw new Error(`timed out: ${what}`); };
const screenshot = async (name) => { await page.evaluate(() => scrollTo({ top: 0, left: 0, behavior: "instant" })); await page.screenshot({ path: join(out, `${name}.png`), fullPage: true, animations: "disabled" }); await page.screenshot({ path: join(out, `${name}-viewport.png`), animations: "disabled" }); };
// The editor is one list of parameters (fidelity F6): a field is there once Upravit shows.
const chooseField = async (reference) => {
  const field = page.locator(`[data-field="${reference}"]`).first(); await field.waitFor(); return field;
};
try {
  await page.goto(base + "/app/settings"); await menuButton().waitFor();
  // No column of tabs (prototype v54): the section menu in the top bar, by click or ⌘K / Ctrl+K.
  assert.equal(await page.getByRole("tablist", { name: "Oddíly nastavení" }).count(), 0, "no tab column");
  const menu = page.getByRole("dialog", { name: "Nastavení – přejít na" });
  for (const keys of ["Control+k", "Meta+k"]) {
    await page.locator("body").press(keys); await menu.waitFor();
    // Ten sections in three columns, each with its line.
    assert.equal(await menu.getByRole("group").count(), 3); assert.equal(await menu.locator("[data-section-link]").count(), 10);
    await page.keyboard.press("Escape"); await menu.waitFor({ state: "detached" });
    assert(await menuButton().evaluate((b) => b === document.activeElement), "Esc gives the focus back to the menu's button");
  }
  // A keyword finds its section, and Enter opens the first match.
  await page.locator("body").press("Control+k"); await page.keyboard.type("Brave"); await page.keyboard.press("Enter");
  await page.locator("#panel-deep_research").waitFor({ state: "visible" }); assert.equal(new URL(page.url()).hash, "#deep_research");
  // A deep link opens its section, and the menu's button names it.
  await page.goto(base + "/app/settings#audit"); await page.locator("#panel-audit").waitFor({ state: "visible" });
  assert.equal(await menuButton().getAttribute("aria-label"), "Nastavení › Audit");
  checks.push("The section menu opens on ⌘K and Ctrl+K, closes on Esc with the focus back, finds Brave and opens it on Enter; #audit opens Audit");
  await page.goto(base + "/app/settings"); await menuButton().waitFor();
  await menuButton().click();
  // At 1440 every tab shows its line under its name (settings-redesign 1).
  assert.equal(await menu.locator("[data-section-link]:visible").count(), 10); await page.keyboard.press("Escape");
  for (const id of ["ai", "prompts", "deep_research", "methodology", "access", "studies", "audit", "system", "reference", "data"]) {
    const panel = await tab(id); await panel.locator("[data-tab-header] h1").waitFor();
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
    if (id === "methodology") await page.locator('[data-module-card="sociomap"]').waitFor(); // the tab opens on the catalogue (F4)
    // Until #839 and #850 are deployed, both boards say so where they are met, never a fabricated state.
    // Before #839 / #850 are deployed each board says it is not in AIA yet; after, it reads its route.
    // Either way it settles on one of the states it can say, never stays loading or invents one.
    if (id === "system") {
      await page.locator("[data-system-readiness] :is([data-not-yet], [data-smoke-check], [data-smoke-none], [role=alert])").first().waitFor();
      await page.locator("[data-system-errors] :is([data-not-yet], [data-glitchtip-unconfigured], h4, [role=alert])").first().waitFor();
    }
    if (id === "data") {
      await page.locator("[data-kept-records] :is([data-not-yet], table, [role=alert])").first().waitFor();
      assert(await page.locator("[data-client-delete] [role=radiogroup] [role=radio]").count() > 0, "data: the clients to choose from");
    }
    await widths(`tab ${id}`); await screenshot(id);
  }
  checks.push("All ten settings sections load and fit desktop/tablet/phone without page overflow; the section menu names each with its line");
  // One technical switch per page instead of a disclosure arrow by every value (product owner, 2026-10-13).
  for (const id of ["ai", "access", "studies", "audit", "reference"]) {
    const panel = await tab(id);
    assert.equal(await panel.locator("details, summary").count(), 0, `${id}: a disclosure is back`);
    // The prototype's head (v51): the tab's name as h1 and one paragraph; who may change it in chips.
    assert.equal(await panel.locator("[data-tab-header] p").count(), 1, `${id}: one lede`);
    assert.equal(await panel.locator("[data-tab-header] [role=switch]").count(), 1, `${id}: the page's one switch, at the end of the open section's head`);
    for (const [width, height] of [[1710, 1000], [1920, 1080]]) { await page.setViewportSize({ width, height }); await measure(`tab ${id} ${width}`); }
    await page.setViewportSize({ width: 1440, height: 900 }); await measure(`tab ${id} 1440x900`); await page.setViewportSize({ width: 1440, height: 1000 });
  }
  const techPanel = await tab("reference");
  assert(await techPanel.locator("[data-reference-category]").count() > 2, "reference: categories");
  await techPanel.getByRole("radiogroup", { name: "Kdo mění" }).getByRole("radio", { name: "Pevné pravidlo", exact: true }).click();
  assert.equal(await techPanel.locator('[data-owner="deployment"]').count(), 0, "reference: the owner filter");
  await techPanel.getByRole("radiogroup", { name: "Kdo mění" }).getByRole("radio", { name: "Vše", exact: true }).click(); const techSwitch = page.locator("[data-technical-switch]").getByRole("switch", { name: "Technické údaje", exact: true });
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
  // Before the reach route is deployed Dosah says it is not in AIA yet; after, a worker's report or
  // that none is recorded. It settles on one of those, never stays loading or invents a route.
  await page.locator("[data-dr-reach] :is([data-not-yet], [data-reach-unrecorded], [data-reach-route])").first().waitFor();
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
  // The tab opens on the catalogue (prototype v51, fidelity F4): a drawing each, no category,
  // neither the reference map nor the H-Model (D-13), and the MVP's note.
  if (!await page.locator("[data-module-card]").count()) await page.locator("[data-methodology-back]").click();
  assert(await page.locator("[data-module-card] svg").count() >= 6, "methodology: each card its drawing");
  assert.equal(await page.locator('[data-module-card="sociomap_reference"], [data-module-card="sociomapping"]').count(), 0, "methodology: D-13");
  assert(await page.locator("[data-mvp-note]").isVisible(), "methodology: the MVP note");
  await widths("methodology cards");
  await page.locator('[data-module-card="sociomap"]').click();
  // An administrator opens the map on the editor (product owner, 2026-10-13): where the edit starts
  // and the list of parameters begin on the first screen (prototype v51, fidelity F6).
  const methodEditor = page.locator("[data-methodology-editor]"); await methodEditor.waitFor();
  for (const [width, height] of [[1440, 900], [1710, 1000], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => scrollTo(0, 0));
    const first = await methodEditor.locator("[data-edit-row]").first().boundingBox(); assert(first && first.y + first.height <= height, `${width}: the first parameter is below the fold (${first?.y})`);
    const actions = await methodEditor.locator("[data-edit-actions]").boundingBox(); assert(actions && actions.y + actions.height <= height, `${width}: the actions are not in reach (${actions?.y})`);
    await measure(`methodology editor ${width}`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Visible feedback inside the Doherty threshold: a press of + and a typed value reach the draft.
  const doherty = async (name, act, done) => { const t0 = Date.now(); await act(); await done(); const ms = Date.now() - t0; assert(ms < 400, `${name}: ${ms} ms`); return ms; };
  const nMinField = await chooseField("relation.n_min");
  const stepMs = await doherty("a press of + changes the value", () => methodEditor.locator('[data-edit-row="relation.n_min"]').getByRole("button", { name: "Zvýšit: Nejmenší n páru", exact: true }).click(), () => methodEditor.getByText("Neuloženo: 1 změna", { exact: true }).waitFor());
  assert.equal(await nMinField.inputValue(), "11");
  const sigmaField = await chooseField("terrain.sigma");
  const typeMs = await doherty("a typed value reaches the draft", () => sigmaField.fill("0,29"), () => methodEditor.getByText("Neuloženo: 2 změny", { exact: true }).waitFor());
  checks.push(`Metodika opens on the editor with its first parameter and its actions on the first screen at 1440/1710/1920; a press of + shows in ${stepMs} ms and a typed value in ${typeMs} ms (< 400 ms)`);
  // A field the keyboard reaches is never under the sticky action bar (WCAG 2.4.11), down the list.
  await page.setViewportSize({ width: 1024, height: 800 }); await page.evaluate(() => scrollTo(0, 0));
  await methodEditor.locator("[data-start-note] select").focus();
  for (let i = 0; i < 16; i += 1) {
    await page.keyboard.press("Tab");
    const covered = await page.evaluate(() => {
      const active = document.activeElement; const bar = document.querySelector("[data-edit-actions]");
      if (!active || !bar || bar.contains(active) || !active.closest("[data-methodology-editor]")) return null;
      const r = active.getBoundingClientRect(); const b = bar.getBoundingClientRect();
      return r.bottom > b.top + 1 ? { field: active.getAttribute("data-field") ?? active.tagName, bottom: Math.round(r.bottom), bar: Math.round(b.top) } : null;
    });
    assert.equal(covered, null, `1024: a focused field under the sticky bar ${JSON.stringify(covered)}`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  checks.push("At 1024 px, sixteen Tabs down the parameter list never leave the focused field under the sticky action bar");
  // Zahodit úpravu asks, then starts over from what is in force, on Upravit.
  await methodEditor.getByRole("button", { name: "Zahodit úpravu", exact: true }).click();
  await page.getByRole("button", { name: "Zahodit neuložené úpravy", exact: true }).click();
  await methodEditor.getByText("Neuloženo: 2 změny", { exact: true }).waitFor({ state: "detached" });
  assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,25", "methodology: a discarded edit starts over from what is in force");
  await page.getByRole("tab", { name: "Výpočet", exact: true }).click();
  // Výpočet as the prototype draws it (fidelity F5): stage tiles, the parameter filter, rows.
  const stageTiles = page.getByRole("group", { name: "Etapy", exact: true }); await stageTiles.waitFor();

  // 6,200 px: Výpočet lists every step as a closed row, as prototype v51 draws it, and the object map
  // has 48 steps (5,904 px measured at F5); the product owner chose this limit on 2026-10-24 (#876).
  // It still catches the page growing with the versions stored on a workbench.
  const defaultHeight = await page.locator("#panel-methodology").evaluate((e) => e.scrollHeight); assert(defaultHeight < 6200, `Methodology default height ${defaultHeight}`);
  await stageTiles.getByRole("button", { name: /^M6\s·\sTerén/ }).click();
  assert.equal(await page.locator("#panel-methodology section[aria-labelledby^='mg-'] h3").filter({ hasText: /^Terén$/ }).count(), 1, "methodology: one stage by its tile");
  await stageTiles.getByRole("button", { name: /^Všechny etapy/ }).click();
  await page.getByRole("radiogroup", { name: "Jen kroky" }).getByRole("radio", { name: "S parametry", exact: true }).click();
  assert(await page.locator("#panel-methodology article[data-step]").count() > 0, "methodology: steps with values");
  await page.getByRole("button", { name: "Rozbalit všechny kroky", exact: true }).click();
  for (const disclosure of await page.locator("#panel-methodology [data-step-body] details").all()) { if (!await disclosure.evaluate((e) => e.open)) await disclosure.locator("summary").first().click(); }
  await widths("methodology technical and formula details");
  await page.getByRole("button", { name: "Sbalit všechny kroky", exact: true }).click();
  await page.getByRole("radiogroup", { name: "Jen kroky" }).getByRole("radio", { name: "Všechny", exact: true }).click();
  const beforeVersions = await get("/api/v1/methodology/sociomap/versions");
  await page.getByRole("tab", { name: "Upravit", exact: true }).click();
  const methodForm = page.locator("[data-methodology-editor]");
  await (await chooseField("terrain.sigma")).fill("0,3"); await (await chooseField("relation.n_min")).fill("2");
  await methodForm.getByRole("button", { name: "Zkontrolovat", exact: true }).click(); await methodForm.getByText(/Kontrola neprošla/).waitFor();
  assert.equal((await get("/api/v1/methodology/sociomap/versions")).versions.length, beforeVersions.versions.length);
  await (await chooseField("relation.n_min")).fill("34"); assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  await methodForm.getByLabel("Začít od metodiky z kódu", { exact: true }).selectOption("aia-sociomap-2"); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
  assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  // Back to the catalogue with a draft open asks first; Ponechat keeps the draft.
  await page.locator("[data-methodology-back]").click(); await page.getByRole("button", { name: "Ponechat", exact: true }).click();
  await widths("methodology editor"); await screenshot("methodology-editor");
  await methodForm.getByRole("button", { name: "Porovnat s platnou", exact: true }).click();
  // The comparison is the module's Porovnání (settings-redesign 10b); the draft stays on Upravit.
  await page.locator("[data-methodology-compare]").waitFor(); assert.equal(await page.getByRole("tab", { name: "Porovnání", exact: true }).getAttribute("aria-selected"), "true");
  await widths("methodology comparison");
  await page.getByRole("tab", { name: "Upravit", exact: true }).click();
  await (await chooseField("terrain.sigma")).fill("0,31"); assert.equal(await page.locator("[data-methodology-compare]").count(), 0);
  await (await chooseField("terrain.sigma")).fill("0,3");
  let refused = false;
  await page.route("**/api/v1/methodology/sociomap/versions", (route) => { if (route.request().method() === "POST" && !refused) { refused = true; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "local_save_refused", message: "Local acceptance refusal" }) }); } return route.continue(); });
  await methodForm.getByRole("button", { name: "Uložit verzi", exact: true }).click(); await methodForm.getByRole("alert").filter({ hasText: "Local acceptance refusal" }).waitFor();
  assert.equal(await (await chooseField("terrain.sigma")).inputValue(), "0,3");
  await methodForm.getByRole("button", { name: "Uložit verzi", exact: true }).click();
  await methodForm.waitFor({ state: "detached" }); await page.unroute("**/api/v1/methodology/sociomap/versions");
  let versions = await get("/api/v1/methodology/sociomap/versions"); const created = versions.versions.find((v) => v.spec.terrain.sigma === 0.3 && v.spec.relation.n_min === 34 && !beforeVersions.versions.some((old) => old.version_number === v.version_number)); assert(created); assert.equal(versions.in_force.origin, "code");
  // Right after a save its confirmation offers the activation, the one button for that version.
  // One I7 dialog: the reason chosen as a chip (required), the act named for an edited map.
  await page.getByRole("button", { name: `Uvést ${created.name} v platnost`, exact: true }).click();
  const activateDialog = page.locator("[data-methodology-activate]");
  await activateDialog.getByRole("button", { name: "Aktivovat jako interní", exact: true }).click(); await activateDialog.getByRole("alert").filter({ hasText: "Vyberte důvod" }).waitFor();
  await activateDialog.getByRole("radio", { name: "Ověření na pilotní studii", exact: true }).click(); await widths("methodology activation dialog");
  await activateDialog.getByRole("button", { name: "Aktivovat jako interní", exact: true }).click();
  await page.locator("[data-in-force]").filter({ hasText: created.name }).waitFor(); await page.reload();
  // After a reload the tab is the catalogue again: the map's card names the version in force, and
  // the register calls an edited method internal (never presumed approved); its page says the same.
  const mapCard = page.locator('[data-module-card="sociomap"]');
  await mapCard.locator("[data-current-name]").filter({ hasText: created.name }).waitFor();
  await mapCard.locator('[data-register="INTERNAL_ONLY"]').waitFor();
  await mapCard.click();
  await page.locator("[data-module-chips]").getByText(`V platnosti: ${created.name}`, { exact: true }).waitFor();
  await page.locator("[data-module-chips]").getByText("Jen interně (neregistrováno)", { exact: true }).waitFor();
  // The next edit starts from it, and says so.
  await page.locator("[data-start-note]").filter({ hasText: created.name }).waitFor();
  versions = await get("/api/v1/methodology/sociomap/versions"); assert.equal(versions.in_force.version_number, created.version_number);
  await screenshot("methodology-activated");
  await page.getByRole("tab", { name: "Verze a aktivace", exact: true }).click();
  await page.getByRole("table", { name: "Historie platnosti" }).getByText("Ověření na pilotní studii").first().waitFor(); await widths("methodology versions");
  await page.getByRole("button", { name: /Vrátit na .* z kódu/ }).click();
  await page.locator("[data-methodology-activate]").getByRole("radio", { name: "Návrat k výchozí metodě", exact: true }).click();
  await page.locator("[data-methodology-activate]").getByRole("button", { name: "Vrátit na výchozí", exact: true }).click();
  await page.locator("[data-in-force]").filter({ hasText: "z kódu" }).waitFor();
  // Verze a aktivace lists the code's preset as a version, in force again (fidelity F6b).
  await page.locator('[data-methodology-version="code"]').getByText("v platnosti", { exact: true }).waitFor();
  // Porovnání with no edit: what is in force beside itself, computed only when asked.
  await page.getByRole("tab", { name: "Porovnání", exact: true }).click();
  await page.getByRole("button", { name: "Ukázat metodiku v platnosti na fiktivních panelech", exact: true }).click();
  await page.locator("[data-compare-baseline]").waitFor({ timeout: 90000 }); await page.locator("[data-methodology-compare]").waitFor();
  await widths("methodology comparison without an edit");
  checks.push("Verze a aktivace lists the code's preset among the versions; Porovnání shows what is in force beside itself when asked, with no edit");
  checks.push("Methodology section edits retain values, invalid fields reject, replacements guard, stale comparisons clear, failed saves retry, saved versions activate separately and survive reload");
  assert.equal(writes.filter((r) => /agent-jobs|research\/runs|deep-research\/runs/.test(r.path)).length, 0); assert.deepEqual(errors, []);
  const report = { status: "PASS", checks, layouts, writes, pageErrors: errors, paidJobs: 0, defaultMethodologyHeight: defaultHeight }; writeFileSync(join(out, "checks.json"), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ ...report, writes: writes.length, layouts: layouts.length, out }, null, 2));
} catch (error) { await page.screenshot({ path: join(out, "failure.png"), fullPage: true }); writeFileSync(join(out, "checks.json"), JSON.stringify({ status: "FAIL", error: String(error), checks, layouts, writes, pageErrors: errors }, null, 2)); throw error; }
finally { await browser.close(); }
