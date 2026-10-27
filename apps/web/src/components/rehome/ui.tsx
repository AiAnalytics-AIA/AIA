"use client";

// AIA's interface primitives. Token utilities only (bg-surface, text-ink,
// border-border-strong; the look contract's radii: rounded-sm and rounded-control = 6 px for
// controls and chips, rounded-md and rounded-card = 8 px for cards, rounded-panel = 10 px for
// dialogs and menus, rounded-pill only for what is round): no raw colour, radius, shadow
// or font here or in anything built on them. Components map a value to an
// appearance; what the value is, the logic beside each screen decides.

import {
  type ButtonHTMLAttributes, type ComponentProps, type ReactNode, type SelectHTMLAttributes,
  useId, useLayoutEffect, useRef, useState,
} from "react";

import type { Tone } from "@/lib/tone";
import { t } from "@/i18n/t";
import { Icon, type IconName, Sparkle } from "./icons";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

const VARIANT = {
  primary: "bg-signal text-on-signal border-signal hover:bg-signal-hover hover:border-signal-hover",
  secondary: "bg-surface-raised text-ink border-border-strong hover:bg-surface-sunken",
  quiet: "bg-transparent text-ink-muted border-transparent hover:text-ink hover:bg-surface-sunken",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANT;
  small?: boolean;
  icon?: IconName;
  children: ReactNode;
};

export function Button({ variant = "secondary", small = false, icon, children, type = "button", className = "", ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center gap-1.5 rounded-sm border font-medium whitespace-nowrap transition-colors duration-[var(--duration-confirm)] disabled:opacity-50 ${small ? "min-h-7 px-2 text-xs" : "min-h-9 px-3 text-sm"} ${VARIANT[variant]} ${FOCUS} ${className}`}
      {...rest}
    >
      {icon ? <Icon name={icon} size={small ? 14 : 16} /> : null}
      {children}
    </button>
  );
}

const AI_VARIANT = {
  primary: "ai-spark ai-spark--solid text-on-ai",
  secondary: "ai-spark text-ink",
} as const;

/**
 * A control that starts an AI worker job: the sparkle, the spark edge (globals.css; it turns on
 * hover and focus, and while `aria-busy`) and the same title everywhere, so a person always knows
 * a click is paid from the study's budget. The spark edge means this and nothing else.
 */
export function AiButton({ variant = "secondary", small = false, children, type = "button", className = "", ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof AI_VARIANT;
  small?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type={type}
      title={t("research.aiActionTitle")}
      data-ai-action="true"
      className={`inline-flex items-center gap-1.5 rounded-control border font-semibold whitespace-nowrap transition-[box-shadow] duration-[var(--duration-confirm)] disabled:opacity-50 ${small ? "min-h-8 px-3 text-[13px] leading-5" : "min-h-9 px-3.5 text-sm"} ${AI_VARIANT[variant]} ${FOCUS} ${className}`}
      {...rest}
    >
      <Sparkle size={15} />
      {children}
    </button>
  );
}

const TONE = {
  running: "text-status-running bg-status-running-wash border-status-running/35",
  you: "text-status-you-ink bg-status-you-wash border-status-you-ink/40 font-semibold",
  world: "text-status-world bg-status-world-wash border-status-world/35",
  fault: "text-status-fault bg-status-fault-wash border-status-fault/40",
  done: "text-status-done bg-surface-sunken border-border",
  neutral: "text-ink-muted bg-surface-sunken border-border",
} as const satisfies Record<Tone, string>;

const GLYPH: Record<Tone, IconName> = {
  running: "running", you: "you", world: "world", fault: "fault", done: "done", neutral: "dot",
};

/** A status, drawn: glyph and label always, so colour is never the only cue. */
/**
 * One row of a section (v73 X1's well item): a tone below the sheet, no border; its mono id at
 * the left, its text, its actions at the right. A list item: its section's list is the caller's.
 */
export function WellItem({ id, actions, children }: { id?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-start gap-3 rounded-sm bg-surface-sunken px-3 py-2 text-sm">
      {id ? <span data-well-id className="mt-px shrink-0 font-mono text-xs text-ink-faint">{id}</span> : null}
      <div className="min-w-0 flex-1">{children}</div>
      {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
    </li>
  );
}

/** A failure said where it happened: the one alert box (fault wash, its words in Czech, errorText's
 *  technical detail after them). Spacing around it is the caller's. */
export function FaultNote({ children, className = "", ...rest }: ComponentProps<"p">) {
  return <p role="alert" className={`rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault ${className}`} {...rest}>{children}</p>;
}

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span data-tone={tone} className={`inline-flex min-h-6 items-center gap-1 rounded-control border px-2 text-xs font-medium leading-4 ${TONE[tone]}`}>
      <Icon name={GLYPH[tone]} size={12} />
      {children}
    </span>
  );
}

/** A plain label chip: a tag, a stage, a provider. No status meaning. */
export function Tag({ children, icon }: { children: ReactNode; icon?: IconName }) {
  return (
    <span className="inline-flex min-h-6 items-center gap-1 rounded-control border border-border bg-surface-raised px-2 text-xs font-medium leading-4 text-ink-muted">
      {icon ? <Icon name={icon} size={12} /> : null}
      {children}
    </span>
  );
}

export function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span className="text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

const CONTROL = `min-h-9 min-w-0 rounded-sm border border-border-strong bg-surface-raised px-2.5 text-sm text-ink placeholder:text-ink-faint ${FOCUS}`;

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${props.className ?? "w-full"}`} />;
}

/** A text field; `ref` is an ordinary prop in React 19 (a range's inputs are read on "Použít interval"). */
export function TextInput(props: ComponentProps<"input">) {
  return <input {...props} className={`${CONTROL} ${props.className ?? "w-full"}`} />;
}

export function TextArea(props: ComponentProps<"textarea">) {
  return <textarea {...props} className={`${CONTROL} min-h-24 py-2 leading-6 ${props.className ?? "w-full"}`} />;
}

export type Ask =
  | {
      kind: "confirm";
      message: string;
      resolve: (ok: boolean) => void;
      /** A consequential yes, named by its action: the focus starts on Zrušit, the safe choice (I7). */
      yes?: string;
    }
  | {
      kind: "prompt";
      message: string;
      initial: string;
      resolve: (value: string | null) => void;
      /** The dialog's heading, above the field's label (`message`). */
      title?: string;
      placeholder?: string;
      /** What OK does, in words ("Založit klienta"); "OK" when unset. */
      yes?: string;
      /** A blank answer is refused in the dialog, said under the field, never closed silently. */
      required?: boolean;
    };

/**
 * confirm() and prompt(), as a modal <dialog>: the classic screen's questions,
 * word for word, without the browser's chrome. Esc and "Zrušit" cancel.
 */
export function AskDialog({ ask, onDone }: { ask: Ask | null; onDone: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  // A layout effect: the dialog opens in the same commit that mounts its form,
  // so the form is never on the page inside a closed (hidden) dialog, where a
  // prompt that follows another could not be answered yet.
  useLayoutEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (ask && !d.open) d.showModal();
    if (!ask && d.open) d.close();
  }, [ask]);

  const finish = (ok: boolean, value: string) => {
    if (!ask) return;
    if (ask.kind === "confirm") ask.resolve(ok);
    else ask.resolve(ok ? value : null);
    onDone();
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        finish(false, "");
      }}
      // Esc answers this question alone: a drawer or inspector beneath never sees it (D21).
      onKeyDown={(e) => {
        if (e.key === "Escape") e.stopPropagation();
      }}
      aria-labelledby={ask?.kind === "prompt" && ask.title ? `ask-${askKey(ask)}-title` : undefined}
      className="m-auto w-[min(35rem,calc(100vw-2rem))] rounded-panel bg-surface-overlay p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-ink/10 backdrop:backdrop-blur-[2px]"
    >
      {/* Mounted per question (keyed by it), so a prompt starts from its own initial value
          even when it follows another without the dialog closing in between. */}
      {ask ? <AskForm key={askKey(ask)} ask={ask} finish={finish} /> : null}
    </dialog>
  );
}

const askKeys = new WeakMap<Ask, number>();
let askSeq = 0;
function askKey(ask: Ask): number {
  let k = askKeys.get(ask);
  if (k === undefined) askKeys.set(ask, (k = ++askSeq));
  return k;
}

function AskForm({ ask, finish }: { ask: Ask; finish: (ok: boolean, value: string) => void }) {
  const [value, setValue] = useState(ask.kind === "prompt" ? ask.initial : "");
  // Each refused attempt remounts the alert, so a second blank submit is announced again.
  const [tried, setTried] = useState(0);
  const blank = ask.kind === "prompt" && !!ask.required && !value.trim();
  const fieldId = useId();
  const hintId = useId();
  const field = useRef<HTMLInputElement>(null);
  return (
    <form
      method="dialog"
      className="flex flex-col gap-4 p-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (blank) {
          setTried((n) => n + 1);
          field.current?.focus();
          return;
        }
        finish(true, value);
      }}
    >
      {ask.kind === "prompt" && ask.title ? (
        <h2 id={`ask-${askKey(ask)}-title`} className="text-base font-semibold">
          {ask.title}
        </h2>
      ) : null}
      {ask.kind === "prompt" ? (
        <label htmlFor={fieldId} className="text-sm leading-6">
          {ask.message}
        </label>
      ) : (
        <p className="text-sm leading-6">{ask.message}</p>
      )}
      {ask.kind === "prompt" ? (
        <TextInput
          id={fieldId}
          ref={field}
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={ask.placeholder}
          aria-invalid={tried > 0 && blank ? true : undefined}
          aria-describedby={tried > 0 && blank ? hintId : undefined}
        />
      ) : null}
      {tried > 0 && blank ? (
        <p key={tried} id={hintId} role="alert" className="-mt-2 text-sm text-status-fault">
          {t("dialog.required")}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button variant="quiet" autoFocus={ask.kind === "confirm" && !!ask.yes} onClick={() => finish(false, value)}>
          {t("dialog.cancel")}
        </Button>
        <Button variant="primary" type="submit" autoFocus={ask.kind === "confirm" && !ask.yes}>
          {ask.yes || t("dialog.ok")}
        </Button>
      </div>
    </form>
  );
}

/** One polite live region: what an action did, said once and gone. */
export function Toast({ message }: { message: string | null }) {
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center">
      {message ? (
        <div className="rounded-md border border-border-strong bg-surface-inverse px-4 py-2 text-sm text-ink-inverse shadow-[var(--shadow-overlay)]">
          {message}
        </div>
      ) : null}
    </div>
  );
}
