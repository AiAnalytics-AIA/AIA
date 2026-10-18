// Browser verification of the V2 prototype in real Chromium (playwright-core).
// node scripts/verify.mjs [baseUrl] [outDir]
// Every check prints PASS/FAIL with what it measured; screenshots go to outDir.
import { chromium } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174/';
const OUT = process.argv[3] ?? 'verify-out';
mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail = '') => { results.push({ name, ok: !!ok, detail }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); };

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const errors = [];
async function open(q, w = 1440, h = 900, { fresh = true } = {}) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(q + ': ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(q + ': ' + m.text()); });
  await page.goto(BASE + '?' + q);
  if (fresh) await page.evaluate(() => { try { localStorage.clear(); } catch { /* */ } });
  await page.waitForTimeout(q.includes('fast=1') ? 700 : 400);
  return page;
}
const st = (page) => page.evaluate(() => window.__aia.getState());
const idle = async (page, ms = 15000) => { const t = Date.now(); while (Date.now() - t < ms) { if (!(await st(page)).busy) return true; await page.waitForTimeout(150); } return false; };
const noHScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

// ---------------------------------------------------------------- 1 stages at three widths
for (const [w, h] of [[1280, 800], [1440, 900], [1920, 1080]]) {
  const page = await open('fast=1&s=G', w, h);
  const labels = await page.$$eval('.nav__stage', (b) => b.map((x) => x.textContent.replace(/,.*$/, '').trim()));
  let ok = labels.length === 11;
  const titles = [];
  for (let i = 0; i < labels.length; i++) {
    await page.locator('.nav__stage').nth(i).click();
    await page.waitForTimeout(120);
    titles.push(await page.textContent('.arthead__title'));
    if (!(await noHScroll(page))) ok = false;
  }
  check(`all 11 stages reachable, no horizontal scroll @${w}`, ok && titles.length === 11, titles.join(' · '));
  const overflow = await page.evaluate(() => [...document.querySelectorAll('.arthead, .shead, .nav, .composer')].filter((e) => e.scrollWidth > e.clientWidth + 2).map((e) => e.className));
  check(`header, navigator, artifact header and composer do not overflow @${w}`, overflow.length === 0, overflow.join(','));
  await page.screenshot({ path: `${OUT}/overview-${w}.png` });
  await page.context().close();
}

// ---------------------------------------------------------------- 2 split: default, drag, keys, reset, persistence
{
  const page = await open('fast=1&s=A&auto=0', 1440, 900);
  const ratio = () => page.evaluate(() => { const l = document.querySelector('.split__left').getBoundingClientRect().width; const t = document.querySelector('.split').getBoundingClientRect().width; return Math.round((l / t) * 1000) / 10; });
  check('default split is 40/60', Math.abs((await ratio()) - 40) < 1, (await ratio()) + ' %');
  const hb = await page.locator('.split__handle').boundingBox();
  const sb = await page.locator('.split').boundingBox();
  await page.mouse.move(hb.x + hb.width / 2, hb.y + 200); await page.mouse.down();
  await page.mouse.move(sb.x + sb.width * 0.5, hb.y + 200, { steps: 8 }); await page.mouse.up();
  check('drag resizes the split', Math.abs((await ratio()) - 50) < 1.5, (await ratio()) + ' %');
  await page.reload(); await page.waitForTimeout(500);
  check('split persists across reload', Math.abs((await ratio()) - 50) < 1.5, (await ratio()) + ' %');
  await page.locator('.split__handle').focus(); await page.keyboard.press('ArrowRight');
  check('ArrowRight widens the conversation by 2', Math.abs((await ratio()) - 52) < 1.5, (await ratio()) + ' %');
  await page.keyboard.press('Home');
  check('Home resets to 40', Math.abs((await ratio()) - 40) < 1, (await ratio()) + ' %');
  await page.keyboard.press('ArrowLeft'); await page.keyboard.press('ArrowLeft');
  await page.locator('.split__handle').dblclick();
  check('double-click resets to 40', Math.abs((await ratio()) - 40) < 1, (await ratio()) + ' %');
  const focusVis = await page.evaluate(() => getComputedStyle(document.querySelector('.split__handle'), '::after').backgroundColor);
  check('focused handle is visibly marked', focusVis !== 'rgba(0, 0, 0, 0)', focusVis);

  // focus modes + restoration
  await page.locator('.split__handle').focus(); await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
  const before = await ratio();
  await page.hover('.conv__scroll'); await page.mouse.wheel(0, -900); await page.waitForTimeout(400);
  const top0 = await page.evaluate(() => document.querySelector('.conv__scroll').scrollTop);
  check('reading history: scrolled up away from the latest', await page.isVisible('.conv__latest'), 'scrollTop ' + top0);
  await page.click('.nav__stage >> nth=2');
  await page.locator('.arthead__actions .iconbtn').last().click();
  check('artifact focus shows the rail, hides the conversation', (await page.$('.split__rail')) && !(await page.$('.split__left')));
  await page.screenshot({ path: `${OUT}/focus-artifact-1440.png` });
  await page.locator('.rail .iconbtn').first().click(); await page.waitForTimeout(200);
  check('returning from artifact focus restores the saved split', Math.abs((await ratio()) - before) < 1, before + ' → ' + (await ratio()));
  const top1 = await page.evaluate(() => document.querySelector('.conv__scroll').scrollTop);
  check('conversation scroll position restored after artifact focus', Math.abs(top1 - top0) < 30, top0 + ' → ' + top1);
  await page.locator('.conv__head .iconbtn').last().click(); await page.waitForTimeout(150);
  check('conversation focus widens chat to 68 % without saving it', Math.abs((await ratio()) - 68) < 1 && (await st(page)).split === before, (await ratio()) + ' % (saved ' + (await st(page)).split + ')');
  await page.screenshot({ path: `${OUT}/focus-conversation-1440.png` });
  await page.locator('.conv__head .iconbtn').last().click(); await page.waitForTimeout(150);
  check('back to normal keeps the person\'s split', Math.abs((await ratio()) - before) < 1, (await ratio()) + ' %');
  await page.context().close();
}

// ---------------------------------------------------------------- 3 inspector: open, back, close, focus return
{
  const page = await open('fast=1&s=J&auto=0', 1440, 900);
  await page.click('.nav__stage:has-text("Analýza")');
  const opener = page.locator('.finding .srcchip').first();
  await opener.focus(); await opener.press('Enter');
  check('claim chip opens the inspector', await page.isVisible('.insp'), await page.textContent('.insp__title'));
  await page.locator('.insp .srcchip').first().click();
  check('inspector stacks a source and offers back', (await page.textContent('.insp__title')).length > 0 && await page.isVisible('.insp [aria-label="Zpět"]'), await page.textContent('.insp__title'));
  await page.click('.insp [aria-label="Zpět"]');
  check('back returns to the claim', (await page.textContent('.insp__title')).startsWith('Nárok'), await page.textContent('.insp__title'));
  await page.keyboard.press('Escape'); await page.waitForTimeout(100);
  const focusedIsChip = await page.evaluate(() => document.activeElement?.classList.contains('srcchip'));
  check('Escape closes the inspector and returns focus to the opener', !(await page.$('.insp')) && focusedIsChip);
  // blocked claim
  await page.click('.blocked .srcchip >> nth=0');
  check('blocked claim explains why', (await page.textContent('.insp__body')).includes('Proč blokováno'));
  await page.context().close();
}

// ---------------------------------------------------------------- 4 proposal: review, accept
{
  const page = await open('fast=1&s=B', 1440, 900);
  await idle(page);
  check('questionnaire proposal appears inline beside items', (await page.$$('.chg')).length >= 6, (await page.$$('.chg')).length + ' inline changes');
  check('protected Set 1 and Q19 are marked kept', (await page.textContent('.artbody')).includes('Ponecháno · Sada 1') && (await page.textContent('.artbody')).includes('Ponecháno · Q19'));
  check('Q16 kept as a separate construct', (await page.textContent('.artbody')).includes('Ponecháno · Q16'));
  await page.click('text=Dopad a pokrytí');
  const imp = await page.textContent('.impact');
  check('impact shows coverage gained, lost, kept and recompute', imp.includes('získá') && imp.includes('ztratí') && imp.includes('zachová') && imp.includes('Přepočet'));
  await page.screenshot({ path: `${OUT}/questionnaire-proposal-1440.png` });
  const ctx2 = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const p16 = await ctx2.newPage(); await p16.goto(BASE + '?fast=1&s=B'); await p16.waitForTimeout(900); await p16.click('text=Dopad a pokrytí'); await p16.waitForTimeout(150);
  await p16.screenshot({ path: `${OUT}/02-questionnaire-1600.png` }); await ctx2.close();
  await page.click('.artbar--you .btn--primary');
  const s = await st(page);
  const body = await page.textContent('.artbody');
  check('accepting creates revision 15', s.revision === 15, 'revision ' + s.revision);
  check('after acceptance Q10 is gone, Q9 open reason stays with routing', !body.includes('Ke které bance byste nejspíš přešli') && body.includes('Proč zvažujete změnu?') && body.includes('Q8 = Ano (kterákoli banka)'));
  check('Q8 keeps the target-bank choice', body.includes('Ano, k: Air Bank'));
  check('duration agrees with the Lead: 8,5 min after acceptance', (await page.textContent('.strip')).includes('8,5'), await page.textContent('.strip'));
  check('acceptance logged as a UI command', s.log.some((l) => l.cmd === 'proposal.accept' && l.by === 'ui' && l.ok));
  await page.context().close();
}
{
  const page = await open('fast=1&s=B', 1440, 900);
  await idle(page);
  await page.click('text=Ponechat současný stav');
  const s = await st(page);
  check('rejecting keeps the accepted questionnaire', s.revision === 14 && (await page.textContent('.artbody')).includes('Ke které bance byste nejspíš přešli') && s.proposals.some((p) => p.status === 'rejected'));
  await page.context().close();
}

// ---------------------------------------------------------------- 5 stale proposal and rebuild
{
  const page = await open('fast=1&s=E', 1440, 900);
  await page.click('.artbar--work .btn:has-text("Přijmout jako revizi")');
  await page.waitForTimeout(200);
  check('accepting your edit makes the pending proposal stale', await page.isVisible('.artbar--stale'), await page.textContent('.artbar--stale'));
  const ctx2 = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const p16 = await ctx2.newPage(); await p16.goto(BASE + '?fast=1&s=E'); await p16.waitForTimeout(700); await p16.click('.artbar--work .btn:has-text("Přijmout jako revizi")'); await p16.waitForTimeout(200);
  await p16.screenshot({ path: `${OUT}/09-stale-proposal-1600.png` }); await ctx2.close();
  const r = await page.evaluate(() => { const s = window.__aia.getState(); return s.proposals.find((p) => p.status === 'pending')?.id; });
  const refused = await page.evaluate(async (id) => { const m = await import('/src/app/commands.ts'); return m.acceptProposal(id, 'ui'); }, r);
  check('the accept command refuses a stale proposal', refused.ok === false && /revize 14/.test(refused.reason), refused.reason);
  const leadTry = await page.evaluate(async (id) => { const m = await import('/src/app/commands.ts'); return m.acceptProposal(id, 'lead'); }, r);
  check('the accept command refuses the Lead', leadTry.ok === false, leadTry.reason);
  await page.click('.artbar--stale .btn:has-text("Sestavit znovu")');
  await idle(page);
  const s = await st(page);
  const np = s.proposals.find((p) => p.status === 'pending');
  check('rebuild makes a new proposal on revision 15, nothing accepted', np && np.baseRev === 15 && s.revision === 15, np ? 'base ' + np.baseRev + ', ' + np.changes.filter((c) => c.why && c.kind !== 'keep').length + ' changes' : 'none');
  check('rebuilt proposal leaves your Q5 alone', np && !np.changes.some((c) => c.label === 'Q5'));
  check('old proposal marked superseded', s.proposals.some((p) => p.status === 'superseded'));
  await page.context().close();
}

// ---------------------------------------------------------------- 6 manual edits noticed; revision vs run binding
{
  const page = await open('fast=1&s=A', 1440, 900);
  await idle(page);
  await page.hover('[data-aia="questionnaire.b4.Q12"]');
  await page.click('[data-aia="questionnaire.b4.Q12"] [aria-label="Upravit Q12"]');
  await page.fill('[data-aia="questionnaire.b4.Q12"] textarea', 'Jak hodnotíte aplikaci své hlavní banky?');
  await page.click('[data-aia="questionnaire.b4.Q12"] >> text=Uložit do pracovní verze');
  check('a manual edit creates an autosaved working copy', await page.isVisible('.artbar--work'), await page.textContent('.artbar--work'));
  await page.waitForTimeout(2600); await idle(page);
  const s = await st(page);
  check('the Lead notices the edit once the person pauses', s.messages.some((m) => m.kind === 'lead' && (m.blocks?.[0]?.x ?? '').startsWith('Vidím 1 vaši úpravu')));
  check('the working-copy bar says the Lead has seen it', (await page.textContent('.artbar--work')).includes('vidí'));
  await page.context().close();
}
{
  const page = await open('fast=1&s=X5', 1440, 900);
  await page.click('.artbar--work .btn:has-text("Přijmout jako revizi")');
  await page.waitForTimeout(200);
  const s = await st(page);
  check('an edit after the run advances the study to revision 17, the run stays on 16', s.revision === 17 && s.run.revision === 16);
  check('fieldwork and results reopen', s.reopened.includes('fieldwork') && s.reopened.includes('results'), s.reopened.join(','));
  await page.click('.nav__stage:has-text("Výsledky")');
  const sub = await page.textContent('.arthead__sub');
  check('results header separates run revision from study revision', sub.includes('revize 16') && sub.includes('studie je na revizi 17'), sub);
  await page.context().close();
}

// ---------------------------------------------------------------- 7 audience research: evidence attached, class refusal
{
  const page = await open('fast=1&s=C', 1440, 900);
  await idle(page);
  const s = await st(page);
  check('research ran inside the envelope without a confirmation', s.decisions.filter((d) => d.status === 'open').length === 0 && s.research.some((r) => r.id === 'DR-41' && r.status === 'done'));
  check('a query derived from class-A material was refused for public search', s.log.some((l) => l.cmd.includes('audience.ass.A3') && !l.ok && /třída A|třídu/.test(l.reason)));
  check('evidence lines sit on assumptions A1–A3', (await page.$$('.evline')).length === 3);
  check('A3 is "unsupported", not "contradicted"', (await page.textContent('.artbody')).includes('nepodloženo dostupnými zdroji') && !(await page.textContent('.artbody')).toLowerCase().includes('vyvráceno'));
  check('assumption status unchanged until accepted', (await page.textContent('[data-aia="audience.ass.A3"] .chip')).includes('k ověření'));
  await page.click('[data-aia="audience.ass.A3.evidence.S3"] .srcchip');
  const insp = await page.textContent('.insp');
  check('source inspector shows kind, class, admission and provenance', ['Znalost klienta', 'A · důvěrné klienta', 'kontext', 'Původ'].every((x) => insp.includes(x)));
  await page.screenshot({ path: `${OUT}/audience-evidence-1440.png` });
  await page.setViewportSize({ width: 1600, height: 1000 }); await page.keyboard.press('Escape'); await page.waitForTimeout(150);
  await page.screenshot({ path: `${OUT}/03-audience-evidence-1600.png` });
  await page.context().close();
}

{
  const page = await open('s=A', 1440, 900);
  await idle(page, 20000);
  await page.fill('#composer', 'Ověř předpoklady o cílové skupině'); await page.keyboard.press('Enter');
  const t0 = Date.now(); while (Date.now() - t0 < 10000) { const s = await st(page); if (s.research.some((r) => r.status === 'running') && s.budget.studyReserved > 0) break; await page.waitForTimeout(100); }
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  const s = await st(page);
  check('stopping research marks the run stopped and releases its reservation', s.research.every((r) => r.status !== 'running') && s.budget.studyReserved === 0, s.research.map((r) => r.id + ':' + r.status).join(',') + ' · reserved ' + s.budget.studyReserved);
  await page.context().close();
}

// ---------------------------------------------------------------- 8 conversation: queue, stop, older, return-to-latest, keys
{
  const page = await open('s=A', 1440, 900);
  await idle(page, 20000);
  await page.fill('#composer', 'Posuď dotazník a navrhni zkrácení'); await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  await page.fill('#composer', 'Kde jsme?'); await page.keyboard.press('Enter');
  await page.waitForTimeout(100);
  check('a message sent while the Lead works is queued', await page.isVisible('.queue'), await page.textContent('.queue'));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  let s = await st(page);
  check('Escape stops the Lead and says nothing was accepted', s.messages.some((m) => m.kind === 'notice' && (m.text ?? '').startsWith('Zastaveno vámi')));
  await idle(page, 20000);
  s = await st(page);
  check('the queued message is sent after the stop', s.messages.filter((m) => m.kind === 'user').some((m) => m.text === 'Kde jsme?') && !s.composer.queue.length);
  await page.fill('#composer', 'řádek 1'); await page.keyboard.press('Shift+Enter'); await page.keyboard.type('řádek 2');
  check('Shift+Enter adds a line instead of sending', (await page.inputValue('#composer')) === 'řádek 1\nřádek 2');
  await page.fill('#composer', ''); await page.keyboard.press('ArrowUp');
  check('ArrowUp on an empty composer recalls the last message', (await page.inputValue('#composer')) === 'Kde jsme?');
  await page.fill('#composer', '@Q1');
  check('@ lists elements of the current artifact', await page.isVisible('.mention'), (await page.textContent('.mention')).slice(0, 60));
  await page.keyboard.press('Enter');
  check('choosing an element makes a reference chip', await page.isVisible('.refchip'), await page.textContent('.refchip'));
  await page.context().close();
}
{
  const page = await open('fast=1&s=M', 1440, 900);
  const ret = await page.textContent('.ret');
  check('return opens on the summary: changed, finished, attention, next', ['Co se změnilo', 'Co doběhlo', 'Co potřebuje pozornost', 'Doporučený další krok'].every((x) => ret.includes(x)));
  await page.screenshot({ path: `${OUT}/return-1440.png` });
  await page.setViewportSize({ width: 1600, height: 1000 }); await page.waitForTimeout(200);
  await page.screenshot({ path: `${OUT}/10-return-1600.png` });
  check('long history loads older messages on request', await page.isVisible('text=Načíst starší zprávy'));
  const n0 = await page.$$eval('.conv__scroll [data-msg]', (x) => x.length);
  await page.click('text=Načíst starší zprávy'); await page.waitForTimeout(150);
  const n1 = await page.$$eval('.conv__scroll [data-msg]', (x) => x.length);
  check('older messages are added above', n1 > n0, n0 + ' → ' + n1);
  await page.hover('.conv__scroll'); await page.mouse.wheel(0, -600); await page.waitForTimeout(200);
  check('scrolling up shows return-to-latest', await page.isVisible('.conv__latest'));
  check('historical answers are marked with their revision', (await page.$$('.histnote')).length > 0, (await page.$$('.histnote')).length + ' marks');
  await page.click('.conv__latest'); await page.waitForTimeout(700);
  check('return-to-latest scrolls to the end', await page.evaluate(() => { const e = document.querySelector('.conv__scroll'); return e.scrollHeight - e.scrollTop - e.clientHeight < 30; }));
  await page.context().close();
}

// ---------------------------------------------------------------- 9 keyboard navigation and focus
{
  const page = await open('fast=1&s=G&auto=0', 1440, 900);
  await page.locator('.nav__stage').first().focus();
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
  const f = await page.evaluate(() => document.activeElement.textContent);
  await page.keyboard.press('Enter');
  check('arrow keys move along the navigator, Enter opens', f.includes('Dotazník') && (await page.textContent('.arthead__title')) === 'Dotazník', f);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
  check('focused control has a visible outline', outline !== 'none', outline);
  await page.click('.nav__more .btn');
  check('lifecycle overview lists all 11 stages with dependencies', (await page.$$('.life__st')).length === 11 && (await page.textContent('.life__deps')).includes('Analýza čte'));
  await page.keyboard.press('Escape');
  await page.context().close();
}

// ---------------------------------------------------------------- 10 values, ranks, units, disclosure
{
  const page = await open('fast=1&s=K&auto=0', 1440, 900);
  await page.click('.nav__stage:has-text("Výsledky")');
  const res = await page.textContent('.artbody');
  check('results: Fio 6,8 z 10 [6,5; 7,1], 4. ze 7', res.includes('6,8 z 10') && res.includes('[6,5; 7,1]') && res.includes('4. ze 7'));
  check('results: Raiffeisenbank suppressed with reason', res.includes('Potlačeno · Kish n 27 < 30'));
  await page.click('.nav__stage:has-text("Sociomapa")');
  const order = await page.$$eval('.objlist .objbtn .grow', (x) => x.map((e) => e.textContent));
  check('Sociomap list ranks Fio 4th by height', order.indexOf('Fio banka') === 3, order.join(' > '));
  await page.click('.nav__stage:has-text("Analýza")');
  check('analysis ranks Fio 4th of 7', (await page.textContent('[data-aia="analysis.finding.F1"]')).includes('4. místo ze 7'));
  await page.click('.nav__stage:has-text("Zpráva")');
  const rep = await page.textContent('.doc');
  check('report: scale values never as percent', !/\d,\d\s?%/.test(rep) && rep.includes('6,8 z 10'));
  check('report figure says values are not percentages', rep.includes('Hodnoty nejsou procenta'));
  check('report claims no calibrated population', !/kalibrov/i.test(rep) && rep.includes('Populace nebyla načtena'));
  check('synthetic disclosure in report head and footer', rep.includes('Fiktivní data.') && (await page.textContent('.doc__foot')).includes('Fiktivní data'));
  await page.context().close();
}

// ---------------------------------------------------------------- 11 display filters preserve the frozen map
{
  const page = await open('fast=1&s=H', 1440, 900);
  await idle(page);
  await page.keyboard.press('Escape');
  const pos0 = await page.$$eval('[data-aia^="sociomap.object."]', (x) => x.map((e) => e.getAttribute('transform')).join('|'));
  const stress0 = await page.textContent('.mapside');
  const links0 = (await page.$$('[data-aia^="sociomap.pair."]')).length;
  await page.click('label:has-text("Skrýt slabé vztahy") input');
  const pos1 = await page.$$eval('[data-aia^="sociomap.object."]', (x) => x.map((e) => e.getAttribute('transform')).join('|'));
  check('hiding weak relations keeps every position', pos0 === pos1);
  check('the active filter is visible and says computation is unchanged', (await page.textContent('.filterbar')).includes('Výpočet'));
  check('fit and heights unchanged by the filter', stress0 === (await page.textContent('.mapside')));
  check('weak links leave the drawing only', (await page.$$('[data-aia^="sociomap.pair."]')).length <= links0);
  const s = await st(page);
  check('filter recorded as a view command, artifact untouched', s.log.some((l) => l.cmd.startsWith('view.filter sociomapHideWeak')) && !(s.accepted.sociomap ?? []).length);
  await page.click('.objbtn:has-text("Fio banka")');
  await page.click('.insp .listbtn:has-text("Air Bank")');
  await page.setViewportSize({ width: 1600, height: 1000 }); await page.waitForTimeout(150);
  await page.screenshot({ path: `${OUT}/06-sociomap-1600.png` });
  await page.context().close();
}

// ---------------------------------------------------------------- 12 map-context research, methodology refusal
{
  const page = await open('fast=1&s=I', 1440, 900);
  await idle(page);
  const s = await st(page);
  check('interpretation research attaches context to the pair', (s.evidenceAttached['pair.fio~air'] ?? []).includes('S4') && await page.isVisible('[data-aia="sociomap.context.S4"]'));
  check('map computation untouched by research', !(s.accepted.sociomap ?? []).length);
  await page.context().close();
}
{
  const page = await open('fast=1&s=X6', 1440, 900);
  await idle(page);
  await page.click('.dec .opt:has-text("Vyřadit z výpočtu")');
  await page.click('.dec button:has-text("Rozhodnout")');
  await idle(page);
  const s = await st(page);
  check('removing weak relations from computation is refused and routed to methodology', s.log.some((l) => l.cmd.startsWith('methodology.change') && !l.ok));
  await page.context().close();
}

// ---------------------------------------------------------------- 13 fieldwork, exceptions
{
  const page = await open('s=F', 1440, 900);
  await idle(page, 20000);
  await page.click('.dec button:has-text("Rozhodnout")');
  await page.waitForTimeout(3500);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.screenshot({ path: `${OUT}/04-fieldwork-1600.png` });
  await page.evaluate(async () => { (await import('/src/app/store.ts')).setFast(true); });
  const t0 = Date.now(); while (Date.now() - t0 < 30000) { const s = await st(page); if (s.run.status === 'completed' && !s.busy) break; const d = s.decisions.find((x) => x.kind === 'data' && x.status === 'open'); if (d) { await page.click('.dec:not(.is-decided) button:has-text("Rozhodnout")'); } await page.waitForTimeout(300); }
  const s = await st(page);
  check('run completes over the frozen revision', s.run.status === 'completed' && s.run.revision === 16, s.run.status);
  check('provider wait recorded and recovered', s.run.waits >= 1);
  check('constant responders asked about, replacement not offered', s.decisions.some((d) => d.kind === 'data') && (await page.$$('.opt[disabled]')).length >= 1);
  await page.context().close();
}
{
  const page = await open('fast=1&s=X1', 1440, 900);
  await idle(page); await page.click('.dec button:has-text("Rozhodnout")');
  const t0 = Date.now(); let saw = false; while (Date.now() - t0 < 15000) { const s = await st(page); if (s.run.status === 'awaiting_budget') { saw = true; break; } await page.waitForTimeout(150); }
  check('budget limit parks the run awaiting your decision', saw);
  const limit0 = (await st(page)).budget.studyLimit;
  await page.click('.nav__stage:has-text("Sběr dat")');
  await page.click('.artbody button:has-text("Navýšit limit o 10 USD")');
  const sl = await st(page);
  check('lifting from the artifact answers the open budget decision once', sl.budget.studyLimit === limit0 + 10 && !sl.decisions.some((d) => d.kind === 'budget' && d.status === 'open'), 'limit ' + limit0 + ' → ' + sl.budget.studyLimit);
  const t1 = Date.now(); while (Date.now() - t1 < 15000) { const s = await st(page); if (s.run.status === 'completed') break; const d = s.decisions.find((x) => x.kind === 'data' && x.status === 'open'); if (d) await page.click('.dec:not(.is-decided) button:has-text("Rozhodnout")'); await page.waitForTimeout(200); }
  check('lifting the budget resumes the run', (await st(page)).run.status === 'completed');
  await page.context().close();
}
{
  const page = await open('fast=1&s=X3', 1440, 900);
  await idle(page); await page.click('.dec button:has-text("Rozhodnout")');
  const t0 = Date.now(); while (Date.now() - t0 < 15000) { if (await page.isVisible('text=Zkusit krok znovu')) break; await page.waitForTimeout(150); }
  check('provider failure parks the step with a retry for the person', await page.isVisible('text=Zkusit krok znovu'));
  await page.click('text=Zkusit krok znovu');
  const sr = await st(page);
  check('retry continues the same operation: the Lead stays busy', sr.busy === true || sr.run.status === 'completed', 'busy ' + sr.busy + ', run ' + sr.run.status);
  const t1 = Date.now(); while (Date.now() - t1 < 15000) { const s = await st(page); if (s.run.status === 'completed') break; const d = s.decisions.find((x) => x.kind === 'data' && x.status === 'open'); if (d) await page.click('.dec:not(.is-decided) button:has-text("Rozhodnout")'); await page.waitForTimeout(200); }
  check('the run continues after the retry', (await st(page)).run.status === 'completed');
  await page.context().close();
}
{
  const page = await open('fast=1&s=X4', 1440, 900);
  check('failed analysis validation is shown as needing repair', (await page.textContent('.artbody')).includes('neprošlo kontrolou'));
  await page.click('text=Nové kolo nad stejnými daty'); await idle(page);
  check('a new round fixes the module', !(await st(page)).failures.analysisValidation);
  await page.context().close();
}
{
  const page = await open('fast=1&s=X7', 1440, 900);
  await idle(page);
  const s = await st(page);
  check('client report for a fictional run refused with reason', s.log.some((l) => l.cmd === 'report.client' && !l.ok));
  await page.context().close();
}

// ---------------------------------------------------------------- 14 PM continue; report edits; approval
{
  const page = await open('fast=1&s=L', 1440, 900);
  await idle(page, 30000);
  const s = await st(page);
  check('continue stops at decisions that belong to you', !!s.pmPaused && s.proposals.filter((p) => p.status === 'pending').length === 2, s.pmPaused);
  check('nothing was accepted by the Lead', s.revision === 14);
  await page.context().close();
}
{
  const page = await open('fast=1&s=K', 1440, 900);
  await idle(page);
  check('report edit appears as tracked changes with references kept', (await page.$$('.doc .chg')).length === 2 && (await page.$$('.doc .srcchip')).length >= 5);
  await page.setViewportSize({ width: 1600, height: 1000 }); await page.waitForTimeout(150);
  await page.screenshot({ path: `${OUT}/08-report-1600.png` });
  check('approval waits while changes are pending', await page.isDisabled('.docbar button:has-text("Schválit interně")'));
  {
    const w = await open('fast=1&s=G&auto=0');
    await w.click('.nav__stage:has-text("Zpráva")');
    await w.hover('[data-aia="report.r3.P5"]');
    await w.click('[data-aia="report.r3.P5"] [aria-label="Posunout Odstavec P5 dolů"]');
    check('approval waits while the report has unaccepted working edits', await w.isDisabled('.docbar button:has-text("Schválit interně")'));
    const refused = await w.evaluate(async () => (await import('/src/app/commands.ts')).approveReport('ui'));
    check('the approve command refuses a report with a working copy', refused.ok === false && !(await st(w)).reportState.reviewed, refused.reason);
    await w.context().close();
  }
  await page.click('.artbar--you .btn--primary');
  const s = await st(page);
  check('accepting report wording advances the draft, not the study revision', s.reportState.draft === 2 && s.revision === 16);
  await page.click('.docbar button:has-text("Schválit interně")');
  check('a person approves the report internally', (await st(page)).reportState.reviewed && (await page.textContent('.doc__foot')).includes('APPROVED_INTERNAL'));
  const fresh = await open('fast=1&s=G&auto=0');
  await fresh.click('.nav__stage:has-text("Zpráva")');
  await fresh.fill('#composer', 'Dej zjištění o mladších zákaznících na začátek'); await fresh.keyboard.press('Enter'); await idle(fresh);
  check('"younger first" is answered honestly (blocked claim), alternative proposed', (await st(fresh)).messages.some((m) => (m.blocks?.[0]?.x ?? '').includes('nemůže')));
  await fresh.fill('#composer', 'Nepřehání věta 1.3 evidenci?'); await fresh.keyboard.press('Enter'); await idle(fresh);
  check('overstatement check proposes a correction', (await st(fresh)).proposals.some((p) => p.title.startsWith('Oprava')));
  await fresh.fill('#composer', 'Odkud je číslo 6,8?'); await fresh.keyboard.press('Enter'); await idle(fresh);
  check('"where did this number come from" opens its chain', (await fresh.textContent('.insp')).includes('Odkud číslo je'));
  await fresh.context().close();
  await page.context().close();
}

// ---------------------------------------------------------------- 15 labels, entry view, 1600 shots
{
  const page = await open('fast=1&s=G&auto=0', 1440, 900);
  let caps = 0;
  for (const name of ['Zadání', 'Cíl. skupina', 'Dimenze', 'Sběr dat', 'Výsledky', 'Analýza', 'Zpráva']) { await page.click(`.nav__stage:has-text("${name}")`); caps += (await page.$$('.capnote')).length; }
  check('proposed / unavailable / simulated capabilities are labelled in the artifacts', caps >= 7, caps + ' labels');
  await page.click('.shead__home');
  check('Client → Study entry shows stage, attention and latest activity', (await page.textContent('.studytable')).includes('Poslední činnost'));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.screenshot({ path: `${OUT}/00-entry-1600.png` });
  await page.click('.studyrow:has-text("Mladí zákazníci")');
  check('opening the study returns to the workbench', await page.isVisible('.split'));
  await page.context().close();
}
for (const [id, file, stage] of [['A', '01-opening', null], ['G', '05-results', null], ['J', '07-analysis', null]]) {
  const page = await open('fast=1&s=' + id, 1600, 1000);
  await idle(page);
  if (stage) await page.click(`.nav__stage:has-text("${stage}")`);
  await page.waitForTimeout(200);
  await page.screenshot({ path: `${OUT}/${file}-1600.png` });
  await page.context().close();
}

check('no page errors in any run', errors.length === 0, errors.slice(0, 5).join(' | '));
writeFileSync(`${OUT}/results.json`, JSON.stringify({ when: new Date().toISOString(), results, errors }, null, 2));
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);
