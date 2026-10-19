"use client";

// The item inspector (research-lead-workbench chunk 2, ADR 0026 D3): a drawer over the
// artifact pane with one opened item's detail, its back stack from lib/inspector-stack.ts.
// Back returns to the item it was opened from; Close and Escape empty it and give the
// focus back to what opened it. The stage's readiness stays in InspectorSlot, beside the
// stage; this drawer shows an item and changes nothing stored.

import { type ReactNode, useEffect, useRef } from "react";

import { t } from "@/i18n/t";
import { type InspectorEntry, type InspectorStack, topEntry } from "@/lib/inspector-stack";
import { Icon } from "../icons";

export function ItemInspector({ stack, onBack, onClose, children }: {
  stack: InspectorStack;
  onBack: () => void;
  onClose: () => void;
  /** The opened item's detail. */
  children: (entry: InspectorEntry) => ReactNode;
}) {
  const top = topEntry(stack);
  const open = top !== null;
  const panel = useRef<HTMLElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  // Opening takes the focus from where it was and keeps that place; closing gives it back.
  useEffect(() => {
    if (open) {
      if (!opener.current) opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      panel.current?.focus();
    } else if (opener.current) {
      const back = opener.current;
      opener.current = null;
      if (back.isConnected) back.focus();
    }
  }, [open, top]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      e.preventDefault();
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!top) return null;
  return (
    <aside
      ref={panel}
      tabIndex={-1}
      aria-label={`${t("aia.study.workbench.inspector")}: ${top.title}`}
      data-item-inspector={top.id}
      className="flex max-h-full min-w-0 flex-col rounded-card border border-border-strong bg-surface-raised shadow-[var(--shadow-overlay)] focus-visible:outline-2 focus-visible:outline-focus-ring"
    >
      <header className="flex items-start gap-2 border-b border-border p-3">
        {stack.entries.length > 1 ? (
          <button type="button" onClick={onBack} aria-label={t("aia.study.workbench.back")} title={t("aia.study.workbench.back")} className="rounded-control p-1 text-ink-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus-ring">
            <Icon name="back" size={16} />
          </button>
        ) : null}
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold">{top.title}</h2>
          {top.sub ? <p className="truncate text-xs text-ink-muted">{top.sub}</p> : null}
        </div>
        <button type="button" onClick={onClose} aria-label={t("aia.study.workbench.close")} title={t("aia.study.workbench.close")} className="rounded-control p-1 text-ink-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus-ring">
          <Icon name="fault" size={16} />
        </button>
      </header>
      <div className="min-h-0 overflow-y-auto p-3 text-sm leading-6">{children(top)}</div>
    </aside>
  );
}
