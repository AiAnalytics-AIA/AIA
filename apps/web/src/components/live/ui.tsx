"use client";

import { ReactNode } from "react";

import { ApiError, Unauthenticated } from "@/lib/api";
import { login } from "@/lib/auth";
import { t } from "@/i18n/t";

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {action}
      </div>
      <div className="p-4 text-sm text-zinc-700">{children}</div>
    </section>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  kind = "primary",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  kind?: "primary" | "secondary";
}) {
  const classes =
    kind === "primary"
      ? "bg-zinc-900 text-white hover:bg-zinc-800 disabled:bg-zinc-400"
      : "border border-zinc-200 text-zinc-800 hover:bg-zinc-50 disabled:text-zinc-400";
  return (
    <button
      type="button"
      className={`rounded-md px-3 py-1.5 text-xs font-semibold ${classes}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

const TONES: Record<string, string> = {
  COMPLETED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  SUCCEEDED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  RUNNING: "bg-blue-50 text-blue-800 border-blue-200",
  EXECUTING: "bg-blue-50 text-blue-800 border-blue-200",
  RUNNABLE: "bg-blue-50 text-blue-800 border-blue-200",
  PENDING: "bg-zinc-100 text-zinc-700 border-zinc-200",
  FAILED: "bg-red-50 text-red-800 border-red-200",
  RECOVERY_REQUIRED: "bg-red-50 text-red-800 border-red-200",
  AWAITING_GATE: "bg-amber-50 text-amber-800 border-amber-200",
  AWAITING_BUDGET: "bg-amber-50 text-amber-800 border-amber-200",
  WAITING_PROVIDER: "bg-amber-50 text-amber-800 border-amber-200",
  WAITING_CAPACITY: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-zinc-100 text-zinc-600 border-zinc-200",
};

/** A status as the server states it. The mapping is colour only; no rule lives here. */
export function Status({ value }: { value: string }) {
  const tone = TONES[value] ?? "bg-zinc-100 text-zinc-700 border-zinc-200";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-xs ${tone}`}>
      {value}
    </span>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  if (error instanceof Unauthenticated) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        {t("live.sessionExpired")}{" "}
        <button className="underline" onClick={() => void login(window.location.pathname)}>
          {t("live.signIn")}
        </button>
      </div>
    );
  }
  const message = error instanceof ApiError ? `${error.code}: ${error.message}` : String(error);
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
      {message}
      {requestId ? <span className="ml-2 font-mono text-xs text-red-700">request {requestId}</span> : null}
    </div>
  );
}

export function Loading() {
  return <div className="text-sm text-zinc-500">{t("live.loading")}</div>;
}
