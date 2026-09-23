from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from ui_server import visualization_respondents, visualization_object_map

html=(ROOT/'ui_app.html').read_text(encoding='utf-8')

def run(pid,family,commercial):
    RR=visualization_respondents({'project_id':pid}); OO=visualization_object_map({'project_id':pid})
    assert RR.get('available') and OO.get('available')
    pre=f'''<script>(()=>{{const RR={json.dumps(RR)},OO={json.dumps(OO)};const s=new Map();Object.defineProperty(window,'localStorage',{{value:{{getItem:k=>s.get(String(k))||null,setItem:(k,v)=>s.set(String(k),String(v)),removeItem:k=>s.delete(String(k)),clear:()=>s.clear()}},configurable:true}});window.fetch=async(url,opt={{}})=>{{let u=String(url);const ok=x=>new Response(JSON.stringify(x),{{status:200,headers:{{'Content-Type':'application/json'}}}});if(u.includes('/api/visualization/respondents'))return ok(RR);if(u.includes('/api/visualization/object-map'))return ok(OO);if(u.includes('/api/visualization/intelligence'))return ok({{available:false}});if(u.includes('/api/visualization/layout'))return ok({{ok:true}});return ok({{}})}}}})();</script>'''
    doc=html.replace('<head>','<head>'+pre,1)
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1600,'height':1050}); errs=[]; page.on('pageerror',lambda e:errs.append(str(e)))
        page.set_content(doc,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(350)
        page.evaluate("(pid)=>{if(!document.getElementById('view'))document.body.insertAdjacentHTML('beforeend','<div id=\"view\"></div>');DEMO_DETAIL_1794={project_id:pid,title:'DEMO',name:'DEMO'};CURRENT='demo_project';}",pid)
        page.evaluate("openSociomap1863('demo')");page.wait_for_timeout(1100)
        page.evaluate("f=>npcFamily27(f)",family);page.wait_for_timeout(350)
        idx=page.evaluate("f=>{for(let i=0;i<SOCIOMAP1866.objects.names.length;i++){if(npcObjectRelationshipProfile1882(i).family===f)return i}return -1}",family)
        assert idx>=0,(pid,family,page.evaluate("SOCIOMAP1866.objectManager27.families"))
        prof=page.evaluate("i=>npcObjectRelationshipProfile1882(i)",idx)
        assert prof['commercial'] is commercial
        assert prof['comparableCount']>=1
        page.evaluate("i=>{SOCIOMAP1866.selectedObject=i;SOCIOMAP1866.selectedPerson=null;SOCIOMAP1866.modalSide27='right';__npcRenderRight66();}",idx)
        page.wait_for_timeout(100)
        text=page.locator('#socioRight66').inner_text().lower()
        assert 'překryv s dalšími objekty stejné family' in text
        assert 'stejné vnímání' in text
        if commercial:
            assert 'naši / unikátní silný vztah' in text
            assert 'o koho soupeříme / sdílený silný vztah' in text
            assert 'potenciál / střední vztah' in text
        else:
            assert 'unikátní silný vztah' in text and 'sdílený silný vztah' in text
            assert 'haters' not in text
            assert 'naši /' not in text
        assert not errs,errs
        b.close()

run('GEMO-DEMO-REPUTATION','Claimy',False)
run('MMC-DEMO-01','Produkty a služby',True)
print('OBJECT_RELATIONSHIP_FIELD_1882_BROWSER_PASS')
