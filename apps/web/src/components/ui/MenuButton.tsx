"use client";

// I3: a <select> never performs an action on change; an action takes a menu button. The button
// opens a menu under it; ↑ ↓ Home End move through the items without doing anything (audit IA-6:
// a closed select fires on the first arrow in some browsers); Enter, Space or a click does the one
// chosen and closes the menu; Esc or a press outside closes it. Focus returns to the button.

import { type KeyboardEvent, type ReactNode, useRef, useState } from "react";

import { rovingIndex } from "@/lib/roving";
import { Icon, type IconName } from "../rehome/icons";
import { FOCUS, POPOVER, POPOVER_END, useDismiss } from "./parts";

export type MenuItem<K extends string> = { key: K; label: ReactNode; disabled?: boolean };

/** The menu's least width (min-w-48: 12rem). */
const MENU_MIN_PX = 192;
/** What the menu keeps clear of the viewport's edge. */
const EDGE_PX = 8;

/**
 * Which way the menu opens: the side asked for, unless that side would put its least width past
 * the viewport (a button that wrapped to the right of a bar at phone width) and the other would
 * not -- a menu that runs off the page widens it and hides its own items (I11).
 */
export function menuSide(asked: "start" | "end", trigger: { left: number; right: number }, viewport: number): "start" | "end" {
  const startFits = trigger.left + MENU_MIN_PX <= viewport - EDGE_PX;
  const endFits = trigger.right - MENU_MIN_PX >= EDGE_PX;
  if (asked === "start") return startFits || !endFits ? "start" : "end";
  return endFits || !startFits ? "end" : "start";
}

export function MenuButton<K extends string>({
  label, name, items, onSelect, icon, disabled = false, small = true, empty, hideLabel = false, align = "start", className = "",
}: {
  /** What the menu does ("Přesunout do složky"): the button's text and the menu's name. */
  label: string;
  /**
   * The button's and the menu's accessible name when the visible `label` alone would not say what
   * the menu does: a tag showing a value ("Jedna odpověď") named for its choice ("Jedna odpověď, typ
   * otázky"). Start it with the label, so the visible text stays in the name (WCAG 2.5.3).
   */
  name?: string;
  items: readonly MenuItem<K>[];
  /**
   * Does the chosen action. Awaited by nothing: the menu has closed by then, so the caller owns
   * the action's errors and says them where the action shows (I9).
   */
  onSelect: (key: K) => void;
  icon?: IconName;
  disabled?: boolean;
  small?: boolean;
  /** Said in the menu when it has no items. */
  empty?: ReactNode;
  /**
   * A row's own actions: the button shows its icon alone ("⋯" unless `icon` says otherwise) and
   * `label` is its accessible name and the menu's, so the row it acts on is named in it
   * ("Akce složky Archiv").
   */
  hideLabel?: boolean;
  /** "end": the menu opens leftwards from the button's right edge, for a button at a row's end. */
  align?: "start" | "end";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const accessible = name ?? label;
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const close = () => setOpen(false);
  useDismiss(open, close, box, trigger);
  const off = (i: number) => !!items[i]?.disabled;

  const focusItem = (i: number | null) => {
    if (i !== null) refs.current[i]?.focus();
  };
  const [side, setSide] = useState(align);
  const openAt = (where: "first" | "last") => {
    const at = trigger.current?.getBoundingClientRect();
    // A trigger not laid out (no width) is not measured: the side asked for.
    setSide(at && at.width > 0 ? menuSide(align, at, window.innerWidth) : align);
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
        aria-label={hideLabel ? accessible : name}
        title={hideLabel ? accessible : undefined}
        onClick={() => (open ? setOpen(false) : openAt("first"))}
        onKeyDown={onTriggerKey}
        className={
          hideLabel
            ? `inline-flex size-11 items-center justify-center rounded-sm text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-50 sm:size-7 ${FOCUS}`
            : `inline-flex items-center gap-1.5 rounded-sm border border-border-strong bg-surface-raised font-medium whitespace-nowrap text-ink hover:bg-surface-sunken disabled:opacity-50 ${small ? "min-h-7 px-2 text-xs" : "min-h-9 px-3 text-sm"} ${FOCUS}`
        }
      >
        {hideLabel ? (
          <Icon name={icon ?? "more"} size={16} />
        ) : (
          <>
            {icon ? <Icon name={icon} size={small ? 14 : 16} /> : null}
            {label}
            <Icon name="chevron" size={12} className="text-ink-faint" />
          </>
        )}
      </button>
      {open ? (
        <div role="menu" aria-label={accessible} className={`${side === "end" ? POPOVER_END : POPOVER} flex max-h-72 min-w-48 max-w-[calc(100vw-1rem)] flex-col overflow-y-auto`}>
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
