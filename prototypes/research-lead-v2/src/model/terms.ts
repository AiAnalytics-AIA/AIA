// All interface copy in one place, Czech, for localisation. Where the product
// already has a word for something, the prototype uses that word: anchors are
// apps/web/src/i18n/cs.ts lines at develop 50547cdc ("cs:NNNN").
import type { StageId, PhaseId, StageStatusKind } from './types';

export const STAGE_ORDER: StageId[] = ['brief', 'design', 'questionnaire', 'audience', 'dimensions', 'sample', 'fieldwork', 'results', 'sociomap', 'analysis', 'report'];

export const STAGES: Record<StageId, { label: string; short: string; phase: PhaseId; product: string }> = {
  brief: { label: 'Zadání', short: 'Zadání', phase: 'design', product: 'brief' },                      // cs:200
  design: { label: 'Návrh', short: 'Návrh', phase: 'design', product: 'plan' },
  questionnaire: { label: 'Dotazník', short: 'Dotazník', phase: 'design', product: 'questionnaire' },
  audience: { label: 'Cílová skupina', short: 'Cíl. skupina', phase: 'sample', product: 'audience' },
  dimensions: { label: 'Dimenze', short: 'Dimenze', phase: 'sample', product: 'persona' },
  sample: { label: 'Vzorek', short: 'Vzorek', phase: 'sample', product: 'persona (vzorek) + run (kontrola)' },
  fieldwork: { label: 'Sběr dat', short: 'Sběr dat', phase: 'execution', product: 'run + progress' },
  results: { label: 'Výsledky', short: 'Výsledky', phase: 'evidence', product: 'results · Data' },
  sociomap: { label: 'Sociomapa', short: 'Sociomapa', phase: 'evidence', product: 'results · Sociomapy' },
  analysis: { label: 'Analýza', short: 'Analýza', phase: 'interpretation', product: 'results · AI analýza' },
  report: { label: 'Zpráva', short: 'Zpráva', phase: 'delivery', product: 'results · Kompletní zpráva studie' },
};

export const PHASES: { id: PhaseId; label: string }[] = [
  { id: 'design', label: 'Návrh výzkumu' },          // cs:1651
  { id: 'sample', label: 'Vymezení vzorku' },
  { id: 'execution', label: 'Sběr' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'interpretation', label: 'Interpretace' },
  { id: 'delivery', label: 'Předání' },
];

export const STATUS_WORD: Record<StageStatusKind, string> = {
  accepted: 'Přijato',
  working: 'Pracovní úpravy',
  proposal: 'Návrh čeká na vás',
  decision: 'Čeká na vaše rozhodnutí',
  running: 'Běží',
  waiting: 'Čeká na poskytovatele',
  reopened: 'Znovu otevřeno',
  ready: 'Připraveno',
  blocked: 'Čeká na předchozí krok',     // cs:2481 BLOCKED
  notstarted: 'Zatím nic',
  complete: 'Hotovo',
  failed: 'Potřebuje opravu',
  frozen: 'Zmrazeno',
};

export const T = {
  app: {
    product: 'AIA',
    lead: 'Vedoucí výzkumu',
    leadLong: 'AIA · Vedoucí výzkumu',
    prototype: 'Prototyp V2 · neprodukční',
  },
  layout: {
    resize: 'Změnit poměr konverzace a artefaktu',
    resizeHint: 'Táhněte, nebo šipkami. Dvojklik vrátí 40 / 60.',
    normal: 'Běžný režim 40 / 60',
    artifactFocus: 'Soustředit se na artefakt',
    chatFocus: 'Soustředit se na konverzaci',
    backToNormal: 'Zpět na 40 / 60',
    openConversation: 'Otevřít konverzaci',
  },
  header: {
    clients: 'Klienti',
    details: 'Podrobnosti studie',
    pending: (n: number) => 'Čeká na vás: ' + n,
    budget: 'Rozpočet',
    menu: 'Nabídka studie',
    lifecycle: 'Přehled fází',
  },
  conv: {
    sees: 'Vidí',
    latest: 'Na nejnovější',
    newBelow: (n: number) => (n === 1 ? '1 nová zpráva' : n + ' nové zprávy'),
    placeholder: 'Napište Vedoucímu výzkumu…',
    placeholderRef: 'Co se má změnit? Např. „kratší“, „přejmenovat na …“, „odebrat“',
    send: 'Odeslat',
    stop: 'Zastavit',
    attach: 'Přidat soubor nebo odkaz',
    reference: 'Odkázat na prvek artefaktu (@)',
    queueTitle: 'Ve frontě · odešle se, až Vedoucí dokončí práci',
    sendNow: 'Odeslat hned',
    editQueued: 'Upravit',
    removeQueued: 'Odebrat z fronty',
    hint: 'Enter odešle · Shift+Enter nový řádek · ↑ poslední zpráva · @ prvek artefaktu · Esc zastaví',
    autopilot: 'Pracuje sám v rámci schválených oprávnění. Zastaví se u prvního rozhodnutí, které patří vám.',
    follow: 'Navázat',
    copy: 'Kopírovat',
    why: 'Proč tato odpověď (původ)',
    openIn: 'Otevřít v artefaktu',
    historical: (rev: number, cur: number) => 'Platilo pro revizi ' + rev + ' · aktuálně ' + cur,
    stoppedNote: 'Zastaveno vámi. Nic nebylo přijato za vás.',
    groupDone: (n: number) => (n === 1 ? '1 dokončená činnost' : n < 5 ? n + ' dokončené činnosti' : n + ' dokončených činností'),
  },
  activity: {
    lead: 'Vedoucí výzkumu',
    worker: 'Specialista',
    research: 'Hloubkový výzkum',
    compute: 'Deterministický výpočet',
    decision: 'Rozhodnutí člověka',
    lookup: 'Čtení',
    details: 'Podrobnosti',
    review: 'Zkontrolovat',
    open: 'Otevřít',
    running: 'Běží',
  },
  decision: {
    head: 'Čeká na vaše rozhodnutí',
    authorise: 'Čeká na vaše schválení',
    impact: 'Dopad',
    cost: 'Náklady',
    recommended: 'Doporučení Vedoucího · neschváleno',
    decided: (x: string) => 'Rozhodli jste: ' + x,
  },
  artifact: {
    working: 'Pracovní verze',
    proposed: 'Návrh k revizi',
    accepted: 'Přijato',
    frozen: 'Zmrazeno',
    empty: 'Zatím prázdné',
    inspector: 'Inspektor',
    details: 'Vstupy, závislosti a původ',
    history: 'Historie revizí',
    contract: 'Kontrakt pro AI',
    savedWorking: (n: number, rev: number) => (n === 1 ? '1 úprava' : n < 5 ? n + ' úpravy' : n + ' úprav') + ' v pracovní verzi · vychází z revize ' + rev,
    acceptAs: (rev: number) => 'Přijmout jako revizi ' + rev,
    discard: 'Zahodit úpravy',
    leadNoticed: 'Vedoucí výzkumu úpravy vidí',
  },
  proposal: {
    review: 'Zkontrolujte návrh AI',                                 // cs ProposalReview
    nothingChanges: 'Nic se nezmění, dokud návrh nepoužijete.',
    keep: 'Ponechat současný stav',
    apply: 'Použít návrh',
    applyAs: (rev: number) => 'Použít jako revizi ' + rev,
    stale: (base: number, cur: number) => 'Návrh vychází z revize ' + base + ', studie je na revizi ' + cur + '. Použít ho nejde.',
    rebuild: (cur: number) => 'Sestavit znovu nad revizí ' + cur,
    rebuildNote: 'Nové sestavení vytvoří nový návrh. Nic tím nepřijímáte.',
    coverage: 'Pokrytí výzkumných otázek',
    implications: 'Dopad na výzkum a metodiku',
    downstream: 'Co se znovu otevře',
    recompute: 'Přepočet',
  },
  synthetic: {
    short: 'Fiktivní data a zdroje',
    long: 'Respondenti, zjištění, citace a zdroje v této studii jsou smyšlené pro prototyp. Nejsou to fakta o Fio bance.',
    run: 'Fiktivní respondenti (SYNTHETIC_AI_FICTIONAL). Výsledky nesmí ke klientovi.',
  },
  internal: 'Interní · nesmí ke klientovi',                              // cs ObjectMapView
};
