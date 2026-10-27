"use client";

// A Design Research run's proposal, reviewed where the run is read (research-lead-workbench 7b, F-DRL-1;
// ADR 0021 checkpoint 1). The run only proposes: per subject its accepted findings, or a gap. A person
// ticks the findings to take and accepts them; the server writes them into the design under
// `design_research` -- one transaction: the working copy, a new Design Revision and the ledger row -- and
// the working copy is read again. Nothing is written until the person accepts; an unticked item is not
// taken, and the proposal stays in the run. A refused accept is said by name (proposal-items.ts); a
// stale proposal is never applied. It is a person's own click: no model is asked, nothing is paid.

import { useEffect, useState } from "react";

import { deepResearch, type DesignProposal } from "@/lib/api";
import {
  acceptBody, INADMISSIBLE, itemsWord, readProposal, refusalWords, SPENT, subjectWords,
} from "@/lib/design-research-review";
import { staleDetails } from "@/research/proposal-items";
import type { ResearchStore } from "@/research/store";
import { Sparkle } from "../icons";
import { Button, StaleMark } from "../ui";
import { ItemReview } from "../ItemReview";
import { errorText } from "@/lib/error-words";

const message = (e: unknown) => errorText(e);
/** How many saves an accept waits for: each one takes what was typed during the one before. */
const SAVE_ATTEMPTS = 3;
const isUrl =(s: string) => /^https?:\/\//i.test(s);

export const REVIEW_LABEL = "Zkontrolovat návrh";
export const ACCEPT_LABEL = "Přijmout vybrané";

export function DesignResearchReview({ studyId, runId, store, project, canApply }: {
  studyId: string;
  runId: string;
  store: Pick<ResearchStore, "flush" | "get" | "reload">;
  /** The working copy's project as the stage shows it: what is already taken is read from it. */
  project: Record<string, unknown> | null;
  /** False on a study that takes no new work, or for a reader: the proposal is read, never accepted. */
  canApply: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [proposal, setProposal] = useState<DesignProposal | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- another run's review is cleared before this one is read
    setProposal(null); setChosen(new Set()); setError(null); setStale(null); setNotice(null);
    deepResearch.designProposal(studyId, runId)
      .then((p) => { if (live) setProposal(p); })
      .catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [studyId, runId]);

  // A proposal belongs to the run it was read for. For the one render after the run changes, before the
  // effect clears it, the last run's proposal and ticks are still held: they are never shown, ticked or
  // sent to this run. The panel also keys this component by its run, so a switch starts it afresh.
  if (!proposal || proposal.run_id !== runId) return error ?<p role="alert" className="text-sm text-status-fault">{error}</p> : null;
  const reading = readProposal(proposal, project);
  const evidence = reading.items.filter((i) => i.kind === "EVIDENCE").length;
  const toggle = (id: string) => setChosen((old) => {
    const next = new Set(old);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const accept = async () => {
    setBusy(true); setError(null); setNotice(null);
    try {
      // A change still waiting for its save is saved first, so the server checks the items against it.
      // ResearchStore.flush resolves only once the copy is saved, an edit typed during its save included
      // (F-STORE-1), and throws FlushIncomplete otherwise; the loop stays as a guard for a store that
      // resolves with a change still waiting. Never post on an unsaved copy: the reload after the accept
      // would replace what was typed.
      for (let i = 0; i < SAVE_ATTEMPTS && store.get().save.kind !== "saved"; i++) await store.flush();
      if (store.get().save.kind !== "saved") {
        setError("Vaše poslední úprava se ještě ukládá. Počkejte, až bude uložená, a podklady přijměte znovu.");
        return;
      }
      const sent = store.get();
      const body = acceptBody(proposal, reading, chosen, sent.revision);
      if (!body) { setError("Pracovní obsah studie ještě není uložený."); return; }
      await deepResearch.acceptDesignProposal(studyId, runId, body.item_ids, body.expected_revision_id, body.expected_workspace_revision);
      setChosen(new Set());
      let replaced: boolean;
      try {
        // The browser writes nothing back: it reads what the server wrote. A change typed while the
        // accept was on its way is kept on screen, in conflict, never dropped (store.reload `since`).
        replaced = await store.reload(undefined, { since: sent });
      } catch {
        setError("Podklady jsou přijaté a uložené v AIA, ale pracovní kopii se nepodařilo znovu načíst. Načtěte studii znovu.");
        return;
      }
      setNotice(replaced
        ? `Přijato do návrhu: ${itemsWord(body.item_ids.length)}. Vznikla nová revize návrhu.`
        : "Podklady jsou přijaté a uložené v AIA. Úpravu, kterou jste mezitím napsali, jsme nepřepsali ani neuložili: zkopírujte si ji a načtěte studii znovu.");
    } catch (e) {
      const words = refusalWords(e, store.get().project as Record<string, unknown>);
      // A stale proposal stays readable and is never applied; the rest is said where it happened.
      if (staleDetails(e)) setStale(words);
      else setError(words ?? message(e));
    } finally { setBusy(false); }
  };

  const mayAccept = canApply && reading.admissible && !reading.spent && !stale;
  return (
    <section aria-labelledby={`dr-review-${runId}`} data-design-research-review className="overflow-hidden rounded-card border ai-spark">
      <div className="flex flex-wrap items-center gap-2 border-b border-ai-edge bg-ai-wash px-4 py-2.5">
        <Sparkle size={14} />
        <h3 id={`dr-review-${runId}`} className="flex-1 text-sm font-semibold text-ink">
          Návrh k dotazníku · {itemsWord(evidence)} s podklady{reading.items.length > evidence ? ` · ${reading.items.length - evidence} bez nálezu` : ""}
        </h3>
        <span className="text-xs text-ink-muted">Nic se nezmění, dokud podklady nepřijmete.</span>
        <Button small aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Zavřít" : REVIEW_LABEL}</Button>
      </div>
      {notice ? <p role="status" className="px-4 pt-3 text-[13px] leading-5 text-ink">{notice}</p> : null}
      {error ? <p role="alert" className="px-4 pt-3 text-[13px] leading-5 text-status-fault">{error}</p> : null}
      {open ? (
        <>
          <div className="flex flex-col gap-3 px-4 py-3">
            {stale ? <StaleMark alert data-proposal-stale>{stale}</StaleMark> : null}
            {!reading.admissible ? <p role="note" className="rounded-sm border border-border p-3 text-[13px] leading-5">{INADMISSIBLE}</p> : null}
            {reading.spent ? <p role="note" className="text-[13px] leading-5 text-ink-muted">{SPENT}</p> : null}
            <ItemReview mode="select" label="Položky návrhu" canEdit={mayAccept} busy={busy}
              selected={chosen} onToggle={toggle} footer={null}
              items={reading.items.map((item) => ({
                id: item.itemId,
                where: <><span className="block text-xs font-normal text-ink-muted">{subjectWords(item.subjectKind)}</span><span className="font-semibold">{item.subjectText}</span></>,
                selectable: item.kind === "EVIDENCE" && canApply ? item.selectable : undefined,
                decided: item.accepted ? "V návrhu" : null,
                data: { "data-design-research-item": item.kind },
                body: item.kind === "GAP" ? (
                  <p className="mt-1 text-ink-muted">Výzkum k tomu nic nenašel. Je dobré to vědět, než návrh zmrazíte; přijmout tu není co.</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-2">
                    {item.findings.map((f) => (
                      <li key={f.evidence_id}>
                        <p>{f.claim}</p>
                        <blockquote className="mt-1 border-l-2 border-border-strong pl-3 text-ink-muted">{f.quote}</blockquote>
                        <p className="mt-1 text-xs text-ink-muted">
                          Zdroj: {isUrl(f.source) ? <a href={f.source} target="_blank" rel="noopener noreferrer" className="underline">{f.source_title || f.source}</a> : (f.source_title || f.source)}
                        </p>
                      </li>
                    ))}
                  </ul>
                ),
              }))} />
          </div>
          {canApply ? (
            <div className="flex flex-wrap items-center gap-2 border-t border-ai-edge px-4 py-2.5">
              <span className="flex-1 text-xs leading-4 text-ink-muted">Přijetí vytvoří novou revizi návrhu: vybrané nálezy se uloží k návrhu jako vnější podklady s citací zdroje. Dotazník, audience ani vzorek se nemění. Nevybrané položky se nikam nezapíšou.</span>
              <Button onClick={() => { setChosen(new Set()); setOpen(false); }}>Ponechat současný návrh</Button>
              <Button variant="primary" disabled={!mayAccept || busy || chosen.size === 0} onClick={() => void accept()}>
                {busy ? "Přijímám…" : chosen.size ? `${ACCEPT_LABEL} (${chosen.size})` : ACCEPT_LABEL}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
