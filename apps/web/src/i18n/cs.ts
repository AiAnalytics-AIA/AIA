/**
 * Czech UI copy. Components never hardcode text; every string comes from here.
 * Status and stage vocabulary follows the domain (`aia_core.domain`), never a
 * frontend-invented flow.
 */
export const cs = {
  app: {
    name: "AIA",
    notFound: "Nenalezeno. Buď to neexistuje, nebo k tomu nemáte přístup.",
    tagline: "Agentic AI Analytics",
    fixtureBanner: "Vývojová data — tato obrazovka zatím není napojená na API.",
  },
  theme: { label: "Vzhled", system: "Systém", light: "Světlý", dark: "Tmavý" },
  nav: {
    portfolio: "Portfolio",
    studies: "Studie",
    projectMemory: "Paměť projektů",
    admin: "Správa",
  },
  portfolio: {
    title: "Portfolio",
    subtitle: "Studie napříč klienty, ke kterým máte přístup",
    columns: {
      study: "Studie",
      client: "Klient",
      status: "Stav studie",
      role: "Vaše role",
      modified: "Poslední změna",
    },
    empty: "Žádné studie, ke kterým máte přístup.",
  },
  study: {
    projects: "Projekty",
    noProjects: "Studie zatím nemá žádný projekt.",
    columns: {
      project: "Projekt",
      lifecycle: "Životní cyklus",
      currentStage: "Aktuální fáze",
      status: "Stav projektu",
      revision: "Revize",
    },
    budget: "Rozpočet",
    budgetHidden: "Náklady nejsou pro vaši roli viditelné.",
  },
  project: {
    stages: "Fáze",
    revision: "revize",
    waitingReason: "Důvod čekání",
    artifacts: "Artefakty",
  },
  stage: {
    status: "Stav fáze",
  },
  lifecycle: {
    research: "Výzkum",
    simulation: "Simulace",
  },
  status: {
    stage: {
      NOT_STARTED: "Nezahájeno", READY: "Připraveno", RUNNING: "Běží", WAITING_USER: "Čeká na člověka",
      WAITING_CREDITS: "Čeká na kredity", WAITING_CAPACITY: "Čeká na kapacitu", DONE: "Hotovo",
      DONE_WITH_WARNINGS: "Hotovo s výhradami", INVALIDATED: "Zneplatněno", FAILED: "Selhalo",
    },
    project: {
      DRAFT: "Koncept", READY_TO_CONTINUE: "Připraveno pokračovat", RUNNING: "Běží", WAITING: "Čeká",
      COMPLETED: "Dokončeno", FAILED: "Selhalo", ARCHIVED: "Archivováno", TRASHED: "V koši",
    },
    study: {
      DRAFT: "Koncept", ACTIVE: "Aktivní", IN_REVIEW: "V revizi", DELIVERED: "Předáno", ARCHIVED: "Archivováno", CANCELLED: "Zrušeno",
    },
    client: { ACTIVE: "Aktivní", DORMANT: "Neaktivní", ARCHIVED: "Archivováno" },
  },
  role: { VIEWER: "Čtenář", REVIEWER: "Recenzent", RESEARCHER: "Výzkumník", LEAD: "Vedoucí studie" },
  modelRole: {
    research_model: "Rešerše", design_model: "Návrh", respondent_model: "Respondenti",
    analysis_model: "Analýza", report_polish_model: "Úprava reportu",
  },
  artifacts: {
    title: "Soubory",
    helper: "Verzované vstupy a výstupy (DOCX, XLSX…).",
    upload: "Nahrát",
    noArtifacts: "Zatím žádné soubory.",
    mockUpload: "Vývojové nahrání",
    type: "Typ",
    filename: "Název souboru",
    versionLabel: "Verze",
    save: "Uložit",
    cancel: "Zrušit",
    note: "Vývojové nahrání",
    localOnly: "Ukládá se jen v tomto prohlížeči (localStorage). Úložiště artefaktů zatím nemá HTTP rozhraní.",
    types: {
      input_docx: "Vstupní DOCX", input_xlsx: "Vstupní XLSX", dataset: "Dataset", import_pack: "Import Pack",
      sociomap: "Sociomapa", final_docx: "Finální DOCX", final_pdf: "Finální PDF",
    },
  },
  docEditor: {
    proposalHeading: "Návrh doplnění (asistent, neschváleno)",
    proposalReady: "Návrh změn je připraven",
    proposalHelp: "„Přijmout změny“ použije návrh na celý dokument, „Zamítnout“ ho zahodí.",
    accept: "Přijmout změny",
    reject: "Zamítnout",
    assistant: "Asistent",
    assistantHelp: "Vyberte roli modelu, napište zprávu a asistent připraví návrh změn celého dokumentu. Vývojová simulace — žádné volání modelu neproběhne.",
    modelRole: "Role modelu",
    message: "Zpráva",
    messagePlaceholder: "Popište, co má asistent doplnit nebo upravit (formální čeština)…",
    generate: "Vygenerovat návrh změn",
    lastProposal: "Poslední návrh",
    time: "Čas",
  },
  projectMemory: {
    title: "Paměť projektů",
    body: "Vyhledávání v historických studiích a schválených artefaktech. Zatím není implementováno.",
  },
  admin: {
    clients: "Klienti a studie",
    clientsBody: "Klienti, studie, rozpočty a přístupy. Zatím není napojeno na API.",
    roles: "Role",
    rolesBody: "Organizace: vlastník, správce, člen. Studie: čtenář, recenzent, výzkumník, vedoucí studie.",
  },
  home: {
    title: "AIA",
    intro: "Interní výzkumný systém. Vývojová verze webového klienta.",
    goToPortfolio: "Otevřít portfolio",
  },
} as const;
