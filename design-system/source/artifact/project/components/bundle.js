/* @ds-bundle: {"format":4,"namespace":"AIA","components":[{"name":"StatusChip"},{"name":"StatusGlyph"},{"name":"EvidenceMark"},{"name":"Value"},{"name":"EvidenceLegend"},{"name":"Money"},{"name":"Button"},{"name":"Kbd"},{"name":"Icon"},{"name":"Mark"},{"name":"Wordmark"},{"name":"Lattice"},{"name":"ScopeBar"},{"name":"ClientMonogram"},{"name":"StageRail"},{"name":"RunTimeline"},{"name":"ImpactPreview"},{"name":"BudgetMeter"},{"name":"ParkAndAsk"},{"name":"ProviderChoice"},{"name":"RecoveryDecision"},{"name":"UsageLedger"},{"name":"ApprovalPanel"},{"name":"RevisionBanner"},{"name":"RevisionHistory"},{"name":"HeadlineAnswer"},{"name":"GradedBars"},{"name":"Sociomap"},{"name":"ReportCover"},{"name":"ReportPage"}]} */
(function(){"use strict";
var React = window.React;
var h = React.createElement;
var F = React.Fragment;

/* ------------------------------------------------------------------ *
 * Copy. Mirrors apps/web/src/i18n/cs.ts — components never hardcode text.
 * ------------------------------------------------------------------ */
var cs = {
  status: {
    stage: {
      NOT_STARTED: "Nezahájeno", READY: "Připraveno", RUNNING: "Běží",
      WAITING_USER: "Čeká na vás", WAITING_CREDITS: "Čeká na kredity", WAITING_CAPACITY: "Čeká na kapacitu",
      DONE: "Hotovo", DONE_WITH_WARNINGS: "Hotovo s výhradami", INVALIDATED: "Zneplatněno", FAILED: "Selhalo"
    },
    run: {
      PENDING: "Ve frontě", RUNNING: "Běží", AWAITING_GATE: "Čeká na schválení", AWAITING_BUDGET: "Čeká na rozpočet",
      WAITING_PROVIDER: "Čeká na poskytovatele", WAITING_CAPACITY: "Čeká na kapacitu", RECOVERY_REQUIRED: "Vyžaduje rozhodnutí",
      COMPLETED: "Dokončeno", FAILED: "Selhalo", CANCELLED: "Zrušeno"
    },
    step: {
      BLOCKED: "Čeká na předchozí krok", RUNNABLE: "Připraveno ke spuštění", RUNNING: "Běží", AWAITING_GATE: "Čeká na schválení",
      AWAITING_BUDGET: "Čeká na rozpočet", WAITING_PROVIDER: "Čeká na poskytovatele", WAITING_CAPACITY: "Čeká na kapacitu",
      RECOVERY_REQUIRED: "Vyžaduje rozhodnutí", SUCCEEDED: "Dokončeno", FAILED: "Selhalo", CANCELLED: "Zrušeno", SKIPPED: "Přeskočeno"
    },
    attempt: {
      PENDING: "Čeká na pracovníka", CLAIMED: "Převzato", EXECUTING: "Provádí se", SUCCEEDED: "Úspěch",
      FAILED: "Selhání", EXPIRED: "Vypršel pronájem", ABANDONED: "Opuštěno"
    },
    reservation: { RESERVED: "Rezervováno", SETTLED: "Vyúčtováno", RELEASED: "Uvolněno", SETTLED_UNCERTAIN: "Nejisté vyúčtování" },
    study: { DRAFT: "Koncept", ACTIVE: "Aktivní", IN_REVIEW: "V revizi", DELIVERED: "Předáno", ARCHIVED: "Archivováno", CANCELLED: "Zrušeno" },
    client: { ACTIVE: "Aktivní", DORMANT: "Neaktivní", ARCHIVED: "Archivováno" },
    project: { DRAFT: "Koncept", READY_TO_CONTINUE: "Připraveno pokračovat", RUNNING: "Běží", WAITING: "Čeká", COMPLETED: "Dokončeno", FAILED: "Selhalo", ARCHIVED: "Archivováno", TRASHED: "V koši" },
    failure: {
      TRANSPORT: "Síťová chyba", PROVIDER_CAPACITY: "Přetížený poskytovatel", TRANSIENT: "Přechodná chyba", QUOTA: "Vyčerpaná kvóta",
      BUDGET_EXCEEDED: "Překročený rozpočet", APPROVAL_REQUIRED: "Vyžaduje schválení", AUTHENTICATION: "Selhalo ověření",
      PERMISSION: "Chybí oprávnění", MISSING_CONFIGURATION: "Chybí konfigurace", MODEL_UNAVAILABLE: "Model nedostupný",
      SCHEMA_VIOLATION: "Neplatná struktura výstupu", MAX_TURNS: "Vyčerpán počet kroků", SDK_OUTDATED: "Zastaralé SDK",
      CANCELLED: "Zrušeno", UNKNOWN: "Neznámá příčina"
    }
  },
  tone: {
    running: "Stroj pracuje — od vás nic nepotřebuje",
    you: "Zaparkováno — čeká na vás. Bez vás se nepohne.",
    world: "Zaparkováno — čeká na svět (kvóta, kapacita). Můžete zasáhnout, nemusíte.",
    fault: "Skončilo chybou — potřebuje diagnózu",
    recovery: "Placené volání mohlo být účtováno a výsledek neznáme — rozhodnutí, ne opakování",
    done: "Hotovo", "done-warn": "Hotovo, s výhradami k přečtení", ready: "Připraveno", inert: "Ještě nezačalo",
    invalid: "Zneplatněno úpravou — vyžaduje nový běh", cancelled: "Zrušeno", skipped: "Přeskočeno", blocked: "Čeká na předchozí krok"
  },
  role: { VIEWER: "Čtenář", REVIEWER: "Recenzent", RESEARCHER: "Výzkumník", LEAD: "Vedoucí studie" },
  orgRole: { OWNER: "Vlastník", ADMIN: "Správce", MEMBER: "Člen" },
  permission: {
    VIEW_STUDY: "Zobrazit studii", VIEW_RESULTS: "Zobrazit výsledky", VIEW_COSTS: "Zobrazit náklady", EDIT_STUDY: "Upravovat studii",
    RUN_WORKFLOW: "Spouštět běhy", CANCEL_WORKFLOW: "Rušit běhy", UPLOAD_DATA: "Nahrávat data", APPROVE_GATE: "Schvalovat brány",
    APPROVE_BUDGET: "Schvalovat výdaje", SIGN_OFF_DELIVERABLE: "Podepsat výstup", EXPORT_DELIVERABLE: "Exportovat výstup",
    MANAGE_STUDY_ACCESS: "Spravovat přístupy", MANAGE_STUDY_BUDGET: "Spravovat rozpočet", DELETE_STUDY: "Smazat studii"
  },
  provider: { claude_code_subscription: "Claude Code (předplatné)", anthropic: "Claude API", openai: "OpenAI API" },
  providerPolicy: {
    CLAUDE_CODE_ONLY: "Pouze Claude Code", CLAUDE_API_ONLY: "Pouze Claude API", OPENAI_ONLY: "Pouze OpenAI",
    CLAUDE_CODE_THEN_API: "Claude Code, poté Claude API (jen ručním přepnutím)"
  },
  modelRole: { research_model: "Rešerše", design_model: "Návrh", respondent_model: "Respondenti", analysis_model: "Analýza", report_polish_model: "Úprava reportu" },
  evidence: {
    MEASURED_JOINT: { name: "Měřeno", long: "Měřeno společně na téže osobě", short: "měř." },
    CALIBRATED_CORE: { name: "Kalibrované jádro", long: "Kalibrované jádro populace vůči externím zdrojům", short: "kal." },
    MODELED_BEHAVIOR_PRIOR: { name: "Modelováno", long: "Modelováno z behaviorálního prioru — nejde o měření", short: "mod." },
    EXTERNAL_HOLDOUT_PENDING: { name: "Validace čeká", long: "Externí prediktivní validace dosud neproběhla", short: "neval." },
    UNKNOWN: { name: "Role neznámá", long: "Evidenční role nedorazila nebo ji systém nezná — nečtěte jako měření", short: "?" },
    CROSS_BLOCK: { name: "Mezi bloky", long: "Vztah mezi bloky — nejde o pravdu o téže osobě" }
  },
  nulls: {
    zero: "Nula", zeroLong: "Podívali jsme se — odpověď je nula.",
    na: "chybí", naLong: "Nezjištěno — nikdy jsme se nepodívali, nebo odpověď nedorazila.",
    suppressed: "potlačeno", suppressedLong: "Máme, ale nezobrazujeme",
    suppressedSample: "vzorek < 30", suppressedPermission: "bez oprávnění",
    loading: "Načítá se", value: "Hodnota", valueLong: "Změřili nebo namodelovali jsme."
  },
  lifecycle: { research: "Výzkum", simulation: "Simulace" },
  stages: {
    research: ["Zadání", "Deep Research", "Výzkumný design", "Dotazník", "Cílová skupina", "Dimenze", "Výběrový plán", "Respondenti", "Agregace", "Validace", "Analýza", "Report", "Předání"],
    simulation: ["Kontext", "Deep Research", "Baseline", "Kontrakt scénáře", "Cílová skupina", "Dimenze", "Varianty", "Simulované světy", "Zmrazené výsledky", "Srovnání", "Interpretace", "Report", "Předání"]
  },
  scope: {
    above: "Napříč klienty", aboveLong: "Jste nad hranicí klienta — tato obrazovka ukazuje více klientů",
    readOnly: "Pouze ke čtení", delivered: "Předáno", archived: "Archivováno", revision: "revize", yourRole: "Vaše role"
  },
  budget: {
    spent: "Utraceno", reserved: "Rezervováno", uncertain: "Nejisté", remaining: "Zbývá", limit: "Rozpočet studie",
    spentLong: "Vyúčtovaná volání", reservedLong: "Probíhající volání, ještě nevyúčtovaná",
    uncertainLong: "Volání mohlo být účtováno; výsledek neznáme. Počítáno jako utracené.", remainingLong: "Rozpočet − utraceno − rezervováno − nejisté",
    over: "překročí rozpočet o"
  },
  park: {
    title: "Schválit výdaj z rozpočtu studie?", what: "Na co", model: "Model a poskytovatel", amount: "Rezervace",
    against: "Proti rozpočtu", after: "Po schválení zbude", decline: "Když zamítnete", declineText: "Fáze zůstane zaparkovaná ve stavu „Čeká na rozpočet“. Nic se neztratí: hotové fáze a artefakty zůstávají platné.",
    approve: "Schválit výdaj", reject: "Zamítnout", askLead: "Požádat vedoucí studie", noPermission: "Výdaj nad rozpočet schvaluje vedoucí studie. Vy ho schválit nemůžete — můžete ale požádat."
  },
  provider_ui: {
    title: "Poskytovatel nemůže pokračovat", wait: "Počkat", waitText: "Bez nákladů. Běh se sám obnoví.",
    switch: "Přepnout na", switchText: "Placené. Změní provenienci: další kroky ponesou tohoto poskytovatele. Hotové kroky zůstanou beze změny.",
    notAllowed: "Politika studie přepnutí nepovoluje", policy: "Politika poskytovatele"
  },
  impact: {
    title: "Dopad úpravy — před uložením", editing: "Upravujete", keep: "Zůstane platné", reopen: "Znovu se otevře", root: "Začátek dopadu",
    presentation: "Jen prezentační změna — výsledky se nepřepočítají", cost: "Odhad nákladů nového běhu", time: "Odhad času",
    costNa: "Odhad zatím backend neposkytuje", artifacts: "artefaktů zůstane", commit: "Uložit jako novou revizi", cancel: "Zahodit úpravu",
    nothing: "Tato změna nic nezneplatní (poskytovatel a model jsou bez dopadu)."
  },
  approval: {
    title: "Schválení výstupu", what: "Schvalujete", producer: "Vytvořil(a)", evidence: "Důkazy", attest: "Svým podpisem potvrzujete",
    attestText: "Report jsem přečetl(a). Každé tvrzení odpovídá důkazům v příloze; modelované hodnoty jsou jako modelované označeny.",
    approve: "Schválit a podepsat", ret: "Vrátit s komentářem", sodTitle: "Tento výstup nemůžete schválit — vytvořil(a) jste ho vy",
    sodText: "Nezávislá kontrola je výchozí politika. Samoschválení tu není povoleno", sodWho: "Schválit mohou", audit: "Auditní stopa",
    selfAllowed: "Samoschválení povoleno politikou", source: { default: "výchozí nastavení", organization: "organizace", client: "klienta", study: "studie" }
  },
  revision: { superseded: "Díváte se na nahrazenou revizi", current: "Aktuální", open: "Otevřít aktuální revizi", compare: "Porovnat" },
  run: { elapsed: "Běží", heartbeat: "poslední signál", current: "Právě", waitingOn: "Čeká na", done: "hotovo", steps: "kroků", attempt: "pokus" },
  actions: { approve: "Schválit", resume: "Pokračovat", open: "Otevřít", export: "Exportovat", reset: "Obnovit originál", edit: "Upravit", retry: "Spustit znovu", decide: "Rozhodnout" }
};

/* ------------------------------------------------------------------ *
 * Formatting — Czech conventions, tabular, unit always explicit.
 * ------------------------------------------------------------------ */
var nf = {};
function fmtNum(v, digits) {
  var k = String(digits == null ? -1 : digits);
  if (!nf[k]) nf[k] = new Intl.NumberFormat("cs-CZ", digits == null ? { maximumFractionDigits: 2 } : { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return nf[k].format(v);
}
function fmtMoney(v, currency, digits) { return fmtNum(v, digits == null ? 2 : digits) + " " + (currency || "USD"); }
function fmtPct(v, digits) { return fmtNum(v, digits == null ? 1 : digits) + " %"; }
function fmtDuration(sec) {
  var hh = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60), ss = Math.floor(sec % 60);
  if (hh) return hh + " h " + mm + " min";
  if (mm) return mm + " min " + ss + " s";
  return ss + " s";
}
function cx() { return Array.prototype.filter.call(arguments, Boolean).join(" "); }

/* ------------------------------------------------------------------ *
 * Client accent: a persisted slot 1–6; fallback deterministic FNV-1a over the id.
 * The accent is a second channel; the name and monogram are primary.
 * ------------------------------------------------------------------ */
var CLIENT_ACCENTS = 6;
function clientAccentIndex(clientId) {
  var hsh = 0x811c9dc5;
  for (var i = 0; i < clientId.length; i++) { hsh ^= clientId.charCodeAt(i); hsh = Math.imul(hsh, 0x01000193) >>> 0; }
  return (hsh % CLIENT_ACCENTS) + 1;
}
/* Preferred: the server's persisted accent slot (assigned least-used at client creation,
 * immutable after). The hash is only the fallback — with 5 clients it already collides. */
function clientAccentVar(clientId, slot) { return "var(--client-" + (slot || clientAccentIndex(clientId)) + ")"; }
/* ------------------------------------------------------------------ *
 * Icons: 24-unit grid, 1.5 stroke, square caps, mitred joins.
 * The same path data is exported as SVG files under assets/Icons/.
 * ------------------------------------------------------------------ */
var ICONS = {
  stage: ["M2 12h5", "M17 12h5", "c:12,12,5"],
  revision: ["M8 3h11v15H8z", "M5 6v15h11"],
  fingerprint: ["M9.5 3.5 7.5 20.5", "M16.5 3.5l-2 17", "M4 8.5h16.5", "M3.5 15.5H20"],
  artifact: ["M6 3h8.5L19 7.5V21H6z", "M14 3v5h5"],
  gate: ["M5 3v18", "M19 3v18", "M5 8h14", "M5 12h14", "M3 21h4", "M17 21h4"],
  reservation: ["M6 5H3v14h3", "M18 5h3v14h-3", "c:12,12,4.5", "M12 9.5v5"],
  evidence: ["M4 4h7v7H4z", "M13 4h7v7h-7z", "M4 13h7v7H4z", "M13 13h7v7h-7z", "f:M4 4h7v7H4z", "f:M13 4h7v7h-7z"],
  parked: ["M4 4h16v16H4z", "M10 8.5v7", "M14 8.5v7"],
  waiting: ["M4 4h16v16H4z", "M10 8.5v7", "M14 8.5v7", "M2 22 22 2"],
  recovery: ["M12 2.5 21.5 12 12 21.5 2.5 12z", "M12 7.5v6", "M12 15.8v1.5"],
  ledger: ["M5 3h14v18H5z", "M8 7.5h8", "M8 11h8", "M8 14.5h8", "M8 18h5"],
  budget: ["M2.5 9.5h19v5h-19z", "M10 9.5v5", "M14 9.5v5", "M2.5 18h19"],
  provider: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M7.5 7h1", "M7.5 17h1"],
  client: ["M4 21V7l8-4 8 4v14", "M2.5 21h19", "M10 21v-6h4v6"],
  study: ["M4 5h6l2 2h8v13H4z", "M4 10h16"],
  suppressed: ["M6 11h12v10H6z", "M8.5 11V7.5a3.5 3.5 0 0 1 7 0V11"],
  missing: ["M4 4h16v16H4z", "M4 12h4", "M10 12h4", "M16 12h4"],
  whatif: ["M5 21V3", "M5 13c5 0 7-5 14-6", "M16 4.5 19 7l-2.5 3"],
  view: ["M12 3 21 8 12 13 3 8z", "M3 12.5 12 17.5l9-5", "M3 16.5 12 21.5l9-5"],
  export: ["M12 3v12", "M7.5 7.5 12 3l4.5 4.5", "M4 14v7h16v-7"],
  signoff: ["M3 17c2-4 4-6 5-3s2.5 5 4 1.5 3-4 4-1.5", "M14 21h7"],
  keyboard: ["M2.5 6h19v12h-19z", "M6 10h1", "M9.5 10h1", "M13 10h1", "M16.5 10h1", "M7 14h10"],
  search: ["c:10.5,10.5,6.5", "M15.5 15.5 21 21"],
  population: ["c:6,6,1.6", "c:12,6,1.6", "c:18,6,1.6", "c:6,12,1.6", "c:12,12,1.6", "c:18,12,1.6", "c:6,18,1.6", "c:12,18,1.6", "c:18,18,1.6"],
  portfolio: ["M3 4h8v7H3z", "M13 4h8v7h-8z", "M3 13h8v7H3z", "M13 13h8v7h-8z"],
  settings: ["M4 7h10", "M18 7h2", "c:16,7,2", "M4 17h2", "M10 17h10", "c:8,17,2"],
  library: ["M4 4h4v16H4z", "M10 4h4v16h-4z", "M16.5 4.5l3.5 1-4 15-3.5-1z"],
  map: ["c:6,7,2", "c:17,6,2", "c:9,17,2", "c:18,16,2", "M8 8l7-1.5", "M7 9l1.5 6", "M11 17h5"],
  check: ["M4.5 12.5 9.5 17.5 19.5 6.5"],
  close: ["M5 5l14 14", "M19 5 5 19"],
  chevron: ["M9 5l7 7-7 7"],
  clock: ["c:12,12,8.5", "M12 7.5V12l3 2"]
};
function Icon(p) {
  var size = p.size || 16, name = p.name, parts = ICONS[name] || [];
  var kids = parts.map(function (d, i) {
    if (d.indexOf("c:") === 0) { var a = d.slice(2).split(","); return h("circle", { key: i, cx: a[0], cy: a[1], r: a[2], fill: name === "population" ? "currentColor" : "none" }); }
    if (d.indexOf("f:") === 0) return h("path", { key: i, d: d.slice(2), fill: "currentColor", stroke: "none" });
    return h("path", { key: i, d: d });
  });
  return h("svg", { className: cx("aia-icon", p.className), width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    strokeWidth: 1.5, strokeLinecap: "square", strokeLinejoin: "miter", "aria-hidden": p.label ? undefined : "true", role: p.label ? "img" : undefined, "aria-label": p.label }, kids);
}

/* ------------------------------------------------------------------ *
 * Status glyphs. Shape carries the state; colour only reinforces it.
 *   circle family  = machine states (running, ready, done, failed)
 *   square + bars  = parked (solid = on you, hollow + slash = on the world)
 *   diamond        = recovery required (a decision about money)
 *   dashed circle  = inert (not started / blocked / cancelled / skipped / invalidated)
 * ------------------------------------------------------------------ */
function StatusGlyph(p) {
  var s = p.size || 14, t = p.tone, k = [];
  var sw = 1.6;
  switch (t) {
    case "running":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6.2, fill: "none", stroke: "currentColor", strokeWidth: sw }), h("circle", { key: 2, cx: 8, cy: 8, r: 3.2, fill: "currentColor" })]; break;
    case "you":
      k = [h("path", { key: 1, d: "M1.5 1.5h13v13h-13z M5 4.5h2v7h-2z M9 4.5h2v7h-2z", fill: "currentColor", fillRule: "evenodd" })]; break; /* bars are holes: the ground shows through */
    case "world":
      k = [h("rect", { key: 1, x: 2, y: 2, width: 12, height: 12, rx: 1, fill: "none", stroke: "currentColor", strokeWidth: sw }), h("path", { key: 2, d: "M6.3 5.5v5M9.7 5.5v5", stroke: "currentColor", strokeWidth: sw })]; break;
    case "fault":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6.8, fill: "currentColor" }), h("path", { key: 2, d: "M5.4 5.4l5.2 5.2M10.6 5.4l-5.2 5.2", stroke: "var(--surface-raised)", strokeWidth: 1.8 })]; break;
    case "recovery":
      k = [h("path", { key: 1, d: "M8 0.8 15.2 8 8 15.2 0.8 8z", fill: "currentColor" }), h("path", { key: 2, d: "M8 4.2v4.6M8 10.6v1.4", stroke: "var(--status-recovery-hatch)", strokeWidth: 1.8 })]; break;
    case "done":
      k = [h("path", { key: 1, d: "M2.5 8.5l3.7 3.7 7.3-8", fill: "none", stroke: "currentColor", strokeWidth: 2 })]; break;
    case "done-warn":
      k = [h("path", { key: 1, d: "M1.5 8.5l3.5 3.5 5.5-6.2", fill: "none", stroke: "currentColor", strokeWidth: 2 }), h("path", { key: 2, d: "M12.5 9.5l3 5.3h-6z", fill: "currentColor" })]; break;
    case "ready":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6, fill: "none", stroke: "currentColor", strokeWidth: sw })]; break;
    case "blocked":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6, fill: "none", stroke: "currentColor", strokeWidth: sw, strokeDasharray: "2.2 2" }), h("path", { key: 2, d: "M5 8h6", stroke: "currentColor", strokeWidth: sw })]; break;
    case "cancelled":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6, fill: "none", stroke: "currentColor", strokeWidth: sw }), h("path", { key: 2, d: "M3.8 12.2 12.2 3.8", stroke: "currentColor", strokeWidth: sw })]; break;
    case "skipped":
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6, fill: "none", stroke: "currentColor", strokeWidth: sw, strokeDasharray: "2.2 2" }), h("path", { key: 2, d: "M5.5 8h5M8.5 6l2 2-2 2", fill: "none", stroke: "currentColor", strokeWidth: sw })]; break;
    case "invalid":
      k = [h("path", { key: 1, d: "M12.6 5.2A5.6 5.6 0 1 0 13.6 9", fill: "none", stroke: "currentColor", strokeWidth: sw, strokeDasharray: "2.2 1.6" }), h("path", { key: 2, d: "M10.5 5.3h2.6V2.6", fill: "none", stroke: "currentColor", strokeWidth: sw })]; break;
    default: /* inert */
      k = [h("circle", { key: 1, cx: 8, cy: 8, r: 6, fill: "none", stroke: "currentColor", strokeWidth: sw, strokeDasharray: "2.2 2" })];
  }
  return h("svg", { className: "aia-glyph", width: s, height: s, viewBox: "0 0 16 16", "aria-hidden": "true" }, k);
}

/* ------------------------------------------------------------------ *
 * Status maps — TOTAL over each domain enum. The domain values are
 * listed in DOMAIN_ENUMS; checkTotality() proves every map covers them.
 * In apps/web these are `satisfies Record<Enum, Appearance>` so a new
 * domain value fails `tsc --noEmit`.
 * ------------------------------------------------------------------ */
var DOMAIN_ENUMS = {
  StageStatus: ["NOT_STARTED", "READY", "RUNNING", "WAITING_USER", "WAITING_CREDITS", "WAITING_CAPACITY", "DONE", "DONE_WITH_WARNINGS", "INVALIDATED", "FAILED"],
  WorkflowRunStatus: ["PENDING", "RUNNING", "AWAITING_GATE", "AWAITING_BUDGET", "WAITING_PROVIDER", "WAITING_CAPACITY", "RECOVERY_REQUIRED", "COMPLETED", "FAILED", "CANCELLED"],
  StepRunStatus: ["BLOCKED", "RUNNABLE", "RUNNING", "AWAITING_GATE", "AWAITING_BUDGET", "WAITING_PROVIDER", "WAITING_CAPACITY", "RECOVERY_REQUIRED", "SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"],
  AttemptStatus: ["PENDING", "CLAIMED", "EXECUTING", "SUCCEEDED", "FAILED", "EXPIRED", "ABANDONED"],
  ReservationStatus: ["RESERVED", "SETTLED", "RELEASED", "SETTLED_UNCERTAIN"],
  StudyStatus: ["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED", "ARCHIVED", "CANCELLED"],
  ClientStatus: ["ACTIVE", "DORMANT", "ARCHIVED"],
  ProjectStatus: ["DRAFT", "READY_TO_CONTINUE", "RUNNING", "WAITING", "COMPLETED", "FAILED", "ARCHIVED", "TRASHED"],
  FailureClass: ["TRANSPORT", "PROVIDER_CAPACITY", "TRANSIENT", "QUOTA", "BUDGET_EXCEEDED", "APPROVAL_REQUIRED", "AUTHENTICATION", "PERMISSION", "MISSING_CONFIGURATION", "MODEL_UNAVAILABLE", "SCHEMA_VIOLATION", "MAX_TURNS", "SDK_OUTDATED", "CANCELLED", "UNKNOWN"]
};
var TONE = {
  StageStatus: { NOT_STARTED: "inert", READY: "ready", RUNNING: "running", WAITING_USER: "you", WAITING_CREDITS: "you", WAITING_CAPACITY: "world", DONE: "done", DONE_WITH_WARNINGS: "done-warn", INVALIDATED: "invalid", FAILED: "fault" },
  WorkflowRunStatus: { PENDING: "ready", RUNNING: "running", AWAITING_GATE: "you", AWAITING_BUDGET: "you", WAITING_PROVIDER: "world", WAITING_CAPACITY: "world", RECOVERY_REQUIRED: "recovery", COMPLETED: "done", FAILED: "fault", CANCELLED: "cancelled" },
  StepRunStatus: { BLOCKED: "blocked", RUNNABLE: "ready", RUNNING: "running", AWAITING_GATE: "you", AWAITING_BUDGET: "you", WAITING_PROVIDER: "world", WAITING_CAPACITY: "world", RECOVERY_REQUIRED: "recovery", SUCCEEDED: "done", FAILED: "fault", CANCELLED: "cancelled", SKIPPED: "skipped" },
  AttemptStatus: { PENDING: "ready", CLAIMED: "running", EXECUTING: "running", SUCCEEDED: "done", FAILED: "fault", EXPIRED: "fault", ABANDONED: "cancelled" },
  ReservationStatus: { RESERVED: "running", SETTLED: "done", RELEASED: "cancelled", SETTLED_UNCERTAIN: "recovery" },
  StudyStatus: { DRAFT: "inert", ACTIVE: "ready", IN_REVIEW: "you", DELIVERED: "done", ARCHIVED: "cancelled", CANCELLED: "cancelled" },
  ClientStatus: { ACTIVE: "ready", DORMANT: "inert", ARCHIVED: "cancelled" },
  ProjectStatus: { DRAFT: "inert", READY_TO_CONTINUE: "ready", RUNNING: "running", WAITING: "world", COMPLETED: "done", FAILED: "fault", ARCHIVED: "cancelled", TRASHED: "cancelled" },
  FailureClass: { TRANSPORT: "world", PROVIDER_CAPACITY: "world", TRANSIENT: "world", QUOTA: "world", BUDGET_EXCEEDED: "you", APPROVAL_REQUIRED: "you", AUTHENTICATION: "fault", PERMISSION: "fault", MISSING_CONFIGURATION: "fault", MODEL_UNAVAILABLE: "fault", SCHEMA_VIOLATION: "fault", MAX_TURNS: "fault", SDK_OUTDATED: "fault", CANCELLED: "cancelled", UNKNOWN: "fault" }
};
var LABELS = {
  StageStatus: cs.status.stage, WorkflowRunStatus: cs.status.run, StepRunStatus: cs.status.step, AttemptStatus: cs.status.attempt,
  ReservationStatus: cs.status.reservation, StudyStatus: cs.status.study, ClientStatus: cs.status.client, ProjectStatus: cs.status.project, FailureClass: cs.status.failure
};
function checkTotality() {
  var missing = [];
  Object.keys(DOMAIN_ENUMS).forEach(function (e) {
    DOMAIN_ENUMS[e].forEach(function (v) {
      if (!TONE[e] || !TONE[e][v]) missing.push(e + "." + v + " (tone)");
      if (!LABELS[e] || !LABELS[e][v]) missing.push(e + "." + v + " (label)");
    });
  });
  return missing;
}
/* An unmapped value renders as UNKNOWN (fault tone, raw value shown) — never as a neutral default. */
function appearance(kind, value) {
  var tone = TONE[kind] && TONE[kind][value];
  var label = LABELS[kind] && LABELS[kind][value];
  if (!tone || !label) return { tone: "fault", label: "Neznámý stav: " + value, unknown: true };
  return { tone: tone, label: label };
}
function StatusChip(p) {
  var a = appearance(p.kind, p.value);
  return h("span", { className: cx("aia-chip", "aia-tone-" + a.tone, p.small && "aia-chip-sm"), title: cs.tone[a.tone], "data-status": p.value },
    h(StatusGlyph, { tone: a.tone, size: p.small ? 12 : 14 }), h("span", null, p.children || a.label));
}

/* ------------------------------------------------------------------ *
 * Evidence grade. Achromatic: form, not colour, so it prints.
 *   ■ MEASURED_JOINT          solid square
 *   ▣ CALIBRATED_CORE         solid square in a frame
 *   □ MODELED_BEHAVIOR_PRIOR  hollow square + dotted underline on the value
 *   ⬚ EXTERNAL_HOLDOUT_PENDING dotted hollow square + dotted underline + tag
 *   ? UNKNOWN                 a bold "?" (no square at all) + dashed underline — never a grade
 * ------------------------------------------------------------------ */
var EVIDENCE_ROLES = ["MEASURED_JOINT", "CALIBRATED_CORE", "MODELED_BEHAVIOR_PRIOR", "EXTERNAL_HOLDOUT_PENDING"];
function evidenceRole(r) { return EVIDENCE_ROLES.indexOf(r) >= 0 ? r : "UNKNOWN"; }
function EvidenceMark(p) {
  var r = evidenceRole(p.role), s = p.size || 8, k;
  var st = { fill: "none", stroke: "var(--evidence-mark)", strokeWidth: 1.2 };
  if (r === "MEASURED_JOINT") k = [h("rect", { key: 1, x: 0, y: 0, width: 8, height: 8, fill: "var(--evidence-mark)" })];
  else if (r === "CALIBRATED_CORE") k = [h("rect", Object.assign({ key: 1, x: 0.6, y: 0.6, width: 6.8, height: 6.8 }, st)), h("rect", { key: 2, x: 2.4, y: 2.4, width: 3.2, height: 3.2, fill: "var(--evidence-mark)" })];
  else if (r === "MODELED_BEHAVIOR_PRIOR") k = [h("rect", Object.assign({ key: 1, x: 0.6, y: 0.6, width: 6.8, height: 6.8 }, st))];
  else if (r === "EXTERNAL_HOLDOUT_PENDING") k = [h("rect", Object.assign({ key: 1, x: 0.6, y: 0.6, width: 6.8, height: 6.8, strokeDasharray: "1.4 1.2" }, st))];
  else if (p.inSvg) k = [h("text", { key: 1, x: 4, y: 8, fontSize: 10, fontWeight: 700, textAnchor: "middle", fill: "var(--evidence-mark)", fontFamily: "var(--font-sans)" }, "?")];
  else return h("span", { className: "aia-ev-unknown", role: "img", "aria-label": cs.evidence[r].name }, "?");
  return h("svg", { className: "aia-ev-mark", width: s, height: s, viewBox: "0 0 8 8", role: "img", "aria-label": cs.evidence[r].name }, k);
}

/* Value — the one way a figure is rendered. Four states, never conflated:
 *   state "value" (default) · "zero" · "na" · "suppressed" · "loading"
 * `role` attaches an evidence grade; `inheritRole` suppresses the per-cell
 * mark when the column header already declares the same grade. */
function Value(p) {
  var st = p.state || (p.value === 0 ? "zero" : p.value == null ? "na" : "value");
  if (st === "na") return h("span", { className: "aia-na", title: cs.nulls.naLong }, cs.nulls.na);
  if (st === "suppressed") return h("span", { className: "aia-supp", title: cs.nulls.suppressedLong + " — " + (p.reason || cs.nulls.suppressedSample) },
    h("span", { className: "aia-supp-bar", style: { width: (p.width || 4) * 7 } }), h(Icon, { name: "suppressed", size: 12 }), h("span", { className: "aia-sr" }, cs.nulls.suppressed), p.showReason ? h("span", null, p.reason || cs.nulls.suppressedSample) : null);
  if (st === "loading") return h("span", { className: "aia-loading", style: { width: (p.width || 4) * 8 }, "aria-label": cs.nulls.loading }, "…");
  var text = p.format ? p.format(p.value) : fmtNum(p.value, p.digits);
  var r = p.role === undefined ? null : evidenceRole(p.role);
  if (!r) return h("span", { className: cx("aia-num", st === "zero" && "aia-zero") }, text);
  return h("span", { className: "aia-ev" },
    h("span", { className: cx("aia-num", "aia-ev-v-" + r) }, text),
    p.inheritRole === r ? null : h(EvidenceMark, { role: r }),
    r === "EXTERNAL_HOLDOUT_PENDING" && p.tag !== false ? h("span", { className: "aia-ev-tag" }, cs.evidence[r].short) : null);
}
function EvidenceLegend(p) {
  var roles = EVIDENCE_ROLES.concat(["UNKNOWN"]);
  return h("div", { className: cx("aia-row", p.className), style: { gap: "4px 16px" }, role: "list", "aria-label": "Legenda evidenčních rolí" },
    roles.map(function (r) {
      return h("span", { key: r, role: "listitem", className: "aia-row", style: { gap: 6 }, title: cs.evidence[r].long },
        h(Value, { value: 41.7, format: p.compact ? function () { return ""; } : function (v) { return fmtPct(v); }, role: r, tag: false }),
        h("span", { className: "aia-caption" }, cs.evidence[r].name));
    }));
}
function Money(p) {
  if (p.value == null) return h(Value, { state: "na" });
  return h("span", { className: cx("aia-num", p.className), title: p.title }, fmtMoney(p.value, p.currency, p.digits));
}
function Button(p) {
  return h("button", { type: "button", className: cx("aia-btn", p.variant && "aia-btn-" + p.variant, p.compact && "aia-btn-compact", p.className), onClick: p.onClick, "aria-keyshortcuts": p.shortcut, autoFocus: p.autoFocus },
    p.icon ? h(Icon, { name: p.icon, size: 14 }) : null, p.children, p.kbd ? h(Kbd, null, p.kbd) : null);
}
function Kbd(p) { return h("kbd", { className: "aia-kbd" }, p.children); }
/* ------------------------------------------------------------------ *
 * Identity
 * ------------------------------------------------------------------ */
var MARK_DOTS = [[2, 0], [1, 1], [3, 1], [1, 2], [2, 2], [3, 2], [0, 3], [4, 3], [0, 4], [4, 4]];
function Mark(p) {
  var s = p.size || 24, dots = [];
  for (var y = 0; y < 5; y++) for (var x = 0; x < 5; x++) {
    var on = MARK_DOTS.some(function (d) { return d[0] === x && d[1] === y; });
    dots.push(h("circle", { key: x + "-" + y, cx: 4 + x * 6, cy: 4 + y * 6, r: on ? 2.3 : 0.9, fill: on ? (x === 2 && y === 0 && !p.mono ? "var(--signal)" : "currentColor") : "currentColor", opacity: on ? 1 : 0.35 }));
  }
  return h("svg", { width: s, height: s, viewBox: "0 0 32 32", role: "img", "aria-label": "AIA" }, dots);
}
function Wordmark(p) {
  var hgt = p.height || 20;
  var col = [0, 1, 2, 3, 4].map(function (i) { return h("circle", { key: i, cx: 63, cy: 4 + i * 8, r: 3.2, fill: i === 0 && !p.mono ? "var(--signal)" : "currentColor" }); });
  return h("svg", { height: hgt, viewBox: "0 0 126 40", role: "img", "aria-label": "AIA" },
    h("path", { d: "M1 40 20 1.5 39 40", fill: "none", stroke: "currentColor", strokeWidth: 6, strokeLinejoin: "miter" }),
    [13, 20, 27].map(function (x) { return h("circle", { key: "a" + x, cx: x, cy: 28, r: 2.3, fill: "currentColor" }); }),
    col,
    h("path", { d: "M87 40 106 1.5 125 40", fill: "none", stroke: "currentColor", strokeWidth: 6, strokeLinejoin: "miter" }),
    [99, 106, 113].map(function (x) { return h("circle", { key: "b" + x, cx: x, cy: 28, r: 2.3, fill: "currentColor" }); }));
}
/* The motif: a field of discrete points that resolves into structure. Deterministic. */
function Lattice(p) {
  var w = p.cols || 32, rows = p.rows || 8, pitch = p.pitch || 8, dots = [];
  for (var y = 0; y < rows; y++) for (var x = 0; x < w; x++) {
    var n = Math.sin(x * 0.37 + y * 0.21) * Math.cos(y * 0.53 - x * 0.11);
    var d = (x / w) * 0.9 + n * 0.25;
    var r = d > 0.62 ? 1.6 : d > 0.35 ? 1.1 : 0.7;
    dots.push(h("circle", { key: x + "." + y, cx: pitch / 2 + x * pitch, cy: pitch / 2 + y * pitch, r: r, fill: "currentColor", opacity: d > 0.62 ? 0.9 : d > 0.35 ? 0.55 : 0.3 }));
  }
  return h("svg", { width: "100%", viewBox: "0 0 " + w * pitch + " " + rows * pitch, "aria-hidden": "true", style: { display: "block", color: p.color || "var(--ink-faint)" } }, dots);
}

/* ------------------------------------------------------------------ *
 * Scope chrome
 * ------------------------------------------------------------------ */
function ClientMonogram(p) {
  if (p.above) return h("span", { className: "aia-mono-tile is-above", title: cs.scope.aboveLong }, h(Icon, { name: "portfolio", size: 14 }));
  return h("span", { className: "aia-mono-tile", style: { background: clientAccentVar(p.clientId, p.accent) }, title: p.name }, p.code);
}
function ScopeBar(p) {
  var above = !!p.above;
  var ro = p.studyStatus === "DELIVERED" || p.studyStatus === "ARCHIVED" || p.studyStatus === "CANCELLED";
  return h("header", { className: "aia-scope", role: "banner", "aria-label": above ? cs.scope.aboveLong : "Klient " + p.client + ", studie " + p.study },
    h("div", { className: cx("aia-scope-band", above && "is-above"), style: above ? null : { background: clientAccentVar(p.clientId, p.accent) } }),
    h("div", { className: "aia-scope-bar" },
      h(Mark, { size: 20 }),
      h(ClientMonogram, { above: above, clientId: p.clientId, accent: p.accent, code: p.code, name: p.client }),
      above
        ? h("div", { className: "aia-scope-crumb" }, h("span", { className: "aia-scope-client" }, cs.scope.above), h("span", { className: "aia-caption" }, p.note || cs.scope.aboveLong))
        : h("div", { className: "aia-scope-crumb" },
            h("span", { className: "aia-scope-client" }, p.client), h("span", { className: "aia-scope-sep", "aria-hidden": "true" }, "/"),
            h("span", { style: { fontWeight: 500 } }, p.study),
            p.studyStatus ? h(StatusChip, { kind: "StudyStatus", value: p.studyStatus, small: true }) : null,
            p.revision != null ? h("span", { className: "aia-mono aia-muted" }, cs.scope.revision + " " + p.revision) : null),
      h("span", { className: "aia-scope-spacer" }),
      ro ? h("span", { className: "aia-scope-ro" }, h(Icon, { name: "suppressed", size: 12 }), cs.scope.readOnly + (p.deliveredAt ? " · " + cs.scope.delivered + " " + p.deliveredAt : "")) : null,
      p.role ? h("span", { className: "aia-caption" }, cs.scope.yourRole + ": ", h("strong", { style: { color: "var(--ink)" } }, cs.role[p.role])) : null,
      p.right || null));
}

/* ------------------------------------------------------------------ *
 * Lifecycle rail — 13 stages, both lifecycles, primary navigation.
 * stages: [{status, note?}] in pipeline order (server-computed).
 * ------------------------------------------------------------------ */
function StageRail(p) {
  var names = cs.stages[p.lifecycle || "research"];
  return h("nav", { "aria-label": "Fáze projektu — " + cs.lifecycle[p.lifecycle || "research"] },
    h("div", { className: "aia-row", style: { justifyContent: "space-between", marginBottom: 6 } },
      h("span", { className: "aia-rail-kind" }, h(Icon, { name: p.lifecycle === "simulation" ? "whatif" : "stage", size: 14 }), cs.lifecycle[p.lifecycle || "research"], h("span", { className: "aia-caption", style: { fontWeight: 400 } }, "· 13 fází")),
      p.summary ? h("span", { className: "aia-caption" }, p.summary) : null),
    h("ol", { className: cx("aia-rail", p.narrow && "is-narrow"), style: { listStyle: "none", margin: 0, padding: 0 } },
      names.map(function (n, i) {
        var s = (p.stages && p.stages[i]) || { status: "NOT_STARTED" };
        var a = appearance("StageStatus", s.status);
        return h("li", { key: i, style: { display: "contents" } },
          h("button", { type: "button", className: cx("aia-rail-cell", "t-" + a.tone, p.current === i && "is-current"), "aria-current": p.current === i ? "step" : undefined, title: n + " — " + a.label + (s.note ? " · " + s.note : ""), onClick: p.onSelect ? function () { p.onSelect(i); } : undefined },
            h("span", { className: "aia-rail-idx" }, h(StatusGlyph, { tone: a.tone, size: 12 }), String(i + 1).padStart(2, "0")),
            h("span", { className: "aia-rail-name" }, n),
            h("span", { className: "aia-rail-state" }, s.note || a.label)));
      })));
}

/* ------------------------------------------------------------------ *
 * Honest progress: real elapsed time, real counts, the current step,
 * what it waits on. No percentage, no shimmer.
 * ------------------------------------------------------------------ */
function RunTimeline(p) {
  var counts = {};
  p.steps.forEach(function (s) { var t = appearance("StepRunStatus", s.status).tone; counts[t] = (counts[t] || 0) + 1; });
  var cur = p.steps.filter(function (s) { return s.status !== "SUCCEEDED" && s.status !== "SKIPPED" && s.status !== "BLOCKED" && s.status !== "RUNNABLE"; })[0];
  return h("section", { className: "aia-panel", "aria-label": "Průběh běhu" },
    h("div", { className: "aia-panel-h" },
      h("div", { className: "aia-row" }, h(StatusChip, { kind: "WorkflowRunStatus", value: p.status }), h("span", { className: "aia-mono aia-muted" }, p.runId)),
      h("div", { className: "aia-row aia-caption" },
        p.status === "RUNNING" ? h("span", { className: "aia-live", "aria-hidden": "true" }) : null,
        h("span", null, cs.run.elapsed + " ", h("strong", { className: "aia-num", style: { color: "var(--ink)" } }, fmtDuration(p.elapsed))),
        p.heartbeat != null ? h("span", null, "· " + cs.run.heartbeat + " před " + fmtDuration(p.heartbeat)) : null)),
    h("div", { className: "aia-panel-b aia-stack" },
      h("div", { className: "aia-row aia-caption", "aria-label": "Počty kroků" },
        h("span", null, h("strong", { className: "aia-num", style: { color: "var(--ink)" } }, (counts.done || 0) + " / " + p.steps.length), " kroků hotovo"),
        counts.running ? h("span", null, "· " + counts.running + " běží") : null,
        counts.you ? h("span", { style: { color: "var(--status-you-ink)", fontWeight: 600 } }, "· " + counts.you + " čeká na vás") : null,
        counts.world ? h("span", null, "· " + counts.world + " čeká na svět") : null,
        counts.blocked || counts.ready ? h("span", null, "· " + ((counts.blocked || 0) + (counts.ready || 0)) + " ve frontě") : null),
      cur && p.waitingOn ? h("div", { className: "aia-caption" }, cs.run.current + ": ", h("strong", { style: { color: "var(--ink)" } }, cur.name), " — " + cs.run.waitingOn.toLowerCase() + " " + p.waitingOn) : null,
      h("ol", { className: "aia-tl" }, p.steps.map(function (s, i) {
        var a = appearance("StepRunStatus", s.status);
        return h("li", { key: i, className: a.tone === "you" ? "aia-wash-you" : a.tone === "recovery" ? "aia-wash-recovery" : undefined, style: a.tone === "you" || a.tone === "recovery" ? { paddingLeft: 8, paddingRight: 8 } : null },
          h("span", { style: { color: a.tone === "you" ? "var(--status-you-ink)" : "inherit", paddingTop: 2 } }, h(StatusGlyph, { tone: a.tone })),
          h("div", null, h("div", { style: { fontWeight: 500 } }, s.name), h("div", { className: "aia-caption", style: a.tone === "recovery" ? { color: "var(--on-status-recovery)" } : null }, a.label + (s.detail ? " · " + s.detail : "") + (s.attempt > 1 ? " · " + cs.run.attempt + " " + s.attempt : ""))),
          h("span", { className: "aia-num aia-caption", style: a.tone === "recovery" ? { color: "var(--on-status-recovery)" } : null }, s.elapsed != null ? fmtDuration(s.elapsed) : ""));
      }))));
}

/* ------------------------------------------------------------------ *
 * Impact preview — consequences of an edit BEFORE it is committed.
 * Shape follows domain ImpactPreview {root_stage, invalidate, preserve,
 * presentation_only} plus optional server estimates (null = not provided).
 * ------------------------------------------------------------------ */
function ImpactPreview(p) {
  var names = cs.stages[p.lifecycle || "research"], ids = p.stageIds, pv = p.preview;
  var nothing = !pv.root_stage;
  return h("section", { className: "aia-panel", role: "region", "aria-label": cs.impact.title },
    h("div", { className: "aia-panel-h" }, h("h3", { className: "aia-h" }, cs.impact.title), h("span", { className: "aia-caption" }, cs.impact.editing + ": ", h("strong", { style: { color: "var(--ink)" } }, p.field))),
    h("div", { className: "aia-panel-b aia-stack", style: { gap: 12 } },
      nothing ? h("p", { style: { margin: 0 } }, cs.impact.nothing) : h(F, null,
        h("div", { className: "aia-impact-rail", "aria-hidden": "true" }, ids.map(function (id, i) {
          var cls = id === pv.root_stage ? "root" : pv.invalidate.indexOf(id) >= 0 ? (pv.presentation_only ? "present" : "reopen") : "keep";
          return h("span", { key: id, className: cls, title: names[i] }, String(i + 1).padStart(2, "0"));
        })),
        pv.presentation_only ? h("div", { className: "aia-caption", style: { color: "var(--ink)" } }, cs.impact.presentation) : null,
        h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
          h("div", null, h("div", { className: "aia-section-label" }, h("span", { style: { display: "inline-block", width: 12, height: 12, background: "var(--surface-sunken)", border: "1px solid var(--border)" } }), cs.impact.keep + " (" + pv.preserve.length + ")"),
            h("ul", { style: { margin: 0, paddingLeft: 16 } }, pv.preserve.map(function (id) { return h("li", { key: id }, names[ids.indexOf(id)]); })),
            p.artifactsKept != null ? h("div", { className: "aia-caption", style: { marginTop: 4 } }, h("span", { className: "aia-num" }, p.artifactsKept), " " + cs.impact.artifacts) : null),
          h("div", null, h("div", { className: "aia-section-label" }, h("span", { style: { display: "inline-block", width: 12, height: 12, border: "1px solid var(--ink)", background: "repeating-linear-gradient(135deg, var(--surface-raised) 0 3px, var(--border-strong) 3px 4px)" } }), cs.impact.reopen + " (" + pv.invalidate.length + ")"),
            h("ul", { style: { margin: 0, paddingLeft: 16 } }, pv.invalidate.map(function (id) { return h("li", { key: id, style: id === pv.root_stage ? { fontWeight: 600 } : null }, names[ids.indexOf(id)] + (id === pv.root_stage ? " — " + cs.impact.root.toLowerCase() : "")); })))),
        h("dl", { className: "aia-dl" },
          h("dt", null, cs.impact.cost), h("dd", null, p.costEstimate ? h(F, null, h(Money, { value: p.costEstimate[0], digits: 0 }), " – ", h(Money, { value: p.costEstimate[1], digits: 0 }), h("span", { className: "aia-caption" }, " · odhad z " + p.costBasis)) : h(F, null, h(Value, { state: "na" }), h("span", { className: "aia-caption" }, " " + cs.impact.costNa))),
          h("dt", null, cs.impact.time), h("dd", null, p.timeEstimate ? h("span", { className: "aia-num" }, p.timeEstimate) : h(F, null, h(Value, { state: "na" }), h("span", { className: "aia-caption" }, " " + cs.impact.costNa))))),
      h("div", { className: "aia-row", style: { justifyContent: "flex-end" } }, h(Button, { variant: "quiet" }, cs.impact.cancel), h(Button, { variant: "primary", kbd: "⌘↵" }, cs.impact.commit))));
}

/* ------------------------------------------------------------------ *
 * Budget meter — four quantities, three are not a progress bar.
 * ------------------------------------------------------------------ */
function BudgetMeter(p) {
  var L = p.limit, sp = p.spent, un = p.uncertain || 0, rs = p.reserved || 0, rem = L - sp - un - rs;
  var pc = function (v) { return Math.max(0, Math.min(100, (v / L) * 100)) + "%"; };
  var key = function (cls, sw, label, long, v, strong) {
    return h("div", { className: "aia-meter-key", title: long }, h("span", { className: "aia-meter-sw " + cls, style: sw }),
      h("div", null, h("div", { className: "aia-caption" }, label), h("div", { className: "aia-num", style: { fontWeight: strong ? 600 : 500, color: strong ? "var(--status-fault)" : undefined } }, v == null ? h(Value, { state: "na" }) : fmtMoney(v, p.currency))));
  };
  return h("div", { role: "group", "aria-label": cs.budget.limit },
    h("div", { className: "aia-row", style: { justifyContent: "space-between", marginBottom: 6 } },
      h("span", { className: "aia-label aia-muted" }, cs.budget.limit),
      h("span", { className: "aia-num", style: { fontWeight: 600 } }, fmtMoney(L, p.currency))),
    h("div", { className: "aia-meter", role: "img", "aria-label": cs.budget.spent + " " + fmtMoney(sp, p.currency) + ", " + cs.budget.uncertain + " " + fmtMoney(un, p.currency) + ", " + cs.budget.reserved + " " + fmtMoney(rs, p.currency) + ", " + cs.budget.remaining + " " + fmtMoney(rem, p.currency) },
      h("span", { className: "m-spent", style: { width: pc(sp) } }), un ? h("span", { className: "m-uncertain", style: { width: pc(un) } }) : null, rs ? h("span", { className: "m-reserved", style: { width: pc(rs) } }) : null),
    h("div", { className: "aia-meter-legend" },
      key("", { background: "var(--budget-spent)" }, cs.budget.spent, cs.budget.spentLong, sp),
      key("", { background: "repeating-linear-gradient(135deg, var(--budget-uncertain) 0 3px, var(--surface-sunken) 3px 5px)" }, cs.budget.uncertain + " (SETTLED_UNCERTAIN)", cs.budget.uncertainLong, un, un > 0),
      key("", { background: "repeating-linear-gradient(45deg, var(--budget-reserved) 0 2px, var(--surface-sunken) 2px 5px)" }, cs.budget.reserved, cs.budget.reservedLong, rs),
      key("", { background: "var(--surface-sunken)" }, cs.budget.remaining, cs.budget.remainingLong, rem)));
}

/* ------------------------------------------------------------------ *
 * Park-and-ask — authorising spend. No cheerful default: focus starts
 * on the heading, both actions carry equal weight.
 * ------------------------------------------------------------------ */
function ParkAndAsk(p) {
  var after = p.remaining - p.amount;
  return h("div", { className: "aia-dialog", role: "alertdialog", "aria-modal": "true", "aria-labelledby": "park-t", "aria-describedby": "park-d" },
    h("div", { className: "aia-scope-band", style: { background: clientAccentVar(p.clientId, p.accent), borderRadius: "4px 4px 0 0" } }),
    h("div", { className: "aia-dialog-h aia-stack", style: { gap: 6 } },
      h("div", { className: "aia-row" }, h(StatusChip, { kind: "WorkflowRunStatus", value: "AWAITING_BUDGET", small: true }), h("span", { className: "aia-caption" }, p.client + " / " + p.study)),
      h("h2", { id: "park-t", className: "aia-title", tabIndex: -1 }, cs.park.title)),
    h("div", { id: "park-d", className: "aia-dialog-b" },
      h("dl", { className: "aia-dl" },
        h("dt", null, cs.park.what), h("dd", null, p.what),
        h("dt", null, cs.park.model), h("dd", null, cs.modelRole[p.modelRole] + " · " + cs.provider[p.provider]),
        h("dt", null, cs.park.amount), h("dd", null, h("strong", { className: "aia-num" }, fmtMoney(p.amount, p.currency)), h("span", { className: "aia-caption" }, " · " + p.basis)),
        h("dt", null, cs.park.against), h("dd", null, cs.budget.remaining + " ", h("span", { className: "aia-num" }, fmtMoney(p.remaining, p.currency)), " z ", h("span", { className: "aia-num" }, fmtMoney(p.limit, p.currency))),
        h("dt", null, cs.park.after), h("dd", { style: after < 0 ? { color: "var(--status-fault)", fontWeight: 600 } : null }, after < 0 ? h(F, null, h(StatusGlyph, { tone: "fault", size: 12 }), " " + cs.budget.over + " ", h("span", { className: "aia-num" }, fmtMoney(-after, p.currency))) : h("span", { className: "aia-num" }, fmtMoney(after, p.currency)))),
      h("div", { style: { borderTop: "1px solid var(--border)", paddingTop: 10 } }, h("div", { className: "aia-label aia-muted" }, cs.park.decline), h("p", { style: { margin: "2px 0 0" } }, cs.park.declineText)),
      p.canApprove ? null : h("div", { className: "aia-world", style: { borderStyle: "solid", borderColor: "var(--border-strong)", background: "var(--surface-sunken)" } }, h(Icon, { name: "gate" }), h("span", null, cs.park.noPermission))),
    h("div", { className: "aia-dialog-f" },
      h(Button, null, cs.park.reject),
      p.canApprove ? h(Button, { variant: "primary" }, cs.park.approve + " " + fmtMoney(p.amount, p.currency, 0)) : h(Button, null, cs.park.askLead)));
}

/* Provider parked: an explicit choice, never a convenience substitution. */
function ProviderChoice(p) {
  var canSwitch = p.policy === "CLAUDE_CODE_THEN_API";
  return h("section", { className: "aia-world", role: "region", "aria-label": cs.provider_ui.title, style: { display: "grid", gap: 10 } },
    h("div", { className: "aia-row" }, h(StatusChip, { kind: "WorkflowRunStatus", value: "WAITING_PROVIDER" }), h("strong", null, cs.provider_ui.title)),
    h("p", { style: { margin: 0 } }, cs.provider[p.provider] + ": " + p.reason, p.resumeAt ? h(F, null, " Obnoví se ", h("strong", { className: "aia-num" }, p.resumeAt), ".") : null),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 } },
      h("div", { className: "aia-panel aia-panel-b" }, h("div", { style: { fontWeight: 600 } }, cs.provider_ui.wait + (p.resumeAt ? " do " + p.resumeAt : "")), h("div", { className: "aia-caption" }, cs.provider_ui.waitText), h("div", { style: { marginTop: 8 } }, h(Button, { compact: true }, "Nechat čekat"))),
      canSwitch
        ? h("div", { className: "aia-panel aia-panel-b" }, h("div", { style: { fontWeight: 600 } }, cs.provider_ui.switch + " " + cs.provider[p.alternative]), h("div", { className: "aia-caption" }, cs.provider_ui.switchText), p.alternativeCost ? h("div", { className: "aia-caption", style: { marginTop: 4 } }, "Odhad zbytku běhu: ", h(Money, { value: p.alternativeCost, digits: 0 })) : null, h("div", { style: { marginTop: 8 } }, h(Button, { compact: true }, "Přepnout — zapíše se do auditu")))
        : h("div", { className: "aia-panel aia-panel-b" }, h("div", { style: { fontWeight: 600 } }, cs.provider_ui.notAllowed), h("div", { className: "aia-caption" }, cs.provider_ui.policy + ": " + cs.providerPolicy[p.policy] + ". Změnu politiky provádí vedoucí studie v nastavení projektu."))));
}

/* Recovery required: a decision about money that may already be spent. */
function RecoveryDecision(p) {
  return h("section", { className: "aia-recovery", role: "alert", style: { display: "grid", gap: 8 } },
    h("div", { className: "aia-row" }, h(StatusGlyph, { tone: "recovery", size: 16 }), h("strong", null, "Vyžaduje rozhodnutí — výsledek placeného volání neznáme")),
    h("p", { style: { margin: 0 } }, p.step + ": volání odešlo na " + cs.provider[p.provider] + " v " + p.at + " a pracovník zanikl dřív, než dorazila odpověď. Rezervace ", h("strong", { className: "aia-num" }, fmtMoney(p.amount, p.currency)), " je vedena jako ", h("strong", null, "nejisté vyúčtování"), " a počítá se do utraceného."),
    h("p", { style: { margin: 0 } }, "Automatické opakování je vypnuté, aby pád nevedl k dvojí platbě."),
    h("div", { className: "aia-row" }, h(Button, null, "Ověřit u poskytovatele"), h(Button, null, "Spustit znovu — může zaplatit podruhé"), h(Button, null, "Ukončit krok")));
}

/* ------------------------------------------------------------------ *
 * Usage ledger — immutable, dense, sortable, attributable.
 * ------------------------------------------------------------------ */
function UsageLedger(p) {
  return h("div", { className: "aia-panel", style: { overflowX: "auto" } },
    h("table", { className: "aia-table", "aria-label": "Záznamy o využití AI (neměnné)" },
      h("thead", null, h("tr", null, ["Čas", "Záznam", "Krok", "Role modelu", "Poskytovatel / model", "Vstup tok.", "Výstup tok.", "Částka", "Stav rezervace"].map(function (c, i) { return h("th", { key: i, className: i >= 5 && i <= 7 ? "r" : undefined, "aria-sort": i === 0 ? "descending" : undefined }, c); }))),
      h("tbody", null, p.rows.map(function (r, i) {
        return h("tr", { key: i },
          h("td", { className: "aia-num aia-muted" }, r.at),
          h("td", { className: "aia-mono", style: { fontSize: 12 } }, r.id),
          h("td", { className: "aia-mono", style: { fontSize: 12 } }, r.step),
          h("td", null, cs.modelRole[r.role]),
          h("td", null, cs.provider[r.provider], h("span", { className: "aia-mono aia-muted", style: { fontSize: 12 } }, " " + r.model)),
          h("td", { className: "r" }, h(Value, { value: r.inTok })),
          h("td", { className: "r" }, h(Value, { value: r.outTok })),
          h("td", { className: "r" }, r.amount == null ? h(Value, { state: "na" }) : h(Money, { value: r.amount, digits: 4 })),
          h("td", null, h(StatusChip, { kind: "ReservationStatus", value: r.status, small: true })));
      }))));
}

/* ------------------------------------------------------------------ *
 * Approval — what, by whom, on what evidence, attesting to what.
 * ------------------------------------------------------------------ */
function ApprovalPanel(p) {
  var sod = p.producerIsViewer && !p.selfAllowed;
  return h("section", { className: "aia-panel", "aria-label": cs.approval.title },
    h("div", { className: "aia-panel-h" }, h("h3", { className: "aia-h" }, cs.approval.title), h(StatusChip, { kind: "WorkflowRunStatus", value: "AWAITING_GATE", small: true })),
    h("div", { className: "aia-panel-b aia-stack", style: { gap: 12 } },
      h("dl", { className: "aia-dl" },
        h("dt", null, cs.approval.what), h("dd", null, p.what, h("div", { className: "aia-mono aia-muted", style: { fontSize: 12 } }, p.fingerprint)),
        h("dt", null, cs.approval.producer), h("dd", null, p.producer),
        h("dt", null, cs.approval.evidence), h("dd", null, h("div", { className: "aia-row" },
          h("span", { className: "aia-chip aia-tone-done aia-chip-sm" }, h(StatusGlyph, { tone: "done", size: 12 }), p.checks.passed + " / " + p.checks.total + " kontrol"),
          p.checks.warnings ? h("span", { className: "aia-chip aia-tone-done-warn aia-chip-sm" }, h(StatusGlyph, { tone: "done-warn", size: 12 }), p.checks.warnings + " výhrady") : null,
          p.checks.modelled ? h("span", { className: "aia-caption" }, h(EvidenceMark, { role: "MODELED_BEHAVIOR_PRIOR" }), " " + p.checks.modelled + " modelovaných tvrzení") : null,
          p.checks.pending ? h("span", { className: "aia-caption" }, h(EvidenceMark, { role: "EXTERNAL_HOLDOUT_PENDING" }), " externí validace čeká") : null))),
      sod
        ? h("div", { role: "status", style: { border: "1.5px solid var(--ink)", borderRadius: 2, padding: "10px 12px", display: "grid", gap: 6, background: "var(--surface-sunken)" } },
            h("div", { className: "aia-row", style: { fontWeight: 600 } }, h(Icon, { name: "gate" }), cs.approval.sodTitle),
            h("div", null, cs.approval.sodText + " (" + cs.approval.source[p.policySource || "default"] + ")."),
            h("div", { className: "aia-caption" }, cs.approval.sodWho + ": ", p.eligible.join(", ")),
            h("div", null, h(Button, { compact: true }, "Požádat o nezávislé schválení")))
        : h(F, null,
            h("div", { style: { borderLeft: 0, background: "var(--surface-sunken)", padding: "10px 12px" } }, h("div", { className: "aia-label aia-muted" }, cs.approval.attest), h("p", { style: { margin: "4px 0 0" } }, cs.approval.attestText),
              p.selfAllowed && p.producerIsViewer ? h("div", { className: "aia-caption", style: { marginTop: 6 } }, cs.approval.selfAllowed + " (" + cs.approval.source[p.policySource] + ") — zapíše se jako samoschválení.") : null),
            h("div", { className: "aia-row", style: { justifyContent: "flex-end" } }, h(Button, null, cs.approval.ret), h(Button, { variant: "primary", icon: "signoff" }, cs.approval.approve))),
      p.audit ? h("div", null, h("div", { className: "aia-section-label" }, cs.approval.audit),
        h("ol", { className: "aia-tl" }, p.audit.map(function (a, i) {
          return h("li", { key: i }, h(Icon, { name: a.icon || "clock", size: 14 }), h("div", null, a.text), h("span", { className: "aia-caption aia-num" }, a.at));
        }))) : null));
}

/* ------------------------------------------------------------------ *
 * Revisions
 * ------------------------------------------------------------------ */
function RevisionBanner(p) {
  return h("div", { className: "aia-superseded", role: "status" },
    h(Icon, { name: "revision" }), h("span", null, cs.revision.superseded + " ", h("span", { className: "aia-mono" }, "rev " + p.viewing), " · aktuální je ", h("span", { className: "aia-mono" }, "rev " + p.current), " (" + p.when + ")"),
    h("span", { className: "aia-scope-spacer" }), h(Button, { compact: true }, cs.revision.compare), h(Button, { compact: true, variant: "primary" }, cs.revision.open));
}
function RevisionHistory(p) {
  return h("div", { className: "aia-panel" },
    h("table", { className: "aia-table", "aria-label": "Historie revizí" },
      h("thead", null, h("tr", null, ["Revize", "Změna", "Kdo", "Kdy", "Otevřené fáze", ""].map(function (c, i) { return h("th", { key: i }, c); }))),
      h("tbody", null, p.revisions.map(function (r, i) {
        return h("tr", { key: i, className: r.viewing ? "is-selected" : undefined },
          h("td", { className: "aia-mono" }, "rev " + r.n, i === 0 ? h("span", { className: "aia-caption" }, " · " + cs.revision.current) : null),
          h("td", null, r.change), h("td", null, r.by), h("td", { className: "aia-num aia-muted" }, r.at),
          h("td", { className: "aia-num" }, r.reopened === 0 ? h("span", { className: "aia-caption" }, "žádné (bez dopadu)") : r.reopened),
          h("td", null, i > 0 ? h(Button, { compact: true, variant: "quiet" }, cs.revision.compare) : null));
      }))));
}

/* ------------------------------------------------------------------ *
 * Headline answer — the sentence a client pays for.
 * ------------------------------------------------------------------ */
function HeadlineAnswer(p) {
  return h("section", { className: "aia-headline", "aria-label": "Hlavní odpověď" },
    h("div", { className: "aia-headline-q" }, "Otázka klienta · " + p.question),
    h("p", { className: "aia-headline-a" }, p.answer),
    h("div", { className: "aia-row aia-caption" },
      h(Value, { value: p.figure, format: fmtPct, role: p.role }), h("span", null, cs.evidence[evidenceRole(p.role)].long),
      h("span", null, "· n = ", h("span", { className: "aia-num" }, fmtNum(p.n))),
      p.interval ? h("span", null, "· interval ", h("span", { className: "aia-num" }, fmtPct(p.interval[0]) + " – " + fmtPct(p.interval[1]))) : null),
    p.findings ? h("ul", { className: "aia-headline-find" }, p.findings.map(function (f, i) {
      return h("li", { key: i }, h("span", { style: { paddingTop: 5 } }, h(EvidenceMark, { role: f.role })), h("span", null, f.text, f.role === "MODELED_BEHAVIOR_PRIOR" ? h("span", { className: "aia-caption" }, " (modelováno)") : null));
    })) : null);
}

/* ------------------------------------------------------------------ *
 * Sociomapa — nodes over immutable originals; view overrides and
 * what-if are visibly layers.
 * nodes: [{id,label,x,y,role,cluster,moved:{x,y}?, whatif?}] edges: [{a,b,w,crossBlock?}]
 * ------------------------------------------------------------------ */
function Sociomap(p) {
  var W = 640, H = 360, byId = {};
  p.nodes.forEach(function (n) { byId[n.id] = n; });
  var pos = function (n) { return p.showOverrides !== false && n.moved ? n.moved : n; };
  var col = ["var(--viz-cat-1)", "var(--viz-cat-2)", "var(--viz-cat-3)", "var(--viz-cat-4)"];
  var overrides = p.nodes.filter(function (n) { return n.moved; }).length;
  return h("figure", { className: "aia-map", style: { margin: 0 } },
    h("div", { className: "aia-map-layer" },
      overrides && p.showOverrides !== false ? h("span", { className: "aia-layer-tag" }, h(Icon, { name: "view", size: 12 }), " Pohled upraven: " + overrides + " uzly posunuty · " + p.overrideBy + " · ", h("u", null, cs.actions.reset)) : null,
      p.whatif ? h("span", { className: "aia-layer-tag is-whatif" }, h(Icon, { name: "whatif", size: 12 }), " Vrstva co-když: " + p.whatif + " — provizorní") : null),
    h("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": p.label },
      h("defs", null,
        h("pattern", { id: "wf-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, h("path", { d: "M0 0v5", stroke: "var(--ink-faint)", strokeWidth: 1.2 }))),
      p.clusters ? p.clusters.map(function (c, i) { return h("ellipse", { key: "c" + i, cx: c.x, cy: c.y, rx: c.rx, ry: c.ry, fill: "none", stroke: col[i % 4], strokeWidth: 1, strokeDasharray: "3 3", opacity: 0.8 }); }) : null,
      p.edges.map(function (e, i) {
        var a = pos(byId[e.a]), b = pos(byId[e.b]);
        if (e.crossBlock) {
          var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
          return h("g", { key: "e" + i }, h("line", { x1: a.x, y1: a.y, x2: mx - (b.x - a.x) * 0.06, y2: my - (b.y - a.y) * 0.06, stroke: "var(--ink-muted)", strokeWidth: 1, strokeDasharray: "4 3" }), h("line", { x1: mx + (b.x - a.x) * 0.06, y1: my + (b.y - a.y) * 0.06, x2: b.x, y2: b.y, stroke: "var(--ink-muted)", strokeWidth: 1, strokeDasharray: "4 3" }));
        }
        return h("line", { key: "e" + i, x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: "var(--ink-faint)", strokeWidth: 0.5 + e.w * 2, opacity: 0.7 });
      }),
      p.showOverrides !== false ? p.nodes.filter(function (n) { return n.moved; }).map(function (n) {
        return h("g", { key: "g" + n.id }, h("circle", { cx: n.x, cy: n.y, r: 7, fill: "none", stroke: "var(--ink-faint)", strokeDasharray: "2 2" }), h("line", { x1: n.x, y1: n.y, x2: n.moved.x, y2: n.moved.y, stroke: "var(--ink-faint)", strokeDasharray: "2 2" }));
      }) : null,
      p.nodes.map(function (n) {
        var q = pos(n), r = evidenceRole(n.role), c = col[(n.cluster || 0) % 4], sel = p.selected === n.id;
        var shape;
        if (n.whatif) shape = h("rect", { x: q.x - 7, y: q.y - 7, width: 14, height: 14, fill: "url(#wf-hatch)", stroke: "var(--ink)", strokeWidth: 1.2, strokeDasharray: "3 2" });
        else if (r === "MEASURED_JOINT") shape = h("circle", { cx: q.x, cy: q.y, r: 7, fill: c, stroke: "var(--surface-raised)", strokeWidth: 2 });
        else if (r === "CALIBRATED_CORE") shape = h("g", null, h("circle", { cx: q.x, cy: q.y, r: 8, fill: "var(--surface-raised)", stroke: c, strokeWidth: 1.5 }), h("circle", { cx: q.x, cy: q.y, r: 4.5, fill: c }));
        else if (r === "MODELED_BEHAVIOR_PRIOR") shape = h("circle", { cx: q.x, cy: q.y, r: 7, fill: "var(--surface-raised)", stroke: c, strokeWidth: 2 });
        else shape = h("g", null, h("circle", { cx: q.x, cy: q.y, r: 7, fill: "var(--surface-raised)", stroke: "var(--ink)", strokeWidth: 1.2, strokeDasharray: "2 2" }), h("text", { x: q.x, y: q.y + 3.5, fontSize: 9, textAnchor: "middle", fill: "var(--ink)", fontWeight: 700 }, "?"));
        return h("g", { key: n.id }, sel ? h("circle", { cx: q.x, cy: q.y, r: 12, fill: "none", stroke: "var(--focus-ring)", strokeWidth: 2 }) : null, shape,
          h("text", { x: q.x + 11, y: q.y + 4, fontSize: 11, fill: "var(--ink)", fontFamily: "var(--font-sans)" }, n.label));
      })),
    p.whatif ? h("div", { className: "aia-whatif-band" }, "CO-KDYŽ — provizorní vrstva nad zmrazenými výsledky. Není to zjištění.") : null,
    h("figcaption", { className: "aia-caption", style: { padding: "6px 10px", borderTop: "1px solid var(--border)", display: "flex", gap: 14, flexWrap: "wrap" } },
      h("span", null, "● měřeno"), h("span", null, "◉ kalibrované jádro"), h("span", null, "○ modelováno"), h("span", null, "◌? role neznámá"), h("span", null, "╌ ╌ vztah mezi bloky (nejde o tutéž osobu)"), p.whatif ? h("span", null, "▨ co-když") : null, overrides ? h("span", null, "◌┄ původní poloha") : null));
}
/* ------------------------------------------------------------------ *
 * GradedBars — a bar chart whose bars carry their evidence grade.
 * rows: [{label, value|null, state?, role, lo?, hi?}]
 *   measured: solid · calibrated: solid + inner frame · modelled: hatched
 *   na: no bar, "chybí" label · suppressed: redaction bar
 * Direct labels on every bar (relief rule), grey text, series hue only on marks.
 * ------------------------------------------------------------------ */
function GradedBars(p) {
  var W = p.width || 560, rowH = 26, lab = 150, right = 96, max = p.max || 100, id = "gb" + (p.id || "0");
  var sx = function (v) { return lab + (v / max) * (W - lab - right); };
  var c = p.color || "var(--viz-cat-1)";
  var Hh = p.rows.length * rowH + 24;
  return h("svg", { viewBox: "0 0 " + W + " " + Hh, width: "100%", role: "img", "aria-label": p.label, style: { display: "block", fontFamily: "var(--font-sans)" } },
    h("defs", null, h("pattern", { id: id + "h", width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, h("rect", { width: 4, height: 4, fill: "var(--surface-raised)" }), h("path", { d: "M0 0v4", stroke: c, strokeWidth: 2 }))),
    [0, 25, 50, 75, 100].filter(function (t) { return t <= max; }).map(function (t) {
      return h("g", { key: t }, h("line", { x1: sx(t), x2: sx(t), y1: 0, y2: Hh - 20, stroke: "var(--viz-grid)" }), h("text", { x: sx(t), y: Hh - 6, fontSize: 11, textAnchor: "middle", fill: "var(--viz-axis)" }, t + " %"));
    }),
    p.rows.map(function (r, i) {
      var y = i * rowH + 4, role = evidenceRole(r.role), st = r.state || (r.value == null ? "na" : "value");
      var bar = null, label = null;
      if (st === "na") label = h("g", null, h("rect", { x: lab, y: y + 3, width: 46, height: 16, fill: "none", stroke: "var(--null-mark)", rx: 2 }), h("text", { x: lab + 23, y: y + 15, fontSize: 11, fontWeight: 600, textAnchor: "middle", fill: "var(--null-mark)" }, cs.nulls.na));
      else if (st === "suppressed") label = h("g", null, h("rect", { x: lab, y: y + 6, width: 40, height: 10, fill: "var(--suppressed-fill)" }), h("text", { x: lab + 48, y: y + 15, fontSize: 11, fill: "var(--ink-muted)" }, cs.nulls.suppressed + " · " + cs.nulls.suppressedSample));
      else {
        var w = sx(r.value) - lab;
        if (role === "MEASURED_JOINT") bar = h("rect", { x: lab, y: y + 3, width: w, height: 16, fill: c, rx: 0 });
        else if (role === "CALIBRATED_CORE") bar = h("g", null, h("rect", { x: lab, y: y + 3, width: w, height: 16, fill: c }), h("rect", { x: lab + 2.5, y: y + 5.5, width: Math.max(0, w - 5), height: 11, fill: "none", stroke: "var(--surface-raised)", strokeWidth: 1.2 }));
        else bar = h("rect", { x: lab, y: y + 3, width: w, height: 16, fill: "url(#" + id + "h)", stroke: c, strokeWidth: 1.5, strokeDasharray: role === "MODELED_BEHAVIOR_PRIOR" ? "none" : "3 2" });
        var whisk = r.lo != null ? h("g", null, h("line", { x1: sx(r.lo), x2: sx(r.hi), y1: y + 11, y2: y + 11, stroke: "var(--ink)", strokeWidth: 1.2 }), h("line", { x1: sx(r.lo), x2: sx(r.lo), y1: y + 7, y2: y + 15, stroke: "var(--ink)" }), h("line", { x1: sx(r.hi), x2: sx(r.hi), y1: y + 7, y2: y + 15, stroke: "var(--ink)" })) : null;
        var lx = sx(r.hi != null ? r.hi : r.value) + 6;
        label = h("g", null, whisk, h("text", { x: lx, y: y + 15, fontSize: 12, fill: "var(--ink)", style: { fontVariantNumeric: "tabular-nums" } }, fmtPct(r.value)),
          h("svg", { x: lx + 44, y: y + 7, width: 8, height: 8, overflow: "visible" }, h(EvidenceMark, { role: role, inSvg: true })));
      }
      return h("g", { key: i }, h("title", null, r.label + ": " + (st === "na" ? cs.nulls.naLong : st === "suppressed" ? cs.nulls.suppressedLong : fmtPct(r.value) + " — " + cs.evidence[role].long)),
        h("text", { x: lab - 8, y: y + 15, fontSize: 12, textAnchor: "end", fill: "var(--ink)" }, r.label), bar, label);
    }));
}

/* ------------------------------------------------------------------ *
 * Deliverable register
 * ------------------------------------------------------------------ */
function ReportCover(p) {
  var dots = [];
  for (var y = 0; y < 22; y++) for (var x = 0; x < 16; x++) {
    var d = (x / 16) * 0.55 + (y / 22) * 0.55 + Math.sin(x * 0.9 + y * 0.4) * 0.12;
    if (d < 0.35) continue;
    dots.push(h("circle", { key: x + "." + y, cx: 250 + x * 22, cy: 360 + y * 22, r: d > 0.85 ? 3.4 : d > 0.62 ? 2.4 : 1.4, fill: "var(--doc-ink)", opacity: d > 0.85 ? 0.9 : d > 0.62 ? 0.55 : 0.28 }));
  }
  return h("div", { className: "aia-doc aia-doc-cover", style: p.style },
    h("svg", { viewBox: "0 0 595 842", width: "100%", style: { display: "block" }, role: "img", "aria-label": "Titulní strana reportu" },
      h("rect", { width: 595, height: 842, fill: "var(--doc-paper)" }), dots,
      h("rect", { x: 56, y: 72, width: 48, height: 3, fill: "var(--doc-accent)" }),
      h("text", { x: 56, y: 104, fontSize: 11, fontFamily: "var(--font-sans)", fill: "var(--doc-muted)", letterSpacing: ".04em" }, p.client + " · Důvěrné"),
      h("text", { x: 56, y: 170, fontSize: 34, fontFamily: "var(--font-display)", fontWeight: 600, fill: "var(--doc-ink)" }, p.title[0]),
      p.title[1] ? h("text", { x: 56, y: 210, fontSize: 34, fontFamily: "var(--font-display)", fontWeight: 600, fill: "var(--doc-ink)" }, p.title[1]) : null,
      h("text", { x: 56, y: 248, fontSize: 14, fontFamily: "var(--font-serif)", fill: "var(--doc-muted)" }, p.subtitle),
      h("text", { x: 56, y: 770, fontSize: 10, fontFamily: "var(--font-sans)", fill: "var(--doc-muted)" }, p.date + " · rev " + p.revision + " · " + p.pages + " stran"),
      h("text", { x: 56, y: 786, fontSize: 10, fontFamily: "var(--font-sans)", fill: "var(--doc-muted)" }, "Syntetická populace ČR, kalibrované jádro v17.4 · Schválil(a): " + p.signedBy)));
}
function ReportPage(p) {
  return h("article", { className: "aia-doc", style: { border: "1px solid var(--doc-rule)" } },
    h("div", { className: "aia-doc-page", style: { padding: p.tight ? "32px 40px" : undefined } },
      h("div", { className: "cap", style: { display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--doc-rule)", paddingBottom: 6, marginBottom: 8 } }, h("span", null, "Důvěra v digitální bankovnictví 2026"), h("span", null, "Strana 4")),
      h("h1", null, h("span", { className: "num" }, "1"), "Hlavní zjištění"),
      h("p", { className: "lede margin-ev" }, h("span", { className: "gm" }, h(EvidenceMark, { role: "CALIBRATED_CORE", size: 9 })),
        "Čtyři z deseti dospělých (", h("span", { className: "aia-num" }, "41,7 %"), ") by převedli hlavní účet k bance, která nabídne plně digitální hypotéku bez návštěvy pobočky."),
      h("div", { className: "holdout", role: "note" }, h(EvidenceMark, { role: "EXTERNAL_HOLDOUT_PENDING", size: 12 }),
        h("div", null, h("strong", null, "Externí prediktivní validace dosud neproběhla. "), "Čísla v této kapitole pocházejí z kalibrované syntetické populace. Nebyla ověřena proti skutečnému chování na nezávislém vzorku (EXTERNAL_HOLDOUT_PENDING). Čtěte je jako odhad struktury, ne jako předpověď tržního podílu.")),
      h("p", { className: "margin-ev" }, h("span", { className: "gm" }, h(EvidenceMark, { role: "MODELED_BEHAVIOR_PRIOR", size: 9 })),
        "U lidí nad 55 let je ochota výrazně nižší. Tento údaj je ", h("em", null, "modelován"), " z behaviorálního prioru, nikoli změřen v téže populaci¹ — rozdíl proto uvádíme jen jako směr."),
      h("figure", null,
        h(GradedBars, { id: "doc", width: 560, label: "Ochota převést účet podle věku", color: "var(--doc-accent)", rows: [
          { label: "18–34", value: 52.3, lo: 48.9, hi: 55.6, role: "CALIBRATED_CORE" }, { label: "35–54", value: 44.1, lo: 41.0, hi: 47.3, role: "CALIBRATED_CORE" },
          { label: "55+", value: 27.8, role: "MODELED_BEHAVIOR_PRIOR" }, { label: "Bez odpovědi", value: null }] }),
        h("figcaption", null, h("strong", null, "Obr. 3 "), " Ochota převést hlavní účet podle věku, % dospělých (n = 1 204). ▣ kalibrované jádro s 95% intervalem · □ modelováno, bez intervalu · „chybí“ = hodnota nezjištěna.")),
      h("table", null, h("caption", { className: "cap", style: { textAlign: "left", captionSide: "bottom", paddingTop: 6 } }, "Tab. 2  Rozhodující faktory. Sloupec „Podíl“ je celý kalibrované jádro (▣), pokud není v buňce uvedeno jinak."),
        h("thead", null, h("tr", null, h("th", null, "Faktor"), h("th", { className: "r" }, "Podíl ▣"), h("th", { className: "r" }, "n"))),
        h("tbody", null,
          h("tr", null, h("td", null, "Bez návštěvy pobočky"), h("td", { className: "r" }, h(Value, { value: 63.2, format: fmtPct, role: "CALIBRATED_CORE", inheritRole: "CALIBRATED_CORE" })), h("td", { className: "r aia-num" }, "1 204")),
          h("tr", null, h("td", null, "Nižší poplatky"), h("td", { className: "r" }, h(Value, { value: 48.0, format: fmtPct, role: "MODELED_BEHAVIOR_PRIOR", inheritRole: "CALIBRATED_CORE" })), h("td", { className: "r aia-num" }, "1 204")),
          h("tr", null, h("td", null, "Doporučení známého"), h("td", { className: "r" }, h(Value, { state: "suppressed", width: 4 })), h("td", { className: "r aia-num" }, "22")),
          h("tr", null, h("td", null, "Značka banky"), h("td", { className: "r" }, h(Value, { value: 0, format: fmtPct, role: "CALIBRATED_CORE", inheritRole: "CALIBRATED_CORE" })), h("td", { className: "r aia-num" }, "1 204")))),
      h("div", { className: "fn" }, "¹ Modelováno z behaviorálního prioru (MODELED_BEHAVIOR_PRIOR). Vztahy mezi bloky dotazníku nejsou pravdou o téže osobě. ",
        "Potlačeno: buňky s n < 30 nezveřejňujeme. Viz Příloha B — evidenční role všech čísel.")));
}
/* ================================================================== *
 * Screen compositions. Real-shaped content; every screen shows at
 * least one degraded state. Data here is fixture data, not logic.
 * ================================================================== */
var PEOPLE = { jd: "Jana Dvořáková", tb: "Tomáš Beneš", ph: "Petra Horáková", mk: "Martin Kučera", es: "Eva Šimková" };
var CLIENTS = [
  { id: "cl_horizont", accent: 1, code: "BH", name: "Banka Horizont" },
  { id: "cl_morava", accent: 2, code: "EM", name: "Energie Morava" },
  { id: "cl_salvia", accent: 4, code: "SL", name: "Lékárny Salvia" },
  { id: "cl_tecka", accent: 5, code: "OT", name: "Operátor Tečka" },
  { id: "cl_brazda", accent: 6, code: "NB", name: "Nakladatelství Brázda" }
];
var R_IDS = ["BRIEF", "DEEP_RESEARCH", "RESEARCH_DESIGN", "QUESTIONNAIRE", "AUDIENCE", "DIMENSIONS", "SAMPLE_PLAN", "FIELDWORK", "AGGREGATION", "VALIDATION", "ANALYSIS", "REPORT", "DELIVERY"];
var S_IDS = ["BRIEF", "DEEP_RESEARCH", "BASELINE", "SCENARIO_CONTRACT", "AUDIENCE", "DIMENSIONS", "VARIANTS", "WORLDS", "FROZEN_RESULTS", "COMPARISON", "INTERPRETATION", "REPORT", "DELIVERY"];
function st(list) { return list.map(function (s) { return typeof s === "string" ? { status: s } : s; }); }

var NAV = [
  { id: "portfolio", icon: "portfolio", label: "Portfolio", count: 3 },
  { id: "study", icon: "study", label: "Studie" },
  { id: "results", icon: "evidence", label: "Výsledky" },
  { id: "map", icon: "map", label: "Sociomapa" },
  { id: "library", icon: "library", label: "Data Library", count: 2 },
  { id: "cost", icon: "budget", label: "Náklady" },
  { id: "report", icon: "artifact", label: "Report a předání" },
  { id: "admin", icon: "settings", label: "Správa" }
];
function AppShell(p) {
  return h("div", { className: "aia", style: { minHeight: "100vh" } },
    h("a", { href: "#main", className: "aia-sr" }, "Přeskočit na obsah"),
    p.scope,
    h("div", { className: "aia-app" },
      h("nav", { className: "aia-nav", "aria-label": "Hlavní navigace" },
        NAV.map(function (n) { return h("a", { key: n.id, href: "#" + n.id, "aria-current": p.active === n.id ? "page" : undefined }, h(Icon, { name: n.icon, size: 16 }), n.label, n.count && p.showCounts !== false ? h("span", { className: "count", title: n.count + " čeká na vás" }, n.count) : null); }),
        h("div", { style: { flex: 1 } }),
        h("div", { className: "aia-caption", style: { padding: "8px", display: "grid", gap: 4 } }, h("span", null, h(Kbd, null, "⌘K"), " příkazy"), h("span", null, h(Kbd, null, "?"), " zkratky"))),
      h("main", { id: "main", className: "aia-main", tabIndex: -1 }, h("div", { className: "aia-content" }, p.children))));
}
function StudyScope(p) {
  var c = CLIENTS[p.client || 0];
  return h(ScopeBar, { clientId: c.id, accent: c.accent, code: c.code, client: c.name, study: p.study || "Důvěra v digitální bankovnictví 2026", studyStatus: p.status || "ACTIVE", revision: p.revision == null ? 14 : p.revision, role: p.role || "LEAD", deliveredAt: p.deliveredAt });
}
function Section(p) {
  return h("section", { className: "aia-panel", "aria-label": p.title, style: p.style },
    h("div", { className: "aia-panel-h" }, h("h2", { className: "aia-h" }, p.title), p.right || null),
    h("div", { className: p.flush ? "aia-scroll-x" : "aia-panel-b" }, p.children));
}

/* ---------------- 1. Portfolio ---------------- */
var PORTFOLIO = [
  { c: 0, study: "Důvěra v digitální bankovnictví 2026", life: "research", stage: 6, status: "AWAITING_BUDGET", need: "Schválit výdaj 4 900 USD na respondenty", since: "2 d 4 h", who: "vy" },
  { c: 2, study: "Věrnostní program 2027", life: "research", stage: 11, status: "AWAITING_GATE", need: "Podepsat report rev 9 (QA prošlo)", since: "5 h 12 min", who: "vy" },
  { c: 1, study: "Tarif pro domácnosti — cenová citlivost", life: "simulation", stage: 3, status: "AWAITING_GATE", need: "Schválit kontrakt scénáře", since: "38 min", who: "vy" },
  { c: 3, study: "Odchody zákazníků 2026", life: "research", stage: 7, status: "RECOVERY_REQUIRED", need: "Rozhodnout o volání s neznámým výsledkem (0,84 USD)", since: "1 h 03 min", who: "vy" },
  { c: 1, study: "Zelená energie — ochota připlatit", life: "simulation", stage: 7, status: "WAITING_PROVIDER", need: "Kvóta Claude Code se obnoví v 18:00", since: "2 h 40 min", who: "svět" },
  { c: 4, study: "Čtenářské návyky 2026", life: "research", stage: 7, status: "RUNNING", need: null, since: "14 min 32 s", who: null },
  { c: 2, study: "Cena volně prodejných léků", life: "research", stage: 8, status: "FAILED", need: "Agregace: neplatná struktura výstupu", since: "včera 16:20", who: null },
  { c: 3, study: "Roaming mimo EU", life: "research", stage: null, status: null, need: null, since: null, who: null }
];
function Portfolio(p) {
  var groups = [
    { key: "you", title: "Čeká na vás", note: "Bez vás se nepohne. Seřazeno podle doby čekání." },
    { key: "recovery", title: "Vyžaduje rozhodnutí o penězích", note: null },
    { key: "world", title: "Čeká na svět", note: "Obnoví se samo; zasáhnout můžete." },
    { key: "running", title: "Běží", note: null },
    { key: "fault", title: "Selhalo", note: null }
  ];
  var rowFor = function (r, i) {
    var c = CLIENTS[r.c], a = r.status ? appearance("WorkflowRunStatus", r.status) : null;
    return h("tr", { key: i, className: a ? (a.tone === "you" ? "aia-wash-you" : a.tone === "recovery" ? "aia-wash-recovery" : undefined) : undefined },
      h("td", null, h("div", { className: "aia-row", style: { flexWrap: "nowrap" } }, h(ClientMonogram, { clientId: c.id, accent: c.accent, code: c.code, name: c.name }), h("div", null, h("div", { style: { fontWeight: 600 } }, r.study), h("div", { className: "aia-caption", style: a && a.tone === "recovery" ? { color: "inherit" } : null }, c.name + " · " + cs.lifecycle[r.life])))),
      h("td", null, r.stage == null ? h(Value, { state: "na" }) : h("span", null, h("span", { className: "aia-num aia-muted" }, String(r.stage + 1).padStart(2, "0") + "/13 "), cs.stages[r.life][r.stage])),
      h("td", null, r.status ? h(StatusChip, { kind: "WorkflowRunStatus", value: r.status }) : h("span", { className: "aia-row" }, h(Value, { state: "na" }), h("span", { className: "aia-caption" }, "stav nedorazil"))),
      h("td", null, r.need || h("span", { className: "aia-caption" }, r.status === "RUNNING" ? "Nic — běží krok Respondenti" : "—")),
      h("td", { className: "aia-num" }, r.since || h(Value, { state: "na" })),
      h("td", { style: { textAlign: "right" } }, r.status ? h(Button, { compact: true, variant: a.tone === "you" ? "primary" : undefined }, a.tone === "you" ? cs.actions.approve : a.tone === "recovery" ? cs.actions.decide : cs.actions.open) : h(Button, { compact: true }, "Načíst znovu")));
  };
  return h(AppShell, { active: "portfolio", scope: h(ScopeBar, { above: true, note: "Portfolio · 5 klientů · 8 studií, ke kterým máte přístup", role: "LEAD" }) },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } },
      h("div", null, h("h1", { className: "aia-title" }, "Co dnes potřebuje vás"), h("div", { className: "aia-caption" }, "Úterý 22. 9. 2026 · aktualizováno před 8 s")),
      h("div", { className: "aia-row" }, h("span", { className: "aia-chip aia-tone-you" }, h(StatusGlyph, { tone: "you" }), "3 čekají na vás"), h("span", { className: "aia-chip aia-tone-recovery" }, h(StatusGlyph, { tone: "recovery" }), "1 rozhodnutí"), h("span", { className: "aia-chip aia-tone-world" }, h(StatusGlyph, { tone: "world" }), "1 čeká na svět"))),
    h("div", { className: "aia-panel", style: { overflowX: "auto" } },
      h("table", { className: "aia-table is-comfortable", "aria-label": "Studie napříč klienty" },
        h("thead", null, h("tr", null, ["Studie", "Fáze", "Stav", "Co je potřeba", "Čeká / běží", ""].map(function (c, i) { return h("th", { key: i }, c); }))),
        groups.map(function (g) {
          var rows = PORTFOLIO.filter(function (r) { return r.status && appearance("WorkflowRunStatus", r.status).tone === g.key; });
          if (!rows.length) return null;
          return h("tbody", { key: g.key },
            h("tr", null, h("td", { colSpan: 6, style: { background: "var(--surface-sunken)", height: 28 } }, h("span", { className: "aia-label" }, g.title + " · " + rows.length), g.note ? h("span", { className: "aia-caption" }, " — " + g.note) : null)),
            rows.map(rowFor));
        }),
        h("tbody", null, h("tr", null, h("td", { colSpan: 6, style: { background: "var(--surface-sunken)", height: 28 } }, h("span", { className: "aia-label" }, "Stav nedostupný · 1"), h("span", { className: "aia-caption" }, " — server odpověď nevrátil; neukazujeme odhad"))),
          PORTFOLIO.filter(function (r) { return !r.status; }).map(rowFor)))));
}

/* ---------------- 2. Study overview ---------------- */
var STUDY_STAGES = st(["DONE", "DONE", "DONE", "DONE_WITH_WARNINGS", "DONE", "DONE", { status: "WAITING_CREDITS", note: "čeká na výdaj" }, "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED"]);
function StudyOverview(p) {
  return h(AppShell, { active: "study", scope: h(StudyScope, {}) },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { className: "aia-title" }, "Důvěra v digitální bankovnictví 2026"), h("div", { className: "aia-row" }, h(Button, { icon: "revision" }, "Historie revizí"), h(Button, { icon: "export" }, cs.actions.export))),
    h(StageRail, { lifecycle: "research", stages: STUDY_STAGES, current: 6, summary: "6 hotovo · 1 čeká na vás · 6 nezahájeno" }),
    h("div", { className: "aia-parked", role: "status" }, h(StatusGlyph, { tone: "you", size: 18 }),
      h("div", { style: { flex: 1, minWidth: 240 } }, h("strong", null, "Výběrový plán čeká na vás 2 d 4 h. "), "Respondenti (1 204 osob, respondent_model) potřebují rezervaci 4 900 USD; v rozpočtu zbývá 3 098,66 USD."),
      h(Button, null, "Otevřít žádost o výdaj")),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" } },
      h(Section, { title: "Rozpočet" }, h(BudgetMeter, { limit: 12000, spent: 7420.5, uncertain: 0.84, reserved: 1480, currency: "USD" })),
      h(Section, { title: "Brány a schválení" }, h("ol", { className: "aia-tl" },
        [["Metodika výzkumu", "DONE", "Schválila " + PEOPLE.ph + " · 14. 9."], ["Dotazník", "DONE_WITH_WARNINGS", "Schválil " + PEOPLE.mk + " · 2 výhrady k otázce Q7"], ["Výdaj na respondenty", "WAITING_CREDITS", "Čeká na vedoucí studie"], ["Report — QA a podpis", "NOT_STARTED", "Až po analýze"]].map(function (g, i) {
          var a = appearance("StageStatus", g[1]);
          return h("li", { key: i }, h("span", { style: { color: a.tone === "you" ? "var(--status-you-ink)" : undefined } }, h(StatusGlyph, { tone: a.tone })), h("div", null, h("div", { style: { fontWeight: 500 } }, g[0]), h("div", { className: "aia-caption" }, a.label + " · " + g[2])), h("span", null));
        }))),
      h(Section, { title: "Tým" }, h("table", { className: "aia-table" }, h("tbody", null,
        [[PEOPLE.jd, "LEAD", "vy"], [PEOPLE.tb, "RESEARCHER", ""], [PEOPLE.ph, "REVIEWER", "nezávislá recenzentka"], [PEOPLE.es, "VIEWER", "jen na této studii"]].map(function (m, i) {
          return h("tr", { key: i }, h("td", null, m[0]), h("td", null, cs.role[m[1]]), h("td", { className: "aia-caption" }, m[2]));
        })))),
      h(Section, { title: "Nedávná aktivita" }, h("ol", { className: "aia-tl" },
        [["revision", "Revize 14: změna cílové skupiny (18–79 → 18–75)", PEOPLE.tb, "20. 9. 11:02"], ["check", "Dimenze hotovo · 11 dimenzí, fingerprint beze změny", "systém", "20. 9. 11:40"], ["parked", "Výběrový plán zaparkován: rozpočet nestačí", "systém", "20. 9. 11:41"], ["missing", "Odhad času analýzy: chybí (backend neposkytuje)", "systém", "—"]].map(function (a, i) {
          return h("li", { key: i }, h(Icon, { name: a[0], size: 14 }), h("div", null, a[1], h("div", { className: "aia-caption" }, a[2])), h("span", { className: "aia-caption aia-num" }, a[3]));
        })))));
}

/* ---------------- 3. Research Studio — a stage page ---------------- */
function ResearchStage(p) {
  return h(AppShell, { active: "study", scope: h(StudyScope, { revision: 14 }) },
    h(StageRail, { lifecycle: "research", stages: st(["DONE", "DONE", "DONE", "DONE_WITH_WARNINGS", { status: "RUNNING", note: "běží 3 min 12 s" }, "READY", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED"]), current: 4, narrow: p.narrow }),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "minmax(0, 1.4fr) minmax(300px, 1fr)", alignItems: "start" } },
      h("div", { className: "aia-stack", style: { gap: 16 } },
        h(Section, { title: "05 · Cílová skupina", right: h("span", { className: "aia-row" }, h("span", { className: "aia-mono aia-muted", style: { fontSize: 12 } }, "fp:7c1e…a90b"), h(Button, { compact: true, icon: "revision" }, "Upravit")) },
          h("div", { className: "aia-stack", style: { gap: 10 } },
            h("div", { className: "aia-label aia-muted" }, "Zadání (brief) — zdroj pravdy"),
            h("p", { style: { margin: 0, maxWidth: "68ch" } }, "Dospělí obyvatelé ČR ve věku 18–75 let, kteří mají alespoň jeden běžný účet a za posledních 12 měsíců použili mobilní bankovnictví. Kvóty podle kraje, věku a vzdělání dle ČSÚ 2021."),
            h("div", { style: { border: "1px dashed var(--border-strong)", padding: "10px 12px", background: "var(--surface-sunken)" } },
              h("div", { className: "aia-row", style: { marginBottom: 4 } }, h("span", { className: "aia-label" }, "Návrh asistenta"), h("span", { className: "aia-caption" }, "design_model · Claude API · neschváleno")),
              h("p", { style: { margin: 0 } }, "Zvažte samostatnou kvótu pro obyvatele obcí do 2 000 obyvatel — v Deep Research se ukázalo, že digitální adopce se tam liší o 11 p. b. ", h("span", { className: "aia-caption" }, "(tvrzení asistenta; zdroj: artefakt Deep Research §3.2)")),
              h("div", { className: "aia-row", style: { marginTop: 8 } }, h(Button, { compact: true }, "Převzít do zadání"), h(Button, { compact: true, variant: "quiet" }, "Zahodit"))))),
        h(ImpactPreview, { lifecycle: "research", stageIds: R_IDS, field: "Cílová skupina: věk 18–79 → 18–75",
          preview: { root_stage: "AUDIENCE", invalidate: ["AUDIENCE", "DIMENSIONS", "SAMPLE_PLAN", "FIELDWORK", "AGGREGATION", "VALIDATION", "ANALYSIS", "REPORT", "DELIVERY"], preserve: ["BRIEF", "DEEP_RESEARCH", "RESEARCH_DESIGN", "QUESTIONNAIRE"], presentation_only: false },
          artifactsKept: 17, costEstimate: [310, 460], costBasis: "posledních 3 běhů fáze Respondenti", timeEstimate: null })),
      h("div", { className: "aia-stack", style: { gap: 16 } },
        h(RunTimeline, { status: "RUNNING", runId: "run_01J8ZK3Q", elapsed: 192, heartbeat: 4, waitingOn: "odpověď design_model (Claude API)", steps: [
          { name: "Načtení zadání a dimenzí", status: "SUCCEEDED", elapsed: 2 }, { name: "Návrh segmentů", status: "SUCCEEDED", elapsed: 61 },
          { name: "Kontrola proti ČSÚ 2021", status: "RUNNING", elapsed: 129, attempt: 2, detail: "1. pokus: přetížený poskytovatel" }, { name: "Kvóty podle krajů", status: "BLOCKED" }, { name: "Uložení artefaktu", status: "BLOCKED" }] }),
        h(Section, { title: "Artefakty fáze", flush: true }, h("table", { className: "aia-table" }, h("tbody", null,
          [["audience-definition.json", "rev 14", "DONE"], ["segment-proposal.md", "rev 14", "RUNNING"], ["quota-matrix.csv", "rev 13", "INVALIDATED"]].map(function (a, i) {
            return h("tr", { key: i }, h("td", null, h(Icon, { name: "artifact", size: 14 }), " ", h("span", { className: "aia-mono", style: { fontSize: 12 } }, a[0])), h("td", { className: "aia-mono aia-muted", style: { fontSize: 12 } }, a[1]), h("td", null, h(StatusChip, { kind: "StageStatus", value: a[2], small: true })));
          })))),
        h(ProviderChoice, { provider: "claude_code_subscription", reason: "kvóta vyčerpána pro krok Kontrola proti ČSÚ.", resumeAt: "18:00", policy: "CLAUDE_CODE_THEN_API", alternative: "anthropic", alternativeCost: 12 }))));
}

/* ---------------- 4. Simulation Studio ---------------- */
function SimulationStudio(p) {
  var c = CLIENTS[1];
  var worlds = [["Svět A · seed 1107", "SUCCEEDED", "4 812 simulovaných domácností"], ["Svět B · seed 2291", "SUCCEEDED", "4 812"], ["Svět C · seed 3048", "FAILED", "neplatná struktura výstupu v kroku 3"], ["Svět D · seed 4410", "RECOVERY_REQUIRED", "0,31 USD nejisté"]];
  return h(AppShell, { active: "study", scope: h(ScopeBar, { clientId: c.id, accent: c.accent, code: c.code, client: c.name, study: "Tarif pro domácnosti — cenová citlivost", studyStatus: "ACTIVE", revision: 6, role: "RESEARCHER" }) },
    h(StageRail, { lifecycle: "simulation", stages: st(["DONE", "DONE", "DONE", "DONE", "DONE", "DONE", "DONE", { status: "FAILED", note: "1 ze 4 světů selhal" }, "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED"]), current: 7 }),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", alignItems: "start" } },
      h(Section, { title: "04 · Kontrakt scénáře", right: h(StatusChip, { kind: "StageStatus", value: "DONE", small: true }) },
        h("dl", { className: "aia-dl" },
          h("dt", null, "Baseline"), h("dd", null, "Současný tarif: 4,20 Kč/kWh, paušál 120 Kč"),
          h("dt", null, "Změna"), h("dd", null, "Dynamický tarif: 3,10–6,80 Kč/kWh podle hodiny"),
          h("dt", null, "Výstup"), h("dd", null, h("strong", null, "Rozdíl proti baseline"), " — absolutní úrovně kontrakt nepovoluje"),
          h("dt", null, "Interpolace"), h("dd", null, "Zakázána: každá varianta se modeluje samostatně"))),
      h(Section, { title: "07 · Varianty" }, h("table", { className: "aia-table" },
        h("thead", null, h("tr", null, h("th", null, "Varianta"), h("th", null, "Cena špička"), h("th", null, "Stav"))),
        h("tbody", null, [["V1 — mírná", "5,20 Kč", "DONE"], ["V2 — střední", "6,00 Kč", "DONE"], ["V3 — ostrá", "6,80 Kč", "DONE"]].map(function (v, i) {
          return h("tr", { key: i }, h("td", null, v[0]), h("td", { className: "aia-num" }, v[1]), h("td", null, h(StatusChip, { kind: "StageStatus", value: v[2], small: true })));
        })))),
      h(Section, { title: "08 · Simulované světy", right: h("span", { className: "aia-caption" }, "2 / 4 hotovo · 1 selhal · 1 rozhodnutí") }, h("ol", { className: "aia-tl" },
        worlds.map(function (w, i) {
          var a = appearance("StepRunStatus", w[1]);
          return h("li", { key: i, className: a.tone === "recovery" ? "aia-wash-recovery" : a.tone === "fault" ? "aia-wash-fault" : undefined, style: { paddingLeft: 8, paddingRight: 8 } }, h(StatusGlyph, { tone: a.tone }), h("div", null, h("div", { style: { fontWeight: 500 } }, w[0]), h("div", { className: "aia-caption", style: a.tone === "recovery" ? { color: "inherit" } : null }, a.label + " · " + w[2])), h("span", null));
        }))),
      h(Section, { title: "09 · Zmrazené výsledky — rozdíl proti baseline", right: h("span", { className: "aia-caption" }, "zatím ze 2 světů") },
        h("table", { className: "aia-table" },
          h("thead", null, h("tr", null, h("th", null, "Ukazatel"), h("th", { className: "r" }, "V1"), h("th", { className: "r" }, "V2"), h("th", { className: "r" }, "V3"))),
          h("tbody", null,
            h("tr", null, h("td", null, "Přesun spotřeby mimo špičku"), h("td", { className: "r" }, h(Value, { value: 4.1, format: function (v) { return "+" + fmtPct(v); }, role: "MODELED_BEHAVIOR_PRIOR" })), h("td", { className: "r" }, h(Value, { value: 7.8, format: function (v) { return "+" + fmtPct(v); }, role: "MODELED_BEHAVIOR_PRIOR" })), h("td", { className: "r" }, h(Value, { value: 9.2, format: function (v) { return "+" + fmtPct(v); }, role: "MODELED_BEHAVIOR_PRIOR" }))),
            h("tr", null, h("td", null, "Ochota přejít k dodavateli"), h("td", { className: "r" }, h(Value, { value: 0, format: fmtPct, role: "MODELED_BEHAVIOR_PRIOR" })), h("td", { className: "r" }, h(Value, { value: 2.3, format: function (v) { return "+" + fmtPct(v); }, role: "MODELED_BEHAVIOR_PRIOR" })), h("td", { className: "r" }, h(Value, { state: "na" }))),
            h("tr", null, h("td", null, "Domácnosti s tepelným čerpadlem"), h("td", { className: "r" }, h(Value, { state: "suppressed" })), h("td", { className: "r" }, h(Value, { state: "suppressed" })), h("td", { className: "r" }, h(Value, { state: "suppressed" }))))),
        h("div", { className: "aia-caption", style: { marginTop: 8 } }, "Všechny simulační výstupy jsou modelované (□). Světy C a D chybí — výsledky se nezprůměrují, dokud nejsou doplněny nebo vědomě vyřazeny.")),
      h(RecoveryDecision, { step: "Svět D · krok 3", provider: "anthropic", at: "14:22:07", amount: 0.31, currency: "USD" })));
}
/* ---------------- 5. Results workspace ---------------- */
var RESP = [
  ["#04 812", "Praha", "35–44", "VŠ", 1, 7.2, "MEASURED_JOINT"], ["#04 813", "Jihomoravský", "55–64", "SŠ", 0, 3.1, "MODELED_BEHAVIOR_PRIOR"],
  ["#04 814", "Ústecký", "18–24", "ZŠ", 1, null, null], ["#04 815", "Zlínský", "45–54", "SŠ", 0, 0, "MEASURED_JOINT"], ["#04 816", "Karlovarský", "65–75", "VŠ", null, 5.4, "UNKNOWN"]
];
function Results(p) {
  return h(AppShell, { active: "results", scope: h(StudyScope, { status: "IN_REVIEW", revision: 14 }) },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { className: "aia-title" }, "Výsledky"), h("div", { className: "aia-row" }, h(Button, { icon: "export" }, "Export XLSX"), h(Button, { icon: "export" }, "Export grafů (SVG)"))),
    h(Section, { title: "Hlavní odpověď" }, h(HeadlineAnswer, { question: "Kolik klientů by přešlo k bance s plně digitální hypotékou?", answer: "Čtyři z deseti dospělých by převedli hlavní účet, nejvíc lidé do 34 let; nad 55 let je ochota výrazně nižší.", figure: 41.7, role: "CALIBRATED_CORE", n: 1204, interval: [38.9, 44.5],
      findings: [{ text: "Rozhodujícím faktorem je vyřízení bez pobočky (63,2 %).", role: "CALIBRATED_CORE" }, { text: "Skupina 55+ vykazuje ochotu kolem 28 %.", role: "MODELED_BEHAVIOR_PRIOR" }, { text: "Souvislost s důvěrou v pojišťovny je vztah mezi bloky dotazníku — nejde o tutéž osobu.", role: "UNKNOWN" }] })),
    h("div", { className: "aia-row", role: "toolbar", "aria-label": "Filtry" },
      ["Region: vše", "Věk: vše", "Vzdělání: vše", "Klient banky: ano/ne"].map(function (f, i) { return h(Button, { key: i, compact: true }, f); }),
      h("span", { className: "aia-scope-spacer" }), h(EvidenceLegend, {})),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", alignItems: "start" } },
      h(Section, { title: "Ochota převést účet podle věku" }, h(GradedBars, { id: "res", label: "Ochota převést účet podle věku", rows: [
        { label: "18–34", value: 52.3, lo: 48.9, hi: 55.6, role: "CALIBRATED_CORE" }, { label: "35–54", value: 44.1, lo: 41.0, hi: 47.3, role: "CALIBRATED_CORE" }, { label: "55+", value: 27.8, role: "MODELED_BEHAVIOR_PRIOR" },
        { label: "Kraj Vysočina", state: "suppressed" }, { label: "Bez odpovědi", value: null }] }),
        h("div", { className: "aia-caption" }, "n = 1 204 · ▣ kalibrované jádro s 95% intervalem · □ modelováno · potlačeno: n < 30 · Zobrazit jako tabulku")),
      h(Section, { title: "Průzkumník respondentů", flush: true, right: h("span", { className: "aia-caption" }, "hustota: kompaktní") },
        h("div", { className: "aia-compact", style: { overflowX: "auto" } }, h("table", { className: "aia-table", "aria-label": "Respondenti" },
          h("thead", null, h("tr", null, ["ID", "Kraj", "Věk", "Vzdělání", "Přejde", "Důvěra 0–10"].map(function (c, i) { return h("th", { key: i, className: i >= 4 ? "r" : undefined }, c); }))),
          h("tbody", null, RESP.map(function (r, i) {
            return h("tr", { key: i, className: i === 0 ? "is-selected" : undefined }, h("td", { className: "aia-mono", style: { fontSize: 12 } }, r[0]), h("td", null, r[1]), h("td", { className: "aia-num" }, r[2]), h("td", null, r[3]),
              h("td", { className: cx("r", r[4] == null && "aia-cell-na") }, r[4] == null ? h(Value, { state: "na" }) : r[4] ? "ano" : "ne"),
              h("td", { className: cx("r", r[5] == null && "aia-cell-na") }, h(Value, { value: r[5], digits: 1, role: r[5] == null ? undefined : r[6] })));
          })))),
        h("div", { className: "aia-caption", style: { padding: "6px 10px" } }, "Syntetičtí respondenti. #04 815 má důvěru 0 (změřeno); #04 814 hodnotu nemá (chybí); u #04 816 nedorazila evidenční role."))));
}

/* ---------------- 6. Sociomapa — three modes ---------------- */
var MAP_NODES = [
  { id: "a", label: "Mobilní app", x: 140, y: 110, role: "MEASURED_JOINT", cluster: 0 }, { id: "b", label: "Poplatky", x: 220, y: 170, role: "MEASURED_JOINT", cluster: 0 },
  { id: "c", label: "Pobočka", x: 470, y: 90, role: "CALIBRATED_CORE", cluster: 1 }, { id: "d", label: "Bezpečnost", x: 400, y: 220, role: "CALIBRATED_CORE", cluster: 1, moved: { x: 360, y: 280 } },
  { id: "e", label: "Hypotéka online", x: 170, y: 270, role: "MODELED_BEHAVIOR_PRIOR", cluster: 0, moved: { x: 110, y: 300 } }, { id: "f", label: "Doporučení", x: 540, y: 250, role: "UNKNOWN", cluster: 2 },
  { id: "g", label: "Značka", x: 300, y: 60, role: "MEASURED_JOINT", cluster: 2, moved: { x: 300, y: 40 } }
];
var MAP_EDGES = [{ a: "a", b: "b", w: 0.8 }, { a: "a", b: "e", w: 0.5 }, { a: "c", b: "d", w: 0.7 }, { a: "b", b: "d", w: 0.2 }, { a: "g", b: "c", w: 0.4 }, { a: "d", b: "f", w: 0.3, crossBlock: true }, { a: "e", b: "b", w: 0.3 }];
function SociomapaPage(p) {
  var mode = p.mode || "matrix";
  var labels = ["Mobilní app", "Poplatky", "Pobočka", "Bezpečnost", "Hypotéka online"];
  var M = [[1, .62, -.21, .18, .44], [.62, 1, -.08, .05, .31], [-.21, -.08, 1, .38, null], [.18, .05, .38, 1, .12], [.44, .31, null, .12, 1]];
  var cellFill = function (v) { if (v == null) return null; var i = Math.round((v + 1) / 2 * 6); return "var(--viz-div-" + (i + 1) + ")"; };
  return h(AppShell, { active: "map", scope: h(StudyScope, { status: "IN_REVIEW" }) },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { className: "aia-title" }, "Sociomapa"), h("span", { className: "aia-caption" }, "Pohledy nemění výsledky. Originály jsou neměnné.")),
    h("div", { className: "aia-tabs", role: "tablist" }, [["matrix", "Matice"], ["compare", "Srovnání"], ["whatif", "Co-když"]].map(function (t) { return h("button", { key: t[0], role: "tab", className: "aia-tab", "aria-selected": mode === t[0] ? "true" : "false" }, t[1]); })),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "minmax(0, 1.5fr) minmax(280px, 1fr)", alignItems: "start" } },
      mode === "whatif"
        ? h(Sociomap, { label: "Sociomapa s vrstvou co-když", nodes: MAP_NODES.concat([{ id: "w", label: "Nový tarif (co-když)", x: 250, y: 220, whatif: true, cluster: 0 }]), edges: MAP_EDGES.concat([{ a: "w", b: "a", w: 0.4 }]), whatif: "„Poplatky −30 %“", overrideBy: PEOPLE.tb, showOverrides: false })
        : mode === "compare"
          ? h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8 } },
              h("div", null, h("div", { className: "aia-label", style: { marginBottom: 4 } }, "Klienti banky (n = 612)"), h(Sociomap, { label: "Klienti", nodes: MAP_NODES, edges: MAP_EDGES, showOverrides: false })),
              h("div", null, h("div", { className: "aia-label", style: { marginBottom: 4 } }, "Neklienti (n = 592)"), h(Sociomap, { label: "Neklienti", nodes: MAP_NODES.map(function (n, i) { return Object.assign({}, n, { x: n.x + (i % 2 ? 30 : -20), y: n.y + (i % 3 ? -15 : 25), moved: null }); }), edges: MAP_EDGES, showOverrides: false })))
          : h(Sociomap, { label: "Sociomapa objektů", nodes: MAP_NODES, edges: MAP_EDGES, overrideBy: PEOPLE.tb + " 21. 9.", selected: "d", clusters: [{ x: 180, y: 190, rx: 110, ry: 110 }, { x: 440, y: 160, rx: 90, ry: 110 }] }),
      h("div", { className: "aia-stack", style: { gap: 16 } },
        h(Section, { title: "Matice souvislostí", flush: true },
          h("table", { className: "aia-table", "aria-label": "Korelační matice" },
            h("thead", null, h("tr", null, h("th", null, ""), labels.map(function (l, i) { return h("th", { key: i, className: "r", title: l }, String(i + 1)); }))),
            h("tbody", null, M.map(function (row, i) {
              return h("tr", { key: i }, h("td", null, (i + 1) + " " + labels[i]), row.map(function (v, j) {
                var strong = v != null && Math.abs(v) > 0.4 && i !== j;
                return h("td", { key: j, className: cx("r", v == null && "aia-cell-na"), style: v == null ? null : { background: cellFill(v), color: strong ? "var(--surface-raised)" : "var(--ink)" } }, i === j ? "—" : v == null ? h(Value, { state: "na" }) : fmtNum(v, 2));
              }));
            }))),
          h("div", { className: "aia-caption", style: { padding: "6px 10px" } }, "Diverging: modrá záporná, oranžová kladná, šedý střed = 0. Pobočka × Hypotéka: chybí (otázky v různých blocích, na téže osobě nezměřeno).")),
        h(Section, { title: "Vybraný uzel: Bezpečnost" },
          h("dl", { className: "aia-dl" },
            h("dt", null, "Evidenční role"), h("dd", null, h(EvidenceMark, { role: "CALIBRATED_CORE" }), " " + cs.evidence.CALIBRATED_CORE.name),
            h("dt", null, "Poloha"), h("dd", null, "Upravený pohled (posunuto) — originál ", h("span", { className: "aia-mono" }, "(400, 220)")),
            h("dt", null, "Upravil"), h("dd", null, PEOPLE.tb + " · 21. 9. 14:10")),
          h("div", { className: "aia-row", style: { marginTop: 8 } }, h(Button, { compact: true }, cs.actions.reset), h(Button, { compact: true, variant: "quiet" }, "Zobrazit jen originál"))))));
}

/* ---------------- 7. Data Library / Society Intelligence ---------------- */
function DataLibrary(p) {
  var steps = [["Příjem zdrojů", "DONE", "14 zdrojů"], ["Návrh evidence", "DONE_WITH_WARNINGS", "38 návrhů · 1 zdroj selhal"], ["Lidské schválení", "WAITING_USER", "2 čekají na vás"], ["Materializace dimenzí", "NOT_STARTED", ""], ["Revize populace", "NOT_STARTED", "LIVE v17.4 → v17.5"]];
  return h(AppShell, { active: "library", scope: h(ScopeBar, { above: true, note: "Data Library · společná znalost organizace — neobsahuje data klientů", role: "LEAD" }) },
    h("h1", { className: "aia-title" }, "Society Intelligence — schvalovací fronta"),
    h("ol", { className: "aia-rail", style: { gridTemplateColumns: "repeat(5, minmax(0,1fr))", listStyle: "none", margin: 0, padding: 0 } }, steps.map(function (s, i) {
      var a = appearance("StageStatus", s[1]);
      return h("li", { key: i, className: cx("aia-rail-cell", "t-" + a.tone) }, h("span", { className: "aia-rail-idx" }, h(StatusGlyph, { tone: a.tone, size: 12 }), String(i + 1)), h("span", { className: "aia-rail-name" }, s[0]), h("span", { className: "aia-rail-state" }, a.label + (s[2] ? " · " + s[2] : "")));
    })),
    h(Section, { title: "Návrhy evidence ke schválení", flush: true, right: h("span", { className: "aia-caption" }, "AI navrhuje, člověk rozhoduje") }, h("div", { className: "aia-scroll-x" },
      h("table", { className: "aia-table is-comfortable" },
        h("thead", null, h("tr", null, ["Návrh", "Zdroj a úryvek", "Navrhovaná dimenze", "Licence", "Stav", ""].map(function (c, i) { return h("th", { key: i }, c); }))),
        h("tbody", null,
          h("tr", { className: "aia-wash-you" }, h("td", null, h("strong", null, "Podíl domácností s chytrým měřičem"), h("div", { className: "aia-caption" }, "ev_0412 · navrhl analysis_model")),
            h("td", null, "ERÚ, Zpráva o trhu 2025, s. 41", h("div", { className: "aia-caption", style: { maxWidth: 320 } }, "„…instalováno v 612 tis. odběrných míst, tj. 11,4 % domácností…“")),
            h("td", null, "energie.smart_meter", h("div", { className: "aia-caption" }, "kategorie · kraj × typ obce")), h("td", null, h("span", { className: "aia-chip aia-tone-done aia-chip-sm" }, h(StatusGlyph, { tone: "done", size: 12 }), "Otevřená data")),
            h("td", null, h(StatusChip, { kind: "StageStatus", value: "WAITING_USER", small: true })), h("td", null, h("div", { className: "aia-row", style: { flexWrap: "nowrap" } }, h(Button, { compact: true }, "Zamítnout"), h(Button, { compact: true, variant: "primary" }, "Schválit")))),
          h("tr", { className: "aia-wash-you" }, h("td", null, h("strong", null, "Důvěra v banky podle věku"), h("div", { className: "aia-caption" }, "ev_0419 · navrhl analysis_model")),
            h("td", null, "Průzkum agentury (PDF), tab. 3", h("div", { className: "aia-caption" }, "„důvěřuje: 18–34 58 %, 35–54 49 %…“")),
            h("td", null, "finance.trust_banks"), h("td", null, h("span", { className: "aia-chip aia-tone-you aia-chip-sm" }, h(StatusGlyph, { tone: "you", size: 12 }), "REVIEW_REQUIRED")),
            h("td", null, h(StatusChip, { kind: "StageStatus", value: "WAITING_USER", small: true })), h("td", null, h("span", { className: "aia-caption" }, "Nejdřív ověřte licenci"))),
          h("tr", { className: "aia-wash-fault" }, h("td", null, h("strong", null, "Mobilní pokrytí obcí"), h("div", { className: "aia-caption" }, "ev_0421")), h("td", null, "CTU_pokryti_2025.xlsx", h("div", { className: "aia-caption" }, "Extrakce textu selhala: soubor je chráněný heslem")),
            h("td", null, h(Value, { state: "na" })), h("td", null, h(Value, { state: "na" })), h("td", null, h(StatusChip, { kind: "FailureClass", value: "SCHEMA_VIOLATION", small: true }, "Extrakce selhala")), h("td", null, h(Button, { compact: true }, "Nahrát znovu"))))))),
    h("div", { className: "aia-world" }, h(Icon, { name: "population" }), h("div", null, h("strong", null, "Revize populace se nevytvoří automaticky. "), "Po schválení a materializaci vznikne návrh revize v17.5; LIVE zůstává v17.4, dokud ji vedoucí nepřepne. Studie běžící na v17.4 se nezmění.")));
}

/* ---------------- 8. Cost and budget ---------------- */
var LEDGER = [
  { at: "22. 9. 14:22:07", id: "led_9f31c2", step: "fieldwork.batch#12", role: "respondent_model", provider: "anthropic", model: "claude-sonnet-5", inTok: 18420, outTok: 6210, amount: 0.8412, status: "SETTLED_UNCERTAIN" },
  { at: "22. 9. 14:21:40", id: "led_9f31c1", step: "fieldwork.batch#11", role: "respondent_model", provider: "anthropic", model: "claude-sonnet-5", inTok: 18377, outTok: 6190, amount: 0.8391, status: "SETTLED" },
  { at: "22. 9. 14:21:02", id: "led_9f31c0", step: "fieldwork.batch#13", role: "respondent_model", provider: "anthropic", model: "claude-sonnet-5", inTok: 18400, outTok: null, amount: null, status: "RESERVED" },
  { at: "22. 9. 13:58:11", id: "led_9f31b7", step: "sample_plan.quota", role: "design_model", provider: "claude_code_subscription", model: "claude-opus-5-5", inTok: 42110, outTok: 3904, amount: 0, status: "SETTLED" },
  { at: "22. 9. 13:40:55", id: "led_9f31a2", step: "analysis.dry_run", role: "analysis_model", provider: "anthropic", model: "claude-opus-5-5", inTok: 9020, outTok: 0, amount: 0.12, status: "RELEASED" }
];
function CostBudget(p) {
  return h(AppShell, { active: "cost", scope: h(StudyScope, {}) },
    h("h1", { className: "aia-title" }, "Náklady a rozpočet"),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(440px, 1fr))", alignItems: "start" } },
      h("div", { className: "aia-stack", style: { gap: 16 } },
        h(Section, { title: "Rozpočet studie" }, h(BudgetMeter, { limit: 12000, spent: 7420.5, uncertain: 0.84, reserved: 1480, currency: "USD" })),
        h(RecoveryDecision, { step: "Respondenti · dávka 12", provider: "anthropic", at: "14:22:07", amount: 0.84, currency: "USD" }),
        h("div", null, h("div", { className: "aia-row", style: { justifyContent: "space-between", marginBottom: 8 } }, h("h2", { className: "aia-h" }, "Záznamy o využití AI"), h("div", { className: "aia-row" }, h("span", { className: "aia-caption" }, "neměnné · řazeno podle času"), h(Button, { compact: true, icon: "export" }, "CSV"))),
          h(UsageLedger, { rows: LEDGER }),
          h("div", { className: "aia-caption", style: { marginTop: 6 } }, "0,00 USD u Claude Code = předplatné, nikoli „zdarma“; tokeny se evidují. Výstupní tokeny u rezervace: chybí, volání ještě neskončilo."))),
      h("div", { style: { background: "var(--surface-sunken)", padding: 16, display: "grid", placeItems: "center" } },
        h(ParkAndAsk, { clientId: CLIENTS[0].id, accent: 1, client: CLIENTS[0].name, study: "Důvěra v digitální bankovnictví 2026", what: "Fáze Respondenti: 1 204 syntetických respondentů, 1 dotazník (38 otázek)", modelRole: "respondent_model", provider: "anthropic", amount: 4900, basis: "horní odhad, rezervuje se před voláním", remaining: 3098.66, limit: 12000, currency: "USD", canApprove: true }))));
}
/* ---------------- 9. Report and Delivery ---------------- */
function ReportDelivery(p) {
  var qa = [["Každé číslo má evidenční roli", "DONE"], ["Modelované hodnoty označeny v textu", "DONE"], ["EXTERNAL_HOLDOUT_PENDING uveden na stránce", "DONE"], ["Buňky n < 30 potlačeny", "DONE"], ["Tvrzení mezi bloky neprezentována jako tatáž osoba", "DONE_WITH_WARNINGS"], ["Lidský podpis", "WAITING_USER"]];
  return h(AppShell, { active: "report", scope: h(StudyScope, { status: "IN_REVIEW", role: p.sod ? "LEAD" : "REVIEWER" }) },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { className: "aia-title" }, "Report a předání"), h("span", { className: "aia-mono aia-muted" }, "report rev 9 · fp:2b90…41de")),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(520px, 1fr))", alignItems: "start" } },
      h("div", { className: "aia-grid", style: { gridTemplateColumns: "minmax(140px, 220px) minmax(0, 1fr)", alignItems: "start" } },
        h(ReportCover, { client: CLIENTS[0].name, title: ["Důvěra spotřebitelů", "v digitální bankovnictví"], subtitle: "Výzkumná zpráva pro vedení · září 2026", date: "22. 9. 2026", revision: 9, pages: 38, signedBy: "čeká na podpis" }),
        h(ReportPage, { tight: true })),
      h("div", { className: "aia-stack", style: { gap: 16 } },
        h(Section, { title: "QA brána", right: h("span", { className: "aia-caption" }, "5 / 6 · 1 výhrada") }, h("ol", { className: "aia-tl" }, qa.map(function (q, i) {
          var a = appearance("StageStatus", q[1]);
          return h("li", { key: i }, h("span", { style: { color: a.tone === "you" ? "var(--status-you-ink)" : undefined } }, h(StatusGlyph, { tone: a.tone })), h("div", null, q[0], h("div", { className: "aia-caption" }, a.label)), h("span", null));
        }))),
        h(ApprovalPanel, { what: "Report rev 9 — 38 stran, 12 obrázků, 7 tabulek", fingerprint: "fp:2b90c7…41de · vychází z analýzy rev 14", producer: PEOPLE.jd, producerIsViewer: !!p.sod, selfAllowed: false, policySource: "default",
          eligible: [PEOPLE.ph + " (recenzentka)", PEOPLE.mk + " (vedoucí jiné studie klienta)"], checks: { passed: 23, total: 24, warnings: 1, modelled: 4, pending: true },
          audit: [{ icon: "artifact", text: "Report rev 9 vygenerován (report_polish_model · Claude API)", at: "22. 9. 09:14" }, { icon: "gate", text: "QA brána: 23 / 24 kontrol, 1 výhrada", at: "22. 9. 09:15" }, { icon: "signoff", text: "Čeká na podpis nezávislého recenzenta", at: "—" }] }),
        h(Section, { title: "Export" }, h("table", { className: "aia-table" }, h("tbody", null,
          [["PDF", "Vektorové grafy a písma vložena; evidenční značky jako vektor", "Připraveno"], ["DOCX", "Grafy jako SVG + PNG 300 dpi záloha; evidenční značky jako vložená vektorová grafika (písma je neobsahují)", "Připraveno"], ["XLSX příloha", "Sloupec evidenční role u každého čísla", "Připraveno"]].map(function (e, i) {
            return h("tr", { key: i }, h("td", null, h("strong", null, e[0])), h("td", { className: "aia-caption" }, e[1]), h("td", null, h(Button, { compact: true, icon: "export" }, e[0])));
          }))), h("div", { className: "aia-caption", style: { marginTop: 6 } }, "Export je dostupný i před podpisem jako interní koncept s vodoznakem „NESCHVÁLENO“. Předání klientovi až po podpisu.")))));
}

/* ---------------- 10. Admin ---------------- */
function Admin(p) {
  var perms = Object.keys(cs.permission);
  var RP = {
    VIEWER: ["VIEW_STUDY", "VIEW_RESULTS"], REVIEWER: ["VIEW_STUDY", "VIEW_RESULTS", "VIEW_COSTS", "APPROVE_GATE", "SIGN_OFF_DELIVERABLE"],
    RESEARCHER: ["VIEW_STUDY", "VIEW_RESULTS", "VIEW_COSTS", "EDIT_STUDY", "RUN_WORKFLOW", "CANCEL_WORKFLOW", "UPLOAD_DATA", "EXPORT_DELIVERABLE"], LEAD: perms
  };
  return h(AppShell, { active: "admin", scope: h(ScopeBar, { above: true, note: "Správa organizace · změny se zapisují do auditu", role: "LEAD" }) },
    h("h1", { className: "aia-title" }, "Správa"),
    h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", alignItems: "start" } },
      h(Section, { title: "Klienti", flush: true }, h("table", { className: "aia-table is-comfortable" },
        h("thead", null, h("tr", null, ["Klient", "Akcent", "Stav", "Studie", "Rozpočet celkem"].map(function (c, i) { return h("th", { key: i }, c); }))),
        h("tbody", null, CLIENTS.map(function (c, i) {
          return h("tr", { key: c.id }, h("td", null, h("div", { className: "aia-row", style: { flexWrap: "nowrap" } }, h(ClientMonogram, { clientId: c.id, accent: c.accent, code: c.code, name: c.name }), c.name)), h("td", { className: "aia-mono aia-muted", style: { fontSize: 12 } }, "slot " + c.accent + (clientAccentIndex(c.id) !== c.accent ? " · hash by dal " + clientAccentIndex(c.id) : "")),
            h("td", null, h(StatusChip, { kind: "ClientStatus", value: i === 4 ? "DORMANT" : "ACTIVE", small: true })), h("td", { className: "aia-num" }, [3, 2, 2, 2, 1][i]), h("td", null, i === 3 ? h(Value, { state: "na" }) : h(Money, { value: [36000, 18000, 22500, 0, 6000][i], digits: 0 })));
        })))),
      h(Section, { title: "Politika samoschválení", right: h("span", { className: "aia-caption" }, "studie > klient > organizace > výchozí") }, h("table", { className: "aia-table" },
        h("thead", null, h("tr", null, h("th", null, "Úroveň"), h("th", null, "Nastavení"), h("th", null, "Výsledek"))),
        h("tbody", null,
          h("tr", null, h("td", null, "Výchozí"), h("td", null, "zakázáno"), h("td", { className: "aia-caption" }, "nezávislá kontrola")),
          h("tr", null, h("td", null, "Organizace AIA"), h("td", null, h("span", { className: "aia-caption" }, "zdědit")), h("td", { className: "aia-caption" }, "zakázáno (výchozí)")),
          h("tr", null, h("td", null, "Klient Lékárny Salvia"), h("td", null, h("strong", null, "povoleno")), h("td", null, "povoleno (klient)")),
          h("tr", null, h("td", null, "Studie Cena léků"), h("td", null, h("strong", null, "zakázáno")), h("td", null, "zakázáno (studie přebíjí klienta)")))),
        h("div", { className: "aia-caption", style: { marginTop: 6 } }, "Samoschválení nikdy nepřidá oprávnění, které člověk nemá. Každé schválení zapisuje zdroj politiky.")),
      h(Section, { title: "Role a oprávnění", flush: true, style: { gridColumn: "1 / -1" } }, h("div", { style: { overflowX: "auto" } }, h("table", { className: "aia-table" },
        h("thead", null, h("tr", null, h("th", null, "Oprávnění"), ["VIEWER", "REVIEWER", "RESEARCHER", "LEAD"].map(function (r) { return h("th", { key: r, style: { textAlign: "center" } }, cs.role[r]); }))),
        h("tbody", null, perms.map(function (pm) {
          return h("tr", { key: pm }, h("td", null, cs.permission[pm], " ", h("span", { className: "aia-enum" }, pm)), ["VIEWER", "REVIEWER", "RESEARCHER", "LEAD"].map(function (r) {
            var has = RP[r].indexOf(pm) >= 0;
            return h("td", { key: r, style: { textAlign: "center" } }, has ? h(Icon, { name: "check", size: 14, label: "ano" }) : h("span", { className: "aia-faint", "aria-label": "ne" }, "·"));
          }));
        }))))),
      h(Section, { title: "Přístupy ke studii Důvěra 2026", flush: true }, h("table", { className: "aia-table" }, h("tbody", null,
        [[PEOPLE.jd, "LEAD", "klient"], [PEOPLE.tb, "RESEARCHER", "klient"], [PEOPLE.ph, "REVIEWER", "studie"], [PEOPLE.es, "VIEWER", "studie — zúženo z LEAD na klientovi"]].map(function (g, i) {
          return h("tr", { key: i }, h("td", null, g[0]), h("td", null, cs.role[g[1]]), h("td", { className: "aia-caption" }, "grant: " + g[2]));
        })))),
      h(Section, { title: "Rozpočty studií", flush: true }, h("table", { className: "aia-table" },
        h("thead", null, h("tr", null, h("th", null, "Studie"), h("th", { className: "r" }, "Limit"), h("th", { className: "r" }, "Utraceno"), h("th", { className: "r" }, "Nejisté"))),
        h("tbody", null,
          h("tr", null, h("td", null, "Důvěra 2026"), h("td", { className: "r" }, h(Money, { value: 12000, digits: 0 })), h("td", { className: "r" }, h(Money, { value: 7420.5 })), h("td", { className: "r", style: { color: "var(--status-fault)", fontWeight: 600 } }, h(Money, { value: 0.84 }))),
          h("tr", null, h("td", null, "Věrnostní program 2027"), h("td", { className: "r" }, h(Money, { value: 8000, digits: 0 })), h("td", { className: "r" }, h(Money, { value: 6112.1 })), h("td", { className: "r" }, h(Money, { value: 0 }))),
          h("tr", null, h("td", null, "Roaming mimo EU"), h("td", { className: "r" }, h(Value, { state: "na" })), h("td", { className: "r" }, h(Value, { state: "na" })), h("td", { className: "r" }, h(Value, { state: "na" }))))))));
}

/* ---------------- 11. The state gallery ---------------- */
function GalleryGroup(p) {
  return h("section", { "aria-label": p.title, style: { display: "grid", gap: 8 } }, h("h2", { className: "aia-h" }, p.title), p.note ? h("p", { className: "aia-caption", style: { margin: 0, maxWidth: "90ch" } }, p.note) : null, p.children);
}
function StateGallery(p) {
  var enumGrid = function (kind) {
    return h("div", { className: "aia-gallery" }, DOMAIN_ENUMS[kind].map(function (v) {
      var a = appearance(kind, v);
      return h("div", { key: v, className: "aia-gallery-cell" }, h(StatusChip, { kind: kind, value: v }), h("span", { className: "aia-enum" }, v), h("span", { className: "aia-caption" }, cs.tone[a.tone]));
    }));
  };
  var missing = checkTotality();
  return h("div", { className: "aia", style: { padding: 16, display: "grid", gap: 24 } },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { className: "aia-title" }, "Galerie stavů"),
      h("span", { className: cx("aia-chip", missing.length ? "aia-tone-fault" : "aia-tone-done") }, h(StatusGlyph, { tone: missing.length ? "fault" : "done" }), missing.length ? "Chybí mapování: " + missing.join(", ") : "Všechny mapy stavů jsou úplné vůči doménovým enumům")),
    h(GalleryGroup, { title: "Pět stavů, které musí být poznat přes místnost", note: "Tvar nese stav, barva ho jen posiluje. Odstín signálu = stroj pracuje. Jantar = zaparkováno na člověku (rezervováno jen pro to). Břidlice s přerušovaným rámem = čeká na svět. Červená s × = selhalo. Inverzní blok se šrafou = rozhodnutí o penězích." },
      h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 8 } },
        [["running", "WorkflowRunStatus", "RUNNING"], ["you", "WorkflowRunStatus", "AWAITING_BUDGET"], ["world", "WorkflowRunStatus", "WAITING_PROVIDER"], ["fault", "WorkflowRunStatus", "FAILED"], ["recovery", "WorkflowRunStatus", "RECOVERY_REQUIRED"]].map(function (s) {
          return h("div", { key: s[0], className: cx("aia-gallery-cell", s[0] === "you" && "aia-wash-you", s[0] === "recovery" && "aia-wash-recovery", s[0] === "world" && "aia-wash-world", s[0] === "fault" && "aia-wash-fault", s[0] === "running" && "aia-wash-running"), style: { minHeight: 96 } },
            h(StatusGlyph, { tone: s[0], size: 32 }), h(StatusChip, { kind: s[1], value: s[2] }), h("span", { className: "aia-caption", style: s[0] === "recovery" ? { color: "inherit" } : null }, cs.tone[s[0]]));
        }))),
    h(GalleryGroup, { title: "StageStatus — fáze" }, enumGrid("StageStatus")),
    h(GalleryGroup, { title: "WorkflowRunStatus — běh", note: "AWAITING_* = člověk dluží rozhodnutí (jantar). WAITING_* = systém dluží kapacitu (břidlice). WAITING_PROVIDER a WAITING_CAPACITY sdílejí tvar, liší se textem a časem obnovení." }, enumGrid("WorkflowRunStatus")),
    h(GalleryGroup, { title: "StepRunStatus — krok" }, enumGrid("StepRunStatus")),
    h(GalleryGroup, { title: "AttemptStatus — pokus" }, enumGrid("AttemptStatus")),
    h(GalleryGroup, { title: "ReservationStatus — rezervace", note: "SETTLED_UNCERTAIN má tvar rozhodnutí: peníze mohly odejít." }, enumGrid("ReservationStatus")),
    h(GalleryGroup, { title: "StudyStatus · ClientStatus · ProjectStatus" }, enumGrid("StudyStatus"), enumGrid("ClientStatus"), enumGrid("ProjectStatus")),
    h(GalleryGroup, { title: "FailureClass — proč pokus selhal", note: "Zaparkovatelné třídy (kvóta, kapacita) mají tvar čekání; rozpočet a schválení tvar „čeká na vás“; ostatní jsou selhání." }, enumGrid("FailureClass")),
    h(GalleryGroup, { title: "Neznámá hodnota", note: "Hodnota, kterou mapa nezná, se nikdy nevykreslí neutrálně." }, h("div", { className: "aia-row" }, h(StatusChip, { kind: "StageStatus", value: "PAUSED_BY_ADMIN" }), h("span", { className: "aia-caption" }, "← budoucí stav, který UI zatím nezná"))),
    h(GalleryGroup, { title: "Evidenční role — jedna gramatika v každém měřítku", note: "Achromatické: přežije černobílý tisk a nekoliduje se stavem ani s daty. Neznámá role nikdy nedostane nejsilnější značku." },
      h("div", { className: "aia-panel", style: { overflowX: "auto" } }, h("table", { className: "aia-table" },
        h("thead", null, h("tr", null, ["Role", "Číslo", "Buňka (kompaktní)", "Řada v grafu", "Uzel mapy", "Věta v reportu"].map(function (c, i) { return h("th", { key: i }, c); }))),
        h("tbody", null, EVIDENCE_ROLES.concat(["UNKNOWN"]).map(function (r) {
          var node = r === "MEASURED_JOINT" ? h("circle", { cx: 10, cy: 10, r: 6, fill: "var(--viz-cat-1)" }) : r === "CALIBRATED_CORE" ? h("g", null, h("circle", { cx: 10, cy: 10, r: 7, fill: "none", stroke: "var(--viz-cat-1)", strokeWidth: 1.5 }), h("circle", { cx: 10, cy: 10, r: 4, fill: "var(--viz-cat-1)" })) : r === "MODELED_BEHAVIOR_PRIOR" ? h("circle", { cx: 10, cy: 10, r: 6, fill: "none", stroke: "var(--viz-cat-1)", strokeWidth: 2 }) : h("g", null, h("circle", { cx: 10, cy: 10, r: 6, fill: "none", stroke: "var(--ink)", strokeDasharray: "2 2" }), h("text", { x: 10, y: 13, fontSize: 8, textAnchor: "middle", fill: "var(--ink)", fontWeight: 700 }, "?"));
          var line = r === "MEASURED_JOINT" || r === "CALIBRATED_CORE" ? "none" : r === "MODELED_BEHAVIOR_PRIOR" ? "6 3" : "1.5 3";
          return h("tr", { key: r }, h("td", null, h("div", { style: { fontWeight: 500 } }, cs.evidence[r].name), h("span", { className: "aia-enum" }, r)),
            h("td", null, h(Value, { value: 41.7, format: fmtPct, role: r })),
            h("td", { className: "aia-compact" }, h(Value, { value: 0.412, digits: 3, role: r })),
            h("td", null, h("svg", { width: 90, height: 20, "aria-hidden": "true" }, h("path", { d: "M2 15 L30 9 L58 12 L88 4", fill: "none", stroke: "var(--viz-cat-1)", strokeWidth: 2, strokeDasharray: line }), r === "CALIBRATED_CORE" ? [2, 30, 58, 88].map(function (x, i) { return h("rect", { key: i, x: x - 2.5, y: [15, 9, 12, 4][i] - 2.5, width: 5, height: 5, fill: "var(--viz-cat-1)" }); }) : null)),
            h("td", null, h("svg", { width: 20, height: 20, "aria-hidden": "true" }, node)),
            h("td", { style: { fontFamily: "var(--font-serif)" } }, h(EvidenceMark, { role: r }), " ", r === "MODELED_BEHAVIOR_PRIOR" ? "…je ochota nižší (modelováno)." : r === "EXTERNAL_HOLDOUT_PENDING" ? "Externí validace dosud neproběhla." : r === "UNKNOWN" ? "…role nedorazila — nečíst jako měření." : "…převedlo 41,7 % dospělých."));
        })))),
      h("div", { className: "aia-caption" }, "Pravidlo pro husté tabulky: sloupec deklaruje roli v záhlaví (např. „Podíl ▣“) a buňka nese značku jen tehdy, když se od sloupce liší. Vztah mezi bloky: přerušená hrana a text „mezi bloky — nejde o tutéž osobu“.")),
    h(GalleryGroup, { title: "Nula není chybějící hodnota, neznámé není neutrální" },
      h("div", { className: "aia-panel", style: { overflowX: "auto" } }, h("table", { className: "aia-table is-comfortable" },
        h("thead", null, h("tr", null, ["Stav", "Inline", "Buňka", "Význam"].map(function (c, i) { return h("th", { key: i }, c); }))),
        h("tbody", null,
          h("tr", null, h("td", null, cs.nulls.value), h("td", null, h(Value, { value: 1204 })), h("td", { className: "r" }, h(Value, { value: 38.4, format: fmtPct })), h("td", { className: "aia-caption" }, cs.nulls.valueLong)),
          h("tr", null, h("td", null, cs.nulls.zero), h("td", null, h(Value, { value: 0 })), h("td", { className: "r" }, h(Value, { value: 0, format: fmtPct })), h("td", { className: "aia-caption" }, cs.nulls.zeroLong)),
          h("tr", null, h("td", null, "Chybí"), h("td", null, h(Value, { state: "na" })), h("td", { className: "r aia-cell-na" }, h(Value, { state: "na" })), h("td", { className: "aia-caption" }, cs.nulls.naLong + " Plná inkoustová barva a šrafa — nikdy slabší než špatná hodnota.")),
          h("tr", null, h("td", null, "Potlačeno"), h("td", null, h(Value, { state: "suppressed", showReason: true })), h("td", { className: "r" }, h(Value, { state: "suppressed" })), h("td", { className: "aia-caption" }, cs.nulls.suppressedLong + " — malý vzorek (n < 30) nebo oprávnění. Důvod v popisku i v legendě.")),
          h("tr", null, h("td", null, cs.nulls.loading), h("td", null, h(Value, { state: "loading" })), h("td", { className: "r" }, h(Value, { state: "loading" })), h("td", { className: "aia-caption" }, "Čekáme na odpověď serveru. Bez třpytu a bez odhadu; po 10 s se změní na „chybí“ s tlačítkem Načíst znovu."))))),
      h("div", { className: "aia-row" }, h("span", { className: "aia-caption" }, "Peníze bez hodnoty:"), h(Money, { value: null }), h("span", { className: "aia-caption" }, "· peníze nula:"), h(Money, { value: 0 }))),
    h(GalleryGroup, { title: "Stavová lišta fází — obě životní cesty, všechny stavy" },
      h(StageRail, { lifecycle: "research", stages: st(["DONE", "DONE_WITH_WARNINGS", "INVALIDATED", "READY", "RUNNING", "WAITING_USER", "WAITING_CREDITS", "WAITING_CAPACITY", "FAILED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED"]), current: 4 }),
      h(StageRail, { lifecycle: "simulation", stages: st(["DONE", "DONE", "DONE", "DONE", "DONE", "DONE", "DONE", { status: "RUNNING", note: "2 / 4 světy" }, "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED"]), current: 7, narrow: true })),
    h(GalleryGroup, { title: "Zaparkováno, odmítnuto, obnova" },
      h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" } },
        h("div", { className: "aia-parked" }, h(StatusGlyph, { tone: "you", size: 18 }), h("div", null, h("strong", null, "Čeká na vás 2 d 4 h. "), "Schválit výdaj 4 900 USD.")),
        h("div", { className: "aia-world" }, h(StatusGlyph, { tone: "world", size: 18 }), h("div", null, h("strong", null, "Čeká na poskytovatele. "), "Kvóta Claude Code se obnoví v 18:00. Nic dělat nemusíte.")),
        h("div", { style: { border: "1.5px solid var(--ink)", padding: "10px 12px", background: "var(--surface-sunken)" } }, h("div", { className: "aia-row", style: { fontWeight: 600 } }, h(Icon, { name: "gate" }), cs.approval.sodTitle), h("div", { className: "aia-caption" }, "Oddělení povinností — navržený stav, ne chybová hláška.")),
        h("div", { style: { border: "1px solid var(--border-strong)", padding: "10px 12px" } }, h("div", { style: { fontWeight: 600 } }, "Studie nenalezena"), h("div", { className: "aia-caption" }, "Buď neexistuje, nebo k ní nemáte přístup. Záměrně nerozlišujeme (404, ne 403) — potvrzení existence by prozradilo zakázku jiného klienta.")),
        h(RecoveryDecision, { step: "Respondenti · dávka 12", provider: "anthropic", at: "14:22:07", amount: 0.84, currency: "USD" }))),
    h(GalleryGroup, { title: "Prázdné a načítací plochy", note: "Motiv: pole bodů. Prázdný stav říká, co chybí a kdo to může doplnit; načítání ukazuje jen to, co skutečně víme." },
      h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" } },
        h("div", { className: "aia-panel aia-panel-b aia-stack" }, h(Lattice, { cols: 36, rows: 5 }), h("strong", null, "Zatím žádní respondenti"), h("span", { className: "aia-caption" }, "Fáze Respondenti nezačala: čeká na schválení výdaje ve Výběrovém plánu.")),
        h("div", { className: "aia-panel aia-panel-b aia-stack" }, h("div", { className: "aia-row aia-caption" }, h("span", { className: "aia-live" }), "Načítání portfolia · 1,4 s"), h("span", { className: "aia-caption" }, "Žádná kostra, žádný třpyt: zobrazujeme skutečný čas čekání."))),
      h("div", { className: "aia-divider", "aria-hidden": "true" })),
    h(GalleryGroup, { title: "Rozsah — klient a hranice", note: "Akcent klienta je deterministický (FNV-1a z id klienta, 6 akcentů) a objevuje se jen v rámu rozsahu. Obrazovky napříč klienty mají šrafovaný inkoustový pás." },
      h("div", { className: "aia-stack", style: { gap: 8 } },
        h(ScopeBar, { clientId: CLIENTS[0].id, accent: 1, code: "BH", client: CLIENTS[0].name, study: "Důvěra v digitální bankovnictví 2026", studyStatus: "ACTIVE", revision: 14, role: "LEAD" }),
        h(ScopeBar, { clientId: CLIENTS[1].id, accent: 2, code: "EM", client: CLIENTS[1].name, study: "Tarif pro domácnosti — cenová citlivost", studyStatus: "ACTIVE", revision: 6, role: "RESEARCHER" }),
        h(ScopeBar, { clientId: CLIENTS[2].id, accent: 4, code: "SL", client: CLIENTS[2].name, study: "Věrnostní program 2025", studyStatus: "DELIVERED", revision: 11, role: "VIEWER", deliveredAt: "12. 6. 2025" }),
        h(ScopeBar, { above: true, note: "Portfolio · 5 klientů", role: "LEAD" }))),
    h(GalleryGroup, { title: "Oprávnění — čtenář vs. výzkumník", note: "Chybějící oprávnění = chybějící akce, ne zašedlé tlačítko. Výjimka: akce, jejíž přítomnost je informace (výdaj schvaluje vedoucí)." },
      h("div", { className: "aia-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" } },
        h("div", { className: "aia-panel" }, h("div", { className: "aia-panel-h" }, h("strong", null, "Výzkumník"), h("div", { className: "aia-row" }, h(Button, { compact: true }, cs.actions.edit), h(Button, { compact: true }, cs.actions.export))), h("div", { className: "aia-panel-b" }, "Cílová skupina: 18–75, běžný účet, mobilní bankovnictví.")),
        h("div", { className: "aia-panel" }, h("div", { className: "aia-panel-h" }, h("strong", null, "Čtenář")), h("div", { className: "aia-panel-b" }, "Cílová skupina: 18–75, běžný účet, mobilní bankovnictví.")))),
    h(GalleryGroup, { title: "Revize" }, h(RevisionBanner, { viewing: 12, current: 14, when: "před 2 dny" })));
}

/* ---------------- Alternate direction B — "Editorial" ---------------- */
function DirectionB(p) {
  var vars = { "--surface": "#f6f1e7", "--surface-raised": "#fbf7ef", "--surface-sunken": "#efe8da", "--border": "#ddd3c1", "--font-sans": "var(--font-serif)" };
  return h("div", { style: vars }, h("div", { className: "aia", style: { padding: 16, display: "grid", gap: 12, background: "#f6f1e7" } },
    h("div", { className: "aia-row", style: { justifyContent: "space-between" } }, h("h1", { style: { fontFamily: "var(--font-display)", fontSize: 30, lineHeight: "34px", margin: 0, fontWeight: 600 } }, "Co dnes potřebuje vás"), h("span", { className: "aia-caption" }, "Směr B — Editorial · srovnávací pass")),
    h("div", { className: "aia-panel", style: { overflowX: "auto" } }, h("table", { className: "aia-table is-comfortable" },
      h("thead", null, h("tr", null, ["Studie", "Fáze", "Stav", "Co je potřeba", "Čeká"].map(function (c, i) { return h("th", { key: i, style: { fontFamily: "var(--font-serif)" } }, c); }))),
      h("tbody", null, PORTFOLIO.slice(0, 6).map(function (r, i) {
        var c = CLIENTS[r.c];
        return h("tr", { key: i }, h("td", { style: { fontFamily: "var(--font-serif)", fontSize: 15 } }, r.study, h("div", { className: "aia-caption" }, c.name)), h("td", null, cs.stages[r.life][r.stage]), h("td", null, h(StatusChip, { kind: "WorkflowRunStatus", value: r.status, small: true })), h("td", null, r.need || "—"), h("td", { className: "aia-num" }, r.since));
      })))),
    h("p", { className: "aia-caption", style: { margin: 0, maxWidth: "80ch" } }, "Silnější na reportu, slabší v hustých tabulkách: serifové číslice v tabulce Portfolia ztrácejí rytmus, teplý papír snižuje odstup jantarového stavu od podkladu a na 13px se serif v češtině (háčky nad ř, č) slévá. Proto A pro Studio, B jen jako hlas Deliverable.")));
}
var AIA = {
  cs: cs, ICONS: ICONS, DOMAIN_ENUMS: DOMAIN_ENUMS, TONE: TONE, checkTotality: checkTotality, appearance: appearance,
  fmtNum: fmtNum, fmtMoney: fmtMoney, fmtPct: fmtPct, fmtDuration: fmtDuration, clientAccentIndex: clientAccentIndex,
  Icon: Icon, StatusGlyph: StatusGlyph, StatusChip: StatusChip, EvidenceMark: EvidenceMark, Value: Value, EvidenceLegend: EvidenceLegend,
  Money: Money, Button: Button, Kbd: Kbd, Mark: Mark, Wordmark: Wordmark, Lattice: Lattice, ClientMonogram: ClientMonogram, ScopeBar: ScopeBar,
  StageRail: StageRail, RunTimeline: RunTimeline, ImpactPreview: ImpactPreview, BudgetMeter: BudgetMeter, ParkAndAsk: ParkAndAsk,
  ProviderChoice: ProviderChoice, RecoveryDecision: RecoveryDecision, UsageLedger: UsageLedger, ApprovalPanel: ApprovalPanel,
  RevisionBanner: RevisionBanner, RevisionHistory: RevisionHistory, HeadlineAnswer: HeadlineAnswer, Sociomap: Sociomap, GradedBars: GradedBars,
  ReportCover: ReportCover, ReportPage: ReportPage,
  Portfolio: Portfolio, StudyOverview: StudyOverview, ResearchStage: ResearchStage, SimulationStudio: SimulationStudio, Results: Results,
  SociomapaPage: SociomapaPage, DataLibrary: DataLibrary, CostBudget: CostBudget, ReportDelivery: ReportDelivery, Admin: Admin,
  StateGallery: StateGallery, DirectionB: DirectionB,
  fixtures: { R_IDS: R_IDS, S_IDS: S_IDS, CLIENTS: CLIENTS, LEDGER: LEDGER, MAP_NODES: MAP_NODES, MAP_EDGES: MAP_EDGES, STUDY_STAGES: STUDY_STAGES }
};
window.AIA = AIA;
})();
