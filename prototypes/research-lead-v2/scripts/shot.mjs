// Quick look: node scripts/shot.mjs "<query>" <out.png> [width] [height] [waitMs]
import { chromium } from 'playwright-core';
const [, , q = 's=A', out = 'shot.png', w = '1440', h = '900', wait = '2500'] = process.argv;
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
const errs = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
await page.goto('http://127.0.0.1:5174/?' + q);
await page.waitForTimeout(+wait);
await page.screenshot({ path: out });
console.log(errs.slice(0, 12).join('\n') || 'no console errors');
await browser.close();
