"use client";

// The states every client-first page can be in besides "ready", drawn the same way.

import Link from "next/link";
import type { ReactNode } from "react";

import { t } from "@/i18n/t";
import { appRoutes } from "@/lib/app-routes";
import { Button } from "../rehome/ui";
import type { Resource } from "./useResource";

export const CARD = "rounded-md border border-border bg-surface-raised p-5";
export const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";

export function NotFound() {
  return (
    <section className={`${CARD} max-w-xl`} aria-labelledby="nf">
      <h2 id="nf" className="text-lg font-semibold">{t("aia.notFoundTitle")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("aia.notFoundText")}</p>
      <Link href={appRoutes.clients()} className="mt-4 inline-block text-sm font-medium text-signal underline">
        {t("aia.backToClients")}
      </Link>
    </section>
  );
}

/** Loading, not found, failed with a retry -- or the ready content. */
export function Loaded<T>({ res, retry, children }: { res: Resource<T>; retry: () => void; children: (data: T) => ReactNode }) {
  if (res.state === "loading") return <p className="py-10 text-sm text-ink-muted">{t("aia.loading")}</p>;
  if (res.state === "not-found") return <NotFound />;
  if (res.state === "failed") {
    return (
      <section role="alert" className="max-w-xl rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
        <h2 className="font-semibold text-status-fault">{t("aia.loadFailed")}</h2>
        <p className="mt-1 text-sm text-ink">{res.message}</p>
        <Button className="mt-3" onClick={retry}>{t("aia.retry")}</Button>
      </section>
    );
  }
  return <>{children(res.data)}</>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-sm border border-dashed border-border-strong p-4 text-sm text-ink-muted">{children}</p>;
}
