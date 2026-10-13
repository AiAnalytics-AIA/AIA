// Presentation explanations only. Permission, effective values and validation stay in the API.
export const TAB_GUIDE: Record<string, { purpose: string; action: string }> = {
  ai: { purpose: "Co AI umí a co je zapnuté", action: "Zkontrolujte dostupné schopnosti. Model a přepínače spravuje nasazení; rozpočty upravíte u studií." },
  prompts: { purpose: "Jaké instrukce dostávají agenti", action: "Vyberte agenta, upravte jeho instrukci a uložte ji jako verzi. Běžet začne až po zapnutí; úloha už zadaná si nechá instrukci, se kterou byla zadána." },
  deep_research: { purpose: "Zdroje, náklady a pravidla rešerše", action: "Navrhněte hodnotu pravidla a pak ji schvalte; platí pro běhy zařazené po schválení. Ochrany v kódu (robots.txt, žádné přihlášení ani paywall, osobní údaje, třída dat C) vypnout nejdou." },
  methodology: { purpose: "Jak se počítají mapy a statistiky", action: "Projděte výpočet nebo upravte jeho parametry. Návrh zkontrolujte, porovnejte a uložte; v platnost vstoupí až po aktivaci." },
  access: { purpose: "Členové, role a schvalování", action: "Spravujte členy a stav klientů. Pravidla samoschválení mohou platit pro organizaci, klienta nebo jedinou studii." },
  studies: { purpose: "Stav studií a limity útraty", action: "Vyhledejte studii a stiskněte Upravit. Rozpočet je maximální celková útrata studie v USD." },
  audit: { purpose: "Kdo co změnil a kdy", action: "Vyhledejte událost, osobu nebo důvod změny. Historie je pouze ke čtení." },
  reference: { purpose: "Technické hodnoty a pevná pravidla", action: "Tyto hodnoty nejsou běžné uživatelské volby. U každé zjistíte její účel a zda změnu spravuje nasazení nebo kód." },
};

export const SETTING_HELP: Record<string, string> = {
  env: "Rozlišuje vývojové, testovací a produkční prostředí této instance.",
  version: "Verze serverového API pro diagnostiku a podporu.",
  debug: "Podrobnější diagnostika serveru. Nemění výzkumné výsledky.",
  database_backend: "Typ databáze, ve které AIA ukládá pracovní obsah a historii.",
  identity_provider: "Služba, která ověřuje přihlášení. Oprávnění ke změnám nadále určuje AIA.",
  cognito_configured: "Zda server má nastavené údaje pro ověření přihlášení; neukazuje žádné tajné hodnoty.",
  cognito_token_use: "Typ přihlašovacího tokenu, který server přijímá.",
  cors_origins: "Webové adresy, ze kterých mohou prohlížeče volat API.",
  max_request_bytes: "Největší tělo jednoho požadavku, které server přijme.",
  log_level: "Podrobnost provozních záznamů používaných při hledání chyb.",
  log_format: "Formát provozních záznamů pro správce serveru.",
  docs_enabled: "Zda tato instance zpřístupňuje interaktivní dokumentaci API.",
  members: "Členové organizace a jejich role. Přidání člena mu zpřístupní její klienty a studie.",
  clients: "Klientské pracovní prostory. Nový klient se zakládá v adresáři klientů.",
  client_status: "Označuje klienta jako aktivního, neaktivního nebo archivovaného.",
  membership_is_access: "Přístup vychází z členství v organizaci; samostatné udělování přístupu ke studii není potřeba.",
  studies: "Výzkumy a simulace založené pod klienty organizace.",
  study_status: "Označuje pracovní stav konkrétní studie.",
  study_budget: "Tvrdý strop celkové placené útraty jedné studie; není to očekávaná ani již utracená cena.",
  no_spend_past_budget: "Před placeným voláním se ověřuje dostupný rozpočet. Tento dohled nelze vypnout.",
  self_approval: "Zda autor může schválit vlastní návrh. Nejpřesnější pravidlo pro studii má přednost před klientem a organizací.",
  default_self_approval: "Výchozí pravidlo, použité jen tam, kde není konkrétnější nastavení.",
  single_model_call_path: "Veškerá placená AI volání procházejí společnou kontrolou rozpočtu a dat.",
  no_silent_provider_fallback: "Systém při selhání nepřepne model nebo poskytovatele bez předepsané cesty.",
  configuration_is_not_verification: "Zapnutí v konfiguraci samo o sobě nepotvrzuje úspěšné spojení s modelem.",
  eu_residency: "Pravidlo, že data zůstávají v povolené evropské oblasti.",
  egress_fails_closed: "Přenos mimo povolené hranice se odmítne, pokud ho nelze doložit.",
  lease_seconds: "Jak dlouho worker vlastní přidělený krok, než je potřeba jeho vlastnictví obnovit.",
  capacity_backoff_seconds: "Jak dlouho čeká další pokus, když není volná kapacita poskytovatele.",
  quota_fallback_seconds: "Jak dlouho se odloží práce po vyčerpání kvóty poskytovatele.",
  max_attempts: "Maximální počet pokusů o provedení jednoho kroku.",
  no_fake_progress: "Průběh ukazuje skutečný stav práce; procenta se nevymýšlejí.",
  dataset_id: "Identifikátor sady dat, kterou daná konfigurace používá.",
  static_reference: "Referenční populace pro porovnání a kalibraci.",
  live_population: "Aktuální schválená populace dostupná novým běhům.",
  field_policy_version: "Verze pravidel určujících, která pole lze použít ve výzkumu.",
  population_bound_once_per_run: "Běh si při spuštění připne populaci; pozdější změny ho nepřepočítají.",
  min_cell: "Nejmenší počet pozorování pro zobrazení buňky výsledku.",
  n_guard: "Pod tímto efektivním počtem pozorování se výsledek potlačí místo zobrazení nejistého čísla.",
  indicative: "Hranice, od které lze číslo uvést jako orientační hodnotu.",
  min_layer_donors: "Nejmenší počet skutečných dárců dat potřebný pro danou vrstvu.",
  indicative_layer_donors: "Počet dárců, od kterého může být výsledek vrstvy orientační.",
  tier_A_permits: "Jaké závěry smí publikovat nejsilnější důkazní úroveň.",
  tier_B_permits: "Jaké závěry smí publikovat prostřední důkazní úroveň.",
  tier_C_permits: "Jaké závěry smí publikovat omezená důkazní úroveň.",
  no_invented_certainty: "Chybějící důkaz se nesmí nahradit tvrzením jistoty.",
  constants_version: "Verze pevně stanovených hodnot deterministické simulace.",
  default_spec_seed: "Výchozí počáteční hodnota náhodného generátoru pro reprodukovatelné výpočty.",
  no_visualisation_mutation: "Změna pohledu nebo kamery nemění data ani výsledek výpočtu.",
  deep_research_settings: "Schvalované organizační hodnoty pro náklady, zdroje a provádění rešerše.",
  deep_research_catalogue: "Verze seznamu povolených nastavení a jejich mezí.",
  deep_research_harness: "Verze pracovního postupu rešeršních agentů.",
  deep_research_switches_in_deployment: "Připojení a povolení poskytovatele spravuje server; nevkládejte sem API klíče.",
  deep_research_public_sources_only: "Rešerše může číst jen povolené veřejné zdroje, bez obcházení přístupových bariér.",
  deep_research_grounded_findings: "Publikované zjištění musí mít doloženou citaci zachyceného zdroje.",
};

export const DR_GROUP_HELP: Record<string, string> = {
  sign_off: "Schválení vymezuje povolený způsob použití rešerše. Nejde o zapnutí poskytovatele.",
  provider: "Podmínky tarifu, cena požadavků a oprávnění k uchovávání výsledků vyhledávání.",
  budgets: "Limity útraty a rozsahu rešerše. Rozpočet konkrétní studie nadále platí jako společný tvrdý strop.",
  limits: "Maximální velikost a četnost požadavků. Nižší hodnoty snižují zátěž, mohou ale omezit rozsah práce.",
  models: "Schválený lehký model a jeho ceny. Připojení k modelu zůstává v nasazení.",
  quotas: "Ověřené rychlostní kvóty poskytovatele, podle kterých se plánuje souběžná práce.",
  retention: "Jak dlouho se uchovávají podklady a důkazy rešerše.",
  sources: "Pravidla kvality a důvěryhodnosti zdrojů, podle kterých rešerše posuzuje důkazy.",
  extraction: "Omezení a rozsah sběru strukturovaných údajů z veřejných stránek.",
};

const DR_HELP: Record<string, string> = {
  "sign_off.design_and_boundaries": "Souhlas s vymezeným návrhem rešerše a hranicemi jejího použití.",
  "sign_off.adr_0017_amendment": "Souhlas s doplněnými pravidly externího vyhledávání a získávání zdrojů.",
  "provider.search.plan": "Název tarifu účtu pro vyhledávání. Nejde o API klíč ani připojení účtu.",
  "provider.search.terms_url": "Odkaz na podmínky poskytovatele, ze kterých vychází schválení použití.",
  "provider.search.terms_date": "Datum ověření podmínek. Pomáhá dohledat, jaká pravidla byla schválená.",
  "provider.search.price_per_1000": "Cena za tisíc vyhledávacích požadavků, použitá při rezervaci a kontrole nákladů.",
  "provider.search.failed_requests_billed": "Zda poskytovatel účtuje také neúspěšný požadavek. Ovlivňuje započtení jeho nákladů.",
  "provider.search.storage_and_ai_use_granted": "Potvrzení, že daný tarif dovoluje uchovávat výsledky a zpracovat je pomocí AI.",
  "provider.search.query_log_retention": "Informace o uchovávání záznamů dotazů u poskytovatele.",
  "budgets.presets": "Schválení předvoleb, které spojují rozsah práce a limity rešerše.",
  "models.lead.model_id": "Model použitý pro vedení a plánování rešerše. Identifikátor musí splnit pravidla povolené evropské trasy.",
  "models.light.model_id": "Lehčí model pro dílčí rešeršní práci. Jeho výběr může ovlivnit kvalitu a náklady.",
  "models.light.input_price": "Cena za milion vstupních tokenů lehkého modelu pro plánování nákladů.",
  "models.light.output_price": "Cena za milion výstupních tokenů lehkého modelu pro plánování nákladů.",
  "quotas.model_requests_per_minute": "Ověřený počet požadavků, které poskytovatel dovolí za minutu.",
  "quotas.model_input_per_minute": "Ověřený počet vstupních tokenů za minutu; ovlivňuje souběh práce.",
  "retention.snapshots": "Počet dní, po které se uchovávají zachycené zdrojové stránky jako důkaz.",
  "retention.datasets": "Počet dní, po které se uchovávají získané datové sady.",
  "sources.tiers": "Schválení pravidel, která rozdělují zdroje podle jejich důkazní síly.",
  "sources.reputation_register": "Schválení registru reputace zdrojů používaného při posuzování důvěryhodnosti.",
  "sources.confidence_weights": "Schválení vah pro posuzování síly důkazů. Nejsou to váhy respondentů studie.",
  "extraction.denylist": "Schválení seznamu zdrojů, ze kterých se údaje nesmějí získávat.",
  "extraction.personal_data_patterns": "Schválení pravidel pro rozpoznání a odmítnutí osobních údajů při sběru.",
  "extraction.record_presets": "Schválení předvoleb, podle kterých se ze stránek získávají strukturované záznamy.",
};
export function researchPolicyHelp(key: string, group: string): string {
  if (DR_HELP[key]) return DR_HELP[key];
  if (key.startsWith("budgets.run_limit.")) return "Nejvyšší placená cena jednoho běhu v tomto režimu. Společný rozpočet studie může práci zastavit dříve.";
  if (key.endsWith("window_tokens")) return "Největší povolený vstup do jednoho volání tohoto agenta, měřený v tokenech.";
  if (key.endsWith("answer_tokens")) return "Největší povolená odpověď tohoto agenta v tokenech; omezuje délku a náklady výstupu.";
  if (key.includes("connector_calls")) return "Maximální počet volání datových konektorů během jednoho běhu v tomto režimu.";
  if (key.endsWith("triage_reads")) return "Kolik nalezených stránek může běh předběžně přečíst při výběru relevantních zdrojů.";
  if (key.endsWith("crawl_pages")) return "Kolik veřejných stránek může běh procházet při podrobné rešerši.";
  if (key.endsWith("index_queries")) return "Kolik dotazů do indexu zdrojů může provést jeden běh.";
  if (key.endsWith("archive_fetches")) return "Kolik archivovaných stránek může získat jeden běh.";
  if (key.endsWith("pages_per_host")) return "Nejvyšší počet stránek z jedné domény; omezuje soustředění sběru na jediný zdroj.";
  if (key.endsWith("hosts")) return "Nejvyšší počet domén, ze kterých smí běh sbírat strukturované údaje.";
  if (key.endsWith("pages")) return "Nejvyšší celkový počet stránek pro sběr strukturovaných údajů během jednoho běhu.";
  return DR_GROUP_HELP[group] ?? "Organizační pravidlo rešerše. Jeho změna se použije až po schválení nové verze.";
}
