"use client";

// A formula drawn as MathML by Temml from the domain's LaTeX (ADR 0023 decision 8); its LaTeX,
// said so, when it cannot be drawn. Shared by the Metodika tab's steps and its editor.

// Temml's layout rules (display math in Firefox and Safari, enclosures, primes) and the
// system math font stack: Cambria Math on Windows, STIX Two Math on macOS.
import "temml/dist/Temml-Local.css";

import { t } from "@/i18n/t";
import { formulaMathML } from "@/lib/methodology";

const M = "aia.settings.methodology";

/** A formula as MathML; its LaTeX, said so, when it cannot be drawn. */
export function Formula({ latex, display = true }: { latex: string; display?: boolean }) {
  const mathml = formulaMathML(latex, display);
  if (mathml === null) {
    return (
      <span className="flex flex-col gap-1">
        <code className="whitespace-pre-wrap break-all font-mono text-xs">{latex}</code>
        <span className="text-xs text-status-fault">{t(`${M}.formulaError`)}</span>
      </span>
    );
  }
  // Temml's own output, trust off: built from the catalogue's LaTeX, no link or HTML passes.
  return <span className={display ? "block min-w-0 max-w-full overflow-x-auto" : "inline-block max-w-full overflow-x-auto align-middle"} dangerouslySetInnerHTML={{ __html: mathml }} />;
}
