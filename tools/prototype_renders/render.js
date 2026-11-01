const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const http=require('http');
// node render.js <folder holding the canvas folders> <out dir> [one canvas folder]
// Each canvas folder needs the Design type's runtime saved as support.js (not committed: it is the type's file).
if(process.argv.length<4){console.error('usage: node render.js <folder holding the canvas folders> <out dir> [one canvas folder]');process.exit(2)}
const root=path.resolve(process.argv[2]), out=path.resolve(process.argv[3]), only=process.argv[4];
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.jpg':'image/jpeg','.png':'image/png','.svg':'image/svg+xml','.json':'application/json','.webp':'image/webp','.woff2':'font/woff2'};
const srv=http.createServer((q,r)=>{const f=path.join(root,decodeURIComponent(q.url.split('?')[0]));if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||fs.statSync(f).isDirectory()){r.writeHead(404);return r.end()}r.writeHead(200,{'content-type':types[path.extname(f)]||'application/octet-stream'});fs.createReadStream(f).pipe(r)}).listen(0,async()=>{
 const port=srv.address().port;const b=await chromium.launch();const report=[];
 // Only folders holding a canvas.json are canvases; anything else in the root is skipped.
 const canvases=fs.readdirSync(root).filter(x=>(!only||x===only)&&fs.existsSync(path.join(root,x,'canvas.json')));
 if(only&&!canvases.length){console.error('no canvas.json in '+path.join(root,only));process.exit(2)}
 for(const d of canvases){const cj=JSON.parse(fs.readFileSync(path.join(root,d,'canvas.json')));const boards=Object.entries(cj.boards||{});
  fs.mkdirSync(path.join(out,d),{recursive:true});let i=0;
  for(const [file,meta] of boards){i++;const w=meta.w||1440,h=meta.h||1200;const p=await b.newPage({viewport:{width:w,height:Math.min(h,4000)}});const errs=[];
   p.on('pageerror',e=>errs.push(String(e).slice(0,200)));p.on('console',m=>{if(m.type()==='error')errs.push(m.text().slice(0,200))});
   const fails=[];p.on('requestfailed',r=>fails.push(r.url()));p.on('response',r=>{if(r.status()>=400)fails.push(r.status()+' '+r.url())});
   await p.goto(`http://127.0.0.1:${port}/${d}/${file}`,{waitUntil:'networkidle',timeout:60000}).catch(e=>errs.push('goto '+e.message));
   await p.mouse.move(w-5,Math.min(h,4000)-5);await p.waitForTimeout(1500);
   const txt=await p.evaluate(()=>document.body.innerText.length).catch(()=>-1);
   const name=String(i).padStart(2,'0')+'-'+file.replace('.dc.html','')+'.png';
   await p.screenshot({path:path.join(out,d,name),fullPage:true}).catch(e=>errs.push('shot '+e.message));
   report.push({canvas:d,board:file,title:meta.title,w,h,png:name,text_chars:txt,errors:errs,failed_requests:fails.filter(u=>!u.includes('fonts.g'))});await p.close()}}
 fs.writeFileSync(path.join(out,'report-'+(only||'all')+'.json'),JSON.stringify(report,null,1));await b.close();srv.close();
 for(const r of report)console.log(r.canvas,r.board,'chars',r.text_chars,'err',r.errors.length,'fail',r.failed_requests.length)});
