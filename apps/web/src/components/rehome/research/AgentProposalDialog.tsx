"use client";

import type { ResearchAgentResult } from "@/lib/api";
import { useLayoutEffect, useRef } from "react";
import { Button } from "../ui";

const strings = (v: unknown) => Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
const objects = (v: unknown) => Array.isArray(v) ? v.filter((x): x is Record<string, unknown> => !!x && typeof x === "object") : [];

function TextList({ title, values }: { title: string; values: unknown }) {
  const list = strings(values);
  return list.length ? <section className="mb-4"><h3 className="font-semibold">{title}</h3><ul className="ml-5 list-disc text-sm">{list.map((s, i) => <li key={i}>{s}</li>)}</ul></section> : null;
}

export function AgentProposalDialog({ result, onDecision, advice = false }: {
  result: ResearchAgentResult; onDecision: (apply: boolean) => void; advice?: boolean;
}) {
  const p = result.result.proposal;
  const ref = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} aria-labelledby="agent-proposal-title"
    onCancel={(e) => { e.preventDefault(); onDecision(false); }}
    className="m-auto max-h-[85vh] w-[min(48rem,calc(100vw-2rem))] overflow-auto rounded-md border border-border-strong bg-surface-overlay p-6 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-surface-inverse/40">
      <h2 id="agent-proposal-title" className="mb-2 text-xl font-semibold">{advice ? "Odpověď AI" : "Zkontrolujte návrh AI"}</h2>
      <p className="mb-5 text-sm text-ink-muted">{advice ? "Odpověď vychází z uloženého kontextu. Nenahrazuje schválení evidence." : "Změny se uloží až po vašem potvrzení. Nové dimenze jsou návrhy; filtry a proveditelnost audience zkontrolujte samostatně."}</p>
      {["title", "problem_summary", "decision_use", "message", "description", "answer", "method_reason"].map((k) => typeof p[k] === "string" && p[k] ? <p key={k} className="mb-3 whitespace-pre-line text-sm">{String(p[k])}</p> : null)}
      <TextList title="Cíle" values={p.objectives} /><TextList title="Výzkumné otázky" values={p.research_questions} />
      <TextList title="Hypotézy" values={p.hypotheses} /><TextList title="Koho zahrnout" values={p.inclusion_criteria} />
      <TextList title="Koho vyloučit" values={p.exclusion_criteria} />
      {objects(p.sections).map((s, i) => <section key={i} className="mb-4"><h3 className="font-semibold">{String(s.title || "Sekce")}</h3>
        <p className="text-sm">{String(s.purpose || "")}</p>
        {objects(s.questions).map((q, j) => <div key={j} className="mt-2 border-l-2 border-border pl-3 text-sm"><p>{String(q.text)}</p>
          <p className="text-ink-muted">{String(q.typ)} · {strings(q.kategorie).join(" · ") || (Array.isArray(q.skala) ? q.skala.join(" až ") : "")}</p>
          <p className="text-ink-muted">{strings(q.popisky_skaly).join(" · ")}{q.povolit_nevim ? " · Lze odpovědět Nevím" : ""}</p></div>)}
        {typeof s.object_question === "string" ? <p className="mt-2 text-sm">{s.object_question}</p> : null}<TextList title="Objekty" values={s.objects} />
        <TextList title="Popisky škály" values={s.scale_labels} />
        {s.familiarity_required ? <p className="text-sm">Vyžaduje znalost objektu.</p> : null}
      </section>)}
      {objects(p.tracked_sets).map((s, i) => <section key={i} className="mb-4"><h3 className="font-semibold">{String(s.title)}</h3><p className="text-sm">{String(s.purpose)}</p><TextList title="Objekty" values={s.objects} /></section>)}
      {objects(p.non_object_measures).map((m, i) => <section key={i} className="mb-4"><h3 className="font-semibold">{String(m.name)}</h3><p className="text-sm">{String(m.reason)} · {String(m.question_type)}</p></section>)}
      {objects(p.new_dimension_suggestions).map((d, i) => <section key={i} className="mb-4"><h3 className="font-semibold">{String(d.label)}</h3><p className="text-sm">{String(d.why)}</p><TextList title="Potřebná evidence" values={d.evidence_needed} /><TextList title="Navržené prediktory" values={d.suggested_predictors} /><p className="text-sm">{String(d.source_strategy || "")}</p></section>)}
      <TextList title="Doplňující otázky" values={p.questions_for_user || p.followup_questions} />
      <TextList title="Omezení" values={p.limitations || p.warnings} /><TextList title="Zdroje" values={p.source_ids} />
      <div className="mt-6 flex gap-3"><Button variant="primary" onClick={() => onDecision(true)} autoFocus>{advice ? "Zavřít" : "Použít návrh"}</Button>
        {!advice ? <Button onClick={() => onDecision(false)}>Ponechat současný návrh</Button> : null}</div>
  </dialog>;
}
