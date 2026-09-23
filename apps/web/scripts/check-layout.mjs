#!/usr/bin/env node
/**
 * Layout evidence against a running build (default http://localhost:3000):
 *   - renders each route in light and dark, saves screenshots to .layout-evidence/
 *   - Czech +35 % stress: extends every text node by 35 % with diacritics and
 *     fails on any element that overflows its box or the page, at 1280 and 1024 px.
 *
 * The screens read the real API, so the routes are discovered from the running
 * app: the portfolio, every study it links to, each study's first project with
 * an impact preview, and that project's REPORT stage. Run the API on a seeded
 * database first (`make dev-seed`). LAYOUT_ROUTES (comma-separated) overrides.
 * LAYOUT_ORG is the organization slug in the URL (default "aia").
 *
 * Needs a Chromium: set PLAYWRIGHT_CHROMIUM (path) or install playwright browsers.
 * Not in CI yet (the CI image has no browser); run before merging layout changes:
 *   npm run build && AIA_DEV_SUBJECT=lead@aia.dev npx next start -p 3000 & npm run check:layout
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://localhost:3000";
const OUT = ".layout-evidence";
const ORG = process.env.LAYOUT_ORG ?? "aia";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
const page = await browser.newPage();

async function links(route, pattern) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  const hrefs = await page.$$eval("a[href]", (as) => as.map((a) => a.getAttribute("href")));
  return [...new Set(hrefs.filter((h) => h && pattern.test(h)))];
}

async function discover() {
  const dashboard = `/org/${ORG}/dashboard`;
  const studies = await links(dashboard, /\/studies\/STU-[0-9a-f]+$/);
  const clients = await links(dashboard, /\/clients\/CLI-[0-9a-f]+$/);
  const routes = [dashboard, ...clients.slice(0, 1), ...studies];
  for (const study of studies) {
    const [project] = await links(study, /\/projects\/PRJ-[0-9a-f]+$/);
    if (project) routes.push(`${project}?field=audience`, `${project}/stages/REPORT`);
  }
  if (studies.length === 0) {
    console.error(`check-layout: no studies linked from ${dashboard} — is the API up and seeded?`);
    process.exit(2);
  }
  return routes;
}

const ROUTES = process.env.LAYOUT_ROUTES ? process.env.LAYOUT_ROUTES.split(",") : await discover();
console.log(`check-layout: ${ROUTES.length} routes`);
let failures = 0;

for (const route of ROUTES) {
  const slug = route.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");
  for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.addInitScript((th) => localStorage.setItem("aia.theme", th), theme);
    await page.goto(BASE + route, { waitUntil: "networkidle" });
    await page.screenshot({ path: `${OUT}/${slug}.${theme}.png`, fullPage: true });
  }
  for (const width of [1280, 1024]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto(BASE + route, { waitUntil: "networkidle" });
    const bad = await page.evaluate(() => {
      const pad = "ěščřžýáíéůú";
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const n of nodes) {
        const s = n.nodeValue ?? "";
        if (!/[A-Za-zÀ-ž]/.test(s) || s.trim().length < 2 || n.parentElement?.closest("script,style")) continue;
        let add = ""; for (let i = 0; i < Math.ceil(s.length * 0.35); i++) add += pad[i % pad.length];
        n.nodeValue = s + add;
      }
      const out = [];
      const vw = document.documentElement.clientWidth;
      for (const el of document.body.querySelectorAll("*")) {
        const cs = getComputedStyle(el);
        if (el.closest("svg") || el.classList.contains("sr-only") || cs.textOverflow === "ellipsis") continue;
        if (el.closest("[data-scroll-x]") || ["auto", "scroll"].includes(cs.overflowX)) continue;
        if (el.getBoundingClientRect().right > vw + 1) out.push(`off-page <${el.tagName.toLowerCase()} class="${el.className}">`);
        else if (cs.overflowX === "hidden" && el.scrollWidth > el.clientWidth + 1) out.push(`clipped <${el.tagName.toLowerCase()}>`);
      }
      return out.slice(0, 10);
    });
    if (bad.length) failures += bad.length;
    console.log(`${bad.length ? "FAIL" : "ok  "} +35% cs @${width}px ${route}${bad.length ? "\n    " + bad.join("\n    ") : ""}`);
  }
}
await browser.close();
console.log(failures ? `layout: ${failures} overflow(s)` : `layout: ${ROUTES.length} routes × 2 widths, 0 overflows; screenshots in ${OUT}/`);
process.exit(failures ? 1 : 0);
