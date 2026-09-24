"use client";

// The rebuilt interface's primitives. Token utilities only (bg-surface, text-ink,
// border-border-strong, rounded-sm/md = 2/4 px): no raw colour, radius, shadow
// or font here or in anything built on them. Components map a value to an
// appearance; what the value is, src/unit/ decides.

import {
  type ButtonHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type InputHTMLAttributes,
  type TextareaHTMLAttributes,
  useEffect, useRef, useState,
} from "react";

import type { Tone } from "@/unit/projects";
import { t } from "@/i18n/t";
import { Icon, type IconName } from "./icons";

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

/**
 * A link out of the rebuilt interface into the classic one: a full document
 * load (not next/link), marked with the external glyph and said aloud, so a
 * person always knows which interface they are about to be in.
 */
export function ClassicLink({ href, children, variant = "quiet", small = false, icon }: {
  href: string; children: ReactNode; variant?: keyof typeof VARIANT; small?: boolean; icon?: IconName;
}) {
  return (
    <a
      href={href}
      className={`inline-flex items-center gap-1.5 rounded-sm border font-medium whitespace-nowrap no-underline ${small ? "min-h-7 px-2 text-xs" : "min-h-9 px-3 text-sm"} ${VARIANT[variant]} ${FOCUS}`}
    >
      {icon ? <Icon name={icon} size={small ? 14 : 16} /> : null}
      {children}
      <Icon name="external" size={12} className="opacity-60" />
      <span className="sr-only"> ({t("rehome.inClassic")})</span>
    </a>
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
export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span data-tone={tone} className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-xs leading-4 ${TONE[tone]}`}>
      <Icon name={GLYPH[tone]} size={12} />
      {children}
    </span>
  );
}

/** A plain label chip: a tag, a stage, a provider. No status meaning. */
export function Tag({ children, icon }: { children: ReactNode; icon?: IconName }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-sm border border-border bg-surface px-1.5 py-0.5 text-xs leading-4 text-ink-muted">
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

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? "w-full"}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${CONTROL} min-h-24 py-2 leading-6 ${props.className ?? "w-full"}`} />;
}

export type Ask =
  | { kind: "confirm"; message: string; resolve: (ok: boolean) => void }
  | { kind: "prompt"; message: string; initial: string; resolve: (value: string | null) => void };

/**
 * confirm() and prompt(), as a modal <dialog>: the classic screen's questions,
 * word for word, without the browser's chrome. Esc and "Zrušit" cancel.
 */
export function AskDialog({ ask, onDone }: { ask: Ask | null; onDone: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
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
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-md border border-border-strong bg-surface-overlay p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-surface-inverse/40"
    >
      {/* Mounted per question, so a prompt starts from its own initial value. */}
      {ask ? <AskForm ask={ask} finish={finish} /> : null}
    </dialog>
  );
}

function AskForm({ ask, finish }: { ask: Ask; finish: (ok: boolean, value: string) => void }) {
  const [value, setValue] = useState(ask.kind === "prompt" ? ask.initial : "");
  return (
    <form
      method="dialog"
      className="flex flex-col gap-4 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        finish(true, value);
      }}
    >
      <p className="text-sm leading-6">{ask.message}</p>
      {ask.kind === "prompt" ? (
        <TextInput autoFocus value={value} onChange={(e) => setValue(e.target.value)} aria-label={ask.message} />
      ) : null}
      <div className="flex justify-end gap-2">
        <Button variant="quiet" onClick={() => finish(false, value)}>
          {t("projects.cancel")}
        </Button>
        <Button variant="primary" type="submit" autoFocus={ask.kind === "confirm"}>
          {t("projects.ok")}
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
