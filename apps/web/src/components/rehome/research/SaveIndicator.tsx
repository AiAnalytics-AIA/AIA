"use client";

// The study's save state, always visible: where the classic interface only
// logged a failed save to the console (scheduleServerSave), a person sees it
// here and can retry. A save refused because someone else saved first is said
// too, with a way to load their version (ADR 0018): nothing is overwritten. So is a change to a
// locked Sociomap input, put back as it was saved (ADR 0029 decision 8).

import { t } from "@/i18n/t";
import type { SaveState } from "@/research/store";
import { Button } from "../ui";
import { Icon } from "../icons";

export function SaveIndicator({ save, onRetry, onReload }: { save: SaveState; onRetry: () => void; onReload?: () => void }) {
  if (save.kind === "conflict") {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash px-2.5 py-1 text-xs text-status-fault">
        <Icon name="fault" size={12} />
        <span className="font-semibold">{t("research.saveConflict")}</span>
        {onReload ? <Button small variant="secondary" onClick={onReload}>{t("research.saveReload")}</Button> : null}
      </div>
    );
  }
  if (save.kind === "closed") {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash px-2.5 py-1 text-xs text-status-fault">
        <Icon name="fault" size={12} />
        <span className="font-semibold">{t("research.saveClosed")}</span>
        {onReload ? <Button small variant="secondary" onClick={onReload}>{t("research.saveReload")}</Button> : null}
      </div>
    );
  }
  if (save.kind === "locked") {
    // A locked Sociomap input (ADR 0029 decision 8): put back as saved, or, when it could not be
    // found again, nothing more is saved until the study is reloaded.
    return (
      <div role="alert" className="flex items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash px-2.5 py-1 text-xs text-status-fault">
        <Icon name="fault" size={12} />
        <span className="font-semibold">{t(save.reverted ? "research.saveLockedReverted" : "research.saveLocked")}</span>
        {save.reverted ? <Button small variant="secondary" onClick={onRetry}>{t("research.saveLockedSave")}</Button>
          : onReload ? <Button small variant="secondary" onClick={onReload}>{t("research.saveReload")}</Button> : null}
      </div>
    );
  }
  if (save.kind === "failed") {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash px-2.5 py-1 text-xs text-status-fault">
        <Icon name="fault" size={12} />
        <span className="font-semibold">{t("research.saveFailed")}</span>
        <span className="max-w-64 truncate text-ink" title={save.message}>{save.message}</span>
        <Button small variant="secondary" onClick={onRetry}>{t("research.saveRetry")}</Button>
      </div>
    );
  }
  const label =
    save.kind === "readonly" ? t("research.saveReadOnly")
    : save.kind === "new" ? t("research.saveNew")
    : save.kind === "saved" ? t("research.saveSaved")
    : save.kind === "saving" ? t("research.saveSaving")
    : t("research.savePending");
  return (
    <span aria-live="polite" className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
      <Icon name={save.kind === "saved" ? "done" : "dot"} size={12} />
      {label}
    </span>
  );
}
