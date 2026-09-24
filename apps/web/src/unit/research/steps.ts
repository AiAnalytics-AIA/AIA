// The research flow's steps (ADR 0014, area A4). The rail is RESEARCH_STEPS
// after its final splice (@417490): seven steps. Progress, verify and next are
// routes of the classic router without a rail entry; the rebuilt flow reaches
// them from the steps that lead to them (OI-47).

export const RAIL_STEPS = [
  { key: "brief", num: "1", label: "Zadání", sub: "Co řešíte" },
  { key: "plan", num: "2", label: "Návrh", sub: "Co má výzkum zjistit" },
  { key: "questionnaire", num: "3", label: "Dotazník", sub: "Excel · ručně · AI" },
  { key: "audience", num: "4", label: "Audience / Cílová skupina", sub: "Koho výsledky reprezentují" },
  { key: "persona", num: "5", label: "Dimenze", sub: "Co ovlivňuje odpovědi" },
  { key: "run", num: "6", label: "Kontrola & Spuštění", sub: "AI kontrola a start" },
  { key: "results", num: "7", label: "Výsledky", sub: "Report a data" },
] as const;

export const STEP_KEYS = ["brief", "plan", "questionnaire", "audience", "persona", "run", "progress", "results", "verify", "next"] as const;
export type StepKey = (typeof STEP_KEYS)[number];

/** The classic router's name for each step, for a hand-off (`#aia:open=<id>@<route>`). */
export const CLASSIC_ROUTE: Record<StepKey, string> = {
  brief: "brief",
  plan: "plan",
  questionnaire: "questionnaire",
  audience: "audience",
  persona: "persona",
  run: "run",
  progress: "research_progress",
  results: "results",
  verify: "verify",
  next: "next",
};

/** The steps with a rebuilt screen. The others hand off to the classic interface. */
export const REBUILT_STEPS: ReadonlySet<StepKey> = new Set<StepKey>(["brief", "plan", "questionnaire", "audience", "persona"]);

export function isStepKey(x: string): x is StepKey {
  return (STEP_KEYS as readonly string[]).includes(x);
}

/** updateTopbarProgress1782: "VÝZKUM · KROK n / 7" on a rail step, "NPC PANEL" elsewhere; how many rail marks are done. */
export function stepEyebrow(step: StepKey): { text: string; done: number; total: number } {
  const idx = RAIL_STEPS.findIndex((s) => s.key === step);
  if (idx < 0) return { text: "NPC PANEL", done: 0, total: 0 };
  return { text: `VÝZKUM · KROK ${idx + 1} / ${RAIL_STEPS.length}`, done: idx + 1, total: RAIL_STEPS.length };
}
