from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from ui_server import visualization_respondents, visualization_object_map
pid='GEMO-DEMO-REPUTATION'
RR=visualization_respondents({'project_id':pid});OO=visualization_object_map({'project_id':pid})
assert RR.get('available') and RR.get('payload',{}).get('respondent_count')==250
assert OO.get('available')
html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
pre=f'''<script>(()=>{{const RR={json.dumps(RR)},OO={json.dumps(OO)};const s=new Map();Object.defineProperty(window,'localStorage',{{value:{{getItem:k=>s.get(String(k))||null,setItem:(k,v)=>s.set(String(k),String(v)),removeItem:k=>s.delete(String(k)),clear:()=>s.clear()}},configurable:true}});window.fetch=async(url,opt={{}})=>{{let u=String(url);const ok=x=>new Response(JSON.stringify(x),{{status:200,headers:{{'Content-Type':'application/json'}}}});if(u.includes('/api/visualization/respondents'))return ok(RR);if(u.includes('/api/visualization/object-map'))return ok(OO);if(u.includes('/api/visualization/intelligence'))return ok({{available:false}});if(u.includes('/api/visualization/layout'))return ok({{ok:true}});return ok({{}})}}}})();</script>'''
html=html.replace('<head>','<head>'+pre,1)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1500,'height':1050});errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(350)
    page.evaluate("()=>{if(!document.getElementById('view'))document.body.insertAdjacentHTML('beforeend','<div id=\"view\"></div>');DEMO_DETAIL_1794={project_id:'GEMO-DEMO-REPUTATION',title:'GEMO DEMO',name:'GEMO DEMO'};CURRENT='demo_project';}")
    page.evaluate("openSociomap1863('demo')");page.wait_for_timeout(1000)
    assert page.evaluate('SOCIOMAP1866.mapType')=='respondents'
    assert page.evaluate('SOCIOMAP1866.heightMetric')=='density'
    r=page.evaluate("()=>{let t=__npcTerrain66();let z=t.grid.flat().map(q=>q.z);return {mode:t.terrain_mode,id:t.hDef.id,min:Math.min(...z),max:Math.max(...z)}}")
    assert r['mode']=='respondent_density' and r['id']=='density' and r['max']-r['min']>5,r
    # Family changes positions, but respondent height semantics remains density.
    fams=page.evaluate("[...new Set(SOCIOMAP1866.objectManager27.families)]")
    target='Claimy' if 'Claimy' in fams else fams[-1]
    page.evaluate("f=>npcFamily27(f)",target);page.wait_for_timeout(300)
    r2=page.evaluate("()=>{let t=__npcTerrain66();let z=t.grid.flat().map(q=>q.z);return {mode:t.terrain_mode,id:t.hDef.id,height:SOCIOMAP1866.heightMetric,min:Math.min(...z),max:Math.max(...z)}}")
    assert r2['mode']=='respondent_density' and r2['id']=='density' and r2['height']=='density' and r2['max']-r2['min']>5,r2
    # Object mode returns to object-metric terrain.
    page.evaluate("socioMapType66('objects')");page.wait_for_timeout(250)
    o=page.evaluate("()=>{let t=__npcTerrain66();return {mode:t.terrain_mode,id:t.hDef.id,height:SOCIOMAP1866.heightMetric}}")
    assert o['mode']=='object_metric' and o['id']!='density' and o['height']!='density',o
    # Back to respondents restores density semantics.
    page.evaluate("socioMapType66('respondents')");page.wait_for_timeout(250)
    back=page.evaluate("()=>({mode:__npcTerrain66().terrain_mode,height:SOCIOMAP1866.heightMetric})")
    assert back=={'mode':'respondent_density','height':'density'},back
    assert not errs,errs
    b.close()
print('SOCIO_HEIGHT_SEMANTICS_1880_BROWSER_PASS')
