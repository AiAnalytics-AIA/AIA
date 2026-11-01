"use client";

import { useRef } from "react";
import { rovingIndex } from "@/lib/roving";
import { Icon } from "./Icons";

const FIELDWORK_VIEWS = [
  { step: "run", label: "Kontrola a spuštění", icon: "listChecks" },
  { step: "progress", label: "Průběh", icon: "chartBar" },
] as const;

/**
 * Sběr dat's two views (FLD9, spec sber F1; Fieldwork.dc.html's "Pohled"): Kontrola a spuštění and
 * Průběh, each its own route, opened through a link's click so a leave guard can stop it. One Tab
 * stop; the arrows move between the two (input-interactions I11), Enter or a click opens one.
 */
export function FieldworkViews({ current, open }: { current: "run" | "progress"; open: (step: "run" | "progress") => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <span className="views" role="tablist" aria-label="Pohled">
      {FIELDWORK_VIEWS.map((v, i) => (
        <button key={v.step} ref={(el) => { refs.current[i] = el; }} type="button" role="tab" aria-selected={v.step === current} tabIndex={v.step === current ? 0 : -1}
          onClick={() => { if (v.step !== current) open(v.step); }}
          onKeyDown={(e) => {
            const to = rovingIndex(i, e.key, FIELDWORK_VIEWS.length, undefined, "horizontal");
            if (to === null) return;
            e.preventDefault();
            refs.current[to]?.focus();
          }}>
          <Icon name={v.icon} size={14} />{v.label}
        </button>
      ))}
    </span>
  );
}
