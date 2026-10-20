import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(async () => chromium.launch());
const html = (await import('fs')).readFileSync('aia-mvp-plan.html', 'utf8');
const doc = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${html}</body></html>`;
for (const [w, scheme] of [[1440, 'light'], [390, 'dark']]) {
  const p = await b.newPage({ viewport: { width: w, height: 900 }, colorScheme: scheme });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await p.setContent(doc, { waitUntil: 'load' }).catch(e => errs.push(String(e)));
  await p.waitForTimeout(800);
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await p.click('.node[data-id="E10"]').catch(e => errs.push('click ' + e.message));
  const panel = await p.textContent('#panel');
  await p.screenshot({ path: `shot-${w}.png`, fullPage: false });
  await p.locator('#graph').scrollIntoViewIfNeeded(); await p.screenshot({ path: `shot-${w}-graph.png` });
  console.log(w, scheme, 'overflow', ov, 'errors', errs.length ? errs.slice(0,5) : 'none', 'panel:', panel.slice(0, 80).replace(/\s+/g,' '));
}
await b.close();
