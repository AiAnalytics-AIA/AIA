// Print the case pack's HTML documents to PDF with the pre-installed Playwright Chromium.
// node prototypes/case-velis/tools/pdf.js   (after documents.py)
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const src = path.join(__dirname, '..', 'documents', 'html'), out = path.join(__dirname, '..', 'documents');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  for (const f of fs.readdirSync(src).filter(x => x.endsWith('.html')).sort()) {
    await p.goto('file://' + path.join(src, f));
    await p.pdf({ path: path.join(out, f.replace('.html', '.pdf')), format: 'A4', printBackground: true, preferCSSPageSize: true });
    console.log('pdf', f.replace('.html', '.pdf'));
  }
  await b.close();
})();
