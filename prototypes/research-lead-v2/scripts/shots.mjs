// node scripts/shots.mjs <outdir> <width> <height> <scenario...>  — fast mode, one browser
import { chromium } from 'playwright-core';
const [, , out, w, h, ...ids] = process.argv;
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
for (const id of ids) {
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  await page.goto('http://127.0.0.1:5174/?fast=1&s=' + id);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/${id}-${w}.png` });
  console.log(id, errs.slice(0, 5).join(' | ') || 'ok');
  await page.close();
}
await browser.close();
