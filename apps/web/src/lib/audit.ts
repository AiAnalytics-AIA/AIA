// How Settings' Audit reads the organization's history (settings-redesign chunk 8): every action
// code by its Czech name, each in one of the redesign's categories, and the period a record falls
// in. Pure; the panel is components/aia/settings/AuditPanel.tsx. A code this file does not know
// still reads as words (its code spelled out) under "Ostatní", never dropped; a record without a
// time is in every period, never filtered out as if it were old.

/** Every action the API writes to the access audit, by its name in Czech. */
export const ACTION_NAMES: Record<string, string> = {
  // Přístup a role
  ORGANIZATION_CREATED: "Založení organizace",
  MEMBER_ADDED: "Přidání nebo úprava člena",
  MEMBER_DEACTIVATED: "Deaktivace člena",
  MEMBER_REACTIVATED: "Opětovná aktivace člena",
  USER_DEACTIVATED: "Deaktivace uživatele",
  MEMBER_ROLE_DENIED: "Odmítnutá změna role",
  IDENTITY_SUBJECT_CLEARED: "Uvolnění přihlašovací identity",
  AIA_SESSION: "Přihlášení do AIA",
  AIA_SESSION_DENIED: "Odmítnuté přihlášení do AIA",
  PERMISSION_DENIED: "Odmítnutá akce",
  SELF_APPROVAL_CONFIGURED: "Nastavení samoschválení",
  SELF_APPROVAL_CHANGED: "Změna samoschválení",
  CLIENT_GRANT: "Záznam přístupu ke klientovi",
  // Peníze
  STUDY_BUDGET_CHANGED: "Změna rozpočtu studie",
  STUDY_SPEND_CONFIRM_CHANGED: "Změna prahu potvrzení",
  CLIENT_BUDGET_CHANGED: "Změna rozpočtu klienta",
  // Klienti a studie
  CLIENT_CREATED: "Založení klienta",
  CLIENT_STATUS_CHANGED: "Změna stavu klienta",
  CLIENT_PROFILE_CHANGED: "Úprava profilu klienta",
  CLIENT_CONTACT_ADDED: "Přidání kontaktu klienta",
  CLIENT_CONTACT_CHANGED: "Úprava kontaktu klienta",
  CLIENT_CONTACT_REMOVED: "Odebrání kontaktu klienta",
  CLIENT_SOURCE_ADDED: "Přidání podkladu klienta",
  CLIENT_SOURCE_REREAD: "Nové přečtení podkladu klienta",
  CLIENT_SOURCE_MARKED_INTERNAL: "Podklad označen jako interní dokument",
  CLIENT_SOURCE_UNMARKED_INTERNAL: "Zrušení označení interní dokument",
  CLIENT_KNOWLEDGE_AUTHORED: "Zápis znalosti klienta",
  CLIENT_KNOWLEDGE_DECIDED: "Rozhodnutí o návrhu znalosti",
  CLIENT_KNOWLEDGE_ORGANIZED: "Zařazení znalosti do složek a štítků",
  CLIENT_KNOWLEDGE_FOLDER_CREATED: "Založení složky znalostí",
  CLIENT_KNOWLEDGE_FOLDER_RENAMED: "Přejmenování složky znalostí",
  CLIENT_KNOWLEDGE_FOLDER_DELETED: "Smazání složky znalostí",
  CLIENT_KNOWLEDGE_LABEL_CREATED: "Založení štítku znalostí",
  CLIENT_KNOWLEDGE_LABEL_CHANGED: "Úprava štítku znalostí",
  CLIENT_KNOWLEDGE_LABEL_DELETED: "Smazání štítku znalostí",
  CLIENT_KNOWLEDGE_SELECTED: "Výběr znalosti pro studii",
  CLIENT_KNOWLEDGE_UNSELECTED: "Zrušení výběru znalosti pro studii",
  STUDY_CREATED: "Založení studie",
  STUDY_STATUS_CHANGED: "Změna stavu studie",
  // Metodika
  METHODOLOGY_PROPOSED: "Nová verze metodiky",
  METHODOLOGY_ACTIVATED: "Uvedení metodiky v platnost",
  METHODOLOGY_RESET: "Návrat metodiky na verzi z kódu",
  // Prompty
  PROMPT_VERSION_CREATED: "Nová verze promptu",
  PROMPT_ACTIVATED: "Zapnutí verze systémového promptu",
  PROMPT_RESET_TO_BASELINE: "Návrat promptu na text z kódu",
  // Deep Research
  DR_SETTING_PROPOSED: "Návrh pravidla rešerše",
  DR_SETTING_APPROVED: "Schválení pravidla rešerše",
  DR_SETTING_WITHDRAWN: "Návrat pravidla rešerše na výchozí",
  DR_SETTING_PROPOSAL_WITHDRAWN: "Stažení návrhu pravidla rešerše",
  DR_SETTING_PROPOSAL_DECLINED: "Zamítnutí návrhu pravidla rešerše",
  DR_TEST_POLICY_PROPOSED: "Návrh testovacích pravidel rešerše",
  DR_TEST_POLICY_APPROVED: "Schválení testovacích pravidel rešerše",
  DR_TEST_POLICY_WITHDRAWN: "Stažení testovacích pravidel rešerše",
  // Vedoucí
  RESEARCH_LEAD_PREFERENCES_SET: "Změna předvoleb Vedoucího",
  LEAD_SEALED: "Vedoucí zapečetěn",
  LEAD_UNSEALED: "Vedoucí odpečetěn",
  LEAD_ERASED: "Vedoucí smazán po lhůtě uchování",
};

export const CATEGORIES = ["method", "access", "money", "clients", "dr", "prompts", "lead", "data", "other"] as const;
export type AuditCategory = (typeof CATEGORIES)[number];

export const CATEGORY_NAMES: Record<AuditCategory, string> = {
  method: "Metodika", access: "Přístup a role", money: "Peníze", clients: "Klienti", dr: "Deep Research",
  prompts: "Prompty", lead: "Vedoucí", data: "Správa dat", other: "Ostatní",
};

const MONEY = new Set(["STUDY_BUDGET_CHANGED", "STUDY_SPEND_CONFIRM_CHANGED", "CLIENT_BUDGET_CHANGED"]);
const ACCESS = new Set([
  "ORGANIZATION_CREATED", "USER_DEACTIVATED", "IDENTITY_SUBJECT_CLEARED", "PERMISSION_DENIED", "CLIENT_GRANT",
]);

/** The category an action is filed under; a code no rule names is "other", still shown. */
export function categoryOf(action: string): AuditCategory {
  if (action.startsWith("METHODOLOGY_")) return "method";
  if (MONEY.has(action) || action.includes("WALLET")) return "money";
  if (action.startsWith("DR_")) return "dr";
  if (action.startsWith("PROMPT_")) return "prompts";
  if (action.startsWith("LEAD_") || action.startsWith("RESEARCH_LEAD_")) return "lead";
  if (action.endsWith("_DELETED") && action.startsWith("CLIENT_") && !action.startsWith("CLIENT_KNOWLEDGE_")) return "data";
  if (ACCESS.has(action) || action.startsWith("MEMBER_") || action.startsWith("AIA_SESSION") || action.startsWith("SELF_APPROVAL_") || action.includes("METODIK") || action.includes("METHODOLOGIST")) return "access";
  if (action.startsWith("CLIENT_") || action.startsWith("STUDY_")) return "clients";
  return "other";
}

/** An action's name in Czech; an unknown code spelled out in words, never hidden. */
export function actionName(action: string): string {
  return ACTION_NAMES[action] ?? action.replaceAll("_", " ").toLocaleLowerCase("cs");
}

export const PERIODS = ["today", "week", "month", "all"] as const;
export type AuditPeriod = (typeof PERIODS)[number];
export const PERIOD_NAMES: Record<AuditPeriod, string> = { today: "Dnes", week: "7 dní", month: "30 dní", all: "Vše" };
const DAY_MS = 86_400_000;

/** Whether a record falls in the period; a record without a time is in every period. */
export function inPeriod(createdAt: string | null, period: AuditPeriod, now: Date): boolean {
  if (period === "all" || createdAt === null) return true;
  const at = Date.parse(createdAt);
  if (Number.isNaN(at)) return true;
  if (period === "today") {
    const day = (d: Date) => new Intl.DateTimeFormat("cs-CZ", { timeZone: "Europe/Prague", dateStyle: "short" }).format(d);
    return day(new Date(at)) === day(now);
  }
  return now.getTime() - at <= (period === "week" ? 7 : 30) * DAY_MS;
}
