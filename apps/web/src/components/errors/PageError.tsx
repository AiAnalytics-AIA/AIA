"use client";

import Link from "next/link";
import { useEffect } from "react";

import { reportError } from "@/lib/error-tracking";
import { t } from "@/i18n/t";

// What a person sees when a page crashed while rendering: said plainly, with the way back
// and the reference that finds the report. The crash itself is reported once, here.
export function PageError({
  error,
  reset,
  boundary,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  boundary: string;
}) {
  useEffect(() => {
    reportError(error, { boundary, ...(error.digest ? { digest: error.digest } : {}) });
  }, [error, boundary]);

  return (
    <main className="mx-auto flex min-h-[60dvh] max-w-xl flex-col justify-center gap-4 px-6 py-12 text-ink">
      <h1 className="text-xl font-semibold">{t("pageError.title")}</h1>
      <p className="leading-relaxed text-ink-muted">{t("pageError.text")}</p>
      {error.digest ? (
        <p className="text-sm text-ink-muted">
          {t("pageError.reference")} <code className="font-mono">{error.digest}</code>
        </p>
      ) : null}
      <div className="flex flex-wrap gap-4">
        <button
          type="button"
          onClick={reset}
          className="inline-flex min-h-9 items-center font-medium text-signal underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          {t("pageError.retry")}
        </button>
        <Link
          href="/app/clients"
          className="inline-flex min-h-9 items-center font-medium text-signal underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          {t("pageError.home")}
        </Link>
      </div>
    </main>
  );
}
