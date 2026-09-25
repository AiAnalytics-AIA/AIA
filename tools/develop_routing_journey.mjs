#!/usr/bin/env node
/**
 * A person's first minutes on the develop product, in a browser, through the
 * committed Caddyfile (ADR 0015): the second half of tools/develop_routing_proof.py.
 *
 *   python3 tools/develop_routing_proof.py --keep     # Caddy and its upstreams, left running
 *   node tools/develop_routing_journey.mjs [OUT_DIR]  # then this; screenshots into OUT_DIR
 *
 * Signed in as /login leaves a person (the gate's cookie and the tab's session),
 * it opens the hostname's root and follows it to the client directory, starts a
 * research under a fictional client, lets the first save bind the study to its
 * unit project, opens the run stage (AIA's: the empty design is not ready), hands
 * off to the classic interface from a stage still there and comes back, and tries two
 * direct routes that must find nothing: another client's study under this
 * client's URL, and a unit project id in a study's place. Prints one line per
 * check; exits 1 on any failure. Needs Playwright with a Chromium (resolved from
 * the environment, as tools/ui_workbench/capture.mjs does).
 */
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

async function playwright() {
  const require = createRequire(import.meta.url);
  try {
    return await import(pathToFileURL(require.resolve("playwright", { paths: [process.cwd()] })).href);
  } catch {
    return await import(pathToFileURL(join(execSync("npm root -g", { encoding: "utf8" }).trim(), "playwright/index.mjs")).href);
  }
}
const { chromium } = await playwright();
const OUT = process.argv[2] || join(dirname(fileURLToPath(import.meta.url)), "../tmp/develop-routing/shots");
mkdirSync(OUT, { recursive: true });
const HOST = "https://aia.localhost";
const OP = "workbench@example.invalid";
const results = [];
const check = (ok, what, got = "") => { results.push(`${ok ? "PASS" : "FAIL"}  ${what}${got ? "  -- " + got : ""}`); };
const api = async (path, init = {}) => {
  const r = await ctx.request.fetch(HOST + "/api/v1" + path, { ...init, headers: { authorization: `Bearer ${OP}`, ...(init.headers || {}) } });
  return { status: r.status(), body: r.ok() ? await r.json().catch(() => null) : null };
};
const browser = await chromium.launch();
// Caddy's local CA for *.localhost is not in Chromium's own store; the proof
// script has already verified these hostnames' TLS against that CA.
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
// Signed in as /login leaves it: the gate's cookie (POST /api/v1/panel/session) and the tab's session.
const opened = await ctx.request.fetch(HOST + "/api/v1/panel/session", { method: "POST", headers: { authorization: `Bearer ${OP}`, origin: HOST } });
check(opened.status() === 204, "panel session opened", String(opened.status()));
const session = JSON.stringify({ idToken: OP, refreshToken: "", expiresAt: 4102444800000, email: OP, subject: OP });
await ctx.addInitScript((s) => sessionStorage.setItem("aia.session", s), session);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

// 1. The product hostname's root is AIA.
const nav = await page.goto(HOST + "/", { waitUntil: "networkidle" });
const chain = []; for (let r = nav.request(); r; r = r.redirectedFrom()) chain.unshift(r.url());
await page.getByRole("heading", { name: "Klienti" }).first().waitFor();
check(new URL(page.url()).pathname === "/app/clients", "/ lands on /app/clients", chain.join(" -> "));
check(!(await page.content()).includes("NPC_BOOT_STAGE"), "no 18.6.6 document in the page");
await page.screenshot({ path: `${OUT}/1-clients.png` });

// 2. Into a client, start a research: a Study of kind RESEARCH, under the client.
await page.getByRole("link", { name: /Horizont Mobility/ }).click();
await page.getByRole("tab", { name: "Přehled" }).or(page.getByRole("link", { name: "Přehled" })).first().waitFor();
const clientId = new URL(page.url()).pathname.split("/")[3];
await page.screenshot({ path: `${OUT}/2-client.png` });
await page.getByRole("button", { name: "Nový výzkum" }).click();
await page.locator("dialog[open] input, dialog[open] textarea").first().fill("Proof · cesta prohlížečem");
await page.locator("dialog[open]").getByRole("button", { name: /OK|Pokračovat|Vytvořit|Potvrdit/ }).first().click();
await page.waitForURL(/\/research\/[^/]+\/brief$/, { timeout: 60000 });
const [, , , , , studyId] = new URL(page.url()).pathname.split("/");
check(new URL(page.url()).pathname === `/app/clients/${clientId}/research/${studyId}/brief`, "new research opens on its brief, under its client", new URL(page.url()).pathname);
await page.getByText("Proof · cesta prohlížečem").first().waitFor();
const crumbs = (await page.locator("nav").filter({ hasText: "Výzkumy" }).first().innerText().catch(() => "")).replace(/\s+/g, " ");
check(/Klienti.*Horizont.*Výzkumy.*Proof.*Zadání/.test(crumbs), "breadcrumbs client / Výzkumy / study / stage", crumbs);
const study = await api(`/studies/${studyId}/workspace`);
check(study.status === 200 && study.body.study.kind === "RESEARCH" && study.body.study.client_id === clientId, "the study is RESEARCH, in this client", `${study.body?.study?.kind} ${study.body?.study?.client_id}`);

// 3. The first save creates the unit project and binds it -- AIA-owned, never looked up by unit id.
const field = page.locator("textarea, input[type=text]").first();
await field.fill("Ověřit, že nová cesta prohlížečem ukládá přes Caddy.");
let bound = null;
for (let i = 0; i < 40 && !bound; i++) { await page.waitForTimeout(500); bound = (await api(`/studies/${studyId}/workspace`)).body?.unit_project_id; }
check(!!bound, "first save bound the study to its unit project", String(bound));
await page.screenshot({ path: `${OUT}/3-brief.png` });

// 4a. The run stage is AIA's (ADR 0016): the design the person sees becomes a
// Design Revision, and AIA's readiness refuses one with no questionnaire yet.
await page.getByRole("link", { name: /Kontrola & Spuštění/ }).click();
await page.waitForURL(/\/run$/, { timeout: 60000 });
await page.getByText("Návrh zatím nelze spustit").first().waitFor({ timeout: 60000 }).catch(() => {});
const start = page.getByRole("button", { name: "Spustit výzkum" });
check((await start.count()) === 1 && (await start.isDisabled()), "run stage is AIA's: the empty design is not ready, no start");
const revisions = await api(`/studies/${studyId}/design/revisions`);
check(revisions.status === 200 && revisions.body.items.length >= 1, "the design on screen was submitted as a Design Revision", `${revisions.status} ${revisions.body?.items?.length} revision(s)`);
await page.screenshot({ path: `${OUT}/4a-run-stage.png` });

// 4b. The hand-off to the classic interface is explicit, labelled and returnable,
// from a stage that still lives there.
await page.goto(`${HOST}/app/clients/${clientId}/research/${studyId}/verify`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const stagePath = new URL(page.url()).pathname;
const classic = page.locator("a[href^='/classic']").first();
const href = await classic.getAttribute("href").catch(() => null);
if (href) {
  await classic.click();
  await page.waitForURL(/\/classic/, { timeout: 60000 });
  const bar = page.locator("#aia-return-bar");
  await bar.waitFor({ timeout: 60000 });
  check((await bar.innerText()).includes("Klasické rozhraní 18.6.6"), "classic page carries its label", (await bar.innerText()).replace(/\s+/g, " "));
  await page.screenshot({ path: `${OUT}/4-classic.png` });
  await bar.getByRole("link", { name: "Zpět do AIA" }).click();
  await page.waitForURL((u) => u.pathname.startsWith("/app/"), { timeout: 60000 });
  check(new URL(page.url()).pathname === stagePath, "Zpět do AIA returns to the stage", `${href} -> ${new URL(page.url()).pathname}`);
} else check(false, "a hand-off link on the stage");

// 5. Isolation: another client's study under this client's URL, and a made-up unit id, fail closed.
const clients = (await api("/workspace/clients")).body;
const lumen = clients.find((c) => c.name.startsWith("Lumen"));
const lumenStudies = (await api(`/clients/${lumen.client_id}/studies`)).body;
await page.goto(`${HOST}/app/clients/${clientId}/research/${lumenStudies[0].study_id}/brief`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const text = await page.locator("main").innerText();
check(/nenalezen|Nenalezeno|neexistuje|nemáte/i.test(text) && !text.includes(lumenStudies[0].name), "Lumen study under Horizont's URL: not found", text.split("\n")[0]);
await page.screenshot({ path: `${OUT}/5-isolation.png` });
await page.goto(`${HOST}/app/clients/${clientId}/research/${bound}/brief`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
check(/nenalezen|Nenalezeno|neexistuje|nemáte/i.test(await page.locator("main").innerText()), "a unit project id in place of a study: not found");
// Knowledge is read only inside a resolved scope: without one, nothing comes back.
// (Two members with grants on different clients: apps/api/tests/test_client_api.py.)
const stranger = await api(`/clients/${lumen.client_id}/knowledge`, { headers: { authorization: "Bearer stranger@example.invalid" } });
check(stranger.status === 403 && stranger.body === null, "a caller outside the organization reads no client knowledge", String(stranger.status));
check(errors.length === 0, "no page errors", errors.slice(0, 2).join(" | "));
await browser.close();
console.log(results.join("\n"));
process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
