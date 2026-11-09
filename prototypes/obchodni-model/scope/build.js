#!/usr/bin/env node
// Builds AIA_MVP-scope_cs.pdf, the MVP scope for executives (version 3), from the chapter files in this folder.
//
//   node build.js            the PDF
//   node build.js --png      the PDF, then every page as PNG under ../../../tmp/scope-pages/ (pdftoppm)
//   node build.js --html     also writes the assembled document as scope.html, for a browser
//
// Needs Node 18+ and Playwright with its Chromium (NODE_PATH=$(npm root -g) when Playwright is installed globally).
// Styles and fonts come from ../methodology/ (style.css, fonts/); scope.css adds what the figures need. Nothing is
// fetched from the network. The engineering record is ../MVP-SCOPE.md; this document is its executive reading.
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const HERE = __dirname;
const OUT = path.join(HERE, 'AIA_MVP-scope_cs.pdf');
const CHAPTERS = fs.readdirSync(HERE).filter((f) => /^\d\d-.*\.html$/.test(f)).sort();

function read(f) { return fs.readFileSync(path.join(HERE, f), 'utf8'); }

function assemble() {
  const body = CHAPTERS.map(read).join('\n');
  return `<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>AIA · Rozsah MVP</title>
<link rel="stylesheet" href="../methodology/style.css"><link rel="stylesheet" href="scope.css"></head><body class="exec">${body}</body></html>`;
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
    headerTemplate: bar('AIA · Rozsah MVP · verze 3', '9. 11. 2026 · návrh'),
    footerTemplate: bar('Návrh ke schválení. Ilustrativní čísla jsou označena.', 'strana <span class="pageNumber"></span> z <span class="totalPages"></span>'),
    margin: { top: '22mm', bottom: '24mm', left: '20mm', right: '20mm' }, preferCSSPageSize: false,
  });
  await browser.close();
  fs.unlinkSync(tmp);
  return errors;
}

(async () => {
  const errors = await render(assemble(), OUT);
  if (process.argv.includes('--html')) fs.writeFileSync(path.join(HERE, 'scope.html'), assemble());
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
