"use client";

// A proposal decided item by item (DS v3.1 ItemReview): what an AI proposes is a list of changes,
// and each is a person's to take or leave. One row per item, always the same parts:
//   where it lands · what is there now (struck through) · what it would be · why
//   and, once decided or refused, that in words.
// Two ways to decide, by what the server can apply:
//   "each":   every row has its own Zahodit / Přijmout, and the head takes or leaves them all
//             (the Lead's edits, one transaction per decision);
//   "select": rows are ticked and "Přijmout vybrané (n)" applies the ticked ones together
//             (a Design Research proposal, one revision per accept).
// Nothing is applied by showing it; colour never carries a decision alone.

import type { ReactNode } from "react";

import { Glyph } from "../workbench/Glyph";
import { Button } from "./ui";

export type ReviewItem = {
  id: string;
  /** Where the change lands, in the stage's words ("Dotazník · upravit otázku"). */
  where: ReactNode;
  before?: ReactNode | null;
  after?: ReactNode | null;
  /** Anything the item carries beyond before / after (a finding, its quote and source). */
  body?: ReactNode;
  why?: ReactNode | null;
  /** The server refused this item; its words. */
  refused?: string | null;
  /** Already decided: shown, never offered again. */
  decided?: string | null;
  /** "select" only: may this row be ticked (an item with nothing to accept may not). */
  selectable?: boolean;
  /** Data attributes the stage marks the row with (data-aia and the like). */
  data?: Record<`data-${string}`, string>;
};

type Common = {
  label: string;
  items: ReviewItem[];
  /** The head's words: how many, and that nothing changes until a person decides. None where the
   *  surface around the list already says it. */
  head?: ReactNode;
  canEdit: boolean;
  busy?: boolean;
};

export function ItemReview(props: Common & (
  | { mode: "each"; onAccept: (ids: string[]) => void; onDismiss: (ids: string[]) => void }
  | { mode: "select"; selected: ReadonlySet<string>; onToggle: (id: string) => void; footer: ReactNode }
)) {
  const { label, items, head, canEdit, busy = false } = props;
  const open = items.filter((i) => !i.decided).map((i) => i.id);
  return (
    <div role="region" aria-label={label} data-item-review={props.mode} className="flex flex-col gap-2">
      {head ? <div className="flex flex-wrap items-center gap-2 text-[13px] leading-5">
        <Glyph tone="you" size={12} />
        <div className="min-w-0 flex-1">{head}</div>
        {props.mode === "each" && open.length > 1 ? <>
          <Button small variant="quiet" disabled={busy} onClick={() => props.onDismiss(open)}>Zahodit vše</Button>
          <Button small variant="primary" disabled={!canEdit || busy} onClick={() => props.onAccept(open)}>Přijmout vše</Button>
        </> : null}
      </div> : null}
      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const box = `review-${item.id}`;
          const ticks = props.mode === "select" && item.selectable !== undefined;
          return (
            <li key={item.id} data-review-item={item.id} {...item.data} className="rounded-sm border border-border bg-surface-raised p-3 text-[13px] leading-5">
              <div className="flex flex-wrap items-start gap-2">
                {ticks && props.mode === "select" ? (
                  <input id={box} type="checkbox" className="mt-1" checked={!!item.decided || props.selected.has(item.id)}
                    disabled={!item.selectable || !canEdit || busy || !!item.decided} onChange={() => props.onToggle(item.id)} />
                ) : null}
                <label htmlFor={ticks ? box : undefined} className="min-w-0 flex-1 font-medium">{item.where}</label>
                {item.refused ? <span className="text-xs text-status-fault">{item.refused}</span> : null}
                {item.decided ? <span className="text-xs font-medium text-signal">{item.decided}</span> : null}
                {props.mode === "each" && !item.decided ? <>
                  <Button small variant="quiet" disabled={busy} onClick={() => props.onDismiss([item.id])}>Zahodit</Button>
                  <Button small disabled={!canEdit || busy} onClick={() => props.onAccept([item.id])}>Přijmout</Button>
                </> : null}
              </div>
              {item.before !== null && item.before !== undefined ? <div data-review-before className="mt-1 text-ink-muted line-through decoration-ink-faint">{item.before}</div> : null}
              {item.after !== null && item.after !== undefined ? <div data-review-after className="mt-1">{item.after}</div> : null}
              {item.body}
              {item.why ? <div className="mt-1 text-xs text-ink-muted">Proč: {item.why}</div> : null}
            </li>
          );
        })}
      </ul>
      {props.mode === "select" ? props.footer : null}
    </div>
  );
}
