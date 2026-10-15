"use client";

// Technical detail on the settings page -- environment names, codes, identifiers, catalogue and
// implementation references -- is shown or hidden for the whole page by one switch, instead of a
// disclosure arrow beside every value (product owner, 2026-10-13: no little arrows, no ids shown to
// researchers). Off by default; the choice is kept for the browser session.

import { type ReactNode, createContext, useContext, useState } from "react";

import { t } from "@/i18n/t";

const KEY = "aia.settings.technical";
const TechnicalContext = createContext(false);

function stored(): boolean {
  try {
    return typeof window !== "undefined" && sessionStorage.getItem(KEY) === "1";
  } catch {
    return false; // storage unavailable: the default stands
  }
}

/** The page's choice, kept for the session; off until the person turns it on. Read on the first
 *  render: the settings panel is drawn only after its data loads in the browser, never on the
 *  server, so no server render can disagree with it (and the details never flash in late). */
export function useTechnicalChoice(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(stored);
  const set = (next: boolean) => {
    setOn(next);
    try { sessionStorage.setItem(KEY, next ? "1" : "0"); } catch { /* the choice lasts this page only */ }
  };
  return [on, set];
}

export function TechnicalProvider({ on, children }: { on: boolean; children: ReactNode }) {
  return <TechnicalContext.Provider value={on}>{children}</TechnicalContext.Provider>;
}

export const useTechnical = () => useContext(TechnicalContext);

/** Shown only while the page's technical detail is on. */
export function Technical({ children }: { children: ReactNode }) {
  return useTechnical() ? <>{children}</> : null;
}

/** The one switch, in the tab header. */
export function TechnicalSwitch({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className="inline-flex shrink-0 items-center gap-2 rounded-sm px-1 text-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
    >
      <span aria-hidden="true" className={`relative inline-block h-5 w-[34px] shrink-0 rounded-pill transition-colors ${on ? "bg-signal" : "bg-border-strong"}`}>
        <i className={`absolute top-0.5 block size-4 rounded-full bg-surface-raised transition-[left] ${on ? "left-4" : "left-0.5"}`} />
      </span>
      {t("aia.settings.panel.technicalSwitch")}
    </button>
  );
}
