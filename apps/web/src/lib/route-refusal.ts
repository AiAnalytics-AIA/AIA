// Who fixes a refusal the AI route's own settings decide (lead-orchestration LO12a). The route's
// data classes, retention and terms are an operator's SSM parameters, never a setting in AIA (whose
// Settings only read them), so a researcher who meets one is told who acts and where the step is
// written, not left to retry. Static copy keyed by the gateway's codes (`egress_` + the reason
// domain/residency.py's EgressDenied names, model_gateway.py); nothing about the route is read.

const RUNBOOK = "deploy/develop/README.md";

/** The parameter, or the runbook section, each route refusal is fixed by. */
const FIXED_BY: Readonly<Record<string, string>> = {
  egress_route_not_approved_for_class: "parametr aia_ai_route_approved_for (oddíl „AI route classes“)",
  egress_retention_unspecified: "parametr aia_ai_route_retention_days (oddíl „AI route classes“)",
  egress_residency_violation: "parametr aia_ai_route_eu_processing_approved (oddíl „AI route classes“)",
  egress_training_exclusion_missing: "parametr aia_ai_route_excluded_from_training (oddíl „AI route classes“)",
  egress_no_approved_route: "trasu k modelu (oddíl „AI“)",
  egress_route_provider_mismatch: "trasu k modelu (oddíl „AI“)",
};

/** The who-fixes-it line for a route refusal; null for any other code, or none. */
export function whoFixes(code: string | null | undefined): string | null {
  const what = code ? FIXED_BY[code] : undefined;
  return what
    ? `Opraví to provozovatel AIA, ne výzkumník: nastaví ${what} podle ${RUNBOOK} a restartuje pracovníka. V Nastavení AIA se to změnit nedá.`
    : null;
}

/** Words with the who-fixes-it line after them when the code is a route refusal. */
export const withFixer = (words: string, code: string | null | undefined): string => {
  const fix = whoFixes(code);
  return fix ? `${words} ${fix}` : words;
};
