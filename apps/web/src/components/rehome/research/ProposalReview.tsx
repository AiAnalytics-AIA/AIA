"use client";

// An AI proposal, reviewed where the work is (research-lane-redesign chunk 5): at the
// top of the stage, not in a modal. It names what would change against the design
// the person has now -- each research question, objective and hypothesis added or
// dropped, each comparable set's items -- and the rest of the proposal below. The
// decision stays one decision for the whole proposal: "Použít návrh" accepts it
// (recorded once per job, ADR 0019 gate 1), "Ponechat současný návrh" keeps the
// design as it is and the proposal stays saved.

import { useLayoutEffect, useRef } from "react";

import type { ResearchAgentResult } from "@/lib/api";
import { proposalDiff } from "@/research/proposal-diff";
import { proposalAnalysis } from "@/research/plan-edit";
import type { ResearchState } from "@/research/store";
import { Sparkle } from "../icons";
import { Button } from "../ui";
import { AgentProposalContent } from "./AgentProposalDialog";

function Item({ kind, children }: { kind: "add" | "del"; children: string }) {
  return (
    <li className="flex items-start gap-2 text-[13px] leading-5">
      <span aria-hidden="true" className={`mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-sm font-mono text-[11px] font-semibold ${kind === "add" ? "bg-signal-wash text-signal" : "bg-status-fault-wash text-status-fault"}`}>
        {kind === "add" ? "+" : "−"}
      </span>
      <span className={kind === "del" ? "text-ink-muted line-through" : ""}>
        <span className="sr-only">{kind === "add" ? "Přibude: " : "Odpadne: "}</span>
        {children}
      </span>
    </li>
  );
}

export function ProposalReview({ result, state, onDecision }: {
  result: ResearchAgentResult;
  state: Pick<ResearchState, "project" | "analysis">;
  onDecision: (apply: boolean) => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    heading.current?.scrollIntoView?.({ block: "start", behavior: "smooth" });
    heading.current?.focus();
  }, []);
  const diff = proposalDiff(proposalAnalysis(state), result.result.proposal);
  const changedSets = diff.sets.filter((s) => s.status !== "same");
  return (
    <section aria-labelledby="proposal-review-title" data-proposal-review className="scroll-mt-40 overflow-hidden rounded-card border border-ai-edge bg-surface-raised">
      <div className="flex flex-wrap items-center gap-2 border-b border-ai-edge bg-ai-wash px-4 py-2.5">
        <Sparkle size={14} />
        <h2 ref={heading} tabIndex={-1} id="proposal-review-title" className="flex-1 text-sm font-semibold text-ai-ink focus:outline-none">
          {diff.changes ? `Zkontrolujte návrh AI · ${diff.changes} ${diff.changes === 1 ? "změna" : diff.changes < 5 ? "změny" : "změn"}` : "Zkontrolujte návrh AI"}
        </h2>
        <span className="text-xs text-ink-muted">Nic se nezmění, dokud návrh nepoužijete.</span>
      </div>
      <div className="flex flex-col gap-4 px-4 py-3">
        {diff.summary ? (
          <div>
            <h3 className="text-xs font-medium text-ink-muted">Shrnutí problému</h3>
            <ul className="mt-1 flex flex-col gap-1">
              {diff.summary.before ? <Item kind="del">{diff.summary.before}</Item> : null}
              <Item kind="add">{diff.summary.after}</Item>
            </ul>
          </div>
        ) : null}
        {diff.lists.filter((l) => l.added.length || l.removed.length).map((l) => (
          <div key={l.key}>
            <h3 className="text-xs font-medium text-ink-muted">{l.label}{l.kept ? ` · ${l.kept} beze změny` : ""}</h3>
            <ul className="mt-1 flex flex-col gap-1">
              {l.removed.map((x) => <Item key={`d-${x}`} kind="del">{x}</Item>)}
              {l.added.map((x) => <Item key={`a-${x}`} kind="add">{x}</Item>)}
            </ul>
          </div>
        ))}
        {changedSets.length ? (
          <div>
            <h3 className="text-xs font-medium text-ink-muted">Porovnatelné sady</h3>
            <ul className="mt-1 flex flex-col gap-2">
              {changedSets.map((s) => (
                <li key={s.title} className="text-[13px] leading-5">
                  <span className="font-semibold">{s.title}</span>{" "}
                  <span className="text-ink-muted">{s.status === "new" ? `· nová sada, ${s.size} položek` : s.status === "removed" ? "· sada odpadne" : `· ${s.size} položek`}</span>
                  {s.status === "changed" ? (
                    <ul className="mt-1 flex flex-col gap-1">
                      {s.removed.map((x) => <Item key={`d-${x}`} kind="del">{x}</Item>)}
                      {s.added.map((x) => <Item key={`a-${x}`} kind="add">{x}</Item>)}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <details className="text-sm">
          <summary className="cursor-pointer text-[13px] font-medium text-ink-muted">{diff.changes ? "Celý návrh" : "Návrh"}</summary>
          <div className="mt-3"><AgentProposalContent result={result} /></div>
        </details>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-ai-edge px-4 py-2.5">
        <span className="flex-1 text-xs leading-4 text-ink-muted">Použití vytvoří novou revizi návrhu. Již vytvořený dotazník se nemění. Nové dimenze jsou návrhy; filtry a proveditelnost audience zkontrolujte samostatně.</span>
        <Button onClick={() => onDecision(false)}>Ponechat současný návrh</Button>
        <Button variant="primary" onClick={() => onDecision(true)}>Použít návrh</Button>
      </div>
    </section>
  );
}
