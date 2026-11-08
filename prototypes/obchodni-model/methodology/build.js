#!/usr/bin/env node
// Builds AIA_business-decision-study_methodology_v3.pdf from the chapter files in this folder.
//
//   node build.js            the PDF (two passes: the second fills the contents' page numbers from pdftotext)
//   node build.js --png      the PDF, then every page as PNG under ../../../tmp/methodology-pages/ (pdftoppm)
//   node build.js --html     also writes the assembled document as methodology.html, for a browser
//
// Needs Node 18+ and Playwright with its Chromium (the repository's environment has both). Page numbers in
// the contents need poppler's pdftotext; without it the contents print without numbers and the build says so.
// Fonts come from ./fonts (the report's own faces, SIL OFL). Nothing is fetched from the network.
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');
const { chromium } = require('playwright');

const HERE = __dirname;
const OUT = path.join(HERE, 'AIA_business-decision-study_methodology_v3.pdf');
const CHAPTERS = fs.readdirSync(HERE).filter((f) => /^\d\d-.*\.html$/.test(f)).sort();

function read(f) { return fs.readFileSync(path.join(HERE, f), 'utf8'); }

// Headings for the contents: every <h1> and the <h2>s that are not the step chapters' fixed parts.
function headings(html) {
  const out = [];
  const re = /<(h[12])([^>]*)>([\s\S]*?)<\/\1>/g;
  let m;
  while ((m = re.exec(html))) {
    const attrs = m[2];
    if (/class="[^"]*\bpart\b/.test(attrs) || /data-toc="no"/.test(attrs)) continue;
    const text = m[3].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    const id = (attrs.match(/id="([^"]+)"/) || [])[1];
    const label = (attrs.match(/data-label="([^"]+)"/) || [])[1] || '';
    out.push({ level: m[1], text, id, label });
  }
  return out;
}

function tocHtml(items, pages) {
  const li = items.map((h) => {
    const pg = pages && pages.get(h.text) ? pages.get(h.text) : '';
    const cls = h.level === 'h2' ? 'l2' : 'l1';
    return `<li class="${cls}"><span class="num">${h.label}</span><span class="t">${h.text}</span><span class="dots"></span><span class="pg">${pg}</span></li>`;
  });
  return `<section class="chapter contents" id="contents"><p class="chapter-label">Contents</p><h1 data-toc="no">What is in this document</h1><ul class="toc">${li.join('')}</ul></section>`;
}

function assemble(pages) {
  const parts = CHAPTERS.map(read);
  const body = parts.map((p, i) => (i === 1 ? tocHtml(allHeadings, pages) + p : p)).join('\n');
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>AIA business-decision study, methodology v3</title>
<link rel="stylesheet" href="style.css"></head><body>${body}</body></html>`;
}

const allHeadings = CHAPTERS.slice(1).flatMap((f) => headings(read(f)));

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
  const header = `<div style="width:100%;font-family:'IBM Plex Sans',Arial,sans-serif;font-size:7.5pt;color:#44484e;padding:0 20mm;display:flex;justify-content:space-between;">
      <span>AIA · Business-decision study · Methodology, version 3</span><span>8 Nov 2026 · design, not product code</span></div>`;
  const footer = `<div style="width:100%;font-family:'IBM Plex Sans',Arial,sans-serif;font-size:7.5pt;color:#44484e;padding:0 20mm;display:flex;justify-content:space-between;">
      <span>Fictional case. No real company, municipality or person.</span><span>page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`;
  await page.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true, headerTemplate: header, footerTemplate: footer,
    margin: { top: '22mm', bottom: '24mm', left: '20mm', right: '20mm' }, preferCSSPageSize: false });
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
    // An h1 is found on the page that also carries its chapter label; an h2 prints its label before its text.
    const text = esc(norm(h.text));
    const re = h.level === 'h1'
      ? new RegExp(text)
      : new RegExp(esc(h.label) + '\\s*' + text);
    const label = h.level === 'h1' && h.label ? new RegExp('(Chapter|Appendix) ' + esc(h.label) + '\\b', 'i') : null;
    for (let i = 2; i < pages.length; i++) { // skip the cover and the contents
      const page = norm(pages[i]);
      if (re.test(page) && (!label || label.test(page))) { map.set(h.text, String(i + 1)); break; }
    }
  }
  return map;
}

(async () => {
  let errors = await render(assemble(null), OUT);
  let pages = pageIndex(OUT);
  if (pages) {
    errors = errors.concat(await render(assemble(pages), OUT));
    const missing = allHeadings.filter((h) => !pages.get(h.text)).map((h) => h.text);
    if (missing.length) console.warn('contents: no page found for', missing);
  } else {
    console.warn('pdftotext not found: the contents print without page numbers');
  }
  if (process.argv.includes('--html')) fs.writeFileSync(path.join(HERE, 'methodology.html'), assemble(pages));
  let count = '?';
  try { count = execFileSync('pdfinfo', [OUT], { encoding: 'utf8' }).match(/Pages:\s+(\d+)/)[1]; } catch (_) {}
  console.log(`${path.basename(OUT)}: ${count} pages, ${errors.length} browser errors`);
  for (const e of errors) console.log('  ' + e);
  if (process.argv.includes('--png')) {
    const dir = path.resolve(HERE, '../../../tmp/methodology-pages');
    fs.mkdirSync(dir, { recursive: true });
    execFileSync('pdftoppm', ['-r', '96', '-png', OUT, path.join(dir, 'page')]);
    console.log('pages as PNG under ' + dir);
  }
  process.exit(errors.length ? 1 : 0);
})();
