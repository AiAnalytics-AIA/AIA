"use client";

// I3 / I5: a colour is chosen by its swatch, never by its name in a list (audit D4, D6). The six
// colours a label takes (hue-*), each with its Czech name as the accessible name, so colour is
// never the only cue. Inline -- inside a row saved as a whole -- it is a radio group whose arrows
// move and choose. With `popover` the choice is an action (a recolour saved at once), so it is one
// swatch button that opens the swatches anchored to the item as a listbox: the arrows only move (audit IA-6),
// a click, Enter or Space chooses and closes, Esc or a press outside closes, and focus returns to
// the button.

import { type KeyboardEvent, useRef, useState } from "react";

import { tv } from "@/i18n/t";
import { rovingIndex, tabStop } from "@/lib/roving";
import { FOCUS, POPOVER, useDismiss } from "./parts";

type Props<C extends string> = {
  value: C;
  /** Reports the colour chosen; awaited by nothing, so a caller that saves on it owns its errors. */
  onChange: (colour: C) => void;
  colours: readonly C[];
  /** The token utility that paints each colour ("bg-hue-blue"). */
  swatch: Record<C, string>;
  /** Each colour's name in words ("Modrá"). */
  name: (colour: C) => string;
  /** What is being coloured ("Barva štítku"). */
  label: string;
  disabled?: boolean;
};

function Swatches<C extends string>({
  value, onChange, colours, swatch, name, label, disabled = false, chooseOnMove, autoFocus = false,
}: Props<C> & { chooseOnMove: boolean; autoFocus?: boolean }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const stop = tabStop(colours.length, colours.indexOf(value), () => disabled);
  const onKey = (i: number) => (e: KeyboardEvent<HTMLButtonElement>) => {
    const next = rovingIndex(i, e.key, colours.length, () => disabled);
    if (next === null) return;
    e.preventDefault();
    refs.current[next]?.focus();
    if (chooseOnMove) onChange(colours[next]);
  };
  // Inline the arrows choose, as radios do: a radio group. In the popover they only move and a
  // click or Enter chooses: that is a listbox of options, not radios (Codex #532).
  return (
    <div role={chooseOnMove ? "radiogroup" : "listbox"} aria-label={label} className="flex flex-wrap gap-1">
      {colours.map((c, i) => {
        const on = c === value;
        return (
          <button
            key={c}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role={chooseOnMove ? "radio" : "option"}
            aria-checked={chooseOnMove ? on : undefined}
            aria-selected={chooseOnMove ? undefined : on}
            aria-label={name(c)}
            title={name(c)}
            disabled={disabled}
            autoFocus={autoFocus && i === stop}
            tabIndex={i === stop ? 0 : -1}
            onClick={() => onChange(c)}
            onKeyDown={onKey(i)}
            className={`inline-flex size-11 items-center justify-center rounded-pill border-2 disabled:opacity-50 sm:size-8 ${FOCUS} ${on ? "border-ink" : "border-transparent hover:border-border-strong"}`}
          >
            <span aria-hidden="true" className={`size-5 rounded-full ${swatch[c]}`} />
          </button>
        );
      })}
    </div>
  );
}

export function SwatchPicker<C extends string>({ popover = false, ...props }: Props<C> & { popover?: boolean }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => setOpen(false);
  useDismiss(open, close, box, trigger);

  if (!popover) return <Swatches {...props} chooseOnMove />;
  return (
    <div ref={box} className="relative inline-block">
      <button
        ref={trigger}
        type="button"
        disabled={props.disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={tv("input.swatch", { label: props.label, colour: props.name(props.value) })}
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex size-11 items-center justify-center rounded-pill hover:bg-surface-sunken disabled:opacity-50 sm:size-7 ${FOCUS}`}
      >
        <span aria-hidden="true" className={`size-3 rounded-full ${props.swatch[props.value]}`} />
      </button>
      {open ? (
        <div className={`${POPOVER} p-1.5`}>
          <Swatches
            {...props}
            chooseOnMove={false}
            autoFocus
            onChange={(c) => {
              setOpen(false);
              trigger.current?.focus();
              if (c !== props.value) props.onChange(c);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
