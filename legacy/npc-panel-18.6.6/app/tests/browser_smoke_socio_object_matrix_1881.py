from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from ui_server import visualization_respondents, visualization_object_map, visualization_intelligence

pid='GEMO-DEMO-REPUTATION'
RR=visualization_respondents({'project_id':pid})
OO=visualization_object_map({'project_id':pid})
II=visualization_intelligence({'project_id':pid})
assert RR.get('available') and RR['payload']['respondent_count']==250
assert OO.get('available') and len(OO['object_map']['names'])==18
assert II.get('available') and len((II.get('intelligence') or {}).get('candidates') or [])>=1
html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
pre=f'''<script>(()=>{{const RR={json.dumps(RR)},OO={json.dumps(OO)},II={json.dumps(II)};const s=new Map();Object.defineProperty(window,'localStorage',{{value:{{getItem:k=>s.get(String(k))||null,setItem:(k,v)=>s.set(String(k),String(v)),removeItem:k=>s.delete(String(k)),clear:()=>s.clear()}},configurable:true}});window.fetch=async(url,opt={{}})=>{{let u=String(url);const ok=x=>new Response(JSON.stringify(x),{{status:200,headers:{{'Content-Type':'application/json'}}}});if(u.includes('/api/visualization/respondents'))return ok(RR);if(u.includes('/api/visualization/object-map'))return ok(OO);if(u.includes('/api/visualization/intelligence'))return ok(II);if(u.includes('/api/visualization/layout'))return ok({{ok:true}});if(u.includes('/api/projects/load'))return ok({{is_demo:true,project_id:'{pid}',title:'GEMO DEMO',name:'GEMO DEMO'}});if(u.includes('/api/visualization/segment'))return ok({{ok:true}});return ok({{}})}}}})();</script>'''
html=html.replace('<head>','<head>'+pre,1)

with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1700,'height':1200})
    errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(500)
    page.evaluate("()=>{if(!document.getElementById('view'))document.body.insertAdjacentHTML('beforeend','<div id=\"view\"></div>');DEMO_DETAIL_1794={project_id:'GEMO-DEMO-REPUTATION',title:'GEMO DEMO',name:'GEMO DEMO'};CURRENT='demo_project';}")
    page.evaluate("openSociomap1863('demo')");page.wait_for_timeout(1400)
    assert page.locator('.socio66').count()==1
    assert page.evaluate('SOCIOMAP1866.respondents.respondent_count')==250
    assert page.evaluate('SOCIOMAP1866.objects.names.length')==18

    # Settings: Mapa + relationships + matrix are visible.
    page.get_by_role('button',name='Nastavení mapy',exact=True).click();page.wait_for_timeout(100)
    panel=page.locator('.npcMapPanel27');txt=panel.inner_text()
    for x in ['Mapa','Mapa respondentů','Objektová mapa','Správa vztahů','Zobrazit matici']:
        assert x in txt

    # Switch to a family with >=5 PRIMARY objects, then stage one removal.
    panel.get_by_role('button',name='Atributy důvěryhodnosti',exact=True).click();page.wait_for_timeout(350)
    assert page.evaluate("SOCIOMAP1866.objectManager27.activeFamily")=='Atributy důvěryhodnosti'
    before_pts=page.evaluate("SOCIOMAP1866.respondents.points.slice(0,80).map(p=>[String(p.id),p.x,p.y])")
    assert page.evaluate('SOCIOMAP1866.objects.names.length')==18
    page.locator('.npcMapPanel27').get_by_role('button',name='Detailní Object Manager',exact=True).click();page.wait_for_timeout(120)
    om=page.locator('.npcObjManager27');assert om.is_visible()
    row=om.locator('.npcObjRow27').filter(has_text='Kvalita stavebni prace').first
    assert row.count()==1
    row.locator('select').first.select_option(label='HIDDEN');page.wait_for_timeout(100)
    assert page.evaluate('SOCIOMAP1866.objects.names.length')==18, 'draft must not mutate active matrix'
    assert 'Po aplikaci: 17 × 17' in om.inner_text()
    om.get_by_role('button',name='Aplikovat změny',exact=True).click();page.wait_for_timeout(450)
    assert page.evaluate('SOCIOMAP1866.objects.names.length')==17
    assert page.evaluate("SOCIOMAP1866.objects.matrix.length") == 17
    assert page.evaluate("SOCIOMAP1866.objects.matrix.every(r=>r.length===17)")
    assert page.evaluate("!SOCIOMAP1866.objects.names.includes('Kvalita stavebni prace')")
    after_pts=page.evaluate("SOCIOMAP1866.respondents.points.slice(0,80).map(p=>[String(p.id),p.x,p.y])")
    moved=sum(1 for a,z in zip(before_pts,after_pts) if abs(float(a[1])-float(z[1]))+abs(float(a[2])-float(z[2]))>0.05)
    assert moved>=20,moved

    # Relationship manager exposes the actual reduced matrix and scenario editing.
    page.get_by_role('button',name='Nastavení mapy',exact=True).click();page.wait_for_timeout(100)
    page.locator('.npcMapPanel27').get_by_role('button',name='Správa vztahů',exact=True).click();page.wait_for_timeout(120)
    rel=page.locator('.npcObjManager27');rt=rel.inner_text()
    assert 'Správa vztahů a aktivní matice' in rt and '17 × 17' in rt
    assert 'Kvalita stavebni prace' not in rt
    rel.get_by_role('button',name='Scénář / upravit vztahy',exact=True).click();page.wait_for_timeout(220)
    assert page.evaluate("SOCIOMAP1866.sourceMode")=='scenario'
    rel=page.locator('.npcObjManager27')
    inputs=rel.locator('table input');assert inputs.count()>0
    first=inputs.first;old=float(first.input_value());newv=8.7 if abs(old-8.7)>.01 else 7.3
    first.fill(str(newv));first.press('Tab');page.wait_for_timeout(220)
    assert page.evaluate("Object.keys(SOCIOMAP1866.edits).length")>=1

    # Scenarios are visible as a first-class map tool.
    page.evaluate('npcClosePanel27()');page.wait_for_timeout(60)
    page.get_by_role('button',name='Nástroje',exact=True).click();page.wait_for_timeout(100)
    tools=page.locator('.npcMapPanel27');tt=tools.inner_text()
    assert 'Scénáře / Co když…' in tt and 'Co se stane, když…' in tt and 'Vztahy / matice' in tt
    tools.get_by_role('button',name='Co se stane, když…',exact=True).click();page.wait_for_timeout(100)
    sim=page.locator('.npcMapPanel27');assert 'Popis scénáře' in sim.inner_text()

    # Return to original state and switch to non-commercial Claimy before testing object click.
    page.evaluate("SOCIOMAP1866.edits={};SOCIOMAP1866.sourceMode='original';SOCIOMAP1866.panel27=null;npcFamily27('Claimy');")
    page.wait_for_timeout(420)
    assert page.evaluate("SOCIOMAP1866.objectManager27.activeFamily")=='Claimy'

    # Real canvas click on a Claim object in respondent mode must open OBJECT detail, not respondent detail.
    hit=page.evaluate(r"""()=>{let hs=SOCIOMAP1866.hits||[],objs=SOCIOMAP1866.respondents?.objects||[];for(const h of hs){if(h.kind==='respondent_object'){let o=objs.find(x=>String(x.key)===String(h.id));if(o?.family==='Claimy')return h}}return hs.find(h=>h.kind==='object')}""")
    assert hit, page.evaluate("(SOCIOMAP1866.hits||[]).map(h=>h.kind)")
    box=page.locator('#socioCanvas66').bounding_box();assert box
    page.mouse.click(box['x']+float(hit['x']),box['y']+float(hit['y']));page.wait_for_timeout(260)
    detail=page.locator('#socioRight66');assert detail.is_visible()
    dt=detail.inner_text()
    assert 'pole vztahů objektu' in dt.lower()
    assert 'unikátní silný vztah' in dt.lower() and 'sdílený silný vztah' in dt.lower()
    assert 'překryv s dalšími objekty stejné family' in dt.lower()
    assert 'stejné vnímání' in dt.lower()
    assert 'haters' not in dt.lower(), dt
    assert 'detail objektu' in dt.lower()
    assert not dt.startswith('Respondent ')

    prof=page.evaluate("()=>npcObjectRelationshipProfile1882(SOCIOMAP1866.selectedObject)")
    assert prof['family']=='Claimy' and prof['commercial'] is False
    assert prof['comparableCount']>=1

    # AI/discovery and quick filters must be distinct concepts and not duplicated labels.
    page.wait_for_timeout(500)
    below=page.locator('.npcSocioBelow1878');bt=below.inner_text()
    assert 'AI / discovery ·' in bt and 'Rychlý filtr ·' in bt
    # Compare visible button labels in JS to avoid opaque locator details.
    pairs=page.evaluate(r"""()=>{let cards=[...document.querySelectorAll('.belowCard1878')];let a=cards.find(x=>x.innerText.includes('AI · zajímavé skupiny')),q=cards.find(x=>x.innerText.includes('Rychlé segmenty'));let norm=s=>s.replace(/^AI \/ discovery · |^Rychlý filtr · /,'').split('\n')[0].trim().toLowerCase();return {a:[...(a?.querySelectorAll('.seg1878')||[])].map(x=>norm(x.innerText)),q:[...(q?.querySelectorAll('.seg1878')||[])].map(x=>norm(x.innerText))}}""")
    assert set(pairs['a']).isdisjoint(set(pairs['q'])),pairs

    unexpected=[e for e in errs if '(intermediate value)(...) is not a function' not in e]
    assert not unexpected,(errs,unexpected)
    b.close()
print('SOCIO_OBJECT_MATRIX_1881_BROWSER_PASS')
