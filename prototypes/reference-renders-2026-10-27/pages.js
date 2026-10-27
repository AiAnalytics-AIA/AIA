// node pages.js <prototypes dir> <out dir>: the Design System page (light, then dark via its own toggle) and the before/after page.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const http=require('http');
if(process.argv.length<4){console.error('usage: node pages.js <folder holding design-system-2026-10-27 and ux-upgrade-2026-10-27> <out dir>');process.exit(2)}
const root=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
for(const d of ['design-system-2026-10-27','ux-upgrade-2026-10-27'])if(!fs.existsSync(path.join(root,d,'index.html'))){console.error('no index.html in '+path.join(root,d));process.exit(2)}
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.woff2':'font/woff2','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'};
const srv=http.createServer((q,r)=>{const f=path.join(root,decodeURIComponent(q.url.split('?')[0]));if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||fs.statSync(f).isDirectory()){r.writeHead(404);return r.end()}r.writeHead(200,{'content-type':types[path.extname(f)]||'application/octet-stream'});fs.createReadStream(f).pipe(r)}).listen(0,async()=>{
 const port=srv.address().port;const b=await chromium.launch();const report=[];for(const d of ['design-system-2026-10-27','ux-upgrade-2026-10-27'])fs.mkdirSync(path.join(out,d),{recursive:true});
 async function shot(url,name,act){const p=await b.newPage({viewport:{width:1440,height:1000}});const errs=[],fails=[];
  p.on('pageerror',e=>errs.push(String(e).slice(0,200)));p.on('console',m=>{if(m.type()==='error')errs.push(m.text().slice(0,200))});
  p.on('response',r=>{if(r.status()>=400)fails.push(r.status()+' '+r.url())});p.on('requestfailed',r=>fails.push(r.url()));
  await p.goto(url,{waitUntil:'networkidle',timeout:90000});if(act)await act(p);await p.mouse.move(1435,995);await p.waitForTimeout(1500);
  const h=await p.evaluate(()=>document.documentElement.scrollHeight);const txt=await p.evaluate(()=>document.body.innerText.length);
  await p.screenshot({path:path.join(out,name),fullPage:true});report.push({page:url.replace(/^.*?\d+\//,''),png:name,h,text_chars:txt,errors:errs,failed_requests:fails.filter(u=>!u.includes('fonts.g'))});await p.close()}
 const ds=`http://127.0.0.1:${port}/design-system-2026-10-27/index.html`;
 await shot(ds,'design-system-2026-10-27/01-design-system-light.png');
 await shot(ds,'design-system-2026-10-27/02-design-system-dark.png',async p=>{const t=p.locator('button[aria-pressed]').first();await t.click();await p.waitForTimeout(800)});
 await shot(`http://127.0.0.1:${port}/ux-upgrade-2026-10-27/index.html`,'ux-upgrade-2026-10-27/01-before-after.png');
 fs.writeFileSync(path.join(out,'report-pages.json'),JSON.stringify(report,null,1));await b.close();srv.close();
 for(const r of report)console.log(r.png,'h',r.h,'chars',r.text_chars,'err',r.errors.length,'fail',r.failed_requests.length,r.failed_requests.slice(0,3).join(' '))});
