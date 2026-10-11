#!/usr/bin/env node
/** Real AIA browser regression over the fictional workbench; run ui-research first.
 * node tools/ui_workbench/ux_journey.mjs --facade http://127.0.0.1:8780 --out DIR
 * No model calls, external searches, budget changes or live-account storage.
 */
import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const arg = (name, fallback) => args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : fallback;
const base = arg("facade", "http://127.0.0.1:8780");
assert(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "This journey uses local fictional identity only");
const out = arg("out", join(repo, "tmp/ui-workbench/ux-journey"));
mkdirSync(out, { recursive: true });
const require = createRequire(import.meta.url);
const module = await import(pathToFileURL(require.resolve("playwright", { paths: [repo, join(repo, "apps/web")] })).href);
const chromium = module.chromium ?? module.default.chromium;
const browser = await chromium.launch({ executablePath: process.env.AIA_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
await context.addInitScript(() => sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "workbench@example.invalid", refreshToken: "", expiresAt: 4102444800000, email: "workbench@example.invalid", subject: "workbench@example.invalid" })));
const page = await context.newPage();
const records = [], errors = [], checks = [], writes = [], httpErrors = [], consoleErrors = [], failedRequests = [], abortedStageMarkers = [];
page.on("pageerror", e => errors.push(String(e)));
page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("requestfailed", request => {
  const entry = { method: request.method(), path: new URL(request.url()).pathname, error: request.failure()?.errorText };
  if (entry.method === "PUT" && entry.path.endsWith("/workspace/stage") && entry.error?.includes("ERR_ABORTED")) abortedStageMarkers.push(entry);
  else failedRequests.push(entry);
});
page.on("response", r => { if (r.status() >= 400) httpErrors.push({ status: r.status(), path: new URL(r.url()).pathname }); });
page.on("request", r => { if (!["GET", "HEAD", "OPTIONS"].includes(r.method()) && !new URL(r.url()).pathname.startsWith("/_next/")) writes.push({ method: r.method(), path: new URL(r.url()).pathname }); });
const fixtures = JSON.parse(readFileSync(join(repo, "tmp/ui-workbench/studies.json"), "utf8"));
const { client, study } = fixtures.persona;
const clientPath = `/app/clients/${client}`;
const studyPath = `${clientPath}/research/${study}`;
const routes = ["/app/clients", clientPath, ...["research", "simulations", "knowledge", "data"].map(s => `${clientPath}/${s}`), "/app/intelligence", "/app/memory", "/app/settings", ...["brief", "plan", "questionnaire", "audience", "dimensions", "run", "progress", "results"].map(s => `${studyPath}/${s}`)];
const visit = async path => {
  await page.goto(base + path);
  await page.locator("main h1, header h1").waitFor();
  await page.waitForLoadState("networkidle");
};
const measure = async label => {
  const row = await page.evaluate(() => ({ path: location.pathname + location.hash, width: innerWidth, documentWidth: document.documentElement.scrollWidth, mainWidth: document.querySelector("main").getBoundingClientRect().width, pageHeight: document.documentElement.scrollHeight, title: document.querySelector("h1").textContent }));
  records.push({ label, ...row });
  assert(row.documentWidth <= row.width + 2, `${label}: page overflow ${row.documentWidth} > ${row.width}`);
  assert(row.mainWidth >= row.width * 0.5, `${label}: content squeezed by navigation`);
};
try {
  for (const route of routes) {
    await visit(route);
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await measure(route);
    }
  }
  checks.push("17 real routes × four widths: no page overflow or squeezed content");
  await visit("/app/clients");
  const search = page.getByRole("searchbox", { name: "Hledat klienta nebo studii" });
  await search.fill("Horizont");
  assert.equal(await page.locator("main > div ul > li > a").count(), 1);
  await search.fill("not-a-client-anywhere");
  await page.getByText(/Žádný klient ani jeho nedávná studie/).waitFor();
  await search.fill("");
  assert(await page.locator("main > div ul > li > a").count() >= 2);
  checks.push("Client search, no-match explanation and recovery");
  await visit(studyPath + "/results");
  await page.getByRole("tab", { name: "Přehled", exact: true }).waitFor();
  assert.equal(await page.getByRole("tabpanel").count(), 1);
  await page.getByText(/Fiktivní data\. Tento běh/).waitFor();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: join(out, "results-overview-desktop.png"), fullPage: true });
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  assert(await page.getByRole("tabpanel", { name: "Data" }).locator("table").count() > 0);
  await page.getByRole("tab", { name: "Sociomapy", exact: true }).click();
  const map = page.getByTestId("object-map-sec_wb_set");
  await map.getByRole("button", { name: "3D terén", exact: true }).click();
  const terrain = map.getByTestId("object-map-3d");
  await terrain.waitFor();
  const initial = await terrain.getAttribute("data-camera");
  await map.getByRole("button", { name: "Otočit vpravo", exact: true }).click();
  const rotated = await terrain.getAttribute("data-camera");
  assert.notEqual(rotated, initial, "3D rotation must change the view");
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  await page.getByRole("tab", { name: "Sociomapy", exact: true }).click();
  assert.equal(await terrain.getAttribute("data-camera"), rotated, "Switching sections must preserve the camera");
  await terrain.screenshot({ path: join(out, "canonical-map-3d.png") });
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const label of ["Data", "Sociomapy", "Rešerše a zpráva", "Přehled"]) {
      await page.getByRole("tab", { name: label, exact: true }).click();
      await measure(label);
    }
  }
  await page.screenshot({ path: join(out, "results-overview-phone.png"), fullPage: true });
  await page.getByRole("tab", { name: "Přehled", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.getByRole("tab", { name: "Data", exact: true }).getAttribute("aria-selected"), "true");
  await page.keyboard.press("End");
  assert.equal(await page.getByRole("tab", { name: "Rešerše a zpráva", exact: true }).getAttribute("aria-selected"), "true");
  await page.reload();
  await page.getByRole("tabpanel", { name: "Rešerše a zpráva" }).waitFor();
  await page.getByRole("button", { name: /AI Analytics ·/ }).click();
  await page.getByRole("navigation", { name: "Hlavní navigace" }).waitFor();
  checks.push("Result sections, keyboard focus, reload and mobile menu");
  checks.push("Canonical 3D map rotation and camera preserved across sections");
  assert.equal(errors.length, 0, errors.join("\n"));
  assert.equal(consoleErrors.length, 0, consoleErrors.join("\n"));
  assert.equal(failedRequests.length, 0, JSON.stringify(failedRequests));
  const unexpected = httpErrors.filter(e => !(e.status === 404 && /\/(workspace\/content|knowledge|agent-jobs|analysis|report)\b/.test(e.path)));
  assert.equal(unexpected.length, 0, JSON.stringify(unexpected));
  const riskyWrites = writes.filter(r => r.method !== "PUT" || !r.path.endsWith("/workspace/stage"));
  // Opening Run freezes the existing design through the normal API; it never starts paid work.
  assert.equal(riskyWrites.filter(r => !(r.method === "POST" && r.path.endsWith("/design/revisions"))).length, 0, JSON.stringify(riskyWrites));
  writeFileSync(join(out, "journey.json"), JSON.stringify({ result: "PASS", checks, records, errors, httpErrors, writes, consoleErrors, failedRequests, abortedStageMarkers }, null, 2));
  console.log(`UX journey: PASS (${records.length} layout checks; ${checks.length} interaction checks; ${out})`);
} catch (error) {
  await page.screenshot({ path: join(out, "failure.png"), fullPage: true });
  writeFileSync(join(out, "journey.json"), JSON.stringify({ result: "FAIL", message: String(error), checks, records, errors, httpErrors, writes, consoleErrors, failedRequests, abortedStageMarkers }, null, 2));
  throw error;
} finally { await browser.close(); }
