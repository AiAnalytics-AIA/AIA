"use client";

// I3: a <select> never performs an action on change; an action takes a menu button. The button
// opens a menu under it; ↑ ↓ Home End move through the items without doing anything (audit IA-6:
// a closed select fires on the first arrow in some browsers); Enter, Space or a click does the one
// chosen and closes the menu; Esc or a press outside closes it. Focus returns to the button.

import { type KeyboardEvent, type ReactNode, useRef, useState } from "react";

import { rovingIndex } from "@/lib/roving";
import { Icon, type IconName } from "../rehome/icons";
import { FOCUS, POPOVER, useDismiss } from "./parts";

export type MenuItem<K extends string> = { key: K; label: ReactNode; disabled?: boolean };

export function MenuButton<K extends string>({
  label, items, onSelect, icon, disabled = false, small = true, empty, className = "",
}: {
  /** What the menu does ("Přesunout do složky"): the button's text and the menu's name. */
  label: string;
  items: readonly MenuItem<K>[];
  onSelect: (key: K) => void;
  icon?: IconName;
  disabled?: boolean;
  small?: boolean;
  /** Said in the menu when it has no items. */
  empty?: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const close = () => setOpen(false);
  useDismiss(open, close, box, trigger);
  const off = (i: number) => !!items[i]?.disabled;

  const focusItem = (i: number | null) => {
    if (i !== null) refs.current[i]?.focus();
  };
  const openAt = (where: "first" | "last") => {
    setOpen(true);
    requestAnimationFrame(() => focusItem(rovingIndex(where === "first" ? -1 : items.length, where === "first" ? "Home" : "End", items.length, off)));
  };

  const pick = (k: K) => {
    setOpen(false);
    trigger.current?.focus();
    onSelect(k);
  };

  const onTriggerKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      openAt(e.key === "ArrowDown" ? "first" : "last");
    }
  };
  const onItemKey = (i: number) => (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    const next = rovingIndex(i, e.key, items.length, off, "vertical");
    if (next === null) return;
    e.preventDefault();
    focusItem(next);
  };

  return (
    <div ref={box} className={`relative inline-block ${className}`}>
      <button
        ref={trigger}
        type="button"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openAt("first"))}
        onKeyDown={onTriggerKey}
        className={`inline-flex items-center gap-1.5 rounded-sm border border-border-strong bg-surface-raised font-medium whitespace-nowrap text-ink hover:bg-surface-sunken disabled:opacity-50 ${small ? "min-h-7 px-2 text-xs" : "min-h-9 px-3 text-sm"} ${FOCUS}`}
      >
        {icon ? <Icon name={icon} size={small ? 14 : 16} /> : null}
        {label}
        <Icon name="chevron" size={12} className="text-ink-faint" />
      </button>
      {open ? (
        <div role="menu" aria-label={label} className={`${POPOVER} flex max-h-72 min-w-48 flex-col overflow-y-auto`}>
          {items.length === 0 && empty ? <p className="px-2 py-1.5 text-xs text-ink-faint">{empty}</p> : null}
          {items.map((item, i) => (
            <button
              key={item.key}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="menuitem"
              tabIndex={-1}
              disabled={item.disabled}
              onClick={() => pick(item.key)}
              onKeyDown={onItemKey(i)}
              className={`flex min-h-11 w-full items-center gap-2 rounded-sm px-2 text-left text-[13px] text-ink hover:bg-surface-sunken focus:bg-surface-sunken disabled:opacity-50 sm:min-h-8 ${FOCUS}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
