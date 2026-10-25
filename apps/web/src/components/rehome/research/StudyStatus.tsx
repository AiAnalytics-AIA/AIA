"use client";

// A study's status, changed on the study (fidelity F7): the Settings table that once held a picker
// per study draws the status read-only, as the prototype does, so the study itself carries the one
// way to deliver, archive, cancel or reopen it. The API decides who may (delivery needs sign-off);
// its refusal is said as given. A change reads the study again, so what it allows follows at once.

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { admin } from "@/lib/api";
import { describeError } from "@/components/aia/settings/errors";
import { MenuButton } from "../../ui/MenuButton";

/** Every status a study takes (domain/scope.py StudyStatus), in the order the menu lists them. */
const STUDY_STATUSES = ["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED", "ARCHIVED", "CANCELLED"] as const;
/** The statuses that accept work again: what reopening a closed study offers. */
const OPEN_STATUSES = ["DRAFT", "ACTIVE", "IN_REVIEW"] as const;

/** The statuses a study at `status` may be moved to: every other one. */
export const otherStatuses = (status: string): string[] => STUDY_STATUSES.filter((s) => s !== status);

/**
 * A status change and what it answered: busy while asked, the API's refusal said as given. A typed
 * change still owed is saved first (`beforeChange`, the store's flush): a study about to close would
 * refuse it after, so it is saved or the change of status is refused with the reason, never dropped.
 */
export function useStudyStatus(studyId: string, onChanged: () => Promise<void> | void, beforeChange?: () => Promise<unknown>, hold?: (on: boolean) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const change = async (status: string) => {
    // The whole change -- the save, the status, the study read again -- holds the editor read-only, so
    // nothing typed meanwhile lands in a store the change is about to replace (Codex on #892).
    setBusy(true); setError(null); hold?.(true);
    try { await beforeChange?.(); await admin.setStudyStatus(studyId, status); await onChanged(); }
    catch (e) { setError(describeError(e)); }
    finally { setBusy(false); hold?.(false); }
  };
  const shown = error ? <p role="alert" className="mt-1 text-xs text-status-fault">{error}</p> : null;
  return { busy, change, shown };
}

/** The study header's status: its name on the button, every other status in its menu. */
export function StudyStatusMenu({ studyId, status, onChanged, beforeChange, hold }: {
  studyId: string; status: string; onChanged: () => Promise<void> | void; beforeChange?: () => Promise<unknown>; hold?: (on: boolean) => void;
}) {
  const { busy, change, shown } = useStudyStatus(studyId, onChanged, beforeChange, hold);
  return (
    <span data-study-status={status} className="inline-flex flex-col items-end">
      <MenuButton label={tv("aia.study.status.label", { status: t(`aia.status.${status}`) })} align="end" disabled={busy}
        items={otherStatuses(status).map((s) => ({ key: s, label: t(`aia.status.${s}`) }))}
        onSelect={(s) => void change(s)} />
      {shown}
    </span>
  );
}

/** "Znovu otevřít" on a closed study's notice: the statuses that accept work again, in place. */
export function ReopenStudy({ studyId, onChanged, hold }: { studyId: string; onChanged: () => Promise<void> | void; hold?: (on: boolean) => void }) {
  const { busy, change, shown } = useStudyStatus(studyId, onChanged, undefined, hold);
  return (
    <span data-study-reopen className="inline-flex flex-col items-start">
      <MenuButton label={t("aia.study.closed.reopen")} disabled={busy}
        items={OPEN_STATUSES.map((s) => ({ key: s, label: t(`aia.status.${s}`) }))}
        onSelect={(s) => void change(s)} />
      {shown}
    </span>
  );
}
