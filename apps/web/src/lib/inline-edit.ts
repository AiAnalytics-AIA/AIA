// Editing a shown value where it is shown (input-interactions I1, I9, I10): the pure part of
// InlineText. Which key saves, which restores, and what a draft becomes before it is saved.

import { t, tv } from "@/i18n/t";

export type EditKey = { key: string; ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean };

/** What a key does while editing: Enter saves (Ctrl/Cmd+Enter in multi-line text), Esc restores. */
export function editKeyAction(e: EditKey, multiline: boolean): "commit" | "cancel" | null {
  if (e.key === "Escape") return "cancel";
  if (e.key !== "Enter") return null;
  if (multiline) return e.ctrlKey || e.metaKey ? "commit" : null;
  return e.shiftKey ? null : "commit";
}

/** Whether a key on the shown value opens it for editing: Enter or F2 (Space is the button's own). */
export function opensEdit(key: string): boolean {
  return key === "Enter" || key === "F2";
}

export type TextRules = {
  /** Default true: an empty value is refused at the field, never saved as "". */
  required?: boolean;
  maxLength?: number;
  /** A further rule of the caller's, in words; null when the draft passes. */
  validate?: (value: string) => string | null;
};

/**
 * A draft as it would be saved: trimmed (a single line also collapses inner runs of spaces, a
 * multi-line text keeps its lines). `problem` is why it is not saved, in words, or null.
 */
export function readDraft(draft: string, multiline: boolean, rules: TextRules = {}): { value: string; problem: string | null } {
  const value = multiline ? draft.trim() : draft.split(/\s+/).filter(Boolean).join(" ");
  if (!value && rules.required !== false) return { value, problem: t("input.required") };
  if (rules.maxLength !== undefined && value.length > rules.maxLength) return { value, problem: tv("input.tooLong", { max: rules.maxLength }) };
  return { value, problem: rules.validate?.(value) ?? null };
}

export type SaveState = "idle" | "saving" | "saved" | "failed";
