from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from ui_server import visualization_respondents, visualization_object_map

pid='GEMO-DEMO-REPUTATION'
RR=visualization_respondents({'project_id':pid})
OO=visualization_object_map({'project_id':pid})
assert RR.get('available') and RR.get('payload',{}).get('respondent_count')==250
assert OO.get('available') and len((OO.get('object_map') or {}).get('names',[]))>=2
html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
pre=f'''<script>(()=>{{const RR={json.dumps(RR)},OO={json.dumps(OO)};const s=new Map();Object.defineProperty(window,'localStorage',{{value:{{getItem:k=>s.get(String(k))||null,setItem:(k,v)=>s.set(String(k),String(v)),removeItem:k=>s.delete(String(k)),clear:()=>s.clear()}},configurable:true}});window.fetch=async(url,opt={{}})=>{{let u=String(url);const ok=x=>new Response(JSON.stringify(x),{{status:200,headers:{{'Content-Type':'application/json'}}}});if(u.includes('/api/visualization/respondents'))return ok(RR);if(u.includes('/api/visualization/object-map'))return ok(OO);if(u.includes('/api/visualization/intelligence'))return ok({{available:false}});if(u.includes('/api/visualization/layout'))return ok({{ok:true}});if(u.includes('/api/projects/load'))return ok({{is_demo:true,project_id:'{pid}',title:'GEMO DEMO',name:'GEMO DEMO'}});return ok({{}})}}}})();</script>'''
html=html.replace('<head>','<head>'+pre,1)

with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1600,'height':1200})
    errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(500)
    page.evaluate("()=>{if(!document.getElementById('view'))document.body.insertAdjacentHTML('beforeend','<div id=\"view\"></div>');DEMO_DETAIL_1794={project_id:'GEMO-DEMO-REPUTATION',title:'GEMO DEMO',name:'GEMO DEMO'};CURRENT='demo_project';}")
    page.evaluate("openSociomap1863('demo')");page.wait_for_timeout(1100)

    # GEMO really opens into the shared interactive workspace.
    assert page.locator('.socio66').count()==1
    dock=page.locator('.npcMapDock1877');assert dock.count()==1 and dock.is_visible()
    assert page.evaluate('SOCIOMAP1866.project_id')==pid
    assert page.evaluate('SOCIOMAP1866.respondents.respondent_count')==250

    # Large map is followed by analysis/segments instead of becoming a dead end.
    below=page.locator('.npcSocioBelow1878');assert below.count()==1 and below.is_visible()
    bt=below.inner_text();assert 'SEGMENTACE A POROVNÁNÍ' in bt and 'Pokračujte pod mapou' in bt

    # Settings stays alive through real interactions.
    dock.get_by_role('button',name='Nastavení mapy',exact=True).click();page.wait_for_timeout(100)
    panel=page.locator('.npcMapPanel27');assert panel.count()==1 and panel.is_visible()
    txt=panel.inner_text();assert 'Předpřipravené mapy / family' in txt and 'Claimy' in txt and 'Důvěra v čase' in txt
    panel.get_by_role('button',name='Claimy',exact=True).click();page.wait_for_timeout(350)
    assert page.evaluate('SOCIOMAP1866.objectManager27.activeFamily')=='Claimy'
    assert page.locator('.npcMapPanel27').is_visible() and page.locator('.npcMapDock1877').is_visible()

    # Height + normalization remains interactive after family recompute.
    sel=page.locator('.npcMapPanel27 select').first
    opts=sel.locator('option').all()
    if len(opts)>1:
        val=opts[1].get_attribute('value')
        sel.select_option(val);page.wait_for_timeout(220)
        assert page.evaluate('SOCIOMAP1866.heightMetric')==val
    page.locator('.npcMapPanel27').get_by_role('button',name='σ',exact=True).click();page.wait_for_timeout(220)
    assert page.evaluate('SOCIOMAP1866.norm')=='sigma'
    assert page.locator('.npcMapPanel27').is_visible() and page.locator('.npcMapDock1877').is_visible()

    # Object Manager is reachable from the same Settings surface.
    page.locator('.npcMapPanel27').get_by_role('button',name='Detailní Object Manager',exact=True).click();page.wait_for_timeout(120)
    om=page.locator('.npcObjManager27');assert om.count()==1 and om.is_visible()
    assert 'Objekty / vrstvy' in om.inner_text()
    page.evaluate('npcClosePanel27()');page.wait_for_timeout(80)

    # Clean slide return must receive a real pointer click above the canvas.
    page.get_by_role('button',name='Čistý slide',exact=True).click();page.wait_for_timeout(120)
    assert 'clean27' in (page.locator('.socio66').get_attribute('class') or '')
    ret=page.locator('.npcReturn27');assert ret.count()==1 and ret.is_visible()
    ret.click();page.wait_for_timeout(180)
    assert 'clean27' not in (page.locator('.socio66').get_attribute('class') or '')
    assert page.locator('.npcMapDock1877').is_visible()

    # Object mode still exposes prepared family maps below the large map.
    page.get_by_role('button',name='Objekty',exact=True).click();page.wait_for_timeout(220)
    assert page.evaluate('SOCIOMAP1866.mapType')=='objects'
    below=page.locator('.npcSocioBelow1878');assert below.is_visible()
    assert 'Předpřipravené family' in below.inner_text()

    assert not errs,errs
    b.close()
print('SOCIO_FLOW_1879_BROWSER_PASS')
