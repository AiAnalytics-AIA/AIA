from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from ui_server import visualization_respondents, visualization_object_map

pid='MMC-DEMO-01'
RR=visualization_respondents({'project_id':pid})
OO=visualization_object_map({'project_id':pid})
assert RR.get('available') and RR.get('payload',{}).get('respondent_count')==1500
html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
pre=f'''<script>(()=>{{const RR={json.dumps(RR)},OO={json.dumps(OO)};const s=new Map();Object.defineProperty(window,'localStorage',{{value:{{getItem:k=>s.get(String(k))||null,setItem:(k,v)=>s.set(String(k),String(v)),removeItem:k=>s.delete(String(k)),clear:()=>s.clear()}},configurable:true}});window.fetch=async(url,opt={{}})=>{{let u=String(url);const ok=x=>new Response(JSON.stringify(x),{{status:200,headers:{{'Content-Type':'application/json'}}}});if(u.includes('/api/visualization/respondents'))return ok(RR);if(u.includes('/api/visualization/object-map'))return ok(OO);if(u.includes('/api/visualization/intelligence'))return ok({{available:false}});if(u.includes('/api/visualization/layout'))return ok({{ok:true}});return ok({{}})}}}})();</script>'''
html=html.replace('<head>','<head>'+pre,1)

with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1600,'height':1100})
    errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(500)
    page.evaluate("()=>{if(!document.getElementById('view'))document.body.insertAdjacentHTML('beforeend','<div id=\"view\"></div>');DEMO_DETAIL_1794={project_id:'MMC-DEMO-01',title:'MMC DEMO',name:'MMC DEMO'};}")
    page.evaluate("renderSociomapWorkspace1866('demo')");page.wait_for_timeout(1000)
    dock=page.locator('.npcMapDock1877');assert dock.count()==1 and dock.is_visible()
    txt=dock.inner_text()
    for token in ['Respondenti','Objekty','Analytik','Klient','Nastavení mapy','Nástroje','Analýza','Čistý slide']:
        assert token in txt
    dock.get_by_role('button',name='Nástroje',exact=True).click();page.wait_for_timeout(80)
    assert 'Nástroje mapy' in page.locator('.npcMapPanel27').inner_text()
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Analýza').click()");page.wait_for_timeout(80)
    assert 'Vysvětli tuto oblast' in page.locator('.npcMapPanel27').inner_text()
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Objekty').click()");page.wait_for_timeout(150)
    assert page.evaluate('SOCIOMAP1866.mapType')=='objects'
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Respondenti').click()");page.wait_for_timeout(150)
    assert page.evaluate('SOCIOMAP1866.mapType')=='respondents'
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Klient').click()");page.wait_for_timeout(80)
    assert page.evaluate('SOCIOMAP1866.viewMode27')=='client'
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Analytik').click()");page.wait_for_timeout(80)
    hits=page.evaluate("SOCIOMAP1866.hits.filter(x=>x.kind==='respondent').slice(0,1)")
    assert hits
    h=hits[0];box=page.locator('#socioCanvas66').bounding_box();page.mouse.click(box['x']+h['x'],box['y']+h['y']);page.wait_for_timeout(120)
    assert page.locator('.socio66Side.right').is_visible()
    assert page.locator('.npcDetailClose1877').count()==1
    page.evaluate('npcCloseDetail1877()');page.wait_for_timeout(50)
    assert not page.locator('.socio66Side.right').is_visible()
    page.evaluate("[...document.querySelectorAll('.npcMapDock1877 button')].find(b=>b.textContent==='Čistý slide').click()");page.wait_for_timeout(80)
    assert 'clean27' in (page.locator('.socio66').get_attribute('class') or '') and page.locator('.npcReturn27').is_visible()
    page.evaluate('npcClean27()');page.wait_for_timeout(80)
    assert page.locator('.npcMapDock1877').count()==1
    assert not errs,errs
    b.close()
print('INTERACTIVE_SOCIO_1877_BROWSER_PASS')
