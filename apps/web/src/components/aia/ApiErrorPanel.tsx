import type { ApiError } from "@/lib/api/client";
import { t } from "@/i18n/t";

/**
 * An API failure, stated as one. Never replaced by fixture data, never rendered
 * as an empty list: "we could not ask" and "the answer is nothing" look different.
 */
export function ApiErrorPanel({ error }: { error: ApiError }) {
  return (
    <div role="alert" data-api-error={error.kind} className="rounded-md border border-status-fault bg-surface-raised px-4 py-3 text-sm">
      <div className="font-semibold text-ink">{t(`api.title.${error.kind}`)}</div>
      <p className="mt-1 text-ink-muted">{t(`api.recovery.${error.kind}`)}</p>
      <dl className="mt-2 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-muted">
        <dt>{t("api.path")}</dt>
        <dd className="break-all font-mono">{error.path}</dd>
        {error.status != null ? (
          <>
            <dt>{t("api.status")}</dt>
            <dd className="font-mono">{error.status}{error.code ? ` · ${error.code}` : ""}</dd>
          </>
        ) : null}
        {error.requestId ? (
          <>
            <dt>{t("api.requestId")}</dt>
            <dd className="break-all font-mono">{error.requestId}</dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}
