"use client";

// Trasa modelu "Podle pracovníka" (lead-orchestration LO12b): each data class as the newest
// worker start's recorded route carries or refuses it, and what a Lead turn would meet. Read only;
// absent when the API's pre-flight read is off (404), unknown never "carried".

import { t, tv } from "@/i18n/t";
import { classLines } from "@/lib/ai-route";
import { settingsStatus } from "@/lib/api";
import { whoFixes } from "@/lib/route-refusal";

import { useResource } from "../useResource";
import { Technical } from "./technical";

const W = "aia.settings.panel.runtime.worker";

function refusalWords(code: string): string {
  const key = `${W}.refusal.${code}`;
  const words = t(key);
  return words === key ? code : words;
}

export function WorkerRoute() {
  const [res] = useResource(() => settingsStatus.aiRoute(), []);
  if (res.state === "loading" || res.state === "not-found") return null;
  if (res.state === "failed") return <p data-worker-route="failed" className="mt-2 text-xs text-ink-muted">{res.message}</p>;
  const route = res.data;
  return (
    <div data-worker-route={route.recorded ? "recorded" : "none"} className="mt-3 flex flex-col gap-1 border-t border-border pt-2.5">
      <h3 className="text-sm font-semibold">{t(`${W}.title`)}</h3>
      <p className="max-w-3xl text-xs leading-5 text-ink-muted">{t(`${W}.help`)}</p>
      {route.recorded ? (
        <>
          <ul className="flex flex-col gap-0.5 text-sm">
            {classLines(route).map((c) => (
              <li key={c.letter} data-class-line={c.letter} data-kind={c.kind}>
                <span className="font-medium">{c.letter}</span>
                {": "}
                {c.kind === "refused" && c.code ? `${t(`${W}.refused`)}: ${refusalWords(c.code)}` : t(`${W}.${c.kind}`)}
                {c.code ? <Technical><code className="ml-1 text-xs">{c.code}</code></Technical> : null}
              </li>
            ))}
          </ul>
          <p data-lead-refusal={route.lead_refusal ?? ""} className="text-sm">
            {t(`${W}.lead`)}
            {route.lead_refusal ? refusalWords(route.lead_refusal) : t(`${W}.leadNone`)}
          </p>
          {/* The route's refusals are an operator's to fix, as LO12a says wherever one is met. */}
          {classLines(route).some((c) => whoFixes(c.code)) ? (
            <p data-who-fixes className="max-w-3xl text-xs leading-5 text-ink-muted">
              {whoFixes(classLines(route).find((c) => whoFixes(c.code))?.code)}
            </p>
          ) : null}
          {route.composed_at ? (
            <p className="text-xs text-ink-faint">
              {tv(`${W}.recordedAt`, { at: new Date(route.composed_at).toLocaleString("cs-CZ") })}
              <Technical><span className="ml-1">{route.worker} {route.build_sha ?? ""}</span></Technical>
            </p>
          ) : null}
        </>
      ) : <p className="text-sm text-ink-muted">{t(`${W}.none`)}</p>}
    </div>
  );
}
