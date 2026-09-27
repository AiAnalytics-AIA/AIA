#!/usr/bin/env node
/**
 * Capture every screen of AIA's client-first interface and, when the workbench
 * runs the 18.6.6 unit, every screen of the unit as it ships -- the reference,
 * never the product (ADR 0018) -- and measure what each AIA screen paints outside
 * the design system (tools/ui_workbench/README.md).
 *
 *   node tools/ui_workbench/capture.mjs [--out DIR] [--widths 1440,1024] [--only a,b]
 *
 * Needs the workbench running (`make ui-workbench`) and Playwright with a
 * Chromium it can launch. Playwright is not a repository dependency: it is
 * resolved from the environment (a local install, or the global one).
 *
 * What a "screen" is comes from the interface, not from this file:
 *   1. every route its router knows -- the keys of `routes={...}` in its go()
 *      and every `v==='name'` its later go() overrides intercept, with aliases
 *      (two keys, one render function; `if(v==='x')v='y'`) folded;
 *   2. the first DEMO project of each collection, opened the way a person opens
 *      one (openProject1785), and each of its tabs.
 *
 *   3. every AIA screen (`aia_screens` of docs/migration/interface-screens.json),
 *      and every classic screen's AIA counterpart the ledger names.
 *
 * Steps 1 and 2 run only when the unit answers (`make ui-workbench`, not
 * `--no-unit`). Per screen and width: a full-page PNG, the unit's as shipped and
 * AIA's; page errors; horizontal overflow; on an AIA screen every computed colour
 * on a visible element that is not a design-system token, with a sample selector;
 * and the unit's text an AIA counterpart does not show. Writes report.json and
 * index.html beside the images.
 */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "../..");
const DOCUMENT = join(REPO, "legacy/npc-panel-18.6.6/app/ui_app.html");
const STUDIES = join(REPO, "tmp/ui-workbench/studies.json");
// The workbench's operator, signed in the way its /workbench/sign-in page does
// (the local API's development credential; tools/ui_workbench/api_standin.py).
const OPERATOR = "workbench@example.invalid";
const TOKENS = join(REPO, "apps/web/src/design/tokens.json");

// ---- arguments -------------------------------------------------------------
const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : fallback;
};
const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const OUT = arg("out", join(REPO, "tmp/ui-workbench/shots", stamp));
const WIDTHS = arg("widths", "1440,1024").split(",").map(Number);
const ONLY = arg("only", "") ? new Set(arg("only").split(",")) : null;
const BASES = { bare: arg("bare", "http://127.0.0.1:8767/") };
const FACADE = arg("facade", "http://127.0.0.1:8780");
const SETTLE_MS = Number(arg("settle", "900"));

// ---- Playwright, from wherever the environment has it ----------------------
async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  for (const from of [REPO, join(REPO, "apps/web")]) {
    try {
      return await import(pathToFileURL(require.resolve("playwright", { paths: [from] })).href);
    } catch { /* next */ }
  }
  try {
    const root = execSync("npm root -g", { encoding: "utf8" }).trim();
    return await import(pathToFileURL(join(root, "playwright/index.mjs")).href);
  } catch {
    console.error("capture: Playwright not found. Install it (npm i -g playwright) with a Chromium it can launch.");
    process.exit(2);
  }
}

// ---- the screens the interface's router knows -------------------------------
export function routesFrom(html) {
  const routes = new Map(); // key -> render function (or the key itself)
  const aliases = new Map();
  for (const m of html.matchAll(/routes=\{([^}]*)\}/g)) {
    for (const pair of m[1].split(",")) {
      const [k, fn] = pair.split(":").map((s) => s?.trim());
      if (k && fn && /^[a-z_]+$/.test(k)) routes.set(k, fn);
    }
  }
  for (const m of html.matchAll(/go=function\(v\)\{([\s\S]{0,400}?)\}/g)) {
    for (const a of m[1].matchAll(/if\(v===?'([a-z_]+)'\)v='([a-z_]+)'/g)) aliases.set(a[1], a[2]);
  }
  for (const m of html.matchAll(/go=function\(v\)\{[\s\S]{0,600}/g)) {
    for (const r of m[0].matchAll(/v===?'([a-z_]+)'/g)) if (!routes.has(r[1])) routes.set(r[1], r[1]);
  }
  const seenFn = new Map();
  const out = [];
  for (const [k, fn] of routes) {
    if (aliases.has(k)) continue;
    if (seenFn.has(fn)) { aliases.set(k, seenFn.get(fn)); continue; }
    seenFn.set(fn, k);
    out.push(k);
  }
  return { routes: out, aliases: Object.fromEntries(aliases) };
}

// ---- the palette AIA's screens are allowed to paint with ---------------------
function palette() {
  const tokens = JSON.parse(readFileSync(TOKENS, "utf8"));
  const byName = new Map(tokens.color.tokens.map((t) => [t.name, t]));
  const resolve = (name, d = 0) => {
    const t = byName.get(name);
    const v = typeof t.value === "string" ? t.value : t.value.light;
    return /^\{.+\}$/.test(v) && d < 16 ? resolve(v.slice(1, -1), d + 1) : v;
  };
  const hexes = new Set();
  for (const t of tokens.color.tokens) {
    const v = resolve(t.name);
    if (/^#[0-9a-f]{6}$/i.test(v)) hexes.add(v.toLowerCase());
  }
  return [...hexes];
}

// Runs in the page. Collects every opaque computed colour on a visible element
// that the palette does not contain, with how often and one sample selector.
function offPalette(allowed) {
  const allow = new Set(allowed);
  const hex = (c) => {
    const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    if (!m || (m[4] !== undefined && Number(m[4]) < 0.05)) return null;
    return "#" + [m[1], m[2], m[3]].map((x) => Math.round(Number(x)).toString(16).padStart(2, "0")).join("");
  };
  const sel = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
    [...el.classList].slice(0, 3).map((c) => "." + c).join("");
  const found = new Map();
  const els = [...document.querySelectorAll("body *")].slice(0, 6000);
  for (const el of els) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") continue;
    const props = [["color", cs.color], ["background", cs.backgroundColor]];
    if (parseFloat(cs.borderTopWidth) > 0) props.push(["border", cs.borderTopColor]);
    if (parseFloat(cs.borderLeftWidth) > 0) props.push(["border", cs.borderLeftColor]);
    for (const [prop, value] of props) {
      const h = hex(value);
      if (!h || allow.has(h)) continue;
      const key = `${prop} ${h}`;
      const f = found.get(key) || { prop, hex: h, count: 0, sample: sel(el), text: (el.innerText || "").trim().slice(0, 40) };
      f.count++;
      found.set(key, f);
    }
  }
  return [...found.values()].sort((a, b) => b.count - a.count);
}

// ---- driving the interface ---------------------------------------------------
// Every context is signed in: the AIA pages read the tab's session, the unit's
// ignore it.
async function context(browser, width) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
  const session = JSON.stringify({ idToken: OPERATOR, refreshToken: "", expiresAt: 4102444800000, email: OPERATOR, subject: OPERATOR });
  await ctx.addInitScript((s) => { try { sessionStorage.setItem("aia.session", s); } catch { /* no storage */ } }, session);
  return ctx;
}

// A ledger path with its placeholders filled from a workbench binding.
export function fill(path, binding) {
  return path.replace("<client>", encodeURIComponent(binding.client)).replace("<id>", encodeURIComponent(binding.study));
}

async function boot(page, base) {
  await page.goto(base, { waitUntil: "load", timeout: 120000 });
  await page.waitForFunction(() => typeof go === "function" && window.NPC_BOOT_STAGE !== "start", null, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(2500);
}

async function shoot(page, file) {
  // A tall viewport rather than fullPage: the interface's rail is position:fixed,
  // and a full-page screenshot draws it only as tall as the viewport was.
  const width = page.viewportSize().width;
  const height = Math.min(8000, await page.evaluate(() => document.documentElement.scrollHeight));
  await page.setViewportSize({ width, height: Math.max(900, height) });
  await page.waitForTimeout(250);
  await page.screenshot({ path: file });
  await page.setViewportSize({ width, height: 900 });
}

// Runs in the page: every distinct text a person can read in the working area
// (the classic topbar and #view; a rebuilt screen's header and main), for the
// classic-vs-rebuilt comparison.
function texts() {
  const roots = [...document.querySelectorAll(".sidebar, .topbar, #view, nav, body > div header, main")];
  const seen = new Set();
  for (const root of roots) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el || el.closest("script, style, [aria-hidden=true]")) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      const v = n.textContent.replace(/\s+/g, " ").trim();
      if (v.length >= 2) seen.add(v);
    }
    for (const el of root.querySelectorAll("input[placeholder], option")) {
      const v = (el.getAttribute("placeholder") || el.textContent || "").trim();
      if (v.length >= 2) seen.add(v);
    }
  }
  return { items: [...seen], full: roots.map((r) => r.innerText).join("\n") };
}

// Classic text a rebuilt screen does not show. Compared without whitespace,
// case or the pictographs, arrows and radio circles ("○ Každý den") the rebuilt
// screens draw as icons or elements.
export function missingIn(classic, rebuilt) {
  const norm = (x) => x.replace(/[\p{Extended_Pictographic}\u2600-\u27BF\u25CB+·•←→↗\uFE0F]/gu, "").replace(/\s+/g, "").toLowerCase();
  const haystack = norm(`${rebuilt.full}\n${rebuilt.items.join("\n")}`);
  return classic.items.filter((x) => {
    const n = norm(x);
    return n.length >= 2 && !haystack.includes(n);
  });
}

async function measure(page, allowed, aia) {
  return page.evaluate(({ allowed, aia, offPaletteSrc, textsSrc }) => {
    const title = document.querySelector("#pageTitle")?.innerText?.trim() || document.querySelector("h1,h2")?.innerText?.trim() || "";
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const fn = new Function(`return (${offPaletteSrc})`)();
    return {
      title: title.slice(0, 80),
      height: document.documentElement.scrollHeight,
      overflowPx: overflow > 1 ? overflow : 0,
      offPalette: aia ? fn(allowed).slice(0, 25) : undefined,
      texts: new Function(`return (${textsSrc})`)()(),
    };
  }, { allowed, aia, offPaletteSrc: offPalette.toString(), textsSrc: texts.toString() });
}

async function main() {
  const { chromium } = await loadPlaywright();
  const html = readFileSync(DOCUMENT, "utf8");
  const { routes, aliases } = routesFrom(html);
  const allowed = palette();
  mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const screens = [];
  const record = (id, label, kind) => {
    let s = screens.find((x) => x.id === id);
    if (!s) screens.push((s = { id, label, kind, shots: {} }));
    return s;
  };

  // The unit is the reference, and only when the workbench runs it.
  const unitUp = await fetch(BASES.bare).then((r) => r.ok, () => false);
  if (!unitUp) console.log(`capture: the unit is not answering at ${BASES.bare}: AIA's screens only`);
  for (const [variant, base] of Object.entries(unitUp ? BASES : {})) {
    for (const width of WIDTHS) {
      const ctx = await context(browser, width);
      const page = await ctx.newPage();
      let errors = [];
      page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
      await boot(page, base);
      const take = async (id, label, kind) => {
        await page.waitForTimeout(SETTLE_MS);
        const file = join(OUT, `${id}.${variant}.${width}.png`);
        await shoot(page, file);
        const m = await measure(page, allowed, false);
        record(id, label, kind).shots[`${variant}.${width}`] = { file: relative(OUT, file), ...m, errors };
        errors = [];
        process.stdout.write(".");
      };

      // 1. every route, with no project open
      for (const r of routes) {
        if (ONLY && !ONLY.has(r)) continue;
        await page.evaluate((r) => { try { go(r); } catch (e) { console.error(e); } }, r).catch(() => {});
        await take(`route-${r}`, r, "route");
      }

      // 2. one DEMO of each collection, and each of its tabs
      if (!ONLY || ONLY.has("demos")) {
        const demos = await page.evaluate(() => jget("/api/demos")).catch(() => []);
        const firsts = demos.filter((d, i) => demos.findIndex((x) => x.collection === d.collection) === i);
        for (const d of firsts) {
          await page.evaluate((id) => openProject1785(id), d.project_id).catch(() => {});
          await page.waitForTimeout(1500);
          const slug = d.collection.replace(/[^a-z]+/g, "-");
          await take(`demo-${slug}`, `DEMO · ${d.collection}`, "demo");
          const tabs = await page.$$eval(".demoTabs1795 button", (bs) => bs.map((b) => (b.textContent || "").trim()));
          for (const [i, name] of tabs.entries()) {
            if (/Sociomapa/.test(name)) continue; // opens the shared tool in its own document
            await page.evaluate((i) => document.querySelectorAll(".demoTabs1795 button")[i]?.click(), i);
            await take(`demo-${slug}-tab${String(i + 1).padStart(2, "0")}`, `DEMO · ${d.collection} · ${name}`, "demo-tab");
          }
        }
      }
      await ctx.close();
    }
  }
  // 3. every AIA screen, and every classic screen's AIA counterpart the ledger
  // names (react_path), from the facade's /app, beside the unit's when it ran
  // (docs/migration/interface-screens.json). A <client> is the one the
  // workbench fixtures are under (tmp/ui-workbench/studies.json).
  const ledger = JSON.parse(readFileSync(join(REPO, "docs/migration/interface-screens.json"), "utf8"));
  const studies = existsSync(STUDIES) ? JSON.parse(readFileSync(STUDIES, "utf8")) : {};
  const anyBinding = Object.values(studies)[0];
  const aia = (ledger.aia_screens || []).filter((x) => !ONLY || ONLY.has(x.id));
  // A path with <id> needs a project: it is captured with its fixture, in 4.
  const rebuilt = ledger.screens.filter((x) => x.react_path && !x.react_path.includes("<id>") && (!ONLY || ONLY.has(x.classic.route)));
  const pages = [
    ...aia.map((x) => ({ id: x.id, label: x.title, kind: "aia", path: x.path })),
    ...rebuilt.map((x) => ({ id: x.id, label: x.id.replace(/^route-/, ""), kind: "route", path: x.react_path })),
  ].filter((x) => {
    if (!x.path.includes("<client>")) return true;
    if (!anyBinding) console.log(`\ncapture: ${x.id}: no workbench client (run make ui-fixtures)`);
    return !!anyBinding;
  });
  for (const width of WIDTHS) {
    const ctx = await context(browser, width);
    const page = await ctx.newPage();
    for (const x of pages) {
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
      const path = anyBinding ? fill(x.path, anyBinding) : x.path;
      await page.goto(new URL(path, FACADE).href, { waitUntil: "networkidle", timeout: 120000 });
      await page.waitForTimeout(SETTLE_MS);
      const file = join(OUT, `${x.id}.react.${width}.png`);
      await shoot(page, file);
      const m = await measure(page, allowed, true);
      record(x.id, x.label, x.kind).shots[`react.${width}`] = { file: relative(OUT, file), ...m, errors, path };
      page.removeAllListeners("pageerror");
      process.stdout.write("+");
    }
    await ctx.close();
  }
  // 4. screens the ledger names a fixture project for (`fixture`, a key of
  // tmp/ui-workbench/studies.json, written by `make ui-fixtures`): the AIA
  // screen at react_path on that study. What a screen shows with an AI answer in it.
  const paired = ledger.screens.filter((x) => x.fixture && x.react_path && (!ONLY || ONLY.has(x.classic.route)));
  for (const x of paired) {
    const binding = studies[x.fixture];
    if (!binding) {
      console.log(`\ncapture: ${x.id}: no fixture "${x.fixture}" (run make ui-fixtures)`);
      continue;
    }
    const id = `${x.id}@${x.fixture}`;
    const path = fill(x.react_path, binding);
    for (const width of WIDTHS) {
      const ctx = await context(browser, width);
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
      await page.goto(new URL(path, FACADE).href, { waitUntil: "networkidle", timeout: 120000 });
      await page.waitForTimeout(SETTLE_MS);
      const file = join(OUT, `${id}.react.${width}.png`);
      await shoot(page, file);
      record(id, `${x.classic.route} · ${x.fixture}`, "fixture").shots[`react.${width}`] = { file: relative(OUT, file), ...(await measure(page, allowed, true)), errors, path };
      await ctx.close();
      process.stdout.write("+");
    }
  }

  for (const sc of screens) {
    for (const width of WIDTHS) {
      const classic = sc.shots[`bare.${width}`], react = sc.shots[`react.${width}`];
      if (classic && react) react.missing = missingIn(classic.texts, react.texts);
    }
  }
  await browser.close();

  const report = { generated: new Date().toISOString(), widths: WIDTHS, bases: BASES, aliases, routes, screens };
  writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 1));
  writeFileSync(join(OUT, "index.html"), sheet(report));
  const worst = screens
    .map((s) => ({ id: s.id, n: (s.shots[`react.${WIDTHS[0]}`]?.offPalette || []).reduce((a, f) => a + f.count, 0) }))
    .sort((a, b) => b.n - a.n).slice(0, 5);
  console.log(`\ncapture: ${screens.length} screens x ${WIDTHS.length} widths -> ${relative(REPO, OUT)}/index.html`);
  console.log(`capture: most off-palette paint: ${worst.map((w) => `${w.id} (${w.n})`).join(", ")}`);
  for (const sc of screens) {
    const r = sc.shots[`react.${WIDTHS[0]}`];
    if (r?.missing) console.log(`capture: ${sc.id} in AIA at ${r.path}: ${r.missing.length} text(s) of the unit's not shown${r.missing.length ? ": " + r.missing.slice(0, 12).map((x) => JSON.stringify(x)).join(", ") : ""}`);
  }
}

// ---- the contact sheet -------------------------------------------------------
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function sheet(r) {
  const w = r.widths[0];
  const rows = r.screens.map((s) => {
    // An AIA screen with no classic counterpart draws only its own shot.
    const b = s.shots[`bare.${w}`], x = s.shots[`react.${w}`], k = x || b || {};
    const fig = (shot, caption) => (shot ? `<figure><figcaption>${esc(caption)}</figcaption><a href="${esc(shot.file)}"><img loading="lazy" src="${esc(shot.file)}"></a></figure>` : "");
    const flags = [
      k.overflowPx ? `overflow ${k.overflowPx}px` : "",
      (k.errors || []).length ? `${k.errors.length} page error(s)` : "",
    ].filter(Boolean).join(" · ");
    const off = (k.offPalette || []).slice(0, 8).map((f) =>
      `<li><span class="sw" style="background:${f.hex}"></span><code>${f.prop} ${f.hex}</code> ×${f.count} <code>${esc(f.sample)}</code></li>`).join("");
    const other = r.widths.slice(1).map((x) => ["bare", "react"].filter((v) => s.shots[`${v}.${x}`]).map((v) => `<a href="${esc(s.shots[`${v}.${x}`].file)}">${v} ${x}</a>`).join(" · ")).join(" · ");
    return `<section id="${esc(s.id)}"><h2>${esc(s.label)} <small>${esc(k.title || b?.title)}</small></h2>
<p class="meta">${esc(s.kind)}${flags ? " · <b>" + esc(flags) + "</b>" : ""} · ${other}</p>
<div class="pair">${fig(b, "18.6.6 as shipped (reference)")}${fig(x, `AIA · ${x?.path}`)}</div>
${x?.missing ? `<details${x.missing.length ? " open" : ""}><summary>The unit's text the AIA screen does not show (${x.missing.length})</summary><ul>${x.missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></details>` : ""}
${off ? `<details><summary>Colours outside the design system (${(k.offPalette || []).length})</summary><ul>${off}</ul></details>` : ""}</section>`;
  }).join("\n");
  return `<!doctype html><html lang="en"><meta charset="utf-8"><title>UI capture</title>
<style>body{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#1b1f24;background:#fafaf9}h1{font-size:20px}
h2{font-size:16px;margin:28px 0 4px}h2 small{color:#6b7280;font-weight:400}.meta{color:#6b7280;margin:0 0 8px}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}figure{margin:0}figcaption{font-size:12px;color:#6b7280}
img{width:100%;border:1px solid #e5e7eb;display:block}code{font-size:12px}.sw{display:inline-block;width:12px;height:12px;border:1px solid #ccc;vertical-align:-2px;margin-right:4px}
nav a{margin-right:10px}</style>
<h1>Every screen, ${esc(r.generated)} · ${r.screens.length} screens · widths ${r.widths.join(", ")}</h1>
<nav>${r.screens.map((s) => `<a href="#${esc(s.id)}">${esc(s.id)}</a>`).join("")}</nav>
${rows}</html>`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await main();
