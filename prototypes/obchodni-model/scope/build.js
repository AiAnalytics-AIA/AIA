#!/usr/bin/env node
// Builds AIA_MVP-scope_cs.pdf from the chapter files in this folder: the MVP scope (../MVP-SCOPE.md) as a Czech,
// figure-led document.
//
//   node build.js            the PDF (two passes: the second fills the contents' page numbers from pdftotext)
//   node build.js --png      the PDF, then every page as PNG under ../../../tmp/scope-pages/ (pdftoppm)
//   node build.js --html     also writes the assembled document as scope.html, for a browser
//
// Needs Node 18+ and Playwright with its Chromium (the repository's environment has both; NODE_PATH=$(npm root -g)
// when Playwright is installed globally). Page numbers in the contents need poppler's pdftotext; without it the
// contents print without numbers and the build says so. Styles and fonts come from ../methodology/ (style.css,
// fonts/); scope.css adds only what the figures need. Nothing is fetched from the network.
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');
const { chromium } = require('playwright');

const HERE = __dirname;
const OUT = path.join(HERE, 'AIA_MVP-scope_cs.pdf');
const CHAPTERS = fs.readdirSync(HERE).filter((f) => /^\d\d-.*\.html$/.test(f)).sort();

function read(f) { return fs.readFileSync(path.join(HERE, f), 'utf8'); }

// Headings for the contents: every <h1> and every <h2> that does not opt out.
function headings(html) {
  const out = [];
  const re = /<(h[12])([^>]*)>([\s\S]*?)<\/\1>/g;
  let m;
  while ((m = re.exec(html))) {
    const attrs = m[2];
    if (/data-toc="no"/.test(attrs)) continue;
    const text = m[3].replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/\s+/g, ' ').trim();
    const label = (attrs.match(/data-label="([^"]+)"/) || [])[1] || '';
    out.push({ level: m[1], text, label });
  }
  return out;
}

const allHeadings = CHAPTERS.slice(1).flatMap((f) => headings(read(f)));

function tocHtml(pages) {
  const li = allHeadings.map((h) => {
    const pg = pages && pages.get(h.text) ? pages.get(h.text) : '';
    const cls = h.level === 'h2' ? 'l2' : 'l1';
    return `<li class="${cls}"><span class="num">${h.label}</span><span class="t">${h.text}</span><span class="dots"></span><span class="pg">${pg}</span></li>`;
  });
  return `<section class="chapter contents" id="contents"><p class="chapter-label">Obsah</p><h1 data-toc="no">Co v dokumentu je</h1><ul class="toc">${li.join('')}</ul></section>`;
}

function assemble(pages) {
  const parts = CHAPTERS.map(read);
  const body = parts.map((p, i) => (i === 1 ? tocHtml(pages) + p : p)).join('\n');
  return `<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>AIA · Rozsah MVP · zpráva typu 2</title>
<link rel="stylesheet" href="../methodology/style.css"><link rel="stylesheet" href="scope.css"></head><body>${body}</body></html>`;
}

async function render(html, out) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('requestfailed', (r) => errors.push('request failed: ' + r.url()));
  const tmp = path.join(HERE, '.build.html');
  fs.writeFileSync(tmp, html);
  await page.goto('file://' + tmp, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const bar = (l, r) => `<div style="width:100%;font-family:'IBM Plex Sans',Arial,sans-serif;font-size:7.5pt;color:#44484e;padding:0 20mm;display:flex;justify-content:space-between;"><span>${l}</span><span>${r}</span></div>`;
  await page.pdf({
    path: out, format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: bar('AIA · Obchodní rozhodnutí · Rozsah MVP', '9. 11. 2026 · návrh, ne kód produktu'),
    footerTemplate: bar('Smyšlený případ. Žádná skutečná firma, obec ani osoba.', 'strana <span class="pageNumber"></span> z <span class="totalPages"></span>'),
    margin: { top: '22mm', bottom: '24mm', left: '20mm', right: '20mm' }, preferCSSPageSize: false,
  });
  await browser.close();
  fs.unlinkSync(tmp);
  return errors;
}

function pageIndex(pdf) {
  const r = spawnSync('pdftotext', ['-layout', pdf, '-'], { encoding: 'utf8', maxBuffer: 64 << 20 });
  if (r.status !== 0) return null;
  const pages = r.stdout.split('\f');
  const map = new Map();
  const norm = (s) => s.replace(/\s+/g, ' ').trim();
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const h of allHeadings) {
    // An h1 is found on the page that also carries its chapter label ("ČÁST n"); an h2 prints its label before its text.
    const text = esc(norm(h.text));
    const re = h.level === 'h1' ? new RegExp(text) : new RegExp(esc(h.label) + '\\s*' + text);
    const label = h.level === 'h1' && h.label ? new RegExp('^AIA[^]{0,120}?Část ' + esc(h.label) + '\\b', 'i') : null;
    for (let i = 2; i < pages.length; i++) { // skip the cover and the contents
      const page = norm(pages[i]);
      if (re.test(page) && (!label || label.test(page))) { map.set(h.text, String(i + 1)); break; }
    }
  }
  return map;
}

(async () => {
  let errors = await render(assemble(null), OUT);
  const pages = pageIndex(OUT);
  if (pages) {
    errors = errors.concat(await render(assemble(pages), OUT));
    const missing = allHeadings.filter((h) => !pages.get(h.text)).map((h) => h.text);
    if (missing.length) console.warn('contents: no page found for', missing);
  } else {
    console.warn('pdftotext not found: the contents print without page numbers');
  }
  if (process.argv.includes('--html')) fs.writeFileSync(path.join(HERE, 'scope.html'), assemble(pages));
  let count = '?';
  try { count = execFileSync('pdfinfo', [OUT], { encoding: 'utf8' }).match(/Pages:\s+(\d+)/)[1]; } catch (_) {}
  console.log(`${path.basename(OUT)}: ${count} pages, ${errors.length} browser errors`);
  for (const e of errors) console.log('  ' + e);
  if (process.argv.includes('--png')) {
    const dir = path.resolve(HERE, '../../../tmp/scope-pages');
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });
    execFileSync('pdftoppm', ['-r', '96', '-png', OUT, path.join(dir, 'page')]);
    console.log('pages as PNG under ' + dir);
  }
  process.exit(errors.length ? 1 : 0);
})();
