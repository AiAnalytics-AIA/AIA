"use client";

// I5: a new thing is created in the list, where it will appear. "+ Nová složka" becomes a row
// with its input focused; Enter creates and opens the next empty row (ten folders are ten Enters);
// Esc, or leaving it empty, cancels and gives focus back to "+". Length and uniqueness are checked
// at the row as the person types; a refusal from the server is said at the same row (I9), with
// the name kept. Reference: `AddItem`, prototypes/research-lead-v2/src/components/ui.tsx:108.

import { type ReactNode, useId, useRef, useState } from "react";

import { t } from "@/i18n/t";
import { NAME_MAX, cleanName, nameProblem, nameProblemWords } from "@/lib/name-input";
import { Icon, type IconName } from "../rehome/icons";
import { FIELD_ERROR, FOCUS } from "./parts";

export function InlineCreateRow({
  label, onCreate, existing = [], maxLength = NAME_MAX, icon = "plus", placeholder, next = true, disabled = false, adornment, className = "",
}: {
  /** The action and the field's name ("Nová složka"). */
  label: string;
  /**
   * Creates the thing. Resolves to nothing (or true) when it was created; to a string, the
   * refusal in words, to say at the row; a rejection or a synchronous throw is said as "Nevytvořeno".
   */
  onCreate: (name: string) => Promise<string | boolean | void> | string | boolean | void;
  /** The names already in the list: one equal to the typed name, case and spacing aside, is refused. */
  existing?: readonly string[];
  maxLength?: number;
  /** The icon of the row while it is typed in (the thing it makes: a folder, a file). */
  icon?: IconName;
  placeholder?: string;
  /** false: the row closes after one creation instead of opening the next. */
  next?: boolean;
  disabled?: boolean;
  /**
   * A control inside the row beside the name, chosen with it (a new label's swatch). Moving to it
   * is not leaving the row: an empty row closes only when focus leaves the row as a whole.
   */
  adornment?: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const errorId = useId();
  const hintId = useId();

  const problem = nameProblem(draft, existing, maxLength);
  // An empty row is said only once the person tried to create it; a taken or too long name at once.
  const shown: string | null = refusal ?? (problem && (problem.kind !== "empty" || submitted) ? nameProblemWords(problem) : null);

  // Each creation is numbered, and closing the row ends the current one: an answer that comes
  // back for a row already left (Esc while it was creating) sets nothing on the row reopened
  // after it (the sweep after Codex on #532).
  const latest = useRef(0);

  const close = (refocus = true) => {
    latest.current++;
    setOpen(false);
    setDraft("");
    setRefusal(null);
    setSubmitted(false);
    setBusy(false);
    // Focus goes back to "+" after Esc or a creation that closes the row (I11); a blur leaves it
    // where the person put it (review of #532, P2-3).
    if (refocus) requestAnimationFrame(() => trigger.current?.focus());
  };

  const create = async () => {
    setSubmitted(true);
    if (problem || busy) return;
    const name = cleanName(draft);
    const op = ++latest.current;
    setBusy(true);
    let answer: string | boolean | void;
    try {
      answer = await onCreate(name);
    } catch {
      answer = t("input.name.failed");
    }
    if (op !== latest.current) return;
    setBusy(false);
    if (typeof answer === "string") {
      setRefusal(answer);
      requestAnimationFrame(() => input.current?.focus());
      return;
    }
    if (answer === false) {
      setRefusal(t("input.name.failed"));
      return;
    }
    if (!next) {
      close();
      return;
    }
    setDraft("");
    setRefusal(null);
    setSubmitted(false);
    requestAnimationFrame(() => input.current?.focus());
  };

  if (!open) {
    return (
      <button
        ref={trigger}
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className={`inline-flex min-h-8 w-full items-center gap-1.5 rounded-control border border-dashed border-border px-2 text-left text-[13px] text-ink-muted hover:border-border-strong hover:text-ink disabled:opacity-50 ${FOCUS} ${className}`}
      >
        <Icon name="plus" size={14} />
        {label}
      </button>
    );
  }

  return (
    <div
      className={`flex min-w-0 flex-col gap-1 ${className}`}
      onBlur={(e) => {
        // Leaving for the adornment is not leaving the row.
        if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
        if (!cleanName(draft) && !busy) close(false);
      }}
    >
      <div
        className={`flex min-h-8 items-center gap-1.5 rounded-control border px-2 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring ${shown ? FIELD_ERROR : "border-border-strong bg-surface-raised"}`}
      >
        <Icon name={icon} size={14} className="text-ink-faint" />
        <input
          ref={input}
          autoFocus
          aria-label={label}
          aria-invalid={shown ? true : undefined}
          aria-describedby={shown ? errorId : hintId}
          placeholder={placeholder ?? label}
          value={draft}
          readOnly={busy}
          onChange={(e) => {
            setDraft(e.target.value);
            setRefusal(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void create();
            } else if (e.key === "Escape") {
              e.preventDefault();
              close();
            }
          }}
          className="min-h-7 min-w-0 flex-1 border-0 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-faint"
        />
        {adornment}
        {busy ? <span aria-live="polite" className="text-xs text-ink-faint">{t("input.saving")}</span> : null}
      </div>
      {shown ? (
        <span id={errorId} role="alert" className="text-xs leading-4 text-status-fault">{shown}</span>
      ) : (
        <span id={hintId} className="text-xs leading-4 text-ink-faint">{t("input.name.createHint")}</span>
      )}
    </div>
  );
}
